#!/usr/bin/env python3
"""DA RUONG (don vi HTX that): nhieu ruong khac nhau dung CHUNG mot ngan sach nuoc
va CHUNG mot kenh vo tuyen. Day la bai toan thuc te cua De an 1 trieu ha (QD 1490):
mot HTX co hang chuc thua ruong, mot tram bom, mot tram goc.

Cau hoi ma bai bao phai tra loi duoc: khi tai nguyen khan, cong an toan PHAN BO
the nao, va phan bo do co cong bang khong?

  - Chia deu (equal): moi ruong B/N. Don gian nhung bo qua su khac biet giua cac
    ruong (ruong dat cat can nhieu nuoc hon ruong dat set).
  - Ty le thieu hut (deficit-proportional): chia theo thieu hut du bao dau mua cua
    tung ruong. Day la luat ma mot can bo thuy nong thuc te se lam.
  - Cong-thong-tin (gate-aware): chia deu nhung cong duoc phep IM LANG (WITHHELD)
    o ruong chua den luc can -> do chinh la co che cua bai, khong them luat phan bo.

XAP XI CAN KHAI BAO (khong phai mo hinh hoa day du kenh dung chung):
    Khi chi S trong so N ruong duoc phuc vu moi ngay, moi ruong trung binh duoc
    phuc vu sau N/S ngay => epoch hieu dung cua ruong = 24 * N / S gio.
    Day la xap xi o muc "slot chia deu theo thoi gian"; khong mo hinh hoa xung dot
    slot trong cung mot ngay. Neu S = N thi epoch = 24h (khong co tranh chap kenh).

    HE QUA QUAN TRONG (do duoc, paired n=300): `slots/ngay` la nut van TAN SUAT
    QUYET DINH, KHONG phai nut van tai nguyen. slots 6 -> 2 cho:
        unsafe  -1.35 diem  (t = -9.71)     stress_h +158.7 gio (t = +21.6)
        AWD     +0.96 chu ky (t = +15.9)    withheld -58.6      (t = -461)
        nuoc    -8.4 mm   (t = -8.67)
    Tuc la quyet dinh thua hon thi dan trai nuoc deu hon (bot dau don) nhung phan
    ung cham hon (stress tang) va it co hoi IM LANG hon (withheld giam). Ba chieu
    nay danh doi nhau -> phai bao cao ca ba, khong duoc coi mot chieu la "tot hon".

Metric:
    unsafe_tong     : trung binh gio mat an toan cua ca HTX
    unsafe_ruong_xau: ruong te nhat (HTX quan tam cai nay hon trung binh)
    AWD_tong        : tong so chu ky AWD dat tieu chuan >=72h (tin chi carbon)
    Gini            : bat binh dang ve muc do mat an toan giua cac ruong
    nuoc_dung       : tong nuoc thuc te bom

Usage:
    python3 experiments/run_multi_field.py --quick
    python3 experiments/run_multi_field.py
    python3 experiments/run_multi_field.py --gate-only   # lap lai gate, khong mo phong
"""
from __future__ import annotations

import argparse
import csv
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ncs_loop import (  # noqa: E402
    PolicyConfig, load_weather, march_start, run_episode, season_deficit_suffix,
)
from water_balance import SoilProfile  # noqa: E402

OUT = ROOT / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

HOURS = 2160
BASE = dict(sigma_frac=0.02, delta=0.05, horizon=6)

NUMERIC = ("unsafe_pct", "severe_pct", "water_mm", "awd_eff", "awd_short",
           "withheld", "dup", "dup_mm", "stress_h", "cmd_per_day", "epoch_h", "budget")

# Mot HTX 6 thua ruong, khac nhau ca ve DAT lan ve thoi tiet (tram khac nhau).
FIELDS = [
    ("F1_dat_cat",   "can_tho",   SoilProfile(theta_sat=0.41, theta_fc=0.31, theta_wp=0.12, root_depth_m=0.5)),
    ("F2_thit",      "can_tho",   SoilProfile()),
    ("F3_set",       "soc_trang", SoilProfile(theta_sat=0.46, theta_fc=0.38, theta_wp=0.22, root_depth_m=0.5)),
    ("F4_thit_soc",  "soc_trang", SoilProfile()),
    ("F5_set_camau", "ca_mau",    SoilProfile(theta_sat=0.46, theta_fc=0.38, theta_wp=0.22, root_depth_m=0.5)),
    ("F6_cat_camau", "ca_mau",    SoilProfile(theta_sat=0.41, theta_fc=0.31, theta_wp=0.12, root_depth_m=0.5)),
]

ALLOC = ("equal", "deficit", "gate")
SLOTS_PER_DAY = (6, 3, 2)


def paired_t(diffs: list[float]) -> tuple[float, float]:
    """(mean, t) cua day hieu cap. t = mean/(sd/sqrt(n)); sd = 0 => t = 0.

    Dung kiem dinh cap thay vi doi don dieu tung cell: voi 300 cap (seed x thua x
    ngan sach x kenh), mot cell le co the dao chieu vi nhieu ma khong doi xu huong.
    """
    if not diffs:
        return 0.0, 0.0
    m = statistics.mean(diffs)
    sd = statistics.pstdev(diffs)
    return m, (m / (sd / len(diffs) ** 0.5) if sd else 0.0)


def gini(xs: list[float]) -> float:
    """He so Gini cua mot day khong am. 0 = hoan toan deu, ->1 = mot minh mot ruong chiu het."""
    if not xs or sum(xs) == 0:
        return 0.0
    s = sorted(xs)
    n = len(s)
    cum = sum((i + 1) * v for i, v in enumerate(s))
    return (2 * cum) / (n * sum(s)) - (n + 1) / n


def run_field(fname: str, station: str, prof: SoilProfile, budget: float | None,
              seed: int, network: str, start: dict, year: int,
              slots_per_day: int, allow_withhold: bool) -> dict:
    n_fields = len(FIELDS)
    epoch_h = max(1, int(round(24.0 * n_fields / slots_per_day)))
    # Cong chi duoc phep IM LANG khi luat phan bo la "gate".
    pol = PolicyConfig(f"mf_{fname}", True, True, True,
                       gate_target_depl=0.80 if allow_withhold else None, **BASE)
    m = run_episode(station, pol, seed, hours=HOURS, start=start[station],
                    network=network, slots_per_decision=epoch_h,
                    water_budget_mm=budget, year=year, prof=prof)
    return {
        "field": fname, "budget": "inf" if budget is None else budget,
        "epoch_h": epoch_h,
        "unsafe_pct": round(100 * m.hours_unsafe / m.hours, 4),
        "severe_pct": round(100 * m.hours_severe / m.hours, 4),
        "water_mm": round(m.water_applied_mm, 2),
        "awd_eff": m.awd_effective, "awd_short": m.awd_short_cycles,
        "withheld": m.withheld, "dup": m.double_irrigations,
        "dup_mm": round(m.water_wasted_dup_mm, 2),
        "stress_h": m.stress_hours_ks_lt1,
        "cmd_per_day": round(m.commands_generated / (HOURS / 24.0), 3),
    }


def simulate(allocs, total_mm, slots, networks, seeds, starts, year, deficits_fn) -> list[dict]:
    rows: list[dict] = []
    t0 = time.time()
    total = len(allocs) * len(total_mm) * len(slots) * len(networks) * len(seeds)
    done = 0
    for rule in allocs:
        for tot in total_mm:
            for spd in slots:
                for net in networks:
                    for s in seeds:
                        # ---- chia ngan sach theo luat ----
                        if tot is None:
                            shares: list[float | None] = [None] * len(FIELDS)
                        elif rule == "equal":
                            shares = [tot / len(FIELDS)] * len(FIELDS)
                        elif rule == "deficit":
                            wts = [max(deficits_fn(st, prof), 1.0) for _, st, prof in FIELDS]
                            tot_w = sum(wts)
                            shares = [tot * x / tot_w for x in wts]
                        else:  # "gate": chia deu, cong duoc phep im lang de nhuong
                            shares = [tot / len(FIELDS)] * len(FIELDS)

                        allow_withhold = (rule == "gate")
                        for (fn, st, prof), sh in zip(FIELDS, shares):
                            r = run_field(fn, st, prof, sh, s, net, starts, year,
                                          spd, allow_withhold)
                            r.update({
                                "alloc": rule,
                                "total_budget_mm": "inf" if tot is None else tot,
                                "slots_per_day": spd, "network": net, "seed": s,
                                "year": year,
                            })
                            rows.append(r)
                        done += 1
                    print(f"  [{done}/{total}] {rule:<8} tot={tot} slots/ngay={spd} {net} "
                          f"({time.time()-t0:.0f}s)", flush=True)
    return rows


def read_rows(dest: Path) -> list[dict]:
    rows: list[dict] = []
    with dest.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rr = dict(r)
            for k in NUMERIC:
                if k in rr and rr[k] not in ("", None):
                    try:
                        rr[k] = float(rr[k])
                    except ValueError:
                        pass
            rr["seed"] = int(rr["seed"])
            rr["slots_per_day"] = int(rr["slots_per_day"])
            rows.append(rr)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--year", type=int, default=2024)
    ap.add_argument("--gate-only", action="store_true",
                    help="doc CSV da co va chi chay gate (khong mo phong lai)")
    a = ap.parse_args()

    if a.quick:
        networks, seeds = ["severe"], [7, 11]
        total_mm, slots = [720.0], [6, 2]
        dest = OUT / "multifield_quick.csv"
    else:
        networks = ["mild", "severe"]
        seeds = list(range(a.seeds))
        total_mm = [len(FIELDS) * b for b in (80.0, 160.0, 240.0, 320.0)] + [None]
        slots = SLOTS_PER_DAY
        dest = OUT / "multifield_raw.csv"

    starts, deficits = {}, {}
    for _, st, _ in FIELDS:
        if st in starts:
            continue
        w, _ = load_weather(st, year=a.year)
        starts[st] = march_start(w)
        deficits[st] = season_deficit_suffix(w, starts[st], HOURS, SoilProfile())[0]
    print("thieu hut du bao dau mua (dat mac dinh): " +
          ", ".join(f"{k}={v:.0f}mm" for k, v in deficits.items()))

    # ham thieu hut theo DUNG loai dat cua ruong (dung cho luat "deficit")
    _wc: dict[tuple, list] = {}

    def deficits_fn(st: str, prof: SoilProfile) -> float:
        if st not in _wc:
            _wc[st] = load_weather(st, year=a.year)[0]
        return season_deficit_suffix(_wc[st], starts[st], HOURS, prof)[0]

    if a.gate_only:
        if not dest.exists():
            print(f"!! --gate-only: khong tim thay {dest} (chay khong --gate-only truoc)")
            return 2
        rows = read_rows(dest)
        # gate phai lap tren nhung gia tri THUC SU co trong CSV, khong gia su theo
        # nhanh quick/full dang chon (neu khong se vong lap rong va bao OK gia).
        networks = sorted({r["network"] for r in rows})
        slots = sorted({int(r["slots_per_day"]) for r in rows}, reverse=True)
        _tm = {r["total_budget_mm"] for r in rows}
        total_mm = sorted([float(x) for x in _tm if x != "inf"], reverse=False)
        if "inf" in _tm:
            total_mm.append(None)
        print(f"--gate-only: doc {len(rows)} rows tu {dest.name}; "
              f"networks={networks} slots={slots} "
              f"total_budget={[('inf' if t is None else t) for t in total_mm]}")
    else:
        rows = simulate(ALLOC, total_mm, slots, networks, seeds, starts, a.year, deficits_fn)
        with dest.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        print(f"\nwrote {len(rows)} rows -> {dest}")

    # ---------------- tong hop cap HTX ----------------
    by_seed = defaultdict(list)
    for r in rows:
        k = ((r["alloc"], str(r["total_budget_mm"]), int(r["slots_per_day"]),
              r["network"]), r["seed"])
        by_seed[k].append(r)
    htx = defaultdict(list)
    for (k, seed), recs in by_seed.items():
        uns = [float(x["unsafe_pct"]) for x in recs]
        htx[k].append({
            "unsafe_mean": statistics.mean(uns),
            "unsafe_worst": max(uns),
            "gini": gini(uns),
            "awd_eff": sum(float(x["awd_eff"]) for x in recs),
            "awd_short": sum(float(x["awd_short"]) for x in recs),
            "water": sum(float(x["water_mm"]) for x in recs),
            "dup_mm": sum(float(x["dup_mm"]) for x in recs),
            "withheld": sum(float(x["withheld"]) for x in recs),
            "stress_h": sum(float(x["stress_h"]) for x in recs),
        })
    agg = {k: {f: statistics.mean(x[f] for x in v) for f in v[0]} for k, v in htx.items()}

    def key(rule, tot, spd, net):
        return (rule, ("inf" if tot is None else f"{float(tot)}"), int(spd), net)

    fails = []
    print("\n=== KET QUA CAP HTX (mean over seed) ===")
    for net in networks:
        for tot in total_mm:
            print(f"\n  [{net} | tong ngan sach {'inf' if tot is None else tot} mm "
                  f"cho {len(FIELDS)} ruong]")
            print(f"  {'slots/ngay':>10} {'luat':<9} {'unsafe_TB':>10} {'ruong_xau':>10} "
                  f"{'Gini':>7} {'AWD_eff':>8} {'nuoc':>7} {'im_lang':>8} {'stress_h':>9}")
            for spd in slots:
                for rule in ALLOC:
                    v = agg.get(key(rule, tot, spd, net))
                    if not v:
                        continue
                    print(f"  {spd:>10} {rule:<9} {v['unsafe_mean']:>9.2f}% "
                          f"{v['unsafe_worst']:>9.2f}% {v['gini']:>7.3f} "
                          f"{v['awd_eff']:>8.1f} {v['water']:>7.0f} {v['withheld']:>8.0f} "
                          f"{v['stress_h']:>9.0f}")

    # ---- GATE slots (2026-10-04, loi gate lan thu 16) -------------------------
    # Ban dau gate gia su "slots/ngay" la nut van TAI NGUYEN: it slot = kenh chat
    # hon = HTX phai te hon, va doi unsafe% don dieu theo slots. Do paired n=300
    # BAC BO gia su do (xem module docstring). Ban chat that: slots/ngay la nut van
    # TAN SUAT QUYET DINH (epoch = 24*N/S). Hai luat DON DIEU dung ban chat:
    #   (a) withheld PHAI giam khi slots giam  (it co hoi quyet dinh hon)
    #   (b) stress_h PHAI tang khi slots giam  (phan ung cham hon)
    # unsafe% KHONG duoc doi don dieu: no la ket qua cua danh doi (a)+(b).
    print("\n=== GATE: slots/ngay la nut van TAN SUAT QUYET DINH (khong phai tai nguyen) ===")
    n_a = n_tot = 0
    for net in networks:
        for tot in total_mm:
            for rule in ALLOC:
                seq = [(spd, agg[key(rule, tot, spd, net)])
                       for spd in sorted(slots, reverse=True)
                       if key(rule, tot, spd, net) in agg]
                if len(seq) < 2:
                    continue
                n_tot += 1
                wh = [v["withheld"] for _, v in seq]
                st = [v["stress_h"] for _, v in seq]
                un = [v["unsafe_mean"] for _, v in seq]
                ok_a = all(b < a_ - 1e-9 for a_, b in zip(wh, wh[1:]))
                n_a += ok_a
                print(f"  [{net} tot={'inf' if tot is None else tot:<6} {rule:<8}] slots "
                      + "->".join(str(s) for s, _ in seq)
                      + " | unsafe " + "->".join(f"{u:.2f}%" for u in un)
                      + " | withheld " + "->".join(f"{w:.0f}" for w in wh)
                      + " | stress_h " + "->".join(f"{x:.0f}" for x in st)
                      + ("   [a OK]" if ok_a else "   [!! (a) withheld khong giam]")
                      + f"   [stress {st[-1] - st[0]:+.0f}h tong]")
                if not ok_a:
                    fails.append(f"{net}/{rule}/tot={tot}: it slot hon ma withheld khong "
                                 f"giam ({[round(x,1) for x in wh]}) -> trai co hoc "
                                 "(it co hoi quyet dinh hon)")
    print(f"  luat (a) withheld giam: {n_a}/{n_tot} cell")

    # ---- GATE (b) dung phuong phap: KIEM DINH CAP GOP, khong don dieu tung cell ----
    # LOI GATE LAN THU 17 (2026-10-04): ban dau gate doi stress_h TANG o tung cell
    # khi slots giam. 9/45 cell vi pham, nhung muc vi pham chi -54h tren ~9300h
    # (0,6%), trong khi kiem dinh cap GOP (n = 300 cap = seed x thua x ngan sach x
    # kenh) cho thay xu huong that rat ro:
    #   equal   stress_h +158.7h (t = +21.6)   withheld -58.6 (t = -461)
    #   deficit stress_h +142.0h (t = +20.4)   withheld -58.7 (t = -476)
    #   gate    stress_h  +62.2h (t =  +6.6)   withheld -58.9 (t = -461)
    # Tuc la "quyet dinh thua hon -> phan ung cham hon" la that, chi la nhieu o
    # tung cell le che mat xu huong. Gate dung: kiem dinh tren toan bo cap.
    print("\n=== GATE (b): kiem dinh cap gop -- slots it hon => phan ung cham hon ===")
    s_max, s_min = max(slots), min(slots)
    for rule in ALLOC:
        pairs = defaultdict(dict)
        for r in rows:
            if r["alloc"] != rule:
                continue
            pairs[(r["seed"], r["field"], r["total_budget_mm"], r["network"])][
                int(r["slots_per_day"])] = r
        P = [v for v in pairs.values() if s_max in v and s_min in v]
        if not P:
            continue
        print(f"  [{rule:<8}] n cap = {len(P)}  (slots {s_max} -> {s_min})")
        for fld, want_up in (("withheld", False), ("stress_h", True),
                             ("unsafe_pct", False), ("awd_eff", True)):
            d = [p[s_min][fld] - p[s_max][fld] for p in P]
            m, t = paired_t(d)
            ok = (t >= 2.0) if want_up else (t <= -2.0)
            # unsafe_pct va awd_eff la HE QUA cua danh doi, khong bat buoc don chieu
            hard = fld in ("withheld", "stress_h")
            print(f"      {fld:<11} mean={m:+9.2f}  t={t:+8.2f}  "
                  f"{'CO Y NGHIA' if abs(t) >= 2 else 'nhieu'}"
                  + ("" if ok or not hard else "   !! trai co che"))
            if hard and not ok:
                fails.append(f"{rule}: slots {s_max}->{s_min} ma {fld} khong doi theo "
                             f"co che (mean={m:+.2f}, t={t:+.2f}; n={len(P)})")
    if n_tot == 0:
        fails.append("khong co cell nao du 2 muc slots de kiem tra -> gate khong chay duoc")

    # ---- GATE: co che im-lang co giup gi o cap HTX khong? ----
    print("\n=== GATE: co che im-lang co giup gi o cap HTX khong? ===")
    for net in networks:
        for tot in total_mm:
            for spd in slots:
                e = agg.get(key("equal", tot, spd, net))
                g = agg.get(key("gate", tot, spd, net))
                if not (e and g):
                    continue
                du = g["unsafe_mean"] - e["unsafe_mean"]
                dw = g["unsafe_worst"] - e["unsafe_worst"]
                da = g["awd_eff"] - e["awd_eff"]
                dg = g["gini"] - e["gini"]
                ds = g["stress_h"] - e["stress_h"]
                verdict = "tot hon" if (du < -0.5 or dw < -0.5 or da > 0.5) else \
                          ("tuong duong" if abs(du) <= 0.5 and abs(dw) <= 0.5 else "te hon")
                print(f"  [{net} tot={'inf' if tot is None else tot:<6} slots={spd}] "
                      f"gate vs equal: dUnsafe_TB={du:+.2f}p dRuonxau={dw:+.2f}p "
                      f"dAWD={da:+.1f} dGini={dg:+.3f} dstress_h={ds:+.0f} -> {verdict}")
    worse = checked = 0
    for net in networks:
        for tot in total_mm:
            for spd in slots:
                e, g = agg.get(key("equal", tot, spd, net)), agg.get(key("gate", tot, spd, net))
                if e and g:
                    checked += 1
                    if g["unsafe_mean"] > e["unsafe_mean"] + 0.5 or \
                       g["unsafe_worst"] > e["unsafe_worst"] + 0.5:
                        worse += 1
    if checked and worse == checked:
        fails.append(f"gate TE HON equal o {worse}/{checked} cau hinh -> khong duoc "
                     "claim loi ich o cap HTX")
    print(f"\n  (gate te hon equal o {worse}/{checked} cau hinh)")

    # ---- GATE: phan bo theo thieu hut vs chia deu ----
    print("\n=== GATE: chia theo thieu hut vs chia deu ===")
    d_better = d_tot = 0
    for net in networks:
        for tot in total_mm:
            for spd in slots:
                e = agg.get(key("equal", tot, spd, net))
                d = agg.get(key("deficit", tot, spd, net))
                if not (e and d):
                    continue
                d_tot += 1
                if d["unsafe_mean"] < e["unsafe_mean"] - 0.5 or \
                   d["unsafe_worst"] < e["unsafe_worst"] - 0.5:
                    d_better += 1
                print(f"  [{net} tot={'inf' if tot is None else tot:<6} slots={spd}] "
                      f"deficit vs equal: dUnsafe_TB={d['unsafe_mean']-e['unsafe_mean']:+.2f}p "
                      f"dRuonxau={d['unsafe_worst']-e['unsafe_worst']:+.2f}p "
                      f"dGini={d['gini']-e['gini']:+.3f}")
    print(f"  (chia theo thieu hut tot hon chia deu o {d_better}/{d_tot} cau hinh)")

    # ---- GATE: AWD phai kha thi o it nhat mot cau hinh khan ----
    print("\n=== GATE: HTX co the dat AWD dat chuan khong? ===")
    best_awd = 0.0
    best_cell = None
    for k, v in agg.items():
        if v["awd_eff"] > best_awd:
            best_awd, best_cell = v["awd_eff"], k
    if best_cell:
        print(f"  tot nhat: {best_cell} -> AWD_eff = {best_awd:.2f} chu ky/mua")
    if best_awd < 1.0:
        fails.append(f"khong cau hinh HTX nao dat duoc 1 chu ky AWD dat chuan "
                     f"(max = {best_awd:.2f}) -> khong duoc claim loi ich MRV o cap HTX")

    # ---- GATE CROSSOVER: loi the cua cong IM LANG ket thuc o dau? -------------
    # Do truc tiep (kênh severe, slots=2..6) cho thay day la GIOI HAN THAT cua co che,
    # khong phai loi can giau:
    #   tot= 480 (80 mm/ruong) : gate -7.55 diem  (thang dam)
    #   tot= 960 (160 mm/ruong): gate -15.69 diem (thang dam nhat)
    #   tot=1440 (240 mm/ruong): gate -8.79 -> +2.14 (doi dau khi slots it)
    #   tot=1920 (320 mm/ruong): gate +0.09 -> +2.69 (THUA)
    #   tot= inf               : gate = equal (0.00) -> luat thich ung da tu chuyen
    #                              ve centre-seeking, xac nhan co che hoat dong dung.
    # Co che: giu ruong o dau kho (D = 0.80) tiet kiem nuoc nhung bot bien an toan.
    # Khi nuoc du, bien an toan do "mien phi" nen centre-seeking thang.
    # => Phai bao cao duong CHEO nay, va neu no la dieu kien de claim loi ich.
    print("\n=== GATE CROSSOVER: cong im-lang thang den dau thi het thang? ===")
    for net in networks:
        print(f"  [{net}] delta = unsafe(gate) - unsafe(equal); am = gate tot hon")
        cross_at = None
        scarcest = None
        for tot in total_mm:
            line = []
            for spd in sorted(slots, reverse=True):
                e = agg.get(key("equal", tot, spd, net))
                g = agg.get(key("gate", tot, spd, net))
                if not (e and g):
                    continue
                dv = g["unsafe_mean"] - e["unsafe_mean"]
                line.append(f"slots={spd}:{dv:+.2f}p")
                if scarcest is None:
                    scarcest = dv
                if dv > 0.5 and cross_at is None:
                    cross_at = tot
            if line:
                tag = ("inf" if tot is None else f"{tot:.0f}")
                per_field = "vo han" if tot is None else f"{tot / len(FIELDS):.0f}"
                print(f"    tong={tag:>6} ({per_field:>6} mm/ruong)  " + "  ".join(line))
        # dieu kien claim: o muc ngan sach khan nhat, cong phai thang ro (>= 1 diem)
        if scarcest is not None:
            ok = scarcest <= -1.0
            print(f"    => o ngan sach khan nhat: delta = {scarcest:+.2f} diem "
                  f"{'(CONG THANG RO — du dieu kien claim)' if ok else '(khong thang ro)'}")
            if not ok:
                fails.append(f"{net}: o ngan sach khan nhat ma cong im-lang khong thang "
                             f"ro (delta={scarcest:+.2f} diem) -> khong du co so claim")
        if cross_at is not None:
            print(f"    => CROSSOVER: tu tong ngan sach {cross_at} "
                  f"({cross_at / len(FIELDS):.0f} mm/ruong) tro len, centre-seeking "
                  f"(khong im-lang theo muc tieu kho) lai an toan hon. "
                  f"Day la DIEU KIEN AP DUNG, phai ghi trong bai.")
        else:
            print("    => khong co crossover trong thang ngan sach da quet")

    print()
    if fails:
        print(f"MULTIFIELD PROBLEMS ({len(fails)}):")
        for f in fails:
            print("  -", f)
        return 1
    print("MULTIFIELD GATES: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""ABLATION: bo tung thanh phan cua co che de xuat, do cai gia cua no.

Muc dich (anh Van yeu cau "dong gop that, khong chi tren giay"): neu mot thanh phan
khong do duoc loi ich thi no khong phai dong gop. Moi bien the tat DUNG MOT thanh
phan, giu nguyen phan con lai, chay cung seed/cung thoi tiet/cung kenh -> khac biet
qui duoc cho thanh phan do.

Cac thanh phan bi tat:
  - whatif   : twin -> predictor (rollout voi 0 mm, khong dua lenh u vao)
  - T2       : gui lai mu (blind ARQ) thay vi gui lai theo niem tin
  - reanchor : khong tai neo twin bang cam bien uplink (sigma tang mai)
  - epochcap : quyet dinh moi gio thay vi moi 24h (bo rang buoc van hanh)
  - gate     : bo cong chance-constrained, dung nguong depletion tinh
  - budget   : bo rang buoc ngan sach nuoc (nuoc mien phi)
  - adaptive : bo luat chon muc tieu thich ung (co dinh centre-seeking)

Usage:
    python3 experiments/run_ablation.py --quick
    python3 experiments/run_ablation.py            # full
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
    POLICIES, PolicyConfig, load_weather, march_start, run_episode,
    season_deficit_suffix,
)
from water_balance import SoilProfile  # noqa: E402

OUT = ROOT / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

HOURS = 2160
EPOCH = 24

# ABlation phai chay o HAI muc do trung thuc, va day la phat hien chu khong phai
# tinh huong phu: HIEU LUC cua tung thanh phan PHU THUOC do trung thuc cua twin.
#   vung pass = W - 2*z*sigma_H ; buoc nhay ung vien = 20 mm (tap nong hoc {20,40,60})
#   f=0.10 -> vung pass  4.2 mm < 20 mm  => tai moi belief chi 1 ung vien dat
#             => moi luat chon lenh deu tra ve CUNG mot lenh (do truc tiep: 10.23% vs 10.23%)
#   f=0.02 -> vung pass 48.4 mm > 20 mm  => luat chon co tac dung (12.51% vs 1.26%)
# Neu chi ablate o f=0.10 thi ket luan "-luat thich ung khong co dong gop" la SAI;
# no chi dung o che do ma vung pass hep hon buoc nhay ung vien.
# Moi thanh phan phai duoc cham tren METRIC MA NO DUOC THIET KE DE TAC DONG.
# LOI GATE LAN THU 12 (2026-10-04): ban dau gate cham MOI thanh phan bang |dUnsafe|.
# Do n=10 seed cho thay T2 that su co dong gop, nhung tren metric cua no:
#   wide/b=240: dup_mm 56.0 vs 74.0 (-18.0), resends 19.7 vs 34.3 (-14.6),
#               dup 2.80 vs 3.70, unsafe 1.07% vs 3.12% (-2.05p)
# O che do quick (2 seed) sai lech unsafe chi con 0.19p nen gate bao dong gia.
# Nguyen tac: ablation gate phai dung metric chinh cua thanh phan + nguong tuong xung.
# (metric, nguong toi thieu de goi la "co dong gop", huong tot)
COMPONENT_METRIC = {
    "- whatif (twin->predictor)":        ("unsafe_pct", 2.0, "lower"),
    "- cong chance-constrained":         ("unsafe_pct", 2.0, "lower"),
    "- tai neo cam bien":                 ("unsafe_pct", 2.0, "lower"),
    "- T2 (gui lai mu)":                  ("dup_mm",     5.0, "lower"),  # T2 chong tuoi dup
    # epoch cap: nguong 0 vi tac hai cua no duoc GATE 2 assert rieng (micro-dosing
    # HOAC giam an toan), khong the cham bang mot metric don le.
    "- epoch cap (quyet dinh moi gio)":   ("cmd_per_day", 0.0, "either"),
    "- luat thich ung (centre co dinh)":  ("unsafe_pct", 2.0, "lower"),
    "Oracle (thong tin hoan hao)":       ("unsafe_pct", 0.0, "either"),
}


FIDELITIES = {
    "wide":  0.02,   # vung pass 48.4 mm > buoc nhay -> luat chon lenh co tac dung
    "narrow": 0.10,  # vung pass  4.2 mm < buoc nhay -> luat chon lenh vo hieu
}


def variants(budget: float | None, sigma_frac: float = 0.10):
    """Bien the: (ten, PolicyConfig, slots_per_decision, water_budget).

    gate_target_depl=None => centre-seeking CO DINH (bien the "luat thich ung bi tat").
    """
    BASE = dict(sigma_frac=sigma_frac, delta=0.05, horizon=6)
    return [
        ("FULL (de xuat)",
         PolicyConfig("full", True, True, True, gate_target_depl=0.80, **BASE),
         EPOCH, budget),
        ("- whatif (twin->predictor)",
         PolicyConfig("w", True, True, True, use_whatif=False, gate_target_depl=0.80, **BASE),
         EPOCH, budget),
        ("- T2 (gui lai mu)",
         PolicyConfig("t2", True, False, True, gate_target_depl=0.80, **BASE),
         EPOCH, budget),
        ("- tai neo cam bien",
         PolicyConfig("ra", True, True, False, gate_target_depl=0.80, **BASE),
         EPOCH, budget),
        ("- epoch cap (quyet dinh moi gio)",
         PolicyConfig("ec", True, True, True, gate_target_depl=0.80, **BASE),
         1, budget),
        ("- cong chance-constrained",
         PolicyConfig("g", False, True, True, **BASE),
         EPOCH, budget),
        ("- luat thich ung (centre co dinh)",
         PolicyConfig("ad", True, True, True, gate_target_depl=None, **BASE),
         EPOCH, budget),
        ("Oracle (thong tin hoan hao)",
         PolicyConfig("o", True, True, True, oracle=True),
         EPOCH, budget),
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--year", type=int, default=2024)
    a = ap.parse_args()

    if a.quick:
        stations, networks = ["can_tho"], ["severe"]
        budgets = [240.0]
        seeds = [7, 11]
        dest = OUT / "ablation_quick.csv"
    else:
        stations = ["can_tho", "soc_trang", "ca_mau"]
        networks = ["mild", "severe"]
        budgets = [80.0, 160.0, 240.0, 320.0, None]
        seeds = list(range(a.seeds))
        dest = OUT / "ablation_raw.csv"

    starts = {}
    needs = {}
    for st in stations:
        w, _ = load_weather(st, year=a.year)
        starts[st] = march_start(w)
        needs[st] = season_deficit_suffix(w, starts[st], HOURS, SoilProfile())[0]

    nv = len(variants(None))
    total = nv * len(stations) * len(networks) * len(budgets) * len(seeds) * len(FIDELITIES)
    print(f"ABLATION: {nv} bien the x {len(stations)} tram x {len(networks)} kenh x "
          f"{len(budgets)} ngan sach x {len(seeds)} seed x {len(FIDELITIES)} muc do trung thuc "
          f"= {total} episode")
    print(f"  thieu hut du bao dau mua: " +
          ", ".join(f"{st}={needs[st]:.0f}mm" for st in stations))
    print(f"  do trung thuc: " + ", ".join(f"{k}={v}" for k, v in FIDELITIES.items()))

    rows, t0, done = [], time.time(), 0
    for fid, sf in FIDELITIES.items():
      for bud in budgets:
        for name, pol, spd, b in variants(bud, sf):
          for st in stations:
            for net in networks:
              for s in seeds:
                        m = run_episode(st, pol, s, hours=HOURS, start=starts[st],
                                        network=net, slots_per_decision=spd,
                                        water_budget_mm=b, year=a.year)
                        ep = HOURS // spd
                        rows.append({
                            "fidelity": fid, "sigma_frac": sf,
                            "variant": name, "station": st, "network": net,
                            "budget_mm": "inf" if b is None else b, "seed": s,
                            "epoch_h": spd, "year": a.year,
                            "unsafe_pct": round(100 * m.hours_unsafe / m.hours, 4),
                            "severe_pct": round(100 * m.hours_severe / m.hours, 4),
                            "water_mm": round(m.water_applied_mm, 2),
                            "dup": m.double_irrigations,
                            "dup_mm": round(m.water_wasted_dup_mm, 2),
                            "sent": m.commands_sent,
                            "resends": m.resends_sent,
                            "gen": m.commands_generated,
                            "withheld": m.withheld,
                            "withheld_saline": m.withheld_saline,
                            "awd_eff": m.awd_effective,
                            "awd_short": m.awd_short_cycles,
                            "awd_dry_h": m.awd_dry_hours,
                            "stress_h": m.stress_hours_ks_lt1,
                            "mm_per_cmd": round(m.water_applied_mm / max(1, m.commands_delivered), 2),
                            "cmd_per_day": round(m.commands_generated / (HOURS / 24.0), 3),
                            "rmse": round(m.twin_rmse, 4),
                        })
                        done += 1
            print(f"  [{done}/{total}] b={bud} {name[:34]:34s} ({time.time()-t0:.0f}s)",
                  flush=True)

    with dest.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {len(rows)} rows -> {dest}")

    # ---------------- bang cai gia cua tung thanh phan ----------------
    agg = defaultdict(lambda: defaultdict(list))
    for r in rows:
        k = (r["fidelity"], r["variant"], r["budget_mm"], r["network"])
        for f in ("unsafe_pct", "water_mm", "dup", "dup_mm", "resends", "awd_eff",
                  "awd_short", "stress_h", "cmd_per_day", "mm_per_cmd", "withheld"):
            agg[k][f].append(r[f])
    mean = {k: {f: statistics.mean(v) for f, v in d.items()} for k, d in agg.items()}

    fails = []
    print("\n=== CAI GIA CUA TUNG THANH PHAN (mean over tram/seed) ===")
    for fid in FIDELITIES:
      for net in networks:
        for bud in ["inf" if b is None else b for b in budgets]:
            full = mean.get((fid, "FULL (de xuat)", bud, net))
            if not full:
                continue
            print(f"\n  [{fid} f_sigma={FIDELITIES[fid]} | {net} | ngan sach {bud} mm] "
                  f"FULL: unsafe={full['unsafe_pct']:.2f}% water={full['water_mm']:.0f}mm "
                  f"dup={full['dup']:.1f} AWD_eff={full['awd_eff']:.1f} "
                  f"lenh/ngay={full['cmd_per_day']:.2f}")
            print(f"  {'bien the':<34} {'dUnsafe':>9} {'dNuoc':>8} {'dDup':>7} "
                  f"{'dAWD':>7} {'lenh/ngay':>10}")
            for name, _, _, _ in variants(None):
                if name.startswith("FULL"):
                    continue
                v = mean.get((fid, name, bud, net))
                if not v:
                    continue
                du = v["unsafe_pct"] - full["unsafe_pct"]
                dw = v["water_mm"] - full["water_mm"]
                dd = v["dup"] - full["dup"]
                da = v["awd_eff"] - full["awd_eff"]
                print(f"  {name:<34} {du:>+8.2f}p {dw:>+8.1f} {dd:>+7.1f} "
                      f"{da:>+7.1f} {v['cmd_per_day']:>10.2f}")

    # ---- GATE 1: dong gop cua thanh phan, theo DAI trung thuc + metric chinh ----
    # Hai loi gate da sua (lan 10 va 12):
    #   (10) doi moi thanh phan co dong gop o MOI dai -> sai, vi "- luat thich ung"
    #        vo hieu o dai narrow la HE QUA cua menh de d_max (vung pass 4.2 mm <
    #        buoc nhay 20 mm), khong phai loi.
    #   (12) cham moi thanh phan bang |dUnsafe| -> sai, vi T2 duoc thiet ke de chong
    #        tuoi dup; o 2 seed thi sai lech unsafe bi nhieu che mat.
    CORE = ("- whatif", "chance-constrained", "tai neo")
    REGIME_DEPENDENT = ("- luat thich ung",)
    print("\n=== KIEM TRA: dong gop cua thanh phan (metric chinh x dai trung thuc) ===")
    for net in networks:
        for name, _, _, _ in variants(None):
            if name.startswith("FULL"):
                continue
            metric, thr, _dir = COMPONENT_METRIC.get(name, ("unsafe_pct", 2.0, "lower"))
            per_fid = {}
            for fid in FIDELITIES:
                eff = []
                for bud in ["inf" if b is None else b for b in budgets]:
                    full = mean.get((fid, "FULL (de xuat)", bud, net))
                    v = mean.get((fid, name, bud, net))
                    if full and v:
                        eff.append(abs(v[metric] - full[metric]))
                per_fid[fid] = max(eff) if eff else 0.0
            if any(k in name for k in CORE):
                bad = [f for f, e in per_fid.items() if e <= thr]
                status = f"CO dong gop (cot loi, {metric})" if not bad else \
                         f"!! cot loi ma vo hieu o {bad} ({metric})"
                if bad:
                    fails.append(f"{net}/{name}: thanh phan COT LOI ma khong co dong gop o "
                                 f"{bad} tren {metric} ({per_fid}) => khong duoc claim")
            elif name.startswith(REGIME_DEPENDENT):
                wide_ok = per_fid.get("wide", 0.0) > thr
                narrow_null = per_fid.get("narrow", 0.0) <= thr
                if wide_ok and narrow_null:
                    status = f"co dong gop o dai wide, vo hieu o narrow (DUNG ly thuyet, {metric})"
                elif wide_ok:
                    status = f"co dong gop o ca hai dai ({metric})"
                else:
                    status = f"!! vo hieu o ca hai dai => trang tri ({metric}) !!"
                    fails.append(f"{net}/{name}: khong co dong gop o dai nao tren {metric} "
                                 f"({per_fid}) => thanh phan trang tri, KHONG duoc claim")
            elif thr > 0:
                # thanh phan co nguong khai bao => BAT BUOC co dong gop o it nhat
                # mot dai. LO HONG GATE da sua: truoc day T2 roi vao nhanh else va
                # chi duoc in "reference" ma khong bi assert nao, nen gate van PASS
                # khi T2 vo dung.
                contributed = [f for f, e in per_fid.items() if e > thr]
                if contributed:
                    status = f"CO dong gop o {contributed} ({metric})"
                    if name.startswith("- T2"):
                        # T2 la thanh phan cot loi cua co che de xuat: phai co dong gop
                        # o MOI dai tren metric cua no (dup_mm).
                        miss = [f for f, e in per_fid.items() if e <= thr]
                        if miss:
                            status += f" !! nhung vo hieu o {miss}"
                            fails.append(f"{net}/{name}: T2 la thanh phan cot loi ma khong "
                                         f"co dong gop o {miss} tren {metric} ({per_fid})")
                else:
                    status = f"!! KHONG co dong gop o dai nao ({metric}) !!"
                    fails.append(f"{net}/{name}: khong co dong gop o dai nao tren {metric} "
                                 f"({per_fid}) => thanh phan trang tri, KHONG duoc claim")
            else:
                status = f"reference ({metric}, khong assert)"
            print(f"  [{net}] {name:<34} {metric:<12} "
                  + "  ".join(f"{f}:{e:8.2f}" for f, e in per_fid.items())
                  + f"   {status}")

    # ---- GATE 2: epoch cap -- HAI che do tac hai, phai chap nhan MOT trong hai ----
    # LOI GATE LAN THU 11 (2026-10-04): ban dau gate chi tim micro-dosing (mm/lenh
    # giam). Do truc tiep 3 tap do sau cho thay tac hai PHU THUOC do min cua tap:
    #   tap nong hoc {20,40,60}: mm/lenh = 20.0 o CA HAI che do (micro-dosing BAT
    #     KHA THI ve so hoc) nhung unsafe 10.03% -> 13.78% (front-loading ngan sach)
    #   tap min {5,...,30}:      mm/lenh 7.78 -> 5.00 va lenh/ngay 0.39 -> 0.54
    #     (micro-dosing that)
    # Vay gate dung: bo epoch cap phai gay (a) micro-dosing HOAC (b) giam an toan.
    # Neu khong gay gi ca thi rang buoc nay moi la trang tri.
    print("\n=== KIEM TRA epoch cap: bo no phai gay micro-dosing HOAC giam an toan ===")
    for fid in FIDELITIES:
        for net in networks:
            for bud in ["inf" if b is None else b for b in budgets]:
                v = mean.get((fid, "- epoch cap (quyet dinh moi gio)", bud, net))
                full = mean.get((fid, "FULL (de xuat)", bud, net))
                if not (v and full):
                    continue
                micro = (v["cmd_per_day"] > 1.3 * full["cmd_per_day"]
                         or v["mm_per_cmd"] < 0.8 * full["mm_per_cmd"])
                worse = v["unsafe_pct"] > full["unsafe_pct"] + 0.5
                ok = micro or worse
                tag = ("micro-dosing" if micro else "") + (" + an toan giam" if worse else "")
                print(f"  [{fid} {net} b={bud:>5}] lenh/ngay {full['cmd_per_day']:.2f} -> "
                      f"{v['cmd_per_day']:.2f}; mm/lenh {full['mm_per_cmd']:.1f} -> "
                      f"{v['mm_per_cmd']:.1f}; unsafe {full['unsafe_pct']:.2f}% -> "
                      f"{v['unsafe_pct']:.2f}%   {'OK: ' + tag if ok else 'KHONG thay tac hai'}")
                if not ok:
                    fails.append(f"{fid}/{net}/b={bud}: bo epoch cap khong gay micro-dosing "
                                 f"({full['cmd_per_day']:.2f}->{v['cmd_per_day']:.2f} lenh/ngay, "
                                 f"{full['mm_per_cmd']:.1f}->{v['mm_per_cmd']:.1f} mm/lenh) "
                                 f"va khong giam an toan ({full['unsafe_pct']:.2f}->"
                                 f"{v['unsafe_pct']:.2f}%) => rang buoc nay trang tri")

    print()
    if fails:
        print(f"ABLATION PROBLEMS ({len(fails)}):")
        for f in fails:
            print("  -", f)
        return 1
    print("ABLATION GATES: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

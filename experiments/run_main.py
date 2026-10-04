#!/usr/bin/env python3
"""Main experiment for the K1 study: policy comparison over the networked control loop.

Design decisions that are load-bearing, and why:

  * DECISION EPOCH = 24 h. Real sluice/pump operation moves a meaningful depth once
    per day, not per hour. Without this cap the command channel is not scarce, the
    gate micro-doses 0.3-0.6 mm sixteen times a day, and every policy trivially
    achieves zero violations. That was measured, not assumed -- see
    tests/diag_epoch_cap.py.
  * WINDOW = the dry season (March-May). ERA5 measurement on the real 2024 series
    showed essentially ALL heat-stress hours of the year fall in March-May, and
    MARD reports salinity intrusion peaking in the same window.
  * One RNG per role, seeded by `seed`, so every policy sees IDENTICAL channel
    draws and weather. Outcome differences are attributable to the policy alone.
  * Ground truth about whether a command landed is held by the SIMULATOR only.
    Policies see the ACK (or its absence) and must maintain a belief. Passing
    `landed` into a policy would invalidate the whole comparison.

  * FIDELITY LADDER (them 2026-10-04, va day la sua loi nghiem trong):
    Ban dau luoi chinh chi chay sigma_frac mac dinh 0.10. Do truc tiep cho thay o
    muc do trung thuc do VUNG PASS cua cong chi rong W - 2*z*sigma_H = 4.2 mm, nho
    hon buoc nhay ung vien 20 mm, nen:
      - hai luat chon lenh (target-seeking vs centre-seeking) tra ve CUNG mot lenh
        => TwinGate+T2 va TwinGate+T2+centre giong het nhau (40.07/24.27/7.91/1.32)
        => luoi chinh KHONG DO DUOC dong gop cua luat thich ung;
      - awd_effective chi 0.3-0.5 chu ky/mua => KHONG DO DUOC kha nang lam AWD.
    Tuc la bang ket qua chinh cua bai cu khong kiem chung duoc hai dong gop lon
    nhat cua co che. Vi vay thang do trung thuc duoc them lam mot CHIEU THUC NGHIEM,
    voi cac moc suy ra tu O SPEC (khong phai so tuy y):
      awd    f=0.02  (sigma_dung 3.21 mm <= 3.57 mm yeu cau)  -> lam AWD du tin chi
      mid    f=0.05  (giua hai nguong)                        -> dai chuyen tiep
      narrow f=0.10  (sigma_dung 16.1 mm >  3.57 mm)           -> cong song, AWD chet
    Ket qua o ca ba moc deu phai duoc bao cao: do la kiem chung tinh vung cua co che.

Usage:
    python3 experiments/run_main.py --quick      # differentiation check, ~1 min
    python3 experiments/run_main.py              # full grid
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ncs_loop import POLICIES, load_weather, march_start, run_episode  # noqa: E402
from twin_gate import safe_bounds  # noqa: E402
from water_balance import SoilProfile  # noqa: E402

OUT = ROOT / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

STATIONS = ["can_tho", "soc_trang", "ca_mau"]
NETWORKS = ["mild", "severe"]
HOURS = 2160          # 90 days: March-May, the dry-season heat/salinity peak
EPOCH = 24            # hourly physics, daily decisions

# Thang do trung thuc cua twin. Cac moc suy ra tu O SPEC trong run_deployment.py
# (sigma* = W/(2z) = 15.18 mm; AWD can sigma_dung <= 3.57 mm; sigma_dung = f*229.4 mm).
FIDELITIES = [
    ("awd", 0.02),      # lam AWD du tin chi duoc
    ("mid", 0.05),      # dai chuyen tiep
    ("narrow", 0.10),   # cong van song nhung AWD chet
]

# Thieu hut mua kho DO THAT (ERA5 2024 Can Tho: ET0 503 mm, mua 210 mm -> thieu
# 293 mm; ETc voi Kc=1.05 -> 318 mm). Dung de phan biet ngan sach "rang buoc"
# (bud < DEFICIT) voi ngan sach "du" (bud >= DEFICIT) trong cac gate.
# Thieu hut mua kho: TINH TU DU LIEU, khong hardcode.
# Co HAI dinh nghia lech nhau 1.5 lan (do tren ERA5 2024, cua so 2160h):
#   NET     = Kc*sum(ET0) - sum(mua)      : 301.6 / 306.0 / 318.4 mm (3 tram)
#   POS-SUM = sum(max(0, Kc*ET0_h - P_h)) : 450.2 / 468.5 / 485.1 mm (3 tram)
# CONG dung POS-SUM (season_deficit_suffix) de xet `scarce`, nen moi ngan sach
# huu han trong luoi (80..400 mm) deu la RANG BUOC. Ban cu hardcode 318 (NET)
# => gan nhan sai cho b = 320 va b = 400, lam gate saturation check sai pham vi.
def _compute_deficits(stations=STATIONS, hours=HOURS):
    from ncs_loop import season_deficit_suffix
    prof = SoilProfile()
    pos, net = {}, {}
    for st in stations:
        w, _ = load_weather(st)
        s0 = march_start(w)
        seg = w[s0:s0 + hours]
        net[st] = max(0.0, prof.kc * sum(r["et0"] for r in seg)
                      - sum(r["p"] for r in seg))
        pos[st] = season_deficit_suffix(w, s0, hours, prof)[0]
    return pos, net

# LOI DA SUA (2026-10-04): _compute_deficits() goi load_weather(st) MA KHONG TRUYEN
# `year`, nen luon tinh theo 2024. Khi chay --year 2025 thi nguong khan bi sai:
#   2024 min POS-SUM = 450.2 mm   (NET 301.6 / 306.0 / 318.4)
#   2025 min POS-SUM = 349.9 mm   (NET   0.0 /  36.1 / 158.3)  <- mua nhieu hon han
# Dua vao DEFICIT_MM = 450 khi chay 2025 lam b = 400 bi xep nham la "rang buoc".
# Sua: tinh theo nam, va KHONG dung no lam tieu chi duy nhat (xem gate AWD duoi).
_YEAR = 2024          # cap nhat trong main() theo --year
_POS, _NET = _compute_deficits()
DEFICIT_POS, DEFICIT_NET = _POS, _NET
DEFICIT_MM = min(_POS.values())   # nguong khan theo dinh nghia cua cong (nam 2024)


def _deficits_for(year: int):
    """Thieu hut cua DUNG nam dang chay (POS-SUM va NET, theo tram)."""
    from ncs_loop import load_weather as _lw2, march_start as _ms2, \
        season_deficit_suffix as _sds2
    _p = SoilProfile()
    pos, net = {}, {}
    for st in STATIONS:
        w, _ = _lw2(st, year=year)
        s0 = _ms2(w)
        seg = w[s0:s0 + HOURS]
        net[st] = max(0.0, _p.kc * sum(r["et0"] for r in seg) - sum(r["p"] for r in seg))
        pos[st] = _sds2(w, s0, HOURS, _p)[0]
    return pos, net

# Chieu rong tap an toan depletion (W = hi - lo), tinh tu FAO-56 chu khong go so.
# Dung de kiem tra co che BAO HOA: mot lenh tuoi sau >= W thi nuoc tran khoi dung
# trong (tham sau), nen "them nuoc" khong mang lai "them nuoc huu ich".
_LO, _HI = safe_bounds(SoilProfile())
W_SAFE = _HI - _LO


def spearman(xs: list[float], ys: list[float]) -> float:
    """He so tuong quan hang Spearman, khong can scipy. -1 = nghich bien hoan hao."""
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    if len(xs) < 3:
        return 0.0
    rx, ry = ranks(xs), ranks(ys)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den if den else 0.0


def paired_t(diffs: list[float]) -> tuple[float, float]:
    """(mean, t) cua day hieu cap. t = mean / (sd/sqrt(n)); sd=0 => t=0."""
    if not diffs:
        return 0.0, 0.0
    m = statistics.mean(diffs)
    sd = statistics.pstdev(diffs)
    if sd == 0:
        return m, 0.0
    return m, m / (sd / len(diffs) ** 0.5)


def run(seeds: list[int], stations: list[str], networks: list[str], hours: int = HOURS,
        budgets: list[float] | None = None, year: int = 2024,
        fidelities: list[tuple[str, float]] | None = None):
    """`budgets` sweeps the season water budget [mm of DELIVERED water].

    This is the binding resource constraint. Without it every policy trivially
    reaches zero violations (measured in the first full run), so there is no
    trade-off to study and no way to rank policies on safety. Sweeping it produces
    the safety-vs-water Pareto frontier, and each budget is one row of the paper's
    main table.

    `fidelities` sweeps how accurate the digital twin is (sigma_frac). Without it
    the grid measures the mechanism at ONE arbitrary accuracy level and cannot tell
    whether a component contributes at all -- measured defect, see module docstring.
    """
    fidelities = fidelities or FIDELITIES
    rows = []
    t0 = time.time()
    starts = {}
    for st in stations:
        w, _ = load_weather(st, year=year)
        starts[st] = march_start(w)
    budgets = budgets or [None]
    # (fidelity, sigma_frac, policy) -- dataclasses.replace giu nguyen moi thu khac
    combos = [(fid, sf, dataclasses.replace(pol, sigma_frac=sf))
              for fid, sf in fidelities for pol in POLICIES]
    # LOI BO DEM (2026-10-04): `done += 1` nam trong vong seed nhung `total` quen
    # nhan len(seeds), nen man hinh bao "[4410/756]" -- vuot 100%. Chi la loi hien
    # thi, khong anh huong ket qua, nhung phai sua vi nguoi doc log se tuong run treo.
    total = len(stations) * len(networks) * len(budgets) * len(combos) * len(seeds)
    done = 0
    for st in stations:
        for net in networks:
          for bud in budgets:
            for fid, sf, pol in combos:
                for s in seeds:
                    m = run_episode(st, pol, s, hours=hours, start=starts[st],
                                    network=net, slots_per_decision=EPOCH,
                                    water_budget_mm=bud, year=year)
                    rows.append({
                        "station": st, "network": net, "policy": pol.name, "seed": s,
                        "budget_mm": "inf" if bud is None else bud,
                        "fidelity": fid, "sigma_frac": sf,
                        "year": year,
                        "hours": m.hours,
                        "hours_unsafe": m.hours_unsafe,
                        "hours_severe": m.hours_severe,
                        "stress_integral": round(m.stress_integral, 4),
                        "water_applied_mm": round(m.water_applied_mm, 2),
                        "commands_generated": m.commands_generated,
                        "commands_sent": m.commands_sent,
                        "commands_delivered": m.commands_delivered,
                        "resends_sent": m.resends_sent,
                        "double_irrigations": m.double_irrigations,
                        "water_wasted_dup_mm": round(m.water_wasted_dup_mm, 2),
                        "withheld": m.withheld,
                        "uplink_success": m.uplink_success,
                        "twin_rmse": round(m.twin_rmse, 4),
                        # AWD 3-ngay (QĐ 4801) + stress — xem docstring EpisodeMetrics
                        "awd_cycles": m.awd_cycles,
                        "awd_effective": m.awd_effective,
                        "awd_short": m.awd_short_cycles,
                        "awd_dry_hours": m.awd_dry_hours,
                        "stress_hours": m.stress_hours_ks_lt1,
                    })
                    done += 1
            print(f"  [{done}/{total}] {fid:6s} {st:10s} {net:7s} {pol.name:20s} "
                  f"({time.time()-t0:.0f}s)", flush=True)
    return rows


def summarise(rows, key="policy"):
    groups: dict[tuple, list[dict]] = {}
    for r in rows:
        groups.setdefault((r.get("fidelity", "narrow"), r[key], r["network"],
                           str(r.get("budget_mm", "inf"))), []).append(r)
    out = []
    for (fid, pol, net, bud), g in sorted(groups.items()):
        def agg(f, fn=statistics.mean):
            return fn([f(x) for x in g])
        out.append({
            "fidelity": fid,
            "policy": pol, "network": net, "budget_mm": bud, "n": len(g),
            "unsafe_pct": round(100 * agg(lambda x: x["hours_unsafe"] / x["hours"]) / 1, 2),
            "severe_pct": round(100 * agg(lambda x: x["hours_severe"] / x["hours"]), 2),
            "stress_int": round(agg(lambda x: x["stress_integral"]), 1),
            "water_mm": round(agg(lambda x: x["water_applied_mm"]), 1),
            "gen": round(agg(lambda x: x["commands_generated"]), 1),
            "sent": round(agg(lambda x: x["commands_sent"]), 1),
            "dup": round(agg(lambda x: x["double_irrigations"]), 1),
            "dup_mm": round(agg(lambda x: x["water_wasted_dup_mm"]), 1),
            "withh": round(agg(lambda x: x["withheld"]), 1),
            "twin_rmse": round(agg(lambda x: x["twin_rmse"]), 3),
            "awd_cyc": round(agg(lambda x: x["awd_cycles"]), 2),
            "awd_eff": round(agg(lambda x: x["awd_effective"]), 2),
            "awd_short": round(agg(lambda x: x["awd_short"]), 2),
            "awd_dry_h": round(agg(lambda x: x["awd_dry_hours"]), 1),
            "stress_h": round(agg(lambda x: x["stress_hours"]), 1),
            "mm_per_event": round(agg(lambda x: x["water_applied_mm"]) /
                              max(1.0, agg(lambda x: x["commands_delivered"])), 2),
            "events_per_day": round(agg(lambda x: x["commands_generated"]) /
                                  (HOURS / 24.0), 3),
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="2 seeds, can_tho only")
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--out", default=None)
    ap.add_argument("--budgets", default=None,
                    help="comma-separated season water budgets in mm; "
                         "empty string element means unlimited")
    ap.add_argument("--year", type=int, default=2024,
                    help="ERA5 forcing year (2024 or 2025 must be fetched)")
    ap.add_argument("--gate-only", action="store_true",
                    help="khong mo phong lai; doc CSV da co va chi chay cac gate. "
                         "Dung de lap lai gate ma khong mat 7 phut mo phong.")
    ap.add_argument("--fidelities", default=None,
                    help="comma-separated sigma_frac values, e.g. 0.02,0.10")
    a = ap.parse_args()

    if a.fidelities:
        fids = [(f"f{v}", float(v)) for v in a.fidelities.split(",")]
    else:
        fids = FIDELITIES

    if a.quick:
        seeds, stations, networks = [7, 11], ["can_tho"], ["mild", "severe"]
        budgets = [80.0, 240.0, 400.0, None]
        fids = [("awd", 0.02), ("narrow", 0.10)]
        dest = OUT / "quick_raw.csv"
    else:
        seeds = list(range(a.seeds))
        stations, networks = STATIONS, NETWORKS
        # Thang ngan sach suy tu thieu hut mua kho DO THAT (ERA5 2024 Can Tho:
        # ET0 503 mm, mua 210 mm -> thieu 293 mm; ETc Kc=1.05 -> 318 mm).
        # Cac muc = 25/50/75/100/125% cua 320 mm => thang co y nghia nong hoc,
        # khong phai so tuy y. Thang cu {80,140,200,260} ung voi tap do sau
        # {10,20,35} da bi loai vi khong tao duoc chu ky AWD hop le.
        budgets = [80.0, 160.0, 240.0, 320.0, 400.0, None]
        # năm 2024 giữ tên gốc (tương thích ngược); năm khác có hậu tố riêng
        suffix = "" if a.year == 2024 else f"_{a.year}"
        dest = OUT / (a.out or f"main_raw{suffix}.csv")
    if a.budgets is not None:
        budgets = [(None if t.strip() == "" else float(t)) for t in a.budgets.split(",")]

    # cap nhat nguong khan theo DUNG nam dang chay (khong luon dung 2024)
    global DEFICIT_MM, DEFICIT_POS, DEFICIT_NET
    _pos_y, _net_y = _deficits_for(a.year)
    DEFICIT_POS, DEFICIT_NET = _pos_y, _net_y
    DEFICIT_MM = min(_pos_y.values())
    print(f"thieu hut nam {a.year}: POS-SUM {min(_pos_y.values()):.1f}-"
          f"{max(_pos_y.values()):.1f} mm | NET {min(_net_y.values()):.1f}-"
          f"{max(_net_y.values()):.1f} mm")

    print(f"seeds={len(seeds)} stations={stations} networks={networks} "
          f"budgets={budgets} fidelities={fids} hours={HOURS} epoch={EPOCH}h year={a.year}")
    if a.gate_only:
        if not dest.exists():
            print(f"!! --gate-only: khong tim thay {dest} (chay khong --gate-only truoc)")
            return 2
        # CSV luu moi thu duoi dang chuoi; ep so de gate tinh duoc. Cac cot phan loai
        # giu nguyen chuoi vi gate dung chung lam khoa (fidelity, network, budget_mm...).
        CAT = {"station", "network", "policy", "fidelity", "budget_mm"}
        rows = []
        with dest.open(newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                rr = {}
                for k, v in r.items():
                    if k in CAT:
                        rr[k] = v
                        continue
                    try:
                        rr[k] = float(v)
                    except (TypeError, ValueError):
                        rr[k] = v
                rows.append(rr)
        print(f"--gate-only: doc {len(rows)} rows tu {dest.name} (khong mo phong lai)")
    else:
        rows = run(seeds, stations, networks, budgets=budgets, year=a.year, fidelities=fids)
        with dest.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        print(f"\nwrote {len(rows)} rows -> {dest}")

    summ = summarise(rows)
    sumdest = dest.with_name(dest.stem.replace("_raw", "") + "_summary.csv")
    with sumdest.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(summ[0]))
        w.writeheader()
        w.writerows(summ)
    print(f"wrote summary -> {sumdest}\n")

    fid_list = [f for f, _ in fids]
    hdr = ("fid", "policy", "net", "budget", "unsafe%", "severe%", "stress", "water_mm",
           "dup", "dup_mm", "withh", "rmse", "AWD_eff", "AWD_short", "mm/ev", "ev/day")
    print("%-7s %-20s %-7s %7s %8s %9s %7s %9s %6s %7s %6s %6s %8s %9s %6s %7s" % hdr)
    print("-" * 140)
    for s in summ:
        print("%-7s %-20s %-7s %7s %8.2f %9.2f %7.1f %9.1f %6.1f %7.1f %6.1f %6.3f "
              "%8.2f %9.2f %6.2f %7.3f" % (
            s["fidelity"], s["policy"], s["network"], s["budget_mm"], s["unsafe_pct"],
            s["severe_pct"], s["stress_int"], s["water_mm"], s["dup"], s["dup_mm"],
            s["withh"], s["twin_rmse"], s["awd_eff"], s["awd_short"],
            s["mm_per_event"], s["events_per_day"]))

    fails = []
    bud_list = sorted({s["budget_mm"] for s in summ},
                      key=lambda b: (b == "inf", float(b) if b != "inf" else 0))

    # ---- does the water budget actually create a TRADE-OFF? -------------------
    print("\n=== TRADE-OFF: unsafe% theo ngân sách nước (policy TwinGate+T2) ===")
    for fid in fid_list:
        for net in networks:
            pts = sorted([(s["budget_mm"], s["unsafe_pct"]) for s in summ
                          if s["fidelity"] == fid and s["network"] == net
                          and s["policy"] == "TwinGate+T2"])
            print(f"  [{fid} {net}] " + "  ".join(f"b={b}:{u}%" for b, u in pts))
            if len({u for _, u in pts}) <= 1:
                print("     ⚠ unsafe% KHÔNG đổi theo budget -> ràng buộc chưa bind")

    # ---- differentiation gate: metric không được bão hoà ----------------------
    print("\n=== KIỂM TRA PHÂN BIỆT (metric không được bão hoà) ===")
    for fid in fid_list:
        for net in networks:
            for bud in bud_list:
                sub = [s for s in summ if s["fidelity"] == fid and s["network"] == net
                       and s["budget_mm"] == bud]
                uns = {s["policy"]: s["unsafe_pct"] for s in sub}
                wat = {s["policy"]: s["water_mm"] for s in sub}
                # Saturation is only a defect when the constraint COULD bind. With an
                # unlimited water budget nothing is scarce, so every policy reaching
                # 0% unsafe is the correct outcome, not a broken metric.
                # Nhat quan voi gate AWD (loi gate thu 24): "rang buoc" phai DO DUOC
                # bang viec nuoc thuc te CHAM TRAN ngan sach, khong suy dien tu thieu
                # hut khi hau. O nam mua nhieu (2025: NET chi 0-158 mm) suy dien do
                # xep nham b=240/320 thanh "rang buoc" trong khi cong chi dung 60-63%
                # tran, tuc ngan sach khong he khan.
                _wmax = max([x["water_mm"] for x in sub], default=0.0)
                binding = bud != "inf" and _wmax >= 0.99 * float(bud)
                if binding and len(set(round(v, 1) for v in uns.values())) <= 1 \
                        and max(uns.values()) == 0:
                    fails.append(f"{fid}/{net}/budget={bud}: unsafe% = 0 for every policy "
                                 "under a BINDING budget -> metric saturated")
                if binding and len(set(round(v) for v in wat.values())) <= 1:
                    if len({(s["gen"], s["dup"], s["unsafe_pct"]) for s in sub}) <= 1:
                        fails.append(f"{fid}/{net}/budget={bud}: policies indistinguishable "
                                     "on water, commands, duplication AND safety")
            print(f"  [{fid} {net}] unsafe% theo budget: "
                  + " | ".join(f"{bud}:" + ",".join(
                      f"{s['unsafe_pct']:.1f}" for s in summ
                      if s["fidelity"] == fid and s["network"] == net
                      and s["budget_mm"] == bud) for bud in bud_list[:3]))

    # ---- GATE TRADE-OFF (da sua: kiem dinh cap, khong don dieu tuyet doi) -----
    # LOI GATE LAN THU 14 (2026-10-04): ban dau gate doi unsafe% giam o MOI cap ngan
    # sach ke nhau, voi MOI chinh sach. Do paired diff (n = 10 seed x 3 tram = 30) cho
    # thay FixedSchedule/severe cap b=160->240 co mean=+0.410p, sd=4.138, t=+0.54,
    # 15 seed te hon / 15 seed tot hon => NHIEU thuan, khong phai phi vat ly.
    # FixedSchedule la lich CO DINH (fixed_every = 5 slot): no khong phan ung voi
    # ngan sach, nen doi no don dieu tung cap la doi mot hien tuong khong co that.
    # Gate dung: (a) xu huong TONG THE phai nghich bien (Spearman rho < 0);
    #            (b) mot cap tang chi bi flag khi tang CO Y NGHIA (|t| >= 2).
    print("\n=== TRADE-OFF: xu hướng unsafe% theo ngân sách (kiểm định cặp) ===")
    by_cell = {}
    for r in rows:
        by_cell.setdefault((r["fidelity"], r["network"], r["policy"],
                            str(r["budget_mm"])), {})[(r["seed"], r["station"])] = \
            100 * r["hours_unsafe"] / r["hours"]
    for fid in fid_list:
        for net in networks:
            for pol_name in ("TwinGate+T2", "Reactive+T2", "FixedSchedule", "Oracle"):
                pts = sorted([(float(b), u) for (f2, n2, p2, b), dd in by_cell.items()
                              for u in [statistics.mean(dd.values())]
                              if f2 == fid and n2 == net and p2 == pol_name and b != "inf"],
                             key=lambda x: x[0])
                if len(pts) < 3:
                    continue
                rho = spearman([b for b, _ in pts], [u for _, u in pts])
                line = f"  [{fid} {net} {pol_name:16s}] rho={rho:+.2f} | " + "  ".join(
                    f"b={b:.0f}:{u:.2f}%" for b, u in pts)
                sig_bad = []
                for i in range(len(pts) - 1):
                    # key trong by_cell dung dung chuoi da ghi ("80.0" ...)
                    ka = (fid, net, pol_name, str(pts[i][0]))
                    kb = (fid, net, pol_name, str(pts[i + 1][0]))
                    da, db = by_cell.get(ka), by_cell.get(kb)
                    if not da or not db:
                        continue
                    ks = sorted(set(da) & set(db))
                    m, t = paired_t([db[k] - da[k] for k in ks])
                    if t >= 2.0 and m > 0.5:
                        # ---- KIEM CHUNG CO CHE (2026-10-04, loi gate lan thu 15) ----
                        # Mot cap "them nuoc ma lai kho hon" chi duoc chap nhan khi
                        # CHUNG MINH DUOC co che bao hoa do sau, khong phai bang cach
                        # bo qua cho gate xanh:
                        #   do sau moi lenh o muc ngan sach cao >= W_SAFE (59.5 mm) thi
                        #   nuoc tran khoi dung trong (tham sau) => "them ngan sach"
                        #   khong con la "them nuoc huu ich";
                        #   DONG THOI nuoc huu ich (tong - lang phi do tuoi dup) van
                        #   PHAI tang, neu khong thi khong co chuyen bao hoa nao ca.
                        # Do truc tiep FixedSchedule/mild b=160->240: mm/lenh 53.3 ->
                        # 60.0 (>= W), dup 0.60 -> 1.30 (t=+4.91), nuoc huu ich
                        # 130 -> 162 mm (van tang don dieu). Day la cap DUY NHAT trong
                        # ca luoi co mm/lenh >= W, va cung la cap DUY NHAT vi pham.
                        sa = next((x for x in summ if x["fidelity"] == fid
                                   and x["network"] == net and x["policy"] == pol_name
                                   and x["budget_mm"] == str(pts[i][0])), None)
                        sb = next((x for x in summ if x["fidelity"] == fid
                                   and x["network"] == net and x["policy"] == pol_name
                                   and x["budget_mm"] == str(pts[i + 1][0])), None)
                        sat = False
                        mpe = float("nan")
                        if sa and sb:
                            mpe = sb["mm_per_event"]
                            useful_a = sa["water_mm"] - sa["dup_mm"]
                            useful_b = sb["water_mm"] - sb["dup_mm"]
                            sat = (mpe >= W_SAFE - 1e-9) and (useful_b > useful_a)
                        sig_bad.append((pts[i][0], pts[i + 1][0], m, t, sat, mpe))
                if sig_bad:
                    line += "\n      " + "\n      ".join(
                        f"b={b1:.0f}->{b2:.0f}: {m:+.2f} điểm (t={t:+.2f}), "
                        f"mm/lệnh={mpe:.1f} "
                        + ("=> BÃO HOÀ ĐỘ SÂU (nước hữu ích vẫn tăng): chấp nhận"
                           if sat else "=> KHÔNG giải thích được: LỖI")
                        for b1, b2, m, t, sat, mpe in sig_bad)
                print(line)
                if rho >= 0:
                    fails.append(f"{fid}/{net}/{pol_name}: unsafe% khong nghich bien theo "
                                 f"ngan sach (Spearman rho={rho:+.2f}, {pts}) -- rang buoc "
                                 "nuoc khong phai thuoc dieu khien chinh sach nay")
                for b1, b2, m, t, sat, mpe in sig_bad:
                    if sat:
                        # da kiem chung co che bao hoa -> ghi nhan de bao cao, khong fail.
                        # Day la ket qua DANG GIA (vi sao lich mu khong loi duoc tu viec
                        # duoc cap them nuoc), khong phai loi can giau.
                        print(f"      [ghi nhan] {fid}/{net}/{pol_name} b={b1:.0f}->{b2:.0f}: "
                              f"mất an toàn tăng {m:+.2f} điểm do bão hoà độ sâu "
                              f"(mm/lệnh {mpe:.1f} >= W={W_SAFE:.1f})")
                        continue
                    fails.append(f"{fid}/{net}/{pol_name}: unsafe% tang CO Y NGHIA thong ke "
                                 f"tu b={b1:.0f} len b={b2:.0f} (mean={m:+.2f}p, t={t:+.2f}) "
                                 f"ma KHONG giai thich duoc bang bao hoa do sau "
                                 f"(mm/lenh={mpe:.1f} < W={W_SAFE:.1f} mm)")
                # ngan sach vo han khong duoc te hon ngan sach huu han
                infv = [statistics.mean(dd.values())
                        for (f2, n2, p2, b), dd in by_cell.items()
                        if f2 == fid and n2 == net and p2 == pol_name and b == "inf"]
                if infv and pts and infv[0] > min(u for _, u in pts) + 0.5:
                    fails.append(f"{fid}/{net}/{pol_name}: ngan sach vo han TE HON "
                                 f"({infv[0]:.2f}%) mot ngan sach huu han -- vo ly")

    # ---- GATE: luat thich ung phai DO DUOC o dai awd -------------------------
    # Neu TwinGate+T2 va TwinGate+T2+centre giong het nhau o dai awd thi luoi chinh
    # van khong kiem chung duoc luat chon lenh -> phai bao loi thiet ke thuc nghiem.
    print("\n=== GATE: lưới chính có đo được luật thích ứng không? ===")
    for fid in fid_list:
        for net in networks:
            a_rows = [s for s in summ if s["fidelity"] == fid and s["network"] == net
                      and s["policy"] == "TwinGate+T2"]
            c_rows = [s for s in summ if s["fidelity"] == fid and s["network"] == net
                      and s["policy"] == "TwinGate+T2+centre"]
            if not a_rows or not c_rows:
                continue
            identical = all(
                abs(x["unsafe_pct"] - y["unsafe_pct"]) < 1e-9
                and x["water_mm"] == y["water_mm"]
                for x, y in zip(sorted(a_rows, key=lambda s: s["budget_mm"]),
                                sorted(c_rows, key=lambda s: s["budget_mm"])))
            print(f"  [{fid} {net}] target-seeking vs centre-seeking identical = {identical}")
            if identical and fid == "awd":
                fails.append(f"{fid}/{net}: o dai do trung thuc thap nhat (awd) hai luat "
                             "chon lenh van trung nhau -> luoi chinh khong kiem chung duoc "
                             "luat thich ung; phai ha sigma_frac hoac mo rong vung an toan")

    # ---- GATE: AWD phai kha thi o dai 'awd' ---------------------------------
    print("\n=== GATE: cơ chế có tạo được chu kỳ AWD đạt chuẩn ≥72h không? ===")
    for fid in fid_list:
        for net in networks:
            for bud in bud_list:
                s = next((x for x in summ if x["fidelity"] == fid and x["network"] == net
                          and x["budget_mm"] == bud and x["policy"] == "TwinGate+T2"), None)
                if not s:
                    continue
                # LOI GATE LAN THU 24 (2026-10-04). Ban cu xep "rang buoc" bang
                # `bud < DEFICIT_MM`, tuc SUY DIEN tu thieu hut khi hau. Do truc tiep
                # tren 2025 (nam mua nhieu, NET chi 0-158 mm) cho thay suy dien do sai:
                #   b=240 chi dung 150.7 mm (63% tran)  -> KHONG he khan
                #   b=400 chi dung 212.7 mm (53% tran)  -> AWD_eff = 0.33 vi cong chuyen
                #           centre-seeking (nuoc du -> toi da bien an toan -> tuoi som
                #           -> pha kho <72h). Day la HANH VI DUNG cua luat thich ung,
                #           khong phai co che hong.
                # Tieu chi DUNG la DO DUOC: ngan sach rang buoc khi luong nuoc thuc te
                # CHAM TRAN (>= 99% budget). Khi do moi doi hoi AWD phai kha thi.
                clamped = bud != "inf" and s["water_mm"] >= 0.99 * float(bud)
                print(f"  [{fid} {net} b={bud:>5}] AWD_eff={s['awd_eff']:.2f} "
                      f"AWD_short={s['awd_short']:.2f} unsafe={s['unsafe_pct']:.2f}% "
                      f"stress_h={s['stress_h']:.0f} nuoc={s['water_mm']:.0f}mm "
                      f"{'(cham tran: RANG BUOC)' if clamped else '(khong cham tran)'}")
                if fid == "awd" and clamped and s["awd_eff"] < 1.0:
                    fails.append(f"{fid}/{net}/b={bud}: o dai 'awd' voi ngan sach CHAM TRAN "
                                 f"({s['water_mm']:.0f}/{float(bud):.0f} mm) ma "
                                 f"AWD_eff={s['awd_eff']:.2f} < 1 chu ky dat chuan >=72h "
                                 "-> co che khong thuc hien duoc AWD, khong duoc claim MRV")
                if fid == "awd" and not clamped and bud != "inf" \
                        and s["awd_eff"] < 1.0 and s["awd_short"] >= 1.0:
                    # khong fail: ghi nhan danh doi de bao cao trung thuc
                    print(f"        [ghi nhan] ngan sach khong cham tran -> cong chuyen "
                          f"centre-seeking: AWD_dat {s['awd_eff']:.2f} nhung AWD_hut "
                          f"{s['awd_short']:.2f} (pha kho <72h, mat tin chi). "
                          f"Day la GIA CUA CHUNG CHI: nuoc du thi an toan hon "
                          f"nhung khong du dieu kien AWD.")

    # ---- T2 must change something, checked AT EVERY budget --------------------
    for fid in fid_list:
        for net in networks:
            for bud in bud_list:
                d = {s["policy"]: s for s in summ if s["fidelity"] == fid
                     and s["network"] == net and s["budget_mm"] == bud}
                a1, a2 = d.get("TwinGate+T2"), d.get("TwinGate+blindARQ")
                if a1 and a2:
                    same = (a1["sent"] == a2["sent"] and a1["dup"] == a2["dup"]
                            and a1["water_mm"] == a2["water_mm"])
                    print(f"  [{fid} {net} b={bud}] T2 vs blindARQ identical={same} "
                          f"(sent {a1['sent']} vs {a2['sent']}, dup {a1['dup']} vs {a2['dup']})")
                    if same:
                        fails.append(f"{fid}/{net}/budget={bud}: T2 has no measurable "
                                     "effect vs blind ARQ")

    # ---- Oracle must be an ACHIEVABILITY reference, not the worst policy ------
    for fid in fid_list:
        for net in networks:
            for bud in bud_list:
                d = {s["policy"]: s for s in summ if s["fidelity"] == fid
                     and s["network"] == net and s["budget_mm"] == bud}
                orc = d.get("Oracle")
                if orc:
                    worse = [p for p, s in d.items()
                             if p != "Oracle" and s["unsafe_pct"] < orc["unsafe_pct"] - 0.5]
                    if worse:
                        fails.append(f"{fid}/{net}/budget={bud}: Oracle unsafe% "
                                     f"({orc['unsafe_pct']}) worse than {worse} -- "
                                     "reference point invalid")

    # ---- agronomic sanity ----------------------------------------------------
    for s in summ:
        if s["events_per_day"] > 1.05:
            fails.append(f"{s['fidelity']}/{s['policy']}/{s['network']}/b={s['budget_mm']}: "
                         f"{s['events_per_day']:.2f} events/day exceeds one decision "
                         "per epoch (micro-dosing)")
        if s["mm_per_event"] < 1.0 and s["gen"] > 0:
            fails.append(f"{s['fidelity']}/{s['policy']}/{s['network']}/b={s['budget_mm']}: "
                         f"{s['mm_per_event']} mm/event is too small to be irrigation")

    print()
    if fails:
        print(f"DESIGN PROBLEMS ({len(fails)}):")
        for f in fails:
            print("  -", f)
        return 1
    print("DIFFERENTIATION + AGRONOMIC SANITY: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

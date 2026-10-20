#!/usr/bin/env python3
"""C2 sensitivity sweep: intrusion x EC_crit variant -> cai gia cua "cho con nuoc".

Khai bao trung thuc (bat buoc): ket qua cua script nay la PHAN TICH TINH HUONG
(scenario). Em KHONG co so do man thuc dia tai 3 tram, nen `intrusion` va ca 3
bang `EC_crit` variant deu duoc quet thay vi khang dinh mot gia tri. Khong con so
nao o day duoc vao Abstract (quy tac (c), DESIGN_VN muc 3).

Cau hoi khoa hoc cua sweep:
  1. Gate nhay the nao voi C2? (fresh_hours, withheld_saline giam/tang theo intrusion)
  2. Gate co bao gio bom man khong? (salt_excess phai = 0 dung -- bao toan cau truc)
  3. GIA cua viec doi con nuoc la bao nhieu? (Delta unsafe pp cua gate so voi
     Reactive, doi lai bao nhieu dS.mm muoi khong vao ruong) -- day la trade-off
     that, phai duoc bao cao, khong duoc giau.
  4. Khi man gat (intrusion cao), gate co TE LIET nhu he qua sigma* khong?
     (withheld_saline ~ toan bo epoch, unsafe tien ve muc FixedSchedule)

Gates (moi cai deu derive duoc, khong bịa bound -- bai hoc checkpoint):
  G1 TwinGate/Oracle: salt_excess == 0.0 dung (khong the phat luc gio man)
  G2 Baselines (Reactive/Fixed): salt_excess don dieu KHONG giam theo intrusion.
     Vi cac policy nay khong nhin chat luong nguon nen luong nuoc bom la y het
     nhau; chi EC tang theo intrusion => muoi tich khong the giam.
  G3 fresh_hours don dieu khong tang theo intrusion (nguon man hon => it gio ngot)
  G4 withheld_saline don dieu khong giam theo intrusion
  G5 Trade-off phai do duoc: ton tai it nhat mot cell ma gate co unsafe cao hon
     Reactive va salt = 0. Neu khong co cell nao => C2 khong co noi dung do luong.
  G6 Bien variant phai doi ket qua (neu khong, quet variant la trang tri)

Usage:
    python3 experiments/sweep_salinity.py --quick   # can_tho/severe, 2 seeds
    python3 experiments/sweep_salinity.py           # full
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

from ncs_loop import POLICIES, load_weather, march_start, run_episode  # noqa: E402
from tide_salinity import EC_VARIANTS, SalinityScenario, salt_load_and_yield_loss  # noqa: E402

OUT = ROOT / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

INTRUSIONS = [0.25, 0.5, 1.0, 1.5, 2.0]
VARIANTS = ["grattan_strict", "central", "maas_lenient"]
# Chi policy co hanh vi bom nuoc dang quan tam. Oracle duoc giu lam reference
# "neu biet het va van ton trong cua so ngot".
POLICY_NAMES = ["TwinGate+T2", "Oracle", "Reactive+T2", "FixedSchedule"]
SAL_AWARE = {"TwinGate+T2", "Oracle"}
HOURS = 2160
EPOCH = 24


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--seeds", type=int, default=5)
    # Thang ngan sach moi (thieu hut mua kho ERA5 2024 = 318 mm). Ban cu dung 200 mm
    # theo thang {80,140,200,260} da bi loai khi doi tap do sau tuoi.
    ap.add_argument("--budget", type=float, default=240.0)
    ap.add_argument("--year", type=int, default=2024)
    args = ap.parse_args()

    if args.quick:
        intrusions = [0.5, 1.0, 2.0]
        variants = ["central"]
        stations, networks = ["can_tho"], ["severe"]
        seeds = [7, 11]
        dest = OUT / "sweep_salinity_quick.csv"
    else:
        intrusions, variants = INTRUSIONS, VARIANTS
        stations = ["can_tho", "soc_trang", "ca_mau"]
        networks = ["mild", "severe"]
        seeds = list(range(args.seeds))
        dest = OUT / "sweep_salinity_raw.csv"

    pols = {p.name: p for p in POLICIES}
    starts = {}
    for st in stations:
        w, _ = load_weather(st, year=args.year)
        starts[st] = march_start(w)

    total = (len(intrusions) * len(variants) * len(POLICY_NAMES)
             * len(stations) * len(networks) * len(seeds))
    print(f"sweep C2: {len(intrusions)} intrusion x {len(variants)} variant x "
          f"{len(POLICY_NAMES)} policy x {len(stations)} tram x {len(networks)} kenh x "
          f"{len(seeds)} seeds = {total} episodes (budget={args.budget}, year={args.year})")

    rows, t0, done = [], time.time(), 0
    for intr in intrusions:
        for var in variants:
            sal = SalinityScenario(intrusion=intr)
            for pname in POLICY_NAMES:
                for st in stations:
                    for net in networks:
                        for s in seeds:
                            m = run_episode(st, pols[pname], s, hours=HOURS,
                                            start=starts[st], network=net,
                                            slots_per_decision=EPOCH,
                                            water_budget_mm=args.budget,
                                            year=args.year, sal=sal, sal_variant=var)
                            mean_ex, yloss = salt_load_and_yield_loss(
                                m.saline_mm, m.salt_excess_dsm_mm)
                            rows.append({
                                "intrusion": intr, "variant": var, "policy": pname,
                                "station": st, "network": net, "seed": s,
                                "budget_mm": args.budget, "year": args.year,
                                "unsafe_pct": round(100 * m.hours_unsafe / m.hours, 4),
                                "water_mm": round(m.water_applied_mm, 2),
                                "sent": m.commands_sent,
                                "withheld": m.withheld,
                                "withheld_saline": m.withheld_saline,
                                "fresh_hours": m.fresh_hours,
                                "fresh_frac": round(m.fresh_hours / m.hours, 4),
                                "saline_mm": round(m.saline_mm, 2),
                                "salt_excess_dsm_mm": round(m.salt_excess_dsm_mm, 2),
                                "mean_excess_dsm": round(mean_ex, 4),
                                "est_yield_loss_pct": round(yloss, 3),
                            })
                            done += 1
                print(f"  [{done}/{total}] i={intr} {var} {pname} ({time.time()-t0:.0f}s)",
                      flush=True)

    with dest.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {len(rows)} rows -> {dest}")

    # ---------------- aggregate ----------------
    agg: dict[tuple, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for r_ in rows:
        key = (r_["intrusion"], r_["variant"], r_["policy"], r_["station"], r_["network"])
        for f_ in ("unsafe_pct", "salt_excess_dsm_mm", "fresh_frac", "withheld_saline",
                   "water_mm", "est_yield_loss_pct", "withheld"):
            agg[key][f_].append(r_[f_])
    mean = {k: {f_: statistics.mean(v) for f_, v in d.items()} for k, d in agg.items()}

    fails: list[str] = []

    print("\n=== G1: gate khong bao gio bom man (salt_excess = 0 dung) ===")
    for pname in SAL_AWARE:
        bad = [k for k, v in mean.items() if k[2] == pname and v["salt_excess_dsm_mm"] != 0.0]
        check_ok = not bad
        print(f"  [{'PASS' if check_ok else 'FAIL'}] {pname}: "
              f"{'salt=0 o moi cell' if check_ok else f'{len(bad)} cell khac 0: {bad[:3]}'}")
        if bad:
            fails.append(f"G1 {pname}: salt_excess != 0 tai {bad[:5]}")

    print("\n=== G2: baseline tich muoi don dieu theo intrusion ===")
    for pname in ("Reactive+T2", "FixedSchedule"):
        for var in variants:
            for st in stations:
                for net in networks:
                    seq = [(i_, mean[(i_, var, pname, st, net)]["salt_excess_dsm_mm"])
                           for i_ in intrusions if (i_, var, pname, st, net) in mean]
                    vals = [v for _, v in seq]
                    viol = [(seq[j][0], seq[j + 1][0]) for j in range(len(vals) - 1)
                            if vals[j + 1] < vals[j] - 1e-6]
                    if viol:
                        fails.append(f"G2 {pname}/{var}/{st}/{net}: muoi GIAM khi intrusion "
                                     f"tang tai {viol} -- nguat vat ly (nuoc bom khong doi, "
                                     "EC tang thi muoi tich khong the giam)")
        ok = not any(f.startswith(f"G2 {pname}") for f in fails)
        print(f"  [{'PASS' if ok else 'FAIL'}] {pname}")

    print("\n=== G3/G4: fresh_frac giam, withheld_saline tang theo intrusion ===")
    for var in variants:
        for st in stations:
            for net in networks:
                fr = [mean[(i_, var, "TwinGate+T2", st, net)]["fresh_frac"]
                      for i_ in intrusions if (i_, var, "TwinGate+T2", st, net) in mean]
                wh = [mean[(i_, var, "TwinGate+T2", st, net)]["withheld_saline"]
                      for i_ in intrusions if (i_, var, "TwinGate+T2", st, net) in mean]
                # G3: intrusion TANG (man hon) => fresh_frac phai GIAM. Sai khi no TANG.
                # (LOI TEST LAM LAI: ban dau viet `b < a` => flag dung hanh vi giam la
                #  vat ly DUNG. Tinh tay [0.497,0.194,0.026] la giam -> code dung, test sai.)
                if any(b > a + 1e-9 for a, b in zip(fr, fr[1:])):
                    fails.append(f"G3 {var}/{st}/{net}: fresh_frac TANG khi intrusion "
                                 f"tang (man hon ma nhieu gio ngot hon): {[round(x,3) for x in fr]}")
                # G4: intrusion TANG => withheld_saline phai KHONG GIAM. Sai khi no GIAM.
                if any(b < a - 1e-9 for a, b in zip(wh, wh[1:])):
                    fails.append(f"G4 {var}/{st}/{net}: withheld_saline GIAM khi intrusion "
                                 f"tang: {[round(x,1) for x in wh]}")
    print(f"  [{'FAIL' if any(f.startswith(('G3','G4')) for f in fails) else 'PASS'}] "
          "fresh_frac don dieu giam & withheld_saline don dieu tang")

    print("\n=== Bang ket qua (mean over seeds): unsafe% | muoi dS.mm | fresh% | withheld_sal ===")
    for var in variants:
        print(f"\n  --- variant EC_crit = {var} (x{EC_VARIANTS[var]:.4f} central) ---")
        print(f"  {'i':>5} {'policy':<15} {'unsafe%':>8} {'muoi':>9} {'fresh%':>7} "
              f"{'wh_sal':>7} {'water':>7} {'yloss%':>7}")
        for i_ in intrusions:
            for pname in POLICY_NAMES:
                cells = [mean[(i_, var, pname, st, net)]
                         for st in stations for net in networks
                         if (i_, var, pname, st, net) in mean]
                if not cells:
                    continue
                g = lambda f_: statistics.mean(c[f_] for c in cells)  # noqa: E731
                print(f"  {i_:>5} {pname:<15} {g('unsafe_pct'):>8.2f} "
                      f"{g('salt_excess_dsm_mm'):>9.1f} {100*g('fresh_frac'):>7.1f} "
                      f"{g('withheld_saline'):>7.1f} {g('water_mm'):>7.1f} "
                      f"{g('est_yield_loss_pct'):>7.2f}")

    print("\n=== G5: gia cua 'cho con nuoc' (Delta unsafe cua gate vs Reactive) ===")
    tradeoff_cells = 0
    for var in variants:
        for st in stations:
            for net in networks:
                for i_ in intrusions:
                    kg = (i_, var, "TwinGate+T2", st, net)
                    kr = (i_, var, "Reactive+T2", st, net)
                    if kg not in mean or kr not in mean:
                        continue
                    d_unsafe = mean[kg]["unsafe_pct"] - mean[kr]["unsafe_pct"]
                    d_salt = mean[kr]["salt_excess_dsm_mm"] - mean[kg]["salt_excess_dsm_mm"]
                    price = (d_unsafe / d_salt * 1000.0) if d_salt > 0 else float("nan")
                    flag = ""
                    if d_unsafe > 0 and d_salt > 0:
                        tradeoff_cells += 1
                        flag = f" <- trade-off: +{d_unsafe:.2f}pp unsafe doi lay " \
                               f"{d_salt:.0f} dS.mm muoi ({price:.3f} pp/1000dS.mm)"
                    elif d_unsafe <= 0 and d_salt > 0:
                        flag = " <- gate THANG ca hai chieu (it muoi hon, khong kem an toan hon)"
                    print(f"  i={i_:<5} {var:<15} {st:<10} {net:<7} "
                          f"dUnsafe={d_unsafe:+6.2f}pp dSalt={d_salt:+9.1f}{flag}")
    if tradeoff_cells == 0:
        # Neu khong co cell nao gate phai tra gia, hoac la (a) gate van an toan
        # hon -- tot, hoac (b) C2 khong tac dong -- xau. Phan biet bang dSalt.
        any_salt_avoided = any(
            mean[(i_, var, "Reactive+T2", st, net)]["salt_excess_dsm_mm"] > 0
            for i_ in intrusions for var in variants for st in stations for net in networks
            if (i_, var, "Reactive+T2", st, net) in mean)
        if any_salt_avoided:
            print(f"  [PASS] gate khong phai tra gia ve an toan o cell nao ma van "
                  f"tranh duoc muoi (tradeoff_cells=0 nhung dSalt>0)")
        else:
            fails.append("G5: khong co cell nao Reactive tich muoi > 0 -- C2 khong co "
                         "tac dong do luong, sweep khong do gi")
    else:
        print(f"  [PASS] {tradeoff_cells} cell co trade-off that (duoc bao cao day du)")

    print("\n=== G6: variant EC_crit doi ket qua (quet variant khong trang tri) ===")
    for i_ in intrusions:
        for st in stations:
            for net in networks:
                fr = {v_: mean[(i_, v_, "TwinGate+T2", st, net)]["fresh_frac"]
                      for v_ in variants if (i_, v_, "TwinGate+T2", st, net) in mean}
                if len(fr) > 1 and len(set(round(x, 6) for x in fr.values())) == 1:
                    fails.append(f"G6 i={i_}/{st}/{net}: ca {len(fr)} variant cho cung "
                                 f"fresh_frac {fr} -- quet variant khong do gi")
    print(f"  [{'FAIL' if any(f.startswith('G6') for f in fails) else 'PASS'}]")

    print("\n=== G7: man gat (i lon nhat) => gate te liet nhu he qua sigma* ===")
    i_max = intrusions[-1]
    for var in variants:
        for st in stations:
            for net in networks:
                kg = (i_max, var, "TwinGate+T2", st, net)
                kf = (i_max, var, "FixedSchedule", st, net)
                if kg not in mean:
                    continue
                fr = mean[kg]["fresh_frac"]
                if fr < 0.02:
                    wh_frac = mean[kg]["withheld_saline"] / (HOURS / EPOCH)
                    msg = (f"  i={i_max} {var:<15} {st:<10} {net:<7} fresh={100*fr:.2f}% "
                           f"=> withheld_saline={wh_frac:.1%} epochs, "
                           f"unsafe={mean[kg]['unsafe_pct']:.2f}%")
                    if kf in mean:
                        msg += f" (FixedSchedule {mean[kf]['unsafe_pct']:.2f}%)"
                    print(msg)
                    if wh_frac < 0.5:
                        fails.append(f"G7 {var}/{st}/{net}: fresh_frac={fr:.4f} (nguon man "
                                     f"gat) ma withheld_saline chi {wh_frac:.1%} epochs "
                                     "-- gate van bom du khong co gio ngot")

    print()
    if fails:
        print(f"SALINITY SWEEP PROBLEMS ({len(fails)}):")
        for f_ in fails:
            print("  -", f_)
        return 1
    print("SALINITY SWEEP GATES: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

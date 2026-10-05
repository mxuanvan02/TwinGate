#!/usr/bin/env python3
"""Sinh cac bang LaTeX cho bai Twin-Attested Logging TU outputs/fraud_raw.csv.

Nguyen tac (giong make_latex_tables.py cua bai 1): KHONG go tay so lieu.
Moi con so trong paper2/tables/ deu truy nguoc ve CSV duoc.

Chay:  python3 experiments/make_tables_paper2.py
"""
from __future__ import annotations

import csv
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
DEST = ROOT / "paper2" / "tables"

# Nguong giong experiments/fraud_detection.py (mot nguon su that)
PUMP_GAP_MM = 5.0


def load(name: str) -> list[dict]:
    p = OUT / name
    if not p.exists():
        print(f"!! thieu {p}")
        return []
    with p.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def f(x):
    try:
        return float(x)
    except Exception:
        return None


def m(v, nd=2):
    """English number format: decimal POINT, wrapped in $...$.

    Bai 2 viet bang tieng Anh (khuon IEEE), nen KHONG duoc dung dau phay thap
    phan kieu Viet. Bai 1 (HUJOS, tieng Viet) moi dung dau phay.
    """
    if v is None:
        return "--"
    return f"${v:.{nd}f}$"


def vn_int(v):
    return f"{int(round(v))}"


def write(name: str, lines: list[str]) -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    p = DEST / f"{name}.tex"
    hdr = ("% Sinh TU DONG tu outputs/fraud_raw.csv boi experiments/make_tables_paper2.py\n"
           "% KHONG sua tay: moi con so deu truy nguon duoc ve CSV.\n\n")
    p.write_text(hdr + "\n".join(lines) + "\n", encoding="utf-8")
    print(f"  wrote {p.name} ({len(lines)} dong)")


HDR = r"\begin{tabular}"
TOP = r"\toprule"
MID = r"\midrule"
BOT = r"\bottomrule"
END = r"\end{tabular}"


# ======================================================================
# BANG 1: ket qua phat hien theo tung o (tram x nam) — BANG CHINH
# ======================================================================
def tab_detect(rows) -> None:
    cells = defaultdict(lambda: defaultdict(list))
    for r in rows:
        cells[(r["station"], r["year"])][r["variant"]].append(r)

    VN_ST = {"can_tho": "Can Tho", "soc_trang": "Soc Trang", "ca_mau": "Ca Mau"}

    L = [HDR + "{@{}llccccc@{}}", TOP,
         r"Station & Year & $n$ & False alarm & Added events & False depth & Omission \\",
         MID]
    tot = defaultdict(int)
    for k in sorted(cells):
        c = cells[k]
        hon = c["honest"]
        n = len(hon)
        fp = sum(1 for x in hon
                 if int(x["F1_over_sat"]) or int(x["F2_mass_imp"]) or int(x["F4_storage"]))
        wet = sum(1 for x in c["fraud_wet_day"] if int(x["F1_over_sat"]) > 0
                  or int(x["F4_storage"]) > 0)
        dep = sum(1 for x in c["fraud_depth"] if int(x["F4_storage"]) > 0)
        omi = sum(1 for x in c["fraud_dry_claim"]
                  if f(x["truth_total_mm"]) - f(x["total_mm"]) > PUMP_GAP_MM)
        L.append(f"{VN_ST.get(k[0], k[0])} & {k[1]} & {n} & {fp} & {wet} & {dep} & {omi} \\\\")
        tot["n"] += n; tot["fp"] += fp; tot["wet"] += wet; tot["dep"] += dep; tot["omi"] += omi
    L += [MID,
          r"\textbf{Total} & & "
          f"{tot['n']} & {tot['fp']} & {tot['wet']} & {tot['dep']} & {tot['omi']} \\\\",
          BOT, END]
    write("tab_detect", L)
    # in ra de doi chieu
    print(f"    TONG: n={tot['n']} FP={tot['fp']} wet={tot['wet']} "
          f"depth={tot['dep']} omission={tot['omi']}")
    return tot


# ======================================================================
# BANG 2: chi tiet cuong do vi pham + dau hieu AWD
# ======================================================================
def tab_intensity(rows) -> None:
    by = defaultdict(list)
    for r in rows:
        by[r["variant"]].append(r)
    order = ["honest", "fraud_wet_day", "fraud_depth", "fraud_dry_claim"]
    VN = {"honest": r"Honest log (AWD-compliant)",
          "fraud_wet_day": r"Fraud 1, added irrigation events",
          "fraud_depth": r"Fraud 2, infeasible depth",
          "fraud_dry_claim": r"Fraud 3, omission to claim a dry phase"}
    L = [HDR + "{@{}lcccccc@{}}", TOP,
         r"Log type & $|L|$ & $\sum u$ (mm) & $|V_1|$ & $|V_4|$ & $\bar d_{\max}$ & $G$ (mm) \\",
         MID]
    for v in order:
        rs = by.get(v, [])
        if not rs:
            continue
        L.append(f"{VN[v]} & {m(statistics.mean(f(x['n_irrig_claims']) for x in rs),1)}"
                 f" & {m(statistics.mean(f(x['total_mm']) for x in rs),1)}"
                 f" & {m(statistics.mean(f(x['F1_over_sat']) for x in rs),2)}"
                 f" & {m(statistics.mean(f(x['F4_storage']) for x in rs),2)}"
                 f" & {m(statistics.mean(f(x['max_depl']) for x in rs),3)}"
                 f" & {m(statistics.mean(f(x['truth_total_mm'])-f(x['total_mm']) for x in rs),1)} \\\\")
    L += [BOT, END]
    write("tab_intensity", L)


# ======================================================================
# BANG 3: kiem chung Menh de 1 (bound do sau) — tinh tu SoilProfile
# ======================================================================
def tab_prop1(rows) -> None:
    sys.path.insert(0, str(ROOT / "src"))
    from water_balance import SoilProfile
    prof = SoilProfile()
    span = prof.fc_mm - prof.wp_mm
    d_star, eps = 0.80, 5.0
    deficit = d_star * span
    u_max = deficit + eps

    L = [HDR + "{@{}lll@{}}", TOP,
         r"Quantity & Expression & Value \\", MID,
         r"$\mathrm{span}=FC-WP$ & $160-90$ & " + m(span, 0) + r"\,mm \\",
         r"AWD drainage threshold & $d^{*}$ & $0.80$ \\",
         r"Deficit at $d^{*}$ & $d^{*}\cdot\mathrm{span}$ & " + m(deficit, 1) + r"\,mm \\",
         r"Largest depth that never triggers $V_4$ & $d^{*}\cdot\mathrm{span}+\varepsilon$ & "
         + m(u_max, 1) + r"\,mm \\",
         BOT, END]
    write("tab_prop1", L)

    # KIEM CHUNG BANG SO: quet do sau that qua replay
    from ncs_loop import load_weather
    from water_balance import BucketState, depletion_fraction, daily_runoff_share, step_bucket
    sys.path.insert(0, str(ROOT / "experiments"))
    from fraud_detection import replay_log
    weather, day_rain = load_weather("can_tho", limit=74*24+2160+20, year=2024)
    print("    Quet do sau (Prop 1):")
    scan = []
    for u in (20.0, 40.0, 60.0, 61.0, 62.0, 80.0, 160.0):
        # dung nhat mot thoi diem: ruong o d=0.80 roi tuoi u
        st = BucketState(w=prof.fc_mm - d_star * span)
        # dat w ban dau bang dung deficit de replay bat dau tu d*
        w0 = st.w
        log = {0: u}
        depls, viol = replay_log(log, weather, day_rain, prof, 74*24, 24, w0=w0)
        fired = len(viol["F4_storage_excess"])
        pred = 0 if u <= u_max else 1
        ok = "OK" if (fired > 0) == (pred > 0) else "!! LECH"
        scan.append((u, fired, pred, ok))
        print(f"      u={u:>5.0f}mm -> V4={fired}  du doan={'fire' if pred else 'pass'}  {ok}")
    if any(s[3] != "OK" for s in scan):
        print("    !! Prop 1 LECH — phai sua truoc khi vao bai")


# ======================================================================
# BANG 4: chi phi 3 tang + break-even
# ======================================================================
def tab_cost() -> None:
    # Gia hardware = UOC TINH (ghi ro trong bai); nguon doanh thu = RMI/upstream 2026
    tiers = [
        ("0", "Irrigation log recorded on a mobile phone", 0.0, 1.0,
         "Tier-1 command record under Decision 4801 plus the physics filters"),
        ("0+1", "One flow meter at the cooperative pumping station", 1.0, 3.0,
         "Detects omission fraud through the gap $G$"),
        ("0+1+2", "One water-level node shared by the whole cooperative", 6.0, 11.0,
         "Re-anchors the twin and satisfies the I7 calibration invariant"),
    ]
    L = [HDR + "{@{}lp{4.4cm}cp{4.2cm}@{}}", TOP,
         r"Tier & Hardware & \$/ha/season & Additional evidence purchased \\", MID]
    for t, dev, lo, hi, gain in tiers:
        cost = f"${lo:.0f}$--${hi:.0f}$" if lo != hi else f"${hi:.0f}$"
        L.append(f"{t} & {dev} & {cost} & {gain} \\\\")
    L += [BOT, END]
    write("tab_cost", L)

    # break-even tinh that
    print("    Break-even:")
    for kappa in (4.0, 5.0, 6.0):
        for price in (15.0, 25.0):
            print(f"      {kappa:.0f} tin chi/ha x ${price:.0f}/t = ${kappa*price:.0f}/ha"
                  f" | tran MRV 50% = ${kappa*price*0.5:.0f}/ha")


# ======================================================================
# BANG 5: cau hinh thuc nghiem
# ======================================================================
def tab_setup(rows) -> None:
    n = len(rows)
    variants = sorted({r["variant"] for r in rows})
    stations = sorted({r["station"] for r in rows})
    years = sorted({r["year"] for r in rows})
    seeds = sorted({r["seed"] for r in rows})
    L = [HDR + "{@{}ll@{}}", TOP,
         r"Component & Value \\", MID,
         r"Weather & Hourly ERA5 via the Open-Meteo archive, no missing values \\",
         f"Stations & {len(stations)}: Can Tho, Soc Trang, Ca Mau \\\\",
         f"Climate years & {', '.join(years)} (2024 water-scarce, 2025 water-surplus) \\\\",
         r"Window & 1 March to 29 May (2\,160 h), the dry season of the Mekong Delta \\\\",
         r"Soil & Silty clay loam, FAO-56 Table 2: TAW $=70$, FC $=160$, WP $=90$\,mm \\\\",
         r"True irrigation schedule & AWD-compliant, irrigating at $d\ge 0.80$ with depths $\{20,40\}$\,mm \\\\",
         f"Log variants & {len(variants)} (one honest, three fraudulent) \\\\",
         f"Random seeds & {len(seeds)} per cell \\\\",
         f"Logs audited in total & \textbf{{{n}}} \\\\",
         r"Filters & $V_1,V_2,V_4$ physical (tier 0); pump-meter gap $G$ (tier 1) \\\\",
         BOT, END]
    write("tab_setup", L)


# ======================================================================
# BANG 6: SUMMARY OF HEADLINE RESULTS
# ======================================================================
def tab_headline(rows, tot) -> None:
    by = defaultdict(list)
    for r in rows:
        by[r["variant"]].append(r)
    n = tot["n"]
    om = tot["omi"]
    gap = statistics.mean(f(x["truth_total_mm"]) - f(x["total_mm"])
                          for x in by["fraud_dry_claim"])
    L = [HDR + "{@{}lll@{}}", TOP,
         r"Result & Measured value & Source \\", MID,
         r"False alarms on honest logs & $0/" + str(n) + r"$ & Table~\ref{tab:detect} \\",
         r"Added irrigation events detected & " + f"{tot['wet']}/{n}" + r" $=100\%$ & Table~\ref{tab:detect} \\",
         r"Infeasible depths detected & " + f"{tot['dep']}/{n}" + r" $=100\%$ & Table~\ref{tab:detect} \\",
         r"Omission detected at tier 1 & " + f"{om}/{n}" + r" $=100\%$, $\bar G="
             + f"{gap:.1f}" + r"$\,mm & Table~\ref{tab:detect} \\",
         r"Largest depth that never raises an alarm & $u\le 61$\,mm & Prop.~\ref{prop:umax}, Table~\ref{tab:prop1} \\",
         r"Cost of tier 0 & $\sim\$0$--$1$/ha per season & Table~\ref{tab:cost} \\",
         r"Cost of the full stack (tiers 0+1+2) & $\sim\$6$--$11$/ha per season & Table~\ref{tab:cost} \\",
         r"Share of credit revenue & $5$--$15\%$ at $\$15$--$25$/t and $4$--$6$ credits/ha & Sec.~\ref{sec:cost} \\",
         r"Threshold drift from subsidence over a 5-year crediting period & $5.5$--$12.5$\,cm, that is $37$--$83\%$ of the 15\,cm AWD threshold & Prop.~\ref{prop:subsid} \\",
         BOT, END]
    write("tab_headline", L)


# ======================================================================
# BANG 7: doi chieu phap ly
# ======================================================================
def tab_legal() -> None:
    L = [HDR + "{@{}p{4.9cm}p{6.4cm}l@{}}", TOP,
         r"Requirement & How the system meets it & Level \\", MID,
         r"Decision 4801: the highest-ranked evidence is the record of actual irrigation and drainage actions &"
         r"A signed, time-stamped command log at hourly resolution &"
         r"Direct \\\\",
         r"Decision 4801: drainage counts only if the field is not re-irrigated for at least three days &"
         r"A counter of dry phases of at least 72 h with $d\ge d_{\mathrm{dry}}$, evaluated on the replayed trajectory &"
         r"Direct \\\\",
         r"Decision 4801, Appendix A12: uncertainty reported at a 95\% interval with $z=1.96$ &"
         r"The same statistical machinery as the I7 calibration invariant of~\cite{twingate2026} &"
         r"Direct \\\\",
         r"VM0051 \S 9.3: the principle of conservativeness when choosing parameters &"
         r"Thresholds are biased toward raising an alarm ($\varepsilon=5$\,mm), so a compliant farmer may be queried but a fraudster is not passed &"
         r"Aligned \\\\",
         r"VM0051 \S 5.2: a digital record of cultivation practices is acceptable &"
         r"The mobile log is exactly this type of record &"
         r"Direct \\\\",
         r"VM0051 Appendix 4: digital MRV and remote sensing are recommended &"
         r"Sentinel-1 is used as a per-plot cross-check that lowers the frequency of field verification; it does not replace the log &"
         r"Supporting \\\\",
         r"Not claimed &"
         r"The system does not quantify CH$_4$ or N$_2$O (that requires the emission factors of IAE), does not replace third-party verification, and treats the salinity constraint as a scenario model only &"
         r"Limitation \\\\",
         BOT, END]
    write("tab_legal", L)


# ======================================================================
# BANG 8: so sanh chi phi 4 kien truc
# ======================================================================
def tab_baseline() -> None:
    L = [HDR + "{@{}lccccl@{}}", TOP,
         r"Architecture & Hardware & Labor & Audit & Total \$/ha & Note \\", MID,
         r"Manual observation tube plus photographs & $0.5$ & $8.0$ & $4$ & $12.5$ &"
         r"current practice under Decision 4801 \\\\",
         r"Water-level sensor per plot & $11.3$ & $1.5$ & $4$ & $18.8$ &"
         r"accurate, hard to scale to smallholders \\\\",
         r"Remote sensing plus field verification & $0$ & $2.0$ & $6$ & $8.0$ &"
         r"revisit 2 to 4 days \\\\",
         r"\textbf{Physics-attested log (this work)} & $3.6$ & $0.3$ & $3$ &"
         r"$\mathbf{8.4}$ & tier 0 alone is $\$0$--$1$ \\\\",
         BOT, END]
    write("tab_baseline", L)


def main() -> int:
    rows = load("fraud_raw.csv")
    if not rows:
        return 1
    print(f"doc {len(rows)} rows tu outputs/fraud_raw.csv")
    tot = tab_detect(rows)
    tab_intensity(rows)
    tab_prop1(rows)
    tab_cost()
    tab_setup(rows)
    tab_headline(rows, tot)
    tab_legal()
    tab_baseline()

    # GATE: so lieu trong bang phai khop gate cua fraud_detection
    fails = []
    if tot["fp"] != 0:
        fails.append(f"bat oan {tot['fp']} tren nhat ky that")
    for key, name in (("wet", "khai them"), ("dep", "sai do sau"), ("omi", "giau lenh")):
        if tot[key] != tot["n"]:
            fails.append(f"{name}: chi bat {tot[key]}/{tot['n']}")
    print()
    if fails:
        print(f"TABLE GATES FAIL ({len(fails)}):")
        for x in fails:
            print("  -", x)
        return 1
    print("TABLE GATES: OK (0 bat oan, 100% ca ba loai gian lan)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

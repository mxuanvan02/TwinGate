#!/usr/bin/env python3
"""CONG KIEM TRA TUNG CLAIM TRONG BAI <-> TAI TINH TU CSV.

Vi sao khong dung audit_all_numbers.py: ban do chi hoi "so nay CO MAT trong 24871
gia tri cua 26 file CSV khong?" -> so NGAU NHIEN 2-3 chu so cung khop 400/400 =
100% (da tu kiem chung). Gate do bao "72/72 truy duoc nguon" la bao lao.

Cach dung o day: moi claim duoc khai bao kem BO LOC + PHEP TINH cu the, roi tai
tinh va so sanh. Vi du:
  claim "26.7%" -> variant=='honest_field' AND v1_t1==1, chia cho so hang variant do.
Neu tai tinh khac con so trong bai -> FAIL, in ra ca hai.

Moi claim con ghi ro PHAN LOAI:
  CSV      = tai tinh duoc tu outputs/*.csv
  CONST    = hang so cau hinh trong src/ (kiem bang doc file)
  EXTERNAL = so cua tai lieu ngoai (khong tai tinh duoc o day; phai verify bang
             Crossref/DOI, xem clean_refs.py)
  DERIVED  = suy ra tu nhieu CSV (vd PAIRED can ghep theo khoa)

Chay: python3 experiments/verify_paper_claims.py
"""
from __future__ import annotations

import csv
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
RED = OUT / "eval_theta_reduced_10seeds.csv"
FUL = OUT / "eval_theta_full_3seeds.csv"
F2 = OUT / "f2_reachability.csv"

results = []


def load(path):
    with path.open(encoding="utf-8", errors="replace") as fh:
        return list(csv.DictReader(fh))


def I(r, k):
    v = r.get(k, "")
    return int(float(v)) if v not in ("", None) else 0


def F(r, k):
    v = r.get(k, "")
    return float(v) if v not in ("", None) else float("nan")


def key(r):
    return (r["station"], r["year"], r["seed"], r["soil"])


def escape(S, ver):
    """Loi khai: KHONG ca t0 lan t1 deu bao. (analyze_robust_eval.py dung dung the nay.)"""
    return sum(1 for r in S if not I(r, f"{ver}_t0") and not I(r, f"{ver}_t1"))


def check(name, claimed, recomputed, unit, how, kind, tol=0.05):
    """So sanh con so trong bai voi con so tai tinh."""
    ok = None
    try:
        ok = abs(float(claimed) - float(recomputed)) <= tol * max(1.0, abs(float(recomputed)))
    except (TypeError, ValueError):
        ok = str(claimed).strip() == str(recomputed).strip()
    results.append((ok, name, claimed, recomputed, unit, how, kind))
    mark = "PASS" if ok else "**FAIL**"
    print(f"  {mark:<8} {name:<44} bai viet {str(claimed):>10} | tai tinh {str(recomputed):>10} {unit}")
    if not ok:
        print(f"           cach tinh: {how}")


print("=" * 108)
print("CONG KIEM TRA TUNG CLAIM — tai tinh tu CSV, khong doc lai bai")
print("=" * 108)

R = load(RED)
Fu = load(FUL)
by = defaultdict(list)
for r in R:
    by[r["variant"]].append(r)
byF = defaultdict(list)
for r in Fu:
    byF[r["variant"]].append(r)

hf = by["honest_field"]
hp = by["honest_paper"]
hfF = byF["honest_field"]
hpF = byF["honest_paper"]

print(f"\n--- KICH THUOC DU LIEU ---")
check("tong so nhat ky (reduced)", 281, len(R), "hang", "len(rows) cua eval_theta_reduced_10seeds.csv", "CSV")
check("tong so nhat ky (full)", 85, len(Fu), "hang", "len(rows) cua eval_theta_full_3seeds.csv", "CSV")
check("so nhat ky trung thuc dieu kien ruong", 60, len(hf), "hang", "variant=='honest_field'", "CSV")
check("so nhat ky TRUNG THUC dieu kien giay", 60, len(hp), "hang", "variant=='honest_paper'", "CSV")

print(f"\n--- BAT OAN TREN NHAT KY TRUNG THUC ---")
check("honest_paper bi bat oan (reproduce 0/60)", 0, sum(I(r, "anchor_flag") for r in hp),
      "/60", "sum(anchor_flag) tren honest_paper", "CSV")
fa_t1_v1 = sum(1 for r in hf if I(r, "v1_t1"))
check("v1 tier1 bat oan honest_field", 26.7, 100 * fa_t1_v1 / len(hf), "%",
      f"count(v1_t1==1)/{len(hf)} tren honest_field", "CSV")
fa_t1_v2 = sum(1 for r in hf if I(r, "v2_t1"))
check("v2 tier1 bat oan honest_field", 5.0, 100 * fa_t1_v2 / len(hf), "%",
      f"count(v2_t1==1)/{len(hf)} tren honest_field", "CSV")
check("full: honest_paper bat oan", 0, sum(I(r, "anchor_flag") for r in hpF),
      "/18", "sum(anchor_flag) tren honest_paper (full)", "CSV")
fa1F = sum(1 for r in hfF if I(r, "v1_t1"))
check("full: v1 tier1 bat oan", 27.8, 100 * fa1F / len(hfF), "%",
      f"count(v1_t1==1)/{len(hfF)} tren honest_field (full)", "CSV")

print(f"\n--- ANCHOR: tinh day du ---")
ch_all = [r for rs in by.values() for r in rs if I(r, "changed") and not r["variant"].startswith("honest")]
ch_F = [r for rs in byF.values() for r in rs if I(r, "changed") and not r["variant"].startswith("honest")]
check("so nhat ky THAT SU bi sua (reduced)", 116, len(ch_all), "hang",
      "count(changed==1) tren moi variant khong phai honest", "CSV")
check("anchor bat duoc (reduced)", 116, sum(I(r, "anchor_flag") for r in ch_all),
      "/116", "sum(anchor_flag) tren tap changed==1", "CSV")
check("so nhat ky THAT SU bi sua (full)", 37, len(ch_F), "hang",
      "count(changed==1) tren moi variant khong phai honest (full)", "CSV")
check("anchor bat duoc (full)", 37, sum(I(r, "anchor_flag") for r in ch_F),
      "/37", "sum(anchor_flag) tren tap changed==1 (full)", "CSV")
check("anchor bat oan honest_field", 0, sum(I(r, "anchor_flag") for r in hf),
      "/60", "sum(anchor_flag) tren honest_field", "CSV")

print(f"\n--- F5 va F2 ---")
f5 = sum(I(r, "v2_f5") for r in by["fraud_infeasible_depth"])
check("V5 fire (reduced)", 648, f5, "lan", "sum(v2_f5) tren fraud_infeasible_depth", "CSV")
f5F = sum(I(r, "v2_f5") for r in byF["fraud_infeasible_depth"])
check("V5 fire (full)", 1350, f5F, "lan", "sum(v2_f5) tren fraud_infeasible_depth (full)", "CSV")
tot_f2 = sum(I(r, "v2_f2") for rs in by.values() for r in rs)
check("V2 fire tong", 0, tot_f2, "lan", "sum(v2_f2) tren toan bo reduced", "CSV")

# f2_reachability
F2r = load(F2)
mx = max(F(r, "max_clipped_depl") for r in F2r)
check("depletion clip cuc dai", 0.9987, mx, "", "max(max_clipped_depl) trong f2_reachability.csv", "CSV", tol=0.001)
ncfg = sum(I(r, "n_configs") for r in F2r)
check("so cau hinh quen (f2 scan)", 150, ncfg, "", "sum(n_configs) trong f2_reachability.csv", "CSV")
hits = sum(I(r, "f2_hits_dry_log") for r in F2r)
check("F2 kich hoat tren nhat ky kho", 0, hits, "lan", "sum(f2_hits_dry_log)", "CSV")

print(f"\n--- OMISSION FRAUD: 78.3% -> 40% ---")
om = by["fraud_omission"]
catch_v1 = len(om) - escape(om, "v1")
catch_v2 = len(om) - escape(om, "v2")
om_ch_rows = [r for r in om if I(r, "changed")]
c1_ch = len(om_ch_rows) - escape(om_ch_rows, "v1")
c2_ch = len(om_ch_rows) - escape(om_ch_rows, "v2")
check("point model bat omission fraud (changed=1)", 100.0,
      100 * c1_ch / len(om_ch_rows), "%",
      f"({len(om_ch_rows)} - escape_v1)/{len(om_ch_rows)} tren tap changed==1", "CSV")
check("robust rule bat omission fraud (changed=1)", 44.4,
      100 * c2_ch / len(om_ch_rows), "%",
      f"({len(om_ch_rows)} - escape_v2)/{len(om_ch_rows)} tren tap changed==1", "CSV")
om_ch = [r for r in om if I(r, "changed")]
c1c = len(om_ch) - escape(om_ch, "v1")
c2c = len(om_ch) - escape(om_ch, "v2")
print(f"    [tham khao] chi tinh changed==1 (n={len(om_ch)}): v1 bat {100*c1c/len(om_ch):.1f}%, "
      f"v2 bat {100*c2c/len(om_ch):.1f}%")

print(f"\n--- THOI PHONG TIN CHI: BA CACH TINH (day la cho SAI) ---")


def three_ways(variant, rows_by, hf_rows, lab):
    rs = rows_by.get(variant, [])
    if not rs:
        return None
    un_f = statistics.mean(F(r, "n_dry") for r in rs)
    un_b = statistics.mean(F(r, "n_dry") for r in hf_rows)
    hfmap = {key(r): r for r in hf_rows}
    pairs = [(F(r, "n_dry"), F(hfmap[key(r)], "n_dry")) for r in rs if key(r) in hfmap]
    paired = (100 * (statistics.mean(a for a, _ in pairs) - statistics.mean(b for _, b in pairs))
              / statistics.mean(b for _, b in pairs)) if pairs else float("nan")
    ch = [r for r in rs if I(r, "changed")]
    chp = [(F(r, "n_dry"), F(hfmap[key(r)], "n_dry")) for r in ch if key(r) in hfmap]
    if chp:
        a = statistics.mean(x[0] for x in chp)
        b = statistics.mean(x[1] for x in chp)
        d = [x[0] - x[1] for x in chp]
        sd = statistics.stdev(d) if len(d) > 1 else 0
        se = sd / len(d) ** 0.5 if d else 0
        condf = 100 * (a - b) / b
        t = statistics.mean(d) / se if se else 0
    else:
        a = b = condf = t = float("nan")
    print(f"  {lab} {variant:<24} n={len(rs):>3} (changed={len(ch):>2})")
    print(f"      UNPAIRED vs honest_field toan bo: {un_f:.2f} vs {un_b:.2f} = {100*(un_f-un_b)/un_b:+.0f}%")
    print(f"      PAIRED  (ghep station+year+seed+soil):                          = {paired:+.0f}%")
    print(f"      PAIRED + chi tan cong that (changed=1): {a:.2f} vs {b:.2f} = {condf:+.0f}%  (t={t:.2f})")
    return dict(variant=variant, n=len(rs), nch=len(ch), unpaired=100*(un_f-un_b)/un_b,
                paired=paired, cond=condf, t=t)


print(f"\n  [REDUCED, baseline honest_field toan bo = "
      f"{statistics.mean(F(r,'n_dry') for r in hf):.2f} pha]")
red = []
for v, claimed in (("fraud_timing", 69), ("fraud_rational", 63), ("fraud_cluster24", 52),
                   ("fraud_cluster96", 53), ("fraud_added_events", 49),
                   ("fraud_infeasible_depth", 25), ("fraud_omission", 43)):
    r = three_ways(v, by, hf, "reduced")
    if r:
        r["claimed"] = claimed
        red.append(r)

print(f"\n  [FULL, baseline honest_field toan bo = "
      f"{statistics.mean(F(r,'n_dry') for r in hfF):.2f} pha]")
full = []
for v, claimed in (("fraud_timing", 78), ("fraud_rational", 70), ("fraud_cluster24", 53),
                   ("fraud_cluster96", 53)):
    r = three_ways(v, byF, hfF, "full")
    if r:
        r["claimed"] = claimed
        full.append(r)

print(f"\n  => BAI DANG VIET COT UNPAIRED. Bang so sanh:")
print(f"     {'bien the':<24}{'bai viet':>10}{'unpaired':>10}{'paired':>9}{'paired+changed':>16}")
for r in red:
    print(f"     {r['variant']:<24}{r['claimed']:>9}%{r['unpaired']:>9.0f}%"
          f"{r['paired']:>8.0f}%{r['cond']:>15.0f}%")


print(f"\n--- THOI PHONG TIN CHI: so PAIRED ma bai bay gio viet ---")
def paired_infl(rows_by, hf_rows, variant):
    rs = rows_by.get(variant, [])
    hfmap = {key(r): r for r in hf_rows}
    pairs = [(F(r, "n_dry"), F(hfmap[key(r)], "n_dry"))
             for r in rs if I(r, "changed") and key(r) in hfmap]
    if not pairs:
        return None, None, 0
    a = statistics.mean(x[0] for x in pairs); b = statistics.mean(x[1] for x in pairs)
    d = [x[0] - x[1] for x in pairs]
    sd = statistics.stdev(d) if len(d) > 1 else 0
    se = sd / len(d) ** 0.5 if d else 0
    return (100 * (a - b) / b if b else float("nan"),
            statistics.mean(d) / se if se else 0, len(pairs))

for lab, rows_by, hf_rows, variant, claim, tclaim in (
        ("reduced fraud_timing", by, hf, "fraud_timing", 33, 5.29),
        ("full fraud_timing", byF, hfF, "fraud_timing", 38, 3.46),
        ("reduced fraud_rational", by, hf, "fraud_rational", 35, 4.39)):
    infl, tv, npair = paired_infl(rows_by, hf_rows, variant)
    if infl is None:
        print(f"    {lab}: khong du cap ghep"); continue
    check(f"{lab} inflation paired", claim, round(infl), "%",
          f"mean(n_dry) ghep cap tren changed==1 (n={npair})", "CSV", tol=0.06)
    check(f"{lab} t-stat", tclaim, round(tv, 2), "", f"t tren {npair} cap ghep", "CSV", tol=0.05)

print(f"\n--- ESCAPE RATE: bai viet 'all attack statistics are conditioned on changed' ---")
tm = by["fraud_timing"]
tm_ch = [r for r in tm if I(r, "changed")]
e_all = 100 * escape(tm, "v2") / len(tm)
e_ch = 100 * escape(tm_ch, "v2") / len(tm_ch)
check("escape v2 fraud_timing tren changed=1 (bai viet 8/9)", 88.9, e_ch, "%",
      f"escape(v2)/{len(tm_ch)} tren tap changed==1; escape={escape(tm_ch,'v2')}", "CSV")
print(f"    [tham khao] condition dung tren changed==1 (n={len(tm_ch)}): {e_ch:.1f}%")
tmF = byF["fraud_timing"]
tmF_ch = [r for r in tmF if I(r, "changed")]
e_allF = 100 * escape(tmF, "v2") / len(tmF)
e_chF = 100 * escape(tmF_ch, "v2") / len(tmF_ch)
check("escape v2 fraud_timing full tren changed=1 (3/3)", 100.0, e_chF, "%",
      f"escape(v2)/{len(tmF_ch)} tren tap changed==1 (full)", "CSV")
print(f"    [tham khao] condition dung tren changed==1 (n={len(tmF_ch)}): {e_chF:.1f}%")

print(f"\n--- PHAN BO THEO NAM: 'across two climate years' ---")
for lab, rows_ in (("reduced", R), ("full", Fu)):
    yr_all = defaultdict(int)
    yr_ch = defaultdict(int)
    for r in rows_:
        yr_all[r["year"]] += 1
        if I(r, "changed") and not r["variant"].startswith("honest"):
            yr_ch[r["year"]] += 1
    print(f"  [{lab}] tong hang theo nam : {dict(sorted(yr_all.items()))}")
    print(f"  [{lab}] TAN CONG THAT (changed=1) theo nam: {dict(sorted(yr_ch.items()))}")
    if yr_ch.get("2025", 0) == 0:
        print(f"     !! NAM 2025 CO 0 TAN CONG THAT. Moi ket luan ve TAN CONG chi")
        print(f"        dung cho nam 2024 (han). Bai viet 'across two climate years'")
        print(f"        ma khong noi dieu nay -> CAN SUA.")

print(f"\n--- GAP 75mm tren nhat ky trung thuc ---")
gaps = [abs(F(r, "gap_mm")) for r in hf if F(r, "gap_mm") == F(r, "gap_mm")]
print(f"  max |gap_mm| tren honest_field = {max(gaps):.1f} mm (bai viet 75)")
check("max gap tren nhat ky trung thuc (field)", 65, round(max(gaps)), "mm",
      "max(abs(gap_mm)) tren honest_field; gia tri 75 chi con trong comment cu", "CSV")

print()
print("=" * 108)
npass = sum(1 for r in results if r[0])
print(f"TONG: {npass}/{len(results)} claim PASS")
print("=" * 108)
fails = [r for r in results if not r[0]]
if fails:
    print("\nCLAIM FAIL — phai sua bai hoac sua cach tinh:")
    for _ok, name, cl, rc, unit, how, kind in fails:
        print(f"  * {name}")
        print(f"      bai viet {cl}{unit} | tai tinh {rc}{unit}")
        print(f"      cach tinh: {how}")
else:
    print("\nKhong co claim FAIL.")

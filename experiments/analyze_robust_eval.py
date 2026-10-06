#!/usr/bin/env python3
"""Phan tich outputs/robust_audit_eval.csv.

HAI BUG DA TRA GIA trong cac ban phan tich truoc, ghi o day de khong tai pham:

  BUG 1 — CSV tra ve CHUOI. `not r["v2_t0"]` voi gia tri "0" la `not "0"` = False,
          vi chuoi khac rong luon truthy. Ket qua: moi dong deu ra escape = 0%,
          va bang in ra "0% lọt" cho ca honest_field — vo ly. PHAI dung int().

  BUG 2 — so sanh baseline cheo. honest_paper sinh tu mot lan build_truth rieng
          nen moi phep so sanh (gap, anchor, changed) phai dung baseline CUA
          CHINH NO, khong phai cua ruong khac.

Moi con so trong bao cao deu doc tu CSV bang int()/float() tuong minh.
"""
from __future__ import annotations

import csv
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ORDER = ["honest_paper", "honest_field", "fraud_added_events", "fraud_infeasible_depth",
         "fraud_omission", "fraud_cluster24", "fraud_cluster96", "fraud_rational",
         "fraud_timing"]


def load(path):
    by = defaultdict(list)
    with open(path, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            by[r["variant"]].append(r)
    return by


def i(r, k):
    """Doc so nguyen tu CSV, thieu/roi thi 0."""
    v = r.get(k, "")
    return int(float(v)) if v not in ("", None) else 0


def fl(r, k):
    v = r.get(k, "")
    return float(v) if v not in ("", None) else float("nan")


def pct(a, b):
    return f"{a / b * 100:5.1f}%" if b else "  n/a"


def escape(rs, ver):
    """So nhat ky THOAT ca hai tang (tuc la bi bo sot)."""
    return sum(1 for r in rs
               if not i(r, f"{ver}_t0") and not i(r, f"{ver}_t1"))


def report(path, title):
    by = load(path)
    n_rows = sum(len(v) for v in by.values())
    print("=" * 96)
    print(f"{title}  ({n_rows} nhat ky)")
    print("=" * 96)
    print(f"  {'biến thể':<24}{'n':>4}{'n_dry':>7}{'lọt v1':>8}{'lọt v2':>8}"
          f"{'anchor/đã đổi':>15}{'bắt oan':>10}")
    for v in ORDER:
        rs = by.get(v, [])
        if not rs:
            continue
        n = len(rs)
        ch = [r for r in rs if i(r, "changed")]
        an = sum(i(r, "anchor_flag") for r in ch)
        if v.startswith("honest"):
            # nhat ky trung thuc: 'bat oan' = bi bat bo bat ky tang nao
            fa = sum(1 for r in rs if i(r, "v2_t0") or i(r, "v2_t1")
                     or i(r, "anchor_flag"))
            fa_s = f"{fa}/{n}"
            anc_s = f"{sum(i(r,'anchor_flag') for r in rs)}/{n}"
        else:
            fa_s = "-"
            anc_s = f"{an}/{len(ch)}"
        print(f"  {v:<24}{n:>4}{statistics.mean(fl(r,'n_dry') for r in rs):>7.2f}"
              f"{pct(escape(rs,'v1'), n):>8}{pct(escape(rs,'v2'), n):>8}"
              f"{anc_s:>15}{fa_s:>10}")

    print("\n  --- chi tiet bat oan tren nhat ky TRUNG THUC (loi hua cot loi) ---")
    for v in ["honest_paper", "honest_field"]:
        rs = by.get(v, [])
        if not rs:
            continue
        n = len(rs)
        print(f"  {v}: tang 0 v1 {pct(sum(i(r,'v1_t0') for r in rs), n)} | "
              f"tang 0 v2 {pct(sum(i(r,'v2_t0') for r in rs), n)} | "
              f"tang 1 v1 {pct(sum(i(r,'v1_t1') for r in rs), n)} | "
              f"tang 1 v2 {pct(sum(i(r,'v2_t1') for r in rs), n)} | "
              f"anchor {pct(sum(i(r,'anchor_flag') for r in rs), n)}")

    print("\n  --- tin chi: n_dry (so pha kho >=72h duoc tra tien) ---")
    base = by.get("honest_field", [])
    b = statistics.mean(fl(r, "n_dry") for r in base) if base else float("nan")
    print(f"  nông dân trung thực (ruộng thật): {b:.2f} pha/vụ  <-- moc so sanh")
    for v in ORDER:
        if v.startswith("honest") or v not in by:
            continue
        rs = by[v]
        nd = statistics.mean(fl(r, "n_dry") for r in rs)
        ch = [r for r in rs if i(r, "changed")]
        tag = "" if len(ch) == len(rs) else f"  (chỉ {len(ch)}/{len(rs)} tấn công thật sự đổi nhật ký)"
        print(f"  {v:<24}{nd:>6.2f}  ({(nd-b)/b*100:+6.1f}%){tag}")

    print("\n  --- F5 (ràng buộc sức thấm) fire ở đâu ---")
    for v in ORDER:
        rs = by.get(v, [])
        if not rs:
            continue
        f5 = sum(i(r, "v2_f5") for r in rs)
        if f5:
            print(f"  {v:<24} F5 fire {f5} lần")
    tot_f2 = sum(i(r, "v2_f2") for rs in by.values() for r in rs)
    tot_f5 = sum(i(r, "v2_f5") for rs in by.values() for r in rs)
    print(f"  TỔNG F2 fire = {tot_f2} (đã đo: depletion max 0.998 < 1.00 nên ruộng lúa"
          f" mùa khô không bao giờ xuống dưới điểm héo)")
    print(f"  TỔNG F5 fire = {tot_f5}")
    return by


def main():
    paths = sys.argv[1:] or [str(ROOT / "outputs" / "robust_audit_eval.csv")]
    for k, p in enumerate(paths):
        lab = Path(p).stem
        report(p, f"BÁO CÁO {k+1}: {lab}")
        print()


if __name__ == "__main__":
    main()

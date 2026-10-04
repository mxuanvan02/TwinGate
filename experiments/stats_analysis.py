#!/usr/bin/env python3
"""Paired Wilcoxon signed-rank + effect size trên outputs/main_raw.csv.

Thiết kế: trong mỗi cell (fidelity, station, network, budget), các policy chạy CÙNG
seed => paired theo seed. So sánh TwinGate+T2 (policy chính) với từng baseline trên
metric unsafe% = hours_unsafe/hours*100 (thấp hơn = tốt hơn).

HAI LỖI ĐÃ SỬA (2026-10-04) — cả hai đều làm THẤP hơn số so sánh thật:
  (1) Danh sách ngân sách bị HARDCODE ["80.0","140.0","200.0","260.0","inf"] theo
      thang cũ. Thang mới là 80/160/240/320/400/inf, nên chỉ b=80 và b=inf khớp =>
      48 so sánh thay vì hàng trăm. Sửa: TỰ KHÁM PHÁ mọi giá trị có trong CSV.
  (2) Key cell không có cột `fidelity` (mới thêm), nên 3 dải độ trung thực bị GỘP
      CHUNG một cell -> gán ghi đè nhau và báo cáo sai. Sửa: đưa fidelity vào key.
  Ngoài ra: baseline cũ thiếu TwinGate+T2+centre (đối chứng của luật chọn lệnh thích
  ứng) nên không kiểm định được đóng góp của luật đó. Đã thêm.

Thống kê:
- Wilcoxon signed-rank, two-sided (scipy.stats.wilcoxon, zero_method='wilcox',
  alternative='two-sided'). Số seed/cell = 10 => mẫu nhỏ, báo cáo chính xác p.
- Effect size: rank-biserial r = Z/sqrt(N_paired) (công thức chuẩn cho Wilcoxon
  matched-pairs), |r| >= 0.5 large, >= 0.3 medium, >= 0.1 small.
- Median difference (TwinGate+T2 - baseline), âm = TwinGate tốt hơn.
- Holm-Bonferroni correction trên họ so sánh trong mỗi cell.

Lưu ý trung thực:
- Với 10 seed, Wilcoxon KHÔNG THỂ đạt p < 0.002 (2^-10) — nếu p nhỏ nhất có thể
  là 0.002, báo cáo p<=0.004 thay vì "p<0.001".
- Nếu diff mọi seed = 0 (tie toàn bộ), wilcoxon raise ValueError => báo "n/a".
- Ô có median_diff = 0 và p = n/a nghĩa là hai policy CHO KẾT QUẢ GIỐNG HỆT NHAU
  ở ô đó. Đây là thông tin quan trọng (ví dụ luật thích ứng vô hiệu khi vùng pass
  hẹp hơn bước nhảy ứng viên) chứ không phải lỗi; phải được báo cáo, không được lọc bỏ.
"""
import csv
import math
import os
import sys
from collections import defaultdict

import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RAW = os.path.join(ROOT, "outputs", "main_raw.csv")
OUT = os.path.join(ROOT, "outputs", "wilcoxon_results.csv")
if len(sys.argv) > 1:
    RAW = sys.argv[1]
    stem = os.path.splitext(os.path.basename(RAW))[0]
    OUT = os.path.join(ROOT, "outputs", f"wilcoxon_{stem.replace('main_raw', 'results')}.csv")

PRIMARY = "TwinGate+T2"
# TwinGate+T2+centre là ĐỐI CHỨNG của luật chọn lệnh thích ứng (cùng cổng, cùng T2,
# chỉ khác luật chọn đích đến). Nó phải nằm trong danh sách để kiểm định được đóng
# góp của luật đó — nếu thiếu thì bài không có bằng chứng thống kê cho thành phần này.
BASELINES = ["TwinGate+T2+centre", "TwinGate+blindARQ", "Reactive+T2",
             "Reactive+blindARQ", "FixedSchedule"]
METRIC = "unsafe_pct"


def load():
    rows = []
    with open(RAW, newline="") as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows


def holm(pvals):
    """Holm-Bonferroni; trả về adjusted p cùng thứ tự input."""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    adj = [0.0] * m
    prev = 0.0
    for k, i in enumerate(order):
        a = min(1.0, (m - k) * pvals[i])
        prev = max(prev, a)
        adj[i] = prev
    return adj


def rank_biserial(z, n):
    return float(z) / math.sqrt(n) if n > 0 else float("nan")


def budget_sort_key(b):
    return (b == "inf", float(b) if b != "inf" else 0.0)


def main():
    rows = load()
    has_fid = "fidelity" in rows[0]
    # index: (fidelity, station, network, budget, policy) -> {seed: unsafe_pct}
    cell = defaultdict(dict)
    for r in rows:
        fid = r.get("fidelity", "all")
        key = (fid, r["station"], r["network"], r["budget_mm"], r["policy"])
        seed = int(r["seed"])
        unsafe = float(r["hours_unsafe"]) / float(r["hours"]) * 100.0
        cell[key][seed] = unsafe

    # TỰ KHÁM PHÁ các trục thay vì hardcode
    fids = sorted({k[0] for k in cell})
    stations = sorted({k[1] for k in cell})
    networks = sorted({k[2] for k in cell})
    budgets = sorted({k[3] for k in cell}, key=budget_sort_key)
    policies = {k[4] for k in cell}
    bases = [b for b in BASELINES if b in policies]
    missing = [b for b in BASELINES if b not in policies]
    if missing:
        print(f"  !! CANH BAO: CSV khong co baseline {missing}")

    print(f"nguon {os.path.basename(RAW)}: {len(rows)} rows")
    print(f"  fidelity={fids}\n  stations={stations}\n  networks={networks}")
    print(f"  budgets={[('inf' if b=='inf' else float(b)) for b in budgets]}")
    print(f"  so sanh {PRIMARY} vs {bases}")

    out_rows = []
    n_cells = 0
    for fid in fids:
        for station in stations:
            for network in networks:
                for budget in budgets:
                    prim = cell.get((fid, station, network, budget, PRIMARY))
                    if not prim:
                        continue
                    seeds = sorted(prim.keys())
                    recs = []
                    for base in bases:
                        bmap = cell.get((fid, station, network, budget, base))
                        if not bmap:
                            continue
                        common = [s for s in seeds if s in bmap]
                        a = np.array([prim[s] for s in common])
                        b = np.array([bmap[s] for s in common])
                        diff = a - b  # âm = TwinGate tốt hơn
                        med = float(np.median(diff))
                        if np.all(diff == 0):
                            recs.append((base, common, med, float("nan"),
                                         float("nan"), "all-tie"))
                            continue
                        try:
                            res = stats.wilcoxon(diff, alternative="two-sided",
                                                 zero_method="wilcox")
                            p = float(res.pvalue)
                            w = float(res.statistic)
                            n_paired = int(np.sum(diff != 0))
                            n = n_paired
                            mu = n * (n + 1) / 4.0
                            sd = math.sqrt(n * (n + 1) * (2 * n + 1) / 24.0)
                            zval = (w - mu) / sd if sd > 0 else float("nan")
                            rb = rank_biserial(zval, n)
                            recs.append((base, common, med, p, rb, ""))
                        except ValueError as e:
                            recs.append((base, common, med, float("nan"),
                                         float("nan"), str(e)))
                    # Holm trong cell
                    pidx = [i for i, r_ in enumerate(recs) if not math.isnan(r_[3])]
                    if pidx:
                        adj = holm([recs[i][3] for i in pidx])
                        for j, i in enumerate(pidx):
                            base, common, med, p, rb, note = recs[i]
                            recs[i] = (base, common, med, p, rb, note, adj[j])
                    for rec in recs:
                        if len(rec) == 6:
                            base, common, med, p, rb, note = rec
                            padj = float("nan")
                        else:
                            base, common, med, p, rb, note, padj = rec
                        out_rows.append({
                            "fidelity": fid,
                            "station": station, "network": network, "budget": budget,
                            "comparison": f"{PRIMARY} vs {base}", "n_paired": len(common),
                            "median_diff_unsafe_pp": round(med, 4),
                            "wilcoxon_p": f"{p:.5f}" if not math.isnan(p) else "n/a",
                            "p_holm": f"{padj:.5f}" if not math.isnan(padj) else "n/a",
                            "rank_biserial_r": f"{rb:.4f}" if not math.isnan(rb) else "n/a",
                            "note": note,
                        })
                    n_cells += 1

    fields = ["fidelity", "station", "network", "budget", "comparison", "n_paired",
              "median_diff_unsafe_pp", "wilcoxon_p", "p_holm", "rank_biserial_r", "note"]
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(out_rows)

    print(f"\ncells={n_cells}, rows={len(out_rows)} -> {OUT}\n")

    # ---- bang tom tat theo (fidelity, baseline, budget): gop tram/kenh ----
    print(f"{'fid':<8}{'budget':>8}  {'baseline':<24}{'n ô':>5}{'medΔ':>9}"
          f"{'p_holm nhỏ nhất':>16}{'|r| TB':>8}  {'ô có ý nghĩa':>13}")
    print("-" * 100)
    agg = defaultdict(list)
    for r_ in out_rows:
        base = r_["comparison"].replace(f"{PRIMARY} vs ", "")
        agg[(r_["fidelity"], r_["budget"], base)].append(r_)
    for (fid, bud, base), rs in sorted(agg.items(),
                                       key=lambda kv: (kv[0][0], budget_sort_key(kv[0][1]), kv[0][2])):
        meds = [x["median_diff_unsafe_pp"] for x in rs]
        phs = [float(x["p_holm"]) for x in rs if x["p_holm"] != "n/a"]
        rbs = [abs(float(x["rank_biserial_r"])) for x in rs if x["rank_biserial_r"] != "n/a"]
        sig = sum(1 for p in phs if p < 0.05)
        med = float(np.median(meds))
        pmin = f"{min(phs):.5f}" if phs else "n/a"
        rbm = f"{np.mean(rbs):.3f}" if rbs else "n/a"
        print(f"{fid:<8}{('inf' if bud=='inf' else bud):>8}  {base:<24}{len(rs):>5}"
              f"{med:>+9.2f}{pmin:>16}{rbm:>8}  {sig:>7}/{len(rs):<5}")

    # ---- GATE: o nao TwinGate THUA co y nghia? ----
    worse_sig = [r_ for r_ in out_rows
                 if r_["p_holm"] != "n/a" and float(r_["p_holm"]) < 0.05
                 and r_["median_diff_unsafe_pp"] > 0]
    print(f"\n=== GATE: có ô nào TwinGate+T2 THUA có ý nghĩa thống kê không? ===")
    if worse_sig:
        print(f"  !! CO {len(worse_sig)} o:")
        for r_ in worse_sig[:20]:
            print(f"     {r_['fidelity']}/{r_['station']}/{r_['network']}/b={r_['budget']} "
                  f"{r_['comparison']} medΔ={r_['median_diff_unsafe_pp']:+.2f} "
                  f"p_holm={r_['p_holm']}")
    else:
        print("  khong co o nao -> TwinGate+T2 khong thua co y nghia o bat ky o nao")

    # ---- GATE: luat thich ung co dong gop co y nghia o dai nao? ----
    print(f"\n=== GATE: luật chọn lệnh thích ứng (vs centre-seeking) ===")
    ct = [r_ for r_ in out_rows if r_["comparison"].endswith("TwinGate+T2+centre")]
    by_fid = defaultdict(list)
    for r_ in ct:
        by_fid[r_["fidelity"]].append(r_)
    for fid in sorted(by_fid):
        rs = by_fid[fid]
        sig = sum(1 for x in rs if x["p_holm"] != "n/a" and float(x["p_holm"]) < 0.05)
        tie = sum(1 for x in rs if x["note"] == "all-tie")
        print(f"  {fid:<8} {len(rs):>4} ô: {sig} có ý nghĩa, {tie} giống hệt nhau (all-tie)")
        if sig == 0 and tie == len(rs):
            print(f"           -> luật thích ứng VÔ HIỆU hoàn toàn ở dải này "
                  f"(đúng dự đoán của mệnh đề d_max: vùng pass hẹp hơn bước nhảy ứng viên)")
        elif sig == 0:
            print(f"           -> không có đóng góp có ý nghĩa ở dải này")

    # ---- tong ----
    tot = len(out_rows)
    sig05 = sum(1 for r_ in out_rows if r_["p_holm"] != "n/a" and float(r_["p_holm"]) < 0.05)
    fav = sum(1 for r_ in out_rows if r_["median_diff_unsafe_pp"] < 0)
    tie = sum(1 for r_ in out_rows if r_["note"] == "all-tie")
    worse = sum(1 for r_ in out_rows if r_["median_diff_unsafe_pp"] > 0)
    print(f"\nTỔNG: {tot} so sánh | {sig05} significant (Holm p<0.05) | "
          f"{fav} median<0 (tốt hơn) | {tie} all-tie (giống hệt) | {worse} median>0 (kém hơn)")
    # khong tra ve 1 khi co o thua: day la thong tin de bao cao, gate o tren da canh bao
    return 0


if __name__ == "__main__":
    sys.exit(main())

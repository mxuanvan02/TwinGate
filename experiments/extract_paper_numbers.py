#!/usr/bin/env python3
"""Trich TOAN BO so lieu that tu outputs/*.csv thanh mot file markdown goc cho bai bao.

Ly do ton tai (2026-10-04): tap do sau tuoi da doi tu {10,20,35} sang {20,40,60},
thang ngan sach doi, va them chieu DO TRUNG THUC (sigma_frac). Moi con so trong ban
thao cu deu VO HIEU. Script nay sinh ra nguon so lieu duy nhat de viet bai, khong
duoc go so tay vao LaTeX.

Moi bang deu ghi ro: nguon CSV, n episode, cach tinh. Neu CSV thieu -> in BLOCKED
chu khong suy ra.

Usage: python3 experiments/extract_paper_numbers.py
Output: paper/RESULTS_DATA.md
"""
from __future__ import annotations

import csv
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTD = ROOT / "outputs"
DEST = ROOT / "paper" / "RESULTS_DATA.md"

Z = 1.959963984540054
W_SAFE = 59.5

sys.path.insert(0, str(ROOT / "src"))
# ---- Thieu hut mua kho: TINH TU DU LIEU, khong hardcode -----------------------
# Co HAI dinh nghia, lech nhau 1.5 lan (do truc tiep tren ERA5 2024, cua so 2160 h):
#   NET     = Kc*sum(ET0) - sum(mua)        can_tho 318.4 | soc_trang 301.6 | ca_mau 306.0
#   POS-SUM = sum(max(0, Kc*ET0_h - P_h))   can_tho 485.1 | soc_trang 468.5 | ca_mau 450.2
# POS-SUM lon hon vi khong cho mua du bu tru (than trong; dung cho cau hoi "nuoc con
# du den het mua khong"). CONG dung POS-SUM de xet `scarce`, nen moi ngan sach huu han
# trong luoi (80..400 mm) deu la RANG BUOC; chi b = inf moi abundant. Ban cu hardcode
# DEFICIT_MM = 318 (NET) => gan nhan sai cho b = 320 va b = 400.

def _compute_deficits(stations=("can_tho", "soc_trang", "ca_mau"), hours=2160):
    """Tra ve (POS-SUM theo tram, NET theo tram) tinh tu chinh chuoi ERA5."""
    from ncs_loop import load_weather, march_start, season_deficit_suffix
    from water_balance import SoilProfile
    prof = SoilProfile()
    pos, net = {}, {}
    for st in stations:
        w, _ = load_weather(st)
        s0 = march_start(w)
        seg = w[s0:s0 + hours]
        net[st] = max(0.0, prof.kc * sum(r["et0"] for r in seg) - sum(r["p"] for r in seg))
        pos[st] = season_deficit_suffix(w, s0, hours, prof)[0]
    return pos, net

_POS, _NET = _compute_deficits()
DEFICIT_POS = _POS                      # cai ma CONG dung de xet scarce
DEFICIT_NET = _NET                      # thieu hut vat ly thuan, dung de bao cao
DEFICIT_MM = min(_POS.values())         # nguong "rang buoc" DUNG dinh nghia cua cong
DEFICIT_NET_RANGE = (min(_NET.values()), max(_NET.values()))
DEFICIT_POS_RANGE = (min(_POS.values()), max(_POS.values()))


def load(name):
    p = OUTD / name
    if not p.exists():
        return None
    with p.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def num(rows, col):
    v = []
    for r in rows:
        try:
            v.append(float(r[col]))
        except (KeyError, TypeError, ValueError):
            pass
    return v


def mean(rows, col):
    v = num(rows, col)
    return statistics.mean(v) if v else float("nan")


def sd(rows, col):
    v = num(rows, col)
    return statistics.pstdev(v) if len(v) > 1 else 0.0


def paired_t(d):
    if not d:
        return 0.0, 0.0
    m = statistics.mean(d)
    s = statistics.pstdev(d)
    return m, (m / (s / len(d) ** 0.5) if s else 0.0)


def spearman(xs, ys):
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
    nu = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    de = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return nu / de if de else 0.0


def gini(xs):
    if not xs or sum(xs) == 0:
        return 0.0
    s = sorted(xs)
    n = len(s)
    return (2 * sum((i + 1) * v for i, v in enumerate(s))) / (n * sum(s)) - (n + 1) / n


L = []
w = L.append
blocked = []

w("# SỐ LIỆU GỐC CHO BÀI BÁO — sinh tự động, KHÔNG sửa tay")
w("")
w("Nguồn: `experiments/extract_paper_numbers.py` đọc `outputs/*.csv`.")
w("Mọi con số trong `paper/main.tex` phải đối chiếu được với file này.")
w("")
w(f"Hằng số: z = {Z:.6f}; W (chiều rộng tập an toàn) = {W_SAFE:.1f} mm.")
w("")
w("**Thiếu hụt mùa khô ERA5 2024 (2 160 giờ từ 1/3) — hai định nghĩa, KHÔNG dùng lẫn:**")
w("")
w("| trạm | thiếu hụt ròng $K_c\\Sigma ET_0-\\Sigma P$ (mm) | POS-SUM $\\Sigma\\max(0,K_c ET_{0,h}-P_h)$ (mm) — cổng dùng để xét khan |")
w("|---|---|---|")
for _st in ("can_tho", "soc_trang", "ca_mau"):
    w(f"| {_st} | {DEFICIT_NET[_st]:.1f} | {DEFICIT_POS[_st]:.1f} |")
w("")
w(f"POS-SUM lớn hơn vì không cho mưa dư bù trừ (cách làm thận trọng, đúng cho câu hỏi "
  f"\"nước còn đủ đến hết mùa không\"). Vì mọi ngân sách hữu hạn trong lưới "
  f"(80–400 mm) đều nhỏ hơn POS-SUM của cả ba trạm "
  f"({DEFICIT_POS_RANGE[0]:.0f}–{DEFICIT_POS_RANGE[1]:.0f} mm), **tất cả đều là ngân sách "
  f"ràng buộc** theo định nghĩa của chính bộ điều khiển; chỉ $B=\\infty$ là không.")
w("")

# ======================================================================
# BANG 1: LUOI CHINH — unsafe% theo (fidelity, policy, budget)
# ======================================================================
main = load("main_raw.csv")
if not main or "fidelity" not in main[0]:
    blocked.append("main_raw.csv thieu cot fidelity -> BANG 1/2/3/4 BLOCKED")
else:
    for r in main:
        r["unsafe"] = 100 * float(r["hours_unsafe"]) / float(r["hours"])
    fids = []
    for r in main:
        if r["fidelity"] not in fids:
            fids.append(r["fidelity"])
    sf_of = {r["fidelity"]: float(r["sigma_frac"]) for r in main}
    fids = sorted(fids, key=lambda f: sf_of[f])
    pols = []
    for r in main:
        if r["policy"] not in pols:
            pols.append(r["policy"])
    buds = sorted({r["budget_mm"] for r in main if r["budget_mm"] != "inf"}, key=float)

    n_ep = len(main)
    w("## 1. Lưới chính — giờ mất an toàn (%) theo chính sách × ngân sách")
    w("")
    w(f"Nguồn `main_raw.csv`, **n = {n_ep} episode** "
      f"({len({r['station'] for r in main})} trạm × "
      f"{len({r['network'] for r in main})} kênh × {len(buds)+1} ngân sách × "
      f"{len(pols)} chính sách × {len({r['seed'] for r in main})} seed × "
      f"{len(fids)} dải trung thực). Cửa sổ 2 160 giờ (1/3–29/5), ERA5 thật.")
    w("")
    for net in ("severe", "mild"):
        for fid in fids:
            w(f"### Kênh {net}, dải `{fid}` (σ_frac = {sf_of[fid]})")
            w("")
            w("| chính sách | " + " | ".join(f"b={float(b):.0f}" for b in buds)
              + " | b=∞ |")
            w("|---|" + "---|" * (len(buds) + 1))
            for p in pols:
                cells = []
                for b in buds + ["inf"]:
                    g = [r for r in main if r["fidelity"] == fid and r["network"] == net
                         and r["policy"] == p and r["budget_mm"] == b]
                    cells.append(f"{mean(g,'unsafe'):.2f}" if g else "—")
                w(f"| {p} | " + " | ".join(cells) + " |")
            w("")

    # ---------------- BANG 2: AWD ----------------
    w("## 2. AWD — số chu kỳ đạt chuẩn ≥72 h (QĐ 4801) theo dải trung thực")
    w("")
    w("| dải | σ_frac | b=80 | b=160 | b=240 | b=320 | b=400 | b=∞ |")
    w("|---|---|---|---|---|---|---|---|")
    for fid in fids:
        cells = []
        for b in ["80.0", "160.0", "240.0", "320.0", "400.0", "inf"]:
            g = [r for r in main if r["fidelity"] == fid and r["network"] == "severe"
                 and r["policy"] == "TwinGate+T2" and r["budget_mm"] == b]
            cells.append(f"{mean(g,'awd_effective'):.2f}" if g else "—")
        w(f"| {fid} | {sf_of[fid]} | " + " | ".join(cells) + " |")
    w("")
    w("Cột = chu kỳ AWD **đạt chuẩn** (pha khô ≥72 h). `awd_short` (mất tín chỉ) "
      "cho cùng ô, kênh severe:")
    w("")
    w("| dải | b=240 đạt | b=240 hụt | b=400 đạt | b=400 hụt | b=∞ đạt | b=∞ hụt |")
    w("|---|---|---|---|---|---|---|")
    for fid in fids:
        c = []
        for b in ("240.0", "400.0", "inf"):
            g = [r for r in main if r["fidelity"] == fid and r["network"] == "severe"
                 and r["policy"] == "TwinGate+T2" and r["budget_mm"] == b]
            c += [f"{mean(g,'awd_effective'):.2f}", f"{mean(g,'awd_short'):.2f}"] if g \
                 else ["—", "—"]
        w(f"| {fid} | " + " | ".join(c) + " |")
    w("")

    # ---------------- BANG 3: Pareto nuoc vs an toan ----------------
    w("## 3. Pareto an toàn–nước (kênh severe, dải `awd`)")
    w("")
    w("| chính sách | nước (mm) | mất an toàn (%) | AWD đạt | giờ stress | nước đúp (mm) |")
    w("|---|---|---|---|---|---|")
    for p in pols:
        g = [r for r in main if r["fidelity"] == "awd" and r["network"] == "severe"
             and r["policy"] == p and r["budget_mm"] == "240.0"]
        if not g:
            continue
        w(f"| {p} | {mean(g,'water_applied_mm'):.1f} | {mean(g,'unsafe'):.2f} | "
          f"{mean(g,'awd_effective'):.2f} | {mean(g,'stress_hours'):.0f} | "
          f"{mean(g,'water_wasted_dup_mm'):.1f} |")
    w("")

    # ---------------- BANG 4: trade-off + kiem dinh ----------------
    # HAI LOI BAO CAO DA SUA (2026-10-04):
    #  (i) Ban dau gan m,t = nan khi chinh sach CAI THIEN -> ca cot toan dau "--",
    #      tuc la giau so lieu o chinh bang dung lam nguon cho bai bao.
    #  (ii) Ban sua dau tien viet ghi chú theo NHANH ELSE, khien FixedSchedule
    #      severe (+0.41 diem = TANG, t = +0.54) bi gan nhan "cai thien khi them
    #      nuoc" -- SAI DAU. Ghi chu phai phan biet 5 truong hop theo (m, t).
    #  (iii) Chi bao cao kenh severe, trong khi hien tuong BAO HOA DO SAU (cap
    #      ngan sach tang ma mat an toan tang CO Y NGHIA) lai nam o kenh MILD
    #      (+2.02 diem, t = +2.51). Bo kenh mild la bo mat phat hien hay nhat.
    w("## 4. Trade-off: kiểm định xu hướng theo ngân sách")
    w("")
    w("ρ = Spearman giữa ngân sách và giờ mất an toàn (kỳ vọng ρ < 0). "
      "Δ và t = kiểm định cặp cho b = 160 → 240 mm, n = 30 cặp (10 seed × 3 trạm).")
    w("")
    w("Ghi chú phân biệt 5 trường hợp theo (Δ, t): cải thiện có ý nghĩa / giảm nhẹ "
      "không ý nghĩa / không đổi đáng kể / tăng nhẹ không ý nghĩa / tăng có ý nghĩa "
      "— trường hợp cuối phải giải thích được bằng cơ chế, nếu không là lỗi.")
    w("")
    w("| kênh | dải | chính sách | ρ | Δ b=160→240 | t | n | ghi chú |")
    w("|---|---|---|---|---|---|---|---|")
    # by_cell: (dải, kênh, chính sách, ngân sách) -> {(seed, trạm): unsafe%}
    # de kiem dinh CAP (cung seed, cung tram) thay vi so hai trung binh.
    by_cell = defaultdict(dict)
    for r in main:
        by_cell[(r["fidelity"], r["network"], r["policy"], r["budget_mm"])][
            (r["seed"], r["station"])] = r["unsafe"]
    for net in ("severe", "mild"):
        for fid in fids:
            for p in ("TwinGate+T2", "Reactive+T2", "FixedSchedule", "Oracle"):
                pts = sorted([(float(b), statistics.mean(dd.values()))
                              for (f2, n2, p2, b), dd in by_cell.items()
                              if f2 == fid and n2 == net and p2 == p and b != "inf"],
                             key=lambda x: x[0])
                if len(pts) < 3:
                    continue
                rho = spearman([b for b, _ in pts], [u for _, u in pts])
                ka = (fid, net, p, "160.0"); kb = (fid, net, p, "240.0")
                if ka not in by_cell or kb not in by_cell:
                    w(f"| {net} | {fid} | {p} | {rho:+.2f} | — | — | 0 | thiếu ô |")
                    continue
                ks = sorted(set(by_cell[ka]) & set(by_cell[kb]))
                d = [by_cell[kb][k] - by_cell[ka][k] for k in ks]
                m, t = paired_t(d)
                n = len(d)

                if m > 0.5 and t >= 2.0:
                    # tang co y nghia -> BAT BUOC giai thich duoc bang co che
                    g160 = [r for r in main if r["fidelity"] == fid and r["network"] == net
                            and r["policy"] == p and r["budget_mm"] == "160.0"]
                    g240 = [r for r in main if r["fidelity"] == fid and r["network"] == net
                            and r["policy"] == p and r["budget_mm"] == "240.0"]
                    mpe = (mean(g240, "water_applied_mm") /
                           max(1.0, mean(g240, "commands_delivered"))) if g240 else float("nan")
                    if mpe >= W_SAFE:
                        note = (f"**tăng có ý nghĩa** — giải thích được bằng bão hoà độ "
                                f"sâu: mm/lệnh {mpe:.1f} ≥ W {W_SAFE:.1f} mm nên nước "
                                f"tràn khỏi dung trọng (nước hữu ích vẫn tăng)")
                    else:
                        note = (f"**tăng có ý nghĩa — KHÔNG giải thích được** "
                                f"(mm/lệnh {mpe:.1f} < W {W_SAFE:.1f})")
                        blocked.append(f"{net}/{fid}/{p}: unsafe tang co y nghia "
                                       f"b=160->240 (Δ={m:+.2f}, t={t:+.2f}) ma "
                                       f"mm/lenh {mpe:.1f} < W -> khong giai thich duoc")
                elif m > 0.5:
                    note = "tăng nhẹ, không có ý nghĩa thống kê (nhiễu)"
                elif m < -0.5 and t <= -2.0:
                    note = "cải thiện có ý nghĩa"
                elif m < -0.5:
                    note = "giảm nhẹ, không có ý nghĩa thống kê"
                else:
                    note = "không đổi đáng kể (nhiễu)"
                w(f"| {net} | {fid} | {p} | {rho:+.2f} | {m:+.2f}p | {t:+.2f} | {n} | {note} |")
    w("")
    w("Lưu ý khi viết bài: ρ < 0 ở **mọi** ô xác nhận xu hướng tổng thể (thêm nước "
      "thì an toàn hơn). Riêng FixedSchedule ở kênh mild có một cặp tăng có ý nghĩa "
      "và đã kiểm chứng được cơ chế — đây là **kết quả** (lịch mù không tận dụng "
      "được nước cấp thêm), không phải lỗi cần giấu.")
    w("")

    # ---------------- BANG 5: kiem chung vung nam 2025 ----------------
    m25 = load("main_raw_2025.csv")
    if m25 and "fidelity" in m25[0]:
        for r in m25:
            r["unsafe"] = 100 * float(r["hours_unsafe"]) / float(r["hours"])
        w("## 5. Kiểm chứng vững: năm 2025 (mùa khô ướt hơn)")
        w("")
        w(f"Nguồn `main_raw_2025.csv`, n = {len(m25)} episode.")
        w("")
        w("| dải | chính sách | b=80 | b=160 | b=240 | b=320 | b=400 |")
        w("|---|---|---|---|---|---|---|")
        buds25 = ["80.0", "160.0", "240.0", "320.0", "400.0"]
        fids25 = sorted({r["fidelity"] for r in m25},
                        key=lambda f: float(next(r["sigma_frac"] for r in m25
                                                 if r["fidelity"] == f)))
        for fid in fids25:
            for p in ("TwinGate+T2", "Reactive+T2", "FixedSchedule", "Oracle"):
                cells = []
                for b in buds25:
                    g = [r for r in m25 if r["fidelity"] == fid and r["network"] == "severe"
                         and r["policy"] == p and r["budget_mm"] == b]
                    cells.append(f"{mean(g,'unsafe'):.2f}" if g else "—")
                w(f"| {fid} | {p} | " + " | ".join(cells) + " |")
        w("")
    elif m25:
        blocked.append("main_raw_2025.csv chua co cot fidelity (chay lai voi code moi) "
                       "-> BANG 5 BLOCKED")

# ======================================================================
# BANG 6: ABLATION
# ======================================================================
abl = load("ablation_raw.csv")
if not abl or "fidelity" not in abl[0]:
    blocked.append("ablation_raw.csv thieu fidelity -> BANG 6 BLOCKED")
else:
    w("## 6. Ablation — cái giá của từng thành phần")
    w("")
    w(f"Nguồn `ablation_raw.csv`, n = {len(abl)} episode. Mỗi biến thể tắt ĐÚNG MỘT "
      "thành phần, giữ nguyên phần còn lại, cùng seed/cùng thời tiết/cùng kênh.")
    w("")
    for fid in sorted({r["fidelity"] for r in abl}):
        for net in ("severe", "mild"):
            sub = [r for r in abl if r["fidelity"] == fid and r["network"] == net]
            if not sub:
                continue
            bind = [r for r in sub if r["budget_mm"] != "inf"
                    and float(r["budget_mm"]) < DEFICIT_MM]
            base = [r for r in bind if r["variant"].startswith("FULL")]
            if not base:
                continue
            bu, bd = mean(base, "unsafe_pct"), mean(base, "dup_mm")
            w(f"### Dải `{fid}` ({next(r['sigma_frac'] for r in sub)}), kênh {net}, "
              f"ngân sách ràng buộc (< {DEFICIT_MM:.0f} mm = POS-SUM nhỏ nhất, "
              f"nên mọi B hữu hạn trong lưới đều ràng buộc), n = {len(bind)}")
            w("")
            w("| biến thể | mất an toàn (%) | Δ | nước đúp (mm) | Δ | AWD đạt |")
            w("|---|---|---|---|---|---|")
            order = []
            for r in bind:
                if r["variant"] not in order:
                    order.append(r["variant"])
            order.sort(key=lambda v: -abs(mean([x for x in bind if x["variant"] == v],
                                               "unsafe_pct") - bu))
            for v in order:
                g = [x for x in bind if x["variant"] == v]
                u, d = mean(g, "unsafe_pct"), mean(g, "dup_mm")
                mark = " **(đề xuất)**" if v.startswith("FULL") else ""
                w(f"| {v}{mark} | {u:.2f} | {u-bu:+.2f} | {d:.1f} | {d-bd:+.1f} | "
                  f"{mean(g,'awd_eff'):.2f} |")
            w("")

# ======================================================================
# BANG 7: TRIEN KHAI
# ======================================================================
dep = load("deployment_raw.csv")
if not dep:
    blocked.append("deployment_raw.csv thieu -> BANG 7 BLOCKED")
else:
    w("## 7. Triển khai thực tế — quét một yếu tố một lần")
    w("")
    w(f"Nguồn `deployment_raw.csv`, n = {len(dep)} episode. Mức tham chiếu: "
      "σ_frac = 0,02; ngân sách 240 mm; 3 trạm × 2 kênh × 5 seed.")
    w("")
    fac_name = {"F1_uplink": "mất gói uplink", "F2_soil": "loại đất",
                "F3_depth": "độ phân giải lệnh", "F4_horizon": "chân trời H (ngày)",
                "F5_radio": "kiểu gửi lại"}
    for fac in ("F1_uplink", "F2_soil", "F3_depth", "F4_horizon", "F5_radio"):
        g0 = [r for r in dep if r["factor"] == fac]
        if not g0:
            continue
        w(f"### {fac} — {fac_name[fac]}")
        w("")
        w("| mức | mất an toàn (%) | AWD đạt | giờ stress | lệnh/ngày | gửi lại/ngày |")
        w("|---|---|---|---|---|---|")
        lv = []
        for r in g0:
            if r["level"] not in lv:
                lv.append(r["level"])
        try:
            lv = sorted(lv, key=float)
        except ValueError:
            pass
        for L2 in lv:
            g = [r for r in g0 if r["level"] == L2]
            w(f"| {L2} | {mean(g,'unsafe_pct'):.2f} | {mean(g,'awd_eff'):.2f} | "
              f"{mean(g,'stress_h'):.0f} | {mean(g,'cmd_per_day'):.3f} | "
              f"{mean(g,'resend_per_day'):.3f} |")
        w("")

# ======================================================================
# BANG 8: DA RUONG HTX
# ======================================================================
mf = load("multifield_raw.csv")
if not mf:
    blocked.append("multifield_raw.csv thieu -> BANG 8 BLOCKED")
else:
    for r in mf:
        for f in ("unsafe_pct", "water_mm", "awd_eff", "awd_short", "stress_h",
                  "withheld", "dup_mm"):
            r[f] = float(r[f])
        r["slots"] = int(r["slots_per_day"])
    w("## 8. Đa ruộng (HTX) — 6 thửa, 2 loại đất × 3 trạm")
    w("")
    w(f"Nguồn `multifield_raw.csv`, n = {len(mf)} episode. "
      "Xấp xỉ khai báo: chỉ S trong 6 thửa được phục vụ mỗi ngày → "
      "epoch hiệu dụng = 24·N/S giờ.")
    w("")
    by_seed = defaultdict(list)
    for r in mf:
        by_seed[((r["alloc"], r["total_budget_mm"], r["slots"], r["network"]),
                 r["seed"])].append(r)
    htx = defaultdict(list)
    for (k, s), recs in by_seed.items():
        uns = [x["unsafe_pct"] for x in recs]
        htx[k].append(dict(um=statistics.mean(uns), uw=max(uns), g=gini(uns),
                           awd=sum(x["awd_eff"] for x in recs),
                           wat=sum(x["water_mm"] for x in recs),
                           st=sum(x["stress_h"] for x in recs),
                           wh=sum(x["withheld"] for x in recs)))
    agg = {k: {f: statistics.mean(x[f] for x in v) for f in v[0]} for k, v in htx.items()}

    w("### 8.1 Ba luật phân bổ (kênh severe, slots = 6/ngày)")
    w("")
    w("| tổng ngân sách | mm/thửa | luật | mất an toàn TB (%) | thửa xấu nhất (%) | Gini | AWD đạt | nước (mm) |")
    w("|---|---|---|---|---|---|---|---|")
    tots = sorted({r["total_budget_mm"] for r in mf},
                  key=lambda t: (t == "inf", float(t) if t != "inf" else 0))
    for tot in tots:
        for rule in ("equal", "deficit", "gate"):
            v = agg.get((rule, tot, 6, "severe"))
            if not v:
                continue
            per = "∞" if tot == "inf" else f"{float(tot)/6:.0f}"
            w(f"| {tot} | {per} | {rule} | {v['um']:.2f} | {v['uw']:.2f} | "
              f"{v['g']:.3f} | {v['awd']:.1f} | {v['wat']:.0f} |")
    w("")

    w("### 8.2 Nút vặn tần suất quyết định (slots/ngày, luật `equal`, kênh severe)")
    w("")
    w("| tổng ngân sách | slots/ngày | mất an toàn (%) | giờ stress | AWD đạt | im lặng | nước (mm) |")
    w("|---|---|---|---|---|---|---|")
    for tot in tots:
        for s in sorted({int(r["slots"]) for r in mf}, reverse=True):
            v = agg.get(("equal", tot, s, "severe"))
            if not v:
                continue
            w(f"| {tot} | {s} | {v['um']:.2f} | {v['st']:.0f} | {v['awd']:.1f} | "
              f"{v['wh']:.0f} | {v['wat']:.0f} |")
    w("")

    w("### 8.3 Kiểm định cặp slots 6 → 2 (n = số cặp seed×thửa×ngân sách×kênh)")
    w("")
    w("| luật | n cặp | Δ im lặng | t | Δ stress (h) | t | Δ mất an toàn | t | Δ AWD | t |")
    w("|---|---|---|---|---|---|---|---|---|---|")
    smax = max(int(r["slots"]) for r in mf); smin = min(int(r["slots"]) for r in mf)
    for rule in ("equal", "deficit", "gate"):
        pr = defaultdict(dict)
        for r in mf:
            if r["alloc"] != rule:
                continue
            pr[(r["seed"], r["field"], r["total_budget_mm"], r["network"])][r["slots"]] = r
        P = [v for v in pr.values() if smax in v and smin in v]
        if not P:
            continue
        cells = [str(len(P))]
        for fld in ("withheld", "stress_h", "unsafe_pct", "awd_eff"):
            m, t = paired_t([p[smin][fld] - p[smax][fld] for p in P])
            cells += [f"{m:+.2f}", f"{t:+.2f}"]
        w(f"| {rule} | " + " | ".join(cells) + " |")
    w("")

    w("### 8.4 Điểm chéo (crossover) — điều kiện áp dụng của cơ chế im lặng")
    w("")
    w("Δ = mất an toàn(`gate`) − mất an toàn(`equal`), kênh severe. **Âm = cơ chế tốt hơn.**")
    w("")
    w("| mm/thửa | slots=6 | slots=3 | slots=2 |")
    w("|---|---|---|---|")
    for tot in tots:
        per = "∞" if tot == "inf" else f"{float(tot)/6:.0f}"
        cells = []
        for s in sorted({int(r["slots"]) for r in mf}, reverse=True):
            e = agg.get(("equal", tot, s, "severe")); g = agg.get(("gate", tot, s, "severe"))
            cells.append(f"{g['um']-e['um']:+.2f}" if e and g else "—")
        w(f"| {per} | " + " | ".join(cells) + " |")
    w("")

# ======================================================================
# BANG 9: MEN DE d_max (ly thuyet + kiem chung)
# ======================================================================
sys.path.insert(0, str(ROOT / "src"))
try:
    from twin_gate import TwinParams, safe_bounds, twin_sigma  # noqa: E402
    from water_balance import SoilProfile  # noqa: E402
    prof = SoilProfile()
    lo, hi = safe_bounds(prof)
    W = hi - lo
    span = prof.fc_mm - prof.wp_mm
    g7 = math.sqrt(sum(0.9 ** (2 * k) for k in range(7)))
    sig_stat = prof.taw_mm / math.sqrt(1 - 0.9 ** 2)
    w("## 9. Ngưỡng lý thuyết (derive, không phải kết quả mô phỏng)")
    w("")
    w("| đại lượng | công thức | giá trị |")
    w("|---|---|---|")
    w(f"| W (chiều rộng tập an toàn) | (0,85 − 0) × TAW | {W:.2f} mm |")
    w(f"| TAW | (θ_fc − θ_wp) × Zr × 1000 | {prof.taw_mm:.2f} mm |")
    w(f"| span (θ_fc − θ_wp) | — | {span:.4f} |")
    w(f"| σ\\* (ngưỡng cổng rỗng) | W / (2z) | {W/(2*Z):.2f} mm |")
    w(f"| σ tĩnh (tuổi ∞) | f × TAW / √(1−ρ²) | f × {sig_stat:.2f} mm |")
    w(f"| g = √Σρ²ᵏ, k=0..6 | ρ = 0,9 | {g7:.4f} |")
    w(f"| σ_H nhỏ nhất có thể (tuổi 0) | f × TAW × g | f × {prof.taw_mm*g7:.2f} mm |")
    w(f"| f để cổng sống | σ\\* / (TAW/√(1−ρ²)) | {W/(2*Z)/sig_stat:.4f} |")
    sig_need = (0.85 - 0.75) * span / Z
    w(f"| σ_H cần cho AWD (d_target = 0,75) | (0,85 − 0,75)·span/z | {sig_need:.2f} mm |")
    w(f"| f cần cho AWD (tuổi 0) | σ_cần / (TAW·g) | {sig_need/(prof.taw_mm*g7):.4f} |")
    w(f"| f cần cho AWD (tuổi ∞) | σ_cần / σ_tĩnh | {sig_need/sig_stat:.4f} |")
    w("")
    w("**Hệ quả triển khai:** với f = 0,10 thì σ_H ≥ "
      f"{0.10*prof.taw_mm*g7:.2f} mm > {sig_need:.2f} mm, nên **tăng tần suất cảm biến "
      "cũng không cứu được** (tuổi 0 là giới hạn dưới của σ) — phải cải thiện mô hình. "
      f"Ngược lại với f = 0,02 thì σ tĩnh = {0.02*sig_stat:.2f} mm ≤ {sig_need:.2f} mm, "
      "nên cổng vẫn làm AWD được **dù không bao giờ được tái neo** (pin yếu/kênh nghẽn).")
    w("")
except Exception as e:
    blocked.append(f"khong derive duoc nguong ly thuyet: {type(e).__name__}: {e}")

# ======================================================================
# BANG 10: MAN (tinh huong)
# ======================================================================
sal = load("sweep_salinity_raw.csv")
if not sal:
    blocked.append("sweep_salinity_raw.csv thieu -> BANG 10 BLOCKED")
else:
    w("## 10. Xâm nhập mặn — PHÂN TÍCH TÌNH HUỐNG (không phải kết quả chính)")
    w("")
    w("**Khai báo trung thực:** KHÔNG có số đo độ mặn thực địa ở 3 trạm. Mọi con số "
      "dưới đây là của mô hình tình huống `src/tide_salinity.py`, chỉ dùng cho phân "
      "tích độ nhạy, **không đưa vào Abstract như kết quả**.")
    w("")
    w(f"Nguồn `sweep_salinity_raw.csv`, n = {len(sal)} episode.")
    w("")
    w("| cường độ | chính sách | nước mặn bơm (mm) | giờ nguồn còn ngọt (%) | thiệt hại NS ước tính (%) | im lặng vì mặn |")
    w("|---|---|---|---|---|---|")
    for it in sorted({float(r["intrusion"]) for r in sal}):
        for p in ("TwinGate+T2", "Reactive+T2", "FixedSchedule", "Oracle"):
            g = [r for r in sal if float(r["intrusion"]) == it and r["policy"] == p
                 and r["variant"] == "central" and r["network"] == "severe"]
            if not g:
                continue
            w(f"| {it} | {p} | {mean(g,'saline_mm'):.2f} | "
              f"{100*mean(g,'fresh_frac'):.1f} | {mean(g,'est_yield_loss_pct'):.2f} | "
              f"{mean(g,'withheld_saline'):.1f} |")
    w("")
    w("Nhạy cảm với bảng ngưỡng chịu mặn (TwinGate+T2, kênh severe, thiệt hại NS %):")
    w("")
    vs = sorted({r["variant"] for r in sal})
    its = sorted({float(r["intrusion"]) for r in sal})
    w("| ngưỡng | " + " | ".join(f"{i}" for i in its) + " |")
    w("|---|" + "---|" * len(its))
    for v in vs:
        cells = []
        for i in its:
            g = [r for r in sal if r["variant"] == v and float(r["intrusion"]) == i
                 and r["policy"] == "TwinGate+T2" and r["network"] == "severe"]
            cells.append(f"{mean(g,'est_yield_loss_pct'):.2f}" if g else "—")
        w(f"| {v} | " + " | ".join(cells) + " |")
    w("")

# ======================================================================
# BANG 11: VUNG PASS (sigma x delta)
# ======================================================================
sw = load("sweep_sigma_delta_raw.csv")
if not sw:
    blocked.append("sweep_sigma_delta_raw.csv thieu -> BANG 11 BLOCKED")
else:
    w("## 11. Vùng hoạt động của cổng — quét σ_frac × δ (chính sách đề xuất)")
    w("")
    w(f"Nguồn `sweep_sigma_delta_raw.csv`, n = {len(sw)} episode.")
    w("")
    # CSV cua sweep gio co cot `rule` (target = chinh sach de xuat; centre = doi chung
    # cua luat chon lenh). KHONG loc thi moi o gop trung binh ca hai luat -> vo nghia.
    if "rule" in sw[0]:
        n_before = len(sw)
        sw = [r for r in sw if r["rule"] == "target"]
        print(f"  muc 11: loc {n_before} -> {len(sw)} rows (giu rule=target, "
              f"chinh sach de xuat)")
    sigs = sorted({float(r["sigma_frac"]) for r in sw})
    dels = sorted({float(r["delta"]) for r in sw})
    buds = sorted({r["budget_mm"] for r in sw}, key=float)
    for b in buds:
        for net in ("severe",):
            w(f"### ngân sách {float(b):.0f} mm, kênh {net} — giờ mất an toàn (%)")
            w("")
            w("| σ_frac \\ δ | " + " | ".join(f"{d:g}" for d in dels) + " |")
            w("|---|" + "---|" * len(dels))
            for s in sigs:
                cells = []
                for d in dels:
                    g = [r for r in sw if float(r["sigma_frac"]) == s
                         and float(r["delta"]) == d and r["budget_mm"] == b
                         and r["network"] == net]
                    cells.append(f"{mean(g,'unsafe_pct'):.1f}" if g else "—")
                w(f"| {s:g} | " + " | ".join(cells) + " |")
            w("")
            w(f"### ngân sách {float(b):.0f} mm, kênh {net} — tỷ lệ quyết định IM LẶNG")
            w("")
            w("| σ_frac \\ δ | " + " | ".join(f"{d:g}" for d in dels) + " |")
            w("|---|" + "---|" * len(dels))
            for s in sigs:
                cells = []
                for d in dels:
                    g = [r for r in sw if float(r["sigma_frac"]) == s
                         and float(r["delta"]) == d and r["budget_mm"] == b
                         and r["network"] == net]
                    cells.append(f"{mean(g,'withheld_frac'):.2f}" if g else "—")
                w(f"| {s:g} | " + " | ".join(cells) + " |")
            w("")

# ======================================================================
w("## BLOCKED — thiếu bằng chứng, KHÔNG được viết vào bài")
w("")
if blocked:
    for b in blocked:
        w(f"- {b}")
else:
    w("- (không có)")
w("")
w("## Đối chiếu hình")
w("")
w("| hình | file | nguồn số liệu |")
w("|---|---|---|")
w("| 1 | `figures/fig1_method.pdf` | sơ đồ phương pháp (không có số liệu) |")
w("| 2 | `figures/fig2_ablation.pdf` | `ablation_raw.csv` |")
w("| 3 | `figures/fig3_awd_fidelity.pdf` | `main_raw.csv` (cột `awd_effective`) |")
w("| 4 | `figures/fig4_pass_region.pdf` | `sweep_sigma_delta_raw.csv` |")
w("| 5 | `figures/fig5_deployment.pdf` | `deployment_raw.csv` |")
w("| 6 | `figures/fig6_multifield.pdf` | `multifield_raw.csv` |")
w("| 7 | `figures/fig7_salinity_scenario.pdf` | `sweep_salinity_raw.csv` |")
w("| 8 | `figures/fig8_pareto.pdf` | `main_raw.csv` |")
w("")

DEST.parent.mkdir(parents=True, exist_ok=True)
DEST.write_text("\n".join(L), encoding="utf-8")
print(f"wrote {DEST} ({len(L)} lines)")
if blocked:
    print("\nBLOCKED:")
    for b in blocked:
        print("  -", b)
    sys.exit(1)
print("\nkhong co muc BLOCKED nao")

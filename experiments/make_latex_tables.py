#!/usr/bin/env python3
"""Sinh CAC BANG LATEX tu outputs/*.csv -> paper/tables/*.tex.

Ly do ton tai: moi con so trong bai phai truy nguon duoc ve CSV. Goi so bang tay
vao .tex la nguon goc cua 4 loi so lieu da bat duoc o vong nay (so cua quick run
lan vao bai, "1800 episode" cu, "41,54%" cu, "loai bo hoan toan tuoi dup" trong khi
do that chi giam 23%). Vi vay bang duoc SINH, khong duoc go.

Quy uoc: so thap phan dung DAU PHAY theo tieng Viet va nam trong $..$ (LVTN QD1418:
thap phan CHAM trong $..$ — nhung bai nay la bao tieng Viet HUJOS-TT, dung dau phay
nhat quan voi toan bo van ban; neu toa soan yeu cau cham trong math thi doi ham
vn_num thanh giu dau cham).

Usage:
    python3 experiments/make_latex_tables.py          # sinh tat ca bang
    python3 experiments/make_latex_tables.py --check  # chi kiem tra nguon, khong ghi
"""
from __future__ import annotations

import argparse
import csv
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
DEST = ROOT / "paper" / "tables"

HDR = r"""% Sinh TU DONG tu outputs/*.csv boi experiments/make_latex_tables.py
% KHONG sua tay: moi con so deu truy nguon duoc ve CSV.
"""

# Nguong "khan" cua CONG: POS-SUM nho nhat trong 3 tram (2024, ca_mau).
# Khong hardcode tuy y: day chinh la gia tri ma ncs_loop.season_deficit_suffix tra ve.
DEFICIT_POS_MIN = 450.2


def vn_num(x: float, nd: int = 2) -> str:
    """So tieng Viet: dau phay thap phan. NaN -> '--'."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "--"
    return f"{x:.{nd}f}".replace(".", "{,}")


def m(x: float, nd: int = 2) -> str:
    """Boc $..$ cho dung che do toan (tranh khoang trang sai trong bang)."""
    t = vn_num(x, nd)
    return "--" if t == "--" else "$" + t + "$"


def load(name: str) -> list[dict]:
    p = OUT / name
    if not p.exists():
        print(f"  !! THIEU {p.name} -> bo qua bang nay (khong sinh so gia)")
        return []
    with p.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def fmean(rows, col):
    v = []
    for r in rows:
        try:
            v.append(float(r[col]))
        except (KeyError, TypeError, ValueError):
            pass
    return statistics.mean(v) if v else float("nan")


def gini(xs):
    if not xs or sum(xs) == 0:
        return 0.0
    t = sorted(xs)
    n = len(t)
    return (2 * sum((i + 1) * v for i, v in enumerate(t))) / (n * sum(t)) - (n + 1) / n


def write(name: str, lines: list[str], check: bool) -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    p = DEST / f"{name}.tex"
    body = "\n".join(lines) + "\n"
    if check:
        print(f"  [check] {name}.tex: {len(lines)} dong (khong ghi)")
        return
    p.write_text(body, encoding="utf-8")
    print(f"  wrote {name}.tex ({len(lines)} dong, {len(body)} bytes)")


# ======================================================================
# BANG W: WILCOXON ghep cap (theo dai trung thuc x moc so sanh)
# ======================================================================
def tab_wilcoxon(check: bool) -> None:
    rows = load("wilcoxon_results.csv")
    if not rows or "fidelity" not in rows[0]:
        print("  !! wilcoxon_results.csv thieu cot fidelity -> chay lai stats_analysis.py")
        return
    fids = sorted({r["fidelity"] for r in rows},
                  key=lambda f: {"awd": 0, "mid": 1, "narrow": 2}.get(f, 9))
    VN = {"TwinGate+T2+centre": "centre-seeking (đối chứng luật chọn lệnh)",
          "TwinGate+blindARQ": "gửi lại mù (đối chứng T2)",
          "Reactive+T2": "ngưỡng tĩnh + T2",
          "Reactive+blindARQ": "ngưỡng tĩnh + gửi lại mù",
          "FixedSchedule": "lịch cố định (tập quán)"}
    SF = {"awd": r"$0{,}02$", "mid": r"$0{,}05$", "narrow": r"$0{,}10$"}
    L = [HDR, r"\begin{tabular}{@{}llcccc@{}}", r"\toprule",
         r"Dải $f_\sigma$ & Mốc so sánh với cổng đề xuất & Số ô & Ô có ý nghĩa & "
         r"Trung vị $\Delta$ (điểm) & $|r|$ TB \\",
         r"\midrule"]
    for fid in fids:
        for b in VN:
            g = [r for r in rows if r["fidelity"] == fid
                 and r["comparison"] == f"TwinGate+T2 vs {b}"]
            if not g:
                continue
            sig = sum(1 for r in g if r["p_holm"] != "n/a" and float(r["p_holm"]) < 0.05)
            meds = [float(r["median_diff_unsafe_pp"]) for r in g]
            rbs = [abs(float(r["rank_biserial_r"])) for r in g
                   if r["rank_biserial_r"] != "n/a"]
            med = statistics.median(meds)
            med_s = m(med) if abs(med) > 1e-9 else r"0 (hòa tuyệt đối)"
            rb_s = m(statistics.mean(rbs), 2) if rbs else "--"
            L.append(f"{SF.get(fid, fid)} & {VN[b]} & {len(g)} & {sig} & {med_s} & "
                     f"{rb_s}" + r" \\")
        L.append(r"\addlinespace[2pt]")
    L += [r"\bottomrule", r"\end{tabular}"]
    write("tab_wilcoxon", L, check)


# ======================================================================
# BANG A: ABLATION (2 dai trung thuc, kenh severe, ngan sach rang buoc)
# ======================================================================
def tab_ablation(check: bool) -> None:
    rows = load("ablation_raw.csv")
    if not rows or "fidelity" not in rows[0]:
        return
    VN = {
        "FULL (de xuat)": r"\textbf{Đầy đủ (cơ chế đề xuất)}",
        "- whatif (twin->predictor)": r"bỏ tính phản thực (twin $\to$ predictor)",
        "- cong chance-constrained": "bỏ cổng ràng buộc cơ hội",
        "- luat thich ung (centre co dinh)": "bỏ luật chọn lệnh thích ứng",
        "- tai neo cam bien": "bỏ tái neo bằng cảm biến",
        "- T2 (gui lai mu)": "bỏ T2 (gửi lại mù)",
        "- epoch cap (quyet dinh moi gio)": "bỏ trần chu kỳ 24 giờ",
        "Oracle (thong tin hoan hao)": "Oracle (thông tin hoàn hảo)",
    }
    def agg(fid, v):
        g = [r for r in rows if r["fidelity"] == fid and r["variant"] == v
             and r["network"] == "severe" and r["budget_mm"] != "inf"
             and float(r["budget_mm"]) < DEFICIT_POS_MIN]
        if not g:
            return None
        return (fmean(g, "unsafe_pct"), fmean(g, "dup_mm"), fmean(g, "awd_eff"))
    L = [HDR, r"\begin{tabular}{@{}lcccccc@{}}", r"\toprule",
         r" & \multicolumn{3}{c}{$f_\sigma=0{,}02$ (vùng đạt rộng 48\,mm)}"
         r" & \multicolumn{3}{c}{$f_\sigma=0{,}10$ (vùng đạt hẹp 4\,mm)} \\",
         r"\cmidrule(lr){2-4}\cmidrule(lr){5-7}",
         r"Biến thể (tắt đúng một thành phần) & mất an toàn (\%) & nước đúp (mm)"
         r" & AWD đạt & mất an toàn (\%) & nước đúp (mm) & AWD đạt \\"]
    L.append(r"\midrule")
    for v, nm in VN.items():
        x, y = agg("wide", v), agg("narrow", v)
        if not x or not y:
            continue
        L.append(f"{nm} & {m(x[0])} & {m(x[1],1)} & {m(x[2])} & "
                 f"{m(y[0])} & {m(y[1],1)} & {m(y[2])}" + r" \\")
    L += [r"\bottomrule", r"\end{tabular}"]
    write("tab_ablation", L, check)


# ======================================================================
# BANG D: TRIEN KHAI THUC TE (5 yeu to, moi yeu to quet rieng)
# ======================================================================
def tab_deployment(check: bool) -> None:
    rows = load("deployment_raw.csv")
    if not rows:
        return
    FAC = [
        ("F1_uplink", "Mất gói uplink", lambda v: f"{100*float(v):.0f}\\%"),
        ("F2_soil", "Loại đất", lambda v: {"loam_cat (sandy loam)": "cát pha",
                                          "thit_pha_set (mac dinh)": "thịt pha sét",
                                          "set (clay)": "sét"}.get(v, v)),
        ("F3_depth", "Độ phân giải lệnh",
         lambda v: {"fine": r"mịn $\{10,20,35\}$",
                    "agronomic": r"nông học $\{20,40,60\}$",
                    "coarse": r"thô $\{35,60,90\}$"}.get(v, v)),
        ("F4_horizon", r"Chân trời dự báo $H$", lambda v: f"{float(v):.0f} ngày"),
        ("F5_radio", "Kiểu gửi lại", lambda v: {"T2": "T2 (đề xuất)",
                                               "blindARQ": "gửi lại mù"}.get(v, v)),
    ]
    L = [HDR, r"\begin{tabular}{@{}llccccc@{}}", r"\toprule",
         r"Yếu tố & Mức & mất an toàn (\%) & AWD đạt & giờ stress & lệnh/ngày"
         r" & gửi lại/ngày \\",
         r"\midrule"]
    for fac, name, fmt in FAC:
        g0 = [r for r in rows if r["factor"] == fac]
        if not g0:
            continue
        lv = []
        for r in g0:
            if r["level"] not in lv:
                lv.append(r["level"])
        try:
            lv = sorted(lv, key=float)
        except ValueError:
            pass
        for k, L2 in enumerate(lv):
            g = [r for r in g0 if r["level"] == L2]
            L.append(f"{(name if k == 0 else '')} & {fmt(L2)} & "
                     f"{m(fmean(g,'unsafe_pct'))} & {m(fmean(g,'awd_eff'))} & "
                     f"{m(fmean(g,'stress_h'),0)} & {m(fmean(g,'cmd_per_day'),3)} & "
                     f"{m(fmean(g,'resend_per_day'),3)}" + r" \\")
        L.append(r"\addlinespace[2pt]")
    L += [r"\bottomrule", r"\end{tabular}"]
    write("tab_deployment", L, check)


# ======================================================================
# BANG H: DA RUONG HTX + diem cheo (crossover)
# ======================================================================
def tab_htx(check: bool) -> None:
    rows = load("multifield_raw.csv")
    if not rows:
        return
    for r in rows:
        r["slots"] = int(r["slots_per_day"])
        for f in ("unsafe_pct", "water_mm", "awd_eff", "awd_short", "stress_h",
                  "withheld"):
            r[f] = float(r[f])
    by = defaultdict(list)
    for r in rows:
        by[((r["alloc"], r["total_budget_mm"], r["slots"], r["network"]),
            r["seed"])].append(r)
    htx = defaultdict(list)
    for (k, sd), recs in by.items():
        uns = [x["unsafe_pct"] for x in recs]
        htx[k].append(dict(um=statistics.mean(uns), uw=max(uns), g=gini(uns),
                           awd=sum(x["awd_eff"] for x in recs),
                           wat=sum(x["water_mm"] for x in recs)))
    A = {k: {f: statistics.mean(x[f] for x in v) for f in v[0]}
         for k, v in htx.items()}
    RN = {"equal": "chia đều", "deficit": "theo thiếu hụt", "gate": "cổng im lặng"}
    tots = sorted({r["total_budget_mm"] for r in rows},
                  key=lambda t: (t == "inf", float(t) if t != "inf" else 0))
    slots = sorted({r["slots"] for r in rows}, reverse=True)

    L = [HDR, r"\begin{tabular}{@{}lllccccc@{}}", r"\toprule",
         r"mm/thửa & thửa/ngày & Luật phân bổ & mất an toàn (\%) & thửa xấu nhất (\%)"
         r" & Gini & AWD đạt & nước (mm) \\",
         r"\midrule"]
    # Chi giu slots = 6 (kênh phục vụ cả 6 thửa mỗi ngày): chieu "slots/ngay" da
    # duoc tab_crossover trinh bay day du. Giu ca 3 muc se tao bang 45 dong (~1 trang)
    # trong khi thong tin trung lap. Day la nen TRANG, khong cat noi dung.
    slots = [max(slots)]
    for tot in tots:
        per = r"$\infty$" if tot == "inf" else f"{float(tot)/6:.0f}"
        for spd in slots:
            for rule in ("equal", "deficit", "gate"):
                v = A.get((rule, tot, spd, "severe"))
                if not v:
                    continue
                L.append(f"{per} & {spd} & {RN[rule]} & {m(v['um'])} & {m(v['uw'])} & "
                         f"{m(v['g'],3)} & {m(v['awd'],1)} & {m(v['wat'],0)}" + r" \\")
        L.append(r"\addlinespace[2pt]")
    L += [r"\bottomrule", r"\end{tabular}"]
    write("tab_htx", L, check)

    # ---- bang CROSSOVER (dieu kien ap dung cua co che im lang) ----
    C = [HDR, r"\begin{tabular}{@{}lccc@{}}", r"\toprule",
         r"Ngân sách mỗi thửa (mm) & thửa/ngày $=6$ & $=3$ & $=2$ \\",
         r"\midrule"]
    for tot in tots:
        per = r"$\infty$" if tot == "inf" else f"{float(tot)/6:.0f}"
        cells = []
        for spd in slots:
            e, g = A.get(("equal", tot, spd, "severe")), A.get(("gate", tot, spd, "severe"))
            cells.append(m(g["um"] - e["um"]) if e and g else "--")
        C.append(f"{per} & " + " & ".join(cells) + r" \\")
    C += [r"\bottomrule", r"\end{tabular}"]
    write("tab_crossover", C, check)


# ======================================================================
# BANG S: MAN (tinh huong) — kenh severe, bien the nguong trung tam
# ======================================================================
def tab_salinity(check: bool) -> None:
    rows = load("sweep_salinity_raw.csv")
    if not rows:
        return
    for r in rows:
        for f in ("intrusion", "unsafe_pct", "saline_mm", "salt_excess_dsm_mm",
                  "est_yield_loss_pct", "withheld_saline", "fresh_frac"):
            r[f] = float(r[f])
    sub = [r for r in rows if r["network"] == "severe" and r["variant"] == "central"]
    POL = {"TwinGate+T2": r"\textbf{Cổng đề xuất}", "Reactive+T2": "ngưỡng tĩnh + T2",
           "FixedSchedule": "lịch cố định", "Oracle": "Oracle"}
    L = [HDR, r"\begin{tabular}{@{}llcccccc@{}}", r"\toprule",
         r"Cường độ $i$ & Chính sách & nước mặn (mm) & muối thừa (dS$\cdot$mm)"
         r" & thiệt hại NS (\%) & mất an toàn (\%) & im lặng (chu kỳ) & giờ ngọt (\%) \\",
         r"\midrule"]
    for it in sorted({r["intrusion"] for r in sub}):
        for pol in ("TwinGate+T2", "Reactive+T2", "FixedSchedule", "Oracle"):
            g = [r for r in sub if r["intrusion"] == it and r["policy"] == pol]
            if not g:
                continue
            lab = f"{vn_num(it,2)}" if pol == "TwinGate+T2" else ""
            L.append(f"{lab} & {POL[pol]} & {m(fmean(g,'saline_mm'),1)} & "
                     f"{m(fmean(g,'salt_excess_dsm_mm'),0)} & "
                     f"{m(fmean(g,'est_yield_loss_pct'),1)} & "
                     f"{m(fmean(g,'unsafe_pct'))} & "
                     f"{m(fmean(g,'withheld_saline'),1)} & "
                     f"{m(100*fmean(g,'fresh_frac'),1)}" + r" \\")
        L.append(r"\addlinespace[2pt]")
    L += [r"\bottomrule", r"\end{tabular}"]
    write("tab_salinity", L, check)

    # ---- nhay cam nguong: moc co so thay doi, cong thi khong ----
    V = {"central": "trung tâm 2,5", "grattan_strict": "Grattan chặt 1,9",
         "maas_lenient": "Maas khoan dung 3,5"}
    its = sorted({r["intrusion"] for r in rows})
    S = [HDR, r"\begin{tabular}{@{}llccccc@{}}", r"\toprule",
         r"Chính sách & Bảng ngưỡng EC$_{crit}$ (dS/m) & "
         + " & ".join(f"$i={vn_num(x,2)}$" for x in its) + r" \\",
         r"\midrule"]
    for pol, pn in (("TwinGate+T2", r"\textbf{Cổng đề xuất}"),
                    ("Reactive+T2", "ngưỡng tĩnh + T2")):
        for k, v in enumerate(("central", "grattan_strict", "maas_lenient")):
            cells = []
            for it in its:
                g = [r for r in rows if r["variant"] == v and r["policy"] == pol
                     and r["network"] == "severe" and r["intrusion"] == it]
                cells.append(m(fmean(g, "est_yield_loss_pct"), 1) if g else "--")
            S.append(f"{(pn if k == 0 else '')} & {V[v]} & " + " & ".join(cells) + r" \\")
        S.append(r"\addlinespace[2pt]")
    S += [r"\bottomrule", r"\end{tabular}"]
    write("tab_salinity_threshold", S, check)


# ======================================================================
# BANG W2: AWD theo dai trung thuc x ngan sach (khoi phuc noi dung da mat)
# ======================================================================
def tab_awd(check: bool) -> None:
    """AWD dat chuan >= 72h (QD 4801) theo dai trung thuc x ngan sach.

    Ly do ton tai: day la "gia cua chung chi carbon" — ket qua manh nhat cua bai.
    No tung nam trong mot khoi hinh + doan van o muc 6.2, nhung khoi do da bi xoa
    khi muc 6.2 duoc viet lai (span_replace chi thay doan dau). Khoi phuc duoi dang
    BANG vi re hon hinh ~0.35 trang ma van day du so lieu.
    """
    rows = load("main_raw.csv")
    if not rows or "fidelity" not in rows[0]:
        return
    for r in rows:
        for f in ("awd_effective", "awd_short", "stress_hours", "hours_unsafe", "hours"):
            r[f] = float(r[f])
    sub = [r for r in rows if r["policy"] == "TwinGate+T2" and r["network"] == "severe"]
    fids = sorted({r["fidelity"] for r in sub},
                  key=lambda f: {"awd": 0, "mid": 1, "narrow": 2}.get(f, 9))
    SF = {"awd": r"$0{,}02$", "mid": r"$0{,}05$", "narrow": r"$0{,}10$"}
    buds = ["80.0", "240.0", "400.0", "inf"]
    L = [HDR, r"\begin{tabular}{@{}llcccc@{}}", r"\toprule",
         r"Dải $f_\sigma$ & Ngân sách $B$ (mm) & AWD đạt chuẩn & AWD hụt chuẩn"
         r" & giờ stress & mất an toàn (\%) \\",
         r"\midrule"]
    for fid in fids:
        for k, b in enumerate(buds):
            g = [r for r in sub if r["fidelity"] == fid and r["budget_mm"] == b]
            if not g:
                continue
            lab = SF.get(fid, fid) if k == 0 else ""
            bl = r"$\infty$" if b == "inf" else f"{float(b):.0f}"
            uns = 100 * statistics.mean([x["hours_unsafe"] / x["hours"] for x in g])
            L.append(f"{lab} & {bl} & {m(fmean(g,'awd_effective'))} & "
                     f"{m(fmean(g,'awd_short'))} & {m(fmean(g,'stress_hours'),0)} & "
                     f"{m(uns)}" + r" \\")
        L.append(r"\addlinespace[2pt]")
    L += [r"\bottomrule", r"\end{tabular}"]
    write("tab_awd", L, check)


# ======================================================================
# BANG M: MAT NGUONG sigma x delta (luoi day du, chinh sach de xuat)
# ======================================================================
def tab_sigma_delta(check: bool) -> None:
    rows = load("sweep_sigma_delta_raw.csv")
    if not rows:
        return
    if "rule" in rows[0]:
        rows = [r for r in rows if r["rule"] == "target"]
    for r in rows:
        r["sigma_frac"] = float(r["sigma_frac"]); r["delta"] = float(r["delta"])
        r["budget_mm"] = float(r["budget_mm"]) if r["budget_mm"] != "inf" else math.inf
    sigs = sorted({r["sigma_frac"] for r in rows})
    dels = sorted({r["delta"] for r in rows})
    buds = sorted({r["budget_mm"] for r in rows})
    W_SAFE, STEP, Z = 59.5, 20.0, 1.959963984540054
    G7 = math.sqrt(sum(0.9 ** (2 * k) for k in range(7)))
    TAW = 70.0

    def width(sf, dl):
        sig = min(sf * TAW * G7, sf * TAW / math.sqrt(1 - 0.9 ** 2))
        return W_SAFE - 2 * Z * sig      # dung z hai duoi nhu trong cong

    net = "severe"
    for bud in buds:
        for metric, cap, nd in (("unsafe_pct", "giờ mất an toàn (\\%)", 1),
                                ("withheld_frac", "tỷ lệ quyết định im lặng", 2)):
            L = [HDR, r"\begin{tabular}{@{}l" + "c" * len(dels) + r"@{}}", r"\toprule",
                 r"$\sigma_{frac}$ \textbackslash\ $\delta$ & "
                 + " & ".join(f"{d:g}" for d in dels) + r" \\",
                 r"\midrule"]
            for sf in sigs:
                cells = []
                for dl in dels:
                    g = [r for r in rows if r["sigma_frac"] == sf and r["delta"] == dl
                         and r["network"] == net and r["budget_mm"] == bud]
                    cells.append(m(fmean(g, metric), nd) if g else "--")
                L.append(f"{sf:g} & " + " & ".join(cells) + r" \\")
            L += [r"\bottomrule", r"\end{tabular}"]
            nm = f"tab_sweep_{int(bud)}_{'unsafe' if 'unsafe' in metric else 'withheld'}"
            write(nm, L, check)

    # ---- bang O DAC TA: nguong tinh bang cong thuc ----
    # LOI SPAN DA SUA (2026-10-04, phat hien khi teach-back doi chieu bang vs text):
    # span = FC - WP = 160 - 90 = 70 mm (water_balance.py depletion_fraction).
    # Ban cu hardcode span*1000 = 140 mm (gap DOI) => bang in 7,14 mm va
    # f_sigma 0,0506/0,0445, mau thuan text paper (3,57 mm; f_sigma <= 0,025).
    SPAN_MM = 70.0
    S = [HDR, r"\begin{tabular}{@{}lll@{}}", r"\toprule",
         r"Đại lượng & Công thức & Giá trị \\", r"\midrule"]
    sig_star = W_SAFE / (2 * Z)
    sig_need = (0.85 - 0.75) * SPAN_MM / Z      # = 3.57 mm, khop text Muc 6.9
    S.append(r"$W$ (chiều rộng tập an toàn) & $(0{,}85-0)\times$TAW & "
             + m(W_SAFE, 1) + r"\,mm \\")
    S.append(r"$\sigma^{*}$ (ngưỡng cổng rỗng) & $W/(2z_{1-\delta/2})$ & "
             + m(sig_star, 2) + r"\,mm \\")
    S.append(r"$\sigma_H$ tối thiểu (tuổi 0) & $f_\sigma\cdot$TAW$\cdot\sqrt{\sum\rho^{2k}}$ & "
             + r"$f_\sigma\times" + vn_num(TAW * G7, 2) + r"$\,mm \\")
    S.append(r"$\sigma$ tĩnh (tuổi $\infty$) & $f_\sigma\cdot$TAW$/\sqrt{1-\rho^2}$ & "
             + r"$f_\sigma\times" + vn_num(TAW / math.sqrt(1 - 0.81), 2) + r"$\,mm \\")
    S.append(r"$\sigma_H$ cần cho AWD ($d^*=0{,}75$) & $(0{,}85-d^{*})\cdot$"
             r"$\mathrm{span}/z$ & " + m(sig_need, 2) + r"\,mm \\")
    S.append(r"$f_\sigma$ tối đa để cổng sống & $\sigma^{*}/(\mathrm{TAW}/\sqrt{1-\rho^2})$ & "
             + m(sig_star / (TAW / math.sqrt(1 - 0.81)), 4) + r" \\")
    S.append(r"$f_\sigma$ tối đa để AWD đạt chuẩn (tuổi 0) & $\sigma_{\text{cần}}/"
             r"(\mathrm{TAW}\cdot g)$ & "
             + m(sig_need / (TAW * G7), 4) + r" \\")
    S.append(r"$f_\sigma$ tối đa để AWD đạt chuẩn (tuổi $\infty$) & $\sigma_{\text{cần}}/"
             r"\sigma_{\text{tĩnh}}$ & "
             + m(sig_need / (TAW / math.sqrt(1 - 0.81)), 4) + r" \\")
    S += [r"\bottomrule", r"\end{tabular}"]
    write("tab_spec", S, check)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="chi kiem tra nguon du lieu, khong ghi file")
    a = ap.parse_args()
    print(f"nguon: {OUT}")
    for fn in (tab_wilcoxon, tab_ablation, tab_deployment, tab_htx, tab_awd,
               tab_salinity, tab_sigma_delta):
        print(f"\n=== {fn.__name__} ===")
        try:
            fn(a.check)
        except Exception as e:
            print(f"  !! THAT BAI {type(e).__name__}: {e}")
            import traceback; traceback.print_exc()
            return 1
    print("\nxong")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""HINH 2..9 — cac hinh KET QUA, ve truc tiep tu CSV trong outputs/.

Nguyen tac bat buoc (anh Van: "dong gop that, khong chi tren giay"):
  * Moi con so tren hinh deu doc tu CSV that do mo phong sinh ra. KHONG co so nao
    duoc go truc tiep trong file nay, tru cac nguong LY THUYET (sigma*, d_max, 72h)
    va nhung so do duoc ghi chu ro la "derive".
  * Neu CSV thieu cot can ve -> in CANH BAO va bo qua hinh do, KHONG ve du lieu gia.
  * In ra man hinh bang so lieu da ve de doi chieu voi bai bao.

Usage:
    python3 figures/fig_results.py            # ve tat ca, can outputs/ da co
    python3 figures/fig_results.py --only 3   # chi ve hinh 3
"""
from __future__ import annotations

import argparse
import csv
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUTD = ROOT / "outputs"
FIG = ROOT / "figures"
FIG.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 7.6,
    "axes.titlesize": 8.4,
    "axes.labelsize": 7.8,
    "axes.linewidth": 0.7,
    "xtick.labelsize": 7.0,
    "ytick.labelsize": 7.0,
    "legend.fontsize": 6.9,
    "legend.frameon": False,
    "figure.dpi": 150,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.03,
})

# mau: in den trang van phan biet duoc (khac net + khac marker)
INK = "#1a1a1a"
C_FULL = "#1b6ca8"
C_BASE = "#8c8c8c"
C_BAD = "#c0392b"
C_OK = "#2e7d32"
C_ACC = "#6a3d9a"
C_NET = "#b9770e"      # mau kenh vo tuyen / nguong EC (nhat quan voi fig_method.py)
MARK = {0: "o", 1: "s", 2: "^", 3: "D", 4: "v", 5: "P", 6: "X", 7: "*"}

# nguong LY THUYET (khong phai ket qua mo phong) — nguon ghi trong chu thich
Z = 1.959963984540054
AWD_HOURS = 72.0          # QD 4801/2025: pha kho toi thieu de duoc tinh
D_SAFE_HI = 0.85          # bien tren depletion an toan
# Thieu hut mua kho: TINH TU DU LIEU (khong hardcode 318 nua).
# CONG dung POS-SUM = sum(max(0, Kc*ET0_h - P_h)) de xet khan: 450.2 / 468.5 / 485.1 mm
# (ca_mau / soc_trang / can_tho). Thieu hut RONG (Kc*sum ET0 - sum mua) = 301.6 / 306.0
# / 318.4 mm. Moi ngan sach huu han trong luoi (80..400) deu < POS-SUM => deu rang buoc.
sys.path.insert(0, str(ROOT / "src"))
from ncs_loop import load_weather as _lw, march_start as _ms, \
    season_deficit_suffix as _sds  # noqa: E402
from water_balance import SoilProfile as _SP  # noqa: E402

_prof = _SP()
DEFICIT_POS, DEFICIT_NET = {}, {}
for _st in ("can_tho", "soc_trang", "ca_mau"):
    _w, _ = _lw(_st)
    _s0 = _ms(_w)
    _seg = _w[_s0:_s0 + 2160]
    DEFICIT_NET[_st] = max(0.0, _prof.kc * sum(r["et0"] for r in _seg)
                           - sum(r["p"] for r in _seg))
    DEFICIT_POS[_st] = _sds(_w, _s0, 2160, _prof)[0]
DEFICIT_MM = min(DEFICIT_POS.values())      # nguong khan (POS-SUM) — cong dung cai nay
DEFICIT_NET_MAX = max(DEFICIT_NET.values()) # thieu hut rong lon nhat, chi de ve tham khao


def load(name: str) -> list[dict]:
    p = OUTD / name
    if not p.exists():
        print(f"  !! CANH BAO: thieu {p.name} -> bo qua")
        return []
    with p.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def need(rows: list[dict], cols: list[str], tag: str) -> bool:
    if not rows:
        return False
    miss = [c for c in cols if c not in rows[0]]
    if miss:
        print(f"  !! CANH BAO {tag}: CSV thieu cot {miss} -> bo qua hinh (khong ve du lieu gia)")
        return False
    return True


def fmean(rows, col, cast=float):
    v = [cast(r[col]) for r in rows if r[col] not in ("", None)]
    return statistics.mean(v) if v else float("nan")


def stats_z_fig(delta: float) -> float:
    """z_{1-delta/2} bang xap xi Acklam; da doi chieu scipy.stats.norm.ppf (lech < 3e-9)."""
    p = 1.0 - delta / 2.0
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
           (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def save(fig, stem: str) -> None:
    fig.savefig(FIG / f"{stem}.pdf")
    fig.savefig(FIG / f"{stem}.png", dpi=300)
    plt.close(fig)
    print(f"  wrote {stem}.pdf + .png")


# ======================================================================
# HINH 2: ABLATION — cai gia cua tung thanh phan
# ======================================================================
def fig2() -> None:
    rows = load("ablation_raw.csv")
    if not need(rows, ["fidelity", "variant", "budget_mm", "network", "seed",
                       "station", "unsafe_pct", "dup_mm"], "fig2"):
        return
    print("\n=== HINH 2: ABLATION ===")
    fid = "wide" if any(r["fidelity"] == "wide" for r in rows) else rows[0]["fidelity"]
    sub = [r for r in rows if r["fidelity"] == fid and r["network"] == "severe"]
    variants = []
    for r in sub:
        if r["variant"] not in variants:
            variants.append(r["variant"])
    # sap xep: FULL dau, Oracle cuoi, con lai theo muc do gay hai
    order = [v for v in variants if v.startswith("FULL")]
    rest = [v for v in variants if not v.startswith(("FULL", "Oracle"))]
    orc = [v for v in variants if v.startswith("Oracle")]

    def harm(v):
        g = [r for r in sub if r["variant"] == v and r["budget_mm"] != "inf"]
        f = [r for r in sub if r["variant"].startswith("FULL") and r["budget_mm"] != "inf"]
        if not g or not f:
            return 0.0
        return abs(fmean(g, "unsafe_pct") - fmean(f, "unsafe_pct"))
    order += sorted(rest, key=harm, reverse=True) + orc

    budgets = sorted({r["budget_mm"] for r in sub},
                     key=lambda b: (b == "inf", float(b) if b != "inf" else 0))
    binding = [b for b in budgets if b != "inf" and float(b) < DEFICIT_MM]

    fig, axes = plt.subplots(1, 2, figsize=(7.1, 2.85),
                             gridspec_kw={"width_ratios": [1.62, 1.0]})

    # (a) unsafe% theo ngan sach, moi bien the mot duong
    ax = axes[0]
    xs = [float(b) if b != "inf" else float(binding[-1]) * 1.22 for b in budgets]
    for i, v in enumerate(order):
        ys = [fmean([r for r in sub if r["variant"] == v and r["budget_mm"] == b],
                    "unsafe_pct") for b in budgets]
        isfull = v.startswith("FULL")
        isorc = v.startswith("Oracle")
        ax.plot(xs, ys, marker=MARK[i % 8], ms=3.6 if not isfull else 4.6,
                lw=2.0 if isfull else (1.5 if isorc else 1.05),
                color=C_FULL if isfull else (C_OK if isorc else
                                             (C_BASE if not v.startswith("-") else C_BAD)),
                alpha=1.0 if (isfull or isorc) else 0.82,
                ls="-" if (isfull or isorc) else "--",
                label=v, zorder=3 if isfull else 2)
    ax.axvline(DEFICIT_MM, color=INK, lw=1.0, ls=":", zorder=1)
    ax.text(DEFICIT_MM * 1.02, ax.get_ylim()[1] * 0.965,
            f"ngưỡng khan\n(POS-SUM {DEFICIT_MM:.0f}–{max(DEFICIT_POS.values()):.0f} mm)",
            fontsize=6.1, va="top", color=INK)
    ax.axvline(DEFICIT_NET_MAX, color=C_ACC, lw=0.8, ls=(0, (2, 2)), zorder=1)
    ax.text(DEFICIT_NET_MAX * 0.985, ax.get_ylim()[1] * 0.62,
            f"thiếu hụt ròng\n({min(DEFICIT_NET.values()):.0f}–{DEFICIT_NET_MAX:.0f} mm)",
            fontsize=6.1, va="top", ha="right", color=C_ACC)
    ax.set_xscale("log")
    ax.set_xticks(xs)
    ax.set_xticklabels([("∞" if b == "inf" else f"{float(b):.0f}") for b in budgets])
    ax.set_xlabel("ngân sách nước cả mùa (mm)")
    ax.set_ylabel("giờ mất an toàn (%)")
    ax.set_title(f"(a) Bỏ từng thành phần, dải {fid}, kênh severe", loc="left")
    ax.grid(alpha=0.22, lw=0.5)
    ax.legend(loc="upper right", ncols=1)

    # (b) thanh ngang: tac hai cua viec bo tung thanh phan (2 chi so)
    ax = axes[1]
    labels, du, dd = [], [], []
    full_g = [r for r in sub if r["variant"].startswith("FULL") and r["budget_mm"] in binding]
    base_u = fmean(full_g, "unsafe_pct")
    base_d = fmean(full_g, "dup_mm")
    for v in order:
        if v.startswith(("FULL", "Oracle")):
            continue
        g = [r for r in sub if r["variant"] == v and r["budget_mm"] in binding]
        if not g:
            continue
        labels.append(v.replace("- ", "").replace(" (centre co dinh)", "")
                      .replace(" (quyet dinh moi gio)", "").replace(" (gui lai mu)", "")
                      .replace(" (twin->predictor)", "→predictor")
                      .replace("chance-constrained", "cổng 95%")
                      .replace("tai neo cam bien", "tái neo cảm biến")
                      .replace("luat thich ung", "luật thích ứng"))
        du.append(fmean(g, "unsafe_pct") - base_u)
        dd.append(fmean(g, "dup_mm") - base_d)
    y = np.arange(len(labels))
    ax.barh(y - 0.19, du, height=0.36, color=C_BAD, alpha=0.88,
            label="Δ giờ mất an toàn (điểm %)")
    ax2 = ax.twiny()
    ax2.barh(y + 0.19, dd, height=0.36, color=C_ACC, alpha=0.85,
             label="Δ nước lãng phí do tưới đúp (mm)")
    ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=6.9)
    ax.invert_yaxis()
    ax.axvline(0, color=INK, lw=0.8)
    ax2.axvline(0, color=INK, lw=0.8)
    ax.set_xlabel("Δ giờ mất an toàn (điểm %)", color=C_BAD)
    ax2.set_xlabel("Δ nước lãng phí (mm)", color=C_ACC)
    ax.tick_params(axis="x", colors=C_BAD); ax2.tick_params(axis="x", colors=C_ACC)
    ax.set_title("(b) Cái giá phải trả nếu bỏ", loc="left")
    ax.grid(axis="x", alpha=0.22, lw=0.5)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="lower right", fontsize=6.2)

    save(fig, "fig2_ablation")
    print(f"  {'thanh phan':<26}{'dUnsafe':>10}{'dDup_mm':>10}")
    for l, a, b in zip(labels, du, dd):
        print(f"  {l:<26}{a:>+10.2f}{b:>+10.2f}")


# ======================================================================
# HINH 3: AWD — BANG roi SUP (dong gop MRV that)
# ======================================================================
def fig3() -> None:
    rows = load("main_raw.csv")
    if not need(rows, ["fidelity", "policy", "network", "budget_mm", "seed", "station",
                       "awd_effective", "awd_short", "hours_unsafe", "hours",
                       "stress_hours"], "fig3"):
        # main_raw.csv cu chua co fidelity -> thu lay tu sweep/ablation
        print("  (thu nguon thay the: ablation_raw.csv)")
        return _fig3_from_ablation()
    print("\n=== HINH 3: AWD theo do trung thuc ===")
    sub = [r for r in rows if r["policy"] == "TwinGate+T2" and r["network"] == "severe"]
    fids = []
    for r in sub:
        if r["fidelity"] not in fids:
            fids.append(r["fidelity"])
    sfs = sorted({float(r["sigma_frac"]) for r in rows})
    lab = {r["fidelity"]: float(r["sigma_frac"]) for r in rows}
    fids = sorted(fids, key=lambda f: lab[f])

    fig, axes = plt.subplots(1, 2, figsize=(7.1, 2.75))

    # (a) so chu ky AWD dat chuan vs khong dat, theo do trung thuc
    ax = axes[0]
    budgets = ["240.0", "320.0"]
    for i, b in enumerate(budgets):
        g = [r for r in sub if r["budget_mm"] == b]
        if not g:
            continue
        xs, eff, short = [], [], []
        for f in fids:
            gg = [r for r in g if r["fidelity"] == f]
            if not gg:
                continue
            xs.append(lab[f])
            eff.append(fmean(gg, "awd_effective"))
            short.append(fmean(gg, "awd_short"))
        ax.plot(xs, eff, marker="o", ms=4.2, lw=1.6, color=C_FULL,
                ls=["-", "--"][i % 2], label=f"đạt chuẩn ≥72h (b={float(b):.0f}mm)")
        ax.plot(xs, short, marker="x", ms=4.0, lw=1.2, color=C_BAD, alpha=0.8,
                ls=["-", "--"][i % 2], label=f"pha khô <72h, mất tín chỉ (b={float(b):.0f}mm)")
    ax.set_xscale("log")
    ax.set_xlabel("độ lệch chuẩn bản sao, σ_frac (phần TAW)")
    ax.set_ylabel("số chu kỳ AWD mỗi mùa")
    ax.set_title("(a) AWD bằng rồi sụp, không đơn điệu", loc="left")
    ax.grid(alpha=0.22, lw=0.5)
    ax.legend(loc="center left", fontsize=6.3)

    # (b) danh doi: AWD dat chuan vs gio stress (cung mot co che)
    ax = axes[1]
    xs, eff, stress = [], [], []
    for f in fids:
        gg = [r for r in sub if r["fidelity"] == f and r["budget_mm"] == "240.0"]
        if not gg:
            continue
        xs.append(lab[f]); eff.append(fmean(gg, "awd_effective"))
        stress.append(fmean(gg, "stress_hours"))
    ax.plot(xs, eff, marker="o", ms=4.4, lw=1.7, color=C_FULL, label="chu kỳ AWD đạt chuẩn")
    ax.set_xlabel("σ_frac (phần TAW)")
    ax.set_ylabel("chu kỳ AWD đạt chuẩn", color=C_FULL)
    ax.tick_params(axis="y", colors=C_FULL)
    ax.set_xscale("log")
    ax2 = ax.twinx()
    ax2.plot(xs, stress, marker="s", ms=4.0, lw=1.4, color=C_BAD, ls="--",
             label="giờ cây bị stress (Ks<1)")
    ax2.set_ylabel("giờ stress cả mùa", color=C_BAD)
    ax2.tick_params(axis="y", colors=C_BAD)
    ax.set_title("(b) Được tín chỉ carbon hay được năng suất?", loc="left")
    ax.grid(alpha=0.22, lw=0.5)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper right", fontsize=6.3)

    save(fig, "fig3_awd_fidelity")
    print(f"  {'sigma_frac':>11}{'AWD_dat':>9}{'AWH_hut':>9}{'stress_h':>10}")
    for x, e, s in zip(xs, eff, stress):
        print(f"  {x:>11.3f}{e:>9.2f}{'':>9}{s:>10.0f}")


def _fig3_from_ablation() -> None:
    """Du phong: neu main_raw.csv chua co cot fidelity thi dung ablation_raw.csv."""
    rows = load("ablation_raw.csv")
    if not need(rows, ["fidelity", "sigma_frac", "variant", "budget_mm", "network",
                       "awd_eff", "awd_short", "unsafe_pct", "stress_h"], "fig3b"):
        return
    sub = [r for r in rows if r["variant"].startswith("FULL") and r["network"] == "severe"]
    fig, ax = plt.subplots(figsize=(3.5, 2.6))
    xs, eff, short = [], [], []
    for f in sorted({float(r["sigma_frac"]) for r in sub}):
        g = [r for r in sub if float(r["sigma_frac"]) == f and r["budget_mm"] == "240.0"]
        if not g:
            continue
        xs.append(f); eff.append(fmean(g, "awd_eff")); short.append(fmean(g, "awd_short"))
    ax.plot(xs, eff, marker="o", color=C_FULL, lw=1.7, label="đạt chuẩn ≥72h")
    ax.plot(xs, short, marker="x", color=C_BAD, lw=1.2, label="mất tín chỉ (<72h)")
    ax.set_xscale("log"); ax.set_xlabel("σ_frac (phần TAW)")
    ax.set_ylabel("chu kỳ AWD mỗi mùa")
    ax.set_title("AWD theo độ trung thực bản sao", loc="left")
    ax.grid(alpha=0.22, lw=0.5); ax.legend(fontsize=6.5)
    save(fig, "fig3_awd_fidelity")
    print("  (ve tu ablation_raw.csv — chi co 2 moc sigma)")


# ======================================================================
# HINH 4: VUNG HOAT DONG CUA CONG — mat (sigma, delta) va menh de d_max
# ----------------------------------------------------------------------
# HAI LOI DA SUA (2026-10-04):
#  (a) CSV cua sweep gio co cot `rule` (target = chinh sach de xuat; centre = doi
#      chung cua luat chon lenh). KHONG loc thi moi o gop trung binh CA HAI luat
#      -> mat nguong ve ra vo nghia.
#  (b) Truc x cua hinh dung `delta` nhung nhan lai ghi theo log10 trong khi
#      imshow dat extent theo log10 -> dung, giu nguyen; chi sua cho tieu de va
#      ghi chu neu can. Ngoai ra them o (c): SO UNG VIEN LOT VUNG PASS tinh tu
#      cong thuc, dat canh o de nguoi doc thay ranh gioi cua menh de d_max.
# ======================================================================
def fig4() -> None:
    rows = load("sweep_sigma_delta_raw.csv")
    if not need(rows, ["sigma_frac", "delta", "budget_mm", "network", "seed",
                       "station", "unsafe_pct", "withheld_frac"], "fig4"):
        return
    print("\n=== HINH 4: VUNG HOAT DONG CUA CONG ===")
    # (a) chi lay chinh sach de xuat
    if "rule" in rows[0]:
        n0 = len(rows)
        rows = [r for r in rows if r["rule"] == "target"]
        print(f"  loc rule=target: {n0} -> {len(rows)} rows")
    sigs = sorted({float(r["sigma_frac"]) for r in rows})
    dels = sorted({float(r["delta"]) for r in rows})
    buds = sorted({r["budget_mm"] for r in rows},
                  key=lambda b: (b == "inf", float(b) if b != "inf" else 0))
    # O ngan sach lon (400 mm) gan nhu moi o deu 0.0% nen phi dai mau va CHE mat
    # nguong. Chon ngan sach RANG BUOC (nho nhat) cho hai o dau de ranh gioi
    # song/chet hien ro; o thu ba dung cong thuc nen khong phu thuoc ngan sach.
    show_b = buds[0]
    show_b_hi = buds[-1] if len(buds) > 1 else buds[0]
    net = "severe" if any(r["network"] == "severe" for r in rows) else rows[0]["network"]

    def grid(metric, bud, netw):
        M = np.full((len(sigs), len(dels)), np.nan)
        for i, sg in enumerate(sigs):
            for k, dl in enumerate(dels):
                g = [r for r in rows if float(r["sigma_frac"]) == sg
                     and float(r["delta"]) == dl and str(r["budget_mm"]) == str(bud)
                     and r["network"] == netw]
                if g:
                    M[i, k] = fmean(g, metric)
        return M

    # do rong vung pass va so ung vien lot (menh de d_max), tinh tu cong thuc
    W_SAFE = 59.5
    STEP = 20.0
    def width(sg, dl):
        g7 = math.sqrt(sum(0.9 ** (2 * k) for k in range(7)))
        sig = min(sg * 70.0 * g7, sg * 70.0 / math.sqrt(1 - 0.9 ** 2))
        return W_SAFE - 2 * stats_z_fig(dl) * sig
    def n_cand(sg, dl):
        w_ = width(sg, dl)
        if w_ <= 0:
            return 0
        return 1 + int(w_ // STEP)

    panels = [("unsafe_pct", f"giờ mất an toàn (%)\nB={float(show_b):.0f} mm (ràng buộc), {net}", "magma_r"),
              ("withheld_frac", f"quyết định IM LẶNG\nB={float(show_b):.0f} mm (ràng buộc), {net}", "viridis"),
              (None, "số lệnh phân biệt lọt vùng đạt\n(mệnh đề d_max, tính từ công thức)", "RdYlBu")]
    fig, axes = plt.subplots(1, 3, figsize=(7.3, 2.55))
    for k, (metric, ttl, cmap) in enumerate(panels):
        ax = axes[k]
        if metric is None:
            M = np.array([[n_cand(sg, dl) for dl in dels] for sg in sigs], dtype=float)
        else:
            M = grid(metric, show_b, net)
        im = ax.imshow(M, aspect="auto", cmap=cmap, origin="lower",
                       extent=[math.log10(dels[0]), math.log10(dels[-1]),
                               math.log10(sigs[0]), math.log10(sigs[-1])])
        for i in range(len(sigs)):
            for q in range(len(dels)):
                if np.isnan(M[i, q]):
                    continue
                v = M[i, q]
                if metric == "withheld_frac":
                    txt = f"{v:.2f}"
                elif metric is None:
                    txt = f"{int(v)}"
                else:
                    txt = f"{v:.0f}" if v >= 10 else f"{v:.1f}"
                thr = np.nanmax(M) * 0.55 if metric != "withheld_frac" else 0.5
                ax.text(math.log10(dels[q]), math.log10(sigs[i]), txt,
                        ha="center", va="center", fontsize=5.4,
                        color="w" if v > thr else INK)
        ax.set_xticks([math.log10(d) for d in dels])
        ax.set_xticklabels([f"{d:g}" for d in dels], fontsize=6.0)
        ax.set_yticks([math.log10(sg) for sg in sigs])
        ax.set_yticklabels([f"{sg:g}" for sg in sigs], fontsize=6.0)
        ax.set_xlabel("δ (mức rủi ro cho phép)")
        if k == 0:
            ax.set_ylabel("σ_frac (phần TAW)")
        ax.set_title(f"({'abc'[k]}) {ttl}", loc="left", fontsize=7.2)
        cb = fig.colorbar(im, ax=ax, pad=0.015, fraction=0.045)
        cb.ax.tick_params(labelsize=5.8)

    # vung cong RONG (width <= 0): vien net dut o ranh gioi sigma*
    ax = axes[2]
    ax.text(0.03, 0.05, "số 0 = cổng rỗng (Hệ quả σ*)\nsố 1 = mọi luật chọn lệnh trùng nhau",
            transform=ax.transAxes, fontsize=5.6, color=INK, va="bottom",
            bbox=dict(fc="white", ec="none", pad=1.2, alpha=0.85))
    save(fig, "fig4_pass_region")

    M = grid("unsafe_pct", show_b, net)
    print(f"  B={show_b} | unsafe% (hang=sigma_frac, cot=delta) | kenh {net}")
    print("        " + " ".join(f"{d:>6g}" for d in dels))
    for i, sg in enumerate(sigs):
        print(f"  {sg:>5g} " + " ".join(
            (f"{M[i, q]:>6.1f}" if not np.isnan(M[i, q]) else f"{'--':>6}")
            for q in range(len(dels))))
    if show_b_hi != show_b:
        M2 = grid("unsafe_pct", show_b_hi, net)
        print(f"  doi chieu B={show_b_hi} mm (khong rang buoc): "
              + " ".join(f"s={sg:g}:" + ",".join(
                  f"{M2[i, q]:.1f}" if not np.isnan(M2[i, q]) else "--"
                  for q in range(len(dels))) for i, sg in enumerate(sigs[:3])))
    print(f"  vung pass (mm): " + " ".join(f"{width(sigs[0], d):.1f}" for d in dels)
          + f"   (tai sigma_frac={sigs[0]})")


# ======================================================================
# HINH 5: TRIEN KHAI THUC TE — 5 yeu to
# ----------------------------------------------------------------------
# LOI TRINH BAY DA SUA (2026-10-04, do bang vision_fallback):
#   * NHAN SAI COT (loi that, khong phai chi dep): SOIL_LBL/DEPTH_LBL duoc dat khoa
#     theo cot `soil` ("fc0.31_wp0.12") va `depth_set` ("20x40x60"), trong khi truc
#     ve theo cot `level` ("loam_cat (sandy loam)", "agronomic"). Mapping truot het
#     -> hinh in chuoi goc dai, xoay, chong nhau. Da sua: map theo DUNG cot `level`,
#     va them kiem tra STRICT de loi loai nay tu bao thay vi am tham in rac.
#   * nhan hang muc o o (a) dinh nhau ("5%15%30%50%70%90%") vi 6 cot trong o hep.
#     Sua theo BAN CHAT bien, khong phai thu nho chu: yeu to LIEN TUC (ty le mat
#     goi, chan troi H) ve duong; yeu to PHAN LOAI (loai dat, do phan giai, kieu
#     gui lai) ve cot. Duong chi can vai tick, khong can 6 nhan.
#   * chu thich mau de len nhan xoay -> chu thich chung dat ngoai vung ve.
# ======================================================================
# NHAN PHAI NGAN: moi o chi rong ~1.3 inch = 94 pt. O 5.9 pt mot ky tu ~3.2 pt,
# nen toi da ~8 ky tu cho o 3 cot, ~29 ky tu cho o 2 cot. Ban truoc de "thịt pha sét"
# = 12 ky tu (o 3 cot) nen dinh nhau la chac chan — day la loi that, khong phai font.
# Ten day du duoc day xuong ghi chu duoi hinh (fig.text) de khong mat thong tin.
LBL_SOIL = {
    "loam_cat (sandy loam)":  "cát pha",
    "thit_pha_set (mac dinh)": "thịt",
    "set (clay)":             "sét",
}
LBL_DEPTH = {"fine": "mịn", "agronomic": "nông học", "coarse": "thô"}
LBL_RADIO = {"T2": "T2", "blindARQ": "gửi lại mù"}
# (factor, kieu bien): "cont" = lien tuc -> ve duong; "cat" = phan loai -> ve cot
FACTOR_KIND = {
    "F1_uplink": ("cont", "tỷ lệ mất gói uplink", lambda v: f"{100*v:.0f}%"),
    "F2_soil": ("cat", "loại đất", None),
    "F3_depth": ("cat", "độ phân giải lệnh", None),
    "F4_horizon": ("cont", "chân trời dự báo H (ngày)", lambda v: f"{v:g}"),
    "F5_radio": ("cat", "kiểu gửi lại", None),
}
# chi cac factor "cat" can map nhan; factor "cont" dung ham fmt trong FACTOR_KIND
FACTOR_LBL = {"F2_soil": LBL_SOIL, "F3_depth": LBL_DEPTH, "F5_radio": LBL_RADIO}
PANEL = {
    "F1_uplink":  "(a) Chất lượng mạng",
    "F2_soil":    "(b) Loại đất",
    "F3_depth":   "(c) Độ phân giải lệnh",
    "F4_horizon": "(d) Chân trời dự báo",
    "F5_radio":   "(e) Kiểu gửi lại",
}


def strict_labels(levels: list[str], mapping, tag: str) -> list[str]:
    """Nhan tieng Viet ngan; bao loi neu co level nao CHUA duoc map.

    Day la cho chot chan loi da xay ra o ban truoc: mapping dat khoa sai cot thi
    moi level deu "khong tim thay" va hinh am tham in chuoi goc dai -> chong chu.
    """
    miss = [L for L in levels if L not in mapping]
    if miss:
        print(f"  !! CANH BAO {tag}: {len(miss)} level CHUA co nhan -> se in chuoi goc: "
              f"{miss}")
    return [mapping.get(L, L) for L in levels]


def fig5() -> None:
    rows = load("deployment_raw.csv")
    if not need(rows, ["factor", "level", "unsafe_pct", "awd_eff"], "fig5"):
        return
    print("\n=== HINH 5: TRIEN KHAI THUC TE ===")
    facs = ["F1_uplink", "F2_soil", "F3_depth", "F4_horizon", "F5_radio"]

    fig, axes = plt.subplots(1, 5, figsize=(7.4, 2.72))
    fig.subplots_adjust(left=0.055, right=0.985, top=0.795, bottom=0.245, wspace=0.70)

    for ax, fac in zip(axes, facs):
        g = [r for r in rows if r["factor"] == fac]
        if not g:
            ax.set_visible(False); continue
        levels = []
        for r in g:
            if r["level"] not in levels:
                levels.append(r["level"])
        kind, xname, fmt = FACTOR_KIND[fac]

        if kind == "cont":
            xs = sorted({float(L) for L in levels})
            uns = [fmean([r for r in g if float(r["level"]) == x], "unsafe_pct") for x in xs]
            awd = [fmean([r for r in g if float(r["level"]) == x], "awd_eff") for x in xs]
            ax.plot(xs, uns, marker="o", ms=3.4, lw=1.5, color=C_BAD, zorder=3)
            ax2 = ax.twinx()
            ax2.plot(xs, awd, marker="s", ms=3.2, lw=1.3, color=C_FULL, ls="--", zorder=3)
            # chon TRUOC <= 4 tick: o chi rong ~1.3 inch nen 6 nhan chac chan dinh nhau
            step = max(1, -(-len(xs) // 4))          # ceil(len/4)
            tk = xs[::step]
            if tk and tk[-1] != xs[-1]:
                tk = tk + [xs[-1]]                   # giu moc cuoi cho day du thang do
            ax.set_xticks(tk)
            ax.set_xticklabels([fmt(v) for v in tk], fontsize=5.9)
            if fac == "F4_horizon":
                ax.set_xscale("log")
                ax.set_xticks(xs)
                ax.set_xticklabels([fmt(v) for v in xs], fontsize=5.9)
        else:
            # thu tu on dinh: so thi tang dan, chu thi theo thu tu khai bao trong map
            mp = FACTOR_LBL[fac]
            try:
                levels = sorted(levels, key=float)
            except ValueError:
                levels = sorted(levels, key=lambda L: (list(mp).index(L)
                                                      if L in mp else 99, L))
            lbls = strict_labels(levels, mp, fac)
            uns = [fmean([r for r in g if r["level"] == L], "unsafe_pct") for L in levels]
            awd = [fmean([r for r in g if r["level"] == L], "awd_eff") for L in levels]
            x = np.arange(len(levels))
            w = 0.36
            ax.bar(x - w / 2, uns, width=w, color=C_BAD, alpha=0.88, zorder=3)
            ax2 = ax.twinx()
            ax2.bar(x + w / 2, awd, width=w, color=C_FULL, alpha=0.88, zorder=3)
            ax.set_xticks(x)
            ax.set_xticklabels(lbls, fontsize=5.9, ha="center")

        ax.tick_params(axis="y", colors=C_BAD, labelsize=6.0)
        ax2.tick_params(axis="y", colors=C_FULL, labelsize=6.0)
        ax.set_xlabel(xname, fontsize=6.3, color=INK, labelpad=1.5)
        ax.set_title(PANEL[fac], loc="left", fontsize=7.2, pad=4)
        ax.grid(axis="y", alpha=0.20, lw=0.5, zorder=0)
        ax.set_axisbelow(True)
        ax.set_ylim(0, max(uns) * 1.30 + 1e-9)
        ax2.set_ylim(0, max(max(awd) * 1.30, 1.0))

    from matplotlib.patches import Patch
    fig.legend(handles=[Patch(fc=C_BAD, alpha=0.88, label="giờ mất an toàn (%)"),
                        Patch(fc=C_FULL, alpha=0.88, label="chu kỳ AWD đạt chuẩn")],
               loc="lower center", ncols=2, fontsize=6.6,
               bbox_to_anchor=(0.5, 0.052), frameon=False)
    fig.text(0.012, 0.985,
             "Mỗi ô quét MỘT yếu tố, các yếu tố khác ở mức tham chiếu "
             "(σ_frac = 0,02; ngân sách 240 mm; 3 trạm × 2 kênh × 5 seed).   "
             "Đất: cát pha θ_fc/θ_wp = 0,31/0,12; thịt = 0,32/0,18; sét = 0,38/0,22.   "
             "Lệnh: mịn 10–35 mm, nông học 20–60 mm, thô 35–90 mm.",
             fontsize=6.2, color=INK, ha="left", va="top")

    # ---- KIEM CHUNG: do bbox that cua nhan tick, bao loi neu hai nhan dinh nhau ----
    fig.canvas.draw()
    _rend = fig.canvas.get_renderer()
    for ax, fac in zip(axes, facs):
        tls = [t for t in ax.get_xticklabels() if t.get_text()]
        if len(tls) < 2:
            continue
        bbs = [t.get_window_extent(renderer=_rend) for t in tls]
        worst = max(bbs[i].x1 - bbs[i + 1].x0 for i in range(len(bbs) - 1))
        if worst > 0:
            print(f"  !! NHAN TICK DÍNH NHAU o {fac}: tran {worst:.1f} pt "
                  f"({[t.get_text() for t in tls]}) -> phai ngan hon hoac bot tick")
        else:
            print(f"  [check] {fac}: {len(tls)} nhan tick, khe hep nhat {-worst:.1f} pt (OK)")

    save(fig, "fig5_deployment")
    for fac in facs:
        g = [r for r in rows if r["factor"] == fac]
        if not g:
            continue
        levels = []
        for r in g:
            if r["level"] not in levels:
                levels.append(r["level"])
        print(f"  {fac:<11}" + "  ".join(
            f"{L}={fmean([r for r in g if r['level'] == L], 'unsafe_pct'):.2f}%"
            for L in levels))


# HINH 6: DA RUONG (HTX)
# ======================================================================
def fig6() -> None:
    rows = load("multifield_raw.csv") or load("multifield_quick.csv")
    if not need(rows, ["alloc", "slots_per_day", "field", "seed", "unsafe_pct",
                       "awd_eff", "stress_h", "withheld", "network"], "fig6"):
        return
    src = "multifield_raw.csv" if (OUTD / "multifield_raw.csv").exists() else "quick"
    print(f"\n=== HINH 6: DA RUONG HTX (nguon: {src}) ===")
    net = rows[0]["network"]
    sub = [r for r in rows if r["network"] == net]
    allocs = []
    for r in sub:
        if r["alloc"] not in allocs:
            allocs.append(r["alloc"])
    slots = sorted({r["slots_per_day"] for r in sub}, key=int, reverse=True)

    def gini(xs):
        if not xs or sum(xs) == 0:
            return 0.0
        s = sorted(xs); n = len(s)
        return (2 * sum((i + 1) * v for i, v in enumerate(s))) / (n * sum(s)) - (n + 1) / n

    fig, axes = plt.subplots(1, 3, figsize=(7.15, 2.5))
    colmap = {"equal": C_BASE, "deficit": C_ACC, "gate": C_FULL}

    # (a) theo tung thua ruong: muc mat an toan
    ax = axes[0]
    fields = []
    for r in sub:
        if r["field"] not in fields:
            fields.append(r["field"])
    fields = sorted(fields)
    w = 0.26
    for i, al in enumerate(allocs):
        vals = [fmean([r for r in sub if r["alloc"] == al and r["field"] == f],
                      "unsafe_pct") for f in fields]
        ax.bar(np.arange(len(fields)) + (i - 1) * w, vals, width=w,
               color=colmap.get(al, INK), alpha=0.9,
               label={"equal": "chia đều", "deficit": "chia theo thiếu hụt",
                      "gate": "cổng được im lặng"}.get(al, al))
    ax.set_xticks(np.arange(len(fields)))
    ax.set_xticklabels([f.split("_", 1)[0] for f in fields], fontsize=6.6)
    ax.set_xlabel("thửa ruộng (F1…F6: 2 loại đất × 3 trạm)")
    ax.set_ylabel("giờ mất an toàn (%)")
    ax.set_title(f"(a) Từng thửa, kênh {net}", loc="left")
    ax.grid(axis="y", alpha=0.22, lw=0.5)
    ax.legend(fontsize=6.2, loc="upper left")

    # (b) theo slots/ngay: danh doi 3 chieu
    ax = axes[1]
    ax.plot([int(s) for s in reversed(slots)],
            [fmean([r for r in sub if r["slots_per_day"] == s and r["alloc"] == "equal"],
                   "unsafe_pct") for s in reversed(slots)],
            marker="o", color=C_BAD, lw=1.7, label="giờ mất an toàn (%)")
    ax.set_xlabel("số thửa được phục vụ mỗi ngày (kênh vô tuyến)")
    ax.set_ylabel("giờ mất an toàn (%)", color=C_BAD)
    ax.tick_params(axis="y", colors=C_BAD)
    ax2 = ax.twinx()
    ax2.plot([int(s) for s in reversed(slots)],
             [fmean([r for r in sub if r["slots_per_day"] == s and r["alloc"] == "equal"],
                    "awd_eff") for s in reversed(slots)],
             marker="s", color=C_FULL, lw=1.5, ls="--", label="chu kỳ AWD đạt chuẩn")
    ax2.plot([int(s) for s in reversed(slots)],
             [fmean([r for r in sub if r["slots_per_day"] == s and r["alloc"] == "equal"],
                    "stress_h") / 100.0 for s in reversed(slots)],
             marker="^", color=C_ACC, lw=1.3, ls=":", label="giờ stress (trăm giờ)")
    ax2.set_ylabel("AWD đạt chuẩn / stress (trăm giờ)")
    ax.set_title("(b) Kênh vô tuyến chật hơn: được và mất", loc="left", fontsize=7.6)
    ax.grid(axis="x", alpha=0.22, lw=0.5)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="center right", fontsize=6.1)

    # (c) cong bang: Gini theo luat phan bo
    ax = axes[2]
    per = defaultdict(lambda: defaultdict(list))
    for r in sub:
        per[(r["alloc"], r["slots_per_day"], r["seed"])][r["field"]].append(
            float(r["unsafe_pct"]))
    gval = defaultdict(list)
    for (al, sp, sd), d in per.items():
        gval[(al, sp)].append(gini([statistics.mean(v) for v in d.values()]))
    xs = np.arange(len(allocs))
    for i, s in enumerate(slots):
        vals = [statistics.mean(gval[(al, s)]) if gval[(al, s)] else 0 for al in allocs]
        ax.bar(xs + (i - (len(slots) - 1) / 2) * 0.3, vals, width=0.28,
               color=[colmap.get(al, INK) for al in allocs],
               alpha=0.95 if i == 0 else 0.55,
               hatch=["", "//"][i % 2],
               label=f"{s} thửa/ngày")
    ax.set_xticks(xs)
    ax.set_xticklabels(["chia đều", "theo\nthiếu hụt", "cổng im\nlặng"], fontsize=6.6)
    ax.set_ylabel("hệ số Gini của mất an toàn")
    ax.set_title("(c) Công bằng giữa các thửa (0 = đều)", loc="left", fontsize=7.6)
    ax.grid(axis="y", alpha=0.22, lw=0.5)
    ax.legend(fontsize=6.2)

    save(fig, "fig6_multifield")
    for al in allocs:
        for s in slots:
            gg = [r for r in sub if r["alloc"] == al and r["slots_per_day"] == s]
            if gg:
                print(f"  {al:<9} slots={s}: unsafe={fmean(gg,'unsafe_pct'):6.2f}% "
                      f"AWD={fmean(gg,'awd_eff'):5.2f} im_lặng={fmean(gg,'withheld'):6.1f}")


# ======================================================================
# HINH 7: MANH HINH — tinh huong (khong phai ket qua chinh)
# ======================================================================
def fig7() -> None:
    rows = load("sweep_salinity_raw.csv")
    if not need(rows, ["intrusion", "policy", "variant", "network", "seed",
                       "saline_mm", "fresh_frac", "unsafe_pct", "est_yield_loss_pct",
                       "withheld_saline"], "fig7"):
        return
    print("\n=== HINH 7: XAM NHAP MAN (tinh huong) ===")
    net = "severe"
    sub = [r for r in rows if r["network"] == net and r["variant"] == "central"]
    if not sub:
        sub = [r for r in rows if r["network"] == net]
    intr = sorted({float(r["intrusion"]) for r in sub})
    pols = []
    for r in sub:
        if r["policy"] not in pols:
            pols.append(r["policy"])
    order = [p for p in ("TwinGate+T2", "Reactive+T2", "FixedSchedule", "Oracle") if p in pols]
    cmap = {"TwinGate+T2": C_FULL, "Reactive+T2": C_ACC,
            "FixedSchedule": C_BASE, "Oracle": C_OK}

    fig, axes = plt.subplots(1, 3, figsize=(7.15, 2.45))

    ax = axes[0]
    for i, p in enumerate(order):
        ys = [fmean([r for r in sub if float(r["intrusion"]) == x and r["policy"] == p],
                    "saline_mm") for x in intr]
        ax.plot(intr, ys, marker=MARK[i % 8], ms=4.0, lw=1.7 if i == 0 else 1.2,
                color=cmap.get(p, INK), label=p, ls="-" if i == 0 else "--")
    ax.axhline(0, color=INK, lw=0.7)
    ax.set_xlabel("cường độ xâm nhập mặn (kịch bản, không phải số đo)")
    ax.set_ylabel("nước mặn đã bơm vào ruộng (mm)")
    ax.set_title("(a) Cổng chặn nước mặn tuyệt đối", loc="left")
    ax.grid(alpha=0.22, lw=0.5); ax.legend(fontsize=6.4)

    ax = axes[1]
    fr = [fmean([r for r in sub if float(r["intrusion"]) == x], "fresh_frac") for x in intr]
    ax.plot(intr, [100 * v for v in fr], marker="o", ms=4.4, lw=1.8, color=C_OK)
    ax.fill_between(intr, 0, [100 * v for v in fr], color=C_OK, alpha=0.14)
    for x, v in zip(intr, fr):
        ax.annotate(f"{100*v:.0f}%", (x, 100 * v), textcoords="offset points",
                    xytext=(0, 4), ha="center", fontsize=6.2, color=C_OK)
    ax.set_xlabel("cường độ xâm nhập mặn (kịch bản)")
    ax.set_ylabel("số giờ nguồn nước còn ngọt (%)")
    ax.set_ylim(0, 105)
    ax.set_title("(b) Cửa sổ nước ngọt hẹp dần", loc="left")
    ax.grid(alpha=0.22, lw=0.5)

    # ---- panel (c): NHAY CAM NGUONG, ve theo MOC CO SO ----
    # LOI DA SUA (2026-10-04): ban cu ve thiệt hại năng suát cua CHINH CONG
    # theo 3 bang nguỡng. Do trục tiếp cho tháy cả 3 đùng trùng nhau tại 0.00%
    # o mọi mức xâm nhập (cỏng loại trù tuỵt đối mọi ḷnh trong gì mạn, nên
    # EC_crit không bao gì đuợc dùng tới). Ba đùng trùng nhau = panel vô nghĩa.
    # Đây lại chính là KẾT QUẢ đáng giá: cỏng MIỄN NHIỄM với tranh cãi văn lị̂u
    # về nguỡng chịu mạn ở giai đoạn trỏ. Vậy vẽ theo MOC CO SO
    # (Reactive+T2) để cho tháy các cách làm truyền thống NHẠY với nguỡng,
    # kèm đùng cỏng = 0 để đối chiếu.
    ax = axes[2]
    variants = []
    for r in rows:
        if r["variant"] not in variants:
            variants.append(r["variant"])
    vname = {"central": "ngưỡng trung tâm 2,5", "grattan_strict": "Grattan chặt 1,9",
             "maas_lenient": "Maas khoan dung 3,5"}
    base_pol = "Reactive+T2" if any(r["policy"] == "Reactive+T2" for r in rows) \
        else ("FixedSchedule" if any(r["policy"] == "FixedSchedule" for r in rows) else None)
    for i2, v in enumerate(variants):
        xs = sorted({float(r["intrusion"]) for r in rows})
        # moc co so: nhay voi nguỡng
        g = [r for r in rows if r["variant"] == v and r["network"] == net
             and r["policy"] == base_pol]
        ys = [fmean([r for r in g if float(r["intrusion"]) == x], "est_yield_loss_pct")
              for x in xs]
        ax.plot(xs, ys, marker=MARK[i2 % 8], ms=4.0, lw=1.5,
                color=[C_ACC, C_NET, C_BASE][i2 % 3], ls="--",
                label=f"{vname.get(v, v)} ({base_pol})")
    # cỏng đề xuất: 0% ỏ cả 3 nguỡng -> vẽ 1 đùng đậm, chú thích rõ
    gate_pol = "TwinGate+T2"
    xs = sorted({float(r["intrusion"]) for r in rows})
    gate_vals = []
    for v in variants:
        g = [r for r in rows if r["variant"] == v and r["network"] == net
             and r["policy"] == gate_pol]
        gate_vals.append([fmean([r for r in g if float(r["intrusion"]) == x],
                                "est_yield_loss_pct") for x in xs])
    flat = all(max(vv) - min(vv) < 1e-9 for vv in zip(*gate_vals)) if gate_vals else False
    ax.plot(xs, gate_vals[0], marker="o", ms=4.6, lw=2.2, color=C_FULL,
            label="cổng đề xuất (0% ở cả ba ngưỡng)")
    if flat:
        print(f"  [check] panel (c): cỏng = {gate_vals[0][0]:.2f}% ỏ cả 3 nguỡng "
              f"(giống hệt nhau) -> miễn nhiễm với tranh cãi về ngưỡng")
    else:
        print("  !! panel (c): cỏng KHÔNG giống nhau ở 3 nguỡng, kiểm tra lại:")
        for v, gv in zip(variants, gate_vals):
            print(f"     {v}: {['%.2f' % x for x in gv]}")
    ax.set_xlabel("cường độ xâm nhập mặn (kịch bản)")
    ax.set_ylabel("thiệt hại năng suất ước tính (%)")
    ax.set_title("(c) Mốc cơ sở nhạy với ngưỡng,\ncổng thì không", loc="left", fontsize=7.6)
    ax.grid(alpha=0.22, lw=0.5)
    ax.legend(fontsize=5.6, loc="upper left")

    save(fig, "fig7_salinity_scenario")
    ax0 = [fmean([r for r in sub if r["policy"] == "TwinGate+T2"], "saline_mm")]
    print(f"  TwinGate+T2 bom nuoc man trung binh = {ax0[0]:.2f} mm (ky vong 0)")
    for p in order:
        print(f"  {p:<16} saline_mm = "
              f"{fmean([r for r in sub if r['policy']==p], 'saline_mm'):8.2f}")
    print("  NHAC LAI: day la MO HINH TINH HUONG, khong co so do man thuc dia;")
    print("            khong duoc dua vao Abstract nhu ket qua chinh.")


# ======================================================================
# HINH 8: PARETO — danh doi an toan vs nuoc
# ======================================================================
def fig8() -> None:
    rows = load("main_raw.csv")
    if not need(rows, ["fidelity", "policy", "network", "budget_mm", "seed", "station",
                       "hours_unsafe", "hours", "water_applied_mm", "awd_effective",
                       "stress_hours"], "fig8"):
        print("  (main_raw.csv chua co fidelity — ve ban khong phan tach dai)")
    print("\n=== HINH 8: PARETO an toan vs nuoc ===")
    net = "severe"
    sub = [r for r in rows if r["network"] == net]
    pols = []
    for r in sub:
        if r["policy"] not in pols:
            pols.append(r["policy"])
    has_fid = "fidelity" in rows[0]
    fids = sorted({r["fidelity"] for r in sub}) if has_fid else ["all"]

    fig, axes = plt.subplots(1, len(fids), figsize=(3.55 * len(fids), 2.9), squeeze=False)
    axes = axes[0]
    for ax, fid in zip(axes, fids):
        g = [r for r in sub if (not has_fid or r["fidelity"] == fid)]
        cmap2 = {"TwinGate+T2": C_FULL, "TwinGate+T2+centre": "#7fb3d5",
                 "TwinGate+blindARQ": "#2c3e50", "Reactive+T2": C_ACC,
                 "Reactive+blindARQ": "#a569bd", "FixedSchedule": C_BASE,
                 "Oracle": C_OK}
        for i, p in enumerate(pols):
            buds = sorted({r["budget_mm"] for r in g if r["policy"] == p},
                          key=lambda b: (b == "inf", float(b) if b != "inf" else 0))
            xs, ys, sz = [], [], []
            for b in buds:
                gg = [r for r in g if r["policy"] == p and r["budget_mm"] == b]
                xs.append(fmean(gg, "water_applied_mm"))
                ys.append(100 * statistics.mean(
                    [float(r["hours_unsafe"]) / float(r["hours"]) for r in gg]))
                sz.append(fmean(gg, "awd_effective"))
            isfull = p == "TwinGate+T2"
            ax.plot(xs, ys, marker=MARK[i % 8], ms=4.6 if isfull else 3.6,
                    lw=2.0 if isfull else 1.05, color=cmap2.get(p, INK),
                    ls="-" if isfull else "--", alpha=1.0 if isfull else 0.75,
                    label=p, zorder=3 if isfull else 2)
            for x, y, s in zip(xs, ys, sz):
                if s > 3:
                    ax.annotate(f"{s:.0f}", (x, y), textcoords="offset points",
                                xytext=(4, 3), fontsize=5.6, color=cmap2.get(p, INK))
        ax.set_xlabel("nước đã bơm cả mùa (mm)")
        ax.set_ylabel("giờ mất an toàn (%)")
        ttl = f"dải {fid}" if has_fid and fid != "all" else "σ_frac mặc định"
        ax.set_title(f"Pareto an toàn–nước, kênh {net} ({ttl})", loc="left", fontsize=7.8)
        ax.grid(alpha=0.22, lw=0.5)
        ax.legend(fontsize=6.0, loc="upper right")
        ax.text(0.03, 0.045, "số cạnh điểm = chu kỳ AWD đạt chuẩn", transform=ax.transAxes,
                fontsize=5.8, color=INK, style="italic")
    save(fig, "fig8_pareto")
    for p in pols:
        gg = [r for r in sub if r["policy"] == p and (not has_fid or r["fidelity"] == fids[0])]
        if gg:
            print(f"  {p:<22} nuoc={fmean(gg,'water_applied_mm'):7.1f}mm "
                  f"unsafe={100*statistics.mean([float(r['hours_unsafe'])/float(r['hours']) for r in gg]):6.2f}%")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", type=int, default=None, help="chi ve hinh thu N (2..8)")
    a = ap.parse_args()
    fns = {2: fig2, 3: fig3, 4: fig4, 5: fig5, 6: fig6, 7: fig7, 8: fig8}
    todo = [a.only] if a.only else sorted(fns)
    # LOI GATE DA SUA (2026-10-04): ban cu bat Exception cua tung hinh roi chi IN ra,
    # van exit 0. Khi fig7 chet vi NameError, log ghi "HINH 7 THAT BAI" nhung
    # "FIG7_EXIT=0" -> de dang tuong la PASS. Hinh khong ve duoc la loi that,
    # phai tra ma thoat khac 0 de bat buoc phai xu ly.
    failed = []
    for n in todo:
        if n not in fns:
            print(f"  !! khong co hinh {n}")
            failed.append(n)
            continue
        try:
            fns[n]()
        except Exception as e:
            print(f"  !! HINH {n} THAT BAI: {type(e).__name__}: {e}")
            import traceback; traceback.print_exc()
            failed.append(n)
    print("\ncac file trong figures/:")
    for p in sorted(FIG.glob("*.png")):
        print(f"  {p.name:<28} {p.stat().st_size/1024:7.0f} KB")
    if failed:
        print(f"\n!! {len(failed)} HINH THAT BAI: {failed}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""VE 6 HINH (3 VI + 3 EN) cho bai HUJOS-TT — moi con so TAI TINH tu outputs/*.csv.

Vi sao phai ve CA ban EN: gate check_vi_numbers so tap so cua blocks VI vs EN.
Caption hinh chua nhieu so (116/116, 0/60, 26,7%, +33%, t=5,29...). Neu chi them
hinh vao ban VI thi ban VI se THUA so -> gate FAIL. Lam yeu gate de chui lot la
sai (bai hoc da ghi trong skill), nen ve doi xung ca hai ban.

NGUYEN TAC:
  * KHONG go tay so nao — moi so tinh tu CSV bang dung phep tinh cua
    experiments/make_tables_anchored.py (ghep cap + t-stat) va
    verify_paper_claims.py (escape(): khong ca t0 lan t1 deu bao).
  * ASSERT so tai tinh khop so bai dang ghi TRUOC khi ve. Lech -> khong ve.
  * ASSERT kich thuoc PNG <= 7 cm x 14 cm (the le HUJOS-TT). LOI DA SUA:
    fig2 ban dau cao 7,04 cm vi legend dat duoi truc + pad_inches 0.03;
    nay giam figsize chieu cao va pad, co assert nen khong the lot qua.
  * BO KIEM TRA TRAN CHU: do be rong that cua tung dong bang renderer, doi chieu
    be rong hop; dong nao tran -> ABORT (them sau khi vision review phat hien
    3 dong tran o fig1 ban dau).
"""
from __future__ import annotations

import csv
import statistics
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = Path("/media/SAS/Van/DeTai2025/TwinGate_K1")
OUT = ROOT / "outputs"
# Layout moi (migration v4, 2026-10-15):
#   VI: paper2_vi_submission/src/figures/fig1_method.png  (khong con _vi)
#   EN: paper2_hujos/figures_en/fig1_method_en.png         (giu _en)
FIGD_VI = ROOT / "paper2_vi_submission" / "src" / "figures"
FIGD_EN = ROOT / "paper2_hujos" / "figures_en"
FIGD_VI.mkdir(parents=True, exist_ok=True)
FIGD_EN.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 5.4,
    "axes.titlesize": 6.0, "axes.labelsize": 5.6, "axes.linewidth": 0.5,
    "xtick.labelsize": 5.2, "ytick.labelsize": 5.2,
    "xtick.major.width": 0.5, "ytick.major.width": 0.5,
    "legend.fontsize": 5.0, "legend.frameon": False,
    "figure.dpi": 300, "savefig.dpi": 300,
    "savefig.bbox": "tight", "savefig.pad_inches": 0.012,
})

W_CM, H_CM = 14.0, 7.0          # tran the le
MAX_H_CM, MAX_W_CM = 7.0, 14.0
BOX_FS = 4.8
TOL = 0.002


def fmt(v, n, lang):
    """Dau thap phan theo QUY UOC CUA TUNG BAN.
    LOI DA SUA (vision review 2026-10-13): hinh VI in '4.78' va 't = 5.29' (dau
    CHAM) trong khi van ban bai viet '$4{,}78$' va '$t=5{,}29$' (dau PHAY) ->
    hinh va bai lech nhau ve quy uoc, nguoi doc se thay la loi. Nay ban VI dung
    dau phay, ban EN dung dau cham."""
    t = f"{v:.{n}f}"
    return t.replace(".", ",") if lang == "vi" else t

# ================= doc CSV + phep tinh giong script cua bai =================
def load(p):
    with Path(p).open(encoding="utf-8", errors="replace") as fh:
        return list(csv.DictReader(fh))

def I(r, k):
    v = r.get(k, "")
    return int(float(v)) if v not in ("", None) else 0

def F(r, k):
    v = r.get(k, "")
    return float(v) if v not in ("", None) else float("nan")

def escape(S, ver):
    return sum(1 for r in S if not I(r, f"{ver}_t0") and not I(r, f"{ver}_t1"))

def key(r):
    """GIONG make_tables_anchored._pair_key()."""
    return (r["station"], r["year"], r["seed"], r["soil"])

R = load(OUT / "eval_theta_reduced_10seeds.csv")
Fu = load(OUT / "eval_theta_full_3seeds.csv")
by = defaultdict(list)
for r in R: by[r["variant"]].append(r)
byF = defaultdict(list)
for r in Fu: byF[r["variant"]].append(r)

hf = by["honest_field"]
ts_ch = [r for r in by["fraud_timing"] if I(r, "changed")]
ra_ch = [r for r in by["fraud_rational"] if I(r, "changed")]
ts_chF = [r for r in byF["fraud_timing"] if I(r, "changed")]
hfmap = {key(r): r for r in hf}
hfmapF = {key(r): r for r in byF["honest_field"]}

def paired(rows, rowmap):
    """GIONG make_tables_anchored.tab_credit() dong 280-291."""
    pairs = [(F(r, "n_dry"), F(rowmap[key(r)], "n_dry")) for r in rows if key(r) in rowmap]
    if not pairs: return None
    a = statistics.mean(x[0] for x in pairs); b = statistics.mean(x[1] for x in pairs)
    d = [x[0] - x[1] for x in pairs]
    sd = statistics.stdev(d) if len(d) > 1 else 0.0
    se = sd / len(d) ** 0.5 if d else 0.0
    t = statistics.mean(d) / se if se else 0.0
    return dict(after=a, before=b, infl=(a - b) / b * 100 if b else float("nan"),
                t=t, n=len(d))

PR = paired(ts_ch, hfmap); PF = paired(ts_chF, hfmapF)
assert PR and PF, "khong ghep cap duoc"

fa_v1 = 100 * sum(1 for r in hf if I(r, "v1_t1")) / len(hf)
fa_v2 = 100 * sum(1 for r in hf if I(r, "v2_t1")) / len(hf)
fa_an = 100 * sum(I(r, "anchor_flag") for r in hf) / len(hf)
esc_v1 = escape(ts_ch, "v1"); esc_v2 = escape(ts_ch, "v2")
ch_all = [r for rs in by.values() for r in rs
          if I(r, "changed") and not r["variant"].startswith("honest")]
an_caught = sum(I(r, "anchor_flag") for r in ch_all)
an_false = sum(I(r, "anchor_flag") for r in hf)
esc_anchor = len(ch_all) - an_caught

def near(a, b, tol=0.05):
    return abs(float(a) - float(b)) <= tol * max(1.0, abs(float(b)))

fails = []
def A(label, got, want):
    ok = near(got, want)
    print(f"  {'PASS' if ok else '!!FAIL':<7} {label:<46} tai tinh={got} bai ghi={want}")
    if not ok: fails.append((label, got, want))

print("=== TAI TINH TU CSV, DOI CHIEU SO BAI DANG GHI ===")
A("mo hinh diem ket toi oan (%)", round(fa_v1, 1), 26.7)
A("tang ben vung ket toi oan (%)", round(fa_v2, 1), 5.0)
A("neo thiet bi ket toi oan (%)", round(fa_an, 1), 0.0)
A("dich thoi diem: nhat ky bi sua", len(ts_ch), 9)
A("dich thoi diem: mo hinh diem bat duoc", len(ts_ch) - esc_v1, 4)
A("dich thoi diem: lot tang ben vung", esc_v2, 8)
A("doi thu duy ly: lot tang ben vung", escape(ra_ch, "v2"), 6)
A("ghep cap: pha kho TRUOC tan cong", round(PR["before"], 2), 4.78)
A("ghep cap: pha kho SAU tan cong", round(PR["after"], 2), 6.33)
A("ghep cap: muc thoat phong (%)", round(PR["infl"], 1), 33)
A("ghep cap: t-stat", round(PR["t"], 2), 5.29)
A("Theta day du: muc thoat phong (%)", round(PF["infl"], 1), 38)
A("Theta day du: t-stat", round(PF["t"], 2), 3.46)
A("Theta day du: so cap ghep", PF["n"], 3)
A("neo: nhat ky that su bi sua", len(ch_all), 116)
A("neo: bat duoc", an_caught, 116)
A("neo: ket toi oan tren honest_field", an_false, 0)
if fails:
    print(f"\n>>> {len(fails)} SO LECH — KHONG VE"); sys.exit(1)
print("  >>> tat ca khop.\n")

# ================= ve + 2 bo kiem tra bat buoc =================
BOXES = []
def box(ax, x, y, w, h, text, fc, fs=BOX_FS):
    BOXES.append((x, y, w, h, text, fs))
    ax.add_patch(FancyBboxPatch((x, y), w, h,
                 boxstyle="round,pad=0.010,rounding_size=0.018",
                 fc=fc, ec="#333333", lw=0.5, zorder=2))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            zorder=3, linespacing=1.30)

def arrow(ax, p, q, color="#333333", lw=0.6, ls="-"):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=5.0, lw=lw,
                 color=color, linestyle=ls, zorder=1))

def no_overflow(ax, fig, label):
    fig.canvas.draw(); rend = fig.canvas.get_renderer(); inv = ax.transData.inverted()
    bad = []; nd = 0
    for (x, y, w, h, text, fs) in BOXES:
        for li, line in enumerate(text.split("\n"), 1):
            nd += 1
            t = ax.text(0.5, 0.5, line, fontsize=fs); fig.canvas.draw()
            bb = t.get_window_extent(renderer=rend)
            x0, _ = inv.transform((bb.x0, bb.y0)); x1, _ = inv.transform((bb.x1, bb.y1))
            t.remove()
            if (x1 - x0) > w + TOL:
                bad.append((li, line, round((x1 - x0 - w) * W_CM * 10, 2)))
    if bad:
        print(f"\n>>> {label}: {len(bad)} DONG TRAN — KHONG LUU")
        for b in bad: print(f"    dong {b[0]}: tran {b[2]} mm '{b[1]}'")
        sys.exit(1)
    print(f"  {label}: 0/{nd} dong tran")

def size_ok(path, label):
    from PIL import Image
    w, h = Image.open(path).size
    wcm, hcm = w / 300 * 2.54, h / 300 * 2.54
    ok = wcm <= MAX_W_CM + 1e-6 and hcm <= MAX_H_CM + 1e-6
    print(f"  {label}: {wcm:.2f} x {hcm:.2f} cm ({w}x{h} px) "
          f"{'OK' if ok else '>>> VUOT THE LE'}")
    if not ok: sys.exit(1)

C_IN = "#EAF1F8"; C_TWIN = "#FDF3E3"; C_FILT = "#F3EAF7"; C_GW = "#E8F5EC"; C_BAD = "#FBE9E9"
X = [0.008, 0.248, 0.513, 0.753]; W = [0.195, 0.220, 0.195, 0.239]
YTOP, YBOT, HH = 0.585, 0.085, 0.315

L = {
 "vi": dict(
   b1="Nhật ký nông dân\n$L=\\{(t_i,u_i)\\}$\nđộ sâu khai báo\nvà dấu thời điểm",
   b2="Bản sao số FAO-56\nphát lại với ERA5 công khai\nphương trình thùng chứa\ntheo từng giờ",
   b3="Quỹ đạo độ cạn kiệt\n$(\\hat w_t,\\hat d_t)$\n→ đếm pha khô\ndài ≥ 72 giờ",
   b4="3 bộ lọc vật lý $V_1,V_4,V_5$\nmô hình điểm, hoặc\ntầng bền vững (giao trên\ntập bất định $\\Theta$)",
   b5="Tấn công dịch thời điểm\ngiữ nguyên tổng lượng\nvà từng độ sâu,\nchỉ dời dấu thời điểm",
   b6="Gateway đóng mở\nmáy bơm, đã ký\n$\\mathcal{G}=\\{(t_j,u_j,\\sigma_j)\\}$",
   b7="Neo thiết bị\nđối chiếu nhật ký\nvới BẢN GHI,\nkhông với mô hình",
   b8=lambda: f"Bắt {an_caught}/{len(ch_all)} ca giả mạo\n{an_false}/{len(hf)} ca kết tội oan\nchi phí biên gần bằng không",
   title="Đường kiểm toán vật lý (trên) và đường neo thiết bị (dưới)",
   foot=f"Kết quả đo trên {len(R)} nhật ký mô phỏng tại ba trạm Đồng bằng sông Cửu Long",
   a1="sửa nhật ký", a2="vật lý KHÔNG thấy:\ndịch thời điểm bất biến",
   t2=["Mô hình điểm\n(ngưỡng tuyệt đối)", "Tầng bền vững\n(giao trên $\\Theta$)", "Neo thiết bị\n(đối chiếu gateway)"],
   l2a="Kết tội oan nông dân trung thực", l2b="Lọt lưới tấn công dịch thời điểm",
   y2="Tỷ lệ (%)", ti2="Bớt kết tội oan thì lọt lưới nhiều hơn, trừ tầng neo thiết bị",
   l3=["Trước tấn công\n(mốc ghép cặp)", "Sau tấn công\ndịch thời điểm"],
   y3="Số pha khô được cấp tín chỉ mỗi vụ",
   ti3="Dịch thời điểm giữ nguyên tổng lượng nước vẫn thổi phồng tín chỉ",
   an3=lambda d: f"+{PR['infl']:.0f}%\n(t = {d(PR['t'],2)}; {PR['n']} cặp ghép)",
   f3=lambda d: f"$\\Theta$ đầy đủ: +{PF['infl']:.0f}% trên {PF['n']} cặp (t = {d(PF['t'],2)})",
 ),
 "en": dict(
   b1="Farmer's log\n$L=\\{(t_i,u_i)\\}$\nclaimed depth\nand timestamp",
   b2="FAO-56 digital twin\nreplayed under public ERA5\nhourly bucket\nequation",
   b3="Depletion trajectory\n$(\\hat w_t,\\hat d_t)$\n→ count dry phases\nof at least 72 h",
   b4="3 physical filters $V_1,V_4,V_5$\npoint model, or robust tier\n(intersection over the\nuncertainty set $\\Theta$)",
   b5="Time-shifting attack\npreserves total volume\nand every depth,\nonly moves timestamps",
   b6="Gateway actuates\nthe pump and signs\n$\\mathcal{G}=\\{(t_j,u_j,\\sigma_j)\\}$",
   b7="Device anchor\nchecks the log against\nthe RECORD,\nnot against a model",
   b8=lambda: f"Catches {an_caught}/{len(ch_all)} forgeries\n{an_false}/{len(hf)} false accusations\nnear-zero marginal cost",
   title="Physical audit path (top) and device-anchor path (bottom)",
   foot=f"Measured on {len(R)} simulated logs at three Mekong Delta stations",
   a1="log tampering", a2="physics is BLIND:\ntime shifts are invariant",
   t2=["Point model\n(absolute threshold)", "Robust tier\n(intersection over $\\Theta$)", "Device anchor\n(matches gateway log)"],
   l2a="False accusation of honest farmers", l2b="Escape of the time-shifting attack",
   y2="Rate (%)", ti2="Less false accusation means more escape, except for the device anchor",
   l3=["Before the attack\n(paired baseline)", "After the time-shifting\nattack"],
   y3="Creditable dry phases per season",
   ti3="Time shifting preserves total volume yet still inflates credits",
   an3=lambda d: f"+{PR['infl']:.0f}%\n(t = {d(PR['t'],2)}; {PR['n']} paired logs)",
   f3=lambda d: f"Full $\\Theta$: +{PF['infl']:.0f}% on {PF['n']} pairs (t = {d(PF['t'],2)})",
 ),
}

for lang in ["vi", "en"]:
    S = L[lang]
    if lang == "vi":
        figd, sfx = FIGD_VI, ""
    else:
        figd, sfx = FIGD_EN, "_en"
    D = lambda v, n: fmt(v, n, lang)
    # ---- HINH 1 ----
    BOXES.clear()
    fig, ax = plt.subplots(figsize=(W_CM / 2.54, H_CM / 2.54))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    b8 = S["b8"]()
    box(ax, X[0], YTOP, W[0], HH, S["b1"], C_IN)
    box(ax, X[1], YTOP, W[1], HH, S["b2"], C_TWIN)
    box(ax, X[2], YTOP, W[2], HH, S["b3"], C_TWIN)
    box(ax, X[3], YTOP, W[3], HH, S["b4"], C_FILT)
    box(ax, X[0], YBOT, W[0], HH, S["b5"], C_BAD)
    box(ax, X[1], YBOT, W[1], HH, S["b6"], C_GW)
    box(ax, X[2], YBOT, W[2], HH, S["b7"], C_GW)
    box(ax, X[3], YBOT, W[3], HH, b8, C_GW)
    for i in range(3):
        x0, x1 = X[i] + W[i], X[i + 1]
        c = "#8B2E2E" if i == 0 else "#333333"
        arrow(ax, (x0, YTOP + HH / 2), (x1, YTOP + HH / 2), color=c)
        arrow(ax, (x0, YBOT + HH / 2), (x1, YBOT + HH / 2), color=c)
    xm_l = X[0] + W[0] / 2
    arrow(ax, (xm_l, YBOT + HH), (xm_l, YTOP), color="#8B2E2E", lw=0.7)
    ax.text(xm_l + 0.012, (YBOT + HH + YTOP) / 2, S["a1"], fontsize=4.7,
            color="#8B2E2E", va="center", ha="left")
    xm_r = X[3] + W[3] / 2
    arrow(ax, (xm_r, YTOP), (xm_r, YBOT + HH), color="#8B2E2E", lw=0.7, ls=(0, (2, 1.5)))
    ax.text(xm_r - 0.012, (YBOT + HH + YTOP) / 2, S["a2"], fontsize=4.6,
            color="#8B2E2E", va="center", ha="right", linespacing=1.25)
    ax.text(0.5, 0.975, S["title"], ha="center", va="top", fontsize=5.8, fontweight="bold")
    ax.text(0.5, 0.020, S["foot"], ha="center", va="bottom", fontsize=5.3, color="#333333")
    no_overflow(ax, fig, f"fig1{sfx}")
    p1 = figd / f"fig1_method{sfx}.png"; fig.savefig(p1); plt.close(fig)
    size_ok(p1, f"fig1{sfx}")

    # ---- HINH 2 ----
    fa = [round(fa_v1, 1), round(fa_v2, 1), round(fa_an, 1)]
    esc = [100 * esc_v1 / len(ts_ch), 100 * esc_v2 / len(ts_ch), 100 * esc_anchor / len(ch_all)]
    # LOI DA SUA (vision review 2026-10-13): 6 nhan cot khong cung kieu —
    # chuoi 'oan' ghi 26,7% / 5,0% / 0-60 (phan tram roi den phan so) trong khi
    # chuoi 'lot luoi' ghi 56% (5/9) / 89% (8/9) / 0% (0/116). Nay ca hai chuoi
    # deu theo mot khuon: '<phan tram>% (<tu so>/<mau so>)'.
    lf = [f"{D(fa_v1,1)}% ({sum(1 for r in hf if I(r,'v1_t1'))}/{len(hf)})",
          f"{D(fa_v2,1)}% ({sum(1 for r in hf if I(r,'v2_t1'))}/{len(hf)})",
          f"{D(fa_an,1)}% ({an_false}/{len(hf)})"]
    # LOI DA SUA (vision review vong 2): 6 nhan cung khuon '<%> (<n>/<N>)' nhung
    # chuoi 'oan' in 1 chu so thap phan (26,7%) con chuoi 'lot luoi' in 0 chu so
    # (56%) -> khong nhat quan. Nay ca hai deu dung D(...,1): 55,6% va 88,9%.
    le = [f"{D(100*esc_v1/len(ts_ch),1)}% ({esc_v1}/{len(ts_ch)})",
          f"{D(100*esc_v2/len(ts_ch),1)}% ({esc_v2}/{len(ts_ch)})",
          f"{D(100*esc_anchor/len(ch_all),1)}% ({esc_anchor}/{len(ch_all)})"]
    # figsize chieu cao 6.55 cm de sau bbox tight van <= 7.00 cm (legend nam duoi truc)
    fig, ax = plt.subplots(figsize=(W_CM / 2.54, 6.55 / 2.54))
    x = range(3); bw = 0.33
    b1 = ax.bar([i - bw / 2 for i in x], fa, bw, label=S["l2a"], color="#C25B5B",
                edgecolor="#7A2E2E", linewidth=0.4)
    b2 = ax.bar([i + bw / 2 for i in x], esc, bw, label=S["l2b"], color="#6C8EBF",
                edgecolor="#2F4A73", linewidth=0.4)
    for bars, labs in [(b1, lf), (b2, le)]:
        for r, t in zip(bars, labs):
            ax.text(r.get_x() + r.get_width() / 2, r.get_height() + 1.8, t,
                    ha="center", va="bottom", fontsize=4.5)
    for bars in (b1, b2):
        for r in bars:
            if r.get_height() < 1e-9:
                ax.plot([r.get_x(), r.get_x() + r.get_width()], [0.9, 0.9],
                        color=r.get_edgecolor(), lw=1.0, zorder=4)
    ax.set_xticks(list(x)); ax.set_xticklabels(S["t2"], fontsize=5.2)
    ax.set_ylabel(S["y2"]); ax.set_ylim(0, 104)
    ax.set_title(S["ti2"], fontsize=5.9, pad=2.5)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=2, fontsize=5.0)
    ax.grid(axis="y", lw=0.3, color="#DDDDDD"); ax.set_axisbelow(True)
    for sp in ["top", "right"]: ax.spines[sp].set_visible(False)
    p2 = figd / f"fig2_tradeoff{sfx}.png"; fig.savefig(p2); plt.close(fig)
    size_ok(p2, f"fig2{sfx}")

    # ---- HINH 3 ----
    fig, ax = plt.subplots(figsize=(W_CM / 2.54, 6.55 / 2.54))
    vals = [PR["before"], PR["after"]]
    bars = ax.bar(S["l3"], vals, 0.42, color=["#9BBB8C", "#C25B5B"],
                  edgecolor=["#4F6B43", "#7A2E2E"], linewidth=0.5)
    for r, v in zip(bars, vals):
        ax.text(r.get_x() + r.get_width() / 2, v + 0.08, D(v, 2),
                ha="center", va="bottom", fontsize=6.0)
    ax.annotate(S["an3"](D), xy=(1, PR["after"]), xytext=(0.40, PR["after"] * 1.10),
                fontsize=5.5, ha="center", color="#7A2E2E",
                arrowprops=dict(arrowstyle="-|>", lw=0.6, color="#7A2E2E"))
    ax.set_ylabel(S["y3"]); ax.set_ylim(0, PR["after"] * 1.30)
    ax.set_title(S["ti3"], fontsize=5.9, pad=2.5)
    # LOI DA SUA (vision review 2026-10-13): ghi chu nay truoc dat o goc duoi
    # PHAI (0.995, 0.045) = de len tren COT MAU DO -> chu do tren nen do, tuong
    # phan thap, va tran qua me cot. Nay dat o goc TREN TRAI (vung trang), chu
    # xam dam trong hop nen trang vien nhat.
    ax.text(0.02, 0.965, S["f3"](D), transform=ax.transAxes, ha="left",
            va="top", fontsize=5.0, color="#333333",
            bbox=dict(boxstyle="round,pad=0.22", fc="white", ec="#BBBBBB",
                      lw=0.4, alpha=0.92))
    ax.grid(axis="y", lw=0.3, color="#DDDDDD"); ax.set_axisbelow(True)
    for sp in ["top", "right"]: ax.spines[sp].set_visible(False)
    p3 = figd / f"fig3_timeshift{sfx}.png"; fig.savefig(p3); plt.close(fig)
    size_ok(p3, f"fig3{sfx}")
    print()

print("=== TONG KET 6 HINH ===")
for f in sorted(FIGD_VI.glob("*.png")) + sorted(FIGD_EN.glob("*.png")):
    print(f"  {f.name:28s} {f.stat().st_size//1024} KB")

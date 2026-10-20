#!/usr/bin/env python3
"""HINH 1 — SO DO PHUONG PHAP (thiet ke rieng, ban v11).

Lich su sua — moi lan deu DO (vision_fallback + renderer), khong sua theo cam tinh:
  v1: 4 cho chu chong lan.
  v2: van con 5 loi (nhan mui ten de len vien hop, chu tran vien).
  v3: van tran 4 hop. NGUYEN NHAN: uoc luong chieu cao chu bang `FIG_H*72` (chieu
      cao CA FIGURE) trong khi vung ve that chi la AXES (~77% figure) => lac quan
      ~1.3 lan.
  v4: bo uoc luong, do bbox that (`get_window_extent`) va tu noi hop -> ALL BOXES FIT.
  v5: sua loi THU TU (autofit chay sau khi ve mui ten). Van con 2 loi do vision bat:
      (a) nhan mui ten de len VIEN hop vi hanh lang chi 0.050-0.060 don vi
          (= 0.36-0.43 inch) trong khi nhan 6.6pt can ~0.5 inch;
      (b) kenhd_doc "nuoc vao ruong" dat tai x = 0.670 trung DUNG x cua nhan
          "rong" va "pi" -> duong xuyen qua chu.
  v6: het loi chu tran va nhan de len hop, nhung con dai trang lon o giua-duoi vi
      ①② chi cao 0.300 trong khi cot trai/phai cao ~0.495.
  v7: het tran chu, nhung con 2 loi vision bat duoc: nhan "dat 95%" sat vien tren-phai
      hop ② (vi cong offset +0.038 day nhan ra ngoai hanh lang), va day hop ①②
      trong 100-130px vi autofit chi biet NOI chu khong biet CO.
  v8: them shrink + margin test. Margin test bat duoc 4 nhan SAT hop — uoc luong
      "ky tu * 0.55 * fontsize" hoa ra SAI vi chu dam rong hon ~13% va bbox co pad.
  v9: het loi tran chu va nhan de len HOP, nhung vision con bat 2 loi: dau mui ten
      nhanh "dat 95%" de len cuoi nhan (verifier khong kiem nhan vs MUI TEN, chi kiem
      vs hop va vs duong thang), va dai trang ngang giua chu thich dau trang voi hang
      hop (hop ket thuc o y = 0.610 trong khi ghi chu o 0.708).
  v10: them kiem tra nhan vs mui ten. Verifier bat duoc ca 6 nhan — nhung nguyen nhan
      that la nhan duoc neo DUNG TAI y cua mui ten nen bbox cat nhau ~0.005 don vi doc.
  v11 (ban nay):
      * 4 cot voi HANH LANG 0.085 don vi (= 0.60 inch) — du cho nhan 11 ky tu o
        6.2pt (do: 11 * 0.55 * 6.2 = 37.5pt < 43pt = 0.60 inch);
      * duong "nuoc vao ruong" chay o KENH PHAI RIET (x = 0.968), khong dung chung
        hanh lang voi nhan nao — dong thoi lap day dai trang ben phai ma vision da
        bao la lang phi;
      * ①② keo xuong y = 0.105 (cao 0.495) cho bang chieu cao hai cot ben; noi dung
        them vao la that (σ = f·TAW·√Σρ²ᵏ, σ* = W/(2z) = 15,18 mm, luat chon lenh),
        khong phai chu dem;
      * π doi tu duong cong (cat vung giua-duoi, cham nhan) sang mui ten NGANG trong
        hanh lang;
      * tach cac dong > 20 ky tu trong hop ②③ (nhieu chu so RONG nhu 1,5,8,=,/) thanh
        dong ngan — autofit chi ha duoc font, khong tu tach dong, nen phai viet ngan;
      * autofit biet CO hop khi du cho (SHRINK_MIN/KEEP_PAD), giu nguyen day hop de
        cac cot van thang hang -> het khoang trang o day;
      * nhan mui ten dat DUNG giua hanh lang, bo moi offset +0.03 (chinh offset nay
        day nhan leo len vien hop);
      * kiem chung nhan doi MARGIN (LBL_MARGIN = 0.010) thay vi chi "khong giao nhau",
        vi hai bbox sat nhau < 1 pt thi mat thuong van doc la "cham";
      * hanh lang noi 0.085 -> 0.105 don vi (0.60 -> 0.745 inch) theo SO DO that cua
        nhan dam, va nhan dai nhat gioi han 8 ky tu (LBL_MAX) — GIU nguong margin
        0.010, khong ha chuan de test tu pass;
      * nang toan bo hop len +0.055 de lap dai trang giua ghi chu va hang hop;
      * nhan dat va="bottom" nam HOAN TOAN phia tren mui ten, khong de len duong;
      * verifier them kiem tra nhan vs MUI TEN (FancyArrowPatch co bbox that nen do
        duoc) - lap day dung lop loi ma v9 bo sot;
      * nang 6 nhan len LBL_LIFT tinh tu phep doi pt -> don vi du lieu
        (PT_PER_YUNIT = YLIM*FIG_H*72), khong dung so uoc luong;
      * verifier phan biet khe DOC (can >= LBL_MARGIN, loi that) voi khe NGANG (am la
        hien nhien vi nhan nam giua hanh lang ma mui ten di ngang qua duoi);
      * them KIEM CHUNG TU DONG: do bbox that cua MOI nhan va MOI doan duong, bao
        loi neu nhan cham hop hoac cham duong. Khong con phu thuoc mat thuong.

Moi thanh phan ung voi doi tuong that trong src/ (doi chieu khi review):
  twin FAO-56   -> water_balance.step_bucket       | tai neo -> ncs_loop (age=0)
  cong 95%      -> twin_gate.twin_gate/safe_bounds | T2      -> ncs_loop belief pi
  epoch cap 24h -> ncs_loop.slots_per_decision

Usage: python3 figures/fig_method.py     (exit 1 neu con loi trinh bay)
Output: figures/fig1_method.pdf + .png (300 dpi)
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "figures"
OUT.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 8.0,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.05,
})

INK = "#1a1a1a"
C_DATA = "#5a5a5a"
C_TWIN = "#1b6ca8"
C_GATE = "#6a3d9a"
C_SEND = "#2e7d32"
C_HOLD = "#c0392b"
C_NET = "#b9770e"
C_FIELD = "#4a7c59"
FILL = 0.10

FIG_W, FIG_H = 7.1, 5.15
YLIM = 0.74
PADX, PADY = 0.008, 0.010
FLOOR = 0.100          # day hop khong vuot xuong qua day (san nuoc o 0.030)
FLOOR_Y = 0.030        # duong "nuoc vao ruong" chay o day
CHANNEL_X = 0.970      # kenh phai rieng cho duong nuoc (khong chung voi nhan)
GAP = 0.006            # khe toi thieu giua 2 hop
SHRINK_MIN = 0.020     # chi co hop khi day trong it nhat chieu nay
KEEP_PAD = 0.010       # chieu cao giu lai sau khi co (le day)
LBL_MARGIN = 0.010     # nhan phai cach hop/duong it nhat chieu nay (khong chi "khong cham")

# LBL_LIFT: khoang nang nhan len phia tren mui ten ngang, TINH CHU KHONG UOC LUONG.
#   1 don vi y = YLIM * FIG_H inch = YLIM * FIG_H * 72 pt
#   mui ten rong nhat lw = 2.0 pt -> nua be rong 1.0 pt; bbox nhan co pad 1.0 pt
#   => can nang it nhat (1.0 + 1.0) / PT_PER_YUNIT + LBL_MARGIN
# Ban v10 neo nhan DUNG TAI y cua mui ten nen bbox nhan cat bbox mui ten khoang
# 0.005 don vi (verifier bat duoc ca 6 nhan). Khe NGANG am (-0.05 den -0.08) la
# hien nhien vi nhan nam giua hanh lang nen chac chan trung pham vi x cua mui ten;
# cai can xu ly la khe DOC.
PT_PER_YUNIT = YLIM * FIG_H * 72.0
LBL_LIFT = (2.0 + LBL_MARGIN * PT_PER_YUNIT) / PT_PER_YUNIT + 0.004

# 4 cot + 3 hanh lang.
# DO LAI O BAN v9: hanh lang 0.085 don vi (= 0.60 inch = 43 pt) KHONG du cho nhan
# dam 6.2 pt. Uoc luong cu "so ky tu * 0.55 * fontsize" sai vi bo sot (a) chu DAM
# rong hon ~13% va (b) bbox pad 1.0 pt moi ben. Do that: nhan "dat 95%" (7 ky tu)
# chiem 0.0726 don vi = 37 pt, nen khe hai ben chi con 0.0062 < LBL_MARGIN 0.010.
# Sua bang cach NOI hanh lang len 0.105 (0.745 inch = 54 pt) va bot be ngang hop;
# GIU NGUYEN nguong 0.010 — khong ha chuan de test tu pass.
C1X, C1W = 0.005, 0.132        # 0.005 .. 0.137
C2X, C2W = 0.242, 0.152        # 0.242 .. 0.394   (hanh lang 1: 0.137..0.242)
C3X, C3W = 0.499, 0.152        # 0.499 .. 0.651   (hanh lang 2: 0.394..0.499)
C4X, C4W = 0.756, 0.190        # 0.756 .. 0.946   (hanh lang 3: 0.651..0.756)
H1 = (C1X + C1W + C2X) / 2     # 0.1895
H2 = (C2X + C2W + C3X) / 2     # 0.4465
H3 = (C3X + C3W + C4X) / 2     # 0.7035
LBL_FS = 6.2
LBL_MAX = 8                    # so ky tu toi da cho nhan nam trong hanh lang


def make_box(ax, x, y, w, h, title, lines, ec, fsize=6.9, tsize=8.3):
    fill = FancyBboxPatch((x, y), w, h,
                          boxstyle="round,pad=0.008,rounding_size=0.016",
                          fc=ec, ec=ec, alpha=FILL, lw=1.4, zorder=2)
    edge = FancyBboxPatch((x, y), w, h,
                          boxstyle="round,pad=0.008,rounding_size=0.016",
                          fc="none", ec=ec, lw=1.4, zorder=3)
    ax.add_patch(fill); ax.add_patch(edge)
    t = ax.text(x + w / 2, y + h - 0.013, title, ha="center", va="top",
                fontsize=tsize, fontweight="bold", color=ec, zorder=4)
    b = ax.text(x + w / 2, y + h - 0.046, "\n".join(lines), ha="center", va="top",
                fontsize=fsize, color=INK, zorder=4, linespacing=1.45)
    return dict(tag=title, x=x, y=y, w=w, h=h, fill=fill, edge=edge,
                title=t, body=b, fsize=fsize, tsize=tsize)


def _reposition(b) -> None:
    for p in (b["fill"], b["edge"]):
        p.set_x(b["x"]); p.set_y(b["y"])
        p.set_width(b["w"]); p.set_height(b["h"])
    b["title"].set_position((b["x"] + b["w"] / 2, b["y"] + b["h"] - 0.013))
    b["body"].set_position((b["x"] + b["w"] / 2, b["y"] + b["h"] - 0.046))


def _bbox_data(ax, fig, tobj):
    fig.canvas.draw()
    bb = tobj.get_window_extent(renderer=fig.canvas.get_renderer())
    inv = ax.transData.inverted()
    (x0, y0) = inv.transform((bb.x0, bb.y0))
    (x1, y1) = inv.transform((bb.x1, bb.y1))
    return x0, y0, x1, y1


def measure(ax, fig, boxes) -> list[dict]:
    """Do bbox that cua chu so voi hinh chu nhat hop (don vi du lieu)."""
    fig.canvas.draw()
    rend = fig.canvas.get_renderer()
    inv = ax.transData.inverted()
    out = []
    for b in boxes:
        worst = dict(tag=b["tag"], left=0.0, right=0.0, top=0.0, bottom=0.0)
        for tobj in (b["title"], b["body"]):
            bb = tobj.get_window_extent(renderer=rend)
            (x0, y0) = inv.transform((bb.x0, bb.y0))
            (x1, y1) = inv.transform((bb.x1, bb.y1))
            worst["left"] = max(worst["left"], (b["x"] + PADX) - x0)
            worst["right"] = max(worst["right"], x1 - (b["x"] + b["w"] - PADX))
            worst["bottom"] = max(worst["bottom"], (b["y"] + PADY) - y0)
            worst["top"] = max(worst["top"], y1 - (b["y"] + b["h"] - PADY))
        out.append(worst)
    return out


def overlaps(boxes) -> list[tuple[str, str, float]]:
    bad = []
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            ox = min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"])
            oy = min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"])
            if ox > -GAP and oy > -GAP:
                bad.append((a["tag"], b["tag"], max(ox, oy)))
    return bad


def autofit(ax, fig, boxes, rounds: int = 12) -> bool:
    for k in range(rounds):
        over = measure(ax, fig, boxes)
        bad = [o for o in over
               if max(o["left"], o["right"], o["top"], o["bottom"]) > 1e-4]
        if not bad:
            print(f"  [autofit] ALL BOXES FIT sau {k} vong do")
            break
        for b, o in zip(boxes, over):
            need = o["bottom"] + o["top"]
            if need > 1e-4:
                b["y"] -= min(o["bottom"], max(0.0, b["y"] - FLOOR))
                b["h"] += need
            # ---- CO hop khi du cho (ban v7 chi biet noi -> day hop trong 100-130px) ----
            # `bottom` am nghia la chu nam cao hon day hop; `-bottom` = khoang du.
            # Co dung bang khoang du tru le an toan, giu NGUYEN day hop de cac cot
            # van thang hang o duoi. Chi co khi du >= SHRINK_MIN de tranh dao dong.
            spare = -o["bottom"]
            if spare >= SHRINK_MIN and o["top"] <= 1e-4:
                b["h"] -= (spare - KEEP_PAD)
            if o["left"] > 1e-4 or o["right"] > 1e-4:
                b["fsize"] = max(5.2, b["fsize"] - 0.35)
                b["body"].set_fontsize(b["fsize"])
                b["tsize"] = max(6.6, b["tsize"] - 0.25)
                b["title"].set_fontsize(b["tsize"])
            _reposition(b)
        print(f"  [autofit] vong {k+1}: con {len(bad)} hop tran "
              f"({', '.join(x['tag'][:12] for x in bad)}) -> da noi/giam chu")
    else:
        print("  !! autofit het so vong ma van chua xong")

    still = [o for o in measure(ax, fig, boxes)
             if max(o["left"], o["right"], o["top"], o["bottom"]) > 1e-4]
    for o in still:
        print(f"  !! VAN TRAN {o['tag']}: trai={o['left']:.4f} phai={o['right']:.4f} "
              f"tren={o['top']:.4f} duoi={o['bottom']:.4f}")
    ov = overlaps(boxes)
    for a, b, m in ov:
        print(f"  !! HOP DE LEN NHAU: {a[:16]} / {b[:16]} (muc {m:.4f})")
    return not still and not ov


def mid(b):
    return b["y"] + b["h"] / 2


def clamp_y(b, y):
    return min(max(y, b["y"] + 0.012), b["y"] + b["h"] - 0.012)


ARROWS: list = []


def arrow(ax, p, q, color, lw=1.6, ls="-", rad=0.0, ms=10, z=5, name=""):
    pa = FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=ms,
                         color=color, lw=lw, ls=ls,
                         connectionstyle=f"arc3,rad={rad}",
                         shrinkA=2, shrinkB=3, zorder=z)
    ax.add_patch(pa)
    # Ghi lai de verifier kiem va cham nhan <-> mui ten. LOI TRINH BAY DA SUA (v9):
    # verifier chi kiem nhan vs HOP va vs DUONG THANG, nen khong bat duoc dau mui
    # ten de len cuoi nhan "dat 95%" (vision phat hien). FancyArrowPatch co bbox
    # that nen do duoc, khong can uoc luong.
    ARROWS.append((pa, name or f"arrow({p[0]:.3f},{p[1]:.3f})"))
    return pa


def main() -> int:
    ARROWS.clear()
    fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
    ax.set_xlim(0, 1); ax.set_ylim(0, YLIM)
    ax.axis("off")

    # ================= 8 HOP =================
    wx = make_box(ax, C1X, 0.535, C1W, 0.105, "THỜI TIẾT",
                  ["ERA5, 3 trạm thật", "ET₀, mưa FAO-56"], C_DATA)
    sn = make_box(ax, C1X, 0.400, C1W, 0.105, "CẢM BIẾN",
                  ["độ ẩm đất θ", "mất gói 15–90%"], C_DATA)
    fl = make_box(ax, C1X, 0.160, C1W, 0.205, "RUỘNG LÚA",
                  ["bucket FAO-56", "", "an toàn:", "D ≤ 0,85", "W = 59,5 mm", "",
                   "chuẩn MRV:", "pha khô ≥ 72 h"], C_FIELD)
    # ①② keo xuong y = 0.105 (cao 0.495) de BANG chieu cao cot trai/phai.
    # Ban v6 de ①② cao 0.300 trong khi cot trai/phai cao ~0.495 -> sinh ra dai
    # trong lon o giua-duoi (vision bat duoc). Noi dung them vao la THAT, khong
    # phai chu dem: nguong sigma* va luat chon lenh — ca hai deu la dong gop cua bai.
    tw = make_box(ax, C2X, 0.160, C2W, 0.495, "① BẢN SAO SỐ",
                  ["mô hình ruộng", "chạy song song", "ruộng thật", "",
                   "mỗi độ sâu u", "rollout H = 6 ngày", "TRƯỚC khi gửi", "",
                   "→ μ(u) ± σ_H", "",
                   "σ = f·TAW·√Σρ²ᵏ", "ρ = 0,9 (hiệu chuẩn)", "",
                   "mất liên lạc", "→ σ phình; θ mới", "về → σ = 0"],
                  C_TWIN, fsize=6.7)
    gt = make_box(ax, C3X, 0.160, C3W, 0.495, "② CỔNG 95%",
                  ["duyệt từng độ sâu", "u ∈ {20, 40, 60}", "mm", "",
                   "chỉ gửi nếu", "P(0 ≤ D ≤ 0,85)", "≥ 95%", "",
                   "luật chọn lệnh:", "nước khan → 0,80", "nước dư → giữa", "",
                   "σ* = W/(2z)", "= 15,18 mm", "vượt σ* →", "cổng rỗng vĩnh viễn"],
                  C_GATE, fsize=6.7)
    sd = make_box(ax, C4X, 0.560, C4W, 0.105, "③a GỬI LỆNH",
                  ["kèm π = tin lệnh đã tới"], C_SEND, fsize=6.8)
    hd = make_box(ax, C4X, 0.415, C4W, 0.105, "③b IM LẶNG",
                  ["không lệnh nào đạt 95%"], C_HOLD, fsize=6.8)
    t2 = make_box(ax, C4X, 0.160, C4W, 0.205, "④ GỬI LẠI T2",
                  ["mất ACK → π giảm", "theo số lần thử", "",
                   "chỉ gửi lại khi π thấp", "→ chặn tưới đúp", "",
                   "−14,6 lần/ngày", "−18 mm lãng phí"],
                  C_NET, fsize=6.8)
    boxes = [wx, sn, fl, tw, gt, sd, hd, t2]

    # ghi chu epoch: 2 dong ngan de khong tran chieu rong canvas
    ax.text(C1X, 0.730,
            "Mỗi 24 giờ một quyết định (epoch cap) → kênh lệnh khan hiếm thật.",
            ha="left", va="top", fontsize=6.3, color=INK, style="italic")
    ax.text(C1X, 0.708,
            "Mô phỏng 2 160 giờ mùa khô (1/3–29/5), ERA5 thật, 10 seed × 3 trạm.",
            ha="left", va="top", fontsize=6.3, color=INK, style="italic")

    # ============ AUTOFIT TRUOC KHI VE MUI TEN (sua loi thu tu cua v4) ============
    ok_boxes = autofit(ax, fig, boxes)

    labels = []          # (text_obj, ten) de kiem tra va cham sau nay
    lines = []           # (x0,y0,x1,y1, ten) cac doan duong thang

    def add_label(x, y, s, color, fs=LBL_FS, maxlen=LBL_MAX):
        # `maxlen` mac dinh = LBL_MAX (nhan nam trong hanh lang hep). Nhan o vung
        # RONG (san day, khong co hop ben canh) duoc truyen maxlen lon hon — khong
        # the dung mot gioi han cho moi vi tri vi se bao dong gia.
        if len(s) > maxlen:
            print(f"  !! CANH BAO nhan {s!r} = {len(s)} ky tu > {maxlen} -> co the "
                  f"tran vung trong {H3 - (C3X + C3W):.3f}")
        # va="bottom" de nhan nam HOAN TOAN phia tren diem neo, khong de len mui ten.
        t = ax.text(x, y, s, ha="center", va="bottom", fontsize=fs, color=color,
                    fontweight="bold", zorder=7,
                    bbox=dict(fc="white", ec="none", pad=1.0, alpha=0.96))
        labels.append((t, s))
        return t

    def add_seg(x0, y0, x1, y1, color, lw=1.8, name=""):
        ax.add_line(Line2D([x0, x1], [y0, y1], color=color, lw=lw, zorder=1))
        lines.append((min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1),
                      name or f"seg({x0:.2f},{y0:.2f})"))

    # ---- (a) thoi tiet -> twin ; (b) cam bien -> twin ----
    y1 = mid(wx)
    arrow(ax, (C1X + C1W, y1), (C2X, clamp_y(tw, y1)), C_DATA)
    add_label(H1, y1 + LBL_LIFT, "dự báo", C_DATA)
    y2 = mid(sn)
    arrow(ax, (C1X + C1W, y2), (C2X, clamp_y(tw, y2)), C_DATA)
    add_label(H1, y2 + LBL_LIFT, "θ thật", C_DATA)

    # ---- (c) twin -> cong ----
    y3 = mid(tw)
    arrow(ax, (C2X + C2W, y3), (C3X, clamp_y(gt, y3)), C_TWIN, lw=2.0)
    add_label(H2, y3 + LBL_LIFT, "μ ± σ", C_TWIN)

    # ---- (d) cong -> gui lenh ; (e) cong -> im lang ----
    # nhan dat TAI GIUA hanh lang, khong day len/xuong: ban v7 cong them 0.038
    # nen nhan leo len tan vien tren-phai hop ② (vision bat duoc).
    y4 = mid(sd)
    y_src = clamp_y(gt, y4 + 0.02)
    arrow(ax, (C3X + C3W, y_src), (C4X, y4), C_SEND, lw=2.0)
    add_label(H3, (y_src + y4) / 2 + LBL_LIFT, "đạt 95%", C_SEND)
    y5 = mid(hd)
    arrow(ax, (C3X + C3W, clamp_y(gt, y5)), (C4X, y5), C_HOLD, lw=2.0)
    add_label(H3, y5 + LBL_LIFT, "rỗng", C_HOLD)

    # ---- (f) T2 -> cong (vong tin): mui ten NGANG trong hanh lang 3 ----
    # Ban v6 cho π cong tu T2 len day hop ②: duong cong cat qua vung giua-duoi va
    # cham nhan. Gio ②③④ cung day tu y = 0.105 nen π chi can di NGANG o y thap,
    # nam tron trong hanh lang 3 (x 0.650..0.735) — ngan, thang, khong cham gi.
    y_pi = 0.215
    arrow(ax, (C4X, y_pi), (C3X + C3W, y_pi), C_NET, ls=(0, (4, 2)), lw=1.4)
    add_label(H3, y_pi + LBL_LIFT, "π", C_NET, fs=7.0)

    # ---- (g) lenh -> ruong: KENH PHAI RIET (x = 0.968), khong chung hanh lang ----
    ytop = mid(sd)
    add_seg(C4X + C4W, ytop, CHANNEL_X, ytop, C_SEND, name="nuoc: ngang tren")
    add_seg(CHANNEL_X, ytop, CHANNEL_X, FLOOR_Y, C_SEND, name="nuoc: doc phai")
    add_seg(CHANNEL_X, FLOOR_Y, C1X + C1W / 2, FLOOR_Y, C_SEND, name="nuoc: ngang duoi")
    arrow(ax, (C1X + C1W / 2, FLOOR_Y), (C1X + C1W / 2, fl["y"]), C_SEND, lw=1.8, z=1)
    # nhan o SAN DAY: khong co hop nao ben canh (moi hop bat dau tu y = FLOOR),
    # nen gioi han dai la chieu rong canvas chu khong phai hanh lang. Kiem chung
    # bbox o cuoi van ap dung cho nhan nay nhu moi nhan khac.
    add_label((CHANNEL_X + C1X + C1W / 2) / 2, FLOOR_Y + 0.026,
              "nước vào ruộng (mm)", C_SEND, maxlen=22)

    # ---- (h) ruong -> cam bien (vong do luong) ----
    axx = C1X + C1W / 2
    arrow(ax, (axx, fl["y"] + fl["h"]), (axx, sn["y"]), C_DATA, lw=1.4)

    # ============ KIEM CHUNG TU DONG: nhan khong cham hop / khong cham duong ======
    fig.canvas.draw()
    rend = fig.canvas.get_renderer()
    inv = ax.transData.inverted()
    rects = [(b["x"], b["y"], b["x"] + b["w"], b["y"] + b["h"], b["tag"]) for b in boxes]
    problems = []
    for tobj, name in labels:
        bb = tobj.get_window_extent(renderer=rend)
        (x0, y0) = inv.transform((bb.x0, bb.y0))
        (x1, y1) = inv.transform((bb.x1, bb.y1))
        for rx0, ry0, rx1, ry1, tag in rects:
            # ban v7 chi bao khi GIAO NHAU. Vision van thay nhan "dat 95%" de len
            # goc hop ② vi hai bbox sat nhau (< 1 pt) ma mat thuong doc la "cham".
            # Doi thanh: phai cach nhau it nhat LBL_MARGIN.
            if (x0 - LBL_MARGIN < rx1 and x1 + LBL_MARGIN > rx0
                    and y0 - LBL_MARGIN < ry1 and y1 + LBL_MARGIN > ry0):
                gapx = max(rx0 - x1, x0 - rx1)
                gapy = max(ry0 - y1, y0 - ry1)
                problems.append(f"nhan {name!r} SAT/DE LEN hop {tag[:18]!r} "
                                f"(khe ngang {gapx:+.4f}, khe doc {gapy:+.4f}, "
                                f"can >= {LBL_MARGIN})")
        for sx0, sy0, sx1, sy1, sn_ in lines:
            pad = LBL_MARGIN
            if x0 - pad < sx1 and x1 + pad > sx0 and y0 - pad < sy1 and y1 + pad > sy0:
                problems.append(f"nhan {name!r} SAT/DE LEN duong {sn_}")
        for pa, an in ARROWS:
            bb = pa.get_window_extent(renderer=rend)
            (wx0, wy0) = inv.transform((bb.x0, bb.y0))
            (wx1, wy1) = inv.transform((bb.x1, bb.y1))
            gx = max(wx0 - x1, x0 - wx1)
            gy = max(wy0 - y1, y0 - wy1)
            # Chi flag khi KHE DOC khong du: nhan nam giua hanh lang nen trung pham vi
            # x cua mui ten ngang la hien nhien va khong phai loi (mui ten di NGANG qua
            # duoi nhan, nhan co nen trang nen van doc duoc). Dieu can dam bao la nhan
            # khong bi duong cat ngang qua chu.
            if gy < LBL_MARGIN and gx < 0:
                problems.append(f"nhan {name!r} DE LEN mui ten {an} "
                                f"(khe doc {gy:+.4f} < {LBL_MARGIN}, khe ngang {gx:+.4f})")
        if x0 < -0.005 or x1 > 1.005 or y0 < -0.005 or y1 > YLIM + 0.005:
            problems.append(f"nhan {name!r} nam NGOAI canvas "
                            f"(x {x0:.3f}..{x1:.3f}, y {y0:.3f}..{y1:.3f})")

    if problems:
        print(f"\n!! {len(problems)} LOI TRINH BAY con lai:")
        for p in problems:
            print("   -", p)
    else:
        print(f"  [check] {len(labels)} nhan: khong cham hop, khong cham duong, "
              f"khong ngoai canvas")

    fig.savefig(OUT / "fig1_method.pdf")
    fig.savefig(OUT / "fig1_method.png", dpi=300)
    print(f"wrote {OUT/'fig1_method.pdf'}")
    print(f"wrote {OUT/'fig1_method.png'}")
    ok = ok_boxes and not problems
    print("ALL BOXES FIT + NO OVERLAP + LABELS CLEAN" if ok else "!! VAN CON LOI")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

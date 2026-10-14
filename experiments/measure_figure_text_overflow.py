#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DO be rong chu that cua tung dong trong cac hop so do (fig1) de biet dong nao
TRAN va phai ngat o dau. KHONG doan: dung chinh renderer cua matplotlib.
In ra: dong | be rong chu (don vi truc) | be rong hop | tran bao nhieu.
"""
from __future__ import annotations
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 5.0})

W_CM, H_CM = 14.0, 7.0
fig, ax = plt.subplots(figsize=(W_CM / 2.54, H_CM / 2.54))
ax.set_xlim(0, 1); ax.set_ylim(0, 1)
fig.canvas.draw()
rend = fig.canvas.get_renderer()

# cac hop hien tai trong fig_vi.py: (x, y, w, h, text)
BOXES = [
    (0.010, 0.60, 0.185, "Nhật ký nông dân\n$L=\\{(t_i,u_i)\\}$\nđộ sâu khai báo\n+ dấu thời điểm"),
    (0.245, 0.60, 0.215, "Bản sao số FAO-56\nphát lại với ERA5 công khai\nphương trình thùng chứa theo giờ"),
    (0.510, 0.60, 0.185, "Quỹ đạo độ cạn kiệt\n$(\\hat w_t,\\hat d_t)$\n→ đếm pha khô\ndài ≥ 72 giờ"),
    (0.745, 0.60, 0.245, "3 bộ lọc vật lý $V_1,V_4,V_5$\nmô hình điểm, hoặc tầng bền vững\n(giao trên tập bất định $\\Theta$)"),
    (0.010, 0.10, 0.185, "Tấn công dịch thời điểm\ngiữ nguyên tổng lượng\nvà từng độ sâu,\nchỉ dời dấu thời điểm"),
    (0.245, 0.10, 0.215, "Gateway đóng mở máy bơm\nđã ký từng lệnh:\n$\\mathcal{G}=\\{(t_j,u_j,\\sigma_j)\\}$"),
    (0.510, 0.10, 0.185, "Neo thiết bị\nđối chiếu nhật ký\nvới BẢN GHI,\nkhông với mô hình"),
    (0.745, 0.10, 0.245, "Bắt 116/116 ca giả mạo\n0/60 ca kết tội oan\nchi phí biên gần bằng không"),
]

print(f"{'hop':>4} {'dong':>4} {'rộng chữ':>9} {'rộng hộp':>9} {'tràn':>8}  nội dung")
print("-" * 100)
worst = []
for bi, (x, y, w, text) in enumerate(BOXES, 1):
    for li, line in enumerate(text.split("\n"), 1):
        t = ax.text(0.5, 0.5, line, fontsize=5.0)
        fig.canvas.draw()
        bb = t.get_window_extent(renderer=rend)
        # doi px -> don vi truc (0..1) theo chieu ngang
        inv = ax.transData.inverted()
        x0, _ = inv.transform((bb.x0, bb.y0))
        x1, _ = inv.transform((bb.x1, bb.y1))
        tw = x1 - x0
        t.remove()
        over = tw - w
        flag = "  <<< TRAN" if over > 0 else ""
        print(f"{bi:>4} {li:>4} {tw:>9.4f} {w:>9.3f} {over:>+8.4f}  {line[:46]}{flag}")
        if over > 0:
            worst.append((bi, li, line, over))

print("\n=== TONG HOP ===")
print(f"  {len(worst)} dong tran tren {len(set(w[0] for w in worst))} hop")
for bi, li, line, over in worst:
    print(f"   hop {bi} dong {li}: tran {over:+.4f} (~{over/14*100:.2f} mm) — '{line}'")
# goi y: doan chu dai nhat co the chua (theo dong ngan nhat da khop)
ok = [(w - 0.0) for (_, _, w, _) in BOXES]
print(f"\n  be rong hop: {sorted(set(round(v,3) for v in ok))}")
plt.close(fig)

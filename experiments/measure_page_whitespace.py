#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Do KHOANG TRANG DOC lon nhat cua moi trang PDF (bang PIL, khong uoc luong).
Dung de xac nhan loi 'muc trong': heading bi mo coi vi bang [!h] bi day sang trang
khac -> giua trang co khoang trang lon.
Chay: python3 experiments/measure_page_whitespace.py <pdf>
"""
from __future__ import annotations
import subprocess, sys, os, glob, re

def measure(pdf: str, dpi: int = 100):
    out = "/tmp/ws_" + os.path.basename(pdf).replace(".pdf", "")
    for f in glob.glob(out + "*.png"):
        os.remove(f)
    subprocess.run(["pdftoppm", "-r", str(dpi), "-png", pdf, out],
                   capture_output=True, check=True)
    from PIL import Image
    rows = []
    for p in sorted(glob.glob(out + "*.png")):
        im = Image.open(p).convert("L")
        w, h = im.size
        px = im.load()
        # voi moi dong y: co phai trang (gan nhu het pixel sang)?
        dark = []
        for y in range(h):
            c = 0
            for x in range(0, w, 4):          # lay mau cach 4 pixel cho nhanh
                if px[x, y] < 200:
                    c += 1
            dark.append(c)
        # tim khoang trang doc dai nhat (o giua trang, bo le tren/duoi)
        best = cur = 0
        y0 = y1 = 0
        st = None
        for y in range(int(h * 0.08), int(h * 0.94)):
            if dark[y] == 0:
                if st is None:
                    st = y
                cur = y - st + 1
                if cur > best:
                    best, y0, y1 = cur, st, y
            else:
                st = None; cur = 0
        nchar = sum(1 for d in dark if d > 0)
        rows.append((os.path.basename(p), nchar, best, best * 25.4 / dpi,
                     y0 * 25.4 / dpi, y1 * 25.4 / dpi))
    return rows

def main():
    pdf = sys.argv[1] if len(sys.argv) > 1 else "paper2_vi_submission/output/main.pdf"
    rows = measure(pdf)
    print(f"{'trang':<26}{'dong co chu':>12}{'khe trang lon nhat':>22}{'tu y0..y1 (cm)':>20}")
    worst = []
    for name, nchar, best_px, best_mm, y0, y1 in rows:
        flag = "   <<< KHE LON" if best_mm > 25 else ""
        print(f"  {name:<24}{nchar:>12}{best_mm:>18.1f} mm{y0:>10.1f}..{y1:.1f}{flag}")
        if best_mm > 25:
            worst.append((name, best_mm))
    print(f"\n  So trang co khe trang > 25 mm: {len(worst)}/{len(rows)}")
    if worst:
        print("  -> heading/bang bi tach: " + ", ".join(f"{n} ({m:.0f}mm)" for n, m in worst))
    return 1 if worst else 0

if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Do baselineskip that cua TeX Gyre Pagella 10pt theo \\linespread.

Vi sao phai do, khong tinh:
  * Quy dinh HUJOS-TT noi "line spacing of 1.15". 2 bai da xuat ban do duoc
    pitch = 15.48pt (n=225 va n=161 khoang cach, trung vi).
  * Ban em dang dung \\linespread{1.15} va do duoc 13.75pt -> chat hon bai cua
    chinh toa soan 1.13 lan.
  * Word tinh "1.15" nhan voi (ascent+descent+lineGap) cua FONT; LaTeX
    \\linespread nhan voi baselineskip cua CLASS. Hai cach khac nhau, nen
    "1.15" trong Word khong bang \\linespread{1.15} trong LaTeX.

Vi sao phai tach moi gia tri thanh mot PDF rieng:
  Probe dau tien em dat ca 4 gia tri \\linespread trong CUNG mot file va tach doan
  bang khoang cach doc. Ham tach gop ca 4 doan lipsum thanh 1 (27 dong), trung vi
  ra 15.54pt = TRON cua 4 gia tri -> vo nghia. \\typeout khong xuat hien trong PDF
  nen khong dung lam moc duoc.

Chay: python3 experiments/probe_linespread.py
"""
import re
import statistics
import subprocess
import tempfile
from pathlib import Path

PT = 28.3465
TARGET = 15.48            # pitch do duoc o ca 2 bai HUJOS-TT da xuat ban
FONT = "TeX Gyre Pagella"

TPL = r"""\documentclass[10pt]{article}
\usepackage[paperwidth=19cm,paperheight=27cm,top=2cm,bottom=2cm,left=2cm,right=2cm]{geometry}
\usepackage{fontspec}
\setmainfont{%s}
\usepackage{lipsum}
\linespread{%s}\selectfont
\begin{document}
\lipsum[1-4]
\end{document}
"""

CANDS = ["1.00", "1.15", "1.20", "1.24", "1.25", "1.29", "1.30"]


def measure(pdf):
    bb = subprocess.run(["pdftotext", "-bbox", str(pdf), "-"],
                        capture_output=True, text=True).stdout
    gaps, heights = [], []
    for _pw, _ph, body in re.findall(
            r'<page width="([\d.]+)" height="([\d.]+)">(.*?)</page>', bb, re.S):
        ws = [(float(m.group(1)), float(m.group(2)), float(m.group(3)), float(m.group(4)))
              for m in re.finditer(
                  r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" '
                  r'yMax="([\d.]+)">([^<]*)</word>', body)]
        ys = sorted({round(w[1], 2) for w in ws})
        lines = []
        for y in ys:
            if lines and y - lines[-1][-1] <= 1.0:
                lines[-1].append(y)
            else:
                lines.append([y])
        cen = [statistics.mean(g) for g in lines]
        for i in range(len(cen) - 1):
            d = cen[i + 1] - cen[i]
            if 5 < d < 30:
                gaps.append(d)
        for w in ws:
            heights.append(w[3] - w[1])
    return (statistics.median(gaps) if gaps else 0,
            statistics.median(heights) if heights else 0, len(gaps))


def main():
    tmp = Path(tempfile.mkdtemp(prefix="lsprobe_"))
    print(f"=== {len(CANDS)} PDF rieng, moi PDF mot \\linespread ===")
    print(f"  font: {FONT} | class article 10pt | target pitch {TARGET}pt\n")
    print(f"  {'linespread':>10} | {'pitch do duoc':>14} | {'baselineskip 1.0':>16} | n")
    rows = []
    for ls in CANDS:
        d = tmp / ls.replace(".", "")
        d.mkdir()
        (d / "p.tex").write_text(TPL % (FONT, ls), encoding="utf-8")
        subprocess.run(["xelatex", "-interaction=nonstopmode", "p.tex"],
                       cwd=d, capture_output=True, timeout=200)
        pdf = d / "p.pdf"
        if not pdf.exists():
            print(f"  {ls:>10} | BUILD FAIL")
            continue
        pitch, h, n = measure(pdf)
        rows.append((float(ls), pitch))
        print(f"  {ls:>10} | {pitch:11.2f}pt | {pitch/float(ls):13.2f}pt | {n}")

    if len(rows) < 2:
        raise SystemExit("khong du du lieu de giai he so")

    # pitch = k * linespread  -> k = baselineskip tu nhien cua font/class
    ks = [p / l for l, p in rows]
    k = statistics.median(ks)
    print(f"\n=== KET QUA ===")
    print(f"  baselineskip tu nhien (k) = {k:.3f}pt  "
          f"(cac gia tri: {[round(x,2) for x in ks]})")
    need = TARGET / k
    print(f"  de dat pitch {TARGET}pt can \\linespread{{{need:.3f}}}")
    print(f"\n  DOI CHIEU:")
    for ls, p in rows:
        print(f"    linespread {ls:.2f} -> {p:.2f}pt  (lech target {p - TARGET:+.2f}pt)")
    best = min(rows, key=lambda r: abs(r[1] - TARGET))
    print(f"\n  => gia tri gan target nhat trong danh sach: {best[0]:.2f} "
          f"({best[1]:.2f}pt, lech {best[1]-TARGET:+.2f}pt)")
    print(f"  => gia tri chinh xac theo he so: {need:.3f}")
    print(f"\n  Ghi chu: 'line spacing 1.15' cua Word voi Palatino Linotype tuong duong")
    print(f"  \\linespread{{{need:.2f}}} trong LaTeX voi TeX Gyre Pagella, vi Word nhan")
    print(f"  1.15 voi (ascent+descent+lineGap) cua font con LaTeX nhan voi {k:.1f}pt.")


if __name__ == "__main__":
    main()

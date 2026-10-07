#!/usr/bin/env python3
"""Verify trinh bay ban LaTeX so voi 2 bai HUJOS-TT da xuat ban — ban CO LOC NHIU.

Vi sao phai sua cong cu do: ban measure_indent.py cu dem moi dong co xMin lon hon
le trai la "dong dau doan", nen no bat ca DONG TRONG BANG (xMin = 2.86 / 3.03 cm do
cot dau rong) va DONG PHUONG TRINH (canh giua). Ket qua "indent trung vi 2.91cm"
la NHIEU, khong phai ban PDF sai. Dau hieu cho thay parindent=1.0cm DA an: xuat
hien 13 dong o dung 1.00cm (ban truoc: 0 dong, chi co 18 dong o 0.45cm).

Ba tieu chi loc de chi giu DONG VAN XUOI that:
  1. >= 6 tu                       (dong bang/phuong trinh thuong ngan)
  2. max internal gap < 1.0 cm     (dong bang co ranh cot rat rong; van xuoi chi
                                    co khoang trang giua cac tu)
  3. xMax >= le phai - 2.0 cm      (van xuoi canh deu nen cham gan le phai;
                                    phuong trinh canh giua va bang thuong khong cham)
"""
import re
import statistics
import subprocess
from collections import Counter

PT = 28.3465
LEFT, RIGHT = 2.00, 17.00          # vung chu 19cm - le 2cm, da do tu bai da xuat ban
RE_W = re.compile(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" '
                  r'yMax="([\d.]+)">([^<]*)</word>')
RE_PG = re.compile(r'<page width="([\d.]+)" height="([\d.]+)">(.*?)</page>', re.S)

DOCS = [("/tmp/hujos_col/published_0.pdf", "XUAT BAN #1"),
        ("/tmp/hujos_col/published_1.pdf", "XUAT BAN #2"),
        ("/media/SAS/Van/DeTai2025/TwinGate_K1/paper2_hujos/main_hujos.pdf", "BAN EM")]


def load(pdf):
    bb = subprocess.run(["pdftotext", "-bbox", pdf, "-"],
                        capture_output=True, text=True).stdout
    pages = []
    for pw, ph, body in RE_PG.findall(bb):
        ws = [(float(m.group(1)), float(m.group(2)), float(m.group(3)),
               float(m.group(4)), m.group(5)) for m in RE_W.finditer(body)]
        pages.append((float(pw), ws))
    return pages


def prose_lines(ws, ymin=2.6, ymax=25.0, tol=1.2):
    """Gom tu thanh dong, roi chi giu dong VAN XUOI theo 3 tieu chi loc."""
    groups = []
    for y in sorted({round(w[1], 2) for w in ws if ymin * PT < w[1] < ymax * PT}):
        if groups and y - groups[-1][-1] <= tol:
            groups[-1].append(y)
        else:
            groups.append([y])
    out = []
    for g in groups:
        yc = statistics.mean(g)
        row = sorted([w for w in ws if abs(w[1] - yc) <= tol + 0.3], key=lambda z: z[0])
        if len(row) < 6:                                     # loc 1: so tu
            continue
        gaps = [row[i + 1][0] - row[i][2] for i in range(len(row) - 1)]
        if gaps and max(gaps) / PT > 1.0:                      # loc 2: ranh cot
            continue
        x0 = min(w[0] for w in row) / PT
        x1 = max(w[2] for w in row) / PT
        if x1 < RIGHT - 2.0:                                   # loc 3: cham le phai
            continue
        out.append(dict(y=yc, x0=x0, x1=x1, n=len(row),
                        txt=" ".join(w[4] for w in row)))
    return out


print("=" * 82)
print("A) INDENT DAU DOAN + KHOANG CACH DOAN  (chi tinh dong van xuoi that)")
print("=" * 82)
for pdf, lab in DOCS:
    pages = load(pdf)
    firsts, pitches, pgaps = [], [], []
    n_prose = 0
    for _, ws in pages:
        L = prose_lines(ws)
        n_prose += len(L)
        for i in range(1, len(L)):
            prev, cur = L[i - 1], L[i]
            dy = cur["y"] - prev["y"]
            if 8 < dy < 25:
                pitches.append(dy)
            # dong dau doan: doan truoc ket thuc som (x1 thut vao) => cur thut le
            if prev["x1"] < RIGHT - 0.5 and cur["x0"] > LEFT + 0.12 and dy < 25:
                firsts.append(cur["x0"] - LEFT)
                if dy > 8:
                    pgaps.append(dy)
    base = statistics.median(pitches) if pitches else 0
    print(f"\n--- {lab}")
    print(f"    {n_prose} dong van xuoi | pitch thuong = {base:.2f}pt (n={len(pitches)})")
    if firsts:
        c = Counter(round(x, 2) for x in firsts)
        print(f"    {len(firsts)} dong dau doan | indent pho bien: {c.most_common(4)}")
        print(f"    indent TRUNG VI = {statistics.median(firsts):.2f}cm   "
              f"(bai da dang: 1.00cm)")
    else:
        print("    0 dong dau doan thut le -> BLOCK STYLE (parindent = 0)")
    if pgaps:
        print(f"    pitch tai cho bat dau doan = {statistics.median(pgaps):.2f}pt"
              f" -> parskip thuc te = {statistics.median(pgaps) - base:+.2f}pt")

print()
print("=" * 82)
print("B) CAPTION BANG/HINH: canh giua hay canh trai?")
print("=" * 82)
for pdf, lab in DOCS:
    pages = load(pdf)
    hits = []
    for pno, (_, ws) in enumerate(pages, 1):
        groups = []
        for y in sorted({round(w[1], 2) for w in ws}):
            if groups and y - groups[-1][-1] <= 1.2:
                groups[-1].append(y)
            else:
                groups.append([y])
        for g in groups:
            yc = statistics.mean(g)
            row = sorted([w for w in ws if abs(w[1] - yc) <= 1.5], key=lambda z: z[0])
            if len(row) < 3:
                continue
            txt = " ".join(w[4] for w in row)
            if re.match(r"^(Table|Fig\.|Figure)\s*\d+[.:]", txt):
                hits.append((pno, min(w[0] for w in row) / PT, max(w[2] for w in row) / PT,
                             statistics.median([w[3] - w[1] for w in row]), txt))
    cent = left_ = 0
    for pno, x0, x1, h, txt in hits:
        mid = (x0 + x1) / 2
        if abs(mid - 9.5) < 1.0:
            cent += 1
        elif x0 < LEFT + 0.3:
            left_ += 1
    hs = [h for *_, h, _ in hits]
    print(f"\n--- {lab}: {len(hits)} caption | canh GIUA {cent} | canh TRAI {left_}"
          f" | co chu trung vi {statistics.median(hs):.2f}pt" if hs else
          f"\n--- {lab}: {len(hits)} caption | canh GIUA {cent} | canh TRAI {left_}")
    for pno, x0, x1, h, txt in hits[:3]:
        mid = (x0 + x1) / 2
        print(f"    tr{pno:>2} x=[{x0:.2f},{x1:.2f}] mid={mid:.2f} "
              f"{'CENTER' if abs(mid-9.5)<1.0 else ('LEFT' if x0<LEFT+0.3 else 'INDENT')}"
              f" | {txt[:56]}")

print()
print("=" * 82)
print("C) DICH XEM PDF (de xac nhan bang mat, khong chi bang so)")
print("=" * 82)
print("  render trang 1 + trang giua cua ban em thanh PNG")

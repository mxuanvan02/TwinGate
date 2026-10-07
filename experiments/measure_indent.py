#!/usr/bin/env python3
"""Do INDENT dau doan + KHOANG CACH giua cac doan cua bai HUJOS-TT da xuat ban.

Cach do (khong doan): mot dong la "dong dau doan" neu dong NGAY TRUOC no ket thuc
som hon le phai it nhat 0.5 cm (tuc doan truoc da het). Do xMin cua dong dau doan
tru le trai -> indent that.

Khoang cach doan = pitch (dong dau doan) - pitch (cac dong thuong), lay trung vi.

Bai hoc: phien ban truoc dem "so dong co xMin > le pho bien" roi goi do la indent,
nhung cac dong do phan lon la dong TRONG BANG / phuong trinh, nen ra ket luan sai
(indent 4.71cm cho ban cua minh). Phai loc dung bang tieu chi "doan truoc ket thuc
som".
"""
import re
import statistics
import subprocess
from collections import Counter

PT = 28.3465
RE_W = re.compile(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" '
                  r'yMax="([\d.]+)">([^<]*)</word>')
RE_PG = re.compile(r'<page width="([\d.]+)" height="([\d.]+)">(.*?)</page>', re.S)

DOCS = [("/tmp/hujos_col/published_0.pdf", "XUAT BAN #1"),
        ("/tmp/hujos_col/published_1.pdf", "XUAT BAN #2"),
        ("/media/SAS/Van/DeTai2025/TwinGate_K1/paper2_hujos/main_hujos.pdf", "BAN EM")]


def load(pdf):
    bb = subprocess.run(["pdftotext", "-bbox", pdf, "-"],
                        capture_output=True, text=True).stdout
    out = []
    for k, (pw, ph, body) in enumerate(RE_PG.findall(bb), 1):
        ws = [(float(m.group(1)), float(m.group(2)), float(m.group(3)),
               float(m.group(4)), m.group(5)) for m in RE_W.finditer(body)]
        out.append((k, float(pw), ws))
    return out


def lines_of(ws, ymin=2.6, ymax=25.0, tol=1.2, minwords=4):
    groups = []
    for y in sorted({round(w[1], 2) for w in ws if ymin * PT < w[1] < ymax * PT}):
        if groups and y - groups[-1][-1] <= tol:
            groups[-1].append(y)
        else:
            groups.append([y])
    res = []
    for g in groups:
        yc = statistics.mean(g)
        row = sorted([w for w in ws if abs(w[1] - yc) <= tol + 0.3], key=lambda z: z[0])
        if len(row) < minwords:
            continue
        res.append(dict(y=yc, x0=min(w[0] for w in row) / PT, x1=max(w[2] for w in row) / PT,
                        n=len(row), txt=" ".join(w[4] for w in row)))
    return res


print("=== INDENT DAU DOAN + KHOANG CACH DOAN (loc bang 'doan truoc ket thuc som') ===\n")
for pdf, lab in DOCS:
    pages = load(pdf)
    left, right = 2.00, 17.00
    firsts, gaps, pitches = [], [], []
    for pno, pw, ws in pages:
        L = lines_of(ws)
        if len(L) < 8:
            continue
        for i in range(1, len(L)):
            prev, cur = L[i - 1], L[i]
            dy = cur["y"] - prev["y"]
            if 8 < dy < 25:
                pitches.append(dy)
            # doan truoc ket thuc som => cur la dong dau doan
            if prev["x1"] < right - 0.5 and cur["x0"] > left + 0.12 and dy < 25:
                firsts.append(cur["x0"] - left)
                if dy > 8:
                    gaps.append(dy)
    base = statistics.median(pitches) if pitches else 0
    print(f"--- {lab}")
    print(f"    pitch dong thuong (trung vi): {base:.2f}pt  (n={len(pitches)})")
    if firsts:
        c = Counter(round(x, 2) for x in firsts)
        print(f"    {len(firsts)} dong dau doan | indent pho bien: {c.most_common(4)}")
        print(f"    indent trung vi = {statistics.median(firsts):.2f}cm")
    else:
        print("    0 dong dau doan thut le  => BLOCK STYLE (parindent = 0)")
    if gaps:
        extra = [g - base for g in gaps]
        print(f"    khoang cach doan: pitch tai cho bat dau doan = {statistics.median(gaps):.2f}pt"
              f" -> thut them {statistics.median(extra):.2f}pt so voi dong thuong")
    else:
        print("    khoang cach doan: khong co (parskip ~ 0)")
    print()

print("=== DOI CHIEU QUY DINH VAN BAN ===")
print("  'lines spacing of 1.15, 6 points before and 3 points after paragraph spacing'")
print("  template docx docDefaults: w:spacing before=120 after=60 line=276 (=6pt/3pt/1.15)")
print("  => parskip phai co (3pt sau doan); con parindent thi theo so do phia tren")

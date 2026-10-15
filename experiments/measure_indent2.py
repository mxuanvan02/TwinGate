#!/usr/bin/env python3
"""Do parindent + parskip KHONG can tim ranh gioi doan.

Vi sao bo cach cu: verify_layout.py ban 1 loc dong van xuoi bang tieu chi
"xMax >= le phai - 2cm" (van canh deu thi cham le phai). Nhung DONG CUOI CUA
DOAN la dong ngan, KHONG cham le phai -> bi loai dung vao cho can nhat. Hau qua:
chi phat hien 4/417 dong dau doan o ban cua minh va 19/23 o bai da dang, roi suy
ra "indent 0.31cm" va "parskip -3.36pt" (am = vo ly hinh hoc, dau hieu chac chan
la nghe thuat cua phep do).

Cach dung, dua vao ban chat van canh deu (justified):
  * MOI dong van xuoi deu bat dau DUNG le trai (2.00cm), NGOAI TRU dong dau doan
    bat dau o 2.00 + parindent.
  => chi can xem PHAN BO x0: dinh tai 2.00cm = dong thuong; dinh thu hai tai
     X cm = parindent. KHONG can biet doan bat dau o dau.
  * parskip: xem PHAN BO khoang cach doc giua 2 dong lien tiep. Mot dinh = pitch
     thuong; dinh thu hai (cao hon) = pitch + parskip. Chi tinh cap dong KE NHAU
     trong cung mot cot van xuoi, khong tinh cap vuot qua bang/cong thuc.
"""
import re
import statistics
import subprocess
from collections import Counter

PT = 28.3465
LEFT, RIGHT = 2.00, 17.00
RE_W = re.compile(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" '
                  r'yMax="([\d.]+)">([^<]*)</word>')
RE_PG = re.compile(r'<page width="([\d.]+)" height="([\d.]+)">(.*?)</page>', re.S)

DOCS = [("/tmp/hujos_col/published_0.pdf", "XUAT BAN #1"),
        ("/tmp/hujos_col/published_1.pdf", "XUAT BAN #2"),
        ("/media/SAS/Van/DeTai2025/TwinGate_K1/paper2_hujos/main_hujos.pdf", "BAN EM")]


def rows(ws, ymin=2.6, ymax=25.0, tol=1.2, minwords=6, maxgap=1.0):
    """Gom tu thanh dong; GIU ca dong ngan (dong cuoi doan) — chi loc bang/cong thuc."""
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
        if len(row) < minwords:
            continue
        gaps = [row[i + 1][0] - row[i][2] for i in range(len(row) - 1)]
        if gaps and max(gaps) / PT > maxgap:      # ranh cot cua bang
            continue
        out.append((yc, min(w[0] for w in row) / PT, max(w[2] for w in row) / PT,
                    " ".join(w[4] for w in row)))
    return out


def load(pdf):
    bb = subprocess.run(["pdftotext", "-bbox", pdf, "-"],
                        capture_output=True, text=True).stdout
    pages = []
    for pw, ph, body in RE_PG.findall(bb):
        ws = [(float(m.group(1)), float(m.group(2)), float(m.group(3)),
               float(m.group(4)), m.group(5)) for m in RE_W.finditer(body)]
        pages.append(ws)
    return pages


print("=" * 84)
print("PARINDENT = dinh thu hai trong phan bo x0 (khong can ranh gioi doan)")
print("=" * 84)
summary = {}
for pdf, lab in DOCS:
    allx0, alldy = [], []
    for ws in load(pdf):
        L = rows(ws)
        for (yc, x0, x1, txt) in L:
            allx0.append(x0)
        for i in range(1, len(L)):
            dy = L[i][0] - L[i - 1][0]
            # chi tinh cap dong SAT NHAU trong cung khoi van (bo cap vuot qua
            # bang/cong thuc: nhung cho do dy lon bat thuong va khong phai parskip)
            if 8 < dy < 30:
                alldy.append(dy)
    c = Counter(round(x, 2) for x in allx0)
    top = c.most_common(5)
    base = top[0]
    # dinh thu hai = gia tri x0 co tan suat >= 5 dong va lon hon le trai
    second = [(v, n) for v, n in top if v > LEFT + 0.3 and n >= 5]
    print(f"\n--- {lab}")
    print(f"    {len(allx0)} dong van xuoi | phan bo x0: {top}")
    print(f"    le trai pho bien = {base[0]:.2f}cm ({base[1]} dong)")
    if second:
        v, n = second[0]
        print(f"    PARINDENT = {v - LEFT:.2f}cm  ({n} dong dau doan)")
        summary[lab] = ("parindent", round(v - LEFT, 2), n)
    else:
        print("    PARINDENT = 0 (khong co dinh thu hai nao >= 5 dong) -> BLOCK STYLE")
        summary[lab] = ("parindent", 0.0, 0)

    dc = Counter(round(d, 2) for d in alldy)
    dtop = dc.most_common(4)
    pitch = dtop[0][0]
    print(f"    phan bo khoang cach doc (n={len(alldy)}): {dtop}")
    taller = [(v, n) for v, n in dtop if v > pitch + 1.0 and n >= 4]
    if taller:
        v, n = taller[0]
        print(f"    pitch = {pitch:.2f}pt | PARSKIP = {v - pitch:+.2f}pt ({n} cho)")
        summary[lab] += ("parskip", round(v - pitch, 2))
    else:
        print(f"    pitch = {pitch:.2f}pt | PARSKIP = 0 (khong co dinh thu hai)")
        summary[lab] += ("parskip", 0.0)

print()
print("=" * 84)
print("TONG HOP")
print("=" * 84)
for lab, v in summary.items():
    print(f"  {lab:<14} parindent={v[1]:.2f}cm ({v[2]:>3} doan) | parskip={v[4]:+.2f}pt")
pub = [v for lab, v in summary.items() if lab.startswith("XUAT BAN")]
mine = summary.get("BAN EM")
if pub and mine:
    pi = statistics.median([v[1] for v in pub])
    ps = statistics.median([v[4] for v in pub])
    print(f"\n  Bai da dang (trung vi): parindent={pi:.2f}cm | parskip={ps:+.2f}pt")
    print(f"  Ban em               : parindent={mine[1]:.2f}cm | parskip={mine[4]:+.2f}pt")
    ok_i = abs(mine[1] - pi) <= 0.15
    ok_s = abs(mine[4] - ps) <= 1.5
    print(f"  => parindent {'KHOP' if ok_i else 'LECH'} | parskip {'KHOP' if ok_s else 'LECH'}")

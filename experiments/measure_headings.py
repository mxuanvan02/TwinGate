#!/usr/bin/env python3
"""Do HEADING cua bai HUJOS-TT da xuat ban: dau cham sau so, va kieu heading phu.

Cau hoi cu the (khong doan):
  1. Section heading la "1 Introduction" hay "1. Introduction"?
     -> ban em dang dung {\thesection.} tuc CO dau cham.
  2. Co subsection danh so kieu "2.1 Related Work" khong? In dam hay nghien?
  3. Heading co cung co chu voi body (10pt) hay lon hon?

Cach do: tim dong ngan (<=8 tu) bat dau bang so (vd "1 ", "2.1 "), roi in
nguyen van + height chu + xMin. In nguyen van de TU MAT thay dau cham.
"""
import re
import statistics
import subprocess

PT = 28.3465
RE_W = re.compile(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" '
                  r'yMax="([\d.]+)">([^<]*)</word>')
RE_PG = re.compile(r'<page width="([\d.]+)" height="([\d.]+)">(.*?)</page>', re.S)

DOCS = [("/tmp/hujos_col/published_0.pdf", "XUAT BAN #1"),
        ("/tmp/hujos_col/published_1.pdf", "XUAT BAN #2"),
        ("/media/SAS/Van/DeTai2025/TwinGate_K1/paper2_hujos/main_hujos.pdf", "BAN EM")]

RE_NUM = re.compile(r"^\d+(\.\d+)*\.?\s+\S")


def lines_of(pdf, page, ymin=2.4, ymax=25.0, tol=1.2):
    bb = subprocess.run(["pdftotext", "-bbox", pdf, "-"],
                        capture_output=True, text=True).stdout
    out = []
    for k, (pw, ph, body) in enumerate(RE_PG.findall(bb), 1):
        if k != page:
            continue
        ws = [(float(m.group(1)), float(m.group(2)), float(m.group(3)),
               float(m.group(4)), m.group(5)) for m in RE_W.finditer(body)]
        groups = []
        for y in sorted({round(w[1], 2) for w in ws if ymin * PT < w[1] < ymax * PT}):
            if groups and y - groups[-1][-1] <= tol:
                groups[-1].append(y)
            else:
                groups.append([y])
        for g in groups:
            yc = statistics.mean(g)
            row = sorted([w for w in ws if abs(w[1] - yc) <= tol + 0.3], key=lambda z: z[0])
            if len(row) < 2:
                continue
            out.append((k, yc, min(w[0] for w in row) / PT,
                        statistics.median([w[3] - w[1] for w in row]),
                        " ".join(w[4] for w in row), len(row)))
    return out


for pdf, lab in DOCS:
    bb = subprocess.run(["pdftotext", "-bbox", pdf, "-"],
                        capture_output=True, text=True).stdout
    npages = len(RE_PG.findall(bb))
    print("=" * 84)
    print(f"{lab} ({npages} trang) — moi dong ngan bat dau bang so")
    n = 0
    for pg in range(1, npages + 1):
        for (k, yc, x0, h, txt, nw) in lines_of(pdf, pg):
            if nw > 9 or not RE_NUM.match(txt):
                continue
            n += 1
            if n > 14:
                continue
            print(f"  tr{pg:>2} y={yc/PT:5.2f}cm h={h:5.2f}pt x0={x0:.2f} nw={nw} | {txt[:64]}")
    if n == 0:
        print("  (khong tim thay heading danh so)")
    print(f"  tong {n} heading danh so\n")

print("=" * 84)
print("DOI CHIEU: dau cham sau so muc")
for pdf, lab in DOCS:
    raw = subprocess.run(["pdftotext", "-layout", pdf, "-"],
                         capture_output=True, text=True).stdout
    withdot = re.findall(r"^\s*(\d+)\.\s+[A-Z][a-z]", raw, re.M)
    nodot = re.findall(r"^\s*(\d+)\s+[A-Z][a-z]", raw, re.M)
    sub = re.findall(r"^\s*(\d+\.\d+)\.?\s+[A-Z]", raw, re.M)
    print(f"  {lab}: 'N. Word' = {len(withdot)} | 'N Word' = {len(nodot)} | subsection 'N.M' = {len(sub)} {sub[:4]}")

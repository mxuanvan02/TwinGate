#!/usr/bin/env python3
"""Do 4 dac trung trinh bay cua 2 bai HUJOS-TT DA XUAT BAN, de bat chuc trong LaTeX.

Khong doan: moi ket luan deu in ra toa do + kich thuoc that tu pdftotext -bbox.

Bai hoc (2 lan vep trong cung mot luot): unpack tuple trong list comprehension de
gay NameError ('b' is not defined). Vi vay o day dung tuple chi muc ro rang
W = (page, xMin, yMin, xMax, yMax, text) va luon truy cap w[1]..w[5], khong
unpack tung bien roi dung lai trong comprehension khac.
"""
import re
import statistics
import subprocess
import sys
from collections import Counter

PT = 28.3465          # 1 cm
PUB = [("/tmp/hujos_col/published_0.pdf", "XUAT BAN #1 (art.7830)"),
       ("/tmp/hujos_col/published_1.pdf", "XUAT BAN #2 (art.7862)")]
MINE = ("/media/SAS/Van/DeTai2025/TwinGate_K1/paper2_hujos/main_hujos.pdf",
        "BAN EM (LaTeX)")

RE_W = re.compile(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" '
                  r'yMax="([\d.]+)">([^<]*)</word>')
RE_PG = re.compile(r'<page width="([\d.]+)" height="([\d.]+)">(.*?)</page>', re.S)


def load(pdf):
    bb = subprocess.run(["pdftotext", "-bbox", pdf, "-"],
                        capture_output=True, text=True).stdout
    out = []
    for k, (pw, ph, body) in enumerate(RE_PG.findall(bb), 1):
        for m in RE_W.finditer(body):
            out.append((k, float(m.group(1)), float(m.group(2)),
                        float(m.group(3)), float(m.group(4)), m.group(5)))
    return out


def group_lines(ws, page, ymin=2.2, ymax=25.0, tol=1.2, minwords=2):
    """Gom tu thanh dong TRONG MOT TRANG. Tra ve [(yCen, xMin, xMax, height, text, nword)]."""
    p = [w for w in ws if w[0] == page and ymin * PT < w[2] < ymax * PT]
    lines = []
    for y in sorted({round(w[2], 2) for w in p}):
        if lines and y - lines[-1][-1] <= tol:
            lines[-1].append(y)
        else:
            lines.append([y])
    res = []
    for g in lines:
        yc = statistics.mean(g)
        row = sorted([w for w in p if abs(w[2] - yc) <= tol + 0.3], key=lambda z: z[1])
        if len(row) < minwords:
            continue
        res.append((yc, min(w[1] for w in row) / PT, max(w[3] for w in row) / PT,
                    statistics.median([w[4] - w[2] for w in row]),
                    " ".join(w[5] for w in row), len(row)))
    return res


def headings(ws, npages, body_h):
    """Dong ngan (<=9 tu) co chu cao hon body -> heading. In size + vi tri + xMin."""
    print("  --- HEADING (dong ngan, chu cao hon body) ---")
    seen = set()
    n = 0
    for pg in range(1, npages + 1):
        for (yc, x0, x1, h, txt, nw) in group_lines(ws, pg):
            if nw > 9 or h <= body_h + 0.6 or len(txt) < 3:
                continue
            key = (pg, round(yc, 1))
            if key in seen:
                continue
            seen.add(key)
            n += 1
            if n > 10:
                continue
            # uoc tinh font size tu height chu thuong (khong tinh chu co dau)
            print(f"   tr{pg:>2} y={yc/PT:5.2f}cm h={h:5.2f}pt x0={x0:.2f} "
                  f"{'CENTER' if abs((x0+x1)/2 - 9.5) < 1.2 else 'left  '} | {txt[:60]}")
    if n == 0:
        print("   (khong tim thay — heading co the cung co chu voi body, chi in dam)")


def captions(pdf):
    """Caption cua bang/hinh: alignment + co chu + dau cach sau so."""
    raw = subprocess.run(["pdftotext", "-layout", pdf, "-"],
                         capture_output=True, text=True).stdout
    ws = load(pdf)
    print("  --- CAPTION 'Table n.' / 'Fig. n.' ---")
    hits = []
    for pg in range(1, max(w[0] for w in ws) + 1):
        for (yc, x0, x1, h, txt, nw) in group_lines(ws, pg, minwords=3):
            if re.match(r"^(Table|Fig\.|Figure)\s*\d+[.:]", txt):
                hits.append((pg, yc, x0, x1, h, txt))
    for pg, yc, x0, x1, h, txt in hits[:4]:
        mid = (x0 + x1) / 2
        al = "CENTER" if abs(mid - 9.5) < 1.0 else ("LEFT" if x0 < 3.0 else "INDENT")
        print(f"   tr{pg:>2} h={h:5.2f}pt x=[{x0:.2f},{x1:.2f}] mid={mid:.2f} -> {al}")
        print(f"        {txt[:78]}")
    if hits:
        hs = [h for *_, h, _ in hits]
        print(f"   tong {len(hits)} caption | co chu trung vi {statistics.median(hs):.2f}pt")
    # dau phan cach sau so
    m = re.findall(r"(Table|Fig\.)\s*(\d+)([.:]?)", raw)
    print(f"   dau sau so: {Counter(x[2] for x in m).most_common(3)}")


def indent(ws, pages):
    print("  --- INDENT DAU DOAN ---")
    for pg in pages:
        L = group_lines(ws, pg, minwords=3)
        if len(L) < 5:
            continue
        xs = [l[1] for l in L]
        modal = Counter(round(x, 1) for x in xs).most_common(1)[0][0]
        deeper = [x for x in xs if x > modal + 0.15]
        style = ("CO thut le dau doan" if len(deeper) >= len(L) * 0.25
                 else "BLOCK (khong thut le)")
        d = statistics.median(deeper) - modal if deeper else 0
        print(f"   tr{pg:>2}: {len(L):>2} dong | le trai {modal:.2f}cm | "
              f"{len(deeper)} dong sau hon (+{d:.2f}cm) -> {style}")


def header(ws):
    print("  --- HEADER ---")
    for pg in (1, 2, 3):
        top = [w for w in ws if w[0] == pg and w[2] < 2.2 * PT]
        if not top:
            print(f"   tr{pg}: (khong co header)"); continue
        rows = {}
        for w in top:
            rows.setdefault(round(w[2] / 2), []).append(w)
        for k in sorted(rows):
            r = sorted(rows[k], key=lambda z: z[1])
            y = statistics.mean([w[2] for w in r]) / PT
            h = statistics.median([w[4] - w[2] for w in r])
            x0 = min(w[1] for w in r) / PT
            x1 = max(w[3] for w in r) / PT
            print(f"   tr{pg} y={y:4.2f}cm h={h:4.2f}pt x=[{x0:.2f},{x1:.2f}] | "
                  f"{' '.join(w[5] for w in r)[:88]}")


for pdf, lab in PUB + [MINE]:
    ws = load(pdf)
    npages = max(w[0] for w in ws)
    print("=" * 80)
    print(f"{lab}: {npages} trang")
    mid = npages // 2 + 1
    Lmid = group_lines(ws, mid, minwords=3)
    body_h = statistics.median([l[3] for l in Lmid]) if Lmid else 10.0
    print(f"  co chu body (trang {mid}): {body_h:.2f}pt")
    headings(ws, npages, body_h)
    captions(pdf)
    indent(ws, [mid, mid + 1])
    header(ws)
    print()

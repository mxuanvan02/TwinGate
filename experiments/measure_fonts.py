#!/usr/bin/env python3
"""Do FONT + CO CHU theo vai tro (title/heading/body/caption) bang PyMuPDF.

Vi sao can: pdffonts chi liet ke ten font, KHONG noi font nao dung cho gi.
Bai HUJOS-TT da xuat ban co 12 font (PalatinoLinotype-Roman/Bold/BoldItalic,
Cambria, Cambria-Italic, CambriaMath, Arial-BoldMT, ArialMT) nen khong the doan
heading dung Palatino-Bold hay Arial-BoldMT.

PyMuPDF doc tung span: (text, font, size, bbox) -> phan loai theo noidung:
  * title        : trang 1, size lon nhat
  * section head : dong bat dau bang "^N Word" (khong co dau cham), size > body
  * subsection   : dong bat dau bang "^N.M Word"
  * caption      : dong bat dau bang "Table n." hoac "Fig. n."
  * body         : phan con lai, size pho bien nhat
In ra font + size that cua tung vai tro de bat chuc trong LaTeX.
"""
import re
import statistics
import subprocess
import sys
from collections import Counter

import fitz          # PyMuPDF

DOCS = [("/tmp/hujos_col/published_0.pdf", "XUAT BAN #1 (art.7830)"),
        ("/tmp/hujos_col/published_1.pdf", "XUAT BAN #2 (art.7862)"),
        ("/media/SAS/Van/DeTai2025/TwinGate_K1/paper2_hujos/main_hujos.pdf", "BAN EM")]


def spans(pdf):
    doc = fitz.open(pdf)
    out = []
    for pno, page in enumerate(doc, 1):
        d = page.get_text("dict")
        for blk in d.get("blocks", []):
            if blk.get("type") != 0:
                continue
            for ln in blk.get("lines", []):
                txt = "".join(sp.get("text", "") for sp in ln.get("spans", []))
                if not txt.strip():
                    continue
                fonts = [sp.get("font", "") for sp in ln.get("spans", [])]
                sizes = [sp.get("size", 0) for sp in ln.get("spans", [])]
                x0 = ln["bbox"][0] / 28.3465
                y0 = ln["bbox"][1] / 28.3465
                out.append(dict(page=pno, txt=txt.strip(),
                                font=Counter(fonts).most_common(1)[0][0] if fonts else "",
                                size=statistics.median(sizes) if sizes else 0,
                                x0=x0, y0=y0, nword=len(txt.split())))
    doc.close()
    return out


RE_SEC = re.compile(r"^\d+\s+[A-Z][A-Za-z]")
RE_SUB = re.compile(r"^\d+\.\d+\s+[A-Z]")
RE_CAP = re.compile(r"^(Table|Fig\.|Figure)\s*\d+[.:]")


def role(s, body_size):
    t = s["txt"]
    if s["page"] == 1 and s["size"] > body_size + 2 and s["nword"] <= 12:
        return "TITLE"
    if RE_CAP.match(t):
        return "CAPTION"
    if RE_SUB.match(t) and s["nword"] <= 10:
        return "SUBSECTION"
    if RE_SEC.match(t) and s["nword"] <= 10:
        return "SECTION"
    if s["page"] == 1 and abs(s["size"] - body_size) < 1.3 and s["nword"] <= 14:
        return "FRONT(author/affil/abstract)"
    return "body"


for pdf, lab in DOCS:
    try:
        S = spans(pdf)
    except Exception as e:
        print(f"{lab}: PyMuPDF doc that bai ({e})"); continue
    sizes = [s["size"] for s in S if s["nword"] > 6]
    body_size = statistics.median(sizes) if sizes else 10
    print("=" * 86)
    print(f"{lab}: {max(s['page'] for s in S)} trang | body size {body_size:.2f}pt")
    buckets = {}
    for s in S:
        buckets.setdefault(role(s, body_size), []).append(s)
    for r in ("TITLE", "SECTION", "SUBSECTION", "CAPTION", "FRONT(author/affil/abstract)", "body"):
        v = buckets.get(r, [])
        if not v:
            continue
        fonts = Counter(x["font"] for x in v).most_common(3)
        szs = Counter(round(x["size"], 2) for x in v).most_common(3)
        x0s = Counter(round(x["x0"], 1) for x in v).most_common(3)
        print(f"  {r:<30} n={len(v):>4}")
        print(f"     font : {fonts}")
        print(f"     size : {szs}")
        print(f"     xMin : {x0s}")
        for x in v[:2]:
            print(f"     vd tr{x['page']} y={x['y0']:5.2f} size={x['size']:.2f} "
                  f"font={x['font']} | {x['txt'][:56]}")
    print()

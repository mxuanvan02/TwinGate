#!/usr/bin/env python3
"""Do 22 TRANG cua ban HUJOS tieu vao dau — de de xuat cat cho nao CO CO SO.

Khong doan: moi muc deu in so trang / so tu / dien tich that, do tu PDF.

Phan loai tung trang theo noi dung chiem dien tich:
  * bang     : vung co nhieu dong ngan + ranh cot (hoac nam giua Table caption va
               dong van xuoi ke tiep)
  * cong thuc: dong co ky tu toan va canh giua (khong cham le phai)
  * refs     : tu trang co "References" tro di
  * tieng Viet: tu trang co "Tóm tắt" tro di (khoi bat buoc theo muc 3 quy dinh)
  * van xuoi : phan con lai
"""
import re
import statistics
import subprocess
import sys
from collections import Counter
from pathlib import Path

import fitz

PDF = sys.argv[1] if len(sys.argv) > 1 else (
    "/media/SAS/Van/DeTai2025/TwinGate_K1/paper2_hujos/main_hujos.pdf")
PT = 28.3465
LEFT, RIGHT = 2.00, 17.00
TOP, BOTTOM = 2.00, 25.00
TEXT_AREA_CM2 = (RIGHT - LEFT) * (BOTTOM - TOP)

MATHCH = set("=+−≤≥∑∏∫∀∃∈∉⊂⊆∪∩∂∇≈≠×÷±√∞⌊⌉⟨⟩∥αβγδεζηθικλμνξπρστυφχψω"
             "ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΠΡΣΤΥΦΧΨΩ")


def analyse(pdf):
    doc = fitz.open(pdf)
    print(f"=== {Path(pdf).name} : {doc.page_count} trang ===")
    print(f"    vung chu {RIGHT-LEFT:.1f} x {BOTTOM-TOP:.1f} cm = {TEXT_AREA_CM2:.0f} cm2\n")
    rows = []
    mode = "body"
    for pno, page in enumerate(doc, 1):
        d = page.get_text("dict")
        blocks = []
        for blk in d.get("blocks", []):
            if blk.get("type") != 0:
                continue
            for ln in blk.get("lines", []):
                txt = "".join(sp.get("text", "") for sp in ln.get("spans", [])).strip()
                if not txt:
                    continue
                b = ln["bbox"]
                blocks.append(dict(x0=b[0] / PT, y0=b[1] / PT, x1=b[2] / PT, y1=b[3] / PT,
                                   txt=txt, size=statistics.median(
                                       [sp.get("size", 0) for sp in ln["spans"]])))
        if not blocks:
            continue
        page_txt = " ".join(b["txt"] for b in blocks)

        # chuyen mode theo moc noi dung
        if "References" in page_txt or "Tài liệu tham khảo" in page_txt:
            mode = "refs"
        if "Tóm tắt" in page_txt:
            mode = "viet"

        in_area = [b for b in blocks if TOP < b["y0"] < BOTTOM and b["x0"] >= LEFT - 0.4]
        # phan loai tung dong
        cls = Counter()
        area = Counter()
        for b in in_area:
            a = max(0.02, (b["x1"] - b["x0"]) * 0.42)      # uoc tinh cm2 cua dong
            h = 0.42                                        # chieu cao dong ~0.42cm
            a = (b["x1"] - b["x0"]) * h
            t = b["txt"]
            frac_math = sum(1 for c in t if c in MATHCH) / max(1, len(t))
            centered = abs((b["x0"] + b["x1"]) / 2 - 9.5) < 1.2
            short = len(t.split()) <= 10
            if re.match(r"^(Table|Fig\.|Figure)\s*\d+[.:]", t):
                k = "caption"
            elif frac_math > 0.10 or (centered and not b["x1"] > RIGHT - 2.0 and short):
                k = "math"
            elif short and not b["x1"] > RIGHT - 3.0 and "&" not in t:
                k = "table?"
            else:
                k = "prose"
            cls[k] += 1
            area[k] += a
        nword = len(re.findall(r"\S+", page_txt))
        rows.append(dict(page=pno, mode=mode, nword=nword, cls=cls, area=area,
                         ytop=min(b["y0"] for b in in_area),
                         ybot=max(b["y1"] for b in in_area)))

    # tong hop theo mode
    print(f"  {'tr':>3} {'tu':>5} {'mode':<6} {'prose':>6} {'math':>5} {'tbl?':>5} {'cap':>4}"
          f" | dien tich cm2 (prose/math/tbl)")
    tot = Counter()
    for r in rows:
        a = r["area"]
        print(f"  {r['page']:>3} {r['nword']:>5} {r['mode']:<6} "
              f"{r['cls']['prose']:>6} {r['cls']['math']:>5} {r['cls']['table?']:>5} "
              f"{r['cls']['caption']:>4} | {a['prose']:5.0f}/{a['math']:4.0f}/{a['table?']:4.0f}")
        for k, v in a.items():
            tot[(r["mode"], k)] += v
    print("\n=== TONG DIEN TICH THEO LOAI (cm2, vung chu 345 cm2/trang) ===")
    by_mode = Counter()
    for (mode, k), v in tot.items():
        by_mode[mode] += v
        print(f"  {mode:<6} {k:<9} {v:7.0f} cm2  = {v/TEXT_AREA_CM2:5.2f} trang")
    print("\n  --- theo mode ---")
    for mode, v in by_mode.most_common():
        print(f"  {mode:<6} {v:7.0f} cm2 = {v/TEXT_AREA_CM2:5.2f} trang "
              f"({100*v/sum(by_mode.values()):.0f}% bai)")
    doc.close()
    return rows, by_mode


if __name__ == "__main__":
    analyse(PDF)

#!/usr/bin/env python3
"""Verify front matter + heading — BAN SUA HAI LOI DO CUA CHINH CONG CU.

Hai loi o ban truoc (khien ca 2 bai DA XUAT BAN cung bi bao FAIL -> chac chan la
cong cu sai, khong phai tai lieu sai):

  LOI 1 (muc C): pham vi abstract lay p1[ia:ik+3] tuc Keywords + 3 DONG, nuot ca
    heading '1 Introduction' ngay sau. Cot 'co chu' lo ra thu pham:
    [(9.0, 18), (12.0, 1)] -> 1 dong 12.0pt = heading. Heading bat dau o x=2.00cm
    (khong thut) nen keo min x0 tu 3.00 xuong 2.00 -> bao "FAIL khong thut 1cm".
    SUA: chi tinh dong co co chu ABSTRACT (9pt), va dung lai TAI Keywords, khong
    cong them 3 dong.

  LOI 2 (muc D): PyMuPDF tach heading thanh HAI DONG rieng ('1' va 'Introduction')
    vi khoang cach labelsep lon. Nen d['txt'] chi la '1' va chua he do duoc cho
    CHU bat dau. SUA: gop cac dong cung y (dung sai 0.15cm) roi do x0 cua phan chu.

Moc so sanh van la 2 bai da xuat ban, cung mot thuong do, de tranh tu cham diem.
"""
from __future__ import annotations

import re
import statistics
from collections import Counter

import fitz

PT = 28.3465
MID = 9.5                       # tam vung chu 2.00..17.00cm
BODY_X0, BODY_X1 = 2.00, 17.00  # vung chu that, do tu bai da xuat ban
DOCS = [("/tmp/hujos_col/published_0.pdf", "DA XUAT BAN #1"),
        ("/tmp/hujos_col/published_1.pdf", "DA XUAT BAN #2"),
        ("/media/SAS/Van/DeTai2025/TwinGate_K1/paper2_hujos/main_hujos.pdf", "BAN EM")]

RE_NUM_ONLY = re.compile(r"^\d{1,2}$")
RE_TITLE_AFTER_NUM = re.compile(r"^[A-Z][A-Za-z]")


def get_lines(page, ymin=0.0, ymax=99.0):
    out = []
    for blk in page.get_text("dict").get("blocks", []):
        if blk.get("type") != 0:
            continue
        for ln in blk.get("lines", []):
            spans = ln.get("spans", [])
            txt = "".join(s.get("text", "") for s in spans).strip()
            if not txt:
                continue
            b = ln["bbox"]
            y = b[1] / PT
            if not (ymin <= y <= ymax):
                continue
            out.append(dict(y=y, x0=b[0] / PT, x1=b[2] / PT, txt=txt,
                            mid=(b[0] + b[2]) / 2 / PT,
                            size=statistics.median([s.get("size", 0) for s in spans]),
                            font=Counter(s.get("font", "") for s in spans).most_common(1)[0][0]))
    return sorted(out, key=lambda d: (d["y"], d["x0"]))


def merge_same_y(rows, tol=0.15):
    """LOI 2: gop cac dong cung y (PyMuPDF tach nhan va chu heading thanh 2 dong)."""
    out = []
    for r in rows:
        if out and abs(r["y"] - out[-1]["y"]) <= tol:
            p = out[-1]
            p["x1"] = max(p["x1"], r["x1"])
            p["x0"] = min(p["x0"], r["x0"])
            p["txt"] = (p["txt"] + " " + r["txt"]).strip()
            p["mid"] = (p["x0"] + p["x1"]) / 2
            p["size"] = max(p["size"], r["size"])
        else:
            out.append(dict(r))
    return out


def probe(pdf, lab):
    doc = fitz.open(pdf)
    p1 = get_lines(doc[0])
    res = {}
    print("=" * 88)
    print(f"{lab}  ({doc.page_count} trang)")

    ia = next((i for i, d in enumerate(p1) if d["txt"].startswith("Abstract")), None)
    ik = next((i for i, d in enumerate(p1) if d["txt"].startswith("Keywords")), None)
    if ia is None or ik is None:
        print("  KHONG tim thay moc Abstract/Keywords -> bo qua")
        doc.close()
        return res

    # ---------- A+B) authors / affiliations: canh giua? ----------
    seg = [d for d in p1[1:ia] if d["size"] < 13 and d["y"] > 2.6]   # bo header + title
    mids = [d["mid"] for d in seg]
    cent = sum(1 for m in mids if abs(m - MID) < 0.9)
    res["center"] = (cent, len(seg), statistics.median(mids) if mids else 0)
    print(f"\n  A+B) authors/affil: {len(seg)} dong | canh giua {cent}/{len(seg)} | "
          f"mid {res['center'][2]:.2f}cm")
    for d in seg[:4]:
        print(f"       y={d['y']:5.2f} x=[{d['x0']:5.2f},{d['x1']:5.2f}] mid={d['mid']:5.2f} "
              f"sz={d['size']:.1f} {'CENTER' if abs(d['mid']-MID)<0.9 else 'LEFT'} | {d['txt'][:44]}")
    res["A_ok"] = cent >= max(1, len(seg) * 0.6)

    # ---------- C) abstract inset: CHI dong 9pt, DUNG tai Keywords ----------
    # Lay cac dong tu Abstract den het khoi Keywords (Keywords co the trai 2 dong),
    # roi loc bo moi dong co co chu khac co chu pho bien cua khoi (heading 12pt).
    block = p1[ia:]
    sizes = Counter(round(d["size"], 1) for d in block)
    abs_size = sizes.most_common(1)[0][0]
    keep, stop = [], False
    for d in block:
        if round(d["size"], 1) != abs_size:      # heading 12pt xen vao -> dung
            stop = True
            continue
        if stop and d["y"] > block[ik]["y"] + 1.5:
            break
        keep.append(d)
        if len(keep) > 2 and not d["txt"].startswith(("Abstract", "Keywords")) \
           and d["y"] > block[ik]["y"] + 1.5:
            break
    x0 = [d["x0"] for d in keep]
    x1 = [d["x1"] for d in keep if d["x1"] - d["x0"] > 2.0]     # bo dong cuoi ngan
    li = min(x0) - BODY_X0
    ri = BODY_X1 - max(x1)
    res["C"] = (len(keep), abs_size, min(x0), max(x1), li, ri)
    print(f"\n  C) abstract: {len(keep)} dong @ {abs_size}pt | x = [{min(x0):.2f}, {max(x1):.2f}] cm")
    print(f"     inset trai = {li:+.2f}cm | inset phai = {ri:+.2f}cm  (mong doi ~1.00cm)")
    res["C_ok"] = 0.7 <= li <= 1.35 and 0.7 <= ri <= 1.35 and abs(abs_size - 9.0) < 0.6

    # ---------- D) section heading: nhan o 2.00, chu bat dau o dau? ----------
    print("\n  D) section heading (nhan 'N' vs cho CHU bat dau):")
    found = []
    for pg in range(min(doc.page_count, 8)):
        rows = merge_same_y(get_lines(doc[pg], 2.3, 25.0))
        for d in rows:
            if d["size"] < 11 or len(d["txt"].split()) > 10:
                continue
            m = re.match(r"^(\d{1,2})\s+([A-Z].*)$", d["txt"])
            if not m:
                continue
            # do x0 cua PHAN CHU: tim span dau tien khong phai so
            spans = []
            for blk in doc[pg].get_text("dict")["blocks"]:
                if blk.get("type") != 0:
                    continue
                for ln in blk["lines"]:
                    if abs(ln["bbox"][1] / PT - d["y"]) < 0.2:
                        spans += [(s["text"], s["bbox"][0] / PT, s["bbox"][2] / PT)
                                  for s in ln["spans"]]
            num_sp = [sp for sp in spans if RE_NUM_ONLY.match(sp[0].strip())]
            txt_sp = [sp for sp in spans if sp[0].strip() and not RE_NUM_ONLY.match(sp[0].strip())]
            nx1 = max((sp[2] for sp in num_sp), default=d["x0"])
            tx0 = min((sp[1] for sp in txt_sp), default=None)
            found.append((pg + 1, d["y"], d["x0"], nx1, tx0, m.group(2)[:34]))
    for pg, y, x0, nx1, tx0, t in found[:4]:
        gap = (tx0 - nx1) if tx0 is not None else None
        print(f"     tr{pg} y={y:5.2f} nhan x0={x0:.2f} het nhan {nx1:.2f} "
              f"chu bat dau {tx0 if tx0 is None else round(tx0,2)} "
              f"gap={gap if gap is None else round(gap,2)}cm | {t}")
    txs = [f[4] for f in found if f[4] is not None]
    res["D_txt_x0"] = statistics.median(txs) if txs else None
    if txs:
        print(f"     => chu heading bat dau tai {statistics.median(txs):.2f}cm "
              f"(bai da dang: 3.00cm)")
    doc.close()
    return res


print("Do lai sau khi sua 2 loi cua cong cu do. Moi muc phai ra SO.\n")
allres = {}
for pdf, lab in DOCS:
    try:
        allres[lab] = probe(pdf, lab)
    except Exception as e:
        print(f"{lab}: LOI {type(e).__name__}: {e}")
    print()

print("=" * 88)
print("DOI CHIEU 3 TAI LIEU CUNG MOT THUONG DO")
print("=" * 88)
pub = [allres[k] for k in allres if k.startswith("DA XUAT BAN") and allres[k]]
mine = allres.get("BAN EM", {})
if pub and mine:
    print(f"  abstract size : da dang {[p['C'][1] for p in pub]} | em {mine['C'][1]}")
    print(f"  abstract x0   : da dang {[round(p['C'][2],2) for p in pub]} | em {round(mine['C'][2],2)}")
    print(f"  abstract x1   : da dang {[round(p['C'][3],2) for p in pub]} | em {round(mine['C'][3],2)}")
    print(f"  inset (L,R)   : da dang {[(round(p['C'][4],2),round(p['C'][5],2)) for p in pub]} | "
          f"em ({round(mine['C'][4],2)},{round(mine['C'][5],2)})")
    print(f"  affil mid     : da dang {[round(p['center'][2],2) for p in pub]} | "
          f"em {round(mine['center'][2],2)}")
    print(f"  heading chu x0: da dang {[None if p['D_txt_x0'] is None else round(p['D_txt_x0'],2) for p in pub]} | "
          f"em {None if mine.get('D_txt_x0') is None else round(mine['D_txt_x0'],2)}")
    print(f"\n  GATE authors/affil center : {'PASS' if mine.get('A_ok') else 'FAIL'}")
    print(f"  GATE abstract inset+9pt   : {'PASS' if mine.get('C_ok') else 'FAIL'}")
    dt = [p["D_txt_x0"] for p in pub if p.get("D_txt_x0")]
    if dt and mine.get("D_txt_x0"):
        d = abs(statistics.median(dt) - mine["D_txt_x0"])
        print(f"  GATE heading chu x0       : {'PASS' if d < 0.2 else 'FAIL'} "
              f"(lech {d:.2f}cm so voi bai da dang)")

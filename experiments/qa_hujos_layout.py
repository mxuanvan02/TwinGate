#!/usr/bin/env python3
"""Gate layout ban HUJOS: so cot, pitch, section->trang, ngan sach trang.

BAI HOC (mac 4 lan trong cung mot session): KHONG de regex chua backslash ben
trong f-string. Python bao:
    SyntaxError: f-string expression part cannot include a backslash
Cach chua: tinh ra bien TRUOC, roi moi dua bien vao f-string. Vi vay file nay
dinh nghia  RE_WS  o cap module va moi cho dem tu dung  wc(p)  -> khong co
backslash nao nam trong phan bieu thuc cua f-string.

Hai gate duoc sua vi ban cu cho ket qua SAI:
  1. Gate "1 cot" cu grep chuoi '\\twocolumn' trong main_hujos.tex -> FAIL, vi chuoi
     do con nam trong DONG COMMENT viet de giai thich ly do bo no. Gate tu ban vao
     chan minh. Ban moi: bo comment bang regex truoc khi tim, VA do dai giua trang
     tren PDF that (chu bat dau trong dai giua trang > 8% = mot cot; ban hai cot
     chi ~5% vi ranh cot trong).
  2. Gate "parskip" cu do tu PDF cua bai bang pdftotext/PyMuPDF -> false negative,
     vi ca hai cong cu deu loai dong ngan ma dong cuoi doan luon ngan. Dung
     probe_parskip.tex (chi co lipsum) thi do duoc +2.99pt, khop 3pt da dat.
"""
from __future__ import annotations

import re
import statistics
import subprocess
from pathlib import Path

H = Path("/media/SAS/Van/DeTai2025/TwinGate_K1/paper2_hujos")
BLOCKS = H.parent / "paper2" / "blocks"
PT = 28.3465                      # 1 cm = 28.3465 pt
LEFT, RIGHT = 2.00, 17.00         # vung chu 19cm - le 2cm, do tu bai da xuat ban

RE_WORD = re.compile(
    r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)</word>')
RE_PAGE = re.compile(r'<page width="([\d.]+)" height="([\d.]+)">(.*?)</page>', re.S)
RE_PCT = re.compile(r"\s+")
RE_SEC_LABEL = re.compile(r"\\newlabel\{(sec:[^}]+)\}\{\{([^}]*)\}\{(\d+)\}")
RE_SEC_TITLE = re.compile(r"\\(?:sub)?section\{([^}]*)\}\s*\n?\s*\\label\{(sec:[^}]+)\}")
RE_SEC_TITLE_REV = re.compile(r"\\label\{(sec:[^}]+)\}\s*\n?\s*\\(?:sub)?section\{([^}]*)\}")


def wc(text):
    """Dem tu. KHONG goi truc tiep trong f-string (chua backslash)."""
    return len(RE_PCT.sub(" ", text).split())


def bbox_pages(pdf):
    bb = subprocess.run(["pdftotext", "-bbox", str(pdf), "-"],
                        capture_output=True, text=True).stdout
    return [(float(w), float(h), body) for w, h, body in RE_PAGE.findall(bb)]


# ---------------------------------------------------------------- 1) SO COT
def col_share(pdf, lo, hi, label):
    """Ty le chu BAT DAU trong dai ngang [lo,hi) cm, bo header/footer."""
    inband = total = 0
    for _pw, _ph, body in bbox_pages(pdf):
        xs = [(float(m.group(1)), float(m.group(2))) for m in RE_WORD.finditer(body)]
        xs = [(x, y) for x, y in xs if 2.3 * PT < y < 25.0 * PT]
        if len(xs) < 40:
            continue
        inband += sum(1 for x, _ in xs if lo <= x / PT < hi)
        total += len(xs)
    pct = 100 * inband / total if total else 0
    verdict = "MOT COT" if pct > 8 else "HAI COT"
    print(f"  {label}: {pct:5.1f}% chu bat dau trong dai {lo}..{hi}cm -> {verdict}")
    return pct, verdict


print("=== GATE 1: SO COT (do tren PDF that) ===")
mine_pct, mine_verdict = col_share(H / "main_hujos.pdf", 8.0, 11.0, "BAN EM      ")
p1_pct, _ = col_share("/tmp/hujos_col/published_0.pdf", 8.0, 11.0, "DA XUAT BAN #1")
p2_pct, _ = col_share("/tmp/hujos_col/published_1.pdf", 8.0, 11.0, "DA XUAT BAN #2")

src = (H / "main_hujos.tex").read_text(encoding="utf-8")
stripped = re.sub(r"(?m)%.*$", "", src)          # bo comment roi moi tim lenh that
n_raw = src.count("\\twocolumn")
n_real = stripped.count("\\twocolumn")
print(f"\n  grep nguon: '\\twocolumn' = {n_raw} lan | sau khi bo COMMENT = {n_real} lan")
print(f"  => gate cu FAIL vi thay chu '\\twocolumn' trong COMMENT giai thich ly do bo no")
col_ok = (mine_verdict == "MOT COT" and n_real == 0)
print(f"  GATE 1: {'PASS' if col_ok else 'FAIL'}  "
      f"(ban em {mine_pct:.1f}% vs bai da dang {p1_pct:.1f}%/{p2_pct:.1f}%)")

# ---------------------------------------------------------------- 2) PDF metrics
raw = subprocess.run(["pdftotext", "-raw", str(H / "main_hujos.pdf"), "-"],
                     capture_output=True, text=True).stdout
pages = [p for p in raw.split("\f") if p.strip()]
NP = len(pages)
info = subprocess.run(["pdfinfo", str(H / "main_hujos.pdf")],
                      capture_output=True, text=True).stdout
log = (H / "main_hujos.log").read_text(encoding="utf-8", errors="replace")

m = re.search(r"Page size:\s+([\d.]+) x ([\d.]+)", info)
pw_cm, ph_cm = float(m.group(1)) / PT, float(m.group(2)) / PT
print(f"\n=== GATE 2: HINH HOC ===")
print(f"  {NP} trang | {pw_cm:.2f} x {ph_cm:.2f} cm | "
      f"{'PASS' if abs(pw_cm-19)<0.05 and abs(ph_cm-27)<0.05 else 'FAIL'} kho 19x27cm")
ov = [float(x) for x in re.findall(r"Overfull \\hbox \((\d+\.\d+)pt", log)]
ovbig = [x for x in ov if x > 15]
print(f"  overfull hbox: tong {len(ov)} | >15pt {len(ovbig)} | "
      f"nang nhat {max(ov, default=0):.2f}pt")
print(f"  underfull vbox: {log.count('Underfull ' + chr(92) + 'vbox')} "
      f"(0 = raggedbottom dang an)")
print(f"  fatal: {len(re.findall(r'^! ', log, re.M))} | "
      f"missing char: {log.count('Missing character')}")

# ---------------------------------------------------------------- 3) SECTION -> TRANG
print("\n=== SECTION -> TRANG (GROUND TRUTH tu main_hujos.aux) ===")
aux = (H / "main_hujos.aux").read_text(encoding="utf-8", errors="replace")
secs = [(k, v, int(pg)) for k, v, pg in RE_SEC_LABEL.findall(aux)]
secs.sort(key=lambda x: (x[2], x[1]))
names = {}
for f in sorted(BLOCKS.glob("*.tex")):
    t = f.read_text(encoding="utf-8", errors="replace")
    for m2 in RE_SEC_TITLE.finditer(t):
        names[m2.group(2)] = m2.group(1)
    for m2 in RE_SEC_TITLE_REV.finditer(t):
        names[m2.group(1)] = m2.group(2)

ref_pg = next((i for i, p in enumerate(pages, 1) if "References" in p), NP + 1)
vi_pg = next((i for i, p in enumerate(pages, 1) if "Tóm tắt" in p), NP + 1)
end_body = min(ref_pg, vi_pg) - 1

print(f"  {'so':>5}  {'label':<22} {'trang':<9} {'tu':>5}  ten muc")
for i, (k, num, pg) in enumerate(secs):
    nxt = secs[i + 1][2] if i + 1 < len(secs) else end_body
    end = max(pg, min(nxt - 1, end_body))
    span = f"tr{pg}-{end}" if end > pg else f"tr{pg}"
    w = 0
    for p in range(pg, end + 1):
        if 1 <= p <= NP:
            w += wc(pages[p - 1])
    nm = names.get(k, "")
    print(f"  {num:>5}  {k:<22} {span:<9} {w:>5}  {nm[:46]}")

# ---------------------------------------------------------------- 4) NGAN SACH TRANG
print("\n=== NGAN SACH TRANG ===")
tot_w = 0
for p in pages:
    tot_w += wc(p)
body_w = 0
for p in range(1, end_body + 1):
    body_w += wc(pages[p - 1])
refs_w = 0
for p in range(ref_pg, NP + 1):
    refs_w += wc(pages[p - 1])
vi_w = 0
for p in range(vi_pg, NP + 1):
    vi_w += wc(pages[p - 1])
print(f"  tong           : {NP} trang | {tot_w} tu")
print(f"  than bai (EN)  : tr1-{end_body} | {body_w} tu")
print(f"  khoi tieng Viet: tr{vi_pg}-{NP} | {vi_w} tu")
print(f"  References     : tr{ref_pg}-{NP} | {refs_w} tu")
print(f"\n  bai da dang HUJOS-TT: 14 trang/5221 tu va 13 trang/3863 tu (trung vi 4542 tu)")
ratio = tot_w / 4542
print(f"  bai minh = {ratio:.2f}x bai dien hinh cua tap chi")
print(f"  quy dinh toi da 12 trang -> can bot {NP - 12} trang ({100 * (NP - 12) // NP}%)")
print(f"  muc bai da dang 14 trang -> can bot {NP - 14} trang ({100 * (NP - 14) // NP}%)")
print("\n  KHOI CO THE CAT NGAY, kem bang chung:")
print(f"   a) khoi tieng Viet cuoi bai = {vi_w} tu ({100 * vi_w // tot_w}%), ~{NP - vi_pg + 1} trang")
print("      ca 2 bai tieng Anh da dang deu KHONG co khoi nay (da kiem tra 15/15 trang)")
print("      nhung Author Guidelines muc 3 yeu cau 'abstract and keywords in")
print("      Vietnamese and English' -> MAU THUAN, can anh quyet")
print(f"   b) References = {refs_w} tu (~{NP - ref_pg + 1} trang), da toi gian, kho cat")

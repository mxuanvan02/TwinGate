#!/usr/bin/env python3
"""Buoc 3/3: rap ban .docx hoan chinh de nop HUJOS-TT.

Lam dung 5 viec ma skill latex-to-venue-word-template yeu cau o buoc 5:
  1. prepend front matter, dung NATIVELY tu gia tri that trong front.tex
     (khong bao gio sinh metadata — luat 1 cua skill)
  2. bien moi marker "EQNUM: n" thanh tab canh phai + so trong ngoac tren CUNG
     dong voi cong thuc (m:oMathPara -> m:oMath de so nam cung dong)
  3. ep do rong bang: tblW dxa = het vung chu, tblLayout fixed, gridCol theo
     DUNG ti le p{...} cua LaTeX (pandoc da vo hieu hoa ti le nay: do that thay
     5 cot deu 1584 twip trong khi spec la 2.85/0.95/1.05/0.95/2.20 cm)
  4. them References tu main_hujos.bbl, moi \\bibitem mot paragraph, hanging
     indent, "--" -> en dash
  5. thay sectPr trong OUTPUT (sectPr cua reference khong song sot tin cay)

 Moi w:pPr duoc dung MOI theo dung thu tu schema (pStyle, keepNext, tabs,
 spacing, ind, jc, outlineLvl). Them con vao pPr co san se tao XML sai thu tu ma
 Word/LibreOffice tu choi.
"""
from __future__ import annotations

import copy          # can cho deepcopy khi chen node tu cay XML khac (front.docx)
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

from lxml import etree

H = Path("/media/SAS/Van/DeTai2025/TwinGate_K1/paper2_hujos")
BUILD = H / "docx_build"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
NS_W = f"{{{W}}}"
NS_M = f"{{{M}}}"

PGSZ_W, PGSZ_H = 10772, 15307          # 19 x 27 cm  (do tu template + bai da xuat ban)
MARGIN = 1134                          # 2 cm
HDRFTR = 708                           # 1.25 cm
TEXT_W = PGSZ_W - 2 * MARGIN           # 8504 twip = 15.00 cm
COL_SPACE = 708
CM_TWIP = 567.0

report = []


def rep(m):
    report.append(m)
    print(m)


def sub(parent, tag, **attrs):
    e = etree.SubElement(parent, NS_W + tag)
    for k, v in attrs.items():
        e.set(NS_W + k, str(v))
    return e


def clear(parent, tags):
    for t in tags:
        for e in parent.findall(NS_W + t):
            parent.remove(e)


def fresh_ppr(p, *, style=None, jc=None, ind_left=None, ind_hanging=None,
              before=None, after=None, line=276, tabs_right=None, keepnext=False):
    """Dung w:pPr MOI theo dung thu tu schema."""
    old = p.find(NS_W + "pPr")
    if old is not None:
        p.remove(old)
    ppr = etree.Element(NS_W + "pPr")
    p.insert(0, ppr)
    if style:
        sub(ppr, "pStyle", val=style)
    if keepnext:
        sub(ppr, "keepNext")
    if tabs_right is not None:
        tabs = sub(ppr, "tabs")
        t = sub(tabs, "tab", val="right", pos=tabs_right)
    if before is not None or after is not None or line is not None:
        sp = sub(ppr, "spacing")
        if before is not None:
            sp.set(NS_W + "before", str(before))
        if after is not None:
            sp.set(NS_W + "after", str(after))
        if line is not None:
            sp.set(NS_W + "line", str(line))
            sp.set(NS_W + "lineRule", "auto")
    if ind_left is not None or ind_hanging is not None:
        ind = sub(ppr, "ind")
        if ind_left is not None:
            ind.set(NS_W + "left", str(ind_left))
        if ind_hanging is not None:
            ind.set(NS_W + "hanging", str(ind_hanging))
    if jc:
        sub(ppr, "jc", val=jc)
    return ppr


def ptext(el):
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip()


# ---------------------------------------------------------------- 1) doc body
SRC = BUILD / "body.docx"
assert SRC.exists(), f"thieu {SRC} — chay build_ref.py truoc"
WORK = BUILD / "out_src"
if WORK.exists():
    shutil.rmtree(WORK)
WORK.mkdir()
with zipfile.ZipFile(SRC) as z:
    z.extractall(WORK)

doc_p = WORK / "word" / "document.xml"
tree = etree.parse(str(doc_p))
root = tree.getroot()
body = root.find(NS_W + "body")
rep(f"[1] body.docx: {len(list(body))} child cap 1")

# ---------------------------------------------------------------- 2) EQNUM -> tab phai
kids = list(body)
eq_marks = [(i, el) for i, el in enumerate(kids)
            if el.tag == NS_W + "p" and re.fullmatch(r"EQNUM: \d+", ptext(el))]
rep(f"[2] tim thay {len(eq_marks)} marker EQNUM")
assert len(eq_marks) == 26, f"mong 26 EQNUM, thay {len(eq_marks)}"

merged = 0
for idx, mark in reversed(eq_marks):          # di nguoc de index khong lech
    n = re.fullmatch(r"EQNUM: (\d+)", ptext(mark)).group(1)
    # tim paragraph chua display math ngay truoc (toi da lui 3 buoc)
    target = None
    for j in range(idx - 1, max(-1, idx - 4), -1):
        el = kids[j]
        if el.tag == NS_W + "p" and el.find(f".//{NS_M}oMathPara") is not None:
            target = el
            break
    assert target is not None, f"EQNUM {n}: khong tim thay oMathPara trong 3 paragraph truoc"

    # m:oMathPara -> m:oMath (de so nam CUNG dong voi cong thuc)
    omp = target.find(NS_M + "oMathPara")
    pos = list(target).index(omp)
    children = [c for c in omp if c.tag == NS_M + "oMath"]
    assert children, f"EQNUM {n}: oMathPara rong"
    target.remove(omp)
    for k, c in enumerate(children):
        target.insert(pos + k, c)

    # tab canh phai + (n)
    fresh_ppr(target, style="BodyText", tabs_right=TEXT_W,
              jc=None, before=120, after=60)
    r = etree.SubElement(target, NS_W + "r")
    etree.SubElement(r, NS_W + "tab")
    t = etree.SubElement(r, NS_W + "t")
    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    t.text = f"({n})"

    body.remove(mark)
    merged += 1
rep(f"[2] da ghep {merged}/26 so cong thuc vao tab canh phai tai {TEXT_W} twip")

# ---------------------------------------------------------------- 3) front matter
front = (BUILD / "front.tex").read_text(encoding="utf-8")


def grab(cmd, txt, nth=1):
    """Trich noi dung {} can bang ngoac cua \\cmd{...}."""
    pat = "\\" + cmd + "{"
    start = -1
    for _ in range(nth):
        start = txt.index(pat, start + 1)
    i = start + len(pat)
    depth, out = 1, []
    while i < len(txt) and depth:
        c = txt[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                break
        out.append(c)
        i += 1
    return "".join(out)


TITLE = " ".join(grab("hujostitle", front).split())
AUTHORS = " ".join(grab("hujosauthors", front).split())
AFFIL1 = grab("hujosaffil", front, 1)
AFFIL2 = grab("hujosaffil", front, 2)
i = front.index(r"\textbf{Abstract.}")
j = front.index(r"\noindent\textbf{Keywords:}")
ABSTRACT = front[i:j].replace(r"\noindent\textbf{Abstract.}", "").strip()
ABSTRACT = ABSTRACT.split(r"\vspace")[0].strip()
k = front.index(r"\textbf{Keywords:}", j)
KEYWORDS = front[k + len(r"\textbf{Keywords:}"):].split(r"\vspace")[0].strip()
rep(f"[3] front: title {len(TITLE)} chars | abstract {len(ABSTRACT.split())} tu | "
    f"keywords {len(KEYWORDS.split())} tu")

# Dung pandoc cho front matter de giu OMML that ($69\%$, $281$, $0.60$--$0.85$)
FRAG = BUILD / "front_frag.tex"
FRAG.write_text("\\documentclass[10pt]{article}\n\\usepackage{amsmath}\n\\begin{document}\n"
                + f"{TITLE}\n\n{AUTHORS}\n\n{AFFIL1}\n\n{AFFIL2}\n\n"
                + f"\\textbf{{Abstract.}} {ABSTRACT}\n\n"
                + f"\\textbf{{Keywords:}} {KEYWORDS}\n"
                + "\\end{document}\n", encoding="utf-8")
FRONT_DOCX = BUILD / "front.docx"
r = subprocess.run(["pandoc", str(FRAG), "-f", "latex", "-t", "docx",
                    f"--reference-doc={BUILD/'ref_venue.docx'}", "-o", str(FRONT_DOCX)],
                   capture_output=True, text=True, timeout=200)
assert r.returncode == 0, f"pandoc front fail: {r.stderr[:400]}"
rep(f"[3] pandoc front.docx OK | stderr: {r.stderr.strip()[:200] or '(trong)'}")

fz = zipfile.ZipFile(FRONT_DOCX)
froot = etree.fromstring(fz.read("word/document.xml"))
fbody = froot.find(NS_W + "body")
fparas = [el for el in fbody if el.tag == NS_W + "p"]
rep(f"[3] front.docx co {len(fparas)} paragraph")
assert len(fparas) == 6, f"mong 6 paragraph front (title/authors/affil1/affil2/abstract/keywords), thay {len(fparas)}"

STYLE_MAP = [("Title", "center"), ("Author", "center"), ("Abstract", "center"),
             ("Abstract", "center"), ("Abstract", "both"), ("Abstract", "both")]
sectpr = body.find(NS_W + "sectPr")          # lay TRUOC khi chen front matter
# LOI DA SUA: co mot dong code chet "body.insert(0, el) if False else None"
# (leftover tu ban nhap). Bo.
# LOI DA SUA (phong ngua): fparas thuoc CAY XML KHAC (front.docx). lxml/libxml2
# khong cho di chuyen node giua hai document -> phai deepcopy khi chen.
copies = [copy.deepcopy(el) for el in fparas]
for el, (sty, jc) in zip(copies, STYLE_MAP):
    fresh_ppr(el, style=sty, jc=jc, before=60, after=60)
# chen dung thu tu vao dau body (title -> keywords)
for k, el in enumerate(copies):
    body.insert(k, el)
rep(f"[3] da prepend {len(copies)} paragraph front matter vao dau body")

# ---------------------------------------------------------------- 4) do rong bang
body_tex = (BUILD / "body.tex").read_text(encoding="utf-8")
specs = re.findall(r"\\begin\{tabular\}\{(.*)\}", body_tex)
rep(f"[4] {len(specs)} spec tabular trong body.tex")


def col_widths_cm(spec: str):
    """Tokenize column spec LaTeX -> chieu rong cm moi cot.

    p{Xcm}/m{Xcm} -> X ; l/c/r -> 1.0 cm (dung uoc tinh cua generator:
    `w if w > 0 else 1.0` trong make_tables_anchored.table). Bo qua @{} va >{...}.
    """
    s = re.sub(r"@\{[^}]*\}", "", spec)
    s = re.sub(r">\{(?:[^{}]|\{[^{}]*\})*\}", "", s)
    s = re.sub(r"<\{[^}]*\}", "", s)
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c in "lcr":
            out.append(1.0)
            i += 1
        elif c in "pmb":
            m = re.match(r"[pmb]\{([^}]*)\}", s[i:])
            assert m, f"spec cot {c} khong co {{}}: {s[i:i+20]}"
            dim = m.group(1)
            v = re.match(r"([\d.]+)\s*cm", dim)
            assert v, f"don vi la: {dim}"
            out.append(float(v.group(1)))
            i += m.end()
        else:
            i += 1
    return out


tables = [el for el in body if el.tag == NS_W + "tbl"]
assert len(tables) == len(specs) == 8, (len(tables), len(specs))
for n, (tbl, spec) in enumerate(zip(tables, specs), 1):
    widths = col_widths_cm(spec)
    grid = tbl.find(NS_W + "tblGrid")
    gcols = grid.findall(NS_W + "gridCol")
    assert len(gcols) == len(widths), (
        f"bang {n}: gridCol {len(gcols)} != spec {len(widths)} cot ({spec[:60]})")
    tot_cm = sum(widths)
    twips = [int(round(w / tot_cm * TEXT_W)) for w in widths]
    # buoc sai so lam tron vao cot rong nhat de tong DUNG bang TEXT_W
    drift = TEXT_W - sum(twips)
    twips[twips.index(max(twips))] += drift

    # tblPr: tblW roi tblLayout (dung thu tu schema)
    tblpr = tbl.find(NS_W + "tblPr")
    clear(tblpr, ["tblW", "tblLayout"])
    style_el = tblpr.find(NS_W + "tblStyle")
    at = list(tblpr).index(style_el) + 1 if style_el is not None else 0
    tw = etree.Element(NS_W + "tblW")
    tw.set(NS_W + "type", "dxa")
    tw.set(NS_W + "w", str(TEXT_W))
    tblpr.insert(at, tw)
    lay = etree.Element(NS_W + "tblLayout")
    lay.set(NS_W + "type", "fixed")
    tblpr.insert(at + 1, lay)

    for gc, w in zip(gcols, twips):
        gc.set(NS_W + "w", str(w))
    ncell = 0
    for tr in tbl.findall(NS_W + "tr"):
        for k, tc in enumerate(tr.findall(NS_W + "tc")):
            if k >= len(twips):
                continue
            tcpr = tc.find(NS_W + "tcPr")
            if tcpr is None:
                tcpr = etree.Element(NS_W + "tcPr")
                tc.insert(0, tcpr)
            clear(tcpr, ["tcW"])
            cw = etree.Element(NS_W + "tcW")
            cw.set(NS_W + "type", "dxa")
            cw.set(NS_W + "w", str(twips[k]))
            cnf = tcpr.find(NS_W + "cnfStyle")
            tcpr.insert((list(tcpr).index(cnf) + 1) if cnf is not None else 0, cw)
            ncell += 1
    rep(f"[4] bang {n}: {len(widths)} cot {widths} cm -> {twips} twip "
        f"(tong {sum(twips)} = {TEXT_W}) | {ncell} o")

# ---------------------------------------------------------------- 5) References
bbl = (H / "main_hujos.bbl").read_text(encoding="utf-8", errors="replace")
items = re.split(r"\\bibitem(?:\[[^\]]*\])?\{[^}]*\}", bbl)[1:]
rep(f"[5] .bbl: {len(items)} bibitem")
assert len(items) == 24, len(items)


def clean_bib(s: str) -> str:
    s = s.replace("\\newblock", " ")
    s = re.sub(r"\\url\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\\emph\{([^}]*)\}", r"\1", s)
    s = s.replace("\\&", "&").replace("\\%", "%")
    s = s.replace("~", " ").replace("\\,", " ").replace("\\ ", " ")
    s = re.sub(r"\{([^{}]*)\}", r"\1", s)          # bo {} nhom cua BibTeX
    s = s.replace("--", "\u2013")                   # en dash
    s = re.sub(r"\s+", " ", s).strip()
    return s


h = etree.SubElement(body, NS_W + "p")
fresh_ppr(h, style="Heading1", before=240, after=120, keepnext=True)
r = etree.SubElement(h, NS_W + "r")
t = etree.SubElement(r, NS_W + "t")
t.text = "References"
for k, it in enumerate(items, 1):
    txt = clean_bib(it)
    assert txt, f"bibitem {k} rong"
    p = etree.SubElement(body, NS_W + "p")
    fresh_ppr(p, style="Bibliography", jc="both", ind_left=284, ind_hanging=284,
              before=0, after=60)
    rr = etree.SubElement(p, NS_W + "r")
    tt = etree.SubElement(rr, NS_W + "t")
    tt.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    tt.text = f"[{k}] {txt}"
rep(f"[5] them heading References + 24 paragraph (hanging indent 284 twip)")

# ---------------------------------------------------------------- 6) sectPr trong OUTPUT
if sectpr is not None:
    body.remove(sectpr)
SECT = (f'<w:sectPr xmlns:w="{W}">'
        f'<w:pgSz w:w="{PGSZ_W}" w:h="{PGSZ_H}"/>'
        f'<w:pgMar w:top="{MARGIN}" w:right="{MARGIN}" w:bottom="{MARGIN}" '
        f'w:left="{MARGIN}" w:header="{HDRFTR}" w:footer="{HDRFTR}" w:gutter="0"/>'
        f'<w:cols w:space="{COL_SPACE}"/><w:docGrid w:linePitch="360"/></w:sectPr>')
body.append(etree.fromstring(SECT))
rep(f"[6] sectPr OUTPUT: {PGSZ_W}x{PGSZ_H} twip = 19.00x27.00 cm, le 2cm, 1 cot")

tree.write(str(doc_p), xml_declaration=True, encoding="UTF-8", standalone=True)

# ---------------------------------------------------------------- 7) zip lai
OUT = BUILD / "HUJOS_manuscript_device_anchored.docx"
if OUT.exists():
    OUT.unlink()
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    for p in sorted(WORK.rglob("*")):
        if p.is_file():
            z.write(p, p.relative_to(WORK).as_posix())
rep(f"[7] {OUT.name}: {OUT.stat().st_size} bytes")

# ---------------------------------------------------------------- 8) QA render
qa = H / "qa_docx"
if qa.exists():
    shutil.rmtree(qa)
qa.mkdir()
r = subprocess.run(["soffice", "--headless", "--convert-to", "pdf", str(OUT),
                    "--outdir", str(qa)], capture_output=True, text=True, timeout=500)
rep(f"[8] soffice exit={r.returncode} | {r.stdout.strip()[:120] or r.stderr.strip()[:120]}")
pdf = qa / (OUT.stem + ".pdf")
if pdf.exists():
    info = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
    rep("[8] " + " | ".join(l.strip() for l in info.split("\n")
                            if l.startswith(("Pages", "Page size"))))
else:
    rep(f"[8] CANH BAO: khong render duoc PDF ({qa})")

(BUILD / "step3_report.txt").write_text("\n".join(report), encoding="utf-8")
print(f"\n=== XONG BUOC 3: {OUT} ===")

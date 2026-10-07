#!/usr/bin/env python3
"""Buoc 2/3: dung --reference-doc cho pandoc, voi typography HUJOS-TT.

LUAT CUA SKILL (latex-to-venue-word-template, buoc 4): "Start from pandoc's OWN
default, never from the venue template". Ly do (references/pandoc-latex-to-docx-traps.md,
trap 1 va 2): template cua tap chi khong co cac style ma pandoc can
(BodyText, FirstParagraph, Compact, TableCaption, Bibliography...), nen dung no
lam reference se khien pandoc roi xuong docDefaults va mat het dinh dang.

MOI con so hinh hoc o day deu DA DO, khong dat ra (xem scan_docx_geom.py va
phep do 2 bai da xuat ban):
  pgSz  10772 x 15307 twip = 19.00 x 27.00 cm
  pgMar 1134 twip = 2.00 cm ca bon ben; header/footer 708 = 1.25 cm
  cols  1 cot (khong co w:num), w:space=708
  text width = 10772 - 1134 - 1134 = 8504 twip = 15.00 cm
  font  Palatino Linotype (docDefaults trong ca 3 file template)
  body  line 276 (=1.15), before 120 (=6pt), after 60 (=3pt)
  Heading1 12pt bold, before 360 twip (=18pt), after 240 (=12pt)
  Heading2 10pt bold, before 18pt, after 8pt
  Title  14pt bold (28 half-pt trong template NS; giu 14pt cho TT)

TRAP 4 cua skill: "docDefaults alone does NOT win: BodyText carries its own
<w:spacing> that overrides it" -> phai va tung style ma pandoc that su phat ra.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import zipfile
from pathlib import Path

from lxml import etree

H = Path("/media/SAS/Van/DeTai2025/TwinGate_K1/paper2_hujos")
BUILD = H / "docx_build"
BUILD.mkdir(exist_ok=True)
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W}

# ---------------------------------------------------------------- geometry
PGSZ_W, PGSZ_H = 10772, 15307          # 19 x 27 cm
MARGIN = 1134                          # 2 cm
HDRFTR = 708                           # 1.25 cm
TEXT_W = PGSZ_W - 2 * MARGIN           # 8504 twip = 15.00 cm
COL_SPACE = 708

# ---------------------------------------------------------------- typography
FONT = "Palatino Linotype"
SZ_BODY = 20          # half-points -> 10 pt
SZ_H1 = 24            # 12 pt
SZ_TITLE = 28         # 14 pt
SZ_SMALL = 18         # 9 pt (abstract/affil/caption)
LINE = 276            # 1.15
BEFORE = 120          # 6 pt
AFTER = 60            # 3 pt
H1_BEFORE, H1_AFTER = 360, 240          # 18 pt / 12 pt
H2_BEFORE, H2_AFTER = 360, 160          # 18 pt / 8 pt

# ---------------------------------------------------------------- 1) ref base
BASE = BUILD / "ref_base.docx"
r = subprocess.run(["pandoc", "--print-default-data-file", "reference.docx"],
                   capture_output=True, timeout=120)
BASE.write_bytes(r.stdout)
# LOI DA SUA: assert len(r.stdout) > 20000 la NGUONG DOAN. Default reference.docx
# cua pandoc 3.1.3 chi 10214 bytes nhung la docx HOP LE (16 parts, 37 style,
# du 18/18 style ma pipeline nay can). Kiem tra tinh hop le that, khong doan kich thuoc.
import zipfile as _zf
_need = ["word/document.xml", "word/styles.xml", "word/settings.xml"]
assert r.returncode == 0, f"pandoc exit {r.returncode}"
try:
    _names = _zf.ZipFile(BASE).namelist()
except Exception as e:
    raise SystemExit(f"reference.docx khong phai zip hop le: {e}")
_missing = [k for k in _need if k not in _names]
assert not _missing, f"reference.docx thieu parts: {_missing} (co {_names})"
_st = _zf.ZipFile(BASE).read("word/styles.xml").decode("utf-8", "replace")
_ids = set(re.findall(r'w:styleId="([^"]+)"', _st))
_want = {"Normal", "BodyText", "FirstParagraph", "Compact", "Heading1",
         "Heading2", "Title", "Caption", "TableCaption", "Bibliography"}
_assert_missing = sorted(_want - _ids)
assert not _assert_missing, f"reference.docx thieu style: {_assert_missing}"
print(f"[1] pandoc default reference.docx: {BASE.stat().st_size} bytes | "
      f"{len(_names)} parts | {len(_ids)} style | du {_want & _ids} ")

# ---------------------------------------------------------------- 2) patch styles.xml
src = BUILD / "ref_src"
if src.exists():
    shutil.rmtree(src)
src.mkdir()
with zipfile.ZipFile(BASE) as z:
    z.extractall(src)

styles_p = src / "word" / "styles.xml"
tree = etree.parse(str(styles_p))
root = tree.getroot()

# styleId -> (sz half-pt, bold, before, after, line, jc, outlineLvl)
SPEC = {
    "Normal":          (SZ_BODY, False, BEFORE, AFTER, LINE, None, None),
    "BodyText":        (SZ_BODY, False, BEFORE, AFTER, LINE, "both", None),
    "FirstParagraph":  (SZ_BODY, False, BEFORE, AFTER, LINE, "both", None),
    "Compact":         (SZ_BODY, False, 0, 0, LINE, None, None),
    "Heading1":        (SZ_H1, True, H1_BEFORE, H1_AFTER, LINE, None, 0),
    "Heading2":        (SZ_BODY, True, H2_BEFORE, H2_AFTER, LINE, None, 1),
    "Heading3":        (SZ_BODY, True, 240, 0, LINE, None, 2),
    "Title":           (SZ_TITLE, True, 0, 240, LINE, "center", None),
    "Subtitle":        (SZ_BODY, False, 0, 240, LINE, "center", None),
    "Author":          (SZ_BODY, True, 120, 60, LINE, "center", None),
    "Date":            (SZ_BODY, False, 0, 120, LINE, "center", None),
    "Abstract":        (SZ_SMALL, False, BEFORE, AFTER, LINE, "both", None),
    "Caption":         (SZ_SMALL, False, 0, 120, LINE, "both", None),
    "TableCaption":    (SZ_SMALL, False, 0, 60, LINE, "both", None),
    "ImageCaption":    (SZ_SMALL, False, 60, 0, LINE, "both", None),
    "Figure":          (SZ_SMALL, False, 60, 60, LINE, "center", None),
    "Bibliography":    (SZ_BODY, False, 0, AFTER, LINE, "both", None),
    "BlockText":       (SZ_BODY, False, BEFORE, AFTER, LINE, "both", None),
    "Quote":           (SZ_BODY, False, BEFORE, AFTER, LINE, "both", None),
    "Verse":           (SZ_BODY, False, BEFORE, AFTER, LINE, "both", None),
}


def el(tag, **attrs):
    e = etree.SubElement(root, "x")            # placeholder, never used
    return e


def sub(parent, tag, **attrs):
    e = etree.SubElement(parent, f"{{{W}}}{tag}")
    for k, v in attrs.items():
        e.set(f"{{{W}}}{k.replace('_', ':')}" if ":" in k else f"{{{W}}}{k}", str(v))
    return e


def clear(parent, tags):
    for t in tags:
        for e in parent.findall(f"{{{W}}}{t}"):
            parent.remove(e)


def set_spacing(ppr, before, after, line):
    clear(ppr, ["spacing"])
    # schema order: spacing nam sau tabs/keepNext..., truoc ind/jc
    sp = etree.SubElement(ppr, f"{{{W}}}spacing")
    sp.set(f"{{{W}}}before", str(before))
    sp.set(f"{{{W}}}after", str(after))
    sp.set(f"{{{W}}}line", str(line))
    sp.set(f"{{{W}}}lineRule", "auto")
    return sp


def set_sz(rpr, sz):
    for t in ("sz", "szCs"):
        e = rpr.find(f"{{{W}}}{t}")
        if e is None:
            e = etree.SubElement(rpr, f"{{{W}}}{t}")
        e.set(f"{{{W}}}val", str(sz))


def set_font(rpr, name):
    f = rpr.find(f"{{{W}}}rFonts")
    if f is None:
        f = etree.Element(f"{{{W}}}rFonts")
        rpr.insert(0, f)
    for a in ("ascii", "hAnsi", "cs", "eastAsia"):
        f.set(f"{{{W}}}{a}", name)


patched = []

# ---- docDefaults ----
dd = root.find(f"{{{W}}}docDefaults")
if dd is not None:
    rpr_def = dd.find(f"{{{W}}}rPrDefault/{{{W}}}rPr")
    if rpr_def is not None:
        set_font(rpr_def, FONT)
        set_sz(rpr_def, SZ_BODY)
        patched.append("docDefaults/rPrDefault")
    ppr_def = dd.find(f"{{{W}}}pPrDefault/{{{W}}}pPr")
    if ppr_def is None:
        ppr_def = etree.SubElement(dd, f"{{{W}}}pPrDefault")
        ppr_def = etree.SubElement(ppr_def, f"{{{W}}}pPr")
    else:
        ppr_def = ppr_def.find(f"{{{W}}}pPr")
        if ppr_def is None:
            ppr_def = etree.SubElement(dd.find(f"{{{W}}}pPrDefault"), f"{{{W}}}pPr")
    clear(ppr_def, ["spacing"])
    sp = etree.SubElement(ppr_def, f"{{{W}}}spacing")
    sp.set(f"{{{W}}}before", str(BEFORE))
    sp.set(f"{{{W}}}after", str(AFTER))
    sp.set(f"{{{W}}}line", str(LINE))
    sp.set(f"{{{W}}}lineRule", "auto")
    patched.append("docDefaults/pPrDefault")

# ---- tung style ----
found = set()
for st in root.findall(f"{{{W}}}style"):
    sid = st.get(f"{{{W}}}styleId")
    if sid not in SPEC:
        continue
    found.add(sid)
    sz, bold, before, after, line, jc, outline = SPEC[sid]
    rpr = st.find(f"{{{W}}}rPr")
    if rpr is None:
        rpr = etree.SubElement(st, f"{{{W}}}rPr")
    set_font(rpr, FONT)
    set_sz(rpr, sz)
    clear(rpr, ["b", "bCs"])
    if bold:
        b = etree.Element(f"{{{W}}}b")
        bcs = etree.Element(f"{{{W}}}bCs")
        # b/bCs phai nam sau rFonts theo schema
        anchor = rpr.find(f"{{{W}}}rFonts")
        idx = list(rpr).index(anchor) + 1 if anchor is not None else 0
        rpr.insert(idx, b)
        rpr.insert(idx + 1, bcs)

    ppr = st.find(f"{{{W}}}pPr")
    if ppr is None:
        ppr = etree.Element(f"{{{W}}}pPr")
        st.insert(list(st).index(rpr), ppr)
    set_spacing(ppr, before, after, line)
    clear(ppr, ["jc"])
    if jc:
        e = etree.SubElement(ppr, f"{{{W}}}jc")
        e.set(f"{{{W}}}val", jc)
    if outline is not None:
        clear(ppr, ["outlineLvl"])
        e = etree.SubElement(ppr, f"{{{W}}}outlineLvl")
        e.set(f"{{{W}}}val", str(outline))
    patched.append(f"style:{sid}")

missing = sorted(set(SPEC) - found)
print(f"[2] da va {len(patched)} muc trong styles.xml")
print(f"[2] style KHONG co trong pandoc default (bo qua, khong sao): {missing}")

tree.write(str(styles_p), xml_declaration=True, encoding="UTF-8", standalone=True)

# ---- settings.xml: bo compat lam lech spacing ----
set_p = src / "word" / "settings.xml"
if set_p.exists():
    st = etree.parse(str(set_p))
    sr = st.getroot()
    for tag in ("compat",):
        for e in sr.findall(f"{{{W}}}{tag}"):
            sr.remove(e)
    st.write(str(set_p), xml_declaration=True, encoding="UTF-8", standalone=True)
    print("[2] settings.xml: bo <w:compat> (tranh Word ghi de spacing theo ban cu)")

REF = BUILD / "ref_venue.docx"
if REF.exists():
    REF.unlink()
with zipfile.ZipFile(REF, "w", zipfile.ZIP_DEFLATED) as z:
    for p in sorted(src.rglob("*")):
        if p.is_file():
            z.write(p, p.relative_to(src).as_posix())
print(f"[2] ref_venue.docx: {REF.stat().st_size} bytes")

# ---------------------------------------------------------------- 3) sectPr geometry
# Skill canh bao: "the reference's sectPr does not reliably survive pandoc —
# set it in the output too". Vi vay geometry se duoc dat ca o reference LAN output.
SECTPR = (f'<w:sectPr xmlns:w="{W}">'
          f'<w:pgSz w:w="{PGSZ_W}" w:h="{PGSZ_H}"/>'
          f'<w:pgMar w:top="{MARGIN}" w:right="{MARGIN}" w:bottom="{MARGIN}" '
          f'w:left="{MARGIN}" w:header="{HDRFTR}" w:footer="{HDRFTR}" w:gutter="0"/>'
          f'<w:cols w:space="{COL_SPACE}"/>'
          f'<w:docGrid w:linePitch="360"/>'
          f'</w:sectPr>')


def write_sectpr(doc_xml_path):
    t = etree.parse(str(doc_xml_path))
    r = t.getroot()
    body = r.find(f"{{{W}}}body")
    old = body.find(f"{{{W}}}sectPr")
    if old is not None:
        body.remove(old)
    new = etree.fromstring(SECTPR)
    body.append(new)
    t.write(str(doc_xml_path), xml_declaration=True, encoding="UTF-8", standalone=True)


# dat vao reference
rd = src / "word" / "document.xml"
if rd.exists():
    write_sectpr(rd)
    REF.unlink()
    with zipfile.ZipFile(REF, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(src.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(src).as_posix())
    print(f"[3] sectPr 19x27cm/le 2cm/1 cot -> reference ({REF.stat().st_size} bytes)")

# ---------------------------------------------------------------- 4) chay pandoc
BODY_TEX = BUILD / "body.tex"
OUT_DOCX = BUILD / "body.docx"
r = subprocess.run(["pandoc", str(BODY_TEX), "-f", "latex", "-t", "docx",
                    f"--reference-doc={REF}", "-o", str(OUT_DOCX)],
                   capture_output=True, text=True, timeout=400)
print(f"[4] pandoc exit={r.returncode}")
if r.stdout.strip():
    print("    stdout:", r.stdout[:400])
# LOI DA SUA: cat stderr[:900] an mat warning. Warning "Could not convert TeX
# math" la dau hieu cong thuc bi xuat ra chu LaTeX THO trong Word, khong phai
# chuyen tham my -> phai dem het va FAIL.
if r.stderr.strip():
    print("    stderr (DAY DU):")
    for _ln in r.stderr.split("\n"):
        if _ln.strip():
            print("      " + _ln[:160])
n_bad_math = r.stderr.count("Could not convert TeX math")
n_warn = r.stderr.count("[WARNING]")
print(f"[4] WARNING: {n_warn} tong | 'Could not convert TeX math': {n_bad_math}")
assert r.returncode == 0 and OUT_DOCX.exists(), "pandoc that bai"
assert n_bad_math == 0, (
    f"{n_bad_math} cong thuc khong chuyen duoc thanh Word math -> se hien chu "
    f"LaTeX tho trong .docx, vi pham yeu cau MathType cua tap chi")
print(f"[4] body.docx: {OUT_DOCX.stat().st_size} bytes")

# ---------------------------------------------------------------- 5) kiem tra dau ra
with zipfile.ZipFile(OUT_DOCX) as z:
    x = z.read("word/document.xml").decode("utf-8", "replace")
    media = [n for n in z.namelist() if n.startswith("word/media")]
t = etree.fromstring(x.encode())
paras = t.findall(f".//{{{W}}}p")
tables = t.findall(f".//{{{W}}}tbl")
omath = x.count("<m:oMath")
print(f"[5] body.docx: {len(paras)} paragraph | {len(tables)} bang | {omath} m:oMath | {len(media)} media")
# LOI CU: sorted(set( ... for i in range(...))) thieu mot ngoac dong cho sorted(),
# va goi findall hai lan. Viet lai bang set comprehension don gian.
_pstyles = t.findall(".//{%s}pStyle" % W)
styles_used = sorted({e.get(f"{{{W}}}val") for e in _pstyles if e.get(f"{{{W}}}val")})

# GATE: TeX tho lot vao text Word? (dau hieu cong thuc khong chuyen duoc)
_alltext = "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", x))
_RAW_MARK = [r"\begin{aligned}", r"\Bigl", r"\mathrm", r"\label{",
             r"\mathcal", r"\forall", r"\frac{", r"\sum_", r"\hat "]
_raw_hit = [m for m in _RAW_MARK if m in _alltext]
print(f"[5] TeX tho trong text Word: {_raw_hit or '(khong co)'}")
assert not _raw_hit, f"TEX THO LOT VAO DOCX: {_raw_hit}"
print(f"[5] pStyle dung: {styles_used}")
sec = t.find(f".//{{{W}}}sectPr")
if sec is not None:
    pgsz = sec.find(f"{{{W}}}pgSz")
    print(f"[5] sectPr pgSz: {pgsz.get(f'{{{W}}}w') if pgsz is not None else '?'} x "
          f"{pgsz.get(f'{{{W}}}h') if pgsz is not None else '?'} (mong doi {PGSZ_W} x {PGSZ_H})")
else:
    print("[5] CANH BAO: khong co sectPr trong output -> phai them o buoc 3")

(BUILD / "step2_report.txt").write_text(
    f"patched={len(patched)}\nmissing_styles={missing}\nparas={len(paras)}\n"
    f"tables={len(tables)}\nomath={omath}\nstyles={styles_used}\n", encoding="utf-8")
print(f"\n=== XONG BUOC 2: {OUT_DOCX} ===")

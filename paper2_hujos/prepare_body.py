#!/usr/bin/env python3
"""Buoc 1/3: tien xu ly LaTeX truoc khi dua vao pandoc (LaTeX -> .docx).

Vi sao phai tien xu ly: do bang probe that (/tmp/pdx), KHONG doan:
  * \\cite{a,b}     -> BIEN MAT HOAN TOAN, pandoc van exit 0. Cau van chi con
                       dau cham: "prior work ." => 28 nhom trich dan se bay khoi
                       ban Word. PHAI thay bang [n] lay tu thu tu \\bibitem that.
  * \\eqref{eq:x}   -> nguyen van "[eq:depl]"
  * \\ref{sec:x}    -> nguyen van "[sec:model]" khi nhan khong co trong cung file
  * caption bang    -> pandoc xuat HAI lan (mot truoc, mot sau bang kieu
                       TableCaption). Quy dinh HUJOS-TT: caption TREN bang.
  * \\fittocol{...} -> lenh tu dinh nghia, pandoc bo qua

Nguon so that (skill latex-to-venue-word-template, luat 2: "Resolve numbers,
never guess them"):
  main_hujos.aux -> \\newlabel{key}{{num}{page}...}   (eq/tab/prop/sec)
  main_hujos.bbl -> thu tu \\bibitem                  (so trich dan Vancouver)

KHONG tach aligned/cases thanh nhieu equation: bai nay dung equation CHUA
aligned/cases (mot so hieu cho ca khoi). Tach ra se SINH THEM so hieu sai.
(Chi tac khong \\begin{align}, ma bai nay khong co align nao.)
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

H = Path("/media/SAS/Van/DeTai2025/TwinGate_K1/paper2_hujos")
BLOCKS = Path("/media/SAS/Van/DeTai2025/TwinGate_K1/paper2/blocks")
OUT = H / "docx_build"
OUT.mkdir(exist_ok=True)

main = (H / "main_hujos.tex").read_text(encoding="utf-8")
aux = (H / "main_hujos.aux").read_text(encoding="utf-8", errors="replace")
bbl = (H / "main_hujos.bbl").read_text(encoding="utf-8", errors="replace")

report = []


def rep(msg):
    report.append(msg)
    print(msg)


# ---------------------------------------------------------------- 1) INLINE \input
RE_INPUT = re.compile(r"^\s*\\input\{([^}]+)\}\s*$", re.M)
n_inlined = 0


def inline_once(txt):
    global n_inlined

    def sub(m):
        global n_inlined
        rel = m.group(1)
        cand = [H / f"{rel}.tex", H / rel, BLOCKS / f"{Path(rel).name}.tex"]
        for c in cand:
            if c.exists():
                n_inlined += 1
                return "\n" + c.read_text(encoding="utf-8") + "\n"
        raise SystemExit(f"KHONG TIM THAY \\input{{{rel}}} — da thu {cand}")

    return RE_INPUT.sub(sub, txt)


body = inline_once(main)
for _ in range(6):                      # \input long nhau (blocks -> tables)
    if not RE_INPUT.search(body):
        break
    body = inline_once(body)
rep(f"[1] inline \\input: {n_inlined} file, con sot lai {len(RE_INPUT.findall(body))}")
assert not RE_INPUT.search(body), "van con \\input chua giai"

# ---------------------------------------------------------------- 2) CAT FRONT MATTER
# pandoc se nhan front matter tu gia tri that trong main (khong tu docx), vi vay
# o day cat bo khoi \begingroup...\endgroup (title/authors/affil/abstract) va
# khoi bibliography; buoc 3 se dung lai de tao natively trong Word.
m = re.search(r"\\begingroup(.*?)\\endgroup", body, re.S)
assert m, "khong tim thay khoi front matter \\begingroup...\\endgroup"
front = m.group(1)
body = body[:m.start()] + "\n%FRONT_MATTER_REMOVED%\n" + body[m.end():]
rep(f"[2] cat front matter: {len(front)} chars (se dung lai o buoc 3)")

body = re.sub(r"\\bibliographystyle\{[^}]*\}", "", body)
body = re.sub(r"\\bibliography\{[^}]*\}", "", body)
rep(f"[2] cat bibliography command; giu lai {body.count('bibitem')} bibitem")

# giu dung phan trong \begin{document}...\end{document}
md = re.search(r"\\begin\{document\}(.*)\\end\{document\}", body, re.S)
assert md, "khong tim thay \\begin{document}...\\end{document}"
body = md.group(1)
rep(f"[2] body sau khi cat: {len(body)} chars")

# ---------------------------------------------------------------- 3) SO THAT TU AUX
labels = {k: v for k, v, _p in re.findall(r"\\newlabel\{([^}]+)\}\{\{([^}]*)\}\{(\d+)\}", aux)}
rep(f"[3] aux: {len(labels)} nhan | namespace: {dict(Counter(k.split(':')[0] for k in labels))}")

# thu tu trich dan that tu .bbl
items = re.findall(r"\\bibitem(?:\[[^\]]*\])?\{([^}]+)\}", bbl)
order = {k: i + 1 for i, k in enumerate(items)}
rep(f"[3] bbl: {len(order)} bibitem (so trich dan Vancouver [1]..[{len(order)}])")

# ---------------------------------------------------------------- 4) THAY \cite -> [n]
cite_groups = re.findall(r"\\cite[tp]?\*?\{([^}]+)\}", body)
missing = sorted({k.strip() for c in cite_groups for k in c.split(",")} - set(order))
rep(f"[4] \\cite: {len(cite_groups)} nhom | key thieu trong bbl: {missing or '(khong)'}")
assert not missing, f"co key cite khong co trong .bbl: {missing}"


def cite_sub(m):
    keys = [k.strip() for k in m.group(2).split(",") if k.strip()]
    nums = sorted({order[k] for k in keys})
    # Vancouver: [1], [1, 2], [1-3] (sort&compress nhu natbib dang dung)
    out, i = [], 0
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        out.append(str(nums[i]) if j == i else
                   (f"{nums[i]}-{nums[j]}" if j - i >= 2 else f"{nums[i]}, {nums[j]}"))
        i = j + 1
    return "[" + ", ".join(out) + "]"


body = re.sub(r"(\\cite[tp]?\*?)\{([^}]+)\}", cite_sub, body)
# LOI DA SUA: viet re.findall(chr(92) + 'cite', body) tao pattern "\cite" ->
# "re.error: bad escape \c". Pattern LUON viet la raw string r"\\cite".
# (Day la lan thu 3 trong cung mot session vep loi escape: truoc do la
#  re.sub(..., TRIVIAL) voi TRIVIAL chua \midrule -> "bad escape \m", va
#  f-string chua backslash -> SyntaxError.)
n_cite_left = len(re.findall(r"\\cite", body))
rep(f"[4] sau thay: con {n_cite_left} lenh \\cite")

# ---------------------------------------------------------------- 5) THAY \ref/\eqref
# PROSE FORM da do that trong nguon (tranh trap double-prefix):
#   Table~\ref{tab:x}  (8 lan)  -> prefix TRONG, neu khong ra "Table Table 1"
#   Prop.~\ref{prop:x} / Proposition~\ref{prop:x} (4 lan) -> prefix TRONG
#   Sec.~\ref{sec:x}   (6 lan)  -> prefix TRONG
#   Eq.~\eqref{eq:x}   (2 lan) + \eqref tran (16 lan) -> eqref sinh "(n)"
unresolved = []


def eqref_sub(m):
    key = m.group(1)
    if key not in labels:
        unresolved.append(("eqref", key))
        return f"(?{key})"
    return f"({labels[key]})"


def ref_sub(m):
    key = m.group(1)
    if key not in labels:
        unresolved.append(("ref", key))
        return f"(?{key})"
    return labels[key]


body = re.sub(r"\\eqref\{([^}]+)\}", eqref_sub, body)
body = re.sub(r"\\ref\{([^}]+)\}", ref_sub, body)
rep(f"[5] eqref/ref: giai {len(labels)} nhan | CHUA GIAI: {unresolved or '(khong)'}")
assert not unresolved, f"nhan chua giai (se lo ra mat chu trong Word): {unresolved}"

# collapsed doubled forms do LaTeX sinh ra
for bad, good in ((r"Table~Table ", "Table "), (r"Table Table ", "Table "),
                  (r"Prop.~Prop. ", "Prop. "), (r"Sec.~Sec. ", "Sec. "),
                  (r"Eq.~Eq. ", "Eq. ")):
    if bad in body:
        rep(f"[5] sua dang lap: {bad!r} -> {good!r} ({body.count(bad)} lan)")
        body = body.replace(bad, good)
# Table~1 -> Table 1 (giu ~ la khong gian khong ngat, Word khong hieu ~ ngoai math)
body = re.sub(r"(Table|Fig\.|Prop\.|Sec\.|Eq\.)~", r"\1 ", body)

# ---------------------------------------------------------------- 6) \fittocol -> unwrap
n_fit = len(re.findall(r"\\fittocol\{", body))
body = re.sub(r"\\fittocol\{%", "", body)
body = re.sub(r"\\fittocol\{", "", body)
# LOI DA SUA: generator viet \fittocol{%\n...\n\end{tabular}\n} — dau } nam TREN
# DONG RIENG, khong dinh vao \end{tabular}. Regex cu r"(\\end\{tabular\})\}"
# khop 0 lan, de lai 8 dau } mo coi -> pandoc exit 64:
#   Error at body.tex (line 372, column 1): unexpected } expecting \end{table}
# Do that roi sua: grep -A2 'end{tabular}' cho thay 8/8 bang deu co } o dong sau.
# Cach chac chan: bo dung so dau } da mo, theo mau that cua generator.
n_before = len(re.findall(r"\\end\{tabular\}\s*\n\s*\}", body))
body = re.sub(r"(\\end\{tabular\})(\s*)\n\s*\}", r"\1\2", body)
n_after = len(re.findall(r"\\end\{tabular\}\s*\n\s*\}", body))
rep(f"[6] \\fittocol: {n_fit} cho -> unwrap; bo {n_before - n_after}/{n_before} dau }} mo coi "
    f"(con {n_after})")
assert n_before == n_fit, f"so dau }} ({n_before}) khac so \\fittocol ({n_fit}) — kiem tra lai"
assert n_after == 0, f"van con {n_after} dau }} mo coi sau \\end{{tabular}}"

# ------------------------------------------------- 6b) MACRO PANDOC KHONG HIEU
# DO THAT, khong doan: pandoc 3.1.3 chi bao DUNG 1 warning tren toan bai
#   [WARNING] Could not convert TeX math \begin{aligned} ... \label{eq:awd},
#   rendering as TeX:  ... unexpected control sequence \Bigl
# va TeX tho THAT SU lot vao word/document.xml (doc nguc lai thay
# "$$\begin{aligned}\n\mathcal{A}\bigl(\{\hat d_t\}\bigr)=\Bigl\{[a,b):...").
# Pandoc ho tro \bigl/\bigr (5 cho khac trong bai khong bao loi) nhung
# KHONG ho tro \Bigl/\Bigr/\biggl.
#
# SUA O DAY, KHONG SUA NGUON: giu \Bigl trong blocks/ de ban PDF LaTeX van co
# dau ngoac dung kich thuoc (eq:awd la set-builder 3 dieu kien), chi ha xuong
# \bigl cho ban nuoi pandoc. Dung luat cua skill:
# "keep the real environment in the LaTeX/PDF build, but feed pandoc a variant
#  where the environment is rewritten ... Do this in a build script (transform()),
#  never by hand-editing the source."
# Thu tu thay: macro DAI truoc, ngan sau (\Biggl khong chua \Bigl nen khong
# xung dot, nhung van lam theo thu tu dai->ngan cho chac).
_MATH_SIZE = ((r"\Biggl", r"\bigl"), (r"\Biggr", r"\bigr"),
              (r"\biggl", r"\bigl"), (r"\biggr", r"\bigr"),
              (r"\Bigl", r"\bigl"), (r"\Bigr", r"\bigr"),
              (r"\Bigl\{", r"\bigl\{"), (r"\Bigr\}", r"\bigr\}"))
n_math = 0
for big, small in _MATH_SIZE:
    k = body.count(big)
    if k:
        body = body.replace(big, small)
        n_math += k
        rep(f"[6b] {big} -> {small}: {k} cho (pandoc khong ho tro; chi sua ban nuoi)")
_left = [m for m in (r"\Bigl", r"\Bigr", r"\biggl", r"\biggr") if m in body]
rep(f"[6b] tong {n_math} macro co do lon bi ha; con sot: {_left or '(khong)'}")
assert not _left, f"van con macro pandoc khong hieu: {_left}"

# ------------------------------------------------- 6c) SO HIEU CONG THUC
# Pandoc BO \label trong math (do that o /tmp/pdx/probe: 3 display equation ->
# 3 m:oMathPara, khong con chu "eq:depl"), nen ban Word se KHONG co so cong thuc.
# Quy dinh HUJOS-TT: "Maths equations should be ... numbered on the right".
# Cach lam theo skill latex-to-venue-word-template buoc 3.8: them mot paragraph
# danh dau "EQNUM: n" sau moi display equation, roi buoc 3 bien no thanh tab phai
# + so trong ngoac tren cung dong voi cong thuc.
#
# So hieu lay theo THU TU XUAT HIEN (1..N), roi DOI CHIEU voi aux: 25/26 equation
# co nhan eq: va aux xac nhan dung thu tu do (eq#14 G(L)=G(L') khong co nhan).
_eq_spans = list(re.finditer(r"\\begin\{equation\}(.*?)\\end\{equation\}", body, re.S))
_n_eq = 0
for _i, _m in enumerate(reversed(_eq_spans), start=1):      # di nguoc de khong lech index
    _idx = len(_eq_spans) - _i + 1
    _inner = _m.group(1)
    _lab = re.search(r"\\label\{([^}]+)\}", _inner)
    if _lab and _lab.group(1) in labels:
        _auxnum = labels[_lab.group(1)]
        if _auxnum.isdigit() and int(_auxnum) != _idx:
            rep(f"[6c] CANH BAO: equation thu {_idx} co nhan {_lab.group(1)} = "
                f"{_auxnum} trong aux -> dung so cua aux")
            _idx = int(_auxnum)
    body = body[:_m.end()] + f"\n\nEQNUM: {_idx}\n\n" + body[_m.end():]
    _n_eq += 1
rep(f"[6c] them {_n_eq} marker EQNUM (so hieu cong thuc cho ban Word)")
assert _n_eq == len(_eq_spans) == 26, (_n_eq, len(_eq_spans))

# ---------------------------------------------------------------- 7) CHECK CUOI
leftover = re.findall(r"\\(?:ref|eqref|cite[tp]?|label)\{([^}]*)\}", body)
rep(f"[7] con sot \\ref/\\eqref/\\cite/\\label: {leftover[:8] or '(khong)'}")
# \label giu lai khong sao (pandoc bo qua), nhung \ref/\cite thi KHONG duoc con
bad_left = [x for x in re.findall(r"\\(?:ref|eqref|cite[tp]?)\{", body)]
assert not bad_left, f"van con {len(bad_left)} lenh ref/cite chua giai"

# % tran: bao dam khong co % lo (pandoc cat het phan con lai cua dong)
bare_pct = len(re.findall(r"(?<!\\)%", body))
rep(f"[7] dau %% lo (khong escape): {bare_pct} — LaTeX comment, pandoc cung cat, OK")

envs = Counter(re.findall(r"\\begin\{([a-zA-Z*]+)\}", body))
rep(f"[7] environment con trong body: {dict(envs)}")
rep(f"[7] \\begin{{table}} = {envs.get('table',0)} | caption = {body.count(chr(92)+'caption')}")
eqn = envs.get("equation", 0)
rep(f"[7] equation = {eqn} (aux co {len([k for k in labels if k.startswith('eq:')])} nhan eq:)")

(OUT / "body.tex").write_text(body, encoding="utf-8")
(OUT / "front.tex").write_text(front, encoding="utf-8")
(OUT / "prepare_report.txt").write_text("\n".join(report), encoding="utf-8")
print(f"\n=== XONG: {OUT/'body.tex'} ({len(body)} chars), front.tex ({len(front)} chars) ===")

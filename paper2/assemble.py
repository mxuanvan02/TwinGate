#!/usr/bin/env python3
"""Rap paper2/main.tex theo truc MOI (device-anchored).

Chien thuat: KHONG dung replace chuoi dai (da tra gia 3 lan vi escape backslash).
Cat ban cu theo NEOC dong that, ghep voi 6 khoi moi trong paper2/blocks/.

Giu lai tu ban cu (van dung, khong bi so lieu moi phu dinh):
  * preamble + author + \\maketitle            (dong 1-75)
  * \\subsection{Field water balance}          (dong 186-214)
  * \\section{Subsidence Invariance}           (dong 433-464)
  * \\section{Cost Model and Break-Even}       (dong 465-521, co va)
  * Data/Code declarations + bibliography

Bo di (da bi chinh so lieu cua minh phu dinh):
  * abstract + keywords cu (claim "three violations", "60/60", "$0--$1 tier 0")
  * Introduction cu
  * The irrigation log as evidence / Threat model / Attestation problem
  * Physics-Based Log Filters cu (khong co V5, khong co menh de blind spot)
  * Guarantees cu (u_max = 61mm mot con so)
  * Omission and the Pump-Meter Closure (claim "closes it exactly" -> do duoc 40%)
  * Experimental Design + Numerical Results + Discussion + Conclusion cu

Sau khi ghep, KIEM CAN BANG moi truong va doi chieu label/ref truoc khi build.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

P = Path("/media/SAS/Van/DeTai2025/TwinGate_K1/paper2")
BLK = P / "blocks"
NL = "\n"
BS = chr(92)

old = (P / "main.tex").read_text(encoding="utf-8")
lines = old.split(NL)


def find(pred, start=0, end=None, what=""):
    end = len(lines) if end is None else end
    for i in range(start, end):
        if pred(lines[i]):
            return i
    raise AssertionError("khong thay " + what)


def cut(a: int, b: int) -> str:
    """Cat [a, b) theo chi so dong 0-based."""
    return NL.join(lines[a:b]).strip(NL)


# ---------------------------------------------------------------- preamble
i_doc = find(lambda l: l.strip() == BS + "begin{document}", what="begin{document}")
preamble = cut(0, i_doc + 1)

# ---------------------------------------------------------------- author
i_title = find(lambda l: l.startswith(BS + "title{"), what="title")
i_maketitle = find(lambda l: l.strip() == BS + "maketitle", i_title,
                   what="maketitle")
author_block = cut(i_title + 2, i_maketitle + 1)   # bo 2 dong title cu

# ---------------------------------------------------------------- system model
i_sm = find(lambda l: l.startswith(BS + "section{System Model}"), what="System Model")
i_sm_sub = find(lambda l: l.startswith(BS + "subsection{The irrigation log as evidence}"),
                i_sm, what="subsection log as evidence")
system_model = cut(i_sm, i_sm_sub)

# ---------------------------------------------------------------- subsidence
i_sub = find(lambda l: l.startswith(BS + "section{Subsidence Invariance}"),
             what="Subsidence")
i_cost = find(lambda l: l.startswith(BS + "section{Cost Model and Break-Even}"),
              i_sub, what="Cost Model")
subsidence = cut(i_sub, i_cost)

# ---------------------------------------------------------------- cost model (co va)
i_design = find(lambda l: l.startswith(BS + "section{Experimental Design}"),
                i_cost, what="Experimental Design")
cost = cut(i_cost, i_design)

COST_EDITS = [
    # tier 0 khong con dung mot minh duoc
    ('''The three tiers differ only in $n_{\\mathrm{dev}}$ and in which fraud class they
close. Tier~0 sets $n_{\\mathrm{dev}}=0$: the log is written on a handset the
farmer already owns, and the filters of Sec.~\\ref{sec:filters} run on public
weather data at no marginal cost. Tier~1 adds a single flow meter at the
cooperative pumping station, so $n_{\\mathrm{dev}}=1$ for the whole area $A$
rather than one device per plot; by Prop.~\\ref{prop:omission} this one device is
sufficient for omission. Tier~2 adds one water-level node per cooperative,
which re-anchors the twin and restores the calibration property that a
measurement-based MRV would need anyway.''',
     '''The tiers differ in $n_{\\mathrm{dev}}$ and, more importantly, in which of the
three forgeable quantities of \\eqref{eq:three} they can observe. Tier~0 is the
physics layer: $n_{\\mathrm{dev}}=0$ beyond the controller, the log is written on
a handset the farmer already owns, and the filters of Sec.~\\ref{sec:filters} run
on public weather data at no marginal cost. Tier~1 adds one flow meter at the
cooperative pumping station --- $n_{\\mathrm{dev}}=1$ for the whole area $A$
rather than one per plot --- which observes the total volume. Tier~2 adds one
water-level node per cooperative, re-anchoring the twin and restoring the
calibration property a measurement-based MRV needs anyway.

None of the three observes timestamps, and by Prop.~\\ref{prop:blind} the first
two are exactly invariant under the transformation that pays. The device anchor
of Sec.~\\ref{sec:anchor} is therefore not an optional fourth tier but a
precondition of admissibility: it is produced by the same controller that
actuates the pump, so it adds storage and transmission of a record that already
exists, and no additional $n_{\\mathrm{dev}}$.'''),

    # khong con noi "tier 0 alone is about 1%" nhu mot claim doc lap
    ('''$\\kappa_{\\min}$ at $\\beta=0.5$ corresponds to a monitoring budget of
$\\$30$--$75$ per hectare. The full three-tier stack sits an order of magnitude
below that ceiling, and tier~0 alone is about $1\\%$ of conservative revenue.''',
     '''$\\kappa_{\\min}$ at $\\beta=0.5$ corresponds to a monitoring budget of
$\\$30$--$75$ per hectare. The full stack sits an order of magnitude below that
ceiling, and the incremental cost of the anchor over a controller that is already
installed is about $1\\%$ of conservative revenue. Table~\\ref{tab:baseline}
decomposes the comparison against the three architectures it replaces; the
connectivity term is shown separately because it is the one that distinguishes a
sensor-per-plot design from a single shared gateway.'''),

    # bang tab:cost khong con duoc sinh nua
    ('''Table~\\ref{tab:cost} reports the three tiers and Table~\\ref{tab:baseline}
compares them with the three architectures they replace. With''',
     '''Table~\\ref{tab:baseline} compares the scheme with the three architectures it
replaces. With'''),

    ('''\\begin{remark}
The device prices in Table~\\ref{tab:cost} are planning estimates, not
quotations.''',
     '''\\begin{remark}
The device prices in Table~\\ref{tab:baseline} are planning estimates, not
quotations.'''),
]
for a, b in COST_EDITS:
    c = cost.count(a)
    assert c == 1, f"cost edit: thay {c} lan (mong 1): {a[:52]!r}"
    cost = cost.replace(a, b)
print("  OK Cost Model: 4 cho va theo truc moi")

# ---------------------------------------------------------------- declarations
i_decl = find(lambda l: l.startswith(BS + "section*{Data, Code and Declarations}"),
              what="Declarations")
i_bibstyle = find(lambda l: l.startswith(BS + "bibliographystyle"), i_decl,
                  what="bibliographystyle")
decl = cut(i_decl, i_bibstyle)
DECL_EDITS = [
    ("Code, the fraud-generation and replay pipeline, and all $240$ audited logs are",
     "Code, the two uncertainty sets, both adversary implementations, and all $281$\n"
     "audited logs are"),
]
for a, b in DECL_EDITS:
    if a in decl:
        decl = decl.replace(a, b)
        print("  OK Declarations: cap nhat 240 -> 281 logs")

tail = NL.join([BS + "bibliographystyle{IEEEtran}", BS + "bibliography{refs}",
                "", BS + "end{document}"])

# ---------------------------------------------------------------- blocks
blocks = [
    BLK / "00_title_abstract.tex",
    BLK / "01_intro.tex",
]
b00 = blocks[0].read_text(encoding="utf-8")
# tach title va abstract de chen author + maketitle vao giua (IEEEtran bat buoc)
i_abs = b00.index(BS + "begin{abstract}")
title_new = b00[:i_abs].rstrip(NL)
abstract_new = b00[i_abs:].strip(NL)

rest = [(BLK / f).read_text(encoding="utf-8").strip(NL) for f in
        ("02_threat_attack.tex", "03_guarantee.tex", "04_anchor.tex",
         "05_design_results.tex", "06_discussion_conclusion.tex")]

# ---------------------------------------------------------------- tables
TBL = [
    ("tab:threat", "tab_threat", False,
     "The three forgeable quantities of \\eqref{eq:three} and which fraud class "
     "alters each. ``true'' means the quantity is preserved, so the corresponding "
     "defence is blind by Prop.~\\ref{prop:blind}."),
    ("tab:falseacc", "tab_false_accusation", False,
     "False accusation on honest logs, the property the scheme is sold on. Paper "
     "conditions reproduce the prior $0/60$; field conditions expose the absolute "
     "gap threshold."),
    ("tab:credit", "tab_credit", False,
     "Creditable dry phases of at least $72$\\,h, the quantity VM0051 and Decision "
     "4801 pay for, against the honest field baseline. The last column counts "
     "attacks that actually altered the log."),
    ("tab:defence", "tab_defence", False,
     "Main result. Escape rate is the fraction of forged logs neither tier flags; "
     "the anchor column is conditioned on the log having actually been altered."),
    ("tab:umax", "tab_umax", False,
     "The admissible depth bound \\eqref{eq:umax} across the FAO-56 Table 2 range. "
     "The previously published single value $61$\\,mm is one row of this table."),
    ("tab:f2reach", "tab_f2_unreachable", False,
     "Reachability of the wilting-point filter over $150$ configurations with an "
     "empty log, i.e.\\ the driest forcing available."),
    ("tab:setup", "tab_setup", False,
     "Experimental configuration. Every value is reproducible from the released "
     "code and the public ERA5 forcing."),
    ("tab:baseline", "tab_baseline", True,
     "MRV cost per hectare per season for the four architectures. Monitoring "
     "dominates MRV cost, so the architecture that avoids dedicated sensing wins "
     "on labour rather than hardware."),
]
tbl_lines = []
for lab, fn, wide, cap in TBL:
    env = "table*" if wide else "table"
    tbl_lines += [BS + f"begin{{{env}}}[!t]", BS + "centering",
                  BS + f"caption{{{cap}}}", BS + f"label{{{lab}}}",
                  BS + "footnotesize", BS + f"input{{tables/{fn}}}",
                  BS + f"end{{{env}}}", ""]

# ---------------------------------------------------------------- ghep
parts = [
    preamble, "",
    title_new, "",
    author_block, "",
    abstract_new, "",
    rest[0 - 0] if False else "",   # placeholder, se xoa
]
parts = [p for p in parts if p != ""]

body = NL.join([
    blocks[1].read_text(encoding="utf-8").strip(NL),   # Introduction
    "", system_model, "",
    rest[0], "",                                        # threat + filters + attack
    rest[1], "",                                        # guarantee + umax + v2reach
    rest[2], "",                                        # anchor
    subsidence, "",
    cost, "",
    rest[3], "",                                        # design + results
    rest[4], "",                                        # discussion + conclusion
    BS + "appendix", "",
    NL.join(tbl_lines),
    decl, "",
    tail,
])

out = NL.join([NL.join(parts), body]) + NL
# xoa dong placeholder rong thua
out = re.sub(NL + "{3,}", NL + NL, out)

shutil.copy(P / "main.tex", P / "main_v1_physics_axis.tex.bak")
(P / "main.tex").write_text(out, encoding="utf-8")
print(f"  main.tex: {len(old)} -> {len(out)} bytes (ban cu luu .bak)")

# ---------------------------------------------------------------- kiem tra
print("\n=== KIEM TRA TRUOC KHI BUILD ===")
for env in ["equation", "multline", "aligned", "cases", "enumerate", "itemize",
            "abstract", "table", "table*", "document", "IEEEkeywords", "proof"]:
    b = len(re.findall(re.escape(BS) + "begin\\{" + re.escape(env) + "\\}", out))
    e = len(re.findall(re.escape(BS) + "end\\{" + re.escape(env) + "\\}", out))
    flag = "OK" if b == e else "<<< LECH"
    if b or e:
        print(f"  {env:<14} begin={b:>2} end={e:>2}  {flag}")

labels = set(re.findall(re.escape(BS) + r"label\{([^}]+)\}", out))
refs = set(re.findall(re.escape(BS) + r"(?:ref|eqref)\{([^}]+)\}", out))
missing = sorted(refs - labels)
print(f"\n  ref thieu label: {missing or 'KHONG'}")
print(f"  label khong duoc ref: {sorted(labels - refs) or '(khong sao)'}")
print(f"  \\input tables: {len(re.findall(re.escape(BS) + 'input{tables/', out))}")
print(f"  section: {len(re.findall(re.escape(BS) + 'section', out))}")
print(f"  con 'tab:cost'/'tab:detect'/'tab:headline'/'tab:legal'/'tab:intensity'/"
      f"'tab:prop1'? "
      f"{[x for x in ['tab:cost','tab:detect','tab:headline','tab:legal','tab:intensity','tab:prop1'] if x in out] or 'KHONG'}")
print(f"  con claim cu '60/60'/'240 audited'/'three violations'? "
      f"{[x for x in ['60/60','240 audited','three violations'] if x in out] or 'KHONG'}")

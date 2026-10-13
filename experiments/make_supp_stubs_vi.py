#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""Sinh supp_stubs_vi.tex: dinh nghia \r@<label> cho cac nhan chi ton tai trong
bai chinh, doc SO THAT tu main_hujos_vi.aux.

VI SAO CAN: paper2_hujos/supplementary.tex (ban EN) go TAY cac so nay bang
\@namedef va lay tu main_hujos.aux (ban EN). Ban VI danh so KHAC, nen neu dich
nguyen xi thi phu luc tieng Viet tro sai. Do that (2026-10-13):
    sec:anchor  EN=8  VI=7   -> "Muc 8" khong ton tai trong bai VI
    eq:v4       EN=12 VI=11
    eq:v5       EN=13 VI=12
    eq:umax     EN=16 VI=15  -> S2 va S14 viet "Eq. (16)" la sai
Ngoai ra ban EN con 2 cho tro sai NGAY TRONG BAN EN:
    S9.2 viet "Table~5 of the main text" — bai chi co 4 bang (bang so sanh
         phuong an MRV la tab:benchmark = 4)
    S15  viet "Table~4 of the main text" cho cac so ghep cap — bang co cot
         Inflation/ghep cap la tab:credit = 2
=> Ban VI dung \ref/\eqref cho MOI tham chieu cheo, khong go tay so nao.

FAIL-CLOSED: neu mot nhan trong LABELS khong co trong .aux thi ABORT (exit 1),
KHONG sinh stub thieu. Stub thieu se khien \ref in ra "??" ma build van exit 0
— dung loi da ghi trong MEMORY: helper 'return 0 khi ImportError' = FAIL-OPEN.

Chay: python3 experiments/make_supp_stubs_vi.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUX = ROOT / "paper2_hujos" / "main_hujos_vi.aux"
OUT = ROOT / "paper2_hujos" / "supp_stubs_vi.tex"

# Moi nhan ma phu luc tham chieu cheo toi bai chinh. Them vao day khi phu luc
# moi trich dan mot nhan khac; KHONG duoc go tay so trong supplementary_vi.tex.
LABELS = [
    "eq:depl",        # ty le can kiet — S4, S11
    "eq:three",       # 3 dai luong lam gia duoc — S1, S5
    "eq:v5",          # gioi han tham — S11
    "eq:umax",        # bien do sau chap nhan duoc — S2, S14
    "eq:anchor",      # phep thu neo — S12
    "prop:blind",     # Menh de 1 — S1, S5, S9.1
    "prop:noalarm",   # Menh de 3 — S7, S21
    "prop:complete",  # Menh de 4 — S12, S18, S21
    "sec:filters",    # Muc cac bo loc — S5
    "sec:anchor",     # Muc neo thiet bi — S5
    "sec:umax",       # Muc bien do sau — S14
    "sec:robust",     # Muc quy tac ben vung — S17
    "tab:falseacc",   # Bang ket toi oan — S1
    "tab:credit",     # Bang so pha kho ghep cap — S15
    "tab:defence",    # Bang cac tang phong thu — S10.4
    "tab:benchmark",  # Bang so sanh phuong an MRV — S9.2
]


def main() -> int:
    if not AUX.exists():
        print(f"  !! KHONG THAY {AUX.name} — phai build main_hujos_vi.tex TRUOC.")
        print("     cd paper2_hujos && xelatex main_hujos_vi.tex")
        return 1
    txt = AUX.read_text(encoding="utf-8")
    found = {
        m.group(1): m.group(2)
        for m in re.finditer(r"\\newlabel\{([^}]*)\}\{\{([^}]*)\}", txt)
    }
    missing = [l for l in LABELS if l not in found]
    if missing:
        print(f"  !! ABORT: {len(missing)} nhan khong co trong {AUX.name}: {missing}")
        print("     Phu luc se in ra '??'. Sua LABELS hoac nhan trong bai chinh.")
        return 1

    lines = [
        "% TU SINH boi experiments/make_supp_stubs_vi.py — KHONG SUA TAY.",
        f"% Nguon so: {AUX.name} (ban TIENG VIET).",
        "% Moi \\r@<label> duoc \\ref doc; {S1} la so trang hien thi khi tro cheo.",
        "% Neu bai chinh doi danh so: build lai main_hujos_vi.tex roi chay lai script nay.",
        r"\makeatletter",
    ]
    for l in LABELS:
        lines.append(r"\@namedef{r@%s}{{%s}{S1}}" % (l, found[l]))
    lines.append(r"\makeatother")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"  OK: sinh {OUT.name} voi {len(LABELS)} nhan (doc tu {AUX.name})")
    for l in LABELS:
        print(f"     {l:18s} = {found[l]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

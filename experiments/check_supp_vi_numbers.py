#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GATE: doi chieu MOI CON SO trong PHU LUC tieng Viet vs tieng Anh.

Bo sung cho check_vi_numbers.py (chi kiem 7 block THAN BAI). Phu luc S1-S21
truoc day dung chung supplementary.tex (EN); nay co ban nop duy nhat main.tex
nen can gate rieng de ban dich khong chep sai so (MEMORY: da tung co loi
'+69%->+33%' o than bai).

KHO KHAN dac thu cua phu luc (khac than bai):
  1. Ban VI dung \\ref/\\eqref cho MOI tham chieu cheo toi bai chinh (so sinh
     tu supplementary_stubs.tex). Ban EN go TAY 'Eq.~(16)','Prop.~1'... -> so cross-ref
     co trong source EN nhung KHONG trong source VI. Day la KHAC BIET DUNG (chinh
     la 4 cho tro sai em sua: eq:umax EN=16/VI=15, eq:v4 12/11, eq:v5 13/12,
     sec:anchor 8/7), KHONG phai mat so lieu. -> Trung hoa cue+so cross-ref ca 2 ben.
  2. Khoi tac gia: phu luc VI lay DUNG khoi cua main.tex (5 tac gia +
     dia chi '34 Le Loi'), phu luc EN chi 2 tac gia -> so chi so mu/at superscript
     ($^{2,*}$...) va dia chi khac nhau. -> Cat bo front matter (\\begingroup..\\endgroup)
     ca 2 ben truoc khi dem.
  3. Stub \\@namedef{r@..}{{N}{S1}} chua so cua BAI CHINH -> cat bo ca 2 ben.

Sau 3 buoc trung hoa tren, tap so CON LAI phai trung nhau tuyet doi. Moi khac
biet con duoc doi chieu voi ALLOWLIST (da duyet bang tay, co giai thich); gate
chi PASS khi phan du NAM TRONG allowlist. Khong co allowlist mo rong ngam.

Chay: python3 experiments/check_supp_vi_numbers.py
"""
from __future__ import annotations
import re, sys, importlib.util
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
H = ROOT / "paper2_hujos"
S = ROOT / "paper2_vi_submission" / "src"

spec = importlib.util.spec_from_file_location("cvn", ROOT / "experiments" / "check_vi_numbers.py")
cvn = importlib.util.module_from_spec(spec); spec.loader.exec_module(cvn)

TABLES = ["tab_threat", "tab_umax", "tab_f2_unreachable", "tab_baseline", "tab_setup"]

def load(vi: bool) -> str:
    if vi:
        parts = [S / "supplementary_body.tex",
                 S / "sections/08_subsidence.tex", S / "sections/09_cost.tex"]
        parts += [S / "tables" / f"{t}.tex" for t in TABLES]
    else:
        parts = [H / "supplementary.tex",
                 ROOT / "paper2/blocks/08_subsidence.tex", ROOT / "paper2/blocks/09_cost.tex"]
        parts += [H / "tables" / f"{t}.tex" for t in TABLES]
    return "\n".join(p.read_text(encoding="utf-8") for p in parts)

# ---- 3 buoc trung hoa (ap dung DOI XUNG ca 2 ben) ----
def neutralize(text: str) -> str:
    s = text
    # (3) stub namedef: so cua bai chinh
    s = re.sub(r"\\@namedef\{r@[^}]*\}\{\{[^}]*\}\{[^}]*\}\}", " ", s)
    # (5) khoang cach dan trang: \vspace{10pt} (EN) vs \clearpage (VI) —
    # LOI DA SUA (Batch 5c): ban VI thay \vspace{10pt} sau \endgroup bang
    # \clearpage (trang bia phu luc) -> so 10 bien mat khoi VI, gate bao
    # THIEU gia. So cua lenh spacing khong phai so lieu nghien cuu.
    s = re.sub(r"\\(?:vspace|hspace|vskip|smallskip|medskip|bigskip)\*?\{[^}]*\}", " ", s)
    # (2) front matter: \begingroup ... \endgroup (title/authors/affil)
    s = re.sub(r"\\begingroup.*?\\endgroup", " ", s, flags=re.S)
    # (1) cue+so cross-ref, ca EN lan VI (\ref/\eqref da duoc cvn.numbers cat).
    # LOI DA SUA (2026-10-13): ban dau chi viet `Mệnh đề~?\d+` (khong co \s)
    # trong khi phia EN co `Proposition\s?\d+` -> heading "Chứng minh Mệnh đề 1"
    # cua ban VI KHONG bi loai, con "Proof of Proposition 1" cua EN THi bi loai.
    # Gate bao thua gia 5 so (1x2, 2, 3, 4) o ban VI. Day dung la loai loi bat
    # doi xung da ghi trong MEMORY: chi liet ke mot phia nen phia kia lech gia.
    # LOI LAN 2 (cung lop, cung file): them Table/Figure cho EN nhung QUEN
    # Bang/Hinh cho VI -> 'FAO-56 Bang 2' va 'Bang 12' chi bi loai o phia EN,
    # gate bao thua gia 2 va 12. Bai hoc: moi mau nhan EN phai co cap doi VI
    # trong CUNG mot dong comment, va phai chay gate that truoc khi tuyen bo PASS.
    # -> MOI mau deu phai chap ca dau cach, dau ~ va dau . (khong co hoac co).
    for pat in [
        r"Eq(?:uation)?[\s.~]*\(?\d+\)?",                 # EN Eq.~(16), Eq.~13
        # LOI LAN 3 (cung lop bat doi xung): EN viet heading "Proofs of
        # Propositions 1 and 2" -> mau cu chi an "Propositions 1" va de tro so "2";
        # VI viet "Chứng minh Mệnh đề 1 và Mệnh đề 2" -> mau `Mệnh đề..\d+` an CA HAI.
        # Gate bao EN thua 1 so '2'. Sua: moi mau phai an CA DANH SACH liet ke
        # (so, and/va/& so) o ca hai ngon ngu.
        r"Prop(?:osition)?s?[\s.~]*\d+(?:[\s,]*(?:and|và|&)[\s,]*\d+)*",
        r"Mệnh đề[\s.~]*\d+(?:[\s,]*(?:và|and|&)[\s,]*(?:Mệnh đề[\s.~]*)?\d+)*",
        r"Sec(?:tion)?s?[\s.~]*\d+",                        # EN Sec.~4
        r"Appendix[\s.~]*\d+|Annex[\s.~]*\d+",            # EN VM0051 Appendix 4
        r"Table[\s.~]*\d+|Figure[\s.~]*\d+",              # EN Table~5, Table 12 (nhan, khong phai so)
        r"Bảng[\s.~]*\d+|Hình[\s.~]*\d+",                # VI Bang 2, Bang 12 (DOI XUNG voi Table/Figure)
        r"Ghi chú[\s.~]*\d+",                              # VI Ghi chú 1
        r"Công thức[\s.~]*\d+|Phương trình[\s.~]*\d+",  # VI
        r"Mục[\s.~]*\d+|Phụ lục[\s.~]*\d+",             # VI Mục 4, Phụ lục 4
    ]:
        s = re.sub(pat, " ", s)
    # (4) ten cong cu / duong dan phan mem: 'python3' trong \errmessage cua
    # \InputIfFileExists chi co o ban VI -> so 3 bi dem nham. Loai DOI XUNG.
    s = re.sub(r"python\d", " ", s)
    return s

# Cac so duoc phep khac sau trung hoa — DA DUYET BANG TAY, co ly do.
# Khoa = (so, 'thieu'|'thua'), gia tri = so lan cho phep + ly do.
ALLOWLIST = {}  # hien de trong: sau trung hoa khong con khac biet nao

def main() -> int:
    en = cvn.numbers(neutralize(load(False)))
    vi = cvn.numbers(neutralize(load(True)))
    print("=" * 70)
    print("GATE SO LIEU PHU LUC: ban tieng Viet vs ban tieng Anh")
    print("=" * 70)
    print(f"  EN={sum(en.values())} so | VI={sum(vi.values())} so (sau 3 buoc trung hoa)")
    missing = en - vi   # co trong EN, thieu trong VI
    extra = vi - en     # co trong VI, khong trong EN
    ok = True
    resid_miss, resid_extra = Counter(), Counter()
    for n, c in missing.items():
        al = ALLOWLIST.get((n, "thieu"), 0)
        if c > al: resid_miss[n] = c - al; ok = False
    for n, c in extra.items():
        al = ALLOWLIST.get((n, "thua"), 0)
        if c > al: resid_extra[n] = c - al; ok = False
    if resid_miss:
        print(f"\n  !! THIEU trong VI (khong nam allowlist): {dict(resid_miss)}")
    if resid_extra:
        print(f"\n  !! THUA trong VI (khong nam allowlist): {dict(resid_extra)}")
    if not resid_miss and not resid_extra:
        print("  Khong con khac biet sau trung hoa front-matter/cross-ref/stub.")
    print("\nGATE:", "PASS — so lieu nghien cuu cua 2 ban phu luc trung nhau"
          if ok else "FAIL — co so lech, phai sua")
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())

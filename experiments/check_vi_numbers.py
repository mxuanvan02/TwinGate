#!/usr/bin/env python3
"""GATE: doi chieu MOI CON SO trong van xoi tieng Viet voi ban tieng Anh.

VI SAO CAN (2026-10-08):
  * Bang so: da an toan — tables_vi/ sinh TU DONG tu tables/ bang
    make_tables_hujos_vi.py, co assert tap chu so trung nhau.
  * Van xoi: nguoi dich (em) GO TAY. Da tung xuat hien loi that o chinh bai nay:
    "+69% -> +33%", "91% -> 89%", "75mm -> 65mm" (commit 4455a4b). Neu ban dich
    tieng Viet chep sai mot so, KHONG gate nao hien co bat duoc:
      - verify_paper_claims.py chi doc blocks/ (ban EN)
      - fix_stale_numbers.py chi quet cac file duoc main_hujos.tex \input
    => Ban dich co the noi "37%" ma khong ai biet.

CACH KIEM: tach moi "so + don vi/ngu canh" cua hai ban thanh multiset, roi so sanh.
So khong can khop 1-1 theo thu tu (cau tieng Viet dao ngu phap), nhung TAP SO
phai giong het nhau. Neu VI thieu/thua so nao -> in ra ca hai phia de doi chieu.

NGOAI LE hop le (khai bao tuong minh, khong duoc mo rong ngam):
  * So thu tu muc/bang cua ban VI (Bảng~S1, Phụ lục~S21...) giong ban EN vi dung
    chung supplementary.tex -> khong tinh.
  * Nam (2024, 2025) va so hieu van ban (4801, 1490, 56, 0051) xuat hien ca hai.
  * Ban EN co cac muc "Sec. 11.1/11.2..." ma ban VI viet gop thanh doan -> cac so
    THU TU TIEU MUC (11.1, 12.2...) duoc bo qua, vi chung la nhan cau truc, khong
    phai ket qua. Nhung so DO LUONG (26.7, 5.29, 0.9987...) khong duoc bo qua.

Chay: python3 experiments/check_vi_numbers.py
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EN_DIR = ROOT / "paper2" / "blocks"
VI_DIR = ROOT / "paper2_hujos" / "blocks_vi"

# Cac file than bai (khong tinh 00_title_abstract vi la FILE CHET, khong duoc input)
FILES = ["01_intro", "07_system_model", "02_threat_attack", "03_guarantee",
         "04_anchor", "05_design_results", "06_discussion_conclusion"]

# Nhan cau truc khong phai ket qua: "Sec.~\ref{...}", so muc, so hieu bang/phu luc.
# Chi loai khi so NAM TRONG cac nguyen mau nay.
STRUCTURAL = [
    re.compile(r"\\ref\{[^}]*\}"),
    re.compile(r"\\eqref\{[^}]*\}"),
    re.compile(r"(?:Table|Bảng|Supplementary|Phụ lục)~?S?\d+(?:\.\d+)?"),
    re.compile(r"Sec\.~?\\?\w*\{?(?:sec:)?\w*\}?"),
    re.compile(r"\\label\{[^}]*\}"),
    re.compile(r"S\d+(?:\.\d+)?"),        # S1, S10.4, S9.2 (phu luc dung chung)
    # TEN BO LOC: phai bat ca dang co gach duoi. LOI DA SUA (2026-10-08):
    # chi viet `[Vv]\d` nen `V_1`/`V_4`/`V_5` trong $...$ khong bi loai -> bao
    # lech gia 1 so o 02_threat_attack.
    re.compile(r"[Vv]_?\d"),
    re.compile(r"[Tt]ier~?-?\d"),          # tier 0/1, Tier-1
    re.compile(r"bậc\s+\d"),               # "bậc 1" = ban dich cua Tier-1
    re.compile(r"\\tau_?\{?0\}?"),
    re.compile(r"(?:Layer|Tầng)~?\d"),
]


def strip_noise(text: str) -> str:
    """Bo comment, command LaTeX, cong thuc, va cac nhan cau truc."""
    out = []
    for line in text.split("\n"):
        line = re.sub(r"(?<!\\)%.*$", "", line)      # comment (khong phai \%)
        out.append(line)
    s = "\n".join(out)
    s = re.sub(r"\\begin\{(equation|aligned|cases|tabular|proof)\}.*?"
               r"\\end\{\1\}", " EQ ", s, flags=re.S)
    for pat in STRUCTURAL:
        s = pat.sub(" ", s)
    s = re.sub(r"\\[a-zA-Z]+\*?", " ", s)
    return s


def numbers(text: str) -> Counter:
    """Moi 'so' = chuoi chu so co the kem dau thap phan, chuan hoa ve dau CHAM.

    LOI DA SUA (2026-10-08, gate bao FAIL gia tren ban dich DUNG):
      Ban tieng Viet viet thap phan kieu Viet trong LaTeX la `26{,}7`, con ban
      Anh viet `26.7`. Bo tach so ban dau:
        (a) KHONG go `{}` -> `26{,}7` bi cat thanh hai so "26" va "7";
        (b) dung `[.,]` trong regex tham lam -> `49.0,86.0` (dau PHAY la dau
            NGAN DANH SACH, khong phai thap phan) bi nuot tron thanh mot so
            `49.0.86.0`.
      Hau qua: gate bao "VI thieu 26.7 x6" va "VI thua 26 x6, 7 x6" — dung bang
      nhau, tuc la loi cua cong cu chu khong phai loi ban dich.
    CACH SUA: doi `{,}` (dau phay thap phan kieu Viet) thanh `.` TRUOC, roi tach
    so bang chi dau `.`. Dau phay tran khi do luon la dau ngan danh sach -> tac
    so dung. `\\,` (khoang trang mong) cung phai go truoc, neu khong `2\\,160`
    bi tach thanh 2 va 160 o ca hai ban (van nhat quan nhung vo nghia).
    """
    s = strip_noise(text)
    s = s.replace("{,}", ".")          # dau thap phan kieu Viet trong LaTeX
    s = s.replace("\\,", " ")          # thin space, khong phai dau phay
    s = s.replace("{.}", ".")
    found = re.findall(r"\d+(?:\.\d+)*", s)
    return Counter(found)


def main() -> int:
    en_all, vi_all = Counter(), Counter()
    per_file = []
    for f in FILES:
        en_p, vi_p = EN_DIR / f"{f}.tex", VI_DIR / f"{f}.tex"
        if not en_p.exists() or not vi_p.exists():
            print(f"  !! thieu file: EN={en_p.exists()} VI={vi_p.exists()} ({f})")
            return 1
        en_n = numbers(en_p.read_text(encoding="utf-8"))
        vi_n = numbers(vi_p.read_text(encoding="utf-8"))
        en_all += en_n
        vi_all += vi_n
        per_file.append((f, en_n, vi_n))

    print("=" * 78)
    print("GATE SO LIEU VAN XOI: ban tieng Viet vs ban tieng Anh")
    print("=" * 78)
    print(f"\n{'file':<30}{'EN':>8}{'VI':>8}  lech")
    for f, en_n, vi_n in per_file:
        diff = (en_n - vi_n) + (vi_n - en_n)
        mark = "OK" if not diff else f"LECH {sorted(diff.items())[:6]}"
        print(f"  {f:<28}{sum(en_n.values()):>8}{sum(vi_n.values()):>8}  {mark}")

    missing = en_all - vi_all     # so co trong EN ma thieu trong VI
    extra = vi_all - en_all       # so co trong VI ma khong co trong EN
    print(f"\nTONG: EN {sum(en_all.values())} so | VI {sum(vi_all.values())} so")
    ok = True
    if missing:
        ok = False
        print(f"\n!! THIEU trong ban VI ({sum(missing.values())} lan xuat hien):")
        for n, c in missing.most_common():
            print(f"     {n:<12} x{c}")
    if extra:
        ok = False
        print(f"\n!! THUA trong ban VI ({sum(extra.values())} lan xuat hien):")
        for n, c in extra.most_common():
            print(f"     {n:<12} x{c}")

    # In cac so TRONG YEU de doi chieu bang mat (khong thay the gate, chi ho tro)
    KEY = ["26.7", "5.0", "33", "38", "35", "40", "116", "281", "60", "37", "18",
           "49.0", "86.0", "61", "0.9987", "65", "5.29", "3.46", "4.78", "6.33",
           "5.33", "7.33", "648", "150", "24", "10", "3", "9", "6", "8", "4", "1"]
    print("\n--- doi chieu so trong yeu (EN vs VI) ---")
    for k in KEY:
        e, v = en_all.get(k, 0), vi_all.get(k, 0)
        flag = "" if e == v else "   <<< LECH"
        print(f"  {k:<10} EN={e:<4} VI={v:<4}{flag}")

    print("\nGATE:", "PASS — tap so cua hai ban trung nhau" if ok else "FAIL — phai sua")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

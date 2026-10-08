#!/usr/bin/env python3
"""GATE: quet ky tu NGOAI LAI (CJK, Cyrillic, Hy Lap lac cho...) trong ban tieng Viet.

LY DO (2026-10-08, 2 lan trong cung mot phien):
  * "phan农 hoc" trong blocks_vi/01_intro.tex
  * "tai引入" trong tieu de 8.2 cua blocks_vi/04_anchor.tex
Ca hai lot qua mat thuong khi doc; chi bi bat khi nhin ky. Bai hoc: ban dich
tieng Viet PHAI co gate tu dong. Ky tu Han/ky tu la lan vao tu qua trinh sinh
cua model la loi tai pham duoc, khong phai tai nan mot lan.

Pham vi quet: moi file duoc main_hujos_vi.tex \input (blocks_vi/, glossary,
blocks_vi.tex khoi tom tat), cong tables_vi/.

Ky tu HOP LE trong file tieng Viet:
  * ASCII (lenh LaTeX, so, ky hieu toan)
  * Latin Extended + Latin Extended Additional (U+0080-U+024F, U+1E00-U+1EFF:
    tieng Viet day du: a-z voi dau)
  * U+2000-U+206F: dau cach, gach noi, dau nhay "smart quotes" ---, ''
  * U+2200-U+22FF: ky hieu toan hoc (nhung it dung, da co $...$)
Cho phep trong COMMENT (%) nhu khong — comment cung phai sach, vi no duoc doc.
Ngoai le duy nhat: khong co.

Chay: python3 experiments/check_vi_foreign_chars.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
H = ROOT / "paper2_hujos"

ALLOWED = [
    (0x0000, 0x007F),   # ASCII
    (0x0080, 0x024F),   # Latin-1 Supplement + Latin Extended-A/B (é, ư, ơ...)
    (0x0300, 0x036F),   # Combining Diacritical Marks (neu co decomposition)
    # LOI DA SUA (2026-10-08): thieu dai nay nen gate bao nham 2491 ky tu.
    # Latin Extended Additional U+1E00-U+1EFF la NOI CHUA TOAN BO chu Viet co
    # dau thanh + dau mu (ế U+1EBF, ộ U+1ED9, ầ U+1EA7, ữ U+1EEF...).
    # Thieu no = gate vo nghia: no "bat" chinh ban dich dung.
    (0x1E00, 0x1EFF),   # Latin Extended Additional — TIENG VIET
    (0x2000, 0x206F),   # General Punctuation: — – ‘’ “” ′ …
    (0x20AB, 0x20AB),   # dong sign (neu can)
    (0x2100, 0x214F),   # Letterlike Symbols (thuong nam trong $...$)
    (0x2200, 0x22FF),   # Mathematical Operators
]

# Cac khoi bi CAM tuyet doi (nguon goc cua 2 loi that trong phien nay:
# U+8FB2 '农' va U+5F15/U+5165 '引入'). In ra ten khoi de bao loi ro nghia.
FORBIDDEN = [
    (0x3000, 0x303F, "CJK Symbols and Punctuation"),
    (0x3040, 0x30FF, "Hiragana/Katakana (Nhat)"),
    (0x3400, 0x4DBF, "CJK Extension A"),
    (0x4E00, 0x9FFF, "CJK Unified (Han)"),
    (0xAC00, 0xD7AF, "Hangul (Han Quoc)"),
    (0x0400, 0x04FF, "Cyrillic"),
    (0x0370, 0x03FF, "Greek"),
    (0xF900, 0xFAFF, "CJK Compatibility Ideographs"),
]


def forbidden_block(cp: int) -> str | None:
    for lo, hi, name in FORBIDDEN:
        if lo <= cp <= hi:
            return name
    return None


def allowed(cp: int) -> bool:
    return any(a <= cp <= b for a, b in ALLOWED)


def main() -> int:
    files = sorted((H / "blocks_vi").glob("*.tex"))
    files += [H / "blocks_vi.tex", H / "main_hujos_vi.tex", H / "glossary_vi.tex",
              H / "supplementary_vi.tex"]
    files += sorted((H / "tables_vi").glob("*.tex"))
    bad_total = 0
    for f in files:
        if not f.exists():
            continue
        text = f.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.split("\n"), 1):
            for col, ch in enumerate(line):
                cp = ord(ch)
                if allowed(cp):
                    continue
                blk = forbidden_block(cp) or "khoi khong xac dinh"
                bad_total += 1
                ctx = line[max(0, col - 12):col + 13]
                print(f"  !! {f.relative_to(ROOT)}:{lineno}:{col} "
                      f"U+{cp:04X} '{ch}' [{blk}] trong ...{ctx}...")
    if bad_total:
        print(f"\nGATE FAIL: {bad_total} ky tu ngoai lai — sua het truoc khi build.")
        return 1
    n = sum(1 for f in files if f.exists())
    print(f"GATE PASS: {n} file tieng Viet, 0 ky tu ngoai lai.")
    print("  (cho phep: ASCII + Latin mo rong + Latin Extended Additional U+1E00-1EFF")
    print("   + dau cau/toan hoc; cam: CJK/Han, Kana, Hangul, Cyrillic, Hy Lap)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

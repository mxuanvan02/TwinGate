#!/usr/bin/env python3
"""GATE: quy uoc TIEU DE theo ngon ngu cua HUJOS (VI khong dau hai cham, EN co the).

VI SAO TON TAI (2026-10-09, anh Van phat hien "ten bai van con dung dau :"):
  Tieu de ban tieng Viet viet theo kieu tieu de tieng Anh:
      "Nhật ký tưới được neo theo thiết bị: đánh giá đối kháng phương án MRV..."
  Day la thoi quen colon + subtitle cua tieng Anh, khong phai thoi quen cua tieu
  de tieng Viet tren tap chi nay.

  Bang chung (khong suy doan tu tri nho):
    * Crossref theo ISSN 2615-9732 (Hue University Journal of Science: Techniques
      and Technology), lay 55 bai: trong 36 tieu de tieng Viet chi CO 3 bai dung
      dau hai cham, 33 bai khong. Tieu de VI cua tap chi la mot cum danh tu lien
      mach, noi bang TRONG / THEO / VE / BANG / CUA.
    * Hai bai cua chinh nhom tac gia da nop HUJOS cung khong dung dau hai cham
      ("KHUNG TIÊU CHÍ THẨM ĐỊNH ... TRONG ĐÀO TẠO LUẬT TRÌNH ĐỘ ĐẠI HỌC";
      "THẨM ĐỊNH CÂU HỎI TRẮC NGHIỆM ... THEO TIẾP CẬN SƯ PHẠM VỀ ...").
    * Nguoc lai, tieu de TIENG ANH cua tap chi dung dau hai cham binh thuong
      (bai da dang: "Short-Term Bitcoin Forecasting Across Multiple Horizons:
      The Effectiveness of GRU Networks"). Vi vay chi bat loi o ban VI.

GATE NAY KIEM 4 DIEU O TIEU DE VI:
  1. Khong co dau hai cham.
  2. Khong chua viet tat dung tran (phai viet day du hoac khai trien) — tieu de la
     noi doc gia gap dau tien, khong duoc bat ho doan.
  3. Do dai nam trong dai da thay o cac bai da dang (8..32 tu).
  4. Khong lap tu noi dung (trừ hư từ va cac tu lap duoc phep).

Chay:
    python3 experiments/check_vi_title.py
Thoat 0 = PASS, 1 = FAIL.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HUJOS = ROOT / "paper2_hujos"
BS = chr(92)

# Dai do dai quan sat duoc o 33 tieu de VI khong dau hai cham cua tap chi
# (Crossref, ISSN 2615-9732, n=33): ngan nhat 8, trung vi 20, dai nhat 32 tu.
MIN_WORDS, MAX_WORDS = 8, 34          # +2 de phong tieu de dai hon mot chut

# Tu lap duoc chap nhan: hu tu va cac tu mang chuc nang cau truc cua cum danh tu.
REPEATABLE = {
    "và", "của", "cho", "trong", "được", "theo", "một", "các", "là", "bằng", "ở",
    "với", "không", "gần", "như", "đã", "do", "phải", "thì", "còn", "nhưng", "vì",
    "để", "khi", "cả", "mọi", "từng", "hai", "ba", "về", "trên", "dưới", "cùng",
    # cum tu khoa co chua tu lap mot cach hop le (vd "đo đạc, báo cáo, thẩm định"
    # lap tu "đo"; "chi phí gần như bằng không" lap tu "gần"/"như")
    "đo", "đạc", "báo", "cáo", "thẩm", "định", "chi", "phí", "phát", "thải", "thấp",
}

# Viet tat khong duoc xuat hien TRAN trong tieu de. Neu tieu de that su can no,
# phai viet dang khai trien "<cum> (<VIET TAT>)".
BARE_ACRONYM = re.compile(r"\b[A-ZĐ]{2,8}(?:-[A-Z0-9]{2,10})?\b")
# Dinh danh van ban luat: giu nguyen van, khong "khai trien".
LEGAL = re.compile(r"\d{1,5}(?:/\d{4})?/(?:Q[ĐD]|ND|NĐ|TT)-[A-ZĐ]{2,}", re.I)
# Ten rieng / ma hieu quoc te khong can khai trien trong tieu de.
PROPER = {"ERA5", "FAO-56", "VM0051", "IoT", "5G", "NSSI", "iRS-TREE", "ONTOLOGY"}


def read_vi_title() -> str:
    """Doc tieu de VI tu \\hujostitle{} dau tien cua main_hujos_vi.tex."""
    p = HUJOS / "main_hujos_vi.tex"
    if not p.exists():
        raise SystemExit(f"thieu {p}")
    src = p.read_text(encoding="utf-8")
    m = re.search(re.escape(BS) + r"hujostitle\{(.*?)\}", src, re.S)
    if not m:
        raise SystemExit(f"{p.name}: khong tim thay {BS}hujostitle{{}}")
    t = re.sub(r"\s+", " ", m.group(1)).strip()
    t = re.sub(r"%.*", "", t)
    return t


def words_of(t: str) -> list[str]:
    return re.findall(r"[A-Za-zÀ-ỹĐđ]+", t)


def check() -> list[str]:
    t = read_vi_title()
    bad: list[str] = []
    print(f"Tieu de VI: {t}")
    ws = words_of(t)
    print(f"  do dai: {len(ws)} tu (dai cho phep {MIN_WORDS}..{MAX_WORDS} "
          f"— theo 33 tieu de VI da dang cua tap chi)")

    # 1) dau hai cham
    if ":" in t:
        bad.append(f"tieu de TIENG VIET dung dau hai cham: '{t}'. Tieu de VI cua "
                   f"HUJOS la mot cum danh tu lien mach (33/36 bai da dang khong "
                   f"co dau hai cham); viet lai thanh mot cum, noi bang "
                   f"trong/theo/ve/bang/cua.")
    else:
        print("  dau hai cham: khong (dung)")

    # 2) viet tat dung tran
    legal = {m.group(0) for m in LEGAL.finditer(t)}
    for m in BARE_ACRONYM.finditer(t):
        tok = m.group(0)
        if tok in PROPER or tok in legal:
            continue
        if any(tok in lg for lg in legal):
            continue
        bad.append(f"tieu de chua viet tat dung tran: '{tok}'. Tieu de khong duoc "
                   f"bat doc gia doan nghia; viet day du hoac khai trien dang "
                   f"'<cum> ({tok})'.")
    if not any("viet tat dung tran" in b for b in bad):
        print("  viet tat tran: khong (dung)")

    # 3) do dai
    if not (MIN_WORDS <= len(ws) <= MAX_WORDS):
        bad.append(f"tieu de {len(ws)} tu, ngoai dai {MIN_WORDS}..{MAX_WORDS} cua "
                   f"cac bai da dang tren tap chi.")

    # 4) lap tu noi dung
    seen: dict[str, int] = {}
    for w in (x.lower() for x in ws):
        seen[w] = seen.get(w, 0) + 1
    dups = {w: c for w, c in seen.items() if c > 1 and w not in REPEATABLE}
    if dups:
        bad.append(f"tieu de lap tu noi dung {dups} — doc gay cam giac luon quan; "
                   f"viet lai de moi tu chi xuat hien mot lan.")
    else:
        print("  lap tu noi dung: khong (dung)")

    return bad


def main() -> int:
    print("=" * 78)
    print("GATE: quy uoc tieu de tieng Viet cua HUJOS")
    print("=" * 78)
    bad = check()
    print()
    if bad:
        print(f"GATE: FAIL — {len(bad)} loi")
        for b in bad:
            print("  * " + b)
        return 1
    print("GATE: PASS — tieu de VI dung quy uoc tap chi")
    return 0


if __name__ == "__main__":
    sys.exit(main())

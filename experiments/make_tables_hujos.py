#!/usr/bin/env python3
"""Sinh cac bang LaTeX cho ban HUJOS-TT (kho 19x27 cm, 2 cot).

Khong chep lai 400 dong cua make_tables_anchored.py. Thay vao do, import module do
va CHI doi ba hang so ve hinh hoc, roi goi main(). Ly do: moi con so trong bang deu
phai sinh tu cung mot CSV, va hai ban phai cho ra CUNG mot so lieu -- chi khac
chieu rong cot. Chep file se tao ra hai ban roi rac va chac chan lech nhau.

Kho that cua HUJOS-TT (do tu geometry cua preamble, khong doan):
  giay A4 20.5 x 29.7 cm theo TEMPLATE that, le 1.5 tren/duoi va 2 trai/phai
  -> vung text 16.5 x 26.7 cm
  2 cot, columnsep 0.75 cm (425 twips tu template chinh thuc)
  -> moi cot      = (16.5 - 0.75) / 2 = 7.875 cm
  -> table* (2 cot) = 16.5 cm
So voi ban IEEE: 8.85 cm -> 7.125 cm (giam 19.5%), nen moi spec p{...} cua ban
IEEE deu tran va phai co lai theo ti le.

Chay:
    python3 experiments/make_tables_hujos.py
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

import make_tables_anchored as base  # noqa: E402

COL_1_HUJOS = 7.875
COL_2_HUJOS = 16.5
DEST_HUJOS = ROOT / "paper2_hujos" / "tables"

def usable_budget(spec, wide):
    """Ngan sach chieu rong cot CON LAI sau khi tru tien ranh tabcolsep.

    Chep dung cong thuc cua base.table de hai ben khong lech nhau.
    """
    budget = COL_2_HUJOS if wide else COL_1_HUJOS
    return budget - base.TABCOLSEP_CM * (len(spec) - 1)


def fit(spec, wide=False):
    """Ep spec cot vua khop ngan sach, KHONG dung ti le co dinh.

    Ban dau em thu nhan tat ca cot p theo SCALE = 7.125/8.85 = 0.805 va gate
    bao tran (6.44cm > 6.28cm). Sai o dau: tien ranh tabcolsep KHONG co gian
    theo kho giay -- 5 cot luon ton 4 x 0.211cm du giay to hay nho. Nen ti le
    dung phai tinh tren phan con lai sau khi tru tien ranh.

    Cach lam: chi thu nho cac cot p (cot l/c/r giu nguyen uoc tinh cua minh),
    theo dung ti le can thiet de tong bang ngan sach. Neu da vua thi giu nguyen.
    """
    usable = usable_budget(spec, wide)
    p_total = sum(w for k, w in spec if k == "p")
    other = sum((w if w > 0 else 1.0) for k, w in spec if k != "p")
    avail = usable - other
    if p_total <= 0:
        return spec
    if p_total <= avail + 1e-9:
        return spec                      # da vua, khong can thu
    factor = avail / p_total
    # FLOOR chu khong ROUND. Da tinh tay bang so that cua tab_defence:
    #   usable = 7.125 - 0.2109*4 = 6.2814 ; avail = 6.2814 - 0.45 = 5.8314
    #   factor = 5.8314/7.10 = 0.82132
    #   4 cot p = 2.34076 / 1.06772 / 1.23198 / 1.19091
    #   round(...,3) lam tron LEN thanh 2.341+1.068+1.232+1.191 = 5.832
    #   -> vuot ngan sach 0.0006 cm va gate chan dung.
    # floor(...*1000)/1000 dam bao tong KHONG BAO GIO vuot avail.
    return [(k, math.floor(w * factor * 1000) / 1000) if k == "p" else (k, w)
            for k, w in spec]


def main() -> int:
    # doi kho va thu muc xuat
    base.COL_1 = COL_1_HUJOS
    base.COL_2 = COL_2_HUJOS
    base.DEST = DEST_HUJOS
    base.OUT = ROOT / "outputs"

    # base.table tinh ngan sach tu COL_1/COL_2, nen chi can doi hai hang so.
    # Nhung cac spec trong base duoc viet CHO KHO IEEE (8.85 cm), vi vay phai
    # thu nho chung. Cach it xam pham nhat: boc base.table de tu scale spec.
    orig_table = base.table

    def table(spec, lines, *, wide=False):
        return orig_table(fit(spec, wide), lines, wide=wide)

    base.table = table

    print(f"=== HUJOS-TT tables ===")
    print(f"  kho cot 1 = {COL_1_HUJOS} cm | table* = {COL_2_HUJOS} cm")
    print(f"  ngan sach 5 cot = {usable_budget([('p',0)]*5, False):.3f} cm "
          f"(tien ranh {base.TABCOLSEP_CM:.4f} cm x 4)")
    print(f"  ngan sach 2 cot = {usable_budget([('p',0)]*2, False):.3f} cm")

    # SELF-CHECK: chay fit() tren DUNG spec that da lam tran, xac nhan tong vua khop
    probe = [("p", 2.85), ("c", 0.45), ("p", 1.30), ("p", 1.50), ("p", 1.45)]
    fitted = fit(probe, False)
    tot = sum(w for k, w in fitted if k == "p") + sum(
        (w if w > 0 else 1.0) for k, w in fitted if k != "p")
    us = usable_budget(probe, False)
    print(f"  self-check tab_defence: tong {tot:.4f} <= ngan sach {us:.4f} "
          f"-> {'OK' if tot <= us + 1e-9 else 'VAN TRAN'}")
    assert tot <= us + 1e-9, "fit() van lam tran khung"
    print(f"  xuat ra = {DEST_HUJOS}")
    return base.main()


if __name__ == "__main__":
    sys.exit(main())

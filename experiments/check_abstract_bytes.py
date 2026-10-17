#!/usr/bin/env python3
"""Kiem tra byte that cua abstract sau ban va cuoi — nghi van RAW-STRING.

LOI NGHI VAN: trong execute_code em viet chuoi thay the dang raw:
    r"\\emph{shifts commands in time} inflates ... $33\\%$ in\n  paired ..."
Trong RAW string thi:
  * \\\\emph  ->  HAI dau backslash + "emph"   (LaTeX: ngat dong roi chu "emph" tran)
  * \\n      ->  chu 'n' theo sau mot backslash, KHONG phai xuong dong
Nghia la abstract co the dang chua LaTeX rac. No CHUA lo ra vi em chua rebuild
sau ban va do (em chi dem tu bang regex tren file nguon, ma regex dem van ra 244 tu).

BAI HOC (lan thu 5 trong cung mot session): KHONG de backslash trong f-string.
Python bao: SyntaxError: f-string expression part cannot include a backslash.
File nay gan BS = chr(92) o cap module roi moi dua vao f-string.
"""
import sys
from pathlib import Path

BS = chr(92)          # mot dau backslash
DBL = BS + BS         # hai dau backslash
NL = chr(10)

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "paper2_hujos"
# NEO (anchor): chuoi bat buoc phai con trong abstract de lay dung doan can soi byte.
# LOI DA SUA (2026-10-15): neo VI cu "thổi phồng số pha khô" het han sau khi viet lai
# cau MRV. Cu gate in "KHONG tim thay anchor" roi `continue` — bo qua han ban VI ma
# VAN exit 0 (FAIL-OPEN, dung lop loi da ghi trong MEMORY). Neo moi lay cum con ton
# tai, nam ngay truoc "$33\%$" trong abstract_vi.tex.
TARGETS = [("main_hujos.tex", "shifts commands in time"),
           ("abstract_vi.tex", "dịch thời điểm lệnh")]

problems = []
print("=== KIEM TRA BYTE THAT cua doan vua va ===")
for name, anchor in TARGETS:
    fp = D / name
    if not fp.exists():
        problems.append(f"thieu file {name}")
        print(f"{NL}--- {name}: !! KHONG CO FILE {fp}")
        continue
    s = fp.read_text(encoding="utf-8")
    i = s.find(anchor)
    if i < 0:
        # FAIL-CLOSED: neo mat = abstract da doi ma gate chua cap nhat. KHONG duoc
        # bo qua roi bao PASS.
        problems.append(f"{name}: KHONG tim thay anchor {anchor!r} (abstract da doi, cap nhat neo)")
        print(f"{NL}--- {name}: !! KHONG tim thay anchor {anchor!r}")
        continue
    seg = s[max(0, i - 90):i + 330]
    print(f"{NL}--- {name} ---")
    print("  repr:")
    print("   ", repr(seg))
    print("  CHAN DOAN:")
    n_dbl = seg.count(DBL + "emph")
    n_litnl = seg.count(BS + "n ")
    n_pct = seg.count(BS + "%")
    if n_dbl:
        problems.append(f"{name}: {n_dbl} cho co HAI backslash truoc 'emph' (LaTeX rac)")
    if n_litnl:
        problems.append(f"{name}: {n_litnl} chu backslash+n (khong phai xuong dong)")
    if n_pct < 1:
        problems.append(f"{name}: khong thay escape phan-tram trong doan — nghi van $33%$ hong")
    print(f"    so cho co HAI backslash truoc 'emph' : {n_dbl}"
          f"   -> {'RAC, phai sua' if n_dbl else 'OK'}")
    print(f"    so chu backslash+n (khong phai xuong dong): {n_litnl}"
          f"   -> {'RAC' if n_litnl else 'OK'}")
    print(f"    so dau {BS}% (LaTeX escape phan tram)  : {n_pct}"
          f"   -> can >=1 cho moi '$33{BS}%$'")

# Doi chung: ban EN khong bi va bang raw string. Ban that nam trong paper2/blocks/.
print(f"{NL}=== DOI CHUNG: doan tuong ung trong ban EN (khong bi va) ===")
en_cand = [ROOT / "paper2" / "blocks" / "00_title_abstract.tex",
           D / "main_hujos.tex"]
found_en = False
for ieee in en_cand:
    if ieee.exists():
        t = ieee.read_text(encoding="utf-8", errors="replace")
        j = t.find("shifts commands in time")
        if j > 0:
            print(f"   [{ieee.relative_to(ROOT)}]")
            print("   ", repr(t[max(0, j - 60):j + 200]))
            found_en = True
            break
if not found_en:
    print("    (khong tim thay ban doi chung EN)")

# VERDICT — gate PHAI fail-closed (truoc day khong co sys.exit nen luon exit 0).
if problems:
    print(f"{NL}GATE FAIL: {len(problems)} van de:")
    for m in problems:
        print(f"   !! {m}")
    sys.exit(1)
print(f"{NL}GATE PASS: byte abstract sach (khong backslash kep, khong backslash+n rac,"
      f" co escape %), ca EN lan VI deu quet duoc.")
sys.exit(0)

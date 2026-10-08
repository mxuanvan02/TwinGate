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
from pathlib import Path

BS = chr(92)          # mot dau backslash
DBL = BS + BS         # hai dau backslash
NL = chr(10)

D = Path("/media/SAS/Van/DeTai2025/TwinGate_K1/paper2_hujos")
TARGETS = [("main_hujos.tex", "shifts commands in time"),
           ("blocks_vi.tex", "thổi phồng số pha khô")]

print("=== KIEM TRA BYTE THAT cua doan vua va ===")
for name, anchor in TARGETS:
    p = D / name
    s = p.read_text(encoding="utf-8")
    i = s.find(anchor)
    if i < 0:
        print(f"{NL}--- {name}: KHONG tim thay anchor {anchor!r}")
        continue
    seg = s[max(0, i - 90):i + 330]
    print(f"{NL}--- {name} ---")
    print("  repr:")
    print("   ", repr(seg))
    print("  CHAN DOAN:")
    n_dbl = seg.count(DBL + "emph")
    n_litnl = seg.count(BS + "n ")
    print(f"    so cho co HAI backslash truoc 'emph' : {n_dbl}"
          f"   -> {'RAC, phai sua' if n_dbl else 'OK'}")
    print(f"    so chu backslash+n (khong phai xuong dong): {n_litnl}"
          f"   -> {'RAC' if n_litnl else 'OK'}")
    print(f"    so dau {BS}% (LaTeX escape phan tram)  : {seg.count(BS + '%')}"
          f"   -> can >=1 cho moi '$33" + BS + "%$'")
    # so sanh voi ban IEEE (khong bi va bang raw string) lam doi chung
print(f"{NL}=== DOI CHUNG: doan tuong ung trong ban IEEE (khong bi va) ===")
ieee = Path("/media/SAS/Van/DeTai2025/TwinGate_K1/paper2/main.tex")
if ieee.exists():
    t = ieee.read_text(encoding="utf-8", errors="replace")
    j = t.find("shifts commands in time")
    if j > 0:
        print("   ", repr(t[max(0, j - 60):j + 200]))
    else:
        print("    (ban IEEE khong co cum nay)")
else:
    print("    (khong co paper2/main.tex)")

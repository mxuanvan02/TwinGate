#!/usr/bin/env python3
"""Sua 2 loi trong abstract EN + sua claim 'escapes BOTH physical tiers' cho dung du lieu.

LOI 1 (rac LaTeX, do em gay ra o buoc va truoc):
  execute_code dung chuoi thay the dang RAW: r"\\emph{...} ... in\\n  paired ..."
  Trong raw string, \\\\ = HAI backslash that va \\n = chu 'n' kem backslash,
  KHONG phai xuong dong. Ket qua trong file:
    ...merely\\n  \\\\emph{shifts commands in time} ... $33\\%$ in\\n  paired ...
  check_abstract_bytes.py da xac nhan: 1 cho co 2 backslash truoc 'emph',
  1 cho co chu backslash+n. Ban VI khong bi (khong dung raw string).

LOI 2 (sai NOI DUNG, nghiem trong hon):
  Em viet "escapes BOTH the point model and the robust physics layer in 8 of 9".
  Do that tu CSV (tap changed==1, reduced): fraud_timing
      v1 (point model): thoat 5/9  -> v1 BAT DUOC 4/9
      v2 (robust)     : thoat 8/9  -> v2 bat duoc 1/9
  Nen "escapes both" la SAI cho v1. Cau dung, va manh hon:
      v1 bat duoc nhieu hon nhung KET TOI OAN 26.7% nong dan trung thuc;
      v2 het bat oan (5.0% / 0/60) nhung BO LOT 8/9 tan cong dich gio.
      => Co mot danh doi bat buoc: hoac bat oan, hoac bo lot. Khong cau hinh
         vat ly nao thoat khoi no. Chi device anchor thoat, vi no quan sat
         TIMESTAMP — thu ma ca hai tang vat ly deu khong nhin thay (Prop 1).

Chay: python3 experiments/fix_abstract_and_claims.py
"""
from __future__ import annotations

from pathlib import Path

BS = chr(92)          # mot backslash
DBL = BS + BS         # hai backslash
NL = chr(10)

D = Path("/media/SAS/Van/DeTai2025/TwinGate_K1")
H = D / "paper2_hujos"
B = D / "paper2" / "blocks"
fixed = []


def sub_once(path: Path, old: str, new: str, label: str) -> None:
    s = path.read_text(encoding="utf-8")
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"[{label}] anchor khop {n} lan (mong 1) trong {path.name}:"
                         f"{NL}{NL}  ANCHOR = {old[:220]!r}")
    path.write_text(s.replace(old, new), encoding="utf-8")
    fixed.append(f"{path.name}: {label}")


# ---------------------------------------------------------------- LOI 1: rac LaTeX
P = H / "main_hujos.tex"
s = P.read_text(encoding="utf-8")
bad_emph = DBL + "emph{shifts commands in time}"
bad_nl = "$33" + BS + "%$ in" + BS + "n  paired comparison"
print("=== CHAN DOAN TRUOC KHI SUA ===")
print(f"  so cho co '{bad_emph}'           : {s.count(bad_emph)}")
print(f"  so cho co chu backslash+n ('in{BS}n  paired'): {s.count(bad_nl)}")
assert s.count(bad_emph) == 1 and s.count(bad_nl) == 1, "rac LaTeX khong dung nhu da chan doan"

good_emph = BS + "emph{shifts commands in time}"
# dong thoi sua LOI 2 ngay trong cung doan: bo "both physical tiers in 89%"
old_seg = (bad_emph + " inflates creditable dry phases by $33" + BS + "%$ in" + BS +
           "n  paired comparison and escapes both physical tiers in $89" + BS +
           "%$ of altered logs.")
new_seg = (good_emph + " inflates creditable dry phases by $33" + BS + "%$ in paired" + NL +
           "  comparison, and no physical tier escapes it usefully: the point model that" + NL +
           "  flags $4$ of $9$ altered logs also accuses $26.7" + BS + "%$ of honest" + NL +
           "  farmers, while the robust tier that accuses none lets $8$ of $9$ through.")
sub_once(P, old_seg, new_seg, "abstract EN: sua rac LaTeX + claim 'both tiers'")

# ---------------------------------------------------------------- LOI 2: cac cho con lai
sub_once(B / "05_design_results.tex",
'''Table~\\ref{tab:defence} shows the corresponding escape
rates: time-shifting escapes both the point model and the robust physics layer
in $8$ of $9$ altered logs, and the rational adversary in $6$ of $6$, exactly as''',
'''Table~\\ref{tab:defence} shows the corresponding escape
rates, and they are the heart of the result: time-shifting escapes the robust
physics layer in $8$ of $9$ altered logs and the rational adversary in $6$ of
$6$. The point model catches more of it ($4$ of $9$), but it is precisely the
detector that accuses $26.7\\%$ of honest farmers; the robust tier removes the
false accusation and gives the detection back. \\emph{No physical configuration
escapes that trade-off} --- it must either accuse the innocent or miss the
permutation --- because both tiers are functions of the replayed trajectory,
exactly as''',
"05: escape 'both tiers' -> dung so v1 4/9 vs v2 8/9 + danh doi bat buoc")

sub_once(B / "05_design_results.tex",
'''$37/37$, time-shift escape $8/9$ and $3/3$, paired credit inflation $+33\\%$
($t=5.29$) and $+38\\%$ ($t=3.46$).''',
'''$37/37$, robust-tier time-shift escape $8/9$ and $3/3$, paired credit inflation
$+33\\%$ ($t=5.29$) and $+38\\%$ ($t=3.46$).''',
"05: tong ket ghi ro 'robust-tier' de khong hieu nham la ca hai tang")

sub_once(B / "06_discussion_conclusion.tex",
'''claimed times inflates creditable dry phases by $33\\%$ to $38\\%$ in paired
comparison while escaping both physical tiers in $8$ of $9$ and $3$ of $3$
altered logs, and we prove this is unavoidable''',
'''claimed times inflates creditable dry phases by $33\\%$ to $38\\%$ in paired
comparison while escaping the robust physical tier in $8$ of $9$ and $3$ of $3$
altered logs --- and the point model that catches more of it is the same model
that accuses $26.7\\%$ of honest farmers, so no physical configuration escapes
the trade-off. We prove this is unavoidable''',
"conclusion: 'both physical tiers' -> robust tier, them danh doi bat buoc")

sub_once(H / "blocks_vi.tex",
'''trong so sánh ghép cặp và vượt cả hai lớp phòng thủ ở $89\\%$ nhật ký bị sửa.''',
'''trong so sánh ghép cặp; không lớp vật lý nào thoát được một cách dùng được: bộ
phát hiện bắt được $4/9$ nhật ký bị sửa thì cũng kết tội oan $26{,}7\\%$ nông dân
trung thực, còn bộ bền vững không kết tội oan thì bỏ lọt $8/9$.''',
"abstract VI: 'ca hai lop' -> dung so v1 4/9 vs v2 8/9")

print(f"{NL}=== DA SUA {len(fixed)} CHO ===")
for f in fixed:
    print(f"  OK {f}")

# ---------------------------------------------------------------- kiem tra lai byte
print(f"{NL}=== KIEM TRA LAI BYTE (khong de rac sot lai) ===")
s = P.read_text(encoding="utf-8")
i = s.find("shifts commands in time")
seg = s[max(0, i - 60):i + 420]
print(f"  con HAI backslash truoc emph : {seg.count(DBL + 'emph')}  (mong 0)")
print(f"  con chu backslash+n          : {seg.count(BS + 'n ')}  (mong 0)")
assert seg.count(DBL + "emph") == 0, "van con rac 2 backslash"
assert seg.count(BS + "n ") == 0, "van con chu backslash+n"
print(f"  doan abstract EN sau khi sua:{NL}{seg[:400]}")

# dem tu abstract (tran 250)
import re


def words(t):
    t = re.sub(r"\$[^$]*\$", " MATH ", t)
    t = re.sub(BS + BS + r"[a-zA-Z]+\*?", " ", t)
    t = re.sub(r"[{}~$&" + BS + BS + r"]", " ", t)
    return [w for w in t.split() if re.search(r"[A-Za-z0-9]", w)]


i0 = s.index(BS + "noindent" + BS + "textbf{Abstract.}")
j0 = s.index(BS + "noindent" + BS + "textbf{Keywords:}")
vi = (H / "blocks_vi.tex").read_text(encoding="utf-8")
a0 = vi.index("MRV là nút thắt")
b0 = vi.index(BS + "textbf{Từ khóa:}")
we, wv = len(words(s[i0:j0])), len(words(vi[a0:b0]))
print(f"{NL}=== ABSTRACT sau khi sua ===")
print(f"  EN: {we} tu (tran 250) -> {'OK' if we <= 250 else 'VUOT ' + str(we - 250)}")
print(f"  VI: {wv} tu (tran 250) -> {'OK' if wv <= 250 else 'VUOT ' + str(wv - 250)}")
if we > 250:
    raise SystemExit(f"abstract EN vuot tran: {we} tu — phai cat {we - 250} tu")
if wv > 250:
    raise SystemExit(f"abstract VI vuot tran: {wv} tu — phai cat {wv - 250} tu")
print(f"{NL}=== XONG ===")

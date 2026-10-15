#!/usr/bin/env python3
"""Kiem tra trang that + chi va nhung cho con thieu (idempotent).

Ly do file nay ton tai: fix_abstract_and_claims.py dung sub_once ghi NGAY sau moi
anchor, nen khi anchor thu 5 fail thi 4 cai dau DA GHI. Chay lai script cu se fail
o anchor 1 (da thay roi -> khop 0 lan). Vi vay o day kiem tra trang thai tung cho
trước, roi chi va nhung cho chua dat.

Nguyen nhan anchor thu 5 fail: em viet anchor thanh MOT dong
    'trong so sanh ghep cap va vuot ca hai lop phong thu o $89\\%$ nhat ky bi sua.'
nhung trong file that co XUONG DONG giua "ghep cap" va "va vuot" (do lan va truoc
dung chuoi co \\n). => dung regex voi \\s+ cho moi cho xuong dong, khong ghep tay.
"""
from __future__ import annotations

import re
from pathlib import Path

BS = chr(92)
DBL = BS + BS
NL = chr(10)

D = Path("/media/SAS/Van/DeTai2025/TwinGate_K1")
H = D / "paper2_hujos"
B = D / "paper2" / "blocks"
fixed, already, missing = [], [], []


def report(name, ok_now, still_bad):
    """ok_now: chuoi dac trung cua ban DA SUA. still_bad: chuoi cua ban CU."""
    return ok_now, still_bad


def try_patch(path, patterns_new, olds, label):
    """patterns_new: list regex; olds: list chuoi cu de phat hien 'da sua chua'."""
    s = path.read_text(encoding="utf-8")
    if any(o in s for o in olds):
        already.append(f"{path.name}: {label}")
        return
    for pat, rep in patterns_new:
        s2, n = re.subn(pat, lambda m: rep, s, flags=re.S)
        if n == 1:
            s = s2
            break
    else:
        missing.append(f"{path.name}: {label} — khong anchor nao khop")
        return
    path.write_text(s, encoding="utf-8")
    fixed.append(f"{path.name}: {label}")


print("=== TRANG THAI HIENTAI cua 5 cho can sua ===")

# ---- 1) abstract EN: rac LaTeX \\emph + claim 'both physical tiers' ----
p1 = H / "main_hujos.tex"
s1 = p1.read_text(encoding="utf-8")
i = s1.find("shifts commands in time")
seg1 = s1[max(0, i - 60):i + 430] if i >= 0 else ""
print(f"{NL}[1] main_hujos.tex abstract EN:")
print(f"    rac 2-backslash emph : {seg1.count(DBL + 'emph')}  (mong 0)")
print(f"    rac chu backslash+n  : {seg1.count(BS + 'n ')}  (mong 0)")
print(f"    con 'escapes both'   : {'both physical tiers' in s1}")
print(f"    da co 'No physical tier' / 'no physical tier': "
      f"{'physical tier' in s1.lower()}")
print(f"    doan that: {seg1[:300]!r}")

# ---- 2) 05: escape 'both tiers' -> danh doi bat buoc ----
p2 = B / "05_design_results.tex"
s2 = p2.read_text(encoding="utf-8")
print(f"{NL}[2] 05_design_results.tex:")
print(f"    con 'escapes both the point model': {'escapes both the point model' in s2}")
print(f"    da co 'No physical configuration' : {'No physical configuration' in s2}")
print(f"    con '$8$ of $9$ altered logs'     : {'8$ of $9$ altered logs' in s2}")

# ---- 3) 05: tong ket 'robust-tier' ----
print(f"{NL}[3] 05 tong ket:")
print(f"    con 'time-shift escape $8/9$' (khong ro rang): "
      f"{'time-shift escape $8/9$' in s2}")
print(f"    da co 'robust-tier time-shift escape'         : "
      f"{'robust-tier time-shift escape' in s2}")

# ---- 4) 06 conclusion ----
p4 = B / "06_discussion_conclusion.tex"
s4 = p4.read_text(encoding="utf-8")
print(f"{NL}[4] 06_discussion_conclusion.tex:")
print(f"    con 'escaping both physical tiers': {'escaping both physical tiers' in s4}")
print(f"    da co 'escapes the trade-off'     : {'escapes' in s4 and 'trade-off' in s4}")

# ---- 5) blocks_vi ----
p5 = H / "blocks_vi.tex"
s5 = p5.read_text(encoding="utf-8")
print(f"{NL}[5] blocks_vi.tex abstract VI:")
print(f"    con 'vượt cả hai lớp phòng thủ': {'vượt cả hai lớp phòng thủ' in s5}")
print(f"    da co 'không lớp vật lý nào'  : {'không lớp vật lý nào' in s5}")
j = s5.find("thổi phồng số pha khô")
print(f"    doan that: {s5[max(0,j-60):j+300]!r}" if j >= 0 else "    (khong tim thay)")

print(f"{NL}{'='*88}")
print("=== VA NHUNG CHO CON THIEU ===")

# [5] blocks_vi: dung regex chiu xuong dong
NEW_VI = ("trong so sánh ghép cặp; không lớp vật lý nào thoát được một cách dùng được: bộ"
          + NL + "phát hiện bắt được $4/9$ nhật ký bị sửa thì cũng kết tội oan $26{,}7\\%$ nông dân"
          + NL + "trung thực, còn bộ bền vững không kết tội oan thì bỏ lọt $8/9$.")
if "vượt cả hai lớp phòng thủ" in s5 and "không lớp vật lý nào" not in s5:
    pat = (r"trong so sánh ghép cặp\s+và vượt cả hai lớp phòng thủ ở \$89\\%\$ nhật ký bị"
           r"\s+sửa\.")
    s5n, n = re.subn(pat, lambda m: NEW_VI, s5, flags=re.S)
    print(f"  [5] regex khop {n} lan")
    if n == 1:
        p5.write_text(s5n, encoding="utf-8")
        fixed.append("blocks_vi.tex: 'ca hai lop' -> v1 4/9 vs v2 8/9")
    else:
        missing.append("blocks_vi.tex: regex khong khop — phai doc nguyen van")
elif "không lớp vật lý nào" in s5:
    already.append("blocks_vi.tex: da sua")

print(f"{NL}=== KET QUA ===")
for f in fixed:
    print(f"  MOI SUA : {f}")
for f in already:
    print(f"  DA SUA  : {f}")
for f in missing:
    print(f"  CON LOI : {f}")

# ---------------------------------------------------------------- kiem tra byte cuoi
print(f"{NL}=== KIEM TRA BYTE CUOI (rac LaTeX phai bang 0) ===")
s1 = (H / "main_hujos.tex").read_text(encoding="utf-8")
i = s1.find("shifts commands in time")
seg1 = s1[max(0, i - 60):i + 500] if i >= 0 else ""
n_dbl = seg1.count(DBL + "emph")
n_litnl = seg1.count(BS + "n ")
print(f"  2-backslash emph: {n_dbl} | chu backslash+n: {n_litnl}")
assert n_dbl == 0, "VAN CON RAC 2 backslash trong abstract EN"
assert n_litnl == 0, "VAN CON chu backslash+n trong abstract EN"

s5 = (H / "blocks_vi.tex").read_text(encoding="utf-8")
assert "vượt cả hai lớp phòng thủ" not in s5, "blocks_vi VAN con claim sai 'ca hai lop'"
assert "không lớp vật lý nào" in s5, "blocks_vi chua duoc sua"
print(f"  abstract VI: OK (het claim 'ca hai lop')")

s2 = (B / "05_design_results.tex").read_text(encoding="utf-8")
assert "escapes both the point model" not in s2, "05 VAN con claim sai"
s4 = (B / "06_discussion_conclusion.tex").read_text(encoding="utf-8")
assert "escaping both physical tiers" not in s4, "06 VAN con claim sai"
print(f"  05 + 06: OK (het claim 'both tiers')")


# ---------------------------------------------------------------- dem tu abstract
def words(t):
    t = re.sub(r"\$[^$]*\$", " MATH ", t)
    t = re.sub(BS + BS + r"[a-zA-Z]+\*?", " ", t)
    t = re.sub(r"[{}~$&" + BS + BS + r"]", " ", t)
    return [w for w in t.split() if re.search(r"[A-Za-z0-9]", w)]


i0 = s1.index(BS + "noindent" + BS + "textbf{Abstract.}")
j0 = s1.index(BS + "noindent" + BS + "textbf{Keywords:}")
a0 = s5.index("MRV là nút thắt")
b0 = s5.index(BS + "textbf{Từ khóa:}")
we, wv = len(words(s1[i0:j0])), len(words(s5[a0:b0]))
print(f"{NL}=== ABSTRACT (tran 250 tu cho CA HAI ngon ngu) ===")
print(f"  EN: {we} tu -> {'OK' if we <= 250 else 'VUOT ' + str(we - 250)}")
print(f"  VI: {wv} tu -> {'OK' if wv <= 250 else 'VUOT ' + str(wv - 250)}")
if we > 250:
    raise SystemExit(f"abstract EN vuot tran {we - 250} tu — phai cat")
if wv > 250:
    raise SystemExit(f"abstract VI vuot tran {wv - 250} tu — phai cat")
print(f"{NL}=== XONG ===")

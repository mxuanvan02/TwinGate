#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KIEM CHUNG AM (negative control) cho check_supp_vi_numbers.py.

Gate vua sai 3 lan lien tiep (bat doi xung EN/VI) truoc khi PASS, nen PASS mot
minh chua du tin cay. Script nay chung minh gate THAT SU bat duoc loi bang cach
TAM THOI sua mot so trong ban dich roi chay gate, sau do HOAN NGUYEN.

Quy trinh: sao luu -> pha 1 so -> chay gate (mong FAIL) -> hoan nguyen ->
chay gate (mong PASS) -> xac nhan file giong het ban sao luu (sha256).
Neu bat ky buoc nao sai ket qua mong doi -> exit 1.
KHONG de lai file bi sua: hoan nguyen bang sha256 doi chieu.
"""
from __future__ import annotations
import hashlib, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "paper2_hujos" / "supplementary_vi.tex"
GATE = [sys.executable, str(ROOT / "experiments" / "check_supp_vi_numbers.py")]

# (chuoi that, chuoi pha, mo ta) — 3 phep thu tren 3 loai so khac nhau
# NGUYEN VAN LAY TU FILE THAT (da kiem tra 2026-10-13): ban dich viet $+33\%$
# (co dau cong), KHONG phai $33\%$. LOI DA SUA: case 2 ban dau dung '$33\%' nen
# khong tim thay chuoi de pha -> script bao 'bo qua' roi ket luan sai rang
# 'gate CO VAN DE' trong khi gate van tot. Bai hoc: script kiem thu phai lay
# nguyen van bang cach tra file, khong viet tu tri nho — va khi mot case khong
# chay duoc thi ket luan phai la 'KHONG XAC DINH', khong phai 'gate hong'.
CASES = [
    ("$116/116$", "$115/116$", "so ket qua chinh 116 -> 115"),
    ("$+33\\%$", "$+39\\%$", "muc thoat khi ghep cap +33% -> +39%"),
    ("$0{,}9987$", "$0{,}9877$", "do can kiet dinh 0,9987 -> 0,9877"),
]


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run_gate() -> int:
    return subprocess.run(GATE, cwd=ROOT, capture_output=True, text=True).returncode


def main() -> int:
    if not TARGET.exists():
        print(f"  !! khong thay {TARGET}"); return 1
    backup = Path("/tmp/supp_vi_backup.tex")
    shutil.copy2(TARGET, backup)
    orig_sha = sha(TARGET)
    print(f"  sha256 goc: {orig_sha[:16]}…")

    base_rc = run_gate()
    print(f"\n  [buoc 0] gate tren ban nguyen trang: exit={base_rc} (mong 0)")
    if base_rc != 0:
        print("  !! gate FAIL truoc khi pha -> khong the kiem chung am"); return 1

    ok = True
    for i, (real, broken, desc) in enumerate(CASES, 1):
        s = backup.read_text(encoding="utf-8")
        if s.count(real) < 1:
            print(f"\n  [case {i}] !! khong tim thay {real!r} de pha ({desc}) -> bo qua")
            ok = False
            continue
        TARGET.write_text(s.replace(real, broken, 1), encoding="utf-8")
        rc = run_gate()
        verdict = "BAT DUOC" if rc != 0 else "!! KHONG BAT DUOC"
        print(f"\n  [case {i}] pha {desc}: gate exit={rc} -> {verdict}")
        if rc == 0:
            ok = False
        # hoan nguyen
        shutil.copy2(backup, TARGET)
        if sha(TARGET) != orig_sha:
            print("     !! hoan nguyen that bai"); return 1
        print(f"     hoan nguyen OK (sha256 khop)")

    final_rc = run_gate()
    print(f"\n  [buoc cuoi] gate sau khi hoan nguyen: exit={final_rc} (mong 0)")
    same = sha(TARGET) == orig_sha
    print(f"  file giong het ban goc: {same}")
    backup.unlink(missing_ok=True)

    if ok and final_rc == 0 and same:
        print("\nKET LUAN: gate that su bat duoc so lieu bi sua sai (3/3 case).")
        return 0
    print("\nKET LUAN: gate CO VAN DE — khong duoc tin ket qua PASS cua no.")
    return 1


if __name__ == "__main__":
    sys.exit(main())

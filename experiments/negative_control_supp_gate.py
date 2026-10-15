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
# LOI DA SUA (batch 17): gate check_supp_vi_numbers.py doc supplementary_body.tex (than phu luc
# dung chung) tu batch 16, con TARGET van tro supplementary_body.tex -> tiem loi vao file
# gate KHONG doc, ca 3 case "khong tim thay chuoi de pha -> bo qua", roi ket luan sai
# rang "gate CO VAN DE — khong duoc tin ket qua PASS". Da chung minh gate van tot bang
# kiem chung am that trong sandbox /tmp: 3/3 case bi bat (exit=1), sha256 hoan nguyen.
TARGET = ROOT / "paper2_vi_submission" / "src" / "supplementary_body.tex"
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
    # GUARD fail-closed (batch 17): TARGET phai la file ma gate THAT SU doc. Neu khong,
    # moi case se "bo qua" va script ket luan SAI ve gate. Day dung la lop loi fail-open
    # da ghi trong MEMORY: helper tra ve 0 khi thieu phu thuoc -> artifact bao 'ĐẠT'.
    gate_path = Path(GATE[1])
    gate_src = gate_path.read_text(encoding="utf-8") if gate_path.exists() else ""
    if TARGET.name not in gate_src:
        print(f"  !! TARGET {TARGET.name} KHONG xuat hien trong nguon cua gate "
              f"{gate_path.name}: kiem chung am se vo nghia. Cap nhat TARGET.")
        return 1
    backup = Path("/tmp/supp_vi_backup.tex")
    shutil.copy2(TARGET, backup)
    orig_sha = sha(TARGET)
    print(f"  sha256 goc: {orig_sha[:16]}…")

    base_rc = run_gate()
    print(f"\n  [buoc 0] gate tren ban nguyen trang: exit={base_rc} (mong 0)")
    if base_rc != 0:
        print("  !! gate FAIL truoc khi pha -> khong the kiem chung am"); return 1

    ok = True
    inconclusive = False
    for i, (real, broken, desc) in enumerate(CASES, 1):
        s = backup.read_text(encoding="utf-8")
        if s.count(real) < 1:
            print(f"\n  [case {i}] !! khong tim thay {real!r} de pha ({desc}) -> bo qua")
            # LOI DA SUA (batch 17): docstring cua chinh file nay (dong 26-28) da ghi bai
            # hoc "khi mot case khong chay duoc thi ket luan phai la KHONG XAC DINH, khong
            # phai gate hong" — nhung code chua cai dat. Thieu bang chung khong phai la
            # bang chung cua loi; ket luan "gate hong" khi chua chay case nao la sai.
            inconclusive = True
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

    if inconclusive and ok:
        print("\nKET LUAN: KHONG XAC DINH — co case khong chay duoc (thieu chuoi nguyen van "
              "de pha), khong du bang chung de ket luan ve gate. Day KHONG phai 'gate hong'.")
        return 1
    if ok and final_rc == 0 and same and not inconclusive:
        print(f"\nKET LUAN: gate that su bat duoc so lieu bi sua sai ({len(CASES)}/{len(CASES)} case).")
        return 0
    print("\nKET LUAN: gate CO VAN DE — khong duoc tin ket qua PASS cua no.")
    return 1


if __name__ == "__main__":
    sys.exit(main())

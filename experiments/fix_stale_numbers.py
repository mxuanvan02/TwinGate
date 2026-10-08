#!/usr/bin/env python3
"""Sua cac con so CU con sot trong bai, bang THAY CHUOI LITERAL (khong regex).

BAI HOC — vi sao khong dung regex o day:
  Em da 7 lan vep lop loi escape trong cung mot session (f-string chua backslash,
  re.sub voi chuoi thay the chua \\midrule, raw-string r"\\emph" cho ra 2 backslash,
  r"\\n" cho ra chu backslash+n, va regex doi `$78\\%$` thanh `78\\%%`).
  Moi lan deu la em GO LAI chuoi tu tri nho / tu output da chuan hoa khoang trang.
  => CACH CHUA DUT DIEM: lay anchor ngan ma chac chan co that, tim vi tri bang
  str.find, roi cat-toa-do de lay dung doan can thay. Khong co lop escape nao.

Idempotent: neu van ban MOI da co trong file thi bo qua (script nay da chay mot
lan va ghi duoc ban va #1 truoc khi fail o #2, nen file dang o trang thai nua voi).

So moi, da verify tu outputs/eval_theta_*.csv bang verify_paper_claims.py (31/31 PASS):
  fraud_timing   : reduced paired +33% (n=9, t=5.29) | full paired +38% (n=3, t=3.46)
                   v1 bat 4/9; v2 bat 1/9 (thoat 8/9); anchor 9/9
  fraud_rational : reduced paired +35% (n=6, t=4.39) | full +40% (n=2)
                   v1 THOAT 6/6, v2 THOAT 6/6
  honest_field   : v1 bat oan 26.7% (16/60) | v2 5.0% (3/60) | anchor 0% (0/60)

Chay: python3 experiments/fix_stale_numbers.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

BS = chr(92)          # mot backslash
NL = chr(10)
D = Path(__file__).resolve().parents[1]
B = D / "paper2" / "blocks"
H = D / "paper2_hujos"

results = []


def span_replace(path: Path, start_anchor: str, end_anchor: str, new: str, label: str,
                 done_marker: str) -> None:
    """Thay doan [start_anchor .. het end_anchor] bang `new`, bang toa do literal.

    start_anchor : chuoi ngan chac chan nam o DAU doan can thay
    end_anchor   : chuoi ngan nam o CUOI doan can thay (duoc giu lai neu muon)
    done_marker  : chuoi dac trung cua ban MOI, de biet da sua chua (idempotent)
    """
    s = path.read_text(encoding="utf-8")
    if done_marker in s:
        results.append(("SKIP (da sua)", label))
        return
    i = s.find(start_anchor)
    if i < 0:
        results.append(("FAIL (khong thay anchor dau)", label))
        print(f"  !! {label}: khong tim thay {start_anchor[:60]!r}")
        return
    j = s.find(end_anchor, i)
    if j < 0:
        results.append(("FAIL (khong thay anchor cuoi)", label))
        print(f"  !! {label}: tim thay dau nhung khong thay cuoi {end_anchor[:60]!r}")
        print(f"     doan that: {s[i:i+420]!r}")
        return
    end = j + len(end_anchor)
    old = s[i:end]
    path.write_text(s[:i] + new + s[end:], encoding="utf-8")
    results.append(("OK", label))
    print(f"  [{label}]")
    print(f"    CU : {old[:200]!r}")
    print(f"    MOI: {new[:200]!r}")


# ---------------------------------------------------------------- 1) 01_intro.tex:55
P1 = B / "01_intro.tex"
NEW1 = ("We" + NL +
        "measure a paired inflation of $+33" + BS + "%$ over nine altered logs "
        "($t=5.29$)" + NL +
        "under the reduced uncertainty set and $+38" + BS + "%$ over three "
        "($t=3.46$)" + NL +
        "under the full one. The point model catches four of the nine, but it is" + NL +
        "the same detector that accuses $26.7" + BS + "%$ of honest farmers; the "
        "robust" + NL +
        "tier that cuts false accusation to $5.0" + BS + "%$ lets eight of the "
        "nine" + NL +
        "through.")
span_replace(P1,
             start_anchor="We" + NL + "measure an inflation of $69",
             end_anchor="of cases.",
             new=NEW1,
             label="01_intro: 69/78/91 -> paired +33/+38, v1 4/9 vs v2 8/9",
             done_marker="paired inflation of $+33")

# ---------------------------------------------------------------- 2) 01_intro.tex:75
NEW2 = ("and we measure the" + NL +
        "resulting credit inflation at $+33$ to $+38" + BS + "%$ in paired" + NL +
        "comparison" + NL +
        "(Sec.~" + BS + "ref{sec:timeshift}, Table~" + BS + "ref{tab:credit}).")
span_replace(P1,
             start_anchor="and we measure the" + NL + "resulting credit inflation at $69",
             end_anchor="ref{tab:credit}).",
             new=NEW2,
             label="01_intro contributions: 69-78% -> +33 to +38% paired",
             done_marker="credit inflation at $+33$ to $+38")

# ---------------------------------------------------------------- 3) 04_anchor.tex:85
# CHI sua con so. GIU claim "escaping every physics-based and volume-based test"
# vi no DUNG: rational adversary thoat 6/6 o ca v1 lan v2 (da verify tu CSV).
P3 = B / "04_anchor.tex"
NEW3 = ("measures a rational adversary inflating credits by $+35" + BS + "%$ in paired" + NL +
        "comparison while escaping every physics-based and volume-based test" + NL +
        "($6/6$ altered logs, under both the point model and the robust tier).")
span_replace(P3,
             start_anchor="measures a rational adversary inflating credits by $69",
             end_anchor="volume-based test.",
             new=NEW3,
             label="04_anchor: 69% -> +35% paired (giu claim 'escaping every test')",
             done_marker="inflating credits by $+35")

# ---------------------------------------------------------------- 4) 00_title_abstract.tex: FILE CHET
P4 = B / "00_title_abstract.tex"
if P4.exists():
    t4 = P4.read_text(encoding="utf-8")
    if t4.startswith("% FILE CHET"):
        results.append(("SKIP (da danh dau)", "00_title_abstract: file chet"))
    else:
        parts = [
            "% FILE CHET -- KHONG duoc " + BS + "input boi build nao (kiem tra 2026-10-07):",
            "%   paper2_hujos/main_hujos.tex va paper2/main.tex deu khong nhap file nay.",
            "% Abstract that nam trong paper2_hujos/main_hujos.tex (EN) va blocks_vi.tex (VI),",
            "% duoc quan ly boi experiments/rewrite_abstracts.py.",
            "% Giu file chi de doi chieu lich su. Cac con so o day DA CU: thuoc cach tinh",
            "% unpaired ma experiments/verify_paper_claims.py da bac bo (baseline lech mau).",
            "% KHONG copy so tu file nay vao bai.",
        ]
        hdr = NL.join(parts) + NL
        P4.write_text(hdr + t4, encoding="utf-8")
        results.append(("OK", "00_title_abstract: danh dau FILE CHET + canh bao so cu"))

print(f"{NL}=== KET QUA ===")
for st, lab in results:
    print(f"  {st:<32} {lab}")
if any(r[0].startswith("FAIL") for r in results):
    print(f"{NL}CO CHO CHUA SUA DUOC — khong duoc bo qua.")
    sys.exit(1)

# ---------------------------------------------------------------- 5) QUET LAI toan bo file duoc build
main = (H / "main_hujos.tex").read_text(encoding="utf-8")
built = re.findall(re.escape(BS) + r"input\{([^}]+)\}", main)
live = [H / "main_hujos.tex", H / "blocks_vi.tex"]
for rel in built:
    if rel == "preamble":
        continue
    for cand in (H / f"{rel}.tex", B / f"{Path(rel).name}.tex",
                 H / "tables" / f"{Path(rel).name}.tex"):
        if cand.exists():
            live.append(cand)
            break
live = list(dict.fromkeys(live))

# Moi muc: (chuoi can tim, ly do, ngu canh DUOC PHEP chua no).
# Ngu canh duoc phep = cho ma so cu xuat hien de GIAI THICH vi sao no sai, khong
# phai de lam CLAIM. Vi du 05_design_results.tex viet "$4.87$ paired baselines
# against $3.23$ overall" de chi ra baseline lech mau — xoa cau do se lam mat di
# bang chung ve tinh trung thuc cua bai.
STALE = [
    ("$69" + BS + "%$", "69% (unpaired)", None),
    ("$78" + BS + "%$", "78% (unpaired)", None),
    ("$91" + BS + "%$", "91% (mau so sai)", None),
    ("$78.3" + BS + "%$", "78.3% (mau so sai)", None),
    ("$40" + BS + "%$", "40% (khong khop to hop nao)", None),
    ("$75$" + BS + ",mm", "75mm (khong co trong du lieu)", None),
    ("$3.23$", "3.23 (baseline lech mau)", "paired baselines against"),
    ("$5.48$", "5.48 (unpaired)", "against $3.23$ overall"),
    ("$6.14$", "6.14 (unpaired)", None),
    ("$3.44$", "3.44 (baseline lech mau)", None),
    ("+63" + BS + "%", "+63% (unpaired)", None),
    ("+70" + BS + "%", "+70% (unpaired)", None),
    ("+52" + BS + "%", "+52% (unpaired)", None),
    ("+53" + BS + "%", "+53% (unpaired)", None),
    ("Measurement, reporting", "thuat ngu sai (tu khoa la Monitoring)", None),
    ("escapes both the point model", "claim sai 'escapes both'", None),
    ("removes the false accusation", "claim sai 'removes false accusation'", None),
    ("robust tier that accuses none", "claim sai 'accuses none' cho v2", None),
]

print(f"{NL}=== QUET SO/CLAIM CU tren {len(live)} file DUOC BUILD THAT ===")
tot = 0
allowed_hits = 0
for f in live:
    t = re.sub(r"(?m)^\s*%.*$", "", f.read_text(encoding="utf-8", errors="replace"))
    for needle, why, allowed_ctx in STALE:
        k = 0
        while True:
            k = t.find(needle, k)
            if k < 0:
                break
            ctx = re.sub(r"\s+", " ", t[max(0, k - 260):k + 260])
            if allowed_ctx and allowed_ctx in ctx:
                # xuat hien trong ngu canh GIAI THICH -> hop le, khong phai claim
                allowed_hits += 1
                ln = t[:k].count(NL) + 1
                print(f"  ~~ {f.name}:{ln} '{why}' nhung o ngu canh giai thich "
                      f"('{allowed_ctx}') -> HOP LE")
                k += len(needle)
                continue
            ln = t[:k].count(NL) + 1
            tot += 1
            short = re.sub(r"\s+", " ", t[max(0, k - 85):k + 55])
            print(f"  !! {f.name}:{ln} con '{why}' | ...{short}...")
            k += len(needle)
print(f"  TONG: {tot}" + ("  -> SACH" if tot == 0 else "  -> van con, phai sua tiep"))
sys.exit(0 if tot == 0 else 1)

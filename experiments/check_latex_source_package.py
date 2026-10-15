#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GATE: goi nguon LaTeX phai SACH va phai BIEN DICH DUOC tu thu muc sach.

Chay:  python3 experiments/check_latex_source_package.py [duong_dan_zip]
Mac dinh doc /tmp/source_latex_final.zip; neu khong co thi tu dong goi lai tu
paper2_hujos/ theo dung danh sach INCLUDE (giong batch 19/20).

Ly do gate nay ton tai (batch 19-20, 2026-10-15):
  * Zip cu chua 76 tep, trong do 44 la rac/khong thuoc ban nop: .bbl/.blg, toan bo
    docx_build/ (~40 XML), qa_png/, probe_width.*, script .py, cay EN rieng, hinh *_en.png.
  * Zip cu KHONG bien dich duoc bang lenh pho bien nhat: `latexmk` tran exit=12,
    `latexmk -pdf` exit=12, `pdflatex` exit=1 voi "Fatal Package fontspec Error".
    Hai nguyen nhan goc: (a) thieu .latexmkrc dat $pdf_mode=5 -> latexmk goi pdflatex;
    (b) thieu @default_files -> latexmk tu bien dich ca cac MANH \\input (preamble.tex,
    supp_body_vi.tex, supp_stubs_vi.tex) nhu tai lieu doc lap, no ra
    "No counter 'proposition' defined" / "Missing \\begin{document}".
  * Bai hoc: mo hinh "build trong repo thanh cong" KHONG chung minh "nguoi nhan goi
    nguon build duoc". Phai giai nen vao thu muc sach va chay LENH MAC DINH cua nguoi
    dung (latexmk tran), khong phai lenh ma minh van dung.

Gate FAIL (exit 1) khi:
  1. zip co tep rac (artifact build, docx_build, qa_*, probe_*, *.py, hinh *_en)
  2. zip thieu bat cu tep nao trong closure phu thuoc that cua 2 tai lieu goc
  3. `latexmk` tran trong thu muc sach khong exit=0
  4. khong sinh du main_hujos_vi.pdf (33 trang) va supplementary_vi.pdf (13 trang)
  5. log co loi '!' hoac 'No counter'/'Missing \\begin{document}'/'Emergency stop'
  6. goi nham pdflatex ma KHONG nhan duoc thong bao huong dan (guard iftex)
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
H = ROOT / "paper2_hujos"

INCLUDE_ROOT = [
    "main_hujos_vi.tex", "supplementary_vi.tex", "preamble.tex",
    "supp_body_vi.tex", "supp_stubs_vi.tex", "refs.bib", "vancouver.bst",
    ".latexmkrc", "README_BUILD.md",
    "main_hujos_vi.pdf", "supplementary_vi.pdf",
]
ROOTS = ["main_hujos_vi.tex", "supplementary_vi.tex"]

JUNK = re.compile(
    r"(\.(aux|bbl|blg|log|out|toc|lof|lot|xdv|synctex\.gz|fdb_latexmk|fls)$"
    r"|_en\.png$|\.py$|^docx_build/|^qa_png/|^qa_docx/|^_backups/|^probe_)"
)

fails: list[str] = []


def fail(msg: str) -> None:
    fails.append(msg)
    print(f"  !! FAIL: {msg}")


def closure() -> set[str]:
    """Tap phu thuoc that: de qui \\input/\\include/\\InputIfFileExists tu 2 tai lieu goc."""
    need: set[str] = set()
    stack = list(ROOTS)
    while stack:
        rel = stack.pop()
        if rel in need:
            continue
        p = H / rel
        if not p.exists():
            fail(f"thieu tep duoc input: {rel}")
            continue
        need.add(rel)
        lines = p.read_text(encoding="utf-8").split("\n")
        body = "\n".join(l for l in lines if not l.lstrip().startswith("%"))
        for m in re.finditer(r"\\(?:input|include)\s*\{([^}]*)\}", body):
            t = m.group(1)
            stack.append(t if t.endswith(".tex") else t + ".tex")
        for m in re.finditer(r"\\InputIfFileExists\s*\{([^}]*)\}", body):
            stack.append(m.group(1))
        for m in re.finditer(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]*)\}", body):
            need.add(m.group(1))
        for m in re.finditer(r"\\bibliography\{([^}]*)\}", body):
            need.add(m.group(1) + ".bib")
    return need


def build_zip(path: Path) -> None:
    """Goi lai zip theo dung INCLUDE (de gate chay duoc ca khi khong co zip san)."""
    stage = Path("/tmp/_gate_pkg_stage")
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    for f in INCLUDE_ROOT:
        src = H / f
        if not src.exists():
            fail(f"khong the goi: thieu {f} trong paper2_hujos/")
            return
        shutil.copy2(src, stage / f)
    for d in ["blocks_vi", "tables_vi"]:
        (stage / d).mkdir()
        for src in sorted((H / d).glob("*.tex")):
            shutil.copy2(src, stage / d / src.name)
    (stage / "figures_vi").mkdir()
    for src in sorted((H / "figures_vi").glob("*_vi.png")):
        shutil.copy2(src, stage / "figures_vi" / src.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    subprocess.run(["zip", "-rqX", str(path), "."], cwd=stage, check=True)
    print(f"  i  da goi lai {path} ({path.stat().st_size / 1024:.0f} KB)")


def sh(cmd: list[str], cwd: Path, timeout: int = 600):
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(cwd), timeout=timeout)


def pages(pdf: Path) -> int:
    out = sh(["pdfinfo", str(pdf)], pdf.parent, 60).stdout
    m = re.search(r"Pages:\s*(\d+)", out)
    return int(m.group(1)) if m else -1


def main() -> int:
    zip_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/source_latex_final.zip")
    if not zip_path.exists():
        print(f"  i  {zip_path} khong ton tai — tu goi lai tu paper2_hujos/")
        build_zip(zip_path)
    if not zip_path.exists():
        fail("khong co zip de kiem")
        print("\nGATE FAIL")
        return 1

    names = zipfile.ZipFile(zip_path).namelist()
    files = [n for n in names if not n.endswith("/")]
    print(f"=== 1) ZIP SACH? ({len(files)} tep, {zip_path.stat().st_size / 1024:.0f} KB) ===")
    junk = sorted(n for n in files if JUNK.search(n))
    if junk:
        fail(f"con {len(junk)} tep rac: {junk[:8]}")
    else:
        print("  PASS: khong con artifact build / docx_build / qa_* / probe_* / *.py / hinh *_en")

    print("\n=== 2) DU CLOSURE PHU THUOC? ===")
    need = closure()
    have = set(files)
    missing = sorted(f for f in need if f not in have)
    if missing:
        fail(f"thieu {len(missing)} tep can thiet: {missing[:10]}")
    else:
        print(f"  PASS: du {len(need)} tep trong closure (tex/hinh/bib)")
    for extra in ["README_BUILD.md", ".latexmkrc", "vancouver.bst"]:
        if extra not in have:
            fail(f"thieu {extra} (bat buoc de nguoi nhan build duoc)")

    print("\n=== 3) BUILD BANG LENH MAC DINH CUA NGUOI DUNG (`latexmk` tran) ===")
    work = Path("/tmp/_gate_build_clean")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    zipfile.ZipFile(zip_path).extractall(work)
    r = sh(["latexmk"], work, 900)
    log = (work / "latexmk.log").read_text(encoding="utf-8", errors="ignore") if (work / "latexmk.log").exists() else ""
    if r.returncode != 0:
        tail = "\n".join((r.stdout + r.stderr).strip().split("\n")[-12:])
        fail(f"`latexmk` tran exit={r.returncode}\n{tail}")
    else:
        print("  PASS: latexmk tran exit=0")
    for bad in ["No counter", "Missing \\begin{document}", "Emergency stop"]:
        if bad in r.stdout + r.stderr:
            fail(f"log con '{bad}' — latexmk van build nham manh \\input")

    print("\n=== 4) PDF SINH RA DU VA DUNG SO TRANG ===")
    for pdf, exp in [("main_hujos_vi.pdf", 33), ("supplementary_vi.pdf", 13)]:
        p = work / pdf
        if not p.exists():
            fail(f"khong sinh ra {pdf}")
            continue
        n = pages(p)
        if n != exp:
            fail(f"{pdf}: {n} trang, mong {exp}")
        else:
            txt = sh(["pdftotext", str(p), "-"], work, 120).stdout
            if "??" in txt:
                fail(f"{pdf}: con '??' (nhan chua giai)")
            else:
                print(f"  PASS: {pdf} {n} trang, khong '??'")
    # log cua tung tai lieu phai sach
    for lg in ["main_hujos_vi.log", "supplementary_vi.log"]:
        lp = work / lg
        if lp.exists():
            body = lp.read_text(encoding="utf-8", errors="ignore")
            nerr = len(re.findall(r"^!", body, re.M))
            nund = len(re.findall("undefined", body, re.I))
            if nerr or nund:
                fail(f"{lg}: {nerr} loi '!', {nund} 'undefined'")
            else:
                print(f"  PASS: {lg} 0 loi, 0 undefined")

    print("\n=== 5) GUARD ENGINE: goi nham pdflatex phai in HUONG DAN ===")
    r2 = sh(["pdflatex", "-interaction=nonstopmode", "main_hujos_vi.tex"], work, 300)
    out = r2.stdout + r2.stderr
    if r2.returncode == 0:
        fail("pdflatex exit=0 — khong the (bai dung fontspec); guard khong hoat dong?")
    elif "BAT BUOC bien dich bang XeLaTeX" not in out:
        fail("pdflatex fail nhung KHONG in huong dan (guard iftex thieu/hong)")
    else:
        ok = ("Fatal Package fontspec Error" not in out) and ("Emergency stop" not in out)
        if not ok:
            fail("guard in huong dan nhung van lot 'Fatal fontspec'/'Emergency stop'")
        else:
            print("  PASS: nguoi dung nhan dung 3 dong cach sua, khong con thong bao mo ho")

    print("\n=== 6) XELATEX THU CONG (duong dan phong khi latexmk khong co) ===")
    work2 = Path("/tmp/_gate_build_xelatex")
    if work2.exists():
        shutil.rmtree(work2)
    work2.mkdir(parents=True)
    zipfile.ZipFile(zip_path).extractall(work2)
    for a in ["aux", "bbl", "blg", "log", "out"]:
        for f in work2.glob(f"*.{a}"):
            f.unlink()
    base = "main_hujos_vi"
    sh(["xelatex", "-interaction=nonstopmode", f"{base}.tex"], work2, 300)
    sh(["bibtex", base], work2, 120)
    sh(["xelatex", "-interaction=nonstopmode", f"{base}.tex"], work2, 300)
    r3 = sh(["xelatex", "-interaction=nonstopmode", f"{base}.tex"], work2, 300)
    if r3.returncode != 0 or not (work2 / f"{base}.pdf").exists():
        fail(f"xelatex thu cong that bai (exit={r3.returncode})")
    elif pages(work2 / f"{base}.pdf") != 33:
        fail(f"xelatex thu cong: {pages(work2 / f'{base}.pdf')} trang, mong 33")
    else:
        print("  PASS: xelatex thu cong 4 buoc -> 33 trang")

    shutil.rmtree(work, ignore_errors=True)
    shutil.rmtree(work2, ignore_errors=True)
    print("\n=== KET LUAN: {} ===".format(
        "GATE PASS — goi nguon sach va bien dich duoc tu thu muc sach"
        if not fails else f"GATE FAIL — {len(fails)} van de"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

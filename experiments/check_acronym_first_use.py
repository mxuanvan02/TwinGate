#!/usr/bin/env python3
"""GATE: moi viet tat phai duoc KHAI TRIEN o LAN DUNG DAU TIEN.

VI SAO TON TAI (2026-10-09, anh Van phat hien "sua chua triet de"):
  Tom tat tieng Viet tung mo dau bang "MRV la nut that..." — viet tat dung TRAN,
  trong khi ban tieng Anh viet dung "Monitoring, reporting and verification
  (MRV) is...". Loi nay sinh ra khi nen abstract tu 248 -> 236 tu: cum khai trien
  bi cat mat.

  Tai sao khong gate nao bat duoc:
    * rewrite_abstracts.py chi kiem "tu khoa co mat trong tom tat" — khong kiem
      "viet tat co duoc dinh nghia hay khong".
    * VI_KEYWORDS la hang so VIET TAY chua "MRV" (viet tat), trong khi dong
      "Từ khóa:" duoc in that trong bai chua cum day du "đo đạc, báo cáo,
      thẩm định". Gate kiem mot chuoi khac voi chuoi duoc in -> van XANH trong
      khi noi dung da doi. (Da sua o rewrite_abstracts.py.)
    * verify_paper_claims.py chi kiem SO, check_vi_foreign_chars.py chi kiem
      KY TU NGOAI LAI, fix_stale_numbers.py chi kiem SO CU. Khong gate nao doc
      van xoi de kiem dinh nghia thuat ngu.

  Quy tac theo academic-prose: mot khai niem/viet tat phai "be defined at first
  use". Day la gate thuc thi quy tac do.

GATE NAY KIEM CA:
  1. Viet tat phai co dang "<cum khai trien> (<VIET TAT>)" hoac "[<VIET TAT>]"
     ngay tai LAN XUAT HIEN DAU TIEN trong chuoi file duoc \\input that.
  2. Dong "Từ khóa:" in trong bai phai nam trong tom tat (doi chieu file that,
     khong tin hang so viet tay) — lop chan thu hai cho chinh loi da xay ra.

CAI KHONG PHAI LOI (mien tru co ly do, xem EXEMPT):
  * Ma van ban quy pham phap luat: 4801/QĐ-BNNMT, 1490/QĐ-TTg, 26/2019/TT-BNNPTNT.
    Dinh danh phai GIU NGUYEN VAN — "khai trien" no la sai luat.
  * Ky hieu toan hoc trong $...$: FC-WP, ETc, Ks... do la bien/cup-phap cua
    phuong trinh, duoc dinh nghia bang phuong trinh chu khong bang chu.
  * Ten rieng / nhan hieu / dinh dang file: ERA5, FAO-56, VM0051, IoT, PDF...

Chay:
    python3 experiments/check_acronym_first_use.py            # ca hai chuoi EN + VI
    python3 experiments/check_acronym_first_use.py --verbose  # in ly do mien tru
Thoat 0 = PASS, 1 = FAIL.
"""
from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HUJOS = ROOT / "paper2_hujos"

BS = chr(92)

# ---------------------------------------------------------------------------
# Chuoi file duoc build that, theo dung THU TU xuat hien trong bai.
# Doc tu lenh \input cua file main de khong phai bao tri tay thu tu.
# ---------------------------------------------------------------------------
CHAINS = {
    "EN": HUJOS / "main_hujos.tex",
    "VI": HUJOS / "main_hujos_vi.tex",
}


# ---------------------------------------------------------------------------
# Mien tru CO LY DO. Them vao day = phai viet ly do, khong duoc xoa loi bang
# cach cho vao danh sach ma khong giai thich.
# ---------------------------------------------------------------------------
EXEMPT = {
    # --- ma van ban quy pham phap luat: dinh danh, GIU NGUYEN VAN ---
    "BNNMT": "ten Bo trong ma van ban luat (4801/QĐ-BNNMT)",
    "QĐ": "loai van ban luat",
    "QD": "loai van ban luat (ban khong dau)",
    "TTG": "co quan ban hanh (QĐ-TTg)",
    "TT": "loai van ban luat (thong tu)",
    "BNNPTNT": "ten Bo trong ma thong tu cu",
    # --- du lieu / mo hinh: ten rieng cua bo du lieu va phuong phap ---
    "ERA5": "ten tai phan tich cua ECMWF (rigid designator)",
    "FAO-56": "ma hieu tai lieu FAO Irrigation and Drainage Paper 56",
    "VM0051": "ma phuong phap luan cua Verra",
    "SCS": "ten co quan (Soil Conservation Service) - da khai trien trong bai",
    # --- thiet bi / dinh dang ---
    "IoT": "thuat ngu pho bien, giu nguyen theo glossary_vi.tex",
    "PVC": "ten vat lieu ong do muc nuoc",
    "PDF": "dinh dang file",
    "CSV": "dinh dang file",
    "JSON": "dinh dang du lieu",
    "DOI": "dinh danh tai lieu",
    "MIT": "ten giay phep",
    "IEEE": "ten nha xuat ban / khuon bai",
    "HUJOS": "ten tap chi",
    "API": "thuat ngu pho bien",
    # --- tieu chuan / chuong trinh quoc te ---
    "CDM": "Co che Phat trien Sach (ghi trong van ban VM0051)",
    "VCS": "ten chuong trinh cua Verra",
    "ICVCM": "ten to chuc",
    "SPOT": "ten don vi canh tac trong QD 4801 (danh tu rieng cua quy trinh)",
    "MSD": "che do nuoc 'mid-season drainage' theo VM0051",
    "QGIS": "ten phan mem",
    "NDVI": "ten chi so vien tham",
    "SOC": "ten dai luong (soil organic carbon)",
    "GHG": "ten nhom khi (greenhouse gas)",
    "CH4": "cong thuc hoa hoc",
    "N2O": "cong thuc hoa hoc",
    "CO2": "cong thuc hoa hoc",
    "TAW": "ky hieu thuy van (total available water), dinh nghia bang phuong trinh",
    "AWD": "duoc khai trien trong bai; giu o day de gate khong bao trung",
}

# Ky hieu toan hoc ngan: bien/chi so trong phuong trinh, khong phai viet tat van xoi.
# Duoc mien vi chung duoc DINH NGHIA BANG PHUONG TRINH ngay canh do.
MATH_SHORT = re.compile(r"^[A-Z]{1,2}(?:-?[A-Z0-9]{1,3})?$")


def fold(t: str) -> str:
    """Gap dau tieng Viet de so sanh ma hieu: 'QĐ-BNNMT' == 'QD-BNNMT'.

    Can vi ban EN viet khong dau con ban VI viet co dau. 'Đ' khong phan ra duoc
    bang NFD nen phai map tay, neu khong no bi mat chu va hai ban khong khop nhau.
    """
    t = t.replace("Đ", "D").replace("đ", "d")
    return unicodedata.normalize("NFD", t).encode("ascii", "ignore").decode("ascii").upper()


# Dinh danh van ban quy pham phap luat VN, bat ca dang co dau lan khong dau.
LEGAL_INSTRUMENT = re.compile(
    r"\d{1,5}(?:/\d{4})?/(?:Q[ĐD]|ND|NĐ|TT)-[A-ZĐ]{2,}(?:\d|[A-Za-zĐđ]+)*", re.I)

ACRONYM = re.compile(r"\b[A-ZĐ]{2,8}(?:-[A-Z0-9]{2,12})?\b")


# ---------------------------------------------------------------------------
# Lam sach van ban truoc khi quet
# ---------------------------------------------------------------------------
def clean(text: str) -> str:
    """Bo comment, cong thuc toan, cite/ref/label va ten lenh LaTeX.

    THU TU QUAN TRONG: phai bo toan ($...$) TRUOC khi bo ten lenh, vi neu bo
    lenh truoc thi 'FC-WP' ben trong $...$ lot ra ngoai va bi hieu nham la viet
    tat van xoi (bao dong gia da gap 2026-10-09).
    """
    t = re.sub(r"(?m)(?<!\\)%.*$", "", text)              # comment
    # LOI DA SUA (2026-10-09): ban dau viet (?:equation|...) la nhom KHONG bat
    # roi lai dung \1 de tham chieu -> re.error "invalid group reference 1".
    # Phai dung nhom BAT (equation|...) thi \1 moi ton tai.
    t = re.sub(r"\\begin\{(equation|align|gather|multline|eqnarray|displaymath)\*?\}.*?"
               r"\\end\{\1\*?\}", " ", t, flags=re.S)      # khoi toan
    t = re.sub(r"\\\[.*?\\\]", " ", t, flags=re.S)         # \[ ... \]
    t = re.sub(r"\$[^$]*\$", " ", t)                       # $ ... $
    t = re.sub(BS + BS + r"(?:cite|ref|eqref|label|bibliography|bibliographystyle)"
               r"\*?\{[^}]*\}", " ", t)                    # cite/ref/label
    t = re.sub(BS + BS + r"(?:input|include)\{[^}]*\}", " ", t)
    t = re.sub(BS + BS + r"[a-zA-Z]+\*?", " ", t)          # ten lenh
    t = re.sub(r"[{}~$]", " ", t)
    return t


def chain_files(main: Path) -> list[Path]:
    """Tra ve main + cac file no \\input, theo dung thu tu (de 'lan dau' co nghia)."""
    out = [main]
    if not main.exists():
        return out
    src = main.read_text(encoding="utf-8", errors="replace")
    for m in re.finditer(re.escape(BS) + r"input\{([^}]*)\}", src):
        rel = m.group(1)
        cand = [main.parent / (rel + ".tex"), main.parent / rel,
                ROOT / "paper2" / (rel.split("/")[-1] + ".tex")]
        for c in cand:
            if c.exists() and c not in out:
                out.append(c)
                break
    return out


def legal_tokens(text: str) -> set[str]:
    """Moi token cua moi ma van ban luat trong text (ca dang day du lan tach roi)."""
    legal: set[str] = set()
    for m in LEGAL_INSTRUMENT.finditer(text):
        whole = re.sub(r"\s+", " ", m.group(0))
        for chunk in {whole, *re.split(r"[/\s-]", whole), *whole.split("/")}:
            if not chunk:
                continue
            legal.add(chunk)
            legal.add(fold(chunk))
        # ban EN viet 'Decision 4801/QD-BNNMT' nen token gate quet ra co the la
        # CA CUM CO GACH NOI ('QD-BNNMT'); chi tach roi tung phan thi van bao gia.
        for seg in whole.split("/"):
            pieces = seg.strip().split("-")
            for k in range(len(pieces)):
                joined = "-".join(pieces[k:])
                if joined:
                    legal.add(joined)
                    legal.add(fold(joined))
    return legal


def find_undefined(lang: str, text: str, verbose: bool = False) -> list[str]:
    """Viet tat xuat hien trong text ma LAN DAU khong co khai trien tai cho."""
    legal = legal_tokens(text)
    exempt_fold = {fold(k) for k in EXEMPT}
    bad, seen, skipped = [], set(), {}

    for m in ACRONYM.finditer(text):
        tok = m.group(0)
        if tok in seen:
            continue
        seen.add(tok)
        if tok in EXEMPT or fold(tok) in exempt_fold:
            skipped.setdefault(tok, "EXEMPT: " + EXEMPT.get(tok, "?"))
            continue
        if tok in legal or fold(tok) in legal:
            skipped.setdefault(tok, "ma van ban luat")
            continue
        if MATH_SHORT.match(tok):
            skipped.setdefault(tok, "ky hieu toan ngan")
            continue
        if tok in {"I", "II", "III", "IV", "V"}:
            skipped.setdefault(tok, "so thu tu La Ma")
            continue

        # Tim dang khai trien tai cho: "<cum 2..80 ky tu> (<TOK>)" hoac "[<TOK>]"
        head = text[: m.end() + 1]
        pat = re.compile(r"[^\(\)\[\]\n]{2,80}[\(\[]\s*" + re.escape(tok) + r"\s*[\)\]]")
        if pat.search(head[-260:]):
            skipped.setdefault(tok, "da khai trien tai cho")
            continue

        ctx = re.sub(r"\s+", " ", text[max(0, m.start() - 70):m.start() + 45])
        bad.append(f"[{lang}] '{tok}' dung lan dau ma khong duoc khai trien: ...{ctx}...")

    if verbose and skipped:
        print(f"  ({lang}) mien tru / da dat:")
        for tok, why in sorted(skipped.items()):
            print(f"     - {tok:12s} {why}")
    return bad


def abstract_text(lang: str, raw: str) -> str:
    """Trich tom tat tu NGUON GOC (chua lam sach), da bo lenh LaTeX.

    LOI DA SUA (2026-10-09): ban dau lay tom tat tu van ban da qua clean(), nhung
    clean() xoa ten lenh nen '\\textbf{Tóm tắt.}' chi con 'Tóm tắt.' -> khong tim
    thay marker va lop chan "tu khoa phai co trong tom tat" im lang bo qua.
    """
    marker = "Abstract." if lang == "EN" else "Tóm tắt."
    k = raw.find(marker)
    if k < 0:
        return ""
    tail = raw[k + len(marker):]
    for stop in (BS + "vspace", BS + "textbf{Keywords", BS + "textbf{Từ khóa"):
        j = tail.find(stop)
        if j > 0:
            tail = tail[:j]
    t = re.sub(BS + BS + r"[a-zA-Z]+\*?", " ", tail)
    t = re.sub(r"[{}~$]", " ", t)
    return re.sub(r"\s+", " ", t).lower()


def keyword_line(lang: str, main: Path) -> list[str]:
    """Doc DONG TU KHOA DUOC IN THAT trong bai (khong tin hang so viet tay)."""
    marker = (BS + "textbf{Keywords:}" if lang == "EN"
              else BS + "textbf{Từ khóa:}")
    src = main.read_text(encoding="utf-8", errors="replace")
    k = src.find(marker)
    if k < 0:
        return []
    tail = src[k + len(marker):]
    stop = tail.find(BS + "vspace")
    line = re.sub(r"\s+", " ", tail[:stop if stop > 0 else 400]).strip().rstrip(".")
    return [x.strip() for x in line.split(";") if x.strip()]


def main() -> int:
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    print("=" * 78)
    print("GATE: viet tat phai duoc khai trien o lan dung dau (academic-prose)")
    print("=" * 78)

    all_bad: list[str] = []
    for lang, main_tex in CHAINS.items():
        if not main_tex.exists():
            all_bad.append(f"[{lang}] thieu file main: {main_tex}")
            continue
        files = chain_files(main_tex)
        raw = "\n".join(f.read_text(encoding="utf-8", errors="replace") for f in files)
        text = clean(raw)

        print(f"\n--- {lang}: {len(files)} file, {len(text)} ky tu sau khi lam sach ---")
        bad = find_undefined(lang, text, verbose)
        all_bad += bad

        # Lop chan thu 2: tu khoa in trong bai phai co mat trong tom tat.
        kws = keyword_line(lang, main_tex)
        abs_txt = abstract_text(lang, raw)
        if not abs_txt:
            all_bad.append(f"[{lang}] khong trich duoc tom tat tu {main_tex.name}")
        if not kws:
            all_bad.append(f"[{lang}] khong doc duoc dong tu khoa tu {main_tex.name}")
        miss = [k for k in kws if k.lower() not in abs_txt]
        print(f"  tu khoa in trong bai ({len(kws)} cum): "
              + ("tat ca co mat trong tom tat" if not miss else f"THIEU {miss}"))
        if miss:
            all_bad.append(f"[{lang}] tu khoa duoc in khong co mat trong tom tat: {miss}")
        for b in bad:
            print("  ! " + b)

    print()
    if all_bad:
        print(f"GATE: FAIL — {len(all_bad)} loi")
        for b in all_bad:
            print("  * " + b)
        print("\n  Cach sua: them cum khai trien tai LAN DUNG DAU theo dang")
        print("          '<cum day du> (<VIET TAT>)'. Neu la ten rieng/ma van ban")
        print("          luat khong the khai trien, them vao EXEMPT kem LY DO.")
        return 1
    print("GATE: PASS — moi viet tat deu duoc khai trien o lan dung dau (EN + VI)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

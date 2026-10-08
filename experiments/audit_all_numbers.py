#!/usr/bin/env python3
"""CONG KIEM TOAN BO SO LIEU TRONG BAI <-> NGUON DU LIEU THAT.

Vi sao can file nay: em da verify theo kieu LAY MAU (dung dau kiem do), nen moi
vong lai lo ra mot loi moi: +69% chon mau lech, 91% khong condition tren changed,
'Anonymous' trong bib, et al.., 4 ky hieu khong duoc dinh nghia. Moi cai deu bat
duoc NEU ra soat het mot lan. Day la cong de khong con loi nao lot.

Nguyen tac: MOI con so xuat hien trong than bai phai truy duoc ve mot trong:
  (1) outputs/*.csv            — ket qua chay that
  (2) src/*.py, experiments/*.py — hang so cau hinh (TAW, FC, WP, d_dry, tau...)
  (3) refs.bib / nguon ngoai    — so cua tai lieu (41-71%, 77%, 350000 ha...)
  (4) danh sach so 'hien nhien'  — nam, so hieu phien ban, kich thuoc luoi

Con so nao KHONG truy duoc -> in ra de nguoi dung quyet dinh (co the la so dung
tu dau, co the la so cu cua phien ban truoc con sot lai).

Chay: python3 experiments/audit_all_numbers.py
"""
from __future__ import annotations

import csv
import glob
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLOCKS = ROOT / "paper2" / "blocks"
H = ROOT / "paper2_hujos"
OUT = ROOT / "outputs"

# ---------------------------------------------------------------- 1) nguon so
# (a) moi so trong moi file CSV cua outputs/
csv_values = set()
csv_files = {}
for p in sorted(OUT.glob("*.csv")):
    try:
        with p.open(encoding="utf-8", errors="replace") as fh:
            rdr = csv.reader(fh)
            hdr = next(rdr, [])
            n = 0
            for row in rdr:
                n += 1
                for cell in row:
                    for tok in re.findall(r"-?\d+\.?\d*", cell):
                        csv_values.add(tok.rstrip("."))
                        # them dang lam tron 1/2 chu so vi bai viet lam tron
                        try:
                            v = float(tok)
                            csv_values.add(f"{v:.0f}")
                            csv_values.add(f"{v:.1f}")
                            csv_values.add(f"{v:.2f}")
                            csv_values.add(f"{round(v*100):d}")   # dang phan tram
                        except ValueError:
                            pass
            csv_files[p.name] = n
    except Exception as e:
        csv_files[p.name] = f"LOI {e}"

# (b) hang so trong src/ va experiments/
const_values = set()
const_src = defaultdict(list)
for p in sorted(glob.glob(str(ROOT / "src" / "*.py")) +
                glob.glob(str(ROOT / "experiments" / "*.py"))):
    t = Path(p).read_text(encoding="utf-8", errors="replace")
    for m in re.finditer(r"([A-Z_]{3,})\s*[:=]\s*(-?[\d.]+)", t):
        const_values.add(m.group(2).rstrip("."))
        const_src[m.group(2).rstrip(".")].append(f"{Path(p).name}:{m.group(1)}")

print("=" * 92)
print("NGUON DU LIEU THAT")
print("=" * 92)
print(f"  {len(csv_files)} file CSV trong outputs/, tong {len(csv_values)} gia tri so doc nhat")
big = sorted(((v, k) for k, v in csv_files.items() if isinstance(v, int)),
             key=lambda x: -x[0])[:8]
for n, k in big:
    print(f"    {k:<38} {n:>8} hang")
print(f"  {len(const_values)} hang so cau hinh trong src/ + experiments/")

# ---------------------------------------------------------------- 2) so trong bai
tex_files = [H / "main_hujos.tex", H / "blocks_vi.tex"] + sorted(BLOCKS.glob("*.tex"))
paper = ""
for f in tex_files:
    if f.exists():
        paper += "\n" + f.read_text(encoding="utf-8", errors="replace")

# chi lay than bai: bo comment
body = re.sub(r"(?m)%.*$", "", paper)
# bo preamble-ish: chi giu tu \begin{document} neu co
if "\\begin{document}" in body:
    body = body.split("\\begin{document}", 1)[1]

# tach toan ra khoi chu de phan loai
math_spans = re.findall(r"\$[^$]*\$|\\begin\{equation\}.*?\\end\{equation\}", body, re.S)
prose = re.sub(r"\$[^$]*\$", " ", body)
prose = re.sub(r"\\begin\{equation\}.*?\\end\{equation\}", " ", prose, flags=re.S)
prose = re.sub(r"\\begin\{tabular\}.*?\\end\{tabular\}", " ", prose, flags=re.S)

# so trong VAN XUOI (day la noi cac claim nam)
RE_NUM = re.compile(r"(?<![\d.])(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?)(?![\d.])")
prose_nums = Counter(m.group(1) for m in RE_NUM.finditer(prose))

# ---------------------------------------------------------------- 3) phan loai
YEAR = {str(y) for y in range(1990, 2031)}
SMALL = {str(i) for i in range(0, 31)}          # so dem muc, so proposition
def norm(s):
    return s.replace(",", ".")

traced, untraced = {}, []
for tok, cnt in prose_nums.most_common():
    v = norm(tok)
    variants = {v, v.replace(".", ""), tok}
    try:
        f = float(v)
        variants |= {f"{f:.0f}", f"{f:.1f}", f"{f:.2f}", f"{f*100:.0f}", f"{round(f):d}"}
    except ValueError:
        pass
    hit = None
    for cand in variants:
        if cand in csv_values:
            hit = "CSV"; break
        if cand in const_values:
            hit = "CONST"; break
    if hit:
        traced[tok] = (hit, cnt)
    elif tok in YEAR:
        traced[tok] = ("NAM", cnt)
    elif tok in SMALL:
        traced[tok] = ("SO-DEM", cnt)
    else:
        untraced.append((tok, cnt))

print()
print("=" * 92)
print("CONG KIEM: moi con so trong VAN XUOI cua bai")
print("=" * 92)
print(f"  tong {len(prose_nums)} gia tri so khac nhau, xuat hien {sum(prose_nums.values())} lan")
by_kind = Counter(k for k, _ in traced.values())
print(f"  truy duoc nguon: {sum(by_kind.values())} gia tri -> {dict(by_kind)}")
print(f"  CHUA truy duoc: {len(untraced)} gia tri")

print()
print("=" * 92)
print("SO CHUA TRUY DUOC NGUON — phai giai trinh tung cai")
print("=" * 92)
print("  (so nay khong thay trong bat ky outputs/*.csv hay hang so src/experiments nao.")
print("   Co the la: so cua tai lieu ngoai, so cua phien ban cu con sot, hoac so viet tay.)")
for tok, cnt in untraced:
    # lay ngu canh de nguoi dung phan xu
    idx = prose.find(tok)
    ctx = re.sub(r"\s+", " ", prose[max(0, idx - 90):idx + 60]).strip() if idx >= 0 else ""
    print(f"\n  {tok!r}  ({cnt} lan)")
    print(f"     ...{ctx[-140:]}")

# ---------------------------------------------------------------- 4) so trong toan
print()
print("=" * 92)
print("SO TRONG CONG THUC / BANG (it nghiem trong hon, van liet ke)")
print("=" * 92)
math_txt = " ".join(math_spans)
mn = Counter(m.group(1) for m in RE_NUM.finditer(math_txt))
mu = [(t, c) for t, c in mn.most_common()
      if norm(t) not in csv_values and norm(t) not in const_values
      and t not in YEAR and t not in SMALL]
print(f"  {len(mn)} gia tri trong toan | chua truy duoc: {len(mu)}")
for tok, cnt in mu[:20]:
    print(f"     {tok!r} ({cnt} lan)")

# ---------------------------------------------------------------- 5) doi chieu claim chinh
print()
print("=" * 92)
print("DOI CHIEU CAC CLAIM HEADLINE VOI CSV (tinh lai tu dau, khong doc bai)")
print("=" * 92)


def load(fn):
    with (OUT / fn).open(encoding="utf-8", errors="replace") as fh:
        return list(csv.DictReader(fh))


def I(r, k):
    v = r.get(k, "")
    return int(float(v)) if v not in ("", None) else 0


def F(r, k):
    v = r.get(k, "")
    return float(v) if v not in ("", None) else float("nan")


import statistics
for fn in ("eval_theta_reduced_10seeds.csv", "eval_theta_full_3seeds.csv"):
    R = load(fn)
    by = defaultdict(list)
    for r in R:
        by[r["variant"]].append(r)
    hf = by.get("honest_field", [])
    print(f"\n  --- {fn} ({len(R)} hang)")

    def esc(S, ver):
        return sum(1 for r in S if not I(r, f"{ver}_t0") and not I(r, f"{ver}_t1"))

    # false accusation
    for v in ("honest_paper", "honest_field"):
        rs = by.get(v, [])
        if not rs:
            continue
        n = len(rs)
        t1 = sum(I(r, "v1_t1") for r in rs)
        t1r = sum(I(r, "v2_t1") for r in rs)
        an = sum(I(r, "anchor_flag") for r in rs)
        fa = sum(1 for r in rs if I(r, "v2_t0") or I(r, "v2_t1") or I(r, "anchor_flag"))
        print(f"    {v:<14} n={n:>3} | bat oan v1 tier1 {t1}/{n}={100*t1/n:.1f}% | "
              f"v2 tier1 {t1r}/{n}={100*t1r/n:.1f}% | anchor {an}/{n} | tong bi bat {fa}/{n}")

    # n_dry: UNPAIRED vs PAIRED
    base_all = statistics.mean(F(r, "n_dry") for r in hf) if hf else float("nan")
    print(f"    honest_field mean n_dry (toan bo, n={len(hf)}) = {base_all:.3f}")
    print(f"    {'bien the':<24}{'n':>4}{'mean':>8}{'UNPAIRED':>11}{'PAIRED':>9}"
          f"{'changed=1':>11}{'esc v2 all':>12}{'esc v2 ch':>11}")
    for v in ("fraud_timing", "fraud_rational", "fraud_cluster24", "fraud_cluster96",
              "fraud_added_events", "fraud_infeasible_depth", "fraud_omission"):
        rs = by.get(v, [])
        if not rs:
            continue
        mn_ = statistics.mean(F(r, "n_dry") for r in rs)
        un = 100 * (mn_ - base_all) / base_all
        ch = [r for r in rs if I(r, "changed")]
        # PAIRED: ghep theo station+year+seed+soil
        key = lambda r: (r["station"], r["year"], r["seed"], r["soil"])
        hfmap = {key(r): r for r in hf}
        pairs = [(F(r, "n_dry"), F(hfmap[key(r)], "n_dry")) for r in rs if key(r) in hfmap]
        pr = (100 * (statistics.mean(a for a, _ in pairs) -
                     statistics.mean(b for _, b in pairs)) /
              statistics.mean(b for _, b in pairs)) if pairs else float("nan")
        chn = statistics.mean(F(r, "n_dry") for r in ch) if ch else float("nan")
        chb = statistics.mean(F(hfmap[key(r)], "n_dry") for r in ch if key(r) in hfmap) if ch else float("nan")
        chp = 100 * (chn - chb) / chb if ch and chb == chb else float("nan")
        e_all = 100 * esc(rs, "v2") / len(rs)
        e_ch = 100 * esc(ch, "v2") / len(ch) if ch else float("nan")
        print(f"    {v:<24}{len(rs):>4}{mn_:>8.2f}{un:>+10.0f}%{pr:>+8.0f}%"
              f"{chp:>+10.0f}%{e_all:>11.1f}%{e_ch:>10.1f}%")

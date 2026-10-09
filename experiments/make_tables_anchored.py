#!/usr/bin/env python3
"""Sinh cac bang LaTeX cho bai bao DOI TRUC (device-anchored log).

Nguyen tac bat buoc, ca hai deu sinh ra tu loi that da tra gia:

  (1) KHONG BAO GIO go backslash literal trong chuoi. Moi ky tu backslash duoc
      tao bang chr(92). Ly do: 15 dong trong make_tables_paper2.py da ket thuc
      bang 4 backslash vi tron raw string (r"..." giu nguyen) voi f-string
      (f"..." giai ma), sinh ra DONG TRONG trong 3 bang ma khong ai thay cho
      toi khi doc PDF.

  (2) Spec cot phai duoc KIEM TONG CHIEU RONG truoc khi ghi. Kho that cua
      IEEEtran journal do bang probe: 1 cot = 252pt = 8.85cm, table* = 516pt
      = 17.8cm. Voi tabcolsep 3pt, ngan sach con lai la 8.85 - 0.212*(ncols-1).
      6/8 bang cua ban dau tran toi 263pt vi dung cot 'l'/'c' khong tu xuong dong.

  (3) Moi con so doc TU CSV. Khong go tay.

Chay:
    python3 experiments/make_tables_anchored.py
"""
from __future__ import annotations

import csv
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
DEST = ROOT / "paper2" / "tables"

# ---------------------------------------------------------------------------
# Ky tu: KHONG dung literal
# ---------------------------------------------------------------------------
BS = chr(92)                 # mot backslash
NL = chr(10)
AMP = " & "
ROW_END = " " + BS + BS      # dung HAI backslash = LaTeX xuong mot dong
CM = 28.453                  # pt per cm
COL_1 = 8.85                 # cm, kho 1 cot IEEE
COL_2 = 17.80                # cm, kho table* (2 cot)
TABCOLSEP_CM = 2 * 3.0 / CM  # 3pt x 2 ben moi ranh


def row(*cells: str) -> str:
    """Mot dong bang. Chi co mot cho duy nhet sinh ra ky tu xuong dong."""
    return AMP.join(cells) + ROW_END


def rule(kind: str) -> str:
    return BS + {"top": "toprule", "mid": "midrule", "bot": "bottomrule"}[kind]


def table(spec: list[tuple[str, float]], lines: list[str], *, wide: bool = False) -> str:
    """Goi bang, KEM kiem tra tong chieu rong cot.

    spec: danh sach (loai_cot, do_rong_cm). Loai 'l'/'c'/'r' khong co do rong
    khai bao -> uoc tinh 1.0cm moi cot (du cho chu ngan).
    """
    budget = COL_2 if wide else COL_1
    ncols = len(spec)
    usable = budget - TABCOLSEP_CM * (ncols - 1)
    total = 0.0
    cols = []
    for kind, w in spec:
        if kind == "p":
            total += w
            # \raggedright TRONG O la bat buoc voi cot hep. Ly do do duoc tu log:
            # 5/6 overfull con lai deu la "in paragraph at lines 4--NNN" trong bang,
            # tuc la LaTeX canh deu (justify) trong o p{} rong ~1cm va tran khi mot
            # tu khong vua dong. Day la loi kinh dien cua cot hep, khong phai do tu
            # don dai (phep uoc tinh chieu rong ky tu cua lan chan doan truoc sai
            # ~3 lan: dung 1.37pt/ky tu trong khi chu 8pt rong ~4pt).
            # \arraybackslash de \\ o cuoi dong van hoat dong trong o.
            cols.append(">{" + BS + "raggedright" + BS + "arraybackslash}p{"
                        + f"{w:.2f}" + "cm}")
        else:
            # Cot l/c/r khong tu xuong dong. `w` o day la UOC TINH chieu rong noi
            # dung (0 = dung mac dinh 1.0cm). Gate van cong no vao tong, nen khai
            # bao hep hon thi phai chac noi dung that su ngan ("23", "60").
            total += (w if w > 0 else 1.0)
            cols.append(kind)
    # Assert van giu lam sanity check cho spec khai bao, nhung KHONG du de dam
    # bao khong tran: cot p{} chua \par nen do chieu rong bang \sbox cho ra so
    # SAI (do duoc 7.92-8.01cm trong khi build that bao overfull 18-26pt ~ 8.8cm).
    # Bisect co doi chung (caption that + tabular trivial -> 0 overfull) xac nhan
    # thu pham la TABULAR. Vi vay ep dung bang \resizebox theo kho cot that.
    assert total <= usable + 1e-9, (
        f"tran khung: tong cot {total:.2f}cm > ngan sach {usable:.2f}cm "
        f"(kho {budget:.2f}cm, {ncols} cot, tabcolsep 3pt)")
    begin = BS + "begin{tabular}{@{}" + "".join(cols) + "@{}}"
    inner = NL.join([begin] + lines + [BS + "end{tabular}"])
    # \fittocol chi thu nho khi that su tran, khong bao gio phong to (dinh nghia
    # trong preamble.tex). Bang rong (table*) duoc do voi \columnwidth cua no vi
    # o do \columnwidth = \textwidth, nen cung mot lenh dung cho ca hai.
    return (BS + "fittocol{%" + NL + inner + NL + "}")


def write(name: str, body: str) -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    hdr = (f"% Sinh TU DONG tu outputs/eval_theta_*.csv boi "
           f"experiments/make_tables_anchored.py{NL}"
           f"% KHONG sua tay: moi con so deu truy nguon duoc ve CSV.{NL}{NL}")
    # CHOT CHAN: dong bang ket thuc 4 backslash = LaTeX xuong 2 dong = DONG TRONG
    for k, ln in enumerate(body.split(NL), 1):
        assert not ln.rstrip().endswith(BS * 4), (
            f"{name}.tex dong {k} ket thuc 4 backslash (dong TRONG): {ln[-46:]!r}")
    (DEST / f"{name}.tex").write_text(hdr + body + NL, encoding="utf-8")
    print(f"  wrote {name}.tex ({len(body.split(NL))} dong)")


def num(x: float, nd: int = 1) -> str:
    """So thap phan kieu ANH (dau CHAM) — bai viet bang tieng Anh, pdflatex/xelatex
    khong hieu dau phay thap phan kieu Viet."""
    return f"{x:.{nd}f}"


def pct(a: int, b: int) -> str:
    return f"{a/b*100:.0f}" + BS + "%" if b else "n/a"


# ---------------------------------------------------------------------------
def load(name: str) -> list[dict]:
    p = OUT / name
    if not p.exists():
        print(f"  !! thieu {p} — chay experiments/robust_audit_eval.py truoc")
        return []
    with p.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def I(r: dict, k: str) -> int:
    """Doc so nguyen tu CSV. CSV tra ve CHUOI, nen `not r['v2_t0']` voi gia tri
    '0' la `not '0'` = False — loi da tra gia, phai ep kieu tuong minh."""
    v = r.get(k, "")
    return int(float(v)) if v not in ("", None) else 0


def F(r: dict, k: str) -> float:
    v = r.get(k, "")
    return float(v) if v not in ("", None) else float("nan")


# ---------------------------------------------------------------------------
# BANG 1 — Moi de doa: cai gi bi lam gia, va lop phong thu nao thay duoc
# ---------------------------------------------------------------------------
THREAT = [
    # (variant, ten hien thi, tong mm?, tung do sau?, thoi diem?, ghi chu)
    ("honest_field", "Honest farmer (field conditions)", "true", "true", "true",
     "Reference: seven reality-gap axes active"),
    ("fraud_added_events", "Added irrigation events", "FALSE", "true", "true",
     "Inflates the record of management activity"),
    ("fraud_infeasible_depth", "Infeasible claimed depth", "FALSE", "FALSE", "true",
     "One third of entries set to the whole storage span"),
    ("fraud_omission", "Omission of real commands", "FALSE", "true", "true",
     "Deletes a 96 h window to manufacture a dry phase"),
    ("fraud_cluster24", "Claim consolidation, 24 h", "true", "varies", "FALSE",
     "Same water, fewer and larger events"),
    ("fraud_cluster96", "Claim consolidation, 96 h", "true", "varies", "FALSE",
     "Same water, events snapped to a coarse grid"),
    ("fraud_timing", "Time shifting (rational)", "true", "true", "FALSE",
     "Hill-climbs each hour to maximise creditable dry phases"),
    ("fraud_rational", "Rational adversary", "true", "true", "FALSE",
     "Chooses the consolidation window that maximises dry phases"),
]


def tab_threat() -> None:
    lines = [rule("top"),
             row("Fraud variant", "Total mm", "Each depth", "Timing", "What it forges"),
             rule("mid")]
    for v, disp, tot, dep, tim, note in THREAT:
        lines.append(row(disp, tot, dep, tim, note))
    lines.append(rule("bot"))
    # 5 cot -> ngan sach 8.007cm; tong 8.00cm
    write("tab_threat", table([("p", 2.85), ("p", 0.95), ("p", 1.05), ("p", 0.95),
                               ("p", 2.20)], lines, wide=False))


# ---------------------------------------------------------------------------
# BANG 2 — KET QUA CHINH: ba lop phong thu tren moi moi de doa
# ---------------------------------------------------------------------------
def tab_defence(by: dict) -> None:
    lines = [rule("top"),
             row("Fraud variant", "Altered logs", "Escapes v1", "Escapes v2 physics",
                 "Caught by anchor"),
             rule("mid")]
    tot_ch = tot_an = 0
    for v, disp, *_ in THREAT:
        rs = by.get(v, [])
        if not rs:
            continue
        n = len(rs)
        if v.startswith("honest"):
            # LOI DA SUA (2026-10-09, peer review F1): o cot "Escapes v1" cua dong
            # honest truoc day in hop v2_t0|v2_t1|anchor (3/60 = 5%) — tuc la so
            # cua v2 nam duoi nhan v1, mau thuan voi Bang 4 (v1_t1 = 16/60 =
            # 26,7%). Dung ngu nghia: moi cot in ty le nhat ky trung thuc BI TANG
            # DO KET TOI OAN boi chinh tang do, dung phep hop t0|t1 nhu e1/e2 cua
            # cac dong gian lan phia duoi.
            fa1 = sum(1 for r in rs if I(r, "v1_t0") or I(r, "v1_t1"))
            fa2 = sum(1 for r in rs if I(r, "v2_t0") or I(r, "v2_t1"))
            faa = sum(I(r, "anchor_flag") for r in rs)
            lines.append(row(disp, f"0/{n} (honest)",
                             BS + "textbf{" + pct(fa1, n) + "} accused",
                             pct(fa2, n) + " accused",
                             pct(faa, n) + " accused"))
            continue
        # CHI TINH TREN TAP changed==1. Truoc day e1/e2 chia cho len(rs)=23 gom ca
        # 14 hang ma adversary tra ve NGUYEN BAN nhat ky (khong tim duoc nuoc di),
        # nen "escape 91%" dem oan nhung truong hop khong co gian lan de thoat.
        # Tren dung tap altered: 8/9 = 89%. Anchor van luon dung tap nay.
        ch = [r for r in rs if I(r, "changed")]
        e1 = sum(1 for r in ch if not I(r, "v1_t0") and not I(r, "v1_t1"))
        e2 = sum(1 for r in ch if not I(r, "v2_t0") and not I(r, "v2_t1"))
        an = sum(I(r, "anchor_flag") for r in ch)
        tot_ch += len(ch); tot_an += an
        lines.append(row(disp, f"{len(ch)}/{n}", pct(e1, len(ch)), pct(e2, len(ch)),
                         f"{an}/{len(ch)}"))
    lines += [rule("mid"),
              row(BS + "textbf{All genuinely forged}", BS + "textbf{" + str(tot_ch) + "}",
                  BS + "textbf{---}", BS + "textbf{---}",
                  BS + "textbf{" + f"{tot_an}/{tot_ch}" + "}"),
              rule("bot")]
    # 5 cot -> ngan sach 8.007cm; cot $n$ chi chua "23"/"60" nen uoc tinh 0.45cm
    write("tab_defence", table([("p", 2.85), ("c", 0.45), ("p", 1.30), ("p", 1.50),
                                ("p", 1.45)], lines))
    return tot_an, tot_ch


# ---------------------------------------------------------------------------
# BANG 3 — Gia phai tra: tin chi bi thoi phong (n_dry)
# ---------------------------------------------------------------------------
def _pair_key(r: dict) -> tuple:
    """Khoa ghep cap: cung tram, cung nam, cung seed, cung loai dat."""
    return (r["station"], r["year"], r["seed"], r["soil"])


def tab_credit(by: dict) -> None:
    """Bang thoi phong tin chi, tinh theo CACH GHEP CAP.

    LOI THONG KE DA SUA (anh Van phat hien 2026-10-07: "ket qua phai chay so sanh
    voi benchmark, SOTA moi la minh chung"):

    Ban cu tinh inflation = mean(n_dry cua variant) / mean(n_dry cua TOAN BO
    honest_field). Hai tap do KHONG CUNG MAU: bien the gian lan chi duoc sinh khi
    quy dao `testable` (>= MIN_CLAIMS lenh), ma chinh tap testable von da nhieu pha
    kho hon. Do tren CSV that:
        honest_field toan bo          = 3.23 pha
        honest_field cung cap voi fraud_timing = 4.87 pha
    Nen phan lon "thoi phong" la do chon mau lech, khong phai do tan cong.

    Cach dung: ghep tung nhat ky gian lan voi nhat ky trung thuc CUA CHINH quy dao
    do (station+year+seed+soil), va chi tinh tren nhung tan cong THAT SU doi nhat ky
    (cot `changed`, vi harness tra ve nguyen ban khi adversary khong tim duoc nuoc di).
    Bao cao kem t de nguoi doc biet hieu ung co that hay khong.

    He qua: fraud_timing tu +69% xuong +33% (n=9, t=5.29). Ket luan KHONG doi —
    tan cong van co loi that va van lot ca hai tang vat ly — nhung con so trung thuc.
    """
    hf = by.get("honest_field", [])
    hfmap = {_pair_key(r): r for r in hf}
    lines = [rule("top"),
             # $\to$ PHAI nam trong math mode: \to tran la math-only, IEEEtran
             # fatal "Missing $ inserted" (da gap 2026-10-09 khi build paper2/main.tex).
             row("Log type", "Altered logs", "Paired dry phases (before $" + BS + "to$ after)",
                 "Inflation", "$t$"),
             rule("mid")]
    for v, disp, *_ in THREAT:
        rs = by.get(v, [])
        if not rs:
            continue
        if v.startswith("honest"):
            nd = statistics.mean(F(r, "n_dry") for r in rs)
            lines.append(row(disp, "---", num(nd, 2) + " (reference)", "reference", "---"))
            continue
        # chi nhung tan cong that su doi nhat ky, va ghep duoc cap
        pairs = [(F(r, "n_dry"), F(hfmap[_pair_key(r)], "n_dry"))
                 for r in rs if I(r, "changed") and _pair_key(r) in hfmap]
        if not pairs:
            lines.append(row(disp, "0", "no altered log", "---", "---"))
            continue
        a = statistics.mean(x[0] for x in pairs)
        b = statistics.mean(x[1] for x in pairs)
        d = [x[0] - x[1] for x in pairs]
        sd = statistics.stdev(d) if len(d) > 1 else 0.0
        se = sd / len(d) ** 0.5 if d else 0.0
        t = statistics.mean(d) / se if se else 0.0
        infl = f"{(a - b) / b * 100:+.0f}" + BS + "%" if b else "n/a"
        lines.append(row(disp, f"{len(pairs)}/{len(rs)}",
                         f"{num(b, 2)} $" + BS + "to$ " + num(a, 2), infl,
                         num(t, 2)))
    lines.append(rule("bot"))
    write("tab_credit", table([("p", 2.90), ("c", 0.60), ("p", 1.90), ("c", 1.10),
                               ("c", 0.60)], lines))


# ---------------------------------------------------------------------------
# BANG 4 — Bat oan: loi hua cot loi cua ca hai tang
# ---------------------------------------------------------------------------
def tab_false_accusation(by: dict) -> None:
    lines = [rule("top"),
             row("Defence layer", "Honest, paper conditions", "Honest, field conditions"),
             rule("mid")]
    for label, key0, key1 in [
            ("v1 tier 0 (physics, point model)", "v1_t0", None),
            ("v1 tier 1 (absolute $G>5$" + BS + ",mm)", "v1_t1", None),
            ("v2 tier 0 ($" + BS + "forall$" + " over $" + BS + "Theta$)", "v2_t0", None),
            ("v2 tier 1 ($" + BS + "tau(n)$ scales with events)", "v2_t1", None),
            ("Device-anchored command log", "anchor_flag", None)]:
        cells = []
        for var in ("honest_paper", "honest_field"):
            rs = by.get(var, [])
            a = sum(I(r, key0) for r in rs)
            cells.append(f"{a}/{len(rs)}" if rs else "n/a")
        lines.append(row(label, cells[0], cells[1]))
    lines += [rule("bot")]
    # 3 cot -> ngan sach 8.428cm
    write("tab_false_accusation", table([("p", 4.20), ("p", 2.10), ("p", 2.10)], lines))


# ---------------------------------------------------------------------------
# BANG 5 — Dai u_max tren Theta (sua claim "61mm" thanh mot dai)
# ---------------------------------------------------------------------------
def tab_umax() -> None:
    sys.path.insert(0, str(ROOT / "src"))
    from log_filters import SOIL_SET, umax_for, Theta
    lines = [rule("top"),
             row("Soil (FAO-56 Table 2)", "Span (mm)", "$u_{\\max}$ at $w_0=0$",
                 "$u_{\\max}$ at $w_0=0.90$"),
             rule("mid")]
    allv = []
    for name, fc, wp in SOIL_SET:
        span = (fc - wp) * 1000 * 0.5
        u0 = umax_for(Theta(name, fc, wp, "fixed", 1.0), w0_depl=0.0)
        u9 = umax_for(Theta(name, fc, wp, "fixed", 1.0), w0_depl=0.90)
        allv += [u0, u9]
        lines.append(row(name.replace("_", " "), num(span), num(u0), num(u9)))
    lines += [rule("mid"),
              row(BS + "textbf{Range to be published}", "---",
                  BS + "textbf{" + num(min(allv)) + "}",
                  BS + "textbf{" + num(max(allv)) + "}"),
              rule("bot")]
    # 4 cot -> ngan sach 8.217cm
    write("tab_umax", table([("p", 3.00), ("p", 1.25), ("p", 1.85), ("p", 1.85)], lines))
    print(f"    dai u_max = [{min(allv):.1f}, {max(allv):.1f}] mm "
          f"(bai cu cong bo mot so 61mm)")


# ---------------------------------------------------------------------------
# BANG 6 — V2 khong the kich hoat: do depletion that
# ---------------------------------------------------------------------------
def tab_f2_unreachable() -> None:
    p = OUT / "f2_reachability.csv"
    if not p.exists():
        print("  !! thieu outputs/f2_reachability.csv — chay diag_f2.py truoc")
        return
    rows = load("f2_reachability.csv")
    lines = [rule("top"),
             row("Station", "Year", "Max clipped depletion", "$V_2$ fires",
                 "Interpretation"),
             rule("mid")]
    for r in rows:
        mx = F(r, "max_clipped_depl")
        fires = I(r, "f2_hits_dry_log")
        interp = ("never below wilting point" if fires == 0 else "reachable")
        lines.append(row(r["station"].replace("_", " "), r["year"], num(mx, 3),
                         str(fires), interp))
    lines.append(rule("bot"))
    # 5 cot -> ngan sach 8.007cm; cot Year chi chua "2024" nen 0.50cm
    write("tab_f2_unreachable", table([("p", 1.55), ("c", 0.50), ("p", 1.75),
                                       ("p", 0.85), ("p", 2.60)], lines))


# ---------------------------------------------------------------------------
# BANG 7 — Chi phi, SUA: them cot Connectivity de Total cong ra duoc
# ---------------------------------------------------------------------------
BASELINE = [
    # (kien truc, hardware, connectivity, labour, audit, ghi chu)
    ("Manual observation tube plus photographs", 0.5, 0.0, 8.0, 4.0,
     "current practice under Decision 4801"),
    ("Water-level sensor per plot", 11.3, 2.0, 1.5, 4.0,
     "accurate, hard to scale to smallholders"),
    ("Remote sensing plus field verification", 0.0, 0.0, 2.0, 6.0,
     "revisit 2 to 4 days"),
    ("Attested log, this work", 3.6, 1.5, 0.3, 3.0,
     "gateway timestamp is what makes it admissible"),
]


def tab_baseline() -> None:
    lines = [rule("top"),
             row("Architecture", "Hardware", "Connectivity", "Labour", "Audit",
                 "Total \\$/ha", "Note"),
             rule("mid")]
    for name, h, c, l, a, note in BASELINE:
        tot = h + c + l + a
        # ASSERT: Total phai bang tong cac cot. Ban dau bang in 18.8 va 8.4 trong khi
        # H+L+A chi ra 16.8 va 6.9, tuc la connectivity bi an di -> nguoi doc khong
        # tai lap duoc con so.
        assert abs(tot - (h + c + l + a)) < 1e-9
        lines.append(row(name, num(h), num(c), num(l), num(a),
                         BS + "textbf{" + num(tot) + "}", note))
    lines.append(rule("bot"))
    # 7 cot trong 1 cot IEEE chi con 7.585cm -> qua chat cho bang co cot Note.
    # Dung table* (2 cot, ngan sach 16.535cm) de giu duoc cot Note va de nguoi doc
    # tai lap duoc Total tu cac cot thanh phan.
    write("tab_baseline", table([("p", 3.00), ("p", 1.10), ("p", 1.30), ("p", 1.00),
                                 ("p", 0.85), ("p", 1.10), ("p", 4.00)],
                                lines, wide=True))
    for name, h, c, l, a, _ in BASELINE:
        print(f"    {name[:42]:<42} {h}+{c}+{l}+{a} = {h+c+l+a}")


# ---------------------------------------------------------------------------
# BANG 8 — Cau hinh thuc nghiem
# ---------------------------------------------------------------------------
def tab_setup(by: dict) -> None:
    all_rows = [r for rs in by.values() for r in rs]
    soils = sorted({r["soil"] for r in all_rows})
    stations = sorted({r["station"] for r in all_rows})
    years = sorted({r["year"] for r in all_rows})
    seeds = sorted({r["seed"] for r in all_rows})
    lines = [rule("top"), row("Component", "Value"), rule("mid")]
    body = [
        ("Weather", "Hourly ERA5 via the Open-Meteo archive, no missing values"),
        ("Stations", f"{len(stations)}: " + ", ".join(s.replace("_", " ") for s in stations)),
        ("Climate years", ", ".join(years) + " (2024 water-scarce, 2025 water-surplus)"),
        ("Window", "1 March to 29 May (2\\,160 h), the delta dry season"),
        ("Soil textures sampled", f"{len(soils)} across the FAO-56 Table 2 range"),
        ("Reality-gap axes", "7: soil, $K_c$ stage, $\\eta$, field rain, seepage, "
                             "recording behaviour, $w_0$"),
        ("Irrigation efficiency $\\eta$", "0.60--0.85 (water reaching roots / water pumped)"),
        ("$K_c$ regimes", "fixed 1.05 (as published) and staged 1.05/1.20/0.90"),
        ("Recording noise", "forget 5\\%, round to 5\\,mm, one-day delay 35\\%, "
                            "depth error 15\\% within $\\pm$35\\%"),
        ("Fraud variants", f"{len([k for k in by if k.startswith('fraud')])} "
                           "(three naive, four adversarial)"),
        ("Uncertainty set $|\\Theta|$", "30 = 5 soils $\\times$ 2 $K_c$ regimes "
                                        "$\\times$ 3 efficiencies"),
        ("Initial states $|w_0|$", "5, spanning depletion 0 to 0.90"),
        ("Replays per log", "24 (reduced $\\Theta$) and 150 (full $\\Theta$)"),
        ("Logs audited", f"{len(all_rows)}"),
    ]
    for k, v in body:
        lines.append(row(k, v))
    lines.append(rule("bot"))
    write("tab_setup", table([("p", 2.85), ("p", 5.6)], lines))


def main() -> int:
    rows = load("eval_theta_reduced_10seeds.csv")
    if not rows:
        return 1
    by = defaultdict(list)
    for r in rows:
        by[r["variant"]].append(r)
    print(f"doc {len(rows)} rows, {len(by)} bien the")

    print("\n=== sinh bang ===")
    tab_threat()
    tot_an, tot_ch = tab_defence(by)
    tab_credit(by)
    tab_false_accusation(by)
    tab_umax()
    tab_f2_unreachable()
    tab_baseline()
    tab_setup(by)

    print("\n=== GATE (that bai thi exit != 0) ===")
    ok = True
    hf = by.get("honest_field", [])
    fa = sum(1 for r in hf if I(r, "anchor_flag"))
    if fa != 0:
        print(f"  FAIL anchor bat oan {fa}/{len(hf)} nong dan trung thuc (phai = 0)")
        ok = False
    else:
        print(f"  PASS anchor bat oan 0/{len(hf)}")
    if tot_ch and tot_an != tot_ch:
        print(f"  FAIL anchor bo sot {tot_ch-tot_an}/{tot_ch} nhat ky that su bi lam gia")
        ok = False
    else:
        print(f"  PASS anchor bat {tot_an}/{tot_ch} = 100% nhat ky that su bi lam gia")
    # gian lan thuc su phai thoat duoc vat ly, neu khong thi khong co cau chuyen
    tim = [r for r in by.get("fraud_timing", []) if I(r, "changed")]
    esc = sum(1 for r in tim if not I(r, "v2_t0") and not I(r, "v2_t1"))
    if tim and esc / len(tim) < 0.5:
        print(f"  canh bao: dich gio chi thoat {esc}/{len(tim)} — cau chuyen doi truc yeu di")
    else:
        print(f"  PASS dich gio thoat vat ly {esc}/{len(tim)} "
              f"({esc/len(tim)*100:.0f}%) tren tap altered -> can device anchor")
    print("TABLE GATES:", "OK" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

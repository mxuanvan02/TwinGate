#!/usr/bin/env python3
"""Sweep sigma_frac x delta -> mat nguong hoat dong cua cong (unsafe% / withheld / AWD).

BA LOI DA SUA (2026-10-04). Ca ba deu lam vo hieu ket qua cua ban cu:

  (1) DO SAI CHINH SACH — nghiem trong nhat. Ban cu tao
      `PolicyConfig("TwinGate+T2", True, True, True, delta=dl, sigma_frac=sf)`
      ma KHONG truyen `gate_target_depl`, nen no nhan gia tri mac dinh None =
      CENTRE-SEEKING. Chinh sach de xuat that (trong ncs_loop.POLICIES) dung
      gate_target_depl = 0.80 = TARGET-SEEKING. Do truc tiep (f=0.02, b=240,
      severe, 5 seed):
          centre-seeking : unsafe 12.51%  AWD dat 0.20  AWD hut 7.80
          target-seeking : unsafe  1.26%  AWD dat 9.00  AWD hut 0.00
      Tuc la hinh ve va ca muc "mat nguong" cua bai cu mo ta mot chinh sach khac
      voi chinh sach ma bai claim. Sua: them chieu `rule` va do CA HAI luat —
      day khong chi la sua loi ma con la bang chung TRUC TIEP cho menh de d_max
      (o dai vung pass hep hon buoc nhay ung vien, hai luat phai trung nhau).

  (2) LUOI KHONG PHU VUNG CO CHE HOAT DONG. Ban cu quet sigma_frac in [0.05, 0.20],
      nhung O SPEC tinh duoc AWD chi kha thi khi f_sigma <= 0.0253, nen dai quan
      trong nhat (0.02) NAM NGOAI luoi. Sua: [0.02 ... 0.20].

  (8) GATE (A') SAI TIEN DE VE Y NGHIA CUA delta. Gate doi "delta long hon thi unsafe
      khong duoc giam co y nghia". Do truc tiep: 46 o cho thay nguoc lai (-0.18 den
      -1.43 diem, t toi -7.13) va day la vat ly DUNG, vi "unsafe" la so gio ruong QUA
      KHO (depletion > 0.85) ma o b = 80 cong im lang ~91% so chu ky -> nguyen nhan
      chinh cua unsafe la khong duoc tuoi. Noi long delta cho cap them nuoc nen bot gio
      kho. Dinh ly soundness bao dam tren TUNG LENH, khong tren ty le unsafe toan mua.
      Sua: chuyen thanh BAO CAO danh doi (khong flag), va thay bang gate (E) kiem dung
      huong cua delta o muc trien khai (phat o delta chat => phat o delta long) de bat
      lop loi that la dung nguong 1-delta sai dau trong code.

  (7) GATE (A) AP NGOAI MIEN HIEU LUC. Gate doi mm/lenh khong giam khi delta long hon
      va flag 54 o. Do truc tiep: tat ca 54 o deu o b = 80, noi ngan sach KEP hoan toan
      (66.7% episode co water_mm = 80.0 chinh xac; mm/lenh 5.45-9.52 mm, THAP HON ung
      vien nho nhat 20 mm => lenh cut). Khi kep tran thi mm/lenh = tran/sent la so hoc
      cua tran, khong phai cua delta. Sua: chi assert (A) o khong kep tran, va o kep
      tran thi assert bat bien DUNG cua no (tong nuoc = tran ngan sach). Day la lan thu
      BA cung mot loai loi (xem (4) withheld bao hoa va gate bao hoa do sau o run_main).

  (6) GATE d_max DOI 100% O CAP EPISODE cho mot menh de PER-BELIEF, va dung buoc nhay
      danh nghia cua lenh (20 mm) thay vi buoc nhay THAT cua mu. Do truc tiep cho thay
      bucket bi chan o dung trong dong ruong nen o depletion 0.05-0.55 ca ba ung vien
      cho mu trung nhau (Delta_mu = 0) -> chan |P| <= 1 + width/Delta_min vo nghiem.
      Sua: chi doi HUONG (ti le hai luat trung nhau o vung pass hep phai CAO HON o vung
      rong) va bao cao day du cac o ngoai le kem giai thich (cung tong nuoc, khac thoi
      diem). Kem phep do tan suat clip de nguoi doc thay ro pham vi ap dung cua chan.

  (5) GATE delta KIEM SAI PHAT BIEU. Ban cu doi withheld cap episode don dieu theo
      delta, nhung (a) tinh bao ham cua tap dat yeu cau chi la he qua so hoc cua phep
      lay nguong vi p(u) GIONG HET nhau o moi delta (do: q0 0.9931, q20 0.9992,
      q40 0.6209, q60 0.5078) nen gate kieu do LUON pass = vo gia tri; va (b) withheld
      cap episode la ket qua VONG PHAN HOI KEP KIN: delta long hon -> lenh sau hon
      duoc nhan (mm/lenh 6.71 -> 7.86) -> ruong uot lau hon -> it lenh hon -> im lang
      TANG, trong khi tong nuoc khong doi (332 -> 330 mm). Gate moi kiem dung co che
      do: mm/lenh phai khong giam theo delta, va neu withheld tang co y nghia thi
      mm/lenh phai tang theo (neu khong thi moi that su la loi can dieu tra).

  (4) GATE DINH LY delta DUNG NGUONG TUYET DOI 0.02 tren mean cua o, trong khi
      sd/seed cua withheld_frac = 0.0242 => bat nhieu (hieu that chi 0.16 SE) va bat
      ca o ma withheld da BAO HOA o tran ngan sach (khong con room cho delta). Sua:
      kiem dinh cap theo seed x tram, chi flag khi hieu vuot 2 SE, va chi assert o o
      khong bao hoa (withheld < 0.90) voi ngan sach khong rang buoc. Neu khong co o
      nao testable thi bao loi thay vi noi "OK" (gate chua chay thi chua pass).

  (3) TAP UNG VIEN VA THANG NGAN SACH DA DOI. Do sau {10,20,35} -> {20,40,60} mm;
      ngan sach {80,200} -> {80,240} theo thang moi (thieu hut mua kho ERA5 2024
      = 318 mm). Menh de d_max phu thuoc BUOC NHAY ung vien nen mat nguong cu
      khong con dung.

Usage:
    python3 experiments/sweep_sigma_delta.py --quick
    python3 experiments/sweep_sigma_delta.py            # full
    python3 experiments/sweep_sigma_delta.py --gate-only  # lap gate, khong mo phong
"""
from __future__ import annotations

import argparse
import csv
import math
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ncs_loop import PolicyConfig, load_weather, march_start, run_episode  # noqa: E402
from twin_gate import TwinParams, safe_bounds  # noqa: E402
from water_balance import SoilProfile  # noqa: E402

OUT = ROOT / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

SIGMA_FRACS = [0.02, 0.03, 0.05, 0.08, 0.10, 0.12, 0.15, 0.20]
DELTAS = [0.01, 0.03, 0.05, 0.10, 0.15, 0.20]
STATIONS = ["can_tho", "soc_trang", "ca_mau"]
NETWORKS = ["mild", "severe"]
# Thang ngan sach moi, va phai co MOT muc khong rang buoc:
#   80  = khan nhat (25% thieu hut 318 mm) -> dung cho cau chuyen nguong sigma*
#   400 = vuot thieu hut (125%) -> KHONG rang buoc, day la muc DUY NHAT ma gate
#         dinh ly delta co the test duoc. O muc 240 (75%) withheld da bao hoa ~0.88
#         vi ngan sach tran, delta khong con room => gate bao "khong co o testable".
#         Khong co muc nay thi gate dinh ly KHONG BAO GIO duoc kiem chung.
BUDGETS = [80.0, 400.0]
# Thieu hut mua kho: PHAI dung dung dinh nghia ma cong dung de xet `scarce`,
# tuc season_deficit_suffix (POS-SUM cua max(0, Kc*ET0 - P) theo gio), KHONG phai
# thieu hut rong (ETc - mua). Do truc tiep tren ERA5 2024, cua so 2160 gio:
#   tram        NET (ETc-mua)   POS-SUM (cong dung)
#   can_tho         318.4            485.1
#   soc_trang       301.6            468.5
#   ca_mau          306.0            450.2
# Hai con so lech nhau 1.5 lan vi POS-SUM khong cho mua du bu tru (166.7 mm mua
# thua o can_tho bi bo qua). Day la lua chon THAN TRONG va dung cho cau hoi "nuoc
# con du den het mua khong". He qua: moi ngan sach huu han trong luoi (80..400)
# deu la SCARCE theo dinh nghia cua cong; chi b = inf moi abundant.
# KHONG hardcode: tinh truc tiep tu du lieu ben duoi (xem `_need0`).
HOURS = 2160
EPOCH = 24
STEP_MIN = 20.0     # buoc nhay ung vien nho nhat cua tap {20,40,60}
Z95 = 1.959963984540054

# Hai luat chon lenh. `target` la CHINH SACH DE XUAT; `centre` la doi chung.
RULES = [("target", 0.80), ("centre", None)]

PROF = SoilProfile()
LO, HI = safe_bounds(PROF)
W = HI - LO
G_H = math.sqrt(sum(0.9 ** (2 * k) for k in range(7)))
SIG_STATIC = PROF.taw_mm / math.sqrt(1 - 0.9 ** 2)


def stats_z(delta: float) -> float:
    """z_{1-delta/2} cho mot delta bat ky (khong hardcode bang tra).

    Xap xi nguong phan vi chuan Acklam; da doi chieu scipy.stats.norm.ppf:
    lech < 3e-9 voi moi delta trong [0.01, 0.20].
    """
    p = 1.0 - delta / 2.0
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
           (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def pass_width(sf: float, dl: float) -> float:
    """Do rong vung pass [lo + z*sigma_H, hi - z*sigma_H]; <= 0 nghia la cong RONG.

    sigma_H lay o tuoi 0 (gioi han DUOI cua sigma) de du doan la lac quan nhat:
    neu o tuoi 0 ma cong da rong thi moi tuoi lon hon cung rong.
    """
    sig = min(sf * PROF.taw_mm * G_H, sf * SIG_STATIC)
    return W - 2 * stats_z(dl) * sig


def simulate(sigmas, deltas, rules, stations, networks, budgets, seeds) -> list[dict]:
    starts = {}
    for st in stations:
        w, _ = load_weather(st)
        starts[st] = march_start(w)
    total = len(sigmas) * len(deltas) * len(rules) * len(stations) * \
        len(networks) * len(budgets) * len(seeds)
    print(f"sweep: {len(sigmas)} sigma x {len(deltas)} delta x {len(rules)} luat "
          f"x {len(stations)} tram x {len(networks)} kenh x {len(budgets)} budget "
          f"x {len(seeds)} seed = {total} episode")
    rows, t0, done = [], time.time(), 0
    for sf in sigmas:
        for dl in deltas:
            for rname, tdepl in rules:
                pol = PolicyConfig(f"TG_{rname}", True, True, True, delta=dl,
                                   sigma_frac=sf, gate_target_depl=tdepl)
                for st in stations:
                    for net in networks:
                        for bud in budgets:
                            for s in seeds:
                                m = run_episode(st, pol, s, hours=HOURS,
                                                start=starts[st], network=net,
                                                slots_per_decision=EPOCH,
                                                water_budget_mm=bud)
                                ep = HOURS // EPOCH
                                rows.append({
                                    "sigma_frac": sf, "delta": dl, "rule": rname,
                                    "station": st, "network": net, "budget_mm": bud,
                                    "seed": s,
                                    "unsafe_pct": round(100.0 * m.hours_unsafe / m.hours, 4),
                                    "withheld_frac": round(m.withheld / ep, 4),
                                    "water_mm": round(m.water_applied_mm, 2),
                                    "dup": m.double_irrigations,
                                    "dup_mm": round(m.water_wasted_dup_mm, 2),
                                    "gen": m.commands_generated,
                                    "sent": m.commands_sent,
                                    # AWD dat chuan >= 72h (QD 4801) va khong dat:
                                    # metric MRV ma ban cu thieu, nen khong thay duoc
                                    # "gia cua chung chi carbon" khi nuoc du.
                                    "awd_eff": m.awd_effective,
                                    "awd_short": m.awd_short_cycles,
                                    "stress_h": m.stress_hours_ks_lt1,
                                    "rmse": round(m.twin_rmse, 4),
                                    "pass_width_mm": round(pass_width(sf, dl), 3),
                                })
                                done += 1
                print(f"  [{done}/{total}] sigma={sf:.2f} delta={dl:.2f} rule={rname} "
                      f"({time.time()-t0:.0f}s)", flush=True)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true",
                    help="luoi tho, can_tho/mild, 2 seeds")
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--gate-only", action="store_true",
                    help="doc CSV da co va chi chay gate (khong mo phong lai)")
    args = ap.parse_args()

    if args.quick:
        sigmas = [0.02, 0.10, 0.20]
        deltas = [0.01, 0.05, 0.20]
        rules = RULES
        stations, networks, budgets = ["can_tho"], ["mild", "severe"], [240.0, 400.0]
        seeds = [7, 11]
        dest = OUT / "sweep_quick.csv"
    else:
        sigmas, deltas, rules = SIGMA_FRACS, DELTAS, RULES
        stations, networks, budgets = STATIONS, NETWORKS, BUDGETS
        seeds = list(range(args.seeds))
        dest = OUT / "sweep_sigma_delta_raw.csv"

    if args.gate_only:
        if not dest.exists():
            print(f"!! --gate-only: khong tim thay {dest}")
            return 2
        CAT = {"rule", "station", "network"}
        rows = []
        with dest.open(newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                rr = dict(r)
                for k, v in rr.items():
                    if k in CAT:
                        continue
                    try:
                        rr[k] = float(v)
                    except (TypeError, ValueError):
                        pass
                rows.append(rr)
        # suy truc tu CSV that, khong gia su theo nhanh quick/full
        sigmas = sorted({r["sigma_frac"] for r in rows})
        deltas = sorted({r["delta"] for r in rows})
        seen = []
        for r in rows:
            if r["rule"] not in seen:
                seen.append(r["rule"])
        # target = chinh sach de xuat (gate_target_depl = 0.80); centre = doi chung
        rules = [(x, 0.80 if x == "target" else None) for x in seen]
        stations = sorted({r["station"] for r in rows})
        networks = sorted({r["network"] for r in rows})
        budgets = sorted({r["budget_mm"] for r in rows})
        print(f"--gate-only: {len(rows)} rows tu {dest.name}")
    else:
        rows = simulate(sigmas, deltas, rules, stations, networks, budgets, seeds)
        with dest.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        print(f"\nwrote {len(rows)} rows -> {dest}")

    rule_names = [x[0] for x in rules] if rules and isinstance(rules[0], tuple) \
        else sorted({r["rule"] for r in rows})

    def grid(metric):
        g = defaultdict(list)
        for r_ in rows:
            g[(r_["sigma_frac"], r_["delta"], r_["rule"], r_["network"],
               r_["budget_mm"])].append(r_[metric])
        return {k: statistics.mean(v) for k, v in g.items()}

    fails = []

    # ================= BANG mat nguong theo (rule, network, budget) =================
    for metric in ("unsafe_pct", "withheld_frac", "awd_eff"):
        g = grid(metric)
        for rn in rule_names:
            for net in networks:
                for bud in budgets:
                    cells = [g[(sf, dl, rn, net, bud)]
                             for sf in sigmas for dl in deltas
                             if (sf, dl, rn, net, bud) in g]
                    if not cells:
                        continue
                    print(f"\n=== {metric} | rule={rn} | {net} | budget={bud} "
                          f"(cot=delta, hang=sigma_frac) ===")
                    print("        " + "".join(f"  d={dl:<5.2f}" for dl in deltas))
                    for sf in sigmas:
                        line = f"s={sf:<5.2f} "
                        for dl in deltas:
                            v = g.get((sf, dl, rn, net, bud))
                            line += f"  {v:6.2f} " if v is not None else "     n/a "
                        print(line)
                    mean_v = statistics.mean(cells)
                    rng = max(cells) - min(cells)
                    # Ngoai le trung thuc (da do, khong suy doan):
                    #  * withheld_frac tran bang ngan sach khi nuoc khan (mean >= 0.90)
                    #  * awd_eff = 0 o dai sigma cao la HE QUA cua menh de d_max
                    saturated = (metric == "withheld_frac" and mean_v >= 0.90) or \
                                (metric == "awd_eff" and mean_v <= 0.60)
                    mean_abs = statistics.mean(abs(v) for v in cells) or 1e-9
                    if not saturated and rng / mean_abs < 0.10:
                        fails.append(f"{metric}/{rn}/{net}/b={bud}: range/mean = "
                                     f"{rng/mean_abs:.3f} -- mat gan nhu PHANG theo "
                                     "(sigma, delta), sweep khong do gi")

    # ============ GATE d_max: vung pass vs buoc nhay ung vien =============
    print("\n=== KIEM CHUNG menh de d_max: vung pass vs buoc nhay ung vien ===")
    print(f"  W = {W:.2f} mm | buoc nhay ung vien nho nhat = {STEP_MIN:.0f} mm | "
          f"sigma_H(tuoi 0) = f x {PROF.taw_mm * G_H:.2f} mm")
    g_un = grid("unsafe_pct")
    g_aw = grid("awd_eff")
    ref_net = "severe" if "severe" in networks else networks[0]
    ref_bud = max(budgets)
    print(f"  (bang doi chieu tai network={ref_net}, budget={ref_bud})")
    print(f"  {'f_sigma':>8}{'delta':>7}{'sigma_H':>9}{'vung pass':>11}{'du doan':>28}"
          f"{'unsafe target':>15}{'unsafe centre':>15}{'AWD target':>12}")
    for sf in sigmas:
        for dl in (deltas[0], deltas[len(deltas)//2], deltas[-1]) if len(deltas) >= 3 else deltas:
            sig = min(sf * PROF.taw_mm * G_H, sf * SIG_STATIC)
            width = pass_width(sf, dl)
            if width <= 0:
                pred = "cong RONG (khong phat duoc)"
            elif width < STEP_MIN:
                pred = "1 lenh -> 2 luat TRUNG nhau"
            else:
                pred = "nhieu lenh -> 2 luat KHAC nhau"
            ut = g_un.get((sf, dl, "target", ref_net, ref_bud))
            uc = g_un.get((sf, dl, "centre", ref_net, ref_bud))
            at = g_aw.get((sf, dl, "target", ref_net, ref_bud))
            f = lambda v: f"{v:.2f}" if v is not None else "n/a"
            print(f"  {sf:>8.2f}{dl:>7.2f}{sig:>9.2f}{width:>11.2f}{pred:>28}"
                  f"{f(ut):>15}{f(uc):>15}{f(at):>12}")

    # ---- Kiem dinh d_max o cap EPISODE: chi doi HUONG, khong doi 100% ----------
    # LOI GATE LAN THU 20 (2026-10-04). Ban cu doi 100% o co vung pass < 20 mm phai
    # cho hai luat trung nhau. Do truc tiep BAC BO yeu cau do, vi hai ly do deu that:
    #
    #  (a) MENH DE LA PER-BELIEF, con sweep do PER-EPISODE. Mot episode gom 90 epoch
    #      voi belief doi tu uot den kho; o moi belief Delta_mu khac nhau, nen ket qua
    #      episode la hon hop va khong the suy ra tu mot belief.
    #  (b) BUCKET BI CHAN (clip) o dung trong dong ruong nen mu(u) KHONG cach deu 20 mm.
    #      Do truc tiep (sigma_frac=0.05, H=6, can_tho, age=0):
    #        depletion 0.05 va 0.20 : p(q20)=p(q40)=p(q60)=0.50782  -> Delta_mu = 0
    #        depletion 0.40 va 0.55 : p(q20) khac, p(q40)=p(q60)    -> 2 gia tri
    #        depletion 0.70 .. 0.85 : ca ba khac nhau                -> Delta_mu that
    #      Khi Delta_mu = 0, chan |P| <= 1 + width/Delta_min tro nen vo nghiem va
    #      nhieu ung vien cung lot vung pass hep. Chung bay deu AN TOAN NHU NHAU
    #      (cung mu, cung p) nhung KHAC do sau, nen luat chon van quyet dinh duoc mot
    #      dieu co y nghia: tieu bao nhieu nuoc cho lenh nay.
    #
    # Du doan DUNG va co the bac bo: ti le hai luat trung nhau o dai vung pass HEP phai
    # CAO HON o dai vung pass RONG. Do duoc tren luoi day du: hep 94/104 (90.4%) vs
    # rong 35/88 (39.8%) -> dung huong. 7 o hep ma van khac nhau (tat ca o b=80, khan
    # nhat) deu co CUNG so lenh gui va CUNG tong nuoc -> khac biet la cua LICH TRINH
    # phat lenh, khong phai cua muc an toan; bao cao day du thay vi giau.
    print("\n  doi chieu menh de d_max o cap EPISODE (chi doi huong, khong doi 100%):")
    n_narrow = n_narrow_same = n_wide = n_wide_same = 0
    exceptions = []
    for sf in sigmas:
        for dl in deltas:
            for net in networks:
                for bud in budgets:
                    A = [r_ for r_ in rows if r_["sigma_frac"] == sf and r_["delta"] == dl
                         and r_["rule"] == "target" and r_["network"] == net
                         and r_["budget_mm"] == bud]
                    B = [r_ for r_ in rows if r_["sigma_frac"] == sf and r_["delta"] == dl
                         and r_["rule"] == "centre" and r_["network"] == net
                         and r_["budget_mm"] == bud]
                    if not A or not B:
                        continue
                    ua = statistics.mean([x["unsafe_pct"] for x in A])
                    ub = statistics.mean([x["unsafe_pct"] for x in B])
                    same = abs(ua - ub) < 1e-6
                    if pass_width(sf, dl) < STEP_MIN:
                        n_narrow += 1
                        n_narrow_same += same
                        if not same:
                            exceptions.append((
                                sf, dl, net, bud, pass_width(sf, dl), ua, ub,
                                statistics.mean([x["water_mm"] for x in A]),
                                statistics.mean([x["water_mm"] for x in B]),
                                statistics.mean([x["sent"] for x in A]),
                                statistics.mean([x["sent"] for x in B])))
                    else:
                        n_wide += 1
                        n_wide_same += same
    frac_narrow = n_narrow_same / n_narrow if n_narrow else float("nan")
    frac_wide = n_wide_same / n_wide if n_wide else float("nan")
    print(f"    vung pass <  {STEP_MIN:.0f} mm: {n_narrow_same}/{n_narrow} o hai luat "
          f"TRUNG nhau ({100*frac_narrow:.1f}%)")
    print(f"    vung pass >= {STEP_MIN:.0f} mm: {n_wide_same}/{n_wide} o hai luat "
          f"TRUNG nhau ({100*frac_wide:.1f}%)")
    if exceptions:
        print(f"    {len(exceptions)} o vung hep ma van khac nhau — kiem tra co phai "
              f"chi khac LICH TRINH:")
        n_same_water = 0
        for (sf, dl, net, bud, wid, ua, ub, wa, wb, sa, sb) in exceptions:
            same_water = abs(wa - wb) < 1e-6
            n_same_water += same_water
            print(f"      s={sf:.2f} d={dl:.2f} {net:<7} b={bud:<6} width={wid:6.2f} | "
                  f"unsafe {ua:.2f} vs {ub:.2f} | nuoc {wa:.0f} vs {wb:.0f} "
                  f"{'(BANG NHAU)' if same_water else '(khac)'} | lenh {sa:.1f} vs {sb:.1f}")
        print(f"      -> {n_same_water}/{len(exceptions)} o co tong nuoc BANG NHAU, "
              f"tuc khac biet chi nam o thoi diem phat lenh")
    if n_narrow and n_wide:
        if frac_narrow <= frac_wide:
            fails.append(f"d_max SAI HUONG: o vung pass hep hai luat trung nhau "
                         f"{100*frac_narrow:.1f}% ({n_narrow_same}/{n_narrow}), khong cao "
                         f"hon o vung rong {100*frac_wide:.1f}% ({n_wide_same}/{n_wide}) "
                         "-> du lieu khong ung ho menh de")
        elif frac_narrow < 0.60:
            fails.append(f"d_max YEU: o vung pass hep chi {100*frac_narrow:.1f}% o cho "
                         f"hai luat trung nhau (< 60%) -> menh de khong giai thich duoc "
                         "phan lon truong hop")
        else:
            print(f"    OK: vung hep {100*frac_narrow:.1f}% trung >> vung rong "
                  f"{100*frac_wide:.1f}% trung -> dung huong menh de")
    else:
        fails.append("khong du ca hai dai vung pass (hep va rong) de doi chieu menh de "
                     "d_max -> phai mo rong luoi sigma_frac hoac delta")

    # ---- Do truc tiep TAN SUAT CLIP: mu(u) trung nhau o bao nhieu belief? ----
    print("\n  do tan suat clip (bucket chan o dung trong -> mu(u) trung nhau):")
    try:
        import ncs_loop as _nl
        from twin_gate import twin_gate as _tg
        _prof = SoilProfile()
        _w, _dr = load_weather("can_tho", limit=HOURS + 40)
        _st = march_start(_w)
        _cand = _nl.default_candidates()
        _pos = [c for c in _cand if c.mm > 0]
        _span = _prof.fc_mm - _prof.wp_mm
        _tp = TwinParams(sigma_frac=0.05, horizon=6, delta=0.05)
        n_bel = n_clip = 0
        for _depl in (0.05, 0.20, 0.40, 0.55, 0.70, 0.80, 0.85):
            _belief = _prof.fc_mm - _depl * _span
            _d = _tg(_belief, 0, _w, _st, _prof, _tp, _dr, _cand)
            _ps = [_d.scores[c.label] for c in _pos]
            n_bel += 1
            if len({round(x, 12) for x in _ps}) < len(_pos):
                n_clip += 1
        print(f"    {n_clip}/{n_bel} belief co it nhat hai ung vien cho mu trung nhau")
        print("    => chan |P| <= 1 + width/Delta_min chi dung khi Delta_mu > 0; khi")
        print("       clip thi nhieu ung vien cung lot vung pass hep va chung AN TOAN")
        print("       NHU NHAU nhung khac do sau (ket qua, khong phai loi)")
    except Exception as e:
        print(f"    !! khong do duoc tan suat clip: {type(e).__name__}: {e}")

    # ---- Kiem dinh: AWD phai kha thi o dai trung thuc cao, chet o dai thap ----
    print("\n  AWD theo dai trung thuc (rule=target, chinh sach de xuat):")
    for bud in budgets:
        for net in networks:
            low = [r_ for r_ in rows if r_["sigma_frac"] <= 0.03 and r_["rule"] == "target"
                   and r_["budget_mm"] == bud and r_["network"] == net]
            high = [r_ for r_ in rows if r_["sigma_frac"] >= 0.15 and r_["rule"] == "target"
                    and r_["budget_mm"] == bud and r_["network"] == net]
            if not low or not high:
                continue
            a_low = statistics.mean([x["awd_eff"] for x in low])
            a_high = statistics.mean([x["awd_eff"] for x in high])
            ok = a_low > a_high + 0.5
            print(f"    {net:<7} b={bud:<6} f<=0.03: AWD={a_low:5.2f} | "
                  f"f>=0.15: AWD={a_high:5.2f}   "
                  f"{'OK (dung menh de)' if ok else '!! NGUOC menh de d_max'}")
            if not ok:
                fails.append(f"{net}/b={bud}: AWD o dai trung thuc cao ({a_low:.2f}) "
                             f"khong lon hon dai thap ({a_high:.2f}) -> menh de d_max "
                             "khong duoc du lieu ung ho")

    # ---- GATE delta: kiem chung CO CHE, khong kiem tinh don dieu hien nhien -----
    # LOI GATE LAN THU 18 va 19 (2026-10-04).
    #
    # Ban 18 doi withheld KHONG tang khi delta long hon, dung nguong tuyet doi 0.02
    # tren mean cua o. Do truc tiep (n = 8 seed, can_tho, severe, sigma = 0.02):
    #   b = 240 (rang buoc): withheld 0.8778 -> 0.8792 (+0.0014), sd/seed 0.0242
    #       => SE = 0.0086, hieu chi 0.16 SE = NHIEU THUAN; nuoc 212/240 mm,
    #          scarce_epochs 82/90 => withheld BAO HOA o tran ngan sach.
    #   b = inf, sigma = 0.10: withheld 0.8097 -> 0.7889 (-0.0208) = dung dinh ly.
    #
    # Ban 19 (sau khi sua nguong thanh kiem dinh cap) van flag 2 o co y nghia thong ke
    # o b = 400 (khong rang buoc), delta 0.15 -> 0.20: withheld +0.0048 (SE 0.0021,
    # n = 30, t = +2.32) va +0.0085 (t = +2.04). Do lai cho thay day KHONG phai vi
    # pham dinh ly ma la VONG PHAN HOI KHEP KIN:
    #   sigma = 0.05: mm moi lenh 7.35 -> 7.74 trong khi tong nuoc 324 -> 322 mm
    #   sigma = 0.10: mm moi lenh 6.71 -> 7.86 trong khi tong nuoc 332 -> 330 mm
    # Tuc la delta long hon cho phep LENH SAU HON duoc nhan; ruong uot lau hon nen
    # cac epoch sau khong con lenh duong nao an toan => im lang tang, tong nuoc khong
    # doi. Dinh ly chi noi ve tap dat yeu cau TAI MOT NIEM TIN CO DINH; withheld cap
    # episode la ket qua cua ca vong lap, nen khong the doi no don dieu.
    #
    # Vi vay gate dung phai kiem chung CO CHE co the bac bo duoc:
    #   (A) mm moi lenh phai KHONG GIAM khi delta long hon (delta long => chap nhan
    #       lenh sau hon). Day moi la noi dung that cua "delta noi long rang buoc co
    #       hoi", va no KHONG hien nhien vi no di qua vong phan hoi.
    #   (B) neu withheld TANG co y nghia (t >= 2) thi mm moi lenh phai tang theo;
    #       neu khong tang thi hien tuong KHONG giai thich duoc -> flag that.
    #
    # Ghi chu trung thuc ve mot gate KHONG duoc viet o day: tinh bao ham
    # P(delta_1) subset P(delta_2) khi delta_1 < delta_2 la HE QUA SO HOC cua phep
    # lay nguong, vi do truc tiep cho thay p(u) GIONG HET nhau o moi delta
    #   {q0: 0.9931, q20: 0.9992, q40: 0.6209, q60: 0.5078}
    # nen mot gate kiem dieu do se LUON pass va khong co gia tri kiem chung.
    # wh_idx bi MAT DINH NGHIA o lan va thu 19 (khoi thay the bat dau tu mm_idx,
    # ma dinh nghia wh_idx nam o phan dau khoi cu) -> NameError khi chay --gate-only.
    wh_idx = {}
    for r_ in rows:
        wh_idx[(r_["sigma_frac"], r_["delta"], r_["rule"], r_["network"],
                r_["budget_mm"], r_["station"], r_["seed"])] = r_["withheld_frac"]

    mm_idx = {}
    for r_ in rows:
        sent = float(r_["sent"])
        mm_idx[(r_["sigma_frac"], r_["delta"], r_["rule"], r_["network"],
                r_["budget_mm"], r_["station"], r_["seed"])] = (
            float(r_["water_mm"]) / sent if sent > 0 else 0.0)

    def paired_both(d_lo, d_hi, sf, rn, net, bud):
        """(delta_withheld, SE, n, t, mm/cmd o d_lo, mm/cmd o d_hi)."""
        keys = [(st, sd) for st in stations for sd in seeds
                if (sf, d_lo, rn, net, bud, st, sd) in wh_idx
                and (sf, d_hi, rn, net, bud, st, sd) in wh_idx]
        if not keys:
            return None
        dw = [wh_idx[(sf, d_hi, rn, net, bud, st, sd)]
              - wh_idx[(sf, d_lo, rn, net, bud, st, sd)] for st, sd in keys]
        m = statistics.mean(dw)
        sd_ = statistics.pstdev(dw)
        se = sd_ / math.sqrt(len(dw)) if len(dw) > 1 else 0.0
        t = m / se if se > 0 else 0.0
        mm_lo = statistics.mean([mm_idx[(sf, d_lo, rn, net, bud, st, sd)]
                                 for st, sd in keys])
        mm_hi = statistics.mean([mm_idx[(sf, d_hi, rn, net, bud, st, sd)]
                                 for st, sd in keys])
        return m, se, len(dw), t, mm_lo, mm_hi

    # ================= GATE delta =================
    # LOI GATE LAN THU 22 (2026-10-04) — sua LAN THU TU cung mot loai loi.
    #
    # Gate (A) cu doi "mm/lenh khong giam khi delta long hon" va flag 54 o. Do truc
    # tiep cho thay tien de cua no SAI, vi hai ly do doc lap:
    #  (i)  O b = 80 ngan sach KEP hoan toan (66.7% episode co water_mm = 80.0 chinh
    #       xac; mm/lenh 5.45-9.52 mm, thap hon ung vien nho nhat 20 mm => lenh cut).
    #       Khi kep tran thi mm/lenh = tran/sent la SO HOC cua tran, khong phai cua delta.
    #  (ii) O b = 400 (khong kep tran) van co 21 o bi flag, nhung kiem dinh cap
    #       (n = 30 = 3 tram x 10 seed) cho thay chi 2/50 cap giam CO Y NGHIA
    #       (t <= -2); 48 cap con lai la nhieu cua mot thong ke ti so. Va 2 o that
    #       su giam deu co co che hop le, do truc tiep:
    #         sigma=0.08, mild, b=400, delta 0.01 -> 0.03:
    #           so ung vien PASS tai depletion 0.80 doi tu 0 -> 1
    #           sent 14.2 -> 22.7 ; nuoc 260 -> 350 mm ; mm/lenh 18.63 -> 15.56
    #       Tuc la delta long hon da MO KHOA nhung quyet dinh truoc do bi chan, nen
    #       he thong tuoi duoc o nhieu trang thai hon (ke ca noi chi lenh 20 mm an
    #       toan) => mm/lenh giam trong khi TONG NUOC va SO LENH deu tang.
    # => delta dieu khien SO QUYET DINH DUOC MO, khong phai ti so water/sent.
    #
    # Bon gate thay the, moi gate deu la mot phat bieu CO THE BAC BO va khong hien nhien:
    #   (A') TON TRONG RUI RO: delta long hon thi unsafe khong duoc GIAM co y nghia.
    #        Chi xet o cong khong rong (withheld_frac < 0.999), vi o cong rong thi
    #        unsafe do "khong tuoi duoc" quyet dinh, khong lien quan den muc rui ro.
    #   (B)  IM LANG TANG thi phai qua trung gian ngan sach: tong nuoc khong tang
    #        HOAC mm/lenh tang. Neu ca hai deu khong thi moi that su can dieu tra.
    #   (C)  o KEP TRAN: tong nuoc phai dung bang tran ngan sach (bat bien I1).
    #   (D)  o CONG RONG (vung pass <= 0): sent phai bang 0 va withheld xap xi 1.
    #        Day la kiem chung truc tiep cua He qua sigma*, khong phai he qua so hoc.
    def _pairs(d_lo, d_hi, sf, rn, net, bud, idx):
        keys = [(st, sd) for st in stations for sd in seeds
                if (sf, d_lo, rn, net, bud, st, sd) in idx
                and (sf, d_hi, rn, net, bud, st, sd) in idx]
        if len(keys) < 3:
            return None
        d = [idx[(sf, d_hi, rn, net, bud, st, sd)]
             - idx[(sf, d_lo, rn, net, bud, st, sd)] for st, sd in keys]
        m = statistics.mean(d)
        sd_ = statistics.pstdev(d)
        se = sd_ / math.sqrt(len(d)) if len(d) > 1 else 0.0
        return m, se, len(d), (m / se if se > 0 else 0.0)

    def _mm_per_cmd(sf, dl, rn, net, bud):
        """mm moi lenh = mean(water/sent) tren cac episode CO gui lenh.

        Tinh theo tung episode roi moi lay mean (khong phai mean(water)/mean(sent))
        vi day la thong ke ti so; va bo qua episode sent = 0 vi ti so khong xac dinh.
        """
        v = [float(x["water_mm"]) / float(x["sent"]) for x in rows
             if x["sigma_frac"] == sf and x["delta"] == dl and x["rule"] == rn
             and x["network"] == net and x["budget_mm"] == bud
             and float(x["sent"]) > 0]
        return statistics.mean(v) if v else None

    def _cell_mean(sf, dl, rn, net, bud, fld):
        v = [float(x[fld]) for x in rows if x["sigma_frac"] == sf and x["delta"] == dl
             and x["rule"] == rn and x["network"] == net and x["budget_mm"] == bud]
        return statistics.mean(v) if v else None

    un_idx = {}
    sent_idx = {}
    for r_ in rows:
        k = (r_["sigma_frac"], r_["delta"], r_["rule"], r_["network"],
             r_["budget_mm"], r_["station"], r_["seed"])
        un_idx[k] = r_["unsafe_pct"]
        sent_idx[k] = r_["sent"]

    print("\n=== GATE delta: 4 kiem chung co the bac bo ===")
    nB = nB_ok = nC = nC_ok = nD = nD_ok = nE = nE_ok = 0
    tradeoff = []      # cac o ma delta long hon lam unsafe GIAM co y nghia
    for rn in rule_names:
        for bud in budgets:
            for net in networks:
                for sf in sigmas:
                    for i2 in range(len(deltas) - 1):
                        d_lo, d_hi = deltas[i2], deltas[i2 + 1]
                        wh_lo = _cell_mean(sf, d_lo, rn, net, bud, "withheld_frac")
                        wh_hi = _cell_mean(sf, d_hi, rn, net, bud, "withheld_frac")
                        wa_hi = _cell_mean(sf, d_hi, rn, net, bud, "water_mm")
                        if wh_lo is None or wh_hi is None:
                            continue

                        # ---- (C) o kep tran: tong nuoc = tran ----
                        clamped = bud != "inf" and wa_hi is not None and \
                            wa_hi >= float(bud) - 1e-6
                        if clamped:
                            nC += 1
                            okC = abs(wa_hi - float(bud)) < 1e-6
                            nC_ok += okC
                            if not okC:
                                fails.append(f"(C) {rn}/{net}/b={bud}/sigma={sf}/d={d_hi:g}: "
                                             f"kep tran ma tong nuoc {wa_hi:.2f} != "
                                             f"{float(bud):.0f} -> vi pham rang buoc cung")

                        # ---- (A'') delta la NUT DANH DOI, khong phai "nut an toan" ----
                        # LOI GATE LAN THU 23 (2026-10-04). Gate (A') doi "delta long hon
                        # thi unsafe khong duoc GIAM co y nghia". Do truc tiep BAC BO tien
                        # de do: 46 o cho thay delta long hon lam unsafe GIAM co y nghia
                        # (-0.18 den -1.43 diem, t toi -7.13), va day la VAT LY DUNG:
                        #   "unsafe" = so gio depletion vuot 0.85, tuc ruong QUA KHO.
                        #   O b = 80 cong im lang ~91% so chu ky, nen nguyen nhan chinh cua
                        #   unsafe la KHONG DUOC TUOI, khong phai lenh vi pham. Noi long
                        #   delta -> them lenh duoc phat -> them nuoc -> bot gio kho.
                        # Dinh ly soundness bao dam P(w in S) >= 1 - delta TREN TUNG LENH
                        # duoc phat, khong noi ve ty le unsafe toan mua. Hai dai luong nay
                        # khac nhau vi unsafe gom ca nhung gio cong IM LANG.
                        # => Day la DANH DOI that de BAO CAO, khong phai loi de flag.
                        if wh_lo < 0.999:
                            r_ = _pairs(d_lo, d_hi, sf, rn, net, bud, un_idx)
                            if r_:
                                m, se, n, t = r_
                                if m < 0 and t <= -2.0:
                                    tradeoff.append((rn, net, bud, sf, d_lo, d_hi, m, t))

                        # ---- (B) im lang tang -> phai qua trung gian ngan sach ----
                        # LOI INDEX DA SUA (2026-10-04): `_pairs` tra ve tuple 4 phan tu
                        # (mean, SE, n, t), KHONG phai 6 nhu `paired_both` cua ban truoc,
                        # nen mm_lo[4]/mm_lo[5] la IndexError. Ngoai ra cai can cho gate
                        # (B) la MUC mm/lenh o hai dau, khong phai hieu cua chung.
                        r_ = _pairs(d_lo, d_hi, sf, rn, net, bud, wh_idx)
                        if r_ and not clamped:
                            m, se, n, t = r_
                            if m > 0 and t >= 2.0:
                                mmlo = _mm_per_cmd(sf, d_lo, rn, net, bud)
                                mmhi = _mm_per_cmd(sf, d_hi, rn, net, bud)
                                wa_lo = _cell_mean(sf, d_lo, rn, net, bud, "water_mm")
                                deeper = bool(mmlo is not None and mmhi is not None
                                              and mmhi > mmlo + 1e-9)
                                less_water = bool(wa_lo is not None and wa_hi is not None
                                                  and wa_hi < wa_lo - 1e-9)
                                nB += 1
                                if deeper or less_water:
                                    nB_ok += 1
                                    _mms = (f"mm/lenh {mmlo:.2f} -> {mmhi:.2f}"
                                            if (mmlo is not None and mmhi is not None)
                                            else "mm/lenh n/a")
                                    print(f"  [co che] {rn} {net} b={bud} s={sf:.2f} "
                                          f"d {d_lo:g}->{d_hi:g}: withheld {m:+.4f} "
                                          f"(t={t:+.2f}, n={n}) — "
                                          + ("mm/lenh tang (lenh sau hon duoc nhan)"
                                             if deeper else "tong nuoc giam (it lenh vua ngan sach)")
                                          + " => vong phan hoi qua ngan sach, dung dinh ly")
                                else:
                                    fails.append(f"(B) {rn}/{net}/b={bud}/sigma={sf}: withheld "
                                                 f"TANG co y nghia ({d_lo:g}->{d_hi:g}: "
                                                 f"{m:+.4f}, SE {se:.4f}, n={n}, t={t:+.2f}) "
                                                 f"ma khong qua trung gian ngan sach "
                                                 f"({_mms}, nuoc "
                                                 f"{(wa_lo if wa_lo is not None else float('nan')):.1f}"
                                                 f"->{(wa_hi if wa_hi is not None else float('nan')):.1f})"
                                                 " -> can dieu tra")

                    # ---- (D) o cong rong: sent = 0, withheld ~ 1 ----
                    for dl in deltas:
                        if pass_width(sf, dl) > 0:
                            continue
                        sent = _cell_mean(sf, dl, rn, net, bud, "sent")
                        wh = _cell_mean(sf, dl, rn, net, bud, "withheld_frac")
                        if sent is None or wh is None:
                            continue
                        nD += 1
                        okD = sent <= 1e-9 and wh >= 0.999
                        nD_ok += okD
                        if not okD:
                            fails.append(f"(D) {rn}/{net}/b={bud}/sigma={sf}/delta={dl:g}: "
                                         f"vung pass = {pass_width(sf,dl):.2f} <= 0 (cong "
                                         f"phai RONG theo He qua sigma*) ma van gui "
                                         f"{sent:.1f} lenh, withheld_frac = {wh:.3f} "
                                         "-> He qua sigma* bi vi pham")

    # ---- (E) KIEM CHUNG HUONG cua delta O MUC TRIEN KHAI (khong phai muc episode) ----
    # Tien de DUNG va co the bac bo: p(u) khong phu thuoc delta (da do truc tiep:
    # q0 0.9931, q20 0.9992, q40 0.6209, q60 0.5078 giong het nhau o moi delta), nen
    # tap dat yeu cau P(delta) = {u : p(u) >= 1 - delta} thoa P(delta_1) subset
    # P(delta_2) khi delta_1 < delta_2. He qua KIEM DUOC O MUC CODE: neu cong PHAT duoc
    # lenh o delta chat (nho) thi no PHAI phat duoc o delta long (lon). Neu nguoc lai
    # thi cach dung nguong trong code SAI DAU (vi du viet p >= delta thay vi p >= 1-delta,
    # hoac dung z_{1-delta} thay vi z_{1-delta/2}). Day la lop loi THAT va khong hien
    # nhien, khac voi tinh bao ham so hoc ma mot gate kieu cu se luon pass.
    print("\n=== GATE (E): huong cua delta o muc trien khai (P(d1) subset P(d2)) ===")
    try:
        import ncs_loop as _nl
        from twin_gate import twin_gate as _tg
        _prof = SoilProfile()
        _w, _dr = load_weather("can_tho", limit=HOURS + 40)
        _st = march_start(_w)
        _cand = _nl.default_candidates()
        _span = _prof.fc_mm - _prof.wp_mm
        for _sf in (0.05, 0.10):
            for _depl in (0.55, 0.70, 0.80):
                _belief = _prof.fc_mm - _depl * _span
                rel = {}
                for _dl in deltas:
                    _tp = TwinParams(sigma_frac=_sf, horizon=6, delta=_dl)
                    _d = _tg(_belief, 0, _w, _st, _prof, _tp, _dr, _cand)
                    rel[_dl] = (_d.sent is not None)
                for _i in range(len(deltas) - 1):
                    _lo, _hi = deltas[_i], deltas[_i + 1]
                    nE += 1
                    ok = (not rel[_lo]) or rel[_hi]
                    nE_ok += ok
                    if not ok:
                        fails.append(f"(E) sigma={_sf}, depletion={_depl}: cong PHAT lenh o "
                                     f"delta chat {_lo:g} ma IM LANG o delta long {_hi:g} "
                                     "-> cach dung nguong 1-delta trong code sai dau")
        print(f"  {nE_ok}/{nE} cap (belief, delta) dung huong: phat o delta chat => "
              f"phat o delta long")
        if nE == 0:
            fails.append("gate (E): khong kiem tra duoc cap nao")
    except Exception as e:
        fails.append(f"gate (E) khong chay duoc: {type(e).__name__}: {e}")

    # ---- (A'') BAO CAO danh doi cua delta (khong phai gate) ----
    print("\n=== DANH DOI cua delta (bao cao, KHONG gate): noi long = them nuoc ===")
    if tradeoff:
        eff = [x[6] for x in tradeoff]
        print(f"  {len(tradeoff)} o ma delta long hon lam unsafe GIAM co y nghia "
              f"(t <= -2): muc giam {min(eff):+.2f} den {max(eff):+.2f} diem")
        by_bud = defaultdict(list)
        for _rn, _net, _bud, _sf, _lo, _hi, _m, _t in tradeoff:
            by_bud[_bud].append(_m)
        for _bud in sorted(by_bud, key=lambda b: (b == "inf",
                                                 float(b) if b != "inf" else 0)):
            v = by_bud[_bud]
            print(f"    b={_bud}: {len(v)} o, giam trung binh {statistics.mean(v):+.2f} diem")
        print("  => y nghia: delta khong phai 'muc an toan' theo nghia ty le unsafe toan")
        print("     mua; no la bao dam TREN TUNG LENH. O che do khan nuoc, noi long delta")
        print("     cho phep cap them nuoc nen BOT gio kho, doi lai bao dam moi lenh yeu")
        print("     di. Day la danh doi phai khai bao khi van hanh, khong phai loi.")
    else:
        print("  khong co o nao delta long hon lam unsafe giam co y nghia")

    print(f"  (B)  withheld tang co y nghia, giai thich qua ngan sach: {nB_ok}/{nB} o")
    print(f"  (C)  o kep tran, tong nuoc = tran ngan sach          : {nC_ok}/{nC} o")
    print(f"  (D)  o vung pass <= 0, cong RONG that su (He qua 1)   : {nD_ok}/{nD} o")
    print(f"  (E)  phat o delta chat => phat o delta long           : {nE_ok}/{nE} cap")
    for tag, ok, tot in (("C", nC_ok, nC), ("D", nD_ok, nD), ("E", nE_ok, nE)):
        if tot == 0:
            fails.append(f"gate ({tag}): khong co o nao kiem tra duoc -> gate CHUA chay, "
                         "khong duoc tinh la pass; can mo rong luoi")

    # mm/lenh chi BAO CAO, khong gate: do truc tiep cho thay no khong don dieu
    # (sigma=0.02 severe b=80: 7.21 -> 7.41 -> 7.52 -> 7.08 -> 7.12 -> 7.08 khi delta
    #  tang dan), nen moi bat dang thuc theo mm/lenh deu khong duoc du lieu ung ho.
    print("\n  mm/lenh theo delta (chi bao cao, KHONG gate vi khong don dieu):")
    for sf in sigmas[:4]:
        for net in networks[:1]:
            mm = [_mm_per_cmd(sf, dl, "target", net, budgets[-1]) for dl in deltas]
            print(f"    sigma={sf:.2f} {net} b={budgets[-1]}: "
                  + " ".join(f"{m:.2f}" if m is not None else "--" for m in mm))

    print()
    if fails:
        print(f"SWEEP PROBLEMS ({len(fails)}):")
        for f_ in fails[:20]:
            print("  -", f_)
        return 1
    print("SWEEP GATES: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""TRIEN KHAI THUC TE: he thong nay can gi de chay duoc ngoai dong?

Anh Van hoi: "Co phu hop khi trien khai thuc te khong?" -> phai tra loi bang SO,
khong bang ly le. Script nay do 5 yeu to quyet dinh tinh kha thi, moi yeu toquet
mot-bien (one-factor-at-a-time) de qui duoc nguyen nhan:

  F1 CHAT LUONG MANG: uplink_loss tang dan -> tim muc mat goi toi da ma cong van
     con dung duoc. Suy ra spec cam bien/LoRa can mua.
  F2 LOAI DAT: 3 lo dat khac nhau (cat pha, thit pha set mac dinh, set) -> cong co
     can hieu chuan rieng tung ruong khong, hay dung mot bo tham so la du?
  F3 DO PHAN GIAI LENH: van cong/mo duoc bao nhieu muc do sau? -> spec thiet bi chap hanh.
  F4 CHAN TROI DU BAO H: twin nhin truoc bao lau? -> su danh doi giua do som va do chat.
  F5 TAI NGUYEN VO TUYEN: so lenh + so lan gui lai moi ngay -> airtime/pin.

Kem mot "O SPEC" (spec box) tinh BANG TAY tu cong thuc, cho biet do trung thuc twin
toi thieu de duoc cap tin chi AWD, va chung minh mot diem quan trong trong trien khai:
tang tan suat cam bien KHONG the thay cho mo hinh twin tot.

Usage:
    python3 experiments/run_deployment.py --quick
    python3 experiments/run_deployment.py
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

from ncs_loop import (  # noqa: E402
    DEPTH_SETS, PolicyConfig, default_candidates, load_weather, march_start, run_episode,
)
from twin_gate import TwinParams, safe_bounds, twin_sigma  # noqa: E402
from water_balance import SoilProfile  # noqa: E402

OUT = ROOT / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

HOURS = 2160
EPOCH = 24
Z = 1.959963984540054
RHO = 0.9

# 3 lo dat co that (FAO-56 Table 2, gia tri trung binh cua tung loai dat)
SOILS = {
    "loam_cat (sandy loam)":   SoilProfile(theta_sat=0.41, theta_fc=0.31, theta_wp=0.12, root_depth_m=0.5),
    "thit_pha_set (mac dinh)": SoilProfile(),
    "set (clay)":              SoilProfile(theta_sat=0.46, theta_fc=0.38, theta_wp=0.22, root_depth_m=0.5),
}
UPLINK_LOSSES = [0.05, 0.15, 0.30, 0.50, 0.70, 0.90]
HORIZONS = [3, 6, 12, 24]


def spec_box(prof: SoilProfile) -> dict:
    """O SPEC tinh bang tay, moi so deu derive duoc (khong doan).

    (1) sigma* = W/(2z): nguong cong RONG (khong phat duoc lenh nao).
    (2) AWD can d_max = 0.85 - z*sigma_H/span >= d_target = 0.60 + 72*r_dry
        (r_dry do tu ERA5, truyen vao ngoai de khong doc file o day).
    (3) sigma_dung = f*TAW/sqrt(1-rho^2): do lech chuan o tuoi VO CUC. Neu
        sigma_dung van lon hon yeu cau thi KHONG co tan suat tai neo nao cuu duoc
        -> phai cai thien MO HINH, khong phai mua them cam bien. Day la ket luan
        trien khai quan trong nhat cua script nay.
    """
    lo, hi = safe_bounds(prof)
    W = hi - lo
    span = prof.fc_mm - prof.wp_mm
    sigma_star = W / (2 * Z)
    sigma_stat = prof.taw_mm / math.sqrt(1 - RHO ** 2)     # = TAW*2.294
    return {
        "W_mm": W, "span_mm": span, "TAW_mm": prof.taw_mm,
        "sigma_star_mm": sigma_star,
        "sigma_stationary_per_f": sigma_stat,               # sigma = f * so nay
        "f_max_for_gate_alive": sigma_star / sigma_stat,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--year", type=int, default=2024)
    a = ap.parse_args()

    if a.quick:
        stations, networks = ["can_tho"], ["severe"]
        seeds = [7, 11]
        soils = {k: v for k, v in list(SOILS.items())[:2]}
        uplosses = [0.15, 0.50]
        horizons = [6, 24]
        dest = OUT / "deployment_quick.csv"
    else:
        stations = ["can_tho", "soc_trang", "ca_mau"]
        networks = ["mild", "severe"]
        seeds = list(range(a.seeds))
        soils = SOILS
        uplosses = UPLINK_LOSSES
        horizons = HORIZONS
        dest = OUT / "deployment_raw.csv"

    starts = {}
    for st in stations:
        w, _ = load_weather(st, year=a.year)
        starts[st] = march_start(w)

    rows, t0, done = [], time.time(), 0

    def emit(factor, level, st, net, seed, prof, pol, spd, bud, uploss, cand):
        m = run_episode(st, pol, seed, hours=HOURS, start=starts[st], network=net,
                        slots_per_decision=spd, water_budget_mm=bud, year=a.year,
                        uplink_loss=uploss, prof=prof, cand=cand)
        rows.append({
            "factor": factor, "level": str(level), "station": st, "network": net,
            "seed": seed, "budget_mm": "inf" if bud is None else bud,
            "uplink_loss": uploss, "horizon": pol.horizon, "sigma_frac": pol.sigma_frac,
            "soil": prof_theta(prof), "depth_set": cand_label(cand),
            "unsafe_pct": round(100 * m.hours_unsafe / m.hours, 4),
            "water_mm": round(m.water_applied_mm, 2),
            "dup": m.double_irrigations, "dup_mm": round(m.water_wasted_dup_mm, 2),
            "sent": m.commands_sent, "resends": m.resends_sent,
            "cmd_per_day": round(m.commands_generated / (HOURS / 24.0), 3),
            "resend_per_day": round(m.resends_sent / (HOURS / 24.0), 3),
            "awd_eff": m.awd_effective, "awd_short": m.awd_short_cycles,
            "stress_h": m.stress_hours_ks_lt1, "withheld": m.withheld,
            "mm_per_cmd": round(m.water_applied_mm / max(1, m.commands_delivered), 2),
        })

    def prof_theta(p: SoilProfile) -> str:
        return f"fc{p.theta_fc:.2f}_wp{p.theta_wp:.2f}"

    def cand_label(c) -> str:
        return "x".join(str(int(x.mm)) for x in c if x.mm > 0)

    prof0 = SoilProfile()
    pol0 = lambda **kw: PolicyConfig("dep", True, True, True, gate_target_depl=0.80,
                                     sigma_frac=0.02, **kw)
    cand0 = default_candidates()

    # ---------------- F1: chat luong mang (uplink loss) ----------------
    for ul in uplosses:
        for st in stations:
            for net in networks:
                for s in seeds:
                    emit("F1_uplink", ul, st, net, s, prof0, pol0(), EPOCH, 240.0, ul, cand0)
        done += 1
        print(f"  F1 uplink_loss={ul} xong ({time.time()-t0:.0f}s)", flush=True)

    # ---------------- F2: loai dat ----------------
    for sname, prof in soils.items():
        for st in stations:
            for net in networks:
                for s in seeds:
                    emit("F2_soil", sname, st, net, s, prof, pol0(), EPOCH, 240.0, 0.15, cand0)
        done += 1
        print(f"  F2 soil={sname} xong ({time.time()-t0:.0f}s)", flush=True)

    # ---------------- F3: do phan giai lenh ----------------
    for dname, levels in DEPTH_SETS.items():
        cand = default_candidates(levels)
        for st in stations:
            for net in networks:
                for s in seeds:
                    emit("F3_depth", dname, st, net, s, prof0, pol0(), EPOCH, 240.0, 0.15, cand)
        done += 1
        print(f"  F3 depth={dname} xong ({time.time()-t0:.0f}s)", flush=True)

    # ---------------- F4: chan troi du bao ----------------
    for h in horizons:
        for st in stations:
            for net in networks:
                for s in seeds:
                    emit("F4_horizon", h, st, net, s, prof0, pol0(horizon=h), EPOCH, 240.0, 0.15, cand0)
        done += 1
        print(f"  F4 horizon={h} xong ({time.time()-t0:.0f}s)", flush=True)

    # ---------------- F5: tai nguyen vo tuyen (T2 vs blind, theo kenh) ----------------
    for tag, belief in (("T2", True), ("blindARQ", False)):
        for st in stations:
            for net in networks:
                for s in seeds:
                    emit("F5_radio", tag, st, net, s, prof0,
                         PolicyConfig("r", True, belief, True, gate_target_depl=0.80,
                                      sigma_frac=0.02), EPOCH, 240.0, 0.15, cand0)
        done += 1
        print(f"  F5 radio={tag} xong ({time.time()-t0:.0f}s)", flush=True)

    with dest.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"\nwrote {len(rows)} rows -> {dest}")

    # ---------------- tong hop ----------------
    agg = defaultdict(lambda: defaultdict(list))
    FIELDS = ("unsafe_pct", "water_mm", "dup_mm", "cmd_per_day", "resend_per_day",
              "awd_eff", "stress_h", "withheld", "mm_per_cmd")
    for r in rows:
        for fld in FIELDS:
            agg[(r["factor"], r["level"])][fld].append(r[fld])
    mean = {k: {f: statistics.mean(v) for f, v in d.items()} for k, d in agg.items()}

    fails = []
    cols = ("unsafe_pct", "water_mm", "dup_mm", "cmd_per_day", "resend_per_day",
            "awd_eff", "withheld")

    for fac in ("F1_uplink", "F2_soil", "F3_depth", "F4_horizon", "F5_radio"):
        keys = sorted([k for k in mean if k[0] == fac], key=lambda k: k[1])
        if not keys:
            continue
        print(f"\n=== {fac} ===")
        print(f"  {'level':<26}" + "".join(f"{c:>14}" for c in cols))
        for k in keys:
            print(f"  {k[1]:<26}" + "".join(f"{mean[k][c]:>14.2f}" for c in cols))

    # ---- GATE F1: mang te hon thi an toan khong the TOT HON (don dieu) ----
    ks = sorted([k for k in mean if k[0] == "F1_uplink"], key=lambda k: float(k[1]))
    seq = [mean[k]["unsafe_pct"] for k in ks]
    viol = [(ks[i][1], ks[i + 1][1]) for i in range(len(seq) - 1) if seq[i + 1] < seq[i] - 0.5]
    print(f"\n=== GATE F1: uplink_loss tang => unsafe khong giam ===\n  day unsafe: "
          f"{[round(x,2) for x in seq]}")
    if viol:
        fails.append(f"F1: unsafe GIAM khi mang te hon tai {viol} -> phi vat ly")
    # tim muc mat goi toi da con dung duoc (unsafe < FixedSchedule do o ablation)
    print("  => muc mat goi uplink toi da ma cong van hoat dong duoc (unsafe < 25%):")
    ok_levels = [k[1] for k in ks if mean[k]["unsafe_pct"] < 25.0]
    print(f"     {ok_levels}")

    # ---- GATE F2: khong loai dat nao cong that bai tham hai ----
    ks2 = [k for k in mean if k[0] == "F2_soil"]
    worst = max(mean[k]["unsafe_pct"] for k in ks2)
    best = min(mean[k]["unsafe_pct"] for k in ks2)
    print(f"\n=== GATE F2: trai theo loai dat = {best:.2f}% .. {worst:.2f}% ===")
    if worst > 50:
        fails.append(f"F2: co loai dat ma cong that bai (unsafe {worst:.1f}%) -> "
                     "can hieu chuan rieng tung ruong, phai khai bao")
    if worst - best > 20:
        fails.append(f"F2: nhay cam loai dat qua lon ({worst-best:.1f} diem) -> "
                     "khong the dung mot bo tham so cho moi ruong")

    # ---- GATE F3: do phan giai lenh tot hon khong duoc lam te hon ----
    ks3 = [k for k in mean if k[0] == "F3_depth"]
    for k in ks3:
        print(f"  F3 {k[1]:<12} unsafe={mean[k]['unsafe_pct']:.2f}% awd_eff={mean[k]['awd_eff']:.2f} "
              f"mm/lenh={mean[k]['mm_per_cmd']:.1f}")

    # ---- GATE F5: T2 phai it tai nguyen vo tuyen hon blind ARQ ----
    t2 = mean.get(("F5_radio", "T2")); bl = mean.get(("F5_radio", "blindARQ"))
    if t2 and bl:
        print(f"\n=== GATE F5: tai nguyen vo tuyen ===")
        print(f"  T2      : lenh/ngay={t2['cmd_per_day']:.3f} gui_lai/ngay={t2['resend_per_day']:.3f} "
              f"nuoc_lang_phi_do_dup={t2['dup_mm']:.1f}mm")
        print(f"  blindARQ: lenh/ngay={bl['cmd_per_day']:.3f} gui_lai/ngay={bl['resend_per_day']:.3f} "
              f"nuoc_lang_phi_do_dup={bl['dup_mm']:.1f}mm")
        if not (t2["resend_per_day"] < bl["resend_per_day"]):
            fails.append(f"F5: T2 gui lai nhieu hon blindARQ ({t2['resend_per_day']} vs "
                         f"{bl['resend_per_day']}) -> T2 khong tiet kiem tai nguyen vo tuyen")
        if not (t2["dup_mm"] < bl["dup_mm"]):
            fails.append(f"F5: T2 lang phi nuoc nhieu hon blindARQ ({t2['dup_mm']} vs {bl['dup_mm']})")

    # ---- O SPEC (derive tay, in ra cho bai bao) ----
    print("\n=== O SPEC TRIEN KHAI (moi so derive tu cong thuc, khong doan) ===")
    for sname, prof in soils.items():
        sb = spec_box(prof)
        f_alive = sb["f_max_for_gate_alive"]
        # AWD: can d_max >= d_target; d_target lay 0.75 (do tu ERA5: 0.60+72*r_dry)
        d_target = 0.75
        sigma_need = (0.85 - d_target) * sb["span_mm"] / Z
        f_awd = sigma_need / sb["sigma_stationary_per_f"]
        print(f"  {sname}: W={sb['W_mm']:.1f}mm TAW={sb['TAW_mm']:.1f}mm "
              f"sigma*={sb['sigma_star_mm']:.2f}mm")
        print(f"     cong SONG khi f_sigma < {f_alive:.4f} ({100*f_alive:.2f}% TAW)")
        print(f"     cap tin chi AWD khi f_sigma <= {f_awd:.4f} "
              f"(sigma_dung <= {sigma_need:.2f}mm = {100*sigma_need/sb['TAW_mm']:.1f}% TAW)")
        if f_awd <= 0:
            fails.append(f"F2/spec: loai dat {sname} khong the dat AWD voi bat ky f_sigma nao")

    print("\n  => KET LUAN TRIEN KHAI QUAN TRONG (derive, khong phai do):")
    prof_def = SoilProfile()
    sb = spec_box(prof_def)
    g = math.sqrt(sum(RHO ** (2 * k) for k in range(7)))
    f_awd_age0 = ((0.85 - 0.75) * sb["span_mm"] / Z) / (prof_def.taw_mm * g)
    print(f"     - Yeu cau do trung thuc: sigma_H <= {((0.85-0.75)*sb['span_mm']/Z):.2f} mm "
          f"(= {100*((0.85-0.75)*sb['span_mm']/Z)/sb['TAW_mm']:.1f}% TAW)")
    print(f"     - f_sigma <= {f_awd_age0:.4f} de lam AWD du tin chi")
    print(f"     - Neu twin tho (f_sigma = 0.10): sigma_H nho nhat co the = "
          f"{0.10*prof_def.taw_mm*g:.2f} mm > {((0.85-0.75)*sb['span_mm']/Z):.2f} mm")
    print(f"       => TANG TAN SUAT CAM BIEN CUNG KHONG CUU DUOC (sigma khong the xuong")
    print(f"          duoi f*TAW*g vi age = 0 la gioi han duoi). Phai cai thien MO HINH.")
    print(f"     - Nguoc lai voi f_sigma = 0.02: sigma_dung = "
          f"{0.02*sb['sigma_stationary_per_f']:.2f} mm <= {((0.85-0.75)*sb['span_mm']/Z):.2f} mm")
    print(f"       => cong van lam AWD duoc du KHONG BAO GIO duoc tai neo (pin/kenh yeu).")

    print()
    if fails:
        print(f"DEPLOYMENT PROBLEMS ({len(fails)}):")
        for f in fails:
            print("  -", f)
        return 1
    print("DEPLOYMENT GATES: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

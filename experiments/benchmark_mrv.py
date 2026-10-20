#!/usr/bin/env python3
"""BENCHMARK: phuong phap cua bai vs cac phuong an MRV AWD DA CONG BO.

Vi sao file nay ton tai (anh Van, 2026-10-07):
  "ket qua phai chay so sanh voi benchmark, SOTA moi la minh chung de su dung duoc"
Truoc day bai chi so 4 lop phong thu CUA MINH voi nhau. Do khong phai minh chung.

BAY phuong an, cham tren CUNG mot ground truth (truth_depl tu build_truth):

  B1  Incumbent QD4801  — anh ong do muc nuoc + nong dan tu bao cao.
  B2  Sentinel-1 (6d)   — revisit 6 ngay voi chom 1A+1B. Nguon: ScienceDirect
                          S1569843222002357 "~10 m, 6-12 days revisit"; DLR elib
                          114137 "1B effectively halves the revisit time".
  B3  Sentinel-1 (12d)  — mot ve tinh, revisit 12 ngay.
  B4  IoT ong do muc    — HAL hal-03693661 (pilot DBSCL 82 nong dan, Can Tho /
                          Tra Vinh / An Giang, ong nang luong mat troi + LoRa,
                          0.1 cm moi 5 phut); Dela Cruz 2022 Water 14(24):4128.
  T0  Physics point     — ban da cong bo (mot profile, gap 5mm).
  T1  Robust Theta      — giao tren Theta.
  T2  Device anchor     — ban ghi lenh co chu ky cua gateway.

HAI CHI SO, dinh nghia sao cho phuong an nao cung do duoc nhu nhau:

  XAC NHAN (confirmation)
    Ty le pha kho THAT (depletion that >= 0.45 lien tuc >= 72h, nguong lay tu
    AWD_DEPL_FLOOR / AWD_DRY_HOURS cua fraud_detection.py) ma thiet bi CO IT NHAT
    MOT lan quan sat roi vao trong no. Pha kho 72h nam tron giua hai lan chup cach
    nhau 144h thi KHONG the xac nhan -> nong dan trung thuc khong lay duoc tin chi.
    IoT quan sat lien tuc nen dat 100% theo dinh nghia; ve tinh thi khong.

  CHI SO THU HAI: KHONG DO DUOC, VA EM KHONG BIA SO CHO NO.
  Ban dau em dinh do "mau thuan" = so gio ma depl_that khac depl_replay(log), roi
  suy ra ty le ket toi oan / phat hien gian lan cua ve tinh va IoT. Ket qua quick
  run cho Sentinel-1 va IoT deu "ket toi oan 100%" -> vo ly, va em truy ra NGUYEN
  NHAN LA PHUONG PHAP SAI, khong phai code sai:
    * depl_replay di qua TWIN MAC DINH, con depl_that sinh tu 7 truc vi pham gia
      dinh. Chenh lech giua hai cai do la REALITY GAP, khong phai gian lan.
      Dem no = dem sai so mo hinh thanh toi cua nong dan.
    * Them mot nhieu khac: MUA cung lam depletion giam, nen "ruong uot ma khong
      khai tuoi" co the chi la mua. Muon tach duoc phai dieu kien hoa luong mua,
      va luc do ket qua phu thuoc vao nguong mua ma em tu dat.
  => Bo chi so nay. Bao cao "khong do duoc" trung thuc hon la mot con so sai.
  Phan con lai (kha nang phat hien dich gio cua ve tinh/IoT) can thiet ke thi
  nghiem rieng, khong the suy ra tu harness nay.

BAN DAU em dung proxy KHAC va no SAI: suy ra "su kien tuoi that" tu viec depletion
giam >= 0.05, roi ghep loi khai vao do. Nhung MUA cung lam depletion giam, nen
proxy dem ca mua thanh tuoi -> bao Sentinel-1 "bat oan 60%", tuc BIA ra ket qua bat
loi cho doi thu. Da bo hoan toan, thay bang so sanh trang thai nhu tren.

Chay:
    python3 experiments/benchmark_mrv.py --quick
    python3 experiments/benchmark_mrv.py --seeds 10
"""
from __future__ import annotations

import argparse
import csv
import random
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

from ncs_loop import load_weather                                     # noqa: E402
from water_balance import SoilProfile                                 # noqa: E402
from fraud_detection import (AWD_DEPL_FLOOR, AWD_DRY_HOURS,            # noqa: E402
                             awd_windows, replay_log)
import reality_gap_probe as rgp                                       # noqa: E402
import robust_audit_eval as rae                                       # noqa: E402
from log_filters import (FilterConfig, RecordingNoise,                # noqa: E402
                         max_event_depth, tier1_gap_flag)

START, HOURS = rgp.START, rgp.HOURS
STATIONS = rgp.STATIONS
TWIN = SoilProfile()              # profile MAC DINH da cong bo = dung thu nguoi kiem toan dung
YEARS = (2024, 2025)
V1_GAP_MM = 5.0                   # nguong tuyet doi cua ban da cong bo
REVISIT_H = {"sentinel_1AB": 6 * 24, "sentinel_1A": 12 * 24}
SAT_OFFSET_H = 7                  # lech pha quy dao, tranh trung gio tuoi mot cach gia tao
IOT_VISIBLE = None                # IoT thay moi gio


# ------------------------------------------------------------------ ground truth
def dry_phases(truth_depl):
    """Pha kho THAT dat chuan tin chi. Nguong lay tu hang so that, khong tu dat."""
    out, a = [], None
    for h, d in enumerate(truth_depl):
        if d >= AWD_DEPL_FLOOR:
            if a is None:
                a = h
        else:
            if a is not None:
                if h - a >= AWD_DRY_HOURS:
                    out.append((a, h))
                a = None
    if a is not None and len(truth_depl) - a >= AWD_DRY_HOURS:
        out.append((a, len(truth_depl)))
    return out


def assess(truth_depl, visible):
    """Kha nang XAC NHAN pha kho that cua mot phuong an quan sat.

    Chi dung truth_depl va nhip quan sat -> khong dung cham twin, nen khong bi
    lan voi reality gap. Day la ly do em bo tham so claim_depl.

    Mot pha kho that [a,b) duoc xac nhan khi CO IT NHAT MOT lan quan sat roi vao
    trong no. Neu khong, giua hai lan quan sat la diem mu: pha kho 72h hoan toan
    co the nam tron trong khoang 144h (Sentinel-1A+1B) hoac 288h (1A).

    Tra ve (so_pha_xac_nhan, tong_so_pha_kho_that, so_gio_quan_sat).
    """
    phases = dry_phases(truth_depl)
    n = len(truth_depl)
    hours = range(n) if visible is None else sorted(visible)
    hs = set(hours)
    conf = sum(1 for a, b in phases if any(h in hs for h in range(a, b)))
    return conf, len(phases), len(hs)


# ------------------------------------------------------------------ vong chay
def run(seeds, thetas, w0set, verbose=True):
    cfg = FilterConfig()
    maxd = max_event_depth(cfg.infil.default_duration_h, cfg.infil)
    noise = RecordingNoise()
    rows, dropped = [], []
    t0 = time.time()
    for year in YEARS:
        for station in STATIONS:
            try:
                weather, day_rain = load_weather(station, limit=START + HOURS + 20,
                                                 year=year)
            except Exception as e:
                dropped.append((year, station, None, f"load_weather {type(e).__name__}"))
                continue
            for seed in range(seeds):
                rng = random.Random(7000 * year + 13 * seed + rgp.station_seed(station))
                soil = rng.choice(rgp.SOILS)
                prof_r, truth_r, honest, pumped_r, eta, thr = rgp.build_truth(
                    rng, weather, soil, rgp.CFG_REAL)
                if len(honest) < rae.MIN_CLAIMS:
                    # KHONG am tham bo. Day la phat hien: nam thua nuoc nong dan
                    # hau nhu khong phai tuoi, nen khong co nhat ky de kiem toan.
                    dropped.append((year, station, seed,
                                    f"n_claim={len(honest)} < MIN_CLAIMS={rae.MIN_CLAIMS}"))
                    continue

                forged, _ = rae.timing_attack(honest, weather, day_rain, max_depth=maxd)
                changed = int(rae._norm(forged) != rae._norm(honest))

                depl_h = replay_log(honest, weather, day_rain, TWIN, START, HOURS)[0]
                depl_f = replay_log(forged, weather, day_rain, TWIN, START, HOURS)[0]

                rec = dict(year=year, station=station, seed=seed, soil=soil[0],
                           eta=round(eta, 3), thr=round(thr, 3), changed=changed,
                           n_claim_honest=len(honest), n_claim_forged=len(forged),
                           pump_mm=round(pumped_r, 1),
                           n_truth_phase=len(dry_phases(truth_r)),
                           ndry_claim_honest=awd_windows(depl_h, honest)[0],
                           ndry_claim_forged=awd_windows(depl_f, forged)[0])

                # ---- B1 incumbent: anh + tu khai, khong co chuoi quan sat nao ----
                rec.update(b1_confirm=0, b1_confirm_tot=len(dry_phases(truth_r)),
                           b1_seen=0)

                # ---- B2/B3 ve tinh ----
                # Chi do XAC NHAN (sound: chi dung depl_that + nhip quan sat).
                # KHONG tinh "mau thuan": xem docstring, no dem reality gap thanh toi.
                for tag, rv in (("b2", REVISIT_H["sentinel_1AB"]),
                                ("b3", REVISIT_H["sentinel_1A"])):
                    vis = set(range(SAT_OFFSET_H, len(truth_r), rv))
                    ch, th, seen = assess(truth_r, vis)
                    rec.update(**{f"{tag}_confirm": ch, f"{tag}_confirm_tot": th,
                                  f"{tag}_seen": seen})

                # ---- B4 IoT (quan sat lien tuc) ----
                ch, th, seen = assess(truth_r, IOT_VISIBLE)
                rec.update(b4_confirm=ch, b4_confirm_tot=th, b4_seen=seen)

                # ---- T0/T1/T2 cua bai: goi lai ham cua harness ----
                v1h = rae.audit_v1(honest, weather, day_rain)
                v1f = rae.audit_v1(forged, weather, day_rain)
                v2h = rae.audit_v2(honest, weather, day_rain, thetas, w0set, cfg)
                v2f = rae.audit_v2(forged, weather, day_rain, thetas, w0set, cfg)
                g_h = pumped_r - sum(honest.values())
                g_f = pumped_r - sum(forged.values())
                t1_abs_h = int(abs(g_h) > V1_GAP_MM)
                t1_abs_f = int(abs(g_f) > V1_GAP_MM)
                t1_prop_h = int(tier1_gap_flag(pumped_r, sum(honest.values()),
                                              max(1, len(honest)), noise)[0])
                t1_prop_f = int(tier1_gap_flag(pumped_r, sum(forged.values()),
                                              max(1, len(forged)), noise)[0])
                rec.update(
                    t0_fa=int(bool(v1h["flag_t0"]) or bool(t1_abs_h)),
                    t0_detect=int(bool(v1f["flag_t0"]) or bool(t1_abs_f)) if changed else 0,
                    t1_fa=int(bool(v2h["flag_t0"]) or bool(t1_prop_h)),
                    t1_detect=int(bool(v2f["flag_t0"]) or bool(t1_prop_f)) if changed else 0,
                    # anchor doi chieu voi ban ghi gateway CUA CHINH RUONG NAY
                    t2_fa=int(rae.device_anchor_flag(honest, honest)),
                    t2_detect=int(rae.device_anchor_flag(forged, honest)) if changed else 0,
                    v2_f5_h=v2h["f5"], v2_f5_f=v2f["f5"],
                )
                rows.append(rec)
                if verbose:
                    print(f"  [{year} {station:<9} s{seed}] pha_kho_that={rec['n_truth_phase']} "
                          f"changed={changed} | t0={rec['t0_fa']}/{rec['t0_detect']} "
                          f"t1={rec['t1_fa']}/{rec['t1_detect']} "
                          f"t2={rec['t2_fa']}/{rec['t2_detect']} "
                          f"| sat6 xac nhan {ch}/{th} ({seen}h quan sat) "
                          f"({time.time()-t0:.0f}s)")
    return rows, dropped


def pct(a, b):
    return f"{100*a/b:5.1f}%" if b else "  n/a"


def summarize(rows, dropped):
    n = len(rows)
    ch = [r for r in rows if r["changed"]]
    tot_phase = sum(r["n_truth_phase"] for r in rows)
    print("\n" + "=" * 112)
    print(f"BANG BENCHMARK MRV — {n} nhat ky trung thuc, {len(ch)} bi dich gio that su, "
          f"{tot_phase} pha kho that")
    print("=" * 112)
    print(f"  {'phuong an':<27}{'ket toi oan':>12}{'phat hien':>11}"
          f"{'xac nhan':>10}{'chi phi':>22}")
    print(f"  {'-'*27}{'-'*12}{'-'*11}{'-'*10}{'-'*22}")

    def block(name, tag, cost, is_ours):
        """is_ours=True: lop cua bai, do duoc ca ket toi oan lan phat hien.
        is_ours=False: phuong an quan sat, chi do duoc XAC NHAN. Cot phat hien
        ghi 'khong do' vi thiet ke thi nghiem rieng (xem docstring)."""
        if is_ours:
            fa = pct(sum(r[f"{tag}_fa"] for r in rows), n)
            det = pct(sum(r[f"{tag}_detect"] for r in ch), len(ch))
            cf = "-"
        else:
            fa = det = "khong do"
            cf = pct(sum(r[f"{tag}_confirm"] for r in rows), tot_phase)
        print(f"  {name:<27}{fa:>12}{det:>11}{cf:>10}{cost:>22}")

    block("B1 QD4801 anh + tu khai", "b1", "0 (ong PVC)", False)
    block("B2 Sentinel-1 revisit 6d", "b2", "0 (ve tinh)", False)
    block("B3 Sentinel-1 revisit 12d", "b3", "0 (ve tinh)", False)
    block("B4 IoT ong do / thua", "b4", "1 thiet bi / thua", False)
    block("T0 physics point (da CB)", "t0", "0", True)
    block("T1 robust Theta", "t1", "0", True)
    block("T2 device anchor", "t2", "0 (controller)", True)

    print(f"\n  CACH DOC (moi mau so deu ghi ro de khong doc nham):")
    print(f"   * 'ket toi oan' chia cho {n} nhat ky trung thuc — chi do cho T0/T1/T2")
    print(f"   * 'phat hien'   chia cho {len(ch)} nhat ky THAT SU bi doi (cot changed=1)")
    print(f"   * 'xac nhan'    chia cho {tot_phase} pha kho that >= {AWD_DRY_HOURS}h")
    print(f"     Day la chi so QUYET DINH ve kinh te: pha kho khong xac nhan duoc")
    print(f"     thi nong dan trung thuc KHONG lay duoc tin chi, du lam dung that.")
    print(f"   * 'khong do' cho B2/B3/B4: xem docstring — moi cach do deu dem reality")
    print(f"     gap hoac mua thanh gian lan, nen em khong dua ra so.")
    print(f"   * B1 (anh + tu khai) khong co chuoi quan sat nen xac nhan = 0%")

    print(f"\n  DU LIEU BI LOAI (khong am thang — day la phat hien, khong phai nhieu):")
    by_year = {}
    for y, st, sd, why in dropped:
        by_year.setdefault(y, []).append((st, sd, why))
    for y in sorted(by_year):
        lst = by_year[y]
        print(f"   {y}: {len(lst)} to hop bi loai")
        for st, sd, why in lst[:4]:
            print(f"      {st} seed{sd}: {why}")
        if len(lst) > 4:
            print(f"      ... va {len(lst)-4} truong hop tuong tu")
    print("   Y NGHIA: nam thua nuoc nong dan hau nhu khong can tuoi -> khong co")
    print("   nhat ky de kiem toan. Moi ket luan ve TAN CONG vi the chi dung cho")
    print("   nam han. Bai viet 'across two climate years' can noi ro dieu nay.")

    pairs = [(r["ndry_claim_forged"], r["ndry_claim_honest"]) for r in ch]
    if pairs:
        a = statistics.mean(x[0] for x in pairs)
        b = statistics.mean(x[1] for x in pairs)
        d = [x[0] - x[1] for x in pairs]
        sd = statistics.stdev(d) if len(d) > 1 else 0
        se = sd / len(d) ** 0.5 if d else 0
        print(f"\n  THOI PHONG TIN CHI (ghep cap, {len(pairs)} tan cong that):")
        print(f"    {a:.2f} vs {b:.2f} pha kho = +{100*(a-b)/b:.0f}% | "
              f"chenh {statistics.mean(d):+.2f} ± se {se:.2f} | "
              f"t={statistics.mean(d)/se if se else 0:.2f}")
        print(f"    pham vi: {len(ch)}/{n} quy dao tim duoc nuoc di = {100*len(ch)/n:.0f}%")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--seeds", type=int, default=0)
    ap.add_argument("--full-theta", action="store_true")
    a = ap.parse_args()
    global seeds_used
    seeds_used = a.seeds or (2 if a.quick else 10)
    if a.full_theta:
        from log_filters import uncertainty_set
        thetas, w0set = uncertainty_set(), (0.0, 0.25, 0.50, 0.75, 0.90)
    else:
        thetas, w0set = rae.THETA_REDUCED, rae.W0_REDUCED
    print(f"=== BENCHMARK MRV: {seeds_used} seed x {len(STATIONS)} tram x {len(YEARS)} nam ===")
    print(f"    |Theta|={len(thetas)} x |w0|={len(w0set)} = {len(thetas)*len(w0set)} replay/nhat ky")
    print(f"    nguong that: AWD_DEPL_FLOOR={AWD_DEPL_FLOOR}, AWD_DRY_HOURS={AWD_DRY_HOURS}")
    print(f"    revisit: 1A+1B={REVISIT_H['sentinel_1AB']}h, 1A={REVISIT_H['sentinel_1A']}h")
    rows, dropped = run(seeds_used, thetas, w0set)
    if not rows:
        raise SystemExit(f"khong co du lieu; {len(dropped)} to hop bi loai: {dropped[:4]}")
    summarize(rows, dropped)
    p = OUT / ("benchmark_mrv_quick.csv" if (a.quick or seeds_used <= 2)
               else "benchmark_mrv.csv")
    keys = sorted({k for r in rows for k in r})
    with p.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    print(f"\n=== xuat {p.name} ({len(rows)} hang, {len(keys)} cot) ===")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""BENCHMARK XAC NHAN TIN CHI: phuong an cua bai vs cac phuong an MRV da cong bo.

Vi sao can (anh Van, 2026-10-07):
  "ket qua phai chay so sanh voi benchmark, SOTA moi la minh chung de su dung duoc"
Truoc day bai chi LAP LUAN rang ve tinh khong phan giai duoc pha kho 72h. File nay
DO dieu do, va do tren TOAN BO mau.

CHI SO DUY NHAT: XAC NHAN (confirmation)
  = ty le pha kho THAT (depletion that >= AWD_DEPL_FLOOR lien tuc >= AWD_DRY_HOURS)
    ma phuong an CO IT NHAT MOT lan quan sat roi vao trong no.
  Mot pha kho 72h nam tron giua hai lan chup cach nhau 144h thi khong the xac nhan
  -> nong dan TRUNG THUC khong lay duoc tin chi du lam dung that. Day la chi so
  quyet dinh ve kinh te, va no doc lap hoan toan voi chat luong detector.

VI SAO FILE NAY RIENG, KHONG NAM TRONG benchmark_mrv.py:
  benchmark_mrv.py bo nhat ky co <3 lenh (khong the tan cong duoc), nen chi con
  23/60 trajectory. Bo loc do gay THIENT LECH cho cot bat oan (60.9% thay vi
  26.7%), vi nhom bi bo hau nhu khong bi bat oan (1/9).
  Nhung cot XAC NHAN khong dung nhat ky nao ca — chi dung truth_depl va nhip quan
  sat — nen no KHONG bi thien lech va phai tinh tren TAT CA 60 trajectory.
  => tach ra de dung mau day du, va de khong ai nham hai mau so voi nhau.

EM TU BO MOT CHI SO (ghi lai de khong tai dien):
  Ban dau em dinh them cot "mau thuan" = so gio ma trang thai ruong that khac
  trang thai loi khai ngu y, de suy ra ty le bat oan cua ve tinh/IoT. Quick run ra
  "Sentinel-1 bat oan 100%" -> vo ly. Nguyen nhan la PHUONG PHAP SAI:
    * loi khai duoc replay qua TWIN MAC DINH, con su that sinh tu 7 truc vi pham
      gia dinh -> chenh lech la REALITY GAP, khong phai gian lan. Dem no = dem
      sai so mo hinh thanh toi cua nong dan.
    * MUA cung lam depletion giam, nen "ruong uot ma khong khai tuoi" co the chi
      la mua; tach duoc phai chon nguong mua tu dat.
  Bao cao "khong do duoc" trung thuc hon mot con so sai.

Chay:
    python3 experiments/benchmark_confirmation.py            # 10 seed x 3 tram x 2 nam
    python3 experiments/benchmark_confirmation.py --seeds 20 # mau lon hon
"""
from __future__ import annotations

import argparse
import csv
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

from ncs_loop import load_weather                          # noqa: E402
from fraud_detection import AWD_DEPL_FLOOR, AWD_DRY_HOURS   # noqa: E402
import reality_gap_probe as rgp                            # noqa: E402

START, HOURS = rgp.START, rgp.HOURS
STATIONS = rgp.STATIONS
YEARS = (2024, 2025)
SAT_OFFSET_H = 7            # lech pha quy dao, tranh trung gio tuoi mot cach gia tao

# Nhip quan sat that, theo nguon da verify Crossref (xem make_table_benchmark.py):
#   hashemi2022s1 (10.1016/j.jag.2022.103047): "10 m ... 6-12 days revisit"
#   clauss2017s1  (10.1080/01431161.2017.1404162): 1A revisit 12 ngay, 1B halved
#   delacruz2022  (10.3390/w14244128): ong do muc nuoc, 0.1 cm, LoRa
# (tag, ten, chu ky gio, nguon cite, thiet bi/thua)
# TAG PHAI TUONG MINH. Ban dau em sinh tag tu nhan bang
# `label.split()[0].lower().replace("-","")[:8]`, va no VA CHAM:
#   "Sentinel-1A+1B ..." -> "sentinel"
#   "Sentinel-1A alone..." -> "sentinel"
# Hai dong ghi de cung cot `conf_sentinel`, nen bang in ra 90/150 = 60% cho CA HAI
# va con so cua ban 6 ngay (15 lan quan sat) CHUA TUNG DUOC DO. Dau hieu nhan ra:
# hai dong giong het nhau ca cot 'lan quan sat' = 8, trong khi 2160/144 = 15.
CADENCES = [
    ("photo",   "Photo + self-report (current practice)", None,    "qd4801",       "0 (PVC tube)"),
    ("s1ab",    "Sentinel-1A+1B (6-day revisit)",          6 * 24, "hashemi2022s1", "0"),
    ("s1a",     "Sentinel-1A alone (12-day revisit)",     12 * 24, "clauss2017s1",  "0"),
    ("iot",     "Continuous water-level tube (IoT)",           1,  "delacruz2022",  "1 per plot"),
    ("anchor",  "Signed command record (this work)",           1,  "twingate2026",  "0 (controller)"),
]

# GATE: tag khong duoc trung. Thieu gate nay thi bug tren da lot qua im lang.
_tags = [c[0] for c in CADENCES]
assert len(_tags) == len(set(_tags)), f"tag trung lap: {_tags}"


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


def confirmable(phases, period_h):
    """So pha kho ma mot nhip quan sat period_h co the xac nhan.

    period_h = None -> khong co chuoi quan sat nao (anh chup dinh ky + tu khai
    khong tao ra du lieu co the doi chieu voi pha kho), nen xac nhan = 0.
    """
    if period_h is None:
        return 0, 0
    hours = set(range(SAT_OFFSET_H, HOURS, period_h))
    return sum(1 for a, b in phases if any(a <= h < b for h in hours)), len(hours)


def run(seeds, verbose=True):
    rows, skipped = [], 0
    for year in YEARS:
        for station in STATIONS:
            try:
                weather, _dr = load_weather(station, limit=START + HOURS + 20, year=year)
            except Exception:
                skipped += seeds
                continue
            for seed in range(seeds):
                rng = random.Random(7000 * year + 13 * seed + rgp.station_seed(station))
                soil = rng.choice(rgp.SOILS)
                # CHI can truth_depl. KHONG loc theo MIN_CLAIMS: cot xac nhan khong
                # dung nhat ky, nen loc do chi lam mat mau mot cach vo ich.
                _prof, truth, rec, _pump, _eta, _thr = rgp.build_truth(
                    rng, weather, soil, rgp.CFG_REAL)
                ph = dry_phases(truth)
                row = dict(year=year, station=station, seed=seed, soil=soil[0],
                           n_claims=len(rec), n_phase=len(ph),
                           total_dry_h=sum(b - a for a, b in ph))
                for tag, _label, period, _cite, _cost in CADENCES:
                    c, seen = confirmable(ph, period)
                    row[f"conf_{tag}"] = c
                    row[f"seen_{tag}"] = seen
                rows.append(row)
                if verbose and (year, station, seed) in (
                        (2024, STATIONS[0], 0), (2025, STATIONS[0], 0)):
                    print(f"  [{year} {station} s{seed}] {len(ph)} pha kho that, "
                          f"{row['total_dry_h']}h kho, n_claims={len(rec)}")
    return rows, skipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=10)
    a = ap.parse_args()

    print(f"=== BENCHMARK XAC NHAN: {a.seeds} seed x {len(STATIONS)} tram x "
          f"{len(YEARS)} nam = {a.seeds*len(STATIONS)*len(YEARS)} trajectory ===")
    print(f"    nguong that: depletion >= {AWD_DEPL_FLOOR} lien tuc >= "
          f"{AWD_DRY_HOURS}h (tu fraud_detection.py)")
    rows, skipped = run(a.seeds)
    if not rows:
        raise SystemExit("khong co du lieu")

    tot_phase = sum(r["n_phase"] for r in rows)
    tot_dry_h = sum(r["total_dry_h"] for r in rows)
    zero = sum(1 for r in rows if r["n_phase"] == 0)
    print(f"\n    {len(rows)} trajectory | {tot_phase} pha kho that | "
          f"{tot_dry_h} gio kho | {zero} trajectory khong co pha kho dat chuan")
    print(f"    trung binh {tot_phase/len(rows):.2f} pha kho/trajectory")

    print(f"\n{'='*104}")
    print(f"BANG BENCHMARK — kha nang XAC NHAN pha kho de cap tin chi "
          f"({len(rows)} trajectory, {tot_phase} pha kho that)")
    print(f"{'='*104}")
    print(f"  {'phuong an':<40}{'xac nhan':>12}{'ty le':>9}{'lan quan sat':>14}"
          f"{'thiet bi':>16}")
    print(f"  {'-'*40}{'-'*12}{'-'*9}{'-'*14}{'-'*16}")
    for tag, label, period, cite, cost in CADENCES:
        c = sum(r[f"conf_{tag}"] for r in rows)
        seen = sum(r[f"seen_{tag}"] for r in rows)
        obs = "---" if not seen else f"{seen//len(rows)}"
        print(f"  {label:<40}{f'{c}/{tot_phase}':>12}{100*c/tot_phase:>8.0f}%"
              f"{obs:>14}{cost:>16}")

    print(f"\n  Cach doc:")
    print(f"   * 'xac nhan' = so pha kho THAT (>= {AWD_DRY_HOURS}h) ma phuong an co it"
          f" nhat mot lan quan sat roi vao. Pha kho nam tron giua hai lan quan sat"
          f" thi KHONG the xac nhan, du nong dan lam dung that.")
    print(f"   * 'lan quan sat' = so lan quan sat moi trajectory trong 90 ngay "
          f"({HOURS}h). Anh + tu khai khong co chuoi quan sat nao nen '---'.")
    print(f"   * IoT va ban ghi lenh deu quan sat lien tuc theo gio. Can bang nuoc"
          f" tinh theo gio nen quan sat mau hon 1h khong them thong tin cho phan"
          f" tich nay; do la ly do hai dong cuoi giong nhau o cot nay, KHONG phai"
          f" hai phuong an tuong duong — chung khac nhau ve chi phi va ve kha nang"
          f" phat hien gian lan (xem benchmark_mrv.py va tab_defence).")
    print(f"   * {skipped} trajectory bi bo vi khong nap duoc thoi tiet.")

    # ghi CSV
    p = OUT / "benchmark_confirmation.csv"
    keys = sorted({k for r in rows for k in r})
    with p.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    print(f"\n=== xuat {p.name} ({len(rows)} hang, {len(keys)} cot) ===")

    # tom tat cho bang LaTeX
    summ = []
    for tag, label, period, cite, cost in CADENCES:
        c = sum(r[f"conf_{tag}"] for r in rows)
        seen = sum(r[f"seen_{tag}"] for r in rows)
        summ.append(dict(tag=tag, label=label, cite=cite, cost=cost, confirm=c,
                         total=tot_phase, pct=round(100 * c / tot_phase),
                         obs=(seen // len(rows)) if seen else 0, n_traj=len(rows)))

    # GATE: hai nhip quan sat KHAC nhau thi ket qua phai KHAC nhau.
    # Day la phep thu phat hien dung loai bug vua roi: neu hai dong ra giong het
    # nhau thi hoac tag va cham, hoac code quan sat sai.
    ab = next(x for x in summ if x["tag"] == "s1ab")
    a1 = next(x for x in summ if x["tag"] == "s1a")
    assert (ab["confirm"], ab["obs"]) != (a1["confirm"], a1["obs"]), (
        f"Sentinel 6 ngay va 12 ngay cho KET QUA GIONG HET NHAU "
        f"({ab['confirm']}/{ab['obs']}) -> tag va cham hoac code quan sat sai")
    (OUT / "_benchmark_summary.json").write_text(
        __import__("json").dumps(dict(rows=summ, n_traj=len(rows), tot_phase=tot_phase,
                                      zero_phase=zero,
                                      mean_phase=round(tot_phase / len(rows), 2)),
                                 indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"=== xuat _benchmark_summary.json ({len(summ)} phuong an) ===")


if __name__ == "__main__":
    main()

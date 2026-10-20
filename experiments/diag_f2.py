#!/usr/bin/env python3
"""Chan doan: V2 co the kich hoat tren lua mua kho DBSCL khong?

BAI TOAN: depletion_fraction() clip ve [0,1] nen nguong DEPL_IMPOSSIBLE=1.02 cua
ban v1 bat kha thi -> V2 fire 0/281. Da sua bang depletion_raw(). Nhung sua roi
van phai hoi: tren ERA5 THAT, ruong lua mua kho co bao gio xuong duoi diem heo
khong? Neu khong, V2 la bo loc AN TOAN (khong bao gio ket toi oan) chu khong phai
bang chung phat hien gian lan — va bai bao phai noi dung nhu vay thay vi quang cao
"ba bo loc".

Do hai dai luong, voi nhat ky TRONG (tinh huong kho nhat co the: khong co nuoc bu):
  * depletion CLIP lon nhat  -> so voi 1.00 (nguong V2)
  * depletion RAW lon nhat   -> so voi 1.00; vuot 1.00 la ruong xuong duoi diem heo
  * so gio V2 fire           -> 0 nghia la khong the kich hoat

Chay:
    python3 experiments/diag_f2.py            # 3 tram x 2 nam
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

from ncs_loop import load_weather                              # noqa: E402
from water_balance import (BucketState, SoilProfile, daily_runoff_share,  # noqa: E402
                           depletion_fraction)
from log_filters import (SOIL_SET, FilterConfig, Theta, depletion_raw,  # noqa: E402
                         kc_value, replay_theta)
from water_balance import stress_coefficient                   # noqa: E402

START = 74 * 24
HOURS = 2160
STATIONS = ("can_tho", "soc_trang", "ca_mau")


def probe(station: str, year: int) -> dict:
    """Quet toan bo (dat x che do Kc x w0) voi nhat ky TRONG, lay cuc dai."""
    weather, day_rain = load_weather(station, limit=START + HOURS + 20, year=year)
    cfg = FilterConfig()
    max_clip = 0.0
    max_raw = 0.0
    f2_hits = 0
    n_conf = 0
    worst = ""
    for name, fc, wp in SOIL_SET:
        th = Theta(name, fc, wp, "stage", 1.0)   # Kc theo giai doan = nhieu nuoc nhat
        prof = th.profile()
        for w0 in (0.0, 0.25, 0.50, 0.75, 0.90):
            n_conf += 1
            # replay de lay depletion clip va so lan V2 fire
            depls, v = replay_theta({}, weather, day_rain, th, START, HOURS, cfg,
                                    w0_depl=w0)
            f2_hits += v.f2
            # depletion RAW: chay lai bucket de lay w that (khong clip)
            st = BucketState(w=prof.fc_mm - w0 * (prof.fc_mm - prof.wp_mm))
            for h in range(HOURS):
                i = START + h
                if i >= len(weather):
                    break
                r = weather[i]
                ro = daily_runoff_share(day_rain.get(r["time"][:10], 0.0), r["p"],
                                        prof.cn_runoff)
                ks = stress_coefficient(st, prof)
                kc = kc_value("stage", h / 24.0)
                w = st.w + max(0.0, r["p"] - ro) - ks * kc * r["et0"]
                st = BucketState(w=min(w, prof.fc_mm))
                raw = depletion_raw(st.w, prof)
                if raw > max_raw:
                    max_raw = raw
                    worst = f"{name}/w0={w0}"
            if depls:
                max_clip = max(max_clip, max(depls))
    return {"station": station, "year": str(year),
            "max_clipped_depl": round(max_clip, 4),
            "max_raw_depl": round(max_raw, 4),
            "f2_hits_dry_log": f2_hits,
            "n_configs": n_conf,
            "worst_config": worst}


def main() -> int:
    rows = [probe(st, yr) for st in STATIONS for yr in (2024, 2025)]
    OUT.mkdir(exist_ok=True)
    p = OUT / "f2_reachability.csv"
    with p.open("w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(rows[0]))
        wr.writeheader(); wr.writerows(rows)

    print(f"{'tram':<12}{'nam':>6}{'clip max':>10}{'raw max':>10}{'V2 fire':>9}"
          f"{'  config'}")
    for r in rows:
        print(f"{r['station']:<12}{r['year']:>6}{r['max_clipped_depl']:>10.4f}"
              f"{r['max_raw_depl']:>10.4f}{r['f2_hits_dry_log']:>9}"
              f"  {r['worst_config']}")

    clip_max = max(r["max_clipped_depl"] for r in rows)
    raw_max = max(r["max_raw_depl"] for r in rows)
    hits = sum(r["f2_hits_dry_log"] for r in rows)
    print(f"\n  depletion CLIP lon nhat tren moi tram/nam/dat/w0: {clip_max:.4f}")
    print(f"  depletion RAW  lon nhat: {raw_max:.4f} (nguong V2 = 1.00)")
    print(f"  V2 fire tong: {hits} lan / {sum(r['n_configs'] for r in rows)} cau hinh")
    print()
    if hits == 0 and raw_max <= 1.0:
        print("  KET LUAN: ruong lua mua kho DBSCL KHONG BAO GIO xuong duoi diem heo.")
        print("  V2 sau khi sua van la bo loc AN TOAN, khong phai bang chung phat hien.")
        print("  Bai bao phai noi 'hai bo loc hoat dong + mot bo loc an toan',")
        print("  KHONG duoc noi 'ba bo loc phat hien gian lan'.")
    elif hits == 0 and raw_max > 1.0:
        print("  canh bao: raw vuot 1.0 nhung V2 van 0 fire -> kiem tra f2_min_hours")
    else:
        print(f"  V2 co kich hoat duoc ({hits} lan) -> co the noi 'ba bo loc'")
    print(f"\n  -> {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

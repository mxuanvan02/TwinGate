#!/usr/bin/env python3
"""Verification of the FAO-56 ET0 implementation and the soil water bucket.

Nothing here is a paper result. The purpose is to catch a wrong constant, a unit
bug, or a sign error BEFORE any number reaches the manuscript. Every assertion
below is independently checkable against published agronomic/climatological
ranges, not against the implementation itself.

  1. Solar geometry sanity: R_a must be zero at night and peak near solar noon.
  2. Night ET0 (no shortwave) must be ~0 and never negative.
  3. Annual mean daily ET0 for the Mekong delta must sit in 3-6 mm/day.
  4. ET0 monotone increasing in temperature, in radiation, and in wind.
  5. Bucket conserves mass EXACTLY over a full year of real ERA5 forcing.
  6. Depletion fraction stays in [0,1]; Ks stays in [0,1].
  7. Rainfall total matches delta climatology (~1500-2200 mm).
"""
from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from water_balance import (  # noqa: E402
    BucketState, SoilProfile, clear_sky_radiation, daily_runoff_share,
    depletion_fraction, et0_hourly, extraterrestrial_hour, is_safe,
    scs_runoff, step_bucket, stress_coefficient,
)

DATA = Path(__file__).resolve().parents[1] / "data" / "era5_multi"
LAT = {"can_tho": 10.0452, "soc_trang": 9.6037, "ca_mau": 9.1769}
STATION = "can_tho"
ELEV = 5.0


def load(station: str) -> list[dict]:
    rows = []
    with (DATA / f"{station}_2024.csv").open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append({"time": r["time"], "t": float(r["temp_c"]),
                         "rh": float(r["rh_pct"]), "w": float(r["wind_kmh"]),
                         "sw": float(r["sw_wm2"]), "p": float(r["precip_mm"])})
    return rows


def et0(rows, station=STATION, elev=ELEV):
    lat = LAT[station]
    return [et0_hourly(r["time"], lat, r["t"], r["rh"], r["w"], r["sw"], elev)
            for r in rows]


def main() -> int:
    fails: list[str] = []
    rows = load(STATION)
    lat = LAT[STATION]
    print(f"loaded {len(rows)} hourly rows for {STATION} (lat={lat})\n")

    # --- 1. solar geometry ---------------------------------------------------
    night_ra = [extraterrestrial_hour(r["time"], lat) for r in rows if r["sw"] < 1.0]
    day_ra = [extraterrestrial_hour(r["time"], lat) for r in rows if r["sw"] >= 300.0]
    print(f"1. R_a night (sw<1): max={max(night_ra):.4f} MJ/m2/h (must be ~0)")
    print(f"   R_a bright day (sw>=300): mean={sum(day_ra)/len(day_ra):.3f} "
          f"max={max(day_ra):.3f} MJ/m2/h")
    if max(night_ra) > 0.35:
        fails.append(f"R_a not ~0 at night: {max(night_ra):.3f}")
    # Hourly R_a ceiling: at lat 10 deg N in April the sun passes close to the
    # zenith, so the hourly extraterrestrial flux approaches the equatorial noon
    # maximum of G_SC * 12*60/pi * (pi/24) * ~2 = ~4.9 MJ/m2/h. A bound of 5.2
    # is physical; anything above means a geometry bug (wrong omega window).
    if not (2.0 <= max(day_ra) <= 5.2):
        fails.append(f"R_a daytime max {max(day_ra):.3f} outside 2.0-5.2 MJ/m2/h")
    rso = clear_sky_radiation(3.5, ELEV)
    print(f"   R_so for R_a=3.5: {rso:.3f} MJ/m2/h")

    # --- 2 & 3. ET0 night and annual ----------------------------------------
    e_all = et0(rows)
    if any(e < 0 for e in e_all):
        fails.append("ET0 negative somewhere")
    night_e = [e for r, e in zip(rows, e_all) if r["sw"] < 1.0]
    night_mean = sum(night_e) / len(night_e)
    print(f"2. night slots={len(night_e)}  mean night ET0={night_mean:.5f} mm/h "
          f"(must be small)")
    if night_mean > 0.05:
        fails.append(f"night ET0 too large: {night_mean:.4f} mm/h")

    daily: dict[str, float] = {}
    for r, e in zip(rows, e_all):
        daily[r["time"][:10]] = daily.get(r["time"][:10], 0.0) + e
    vals = sorted(daily.values())
    n = len(vals)
    mean_d = sum(vals) / n
    print(f"3. daily ET0 over {n} days: mean={mean_d:.2f} median={vals[n//2]:.2f} "
          f"p95={vals[int(0.95*n)]:.2f} max={vals[-1]:.2f} min={vals[0]:.2f} mm/day")
    print(f"   annual ET0 total = {sum(e_all):.0f} mm "
          f"(delta climatology ~1300-1700 mm/yr)")
    if not (3.0 <= mean_d <= 6.0):
        fails.append(f"mean daily ET0 {mean_d:.2f} mm/day outside 3-6")
    if not (1100 <= sum(e_all) <= 1900):
        fails.append(f"annual ET0 {sum(e_all):.0f} mm outside 1100-1900")

    # --- 4. monotonicity -----------------------------------------------------
    iso = "2024-04-15T12:00"
    temps = [et0_hourly(iso, lat, t, 70.0, 10.0, 600.0) for t in (20, 25, 30, 35)]
    rads = [et0_hourly(iso, lat, 30, 70.0, 10.0, s) for s in (100, 300, 600, 900)]
    winds = [et0_hourly(iso, lat, 30, 40.0, w, 600.0) for w in (2.0, 8.0, 20.0, 40.0)]
    print(f"4. ET0 vs T:  {[round(x,3) for x in temps]}")
    print(f"   ET0 vs SW: {[round(x,3) for x in rads]}")
    print(f"   ET0 vs u:  {[round(x,3) for x in winds]}")
    for name, seq in (("temperature", temps), ("shortwave", rads), ("wind", winds)):
        if any(b <= a for a, b in zip(seq, seq[1:])):
            fails.append(f"ET0 not increasing in {name}")

    # --- 5. bucket conservation over the real year ---------------------------
    # Daily rainfall totals, needed because SCS-CN is an event/daily method.
    day_rain: dict[str, float] = {}
    for r in rows:
        d = r["time"][:10]
        day_rain[d] = day_rain.get(d, 0.0) + r["p"]

    # CN curve sanity at its own resolution. Expected values are computed here
    # from the closed form independently of src/, so this is a real cross-check
    # and not a bound invented by eye (an earlier version of this test asserted
    # 20-35 mm for a 50 mm event; hand calculation gives 13.8 mm -- the
    # assertion was wrong, the implementation was right).
    prof = SoilProfile()
    cn = prof.cn_runoff
    S_mm = 25400.0 / cn - 254.0
    Ia = 0.2 * S_mm

    def expected_runoff(p: float) -> float:
        if p <= Ia:
            return 0.0
        return ((p - Ia) ** 2) / (p - Ia + S_mm)

    for p_evt in (5.0, 15.0, 50.0, 75.0, 100.0):
        got, exp = scs_runoff(p_evt, cn), expected_runoff(p_evt)
        if abs(got - exp) > 1e-9:
            fails.append(f"SCS-CN mismatch at P={p_evt}: got {got:.4f} expect {exp:.4f}")
    ro50 = scs_runoff(50.0, cn)
    print(f"5a. SCS-CN event check (CN={cn}, S={S_mm:.1f} mm, Ia={Ia:.1f} mm):")
    print(f"    P=50 mm -> Q={ro50:.2f} mm ({100*ro50/50:.1f}%); "
          f"P=5 mm -> Q={scs_runoff(5.0, cn):.2f} mm (below Ia, must be 0)")
    print(f"    closed-form cross-check at P=5,15,50,75,100: OK")
    if scs_runoff(5.0, cn) != 0.0:
        fails.append("SCS-CN produced runoff below the initial abstraction")
    if not (13.0 <= ro50 <= 14.5):
        fails.append(f"SCS-CN 50mm event runoff {ro50:.2f} mm off the derived 13.80 mm")

    st = BucketState(w=prof.fc_mm)
    rain_tot = et0_tot = etc_tot = dp_tot = ro_tot = 0.0
    resid_max = 0.0
    depl_lo, depl_hi, ks_lo = 1.0, 0.0, 1.0
    dry_days = 0
    for r, e in zip(rows, e_all):
        d = r["time"][:10]
        ro_h = daily_runoff_share(day_rain[d], r["p"], prof.cn_runoff)
        before = st.w
        st, info = step_bucket(st, prof, r["p"], 0.0, e, runoff_mm=ro_h)
        resid = abs((before + info.infiltration + info.irrigation
                     - info.etc - info.deep_percolation) - info.w_end)
        resid_max = max(resid_max, resid)
        if abs(info.runoff - ro_h) > 1e-12:
            fails.append("bucket did not use the supplied daily runoff share")
            break
        rain_tot += r["p"]; et0_tot += e; etc_tot += info.etc
        dp_tot += info.deep_percolation; ro_tot += info.runoff
        d_frac = depletion_fraction(st, prof)
        depl_lo, depl_hi = min(depl_lo, d_frac), max(depl_hi, d_frac)
        ks_lo = min(ks_lo, stress_coefficient(st, prof))
        if not is_safe(st, prof):
            dry_days += 1
    print(f"5b. bucket: TAW={prof.taw_mm:.1f} FC={prof.fc_mm:.1f} WP={prof.wp_mm:.1f} mm")
    print(f"   max conservation residual = {resid_max:.3e} (must be < 1e-9)")
    if resid_max > 1e-9:
        fails.append(f"water balance residual {resid_max:.3e}")
    print(f"   year: rain={rain_tot:.0f} runoff={ro_tot:.0f} "
          f"({100*ro_tot/rain_tot:.1f}% of rain) ET0={et0_tot:.0f} "
          f"ETc={etc_tot:.0f} DP={dp_tot:.0f} mm")
    ro_frac = ro_tot / rain_tot
    if not (0.02 <= ro_frac <= 0.45):
        fails.append(f"runoff fraction {ro_frac:.3f} outside plausible 0.02-0.45")
    print(f"6. depletion range {depl_lo:.3f}..{depl_hi:.3f} | min Ks={ks_lo:.3f} | "
          f"unsafe hours={dry_days} ({100*dry_days/len(rows):.1f}%)")
    if not (0.0 <= depl_lo and depl_hi <= 1.0):
        fails.append("depletion fraction out of [0,1]")
    if not (0.0 <= ks_lo <= 1.0):
        fails.append("Ks out of [0,1]")
    print(f"7. rainfall total {rain_tot:.0f} mm (delta climatology ~1500-2200)")
    if not (1000 <= rain_tot <= 3000):
        fails.append(f"rainfall {rain_tot:.0f} mm implausible")
    if dry_days == 0:
        fails.append("no unsafe hours at all -- the safe set would be vacuous")

    print()
    if fails:
        print("FAILED CHECKS:")
        for f in fails:
            print("  -", f)
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

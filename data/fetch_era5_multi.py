#!/usr/bin/env python3
"""Fetch real ERA5 hourly weather for the K1 (TwinGate) irrigation study.

K1 needs a FIELD WATER BALANCE (FAO-56 style), which requires more than the
temperature-only series cached by the RABS reproduction. This script pulls the
five variables the FAO-56 reference evapotranspiration needs, plus rainfall:

    temperature_2m        [deg C]
    relative_humidity_2m  [%]
    wind_speed_10m        [km/h]
    shortwave_radiation   [W/m2]
    precipitation         [mm]

Source: Open-Meteo historical weather API, which serves the ERA5 reanalysis.
No API key. Deterministic: the same (lat, lon, year) always returns the same
ERA5 grid series, so the whole pipeline is reproducible without credentials.

Station coordinates are copied verbatim from the RABS reproduction fetch script
(/home/hitokiri/rabs_repro_20260702_112319/data/fetch_era5_vn.py) so that this
study and the two published papers share one definition of "Mekong delta zone".

Usage:
    python3 data/fetch_era5_multi.py                    # all stations, YEAR below
    python3 data/fetch_era5_multi.py can_tho            # one station
    python3 data/fetch_era5_multi.py --year 2025 can_tho soc_trang ca_mau
"""
from __future__ import annotations

import csv
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent / "era5_multi"
OUT.mkdir(parents=True, exist_ok=True)

# Coordinates identical to the RABS reproduction script (same zones, same names).
STATIONS = {
    "can_tho":    (10.0452, 105.7469),
    "soc_trang":  (9.6037, 105.9739),
    "ca_mau":     (9.1769, 105.1524),
    "long_xuyen": (10.3860, 105.4381),
    "rach_gia":   (10.0125, 105.0808),
    "my_tho":     (10.3600, 106.3600),
    "ben_tre":    (10.2415, 106.3759),
    "vinh_long":  (10.2537, 105.9722),
    "tra_vinh":   (9.9347, 106.3453),
    "cao_lanh":   (10.4593, 105.6329),
}
YEAR = 2024
BASE = "https://archive-api.open-meteo.com/v1/archive"
VARS = ["temperature_2m", "relative_humidity_2m", "wind_speed_10m",
        "shortwave_radiation", "precipitation"]
COLUMNS = ["time", "temp_c", "rh_pct", "wind_kmh", "sw_wm2", "precip_mm"]


def fetch(lat: float, lon: float, year: int) -> list[dict]:
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": f"{year}-01-01",
        "end_date": f"{year}-12-31",
        "hourly": ",".join(VARS),
        "timezone": "Asia/Ho_Chi_Minh",
    }
    url = BASE + "?" + urllib.parse.urlencode(params)
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "twingate-data/1.0"})
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception as exc:  # transient network/API errors
            if attempt == 3:
                raise SystemExit(f"FAILED {lat},{lon}: {type(exc).__name__}: {exc}")
            time.sleep(5 * (attempt + 1))
    raise AssertionError("unreachable")


def validate(payload: dict, name: str) -> list[list]:
    hourly = payload.get("hourly") or {}
    missing = [v for v in ["time", *VARS] if v not in hourly]
    if missing:
        raise SystemExit(f"{name}: API returned no column(s) {missing}; keys={list(hourly)}")
    n = len(hourly["time"])
    rows = []
    nulls = {v: 0 for v in VARS}
    for i in range(n):
        rec = [hourly["time"][i]]
        for v in VARS:
            x = hourly[v][i]
            if x is None:
                nulls[v] += 1
            rec.append("" if x is None else x)
        rows.append(rec)
    print(f"  {name}: {n} hourly rows | nulls per var: {nulls}")
    if n < 8000:
        raise SystemExit(f"{name}: only {n} rows for a full year -- refusing to write partial data")
    return rows


def main() -> None:
    argv = sys.argv[1:]
    year = YEAR
    if argv and argv[0] == "--year":
        year = int(argv[1])
        argv = argv[2:]
    wanted = argv or list(STATIONS)
    unknown = [w for w in wanted if w not in STATIONS]
    if unknown:
        raise SystemExit(f"unknown station(s) {unknown}; known: {sorted(STATIONS)}")
    for name in wanted:
        lat, lon = STATIONS[name]
        dest = OUT / f"{name}_{year}.csv"
        print(f"fetching {name} ({lat}, {lon}) year={year} ...")
        payload = fetch(lat, lon, year)
        rows = validate(payload, name)
        with dest.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(COLUMNS)
            w.writerows(rows)
        # provenance: record exactly what was asked for
        (OUT / f"{name}_{year}.provenance.json").write_text(
            json.dumps({
                "station": name, "latitude": lat, "longitude": lon, "year": year,
                "api": BASE, "hourly_vars": VARS, "timezone": payload.get("timezone"),
                "elevation_m": payload.get("elevation"),
                "rows": len(rows),
                "reanalysis": "ERA5 via Open-Meteo historical weather API (no key)",
                "coordinate_source": "identical to RABS reproduction fetch_era5_vn.py",
            }, indent=2), encoding="utf-8")
        time.sleep(1.0)
    print(f"\nwrote -> {OUT}")


if __name__ == "__main__":
    main()

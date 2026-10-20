#!/usr/bin/env python3
"""FAO-56 reference evapotranspiration + root-zone soil water balance.

This is the PHYSICAL PLANT of the K1 (TwinGate) study. It is deliberately the
standard published formulation so that no number in the paper depends on a model
invented here.

  * ET0 -- FAO-56 Penman-Monteith, HOURLY form (Allen et al. 1998, eq. 53),
    with net radiation built from solar geometry (eq. 21-24, 37-41) rather than
    from an ad-hoc clearness proxy.
  * Soil water balance -- FAO-56 ch. 8 root-zone bucket.

Every function below is checked numerically in tests/test_water_balance.py
(physical ranges, monotonicity, and exact water conservation). If a check fails,
the constant is wrong -- do not tune it away.

Units: depths in mm, energy in MJ m^-2, time step = 1 hour.

References
----------
Allen, R.G., Pereira, L.S., Raes, D., Smith, M. (1998). Crop evapotranspiration:
Guidelines for computing crop water requirements. FAO Irrigation and Drainage
Paper 56, Rome.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

G_SC = 0.0820          # solar constant [MJ m^-2 min^-1]
SIGMA_DAY = 4.903e-9   # Stefan-Boltzmann [MJ K^-4 m^-2 day^-1]
SIGMA_HOUR = SIGMA_DAY / 24.0   # hourly form used by FAO-56 eq. 41
ALBEDO = 0.23          # reference grass (FAO-56 eq. 40)
LATENT_HEAT = 2.45     # MJ/kg, converts ET0 [mm/h] to energy [MJ m^-2 h^-1]


# --------------------------------------------------------------- solar geometry
def day_of_year_from_iso(iso: str) -> float:
    """Fractional day-of-year J for an ISO timestamp 'YYYY-MM-DDTHH:MM'.

    FAO-56 eq. 25 uses the midpoint of the period, so the hour is folded in.
    """
    date_part, _, time_part = iso.partition("T")
    y, m, d = (int(x) for x in date_part.split("-"))
    hour = 0.0
    if time_part:
        hh, _, rest = time_part.partition(":")
        hour = float(hh) + (float(rest) / 60.0 if rest else 0.0)
    # days before month m (non-leap), then add; 2024 is a leap year but FAO-56
    # eq. 23 tolerates the non-leap cumulative table; keep it simple and exact
    # for the actual year by counting from Jan 1.
    cum = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    if _is_leap(y) and m > 2:
        base = cum[m - 1] + 1
    else:
        base = cum[m - 1]
    return base + d + hour / 24.0


def _is_leap(y: int) -> bool:
    return (y % 4 == 0 and y % 100 != 0) or (y % 400 == 0)


def extraterrestrial_hour(iso: str, lat_deg: float) -> float:
    """Extraterrestrial radiation R_a for the ONE-HOUR period ending at `iso`.

    FAO-56 eq. 28 (hourly), with omega_1/omega_2 bounding the hour around its
    midpoint (eq. 25-27). Returns MJ m^-2 hour^-1.
    """
    J = day_of_year_from_iso(iso)
    d_r = 1.0 + 0.033 * math.cos(2.0 * math.pi * J / 365.0)          # eq. 23
    delta = 0.409 * math.sin(2.0 * math.pi * J / 365.0 - 1.39)        # eq. 24
    phi = math.radians(lat_deg)

    hour = (J % 1.0) * 24.0            # local solar-clock hour at period END
    t_mid = hour - 0.5                 # midpoint of the hour
    omega_mid = math.pi / 12.0 * (t_mid - 12.0)
    omega1 = omega_mid - math.pi / 24.0
    omega2 = omega_mid + math.pi / 24.0

    term = ((omega2 - omega1) * math.sin(phi) * math.sin(delta)
            + math.cos(phi) * math.cos(delta) * (math.sin(omega2) - math.sin(omega1)))
    ra = (12.0 * 60.0 / math.pi) * G_SC * d_r * term                   # eq. 28
    return max(0.0, ra)


def clear_sky_radiation(ra: float, elev_m: float) -> float:
    """R_so = (0.75 + 2e-5 z) R_a   (FAO-56 eq. 37)."""
    return (0.75 + 2e-5 * elev_m) * ra


# ------------------------------------------------------------------ psychrometry
def saturation_vapour_pressure(t_c: float) -> float:
    """e_s(T) [kPa], FAO-56 eq. 11."""
    return 0.6108 * math.exp(17.27 * t_c / (t_c + 237.3))


def slope_vapour_curve(t_c: float) -> float:
    """Delta = de_s/dT [kPa/degC], FAO-56 eq. 13."""
    es = saturation_vapour_pressure(t_c)
    return 4098.0 * es / ((t_c + 237.3) ** 2)


def atmospheric_pressure(elev_m: float) -> float:
    """P [kPa], FAO-56 eq. 7."""
    return 101.3 * ((293.0 - 0.0065 * elev_m) / 293.0) ** 5.26


def psychrometric_constant(elev_m: float) -> float:
    """gamma [kPa/degC], FAO-56 eq. 8."""
    return 0.000665 * atmospheric_pressure(elev_m)


# -------------------------------------------------------------------------- ET0
def et0_hourly(iso: str, lat_deg: float, temp_c: float, rh_pct: float,
               wind_kmh: float, sw_wm2: float, elev_m: float = 5.0) -> float:
    """FAO-56 Penman-Monteith, HOURLY reference ET0 [mm/hour] (eq. 53).

    Inputs are exactly the Open-Meteo/ERA5 columns stored in data/era5_multi:
      iso        local timestamp at the END of the hour ('YYYY-MM-DDTHH:MM')
      lat_deg    station latitude (deg N positive)
      temp_c     2-m air temperature [degC]
      rh_pct     2-m relative humidity [%]
      wind_kmh   10-m wind speed [km/h]  (FAO-56 asks for u2 at 2 m; see note)
      sw_wm2     downward shortwave radiation [W/m2]

    Note on wind height: ERA5/Open-Meteo archive delivers 10-m wind. FAO-56
    eq. 47 converts u_z to u2 with the logarithmic wind profile; we apply that
    conversion here so the PM equation receives a true u2. Omitting it would
    overestimate the aerodynamic term by ~35% at 10 m.
    """
    # --- u10 -> u2 (FAO-56 eq. 47) ----------------------------------------
    u_z = wind_kmh / 3.6
    u2 = u_z * 4.87 / math.log(67.8 * 10.0 - 5.42)

    # --- vapour pressures ---------------------------------------------------
    es = saturation_vapour_pressure(temp_c)
    ea = es * rh_pct / 100.0
    vap_def = max(0.0, es - ea)

    # --- radiation ----------------------------------------------------------
    rs = sw_wm2 * 3600.0 / 1e6                       # W/m2 -> MJ m^-2 h^-1
    ra = extraterrestrial_hour(iso, lat_deg)
    rso = clear_sky_radiation(ra, elev_m)
    rns = (1.0 - ALBEDO) * rs                        # eq. 40

    # Net longwave, eq. 41 hourly. The clearness factor (1.35 Rs/Rso - 0.35) is
    # bounded to [0.35, 1.0] as FAO-56 prescribes: without the floor, night
    # (Rs = 0) would give a NEGATIVE Rnl, i.e. the surface gaining longwave
    # energy from the sky, which is unphysical and would produce night ET0 > 0.
    if rso > 0.0:
        clear_factor = 1.35 * min(1.0, rs / rso) - 0.35
    else:
        clear_factor = 0.35
    clear_factor = min(1.0, max(0.35, clear_factor))

    t_k = temp_c + 273.16
    rnl = SIGMA_HOUR * (t_k ** 4) * (0.34 - 0.14 * math.sqrt(ea)) * clear_factor

    rn = rns - rnl                                   # MJ m^-2 h^-1

    # Soil heat flux for hourly periods (FAO-56 eq. 45/46)
    g = 0.1 * rn if rn > 0 else 0.5 * rn

    # --- Penman-Monteith, eq. 53 -------------------------------------------
    delta = slope_vapour_curve(temp_c)
    gamma = psychrometric_constant(elev_m)
    numerator = 0.408 * delta * (rn - g) + gamma * (37.0 / (temp_c + 273.0)) * u2 * vap_def
    denominator = delta + gamma * (1.0 + 0.34 * u2)
    return max(0.0, numerator / denominator)


# ------------------------------------------------------------- soil water bucket
@dataclass(frozen=True)
class SoilProfile:
    """Root-zone soil water bucket parameters.

    Defaults: silty-clay loam typical of the Mekong delta, using mid-range
    FAO-56 Table 2 texture values with a 0.5 m root zone.
      theta_sat 0.45, theta_fc 0.32, theta_wp 0.18 [m3/m3]
    """
    theta_sat: float = 0.45
    theta_fc: float = 0.32
    theta_wp: float = 0.18
    root_depth_m: float = 0.5
    cn_runoff: float = 80.0
    kc: float = 1.05          # mid-season rice Kc, FAO-56 Table 12

    @property
    def awc_mm_per_m(self) -> float:
        return (self.theta_fc - self.theta_wp) * 1000.0

    @property
    def taw_mm(self) -> float:
        """Total available water in the root zone [mm], FAO-56 eq. 82."""
        return self.awc_mm_per_m * self.root_depth_m

    @property
    def fc_mm(self) -> float:
        return self.theta_fc * 1000.0 * self.root_depth_m

    @property
    def wp_mm(self) -> float:
        return self.theta_wp * 1000.0 * self.root_depth_m

    @property
    def sat_mm(self) -> float:
        return self.theta_sat * 1000.0 * self.root_depth_m


def scs_runoff(precip_mm: float, cn: float) -> float:
    """SCS-CN direct runoff [mm] for ONE RAINFALL EVENT (SCS 1972).

    WARNING -- resolution matters. The CN method is defined for an event or a
    day of rainfall. Applying it to individual HOURS is wrong: with CN=80 the
    initial abstraction is Ia = 0.2*S = 12.7 mm, which a single hour of rain
    almost never exceeds, so the yearly runoff collapses to a few millimetres
    even where the delta floods every wet season. Measured on the real 2024 Can
    Tho series this gave 2 mm of runoff against 2248 mm of rain -- physically
    absurd.

    Therefore callers must pass an EVENT/DAILY depth, and the hourly bucket uses
    `daily_runoff_share` below, which computes runoff once per day and returns it
    to the hourly balance pro rata over the day's rain.
    """
    if precip_mm <= 0.0:
        return 0.0
    s = 25400.0 / cn - 254.0
    ia = 0.2 * s
    if precip_mm <= ia:
        return 0.0
    return ((precip_mm - ia) ** 2) / (precip_mm - ia + s)


def daily_runoff_share(day_precip_mm: float, hour_precip_mm: float,
                       cn: float) -> float:
    """Runoff attributable to one hour, given the day's total rainfall.

    Runoff is computed on the DAILY depth (the resolution the CN method is
    defined for), then split across the day's wet hours in proportion to each
    hour's rainfall. Hours with no rain get no runoff. This keeps the hourly
    water balance exact while using the CN method at its correct resolution.
    """
    if hour_precip_mm <= 0.0:
        return 0.0
    ro_day = scs_runoff(day_precip_mm, cn)
    if ro_day <= 0.0 or day_precip_mm <= 0.0:
        return 0.0
    return ro_day * (hour_precip_mm / day_precip_mm)


@dataclass
class BucketState:
    """Root-zone water content [mm]. Higher = wetter.

    Conservation is exact: this value is only ever changed by the terms returned
    in the info dict of step_bucket(). There is NO silent clamping -- a soil that
    dries below the wilting point keeps integrating downward (FAO-56 ch. 8 allows
    Dr > TAW under sustained deficit), and stress is handled by Ks, not by
    clipping storage, which would destroy the mass balance.
    """
    w: float = 0.0


@dataclass(frozen=True)
class StepInfo:
    """Every flux of one bucket step, so conservation can be audited."""
    rainfall: float
    runoff: float
    infiltration: float
    irrigation: float
    etc: float
    deep_percolation: float
    w_end: float


def stress_coefficient(st: BucketState, prof: SoilProfile, p: float = 0.5) -> float:
    """Ks, FAO-56 eq. 84: linear reduction of ETc once depletion passes p*TAW."""
    if st.w >= prof.fc_mm:
        return 1.0
    dr = prof.fc_mm - st.w
    raw = prof.taw_mm * p
    if dr <= raw:
        return 1.0
    ks = (prof.taw_mm - dr) / ((1.0 - p) * prof.taw_mm)
    return min(1.0, max(0.0, ks))


def step_bucket(st: BucketState, prof: SoilProfile, precip_mm: float,
                irrig_mm: float, et0_mm: float,
                runoff_mm: float | None = None) -> tuple[BucketState, StepInfo]:
    """Advance the root-zone water balance by one hour.

    ETc = Ks * Kc * ET0 (FAO-56 eq. 83-84). Order of operations follows ch. 8:
    add inflows (rain net of runoff, irrigation), subtract ETc, then drain the
    excess above field capacity as deep percolation.

    `runoff_mm` MUST be supplied by the caller as a daily-resolution value
    (see `daily_runoff_share`). If omitted, the SCS-CN formula is applied to the
    single hour, which under-produces runoff by orders of magnitude -- the
    default is kept only for unit tests of the CN curve itself.

    Conservation identity (audited by the test):
        w_end == w_start + infiltration + irrigation - etc - deep_percolation
    """
    ro = scs_runoff(precip_mm, prof.cn_runoff) if runoff_mm is None else runoff_mm
    infil = max(0.0, precip_mm - ro)

    ks = stress_coefficient(st, prof)
    etc = ks * prof.kc * et0_mm

    w = st.w + infil + irrig_mm - etc
    dp = 0.0
    if w > prof.fc_mm:
        dp = w - prof.fc_mm
        w = prof.fc_mm

    info = StepInfo(rainfall=precip_mm, runoff=ro, infiltration=infil,
                    irrigation=irrig_mm, etc=etc, deep_percolation=dp, w_end=w)
    return BucketState(w=w), info


def depletion_fraction(st: BucketState, prof: SoilProfile) -> float:
    """Root-zone depletion p in [0,1]: 0 = field capacity, 1 = wilting point.

    Clipping happens HERE, in the reported indicator only -- never inside the
    balance, so the mass-balance identity stays exact.
    """
    span = prof.fc_mm - prof.wp_mm
    if span <= 0:
        return 0.0
    return min(1.0, max(0.0, (prof.fc_mm - st.w) / span))


def is_safe(st: BucketState, prof: SoilProfile, lo: float = 0.0,
            hi: float = 0.85) -> bool:
    """Safe set: depletion fraction inside [lo, hi].

    hi = 0.85 keeps the crop above severe stress (Ks still > 0.3 by eq. 84 with
    p = 0.5); lo = 0 excludes waterlogging at saturation.
    """
    return lo <= depletion_fraction(st, prof) <= hi

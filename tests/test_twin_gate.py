#!/usr/bin/env python3
"""Verification of the K1 twin gate mechanism.

These checks are about MECHANISM, not about paper results. They exist to prove
the gate is not a no-op, that its parts behave monotonically, and that the two
baselines really do exhibit the failure mode the paper claims.

  1. safe_probability is monotone in the mean and in sigma, and exact for a
     deterministic twin (sigma -> 0).
  2. safe_bounds agrees with water_balance.is_safe (two definitions, one set).
  3. The gate CAN withhold, and withholding is not vacuous: with a candidate set
     that includes "no irrigation" it releases, with only large candidates on a
     wet field it withholds.
  4. Fidelity monotonicity -- the paper's core claim in mechanism form: as
     sigma_frac grows (worse twin), fewer commands pass the chance constraint.
     If this is flat, the delta/sigma bound is decorative and the theorem is
     meaningless.
  5. delta monotonicity: a stricter delta admits fewer commands.
  6. The twin takes the command as an INPUT (the what-if property): two
     different candidate commands must roll out to two different means. A
     "predictor" cannot do this; if this test passes, renaming twin->predictor
     breaks the mechanism.
  7. blind_resend_policy double-irrigates when the original command actually
     landed (the failure mode the gate prevents).
  8. reactive_threshold_policy ignores probability entirely: on a field whose
     point estimate is just over the threshold it fires the largest candidate,
     even when the twin says that command is unsafe.
"""
from __future__ import annotations

import csv
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "src"))

from water_balance import (  # noqa: E402
    BucketState, SoilProfile, depletion_fraction, et0_hourly, is_safe,
)
from twin_gate import (  # noqa: E402
    CommandCandidate, GilbertElliott, TwinBelief, TwinParams,
    blind_resend_policy, reactive_threshold_policy, safe_bounds,
    safe_probability, twin_gate, twin_rollout,
)

DATA = HERE / "data" / "era5_multi"
STATION = "can_tho"
LAT = 10.0452


def load_weather(station: str = STATION, limit: int | None = None) -> tuple[list[dict], dict[str, float]]:
    rows = []
    with (DATA / f"{station}_2024.csv").open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append({"time": r["time"], "t": float(r["temp_c"]),
                         "rh": float(r["rh_pct"]), "w": float(r["wind_kmh"]),
                         "sw": float(r["sw_wm2"]), "p": float(r["precip_mm"])})
    if limit:
        rows = rows[:limit]
    for r in rows:
        r["et0"] = et0_hourly(r["time"], LAT, r["t"], r["rh"], r["w"], r["sw"])
    day_rain: dict[str, float] = {}
    for r in rows:
        d = r["time"][:10]
        day_rain[d] = day_rain.get(d, 0.0) + r["p"]
    return rows, day_rain


def main() -> int:
    fails: list[str] = []
    weather, day_rain = load_weather()
    prof = SoilProfile()
    print(f"weather rows: {len(weather)} | days: {len(day_rain)}")
    print(f"profile: TAW={prof.taw_mm:.1f} FC={prof.fc_mm:.1f} WP={prof.wp_mm:.1f} mm")

    # --- 1. safe_probability monotone + deterministic limit -------------------
    lo, hi = safe_bounds(prof)
    print(f"\n1. safe bounds from depletion set [0, {0.85}]: "
          f"w in [{lo:.1f}, {hi:.1f}] mm")
    mid = 0.5 * (lo + hi)
    sig = 5.0
    seq = [safe_probability(mid + k, sig, prof, lo, hi) for k in (0, 5, 10, 20)]
    print(f"   P(safe) moving the mean up from midpoint: {[round(x,4) for x in seq]}")
    if any(b > a for a, b in zip(seq, seq[1:])):
        fails.append("P(safe) should fall as the mean leaves the safe interval")
    sigs = [safe_probability(mid, s, prof, lo, hi) for s in (0.5, 2.0, 8.0, 30.0)]
    print(f"   P(safe) vs sigma at midpoint: {[round(x,4) for x in sigs]}")
    if any(b > a for a, b in zip(sigs, sigs[1:])):
        fails.append("P(safe) must decrease as sigma grows")
    p_det_in = safe_probability(mid, 0.0, prof, lo, hi)
    p_det_out = safe_probability(hi + 10.0, 0.0, prof, lo, hi)
    print(f"   sigma=0 inside={p_det_in} outside={p_det_out} (must be 1.0 / 0.0)")
    if p_det_in != 1.0 or p_det_out != 0.0:
        fails.append("deterministic limit of safe_probability is wrong")

    # --- 2. bounds agree with is_safe ----------------------------------------
    for frac in (0.0, 0.2, 0.5, 0.85, 1.0):
        w = prof.fc_mm - frac * (prof.fc_mm - prof.wp_mm)
        st = BucketState(w=w)
        in_set = is_safe(st, prof)
        in_bounds = (lo <= w <= hi)
        if in_set != in_bounds:
            fails.append(f"is_safe={in_set} but bounds={in_bounds} at depletion {frac:.2f}")
    print(f"2. is_safe() and safe_bounds() agree at depletion 0,0.2,0.5,0.85,1.0: OK")

    # --- 3. gate can withhold -------------------------------------------------
    big = [CommandCandidate(30.0, "open30"), CommandCandidate(20.0, "open20")]
    tp = TwinParams(sigma_frac=0.10, horizon=6, delta=0.05)
    # a WET field (at field capacity): big commands push it out of the safe set
    w_wet = prof.fc_mm
    dec_wet = twin_gate(w_wet, 0, weather, 100, prof, tp, day_rain, big)
    # a DRY field (near wilting): some command should be released
    w_dry = prof.wp_mm + 0.10 * (prof.fc_mm - prof.wp_mm)
    dec_dry = twin_gate(w_dry, 0, weather, 100, prof, tp, day_rain, big)
    print(f"\n3. gate on WET field (w={w_wet:.1f}): sent={dec_wet.sent} "
          f"p={dec_wet.prob:.3f} reason='{dec_wet.reason}'")
    print(f"   gate on DRY field (w={w_dry:.1f}): sent="
          f"{dec_dry.sent.label if dec_dry.sent else None} p={dec_dry.prob:.3f}")
    if dec_wet.sent is None and "withheld" not in dec_wet.reason:
        fails.append("wet-field decision was None but reason is not 'withheld'")
    if dec_wet.sent is not None:
        fails.append("gate released a 20-30 mm command on an already-wet field")
    if dec_dry.sent is None:
        fails.append("gate withheld everything on a near-wilting field -- "
                     "candidate set or horizon is misconfigured")

    # --- 4 & 5. fidelity and delta monotonicity ------------------------------
    cands = [CommandCandidate(m, f"open{m}") for m in (0.0, 5.0, 10.0, 15.0, 20.0, 30.0)]
    n_slots = 600
    start0 = 2000
    print(f"\n4. fidelity monotonicity over {n_slots} slots, dry-ish start")
    rel_by_sigma = {}
    for sf in (0.02, 0.05, 0.10, 0.20, 0.40):
        tpp = TwinParams(sigma_frac=sf, horizon=6, delta=0.05)
        released = 0
        for k in range(n_slots):
            w_k = w_dry + 0.02 * (prof.fc_mm - prof.wp_mm) * (k % 10)
            d = twin_gate(w_k, k % 12, weather, (start0 + k) % len(weather),
                          prof, tpp, day_rain, cands)
            released += 1 if d.sent is not None and d.sent.mm > 0 else 0
        rel_by_sigma[sf] = released
        print(f"   sigma_frac={sf:5.2f} -> released {released:4d}/{n_slots} "
              f"({100*released/n_slots:.1f}%)")
    vals = [rel_by_sigma[k] for k in sorted(rel_by_sigma)]
    if any(b > a for a, b in zip(vals, vals[1:])):
        fails.append(f"released commands did NOT decrease as the twin got worse: {vals}")

    print(f"\n5. delta monotonicity (sigma_frac=0.10)")
    rel_by_delta = {}
    for dl in (0.50, 0.20, 0.05, 0.01):
        tpp = TwinParams(sigma_frac=0.10, horizon=6, delta=dl)
        released = 0
        for k in range(n_slots):
            w_k = w_dry + 0.02 * (prof.fc_mm - prof.wp_mm) * (k % 10)
            d = twin_gate(w_k, k % 12, weather, (start0 + k) % len(weather),
                          prof, tpp, day_rain, cands)
            released += 1 if d.sent is not None and d.sent.mm > 0 else 0
        rel_by_delta[dl] = released
        print(f"   delta={dl:4.2f} (need p>={1-dl:.2f}) -> released {released:4d}/{n_slots}")
    dvals = [rel_by_delta[k] for k in sorted(rel_by_delta, reverse=True)]
    if any(b > a for a, b in zip(dvals, dvals[1:])):
        fails.append(f"stricter delta did not reduce releases: {dvals}")

    # --- 6. the what-if property (twin vs predictor) -------------------------
    w0 = 0.5 * (lo + hi)
    idx0 = 100
    outs = {}
    for mm in (0.0, 10.0, 25.0):
        m, s = twin_rollout(w0, 0, weather, prof, tp, mm, day_rain, idx0)
        outs[mm] = m
    print(f"\n6. twin rollout from the SAME belief w0={w0:.1f} mm, horizon={tp.horizon}h "
          f"(start index {idx0}):")
    for mm, m in outs.items():
        print(f"   command {mm:5.1f} mm -> predicted w = {m:7.2f} mm")
    # Physics: more applied water means MORE stored water, so the predicted mean
    # must INCREASE with command size. (An earlier version of this test asserted
    # the opposite; the assertion was wrong, not the rollout.)
    if not (outs[0.0] < outs[10.0] < outs[25.0]):
        fails.append("rollout mean is not increasing in command size -- "
                     "the twin is not responding to u, so it is a predictor, not a twin")
    spread = outs[25.0] - outs[0.0]
    print(f"   command sensitivity: {spread:.2f} mm of storage for 25 mm applied "
          f"(rest lost to ETc/drainage over {tp.horizon}h)")
    if spread <= 1.0:
        fails.append(f"rollout barely responds to u (spread {spread:.2f} mm) -- "
                     "the what-if query carries no information")

    # --- 7. blind resend double-irrigates ------------------------------------
    pending = CommandCandidate(20.0, "open20")
    rng = random.Random(7)
    ge = GilbertElliott()
    delivered_but_flagged_lost = True   # ACK lost, command landed
    fire = blind_resend_policy(pending, delivered_but_flagged_lost, cands)
    print(f"\n7. blind resend when the ACK was lost but the command LANDED: "
          f"resends {fire.label if fire else None} "
          f"=> field receives 20+20 = 40 mm (double irrigation)")
    if fire is None or fire.mm != 20.0:
        fails.append("blind_resend_policy did not reproduce the failure mode")
    no_fire = blind_resend_policy(pending, False, cands)
    if no_fire is not None:
        fails.append("blind_resend_policy fired without a loss")

    # --- 8. reactive threshold ignores probability --------------------------
    w_edge = prof.fc_mm - 0.60 * (prof.fc_mm - prof.wp_mm)   # depletion 0.60 > 0.55
    react = reactive_threshold_policy(w_edge, 0, weather, 100, prof, day_rain, cands)
    dec_gate = twin_gate(w_edge, 0, weather, 100, prof, tp, day_rain, cands)
    print(f"\n8. at depletion 0.60 (above the 0.55 reactive threshold):")
    print(f"   reactive fires: {react.label if react else None} "
          f"({react.mm if react else 0:.0f} mm, the LARGEST candidate)")
    print(f"   twin gate:      {dec_gate.sent.label if dec_gate.sent else 'WITHHELD'} "
          f"(p={dec_gate.prob:.3f})")
    if react is None or react.mm != max(c.mm for c in cands):
        fails.append("reactive baseline should fire its largest candidate")
    if react is not None and dec_gate.sent is not None and dec_gate.sent.mm >= react.mm:
        fails.append("gate and reactive are indistinguishable here -- pick a slot where they differ")

    # --- channel sanity ------------------------------------------------------
    for name, ge in [("mild", GilbertElliott(0.06, 0.22, 0.035, 0.65)),
                     ("severe", GilbertElliott(0.08, 0.15, 0.82, 0.15))]:
        rng = random.Random(11)
        n = 20000
        ok = sum(1 for _ in range(n) if ge.send(rng))
        print(f"9. channel '{name}': empirical delivery {ok/n:.3f}, "
              f"stationary bad-state {ge.stationary_loss:.3f}")
        if not (0.0 < ok / n < 1.0):
            fails.append(f"channel {name} delivered nothing or everything")

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

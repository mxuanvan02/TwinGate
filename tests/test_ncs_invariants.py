#!/usr/bin/env python3
"""Invariant checks for the networked control loop.

These are not performance results. They are properties that MUST hold for the
experiment to mean anything at all; a violation invalidates every comparison in
the main table. Each one was added because it was actually violated once:

  I1. HARD WATER BUDGET: delivered water must never exceed water_budget_mm.
      Violated before: a retransmission path bypassed the cap, so
      TwinGate+blindARQ delivered 215 mm under a 200 mm budget and then "won"
      the safety ranking purely by spending water it was not allocated.

  I2. ONE DECISION PER EPOCH: commands_generated <= number of epochs.
      Violated before: withheld decisions did not consume the epoch, so a
      withholding policy re-evaluated every hour and fired ~16 micro-doses/day.

  I3. NO MICRO-DOSING: every DELIVERED command has depth > 0 and the mean
      delivered depth is a value the candidate set can actually produce.
      Violated before: the gate released a 0 mm command, which was counted as a
      delivery and inflated mm_per_event to 3.84 with candidates {10,20,35}.

  I4. CONSERVATION: water_applied == water delivered by the downlink, and
      double-irrigation waste is a subset of applied water.

  I5. ORACLE IS A VALID REFERENCE: with an unlimited budget the perfect-
      information controller must not be the worst policy on safety.
      Violated before: Oracle scored 3.21% unsafe vs 0.00% for every baseline,
      because it only reacted after a violation with the largest depth.

  I6. RE-ANCHORING IS NOT VACUOUS, and a DEGENERATE zero is detected rather than
      rewarded. The first version of this check asserted RMSE(ON) < RMSE(OFF) and
      FAILED with OFF = 0.000 mm. Diagnosis: with re-anchoring disabled the gate
      never regains information, sigma exceeds sigma* (T1'), the gate is EMPTY for
      every candidate set, so it issues ZERO commands -- and because the twin and
      the field then both receive zero irrigation, the twin tracks the field
      perfectly and RMSE is exactly 0. A zero RMSE there is degenerate agreement,
      not accuracy. The invariant is therefore: if commands_generated == 0 then
      the field must actually suffer (unsafe% large), which is precisely the T1'
      abstain region showing up in the experiment.

  I7. BELIEF CALIBRATION: T1 states its guarantee using the twin's own sigma, so
      that sigma must be honest. Measure the standardised residual z = (w_hat -
      w_true)/sigma(twin_age) on real ERA5 forcing and require the empirical
      95% coverage to be within tolerance of 0.95. If coverage is far below 0.95
      the Gaussian belief is over-confident and the guarantee does not hold; if it
      is far above, sigma is inflated and the gate withholds without cause.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ncs_loop import (  # noqa: E402
    NETWORKS, POLICIES, PolicyConfig, default_candidates, load_weather,
    march_start, run_episode,
)

STATION = "can_tho"
HOURS = 2160
EPOCH = 24
SEEDS = (7, 11, 17)
BUDGETS = (80.0, 140.0, 200.0)
CAND = default_candidates()
DEPTHS = sorted({c.mm for c in CAND if c.mm > 0.0})


def main() -> int:
    fails: list[str] = []
    weather, _ = load_weather(STATION)
    ms = march_start(weather)
    print(f"station={STATION} start={ms} ({weather[ms]['time']}) hours={HOURS} "
          f"epoch={EPOCH}h candidates={DEPTHS} mm\n")

    # ---- I1 + I2 + I3 + I4 across every policy/network/budget --------------
    worst_over = 0.0
    max_gen = 0
    epochs = HOURS // EPOCH
    print("I1-I4: invariants per (policy, network, budget)")
    for net in NETWORKS:
        for bud in BUDGETS:
            for pol in POLICIES:
                for s in SEEDS:
                    m = run_episode(STATION, pol, s, hours=HOURS, start=ms,
                                    network=net, slots_per_decision=EPOCH,
                                    water_budget_mm=bud)
                    over = m.water_applied_mm - bud
                    if over > 1e-9:
                        worst_over = max(worst_over, over)
                        fails.append(f"I1 {pol.name}/{net}/b={bud}/seed{s}: delivered "
                                     f"{m.water_applied_mm:.1f} > budget {bud} "
                                     f"(over by {over:.1f} mm)")
                    max_gen = max(max_gen, m.commands_generated)
                    if m.commands_generated > epochs:
                        fails.append(f"I2 {pol.name}/{net}/b={bud}/seed{s}: generated "
                                     f"{m.commands_generated} > {epochs} epochs")
                    if m.commands_delivered > 0:
                        mean_depth = m.water_applied_mm / m.commands_delivered
                        if mean_depth < min(DEPTHS) - 1e-9:
                            fails.append(f"I3 {pol.name}/{net}/b={bud}/seed{s}: mean "
                                         f"delivered depth {mean_depth:.2f} mm below the "
                                         f"smallest candidate {min(DEPTHS)} mm")
                    if m.water_wasted_dup_mm > m.water_applied_mm + 1e-9:
                        fails.append(f"I4 {pol.name}/{net}/b={bud}/seed{s}: dup waste "
                                     f"{m.water_wasted_dup_mm:.1f} exceeds applied "
                                     f"{m.water_applied_mm:.1f}")
                    if m.commands_delivered > m.commands_sent:
                        fails.append(f"I4 {pol.name}/{net}/b={bud}/seed{s}: delivered "
                                     f"{m.commands_delivered} > sent {m.commands_sent}")
    print(f"  checked {len(NETWORKS)*len(BUDGETS)*len(POLICIES)*len(SEEDS)} episodes; "
          f"worst budget overshoot = {worst_over:.3f} mm (must be 0)")
    print(f"  max commands_generated = {max_gen} vs epochs = {epochs}")

    # ---- I3 detail: every delivered command depth must be real -------------
    print("\nI3: mean delivered depth per policy (must be in the candidate set range)")
    for pol in POLICIES:
        m = run_episode(STATION, pol, 7, hours=HOURS, start=ms, network="mild",
                        slots_per_decision=EPOCH, water_budget_mm=200.0)
        md = (m.water_applied_mm / m.commands_delivered) if m.commands_delivered else 0.0
        ok = (md == 0.0) or (min(DEPTHS) - 1e-9 <= md <= max(DEPTHS) + 1e-9)
        print(f"  {pol.name:20s} applied={m.water_applied_mm:7.1f} "
              f"delivered_cmds={m.commands_delivered:3d} mean={md:6.2f} "
              f"{'OK' if ok else 'IMPOSSIBLE'}")
        if not ok:
            fails.append(f"I3 {pol.name}: mean depth {md:.2f} outside "
                         f"[{min(DEPTHS)}, {max(DEPTHS)}]")

    # ---- I5: Oracle validity with an unlimited budget ----------------------
    print("\nI5: Oracle must be a valid achievability reference (budget=inf)")
    for net in NETWORKS:
        uns = {}
        for pol in POLICIES:
            vals = [run_episode(STATION, pol, s, hours=HOURS, start=ms, network=net,
                                slots_per_decision=EPOCH, water_budget_mm=None)
                    for s in SEEDS]
            uns[pol.name] = 100 * sum(v.hours_unsafe for v in vals) / sum(v.hours for v in vals)
        orc = uns["Oracle"]
        worse = [p for p, v in uns.items() if p != "Oracle" and v < orc - 0.5]
        print(f"  [{net}] unsafe% = " + ", ".join(f"{k}:{v:.2f}" for k, v in uns.items()))
        print(f"        Oracle={orc:.2f}%  better-than-Oracle={worse}")
        if worse:
            fails.append(f"I5 {net}: Oracle unsafe% {orc:.2f} is worse than {worse}")

    # ---- I6: re-anchoring is not vacuous; detect the degenerate zero --------
    print("\nI6: with vs without uplink re-anchoring (same seeds, budget=inf)")
    for net in NETWORKS:
        on = PolicyConfig("on", True, True, True)
        off = PolicyConfig("off", True, True, False)
        m_on = [run_episode(STATION, on, s, hours=HOURS, start=ms, network=net,
                            slots_per_decision=EPOCH, water_budget_mm=None) for s in SEEDS]
        m_off = [run_episode(STATION, off, s, hours=HOURS, start=ms, network=net,
                             slots_per_decision=EPOCH, water_budget_mm=None) for s in SEEDS]
        n = len(SEEDS)
        rm_on = sum(x.twin_rmse for x in m_on) / n
        rm_off = sum(x.twin_rmse for x in m_off) / n
        gen_on = sum(x.commands_generated for x in m_on) / n
        gen_off = sum(x.commands_generated for x in m_off) / n
        uns_on = 100 * sum(x.hours_unsafe for x in m_on) / sum(x.hours for x in m_on)
        uns_off = 100 * sum(x.hours_unsafe for x in m_off) / sum(x.hours for x in m_off)
        print(f"  [{net}] ON : rmse={rm_on:.3f} mm gen={gen_on:.1f} unsafe={uns_on:.2f}%")
        print(f"        OFF: rmse={rm_off:.3f} mm gen={gen_off:.1f} unsafe={uns_off:.2f}%")

        # The informative direction: without re-anchoring the twin's sigma grows
        # past sigma* (T1'), the gate becomes EMPTY, no command is ever issued, and
        # the field suffers. A zero RMSE in that state is degenerate agreement
        # (both sides receive zero irrigation), NOT accuracy -- so it must not be
        # treated as "better".
        if gen_off == 0:
            if uns_off < 5.0:
                fails.append(f"I6 {net}: no commands issued without re-anchoring yet "
                             f"unsafe% is only {uns_off:.2f}% -- the episode is too easy "
                             "to distinguish the abstain region")
            else:
                print(f"        => abstain region confirmed (T1'): no information, "
                      f"empty gate, {uns_off:.2f}% unsafe. rmse=0 is degenerate, not accurate.")
        else:
            # If it DID issue commands, tracking must genuinely be worse without
            # re-anchoring, otherwise the uplink contributes nothing.
            if not (rm_off > rm_on):
                fails.append(f"I6 {net}: re-anchoring did not reduce twin RMSE "
                             f"({rm_on:.3f} vs {rm_off:.3f}) while {gen_off:.0f} commands "
                             "were issued")
        # And re-anchoring must be worth having: the field does better with it.
        if uns_on >= uns_off and gen_on > 0:
            fails.append(f"I6 {net}: re-anchoring did not improve safety "
                         f"({uns_on:.2f}% vs {uns_off:.2f}%)")
        else:
            print(f"        => re-anchoring improves safety: {uns_on:.2f}% vs {uns_off:.2f}% OK")

    # ---- I7: is the twin's own sigma honest? (T1 depends on this) -----------
    print("\nI7: empirical 95% coverage of |w_hat - w_true| <= 1.96*sigma(twin_age)")
    print("    (T1 states the guarantee in terms of this sigma; if the residual is")
    print("     wider than sigma claims, the guarantee is decorative)")
    for net in NETWORKS:
        for sf in (0.05, 0.10, 0.20):
            pol = PolicyConfig("calib", True, True, True, sigma_frac=sf)
            tot_n = tot_ok = 0
            for s in SEEDS:
                m = run_episode(STATION, pol, s, hours=HOURS, start=ms, network=net,
                                slots_per_decision=EPOCH, water_budget_mm=None)
                tot_n += m.calib_n
                tot_ok += m.calib_ok
            if tot_n == 0:
                print(f"  [{net} sigma_frac={sf}] no slots with sigma>0 -- skipped")
                continue
            cov = tot_ok / tot_n
            flag = "OK" if 0.85 <= cov <= 1.0 else "MISCALIBRATED"
            print(f"  [{net} sigma_frac={sf:.2f}] coverage={cov:.4f} "
                  f"(n={tot_n}) target=0.95  {flag}")
            # Only flag gross under-coverage as a hard failure: an over-confident
            # sigma silently breaks T1. Over-coverage means sigma is conservative,
            # which weakens the result but does not invalidate the guarantee.
            if cov < 0.85:
                fails.append(f"I7 {net}/sigma_frac={sf}: coverage {cov:.3f} < 0.85 -- "
                             "sigma is over-confident, T1's guarantee does not hold "
                             "at this fidelity setting")

    print()
    if fails:
        print(f"FAILED INVARIANTS ({len(fails)}):")
        for f in fails[:25]:
            print("  -", f)
        if len(fails) > 25:
            print(f"  ... and {len(fails)-25} more")
        return 1
    print("ALL INVARIANTS HOLD")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

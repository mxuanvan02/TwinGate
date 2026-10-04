#!/usr/bin/env python3
"""Diagnostic: does the decision-epoch command budget actually bind?

Run in a FRESH process (python3 tests/diag_epoch_cap.py). Do not run this inside a
persistent kernel that has already imported ncs_loop -- the stale module object
would silently be the pre-patch version and every number below would be wrong.
That exact mistake produced a bogus "epoch cap does not work" reading.

Decisive test: if `slots_per_decision` caps NEW commands, then commands_generated
must scale DOWN roughly as hours/slots_per_decision. If it stays flat, the cap is
not wired in.
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ncs_loop import POLICIES, load_weather, march_start, run_episode  # noqa: E402

sig = inspect.signature(run_episode)
print("run_episode params:", list(sig.parameters))
assert "slots_per_decision" in sig.parameters, "PATCH NOT PRESENT in the imported module"
assert "commands_per_epoch" in sig.parameters, "PATCH NOT PRESENT in the imported module"

weather, _ = load_weather("can_tho")
ms = march_start(weather)
HOURS = 720
pol = POLICIES[0]          # TwinGate+T2

print(f"\nstation=can_tho start={ms} ({weather[ms]['time']}) hours={HOURS} policy={pol.name}\n")
print(f"{'slots_per_decision':>18} {'epochs':>7} {'generated':>10} {'sent':>7} "
      f"{'resends':>8} {'events/day':>11} {'mm/event':>9}")
prev = None
ok = True
for spd in (1, 6, 24, 120, 720):
    m = run_episode("can_tho", pol, 7, hours=HOURS, start=ms, network="mild",
                    slots_per_decision=spd)
    epochs = HOURS / spd
    per_day = m.commands_generated / (HOURS / 24.0)
    mm_ev = m.water_applied_mm / max(1, m.commands_delivered)
    print(f"{spd:>18} {epochs:>7.1f} {m.commands_generated:>10} {m.commands_sent:>7} "
          f"{m.resends_sent:>8} {per_day:>11.2f} {mm_ev:>9.2f}")
    if prev is not None and m.commands_generated > prev:
        ok = False
    prev = m.commands_generated

print()
print("monotone non-increasing in slots_per_decision:", "OK" if ok else "FAIL")
# At spd=24 with 1 command per epoch, generated must be <= number of epochs.
m24 = run_episode("can_tho", pol, 7, hours=HOURS, start=ms, network="mild",
                  slots_per_decision=24)
epochs24 = HOURS // 24
print(f"hard cap check: generated={m24.commands_generated} <= epochs={epochs24}: "
      f"{'OK' if m24.commands_generated <= epochs24 else 'FAIL'}")
if m24.commands_generated > epochs24:
    ok = False

sys.exit(0 if ok else 1)

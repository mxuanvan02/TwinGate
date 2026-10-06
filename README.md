# TwinGate — Digital-Twin Safety Gate for Irrigation Command Dispatch over Lossy Networks

Reference implementation for the paper

> **A Digital-Twin Safety Gate for Irrigation Command Dispatch over Lossy
> Networks and Its Relevance to Emission MRV**
>
> Mai Xuan Van, Nguyen Tuong Tri (corresponding) — Hue University, Vietnam.
> Funded by Hue University, Grant No. DHH2025-19-07.
> Manuscript under review at the Hue University Journal of Science (HUJOS-TT).

TwinGate decides, once every 24-hour epoch, *whether* an irrigation command may
be sent at all — and with what depth — when the command channel drops packets
and the gateway's view of the field is a drifting digital twin. It is built for
MRV-grade water management of low-emission rice in the Mekong Delta, where
every credit-eligible action (alternate wetting and drying, drainage) passes
through a control command on cheap, lossy wireless links.

## The problem

Carbon-credit programmes for rice (Decision 1490/QD-TTg, Verra VM0051 v1.1)
bottleneck at MRV cost, and the highest-rank evidence under Decision
4801/QD-BNNMT is the *record of actual irrigation and drainage actions*. In
NCS terms, the scarce resource here is not the uplink sample (as in AoI /
digital-twin-sync literature) but the **downlink command**. The gateway must
answer: *is it safe to issue this command now?*

## Contributions

- **A chance-constrained safety gate in front of the command transmitter.**
  A FAO-56 root-zone water-balance twin takes each candidate depth `u` as
  input (counterfactual rollout), and the command is released only when the
  predicted post-command state lies in the agronomic safe set with probability
  ≥ 1 − δ.
- **A fidelity threshold σ\* = W / (2·z₁₋δ/₂).** When the twin's predictive
  standard deviation exceeds σ\*, the gate is empty for *every* command set and
  silence (WITHHELD) is the optimal action. Verified by invariant I6
  (`tests/test_ncs_invariants.py`, uncapped-budget configuration): with uplink
  re-anchoring disabled, σ crosses σ\*, the gate generates **0.0 commands**,
  the field is unsafe **57.82 %** of the hours, and twin RMSE reads **0.000 mm**
  — a degenerate agreement (twin and field both receive zero water), not
  accuracy. Exactly the predicted gate paralysis. Re-anchoring restores
  0.00 % (mild) and 2.84 % (severe) unsafe hours.
- **WITHHELD as a first-class action.** Unlike every AoI-based scheduler,
  *not transmitting* is a valid, logged, MRV-useful outcome.
- **Belief-driven resend policy T2.** After a lost ACK the gateway keeps
  πₖ = 1 − (1 − φ)ᵏ (φ = p_dl·(1 − p_ack)), the belief that the pending command
  already landed, and resends only while πₖ stays below a myopic
  expected-cost threshold. T2 cuts double-irrigation water waste 23 % vs blind
  ARQ at equal or better safety.
- **A closed-form applicability proposition.** |P| ≤ 1 + |W − 2zσ_H| / Δ_min:
  once the pass region is narrower than the actuator step, every command
  selection rule collapses to the same command — measured 36/36 cells identical
  at f_σ = 0.10 vs 18/36 significantly different at f_σ = 0.02.
- **A tidal-salinity constraint (scenario model).** The gate hard-excludes
  pumping whenever the source is saline (0 mm saline delivered vs up to
  2 116 dS·mm of excess salt load for baselines at intrusion intensity
  i = 2.0, station×network×seed aggregate), and is invariant to the disputed
  salinity
  tolerance thresholds. No field salinity measurements exist, so this is a
  scenario analysis, not a compliance claim.

## Headline results

Main grid: 3 stations × 2 channels × 6 water budgets × 7 policies × 10 seeds ×
3 fidelity bands = **7 560 episodes per year** (2024 dry-scarce, 2025
water-surplus); 36 480 episodes in total across all grids.

- Unsafe hours, severe channel, f_σ = 0.02: **34.79 %** (TwinGate+T2) vs
  41.27–53.78 % (all baselines) at B = 80 mm; **0.81 %** vs 11.30–48.39 % at
  B = 240 mm. Oracle gap = the price of imperfect information.
- Paired Wilcoxon with Holm correction over 540 comparisons: **344
  significant, none favouring a baseline**.
- Credit-eligible AWD cycles (dry phase ≥ 72 h per QĐ 4801) appear **only when
  f_σ ≤ 0.025** — a closed-form condition that more frequent sensing cannot
  fix (σ has a floor f_σ·TAW·g even at age 0).

## Second paper: physics-attested irrigation logs

The same FAO-56 twin is used a second time, in a different role. Paper 1 uses it
as a pre-transmission safety gate for irrigation commands. Paper 2 uses it as a
post-hoc auditor of what a farmer *claimed*, so that an irrigation log recorded
on a mobile phone can serve as MRV evidence with no sensor deployed.

A claimed depth is an input to the water balance, so a fabricated log produces a
trajectory the soil cannot produce. Three filters follow:

| Filter | Violation it detects |
|---|---|
| `V1` saturation | irrigation claimed while the root zone is already at field capacity |
| `V2` infeasible depletion | a claimed history that drives depletion outside its physical range |
| `V4` storage excess | a claimed depth larger than the storage the soil can hold at that hour |

Guarantee: an AWD-compliant log never triggers any of them, and the largest
claimable depth that never raises an alarm is `u_max = d* · span + ε = 61 mm`
for the reference soil. Omission fraud (deleting real commands to fake a dry
phase) is provably invisible to replay, and is closed exactly by one flow meter
at the cooperative pumping station, `G = M − U(L) > τ`.

Measured on 240 audited logs (3 stations × 2 climate years × 10 seeds):
**0 false alarms**, **60/60** detected for each of the three fraud classes, mean
pump gap 29.0 mm against τ = 5 mm.

```bash
python3 experiments/fraud_detection.py           # 240 logs, exits non-zero on any gate failure
python3 experiments/make_tables_paper2.py        # regenerates paper2/tables/*.tex from the CSV
```

Design notes: `PROPOSAL_TWIN_ATTESTED.md` (the proposal) and
`PROPOSAL_MRV_COST.md` (the four-architecture cost comparison). Hardware prices
there are planning estimates, not quotations.

## What the robustness upgrade found (read this before quoting the paper)

The v1 fraud experiment reported "0 false alarms / 60/60 detected". That result is
**correct but self-referential**: the "real" trajectory was generated by the same
model that then audited it — same default `SoilProfile`, same ERA5 forcing with no
noise, irrigation as a one-hour impulse of exactly {20,40} mm, threshold exactly
0.80, and a farmer who records the right hour and the right number every time.

`experiments/reality_gap_probe.py` rebuilds the field so that it deliberately
violates every one of those assumptions, then lets the **published default** twin
audit it. Seven axes differ, each with a source: soil texture across the FAO-56
Table 2 range, Kc by growth stage (Table 12: 1.05/1.20/0.90), irrigation
efficiency 60–85%, field rain vs ERA5 grid cell, bund seepage, recording behaviour
(forgetting, rounding to 5 mm, one-day delay, depth error), and unknown initial
soil water.

Seven design holes were measured. Three matter most:

**Tier 1 falsely accused 26.7 % of honest farmers.** The absolute `G > 5 mm`
threshold treats a farmer who forgets one entry, rounds to 5 mm, or records a day
late exactly like one who irrigated secretly. Measured gap on honest logs reached
75 mm. Replaced by `τ(n) = δ_rel·M + z·σ(n)` with `σ(n) ∝ √n`, which cuts false
accusation to 5.0 % — **and cuts omission detection from 80 % to 40 %.** That
trade-off is real and must be reported, not hidden.

**Claim consolidation and time-shifting are invisible to physics.** An attacker
keeps the total mm identical (so the pump meter sees nothing) and keeps every
single depth under the infiltration bound (so F1/F4/F5 see nothing), and merely
moves commands in time. Measured: **+69 % to +78 % more credit-eligible dry
phases**, escaping both tiers in 91–100 % of cases.

**The only defence that reaches 100 % / 0 % is the device-anchored log** — matching
the claimed log against the gateway's signed, time-stamped command record:
**116/116** genuinely forged logs caught, **0/60** honest farmers accused (re-verified by counting the CSV; **37/37** under the full 150-replay Θ). Paper 1's
TwinGate gateway already writes that record, so the marginal cost stays near zero
*if the two are deployed together*. **Tier 0 as a standalone phone app is not
trustworthy on its own** — the cost model in the paper must say so.

Two further honesty corrections:

- **V2 was dead code.** `depletion_fraction()` clips to [0,1], so the
  `DEPL_IMPOSSIBLE = 1.02` threshold could never fire — 0 hits in 281 logs. It is
  now fixed via `depletion_raw()`, but on real ERA5 the clipped depletion peaks at
  **0.998 (2024) and 0.988 (2025)**: a dry-season delta rice field never goes below
  the wilting point. So V2 is a *safety* filter, **not** evidence of detection. Do
  not advertise "three filters".
- **`u_max` is per event, not per season.** `u_max = max(d*, w0)·span + ε` yields a
  **range [49.0, 86.0] mm** across Θ, not the single 61 mm the paper states, and the
  bucket drains continuously so a season-long inflation of many sub-threshold claims
  is not bounded by it.

Full measurement log: `UPGRADE_FINDINGS.md`.

```bash
python3 tests/test_log_filters.py                       # 46 tests, one per hole
python3 experiments/reality_gap_probe.py 3              # 7 reality-gap axes
python3 experiments/robust_audit_eval.py --quick        # v1 vs v2, 9 fraud variants
python3 experiments/analyze_robust_eval.py outputs/robust_audit_eval.csv
```

## Paper 2 changed axis: device-anchored, not physics-attested

The robustness work above did not merely add caveats — it reversed the paper's
conclusion. The first version claimed that soil-water physics could attest a
farmer-written log at near-zero cost. Two propositions show why it cannot:

- **Aggregate defences are exactly blind.** If two logs share the same multiset of
  depths, then `G = M − U(L)` and the infiltration-bound violation count are both
  invariant. The pump meter and `V5` cannot distinguish them at all.
- **Profit and undetectability share a gradient.** Delaying a claim both extends
  the creditable dry phase *and* increases the deficit available to it, so the
  move that earns more credit is also the move that looks more legitimate.

Measured consequence: a volume-preserving, depth-bounded **time shift** inflates
creditable dry phases by **+69%** (reduced Θ) to **+78%** (full Θ) while escaping
both physical tiers in 91–100% of cases.

What actually holds is the **device anchor** — matching the claimed log against
the gateway's signed, time-stamped command record:

| Defence | Caught genuinely forged | False accusation on honest logs |
|---|---|---|
| v1 point model (as published) | naive only | **26.7%** |
| v2 physics, ∀ over Θ | naive only | 5.0% |
| **Device anchor** | **116/116 = 100%** | **0/60** |

So the honest claim is narrower and more useful: near-zero-cost MRV is
achievable **only where a controller stands between the farmer and the pump**.
Hand-operated sluices have no command record, so this layer does not apply there.

Two published numbers were corrected: the admissible depth is a range
**[49.0, 86.0] mm**, not a single 61 mm (it is a *per-event* bound, and
`u_max = max(d*, w0)·span + ε`); and the wilting-point filter **cannot activate**
on dry-season delta rice — over 150 configurations the unclipped depletion peaks
at **0.9987**, so it is a safety device, not detection evidence. Do not describe
the layer as having "three physical filters".

```bash
python3 experiments/diag_f2.py                 # V2 reachability, 150 configs
python3 experiments/make_tables_anchored.py    # paper2 tables + gate (exits non-zero on failure)
```

## Repository layout

```
src/water_balance.py     FAO-56 hourly ET0 (Penman–Monteith, wind u10→u2,
                         solar geometry) + soil-water bucket + SCS-CN runoff
src/twin_gate.py         chance-constrained gate, σ(a) AR(1)/Kalman law, σ*
src/command_resend.py    T2 belief filter + myopic resend threshold
src/tide_salinity.py     tidal salinity scenario model (C2 constraint)
src/ncs_loop.py          the 3-state NCS loop, 5 metrics, budget accounting
tests/                   7 test scripts incl. the 6 paper invariants (I1–I7)
experiments/             main grid, ablation, deployment sweep, multi-field,
                         σ×δ sweep, salinity scenario, Wilcoxon stats,
                         LaTeX table generator
data/                    ERA5 fetch script + cached 2024/2025 hourly weather
                         for Can Tho, Soc Trang, Ca Mau (Open-Meteo archive;
                         provenance JSONs included)
figures/                 all 8 paper figures, drawn from outputs/*.csv
outputs/                 every raw CSV and summary behind every paper number
reproduce.sh             one-command full reproduction
```

## Reproducing every number in the paper

```bash
./reproduce.sh            # full: tests + all grids + stats + figures (~2-4 min)
./reproduce.sh --quick    # smoke run (2 seeds, main grid only)
./reproduce.sh --tests    # invariant scripts only
```

The script creates its own `.venv`, fetches ERA5 weather only if the CSV cache
is missing (the Open-Meteo archive needs no API key and is deterministic for a
given station/year), runs the six test scripts, all seven experiment grids, the
paired Wilcoxon analysis, and regenerates every figure and LaTeX table.
Requirements: Python ≥ 3.11, numpy, scipy, matplotlib.

Every test script is a standalone executable that exits non-zero on any
violation:

```bash
python3 tests/test_ncs_invariants.py   # I1–I7, ALL INVARIANTS HOLD
```

| Invariant | Guarantee |
|---|---|
| I1 | water budget is hard: worst overshoot 0.000 mm over 108 episodes |
| I2 | exactly one decision per 24-h epoch (WITHHELD consumes the epoch too) |
| I3 | no micro-dosing: delivered depth ∈ candidate set {20, 40, 60} mm |
| I4 | mass conservation: bucket residual exactly 0 |
| I5 | Oracle is valid: no policy beats it by > 0.5 points |
| I6 | σ ≥ σ\* ⇒ gate empty (0 commands, WITHHELD always) |
| I7 | 95 % calibration band covers 0.99–1.00 empirically |

## Key parameters

| Symbol | Meaning | Value |
|---|---|---|
| W | safe-set width (depletion 0–0.85, TAW 70 mm) | 59.5 mm |
| σ\* | fidelity threshold at δ = 0.05 | 15.18 mm |
| H | twin rollout horizon | 6 h |
| ρ | AR(1) correlation of twin residual | 0.9 |
| f_σ | fidelity band (σ₀ = f_σ·TAW) | 0.02 / 0.05 / 0.10 |
| epoch | decision period | 24 h |
| candidates | agronomic irrigation depths | {20, 40, 60} mm |
| p_ack loss | ACK loss probability | 0.35 |
| channel | Gilbert–Elliott downlink | mild & severe configs |

## Limitations (read before citing numbers)

- Simulation study; no field deployment. 3 stations; FAO-56 Table-2 average
  soil parameters.
- σ is slightly conservative (I7 coverage 0.99–1.00 > 0.95) — the gate
  withholds more than strictly optimal.
- T2 is myopic; the full dynamic program remains open, and no closed-form
  optimality bound for T2 is proven yet.
- The salinity constraint is a scenario model (no field salinity data); yield
  loss uses a linear −12 % per dS/m translation capped at 100 %.
- Results are climate-year dependent (2024 scarce vs 2025 surplus reported
  separately; conclusions are conditional).

## Data

Hourly ERA5 weather (temperature, humidity, wind, shortwave radiation,
precipitation) for three Mekong-Delta stations, 2024 and 2025, via the public
Open-Meteo archive API (no API key). Per-file provenance JSONs are tracked in
`data/era5_multi/`; the weather CSVs themselves are not committed —
`reproduce.sh` re-fetches them deterministically (the same station/year always
returns the same ERA5 grid series). All 36 480 result rows behind every number
in the paper are committed under `outputs/`.

## Citation

If you use this code, please cite the paper (see `CITATION.cff`) and mention
the grant:

```bibtex
@unpublished{twingate2026,
  title  = {A Digital-Twin Safety Gate for Irrigation Command Dispatch over
            Lossy Networks and Its Relevance to Emission MRV},
  author = {Mai, Xuan Van and Nguyen, Tuong Tri},
  year   = {2026},
  note   = {Under review, Hue University Journal of Science — Techniques and
            Technology (HUJOS-TT). Code:
            \url{https://github.com/mxuanvan02/TwinGate}}
}
```

## Funding and declarations

Funded by Hue University under Grant No. DHH2025-19-07. The authors declare no
competing interests. The study uses public reanalysis weather data and
simulation experiments only; no human participants, animals or field
interventions were involved.

## License

MIT — see [LICENSE](LICENSE). Third-party policy documents referenced in the
paper (Verra VM0051, QĐ 4801/QĐ-BNNMT, QĐ 1490/QĐ-TTg) are **not**
redistributed here; they are publicly available from Verra and the Vietnamese
government portals.

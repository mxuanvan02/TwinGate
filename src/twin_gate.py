#!/usr/bin/env python3
"""The K1 mechanism: a lossy COMMAND channel, a twin that gates commands, and
the policies that compete for the same command budget.

What makes this study K1 rather than a re-run of RABS/CAW-VoU:

  * The scarce resource is the DOWNLINK COMMAND (open the valve for X minutes),
    not the uplink sensor sample. Both published papers schedule *data*.
  * The gateway holds a digital twin of the field water balance (FAO-56, see
    src/water_balance.py). A twin is not a predictor: it takes the candidate
    command u_t as an INPUT and rolls the field state forward under it. That is
    what makes "simulate the command before sending it" possible, and it is the
    property that does not survive renaming the twin to "predictor".
  * Commands are lost in bursts (Gilbert-Elliott). A lost command means the crop
    actually dries; a blind retransmission can double-irrigate and waste water.
  * The gate only releases a command whose predicted post-command state stays in
    the safe set with probability >= 1 - delta, under the twin's OWN predictive
    uncertainty (twin fidelity). Fidelity is therefore an explicit parameter of
    the safety guarantee, which is the theorem this paper proves.

All randomness is seeded; every number reported by experiments/ is reproducible
from data/era5_multi plus the seed.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from water_balance import (
    BucketState, SoilProfile, daily_runoff_share, depletion_fraction, is_safe,
    step_bucket,
)


# --------------------------------------------------------------- command channel
@dataclass
class GilbertElliott:
    """Two-state burst-loss channel for the DOWNLINK command path.

    States: good (command delivered) / bad (command lost).
      p_gb = P(bad -> good), p_bg = P(good -> bad)
    Stationary loss probability is p_bg / (p_bg + p_gb). The parameterisation
    mirrors the one used in the RABS/CAW-VoU experiments so the channel is
    comparable across the three papers.
    """
    p_good_to_bad: float = 0.06
    p_bad_to_good: float = 0.22
    loss_in_good: float = 0.035
    loss_in_bad: float = 0.65
    bad: bool = False

    @property
    def stationary_loss(self) -> float:
        """Long-run fraction of slots in the bad state (unconditional loss)."""
        tot = self.p_good_to_bad + self.p_bad_to_good
        return self.p_good_to_bad / tot if tot > 0 else 0.0

    def send(self, rng: random.Random) -> bool:
        """Advance one slot and return True if the command was delivered."""
        if self.bad:
            delivered = rng.random() > self.loss_in_bad
            if rng.random() < self.p_bad_to_good:
                self.bad = False
        else:
            delivered = rng.random() > self.loss_in_good
            if rng.random() < self.p_good_to_bad:
                self.bad = True
        return delivered


# ----------------------------------------------------------------- twin machinery
@dataclass
class TwinParams:
    """Twin fidelity knobs.

    `sigma_frac` is the multiplicative predictive standard deviation of the
    twin's next-step water content, expressed as a fraction of TAW. It is the
    single number that measures "how faithful is this twin", and the safety
    bound in the paper is stated in terms of it.

    `horizon` is how many hours ahead the twin rolls the candidate command.
    A predictor with no command input could never do this: rolling forward
    REQUIRES u, which is exactly the twin property.
    """
    sigma_frac: float = 0.10
    horizon: int = 6
    delta: float = 0.05          # allowed violation probability (1 - delta)


@dataclass
class TwinBelief:
    """What the gateway currently believes about one field.

    `w_hat` is the twin's water content [mm]; `age` is the number of hours since
    the last successful SENSOR uplink re-anchored it. Uncertainty grows with age
    exactly as in CAW-VoU, so the two papers share one staleness law.
    """
    w_hat: float = 0.0
    age: int = 0


def normal_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def twin_sigma(age: int, prof: SoilProfile, tp: TwinParams,
               rho: float = 0.90) -> float:
    """Predictive std of twin water content [mm], growing with age.

    Geometric accumulation of per-step innovation noise, saturating at the
    stationary value -- same shape as the AR(1)/Kalman variance recursion in
    CAW-VoU, so the staleness law is inherited rather than reinvented.
    """
    base = tp.sigma_frac * prof.taw_mm
    acc = base * math.sqrt(sum(rho ** (2 * k) for k in range(max(1, age + 1))))
    stationary = base / math.sqrt(max(1e-12, 1.0 - rho ** 2))
    return min(acc, stationary)


def twin_rollout(w_hat: float, age: int, weather: list[dict], prof: SoilProfile,
                 tp: TwinParams, command_mm: float,
                 day_rain: dict[str, float], start_idx: int) -> tuple[float, float]:
    """Roll the TWIN forward `horizon` hours under a candidate command.

    Returns (mean_w, sigma_w) after the horizon. The candidate command is applied
    in the FIRST hour (that is when the valve would open); the remaining hours
    carry only weather forcing. This is the what-if query that defines a twin:
    "if I send u, where does the field land?"
    """
    st = BucketState(w=w_hat)
    n = len(weather)
    for h in range(tp.horizon):
        i = start_idx + h
        if i >= n:
            break
        r = weather[i]
        d = r["time"][:10]
        ro = daily_runoff_share(day_rain.get(d, 0.0), r["p"], prof.cn_runoff)
        irrig = command_mm if h == 0 else 0.0
        et0 = r["et0"]
        st, _ = step_bucket(st, prof, r["p"], irrig, et0, runoff_mm=ro)
    sigma = twin_sigma(age + tp.horizon, prof, tp)
    return st.w, sigma


def safe_probability(w_mean: float, sigma: float, prof: SoilProfile,
                     lo_mm: float, hi_mm: float) -> float:
    """P(lo_mm <= W <= hi_mm) for W ~ N(w_mean, sigma^2).

    lo/hi are the safe set expressed as water-content bounds (mm), derived from
    the depletion-fraction safe set in water_balance.is_safe so that the two
    definitions agree exactly.
    """
    if sigma <= 1e-12:
        return 1.0 if (lo_mm <= w_mean <= hi_mm) else 0.0
    p_below = normal_cdf((lo_mm - w_mean) / sigma)
    p_above = 1.0 - normal_cdf((hi_mm - w_mean) / sigma)
    return max(0.0, min(1.0, 1.0 - p_below - p_above))


def safe_bounds(prof: SoilProfile, lo_frac: float = 0.0,
                hi_frac: float = 0.85) -> tuple[float, float]:
    """Convert the depletion-fraction safe set into water-content bounds [mm]."""
    span = prof.fc_mm - prof.wp_mm
    hi_mm = prof.fc_mm - lo_frac * span     # depletion >= lo  => w <= hi
    lo_mm = prof.fc_mm - hi_frac * span     # depletion <= hi  => w >= lo
    return lo_mm, hi_mm


# --------------------------------------------------------------------- decisions
@dataclass
class CommandCandidate:
    """One candidate action the gateway may send in a slot."""
    mm: float            # irrigation depth to apply [mm]
    label: str


@dataclass
class GateDecision:
    """Outcome of the twin gate for one slot."""
    sent: CommandCandidate | None
    prob: float
    reason: str
    scores: dict = field(default_factory=dict)


def twin_gate(w_hat: float, age: int, weather: list[dict], start_idx: int,
              prof: SoilProfile, tp: TwinParams, day_rain: dict[str, float],
              candidates: list[CommandCandidate],
              use_whatif: bool = True,
              target_depl: float | None = None) -> GateDecision:
    """K1 core: release only commands the twin says are safe with prob >= 1-delta.

    Among the candidates that pass the chance constraint, pick the one leaving
    the field closest to the middle of the safe set (least residual risk). If
    NONE passes, send nothing -- withholding is a legitimate gate action, and it
    is what stops blind retransmission from double-irrigating.

    `use_whatif=False` is the TWIN->PREDICTOR ABLATION: the rollout no longer
    receives the candidate command, so every candidate gets the SAME p and the
    gate loses the ability to compare consequences. That is exactly the property
    that makes this a twin rather than a predictor, so removing it must cost
    something measurable -- which is what the ablation experiment checks.
    """
    lo_mm, hi_mm = safe_bounds(prof)
    scores: dict[str, float] = {}
    passing: list[tuple[float, float, CommandCandidate]] = []
    for c in candidates:
        w_mean, sigma = twin_rollout(w_hat, age, weather, prof, tp,
                                     c.mm if use_whatif else 0.0,
                                     day_rain, start_idx)
        p = safe_probability(w_mean, sigma, prof, lo_mm, hi_mm)
        scores[c.label] = p
        if p >= 1.0 - tp.delta:
            # Selection rule. Two regimes, and picking the wrong one is measurable:
            #   target_depl=None  -> CENTRE-SEEKING: aim at the middle of the safe
            #       set, i.e. minimise residual risk. Correct when water is not the
            #       binding resource.
            #   target_depl=x     -> TARGET-SEEKING: aim at depletion x, i.e. hold
            #       the field at the dry end of the safe set. Required under a
            #       binding water budget, AND required for AWD compliance: an
            #       effective AWD dry phase must last >= 72 h (Decision 4801), and
            #       centre-seeking irrigates too early, cutting dry phases short.
            #       Measured before this change: 1 effective AWD cycle vs the
            #       Oracle's 10 at the same 200 mm budget.
            if target_depl is None:
                mid = 0.5 * (lo_mm + hi_mm)
                half = 0.5 * (hi_mm - lo_mm)
                dist = abs(w_mean - mid) / half if half > 0 else 0.0
            else:
                span = prof.fc_mm - prof.wp_mm
                w_target = prof.fc_mm - target_depl * span
                dist = abs(w_mean - w_target) / span if span > 0 else 0.0
            if not use_whatif:
                # Predictor mode: every candidate is scored identically, so the
                # centre-seeking rule carries no information. A system with no
                # what-if capability has no basis to prefer a small depth, and
                # in the field it simply opens the sluice as far as the budget
                # allows -- so rank by depth descending (largest affordable).
                dist = -c.mm
            passing.append((dist, p, c))
    if not passing:
        return GateDecision(None, max(scores.values()) if scores else 0.0,
                            "withheld: no candidate met the chance constraint",
                            scores)
    passing.sort(key=lambda t: t[0])
    _, p, best = passing[0]
    # A zero-depth command IS withholding. Emitting it over the radio would cost a
    # channel use and -- worse -- be counted as a delivered command, which inflates
    # the denominator of mm-per-event and silently corrupts every water metric.
    # Measured symptom before this fix: mm_per_event = 3.84 with a candidate set of
    # {10, 20, 35} mm, which is arithmetically impossible.
    if best.mm <= 0.0:
        return GateDecision(None, p, "withheld: zero-depth command is not a transmission",
                            scores)
    return GateDecision(best, p, "released", scores)


# ---------------------------------------------------------------------- policies
def reactive_threshold_policy(w_hat: float, age: int, weather: list[dict],
                              start_idx: int, prof: SoilProfile,
                              day_rain: dict[str, float],
                              candidates: list[CommandCandidate],
                              thresh: float = 0.55) -> CommandCandidate | None:
    """Baseline: irrigate as soon as the twin's point estimate is drier than
    `thresh` of the way from field capacity to wilting point. No probability, no
    horizon, no what-if -- this is the control the paper must beat.
    """
    d = depletion_fraction(BucketState(w=w_hat), prof)
    if d < thresh:
        return None
    return max(candidates, key=lambda c: c.mm)


def blind_resend_policy(pending: CommandCandidate | None,
                        lost_last_slot: bool,
                        candidates: list[CommandCandidate]) -> CommandCandidate | None:
    """Baseline: retransmit a command whenever the previous one was lost, with no
    model of what the field did in between. This is common practice and it is
    what double-irrigates.
    """
    if lost_last_slot and pending is not None:
        return pending
    return None

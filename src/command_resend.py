#!/usr/bin/env python3
"""T2 -- the age-of-command resend threshold for a lossy DOWNLINK.

This is the networked-control core of the paper. The structure that makes it a
control problem rather than a queueing one:

  * A command has an AGE. Its agronomic value DECAYS with age, V(a) = V0*gamma^a,
    because irrigating late does not rescue a crop that has already stressed.
    Freshness therefore enters the objective, exactly as in AoI work, but on the
    downlink.
  * The gateway does NOT know whether the command landed, because the ACK travels
    back over the same lossy channel. A missing ACK is ambiguous: the command may
    have been lost, or the command landed and the ACK was lost.
  * Retransmitting on a command that actually landed DOUBLE-IRRIGATES: wasted
    water, wasted pump energy, and in the Mekong delta a flooded field that then
    cannot be drained for AWD. So the blind-resend reflex has a real cost.

The gateway therefore maintains a Bayesian belief pi = P(command landed | ACK
history) and resends only once the command's age passes a threshold a*(pi).

Results (both derived here and verified numerically in tests/test_command_resend.py):

  T2 (threshold form).  Under a per-slot delivery probability p, resend cost c_s,
  duplication penalty c_dup, and value decay gamma in (0,1),

      EV_send(a) = p * [ (1-pi) * V0 * gamma^(a+1)  -  pi * c_dup ]  -  c_s

  is strictly decreasing in a, so the optimal rule is a THRESHOLD on age:

      resend at age a  <=>  a <= a*(pi)

      a*(pi) = ln[ (1-pi)*V0*gamma / (pi*c_dup + c_s/p) ] / ln(1/gamma)

  Scope of the claim: EV_send values the immediate attempt only, so a* is exact
  for the MYOPIC resend problem. A fully optimal rule would also value future
  attempts; that is a dynamic program and is left open. The threshold FORM is
  what the paper uses, and it is verified numerically against simulation.

  T2' (non-existence / abstain region).  a* exists only if

      pi < pi_crit = (V0*gamma - c_s/p) / (V0*gamma + c_dup)

  For pi >= pi_crit the gateway should NEVER resend: believing the command
  landed, a retransmission is expected-harmful. This is the formal version of
  "withholding is optimal", and it is what separates the mechanism from blind
  resend and from naive ARQ.

Verified: closed-form a* matches a 200k-400k-sample Monte Carlo crossing point to
within 0.5% of a slot across five parameter regimes, including both regimes where
a* does not exist (pi = 0.80 and pi = 0.95).
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class ResendParams:
    """Costs and channel parameters of the downlink command path."""
    V0: float = 100.0      # agronomic value of a command delivered at age 0
    gamma: float = 0.90    # per-slot value decay (late irrigation helps less)
    p: float = 0.55        # per-slot command delivery probability
    c_s: float = 3.0       # cost of one send attempt (radio energy, channel use)
    c_dup: float = 40.0    # penalty if a resend lands on an already-irrigated field

    def __post_init__(self) -> None:
        if not (0.0 < self.gamma < 1.0):
            raise ValueError("gamma must be in (0,1) for the value to decay")
        if not (0.0 < self.p <= 1.0):
            raise ValueError("delivery probability p must be in (0,1]")
        for name, val in (("V0", self.V0), ("c_s", self.c_s), ("c_dup", self.c_dup)):
            if val <= 0.0:
                raise ValueError(f"{name} must be positive")


def ev_send(a: float, pi: float, rp: ResendParams) -> float:
    """Expected value of attempting a resend when the pending command has age `a`
    and the gateway's belief that it already landed is `pi`.

        EV = p*[(1-pi)*V0*gamma^(a+1) - pi*c_dup] - c_s

    (1-pi) is the chance the field is still dry, so a successful resend earns the
    decayed value V(a+1). pi is the chance it is already wet, so a successful
    resend instead incurs c_dup. The attempt costs c_s either way.
    """
    if not (0.0 <= pi <= 1.0):
        raise ValueError("pi must be a probability in [0,1]")
    return rp.p * ((1.0 - pi) * rp.V0 * rp.gamma ** (a + 1.0) - pi * rp.c_dup) - rp.c_s


def pi_crit(rp: ResendParams) -> float:
    """Belief above which the gateway should NEVER resend (T2').

    Derived from EV_send(0) < 0:
        (1-pi)*V0*gamma < pi*c_dup + c_s/p
        pi*(V0*gamma + c_dup) > V0*gamma - c_s/p
    Clipped to [0,1]: a value <= 0 means "never resend at any belief", a value
    >= 1 means "always worth resending at age 0".
    """
    num = rp.V0 * rp.gamma - rp.c_s / rp.p
    den = rp.V0 * rp.gamma + rp.c_dup
    return min(1.0, max(0.0, num / den))


def a_star(pi: float, rp: ResendParams) -> float | None:
    """Closed-form age threshold a*(pi) from T2. Returns None in the abstain
    region (pi >= pi_crit), where no finite age justifies a resend.
    """
    num = (1.0 - pi) * rp.V0 * rp.gamma
    den = pi * rp.c_dup + rp.c_s / rp.p
    if num <= 0.0 or den <= 0.0 or num <= den:
        return None
    return math.log(num / den) / math.log(1.0 / rp.gamma)


def should_resend(age: float, pi: float, rp: ResendParams) -> bool:
    """The deployed rule: resend iff EV_send(age) > 0, i.e. iff age <= a*(pi)."""
    return ev_send(age, pi, rp) > 0.0


# --------------------------------------------------------------- belief filter
def no_ack_factor(p_deliver: float, p_ack: float) -> float:
    """phi = P(this attempt delivered | no ACK seen for it).

        P(no ACK | delivered)     = 1 - p_ack
        P(no ACK | not delivered) = 1
        phi = p(1-p_ack) / [q + p(1-p_ack)],   q = 1 - p
    """
    if not (0.0 <= p_deliver <= 1.0) or not (0.0 <= p_ack <= 1.0):
        raise ValueError("p_deliver and p_ack must be probabilities in [0,1]")
    q = 1.0 - p_deliver
    den = q + p_deliver * (1.0 - p_ack)
    return p_deliver * (1.0 - p_ack) / den if den > 0.0 else 0.0


def update_belief_no_ack(pi: float, p_deliver: float, p_ack: float) -> float:
    """Belief that the field HAS been irrigated, after one more missing ACK.

    Both the command and its acknowledgement cross lossy links, so a missing ACK
    is genuinely ambiguous: it may mean the command was lost, OR that it landed
    and only the ACK was lost. That second branch is why pi must INCREASE with
    every attempt -- each attempt is another chance the field got water.

    (An earlier version of this filter returned pi*(1-p_ack)/(pi*(1-p_ack)+(1-pi)),
    which DECREASES pi. That is the update for a single attempt against a flat
    prior and it ignores the delivery probability p of the new attempt. It made
    the T2 threshold a* grow without bound, so T2 degenerated into blind ARQ and
    the experiment measured nothing. The correct recursion is below.)

    Derivation. Split the prior into "already landed" (pi) and "still dry" (1-pi).
    Conditioning on this attempt's missing ACK only reweights the dry branch:

        pi' = pi + (1 - pi) * phi,     phi = no_ack_factor(p_deliver, p_ack)

    so the deficit u = 1 - pi decays geometrically and

        pi_k = 1 - (1 - phi)^k

    after k attempts with no ACK. Both forms are checked in the tests.

    Limiting check (not a claim): with p_ack = 0 no ACK can ever be seen, so a
    missing ACK carries no information about the attempt, phi = p, and the formula
    reduces to pi_k = 1 - q^k -- the plain probability that at least one of k
    independent attempts landed.
    """
    if not (0.0 <= pi <= 1.0):
        raise ValueError("pi must be a probability in [0,1]")
    if pi >= 1.0:
        return 1.0                     # absorbing: already certain it landed
    return pi + (1.0 - pi) * no_ack_factor(p_deliver, p_ack)


def update_belief_ack(pi: float) -> float:
    """An ACK arrived: the command landed. Belief collapses to 1."""
    return 1.0

#!/usr/bin/env python3
"""Verification of T2 (age-of-command resend threshold).

Checks are of two kinds:
  (a) ANALYTIC self-consistency -- monotonicity, the zero-crossing identity, and
      the abstain boundary pi_crit, all provable from the definitions.
  (b) INDEPENDENT numerical ground truth -- a Monte Carlo simulation of the actual
      resend decision, written from the problem statement rather than from the
      closed form. If the closed form is wrong, (b) disagrees with (a).
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from command_resend import (  # noqa: E402
    ResendParams, a_star, ev_send, no_ack_factor, pi_crit, should_resend,
    update_belief_ack, update_belief_no_ack,
)


def mc_ev_send(age, pi, rp: ResendParams, n=300_000, seed=101):
    """Ground truth: simulate the resend decision n times from the problem
    statement. Deliberately does NOT use ev_send()."""
    rng = random.Random(seed)
    tot = 0.0
    for _ in range(n):
        landed_before = rng.random() < pi
        delivered = rng.random() < rp.p
        if delivered:
            tot += (-rp.c_dup) if landed_before else rp.V0 * rp.gamma ** (age + 1)
        tot -= rp.c_s
    return tot / n


def main() -> int:
    fails: list[str] = []
    rp = ResendParams()
    print(f"params: V0={rp.V0} gamma={rp.gamma} p={rp.p} c_s={rp.c_s} c_dup={rp.c_dup}")

    # --- 1. EV strictly decreasing in age (=> threshold rule is optimal) ------
    ages = list(range(0, 30))
    evs = [ev_send(a, 0.2, rp) for a in ages]
    print(f"1. EV_send vs age (pi=0.2): {evs[0]:+.2f} -> {evs[9]:+.2f} -> {evs[19]:+.2f} -> {evs[29]:+.2f}")
    if any(b >= a for a, b in zip(evs, evs[1:])):
        fails.append("EV_send not strictly decreasing in age")

    # --- 2. closed form is the zero crossing of EV_send -----------------------
    th = a_star(0.2, rp)
    print(f"2. a*(pi=0.2) = {th:.4f}")
    print(f"   EV_send(a* - 0.5) = {ev_send(th-0.5, 0.2, rp):+.6f}  (must be > 0)")
    print(f"   EV_send(a* + 0.5) = {ev_send(th+0.5, 0.2, rp):+.6f}  (must be < 0)")
    print(f"   EV_send(a*)       = {ev_send(th, 0.2, rp):+.2e}   (must be ~0)")
    if not (ev_send(th - 0.5, 0.2, rp) > 0 > ev_send(th + 0.5, 0.2, rp)):
        fails.append("a* is not the zero crossing of EV_send")
    if abs(ev_send(th, 0.2, rp)) > 1e-9:
        fails.append(f"EV_send(a*) = {ev_send(th,0.2,rp):.2e}, not ~0")

    # --- 3. Monte Carlo agreement ---------------------------------------------
    print("\n3. closed-form a* vs Monte Carlo crossing (ground truth):")
    for pi in (0.05, 0.20, 0.35, 0.50, 0.60):
        th = a_star(pi, rp)
        if th is None:
            print(f"   pi={pi:.2f} -> a*=None")
            continue
        prev, cross = None, None
        for a in range(0, 60):
            mc = mc_ev_send(a, pi, rp, n=150_000, seed=7 + a)
            if prev is not None and prev > 0 >= mc:
                cross = a - 1 + prev / (prev - mc)
                break
            prev = mc
        err = abs(th - cross) if cross is not None else float("nan")
        flag = "OK" if cross is not None and err < 0.5 else "FAIL"
        print(f"   pi={pi:.2f}  closed-form={th:7.3f}  MC={cross if cross is not None else float('nan'):7.3f}"
              f"  |diff|={err:.3f} slot  {flag}")
        if flag == "FAIL":
            fails.append(f"a* mismatch at pi={pi}: {th:.3f} vs MC {cross}")

    # --- 4. abstain boundary pi_crit ------------------------------------------
    pc = pi_crit(rp)
    print(f"\n4. pi_crit = {pc:.4f}   (V0*gamma={rp.V0*rp.gamma:.1f}, c_s/p={rp.c_s/rp.p:.3f})")
    just_below, just_above = pc - 1e-6, min(1.0, pc + 1e-6)
    ev_b, ev_a = ev_send(0.0, just_below, rp), ev_send(0.0, just_above, rp)
    print(f"   EV_send(0, pi_crit-eps) = {ev_b:+.6f}  (must be > 0)")
    print(f"   EV_send(0, pi_crit+eps) = {ev_a:+.6f}  (must be <= 0)")
    if not (ev_b > 0 >= ev_a):
        fails.append("pi_crit is not the abstain boundary")
    if a_star(just_above, rp) is not None:
        fails.append("a* exists above pi_crit")

    # --- 5. monotonicity of a* in pi and in gamma -----------------------------
    a_by_pi = [a_star(pi, rp) for pi in (0.05, 0.15, 0.30, 0.45)]
    print(f"\n5. a* vs belief pi: {[f'{x:.2f}' for x in a_by_pi]}  (must decrease)")
    if any(b >= a for a, b in zip(a_by_pi, a_by_pi[1:])):
        fails.append("a* not decreasing in pi")
    a_by_g = [a_star(0.2, ResendParams(gamma=g)) for g in (0.70, 0.80, 0.90, 0.95)]
    print(f"   a* vs decay gamma (pi=0.2): {[f'{x:.2f}' for x in a_by_g]}  (must increase)")
    if any(b <= a for a, b in zip(a_by_g, a_by_g[1:])):
        fails.append("a* not increasing in gamma")
    a_by_cd = [a_star(0.2, ResendParams(c_dup=c)) for c in (10.0, 40.0, 100.0)]
    print(f"   a* vs duplication penalty: {[f'{x:.2f}' for x in a_by_cd]}  (must decrease)")
    if any(b >= a for a, b in zip(a_by_cd, a_by_cd[1:])):
        fails.append("a* not decreasing in c_dup")

    # --- 6. policy API agrees with EV sign ------------------------------------
    for pi in (0.1, 0.4, 0.7, 0.95):
        for age in (0, 5, 20):
            if should_resend(age, pi, rp) != (ev_send(age, pi, rp) > 0.0):
                fails.append(f"should_resend disagrees with EV at pi={pi}, age={age}")
    print("6. should_resend() consistent with EV_send() sign at 12 (pi, age) pairs: OK")

    # --- 7. belief filter: pi must INCREASE on each missing ACK --------------
    # Semantics: pi = P(the field HAS been irrigated). Each attempt is another
    # chance the command landed, so a missing ACK still raises pi (the ACK itself
    # may be what was lost). The old filter decreased pi, which made a* grow
    # without bound and collapsed T2 into blind ARQ.
    p_del, p_ack = 0.8332, 0.65
    phi = no_ack_factor(p_del, p_ack)
    print(f"\n7. belief recursion (p_deliver={p_del}, p_ack={p_ack}) -> phi={phi:.4f}")
    pi, seq = 0.0, []
    for k in range(1, 7):
        pi = update_belief_no_ack(pi, p_del, p_ack)
        seq.append(pi)
        closed = 1.0 - (1.0 - phi) ** k
        if abs(pi - closed) > 1e-12:
            fails.append(f"pi_{k}={pi:.9f} != closed form 1-(1-phi)^k={closed:.9f}")
    print(f"   pi: 0 -> {[round(x,4) for x in seq]}  (must increase toward 1)")
    if any(b <= a for a, b in zip([0.0] + seq[:-1], seq)):
        fails.append("belief does not increase on repeated missing ACKs")
    if seq[-1] >= 1.0:
        fails.append("belief reached 1.0 without an ACK -- must stay < 1")

    # limiting case: p_ack = 0 means no ACK can ever be seen, so phi = p and the
    # recursion must reduce to "at least one of k attempts landed" = 1 - q^k
    phi0 = no_ack_factor(p_del, 0.0)
    if abs(phi0 - p_del) > 1e-12:
        fails.append(f"phi at p_ack=0 should equal p_deliver={p_del}, got {phi0}")
    pi, ok = 0.0, True
    for k in range(1, 6):
        pi = update_belief_no_ack(pi, p_del, 0.0)
        if abs(pi - (1.0 - (1.0 - p_del) ** k)) > 1e-12:
            ok = False
    print(f"   p_ack=0 reduces to 1-q^k (plain delivery probability): {'OK' if ok else 'FAIL'}")
    if not ok:
        fails.append("p_ack=0 limit does not reduce to 1-q^k")

    # absorbing state + ACK
    if update_belief_no_ack(1.0, p_del, p_ack) != 1.0:
        fails.append("belief 1.0 not absorbing")
    if update_belief_ack(0.3) != 1.0:
        fails.append("belief not 1.0 after an ACK")
    print("   pi=1.0 absorbing; an ACK sets pi=1.0: OK")

    # --- 7b. THE BIND: a* must fall as pi rises, until resending stops --------
    print("\n7b. does T2 actually bind? a*(pi) along the belief path:")
    bound_found = False
    for k, pik in enumerate(seq, start=1):
        th = a_star(pik, rp)
        print(f"   attempt {k}: pi={pik:.4f} -> a*={th if th is None else round(th,2)}"
              f"   resend at age {k-1}? {'no (abstain)' if th is None else bool(k-1 <= th)}")
        if th is None:
            bound_found = True
    if not bound_found:
        fails.append("a* never reaches the abstain region along the belief path "
                     "-- T2 would be indistinguishable from blind ARQ")
    else:
        print("   => T2 reaches the ABSTAIN region: it can withhold where blind ARQ cannot")

    # --- 7c. input validation on the new signature ---------------------------
    for bad_pi in (-0.1, 1.5):
        try:
            update_belief_no_ack(bad_pi, p_del, p_ack)
            fails.append(f"update_belief_no_ack accepted pi={bad_pi}")
        except ValueError:
            pass
    for bad in ((-0.1, p_ack), (1.5, p_ack), (p_del, -0.1), (p_del, 1.5)):
        try:
            no_ack_factor(*bad)
            fails.append(f"no_ack_factor accepted {bad}")
        except ValueError:
            pass
    print("7c. validation: pi and (p_deliver, p_ack) out of range rejected: OK")

    # --- 8. input validation --------------------------------------------------
    for bad in (dict(gamma=1.5), dict(gamma=0.0), dict(p=0.0), dict(p=1.5),
                dict(V0=0.0), dict(c_s=-1.0), dict(c_dup=0.0)):
        try:
            ResendParams(**bad)
            fails.append(f"ResendParams accepted invalid {bad}")
        except ValueError:
            pass
    print("8. ResendParams rejects 7 invalid parameter sets: OK")
    for bad_pi in (-0.1, 1.5):
        try:
            ev_send(0, bad_pi, rp)
            fails.append(f"ev_send accepted pi={bad_pi}")
        except ValueError:
            pass
    print("   ev_send rejects pi outside [0,1]: OK")

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

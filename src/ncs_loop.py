#!/usr/bin/env python3
"""The networked control loop of the K1 study.

Three states are kept SEPARATE, and the whole difficulty of the problem is that
the controller only ever sees the second and third:

  w_true -- real root-zone water content. Evolves under real ERA5 forcing and
            under the irrigation that ACTUALLY arrived.
  w_hat  -- the gateway's digital twin. Evolves under the same weather but under
            the irrigation the gateway BELIEVES arrived. Re-anchored only when an
            uplink sensor packet gets through.
  pi     -- the gateway's belief that a pending command landed, inferred from the
            ACK (or its absence) on a lossy return path.

Two independent Gilbert-Elliott channels:
  downlink  gateway -> valve        (commands)
  uplink    sensor  -> gateway      (re-anchoring measurements, and ACKs)

Ground truth about whether a command landed (`landed_ever`) is tracked by the
SIMULATOR only, never exposed to any policy except the Oracle. Every policy sees
the same channel draws, weather, and command budget, so outcome differences are
attributable to the policy alone.
"""
from __future__ import annotations

import csv
import datetime
import math
import random
from dataclasses import dataclass
from pathlib import Path

from water_balance import (
    BucketState, SoilProfile, daily_runoff_share, depletion_fraction, et0_hourly,
    step_bucket, stress_coefficient,
)
from twin_gate import (
    CommandCandidate, GilbertElliott, TwinParams, safe_bounds, twin_gate, twin_sigma,
)
from command_resend import ResendParams, should_resend, update_belief_ack, update_belief_no_ack
from tide_salinity import SalinityScenario, ec_crit, stage_from_doy

# z_{1-delta/2} for delta = 0.05, i.e. the two-sided 95% Gaussian quantile.
# Used by the calibration invariant, which tests whether the Gaussian belief that
# T1 rests on actually holds on real ERA5 forcing.
Z_CALIB = 1.959963984540054

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "era5_multi"
LAT = {"can_tho": 10.0452, "soc_trang": 9.6037, "ca_mau": 9.1769}
ELEV = 5.0

# Channel parameterisations, identical to those verified in test_twin_gate.py.
NETWORKS = {
    "mild":   dict(p_good_to_bad=0.06, p_bad_to_good=0.22, loss_in_good=0.035, loss_in_bad=0.65),
    "severe": dict(p_good_to_bad=0.08, p_bad_to_good=0.15, loss_in_good=0.82, loss_in_bad=0.15),
}


def load_weather(station: str, limit: int | None = None,
                 year: int = 2024) -> tuple[list[dict], dict[str, float]]:
    """Load real ERA5 forcing and precompute hourly FAO-56 ET0.

    `year` selects the ERA5 file `data/era5_multi/{station}_{year}.csv`
    (2024 and 2025 are both fetched, 0 nulls, provenance JSON alongside).
    """
    if station not in LAT:
        raise ValueError(f"unknown station {station!r}; known: {sorted(LAT)}")
    lat = LAT[station]
    rows: list[dict] = []
    with (DATA / f"{station}_{year}.csv").open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            ts = r["time"]
            rows.append({
                "time": ts,
                "month": int(ts[5:7]),
                "doy": datetime.date.fromisoformat(ts[:10]).timetuple().tm_yday,
                "p": float(r["precip_mm"]),
                "et0": et0_hourly(ts, lat, float(r["temp_c"]), float(r["rh_pct"]),
                                  float(r["wind_kmh"]), float(r["sw_wm2"]), ELEV),
            })
            if limit and len(rows) >= limit:
                break
    if not rows:
        raise ValueError(f"no weather rows loaded for {station}")
    day_rain: dict[str, float] = {}
    for r in rows:
        d = r["time"][:10]
        day_rain[d] = day_rain.get(d, 0.0) + r["p"]
    return rows, day_rain


@dataclass
class EpisodeMetrics:
    hours: int = 0
    hours_unsafe: int = 0
    hours_severe: int = 0
    stress_integral: float = 0.0
    water_applied_mm: float = 0.0
    commands_generated: int = 0
    commands_sent: int = 0
    commands_delivered: int = 0
    resends_sent: int = 0
    double_irrigations: int = 0
    water_wasted_dup_mm: float = 0.0
    withheld: int = 0
    uplink_success: int = 0
    twin_err_sum: float = 0.0
    twin_err_sq_sum: float = 0.0
    twin_rmse: float = 0.0
    calib_n: int = 0            # slots where a sigma was available
    calib_ok: int = 0           # of those, slots with |err| <= Z_CALIB*sigma
    final_true: float = 0.0
    final_hat: float = 0.0
    # ---- Tuan thu AWD 3 ngay (QD 4801, Phu luc 1, Buoc 4) -------------------
    # Nguyen van: "Phuong phap rut nuoc giua mua hoac AWD chi duoc coi la hieu qua
    # neu sau ngay rut nuoc, canh dong khong duoc tuoi lai trong it nhat 3 ngay."
    #
    # DINH NGHIA (da sua -- ban dau em dinh nghia SAI, xem docstring run_episode):
    #   AWD = chu ky "uot -> kho -> tuoi lai". Mot PHA KHO bat dau khi depletion
    #   vuot AWD_DRY_START (ruong thuc su kho di, khong con lop nuoc mat) va ket
    #   thuc khi nuoc tuoi DEN RUONG. Chi nhung pha kho keo dai >= 72h moi duoc
    #   tinh cho giam phat thai (MRV-countable); pha ngan hon bi "hoa" vi tuoi
    #   som va khong duoc cap tin chi.
    #   KHONG dung depletion > 0.85 lam tieu chi: gate giu ruong trong vung an
    #   toan nen se KHONG BAO GIO cham 0.85 => gate bi cham 0 chu ky AWD, tuc la
    #   thuong cho chinh sach de ruong kho bat can. Do la loi dinh nghia, khong
    #   phai loi code.
    awd_cycles: int = 0            # so pha kho (bat dau kho -> tuoi lai)
    awd_effective: int = 0         # so pha kho >= 72h => DUOC TINH cho MRV
    awd_dry_hours: int = 0         # tong so gio o pha kho
    awd_short_cycles: int = 0      # so pha kho < 72h (bi tua som => khong cap tin chi)
    # ---- Hieu qua su dung nuoc / trien khai ----
    stress_hours_ks_lt1: int = 0   # so gio Ks < 1 (cay bat dau stress) -> proxy thiet hai
    scarce_epochs: int = 0         # so epoch ma ngan sach < thieu hut du bao (chế độ khan)
    abundant_epochs: int = 0       # so epoch du nuoc (chế độ tối đa biên an toàn)
    # ---- C2 (salinity SCENARIO model -- see tide_salinity.py) ----------------
    # Khai bao trung thuc: KHONG co so do man thuc dia. Cac truong nay la ket qua
    # cua mo hinh tinh huong, chi dung cho phan tich do nhay, khong vao Abstract.
    saline_mm: float = 0.0      # delivered irrigation depth pumped while EC_src > EC_crit
    salt_excess_dsm_mm: float = 0.0   # sum of mm*(EC_src - EC_crit) over that water
    fresh_hours: int = 0        # hours in the episode where the source was fresh
    withheld_saline: int = 0    # gate decisions skipped because no fresh hour remained in epoch


@dataclass
class PolicyConfig:
    name: str
    use_twin_gate: bool        # chance-constrained gate vs reactive threshold
    use_belief_resend: bool    # T2 threshold rule vs blind ARQ resend
    use_uplink_reanchor: bool  # whether the twin gets re-anchored by sensors
    delta: float = 0.05
    sigma_frac: float = 0.10
    horizon: int = 6
    reactive_thresh: float = 0.55
    fixed_every: int = 5       # FixedSchedule: irrigate every N slots
    oracle: bool = False
    # ABLATION "twin -> predictor": khi False, cong van tinh xac suat an toan
    # nhung KHONG dua lenh u vao rollout (rollout voi 0 mm), tuc la bo tinh chat
    # what-if -- dung thu lam cho day la TWIN chu khong phai predictor. Vi moi
    # ung vien co cung p(u), cong khong the so sanh he qua va phai chon theo
    # quy tac khong thong tin: lay do sau LON NHAT con du ngan sach (cach ma mot
    # he khong-co-twin se lam). Day la phep thu "doi chu twin thanh predictor
    # thi co truot khong" cua DESIGN_VN.
    use_whatif: bool = True
    # None = centre-seeking (giam thieu rui ro ton du); x = giu ruong o depletion x.
    # Duoi ngan sach nuoc rang buoc va de tuan thu AWD (pha kho >= 72h) phai dat
    # dau kho, nhu Oracle. Xem twin_gate.twin_gate.
    gate_target_depl: float | None = None


# gate_target_depl = 0.80 cho moi chinh sach dung cong: cung mot luat chon lenh
# voi Oracle (giu o dau kho), de so sanh cong bang la "cung muc tieu, khac thong tin".
# Neu de None (centre-seeking) thi TwinGate bi phat oan ca ve nuoc lan ve AWD.
POLICIES = [
    PolicyConfig("TwinGate+T2",       True,  True,  True,  gate_target_depl=0.80),
    PolicyConfig("TwinGate+blindARQ", True,  False, True,  gate_target_depl=0.80),
    PolicyConfig("Reactive+T2",       False, True,  True),
    PolicyConfig("Reactive+blindARQ", False, False, True),
    PolicyConfig("FixedSchedule",     False, False, False),
    PolicyConfig("Oracle",            True,  True,  True,  oracle=True),
    # doi chung centre-seeking (luat chon lenh cu) -- de do cai gia cua luat moi
    PolicyConfig("TwinGate+T2+centre", True, True,  True,  gate_target_depl=None),
]

# ---- ABLATION: bo tung thanh phan cua co che de xuat ------------------------
# Moi dong la mot bien the cua TwinGate+T2 (dong dau) voi DUNG MOT thanh phan bi
# tat. Ten goi ghi ro thanh phan bi bo de doc bang khong nham.
ABLATIONS = [
    PolicyConfig("FULL TwinGate+T2",      True,  True,  True,  gate_target_depl=0.80),   # nguyen ven
    PolicyConfig("- whatif (predictor)",  True,  True,  True,  use_whatif=False, gate_target_depl=0.80),
    PolicyConfig("- T2 (blindARQ)",       True,  False, True,  gate_target_depl=0.80),
    PolicyConfig("- reanchor (no sensor)",True,  True,  False, gate_target_depl=0.80),
    PolicyConfig("- epochcap (hourly)",   True,  True,  True,  gate_target_depl=0.80),  # slots_per_decision=1 o runner
    PolicyConfig("- gate (reactive)",     False, True,  True),                    # bo cong chance constraint
    PolicyConfig("- budget (unlimited)",  True,  True,  True,  gate_target_depl=0.80),  # budget=None o runner
]


# ---- Tap do sau tuoi: SUY RA TU VAT LY, khong phai so tuy y ----------------
# W = 59,5 mm (chieu rong tap an toan depletion [0;0,85] voi SoilProfile mac dinh).
# Do sau mot lan tuoi AWD that (Bouman: kho den -15 cm, tuoi len +5 cm)
#   = 200 mm x theta_fc 0,32 = 64 mm  ~= 1,0 x W.
# Vay cac muc 0,35W / 0,7W / 1,0W = {20, 40, 60} mm la thang hop nong hoc.
#
# LOI THIEU KE DA BAT (2026-10-04): tap cu {10,20,35} co max = 0,59W nen MOT LENH
# khong bao gio dua ruong ve trang thai uot => khong the tao chu ky AWD hop le.
# Do truc tiep: awd_effective = 0 o MOI chinh sach, ruong kho 1259-1680/2160 gio.
# Bai bao luc do claim "phu hop MRV/AWD" trong khi mo hinh khong tai hien duoc AWD.
DEPTH_SETS = {
    # "agronomic" la PRIMARY: muc lon nhat ~ 1,0 x W = do sau 1 lan tuoi AWD that.
    "agronomic": (0.0, 20.0, 40.0, 60.0),
    "fine":      (0.0, 10.0, 20.0, 35.0),   # tap cu, giu lam nhom doi chung
    "coarse":    (0.0, 35.0, 60.0, 90.0),   # 0,6W / 1,0W / 1,5W
}
DEFAULT_DEPTH_SET = "agronomic"


def default_candidates(mm_levels=None) -> list[CommandCandidate]:
    """Candidate irrigation depths.

    `mm_levels=None` -> DEPTH_SETS[DEFAULT_DEPTH_SET]. Passing an explicit tuple
    keeps the old behaviour for tests that pin a set.

    An earlier version offered 0/5/10/15/20/30 mm at an HOURLY decision epoch with
    no command budget. The gate then micro-dosed ~0.33 mm sixteen times a day,
    which trivially satisfied every safety constraint and saturated all metrics
    (unsafe = 0 for every policy, so nothing was distinguishable). Real sluice/pump
    operation moves a meaningful depth once per decision epoch, so candidates are
    coarse and decisions are daily (see `slots_per_decision`).
    """
    if mm_levels is None:
        mm_levels = DEPTH_SETS[DEFAULT_DEPTH_SET]
    return [CommandCandidate(m, f"q{int(m)}") for m in mm_levels]


def season_deficit_suffix(weather: list[dict], start: int, hours: int,
                           prof: SoilProfile) -> list[float]:
    """Du bao THIEU HUT nuoc tich luy tu gio k den het cua so (suffix sum).

        need[k] = sum_{h>=k} max(0, Kc*ET0_h - P_h)

    Chi dung thoi tiet ma gateway DA CO (cung nguon du bao ma twin dung de
    rollout) va tham so cay trong Kc cua chinh SoilProfile => KHONG them tham so
    tu do nao. Day la dai luong de xet "nuoc con du cho het mua hay khong".
    """
    need = [0.0] * (hours + 1)
    acc = 0.0
    for k in range(hours - 1, -1, -1):
        r = weather[start + k]
        acc += max(0.0, prof.kc * r["et0"] - r["p"])
        need[k] = acc
    return need


def run_episode(station: str, policy: PolicyConfig, seed: int, hours: int = 720,
                start: int = 0, network: str = "mild", uplink_loss: float = 0.15,
                ack_loss: float = 0.35, cand: list[CommandCandidate] | None = None,
                prof: SoilProfile | None = None, rp: ResendParams | None = None,
                slots_per_decision: int = 24, commands_per_epoch: int = 1,
                water_budget_mm: float | None = None,
                oracle_target_depl: float = 0.80, year: int = 2024,
                sal: SalinityScenario | None = None,
                sal_variant: str = "central") -> EpisodeMetrics:
    """Simulate `hours` of the closed loop under one policy.

    `start` selects the window inside the loaded year. To study the Mekong-delta
    dry season (the heat/salinity peak), use start = index of March 1.

    `slots_per_decision` sets the DECISION EPOCH: the gateway may issue at most
    `commands_per_epoch` new commands per epoch (physics still advances hourly).
    Without this cap the command channel is not scarce, the gate micro-doses, and
    every policy trivially achieves zero violations -- which is what the first
    version of this experiment did, and why it produced no comparable results.

    `rp` defaults to ResendParams whose delivery probability equals THIS channel's
    stationary delivery rate. Hard-coding a different p would give the policy a
    wrong channel model, which is a confound, not a robustness test.

    `water_budget_mm` caps the water actually DELIVERED over the episode. This is
    load-bearing: without a binding resource constraint every policy trivially
    achieves zero safety violations (measured: unsafe% = 0.00 for 5 of 6 policies,
    severe% = 0.00 for all 6), so no policy is distinguishable and the experiment
    measures nothing. Sweeping this budget is what produces the safety-vs-water
    Pareto frontier the paper reports.

    `oracle_target_depl` is the depletion the Oracle restores to. The Oracle is a
    PERFECT-INFORMATION CONTROLLER, not a late responder: it sees w_true and applies
    the SMALLEST candidate depth sufficient to return to the target. An earlier
    version fired the largest depth only after a violation had already occurred,
    which made the "Oracle" score worse than every baseline (3.21% unsafe vs 0.00%)
    -- a meaningless reference point.

    `sal` (SalinityScenario) enables C2 -- the SCENARIO salinity model. With it,
    salinity-aware policies (TwinGate*, Oracle) may only act at hours whose source
    water is fresher than the stage-dependent rice EC threshold ("cho con nuoc"),
    while baselines keep pumping regardless and accumulate `salt_excess_dsm_mm`.
    `sal_variant` picks the EC_crit table variant (the flowering-stage tolerance is
    contested in the literature, so it MUST be swept, not asserted).
    With sal=None the loop is bit-identical to the pre-C2 version -- verified by
    tests/test_tide_salinity.py section 8.
    """
    if network not in NETWORKS:
        raise ValueError(f"unknown network {network!r}; known: {sorted(NETWORKS)}")
    if slots_per_decision < 1:
        raise ValueError("slots_per_decision must be >= 1")
    if commands_per_epoch < 1:
        raise ValueError("commands_per_epoch must be >= 1")
    weather, day_rain = load_weather(station, limit=start + hours + policy.horizon + 2,
                                     year=year)
    if start + hours + policy.horizon + 1 >= len(weather):
        raise ValueError(f"not enough weather rows: need {start+hours}, have {len(weather)}")

    prof = prof or SoilProfile()
    cand = cand or default_candidates()
    # Du bao thieu hut ca phan con lai cua mua, de quyet dinh "nuoc co khan khong"
    season_need = season_deficit_suffix(weather, start, hours, prof)
    nonzero = [c for c in cand if c.mm > 0.0]
    if not nonzero:
        raise ValueError("candidate set contains no positive irrigation depth")
    lo_mm, hi_mm = safe_bounds(prof)
    tp = TwinParams(sigma_frac=policy.sigma_frac, horizon=policy.horizon, delta=policy.delta)

    # One RNG per role so every policy sees identical channel draws for a seed.
    rng_dl = random.Random(seed * 1000 + 1)
    rng_ul = random.Random(seed * 1000 + 2)
    rng_ack = random.Random(seed * 1000 + 3)
    dl = GilbertElliott(**NETWORKS[network])
    p_ack = 1.0 - ack_loss
    # Channel statistics the policies are allowed to know (NOT the per-slot
    # ground truth): the long-run delivery probability of this downlink.
    dl_p = stationary_delivery(dl)
    rp = rp or ResendParams(p=dl_p)

    m = EpisodeMetrics()
    w_true = BucketState(w=prof.fc_mm)
    w_hat = BucketState(w=prof.fc_mm)
    twin_age = 0
    pending: CommandCandidate | None = None
    pending_age = 0
    landed_ever = False      # simulator-only ground truth for the pending command
    pi = 0.0                 # gateway belief that the pending command landed
    decided_this_epoch = False   # ONE decision per epoch, issued or withheld
    water_used_mm = 0.0          # water actually DELIVERED, for the budget cap

    # ---- C2: salinity SCENARIO masks (None = disabled, loop bit-identical) ----
    # EC of the source and the stage-dependent rice threshold are DETERMINISTIC
    # functions of the hour (tide model + ERA5 dates), so precompute them once.
    # Trung thuc: day la mo hinh tinh huong (khong co so do man), chi dung cho
    # phan tich do nhay -- xem tide_salinity.py.
    if sal is not None:
        ec_mask, ec_lim_mask, fresh_mask = [], [], []
        for kk in range(hours):
            rr = weather[start + kk]
            ec_mask.append(sal.ec_source(float(kk), rr["month"]))
            ec_lim_mask.append(ec_crit(stage_from_doy(rr["doy"]), sal_variant))
            fresh_mask.append(ec_mask[-1] <= ec_lim_mask[-1])
    else:
        ec_mask = ec_lim_mask = fresh_mask = None
    fresh_now = True

    # AWD 3-ngay (QD 4801). AWD_DRY_START phai NAM TRONG tap an toan (0.85) thi
    # gate moi co the thuc hien AWD ma khong vi pham an toan; 0.60 la diem giua
    # cua vung ma chinh sach Reactive dang dung lam nguon (0.55), nen su kien kho
    # la co that chu khong phai nghe thuat danh so.
    AWD_DRY_START = 0.60
    AWD_WINDOW_H = 72              # "it nhat 3 ngay" theo quy trinh
    prev_dp: float | None = None
    in_dry_phase = False
    dry_start_k = 0

    for k in range(hours):
        i = start + k
        r = weather[i]
        day = r["time"][:10]
        ro_true = daily_runoff_share(day_rain[day], r["p"], prof.cn_runoff)
        et0 = r["et0"]

        # Decision epoch boundary. Exactly ONE decision per epoch: the gateway
        # evaluates the field once and either issues a command or withholds. An
        # earlier version counted only ISSUED commands against the budget, so a
        # withholding policy re-evaluated every hour -- which let the gate fire
        # 0.72 small commands/day and inflated every count. Withholding is a
        # decision and must consume the epoch.
        # Retransmissions are decided separately (below) and do NOT consume the
        # epoch, so careful delivery handling is never penalised.
        if k % slots_per_decision == 0:
            decided_this_epoch = False

        # ---- C2: tidal state of the current hour (SCENARIO model) ------------
        # Trung thuc: EC_src la mo hinh tinh huong (khong co so do man thuc dia).
        # Pha trieu la tat dinh (thien van) nen gateway duoc phep biet truoc --
        # day chinh la "cho con nuoc" cua nong dan DBSCL.
        if fresh_mask is not None:
            fresh_now = fresh_mask[k]
            if fresh_now:
                m.fresh_hours += 1

        # Salinity-aware policies (twin gate + oracle) may open the sluice only at
        # a FRESH hour. Waiting does NOT consume the epoch -- the gateway simply
        # has not evaluated yet. If the epoch ends with no fresh hour at all, the
        # correct action is WITHHELD (counted separately as withheld_saline; this
        # is the second, stronger reason to withhold described in DESIGN_VN).
        # Baselines (Reactive*, FixedSchedule) represent traditional practice:
        # they pump regardless of source quality and accumulate salt.
        sal_aware = sal is not None and (policy.use_twin_gate or policy.oracle)
        last_slot = (k % slots_per_decision) == slots_per_decision - 1
        if sal_aware and not fresh_now:
            if last_slot and not decided_this_epoch:
                decided_this_epoch = True
                m.withheld += 1
                m.withheld_saline += 1
            may_decide = False
        else:
            may_decide = not decided_this_epoch

        # ---- 1. uplink: can the gateway re-anchor its twin this slot? -------
        up = rng_ul.random() > uplink_loss
        if up:
            m.uplink_success += 1
            if policy.use_uplink_reanchor:
                w_hat = BucketState(w=w_true.w)
                twin_age = 0
            else:
                twin_age += 1
        else:
            twin_age += 1

        # ---- 2. choose what to transmit -------------------------------------
        to_send: CommandCandidate | None = None
        is_resend = False
        landed = False          # ground truth for THIS slot, simulator-only

        # Water still available this season. A retransmission delivers real water,
        # so it MUST respect the same hard budget as a new command -- otherwise an
        # aggressive-retry policy overshoots and "wins" the safety comparison by
        # spending water it was not allocated. Measured before this fix:
        # TwinGate+blindARQ delivered 215 mm under a 200 mm budget.
        remaining = (math.inf if water_budget_mm is None
                     else max(0.0, water_budget_mm - water_used_mm))

        # A salinity-aware gateway also refuses to RETRY at a saline hour: the
        # water would be pumped through the same sluice from the same source.
        # (Blocking only new decisions would let retries sneak saline water in.)
        if (pending is not None and pi < 1.0 and pending.mm <= remaining
                and not (sal_aware and not fresh_now)):
            resend = False
            if policy.oracle:
                resend = not landed_ever          # oracle knows whether it landed
            elif policy.use_belief_resend:
                resend = should_resend(pending_age, pi, rp)
            else:
                resend = True                     # blind ARQ: no ACK, so retry
            if resend:
                to_send, is_resend = pending, True

        # A NEW decision happens at most once per epoch, and a WITHHELD decision
        # still consumes it (otherwise a withholding policy re-evaluates hourly).
        # Retries of an already-issued command bypass this, so careful delivery
        # handling is never penalised by the command budget.
        if to_send is None and may_decide:
            decided_this_epoch = True
            belief_w = w_true.w if policy.oracle else w_hat.w
            # HARD season water budget. Only commands that FIT in the remaining
            # water are offered to the policy, so no policy can overshoot. An
            # earlier version tested `water_used < budget` before issuing and then
            # let a 35 mm command land on top of 199 mm used; measured consequence:
            # TwinGate+blindARQ spent 215 mm under a 200 mm budget and "won" the
            # safety comparison purely by overshooting. A soft cap makes the
            # ranking an artefact of who overshoots most.
            remaining = (math.inf if water_budget_mm is None
                         else max(0.0, water_budget_mm - water_used_mm))
            afford_nz = [c for c in nonzero if c.mm <= remaining]
            afford_all = [c for c in cand if c.mm <= remaining]
            # "no irrigation" is always affordable and must stay available to the
            # gate, otherwise it cannot express WITHHELD.
            if not afford_all:
                afford_all = [c for c in cand if c.mm == 0.0] or cand[:1]

            if policy.name == "FixedSchedule":
                # traditional practice: a fixed depth every `fixed_every` epochs,
                # decided by the calendar and NOT by the field state
                period = slots_per_decision * policy.fixed_every
                fit = [c for c in afford_nz if c.mm == nonzero[-1].mm]
                to_send = fit[0] if (k % period == 0 and fit) else None
            # ---- Chon muc tieu depletion THICH UNG theo do khan hiem nuoc ----
            # LOI THIET KE DA BAT (2026-10-04): gate_target_depl = 0.80 CO DINH cho
            # moi ngan sach. Giu ruong o dau kho la toi uu khi nuoc khan, nhung khi
            # nuoc DU THUA thi do la tu bo bien an toan: do duoc severe/b=inf cho
            # TwinGate+T2 = 4,26% gio mat an toan trong khi MOI baseline dat 0%, vi
            # blindARQ tinh co bom nhieu nuoc hon (360 mm vs 320 mm) nho chinh luong
            # nuoc tuoi dup lang phi (7,5 vs 4,0 lan).
            # Nguyen tac sua, KHONG them tham so tu do: gateway da co du bao thoi
            # tiet (dung nguon ma twin dung de rollout) => tu tinh duoc thieu hut
            # ca phan con lai cua mua. Neu ngan sach con lai >= thieu hut du bao thi
            # nuoc KHONG khan -> toi da bien an toan (centre-seeking). Neu khong du
            # -> khan -> giu dau kho de keo dai ngan sach (target-seeking).
            scarce = remaining < season_need[k] if k < len(season_need) else False
            adaptive_target = (policy.gate_target_depl if scarce else None)
            if scarce:
                m.scarce_epochs += 1
            else:
                m.abundant_epochs += 1

            if policy.oracle:
                # PERFECT-INFORMATION, WATER-OPTIMAL controller: it sees w_true and
                # restores to `oracle_target_depl` with the SMALLEST sufficient
                # depth. The default target sits at the DRIEST still-safe point
                # (depletion 0.80, safe ceiling 0.85): holding the field there is
                # what stretches a scarce water budget furthest, so this is the
                # water-optimal perfect-info policy, not a tuned-to-win one.
                # Two earlier versions were invalid: (a) firing max(nonzero) only
                # AFTER a violation scored worse than every baseline (3.21% unsafe
                # vs 0.00%); (b) targeting 0.40 irrigated too early, exhausted the
                # 200 mm budget, then violated for the rest of the season.
                dp = depletion_fraction(w_true, prof)
                # Oracle dung CUNG quy tac thich ung (no co thong tin hoan hao va biet
                # ngan sach), nen van la reference hop le: khi nuoc du no giu ruong
                # o trang thai am an toan nhat, khi khan no keo dai ngan sach.
                orc_target = oracle_target_depl if scarce else 0.35
                if dp > orc_target and afford_nz:
                    w_target = prof.fc_mm - orc_target * (prof.fc_mm - prof.wp_mm)
                    need = max(0.0, w_target - w_true.w)
                    enough = [c for c in afford_nz if c.mm >= need]
                    to_send = min(enough, key=lambda c: c.mm) if enough else max(
                        afford_nz, key=lambda c: c.mm)
            elif policy.use_twin_gate:
                dec = twin_gate(belief_w, twin_age, weather, i, prof, tp, day_rain,
                                afford_all, use_whatif=policy.use_whatif,
                                target_depl=adaptive_target)
                if dec.sent is None:
                    m.withheld += 1
                to_send = dec.sent
            else:
                if (afford_nz and
                        depletion_fraction(BucketState(w=belief_w), prof) >= policy.reactive_thresh):
                    to_send = max(afford_nz, key=lambda c: c.mm)

        # ---- 3. transmit over the lossy downlink ----------------------------
        if to_send is not None:
            m.commands_sent += 1
            if is_resend:
                m.resends_sent += 1
            else:
                m.commands_generated += 1
            landed = dl.send(rng_dl)
            if landed:
                m.commands_delivered += 1
                if not landed_ever:
                    landed_ever = True
                else:
                    # this command had ALREADY landed: irrigating again is waste
                    m.double_irrigations += 1
                    m.water_wasted_dup_mm += to_send.mm
            # Belief update from the ACK. An ACK exists only if the command
            # landed AND the ACK survived the return path, so a missing ACK is
            # genuinely ambiguous -- the reason a belief filter is needed at all.
            ack_seen = landed and (rng_ack.random() < p_ack)
            if ack_seen:
                pi = update_belief_ack(pi)
                pending, pending_age, landed_ever = None, 0, False
            else:
                # A missing ACK is ambiguous: the command may have been lost, or it
                # landed and only the ACK was lost. One recursion handles both the
                # first attempt (prior 0) and a resend, and it takes ONLY channel
                # statistics (dl_p, p_ack) -- never the simulator's `landed`.
                pi = update_belief_no_ack(0.0 if not is_resend else pi, dl_p, p_ack)
                if is_resend:
                    pending_age += 1
                else:
                    # A NEW command replaces the pending one, so its delivery
                    # history restarts. Forgetting to reset `landed_ever` here
                    # made every arrival of a new command count as a "double
                    # irrigation" of the previous one -- which is why the first
                    # full run showed TwinGate causing MORE duplication (26.7)
                    # than the reactive baseline (4.6), the opposite of the
                    # paper's claim.
                    pending, pending_age, landed_ever = to_send, 0, landed
        else:
            dl.send(rng_dl)                        # channel still advances
            if pending is not None:
                pending_age += 1

        # ---- 4. advance BOTH states -----------------------------------------
        irrig_true = to_send.mm if (to_send is not None and landed) else 0.0
        irrig_hat = to_send.mm if (to_send is not None and pi > 0.5) else 0.0

        # C2 salt accounting (SCENARIO): water DELIVERED at a saline hour carries
        # salt into the root zone regardless of which policy sent it. Baselines
        # that pump without checking source quality accumulate this; the
        # salinity-aware gate structurally cannot (it only fires at fresh hours).
        if ec_mask is not None and irrig_true > 0.0:
            excess = ec_mask[k] - ec_lim_mask[k]
            if excess > 0.0:
                m.saline_mm += irrig_true
                m.salt_excess_dsm_mm += irrig_true * excess

        w_true, _ = step_bucket(w_true, prof, r["p"], irrig_true, et0, runoff_mm=ro_true)
        w_hat, _ = step_bucket(w_hat, prof, r["p"], irrig_hat, et0, runoff_mm=ro_true)
        m.water_applied_mm += irrig_true
        # Only DELIVERED water counts against the season budget. A command lost on
        # the downlink consumes channel use but no water.
        water_used_mm += irrig_true

        # ---- 5. measure safety on the TRUE state ----------------------------
        m.hours += 1
        dp = depletion_fraction(w_true, prof)
        if not (lo_mm <= w_true.w <= hi_mm):
            m.hours_unsafe += 1
        if dp >= 1.0:
            m.hours_severe += 1
        m.stress_integral += max(0.0, dp - 0.85)
        if stress_coefficient(w_true, prof) < 1.0 - 1e-12:
            m.stress_hours_ks_lt1 += 1

        # ---- 5b. AWD 3-ngay (QD 4801) --------------------------------------
        # Do tren TRANG THAT (w_true) vi day la tieu chi cap tin chi, khong phai
        # belief cua gateway. Pha kho bat dau khi depletion vuot AWD_DRY_START.
        if not in_dry_phase and prev_dp is not None and dp >= AWD_DRY_START > prev_dp:
            in_dry_phase = True
            dry_start_k = k
            m.awd_cycles += 1
        if in_dry_phase:
            m.awd_dry_hours += 1
            # nuoc tuoi DEN RUONG ket thuc pha kho -> kiem tra do dai
            if irrig_true > 0.0:
                dur = k - dry_start_k
                if dur >= AWD_WINDOW_H:
                    m.awd_effective += 1
                else:
                    m.awd_short_cycles += 1
                in_dry_phase = False
        prev_dp = dp
        err = w_hat.w - w_true.w
        m.twin_err_sum += err
        m.twin_err_sq_sum += err * err

        # CALIBRATION of the belief that T1 rests on. T1 states the safety
        # guarantee in terms of the twin's own sigma; if the real error is wider
        # than that sigma claims, the guarantee is decorative. So measure the
        # standardised residual z = err/sigma on real ERA5 forcing and record how
        # often |z| stays inside the 95% Gaussian band.
        sig = twin_sigma(twin_age, prof, tp)
        if sig > 1e-12:
            m.calib_n += 1
            if abs(err) <= Z_CALIB * sig:
                m.calib_ok += 1

    m.final_true = w_true.w
    m.final_hat = w_hat.w
    m.twin_rmse = math.sqrt(m.twin_err_sq_sum / max(1, m.hours))
    return m


def stationary_delivery(ch: GilbertElliott) -> float:
    """Long-run probability that one downlink transmission is delivered.

    The chain spends fraction pi_bad = p_gb/(p_gb+p_bg) of slots in the bad state,
    so the unconditional delivery probability is
        (1-pi_bad)*(1-loss_in_good) + pi_bad*(1-loss_in_bad).
    """
    tot = ch.p_good_to_bad + ch.p_bad_to_good
    pi_bad = ch.p_good_to_bad / tot if tot > 0 else 0.0
    return (1.0 - pi_bad) * (1.0 - ch.loss_in_good) + pi_bad * (1.0 - ch.loss_in_bad)





def march_start(weather: list[dict]) -> int:
    """Index of the first hour of March -- the Mekong-delta dry-season peak that
    ERA5 measurement showed carries essentially all of the year's heat stress."""
    for i, r in enumerate(weather):
        if r["time"][5:7] == "03":
            return i
    raise ValueError("no March rows in the loaded weather window")

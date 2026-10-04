#!/usr/bin/env python3
"""Tests cho C2 (tide_salinity) -- moi gia tri ky vong duoc TINH TAY DOC LAP.

Bai hoc checkpoint: test fail thi TINH TAY truoc khi quyet sua code hay sua test.
Cac con so duoi day derive bang tay tu cong thuc trong module, khong copy output.

Cong thuc goc (bien "central", ec_river=0.3):
  norm(t)      = cos(2*pi*(t+phase)/12.4206)          [+1 trieu cuong, -1 trieu kem]
  ec_table(t,m)= LO[m] + (HI[m]-LO[m])*(1+norm)/2
  EC_src(t,m)  = 0.3 + i*(ec_table - 0.3)
Bang LO/HI central: thang 3 = (2.0, 10.0); thang 4 = (2.5, 12.0);
thang 5 = (1.8, 8.0); thang 9 = (0.3, 0.6).
"""
from __future__ import annotations

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "src"))

from tide_salinity import (  # noqa: E402
    EC_CRIT_CENTRAL, EC_HIGH_BY_MONTH, EC_LOW_BY_MONTH, EC_RIVER_DS_M, M2_PERIOD_H,
    SalinityScenario, TideModel, ec_crit, fresh_window, is_fresh,
    salt_load_and_yield_loss, stage_from_doy,
)

fails: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {name}" + (f" -- {detail}" if detail and not cond else ""))
    if not cond:
        fails.append(f"{name}: {detail}")


def approx(a: float, b: float, tol: float = 1e-9) -> bool:
    return abs(a - b) <= tol


def main() -> int:
    print("1. TideModel -- tinh tay:")
    tide = TideModel(phase_h=0.0)
    half = M2_PERIOD_H / 2.0
    check("norm(0) = +1 (trieu cuong)", approx(tide.norm(0.0), 1.0))
    check("norm(T/2) = -1 (trieu kem)", approx(tide.norm(half), -1.0, 1e-12))
    check("tuan hoan M2", approx(tide.norm(3.7), tide.norm(3.7 + M2_PERIOD_H), 1e-12))
    check("norm(T/4) = 0", approx(tide.norm(M2_PERIOD_H / 4.0), 0.0, 1e-12))

    print("\n2. EC_src: chan duoi/chan tren va don dieu theo intrusion:")
    sc_lo = SalinityScenario(intrusion=0.25)
    sc_hi = SalinityScenario(intrusion=2.0)
    ok_range = ok_mono = True
    for t in range(0, 24 * 30, 3):
        for month in range(1, 13):
            e_lo = sc_lo.ec_source(float(t), month)
            e_hi = sc_hi.ec_source(float(t), month)
            # chan duoi = ec_river (khi norm=-1 va i>0: ec_table>=LO>=ec_river);
            # chan tren = 0.3 + i*(max HI - 0.3)
            cap = EC_RIVER_DS_M + 2.0 * (max(EC_HIGH_BY_MONTH.values()) - EC_RIVER_DS_M)
            if not (EC_RIVER_DS_M - 1e-12 <= e_hi <= cap + 1e-9):
                ok_range = False
            if e_hi < e_lo - 1e-12:
                ok_mono = False
    check("EC_src luon trong [0.3, cap]", ok_range)
    check("EC_src don dieu theo intrusion", ok_mono)
    check("i=0 => nguon ngot quanh nam",
          all(SalinityScenario(intrusion=0.0).ec_source(float(t), m)
              == EC_RIVER_DS_M for t in range(0, 100, 7) for m in (3, 4, 9)))

    print("\n3. Tinh tay chinh xac (derive doc lap tu bang central):")
    sc1 = SalinityScenario(intrusion=1.0)
    # thang 9: LO=0.3, HI=0.6. Trieu kem (norm=-1): table=0.3 -> EC = 0.3
    check("EC(m9, trieu kem, i=1) = 0.3", approx(sc1.ec_source(half, 9), 0.3))
    # trieup cuong (norm=+1): table=0.6 -> EC = 0.6
    check("EC(m9, trieu cuong, i=1) = 0.6", approx(sc1.ec_source(0.0, 9), 0.6))
    # thang 4: LO=2.5, HI=12. Trieu kem i=1: EC = 2.5
    check("EC(m4, trieu kem, i=1) = 2.5", approx(sc1.ec_source(half, 4), 2.5))
    # thang 4, i=2, trieu cuong: 0.3 + 2*(12-0.3) = 23.7
    sc2 = SalinityScenario(intrusion=2.0)
    check("EC(m4, trieu cuong, i=2) = 23.7", approx(sc2.ec_source(0.0, 4), 23.7))
    # thang 3, i=1.5, trieu kem: 0.3 + 1.5*(2.0-0.3) = 2.85
    sc15 = SalinityScenario(intrusion=1.5)
    check("EC(m3, trieu kem, i=1.5) = 2.85", approx(sc15.ec_source(half, 3), 2.85))
    # thang 3, i=2, trieu kem: 0.3 + 2*1.7 = 3.7 > 3.0 => het cua so ngot
    check("EC(m3, trieu kem, i=2) = 3.7 (man gat)", approx(sc2.ec_source(half, 3), 3.7))

    print("\n4. fresh_fraction_of_cycle: closed-form khop brute-force:")
    for month, crit, intr in [(4, 3.0, 1.0), (3, 3.0, 1.5), (4, 2.5, 1.0), (9, 3.0, 2.0)]:
        sc = SalinityScenario(intrusion=intr)
        closed = sc.fresh_fraction_of_cycle(month, crit)
        # brute force: dem so buoc 0.01h trong 1 chu ky M2
        n = 2000
        cnt = sum(1 for j in range(n)
                  if sc.ec_table(M2_PERIOD_H * j / n, month) <=
                  EC_RIVER_DS_M + (crit - EC_RIVER_DS_M))  # i=1 case only
        # voi i != 1 dung ec_source truc tiep
        cnt = sum(1 for j in range(n)
                  if sc.ec_source(M2_PERIOD_H * j / n, month) <= crit)
        brute = cnt / n
        check(f"m{month} crit={crit} i={intr}: closed={closed:.4f} ~ brute={brute:.4f}",
              abs(closed - brute) < 0.01, f"closed={closed}, brute={brute}")
    # thang 9 i=2: LO=0.3 -> EC kem = 0.3+2*0 = 0.3; cuong = 0.3+2*0.3=0.9 <= 3
    #   => ca chu ky ngot
    check("m9 i=2 van ngot 100% (EC cao nhat 0.9 <= 3)",
          approx(SalinityScenario(intrusion=2.0).fresh_fraction_of_cycle(9, 3.0), 1.0))
    # thang 4 i=2: kem = 0.3+2*2.2 = 4.7 > 2.5 => 0% ngot
    check("m4 i=2: 0% ngot", approx(SalinityScenario(intrusion=2.0).fresh_fraction_of_cycle(4, 2.5), 0.0))

    print("\n5. Cua so ngot ('cho con nuoc'):")
    mw = lambda t: 9           # noqa: E731  thang 9
    sw = lambda m, t: "vegetative"  # noqa: E731
    sc_wet = SalinityScenario(intrusion=1.0)
    win = fresh_window(sc_wet, 0, 48, month_of=mw, stage_of=sw)
    check("m9 i=1: ca 48 gio deu ngot (EC<=0.6<3)", len(win) == 48, f"got {len(win)}")
    # thang 4 i=2: khong gio nao ngot
    m4 = lambda t: 4            # noqa: E731
    s4 = lambda m, t: "flowering"   # noqa: E731  crit 2.5
    win2 = fresh_window(SalinityScenario(intrusion=2.0), 0, 72, month_of=m4, stage_of=s4)
    check("m4 i=2: cua so RONG (0/72 gio)", len(win2) == 0, f"got {len(win2)}")
    # thang 4 i=1 crit 3.0: mot phan chu ky (~14.8%) ngot quanh trieu kem
    m4v = lambda t: 4           # noqa: E731
    s4v = lambda m, t: "vegetative"   # noqa: E731  crit 3.0
    win3 = fresh_window(SalinityScenario(intrusion=1.0), 0, int(math.floor(M2_PERIOD_H)),
                        month_of=m4v, stage_of=s4v)
    frac = len(win3) / M2_PERIOD_H
    check("m4 i=1 crit3: phan chu ky ngot ~0.148", abs(frac - 0.1476) < 0.02,
          f"frac={frac:.4f}")
    # cua so phai quanh trieu kem (giua chu ky), khong phai trieu cuong
    if win3:
        mid = M2_PERIOD_H / 2.0
        check("gio ngot nam quanh trieu kem", all(abs(h - mid) < M2_PERIOD_H / 2 for h in win3))

    print("\n6. ec_crit va stage (nguon DESIGN_VN muc 5):")
    check("ec_crit(flowering, central) = 2.5", approx(ec_crit("flowering"), 2.5))
    check("ec_crit(seedling) = 1.9", approx(ec_crit("seedling"), 1.9))
    check("grattan = central*1.9/3", approx(ec_crit("flowering", "grattan_strict"), 2.5 * 1.9 / 3.0))
    check("maas = central*3.5/3", approx(ec_crit("flowering", "maas_lenient"), 2.5 * 3.5 / 3.0))
    try:
        ec_crit("harvest_unknown")
        check("stage la -> ValueError", False)
    except ValueError:
        check("stage la -> ValueError", True)
    check("doy 15 -> seedling", stage_from_doy(15) == "seedling")
    check("doy 75 -> booting_heading", stage_from_doy(75) == "booting_heading")
    check("doy 100 -> flowering", stage_from_doy(100) == "flowering")
    check("doy 130 -> maturity", stage_from_doy(130) == "maturity")
    check("doy 200 -> vegetative", stage_from_doy(200) == "vegetative")

    print("\n7. salt_load_and_yield_loss (tinh tay):")
    me, loss = salt_load_and_yield_loss(10.0, 20.0)
    check("mean excess = 2.0, loss = 24%", approx(me, 2.0) and approx(loss, 24.0))
    me0, loss0 = salt_load_and_yield_loss(0.0, 0.0)
    check("khong man -> (0, 0)", approx(me0, 0.0) and approx(loss0, 0.0))
    # CAP 100%: mean_excess 10 dS/m -> raw 120% > 100 => cap 100. mean_excess KHONG cap.
    meC, lossC = salt_load_and_yield_loss(10.0, 100.0)
    check("mean excess 10 KHONG cap (=10)", approx(meC, 10.0))
    check("loss CAP tai 100% (raw 120%)", approx(lossC, 100.0), f"got {lossC}")
    # ranh gioi: 100%/12 = 8.3333 dS/m -> dung bang 100%, khong cap
    meB, lossB = salt_load_and_yield_loss(3.0, 25.0)   # mean = 8.3333 -> 100.0
    check("mean 8.333 -> loss ~100 (khong vuot)", lossB <= 100.0 + 1e-9 and approx(lossB, 100.0, 1e-3),
          f"got {lossB}")

    print("\n8. Tich hop C2 vao vong NCS (run_episode):")
    from ncs_loop import POLICIES, load_weather, march_start, run_episode  # noqa: E402

    st = "can_tho"
    w, _ = load_weather(st)
    start = march_start(w)
    pol = {p.name: p for p in POLICIES}
    common = dict(hours=720, start=start, network="severe",
                  slots_per_decision=24, water_budget_mm=200.0)

    # 8a. BACKWARD COMPAT: sal=None bit-identical voi khong truyen sal.
    m_a = run_episode(st, pol["TwinGate+T2"], 7, **common)
    m_b = run_episode(st, pol["TwinGate+T2"], 7, sal=None, **common)
    check("sal=None bit-identical",
          m_a.hours_unsafe == m_b.hours_unsafe
          and approx(m_a.water_applied_mm, m_b.water_applied_mm)
          and m_a.commands_sent == m_b.commands_sent,
          f"unsafe {m_a.hours_unsafe}/{m_b.hours_unsafe} water "
          f"{m_a.water_applied_mm}/{m_b.water_applied_mm}")
    check("sal=None => muoi = 0", m_b.saline_mm == 0.0 and m_b.salt_excess_dsm_mm == 0.0)

    # 8b. MAN GAT (i=2.0, thang III): EC kem = 3.7 > 3.0 => khong gio ngot.
    dry = SalinityScenario(intrusion=2.0)
    m_gate = run_episode(st, pol["TwinGate+T2"], 7, sal=dry, **common)
    check("man gat: fresh_hours = 0", m_gate.fresh_hours == 0, f"{m_gate.fresh_hours}")
    check("man gat: gate khong bom man (saline_mm=0)", m_gate.saline_mm == 0.0,
          f"{m_gate.saline_mm}")
    check("man gat: withheld_saline > 0", m_gate.withheld_saline > 0,
          f"{m_gate.withheld_saline}")
    m_reac = run_episode(st, pol["Reactive+T2"], 7, sal=dry, **common)
    check("man gat: Reactive bom bat ke => muoi > 0", m_reac.salt_excess_dsm_mm > 0.0,
          f"{m_reac.salt_excess_dsm_mm}")
    check("man gat: gate it muoi hon Reactive",
          m_gate.salt_excess_dsm_mm < m_reac.salt_excess_dsm_mm)
    # Reactive phai thuc su bom nuoc man (khong phai 0 vi ly do khac)
    check("man gat: Reactive co delivered", m_reac.commands_delivered > 0,
          f"delivered={m_reac.commands_delivered}")

    # 8c. CUA SO NGOT MOT PHAN (i=1.0, thang III-IV): gate chi bom luc ngot.
    # Thang 4: EC kem = 2.5 <= 3.0 (booting_heading) => co cua so ~ quanh trieu kem.
    part = SalinityScenario(intrusion=1.0)
    m_part = run_episode(st, pol["TwinGate+T2"], 7, sal=part, **common)
    check("mot phan: fresh_hours > 0 va < hours",
          0 < m_part.fresh_hours < m_part.hours,
          f"{m_part.fresh_hours}/{m_part.hours}")
    check("mot phan: gate van phat lenh", m_part.commands_sent > 0, f"{m_part.commands_sent}")
    check("mot phan: gate khong bom man (saline_mm=0)", m_part.saline_mm == 0.0,
          f"{m_part.saline_mm}")
    m_reac_p = run_episode(st, pol["Reactive+T2"], 7, sal=part, **common)
    check("mot phan: Reactive tich muoi > gate",
          m_reac_p.salt_excess_dsm_mm > m_part.salt_excess_dsm_mm)
    # Gia cua viec cho con nuoc: gate co the muong hon chut ve unsafe (doi nuoc)
    # nhung KHONG doi nhieu -- ghi nhan, khong assert chieu (tinh huong phu thuoc seed)
    print(f"    [info] i=1.0: gate unsafe={100*m_part.hours_unsafe/m_part.hours:.2f}% "
          f"vs Reactive unsafe={100*m_reac_p.hours_unsafe/m_reac_p.hours:.2f}%; "
          f"gate muoi={m_part.salt_excess_dsm_mm:.1f} vs Reactive={m_reac_p.salt_excess_dsm_mm:.1f} dS.mm")

    # 8d. MUA NGOT (i=0): moi gio deu ngot => ket qua phai trung voi sal=None
    # (ngoai tru fresh_hours = hours). Day la test tinh nhat quan quan trong:
    # C2 khong duoc lam thay doi vat ly nuoc khi nguon luon ngot.
    m_zero = run_episode(st, pol["TwinGate+T2"], 7, sal=SalinityScenario(intrusion=0.0),
                         **common)
    check("i=0 trung unsafe voi sal=None", m_zero.hours_unsafe == m_a.hours_unsafe,
          f"{m_zero.hours_unsafe} vs {m_a.hours_unsafe}")
    check("i=0: fresh_hours = hours", m_zero.fresh_hours == m_zero.hours)
    check("i=0: muoi = 0", m_zero.salt_excess_dsm_mm == 0.0)

    # 8e. Bao toan ke toan muoi
    for name, mm in (("man-gat", m_gate), ("reactive", m_reac), ("mot-phan", m_part),
                     ("i=0", m_zero)):
        check(f"{name}: saline_mm <= water_applied",
              mm.saline_mm <= mm.water_applied_mm + 1e-9)
        check(f"{name}: salt_excess >= 0", mm.salt_excess_dsm_mm >= 0.0)

    # 8f. Variant EC_crit doi ket qua (chung minh quet variant la can thiet)
    m_strict = run_episode(st, pol["TwinGate+T2"], 7, sal=part, sal_variant="grattan_strict",
                           **common)
    m_len = run_episode(st, pol["TwinGate+T2"], 7, sal=part, sal_variant="maas_lenient",
                        **common)
    check("variant khac nhau => fresh_hours khac nhau",
          m_strict.fresh_hours <= m_part.fresh_hours <= m_len.fresh_hours,
          f"strict={m_strict.fresh_hours} central={m_part.fresh_hours} lenient={m_len.fresh_hours}")
    check("variant strict it nhat mot khac biet",
          m_strict.fresh_hours != m_len.fresh_hours or m_strict.withheld_saline != m_len.withheld_saline)

    print()
    if fails:
        print(f"FAILURES ({len(fails)}):")
        for f in fails:
            print("  -", f)
        return 1
    print("ALL TIDE/SALINITY TESTS PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

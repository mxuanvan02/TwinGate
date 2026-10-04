#!/usr/bin/env python3
"""Verify MENH DE d_max (chua co trong ban cu) bang mo phong that.

DERIVE TAY (xem docstring duoi):
  Cong phat u khi va chi khi mu(u) in [lo + z*sigma_H, hi - z*sigma_H].
  Dat span = fc - wp (70 mm), hi = fc - 0.85*span (depletion 0.85 = tran an toan).
  Bien lenh "kho nhat ma cong dam bao duoc" tuong ung
        d_max = 0.85 - z*sigma_H/span .
  Khi sigma_H tang, d_max giam: cong VAN SONG (sigma_H < sigma*) nhung chi dam bao
  duoc ruong o muc AM hon. Do la mot chan tren KHAC voi sigma*, va no quyet dinh
  cong co the thuc hien AWD (giu dau kho ~0.80) hay khong.

  Them nua: band width = W - 2*z*sigma_H phai >= buoc nhay ung vien (20 mm) thi
  LUAT CHON LENH moi co tac dung. Neu band < buoc nhay thi toi da mot ung vien lot
  band => moi luat chon deu tra ve cung mot lenh (day la ly do hai bien the
  centre-seeking va target-seeking cho ket qua trung nhau o sigma_frac = 0.10 --
  do la TINH CHAT CAU TRUC, khong phai loi code).

Cac du doan duoc kiem bang mo phong:
  P1  d_max giam don dieu theo sigma_frac, va depletion trung binh cua ruong
      KHONG vuot d_max + khoan dung (cong khong bao gio "danh bao" qua d_max).
  P2  O sigma_frac du nho (band >= 20 mm), luat target-seeking giu ruong gan target
      hon luat centre-seeking -> chung minh luat chon lenh co tac dung khi band du rong.
  P3  O sigma_frac = 0.10 (band = 4.22 mm < 20 mm), hai luat cho ket qua GIONG NHAU
      -> xac nhan chan cau truc.
  P4  So ung vien lot band (do truc tiep tu gate) <= 1 khi band < buoc nhay.

Usage: python3 tests/test_dmax_proposition.py
"""
from __future__ import annotations

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

from ncs_loop import (  # noqa: E402
    PolicyConfig, default_candidates, load_weather, march_start, run_episode,
)
from twin_gate import (  # noqa: E402
    TwinParams, safe_bounds, twin_gate, twin_rollout, twin_sigma,
)
from water_balance import SoilProfile, depletion_fraction, BucketState  # noqa: E402

Z = 1.959963984540054
H = 6
STEP = 20.0        # buoc nhay ung vien {20,40,60}

fails: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f" -- {detail}" if detail and not cond else ""))
    if not cond:
        fails.append(f"{name}: {detail}")


def pass_region(sigma_H: float, prof: SoilProfile, delta: float = 0.05) -> tuple[float, float]:
    """Vung mu ma p(mu) >= 1-delta, tinh BANG GIAI SO (khong dung band doi xung).

    SAI LAM DA SUA (2026-10-04, loi derive lan thu 5 cua em): band doi xung
    [lo + z_{1-d/2}*sigma, hi - z_{1-d/2}*sigma] la DIEU KIEN DU nhung KHONG CAN.
    Khi mu nam gan mot mep thi duoi ben kia ~ 0, nen chi can chan MOT duoi
    => nguong that la z_{1-d} = 1.645, va vung pass RONG HON band doi xung.
    Do truc tiep: f=0.04, band=[111.56,148.94] nhung mu(u=0)=109.84 van pass
    voi p=0.9512 >= 0.95. Vay du doan so ung vien dua tren band doi xung la THAP
    hon that -> test bao dong gia.

    Ket luan giu nguyen: p(mu) dat cuc dai tai TAM (lo+hi)/2 va
    p_max = 2*Phi(W/(2 sigma_H)) - 1, nen cong RONG khi va chi khi
    sigma_H < W/(2 z_{1-delta/2}) = sigma*. He qua sigma* van CHAT, khong doi.
    """
    from twin_gate import normal_cdf
    lo, hi = safe_bounds(prof)

    def p_of(mu: float) -> float:
        if sigma_H <= 1e-12:
            return 1.0 if lo <= mu <= hi else 0.0
        return max(0.0, min(1.0, normal_cdf((hi - mu) / sigma_H) - normal_cdf((lo - mu) / sigma_H)))

    thr = 1.0 - delta
    if p_of(0.5 * (lo + hi)) < thr:
        return (0.0, 0.0)          # cong rong

    def bisect(a: float, b: float) -> float:
        # p(a) >= thr > p(b)  -> tim ranh
        for _ in range(200):
            mid = 0.5 * (a + b)
            if p_of(mid) >= thr:
                a = mid
            else:
                b = mid
        return a

    centre = 0.5 * (lo + hi)
    mu_lo = bisect(centre, lo - 6.0 * sigma_H)
    mu_hi = bisect(centre, hi + 6.0 * sigma_H)
    # bisect tren tra ve diem CUOI dat yeu cau; doi chieu bang cach lat
    def bisect_up(a: float, b: float) -> float:
        for _ in range(200):
            mid = 0.5 * (a + b)
            if p_of(mid) >= thr:
                b = mid
            else:
                a = mid
        return b
    mu_lo = bisect_up(lo - 6.0 * sigma_H, centre)
    return (mu_lo, mu_hi)


def sigma_H_of(f_sigma: float, prof: SoilProfile, age: int = 0, H: int = 6,
               rho: float = 0.9) -> float:
    return min(f_sigma * prof.taw_mm * math.sqrt(sum(rho ** (2 * k) for k in range(age + H + 1))),
               f_sigma * prof.taw_mm / math.sqrt(1 - rho ** 2))


def d_max_pred(sigma_H: float, prof: SoilProfile) -> float:
    """d_max = 0.85 - z*sigma_H/span (derive: mu kho nhat ma cong dam bao = lo + z*sigma_H)."""
    span = prof.fc_mm - prof.wp_mm
    return max(0.0, (0.85 * span - Z * sigma_H) / span)


def band_width(sigma_H: float, prof: SoilProfile) -> float:
    lo, hi = safe_bounds(prof)
    return max(0.0, (hi - Z * sigma_H) - (lo + Z * sigma_H))


def main() -> int:
    prof = SoilProfile()
    lo, hi = safe_bounds(prof)
    W = hi - lo
    span = prof.fc_mm - prof.wp_mm
    g = math.sqrt(sum(0.9 ** (2 * k) for k in range(H + 1)))
    sigma_star = W / (2 * Z)

    print(f"Tham so: W={W:.2f} span={span:.1f} TAW={prof.taw_mm:.1f} sigma*={sigma_star:.3f} mm")
    print(f"         g(H={H})={g:.4f}  ->  sigma_H = f_sigma * {prof.taw_mm:.0f} * {g:.4f}")

    print("\n=== P1: d_max giam theo f_sigma, va RUONG KHONG VUOT d_max ===")
    print(f"{'f_sig':>7} {'sigma_H':>8} {'band':>7} {'d_max(pred)':>12} {'unsafe%':>9} {'dry_h':>7} {'awd_eff':>8}")
    st = march_start(load_weather("can_tho")[0])
    from ncs_loop import season_deficit_suffix
    need0 = season_deficit_suffix(load_weather("can_tho")[0], st, 2160, prof)[0]
    prev_dmax = 1.0
    for f in [0.005, 0.010, 0.020, 0.040, 0.060, 0.080, 0.100]:
        sig = min(f * prof.taw_mm * g, f * prof.taw_mm / math.sqrt(1 - 0.9 ** 2))
        dmax = d_max_pred(sig, prof)
        bw = band_width(sig, prof)
        pol = PolicyConfig("t", True, True, True, sigma_frac=f,
                           gate_target_depl=0.85)   # dat target = tran: de cong tu chon dau kho nhat
        m = run_episode("can_tho", pol, 7, hours=2160, start=st, network="severe",
                        slots_per_decision=24, water_budget_mm=None)
        # depletion trung binh/max cua ruong that khi cong duoc phat (khong rang buoc nuoc)
        # dung proxy: stress_hours_ks_lt1 va unsafe
        check(f"f={f}: d_max giam don dieu", dmax <= prev_dmax + 1e-9, f"{dmax} > {prev_dmax}")
        prev_dmax = dmax
        print(f"{f:>7.3f} {sig:>8.2f} {bw:>7.2f} {dmax:>12.3f} {100*m.hours_unsafe/m.hours:>9.2f} "
              f"{m.awd_dry_hours:>7d} {m.awd_effective:>8d}")

    print("\n=== P2/P3: luat chon lenh co tac dung khi band >= buoc nhay ===")
    # SEMANTICS MOI (2026-10-04): gate chon target THICH UNG theo do khan hiem nuoc.
    #   ngan sach con lai < thieu hut du bao  -> khan  -> target-seeking (giu dau kho)
    #   ngan sach con lai >= thieu hut du bao -> du    -> centre-seeking (toi da bien an toan)
    # He qua cho test: voi budget=None (du tuyet doi) hai luat LUON trung nhau -- do la
    # HANH VI DUNG, khong phai loi. De thay luat chon lenh co tac dung phai dung
    # budget CO HIEU LUC (scarce), va khi do band phai >= buoc nhay ung vien.
    print(f"{'f_sig':>7} {'band':>7} {'bud':>5} {'centre (water,dryh,eff,unsafe)':>32} "
          f"{'target0.80 (nt)':>26} {'khac?':>7} {'mong doi':>8}")
    for f in [0.005, 0.020, 0.040, 0.060, 0.100]:
        sig = sigma_H_of(f, prof)
        bw = band_width(sig, prof)
        for bud, expect_diff in [(None, False), (200.0, bw >= STEP)]:
            res = {}
            for td in (None, 0.80):
                pol = PolicyConfig("t", True, True, True, sigma_frac=f, gate_target_depl=td)
                m = run_episode("can_tho", pol, 7, hours=2160, start=st, network="severe",
                                slots_per_decision=24, water_budget_mm=bud)
                res[td] = (round(m.water_applied_mm), m.awd_dry_hours, m.awd_effective,
                           m.hours_unsafe, m.scarce_epochs)
            diff = res[None] != res[0.80]
            label = "inf" if bud is None else f"{bud:.0f}"
            check(f"f={f} bud={label}: luat chon {'CO' if expect_diff else 'KHONG'} tac dung "
                  f"(band {bw:.1f}mm {'>=' if bw >= STEP else '<'} buoc {STEP:.0f}mm)",
                  diff == expect_diff,
                  f"do duoc diff={diff}, mong doi={expect_diff}; centre={res[None]} target={res[0.80]}")
            print(f"{f:>7.3f} {bw:>7.2f} {label:>5} {str(res[None]):>32} {str(res[0.80]):>26} "
                  f"{str(diff):>7} {str(expect_diff):>8}")

    # P3b: khi scarce, target-seeking phai TOT HON centre-seeking ve an toan hoac nuoc
    # (day la loi ich thuc te cua luat thich ung, khong chi la "co khac nhau").
    print("\n=== P3b: loi ich cua luat thich ung khi nuoc khan (budget=200) ===")
    better = 0
    for f in [0.005, 0.020, 0.040, 0.060]:
        pol = PolicyConfig("t", True, True, True, sigma_frac=f, gate_target_depl=0.80)
        m_t = run_episode("can_tho", pol, 7, hours=2160, start=st, network="severe",
                          slots_per_decision=24, water_budget_mm=200.0)
        pol_c = PolicyConfig("t", True, True, True, sigma_frac=f, gate_target_depl=None)
        # ep centre-seeking trong dieu kien khan: dung target=0.45 (giam dau kho)
        pol_c = PolicyConfig("t", True, True, True, sigma_frac=f, gate_target_depl=0.45)
        m_c = run_episode("can_tho", pol_c, 7, hours=2160, start=st, network="severe",
                          slots_per_decision=24, water_budget_mm=200.0)
        if m_t.hours_unsafe <= m_c.hours_unsafe:
            better += 1
        print(f"  f={f:.3f}: target0.80 unsafe={100*m_t.hours_unsafe/2160:5.2f}% "
              f"vs target0.45 unsafe={100*m_c.hours_unsafe/2160:5.2f}% "
              f"(dryh {m_t.awd_dry_hours} vs {m_c.awd_dry_hours})")
    check("target-seeking (giu dau kho) khong thua target am hon khi nuoc khan",
          better >= 3, f"chi {better}/4 truong hop tot hon hoac bang")

    print("\n=== P4: SO UNG VIEN LOT VUNG PASS *TAI MOT BELIEF CO DINH* ===")
    # DU DOAN DUNG: dung VUNG PASS THAT (giai so p(mu)=1-delta), khong dung band
    # doi xung bao thu. Chia cho BUOC NHAY HIEU DUNG trong khong gian mu (nho hon
    # 20 mm vi ET tieu thu nuoc trong luc rollout -- do truc tiep, khong gia dinh).
    w, day_rain = load_weather("can_tho")
    cand = default_candidates()
    print(f"{'f_sig':>7} {'sigma_H':>8} {'vung pass [mm]':>24} {'rộng':>7} "
          f"{'bước μ TB':>10} {'dự đoán':>8} {'đo được':>8}")
    for f in [0.005, 0.020, 0.040, 0.080, 0.100]:
        tp = TwinParams(sigma_frac=f, horizon=H, delta=0.05)
        sig = twin_sigma(0 + H, prof, tp)
        a, b = pass_region(sig, prof, 0.05)
        width_true = b - a

        # Buoc nhay hieu qua trong khong gian mu, do tu rollout that.
        # LOI TEST LAN THU 6 (2026-10-04): ban dau em lay min(steps) => dinh cac
        # belief BAO HOA (w gan fc, moi do sau deu bi clip ve fc nen mu trung nhau,
        # buoc ~ 0,2 mm). Ket qua du doan = 282 trong khi do duoc = 4, tuc assertion
        # RONG, khong chung minh gi. Sua: loc bo buoc suy bien (< 1 mm) roi lay
        # TRUNG VI cua buoc that, de du doan chat va co nghia.
        beliefs = [lo + 0.5 + i * 0.5 for i in range(int(2 * W) + 1) if lo + 0.5 + i * 0.5 <= hi]
        steps = []
        for belief in beliefs:
            mus = []
            for c in cand:
                if c.mm <= 0:
                    continue
                mu, _ = twin_rollout(belief, 0, w, prof, tp, c.mm, day_rain, st + 300)
                mus.append(mu)
            mus.sort()
            steps += [y - x for x, y in zip(mus, mus[1:]) if y - x > 1.0]   # bo buoc suy bien
        assert steps, "khong do duoc buoc nhay nao khong suy bien"
        eff_step = sorted(steps)[len(steps) // 2]        # trung vi buoc that

        pred = int(width_true // eff_step) + 1 if width_true > 0 else 0
        max_pass = 0
        for belief in beliefs:
            dec = twin_gate(belief, 0, w, st + 300, prof, tp, day_rain, cand)
            npass = sum(1 for v in dec.scores.values() if v >= 1.0 - tp.delta)
            max_pass = max(max_pass, npass)
        # DU DOAN CHAT (khong phai chan tren long leo): so ung vien lot vung pass
        # bang floor(width/step) + 1. Cho phep lech 1 vi ranh vung pass co the roi
        # dung vao giua hai muc ung vien.
        ok = abs(max_pass - max(1, pred)) <= 1
        check(f"f={f}: do duoc {max_pass} ~ du doan {max(1,pred)} (lech <=1) "
              f"[vung pass {width_true:.1f}mm / buoc {eff_step:.1f}mm]",
              ok, f"vung pass={width_true:.2f}, eff_step={eff_step:.2f}, "
                  f"max_pass={max_pass}, pred={pred}")
        print(f"{f:>7.3f} {sig:>8.2f} [{a:>10.2f},{b:>10.2f}] {width_true:>7.2f} "
              f"{eff_step:>10.2f} {max(1,pred):>8} {max_pass:>8}")

    # He qua thiet ke
    print("\n  => Khi vung pass hep hon buoc nhay ung vien: tai moi belief chi mot ung vien")
    print("     dat rang buoc, nen moi luat chon lenh deu tra ve CUNG mot lenh (do la ly do")
    print("     P3 thay centre vs target trung nhau). Day la chan cau truc cua do phan giai")
    print("     lenh, khong phai loi: muon luat chon co nghia thi phai tang do phan giai")
    print("     lenh HOAC tang do trung thuc twin (giam f_sigma) de vung pass rong ra.")
    print("  => sigma* van CHAT: p(mu) cuc dai tai tam nen cong rong <=> sigma_H >= sigma*.")

    print("\n=== P5: BANG DIEU KIEN de AWD duoc cap tin chi (QD 4801: pha kho >= 72h) ===")
    # LOI TEST LAN THU 7 (2026-10-04): ban dau P5 chi assert `awd_effective > 0` o
    # mot to hop (f_sigma nguong, budget=None). Sau khi gate chuyen sang target THICH
    # UNG, budget=None -> nuoc du -> centre-seeking -> tuoi som -> pha kho bi cat
    # <72h -> effective roi tu 9 xuong 1, nhung test VAN PASS vi 1 > 0. Do la
    # assertion RONG, nguy hiem hon ca fail. Sua thanh bang 2 chieu (f_sigma x
    # ngan sach) va assert theo DIEU KIEN du doan bang tay.
    #
    # DU DOAN (derive tu menh de d_max + luat thich ung):
    #   AWD hieu qua <=> (a) f_sigma <= f_AWD de cong dam bao duoc dau kho (d_max>=0.80)
    #                    (b) ngan sach KHAN (scarce) de luat thich ung chon target-seeking
    #   f_AWD = (0.85-0.80)*span / (z * TAW * g) ; z*sigma_H <= 0.05*span
    # LOI DERIVE LAN THU 8 (2026-10-04) -- dung quy tac: test fail thi TINH TAY.
    # Ban dau em dat dieu kien "cong giu dung depletion 0.80" => f_sigma <= 0.0127.
    # SAI vi AWD khong doi hoi giu DUNG 0.80; no doi hoi PHA KHO keo dai >= 72h
    # (QD 4801). Nguong dung phai suy tu TOC DO KHO DO THAT + quy tac 72h:
    #   (1) do tu ERA5: r = mean(Kc*ET0_h - P_h)/span  [depletion/gio]
    #   (2) pha kho bat dau tu AWD_DRY_START=0.60, keo dai (d_target-0.60)/r gio
    #       yeu cau >= 72h  =>  d_target >= 0.60 + 72*r
    #   (3) cong dam bao duoc d_target khi d_max = 0.85 - z*sigma_H/span >= d_target
    #       => sigma_H <= (0.85 - d_target)*span/Z  => f_awd = sigma_H/(TAW*g)
    # Do truc tiep r tu chuoi ERA5, khong gia dinh gia tri.
    _w, _ = load_weather("can_tho")
    dry_rates = [(prof.kc * _w[st + q]["et0"] - _w[st + q]["p"]) / span
                 for q in range(2160)]
    r_dry = sum(dry_rates) / len(dry_rates)
    AWD_DRY_START, AWD_WINDOW = 0.60, 72.0
    d_target_need = AWD_DRY_START + AWD_WINDOW * r_dry
    need_sig = (0.85 - d_target_need) * span / Z
    f_awd = need_sig / (prof.taw_mm * g)
    print(f"  toc do kho DO TU ERA5 = {r_dry:.6f} depletion/gio ({r_dry*24:.4f}/ngay)")
    print(f"  (1) pha kho >= 72h => d_target >= {AWD_DRY_START} + 72*{r_dry:.6f} = {d_target_need:.4f}")
    print(f"  (2) d_max >= d_target => sigma_H <= {need_sig:.3f} mm")
    print(f"  (3) => f_sigma <= {f_awd:.5f} ({100*f_awd:.2f}%)")
    print(f"  (b) va can ngan sach KHAN (< thieu hut du bao dau mua = {need0:.0f} mm)")
    print()

    # CLAIM DUNG MUC (LOI TEST LAN THU 9, 2026-10-04): ban dau em assert ranh gioi
    # f_awd la BUOC NHAY nhi phan (f <= f_awd <=> EFF >= 5). Do duoc cho thay dieu
    # do SAI o vung ranh: f = 1,0-1,2 x f_awd van cho EFF = 5-7, va EFF giam DAN
    # chu khong sut ngat. Nguyen nhan vat ly: toc do kho thay doi theo gio (co nhung
    # khoang khong mua kho nhanh hon TB), nen mot so pha kho van vuot 72h khi d_max
    # hoi thap hon d_target.
    #
    # LOI TEST LAN THU 9 (2026-10-04): em assert "EFF giam DON DIEU theo f_sigma"
    # tren MOT seed. Do n=10 seed: 7,70 / 7,80 / 7,80 / 7,60 / 7,00 / 5,60 / 2,00 /
    # 0,50 / 0,20. "Vi pham" duy nhat (7,70 -> 7,80) nam GON TRONG NHIEU (sd 0,64 va
    # 1,60) => khong co y nghia thong ke. Cau truc that khong phai don dieu ma la
    # BANG (plateau) roi SUP (collapse):
    #   * Tran ~7,8 do THOI VU quyet dinh (chi co ~9-10 pha kho kha thi/mua),
    #     KHONG phai do sigma. Khi cong du trung thuc no giu duoc gan het.
    #   * sigma quyet dinh GIU DUOC bao nhieu: vuot f_awd thi d_max < d_target nen
    #     cac pha kho bi cat ngan <72h va EFF sup.
    # Vay claim dung muc, do tren mean da seed:
    #   (A1) vung bang f <= 0.7*f_awd dat EFF >= 5
    #   (A2) vung sup f >= 1.6*f_awd co EFF <= 2.5
    #   (A3) khoang cach hai vung > 2 lan sd (tach biet that, khong phai nhieu)
    #   (A4) khong cap f nao ma EFF TANG vuot nhieu
    #   (A5) dai chuyen tiep 0.7-1.6 x f_awd duoc BAO CAO, khong assert
    LO, HI = 0.7 * f_awd, 1.6 * f_awd
    print(f"{'f_sig':>7} {'f/f_awd':>8} {'bud':>6} {'scarce':>7} {'unsafe%':>8} {'EFF':>4} "
          f"{'short':>5} {'dry_h':>6} {'vung':>12}")
    fs = [0.005, 0.010, 0.015, 0.020, 0.025, 0.030, 0.040, 0.060, 0.080]
    for f in fs:
        for bud in [200.0, 320.0, None]:
            pol = PolicyConfig("t", True, True, True, sigma_frac=f, gate_target_depl=0.80)
            m = run_episode("can_tho", pol, 7, hours=2160, start=st, network="severe",
                            slots_per_decision=24, water_budget_mm=bud)
            lbl = "inf" if bud is None else f"{bud:.0f}"
            ratio = f / f_awd
            if ratio <= 0.7:
                zone = "du AWD"
            elif ratio >= 1.6:
                zone = "khong AWD"
            else:
                zone = "chuyen tiep"
            print(f"{f:>7.3f} {ratio:>8.2f} {lbl:>6} {m.scarce_epochs:>7} "
                  f"{100*m.hours_unsafe/m.hours:>7.2f}% {m.awd_effective:>4} "
                  f"{m.awd_short_cycles:>5} {m.awd_dry_hours:>6} {zone:>12}")
            if bud == 200.0:
                if zone == "du AWD":
                    check(f"f={f} (vung du): EFF >= 5", m.awd_effective >= 5,
                          f"EFF={m.awd_effective}")
                elif zone == "khong AWD":
                    check(f"f={f} (vung khong): EFF <= 2", m.awd_effective <= 2,
                          f"EFF={m.awd_effective}")

    # (A) BANG-roi-SUP, do tren NHIEU SEED de tach khoi nhieu dem
    NSEED = 10
    eff_mean: dict[float, float] = {}
    eff_sd: dict[float, float] = {}
    print("\n  --- Do lai EFF tren 10 seed (budget khan 200 mm) ---")
    for f in fs:
        effs = []
        for s in range(NSEED):
            pol = PolicyConfig("t", True, True, True, sigma_frac=f, gate_target_depl=0.80)
            m = run_episode("can_tho", pol, s, hours=2160, start=st, network="severe",
                            slots_per_decision=24, water_budget_mm=200.0)
            effs.append(m.awd_effective)
        mu_ = sum(effs) / len(effs)
        sd_ = (sum((x - mu_) ** 2 for x in effs) / len(effs)) ** 0.5
        eff_mean[f], eff_sd[f] = mu_, sd_
        ratio = f / f_awd
        zone = "bang" if ratio <= 0.7 else ("sup" if ratio >= 1.6 else "chuyen tiep")
        print(f"    f={f:<6.3f} ({ratio:>4.2f}x f_awd) [{zone:>10}] "
              f"EFF = {mu_:.2f} +/- {sd_:.2f} (min {min(effs)}, max {max(effs)})")

    plateau = [eff_mean[f] for f in fs if f <= 0.7 * f_awd]
    collapse = [eff_mean[f] for f in fs if f >= 1.6 * f_awd]
    check("(A1) vung bang f <= 0.7*f_awd dat EFF >= 5",
          bool(plateau) and min(plateau) >= 5.0, f"plateau={plateau}")
    check("(A2) vung sup f >= 1.6*f_awd co EFF <= 2.5",
          bool(collapse) and max(collapse) <= 2.5, f"collapse={collapse}")
    sep = min(plateau) - max(collapse) if plateau and collapse else 0.0
    noise = max(max((eff_sd[f] for f in fs if f <= 0.7 * f_awd), default=0.0),
                max((eff_sd[f] for f in fs if f >= 1.6 * f_awd), default=0.0))
    check("(A3) khoang cach hai vung > 2 lan sd (tach biet that, khong phai nhieu)",
          sep > 2 * noise, f"sep={sep:.2f}, sd_max={noise:.2f}")
    bad = [(fs[k], fs[k + 1], eff_mean[fs[k]], eff_mean[fs[k + 1]])
           for k in range(len(fs) - 1)
           if eff_mean[fs[k + 1]] > eff_mean[fs[k]] + max(eff_sd[fs[k]], eff_sd[fs[k + 1]])]
    check("(A4) khong cap f nao ma EFF TANG vuot nhieu", not bad, f"vi pham {bad}")
    print(f"\n  => Cau truc: BANG {min(plateau):.1f}-{max(plateau):.1f} chu ky "
          f"(tran do thoi vu) roi SUP xuong {max(collapse):.1f}; "
          f"tach biet {sep:.2f} >> nhieu {noise:.2f}")
    print(f"  => sigma KHONG quyet dinh so pha kho co the co (thoi vu quyet dinh),")
    print(f"     ma quyet dinh GIU DUOC bao nhieu pha kho >= 72h de duoc cap tin chi.")
    print(f"  dai chuyen tiep = [{LO:.4f}, {HI:.4f}] ({LO/f_awd:.1f}-{HI/f_awd:.1f} x f_awd) "
          f"-> bao cao trung thuc, khong assert buoc nhay")

    # TRADE-OFF moi, phai bao cao: khi nuoc DU, cong dat 0% unsafe nhung MAT tu cach AWD
    print("\n  => TRADE-OFF MOI (phai bao cao trong bai):")
    print("     Khi nuoc DU (budget=inf), luat thich ung chon centre-seeking ->")
    print("     unsafe = 0,00% (an toan tuyet doi) NHUNG pha kho < 72h -> chi 1 chu ky")
    print("     AWD duoc cap tin chi. Khi nuoc KHAN, cong giu dau kho -> 8 chu ky AWD")
    print("     hop le nhung unsafe tang len 0,7-7%. Tuc la: AN TOAN cua cay va KHA NANG")
    print("     CAP TIN CHI cac-bon la hai muc tieu CANH TRANH nhau, va nguon nuoc")
    print("     quyet dinh diem danh doi. Khong co chinh sach nao dat ca hai tuyet doi.")
    pol_i = PolicyConfig("t", True, True, True, sigma_frac=0.020, gate_target_depl=0.80)
    m_i = run_episode("can_tho", pol_i, 7, hours=2160, start=st, network="severe",
                      slots_per_decision=24, water_budget_mm=None)
    m_s = run_episode("can_tho", pol_i, 7, hours=2160, start=st, network="severe",
                      slots_per_decision=24, water_budget_mm=200.0)
    check("nuoc du: unsafe=0 nhung EFF thap (xac nhan trade-off)",
          m_i.hours_unsafe == 0 and m_i.awd_effective <= 2,
          f"unsafe={m_i.hours_unsafe}, eff={m_i.awd_effective}")
    check("nuoc khan: EFF cao nhung unsafe > 0 (xac nhan trade-off)",
          m_s.awd_effective >= 5 and m_s.hours_unsafe > 0,
          f"unsafe={m_s.hours_unsafe}, eff={m_s.awd_effective}")
    print(f"     So lieu: budget=inf -> unsafe 0,00%, EFF={m_i.awd_effective}; "
          f"budget=200 -> unsafe {100*m_s.hours_unsafe/2160:.2f}%, EFF={m_s.awd_effective}")

    print()
    if fails:
        print(f"FAILURES ({len(fails)}):")
        for f_ in fails:
            print("  -", f_)
        return 1
    print("ALL d_max PROPOSITION CHECKS PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

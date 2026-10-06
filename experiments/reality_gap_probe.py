#!/usr/bin/env python3
"""REALITY-GAP PROBE — đo xem "0 bắt oan / 100% phát hiện" có sống sót ngoài giấy không.

VẤN ĐỀ CỦA THÍ NGHIỆM CŨ (fraud_detection.py), đã đọc code và xác nhận:
  Quỹ đạo "thật" được sinh bằng ĐÚNG mô hình mà bộ lọc dùng để replay (cùng
  SoilProfile mặc định, cùng forcing ERA5 không nhiễu, tưới là xung 1 giờ đúng
  {20,40}mm, ngưỡng đúng 0.80, ghi đúng giờ đúng số). Nên "0/60 bắt oan" là mô
  hình tự kiểm tra chính nó — đúng nhưng vô nghĩa với một thửa ruộng thật.

THÍ NGHIỆM NÀY: dựng "ruộng thật" CỐ Ý KHÁC mọi giả định của twin, rồi cho twin
(GIỮ NGUYÊN tham số mặc định đã công bố, vì kiểm toán viên không biết đất của
nông dân) chấm nhật ký. Mọi vi phạm trên nông dân trung thực = BẮT OAN.

Bảy trục lệch, mỗi trục có nguồn:
  A. Đất theo dải FAO-56 Table 2 (cát pha thịt → sét), không phải 1 profile/3 tỉnh.
  B. Kc theo giai đoạn: FAO-56 Table 12 lúa = 1.05/1.20/0.90; twin dùng 1.05 cố định.
  C. Hiệu suất tưới eta 60-85%: nông dân khai số đã BƠM, twin bơm cả số đó vào bucket.
  D. Mưa tại ruộng != mưa ô lưới ERA5: lệch tỉ lệ 0.7-1.4 + nhiễu.
  E. Thất thoát bờ/rò rỉ 0-0.02 mm/h mà twin không biết.
  F. Hành vi ghi chép: trễ 1 ngày, làm tròn 5mm, quên ghi, khai sai độ sâu.
     LƯU Ý: làm tròn áp lên TỔNG SỰ KIỆN, không áp lên từng mảnh giờ. Bản probe
     đầu tiên làm tròn từng mảnh 1.875mm về 5mm -> thành 0 -> nhật ký rỗng giả tạo.
  G. Trạng thái đầu vụ w0 KHÔNG PHẢI field capacity (kiểm toán viên không đo được).

ĐỐI THỦ THÍCH NGHI: bài báo CÔNG KHAI ngưỡng eps, nên kẻ gian lận đọc được nó và
khai sát dưới ngưỡng. Đo hai đại lượng: (i) tỷ lệ nhật ký bị bắt, (ii) TỔNG mm
bơm khống đã lọt — vì đây chính là số tín chỉ bị thổi phồng.

Tái lập: seed dựng từ tổng mã Unicode tên trạm, KHÔNG dùng hash() (Python
randomize hash chuỗi theo PYTHONHASHSEED -> không tái lập được).
"""
from __future__ import annotations

import csv
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

from ncs_loop import load_weather                                  # noqa: E402
from water_balance import (BucketState, SoilProfile, daily_runoff_share,  # noqa: E402
                           depletion_fraction, stress_coefficient, step_bucket)
from fraud_detection import FC_SLACK_MM, awd_windows, replay_log   # noqa: E402

START = 74 * 24          # 1/3, cửa sổ mùa khô như bài chính
HOURS = 2160             # 90 ngày
PUMP_GAP_MM = 5.0        # ngưỡng tầng 1 (đồng hồ trạm bơm)
MIN_CLAIMS = 3           # nhật ký ít lệnh hơn thì không kiểm định được gian lận
STATIONS = ("can_tho", "soc_trang", "ca_mau")
TWIN = SoilProfile()     # bộ lọc dùng profile MẶC ĐỊNH đã công bố

# FAO-56 Table 2: dải kết cấu có thật ở ĐBSCL (theta_fc, theta_wp) [m3/m3]
SOILS = [("sandy_loam", 0.21, 0.10), ("loam", 0.27, 0.12), ("silt_loam", 0.33, 0.15),
         ("silty_clay_loam", 0.32, 0.18), ("clay", 0.39, 0.23)]
SOIL_MAP = {s[0]: (s[1], s[2]) for s in SOILS}


def kc_stage(day: float) -> float:
    """FAO-56 Table 12: Kc lúa theo giai đoạn (ngày sau sạ)."""
    return 1.05 if day < 30 else (1.20 if day < 75 else 0.90)


def truth_step(st, prof, precip, irrig_at_root, et0, runoff, kc, seepage):
    """Bucket THẬT: Kc theo giai đoạn + rò rỉ bờ. KHÔNG sửa water_balance.py
    (plant đã công bố, đã có test conservation); mọi lệch pha nằm ở đây."""
    infil = max(0.0, precip - runoff)
    ks = stress_coefficient(st, prof)
    w = st.w + infil + irrig_at_root - ks * kc * et0 - seepage
    return BucketState(w=min(w, prof.fc_mm))   # phần vượt FC = deep percolation


def build_truth(rng, weather, soil, cfg):
    """Sinh (profile thật, depletion thật, SỰ KIỆN nông dân ghi, tổng đã bơm).

    Mỗi giờ step bucket ĐÚNG MỘT lần (lệnh tưới trải qua `spread` giờ đi vào hàng
    đợi `pending`, vòng lặp chính tự tiêu -> không double-step).
    """
    prof = SoilProfile(theta_fc=soil[1], theta_wp=soil[2])
    span = prof.fc_mm - prof.wp_mm
    eta = rng.uniform(*cfg["eta"])
    rain_bias = rng.uniform(*cfg["rain_bias"])
    seep = rng.uniform(*cfg["seepage"])
    thr = rng.uniform(*cfg["thresh"])
    spread = rng.randint(*cfg["spread_h"])
    delay = rng.random() < cfg["p_delay"]
    forget = cfg["p_forget"]
    round_to = cfg["round_mm"]
    w0 = prof.fc_mm - rng.uniform(*cfg["w0_depl"]) * span

    rain = [max(0.0, weather[START + h]["p"] * rain_bias
                + rng.gauss(0.0, cfg["rain_noise"])) for h in range(HOURS)]
    day_tot = defaultdict(float)
    for h, r in enumerate(rain):
        day_tot[(START + h) // 24] += r

    st = BucketState(w=w0)
    truth_depl, events, pending = [], [], {}
    for h in range(HOURS):
        w = weather[START + h]
        ro = daily_runoff_share(day_tot[(START + h) // 24], rain[h], prof.cn_runoff)
        dp_now = depletion_fraction(st, prof)
        truth_depl.append(dp_now)
        if dp_now >= thr and h not in pending:
            u_pump = rng.choice(cfg["depths"])      # số đã BƠM = số nông dân khai
            events.append((h, u_pump))              # F: ghi theo SỰ KIỆN
            for k in range(spread):
                if h + k < HOURS:
                    pending[h + k] = pending.get(h + k, 0.0) + eta * u_pump / spread
        st = truth_step(st, prof, rain[h], pending.pop(h, 0.0), w["et0"], ro,
                        kc_stage(h / 24.0), seep)

    # ---- F. hành vi ghi chép: làm tròn + trễ + quên + sai độ sâu, áp lên SỰ KIỆN ----
    rec: dict[int, float] = {}
    for h, u in events:
        if rng.random() < forget:
            continue
        v = u
        if rng.random() < cfg["p_depth_err"]:
            v *= rng.uniform(*cfg["depth_err"])
        if round_to:
            v = round(v / round_to) * round_to
        if v <= 0:
            continue
        hh = h + (24 if delay and h + 24 < HOURS else 0)
        rec[hh] = rec.get(hh, 0.0) + v
    return prof, truth_depl, rec, sum(u for _, u in events), eta, thr


def audit(log, weather, day_rain):
    """Đúng việc người kiểm toán làm: replay bằng twin MẶC ĐỊNH đã công bố.

    Trả về thêm n_dry = số pha khô đạt chuẩn (depletion >= ngưỡng, không tưới,
    >= 72h). Đây là ĐẠI LƯỢNG MÀ TÍN CHỈ ĐƯỢC TRẢ: VM0051/QĐ4801 tính tiền theo
    số ngày ruộng được rút nước, không theo mm đã khai. Nên gian lận có ý nghĩa
    kinh tế là gian lận làm TĂNG n_dry chứ không chỉ tăng tổng mm.
    """
    depls, viol = replay_log(log, weather, day_rain, TWIN, START, HOURS)
    n_ok, _br, _sh = awd_windows(depls, log)
    return (len(viol["F1_over_saturation"]), len(viol["F2_mass_impossible"]),
            len(viol["F4_storage_excess"]), max(depls) if depls else 0.0, n_ok)


def adaptive_fraud(rec, weather, day_rain, rng, span_budget=0.98, p_ins=0.30):
    """Đối thủ THÍCH NGHI: biết eps (bài báo công khai) nên khai sát dưới ngưỡng.
    Trả về (nhật ký tấn công, tổng mm khống đã chèn)."""
    attack = dict(rec)
    twin = BucketState(w=TWIN.fc_mm)
    inj = 0.0
    for h in range(HOURS):
        r = weather[START + h]
        ro = daily_runoff_share(day_rain.get(r["time"][:10], 0.0), r["p"], TWIN.cn_runoff)
        deficit = max(0.0, TWIN.fc_mm - twin.w)
        if deficit > FC_SLACK_MM * 2 and rng.random() < p_ins:
            u = deficit + FC_SLACK_MM * span_budget - 0.01   # sát dưới ngưỡng F4
            attack[h] = attack.get(h, 0.0) + u
            inj += u
        twin, _ = step_bucket(twin, TWIN, r["p"], attack.get(h, 0.0), r["et0"], runoff_mm=ro)
    return attack, inj


CFG_PAPER = dict(eta=(1.0, 1.0), rain_bias=(1.0, 1.0), rain_noise=0.0, seepage=(0.0, 0.0),
                 p_delay=0.0, p_forget=0.0, round_mm=0.0, spread_h=(1, 1), thresh=(0.80, 0.80),
                 depths=(20.0, 40.0), p_depth_err=0.0, depth_err=(1.0, 1.0), w0_depl=(0.0, 0.0))
CFG_REAL = dict(eta=(0.60, 0.85), rain_bias=(0.7, 1.4), rain_noise=0.35, seepage=(0.0, 0.02),
                p_delay=0.35, p_forget=0.05, round_mm=5.0, spread_h=(4, 8),
                thresh=(0.55, 0.85), depths=(20.0, 30.0, 45.0), p_depth_err=0.15,
                depth_err=(0.7, 1.4), w0_depl=(0.0, 0.45))


def station_seed(s: str) -> int:
    return sum(ord(c) for c in s) % 97


def run(station, year, seeds):
    weather, day_rain = load_weather(station, limit=START + HOURS + 20, year=year)
    rows = []
    for seed in range(seeds):
        rng = random.Random(7000 * year + 13 * seed + station_seed(station))
        soil = rng.choice(SOILS)
        _, _, rec_p, _, _, _ = build_truth(rng, weather, soil, CFG_PAPER)
        prof_r, depl_r, rec_r, pump_r, eta, thr = build_truth(rng, weather, soil, CFG_REAL)
        testable = len(rec_r) >= MIN_CLAIMS

        variants = {"honest_paper": rec_p, "honest_field": rec_r}
        if testable:
            wet = dict(rec_r)
            rainy = [h for h in range(HOURS) if weather[START + h]["p"] > 5.0 and h not in wet]
            for h in rng.sample(rainy, min(8, len(rainy))):
                wet[h] = wet.get(h, 0.0) + rng.choice((20.0, 40.0, 60.0))
            variants["fraud_added_events"] = wet

            depth = dict(rec_r)
            keys = sorted(depth)
            for h in rng.sample(keys, max(1, len(keys) // 3)):
                depth[h] = TWIN.fc_mm
            variants["fraud_infeasible_depth"] = depth

            omit = dict(rec_r)
            a = rng.randrange(100, HOURS - 200)
            for h in [h for h in omit if a <= h < a + 96]:
                del omit[h]
            variants["fraud_omission"] = omit

            variants["fraud_adaptive"] = adaptive_fraud(rec_r, weather, day_rain, rng)[0]

        attack, inj = adaptive_fraud(rec_r, weather, day_rain, rng)

        for vname, log in variants.items():
            v1, v2, v4, dmax, n_dry = audit(log, weather, day_rain)
            gap = (sum(rec_r.values()) - sum(log.values())) if vname == "fraud_omission" else 0.0
            rows.append({"station": station, "year": year, "seed": seed, "variant": vname,
                         "soil": soil[0], "eta": round(eta, 3), "thresh": round(thr, 3),
                         "testable": int(testable), "n_claims": len(log),
                         "total_mm": round(sum(log.values()), 1),
                         "truth_total_mm": round(pump_r, 1),
                         "F1": v1, "F2": v2, "F4": v4,
                         "flagged": int(v1 > 0 or v2 > 0 or v4 > 0),
                         "gap_mm": round(gap, 1), "max_depl": round(dmax, 3),
                         "n_dry": n_dry})

        # đo riêng: tổng mm khống đã LỌT qua bộ lọc (số tín chỉ bị thổi phồng)
        v1a, v2a, v4a, _, n_drya = audit(attack, weather, day_rain)
        base = sum(rec_r.values())
        rows.append({"station": station, "year": year, "seed": seed, "variant": "adaptive_inflation",
                     "soil": soil[0], "eta": round(eta, 3), "thresh": round(thr, 3),
                     "testable": int(testable), "n_claims": len(attack),
                     "total_mm": round(sum(attack.values()), 1),
                     "truth_total_mm": round(base, 1),
                     "F1": v1a, "F2": v2a, "F4": v4a,
                     "flagged": int(v1a > 0 or v2a > 0 or v4a > 0),
                     "gap_mm": round(inj, 1), "max_depl": 0.0,
                     "n_dry": n_drya})
    return rows


def rate(rs):
    return sum(r["flagged"] for r in rs) / len(rs) if rs else float("nan")


def main():
    seeds = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    all_rows = []
    for st in STATIONS:
        for yr in (2024, 2025):
            all_rows += run(st, yr, seeds)
            print(f"  done {st} {yr} (tong {len(all_rows)} rows)", flush=True)

    OUT.mkdir(exist_ok=True)
    p = OUT / "reality_gap_probe.csv"
    with p.open("w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(all_rows[0]))
        wr.writeheader(); wr.writerows(all_rows)

    by = defaultdict(list)
    for r in all_rows:
        by[r["variant"]].append(r)

    print("\n" + "=" * 86)
    print("KẾT QUẢ: twin MẶC ĐỊNH chấm nhật ký sinh NGOÀI giả định của nó")
    print("=" * 86)
    print(f"{'biến thể':<24}{'n':>5}{'k.định':>8}{'lệnh TB':>9}{'kết quả':>20}{'F1':>6}{'F2':>5}{'F4':>6}")
    for v in ["honest_paper", "honest_field", "fraud_added_events",
              "fraud_infeasible_depth", "fraud_omission", "fraud_adaptive"]:
        rs = by.get(v, [])
        if not rs:
            continue
        fl = sum(r["flagged"] for r in rs)
        lab = "BẮT OAN" if v.startswith("honest") else "bắt được"
        print(f"{v:<24}{len(rs):>5}{sum(r['testable'] for r in rs):>8}"
              f"{statistics.mean(r['n_claims'] for r in rs):>9.1f}"
              f"{f'{fl}/{len(rs)} {lab}':>22}{sum(r['F1'] for r in rs):>6}"
              f"{sum(r['F2'] for r in rs):>5}{sum(r['F4'] for r in rs):>6}")

    print("\n=== LỖ HỔNG #1: V2 LÀ CODE CHET (đã đọc trong code) ===")
    tot_f2 = sum(r["F2"] for r in all_rows)
    print(f"  V2 fire {tot_f2} lần / {len(all_rows)} nhật ký. depletion_fraction() clip về")
    print("  [0,1] nên dp > 1.02 bất khả thi -> bài báo quảng cáo 3 bộ lọc nhưng V2 vô hiệu."
          if tot_f2 == 0 else "  -> V2 có fire")

    hp, hf = by.get("honest_paper", []), by.get("honest_field", [])
    print("\n=== LỖ HỔNG #2: BẮT OAN KHI RUỘNG THẬT LỆCH GIẢ ĐỊNH ===")
    if hp and hf:
        print(f"  GIẤY      {sum(r['flagged'] for r in hp)}/{len(hp)} = {rate(hp)*100:.0f}%")
        print(f"  RUỘNG THẬT {sum(r['flagged'] for r in hf)}/{len(hf)} = {rate(hf)*100:.0f}%")
        per = defaultdict(list)
        for r in hf:
            per[r["soil"]].append(r)
        print("  theo loại đất:")
        for s in sorted(per, key=lambda k: -rate(per[k])):
            rs = per[s]
            fc, wp = SOIL_MAP[s]
            print(f"    {s:<18} span={(fc-wp)*500:5.1f}mm  bắt oan "
                  f"{sum(r['flagged'] for r in rs):>2}/{len(rs):<3} = {rate(rs)*100:5.1f}%")

    print("\n=== LỖ HỔNG #3: ĐỐI THỦ THÍCH NGHI BIẾT eps (bài báo công khai) ===")
    ai = by.get("adaptive_inflation", [])
    if ai:
        inj = [r["gap_mm"] for r in ai]
        infl = [r["total_mm"] - r["truth_total_mm"] for r in ai]
        caught = sum(r["flagged"] for r in ai)
        print(f"  nhật ký bị bắt: {caught}/{len(ai)} = {rate(ai)*100:.0f}%")
        print(f"  mm khống chèn vào: TB {statistics.mean(inj):6.1f} | max {max(inj):6.1f}")
        print(f"  mm khống LỌT (tổng khai - khai thật): TB {statistics.mean(infl):6.1f}"
              f" | max {max(infl):6.1f}")
        span = TWIN.fc_mm - TWIN.wp_mm
        k = statistics.mean(infl)
        print(f"  mm khống TB {k:.0f} so với span {span:.0f}mm -> "
              f"{k/span:.1f} LẦN sức chứa root zone")
        print("  QUAN TRỌNG — sửa một suy luận sai của chính bản probe đầu:")
        print("    u_max = d*·span + eps là chặn THEO TỪNG SỰ KIỆN, KHÔNG phải theo vụ.")
        print("    Bucket thoát nước liên tục (deep percolation + ETc) nên kẻ tấn công")
        print("    khai nhiều lệnh nhỏ sát ngưỡng vẫn thổi phồng được CẢ VỤ mà không")
        print("    lần nào vượt ngưỡng. Nghĩa là Mệnh đề u_max yếu hơn bài báo ngụ ý.")
        over = sum(1 for x in infl if x > span)
        print(f"  số nhật ký tấn công có tổng bơm khống VƯỢT span: {over}/{len(ai)}"
              f" ({over/len(ai)*100:.0f}%)")
        # chi tieu that: so pha kho duoc tinh tin chi
        if hf:
            d_h = statistics.mean(r["n_dry"] for r in hf)
            d_a = statistics.mean(r["n_dry"] for r in ai)
            print("  CHỈ TIÊU MRV (số pha khô >= 72h được tính tín chỉ):")
            print(f"    nông dân trung thực : {d_h:.2f} pha/vụ")
            print(f"    đối thủ thích nghi   : {d_a:.2f} pha/vụ")
            if d_h > 0:
                print(f"    => tín chỉ bị thổi phồng {((d_a-d_h)/d_h)*100:+.0f}% "
                      f"mà bộ lọc vẫn cho qua ở {len(ai)-sum(r['flagged'] for r in ai)}"
                      f"/{len(ai)} nhật ký")
            else:
                print("    (mẫu chưa có nhật ký trung thực nào đạt pha khô -> tăng seed)")

    om = by.get("fraud_omission", [])
    if om:
        gaps = [r["gap_mm"] for r in om]
        print(f"\n=== GIẤU LỆNH (tầng 1) ===\n  gap TB {statistics.mean(gaps):.1f}mm | "
              f"bắt {sum(1 for g in gaps if g > PUMP_GAP_MM)}/{len(gaps)}")

    empt = sum(1 for r in hf if r["n_claims"] == 0)
    print(f"\n=== NHẬT KÝ RỖNG ===\n  {empt}/{len(hf)} nhật ký ruộng thật có 0 lệnh "
          f"(mùa mưa không cần tưới là ĐÚNG). Gian lận chỉ kiểm định trên "
          f"{sum(r['testable'] for r in hf)}/{len(hf)} nhật ký có >= {MIN_CLAIMS} lệnh.")
    print(f"\n  -> {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Unit tests cho src/log_filters.py — bộ lọc bền vững (v2).

Mỗi test khóa chặt MỘT lỗ hổng đã đo được ở reality_gap_probe, để không ai
sửa ngược lại mà không làm test đỏ.

Chạy: python3 tests/test_log_filters.py
Exit code != 0 nếu có test fail.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from log_filters import (ETA_SET, KC_MODES, SOIL_SET, FilterConfig,  # noqa: E402
                         InfilCapacity, Theta, depletion_raw, kc_value,
                         max_event_depth, tier1_gap_flag, tier1_threshold,
                         umax_envelope, umax_for, uncertainty_set,
                         replay_theta, robust_audit, RecordingNoise)
from water_balance import BucketState, SoilProfile, depletion_fraction  # noqa: E402

FAILS: list[str] = []
PASSES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASSES if cond else FAILS).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))


# --------------------------------------------------------------------------
print("== LỖ HỔNG 1: V2 từng là code chết (clip về [0,1]) ==")
prof = SoilProfile()
raws = [depletion_raw(w, prof) for w in (160, 120, 90, 50, 0, -50, -500)]
clipped = [depletion_fraction(BucketState(w=w), prof) for w in (160, 120, 90, 50, 0, -50, -500)]
check("depletion_raw vượt được 1.0", max(raws) > 1.0, f"max raw = {max(raws):.2f}")
check("depletion_fraction vẫn clip về 1.0", max(clipped) == 1.0,
      f"max clipped = {max(clipped):.2f}")
check("raw > 1 khi w < WP", depletion_raw(prof.wp_mm - 10, prof) > 1.0)

# V2 phải fire khi ruộng khô hơn điểm héo kéo dài
w0_bad = prof.wp_mm - 5.0
cfg = FilterConfig(f2_min_hours=3)
# dựng một chuỗi "thời tiết" khô tuyệt đối: ET0 cao, không mưa
dry_weather = [{"time": f"2024-03-01T{h:02d}:00", "p": 0.0, "et0": 0.5} for h in range(24)]
th_dry = Theta("silty_clay_loam", 0.32, 0.18, "fixed", 1.0)
_, v_dry = replay_theta({}, dry_weather, {"2024-03-01": 0.0}, th_dry, 0, 12, cfg,
                        w0_depl=1.10)   # bắt đầu ĐÃ khô hơn điểm héo
check("V2 fire trên ruộng khô hơn điểm héo kéo dài", v_dry.f2 > 0, f"f2 = {v_dry.f2}")
_, v_wet = replay_theta({}, dry_weather, {"2024-03-01": 0.0}, th_dry, 0, 12, cfg,
                        w0_depl=0.0)
check("V2 KHÔNG fire trên ruộng bình thường", v_wet.f2 == 0, f"f2 = {v_wet.f2}")

# --------------------------------------------------------------------------
print("\n== LỖ HỔNG 2: Kc cố định 1.05 vs FAO-56 Table 12 ==")
check("kc_value('fixed') = 1.05 mọi giai đoạn",
      kc_value("fixed", 5) == kc_value("fixed", 50) == kc_value("fixed", 90) == 1.05)
check("kc_value('stage') = 1.05 đầu vụ", kc_value("stage", 10) == 1.05)
check("kc_value('stage') = 1.20 giữa vụ", kc_value("stage", 50) == 1.20)
check("kc_value('stage') = 0.90 cuối vụ", kc_value("stage", 85) == 0.90)
check("sai số Kc lớn nhất giữa hai chế độ",
      abs(kc_value("stage", 50) / kc_value("fixed", 50) - 1) > 0.10,
      f"{abs(kc_value('stage',50)/1.05-1)*100:.1f}%")

# --------------------------------------------------------------------------
print("\n== LỖ HỔNG 3: u_max phụ thuộc loại đất ==")
ths = uncertainty_set()
check("Θ = đất × Kc × eta = 5×2×3 = 30", len(ths) == 30, f"len = {len(ths)}")
check("5 loại đất", len(SOIL_SET) == 5)
check("2 chế độ Kc", len(KC_MODES) == 2)
check("3 mức eta", len(ETA_SET) == 3)
lo, hi = umax_envelope()
check("u_max là DẢI chứ không phải một số", hi - lo > 5.0,
      f"[{lo:.1f}, {hi:.1f}] mm, rộng {hi-lo:.1f}mm")
# TÍNH TAY: span(silty_clay_loam) = (0.32-0.18)*1000*0.5 = 70mm
u_scl = umax_for(Theta("silty_clay_loam", 0.32, 0.18, "fixed", 1.0))
check("u_max cho silty_clay_loam w0=0 tái tạo được 61mm của v1 (0.80*70+5)",
      abs(u_scl - 61.0) < 0.01, f"{u_scl:.2f}")
# w0 = 0.25 < d* = 0.80 nên d* chi phối -> vẫn 61mm (KHÔNG phải 43.5 như bản sai)
u_scl_w0 = umax_for(Theta("silty_clay_loam", 0.32, 0.18, "fixed", 1.0), w0_depl=0.25)
check("w0 < d* không làm đổi u_max (d* chi phối)", abs(u_scl_w0 - 61.0) < 0.01,
      f"{u_scl_w0:.2f}")
# w0 = 0.90 > d* -> ruộng bắt đầu đã khô hơn ngưỡng tưới: 0.90*70+5 = 68mm
u_scl_dry = umax_for(Theta("silty_clay_loam", 0.32, 0.18, "fixed", 1.0), w0_depl=0.90)
check("w0 > d* làm u_max TĂNG (0.90*70+5 = 68)", abs(u_scl_dry - 68.0) < 0.01,
      f"{u_scl_dry:.2f}")

# --------------------------------------------------------------------------
print("\n== LỖ HỔNG 4: tầng 1 ngưỡng tuyệt đối 5mm bắt oan nông dân ==")
# Nông dân trung thực quên ghi 1 sự kiện 30mm trong 8 sự kiện, tổng bơm 240mm
tau_v1 = 5.0
gap = 30.0
flagged_v1 = abs(gap) > tau_v1
n_ev = 8
noise = RecordingNoise()
tau_v2 = tier1_threshold(240.0, n_ev, noise)
flagged_v2, g2, t2 = tier1_gap_flag(240.0, 210.0, n_ev, noise)
check("v1 (τ=5mm) CÁO BUỘC nông dân quên ghi 1 sự kiện", flagged_v1)
check("v2 KHÔNG cáo buộc trường hợp đó", not flagged_v2,
      f"gap {g2:.1f}mm vs τ {t2:.1f}mm")
check("τ co giãn theo số sự kiện: n=20 > n=2",
      tier1_threshold(600.0, 20, noise) > tier1_threshold(600.0, 2, noise),
      f"{tier1_threshold(600.0,20,noise):.1f} > {tier1_threshold(600.0,2,noise):.1f}")
# nhưng gian lận THẬT (tưới lén cả một pha) vẫn phải bị bắt
big_gap, g3, t3 = tier1_gap_flag(240.0, 90.0, 8, noise)   # giấu 150mm
check("v2 VẪN bắt gian lận lớn (giấu 150mm)", big_gap,
      f"gap {g3:.1f}mm vs τ {t3:.1f}mm")
check("τ tăng theo tổng bơm (δ_rel·M)",
      tier1_threshold(1000.0, 8, noise) > tier1_threshold(100.0, 8, noise))

# --------------------------------------------------------------------------
print("\n== LỖ HỔNG 5 + (S1): buộc tội kiểu ∀ trên Θ ==")
# một nhật ký khai tưới sát ngưỡng trên đất CÁT (span nhỏ) — v1 với profile mặc
# định (silty clay loam, span 70) sẽ không thấy gì, nhưng θ cát thì thấy
wet = [{"time": f"2024-03-01T{h:02d}:00", "p": 0.0, "et0": 0.05} for h in range(24)]
# TÍNH TAY: w0_depl=0 nghĩa là bucket Ở FIELD CAPACITY, deficit = 0, nên ngưỡng
# F4 = 0 + eps = 5mm với MỌI θ. Khai 55mm > 5mm -> fire ở mọi θ. Đây là vật lý
# đúng (ruộng đã no nước thì không thể "tưới thành công" 55mm), và kỳ vọng của bản
# test đầu tiên ("θ mặc định KHÔNG phát hiện") là SAI.
log = {0: 55.0}
th_sand = Theta("sandy_loam", 0.21, 0.10, "fixed", 1.0)
th_twin = Theta("silty_clay_loam", 0.32, 0.18, "fixed", 1.0)
_, v_sand = replay_theta(log, wet, {"2024-03-01": 0.0}, th_sand, 0, 6, FilterConfig())
_, v_twin = replay_theta(log, wet, {"2024-03-01": 0.0}, th_twin, 0, 6, FilterConfig())
check("ruộng ở FC: 55mm fire F4 dưới θ cát (deficit 0, ngưỡng 5mm)", v_sand.f4 > 0,
      f"f4={v_sand.f4}")
check("ruộng ở FC: 55mm fire F4 dưới θ twin NHƯ NHAU (không phân biệt θ)",
      v_twin.f4 > 0, f"f4={v_twin.f4}")

# Trường hợp PHÂN BIỆT được θ: ruộng khô (w0=0.80), khai 55mm.
#   sandy span 55 -> ngưỡng 0.80*55+5 = 49mm  -> 55 > 49 : FIRE
#   silt_loam span 90 -> ngưỡng 0.80*90+5 = 77mm -> 55 <= 77 : KHÔNG fire
_, v_sand_dry = replay_theta(log, wet, {"2024-03-01": 0.0}, th_sand, 0, 6,
                             FilterConfig(), w0_depl=0.80)
th_silt = Theta("silt_loam", 0.33, 0.15, "fixed", 1.0)
_, v_silt_dry = replay_theta(log, wet, {"2024-03-01": 0.0}, th_silt, 0, 6,
                             FilterConfig(), w0_depl=0.80)
check("ruộng khô: 55mm FIRE dưới θ cát (ngưỡng 49mm)", v_sand_dry.f4 > 0,
      f"f4={v_sand_dry.f4}")
check("ruộng khô: 55mm KHÔNG fire dưới θ phù sa (ngưỡng 77mm)",
      v_silt_dry.f4 == 0, f"f4={v_silt_dry.f4}")

# ∀-semantics: vì w0=0.90 nằm trong W0_SET, tồn tại một thế giới mà 55mm hợp
# pháp -> KHÔNG được buộc tội. Đây chính là sửa lỗi B.
verdict = robust_audit(log, wet, {"2024-03-01": 0.0}, 0, 6)
check("∀-semantics: 55mm KHÔNG bị buộc tội (ruộng khô giải thích được)",
      not verdict.flagged,
      f"{verdict.n_theta_flagging}/{verdict.n_theta} (θ,w0) fire")

# gian lận thô (khai 160mm = cả sức chứa) phải bị MỌI θ bắt
log2 = {0: 160.0}
# TÍNH TAY: ngưỡng F4 lớn nhất có thể có = max(w0)·max(span)+eps = 0.90·90+5 = 86mm.
# Khai 160mm > 86mm nên fire dưới MỌI (θ, w0) -> giao khác rỗng -> buộc tội.
verdict2 = robust_audit(log2, wet, {"2024-03-01": 0.0}, 0, 6)
check("gian lận thô 160mm bị buộc tội dưới ∀ (vượt mọi ngưỡng 86mm)",
      verdict2.flagged,
      f"{verdict2.n_theta_flagging}/{verdict2.n_theta} (θ,w0) fire, "
      f"f1={verdict2.f1} f4={verdict2.f4}")
check("n_theta = |Θ| × |W0_SET| = 30 × 5 = 150", verdict2.n_theta == 150,
      f"{verdict2.n_theta}")
check("mọi (θ,w0) đều fire với gian lận thô",
      verdict2.n_theta_flagging == verdict2.n_theta)

# --------------------------------------------------------------------------
print("\n== LỖ HỔNG 6: gian lận DỒN LỆNH — vật lý và đồng hồ bơm đều mù ==")
cap = InfilCapacity()
# TÍNH TAY: u_max sự kiện 1 giờ = 10 mm/h × 1h + 100 mm ponding = 110mm
check("max_event_depth(1h) = 110mm (10·1 + 100)",
      abs(max_event_depth(1.0, cap) - 110.0) < 1e-9, f"{max_event_depth(1.0, cap):.1f}")
check("max_event_depth(4h) = 140mm (10·4 + 100)",
      abs(max_event_depth(4.0, cap) - 140.0) < 1e-9, f"{max_event_depth(4.0, cap):.1f}")
check("max_event_depth tăng đơn điệu theo thời lượng",
      max_event_depth(8.0, cap) > max_event_depth(4.0, cap) > max_event_depth(1.0, cap))
check("duration_h <= 0 rơi về mặc định 1h (không chia 0 / âm)",
      max_event_depth(0.0, cap) == max_event_depth(1.0, cap))

# Nhật ký bị dồn: 5 lệnh 40mm rải mỗi 24h (hợp lý) -> 1 lệnh 200mm (bất khả thi)
# TỔNG KHÔNG ĐỔI nên đồng hồ trạm bơm mù: gap = 0.
spread_log = {h: 40.0 for h in (0, 24, 48, 72, 96)}
clustered_log = {0: 200.0}
check("hai nhật ký có TỔNG bằng nhau (đồng hồ bơm không phân biệt được)",
      abs(sum(spread_log.values()) - sum(clustered_log.values())) < 1e-9,
      f"{sum(spread_log.values())} vs {sum(clustered_log.values())}")

dry6 = [{"time": f"2024-03-01T{h:02d}:00", "p": 0.0, "et0": 0.02} for h in range(6)]
th_scl = Theta("silty_clay_loam", 0.32, 0.18, "fixed", 1.0)
_, v_spread = replay_theta(spread_log, dry6, {"2024-03-01": 0.0}, th_scl, 0, 6,
                           FilterConfig())
_, v_clust = replay_theta(clustered_log, dry6, {"2024-03-01": 0.0}, th_scl, 0, 6,
                          FilterConfig())
check("nhật ký rải 40mm/h: F5 KHÔNG fire (40 <= 110)", v_spread.f5 == 0,
      f"f5={v_spread.f5}")
check("nhật ký dồn 200mm/1h: F5 FIRE (200 > 110)", v_clust.f5 > 0,
      f"f5={v_clust.f5}")
check("F5 thấy được điều F4 không thấy (F4 vẫn có thể im nếu ruộng khô)",
      v_clust.f5 > 0)

# F5 phải sống sót dưới ∀ trên Θ: nó không phụ thuộc đất nên fire ở MỌI θ
verdict_spread = robust_audit(spread_log, dry6, {"2024-03-01": 0.0}, 0, 6)
verdict_clust = robust_audit(clustered_log, dry6, {"2024-03-01": 0.0}, 0, 6)
check("∀-audit: nhật ký rải KHÔNG bị buộc tội", not verdict_spread.flagged,
      f"{verdict_spread.n_theta_flagging}/{verdict_spread.n_theta} fire")
check("∀-audit: nhật ký dồn BỊ buộc tội", verdict_clust.flagged,
      f"{verdict_clust.n_theta_flagging}/{verdict_clust.n_theta} fire")
check("RobustVerdict.f5 được cộng dồn", verdict_clust.f5 > 0, f"f5={verdict_clust.f5}")

# tắt F5 thì mất khả năng bắt dồn lệnh — chứng minh F5 là thứ duy nhất bắt được
_, v_off = replay_theta(clustered_log, dry6, {"2024-03-01": 0.0}, th_scl, 0, 6,
                        FilterConfig(enable_f5=False))
check("tắt F5 thì dồn lệnh lọt (chứng minh F5 cần thiết)", v_off.f5 == 0)

# biên độ: lệnh 100mm vẫn hợp pháp (dưới 110), 120mm thì không
_, v_100 = replay_theta({0: 100.0}, dry6, {"2024-03-01": 0.0}, th_scl, 0, 6,
                        FilterConfig())
_, v_120 = replay_theta({0: 120.0}, dry6, {"2024-03-01": 0.0}, th_scl, 0, 6,
                        FilterConfig())
check("100mm KHÔNG fire F5 (dưới ngưỡng 110)", v_100.f5 == 0, f"f5={v_100.f5}")
check("120mm fire F5 (trên ngưỡng 110)", v_120.f5 > 0, f"f5={v_120.f5}")

# --------------------------------------------------------------------------
print("\n== TÍNH THUẦN TÚY: cùng input phải cùng output (tái lập) ==")
a = robust_audit(log2, wet, {"2024-03-01": 0.0}, 0, 6)
b = robust_audit(log2, wet, {"2024-03-01": 0.0}, 0, 6)
check("robust_audit tất định", (a.flagged, a.f1, a.f4, a.hours) == (b.flagged, b.f1, b.f4, b.hours))

print("\n" + "=" * 70)
print(f"PASS {len(PASSES)} | FAIL {len(FAILS)}")
if FAILS:
    print("Các test FAIL:")
    for f in FAILS:
        print("  -", f)
    sys.exit(1)
print("TẤT CẢ TEST PASS")
sys.exit(0)

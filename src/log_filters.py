#!/usr/bin/env python3
"""Bộ lọc nhật ký tưới BỀN VỮNG (v2) — sửa 5 lỗ hổng đo được ở reality_gap_probe.

BỐI CẢNH: bản v1 (experiments/fraud_detection.py) đạt "0 bắt oan / 100% phát hiện"
nhưng chỉ trên quỹ đạo do CHÍNH mô hình đó sinh ra. Khi ruộng thật lệch giả định
(đất khác, Kc theo giai đoạn, hiệu suất tưới < 1, mưa tại ruộng ≠ ô lưới ERA5,
rò rỉ bờ, nông dân quên/làm tròn/ghi trễ) thì đo được:

  LỖ HỔNG 1  V2 là code chết: depletion_fraction() clip về [0,1] nên ngưỡng
             DEPL_IMPOSSIBLE=1.02 bất khả thi. Fire 0/288 nhật ký.
  LỖ HỔNG 2  Kc cố định 1.05 trong khi FAO-56 Table 12 cho lúa là 1.05/1.20/0.90
             → sai ETc ±14%, tích lũy 90 ngày.
  LỖ HỔNG 3  Một SoilProfile cho cả ba tỉnh; span thật 55–90mm nên ngưỡng u_max
             = d*·span + ε chỉ đúng cho một loại đất.
  LỖ HỔNG 4  Tầng 1 dùng ngưỡng gap TUYỆT ĐỐI 5mm → bắt oan 8/60 = 13% nông dân
             trung thực (gap max 75mm) chỉ vì họ quên ghi, làm tròn, ghi trễ.
             Điều này PHÁ lời hứa cốt lõi "không thể trừng phạt hành vi đúng".
  LỖ HỔNG 5  Bắt oan tăng 0% → 8% khi rời điều kiện giấy.
  LỖ HỔNG 6  GIAN LẬN DỒN LỆNH — nghiêm trọng nhất, và cả vật lý cân bằng nước
             lẫn đồng hồ trạm bơm đều KHÔNG thấy. Kẻ gian giữ nguyên TỔNG mm đã
             bơm (gap đồng hồ = 0) và giữ từng lệnh dưới ngưỡng F4, chỉ gộp nhiều
             lệnh rải rác thành ít lệnh tập trung. Bucket đẩy phần vượt FC thành
             deep percolation ngay trong giờ đó nên các pha khô dài ra và không bị
             cắt: số pha khô >= 72h — ĐẠI LƯỢNG MÀ TÍN CHỈ ĐƯỢC TRẢ — tăng +80%
             mà vẫn lọt 5/5 ở cả bản v1 lẫn bản v2 chưa có F5. Sửa bằng ràng
             buộc sức thấm (InfilCapacity / max_event_depth), độc lập với trạng
             thái bucket.

HAI ĐIỀU PHẢI CÔNG BỐ THAY VÌ QUẢNG CÁO
=======================================
  (a) V2 đã được sửa cho fire được (depletion không clip), nhưng TRÊN DỮ LIỆU
      THẬT NÓ VẪN KHÔNG BAO GIỜ KÍCH HOẠT: đo depletion clip max = 0.998 (2024)
      và 0.988 (2025) tại Cần Thơ, tức ruộng lúa mùa khô ĐBSCL không xuống dưới
      điểm héo. Nói "ba bộ lọc" khi một bộ không có dữ liệu nào kích hoạt được
      là quảng cáo. Phải nói rõ V2 là bộ lọc an toàn (không kích hoạt được trên
      lúa mùa khô) chứ không phải bằng chứng phát hiện gian lận.
  (b) Buộc tội kiểu ∀ mua được sự an toàn bằng sức phát hiện. Phần đánh đổi đó
      phải đo và in ra (cột "cái giá của sự bền vững" trong robust_audit_eval),
      không được giấu.

BA SỬA ĐỔI THIẾT KẾ
===================

(S1) BUỘC TỘI KIỂU ∀ (robust accusation). Thay vì replay bằng một mô hình điểm
     rồi coi mọi lệch pha là gian lận, ta định nghĩa tập bất định Θ (đất × chế
     độ Kc × hiệu suất tưới) và chỉ buộc tội khi MỌI θ ∈ Θ đều báo vi phạm:

         V_robust(L) = ∩_{θ∈Θ} V_θ(L)

     Hệ quả: nếu ruộng thật nằm trong Θ thì nông dân trung thực KHÔNG THỂ bị
     buộc tội, bất kể ta không biết θ thật. Đây chính là mệnh đề no-alarm được
     khôi phục dưới bất định mô hình — cái giá là mất sức phát hiện, và phần
     mất đó phải được đo chứ không được giấu.

(S2) V2 THẬT: dùng depletion KHÔNG clip. BucketState cho phép w < WP (docstring
     water_balance.py ghi rõ: "NO silent clamping ... Dr > TAW under sustained
     deficit"). V2 fire khi depletion thô vượt 1 trong ≥ N giờ liên tiếp, tức
     ruộng khô hơn điểm héo kéo dài — trạng thái không thể là ruộng lúa sống.
     Không sửa water_balance.py (plant đã công bố, đã có test conservation);
     depletion thô tính lại ở đây từ st.w, fc_mm, wp_mm.

(S3) TẦNG 1 THEO TỈ LỆ, không tuyệt đối. Khoảng cách giữa nước BƠM thật M và
     nước KHAI U(L) trên nông dân trung thực đến từ ba nguồn có thể định lượng:
     quên ghi (p_forget), làm tròn (round_to/2 cho mỗi sự kiện), khai sai độ sâu.
     Nên ngưỡng phải co giãn theo số sự kiện:

         τ(n) = δ_rel · M + z · σ_noise(n),   σ_noise(n) ∝ √n

     với δ_rel là dung sai hệ thống và z lấy từ phân phối của chính nhiễu ghi
     chép. Ngưỡng cố định 5mm là trường hợp suy biến của công thức này khi n nhỏ
     và nhiễu bằng 0 — tức là nó chỉ đúng trong phòng thí nghiệm.

Toàn bộ hàm ở đây THUẦN TÚY (không I/O), để experiment gọi và để test đơn vị.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Iterable, Sequence

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from water_balance import (BucketState, SoilProfile, daily_runoff_share,   # noqa: E402
                           depletion_fraction, stress_coefficient, step_bucket)

# ---------------------------------------------------------------------------
# Tập bất định Θ
# ---------------------------------------------------------------------------

# FAO-56 Table 2, các kết cấu có thật ở ĐBSCL (theta_fc, theta_wp) [m3/m3]
SOIL_SET: tuple[tuple[str, float, float], ...] = (
    ("sandy_loam", 0.21, 0.10),
    ("loam", 0.27, 0.12),
    ("silt_loam", 0.33, 0.15),
    ("silty_clay_loam", 0.32, 0.18),
    ("clay", 0.39, 0.23),
)

# Chế độ Kc: bản công bố (cố định) và bản đúng FAO-56 Table 12 (theo giai đoạn)
KC_MODES: tuple[str, ...] = ("fixed", "stage")

# Hiệu suất tưới: nước tới vùng rễ / nước đã bơm
ETA_SET: tuple[float, ...] = (0.60, 0.75, 1.00)


def kc_value(mode: str, day: float, kc_fixed: float = 1.05) -> float:
    """FAO-56 Table 12 (lúa): 1.05 initial (<30 d), 1.20 mid (30–75 d), 0.90 late.

    'fixed' tái tạo đúng hành vi bản v1 để có thể so sánh trước/sau.
    """
    if mode == "fixed":
        return kc_fixed
    return 1.05 if day < 30 else (1.20 if day < 75 else 0.90)


def depletion_raw(w: float, prof: SoilProfile) -> float:
    """Depletion KHÔNG clip — sửa LỖ HỔNG 1.

    Có thể > 1 (khô hơn điểm héo) hoặc < 0 (trên field capacity). Chỉ dùng cho
    bộ lọc; depletion_fraction() đã công bố vẫn là chỉ tiêu báo cáo có clip.
    """
    span = prof.fc_mm - prof.wp_mm
    if span <= 0:
        return 0.0
    return (prof.fc_mm - w) / span


@dataclass(frozen=True)
class Theta:
    """Một điểm của tập bất định Θ."""
    soil: str
    theta_fc: float
    theta_wp: float
    kc_mode: str
    eta: float
    root_depth_m: float = 0.5

    def profile(self) -> SoilProfile:
        return SoilProfile(theta_fc=self.theta_fc, theta_wp=self.theta_wp,
                           root_depth_m=self.root_depth_m)


# Trạng thái đầu vụ bất định, phủ hết dải mà một lệnh tưới còn có thể hợp pháp:
# 0.0 (đất ở field capacity) đến 0.9 (khô hơn cả ngưỡng rút nước AWD d* = 0.80).
W0_SET: tuple[float, ...] = (0.0, 0.25, 0.50, 0.75, 0.90)


def uncertainty_set(soils: Sequence[tuple[str, float, float]] = SOIL_SET,
                    kc_modes: Sequence[str] = KC_MODES,
                    etas: Sequence[float] = ETA_SET) -> list[Theta]:
    """Θ = đất × chế độ Kc × hiệu suất tưới (5 × 2 × 3 = 30 điểm)."""
    return [Theta(s[0], s[1], s[2], k, e)
            for s in soils for k in kc_modes for e in etas]


# ---------------------------------------------------------------------------
# Replay cho MỘT θ
# ---------------------------------------------------------------------------

@dataclass
class Violations:
    """Số lần mỗi bộ lọc fire, cùng bằng chứng giờ cụ thể."""
    f1: int = 0          # tưới khi đã ở/trên field capacity
    f2: int = 0          # depletion thô > 1 kéo dài (khô hơn điểm héo)
    f4: int = 0          # độ sâu khai vượt sức chứa tại giờ đó
    f5: int = 0          # độ sâu khai vượt sức thấm của ruộng (dồn lệnh)
    hours_f1: tuple = ()
    hours_f2: tuple = ()
    hours_f4: tuple = ()
    hours_f5: tuple = ()

    def any(self) -> bool:
        # (f1 or f2 or f4) tra ve GIA TRI CUOI, khong phai bool — bài học đã trả
        # giá ở harness đánh giá: int(0 or 0 or 7) == 7 nên "560% bắt được".
        return bool((self.f1 + self.f2 + self.f4 + self.f5) > 0)

    def key(self) -> frozenset:
        """Tập giờ bị cáo buộc — dùng để giao (∩) giữa các θ."""
        out = set()
        for h in self.hours_f1:
            out.add(("F1", h))
        for h in self.hours_f2:
            out.add(("F2", h))
        for h in self.hours_f4:
            out.add(("F4", h))
        for h in self.hours_f5:
            out.add(("F5", h))
        return frozenset(out)


@dataclass(frozen=True)
class InfilCapacity:
    """Khả năng TIẾP NHẬN nước của một thửa ruộng lúa trong một sự kiện tưới.

    Đây là ràng buộc vật lý ĐỘC LẬP với cân bằng nước, và nó bắt được loại gian
    lận mà cả F1/F2/F4 lẫn đồng hồ trạm bơm đều mù — xem LỖ HỔNG 6 ở module
    docstring.

    Vật lý: một sự kiện kéo dài `duration_h` giờ chỉ đưa vào ruộng được

        u_max = infil_mm_h · duration_h + max_pond_mm

    vì phần vượt tốc độ thấm sẽ đọng trên mặt chứ không vào vùng rễ, và phần vượt
    mực ao hoá sẽ chảy tràn qua bờ (bờ ruộng lúa cao 15–20cm, mực nước giữ
    thường 5–15cm). Dải tham số cho lúa: thấm 5–20 mm/h, ponding 50–100mm.

    Mặc định LẤY Ở BIÊN NỚI LỎNG NHẤT của dải (thấm thấp 10mm/h, ponding cao
    100mm) để không buộc tội oan nông dân ghi gộp hai sự kiện liền nhau vào cùng
    một giờ — một artifact ghi chép hợp pháp, không phải gian lận.
    """
    infil_mm_h: float = 10.0      # tốc độ thấm ruộng lúa, biên dưới dải 5–20
    max_pond_mm: float = 100.0    # mực ao hoá tối đa giữ được trước khi tràn bờ
    default_duration_h: float = 1.0


def max_event_depth(duration_h: float, cap: InfilCapacity = InfilCapacity()) -> float:
    """Độ sâu lớn nhất một sự kiện tưới có thể đưa vào ruộng trong duration_h giờ."""
    d = duration_h if duration_h > 0 else cap.default_duration_h
    return cap.infil_mm_h * d + cap.max_pond_mm


@dataclass(frozen=True)
class FilterConfig:
    fc_slack_mm: float = 5.0     # ε công bố: dung sai cho sai số mô hình
    f2_min_hours: int = 24       # khô hơn điểm héo liên tục ít nhất 1 ngày
    f2_raw_limit: float = 1.00   # depletion thô vượt 1.00 = dưới điểm héo
    infil: InfilCapacity = InfilCapacity()
    enable_f5: bool = True       # V5: ràng buộc sức thấm (bắt gian lận dồn lệnh)


def replay_theta(log_irrig: dict[int, float], weather: list[dict],
                 day_rain: dict[str, float], th: Theta, start: int, hours: int,
                 cfg: FilterConfig = FilterConfig(),
                 w0_depl: float = 0.0) -> tuple[list[float], Violations]:
    """Replay nhật ký dưới MỘT cấu hình θ.

    Khác bản v1 ở ba chỗ, đều là sửa lỗ hổng:
      * Kc lấy theo th.kc_mode (sửa LỖ HỔNG 2)
      * nước tới vùng rễ = eta × số đã khai (sửa LỖ HỔNG 2/C: nông dân khai số
        đã BƠM, không phải số tới rễ)
      * depletion thô không clip cho F2 (sửa LỖ HỔNG 1)
      * w0 từ depletion ban đầu, không mặc định = field capacity (sửa LỖ HỔNG G)
    """
    prof = th.profile()
    span = prof.fc_mm - prof.wp_mm
    st = BucketState(w=prof.fc_mm - w0_depl * span)
    depls: list[float] = []
    v = Violations()
    h1: list[int] = []
    h2: list[int] = []
    h4: list[int] = []
    h5: list[int] = []
    run_below = 0
    cap = cfg.infil

    for h in range(hours):
        i = start + h
        if i >= len(weather):
            break
        r = weather[i]
        d = r["time"][:10]
        ro = daily_runoff_share(day_rain.get(d, 0.0), r["p"], prof.cn_runoff)
        claimed = log_irrig.get(h, 0.0)

        # F1: khai tưới khi bucket đã ở/trên field capacity
        if claimed > 0 and st.w >= prof.fc_mm - cfg.fc_slack_mm:
            v.f1 += 1
            h1.append(h)

        # F4: lượng khai vượt sức chứa của đất tại giờ đó
        if claimed > 0:
            deficit = max(0.0, prof.fc_mm - st.w)
            if claimed > deficit + cfg.fc_slack_mm:
                v.f4 += 1
                h4.append(h)

        # F5: lượng khai vượt khả năng TIẾP NHẬN của ruộng trong thời gian đó.
        # Ràng buộc này KHÔNG phụ thuộc trạng thái bucket, nên nó thấy được điều
        # mà F1/F4 không thấy: một lệnh 180mm là bất khả thi dù ruộng đang khô
        # tới đâu. Nhật ký chỉ có {giờ: mm} nên thời lượng mặc định 1 giờ; nếu
        # gateway cung cấp thời lượng van mở thật (bài 1 đã ghi bản lệnh này) thì
        # truyền vào để ràng buộc chặt hơn và giảm bắt oan.
        if cfg.enable_f5 and claimed > 0:
            if claimed > max_event_depth(cap.default_duration_h, cap):
                v.f5 += 1
                h5.append(h)

        # nước THẬT tới vùng rễ chỉ là eta × số đã bơm
        to_root = th.eta * claimed
        kc = kc_value(th.kc_mode, h / 24.0, prof.kc)
        ks = stress_coefficient(st, prof)
        infil = max(0.0, r["p"] - ro)
        w = st.w + infil + to_root - ks * kc * r["et0"]
        if w > prof.fc_mm:
            w = prof.fc_mm
        st = BucketState(w=w)

        raw = depletion_raw(st.w, prof)
        depls.append(depletion_fraction(st, prof))

        # F2 (THẬT): khô hơn điểm héo kéo dài
        if raw > cfg.f2_raw_limit:
            run_below += 1
            if run_below >= cfg.f2_min_hours:
                v.f2 += 1
                h2.append(h)
        else:
            run_below = 0

    v.hours_f1 = tuple(h1)
    v.hours_f2 = tuple(h2)
    v.hours_f4 = tuple(h4)
    v.hours_f5 = tuple(h5)
    return depls, v


# ---------------------------------------------------------------------------
# (S1) Buộc tội kiểu ∀ — giao trên toàn bộ Θ
# ---------------------------------------------------------------------------

@dataclass
class RobustVerdict:
    flagged: bool
    n_theta_flagging: int
    n_theta: int
    f1: int
    f2: int
    f4: int
    f5: int
    hours: tuple
    worst_theta: str = ""


def robust_audit(log_irrig: dict[int, float], weather: list[dict],
                 day_rain: dict[str, float], start: int, hours: int,
                 thetas: Iterable[Theta] | None = None,
                 cfg: FilterConfig = FilterConfig(),
                 w0_depl_set: Sequence[float] = W0_SET) -> RobustVerdict:
    """Chỉ buộc tội khi MỌI θ ∈ Θ và MỌI w0 hợp lý đều báo vi phạm.

    w0 cũng bất định (kiểm toán viên không đo được độ ẩm đầu vụ) nên ta lấy giao
    trên cả tập w0: buộc tội giờ h chỉ khi h bị cáo buộc với mọi (θ, w0).

    W0_SET PHỦ HẾT DẢI MÀ NÔNG DÂN CÓ THỂ TƯỚI. Đây là điểm thiết kế dễ sai và
    bản đầu tiên đã sai: với w0 ∈ {0, 0.25} thì ngưỡng F4 cao nhất chỉ 22.5mm,
    nên MỌI lệnh khai > 22.5mm đều bị kết tội trong mọi thế giới — ∀-semantics
    trở nên vô dụng và buộc tội oan nông dân tưới trên ruộng khô. Ngưỡng F4 là
    deficit + ε = w0_depl·span + ε; ruộng khô tới d* = 0.80 có deficit 0.80·span,
    nên một lệnh 55mm trên đất span 70 là HỢP PHÁP (55 <= 61). Muốn ∀ có nghĩa
    thì tập w0 phải chứa trạng thái khô đó.

    Trả về số θ đã fire — bằng chứng về mức độ "chắc" của cáo buộc, và để đo cái
    giá của sự bền vững (bao nhiêu sức phát hiện đã mất).
    """
    ths = list(thetas) if thetas is not None else uncertainty_set()
    inter: frozenset | None = None
    n_flag = 0
    f1 = f2 = f4 = f5 = 0
    binding = ""
    for th in ths:
        for w0 in w0_depl_set:
            _, v = replay_theta(log_irrig, weather, day_rain, th, start, hours,
                                cfg, w0_depl=w0)
            # MỘT THẾ GIỚI KHÔNG FIRE PHẢI ĐÓNG GÓP TẬP RỖNG VÀO PHÉP GIAO.
            # Bản nâng cấp đầu tiên bỏ qua thế giới đó nên phép ∩ chỉ lấy trên
            # các θ đã fire — tức là "∃ θ buộc tội" chứ không phải "∀ θ buộc
            # tội". Đo được: 102/150 fire và code vẫn kết tội, trong khi 48 thế
            # giới vô tội tồn tại. Đó chính là lỗ hổng bắt-oan tái sinh trong
            # bản vá. Giữ v.key() rỗng cho thế giới không fire.
            k = v.key() if v.any() else frozenset()
            inter = k if inter is None else (inter & k)
            if v.any():
                n_flag += 1
                f1 += v.f1
                f2 += v.f2
                f4 += v.f4
                f5 += v.f5
                if not binding:
                    binding = f"{th.soil}/{th.kc_mode}/eta={th.eta}"
    n_all = len(ths) * len(w0_depl_set)
    hours = tuple(sorted(inter)) if inter else ()
    return RobustVerdict(flagged=bool(hours), n_theta_flagging=n_flag,
                         n_theta=n_all, f1=f1, f2=f2, f4=f4, f5=f5, hours=hours,
                         worst_theta=binding)


# ---------------------------------------------------------------------------
# (S3) Tầng 1 theo tỉ lệ — sửa việc bắt oan nông dân quên ghi / làm tròn
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RecordingNoise:
    """Nhiễu ghi chép của nông dân trung thực. Mọi trường đều đo được ở hiện
    trường (đếm số lần quên, độ lớn bước làm tròn) chứ không phải đoán."""
    p_forget: float = 0.05       # xác suất quên ghi một sự kiện
    round_to_mm: float = 5.0     # bước làm tròn khi ghi (0 = ghi đúng)
    p_depth_err: float = 0.15    # xác suất khai sai độ sâu
    depth_err_span: float = 0.35 # biên độ sai độ sâu (±35%)


def tier1_threshold(pumped_mm: float, n_events: int,
                    noise: RecordingNoise = RecordingNoise(),
                    z: float = 3.0, delta_rel: float = 0.02) -> float:
    """Ngưỡng gap τ(n) cho đồng hồ trạm bơm, co giãn theo số sự kiện.

    τ(n) = δ_rel·M + z·σ(n),  σ(n) = sqrt(n·σ_event²)

    σ_event gộp ba nguồn độc lập:
      * quên ghi: p_forget × độ sâu trung bình (mất nguyên một sự kiện)
      * làm tròn: round_to/(2√3) — sai số đều trên nửa bước
      * sai độ sâu: p_depth_err × depth_err_span × độ sâu / √3
    Độ sâu trung bình lấy 30mm (dải khai báo thường gặp 20–45mm).

    Bản v1 dùng τ = 5mm cố định, là trường hợp suy biến với n nhỏ và nhiễu = 0.
    """
    mean_depth = 30.0
    var_forget = noise.p_forget * (1 - noise.p_forget) * mean_depth ** 2
    var_round = (noise.round_to_mm ** 2) / 12.0 if noise.round_to_mm else 0.0
    var_depth = (noise.p_depth_err * (1 - noise.p_depth_err)
                 * (noise.depth_err_span * mean_depth) ** 2)
    sigma_event = math.sqrt(var_forget + var_round + var_depth)
    sigma_n = math.sqrt(max(1, n_events)) * sigma_event
    return delta_rel * pumped_mm + z * sigma_n


def tier1_gap_flag(pumped_mm: float, claimed_mm: float, n_events: int,
                   noise: RecordingNoise = RecordingNoise(),
                   z: float = 3.0) -> tuple[bool, float, float]:
    """Trả về (bị_cáo_buộc, gap, ngưỡng τ). Gap ÂM (khai nhiều hơn bơm) cũng là
    dấu hiệu gian lận — khai khống — nên xét |gap| theo hai chiều có chủ đích."""
    gap = pumped_mm - claimed_mm
    tau = tier1_threshold(pumped_mm, n_events, noise, z)
    return (abs(gap) > tau), gap, tau


# ---------------------------------------------------------------------------
# Mệnh đề u_max tổng quát hoá theo θ — sửa LỖ HỔNG 3
# ---------------------------------------------------------------------------

def umax_for(th: Theta, d_star: float = 0.80, eps: float = 5.0,
             w0_depl: float = 0.0) -> float:
    """Độ sâu khai lớn nhất không bao giờ fire F4, tính cho MỘT θ.

    Bản v1 công bố một con số duy nhất 61mm; nó chỉ đúng cho silty_clay_loam.

    CÔNG THỨC — và bản nâng cấp đầu tiên đã viết SAI chỗ này. Trong replay_theta
    ngưỡng F4 tại giờ h là deficit + ε với deficit = fc − w = depl·span. Nên chặn
    trên của một lệnh khai hợp pháp là depletion LỚN NHẤT mà ruộng có thể đạt
    lúc được tưới, nhân span:

        u_max = max(d*, w0_depl) · span + ε

    KHÔNG phải (d* − w0)·span + ε. Bản sai cho 43.5mm với span 70 và w0 = 0.25,
    trong khi ngưỡng thật là 22.5mm lúc đầu vụ và 61mm sau khi khô tới d* — tức
    43.5 không tương ứng trạng thái vật lý nào. Kiểm bằng tay: w0 = 0 và
    w0 = 0.25 đều phải cho 61mm vì d* = 0.80 chi phối; w0 = 0.90 phải cho 68mm
    vì ruộng bắt đầu đã khô hơn ngưỡng tưới.
    """
    prof = th.profile()
    span = prof.fc_mm - prof.wp_mm
    return max(0.0, max(d_star, w0_depl) * span + eps)


def umax_envelope(d_star: float = 0.80, eps: float = 5.0,
                  thetas: Iterable[Theta] | None = None,
                  w0_depls: Sequence[float] = W0_SET) -> tuple[float, float]:
    """(min, max) của u_max trên toàn Θ × w0 — dải phải công bố thay vì một số."""
    ths = list(thetas) if thetas is not None else uncertainty_set()
    vals = [umax_for(t, d_star, eps, w0) for t in ths for w0 in w0_depls]
    return (min(vals), max(vals))

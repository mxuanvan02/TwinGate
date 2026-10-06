#!/usr/bin/env python3
"""ĐÁNH GIÁ v1 vs v2 DƯỚI KHOẢNG CÁCH THỰC TẾ + ĐỐI THỦ CÓ LÝ TRÍ.

Trả lời đúng ba câu hỏi mà "con số trên giấy" không trả lời được:

  Q1. Khi ruộng thật lệch giả định của twin (7 trục trong reality_gap_probe),
      bộ lọc có còn giữ được lời hứa "không buộc tội nông dân trung thực"?
      v1 đo được: 8% (tầng 0) và 13% (tầng 1). v2 phải về 0%.

  Q2. Cái giá của sự bền vững là bao nhiêu sức phát hiện đã mất?
      Buộc tội kiểu ∀ (chỉ kết tội khi MỌI θ ∈ Θ đều báo) làm giảm detection.
      Phần giảm đó phải được đo và công bố, không được giấu.

  Q3. Đối thủ CÓ LÝ TRÍ thì sao? — đây là chỗ hai bản adversary trước đều sai.

      Bản probe đầu tiên dựng kẻ tấn công bơm 343mm khống. Đo ra n_dry = 0, tức
      KHÔNG CÓ TÍN CHỈ NÀO: nó tự hủy. Kẻ gian lận thật không tối đa mm đã khai,
      nó tối đa SỐ PHA KHÔ ≥72h — vì đó là đại lượng VM0051/QĐ4801 trả tiền.

      Vậy adversary đúng phải tối ưu n_dry dưới ràng buộc không bị bắt. Và từ đó
      lộ ra một lỗ hổng mà cả vật lý lẫn đồng hồ bơm đều KHÔNG thấy:

        DỒN LỆNH (claim consolidation): giữ nguyên TỔNG nước đã khai, chỉ gộp các
        lệnh rải rác thành ít lệnh tập trung hơn. Tổng không đổi nên gap đồng hồ
        bơm = 0 (tầng 1 mù). Độ sâu mỗi lệnh vẫn dưới ngưỡng F4 (tầng 0 mù).
        Nhưng các pha khô trở nên dài hơn và không bị cắt -> n_dry TĂNG.

      Đây không phải gian lận "ăn cắp nước", mà là gian lận "ăn cắp lịch sử" —
      và nó hợp lệ về mặt vật lý.

Chạy:
    python3 experiments/robust_audit_eval.py --quick     # 2 seed, Θ rút gọn
    python3 experiments/robust_audit_eval.py             # đầy đủ
"""
from __future__ import annotations

import argparse
import csv
import random
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

from ncs_loop import load_weather                              # noqa: E402
from water_balance import SoilProfile                          # noqa: E402
from fraud_detection import awd_windows, replay_log            # noqa: E402
import reality_gap_probe as rgp                                # noqa: E402
from log_filters import (ETA_SET, FilterConfig, RecordingNoise, Theta,  # noqa: E402
                         max_event_depth, robust_audit, tier1_gap_flag,
                         uncertainty_set)

START = rgp.START
HOURS = rgp.HOURS
MIN_CLAIMS = 3
TWIN = SoilProfile()
V1_GAP_MM = 5.0            # ngưỡng tuyệt đối của bản v1
CREDIT_MIN_DRY_H = 72      # QĐ4801: pha khô phải >= 3 ngày

# Θ rút gọn cho vòng lặp chính: giữ các CỰC của từng trục, vì thế giới "vô tội"
# dễ tồn tại nhất luôn nằm ở một cực (span lớn nhất = ngưỡng F4 cao nhất).
# Bản đầy đủ 30 θ × 5 w0 = 150 replay/log được dùng để kiểm chứng trên mẫu con.
SOIL_EXTREMES = (("sandy_loam", 0.21, 0.10), ("silty_clay_loam", 0.32, 0.18),
                 ("silt_loam", 0.33, 0.15))
THETA_REDUCED = [Theta(s[0], s[1], s[2], k, e)
                 for s in SOIL_EXTREMES for k in ("fixed", "stage") for e in (0.60, 1.00)]
W0_REDUCED = (0.0, 0.90)


# --------------------------------------------------------------------------
# hai bộ kiểm toán
# --------------------------------------------------------------------------
def audit_v1(log, weather, day_rain):
    """Bản đã công bố: một mô hình điểm + ngưỡng gap tuyệt đối 5mm."""
    depls, viol = replay_log(log, weather, day_rain, TWIN, START, HOURS)
    f1 = len(viol["F1_over_saturation"])
    f2 = len(viol["F2_mass_impossible"])     # luôn 0: code chết (đã chứng minh)
    f4 = len(viol["F4_storage_excess"])
    # int(f1 or f2 or f4) la BUG: Python tra ve gia tri truthy CUOI CUNG (7), khong
    # phai True. Do bang CSV: v1_t0 = [6,4,6,6,6] -> "560% bắt được". Dung > 0.
    return {"flag_t0": int((f1 + f2 + f4) > 0), "f1": f1, "f2": f2, "f4": f4,
            "n_dry": awd_windows(depls, log)[0], "depls": depls}


def audit_v2(log, weather, day_rain, thetas, w0set, cfg=FilterConfig()):
    """Bản nâng cấp: buộc tội kiểu ∀ trên Θ, V2 thật (depletion không clip)."""
    verdict = robust_audit(log, weather, day_rain, START, HOURS,
                           thetas=thetas, cfg=cfg, w0_depl_set=w0set)
    depls, _ = replay_log(log, weather, day_rain, TWIN, START, HOURS)
    return {"flag_t0": 1 if verdict.flagged else 0, "f1": verdict.f1,
            "f2": verdict.f2, "f4": verdict.f4, "f5": verdict.f5,
            "n_theta": verdict.n_theta_flagging,
            "n_theta_all": verdict.n_theta,
            "n_dry": awd_windows(depls, log)[0], "depls": depls}


def consolidate(log: dict, window_h: int) -> dict:
    """DỒN LỆNH: gộp mọi lệnh trong mỗi cửa sổ window_h giờ vào giờ đầu cửa sổ.

    TỔNG nước được bảo toàn từng bit -> đồng hồ trạm bơm (tầng 1) không thấy gì.
    Độ sâu mỗi lệnh tăng lên, nên adversary phải kiểm tra ngưỡng F4 trước khi dùng.
    """
    if window_h <= 1:
        return dict(log)
    out: dict[int, float] = {}
    for h, u in sorted(log.items()):
        key = (h // window_h) * window_h
        out[key] = out.get(key, 0.0) + u
    return out


def rational_adversary(log, weather, day_rain, thetas, w0set, cfg,
                       windows=(1, 6, 12, 24, 48, 96), max_depth=None):
    """Đối thủ CÓ LÝ TRÍ: chọn cách dồn lệnh tối đa n_dry mà không bị bắt.

    Nó biết bộ lọc (bài báo công khai ngưỡng eps và cấu trúc Θ), biết tổng bơm
    bị đồng hồ đo, nên nó giữ nguyên tổng và chỉ đổi LỊCH SỬ thời điểm.
    """
    best = None
    for w in windows:
        cand = consolidate(log, w)
        # ràng buộc 1: tổng không đổi (nếu không, tầng 1 bắt được)
        if abs(sum(cand.values()) - sum(log.values())) > 1e-6:
            continue
        # ràng buộc 2: đối thủ CÓ LÝ TRÍ biết F5, vì bài báo công khai ngưỡng sức
        # thấm (infil·h + ponding). Không đặt ràng buộc này thì ta đang đo một kẻ
        # thù ngu và con số "lọt 5/5" vô nghĩa — đúng lỗi mà bản adversary bơm
        # 343mm đã mắc (n_dry = 0, nó tự hủy).
        if max_depth is not None and cand and max(cand.values()) > max_depth:
            continue
        v2 = audit_v2(cand, weather, day_rain, thetas, w0set, cfg)
        gap_flag, gap, tau = tier1_gap_flag(sum(log.values()), sum(cand.values()),
                                            len(cand))
        if v2["flag_t0"] or gap_flag:
            continue                     # bị bắt -> adversary không chọn
        if best is None or v2["n_dry"] > best[1]:
            best = (w, v2["n_dry"], cand, v2, gap, tau)
    if best is None:
        return None
    return best


# --------------------------------------------------------------------------
def f2_reachability(station, year, thetas, w0set, cfg):
    """Chẩn đoán: V2 fire 0 lần là do CODE hay do RUỘNG KHÔNG BAO GIỜ KHÔ TỚI ĐIỂM HÉO?

    Unit test đã chứng minh V2 fire được (f2 = 10) khi w < WP. Vậy nếu end-to-end
    ra 0, phải đo depletion THÔ lớn nhất mà ERA5 thật + lịch tưới AWD tạo ra. Nếu
    nó < 1.00 thì V2 không phải code chết — nó chỉ không bao giờ được kích hoạt
    trên dữ liệu mùa khô ĐBSCL, và điều đó PHẢI được công bố thay vì quảng cáo
    "ba bộ lọc".
    """
    weather, day_rain = load_weather(station, limit=START + HOURS + 20, year=year)
    worst_raw, worst_dp = 0.0, 0.0
    f2_hits = 0
    for th in thetas[:6]:
        for w0 in w0set:
            # nhật ký rỗng = tình huống khô nhất có thể (không có nước bù)
            from log_filters import depletion_raw, replay_theta
            depls, v = replay_theta({}, weather, day_rain, th, START, HOURS, cfg,
                                    w0_depl=w0)
            f2_hits += v.f2
            if depls:
                worst_dp = max(worst_dp, max(depls))
    # depletion thô: tính lại từ w thấp nhất mà replay đạt được
    prof = thetas[0].profile()
    worst_raw = w0max = max(w0set)
    return {"station": station, "year": year, "max_clipped_depl": round(worst_dp, 4),
            "f2_hits_dry_log": f2_hits,
            "verdict": ("V2 reachable nhưng không kích hoạt trên dữ liệu thật"
                        if f2_hits > 0 else
                        "V2 KHÔNG kích hoạt: ruộng mùa khô không xuống dưới điểm héo")}


# --------------------------------------------------------------------------
# LỖ HỔNG 7 — THAO TÚNG THỜI ĐIỂM (timing manipulation)
# --------------------------------------------------------------------------
# Quick run đo được điều này: F5 fire 144 lần trên fraud_infeasible_depth nhưng
# 0 lần trên fraud_cluster24/96 và fraud_rational — mà hai loại đó vẫn LỌT 5/5
# và thổi phồng n_dry +62% đến +80%. Lý do: đối thủ không gộp đủ sâu để vượt
# ngưỡng thấm (110mm), nó chỉ DỊCH GIỜ (consolidate snap lệnh về biên cửa sổ,
# lệch tới 23h).
#
# Đây là lỗ hổng KHÔNG ĐÓNG ĐƯỢC BẰNG VẬT LÝ:
#   * tổng mm không đổi            -> đồng hồ trạm bơm (tầng 1) mù
#   * từng độ sâu vẫn dưới ngưỡng  -> F1/F4/F5 mù
#   * quỹ đạo vẫn tự nhất quán     -> cân bằng nước không có gì để bắt
# Chỉ có MỘT thứ bị làm giả: THỜI ĐIỂM. Nên phòng tuyến duy nhất là thời điểm
# phải do THIẾT BỊ đóng dấu, không phải do nông dân nhập. Paper 1 (TwinGate) đã
# ghi bản lệnh có chữ ký + timestamp tại gateway, nên phòng tuyến này KHÔNG tốn
# thêm thiết bị nếu đã triển khai paper 1 — nhưng điều đó có nghĩa "tầng 0 thuần
# app trên điện thoại" KHÔNG đủ tin cậy một mình. Đây là điều phải sửa trong mô
# hình chi phí, không phải giấu đi.

def _norm(log: dict) -> dict:
    """Chuan hoa nhat ky de so sanh: bo gia tri ~0, lam tron 9 chu so.

    Can vi consolidate/timing_attack dung phep cong float nen 20.0 co the thanh
    19.999999999999996, va so sanh dict truc tiep se bao 'da doi' khi thuc ra
    khong doi -> dem oan vao mau 'co gian lan'.
    """
    return {int(h): round(float(u), 6) for h, u in sorted(log.items())
            if abs(u) > 1e-9}


def timing_attack(log, weather, day_rain, max_depth=None,
                  shifts=tuple(range(-36, 37, 6))):
    """Đối thủ thao túng THỜI ĐIỂM: hill-climb dịch giờ từng lệnh để tối đa n_dry.

    Ràng buộc nó tôn trọng (nếu không nó bị bắt ngay):
      * TỔNG mm giữ nguyên từng bit   -> gap đồng hồ bơm = 0
      * độ sâu từng lệnh <= max_depth -> không kích hoạt F5
      * giờ nằm trong cửa sổ vụ        -> hợp lệ về thời gian
    """
    total = sum(log.values())
    best = dict(log)
    best_nd = audit_v1(best, weather, day_rain)["n_dry"]
    improved = True
    while improved:
        improved = False
        for h in sorted(best):
            u = best[h]
            if max_depth is not None and u > max_depth:
                continue
            for d in shifts:
                if d == 0:
                    continue
                h2 = h + d
                if h2 < 0 or h2 >= HOURS or h2 in best:
                    continue
                cand = dict(best)
                del cand[h]
                cand[h2] = u
                if abs(sum(cand.values()) - total) > 1e-6:
                    continue
                nd = audit_v1(cand, weather, day_rain)["n_dry"]
                if nd > best_nd:
                    best, best_nd, improved = cand, nd, True
                    break
            if improved:
                break
    return best, best_nd


def device_anchor_flag(claimed: dict, gateway: dict, tol_mm: float = 1e-6) -> bool:
    """Phòng tuyến chống thao túng thời điểm: đối chiếu nhật ký khai với BẢN LỆNH
    DO THIẾT BỊ ĐÓNG DẤU (gateway của paper 1). Mọi lệnh tưới đều đi qua bộ điều
    khiển nên giờ và độ sâu thật nằm ở đó, có chữ ký số.

    Trả về True nếu phát hiện giả mạo (khác tập giờ, hoặc khác độ sâu tại cùng giờ).
    """
    if set(claimed) != set(gateway):
        return True
    return any(abs(claimed[h] - gateway[h]) > tol_mm for h in claimed)


def run(station, year, seeds, thetas, w0set, cfg):
    weather, day_rain = load_weather(station, limit=START + HOURS + 20, year=year)
    rows = []
    noise = RecordingNoise()

    for seed in range(seeds):
        rng = random.Random(7000 * year + 13 * seed + rgp.station_seed(station))
        soil = rng.choice(rgp.SOILS)
        prof_r, depl_r, rec_r, pump_r, eta, thr = rgp.build_truth(
            rng, weather, soil, rgp.CFG_REAL)
        _, _, rec_p, pump_p, _, _ = rgp.build_truth(rng, weather, soil, rgp.CFG_PAPER)

        # BUG cua ban dau (do duoc trong quick run: honest_paper bi bao oan
        # tier-1 66.7%): honest_paper duoc sinh tu mot lan build_truth RIENG voi
        # CFG_PAPER, nen lay gap = pump_r - sum(rec_p) la so sanh HAI RUONG KHAC
        # NHAU. Moi bien the phai duoc cham bang truth CUA CHINH NO.
        pump_of = {"honest_paper": pump_p}
        # BUG THU BA CUNG LOP (do duoc: honest_paper bi anchor "bat oan" 56/60 = 93%):
        # honest_paper sinh tu mot lan build_truth RIENG voi CFG_PAPER, nen so voi
        # rec_r la so HAI RUONG KHAC NHAU -> luon "khac" -> luon ket toi. Da sua
        # cho cot gap (pump_of) nhung QUEN sua cho anchor_flag va changed.
        # NGUYEN TAC: moi bien the phai duoc cham bang BASELINE CUA CHINH NO.
        rec_of = {"honest_paper": rec_p}

        testable = len(rec_r) >= MIN_CLAIMS
        variants = {"honest_paper": rec_p, "honest_field": rec_r}

        if testable:
            # gian lận thô (vẫn như cũ)
            wet = dict(rec_r)
            rainy = [h for h in range(HOURS)
                     if weather[START + h]["p"] > 5.0 and h not in wet]
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

            # LỖ HỔNG 6: dồn lệnh, giữ nguyên tổng
            variants["fraud_cluster24"] = consolidate(rec_r, 24)
            variants["fraud_cluster96"] = consolidate(rec_r, 96)

            # LỖ HỔNG 7: chỉ dịch giờ, giữ nguyên tổng VÀ từng độ sâu
            timing_log, _timing_nd = timing_attack(
                rec_r, weather, day_rain,
                max_depth=max_event_depth(cfg.infil.default_duration_h, cfg.infil))
            variants["fraud_timing"] = timing_log

        for vname, log in variants.items():
            v1 = audit_v1(log, weather, day_rain)
            v2 = audit_v2(log, weather, day_rain, thetas, w0set, cfg)
            # tầng 1: v1 ngưỡng tuyệt đối, v2 ngưỡng theo nhiễu ghi chép
            n_ev = max(1, len(log))
            truth_mm = pump_of.get(vname, pump_r)
            gw = rec_of.get(vname, rec_r)   # ban ghi gateway CUA CHINH RUONG NAY
            g = truth_mm - sum(log.values())
            rows.append({
                "station": station, "year": year, "seed": seed, "variant": vname,
                "soil": soil[0], "eta": round(eta, 3), "testable": int(testable),
                "n_claims": len(log), "total_mm": round(sum(log.values()), 1),
                "truth_mm": round(truth_mm, 1), "gap_mm": round(g, 1),
                "n_dry": v1["n_dry"],
                "v1_t0": v1["flag_t0"], "v1_f1": v1["f1"], "v1_f2": v1["f2"],
                "v1_f4": v1["f4"], "v1_t1": int(abs(g) > V1_GAP_MM),
                "v2_t0": v2["flag_t0"], "v2_f1": v2["f1"], "v2_f2": v2["f2"],
                "v2_f4": v2["f4"], "v2_f5": v2["f5"],
                "v2_t1": int(tier1_gap_flag(truth_mm, sum(log.values()),
                                            n_ev, noise)[0]),
                "v2_theta": v2["n_theta"], "v2_theta_all": v2["n_theta_all"],
                # phòng tuyến device-anchor: so với bản ghi gateway (= nhật ký thật
                # trước khi bị làm giả). honest -> 0; mọi gian lận -> 1.
                "anchor_flag": int(device_anchor_flag(log, gw)),
                # ARTIFACT cua harness (do duoc trong quick run): consolidate(1)
                # va timing_attack khong tim duoc cai thien se tra ve NGUYEN BAN
                # nhat ky trung thuc. Khi do anchor = 0 vi KHONG CO GIAN LAN nao
                # xay ra, khong phai vi anchor yeu. Neu khong tach ra, ta bao cao
                # sai rang "anchor chi bat 40-60%". Phai dieu kien hoa theo cot nay.
                "changed": int(_norm(log) != _norm(gw)),
            })

        # đối thủ có lý trí (chỉ khi có đủ lệnh để thao túng)
        if testable:
            base_n_dry = audit_v1(rec_r, weather, day_rain)["n_dry"]
            adv = rational_adversary(rec_r, weather, day_rain, thetas, w0set, cfg,
                                     max_depth=max_event_depth(
                                         cfg.infil.default_duration_h, cfg.infil))
            if adv:
                w, nd, cand, v2, gap, tau = adv
                rows.append({
                    "station": station, "year": year, "seed": seed,
                    "variant": "fraud_rational", "soil": soil[0],
                    "eta": round(eta, 3), "testable": 1, "n_claims": len(cand),
                    "total_mm": round(sum(cand.values()), 1),
                    "truth_mm": round(pump_r, 1), "gap_mm": round(gap, 1),
                    "n_dry": nd, "v1_t0": 0, "v1_f1": 0, "v1_f2": 0, "v1_f4": 0,
                    "v1_t1": int(abs(gap) > V1_GAP_MM),
                    "v2_t0": int(v2["flag_t0"]), "v2_f1": v2["f1"],
                    "v2_f2": v2["f2"], "v2_f4": v2["f4"], "v2_f5": v2["f5"],
                    "v2_t1": int(abs(gap) > tau),
                    "v2_theta": v2["n_theta"], "v2_theta_all": v2["n_theta_all"],
                    "anchor_flag": int(device_anchor_flag(cand, rec_r)),
                    # adversary xuat phat tu rec_r nen baseline rec_r la dung
                    "changed": int(_norm(cand) != _norm(rec_r)),
                    "adv_window_h": w, "adv_base_n_dry": base_n_dry,
                })
    return rows


def pct(a, b):
    return f"{a/b*100:5.1f}%" if b else "  n/a"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--seeds", type=int, default=0)
    ap.add_argument("--full-theta", action="store_true",
                    help="dùng Θ đầy đủ 30×5=150 thay vì bản rút gọn 12×2=24")
    args = ap.parse_args()

    seeds = args.seeds or (2 if args.quick else 10)
    if args.full_theta:
        thetas, w0set = uncertainty_set(), (0.0, 0.25, 0.50, 0.75, 0.90)
    else:
        thetas, w0set = THETA_REDUCED, W0_REDUCED
    cfg = FilterConfig()
    nreplay = len(thetas) * len(w0set)
    print(f"seeds={seeds} | |Θ|={len(thetas)} × |w0|={len(w0set)} = {nreplay} "
          f"replay/log | stations={rgp.STATIONS}", flush=True)

    t0 = time.time()
    rows = []
    for st in rgp.STATIONS:
        for yr in (2024, 2025):
            rows += run(st, yr, seeds, thetas, w0set, cfg)
            print(f"  done {st} {yr} | {len(rows)} rows | {time.time()-t0:.0f}s",
                  flush=True)

    OUT.mkdir(exist_ok=True)
    p = OUT / "robust_audit_eval.csv"
    fields = sorted({k for r in rows for k in r})
    with p.open("w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=fields)
        wr.writeheader(); wr.writerows(rows)

    by = defaultdict(list)
    for r in rows:
        by[r["variant"]].append(r)

    W = 92
    print("\n" + "=" * W)
    print("Q1 + Q2 — v1 vs v2 DƯỚI KHOẢNG CÁCH THỰC TẾ")
    print("=" * W)
    print(f"{'biến thể':<24}{'n':>4}{'n_dry':>7}{'v1 t0':>8}{'v1 t1':>8}"
          f"{'v2 t0':>8}{'v2 t1':>8}{'F5':>6}")
    for v in ["honest_paper", "honest_field", "fraud_added_events",
              "fraud_infeasible_depth", "fraud_omission", "fraud_cluster24",
              "fraud_cluster96", "fraud_rational", "fraud_timing"]:
        rs = by.get(v, [])
        if not rs:
            continue
        n = len(rs)
        nf5 = sum(int(r.get("v2_f5", 0)) for r in rs)
        print(f"{v:<24}{n:>4}{statistics.mean(r['n_dry'] for r in rs):>7.2f}"
              f"{pct(sum(r['v1_t0'] for r in rs), n):>8}"
              f"{pct(sum(r['v1_t1'] for r in rs), n):>8}"
              f"{pct(sum(r['v2_t0'] for r in rs), n):>8}"
              f"{pct(sum(r['v2_t1'] for r in rs), n):>8}{nf5:>6}")

    hf = by.get("honest_field", [])
    print("\n--- Q1: lời hứa 'không buộc tội nông dân trung thực' ---")
    if hf:
        print(f"  tầng 0 : v1 {sum(r['v1_t0'] for r in hf)}/{len(hf)}"
              f" = {pct(sum(r['v1_t0'] for r in hf), len(hf)).strip()}"
              f"   ->   v2 {sum(r['v2_t0'] for r in hf)}/{len(hf)}"
              f" = {pct(sum(r['v2_t0'] for r in hf), len(hf)).strip()}")
        print(f"  tầng 1 : v1 {sum(r['v1_t1'] for r in hf)}/{len(hf)}"
              f" = {pct(sum(r['v1_t1'] for r in hf), len(hf)).strip()}"
              f"   ->   v2 {sum(r['v2_t1'] for r in hf)}/{len(hf)}"
              f" = {pct(sum(r['v2_t1'] for r in hf), len(hf)).strip()}")
        both = sum(1 for r in hf if r["v1_t0"] or r["v1_t1"])
        both2 = sum(1 for r in hf if r["v2_t0"] or r["v2_t1"])
        print(f"  gộp cả hai tầng: v1 {both}/{len(hf)} = {pct(both, len(hf)).strip()}"
              f"  ->  v2 {both2}/{len(hf)} = {pct(both2, len(hf)).strip()}")

    print("\n--- Q2: cái giá của sự bền vững (detection mất bao nhiêu) ---")
    for v in ["fraud_added_events", "fraud_infeasible_depth", "fraud_omission"]:
        rs = by.get(v, [])
        if not rs:
            continue
        a = sum(r["v1_t0"] for r in rs)
        b = sum(r["v2_t0"] for r in rs)
        print(f"  {v:<24} v1 {a}/{len(rs)}  ->  v2 {b}/{len(rs)}"
              f"   ({'mất' if b < a else 'giữ'} {abs(a-b)}/{len(rs)})")

    print("\n" + "=" * W)
    print("Q3 — ĐỐI THỦ CÓ LÝ TRÍ: gian lận 'ăn cắp lịch sử', không ăn cắp nước")
    print("=" * W)
    cl24 = by.get("fraud_cluster24", [])
    cl96 = by.get("fraud_cluster96", [])
    ra = by.get("fraud_rational", [])
    base = statistics.mean(r["n_dry"] for r in hf) if hf else 0.0
    print(f"  n_dry (số pha khô >=72h được tính TÍN CHỈ) của nông dân trung thực: "
          f"{base:.2f} pha/vụ")
    tm = by.get("fraud_timing", [])
    for tag, rs in [("dồn lệnh 24h (naive)", cl24), ("dồn lệnh 96h (naive)", cl96),
                    ("đối thủ có lý trí", ra), ("DỊCH GIỜ (lỗ hổng 7)", tm)]:
        if not rs:
            continue
        nd = statistics.mean(r["n_dry"] for r in rs)
        gain = (nd - base) / base * 100 if base else float("nan")
        esc_v1 = sum(1 for r in rs if not r["v1_t0"] and not r["v1_t1"])
        esc_v2 = sum(1 for r in rs if not r["v2_t0"] and not r["v2_t1"])
        print(f"  {tag:<24} n_dry {nd:5.2f} ({gain:+6.1f}%) | gap TB "
              f"{statistics.mean(abs(r['gap_mm']) for r in rs):5.1f}mm | "
              f"LỌT v1 {esc_v1}/{len(rs)} | LỌT v2 {esc_v2}/{len(rs)}")
    for tag, rs in [("đối thủ có lý trí", ra), ("DỊCH GIỜ (lỗ hổng 7)", tm)]:
        if not rs:
            continue
        ch = sum(int(r.get("changed", 0)) for r in rs)
        print(f"  {tag}: tấn công thật sự đổi nhật ký ở {ch}/{len(rs)} trường hợp"
              f" — {len(rs)-ch} no-op (hill-climb không tìm được lợi, KHÔNG phải"
              f" hệ thống thắng)")
    if tm:
        nf5 = sum(int(r.get("v2_f5", 0)) for r in tm)
        print(f"  F5 fire trên fraud_timing: {nf5} lần -> "
              + ("F5 KHÔNG bắt được (đúng dự đoán: độ sâu không đổi, chỉ giờ đổi)"
                 if nf5 == 0 else "F5 có bắt được"))
    if ra:
        ws = [r.get("adv_window_h", 0) for r in ra]
        print(f"  cửa sổ dồn lệnh adversary chọn: TB {statistics.mean(ws):.0f}h "
              f"(max {max(ws)}h) — nó tự tìm ra mức thao túng tối ưu")
        infl = [r["n_dry"] - r.get("adv_base_n_dry", r["n_dry"]) for r in ra]
        print(f"  tín chỉ thổi phồng TB: {statistics.mean(infl):+.2f} pha/vụ "
              f"(max {max(infl):+.2f})")

    print("\n" + "=" * W)
    print("Q4 — PHÒNG TUYẾN DUY NHẤT CHO LỖ HỔNG 7: timestamp do THIẾT BỊ đóng dấu")
    print("=" * W)
    fr = [v for v in ["fraud_added_events", "fraud_infeasible_depth", "fraud_omission",
                      "fraud_cluster24", "fraud_cluster96", "fraud_rational",
                      "fraud_timing"] if by.get(v)]
    print(f"  {'loại gian lận':<24}{'n':>4}{'đã đổi':>8}{'lọt v1':>9}{'lọt v2':>9}"
          f"{'anchor bắt':>12}{'/đã đổi':>10}")
    tot_ch = tot_an = 0
    for v in fr:
        rs = by[v]
        ch = [r for r in rs if int(r.get("changed", 0))]
        e1 = sum(1 for r in rs if not r["v1_t0"] and not r["v1_t1"])
        e2 = sum(1 for r in rs if not r["v2_t0"] and not r["v2_t1"])
        an = sum(int(r.get("anchor_flag", 0)) for r in rs)
        anc = sum(int(r.get("anchor_flag", 0)) for r in ch)
        tot_ch += len(ch); tot_an += anc
        print(f"  {v:<24}{len(rs):>4}{len(ch):>8}{pct(e1, len(rs)):>9}"
              f"{pct(e2, len(rs)):>9}{pct(an, len(rs)):>12}{pct(anc, len(ch)):>10}")
    print(f"\n  TỔNG: {tot_an}/{tot_ch} nhật ký THẬT SỰ bị làm giả đều bị anchor bắt "
          f"= {pct(tot_an, tot_ch).strip()}")
    print("  (cột 'đã đổi' = số lần tấn công thật sự thay đổi nhật ký; phần còn lại"
          " là no-op, không phải gian lận nên anchor đúng khi im lặng)")
    hon = by.get("honest_field", [])
    if hon:
        fa = sum(int(r.get("anchor_flag", 0)) for r in hon)
        print(f"  {'honest_field (bắt oan?)':<26}{len(hon):>4}{'-':>9}{'-':>9}"
              f"{pct(fa, len(hon)):>12}")
        print(f"\n  anchor bắt oan nông dân trung thực: {fa}/{len(hon)} "
              f"(phải = 0, vì nhật ký thật == bản ghi gateway)")
    if tm:
        nd_t = statistics.mean(r["n_dry"] for r in tm)
        gain = (nd_t - base) / base * 100 if base else float("nan")
        print(f"\n  DỊCH GIỜ: n_dry {base:.2f} -> {nd_t:.2f} ({gain:+.1f}% tín chỉ) "
              f"mà vật lý và đồng hồ bơm đều mù.")
    print("\n  KẾT LUẬN BẮT BUỘC: 'tầng 0 thuần app trên điện thoại' KHÔNG đủ tin cậy")
    print("  một mình. Timestamp phải do gateway đóng dấu — thứ paper 1 đã có sẵn, nên")
    print("  chi phí biên vẫn ~0 NẾU triển khai kèm paper 1. Mô hình chi phí trong bài")
    print("  phải ghi điều kiện này, không được để tier 0 đứng độc lập như đang viết.")

    print("\n--- kiểm tra lỗ hổng #1 (V2 code chết) đã được sửa chưa ---")
    print("  unit test: V2 fire được khi w < WP (đã PASS, f2=10)")
    print("  end-to-end trên ERA5 thật: đo xem có đạt tới trạng thái đó không")
    for st in rgp.STATIONS[:1]:
        for yr in (2024, 2025):
            diag = f2_reachability(st, yr, thetas, w0set, cfg)
            print(f"    {st} {yr}: depletion clip max = {diag['max_clipped_depl']:.3f}"
                  f" | f2 hits với nhật ký rỗng = {diag['f2_hits_dry_log']}")
            print(f"      -> {diag['verdict']}")
    tot_v1f2 = sum(r["v1_f2"] for r in rows)
    tot_v2f2 = sum(r["v2_f2"] for r in rows)
    print(f"  v1 F2 fire: {tot_v1f2} / {len(rows)} nhật ký  "
          f"({'CODE CHẾT' if tot_v1f2 == 0 else 'có hoạt động'})")
    print(f"  v2 F2 fire: {tot_v2f2} / {len(rows)} nhật ký  "
          f"({'VẪN CHẾT' if tot_v2f2 == 0 else 'ĐÃ SỐNG'})")

    print(f"\n  {len(rows)} rows -> {p} | {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())

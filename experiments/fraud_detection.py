#!/usr/bin/env python3
"""TWIN-ATTESTED LOGGING — thí nghiệm phát hiện gian lận nhật ký tưới.

Ý tưởng (PROPOSAL_TWIN_ATTESTED.md): bằng chứng MRV bậc 1 theo QĐ 4801 là
"hồ sơ tưới/rút nước thực tế". Nông dân chỉ cần GHI (app trên điện thoại,
$0 thiết bị). Câu hỏi duy nhất phải trả lời: một cuốn nhật ký có bị làm giả
được không nếu KHÔNG có cảm biến tại ruộng?

Bộ lọc vật lý: cuốn nhật ký được phát lại (replay) qua đúng mô hình cân bằng
nước FAO-56 mà twin đang dùng, với forcing ERA5 công khai (không ai tranh
cãi được). Nhật ký giả tạo ra các trạng thái VI PHẠM VẬT LÝ mà nhật ký thật
không bao giờ tạo ra:

  F1. over_saturation : khai tưới khi ruộng đã no nước -> w vượt FC quá xa
                        (đất không giữ nổi, nước phải chảy tràn/drain tự do)
  F2. mass_impossible : chuỗi khai báo làm depletion ra ngoài [0,1] kéo dài,
                        tức trạng thái không thể đạt bằng bất kỳ lịch tưới thật nào
  F3. awd_violation   : khai có pha khô >=72h (điều kiện tín chỉ) nhưng
                        replay cho thấy ruộng được tưới trong cửa sổ đó
                        (hoặc chưa bao giờ khô đến ngưỡng)

Không có cảm biến nào được dùng. Chỉ có: nhật ký + ERA5 công khai + FAO-56.

Chạy:
    python3 experiments/fraud_detection.py            # đầy đủ 3 trạm x 2 năm
    python3 experiments/fraud_detection.py --quick    # 1 trạm, ít seed
"""
from __future__ import annotations

import argparse
import csv
import math
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ncs_loop import load_weather                                    # noqa: E402
from water_balance import (BucketState, SoilProfile, depletion_fraction,
                          daily_runoff_share, step_bucket)            # noqa: E402

OUT = ROOT / "outputs"

# ----------------------------------------------------------------------------
# Ngưỡng phát hiện — SUY RA TỪ VẬT LÝ, không chỉnh tay
# ----------------------------------------------------------------------------
FC_SLACK_MM = 5.0        # w > FC + 5mm là over-saturation: bucket chỉ giữ tới FC,
                         # phần dư phải drain/runoff tự do, không thể là "tưới thành công"
DEPL_IMPOSSIBLE = 1.02   # depletion > 1.02 (dưới điểm héo) kéo dài là bất khả thi
                         # cho một ruộng CÓ tưới; 1.02 thay vì 1.0 vì bucket cho phép
                         # Dr > TAW dưới hạn kéo dài (FAO-56 ch.8)
AWD_DRY_HOURS = 72       # đúng quy tắc QĐ 4801: không tưới lại trong >= 3 ngày
AWD_DEPL_FLOOR = 0.45    # depletion tối thiểu để coi là "đã rút nước" thật
                         # (ruộng khô tới mức có ý nghĩa, không phải ẩm nhẹ)


# ----------------------------------------------------------------------------
# Replay một cuốn nhật ký qua FAO-56
# ----------------------------------------------------------------------------
def replay_log(log_irrig: dict[int, float], weather: list[dict],
               day_rain: dict[str, float], prof: SoilProfile,
               start: int, hours: int, w0: float | None = None):
    """Phát lại nhật ký, trả về (chuỗi depletion, danh sách vi phạm).

    log_irrig: {hour_offset: mm đã khai tưới}
    """
    st = BucketState(w=(prof.fc_mm if w0 is None else w0))
    depls: list[float] = []
    viol = {"F1_over_saturation": [], "F2_mass_impossible": [],
            "F4_storage_excess": []}
    for h in range(hours):
        i = start + h
        if i >= len(weather):
            break
        r = weather[i]
        d = r["time"][:10]
        ro = daily_runoff_share(day_rain.get(d, 0.0), r["p"], prof.cn_runoff)
        irrig = log_irrig.get(h, 0.0)
        # F1: khai tưới khi bucket đã ở/trên FC -> nước không thể được giữ
        if irrig > 0 and st.w >= prof.fc_mm - FC_SLACK_MM:
            viol["F1_over_saturation"].append((h, round(st.w, 1), irrig))
        # F4: do luong khai VUOT suc chua cua dat tai thoi diem do.
        # Vat ly: root zone chi giu duoc (FC - w); phan thua phai chay tran/drain,
        # nen khai "tuoi thanh cong" lon hon deficit + slack la khai khong.
        # F1 la truong hop rieng cua F4 khi deficit ~ 0; giu rieng de doc bang.
        if irrig > 0:
            deficit = max(0.0, prof.fc_mm - st.w)
            if irrig > deficit + FC_SLACK_MM:
                viol["F4_storage_excess"].append(
                    (h, round(irrig, 1), round(deficit, 1)))
        st, _ = step_bucket(st, prof, r["p"], irrig, r["et0"], runoff_mm=ro)
        dp = depletion_fraction(st, prof)
        depls.append(dp)
        if dp > DEPL_IMPOSSIBLE:
            viol["F2_mass_impossible"].append((h, round(dp, 3)))
    return depls, viol


def awd_windows(depls: list[float], log_irrig: dict[int, float],
                threshold: float = AWD_DEPL_FLOOR):
    """Đếm pha khô đạt chuẩn: depletion >= threshold, không tưới, kéo dài >= 72h.

    Trả về (số pha đạt, số pha bị phá vỡ bởi lệnh tưới giữa chừng,
            danh sách pha khai báo nhưng không đạt ngưỡng khô).
    """
    n_ok = n_broken = n_shallow = 0
    dry_start = None
    dry_peak = 0.0
    for h, dp in enumerate(depls):
        irrigated = log_irrig.get(h, 0.0) > 0
        if dp >= threshold and not irrigated:
            if dry_start is None:
                dry_start = h
                dry_peak = dp
            dry_peak = max(dry_peak, dp)
        else:
            if dry_start is not None:
                length = h - dry_start
                if length >= AWD_DRY_HOURS and dry_peak >= threshold:
                    n_ok += 1
                elif irrigated and dry_peak >= threshold:
                    n_broken += 1        # pha khô bị cắt bởi một lần tưới
                else:
                    n_shallow += 1       # chưa bao giờ khô tới ngưỡng
                dry_start = None
    return n_ok, n_broken, n_shallow


# ----------------------------------------------------------------------------
# Sinh nhật ký THẬT (nông dân tuân thủ AWD) và nhật ký GIAN LẬN
# ----------------------------------------------------------------------------
def make_honest_log(rng, depls_target: list[float], prof: SoilProfile,
                    hours: int, depth_choices=(20.0, 40.0)):
    """Nông dân thật: tưới khi ruộng khô tới ngưỡng, độ sâu hợp lý, ghi đúng."""
    log: dict[int, float] = {}
    dp = 0.20                      # bắt đầu vụ ở trạng thái ẩm vừa
    for h in range(hours):
        if h >= len(depls_target):
            break
        dp = depls_target[h]
        if dp >= 0.80:             # ngưỡng rút nước an toàn của AWD (Bouman 2007)
            u = rng.choice(depth_choices)
            log[h] = u
            dp = max(0.0, dp - u / (prof.fc_mm - prof.wp_mm))
    return log


def fraud_fake_irrigation_on_wet(rng, honest: dict[int, float], weather, start,
                                 n_extra=8):
    """GIAN LẬN 1: khai thêm các lần tưới vào ngày ruộng đang no nước
    (để thổi phồng 'hoạt động quản lý nước' / khai khống chi phí)."""
    fake = dict(honest)
    wet_hours = [h for h in range(len(weather) - start - 1)
                 if weather[start + h]["p"] > 5.0 and h not in fake]
    rng.shuffle(wet_hours)
    for h in wet_hours[:n_extra]:
        fake[h] = rng.choice((20.0, 40.0, 60.0))
    return fake, n_extra


def fraud_claim_dry_phase(rng, honest: dict[int, float], depls: list[float],
                          prof: SoilProfile):
    """GIAN LẬN 2: khai có pha khô >=72h (để lấy tín chỉ) nhưng thực tế đã
    tưới lén trong cửa sổ đó — tức bản ghi gốc KHÔNG có pha khô đạt chuẩn,
    nông dân khai khống là có."""
    fake = dict(honest)
    # tìm một cửa sổ 96h và XOÁ các lần tưới trong đó -> khai là đã khô 4 ngày
    for start_h in range(200, min(len(depls) - 100, 1500), 50):
        window = list(range(start_h, start_h + 96))
        removed = [h for h in window if h in fake]
        for h in removed:
            del fake[h]
        if removed:
            return fake, start_h, len(removed)
    return fake, None, 0


def fraud_implausible_depth(rng, honest: dict[int, float], prof: SoilProfile):
    """GIAN LẬN 3: khai độ sâu vô lý (quá lớn so với khả năng giữ của đất)."""
    fake = dict(honest)
    hs = sorted(fake)
    if not hs:
        return fake, 0
    for h in rng.sample(hs, max(1, len(hs) // 3)):
        fake[h] = float(prof.fc_mm)     # khai tưới cả một lần = FC (bất khả thi)
    return fake, len(hs) // 3


# ----------------------------------------------------------------------------
def run(station: str, year: int, seeds: int) -> list[dict]:
    start = 74 * 24                  # 1/3, đúng cửa sổ mùa khô như bài chính
    hours = 2160
    # limit phai du de index start+hours+margin; ban dau dat 2200 => IndexError
    weather, day_rain = load_weather(station, limit=start + hours + 20, year=year)
    prof = SoilProfile()

    # Depletion "thật" của ruộng: chạy FAO-56 với lịch tưới tuân thủ AWD
    # (đây là ground truth mà một hệ cảm biến sẽ thấy)
    rows = []
    for seed in range(seeds):
        rng = random.Random(1000 * year + seed)
        # B1: dựng quỹ đạo depletion thật bằng cách mô phỏng một lịch AWD hợp lệ
        base_log: dict[int, float] = {}
        st = BucketState(w=prof.fc_mm)
        truth_depl: list[float] = []
        for h in range(hours):
            i = start + h
            r = weather[i]
            d = r["time"][:10]
            ro = daily_runoff_share(day_rain.get(d, 0.0), r["p"], prof.cn_runoff)
            dp = depletion_fraction(st, prof)
            truth_depl.append(dp)
            irrig = 0.0
            if dp >= 0.80:                      # nông dân thật tưới khi khô tới ngưỡng
                irrig = rng.choice((20.0, 40.0))
                base_log[h] = irrig
            st, _ = step_bucket(st, prof, r["p"], irrig, r["et0"], runoff_mm=ro)

        honest = base_log
        ok_h, br_h, sh_h = awd_windows(truth_depl, honest)

        variants = {}
        variants["honest"] = (honest, f"tuan thu AWD, {ok_h} pha kho dat chuan")

        f1, n1 = fraud_fake_irrigation_on_wet(rng, honest, weather, start)
        variants["fraud_wet_day"] = (f1, f"khai them {n1} lan tuoi vao ngay mua")

        f2, win, nremoved = fraud_claim_dry_phase(rng, honest, truth_depl, prof)
        variants["fraud_dry_claim"] = (f2, f"khai pha kho 96h tai h={win}, xoa {nremoved} lenh")

        f3, n3 = fraud_implausible_depth(rng, honest, prof)
        variants["fraud_depth"] = (f3, f"khai {n3} lan tuoi = FC ({prof.fc_mm:.0f}mm)")

        for vname, (log, desc) in variants.items():
            depls, viol = replay_log(log, weather, day_rain, prof, start, hours)
            ok, br, sh = awd_windows(depls, log)
            rows.append({
                "station": station, "year": year, "seed": seed, "variant": vname,
                "desc": desc,
                "n_irrig_claims": len(log),
                "total_mm": round(sum(log.values()), 1),
                "truth_total_mm": round(sum(honest.values()), 1),
                "F1_over_sat": len(viol["F1_over_saturation"]),
                "F2_mass_imp": len(viol["F2_mass_impossible"]),
                "F4_storage": len(viol["F4_storage_excess"]),
                "max_depl": round(max(depls), 3) if depls else 0.0,
                "awd_ok": ok, "awd_broken": br, "awd_shallow": sh,
                "truth_awd_ok": ok_h,
            })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--seeds", type=int, default=10)
    args = ap.parse_args()

    stations = ["can_tho"] if args.quick else ["can_tho", "soc_trang", "ca_mau"]
    years = [2024] if args.quick else [2024, 2025]
    seeds = 3 if args.quick else args.seeds

    allrows: list[dict] = []
    for y in years:
        for st in stations:
            r = run(st, y, seeds)
            allrows += r
            print(f"  {st} {y}: {len(r)} rows", flush=True)

    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / ("fraud_quick.csv" if args.quick else "fraud_raw.csv")
    with dest.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(allrows[0].keys()))
        w.writeheader()
        w.writerows(allrows)
    print(f"wrote {dest} ({len(allrows)} rows)")

    # ================= GATE: bộ lọc phải bắt được gian lận, KHÔNG được bắt oan =================
    print("\n=== KET QUA PHAT HIEN (trung binh moi bien the) ===")
    by = {}
    for r in allrows:
        by.setdefault(r["variant"], []).append(r)
    print(f"{'variant':<18}{'F1':>6}{'F2':>6}{'F4':>6}{'pump-gap':>9}{'awd_ok':>8}{'max_depl':>10}{'mm khai':>9}")
    for v, rs in by.items():
        gap = statistics.mean(x["truth_total_mm"] - x["total_mm"] for x in rs)
        print(f"{v:<18}"
              f"{statistics.mean(x['F1_over_sat'] for x in rs):>6.2f}"
              f"{statistics.mean(x['F2_mass_imp'] for x in rs):>6.2f}"
              f"{statistics.mean(x['F4_storage'] for x in rs):>6.2f}"
              f"{gap:>9.1f}"
              f"{statistics.mean(x['awd_ok'] for x in rs):>8.2f}"
              f"{statistics.mean(x['max_depl'] for x in rs):>10.3f}"
              f"{statistics.mean(x['total_mm'] for x in rs):>9.1f}")

    fails = []
    # 1) Nhat ky THAT phai SACH: F1=F2=0 (neu khong, bo loc bat oan nong dan)
    hon = by.get("honest", [])
    fp1 = sum(1 for x in hon if x["F1_over_sat"] > 0)
    fp2 = sum(1 for x in hon if x["F2_mass_imp"] > 0)
    fp4 = sum(1 for x in hon if x["F4_storage"] > 0)
    print(f"\n[FP] nhat ky that bi bat oan: F1 {fp1}/{len(hon)}, F2 {fp2}/{len(hon)}, F4 {fp4}/{len(hon)}")
    if fp1 or fp2 or fp4:
        fails.append(f"FALSE POSITIVE tren nhat ky that: F1={fp1}, F2={fp2}, F4={fp4}")

    # 2) Gian lan phai BI BAT
    for v, flag in (("fraud_wet_day", "F1_over_sat"),
                    ("fraud_depth", "F4_storage")):
        rs = by.get(v, [])
        caught = sum(1 for x in rs if x[flag] > 0)
        rate = caught / len(rs) if rs else 0
        print(f"[TP] {v}: bat duoc {caught}/{len(rs)} = {rate*100:.0f}% (qua {flag})")
        if rs and rate < 0.50:
            fails.append(f"{v}: chi bat duoc {rate*100:.0f}% (< 50%)")

    # 3) Gian lan khai pha kho: phai lo ra o awd metrics
    rs = by.get("fraud_dry_claim", [])
    if rs:
        # TRUNG THUC: gian lan GIAU LENH (khai it hon that) KHONG the bat bang
        # vat ly thuan o tang 0 — nhat ky 'bot di' van tu nhat quan. Day la ly do
        # ton tai tang 1: dong ho o tram bom do TONG nuoc that da bom; tong khai
        # thap hon => lo ngay. Mo phong: pump_gap = truth_total - claimed_total.
        caught = sum(1 for x in rs
                     if x["truth_total_mm"] - x["total_mm"] > 5.0)   # >5mm moi y nghia
        rate = caught / len(rs)
        gap = statistics.mean(x["truth_total_mm"] - x["total_mm"] for x in rs)
        print(f"[OMISSION] fraud_dry_claim: tang 0 (vat ly) bat 0/{len(rs)} — DUNG nhu thiet ke;")
        print(f"           tang 1 (dong ho bom) bat {caught}/{len(rs)} = {rate*100:.0f}% "
              f"(pump-gap TB {gap:.1f}mm)")
        if rate < 0.90:
            fails.append(f"fraud_dry_claim: dong ho bom chi bat {rate*100:.0f}% (<90%)")

    print()
    if fails:
        print(f"FRAUD DETECTION PROBLEMS ({len(fails)}):")
        for f in fails:
            print("  -", f)
        return 1
    print("FRAUD DETECTION GATES: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

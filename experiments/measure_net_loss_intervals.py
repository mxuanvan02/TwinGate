#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""MEASURE: gia thiet "khoang ton that rong" (Delta_t >= 0) song duoc bao lau tren du lieu that.

BAI TOAN
Mệnh đề về lợi ích tín chỉ chứng minh rằng hoãn khai báo làm tăng phần thiếu hụt,
nhưng lập luận đó cần khoảng chờ giữa hai lần khai là khoảng mất nước ròng:
    Delta_t = sum_s (ETc_s + DP_s - P_s^+) >= 0
Cân bằng nước có chứa mưa, nên một trận mưa đủ lớn có thể làm GIẢM độ cạn kiệt và
phá giả thiết. Script này đo tần suất giả thiết bị phá thay vì giả định nó.

HAI QUY ĐẠO ĐƯỢC ĐO (đúng hai đối tượng báo cáo phân biệt)
  replay : twin kiểm toán phát lại nhật ký bằng mưa ô lưới ERA5 quan sát
           (reality_gap_probe.audit/replay_log, TWIN = SoilProfile() đã công bố).
           Đây là đối tượng mà mệnh đề nói tới.
  truth  : "ruộng thật" sinh bởi build_truth(..., CFG_REAL) — mưa tại ruộng lệch
           0.7-1.4 lần ô lưới cộng nhiễu 0.35 mm, eta 0.60-0.85, rò rỉ bờ, Kc theo
           giai đoạn, đất theo dải FAO-56 Table 2, trễ ghi/làm tròn/quên ghi.

ĐỊNH NGHĨA "KHOẢNG" (ghim rõ để tái lập được)
  Khoảng = giữa hai giờ khai liên tiếp trong nhật ký được kiểm toán (rec_r), tức
  đúng đối tượng mà kẻ gian lận chọn để hoãn. Chỉ lấy các nhật ký có ít nhất
  MIN_CLAIMS lần khai (tập kiểm định được, như thí nghiệm chính).
  Delta_t = depletion(h_end - 1) - depletion(h_start), theo depletion_fraction của
  src/water_balance.py; dương = mất nước ròng.

TÁI LẬP
  3 trạm x 2 năm (2024, 2025) x 10 seed. Seed dựng đúng công thức của
  reality_gap_probe.run: 7000*year + 13*seed + station_seed(station), và gọi
  build_truth(CFG_PAPER) TRƯỚC build_truth(CFG_REAL) để giữ nguyên chuỗi seed.
  Không dùng hash() (Python randomize theo PYTHONHASHSEED).

  python3 experiments/measure_net_loss_intervals.py
  -> outputs/net_loss_intervals.csv   (mỗi dòng một khoảng, có d_replay/d_truth)
  -> outputs/_net_loss_summary.json   (nguồn duy nhất của các số tổng hợp được công bố)

CHỨNG MINH BẤT BIẾN
  Nếu một con số in ra ở đây khác với outputs/_net_loss_summary.json đã commit,
  script exit != 0. Mọi con số công bố về phép đo này chỉ được trích từ file JSON đó,
  không được gõ tay vào văn bản.
"""
from __future__ import annotations

import csv
import json
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "experiments"))

import reality_gap_probe as rgp                      # noqa: E402
from ncs_loop import load_weather                     # noqa: E402
from fraud_detection import replay_log                # noqa: E402

SEEDS = 10
YEARS = (2024, 2025)
START, HOURS = rgp.START, rgp.HOURS
STATIONS = rgp.STATIONS
TOL = 1e-12


def intervals_of(rec: dict) -> list[tuple[int, int]]:
    ks = sorted(rec)
    return [(ks[i], ks[i + 1]) for i in range(len(ks) - 1)]


def delta_at(depl: list[float], a: int, b: int) -> float:
    n = len(depl)
    if n == 0:
        return 0.0
    ia = min(max(a, 0), n - 1)
    ib = min(max(b - 1, 0), n - 1)
    return depl[ib] - depl[ia]


def collect() -> list[dict]:
    rows: list[dict] = []
    for year in YEARS:
        for st in STATIONS:
            weather, day_rain = load_weather(st, limit=START + HOURS + 20, year=year)
            for seed in range(SEEDS):
                rng = random.Random(7000 * year + 13 * seed + rgp.station_seed(st))
                soil = rng.choice(rgp.SOILS)
                # giữ đúng chuỗi seed của reality_gap_probe.run
                rgp.build_truth(rng, weather, soil, rgp.CFG_PAPER)
                _, depl_r, rec_r, _, _, _ = rgp.build_truth(rng, weather, soil, rgp.CFG_REAL)
                if len(rec_r) < rgp.MIN_CLAIMS:
                    continue                      # tập kiểm định được
                ivs = intervals_of(rec_r)
                if not ivs:
                    continue
                depls, _ = replay_log(rec_r, weather, day_rain, rgp.TWIN, START, HOURS)
                for a, b in ivs:
                    rows.append(dict(
                        year=year, station=st, seed=seed, soil=soil[0],
                        h_start=a, h_end=b, duration_h=b - a,
                        d_replay=delta_at(depls, a, b),
                        d_truth=delta_at(depl_r, a, b),
                    ))
    return rows


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    assert n > 0, "khong co khoang nao — kiem tra lai du lieu thoi tiet"
    neg_rep = [r for r in rows if r["d_replay"] < -TOL]
    neg_tru = [r for r in rows if r["d_truth"] < -TOL]
    pos_tru = [r for r in rows if r["d_truth"] >= -TOL]
    drops = [-r["d_truth"] for r in neg_tru]
    s = {
        "definition": "interval between consecutive claims of the audited log (CFG_REAL); "
                      "Delta = depletion(h_end-1) - depletion(h_start)",
        "stations": list(STATIONS), "years": list(YEARS), "seeds_per_cell": SEEDS,
        "n_intervals": n,
        "replay": {
            "n_negative": len(neg_rep),
            "pct_negative": round(100 * len(neg_rep) / n, 1),
        },
        "truth": {
            "n_negative": len(neg_tru),
            "pct_negative": round(100 * len(neg_tru) / n, 1),
            "mean_drop": round(statistics.fmean(drops), 4) if drops else 0.0,
            "max_drop": round(max(drops), 4) if drops else 0.0,
            "mean_duration_h_negative": round(statistics.fmean(r["duration_h"] for r in neg_tru), 1) if neg_tru else 0.0,
            "mean_duration_h_net_loss": round(statistics.fmean(r["duration_h"] for r in pos_tru), 1) if pos_tru else 0.0,
        },
        "by_year": {},
    }
    for y in YEARS:
        sub = [r for r in rows if r["year"] == y]
        s["by_year"][str(y)] = {
            "n": len(sub),
            "n_negative": sum(1 for r in sub if r["d_truth"] < -TOL),
        }
    return s


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = collect()
    s = summarize(rows)

    csv_path = OUT / "net_loss_intervals.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow({k: (f"{v:.6f}" if isinstance(v, float) else v) for k, v in r.items()})

    json_path = OUT / "_net_loss_summary.json"
    old = None
    if json_path.exists():
        try:
            old = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            old = None
    json_path.write_text(json.dumps(s, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("=" * 78)
    print(f"  {s['n_intervals']} khoang giua hai lan khai | {len(STATIONS)} tram x {len(YEARS)} nam x {SEEDS} seed")
    print(f"  QUY DAO PHAT LAI (doi tuong cua menh de): vi pham {s['replay']['n_negative']}/{s['n_intervals']}"
          f" ({s['replay']['pct_negative']}%)")
    t = s["truth"]
    print(f"  RUONG THAT (CFG_REAL, mua lech 0.7-1.4x): vi pham {t['n_negative']}/{s['n_intervals']}"
          f" ({t['pct_negative']}%)")
    print(f"    giam do can kiet: TB {t['mean_drop']} | lon nhat {t['max_drop']}")
    print(f"    do dai khoang: vi pham TB {t['mean_duration_h_negative']}h | net-loss TB {t['mean_duration_h_net_loss']}h")
    for y, v in s["by_year"].items():
        print(f"    nam {y}: {v['n_negative']}/{v['n']} khoang vi pham")
    print(f"  -> {csv_path.name} ({len(rows)} dong) | {json_path.name}")

    if old is not None and old != s:
        diff = [k for k in set(old) | set(s) if old.get(k) != s.get(k)]
        print(f"\n!!! KET QUA KHAC BAN DA COMMIT o khoa: {diff}")
        print("    Van ban cong bo dang trich so cu -> phai sua lai roi commit.")
        return 1
    print("\nGATE PASS: ket qua khop ban da commit (hoac lan chay dau tien).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

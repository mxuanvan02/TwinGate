#!/usr/bin/env python3
"""Tinh outputs/_verified_numbers.json tu hai snapshot eval_theta_*.csv.

File nay tong hop phep ghep cap dung de bao cao muc thoi phong tin chi: moi nhat ky
gian lan duoc ghep voi nhat ky trung thuc CUA CHINH quy dao do (cung tram, cung nam,
cung seed, cung loai dat), va chi nhung tan cong that su doi nhat ky (cot `changed`)
moi duoc tinh. Hai tap do cung mau nen muc thoi phong khong bi lech do chon mau.

Moi khoa co dang `<snapshot>|<variant>` va chua:
  n       so cap ghep duoc
  a       trung binh so pha kho cua nhat ky gian lan
  b       trung binh so pha kho cua nhat ky trung thuc ghep cap
  infl    muc thoi phong theo phan tram
  mean_d  hieu trung binh a - b
  se      sai so chuan cua hieu
  t       gia tri thong ke mean_d / se

Doc hai snapshot:
  eval_theta_reduced_10seeds.csv  |Theta| rut gon 12x2=24, 10 seeds -> 281 nhat ky
  eval_theta_full_3seeds.csv      |Theta| day du 30x5=150, 3 seeds  ->  85 nhat ky

CHAY:  python experiments/make_verified_numbers.py
Truoc do can co hai snapshot (reproduce.sh sinh chung tu robust_audit_eval.py).
"""
from __future__ import annotations

import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs"

# Thu tu khoa va thu tu snapshot bi khoa boi dinh dang da cong bo cua file
# ket qua; giu nguyen de tai tao duoc giong het tung byte.
CREDIT_ORDER = [
    "fraud_timing", "fraud_rational", "fraud_cluster24", "fraud_cluster96",
    "fraud_added_events", "fraud_infeasible_depth", "fraud_omission",
]
SNAPSHOTS = [("reduced", "eval_theta_reduced_10seeds.csv"),
             ("full", "eval_theta_full_3seeds.csv")]


def load(name: str) -> list[dict]:
    p = OUT / name
    if not p.exists():
        raise SystemExit(
            f"!! thieu outputs/{name}\n"
            f"   chay truoc:  python experiments/robust_audit_eval.py --seeds 10 "
            f"--out {SNAPSHOTS[0][1]}\n"
            f"              python experiments/robust_audit_eval.py --full-theta "
            f"--seeds 3")
    with p.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def I(r: dict, k: str) -> int:
    """CSV tra ve CHUOI, nen `not r['v2_t0']` voi '0' la `not '0'` = False.
    Moi phep doc so deu phai ep kieu tuong minh."""
    v = r.get(k, "")
    return int(float(v)) if v not in ("", None) else 0


def F(r: dict, k: str) -> float:
    v = r.get(k, "")
    return float(v) if v not in ("", None) else float("nan")


def pair_key(r: dict) -> tuple:
    return (r["station"], r["year"], r["seed"], r["soil"])


def credit_stats(rows: list[dict]) -> dict:
    by = defaultdict(list)
    for r in rows:
        by[r["variant"]].append(r)
    hf = by.get("honest_field", [])
    hfmap = {pair_key(r): r for r in hf}

    out = {}
    for v in CREDIT_ORDER:
        rs = by.get(v, [])
        if not rs:
            continue
        pairs = [(F(r, "n_dry"), F(hfmap[pair_key(r)], "n_dry"))
                 for r in rs if I(r, "changed") and pair_key(r) in hfmap]
        if not pairs:
            continue
        a = statistics.mean(x[0] for x in pairs)
        b = statistics.mean(x[1] for x in pairs)
        d = [x[0] - x[1] for x in pairs]
        mean_d = statistics.mean(d)
        sd = statistics.stdev(d) if len(d) > 1 else 0.0
        se = sd / len(d) ** 0.5 if d else 0.0
        out[v] = {
            "n": len(pairs),
            "a": a,
            "b": b,
            # THU TU PHEP TOAN QUAN TRONG cho viec tai tao giong het tung byte:
            # 100*(a-b)/b. Viet (a-b)/b*100 cho ra khac 1-2 ULP o chu so cuoi cua
            # 5/14 khoa (da do bang cach so sanh repr(), khong so sanh gia tri).
            "infl": 100 * (a - b) / b if b else 0.0,
            "mean_d": mean_d,
            "se": se,
            "t": mean_d / se if se else 0.0,
        }
    return out


def main() -> int:
    result = {}
    for tag, fname in SNAPSHOTS:
        stats = credit_stats(load(fname))
        print(f"  {tag:8s} {fname}: {len(stats)} bien the")
        for v in CREDIT_ORDER:
            if v in stats:
                result[f"{tag}|{v}"] = stats[v]

    dest = OUT / "_verified_numbers.json"
    # File ket qua da cong bo ket thuc bang '}' khong co newline cuoi file
    # (kiem bang `tail -c 40 outputs/_verified_numbers.json | od -c`), nen khong
    # ghi them '\n' — them vao se lech byte.
    dest.write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(f"  -> outputs/{dest.name} ({dest.stat().st_size} byte, {len(result)} khoa)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env bash
# =============================================================================
# TwinGate — one-command reproduction of every number in the paper.
#
#   A Digital-Twin Safety Gate for Irrigation Command Dispatch over Lossy
#   Networks and Its Relevance to Emission MRV
#
# What this does, end to end:
#   1. creates an isolated Python virtual environment (.venv)
#   2. installs the third-party deps (numpy, scipy for paired stats,
#      matplotlib for the figures)
#   3. fetches the real ERA5 hourly weather (2024 + 2025) for three Mekong-delta
#      stations from the public Open-Meteo archive  (skipped if already cached)
#   4. runs the six invariant test scripts + the d_max proposition test
#   5. runs the main grid (7 560 episodes/year x 2 years), the ablation, the
#      deployment sweep, the multi-field experiment, the sigma x delta sweep,
#      the salinity scenario, the fraud-detection experiment (240 audited
#      irrigation logs, paper 2) and the robust-audit evaluation (v2 filters
#      under seven reality-gap axes plus nine fraud variants)
#   6. runs the paired Wilcoxon analysis and regenerates every figure + LaTeX
#      table
#
# All results land under outputs/. The manuscript tables are emitted by
# experiments/make_latex_tables.py into paper/tables/, so the paper cannot
# drift from the code.
#
# Usage:
#   ./reproduce.sh            # full reproduction (~2-4 min on a laptop)
#   ./reproduce.sh --quick    # smoke run (2 seeds, main grid only)
#   ./reproduce.sh --tests    # test scripts only
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PY="${PYTHON:-python3}"
MODE="full"
[[ "${1:-}" == "--quick" ]] && MODE="quick"
[[ "${1:-}" == "--tests" ]] && MODE="tests"

echo "== TwinGate reproduction ($MODE) =="
echo "   root: $ROOT"
echo "   python: $($PY --version 2>&1)"

# --- 1. virtualenv ---------------------------------------------------------
if [[ ! -d .venv ]]; then
  echo "[1/6] creating .venv"
  "$PY" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --quiet --upgrade pip

# --- 2. deps ----------------------------------------------------------------
echo "[2/6] installing deps"
python -m pip install --quiet -r requirements.txt

# --- 3. weather -------------------------------------------------------------
echo "[3/6] ERA5 weather (Open-Meteo archive; cached CSVs reused)"
if [[ ! -f data/era5_multi/can_tho_2024.csv ]]; then
  python data/fetch_era5_multi.py --year 2024 can_tho soc_trang ca_mau
  python data/fetch_era5_multi.py --year 2025 can_tho soc_trang ca_mau
else
  echo "   cache hit — skipping fetch"
fi

# --- 4. tests ---------------------------------------------------------------
echo "[4/6] invariant + proposition test scripts"
for t in tests/test_water_balance.py tests/test_twin_gate.py \
         tests/test_command_resend.py tests/test_ncs_invariants.py \
         tests/test_tide_salinity.py tests/test_dmax_proposition.py \
         tests/test_log_filters.py \
         experiments/fraud_detection.py; do
  printf '   %-40s' "$t"
  if python "$t" > "/tmp/$(basename "$t").log" 2>&1; then
    echo "PASS"
  else
    echo "FAIL (see /tmp/$(basename "$t").log)"; exit 1
  fi
done
[[ "$MODE" == "tests" ]] && { echo "== tests done =="; exit 0; }

# --- 5. experiments ---------------------------------------------------------
if [[ "$MODE" == "quick" ]]; then
  echo "[5/6] main grid (QUICK: 2 seeds)"
  python experiments/run_main.py --quick
else
  echo "[5/6] full experiment suite"
  python experiments/run_main.py --seeds 10
  python experiments/run_main.py --seeds 10 --year 2025
  python experiments/run_ablation.py
  python experiments/run_deployment.py
  python experiments/run_multi_field.py
  python experiments/sweep_sigma_delta.py
  python experiments/sweep_salinity.py
  python experiments/fraud_detection.py
  # v2: bo loc ben vung. reality_gap_probe dung ERA5 that nen phai co data truoc.
  python experiments/reality_gap_probe.py 3
  python experiments/robust_audit_eval.py --quick
  python experiments/analyze_robust_eval.py outputs/robust_audit_eval.csv
  # chan doan V2 co the kich hoat tren lua mua kho khong (150 cau hinh)
  python experiments/diag_f2.py
  # bang cua bai 2 theo truc device-anchored (gate: anchor 116/116, bat oan 0)
  python experiments/make_tables_anchored.py
  python experiments/make_tables_paper2.py
fi

# --- 6. stats + figures + tables -------------------------------------------
echo "[6/6] statistics, figures, LaTeX tables"
python experiments/stats_analysis.py
python figures/fig_method.py
python figures/fig_results.py
python experiments/make_latex_tables.py
python experiments/extract_paper_numbers.py

echo
echo "== reproduction complete =="
echo "   CSV results : outputs/"
echo "   figures     : figures/*.pdf"
echo "   LaTeX tables: paper/tables/*.tex"

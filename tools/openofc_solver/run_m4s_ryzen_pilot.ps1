param(
    [string]$OutputDir = "runs\m4s_f14_f14_pilot"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

Write-Host "[M4S] Materializing certified Joker semantics..."
python tools/openofc_solver/apply_m1b_joker_semantics.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[M4S] Running conservative resumable F14/F14 pilot..."
python tools/openofc_solver/run_m4s_multiseed.py `
    --output-dir $OutputDir `
    --pair 14:14 `
    --buttons 0,1 `
    --train-worlds-per-state 1 `
    --heldout-worlds-per-state 1 `
    --synthetic-worlds 2 `
    --max-candidates 8 `
    --selfplay-iterations 2 `
    --epochs-per-iteration 2 `
    --support-gap-samples 1 `
    --base-seed 20260828
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[M4S] PASS. Report: $OutputDir\M4S_HELDOUT_REPORT.json"

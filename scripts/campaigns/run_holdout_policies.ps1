# Runs the complementary holdout policy comparison from the project root.
# Examples:
#   .\scripts\campaigns\run_holdout_policies.ps1 -DryRun
#   .\scripts\campaigns\run_holdout_policies.ps1
#   .\scripts\campaigns\run_holdout_policies.ps1 -Compositions moead_blmr -Workers 10
param(
    [string[]]$Compositions = @('moead_blmr','spea2_blmr','nsga2_blmr','quartet_blmr'),
    [string[]]$Policies = @('uniform','sw_ucb','scaled','ph','dynamic'),
    [int]$Workers = 14,
    [switch]$DryRun
)
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $root
$env:PYTHONPATH = 'src'
$output = 'results\experiments\holdout_policy_comparison_20261025'
$arguments = @('scripts\campaigns\run_holdout_policy_comparison.py', '--output-dir', $output, '--workers', $Workers,
               '--compositions') + $Compositions + @('--policies') + $Policies
if (Test-Path $output) { $arguments += '--resume' }
if ($DryRun) { $arguments += '--dry-run' }
& .venv\Scripts\python.exe @arguments

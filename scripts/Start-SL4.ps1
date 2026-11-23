# Windows entry point for the SL4 safety-first offline workflow.
# One-line invocation: powershell.exe -ExecutionPolicy Bypass -File .\scripts\Start-SL4.ps1 -Action Inventory
[CmdletBinding()]
param(
  [ValidateSet("Inventory","Inspect","Backup","Prepare","VerifyBackup","VerifyPins","RestoreOffline")][string]$Action="Inventory",
  [string]$SourceEfi="",
  [string]$BackupPath="",
  [string]$Out=""
)
$ErrorActionPreference="Stop"
$root=Split-Path -Parent $PSScriptRoot
$py=(Get-Command py.exe -ErrorAction SilentlyContinue)
if (-not $py) { throw "Python 3 launcher (py.exe) required; no system files changed" }
switch ($Action) {
  "Inventory" { & $py.Source -3 (Join-Path $PSScriptRoot "sl4_inventory.py"); break }
  "VerifyPins" { & $py.Source -3 (Join-Path $PSScriptRoot "sl4_setup.py") verify-pins; break }
  "Inspect" { if (-not $SourceEfi) {throw "-SourceEfi required"}; & $py.Source -3 (Join-Path $PSScriptRoot "sl4_setup.py") inspect --source-efi $SourceEfi; break }
  "VerifyBackup" { if (-not $Out) {throw "-Out required"}; & $py.Source -3 (Join-Path $PSScriptRoot "sl4_setup.py") verify-backup --out $Out; break }
  "Backup" { if (-not $Out -or -not $SourceEfi) {throw "-Out and -SourceEfi required"}; & $py.Source -3 (Join-Path $PSScriptRoot "sl4_setup.py") backup --source-efi $SourceEfi --out $Out --ack BACKUP-PRIVATE-EFI; break }
  "Prepare" { if (-not $Out -or -not $SourceEfi) {throw "-Out and -SourceEfi required"}; & $py.Source -3 (Join-Path $PSScriptRoot "sl4_setup.py") prepare --source-efi $SourceEfi --out $Out --ack PREPARE-OFFLINE-ONLY; break }
  "RestoreOffline" { if (-not $Out -or -not $BackupPath) {throw "-Out and -BackupPath required"}; & $py.Source -3 (Join-Path $PSScriptRoot "sl4_setup.py") restore-offline --backup-path $BackupPath --out $Out --ack RESTORE-OFFLINE-COPY; break }
}
if ($LASTEXITCODE -ne 0) { throw "Workflow stopped with exit code $LASTEXITCODE" }

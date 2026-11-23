# Windows-only safe integration test. Uses dummy files in a new temp folder.
# Never mounts or touches a physical EFI partition, BCD, NVRAM, or boot order.
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$tempRoot = Join-Path $env:TEMP ("SL4-OFFLINE-CI-" + [Guid]::NewGuid().ToString("N"))
$entry = Join-Path $repo "scripts\Start-SL4.ps1"
$fixture = Join-Path $repo "tests\test_setup_workflow.py"
$efi = Join-Path $tempRoot "private\EFI"
$backup = Join-Path $tempRoot "backup"
$stage = Join-Path $tempRoot "stage"
$restored = Join-Path $tempRoot "restored"
$python = Get-Command py.exe -ErrorAction Stop

New-Item -ItemType Directory -Path $tempRoot -ErrorAction Stop | Out-Null
try {
  & $python.Source -3 -c "import runpy,sys,pathlib; ns=runpy.run_path(sys.argv[1]); print(ns['make_private_efi'](pathlib.Path(sys.argv[2])))" $fixture $tempRoot
  if ($LASTEXITCODE -ne 0) { throw "Fixture generation failed" }
  $configFile = Join-Path $efi "OC\config.plist"
  $windowsLoader = Join-Path $efi "Microsoft\Boot\bootmgfw.efi"
  if (-not (Test-Path -LiteralPath $configFile) -or -not (Test-Path -LiteralPath $windowsLoader)) { throw "Synthetic EFI incomplete" }
  $beforeOC = (Get-FileHash -LiteralPath $configFile -Algorithm SHA256).Hash
  $beforeWindows = (Get-FileHash -LiteralPath $windowsLoader -Algorithm SHA256).Hash

  & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $entry -Action Inspect -SourceEfi $efi
  if ($LASTEXITCODE -ne 0) { throw "Inspect failed" }
  & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $entry -Action Backup -SourceEfi $efi -Out $backup
  if ($LASTEXITCODE -ne 0) { throw "Backup failed" }
  & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $entry -Action Prepare -SourceEfi $efi -Out $stage
  if ($LASTEXITCODE -ne 0) { throw "Prepare failed" }
  & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $entry -Action VerifyBackup -Out $stage
  if ($LASTEXITCODE -ne 0) { throw "VerifyBackup failed" }
  & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $entry -Action RestoreOffline -BackupPath $stage -Out $restored
  if ($LASTEXITCODE -ne 0) { throw "RestoreOffline failed" }
  & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $entry -Action VerifyBackup -Out $restored
  if ($LASTEXITCODE -ne 0) { throw "Restored copy failed integrity check" }

  if ((Get-FileHash -LiteralPath $configFile -Algorithm SHA256).Hash -ne $beforeOC) { throw "Source config was modified" }
  if ((Get-FileHash -LiteralPath $windowsLoader -Algorithm SHA256).Hash -ne $beforeWindows) { throw "Source Windows boot loader was modified" }
  Write-Output "WINDOWS SYNTHETIC WORKFLOW PASS: no live EFI, BCD or boot changes"
} finally {
  # Owned test-only path with GUID; never use a generic drive/EFI target.
  if (Test-Path -LiteralPath $tempRoot) { Remove-Item -LiteralPath $tempRoot -Recurse -Force }
}

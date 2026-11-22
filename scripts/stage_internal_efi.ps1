# ASCII-only script for Windows PowerShell 5.1 (UTF-8 without BOM also supported).
# Stage a known-working USB OpenCore on the INTERNAL Windows EFI System Partition.
# Windows PowerShell 5.1+; run elevated. This never changes boot order or BCD entries.
# It copies ONLY EFI\OC, never EFI\Microsoft or EFI\BOOT.
[CmdletBinding()]
param(
  [ValidateSet("Inspect","Stage","Verify")][string]$Mode="Inspect",
  [int]$InternalDiskNumber=0,
  [string]$UsbLabel="MACOS-OC"
)
$ErrorActionPreference="Stop"
function Require([bool]$ok,[string]$msg){if(-not $ok){throw "STOP: $msg"}}
$espGuid="{c12a7328-f81f-11d2-ba4b-00a0c93ec93b}"
$disk=Get-Disk -Number $InternalDiskNumber -ErrorAction Stop
Require ($disk.BusType -ne "USB" -and $disk.IsSystem -and $disk.PartitionStyle -eq "GPT") "Target must be current system GPT disk, not USB"
$esps=@(Get-Partition -DiskNumber $InternalDiskNumber | Where-Object { "$($_.GptType)".Trim("{}") -ieq $espGuid.Trim("{}") })
Require ($esps.Count -eq 1) "Expected exactly one Windows EFI system partition on target disk"
Require ($esps[0].Size -ge 150MB) "Internal EFI partition unusually small; review manually"
Require (-not (Get-PSDrive -Name S -ErrorAction SilentlyContinue)) "S: must be unused before mounting Windows EFI"
$src=$null
if($Mode -ne "Verify"){
  $volumes=@(Get-Volume -FileSystemLabel $UsbLabel -ErrorAction Stop | Where-Object DriveLetter)
  Require ($volumes.Count -eq 1) "Expected exactly one mounted USB volume labeled $UsbLabel"
  $usbPart=Get-Partition -DriveLetter $volumes[0].DriveLetter
  $usbDisk=Get-Disk -Number $usbPart.DiskNumber
  Require ($usbDisk.BusType -eq "USB" -and $usbDisk.Number -ne $InternalDiskNumber) "Source must be USB, not Windows disk"
  $src="$($volumes[0].DriveLetter):\EFI\OC"
  foreach($f in @("OpenCore.efi","config.plist","ACPI\SSDT-RTC0-SL4.aml","Kexts\Lilu.kext\Contents\Info.plist")){
    Require (Test-Path -LiteralPath (Join-Path $src $f)) "Source USB is missing $f - do not use a generated, untested EFI"
  }
}
$mounted=$false
try {
  & mountvol.exe S: /S | Out-Null
  Require ($LASTEXITCODE -eq 0) "Could not mount Windows ESP at S:"
  $mounted=$true
  $mountedEsp=Get-Partition -DriveLetter S -ErrorAction Stop
  Require ($mountedEsp.DiskNumber -eq $InternalDiskNumber -and $mountedEsp.PartitionNumber -eq $esps[0].PartitionNumber) "S: is not the verified internal ESP"
  $windowsBoot="S:\EFI\Microsoft\Boot\bootmgfw.efi"
  Require (Test-Path -LiteralPath $windowsBoot) "Windows Boot Manager missing - abort"
  $before=(Get-FileHash -LiteralPath $windowsBoot -Algorithm SHA256).Hash
  $dst="S:\EFI\OC"
  Write-Host "Internal: disk $InternalDiskNumber $($disk.FriendlyName), ESP partition $($esps[0].PartitionNumber)"
  Write-Host "Windows Boot Manager SHA256: $before"
  Write-Host "OpenCore location: $dst"
  if($Mode -eq "Inspect"){
    Write-Host "Source USB: $src"
    Require (-not (Test-Path -LiteralPath $dst)) "Internal EFI\OC already exists: back up or inspect it before changing"
    $srcFiles=@(Get-ChildItem -LiteralPath $src -File -Recurse)
    $size=($srcFiles | Measure-Object -Property Length -Sum).Sum
    $free=(Get-Volume -DriveLetter S).SizeRemaining
    Write-Host "Source files: $($srcFiles.Count); total bytes: $size; internal ESP available bytes: $free"
    Require ($free -gt ($size + 8MB)) "Not enough free space on internal ESP"
    Write-Host "INSPECT OK: Windows EFI and boot order unchanged"
  } elseif($Mode -eq "Stage"){
    Require (-not (Test-Path -LiteralPath $dst)) "Internal EFI\OC already exists; refusing to overwrite"
    $srcFiles=@(Get-ChildItem -LiteralPath $src -File -Recurse)
    $total=($srcFiles | Measure-Object -Property Length -Sum).Sum
    Require ((Get-Volume -DriveLetter S).SizeRemaining -gt ($total + 8MB)) "Insufficient ESP free space"
    $answer=Read-Host "Type STAGE-OPENCORE-INTERNAL to copy ONLY EFI\OC"
    Require ($answer -ceq "STAGE-OPENCORE-INTERNAL") "Not confirmed"
    $backup=Join-Path $env:USERPROFILE ("Downloads\SL4-ESP-BACKUP-"+(Get-Date -Format "yyyyMMdd-HHmmss"))
    New-Item -ItemType Directory -Path $backup -Force | Out-Null
    & bcdedit.exe /export "$backup\Windows-BCD.bak" | Out-Null
    Require ($LASTEXITCODE -eq 0) "BCD export failed; no EFI changes made"
    Copy-Item -LiteralPath "S:\EFI\Microsoft" -Destination (Join-Path $backup "Microsoft") -Recurse -Force
    New-Item -ItemType Directory -Path $dst -Force | Out-Null
    Copy-Item -Path "$src\*" -Destination $dst -Recurse -Force
    foreach($f in $srcFiles){
      $rel=$f.FullName.Substring($src.Length).TrimStart("\")
      $copy=Join-Path $dst $rel
      Require (Test-Path -LiteralPath $copy) "Missing copied file: $rel"
      Require ((Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash -eq (Get-FileHash -LiteralPath $copy -Algorithm SHA256).Hash) "SHA256 mismatch: $rel"
    }
    Write-Host "STAGE SUCCESS: copied $($srcFiles.Count) files; backup at $backup"
    Write-Host "No BCD entry, boot order, EFI\BOOT, or Windows Boot Manager was changed"
  } else {
    foreach($f in @("OpenCore.efi","config.plist","ACPI\SSDT-RTC0-SL4.aml","Kexts\Lilu.kext\Contents\Info.plist")){
      Require (Test-Path -LiteralPath (Join-Path $dst $f)) "Staged OpenCore missing $f"
    }
    Write-Host "VERIFY OK: Internal EFI\OC exists. Windows Boot Manager intact."
  }
  Require ((Get-FileHash -LiteralPath $windowsBoot -Algorithm SHA256).Hash -eq $before) "Windows EFI bootmgfw.efi changed - investigate"
} finally {
  if($mounted){ & mountvol.exe S: /D | Out-Null }
}

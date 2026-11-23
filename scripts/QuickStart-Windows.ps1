# Surface Laptop 4 macOS Tahoe - Windows-first interactive Quick Start.
# Main path: Prepare fresh Apple Recovery + personal OpenCore + driver bundle.
# USB writing is an independent, administrator-confirmed action.
[CmdletBinding()]
param(
  [ValidateSet('Menu','Prepare','WriteUSB','Repair','Experimental','InternalBoot')][string]$Mode='Menu',
  [string]$StageFolder='',
  [int]$UsbDiskNumber=-1,
  [ValidateSet('latest','default')][string]$OsSelection='latest',
  [string]$BoardId='Mac-CFF7D910A743CAAF',
  [string]$InstallAssistantPkg='',
  [switch]$Experimental
)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $env:USERPROFILE 'Downloads\SL4-Tahoe'
$downloads=Join-Path $work 'Downloads'
if (-not (Test-Path -LiteralPath $downloads)) { New-Item -ItemType Directory -Path $downloads -Force | Out-Null }
$stageBase=Join-Path $work 'Prepared'

function Assert-Windows {
  if (-not [Environment]::OSVersion.Platform.ToString().StartsWith('Win')) {
    throw 'Quick Start is a Windows PowerShell workflow.'
  }
}
function Get-Python {
  $py=Get-Command py.exe -ErrorAction SilentlyContinue
  if ($py) {
    & $py.Source -3 --version 2>$null
    if ($LASTEXITCODE -eq 0) { return ,@($py.Source,'-3') }
  }
  $python=Get-Command python.exe -ErrorAction SilentlyContinue
  if ($python) {
    & $python.Source --version 2>$null
    if ($LASTEXITCODE -eq 0) { return ,@($python.Source) }
  }
  Write-Host 'Downloading the official Python 3.12.10 installer for this Windows user...' -ForegroundColor Cyan
  $exe=Get-Download -Url 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' -File 'python-3.12.10-amd64.exe' -Sha '67b5635e80ea51072b87941312d00ec8927c4db9ba18938f7ad2d27b328b95fb'
  $result=Start-Process -FilePath $exe -ArgumentList '/quiet InstallAllUsers=0 PrependPath=0 Include_test=0 Include_pip=0 Include_launcher=0' -Wait -PassThru
  if ($result.ExitCode -ne 0) { throw "Official Python installer failed: $($result.ExitCode)" }
  $installed=Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'
  if (-not (Test-Path -LiteralPath $installed)) { throw 'Python installer completed, but python.exe was not found' }
  return ,@($installed)
}
function Get-Download([string]$Url,[string]$File,[string]$Sha) {
  $dest=Join-Path $downloads $File
  if (Test-Path -LiteralPath $dest) {
    $actual=(Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $Sha.ToLowerInvariant()) { throw "Downloaded file SHA mismatch: $dest" }
    return $dest
  }
  $temp=$dest+'.partial'
  if (Test-Path -LiteralPath $temp) { throw "Incomplete prior download: $temp" }
  Write-Host "Downloading $File"
  try {
    Invoke-WebRequest -Uri $Url -OutFile $temp -UseBasicParsing
    if ((Get-FileHash -LiteralPath $temp -Algorithm SHA256).Hash.ToLowerInvariant() -ne $Sha.ToLowerInvariant()) {
      throw "Downloaded file SHA mismatch: $File"
    }
    Move-Item -LiteralPath $temp -Destination $dest
  } finally {
    if (Test-Path -LiteralPath $temp) { Remove-Item -LiteralPath $temp -Force }
  }
  return $dest
}
function Confirm-Surface-Hardware {
  $machine=Get-CimInstance Win32_ComputerSystem
  $cpu=Get-CimInstance Win32_Processor | Select-Object -First 1
  $gpus=@(Get-CimInstance Win32_VideoController)
  $known=($machine.Manufacturer -match 'Microsoft') -and
         ($machine.Model -match 'Surface Laptop 4') -and
         ($cpu.Name -match '1185G7') -and
         (@($gpus | Where-Object {$_.PNPDeviceID -match 'VEN_8086&DEV_9A49'}).Count -gt 0)
  Write-Host ("Target computer: "+$machine.Manufacturer+" "+$machine.Model)
  Write-Host ("CPU: "+$cpu.Name)
  if ($known) {
    Write-Host 'Matched built-in Surface Laptop 4 Intel profile.' -ForegroundColor Green
  } elseif (-not $Experimental) {
    throw 'Target hardware differs from built-in SL4 i7 profile. Use menu option 3 (Advanced) for manual experiments; no wrong EFI was applied.'
  } else {
    Write-Host 'Advanced experimental mode: the SL4 Intel EFI is NOT a universal EFI for this hardware.' -ForegroundColor Yellow
    $accept=Read-Host 'Continue building an experimental SL4 reference only? (Y/N)'
    if ($accept -ne 'Y') { throw 'Experimental build cancelled' }
  }
}
function Prepare-Installation {
  Assert-Windows
  Confirm-Surface-Hardware
  $py=Get-Python
  $out=$StageFolder
  if (-not $out) {
    $out=Join-Path $stageBase ("Tahoe-"+(Get-Date -Format 'yyyyMMdd-HHmmss'))
  }
  $cache=Join-Path $work 'Cache'
  if (-not (Test-Path -LiteralPath $stageBase)) { New-Item -ItemType Directory -Path $stageBase -Force | Out-Null }
  $prefix=@()
  if ($py.Count -gt 1) { $prefix=@($py[1..($py.Count-1)]) }
  $args=$prefix + @(
    (Join-Path $PSScriptRoot 'windows_prepare_tahoe.py'),
    '--out',$out,'--cache',$cache,'--os-selection',$OsSelection,'--board-id',$BoardId
  )
  if ($Experimental) { $args+=@('--experimental') }
  if ($InstallAssistantPkg) { $args+=@('--installassistant',$InstallAssistantPkg) }
  Write-Host ''
  Write-Host 'Preparing personal OpenCore, Apple Tahoe Recovery and drivers from Windows.' -ForegroundColor Cyan
  Write-Host 'No Windows partitions, BCD, NVRAM or EFI are changed.'
  & $py[0] @args
  if ($LASTEXITCODE -ne 0) { throw 'Tahoe preparation failed; see Python output' }
  Write-Host "Preparation complete: $out" -ForegroundColor Green
  Write-Host 'USB can be prepared next, or this staged folder can be preserved for another computer.'
  $confirm=Read-Host 'Write prepared files to an empty USB drive now? (Y/N)'
  if ($confirm -eq 'Y') {
    Show-USB-Choices
    $value=Read-Host 'Enter the USB disk number (never C: or internal SSD)'
    $number=0
    if (-not [int]::TryParse($value,[ref]$number)) { throw 'Invalid disk number' }
    Write-USB -folder $out -number $number
  }
}
function Show-USB-Choices {
  Write-Host ''
  Write-Host 'Available removable USB disks:' -ForegroundColor Cyan
  Get-Disk | Where-Object { $_.BusType -eq 'USB' -and -not $_.IsBoot -and -not $_.IsSystem } |
    Select-Object Number,FriendlyName,Size,PartitionStyle | Format-Table -AutoSize
}
function Assert-Stage([string]$folder) {
  $abs=[IO.Path]::GetFullPath($folder)
  $m=Join-Path $abs 'manifest.json'
  if (-not (Test-Path -LiteralPath $m)) { throw 'Missing prepared installer manifest.json' }
  $manifest=Get-Content -LiteralPath $m -Raw | ConvertFrom-Json
  if ($manifest.mode -ne 'windows_new_macos_setup' -or -not $manifest.private_efi -or -not $manifest.windows_untouched) {
    throw 'Unrecognized prepared installer manifest'
  }
  foreach ($name in @('personal-boot\EFI\BOOT\BOOTx64.efi','personal-boot\EFI\OC\config.plist',
                      'com.apple.recovery.boot','SL4DATA\SL4-S0ix-DMC-0.2.0-beta.zip')) {
    if (-not (Test-Path -LiteralPath (Join-Path $abs $name))) { throw "Missing installer component: $name" }
  }
  if ((Get-FileHash -LiteralPath (Join-Path $abs 'personal-boot\EFI\OC\OpenCore.efi') -Algorithm SHA256).Hash.ToLowerInvariant() -ne $manifest.bootloader_sha256) {
    throw 'OpenCore checksum changed after staging'
  }
  if ((Get-FileHash -LiteralPath (Join-Path $abs 'SL4DATA\SL4-S0ix-DMC-0.2.0-beta.zip') -Algorithm SHA256).Hash.ToLowerInvariant() -ne $manifest.driver_release_sha256) {
    throw 'Driver release checksum changed after staging'
  }
  $dmgs=Get-ChildItem -LiteralPath (Join-Path $abs 'com.apple.recovery.boot') -File -Filter '*.dmg'
  if (@($dmgs).Count -ne 1) { throw 'Missing or multiple Recovery DMGs' }
  foreach ($item in $manifest.recovery_sha256.PSObject.Properties) {
    $file=Join-Path (Join-Path $abs 'com.apple.recovery.boot') $item.Name
    if (-not (Test-Path -LiteralPath $file)) { throw "Recovery file missing: $($item.Name)" }
    if ((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant() -ne [string]$item.Value) {
      throw "Recovery checksum failed: $($item.Name)"
    }
    if ((Get-Item -LiteralPath $file).Length -ge 4GB) { throw 'Recovery file too large for FAT32 USB partition' }
  }
  return $abs
}
function Ensure-AdminOrElevate([string]$folder,[int]$number) {
  $p=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
  if ($p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { return $true }
  if ($folder.Contains('"')) { throw 'Invalid staging path for UAC elevation' }
  Write-Host 'Windows will request administrator rights to write ONLY the selected USB.'
  $script=$PSCommandPath
  $arguments='-NoProfile -ExecutionPolicy Bypass -File "'+$script+'" -Mode WriteUSB -StageFolder "'+$folder+'" -UsbDiskNumber '+$number
  $child=Start-Process -FilePath 'powershell.exe' -ArgumentList $arguments -Verb RunAs -Wait -PassThru
  if ($child.ExitCode -ne 0) { throw 'Elevated USB preparation failed or was cancelled' }
  return $false
}
function Write-USB([string]$folder,[int]$number) {
  Assert-Windows
  $src=Assert-Stage $folder
  if (-not (Ensure-AdminOrElevate -folder $src -number $number)) { return }
  $disk=Get-Disk -Number $number -ErrorAction Stop
  if ($disk.BusType -ne 'USB' -or $disk.IsBoot -or $disk.IsSystem -or $disk.Size -lt 14GB) {
    throw 'Refusing non-USB, internal system, boot or too-small disk'
  }
  if ($disk.IsOffline -or $disk.IsReadOnly) { throw 'USB disk must be online and writable' }
  $parts=@(Get-Partition -DiskNumber $number -ErrorAction SilentlyContinue)
  foreach ($part in $parts) {
    if ($part.DriveLetter -eq $env:SystemDrive.Substring(0,1)) { throw 'Refusing to erase Windows system volume' }
  }
  $size=[math]::Round($disk.Size/1GB,1)
  Write-Host "USB DISK $number : $($disk.FriendlyName), $size GiB." -ForegroundColor Yellow
  Write-Host 'ALL EXISTING FILES AND PARTITIONS ON THIS USB DISK WILL BE DELETED.' -ForegroundColor Red
  Write-Host 'Windows internal disk and existing Windows EFI are NOT touched.'
  $expected="ERASE USB $number"
  $typed=Read-Host "Type exactly: $expected"
  if ($typed -cne $expected) { throw 'Confirmation did not match; no USB changes' }
  # All side-effecting operations happen AFTER exact disk, bus and confirmation checks.
  Clear-Disk -Number $number -RemoveData -RemoveOEM -Confirm:$false -ErrorAction Stop
  $disk=Get-Disk -Number $number
  if ($disk.PartitionStyle -eq 'RAW') {
    Initialize-Disk -Number $number -PartitionStyle GPT -ErrorAction Stop | Out-Null
  }
  $boot=New-Partition -DiskNumber $number -Size 8GB -AssignDriveLetter -ErrorAction Stop
  Format-Volume -Partition $boot -FileSystem FAT32 -NewFileSystemLabel 'MACOS-OC' -Confirm:$false -Force -ErrorAction Stop | Out-Null
  $data=New-Partition -DiskNumber $number -UseMaximumSize -AssignDriveLetter -ErrorAction Stop
  Format-Volume -Partition $data -FileSystem exFAT -NewFileSystemLabel 'SL4DATA' -Confirm:$false -Force -ErrorAction Stop | Out-Null
  $bootLetter=([string]$boot.DriveLetter)+':\'
  $dataLetter=([string]$data.DriveLetter)+':\'
  Copy-Item -LiteralPath (Join-Path $src 'personal-boot\EFI') -Destination $bootLetter -Recurse -ErrorAction Stop
  Copy-Item -LiteralPath (Join-Path $src 'com.apple.recovery.boot') -Destination $bootLetter -Recurse -ErrorAction Stop
  Copy-Item -Path (Join-Path (Join-Path $src 'SL4DATA') '*') -Destination $dataLetter -Recurse -Force -ErrorAction Stop
  foreach ($name in @('EFI\BOOT\BOOTx64.efi','EFI\OC\config.plist','com.apple.recovery.boot')) {
    if (-not (Test-Path -LiteralPath (Join-Path $bootLetter $name))) { throw "USB verification failed: $name" }
  }
  if (-not (Test-Path -LiteralPath (Join-Path $dataLetter 'SL4-S0ix-DMC-0.2.0-beta.zip'))) {
    throw 'Postinstall data not copied'
  }
  Write-Host ''
  Write-Host 'USB READY. In Surface UEFI first set Secure Boot to OFF (keep Windows BitLocker recovery key).' -ForegroundColor Green
  Write-Host 'Then power off, hold Volume Down, press Power to start USB OpenCore.'
  Write-Host 'IMPORTANT - FIRST BOOT: OpenCore shows the Recovery option by default (15-second selection window).' -ForegroundColor Yellow
  Write-Host 'Use arrow keys and Enter to choose macOS Base System (External), sometimes labeled Recovery.'
  Write-Host 'Do NOT choose Windows Boot Manager or an existing macOS installation for the initial Recovery boot.'
  Write-Host 'On older USB builds only: press Space inside OpenCore if the Recovery entry is hidden.'
  Write-Host 'Install Tahoe into NEW free disk space, not Windows/EFI partitions.'
  Write-Host "After installation use the SL4DATA partition $dataLetter for drivers."
}
function Stage-Internal-OpenCore {
  Assert-Windows
  $admin=[Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
  if (-not $admin.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host 'Requesting Windows administrator permissions for the separate OpenCore entry.'
    $result=Start-Process -FilePath 'powershell.exe' -ArgumentList ('-NoProfile -ExecutionPolicy Bypass -File "'+$PSCommandPath+'" -Mode InternalBoot') -Verb RunAs -Wait -PassThru
    if ($result.ExitCode -ne 0) { throw 'Admin-assisted internal OpenCore installation failed' }
    return
  }
  $sys=(Get-Disk | Where-Object { $_.IsSystem -and $_.BusType -ne 'USB' })
  if (@($sys).Count -ne 1) { throw 'Expected exactly one Windows system disk; use advanced setup' }
  Write-Host 'Copying the known-working USB OpenCore onto the internal Windows ESP.' -ForegroundColor Cyan
  Write-Host 'Existing Windows EFI and boot order will be preserved.'
  $script=Join-Path $PSScriptRoot 'stage_internal_efi.ps1'
  & $script -Mode Inspect -InternalDiskNumber $sys.Number -UsbLabel 'MACOS-OC'
  if ($LASTEXITCODE -ne 0) { throw 'Internal OpenCore inspection failed' }
  $confirm=Read-Host 'Stage the tested USB OpenCore internally? (Y/N)'
  if ($confirm -ne 'Y') { return }
  & $script -Mode Stage -InternalDiskNumber $sys.Number -UsbLabel 'MACOS-OC'
  if ($LASTEXITCODE -ne 0) { throw 'Internal OpenCore staging failed' }
  Write-Host 'OpenCore copied, Windows Boot Manager and BCD backed up.'
  Write-Host 'Create a SEPARATE OpenCore boot entry only after confirming Windows can still boot.'
  $separate=Read-Host 'Create an additional OpenCore firmware boot entry? (Y/N)'
  if ($separate -eq 'Y') {
    $saved=& bcdedit.exe /copy '{bootmgr}' /d 'OpenCore (Surface Laptop 4)'
    if ($LASTEXITCODE -ne 0) { throw 'Could not create independent boot entry' }
    $hit=[regex]::Match(($saved -join ' '),'\{[0-9a-fA-F\-]{36}\}')
    if (-not $hit.Success) { throw 'Could not parse new independent boot identifier. Verify with bcdedit /enum firmware.' }
    $newId=$hit.Value
    & bcdedit.exe /set $newId path '\EFI\OC\OpenCore.efi'
    if ($LASTEXITCODE -ne 0) { throw 'Could not configure independent OpenCore boot entry; Windows boot was not overwritten' }
    Write-Host "Separate boot entry created: $newId" -ForegroundColor Green
    Write-Host 'Select it using Surface UEFI boot menu. Windows Boot Manager remains available.'
  }
}
function Prepare-Repair {
  Assert-Windows
  $py=Get-Python
  $out=Join-Path $work ('Repair-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))
  $cache=Join-Path $work 'Cache'
  $prefix=@()
  if ($py.Count -gt 1) { $prefix=@($py[1..($py.Count-1)]) }
  $args=$prefix + @((Join-Path $PSScriptRoot 'windows_prepare_tahoe.py'),
                    '--repair-only','--out',$out,'--cache',$cache)
  & $py[0] @args
  if ($LASTEXITCODE -ne 0) { throw 'Driver recovery preparation failed' }
  Write-Host "Driver repair kit ready in: $out" -ForegroundColor Green
  Write-Host 'Copy SL4DATA folder into your Tahoe Downloads or a USB drive and open QuickStart-Mac.command.'
}
try {
  if ($Mode -eq 'Menu') {
    Write-Host ''
    Write-Host 'SURFACE LAPTOP 4 / macOS TAHOE - QUICK START' -ForegroundColor Cyan
    Write-Host '[1] Install Tahoe from Windows (prepares bootloader, Apple Recovery, drivers, USB)'
    Write-Host '[2] Tahoe already installed - prepare hardware drivers'
    Write-Host '[3] Advanced: alternate Apple Recovery version / experiments'
    Write-Host '[4] Write a previously prepared USB'
    Write-Host '[5] Finish installation: add OpenCore to Surface internal SSD (Windows retained)'
    Write-Host '[0] Exit'
    $choice=Read-Host 'Choose 1, 2, 3, 4, 5 or 0'
    switch ($choice) {
      '1' { Prepare-Installation }
      '2' { Prepare-Repair }
      '3' {
        $Experimental=$true
        $selected=Read-Host 'Recovery version: latest (Tahoe) or default (Enter for latest)'
        if ($selected -eq 'default') { $OsSelection='default' }
        $chosenBoard=Read-Host 'Apple board ID (Enter to keep built-in Tahoe board)'
        if ($chosenBoard) { $BoardId=$chosenBoard }
        Prepare-Installation
      }
      '4' {
        Show-USB-Choices
        $folder=Read-Host 'Prepared installer directory'
        $value=Read-Host 'USB disk number'
        $num=0
        if (-not [int]::TryParse($value,[ref]$num)) { throw 'Invalid disk number' }
        Write-USB -folder $folder -number $num
      }
      '5' { Stage-Internal-OpenCore }
      '0' { Write-Host 'Exited without changes.' }
      default { throw 'Invalid menu option' }
    }
  } elseif ($Mode -eq 'Prepare' -or $Mode -eq 'Experimental') {
    if ($Mode -eq 'Experimental') { $Experimental=$true }
    Prepare-Installation
  } elseif ($Mode -eq 'WriteUSB') {
    if (-not $StageFolder -or $UsbDiskNumber -lt 0) { throw 'Provide -StageFolder and -UsbDiskNumber' }
    Write-USB -folder $StageFolder -number $UsbDiskNumber
  } elseif ($Mode -eq 'Repair') {
    Prepare-Repair
  } elseif ($Mode -eq 'InternalBoot') {
    Stage-Internal-OpenCore
  }
  Write-Host ''
  Write-Host 'Quick Start finished.' -ForegroundColor Cyan
} catch {
  Write-Host ('STOP: '+$_.Exception.Message) -ForegroundColor Red
  exit 1
}

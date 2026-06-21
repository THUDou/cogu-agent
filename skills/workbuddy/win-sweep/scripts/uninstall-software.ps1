#Requires -Version 5.1
<#
.SYNOPSIS
    win-sweep software removal — list candidates, attempt uninstall, and clean up leftovers.
.DESCRIPTION
    Five modes of operation:
    - List: Scan installed software from registry, generate a "recommended uninstall list."
    - Uninstall: Attempt to invoke the uninstaller from the terminal. WARNING: This is unreliable
      for many programs (GUI-only uninstallers, guardian processes, kernel driver locks). The
      preferred workflow is: List → user manually uninstalls via Settings/Control Panel → Cleanup.
      Includes timeout protection to prevent indefinite hangs.
    - Cleanup: After uninstall (manual or automated), scan for leftover artifacts — orphaned
      services, scheduled tasks, startup items, program directories, AppData, temp files,
      desktop shortcuts, taskbar pins, and Start Menu shortcuts.
      Outputs findings and suggested commands (AI presents for user confirmation).
    - CleanupPlan: Same scan as Cleanup but outputs a structured JSON plan to stdout.
      AI can parse this and pass it to CleanupExecute.
    - CleanupExecute: Takes a JSON plan (from CleanupPlan) and executes the cleanup operations
      with proper backup (reg export), logging, and PendingFileRenameOperations for locked files.
.PARAMETER Action
    Operation mode: List, Uninstall, Cleanup, CleanupPlan, or CleanupExecute.
.PARAMETER Programs
    JSON array of programs to uninstall. Each object must have a "Name" key matching
    the registry DisplayName (exact or substring match).
    Example: '[{"Name":"Bonjour"},{"Name":"Adobe Flash"}]'
.PARAMETER Quiet
    Attempt quiet/silent uninstall when available.
.PARAMETER TimeoutSeconds
    Maximum seconds to wait for each uninstaller process (default: 120).
    If the uninstaller does not exit within this time, it will be killed.
    This prevents GUI uninstallers and hung processes from freezing the terminal.
.PARAMETER CleanupTarget
    For Cleanup/CleanupPlan action: the software name(s) to scan leftovers for.
    Example: 'Adobe Flash','Bonjour'
.PARAMETER Plan
    For CleanupExecute action: JSON string from CleanupPlan output.
.PARAMETER SkipUninstaller
    For Cleanup action: skip running the uninstaller, only scan and remove leftovers.
    Useful when the software has already been uninstalled but left residue behind.
.PARAMETER BackupDir
    Backup directory for CleanupExecute, defaults to %TEMP%\win-sweep-backup.
.NOTES
    ⚠️ IMPORTANT: Terminal-based uninstall is unreliable for many programs, especially:
    - Chinese rogue software (360, 鲁大师, 2345, etc.) — GUI-only, guardian processes, kernel locks
    - Bloated AV products (McAfee, Norton, Avast) — require vendor-specific removal tools
    - Any software with no silent/quiet uninstall mode
    The recommended workflow is to use List + Cleanup, with the user doing the actual
    uninstall manually through Settings > Apps or Control Panel.
#>

[CmdletBinding(SupportsShouldProcess)]
param(
    [ValidateSet('List', 'Uninstall', 'Cleanup', 'CleanupPlan', 'CleanupExecute')]
    [string]$Action = 'List',

    [string]$Programs,

    [switch]$Quiet,

    [ValidateRange(10, 600)]
    [int]$TimeoutSeconds = 120,

    [string[]]$CleanupTarget,

    [string]$Plan,

    [switch]$SkipUninstaller,

    [string]$BackupDir = "$env:TEMP\win-sweep-backup"
)

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)

# ── Registry paths for installed software ──
$regPaths = @(
    'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*'
    'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*'
    'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*'
)

function Get-InstalledSoftware {
    $regPaths | ForEach-Object { Get-ItemProperty $_ -ErrorAction SilentlyContinue } |
        Where-Object { $_.DisplayName -and $_.DisplayName.Trim() } |
        Select-Object @{N='DisplayName';       E={$_.DisplayName.Trim()}},
                      DisplayVersion,
                      Publisher,
                      @{N='SizeMB';            E={if ($_.EstimatedSize) {[math]::Round($_.EstimatedSize / 1024, 1)} else {$null}}},
                      InstallDate,
                      UninstallString,
                      QuietUninstallString,
                      InstallLocation,
                      @{N='RegistryPath';      E={$_.PSPath}} |
        Sort-Object DisplayName
}

function Find-SoftwareEntry([string]$Name) {
    $all = Get-InstalledSoftware
    # Try exact match first, then substring
    $match = $all | Where-Object { $_.DisplayName -eq $Name }
    if (-not $match) {
        $match = $all | Where-Object { $_.DisplayName -like "*$Name*" }
    }
    return $match
}

# ── Known Windows standard C:\ root directories (whitelist) ──
$knownRootDirs = @(
    'Windows', 'Program Files', 'Program Files (x86)', 'Users', 'PerfLogs',
    'Recovery', '$Recycle.Bin', 'System Volume Information', 'Documents and Settings',
    'ProgramData', 'Intel', 'AMD', 'NVIDIA', 'MSOCache', 'inetpub', 'Boot',
    'EFI', 'OneDriveTemp', 'Drivers', 'swapfile.sys', 'pagefile.sys', 'hiberfil.sys'
)

# ── Shared leftover scanning function ──
function Invoke-LeftoverScan([string]$Target) {
    $findings = @()

    # Debug: confirm received parameter (helps diagnose encoding issues)
    Write-Host "`nTarget: $Target" -ForegroundColor Yellow
    Write-Host "  [DEBUG] Target bytes: $(([System.Text.Encoding]::UTF8.GetBytes($Target) | ForEach-Object { '{0:X2}' -f $_ }) -join ' ')" -ForegroundColor DarkGray

    # Build keyword variants for fuzzy matching
    # e.g., "LuDaShi" -> matches "LudashiProtect", "ludashi_service", etc.
    $targetLower = $Target.ToLower() -replace '[^a-z0-9\u4e00-\u9fff]', ''
    $keywords = @($Target)
    if ($targetLower -and $targetLower -ne $Target.ToLower()) {
        $keywords += $targetLower
    }

    # 1. Orphaned registry entries
    Write-Host "  Checking registry..." -ForegroundColor Gray
    $regEntries = $regPaths | ForEach-Object { Get-ItemProperty $_ -ErrorAction SilentlyContinue } |
        Where-Object { $_.DisplayName -and $_.DisplayName -like "*$Target*" }
    foreach ($r in $regEntries) {
        $findings += [PSCustomObject]@{
            Type     = 'Registry'
            Path     = $r.PSPath -replace 'Microsoft\.PowerShell\.Core\\Registry::', ''
            Detail   = "Uninstall entry: $($r.DisplayName)"
            Action   = 'Remove registry key'
            Command  = "Remove-Item -Path '$($r.PSPath)' -Recurse -Force"
        }
    }

    # 2. Orphaned services (including kernel drivers) — fuzzy keyword matching
    Write-Host "  Checking services and drivers..." -ForegroundColor Gray
    $services = @(Get-CimInstance Win32_Service | Where-Object {
        $svc = $_
        $keywords | Where-Object {
            $k = $_
            $svc.DisplayName -like "*$k*" -or
            $svc.Name -like "*$k*" -or
            # Case-insensitive substring match for partial keywords (e.g., "LuDaShi" matches "LudashiProtect")
            ($svc.Name -and $svc.Name.ToLower().Contains($k.ToLower())) -or
            ($svc.DisplayName -and $svc.DisplayName.ToLower().Contains($k.ToLower())) -or
            ($svc.PathName -and $svc.PathName -like "*$k*")
        } | Select-Object -First 1
    })
    $drivers = @(Get-CimInstance Win32_SystemDriver -ErrorAction SilentlyContinue | Where-Object {
        $drv = $_
        $keywords | Where-Object {
            $k = $_
            $drv.DisplayName -like "*$k*" -or
            $drv.Name -like "*$k*" -or
            ($drv.Name -and $drv.Name.ToLower().Contains($k.ToLower())) -or
            ($drv.DisplayName -and $drv.DisplayName.ToLower().Contains($k.ToLower())) -or
            ($drv.PathName -and $drv.PathName -like "*$k*")
        } | Select-Object -First 1
    })
    foreach ($s in ($services + $drivers)) {
        $exePath = $null
        if ($s.PathName) {
            $p = $s.PathName.Trim()
            if ($p.StartsWith('"')) {
                $end = $p.IndexOf('"', 1)
                if ($end -gt 0) { $exePath = $p.Substring(1, $end - 1) }
            } elseif ($p -match '^(.+\.exe)\b') {
                $exePath = $Matches[1]
            } elseif ($p -match '^(.+\.sys)\b') {
                $exePath = $Matches[1]
            }
        }
        $fileGone = $exePath -and -not (Test-Path $exePath -ErrorAction SilentlyContinue)
        $emptyPath = -not $s.PathName -or $s.PathName.Trim() -eq ''

        $findings += [PSCustomObject]@{
            Type     = 'Service'
            Path     = $s.Name
            Detail   = "$($s.DisplayName) [State: $($s.State)]$(if($fileGone){' (EXE missing!)'}elseif($emptyPath){' (empty ImagePath!)'})"
            Action   = 'Stop and delete service'
            Command  = "sc.exe stop `"$($s.Name)`"; sc.exe delete `"$($s.Name)`""
        }
    }

    # 3. Orphaned scheduled tasks — fuzzy keyword matching
    Write-Host "  Checking scheduled tasks..." -ForegroundColor Gray
    $tasks = Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object {
        $t = $_
        $actionsStr = ($t.Actions | ForEach-Object { $_.Execute + ' ' + $_.Arguments }) -join ' '
        $keywords | Where-Object {
            $k = $_
            $t.TaskName -like "*$k*" -or
            $t.TaskPath -like "*$k*" -or
            ($t.TaskName -and $t.TaskName.ToLower().Contains($k.ToLower())) -or
            $actionsStr -like "*$k*"
        } | Select-Object -First 1
    }
    foreach ($t in $tasks) {
        $findings += [PSCustomObject]@{
            Type     = 'ScheduledTask'
            Path     = "$($t.TaskPath)$($t.TaskName)"
            Detail   = "State: $($t.State)"
            Action   = 'Unregister task'
            Command  = "Unregister-ScheduledTask -TaskName '$($t.TaskName)' -TaskPath '$($t.TaskPath)' -Confirm:`$false"
        }
    }

    # 4. Orphaned startup items (including WOW6432Node)
    Write-Host "  Checking startup items..." -ForegroundColor Gray
    $runKeys = @(
        'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
        'HKLM:\Software\Microsoft\Windows\CurrentVersion\Run'
        'HKCU:\Software\Microsoft\Windows\CurrentVersion\RunDisabled'
        'HKLM:\Software\Microsoft\Windows\CurrentVersion\RunDisabled'
        'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run'
        'HKCU:\Software\Microsoft\Windows\CurrentVersion\RunOnce'
        'HKLM:\Software\Microsoft\Windows\CurrentVersion\RunOnce'
    )
    $excludeProps = '^PS(Path|ParentPath|ChildName|Provider|Drive)$'
    foreach ($key in $runKeys) {
        if (-not (Test-Path $key)) { continue }
        $props = Get-ItemProperty $key -ErrorAction SilentlyContinue
        if (-not $props) { continue }
        $props.PSObject.Properties |
            Where-Object { $_.Name -notmatch $excludeProps -and ($_.Name -like "*$Target*" -or $_.Value -like "*$Target*") } |
            ForEach-Object {
                $findings += [PSCustomObject]@{
                    Type     = 'StartupItem'
                    Path     = "$key\$($_.Name)"
                    Detail   = $_.Value
                    Action   = 'Remove registry value'
                    Command  = "Remove-ItemProperty -Path '$key' -Name '$($_.Name)' -Force"
                }
            }
    }

    # 5. Leftover directories
    Write-Host "  Checking filesystem..." -ForegroundColor Gray
    $dirPaths = @(
        "$env:ProgramFiles"
        "${env:ProgramFiles(x86)}"
        "$env:ProgramData"
        "$env:LOCALAPPDATA"
        "$env:APPDATA"
        "$env:LOCALAPPDATA\Programs"
    )
    foreach ($base in $dirPaths) {
        if (-not (Test-Path $base)) { continue }
        Get-ChildItem $base -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -like "*$Target*" } |
            ForEach-Object {
                $sizeBytes = (Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue |
                              Measure-Object -Property Length -Sum).Sum
                $sizeMB = [math]::Round($sizeBytes / 1MB, 1)
                $findings += [PSCustomObject]@{
                    Type     = 'Directory'
                    Path     = $_.FullName
                    Detail   = "${sizeMB} MB"
                    Action   = 'Delete directory'
                    Command  = "Remove-Item -Path '$($_.FullName)' -Recurse -Force"
                }
            }
    }

    # 6. Leftover TEMP files
    Write-Host "  Checking TEMP folders..." -ForegroundColor Gray
    $tempPaths = @($env:TEMP, "$env:SystemRoot\Temp")
    foreach ($tmp in $tempPaths) {
        if (-not (Test-Path $tmp)) { continue }
        Get-ChildItem $tmp -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -like "*$Target*" } |
            ForEach-Object {
                $findings += [PSCustomObject]@{
                    Type     = 'TempDir'
                    Path     = $_.FullName
                    Detail   = 'Temporary files'
                    Action   = 'Delete directory'
                    Command  = "Remove-Item -Path '$($_.FullName)' -Recurse -Force"
                }
            }
    }

    # 7. Invalid desktop shortcuts
    Write-Host "  Checking desktop shortcuts..." -ForegroundColor Gray
    $desktopPaths = @(
        [Environment]::GetFolderPath('Desktop')
        [Environment]::GetFolderPath('CommonDesktopDirectory')
    )
    $wshShell = New-Object -ComObject WScript.Shell
    foreach ($deskPath in $desktopPaths) {
        if (-not (Test-Path $deskPath)) { continue }
        Get-ChildItem $deskPath -Filter '*.lnk' -ErrorAction SilentlyContinue | ForEach-Object {
            try {
                $shortcut = $wshShell.CreateShortcut($_.FullName)
                $shortcutTarget = $shortcut.TargetPath
                $nameMatch = $_.BaseName -like "*$Target*" -or $shortcutTarget -like "*$Target*"
                $targetMissing = $shortcutTarget -and -not (Test-Path $shortcutTarget -ErrorAction SilentlyContinue)
                if ($nameMatch -or $targetMissing) {
                    $reason = if ($nameMatch -and $targetMissing) { "Name matches + target missing" }
                              elseif ($nameMatch) { "Name matches '$Target'" }
                              else { "Target missing: $shortcutTarget" }
                    $findings += [PSCustomObject]@{
                        Type     = 'DesktopShortcut'
                        Path     = $_.FullName
                        Detail   = $reason
                        Action   = 'Delete shortcut'
                        Command  = "Remove-Item -Path '$($_.FullName)' -Force"
                    }
                }
            } catch {}
        }
    }

    # 8. Invalid taskbar pinned items
    Write-Host "  Checking taskbar pins..." -ForegroundColor Gray
    $taskbarPath = "$env:APPDATA\Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar"
    if (Test-Path $taskbarPath) {
        Get-ChildItem $taskbarPath -Filter '*.lnk' -ErrorAction SilentlyContinue | ForEach-Object {
            try {
                $shortcut = $wshShell.CreateShortcut($_.FullName)
                $shortcutTarget = $shortcut.TargetPath
                $nameMatch = $_.BaseName -like "*$Target*" -or $shortcutTarget -like "*$Target*"
                $targetMissing = $shortcutTarget -and -not (Test-Path $shortcutTarget -ErrorAction SilentlyContinue)
                if ($nameMatch -or $targetMissing) {
                    $reason = if ($nameMatch -and $targetMissing) { "Name matches + target missing" }
                              elseif ($nameMatch) { "Name matches '$Target'" }
                              else { "Target missing: $shortcutTarget" }
                    $findings += [PSCustomObject]@{
                        Type     = 'TaskbarPin'
                        Path     = $_.FullName
                        Detail   = $reason
                        Action   = 'Delete pinned shortcut'
                        Command  = "Remove-Item -Path '$($_.FullName)' -Force"
                    }
                }
            } catch {}
        }
    }

    # 9. Invalid Start Menu shortcuts
    Write-Host "  Checking Start Menu shortcuts..." -ForegroundColor Gray
    $startMenuPaths = @(
        [Environment]::GetFolderPath('StartMenu')
        [Environment]::GetFolderPath('CommonStartMenu')
    )
    foreach ($smPath in $startMenuPaths) {
        if (-not (Test-Path $smPath)) { continue }
        Get-ChildItem $smPath -Filter '*.lnk' -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
            try {
                $shortcut = $wshShell.CreateShortcut($_.FullName)
                $shortcutTarget = $shortcut.TargetPath
                $nameMatch = $_.BaseName -like "*$Target*" -or $shortcutTarget -like "*$Target*"
                $targetMissing = $shortcutTarget -and -not (Test-Path $shortcutTarget -ErrorAction SilentlyContinue)
                if ($nameMatch -or $targetMissing) {
                    $reason = if ($nameMatch -and $targetMissing) { "Name matches + target missing" }
                              elseif ($nameMatch) { "Name matches '$Target'" }
                              else { "Target missing: $shortcutTarget" }
                    $findings += [PSCustomObject]@{
                        Type     = 'StartMenuShortcut'
                        Path     = $_.FullName
                        Detail   = $reason
                        Action   = 'Delete shortcut'
                        Command  = "Remove-Item -Path '$($_.FullName)' -Force"
                    }
                }
            } catch {}
        }
        Get-ChildItem "$smPath\Programs" -Directory -Recurse -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -like "*$Target*" } |
            ForEach-Object {
                $hasFiles = (Get-ChildItem $_.FullName -File -Recurse -ErrorAction SilentlyContinue | Measure-Object).Count
                if ($hasFiles -eq 0) {
                    $findings += [PSCustomObject]@{
                        Type     = 'StartMenuFolder'
                        Path     = $_.FullName
                        Detail   = 'Empty program folder'
                        Action   = 'Delete folder'
                        Command  = "Remove-Item -Path '$($_.FullName)' -Recurse -Force"
                    }
                }
            }
    }

    # 10. C:\ root anomaly scan — detect directories that don't belong in standard Windows
    Write-Host "  Checking C:\ root for anomalous directories..." -ForegroundColor Gray
    Get-ChildItem C:\ -Directory -ErrorAction SilentlyContinue | Where-Object {
        $dirName = $_.Name
        # Skip known standard directories (case-insensitive)
        -not ($knownRootDirs | Where-Object { $dirName -eq $_ }) -and
        # Skip hidden/system directories starting with $
        -not $dirName.StartsWith('$')
    } | ForEach-Object {
        $dirName = $_.Name
        # Check if it matches the target keyword OR contains Chinese characters (always suspicious at C:\)
        $matchesTarget = $false
        foreach ($k in $keywords) {
            if ($dirName -like "*$k*" -or $dirName.ToLower().Contains($k.ToLower())) {
                $matchesTarget = $true; break
            }
        }
        # Also flag non-standard directories regardless of target match (if they contain CJK or look vendor-ish)
        $hasCJK = $dirName -match '[\u4e00-\u9fff]'

        if ($matchesTarget -or $hasCJK) {
            $sizeBytes = (Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue |
                          Measure-Object -Property Length -Sum).Sum
            $sizeMB = [math]::Round($sizeBytes / 1MB, 1)
            $reason = if ($matchesTarget -and $hasCJK) { "Matches '$Target' + CJK name at C:\ root" }
                      elseif ($matchesTarget) { "Matches '$Target' at C:\ root" }
                      else { "[SUSPECT] Non-standard CJK-named directory at C:\ root" }
            $findings += [PSCustomObject]@{
                Type     = 'Directory'
                Path     = $_.FullName
                Detail   = "$reason ($sizeMB MB)"
                Action   = 'Review and delete directory'
                Command  = "Remove-Item -Path '$($_.FullName)' -Recurse -Force"
            }
        }
    }

    return $findings
}

function Show-LeftoverReport([string]$Target, [array]$Findings) {
    if ($Findings.Count -eq 0) {
        Write-Host "  [CLEAN] No leftovers found for '$Target'" -ForegroundColor Green
    } else {
        Write-Host "`n  Found $($Findings.Count) leftover(s):" -ForegroundColor Yellow
        $Findings | Format-Table -Property @(
            @{N='#'; E={[array]::IndexOf($Findings, $_) + 1}; W=3},
            'Type',
            @{N='Path'; E={if($_.Path.Length -gt 60){$_.Path.Substring(0,57)+'...'}else{$_.Path}}},
            'Detail',
            'Action'
        ) -AutoSize -Wrap

        Write-Host "`n  Cleanup commands (AI should present these for user confirmation):" -ForegroundColor Cyan
        $i = 0
        foreach ($f in $Findings) {
            $i++
            Write-Host "    # $i. $($f.Type): $($f.Path)" -ForegroundColor DarkGray
            Write-Host "    $($f.Command)" -ForegroundColor White
        }
    }
}

# ── Main actions ──
switch ($Action) {
    'List' {
        Write-Host "`nInstalled Software:" -ForegroundColor Cyan
        $software = Get-InstalledSoftware
        Write-Host "  Total: $($software.Count) programs`n" -ForegroundColor Yellow

        $software |
            Select-Object DisplayName, DisplayVersion, Publisher, SizeMB, InstallDate |
            Format-Table -AutoSize -Wrap

        # Also check for winget availability
        $wingetAvailable = $false
        try {
            $null = Get-Command winget -ErrorAction Stop
            $wingetAvailable = $true
        } catch {}

        if ($wingetAvailable) {
            Write-Host "  [INFO] winget is available — can be used for cleaner uninstalls." -ForegroundColor Green
        } else {
            Write-Host "  [INFO] winget not found — will use native uninstallers." -ForegroundColor DarkYellow
        }
    }

    'Uninstall' {
        Write-Host "`n" -NoNewline
        Write-Host ('!' * 60) -ForegroundColor Yellow
        Write-Host ' WARNING: Terminal-based uninstall has significant limitations' -ForegroundColor Yellow
        Write-Host ('!' * 60) -ForegroundColor Yellow
        Write-Host @"

  Many programs (especially rogue software) have GUI-only uninstallers
  that will hang the terminal or fail silently. The recommended workflow:
    1. Use this script's List mode to identify what to remove
    2. Uninstall manually via Settings > Apps or Control Panel
    3. Use this script's Cleanup mode to remove leftovers

  Proceeding with terminal uninstall (timeout: $TimeoutSeconds seconds per program)...

"@ -ForegroundColor Yellow

        if (-not $Programs) {
            Write-Error "Uninstall action requires the -Programs parameter (JSON array)."
            exit 1
        }

        try {
            $programList = $Programs | ConvertFrom-Json
        } catch {
            Write-Error "Failed to parse Programs parameter. Format: '[{`"Name`":`"ProgramName`"}]'"
            exit 1
        }

        if ($programList.Count -eq 0) {
            Write-Host "No programs specified." -ForegroundColor Yellow
            exit 0
        }

        # Check winget availability
        $wingetAvailable = $false
        try {
            $null = Get-Command winget -ErrorAction Stop
            $wingetAvailable = $true
        } catch {}

        $results = @()

        foreach ($prog in $programList) {
            $name = $prog.Name
            Write-Host "`n─── Uninstalling: $name ───" -ForegroundColor Cyan

            $entries = Find-SoftwareEntry $name
            if (-not $entries) {
                Write-Host "  [SKIP] '$name' — not found in registry" -ForegroundColor DarkYellow
                $results += [PSCustomObject]@{ Name=$name; Status='NotFound'; Method='N/A' }
                continue
            }

            # If multiple matches, list them
            if (@($entries).Count -gt 1) {
                Write-Host "  [WARN] Multiple matches found:" -ForegroundColor Yellow
                $i = 0
                foreach ($e in $entries) {
                    $i++
                    Write-Host "    $i. $($e.DisplayName) ($($e.DisplayVersion))" -ForegroundColor Yellow
                }
                Write-Host "  Using first match: $($entries[0].DisplayName)" -ForegroundColor Yellow
                $entries = @($entries)[0]
            } else {
                $entries = @($entries)[0]
            }

            Write-Host "  Found: $($entries.DisplayName) v$($entries.DisplayVersion)" -ForegroundColor White

            # Strategy 1: Try winget first (cleanest and most reliable from terminal)
            $uninstalled = $false
            if ($wingetAvailable) {
                Write-Host "  Attempting winget uninstall (timeout: ${TimeoutSeconds}s)..." -ForegroundColor Gray
                try {
                    $wingetArgs = @('uninstall', '--name', $entries.DisplayName, '--accept-source-agreements')
                    if ($Quiet) { $wingetArgs += '--silent' }

                    $proc = Start-Process winget -ArgumentList ($wingetArgs -join ' ') -PassThru -NoNewWindow -ErrorAction Stop
                    $exited = $proc.WaitForExit($TimeoutSeconds * 1000)

                    if (-not $exited) {
                        Write-Host "  [TIMEOUT] winget did not finish within ${TimeoutSeconds}s — killing process" -ForegroundColor Red
                        $proc | Stop-Process -Force -ErrorAction SilentlyContinue
                        Write-Host "  [INFO] Please uninstall '$($entries.DisplayName)' manually via Settings > Apps" -ForegroundColor Yellow
                        $results += [PSCustomObject]@{ Name=$entries.DisplayName; Status='Timeout'; Method='winget' }
                        continue
                    } elseif ($proc.ExitCode -eq 0) {
                        Write-Host "  [OK] Uninstalled via winget" -ForegroundColor Green
                        $uninstalled = $true
                        $results += [PSCustomObject]@{ Name=$entries.DisplayName; Status='Uninstalled'; Method='winget' }
                    } else {
                        Write-Host "  [INFO] winget failed (exit code: $($proc.ExitCode)), falling back to native uninstaller" -ForegroundColor DarkYellow
                    }
                } catch {
                    Write-Host "  [INFO] winget error, falling back to native uninstaller" -ForegroundColor DarkYellow
                }
            }

            # Strategy 2: Native uninstaller (with timeout protection)
            if (-not $uninstalled) {
                $uninstallCmd = if ($Quiet -and $entries.QuietUninstallString) {
                    $entries.QuietUninstallString
                } else {
                    $entries.UninstallString
                }

                if (-not $uninstallCmd) {
                    Write-Host "  [FAIL] No uninstall command found in registry" -ForegroundColor Red
                    Write-Host "  [INFO] Please uninstall '$($entries.DisplayName)' manually via Settings > Apps" -ForegroundColor Yellow
                    $results += [PSCustomObject]@{ Name=$entries.DisplayName; Status='NoUninstaller'; Method='N/A' }
                    continue
                }

                Write-Host "  Running: $uninstallCmd (timeout: ${TimeoutSeconds}s)" -ForegroundColor Gray

                try {
                    $proc = $null
                    # Parse the uninstall command — handle both EXE and MsiExec
                    if ($uninstallCmd -match 'MsiExec') {
                        # MSI-based uninstall
                        $msiArgs = $uninstallCmd -replace '^MsiExec\.exe\s*', ''
                        if ($Quiet -and $msiArgs -notmatch '/quiet|/qn') {
                            $msiArgs = "$msiArgs /quiet /norestart"
                        }
                        $proc = Start-Process msiexec.exe -ArgumentList $msiArgs -PassThru -ErrorAction Stop
                    } else {
                        # EXE-based uninstall
                        $proc = Start-Process cmd.exe -ArgumentList "/c `"$uninstallCmd`"" -PassThru -ErrorAction Stop
                    }

                    $exited = $proc.WaitForExit($TimeoutSeconds * 1000)

                    if (-not $exited) {
                        Write-Host "  [TIMEOUT] Uninstaller did not finish within ${TimeoutSeconds}s — killing process" -ForegroundColor Red
                        $proc | Stop-Process -Force -ErrorAction SilentlyContinue
                        Write-Host "  [INFO] This program likely has a GUI uninstaller that cannot run from the terminal." -ForegroundColor Yellow
                        Write-Host "  [INFO] Please uninstall '$($entries.DisplayName)' manually:" -ForegroundColor Yellow
                        Write-Host "         Settings > Apps > Installed apps (Windows 11)" -ForegroundColor Yellow
                        Write-Host "         Control Panel > Programs and Features (Windows 10)" -ForegroundColor Yellow
                        $results += [PSCustomObject]@{ Name=$entries.DisplayName; Status='Timeout-ManualRequired'; Method='Native' }
                        continue
                    }

                    # Verify removal
                    $stillExists = Find-SoftwareEntry $entries.DisplayName
                    if (-not $stillExists) {
                        Write-Host "  [OK] Uninstalled successfully" -ForegroundColor Green
                        $results += [PSCustomObject]@{ Name=$entries.DisplayName; Status='Uninstalled'; Method='Native' }
                    } else {
                        Write-Host "  [WARN] Uninstaller ran but registry entry still exists — may need reboot or manual cleanup" -ForegroundColor Yellow
                        $results += [PSCustomObject]@{ Name=$entries.DisplayName; Status='MayNeedReboot'; Method='Native' }
                    }
                } catch {
                    Write-Host "  [FAIL] Uninstall error: $($_.Exception.Message)" -ForegroundColor Red
                    Write-Host "  [INFO] Please uninstall '$($entries.DisplayName)' manually via Settings > Apps" -ForegroundColor Yellow
                    $results += [PSCustomObject]@{ Name=$entries.DisplayName; Status='Error'; Method='Native' }
                }
            }
        }

        # Summary
        Write-Host "`n─── Uninstall Summary ───" -ForegroundColor Cyan
        $results | Format-Table -AutoSize

        # Post-summary advice
        $failedOrTimeout = $results | Where-Object { $_.Status -match 'Timeout|Error|NoUninstaller|ManualRequired' }
        if ($failedOrTimeout) {
            Write-Host "Some programs could not be uninstalled from the terminal." -ForegroundColor Yellow
            Write-Host "Please uninstall them manually, then run:" -ForegroundColor Yellow
            Write-Host "  .\uninstall-software.ps1 -Action Cleanup -CleanupTarget 'Name1','Name2'" -ForegroundColor White
            Write-Host "to clean up any leftovers.`n" -ForegroundColor Yellow
        }
    }

    'Cleanup' {
        if (-not $CleanupTarget -or $CleanupTarget.Count -eq 0) {
            Write-Error "Cleanup action requires the -CleanupTarget parameter."
            exit 1
        }

        Write-Host "`n─── Scanning for leftovers ───" -ForegroundColor Cyan

        foreach ($target in $CleanupTarget) {
            $findings = Invoke-LeftoverScan -Target $target
            Show-LeftoverReport -Target $target -Findings $findings
        }
    }

    'CleanupPlan' {
        if (-not $CleanupTarget -or $CleanupTarget.Count -eq 0) {
            Write-Error "CleanupPlan action requires the -CleanupTarget parameter."
            exit 1
        }

        Write-Host "Scanning for leftovers (plan mode)..." -ForegroundColor Cyan

        $allFindings = @()
        foreach ($target in $CleanupTarget) {
            $findings = Invoke-LeftoverScan -Target $target
            foreach ($f in $findings) {
                $allFindings += [PSCustomObject]@{
                    Target  = $target
                    Type    = $f.Type
                    Path    = $f.Path
                    Detail  = $f.Detail
                    Action  = $f.Action
                    Command = $f.Command
                }
            }
        }

        # Output structured JSON to stdout for AI consumption
        $allFindings | ConvertTo-Json -Depth 5
    }

    'CleanupExecute' {
        if (-not $Plan) {
            Write-Error "CleanupExecute action requires the -Plan parameter (JSON from CleanupPlan)."
            exit 1
        }

        try {
            $planItems = $Plan | ConvertFrom-Json
        } catch {
            Write-Error "Failed to parse Plan parameter. Provide valid JSON from CleanupPlan."
            exit 1
        }

        if (-not (Test-Path $BackupDir)) {
            New-Item -Path $BackupDir -ItemType Directory -Force | Out-Null
        }

        $timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
        $succeeded = @()
        $failed = @()
        $pendingReboot = @()

        Write-Host "`n─── Executing Cleanup Plan ($($planItems.Count) items) ───" -ForegroundColor Cyan
        Write-Host "  Backup dir: $BackupDir" -ForegroundColor DarkGray

        $i = 0
        foreach ($item in $planItems) {
            $i++
            $logPrefix = "  [$i/$($planItems.Count)]"

            switch ($item.Type) {
                'Registry' {
                    # Backup registry key before deletion
                    $regPath = $item.Path
                    $backupFile = Join-Path $BackupDir "reg-backup-$timestamp-$i.reg"
                    $regExportPath = $regPath -replace '^Microsoft\.PowerShell\.Core\\Registry::', '' -replace ':', ''
                    Write-Host "$logPrefix Backing up registry: $regPath" -ForegroundColor DarkGray
                    reg export $regExportPath $backupFile /y 2>$null | Out-Null
                    try {
                        Remove-Item -Path "Registry::$regPath" -Recurse -Force -ErrorAction Stop
                        Write-Host "$logPrefix [OK] Registry removed: $regPath" -ForegroundColor Green
                        $succeeded += [PSCustomObject]@{ Type=$item.Type; Path=$regPath; Backup=$backupFile }
                    } catch {
                        Write-Host "$logPrefix [FAIL] Registry: $($_.Exception.Message)" -ForegroundColor Red
                        $failed += [PSCustomObject]@{ Type=$item.Type; Path=$regPath; Error=$_.Exception.Message }
                    }
                }
                'Service' {
                    $svcName = $item.Path
                    $backupFile = Join-Path $BackupDir "svc-backup-$svcName-$timestamp.reg"
                    Write-Host "$logPrefix Backing up service: $svcName" -ForegroundColor DarkGray
                    reg export "HKLM\SYSTEM\CurrentControlSet\Services\$svcName" $backupFile /y 2>$null | Out-Null
                    $stopOut = sc.exe stop $svcName 2>&1 | Out-String
                    $delOut = sc.exe delete $svcName 2>&1 | Out-String
                    if ($delOut -match 'SUCCESS|MARKED_FOR_DELETE') {
                        Write-Host "$logPrefix [OK] Service deleted: $svcName" -ForegroundColor Green
                        $succeeded += [PSCustomObject]@{ Type=$item.Type; Path=$svcName; Backup=$backupFile }
                    } else {
                        Write-Host "$logPrefix [FAIL] Service delete: $($delOut.Trim())" -ForegroundColor Red
                        $failed += [PSCustomObject]@{ Type=$item.Type; Path=$svcName; Error=$delOut.Trim() }
                    }
                }
                'ScheduledTask' {
                    $taskFullPath = $item.Path
                    # Export task XML for rollback
                    $taskName = ($taskFullPath -split '\\')[-1]
                    $taskPath = $taskFullPath.Substring(0, $taskFullPath.Length - $taskName.Length)
                    $xmlBackup = Join-Path $BackupDir "task-$taskName-$timestamp.xml"
                    try {
                        $taskObj = Get-ScheduledTask -TaskName $taskName -TaskPath $taskPath -ErrorAction Stop
                        Export-ScheduledTask -TaskName $taskName -TaskPath $taskPath | Out-File $xmlBackup -Encoding UTF8
                        Unregister-ScheduledTask -TaskName $taskName -TaskPath $taskPath -Confirm:$false -ErrorAction Stop
                        Write-Host "$logPrefix [OK] Task unregistered: $taskFullPath" -ForegroundColor Green
                        $succeeded += [PSCustomObject]@{ Type=$item.Type; Path=$taskFullPath; Backup=$xmlBackup }
                    } catch {
                        Write-Host "$logPrefix [FAIL] Task: $($_.Exception.Message)" -ForegroundColor Red
                        $failed += [PSCustomObject]@{ Type=$item.Type; Path=$taskFullPath; Error=$_.Exception.Message }
                    }
                }
                'StartupItem' {
                    try {
                        # Path format: HKCU:\...\Run\ItemName — extract key and name
                        $parts = $item.Path -split '\\'
                        $propName = $parts[-1]
                        $keyPath = ($parts[0..($parts.Count - 2)]) -join '\'
                        Remove-ItemProperty -Path $keyPath -Name $propName -Force -ErrorAction Stop
                        Write-Host "$logPrefix [OK] Startup item removed: $($item.Path)" -ForegroundColor Green
                        $succeeded += [PSCustomObject]@{ Type=$item.Type; Path=$item.Path }
                    } catch {
                        Write-Host "$logPrefix [FAIL] Startup item: $($_.Exception.Message)" -ForegroundColor Red
                        $failed += [PSCustomObject]@{ Type=$item.Type; Path=$item.Path; Error=$_.Exception.Message }
                    }
                }
                { $_ -in 'Directory', 'TempDir', 'StartMenuFolder' } {
                    try {
                        Remove-Item -Path $item.Path -Recurse -Force -ErrorAction Stop
                        Write-Host "$logPrefix [OK] Deleted: $($item.Path)" -ForegroundColor Green
                        $succeeded += [PSCustomObject]@{ Type=$item.Type; Path=$item.Path }
                    } catch {
                        if ($_.Exception.Message -match 'being used by another process|access.*denied|cannot remove') {
                            # File locked — schedule for deletion on next reboot
                            Write-Host "$logPrefix [LOCKED] Scheduling for reboot deletion: $($item.Path)" -ForegroundColor Yellow
                            try {
                                $pendingKey = 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager'
                                $existing = @((Get-ItemProperty $pendingKey -Name PendingFileRenameOperations -ErrorAction SilentlyContinue).PendingFileRenameOperations)
                                $existing += "\??\$($item.Path)"
                                $existing += ''  # empty string = delete (not rename)
                                Set-ItemProperty -Path $pendingKey -Name PendingFileRenameOperations -Value $existing
                                Write-Host "$logPrefix [PENDING] Will be deleted on next reboot" -ForegroundColor Yellow
                                $pendingReboot += [PSCustomObject]@{ Type=$item.Type; Path=$item.Path }
                            } catch {
                                Write-Host "$logPrefix [FAIL] Could not schedule reboot delete: $($_.Exception.Message)" -ForegroundColor Red
                                $failed += [PSCustomObject]@{ Type=$item.Type; Path=$item.Path; Error="Locked + pending failed: $($_.Exception.Message)" }
                            }
                        } else {
                            Write-Host "$logPrefix [FAIL] Delete: $($_.Exception.Message)" -ForegroundColor Red
                            $failed += [PSCustomObject]@{ Type=$item.Type; Path=$item.Path; Error=$_.Exception.Message }
                        }
                    }
                }
                { $_ -in 'DesktopShortcut', 'TaskbarPin', 'StartMenuShortcut' } {
                    try {
                        Remove-Item -Path $item.Path -Force -ErrorAction Stop
                        Write-Host "$logPrefix [OK] Deleted: $($item.Path)" -ForegroundColor Green
                        $succeeded += [PSCustomObject]@{ Type=$item.Type; Path=$item.Path }
                    } catch {
                        Write-Host "$logPrefix [FAIL] Delete: $($_.Exception.Message)" -ForegroundColor Red
                        $failed += [PSCustomObject]@{ Type=$item.Type; Path=$item.Path; Error=$_.Exception.Message }
                    }
                }
                default {
                    Write-Host "$logPrefix [SKIP] Unknown type: $($item.Type)" -ForegroundColor DarkYellow
                }
            }
        }

        # ── Summary ──
        Write-Host "`n$('=' * 50)" -ForegroundColor Cyan
        Write-Host "Cleanup Summary: OK $($succeeded.Count) | Failed $($failed.Count) | Pending Reboot $($pendingReboot.Count)" -ForegroundColor Cyan

        if ($pendingReboot.Count -gt 0) {
            Write-Host "`n⚠️ $($pendingReboot.Count) item(s) are locked and will be deleted on next reboot:" -ForegroundColor Yellow
            $pendingReboot | Format-Table -AutoSize
            Write-Host "A reboot is required to complete cleanup." -ForegroundColor Yellow
        }

        if ($failed.Count -gt 0) {
            Write-Host "`nFailed items:" -ForegroundColor Red
            $failed | Format-Table -AutoSize -Wrap
        }

        Write-Host "`nBackup location: $BackupDir" -ForegroundColor Cyan
    }
}

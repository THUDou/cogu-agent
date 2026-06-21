#Requires -Version 5.1
<#
.SYNOPSIS
    win-sweep diagnostics — scan and report system status.
.DESCRIPTION
    Collects disk usage, installed software, startup items, services,
    scheduled tasks, and memory usage rankings, outputting a structured report.

    Two preset modes:
    - Quick (default): System overview, disk capacity, startups, non-svchost services,
      non-Microsoft tasks, memory top. Skips slow directory scanning.
    - Deep: Everything in Quick + C: top-level directory sizes (recursive scan).
      Use when investigating disk space issues specifically.

    Individual sections can still be selected with -Section.
.PARAMETER Section
    Default 'Quick'. Use 'Deep' to include directory size scan, 'All' for everything,
    or pick individual sections.
.PARAMETER Output
    Output format: 'Text' (default, human-readable) or 'Json' (structured, for AI parsing).
.NOTES
    Full results require an elevated (Administrator) PowerShell session.
    Without admin privileges, some information will be skipped (service details, etc.).
#>

[CmdletBinding()]
param(
    [ValidateSet('Quick','Deep','All','System','Disk','DiskDeep','Software','Startups','Services','Tasks','Memory','Telemetry','Shortcuts','CleanableSpace')]
    [string[]]$Section = 'Quick',

    [ValidateSet('Text','Json')]
    [string]$Output = 'Text'
)

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)

if (-not $isAdmin) {
    Write-Host "`n" -NoNewline
    Write-Host ('!' * 60) -ForegroundColor Red
    Write-Host ' WARNING: Running WITHOUT Administrator privileges' -ForegroundColor Red
    Write-Host ('!' * 60) -ForegroundColor Red
    Write-Host @"

  The following information will be INCOMPLETE or MISSING:
    - Service binary paths and startup accounts
    - HKLM startup items
    - Scheduled task internal details
    - Signature verification for some executables
    - Full memory usage for system processes

  For a complete diagnosis, restart your tool as Administrator.
  (Right-click the app icon -> Run as administrator)

  Proceeding with partial results...
"@ -ForegroundColor Yellow
    Write-Host ('!' * 60) -ForegroundColor Red
    Write-Host ''
}

function Write-Section([string]$Title) {
    Write-Host "`n$('=' * 60)" -ForegroundColor Cyan
    Write-Host " $Title" -ForegroundColor Cyan
    Write-Host "$('=' * 60)" -ForegroundColor Cyan
}

# Resolve Quick/Deep/All into individual sections
$runAll    = $Section -contains 'All' -or $Section -contains 'Deep'
$runQuick  = $Section -contains 'Quick'
$runDeep   = $Section -contains 'Deep' -or $Section -contains 'All'

# Quick = System + Disk(summary) + Software + Startups + Services + Tasks + Memory
# Deep  = Quick + DiskDeep (directory size scan)

$jsonResult = @{}  # Collect structured data when Output=Json

# ── System Info ──
if ($runAll -or $runQuick -or $Section -contains 'System') {
    Write-Section 'System Info'
    $os = Get-CimInstance Win32_OperatingSystem
    $cs = Get-CimInstance Win32_ComputerSystem

    # Detect Windows edition type
    $editionType = 'Unknown'
    $caption = $os.Caption
    if ($caption -match 'LTSC|LTSB') { $editionType = 'LTSC' }
    elseif ($caption -match 'Enterprise') { $editionType = 'Enterprise' }
    elseif ($caption -match 'Education') { $editionType = 'Education' }
    elseif ($caption -match 'Pro') { $editionType = 'Pro' }
    elseif ($caption -match 'Home') { $editionType = 'Home' }

    [PSCustomObject]@{
        ComputerName  = $cs.Name
        OS            = $os.Caption
        Build         = $os.BuildNumber
        EditionType   = $editionType
        InstallDate   = $os.InstallDate
        LastBoot      = $os.LastBootUpTime
        Uptime        = ((Get-Date) - $os.LastBootUpTime).ToString('d\.hh\:mm\:ss')
        TotalMemoryGB = [math]::Round($cs.TotalPhysicalMemory / 1GB, 1)
        FreeMemoryGB  = [math]::Round($os.FreePhysicalMemory / 1MB, 1)
        AdminSession  = $isAdmin
    } | Format-List

    # Edition-specific warnings
    if ($editionType -eq 'LTSC') {
        Write-Host "  [NOTE] LTSC edition detected — no Microsoft Store, no Cortana, System Restore may be disabled by default." -ForegroundColor DarkYellow
    } elseif ($editionType -eq 'Home') {
        Write-Host "  [NOTE] Home edition detected — no Group Policy Editor (gpedit.msc)." -ForegroundColor DarkYellow
    }

    if ($Output -eq 'Json') {
        $jsonResult['System'] = [PSCustomObject]@{
            ComputerName = $cs.Name; OS = $os.Caption; Build = $os.BuildNumber
            EditionType = $editionType
            InstallDate = $os.InstallDate; LastBoot = $os.LastBootUpTime
            TotalMemoryGB = [math]::Round($cs.TotalPhysicalMemory / 1GB, 1)
            FreeMemoryGB = [math]::Round($os.FreePhysicalMemory / 1MB, 1)
            AdminSession = $isAdmin
        }
    }
}

# ── Disk Usage ──
if ($runAll -or $runQuick -or $Section -contains 'Disk' -or $Section -contains 'DiskDeep') {
    Write-Section 'Disk Usage'
    $diskInfo = Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" |
        Select-Object DeviceID,
            @{N='SizeGB';    E={[math]::Round($_.Size / 1GB, 1)}},
            @{N='FreeGB';    E={[math]::Round($_.FreeSpace / 1GB, 1)}},
            @{N='UsedGB';    E={[math]::Round(($_.Size - $_.FreeSpace) / 1GB, 1)}},
            @{N='UsedPct';   E={[math]::Round(($_.Size - $_.FreeSpace) / $_.Size * 100, 1)}}

    if ($Output -eq 'Json') { $jsonResult['Disk'] = $diskInfo }
    else { $diskInfo | Format-Table -AutoSize }

    # C: drive top-level directory sizes — Deep/DiskDeep/All only (slow operation)
    if ($runDeep -or $Section -contains 'DiskDeep') {
        Write-Host "`nC:\ Top-Level Directory Sizes (Top 15) — this may take a moment..." -ForegroundColor Yellow
        $knownRootDirs = @(
            'Windows', 'Program Files', 'Program Files (x86)', 'Users', 'PerfLogs',
            'Recovery', '$Recycle.Bin', 'System Volume Information', 'Documents and Settings',
            'ProgramData', 'Intel', 'AMD', 'NVIDIA', 'MSOCache', 'inetpub', 'Boot',
            'EFI', 'OneDriveTemp', 'Drivers'
        )
        $dirSizes = Get-ChildItem C:\ -Directory -ErrorAction SilentlyContinue |
            ForEach-Object {
                $size = (Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue |
                         Measure-Object -Property Length -Sum).Sum
                $isSuspect = -not ($knownRootDirs | Where-Object { $_ -eq $_.Name }) -and
                             -not $_.Name.StartsWith('$')
                # More accurate check: compare against whitelist
                $isKnown = $false
                foreach ($kd in $knownRootDirs) {
                    if ($_.Name -eq $kd) { $isKnown = $true; break }
                }
                $flag = if (-not $isKnown -and -not $_.Name.StartsWith('$')) { '[SUSPECT] ' } else { '' }
                [PSCustomObject]@{
                    Directory = "$flag$($_.Name)"
                    SizeGB    = [math]::Round($size / 1GB, 2)
                }
            } |
            Sort-Object SizeGB -Descending | Select-Object -First 15

        if ($Output -eq 'Json') { $jsonResult['DiskDirectories'] = $dirSizes }
        else { $dirSizes | Format-Table -AutoSize }
    } elseif ($runQuick) {
        Write-Host "`n  (Directory size scan skipped in Quick mode. Use -Section Deep for full scan.)" -ForegroundColor DarkGray
    }
}

# ── Installed Software ──
if ($runAll -or $runQuick -or $Section -contains 'Software') {
    Write-Section 'Installed Software (Top 30 by size)'
    $regPaths = @(
        'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*'
        'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*'
        'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*'
    )
    $regPaths | ForEach-Object { Get-ItemProperty $_ -ErrorAction SilentlyContinue } |
        Where-Object { $_.DisplayName -and $_.DisplayName.Trim() } |
        Select-Object DisplayName, DisplayVersion, Publisher,
            @{N='SizeMB'; E={[math]::Round($_.EstimatedSize / 1024, 1)}} |
        Sort-Object SizeMB -Descending | Select-Object -First 30 |
        Format-Table -AutoSize
}

# ── Startup Items ──
if ($runAll -or $runQuick -or $Section -contains 'Startups') {
    Write-Section 'Startup Items'

    $runKeys = @(
        @{ Scope='HKCU'; Path='HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' }
        @{ Scope='HKLM'; Path='HKLM:\Software\Microsoft\Windows\CurrentVersion\Run' }
    )
    foreach ($k in $runKeys) {
        Write-Host "`n$($k.Scope)\Run:" -ForegroundColor Yellow
        $props = Get-ItemProperty $k.Path -ErrorAction SilentlyContinue
        if ($props) {
            $props.PSObject.Properties |
                Where-Object { $_.Name -notmatch '^PS(Path|ParentPath|ChildName|Provider|Drive)$' } |
                ForEach-Object { [PSCustomObject]@{ Name=$_.Name; Command=$_.Value } } |
                Format-Table -AutoSize -Wrap
        } else {
            Write-Host '  (empty)'
        }
    }

    # RunDisabled (backed-up startup items)
    $disPath = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\RunDisabled'
    if (Test-Path $disPath) {
        Write-Host "`nHKCU\RunDisabled (disabled backups):" -ForegroundColor Yellow
        (Get-ItemProperty $disPath -ErrorAction SilentlyContinue).PSObject.Properties |
            Where-Object { $_.Name -notmatch '^PS(Path|ParentPath|ChildName|Provider|Drive)$' } |
            ForEach-Object { [PSCustomObject]@{ Name=$_.Name; Command=$_.Value } } |
            Format-Table -AutoSize -Wrap
    }
}

# ── Services ──
if ($runAll -or $runQuick -or $Section -contains 'Services') {
    Write-Section 'Auto-Start Services (non-svchost first)'
    $services = Get-CimInstance Win32_Service -Filter "StartMode='Auto'" |
        Select-Object Name, DisplayName, State, StartName,
            @{N='BinaryPath'; E={
                # Truncate to first 80 chars for readability
                $p = $_.PathName
                if ($p.Length -gt 80) { $p.Substring(0, 77) + '...' } else { $p }
            }},
            @{N='IsSvchost'; E={ $_.PathName -match 'svchost\.exe' }}

    Write-Host "`nNon-svchost auto-start services ($($services | Where-Object {-not $_.IsSvchost} | Measure-Object | Select-Object -ExpandProperty Count)):" -ForegroundColor Yellow
    $services | Where-Object { -not $_.IsSvchost } |
        Sort-Object Name |
        Select-Object Name, DisplayName, State, StartName, BinaryPath |
        Format-Table -AutoSize -Wrap

    $svchostCount = ($services | Where-Object {$_.IsSvchost} | Measure-Object).Count
    Write-Host "`nsvchost-hosted auto-start services: $svchostCount (names only — expand with -Section Services if needed)" -ForegroundColor DarkGray
    $services | Where-Object { $_.IsSvchost } |
        Sort-Object Name |
        Select-Object Name, DisplayName |
        Format-Table -AutoSize
}

# ── Scheduled Tasks ──
if ($runAll -or $runQuick -or $Section -contains 'Tasks') {
    Write-Section 'Enabled Non-Microsoft Scheduled Tasks'
    Get-ScheduledTask -ErrorAction SilentlyContinue |
        Where-Object { $_.State -ne 'Disabled' -and $_.TaskPath -notmatch '^\\Microsoft\\' } |
        Select-Object TaskName, TaskPath, State,
            @{N='Actions'; E={
                ($_.Actions | ForEach-Object {
                    if ($_.Execute) { $_.Execute + ' ' + $_.Arguments }
                }) -join '; '
            }} |
        Sort-Object TaskPath, TaskName |
        Format-Table -AutoSize -Wrap
}

# ── Memory Usage ──
if ($runAll -or $runQuick -or $Section -contains 'Memory') {
    Write-Section 'Memory Usage Top 30 (non-system processes)'
    Get-Process -ErrorAction SilentlyContinue |
        Where-Object { $_.ProcessName -notmatch '^(Idle|System|Registry|Memory Compression|smss|csrss|wininit|winlogon|services|lsass|svchost)$' } |
        Sort-Object WorkingSet64 -Descending | Select-Object -First 30 |
        Select-Object @{N='PID';E={$_.Id}},
            ProcessName,
            @{N='MemMB'; E={[math]::Round($_.WorkingSet64 / 1MB, 1)}},
            @{N='Path'; E={
                $p = $_.Path
                if ($p -and $p.Length -gt 60) { $p.Substring(0, 57) + '...' } else { $p }
            }} |
        Format-Table -AutoSize
}

# ── Telemetry Quick Scan ──
if ($runAll -or $runQuick -or $Section -contains 'Telemetry') {
    Write-Section 'Telemetry Components (Quick Scan)'
    $telemetryPattern = 'telemetry|CEIP|SQM|DiagTrack|esrv|QUEENCREEK|UsageReport|NvTelemetry|dmwappushservice'
    $issueCount = 0

    $telemetrySvc = @(Get-CimInstance Win32_Service |
        Where-Object { $_.Name -match $telemetryPattern -or $_.DisplayName -match $telemetryPattern } |
        Select-Object Name, DisplayName, StartMode, State)
    if ($telemetrySvc.Count -gt 0) {
        Write-Host "`n  Telemetry Services ($($telemetrySvc.Count)):" -ForegroundColor Yellow
        $telemetrySvc | Format-Table -AutoSize
        $issueCount += $telemetrySvc.Count
    }

    $telemetryTasks = @(Get-ScheduledTask -ErrorAction SilentlyContinue |
        Where-Object { $_.State -ne 'Disabled' -and ($_.TaskName -match $telemetryPattern -or $_.TaskPath -match $telemetryPattern) } |
        Select-Object TaskName, TaskPath, State)
    if ($telemetryTasks.Count -gt 0) {
        Write-Host "  Telemetry Scheduled Tasks ($($telemetryTasks.Count)):" -ForegroundColor Yellow
        $telemetryTasks | Format-Table -AutoSize
        $issueCount += $telemetryTasks.Count
    }

    if ($issueCount -eq 0) {
        Write-Host "  No active telemetry components found." -ForegroundColor Green
    } else {
        Write-Host "  Total: $issueCount telemetry component(s) detected. See references/telemetry.md for three-layer sweep." -ForegroundColor Yellow
    }

    if ($Output -eq 'Json') {
        $jsonResult['Telemetry'] = @{ Services = $telemetrySvc; Tasks = $telemetryTasks; Count = $issueCount }
    }
}

# ── Multi-layer Association (Edge example: service + tasks for same product) ──
if ($runAll -or $runQuick) {
    Write-Section 'Multi-Layer Associations'
    # Detect products with presence across services + tasks + startups
    $edgeSvc = @(Get-CimInstance Win32_Service | Where-Object { $_.Name -match 'edgeupdate' } | Select-Object Name, StartMode, State)
    $edgeTasks = @(Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { $_.TaskName -match 'MicrosoftEdgeUpdate' -and $_.State -ne 'Disabled' } | Select-Object TaskName, State)
    if ($edgeSvc.Count -gt 0 -or $edgeTasks.Count -gt 0) {
        Write-Host "`n  Microsoft Edge Update:" -ForegroundColor Yellow
        if ($edgeSvc.Count -gt 0) {
            Write-Host "    Services:" -ForegroundColor DarkGray
            $edgeSvc | ForEach-Object { Write-Host "      - $($_.Name) ($($_.StartMode)/$($_.State))" }
        }
        if ($edgeTasks.Count -gt 0) {
            Write-Host "    Scheduled Tasks:" -ForegroundColor DarkGray
            $edgeTasks | ForEach-Object { Write-Host "      - $($_.TaskName) ($($_.State))" }
        }
        Write-Host "    [TIP] Optimizing Edge services without disabling tasks leaves update alive via task trigger." -ForegroundColor Cyan
    }

    # Generic: check for update-related tasks whose corresponding services exist
    $updateSvcNames = @(Get-CimInstance Win32_Service | Where-Object { $_.Name -match 'update' -and $_.Name -notmatch '^(wuauserv|UsoSvc)$' } | Select-Object -ExpandProperty Name)
    $updateTasks = @(Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object {
        $_.State -ne 'Disabled' -and $_.TaskPath -notmatch '^\\Microsoft\\' -and $_.TaskName -match 'update'
    })
    if ($updateSvcNames.Count -gt 0 -and $updateTasks.Count -gt 0) {
        Write-Host "`n  Other Update Service+Task pairs:" -ForegroundColor Yellow
        foreach ($sn in $updateSvcNames) {
            $related = $updateTasks | Where-Object { $_.TaskName -match ($sn -replace 'update', '') -or $_.TaskName -match $sn }
            if ($related) {
                Write-Host "    Service '$sn' has related tasks:" -ForegroundColor DarkGray
                $related | ForEach-Object { Write-Host "      - $($_.TaskName)" }
            }
        }
    }
}

# ── Shortcut Scan ──
if ($runAll -or $runQuick -or $Section -contains 'Shortcuts') {
    Write-Section 'Shortcut Health (Desktop / Start Menu / Taskbar)'

    # Known promotional keywords — shortcuts matching these with invalid targets are likely bundleware drops
    $promoKeywords = @(
        '安装向导', '修复工具', '优化大师', '清理大师', '清理工具',
        '压缩', '壁纸', '浏览器', '加速', '驱动', '体检', '游戏盒子', '维修',
        '免费领取', '红包', '练习', 'Setup', 'Install'
    )

    # Collect installed software names for cross-reference
    $installedNames = @()
    $regPaths2 = @(
        'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*'
        'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*'
        'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*'
    )
    $regPaths2 | ForEach-Object { Get-ItemProperty $_ -ErrorAction SilentlyContinue } |
        Where-Object { $_.DisplayName -and $_.DisplayName.Trim() } |
        ForEach-Object { $installedNames += $_.DisplayName.Trim() }

    $shortcutLocations = @(
        @{ Name='User Desktop';       Path=[Environment]::GetFolderPath('Desktop') }
        @{ Name='Public Desktop';      Path=[Environment]::GetFolderPath('CommonDesktopDirectory') }
        @{ Name='User Start Menu';     Path=[Environment]::GetFolderPath('StartMenu') }
        @{ Name='All Users Start Menu'; Path=[Environment]::GetFolderPath('CommonStartMenu') }
        @{ Name='Taskbar';             Path="$env:APPDATA\Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar" }
    )

    $wshShell = New-Object -ComObject WScript.Shell
    $shortcutResults = @()

    foreach ($loc in $shortcutLocations) {
        if (-not (Test-Path $loc.Path)) { continue }
        $recurse = $loc.Name -match 'Start Menu'
        $lnks = if ($recurse) {
            Get-ChildItem $loc.Path -Filter '*.lnk' -Recurse -ErrorAction SilentlyContinue
        } else {
            Get-ChildItem $loc.Path -Filter '*.lnk' -ErrorAction SilentlyContinue
        }

        foreach ($lnk in $lnks) {
            $status = 'OK'
            $tag = ''
            try {
                $shortcut = $wshShell.CreateShortcut($lnk.FullName)
                $target = $shortcut.TargetPath

                if (-not $target -or $target.Trim() -eq '') {
                    # Empty TargetPath: could be advertised shortcut or truly dead
                    if ($lnk.Length -gt 500) {
                        # Likely an MSI advertised shortcut — cross-check against installed software
                        $matchesInstalled = $installedNames | Where-Object { $lnk.BaseName -like "*$_*" -or $_ -like "*$($lnk.BaseName)*" } | Select-Object -First 1
                        if ($matchesInstalled) {
                            $status = 'ADVERTISED'
                            $tag = "Advertised (matches: $matchesInstalled)"
                        } else {
                            $status = 'UNKNOWN'
                            $tag = 'Empty TargetPath, large file — possible advertised shortcut'
                        }
                    } else {
                        $status = 'DEAD'
                        $tag = 'Empty TargetPath, small file'
                    }
                } elseif (-not (Test-Path $target -ErrorAction SilentlyContinue)) {
                    # Target path exists in shortcut but file is missing
                    $isPromo = $false
                    foreach ($kw in $promoKeywords) {
                        if ($lnk.BaseName -like "*$kw*") { $isPromo = $true; break }
                    }
                    # Also check if it matches any installed software
                    $matchesInstalled = $installedNames | Where-Object { $lnk.BaseName -like "*$_*" -or $_ -like "*$($lnk.BaseName)*" } | Select-Object -First 1

                    if ($isPromo -and -not $matchesInstalled) {
                        $status = 'PROMO'
                        $tag = "Promotional — target missing: $target"
                    } elseif ($matchesInstalled) {
                        $status = 'DEAD'
                        $tag = "Target missing (was: $matchesInstalled): $target"
                    } else {
                        $status = 'UNKNOWN'
                        $tag = "Target missing, unknown origin: $target"
                    }
                }
            } catch {
                # WScript.Shell failed (possibly CJK filename issue, see sc-gotchas #17)
                $status = 'ERROR'
                $tag = "COM error: $($_.Exception.Message)"
            }

            if ($status -ne 'OK') {
                $shortcutResults += [PSCustomObject]@{
                    Location = $loc.Name
                    Status   = "[$status]"
                    Name     = $lnk.BaseName
                    Detail   = $tag
                }
            }
        }
    }

    # Also scan for empty Start Menu program folders
    $emptyFolders = @()
    foreach ($loc in $shortcutLocations | Where-Object { $_.Name -match 'Start Menu' }) {
        $progDir = Join-Path $loc.Path 'Programs'
        if (Test-Path $progDir) {
            Get-ChildItem $progDir -Directory -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
                $fileCount = (Get-ChildItem $_.FullName -File -Recurse -ErrorAction SilentlyContinue | Measure-Object).Count
                if ($fileCount -eq 0) {
                    $emptyFolders += [PSCustomObject]@{ Location=$loc.Name; Path=$_.FullName }
                }
            }
        }
    }

    $deadCount = ($shortcutResults | Where-Object { $_.Status -match 'DEAD|PROMO|UNKNOWN|ERROR' }).Count
    $promoCount = ($shortcutResults | Where-Object { $_.Status -eq '[PROMO]' }).Count
    $advCount = ($shortcutResults | Where-Object { $_.Status -eq '[ADVERTISED]' }).Count

    if ($shortcutResults.Count -eq 0 -and $emptyFolders.Count -eq 0) {
        Write-Host "  All shortcuts are valid." -ForegroundColor Green
    } else {
        if ($shortcutResults.Count -gt 0) {
            $shortcutResults | Sort-Object Location, Status |
                Format-Table -Property Status, Location, Name, Detail -AutoSize -Wrap
        }
        if ($emptyFolders.Count -gt 0) {
            Write-Host "  Empty Start Menu folders ($($emptyFolders.Count)):" -ForegroundColor Yellow
            $emptyFolders | ForEach-Object { Write-Host "    - $($_.Path)" -ForegroundColor DarkGray }
        }
        Write-Host ""
        if ($promoCount -gt 0) {
            Write-Host "  [PROMO] shortcuts ($promoCount) are likely bundleware drops — safe to delete." -ForegroundColor Yellow
        }
        if ($advCount -gt 0) {
            Write-Host "  [ADVERTISED] shortcuts ($advCount) are MSI advertised — do NOT delete without verification." -ForegroundColor Cyan
        }
    }

    if ($Output -eq 'Json') {
        $jsonResult['Shortcuts'] = @{
            Issues = $shortcutResults
            EmptyFolders = $emptyFolders
            DeadCount = $deadCount
            PromoCount = $promoCount
            AdvertisedCount = $advCount
        }
    }
}

# ── Cleanable Space ──
if ($runAll -or $runQuick -or $Section -contains 'CleanableSpace') {
    Write-Section 'Cleanable Space Estimate'

    $cleanable = @()

    # User TEMP
    $userTemp = $env:TEMP
    if (Test-Path $userTemp) {
        $sz = (Get-ChildItem $userTemp -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
        $cleanable += [PSCustomObject]@{ Area='User Temp (%TEMP%)'; SizeMB=[math]::Round($sz/1MB,1) }
    }

    # Windows Temp
    $winTemp = "$env:SystemRoot\Temp"
    if (Test-Path $winTemp) {
        $sz = (Get-ChildItem $winTemp -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
        $cleanable += [PSCustomObject]@{ Area='Windows Temp'; SizeMB=[math]::Round($sz/1MB,1) }
    }

    # Windows Update Cache (SoftwareDistribution\Download)
    $wuCache = "$env:SystemRoot\SoftwareDistribution\Download"
    if (Test-Path $wuCache) {
        $sz = (Get-ChildItem $wuCache -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
        $cleanable += [PSCustomObject]@{ Area='Windows Update Cache'; SizeMB=[math]::Round($sz/1MB,1) }
    }

    # Delivery Optimization
    $doCache = "$env:SystemRoot\ServiceProfiles\NetworkService\AppData\Local\Microsoft\Windows\DeliveryOptimization\Cache"
    if (Test-Path $doCache) {
        $sz = (Get-ChildItem $doCache -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
        $cleanable += [PSCustomObject]@{ Area='Delivery Optimization'; SizeMB=[math]::Round($sz/1MB,1) }
    }

    # Recycle Bin item count (size requires Shell COM, just count items)
    $recycleBin = (New-Object -ComObject Shell.Application).Namespace(0xA)
    $rbCount = 0
    if ($recycleBin) { $rbCount = $recycleBin.Items().Count }
    $cleanable += [PSCustomObject]@{ Area="Recycle Bin ($rbCount items)"; SizeMB=$null }

    $totalMB = ($cleanable | Where-Object { $_.SizeMB } | Measure-Object -Property SizeMB -Sum).Sum
    $cleanable += [PSCustomObject]@{ Area='--- Total estimated reclaimable ---'; SizeMB=$totalMB }

    $cleanable | Format-Table -Property Area, @{N='Size'; E={
        if ($null -eq $_.SizeMB) { 'N/A' }
        elseif ($_.SizeMB -ge 1024) { "$([math]::Round($_.SizeMB/1024,1)) GB" }
        else { "$($_.SizeMB) MB" }
    }} -AutoSize

    if ($totalMB -ge 1024) {
        Write-Host "  ~$([math]::Round($totalMB/1024,1)) GB reclaimable via Disk Cleanup (cleanmgr) or Storage Sense." -ForegroundColor Yellow
    }

    if ($Output -eq 'Json') {
        $jsonResult['CleanableSpace'] = @{
            Items = $cleanable | Where-Object { $_.Area -notmatch '^---' }
            TotalMB = $totalMB
            RecycleBinItems = $rbCount
        }
    }
}

# ── Summary ──
if ($runAll -or $runQuick) {
    Write-Section 'Summary'
    $summaryIssues = @()

    # Count non-svchost auto services
    $nonSvchostAuto = @(Get-CimInstance Win32_Service -Filter "StartMode='Auto'" | Where-Object { $_.PathName -notmatch 'svchost\.exe' })
    if ($nonSvchostAuto.Count -gt 15) {
        $summaryIssues += "[WARN] $($nonSvchostAuto.Count) non-svchost auto-start services (many may be unnecessary)"
    }

    # Count non-MS active tasks
    $nmTasks = @(Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { $_.State -ne 'Disabled' -and $_.TaskPath -notmatch '^\\Microsoft\\' })
    if ($nmTasks.Count -gt 5) {
        $summaryIssues += "[INFO] $($nmTasks.Count) active non-Microsoft scheduled tasks"
    }

    # Disk space
    $cDrive = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'"
    if ($cDrive) {
        $freeGB = [math]::Round($cDrive.FreeSpace / 1GB, 1)
        $usedPct = [math]::Round(($cDrive.Size - $cDrive.FreeSpace) / $cDrive.Size * 100, 1)
        if ($freeGB -lt 20) {
            $summaryIssues += "[WARN] C: drive only $freeGB GB free ($usedPct% used)"
        }
    }

    # Dead/promo shortcuts
    if ($jsonResult.ContainsKey('Shortcuts') -and $jsonResult['Shortcuts'].DeadCount -gt 0) {
        $sc = $jsonResult['Shortcuts']
        $summaryIssues += "[WARN] $($sc.DeadCount) dead/invalid shortcut(s) found (PROMO: $($sc.PromoCount), ADVERTISED: $($sc.AdvertisedCount))"
    }

    # Cleanable space
    if ($jsonResult.ContainsKey('CleanableSpace') -and $jsonResult['CleanableSpace'].TotalMB -ge 1024) {
        $summaryIssues += "[INFO] ~$([math]::Round($jsonResult['CleanableSpace'].TotalMB / 1024, 1)) GB reclaimable temp/cache space"
    }

    if ($summaryIssues.Count -eq 0) {
        Write-Host "  No major issues detected." -ForegroundColor Green
    } else {
        foreach ($issue in $summaryIssues) {
            $color = if ($issue.StartsWith('[WARN]')) { 'Yellow' } else { 'Cyan' }
            Write-Host "  $issue" -ForegroundColor $color
        }
    }

    if ($Output -eq 'Json') {
        $jsonResult['Summary'] = $summaryIssues
    }
}

Write-Host "`nDiagnostics complete." -ForegroundColor Green

# ── Json output ──
if ($Output -eq 'Json' -and $jsonResult.Count -gt 0) {
    Write-Host "`n─── JSON OUTPUT ───" -ForegroundColor Cyan
    $jsonResult | ConvertTo-Json -Depth 5
}

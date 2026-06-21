#Requires -Version 5.1
<#
.SYNOPSIS
    win-sweep shortcut management — scan, clean, and repair shortcuts across Desktop, Start Menu, and Taskbar.
.DESCRIPTION
    Standalone shortcut management independent of software uninstall workflow.
    Handles four scenarios:
    - Scan: Report all invalid, promotional, and advertised shortcuts
    - Clean: Delete invalid/promotional shortcuts (with confirmation)
    - Repair: Fix broken shortcuts for installed software (8.3 short path fallback for CJK targets)
    - CleanEmptyFolders: Remove empty Start Menu program folders

    Shortcut classification:
    - [DEAD]       — TargetPath points to a non-existent file, no matching installed software
    - [PROMO]      — TargetPath invalid AND name matches known promotional keywords
    - [ADVERTISED] — Empty TargetPath but file is large (MSI advertised shortcut); may still be valid
    - [UNKNOWN]    — TargetPath invalid, does not match promo keywords or installed software
    - [ERROR]      — WScript.Shell COM failed to read the shortcut (see sc-gotchas.md #17 for CJK issues)
.PARAMETER Action
    Operation mode: Scan, Clean, Repair, or CleanEmptyFolders.
.PARAMETER Scope
    Which locations to scan. Default: All.
    UserDesktop, PublicDesktop, UserStartMenu, AllUsersStartMenu, Taskbar, All.
.PARAMETER Force
    For Clean action: skip per-item confirmation for [PROMO] and [DEAD] shortcuts.
    [UNKNOWN] shortcuts always require confirmation.
.PARAMETER Output
    Output format: 'Text' (default) or 'Json' (structured).
.NOTES
    See sc-gotchas.md #17 for WScript.Shell CJK character limitations.
    See sc-gotchas.md #18 for PSReadLine long-script paste crash.
#>

[CmdletBinding(SupportsShouldProcess)]
param(
    [ValidateSet('Scan', 'Clean', 'Repair', 'CleanEmptyFolders')]
    [string]$Action = 'Scan',

    [ValidateSet('UserDesktop', 'PublicDesktop', 'UserStartMenu', 'AllUsersStartMenu', 'Taskbar', 'All')]
    [string[]]$Scope = 'All',

    [switch]$Force,

    [ValidateSet('Text', 'Json')]
    [string]$Output = 'Text'
)

# ── Known promotional keywords (Chinese bundleware common patterns) ──
$promoKeywords = @(
    '安装向导', '修复工具', '优化大师', '清理大师', '清理工具',
    '压缩', '壁纸', '浏览器', '加速', '驱动', '体检', '游戏盒子', '维修',
    '免费领取', '红包', '练习', 'Setup', 'Install',
    '一键安装', '极速版', '特惠', '福利'
)

# ── Build scope location map ──
$allLocations = @(
    @{ Name='UserDesktop';        ScopeKey='UserDesktop';        Path=[Environment]::GetFolderPath('Desktop');                     Recurse=$false }
    @{ Name='PublicDesktop';      ScopeKey='PublicDesktop';      Path=[Environment]::GetFolderPath('CommonDesktopDirectory');      Recurse=$false }
    @{ Name='UserStartMenu';     ScopeKey='UserStartMenu';     Path=[Environment]::GetFolderPath('StartMenu');                   Recurse=$true }
    @{ Name='AllUsersStartMenu'; ScopeKey='AllUsersStartMenu'; Path=[Environment]::GetFolderPath('CommonStartMenu');             Recurse=$true }
    @{ Name='Taskbar';           ScopeKey='Taskbar';           Path="$env:APPDATA\Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar"; Recurse=$false }
)

$locations = if ($Scope -contains 'All') {
    $allLocations
} else {
    $allLocations | Where-Object { $Scope -contains $_.ScopeKey }
}

# ── Collect installed software names for cross-reference ──
$installedNames = @()
$regPaths = @(
    'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*'
    'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*'
    'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*'
)
$regPaths | ForEach-Object { Get-ItemProperty $_ -ErrorAction SilentlyContinue } |
    Where-Object { $_.DisplayName -and $_.DisplayName.Trim() } |
    ForEach-Object { $installedNames += $_.DisplayName.Trim() }

# ── Utility: resolve 8.3 short path for CJK workaround ──
function Resolve-ShortPath($LongPath) {
    if (-not (Test-Path $LongPath -ErrorAction SilentlyContinue)) { return $null }
    try {
        $fso = New-Object -ComObject Scripting.FileSystemObject
        return $fso.GetFile($LongPath).ShortPath
    } catch {
        return $null
    }
}

# ── Core scan function ──
function Invoke-ShortcutScan {
    $wshShell = New-Object -ComObject WScript.Shell
    $results = @()

    foreach ($loc in $locations) {
        if (-not (Test-Path $loc.Path)) { continue }

        $lnks = if ($loc.Recurse) {
            Get-ChildItem $loc.Path -Filter '*.lnk' -Recurse -ErrorAction SilentlyContinue
        } else {
            Get-ChildItem $loc.Path -Filter '*.lnk' -ErrorAction SilentlyContinue
        }

        foreach ($lnk in $lnks) {
            $status = 'OK'
            $tag = ''
            $targetPath = ''

            try {
                $shortcut = $wshShell.CreateShortcut($lnk.FullName)
                $targetPath = $shortcut.TargetPath

                if (-not $targetPath -or $targetPath.Trim() -eq '') {
                    # Empty TargetPath: advertised shortcut or truly dead
                    if ($lnk.Length -gt 500) {
                        $matchesInstalled = $installedNames | Where-Object {
                            $lnk.BaseName -like "*$_*" -or $_ -like "*$($lnk.BaseName)*"
                        } | Select-Object -First 1
                        if ($matchesInstalled) {
                            $status = 'ADVERTISED'
                            $tag = "MSI advertised (matches: $matchesInstalled)"
                        } else {
                            $status = 'UNKNOWN'
                            $tag = 'Empty TargetPath, large file — possible advertised shortcut'
                        }
                    } else {
                        $status = 'DEAD'
                        $tag = 'Empty TargetPath, small file'
                    }
                } elseif (-not (Test-Path $targetPath -ErrorAction SilentlyContinue)) {
                    # Target exists in shortcut but file is missing
                    $isPromo = $false
                    foreach ($kw in $promoKeywords) {
                        if ($lnk.BaseName -like "*$kw*") { $isPromo = $true; break }
                    }
                    $matchesInstalled = $installedNames | Where-Object {
                        $lnk.BaseName -like "*$_*" -or $_ -like "*$($lnk.BaseName)*"
                    } | Select-Object -First 1

                    if ($isPromo -and -not $matchesInstalled) {
                        $status = 'PROMO'
                        $tag = "Promotional — target missing: $targetPath"
                    } elseif ($matchesInstalled) {
                        $status = 'DEAD'
                        $tag = "Target missing (was: $matchesInstalled): $targetPath"
                    } else {
                        $status = 'UNKNOWN'
                        $tag = "Target missing, unknown origin: $targetPath"
                    }
                }
            } catch {
                $status = 'ERROR'
                $tag = "COM error: $($_.Exception.Message)"
            }

            if ($status -ne 'OK') {
                $results += [PSCustomObject]@{
                    Location   = $loc.Name
                    Status     = "[$status]"
                    Name       = $lnk.BaseName
                    FullPath   = $lnk.FullName
                    TargetPath = $targetPath
                    Detail     = $tag
                    FileSize   = $lnk.Length
                    Created    = $lnk.CreationTime
                }
            }
        }
    }

    return $results
}

# ── Main actions ──
switch ($Action) {
    'Scan' {
        Write-Host "`n── Scanning shortcuts ──" -ForegroundColor Cyan
        $results = Invoke-ShortcutScan

        if ($results.Count -eq 0) {
            Write-Host "  All shortcuts are valid." -ForegroundColor Green
        } else {
            $grouped = $results | Group-Object Status
            foreach ($g in $grouped) {
                Write-Host "`n  $($g.Name) ($($g.Count)):" -ForegroundColor Yellow
                $g.Group | Format-Table -Property Location, Name, Detail, @{N='Created';E={$_.Created.ToString('yyyy-MM-dd')}} -AutoSize -Wrap
            }

            # Summary
            $deadCount = ($results | Where-Object { $_.Status -match 'DEAD|PROMO' }).Count
            $unknownCount = ($results | Where-Object { $_.Status -eq '[UNKNOWN]' }).Count
            $advCount = ($results | Where-Object { $_.Status -eq '[ADVERTISED]' }).Count
            $errCount = ($results | Where-Object { $_.Status -eq '[ERROR]' }).Count
            Write-Host "`n  Summary: $($results.Count) issue(s) — DEAD/PROMO: $deadCount, UNKNOWN: $unknownCount, ADVERTISED: $advCount, ERROR: $errCount" -ForegroundColor Cyan
            if ($deadCount -gt 0) {
                Write-Host "  Run with -Action Clean to remove [DEAD] and [PROMO] shortcuts." -ForegroundColor Yellow
            }
        }

        if ($Output -eq 'Json') {
            $results | ConvertTo-Json -Depth 5
        }
    }

    'Clean' {
        Write-Host "`n── Cleaning invalid shortcuts ──" -ForegroundColor Cyan
        $results = Invoke-ShortcutScan

        if ($results.Count -eq 0) {
            Write-Host "  Nothing to clean." -ForegroundColor Green
            return
        }

        # Auto-deletable: DEAD and PROMO
        $autoDelete = $results | Where-Object { $_.Status -match 'DEAD|PROMO' }
        # Manual confirmation: UNKNOWN
        $manualDelete = $results | Where-Object { $_.Status -eq '[UNKNOWN]' }
        # Skip: ADVERTISED and ERROR (too risky)
        $skipped = $results | Where-Object { $_.Status -match 'ADVERTISED|ERROR' }

        $deleted = 0
        $failed = 0

        if ($autoDelete.Count -gt 0) {
            Write-Host "`n  Auto-deletable shortcuts ($($autoDelete.Count)):" -ForegroundColor Yellow
            $autoDelete | Format-Table -Property Status, Location, Name, Detail -AutoSize -Wrap

            if (-not $Force) {
                Write-Host "  Delete these $($autoDelete.Count) shortcuts? (Y/N) " -ForegroundColor Yellow -NoNewline
                $confirm = Read-Host
                if ($confirm -notmatch '^[Yy]') {
                    Write-Host "  Skipped." -ForegroundColor DarkGray
                    $autoDelete = @()
                }
            }

            foreach ($item in $autoDelete) {
                try {
                    Remove-Item -Path $item.FullPath -Force -ErrorAction Stop
                    Write-Host "  [OK] Deleted: $($item.Name) ($($item.Location))" -ForegroundColor Green
                    $deleted++
                } catch {
                    Write-Host "  [FAIL] $($item.Name): $($_.Exception.Message)" -ForegroundColor Red
                    $failed++
                }
            }
        }

        if ($manualDelete.Count -gt 0) {
            Write-Host "`n  Unknown-origin shortcuts ($($manualDelete.Count)) — require individual confirmation:" -ForegroundColor Yellow
            foreach ($item in $manualDelete) {
                Write-Host "    $($item.Status) $($item.Location) / $($item.Name)" -ForegroundColor White
                Write-Host "    Detail: $($item.Detail)" -ForegroundColor DarkGray
                Write-Host "    Delete? (Y/N) " -ForegroundColor Yellow -NoNewline
                $confirm = Read-Host
                if ($confirm -match '^[Yy]') {
                    try {
                        Remove-Item -Path $item.FullPath -Force -ErrorAction Stop
                        Write-Host "    [OK] Deleted." -ForegroundColor Green
                        $deleted++
                    } catch {
                        Write-Host "    [FAIL] $($_.Exception.Message)" -ForegroundColor Red
                        $failed++
                    }
                } else {
                    Write-Host "    Skipped." -ForegroundColor DarkGray
                }
            }
        }

        if ($skipped.Count -gt 0) {
            Write-Host "`n  Skipped (ADVERTISED/ERROR — too risky for auto-delete): $($skipped.Count)" -ForegroundColor DarkGray
            $skipped | ForEach-Object { Write-Host "    $($_.Status) $($_.Location) / $($_.Name)" -ForegroundColor DarkGray }
        }

        Write-Host "`n  Result: $deleted deleted, $failed failed, $($skipped.Count) skipped" -ForegroundColor Cyan
    }

    'Repair' {
        Write-Host "`n── Repairing broken shortcuts for installed software ──" -ForegroundColor Cyan
        $results = Invoke-ShortcutScan

        # Only repair shortcuts for software that IS installed but has a broken path
        $repairable = @()
        foreach ($r in $results) {
            if ($r.Status -match 'DEAD|UNKNOWN' -and $r.TargetPath) {
                # Try to find the correct executable from installed software
                $baseName = [System.IO.Path]::GetFileNameWithoutExtension($r.TargetPath)
                $matchedSoftware = $installedNames | Where-Object {
                    $r.Name -like "*$_*" -or $_ -like "*$($r.Name)*"
                } | Select-Object -First 1

                if ($matchedSoftware) {
                    $repairable += [PSCustomObject]@{
                        Shortcut       = $r
                        MatchedSoftware = $matchedSoftware
                    }
                }
            }
        }

        if ($repairable.Count -eq 0) {
            Write-Host "  No repairable shortcuts found (no broken shortcuts matching installed software)." -ForegroundColor Green
            return
        }

        Write-Host "  Found $($repairable.Count) potentially repairable shortcut(s):" -ForegroundColor Yellow
        $repairable | ForEach-Object {
            Write-Host "    - $($_.Shortcut.Name) → matched software: $($_.MatchedSoftware)" -ForegroundColor White
            Write-Host "      Original target: $($_.Shortcut.TargetPath)" -ForegroundColor DarkGray
        }
        Write-Host "`n  [NOTE] Automatic repair requires knowing the correct target path." -ForegroundColor Cyan
        Write-Host "  For CJK target paths, the 8.3 short name workaround will be used (see sc-gotchas #17)." -ForegroundColor Cyan
        Write-Host "  Manual intervention may be needed — the AI should locate the correct .exe and create a new shortcut." -ForegroundColor Yellow
    }

    'CleanEmptyFolders' {
        Write-Host "`n── Cleaning empty Start Menu folders ──" -ForegroundColor Cyan

        $startMenuLocations = $locations | Where-Object { $_.Name -match 'StartMenu' }
        if ($startMenuLocations.Count -eq 0) {
            $startMenuLocations = $allLocations | Where-Object { $_.Name -match 'StartMenu' }
        }

        $emptyFolders = @()
        foreach ($loc in $startMenuLocations) {
            $progDir = Join-Path $loc.Path 'Programs'
            if (-not (Test-Path $progDir)) { continue }
            Get-ChildItem $progDir -Directory -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
                $fileCount = (Get-ChildItem $_.FullName -File -Recurse -ErrorAction SilentlyContinue | Measure-Object).Count
                if ($fileCount -eq 0) {
                    $emptyFolders += [PSCustomObject]@{
                        Location = $loc.Name
                        Path     = $_.FullName
                        Name     = $_.Name
                    }
                }
            }
        }

        if ($emptyFolders.Count -eq 0) {
            Write-Host "  No empty Start Menu folders found." -ForegroundColor Green
            return
        }

        Write-Host "  Found $($emptyFolders.Count) empty folder(s):" -ForegroundColor Yellow
        $emptyFolders | Format-Table -Property Location, Name, Path -AutoSize -Wrap

        if (-not $Force) {
            Write-Host "  Delete all empty folders? (Y/N) " -ForegroundColor Yellow -NoNewline
            $confirm = Read-Host
            if ($confirm -notmatch '^[Yy]') {
                Write-Host "  Skipped." -ForegroundColor DarkGray
                return
            }
        }

        $deleted = 0
        foreach ($f in $emptyFolders) {
            try {
                Remove-Item -Path $f.Path -Recurse -Force -ErrorAction Stop
                Write-Host "  [OK] Deleted: $($f.Path)" -ForegroundColor Green
                $deleted++
            } catch {
                Write-Host "  [FAIL] $($f.Path): $($_.Exception.Message)" -ForegroundColor Red
            }
        }
        Write-Host "`n  Cleaned $deleted/$($emptyFolders.Count) empty folders." -ForegroundColor Cyan
    }
}

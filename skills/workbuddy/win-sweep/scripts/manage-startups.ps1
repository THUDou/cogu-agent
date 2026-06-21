#Requires -Version 5.1
<#
.SYNOPSIS
    win-sweep startup management — disable startup items with safe backup.
.DESCRIPTION
    Moves selected Run entries to the RunDisabled key for safe disabling.
    Supports restoring individual startup items. HKCU entries do not require admin privileges.
    Covers: Run, RunOnce, WOW6432Node Run, and Startup folder items.
.PARAMETER Action
    Operation mode: List (list items), Disable (disable items), Restore (restore items).
.PARAMETER Names
    Array of startup item names to disable/restore. Required when Action is Disable or Restore.
.PARAMETER Scope
    Registry scope: HKCU (default) or HKLM (requires admin privileges).
#>

[CmdletBinding(SupportsShouldProcess)]
param(
    [ValidateSet('List', 'Disable', 'Restore')]
    [string]$Action = 'List',

    [string[]]$Names,

    [ValidateSet('HKCU', 'HKLM')]
    [string]$Scope = 'HKCU'
)

# ── Admin check for HKLM scope ──
if ($Scope -eq 'HKLM') {
    $isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator
    )
    if (-not $isAdmin) {
        Write-Error "HKLM scope requires Administrator privileges. Restart as admin or use -Scope HKCU."
        exit 1
    }
}

$runPath      = "${Scope}:\Software\Microsoft\Windows\CurrentVersion\Run"
$disabledPath = "${Scope}:\Software\Microsoft\Windows\CurrentVersion\RunDisabled"
$runOncePath  = "${Scope}:\Software\Microsoft\Windows\CurrentVersion\RunOnce"
$wow64RunPath = if ($Scope -eq 'HKLM') { 'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run' } else { $null }

# Startup folder paths
$startupFolder = if ($Scope -eq 'HKCU') {
    [Environment]::GetFolderPath('Startup')
} else {
    [Environment]::GetFolderPath('CommonStartup')
}

# Exclude default registry properties
$excludeProps = '^PS(Path|ParentPath|ChildName|Provider|Drive)$'

function Get-RunEntries([string]$RegPath) {
    if (-not $RegPath -or -not (Test-Path $RegPath)) { return @() }
    $props = Get-ItemProperty $RegPath -ErrorAction SilentlyContinue
    if (-not $props) { return @() }
    $props.PSObject.Properties |
        Where-Object { $_.Name -notmatch $excludeProps } |
        ForEach-Object { [PSCustomObject]@{ Name = $_.Name; Command = $_.Value } }
}

function Get-StartupFolderEntries([string]$FolderPath) {
    if (-not $FolderPath -or -not (Test-Path $FolderPath)) { return @() }
    Get-ChildItem $FolderPath -Filter '*.lnk' -ErrorAction SilentlyContinue | ForEach-Object {
        [PSCustomObject]@{ Name = $_.BaseName; Command = $_.FullName }
    }
}

switch ($Action) {
    'List' {
        Write-Host "`n$Scope\Run (active startup items):" -ForegroundColor Cyan
        $active = Get-RunEntries $runPath
        if ($active.Count -gt 0) {
            $active | Format-Table -AutoSize -Wrap
        } else {
            Write-Host "  (empty)" -ForegroundColor DarkGray
        }

        Write-Host "`n$Scope\RunDisabled (disabled backups):" -ForegroundColor Cyan
        $disabled = Get-RunEntries $disabledPath
        if ($disabled.Count -gt 0) {
            $disabled | Format-Table -AutoSize -Wrap
        } else {
            Write-Host "  (empty)" -ForegroundColor DarkGray
        }

        # RunOnce entries
        Write-Host "`n$Scope\RunOnce:" -ForegroundColor Cyan
        $runOnce = Get-RunEntries $runOncePath
        if ($runOnce.Count -gt 0) {
            $runOnce | Format-Table -AutoSize -Wrap
        } else {
            Write-Host "  (empty)" -ForegroundColor DarkGray
        }

        # WOW6432Node (HKLM only)
        if ($wow64RunPath) {
            Write-Host "`nHKLM\WOW6432Node\Run (32-bit startup items):" -ForegroundColor Cyan
            $wow64 = Get-RunEntries $wow64RunPath
            if ($wow64.Count -gt 0) {
                $wow64 | Format-Table -AutoSize -Wrap
            } else {
                Write-Host "  (empty)" -ForegroundColor DarkGray
            }
        }

        # Startup folder
        Write-Host "`nStartup Folder ($Scope): $startupFolder" -ForegroundColor Cyan
        $folderItems = Get-StartupFolderEntries $startupFolder
        if ($folderItems.Count -gt 0) {
            $folderItems | Format-Table -AutoSize -Wrap
        } else {
            Write-Host "  (empty)" -ForegroundColor DarkGray
        }
    }

    'Disable' {
        if (-not $Names -or $Names.Count -eq 0) {
            Write-Error "Disable action requires the -Names parameter."
            exit 1
        }

        # Ensure the RunDisabled key exists
        if (-not (Test-Path $disabledPath)) {
            New-Item -Path $disabledPath -Force | Out-Null
        }

        foreach ($name in $Names) {
            # Check if startup item exists
            $value = $null
            try {
                $value = (Get-ItemProperty $runPath -Name $name -ErrorAction Stop).$name
            } catch {
                Write-Host "  [SKIP] '$name' — not found in $Scope\Run" -ForegroundColor DarkYellow
                continue
            }

            # Move to RunDisabled
            Write-Host "  [MOVE] '$name' → RunDisabled" -ForegroundColor White -NoNewline
            try {
                Set-ItemProperty -Path $disabledPath -Name $name -Value $value
                Remove-ItemProperty -Path $runPath -Name $name
                Write-Host " ✓" -ForegroundColor Green
                Write-Host "    Command: $value" -ForegroundColor DarkGray
            } catch {
                Write-Host " ✗" -ForegroundColor Red
                Write-Host "    $($_.Exception.Message)" -ForegroundColor Red
            }
        }

        Write-Host "`nRestore command: .\manage-startups.ps1 -Action Restore -Names 'ItemName' -Scope $Scope" -ForegroundColor Cyan
    }

    'Restore' {
        if (-not $Names -or $Names.Count -eq 0) {
            Write-Error "Restore action requires the -Names parameter."
            exit 1
        }

        foreach ($name in $Names) {
            $value = $null
            try {
                $value = (Get-ItemProperty $disabledPath -Name $name -ErrorAction Stop).$name
            } catch {
                Write-Host "  [SKIP] '$name' — not found in RunDisabled" -ForegroundColor DarkYellow
                continue
            }

            Write-Host "  [RESTORE] '$name' → Run" -ForegroundColor White -NoNewline
            try {
                Set-ItemProperty -Path $runPath -Name $name -Value $value
                Remove-ItemProperty -Path $disabledPath -Name $name
                Write-Host " ✓" -ForegroundColor Green
            } catch {
                Write-Host " ✗" -ForegroundColor Red
                Write-Host "    $($_.Exception.Message)" -ForegroundColor Red
            }
        }
    }
}

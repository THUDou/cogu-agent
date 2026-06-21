# Telemetry Identification & Removal

This document provides an **identification framework** for the AI to discover and completely disable telemetry/data collection components in Windows.
The core challenge: telemetry vendors register multiple persistence mechanisms that re-enable each other — disabling only one layer is ineffective.

---

## Three-Layer Sweep Rule (Iron Rule)

Telemetry must be disabled at **all three layers** simultaneously, or it will resurrect itself.

| Layer | Scan Command | Disable Command | Consequence of Missing |
|-------|-------------|----------------|----------------------|
| Services | `Get-CimInstance Win32_Service \| Where-Object { $_.Name -match '<pattern>' }` | `sc.exe config "<name>" start= disabled` | Scheduled tasks or startup items will re-enable the service |
| Scheduled Tasks | `Get-ScheduledTask \| Where-Object { $_.TaskName -match '<pattern>' }` | `Disable-ScheduledTask -TaskName "<name>"` | Task fires on login/schedule, running the process directly and bypassing the service |
| Startup Items | `Get-ItemProperty HKCU:\Software\Microsoft\Windows\CurrentVersion\Run` | Move to `RunDisabled` key (see manage-startups.ps1) | Process launches on user login |

### Sweep Workflow

For each suspected telemetry vendor:

1. **Service layer** — Search service names and executable paths by vendor keywords
2. **Task layer** — Search scheduled task names by vendor keywords and executable filenames
3. **Startup layer** — Search `Run` / `RunOnce` keys for the same executables
4. **Cross-verify** — After disabling, reboot and check if the process is still running (`Get-Process`)

---

## Identifying Unknown Telemetry Components

Known vendors are just the tip of the iceberg. The AI should be able to identify **any** telemetry component, not just match the list below.

### Telemetry Trait Keywords

The following patterns in service names, descriptions, executable paths, or scheduled task names strongly suggest telemetry:

| Category | Keyword Pattern (regex) | Description |
|----------|------------------------|-------------|
| Direct identifiers | `telemetry\|CEIP\|SQM\|DiagTrack` | Explicit telemetry / Customer Experience Improvement Program |
| Data reporting | `usage.?report\|crash.?report\|error.?report\|feedback` | Usage data / crash report upload |
| Data collection | `collect\|harvest\|beacon\|analytics\|metrics\|heartbeat` | Generic collection terminology |
| Vendor-specific | `QUEENCREEK\|esrv\|SUR\|PimIndexMaint\|OfficeTelemetry` | Known vendor-specific identifiers |

### Behavioral Traits

| Trait | Description |
|-------|-------------|
| Service set to Auto but has no user-visible functionality | Pure background data upload |
| Scheduled task trigger is "at logon" or "daily" | Periodic data collection |
| Executable name contains `report`, `send`, `upload` | Reporting functionality |
| Network connection targets `*.data.microsoft.com`, `telemetry.*`, `*.events.data.*` | Known telemetry endpoints |
| Process with the same name still running after disabling the service | Being launched by a scheduled task or startup item — classic three-layer persistence |

---

## Known Telemetry Vendors

Common cases below for quick matching during scan results. `S` = Service, `T` = Scheduled Task, `R` = Startup/Registry item.

### Intel

| Type | Name | Description |
|------|------|-------------|
| S | `ESRV_SVC_QUEENCREEK` | Intel software usage reporting |
| S | `SystemUsageReportSvc_QUEENCREEK` | System usage data collection |
| T | `USER_ESRV_SVC_QUEENCREEK` | Launches esrv.exe on user login |
| T | `IntelSURQC-Upgrade-*` | Upgrade check |
| T | `IntelSURQC-Upgrade-*-Logon` | Upgrade check on login |

**Gotcha**: Disabling only the service is ineffective. The `USER_ESRV_SVC_QUEENCREEK` task directly runs `esrv.exe` on user login (~138 MB memory), completely bypassing the service. This is why the three-layer sweep rule exists.

### Microsoft

| Type | Name | Description |
|------|------|-------------|
| S | `DiagTrack` | Connected User Experiences and Telemetry — primary telemetry service |
| S | `dmwappushservice` | WAP Push message routing, data channel for DiagTrack |
| T | `\Microsoft\Windows\Application Experience\Microsoft Compatibility Appraiser` | Compatibility assessment (periodic scan of installed software) |
| T | `\Microsoft\Windows\Application Experience\ProgramDataUpdater` | Program data updater |
| T | `\Microsoft\Windows\Autochk\Proxy` | Collects and uploads SQM data |
| T | `\Microsoft\Windows\Customer Experience Improvement Program\Consolidator` | CEIP data consolidation and upload |
| T | `\Microsoft\Windows\Customer Experience Improvement Program\UsbCeip` | USB device CEIP |
| T | `\Microsoft\Windows\DiskDiagnostic\Microsoft-Windows-DiskDiagnosticDataCollector` | Disk diagnostic data collection |

**Notes**:
- `DiagTrack` may be re-enabled after major Windows updates — re-check after updates
- Group Policy `Computer Configuration > Administrative Templates > Windows Components > Data Collection` can control this at the policy level, more persistent than disabling individually

### SQL Server

| Type | Name | Description |
|------|------|-------------|
| S | `SQLTELEMETRY` | Default instance telemetry |
| S | `SQLTELEMETRY$<instance>` | Named instance telemetry (`$` needs escaping in PowerShell) |

### NVIDIA

| Type | Name | Description |
|------|------|-------------|
| S | `NvTelemetryContainer` | NVIDIA telemetry container (removed in newer drivers, still present in older versions) |
| T | `NvTmMon_*` | Telemetry monitoring task |
| T | `NvTmRep_*` | Telemetry reporting task |

**Note**: In newer GeForce Experience / NVIDIA App versions, NVIDIA merged telemetry into `NVDisplay.ContainerLocalSystem` and no longer registers `NvTelemetryContainer` separately. For complete disabling, use the NVIDIA App settings.

### OEM Vendors (Lenovo / Dell / HP)

OEM preinstalled software universally includes telemetry components with inconsistent naming. Search by these patterns:

| Vendor | Service/Task Keyword Pattern | Common Components |
|--------|------------------------------|-------------------|
| Lenovo | `Lenovo.*metric\|Lenovo.*telemetry\|ImController` | Lenovo Vantage telemetry, System Update data collection |
| Dell | `Dell.*telemetry\|DellDataVault\|SupportAssist` | Dell SupportAssist diagnostic data upload |
| HP | `HP.*telemetry\|HPDiag\|HpTouchpoint` | HP Touchpoint Analytics (known privacy controversy) |

**Principle**: OEM telemetry components can generally be safely disabled. Core functionality (driver updates, warranty queries) does not depend on telemetry.

### Adobe

| Type | Name | Description |
|------|------|-------------|
| S | `AdobeARMservice` | Update checker (also has telemetry; see Pattern 6 in service-rules.md) |
| T | `Adobe Acrobat Update Task` | Periodic update check |
| T | `AdobeGCInvoker-*` | Adobe Genuine Copy verification (includes reporting) |

---

## Disable Operation Templates

### Complete Disable Flow for a Single Vendor

```powershell
# === Intel telemetry example ===

# 1. Disable services
sc.exe config "ESRV_SVC_QUEENCREEK" start= disabled
sc.exe config "SystemUsageReportSvc_QUEENCREEK" start= disabled

# 2. Stop running services
sc.exe stop "ESRV_SVC_QUEENCREEK"
sc.exe stop "SystemUsageReportSvc_QUEENCREEK"

# 3. Disable scheduled tasks
Get-ScheduledTask | Where-Object { $_.TaskName -match 'ESRV|IntelSURQC' } |
    Disable-ScheduledTask

# 4. Check startup items (Run key)
Get-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" |
    ForEach-Object { $_.PSObject.Properties } |
    Where-Object { $_.Value -match 'esrv|IntelSUR' }
# If matches found, move to RunDisabled
```

### Batch Discovery of Telemetry Components

```powershell
# Scan all three layers at once using keyword patterns
$pattern = 'telemetry|CEIP|SQM|DiagTrack|esrv|QUEENCREEK|UsageReport|NvTelemetry'

Write-Host "`n=== Services ===" -ForegroundColor Cyan
Get-CimInstance Win32_Service |
    Where-Object { $_.Name -match $pattern -or $_.DisplayName -match $pattern } |
    Select-Object Name, DisplayName, StartMode, State |
    Format-Table -AutoSize

Write-Host "`n=== Scheduled Tasks ===" -ForegroundColor Cyan
Get-ScheduledTask |
    Where-Object { $_.TaskName -match $pattern -or $_.TaskPath -match $pattern } |
    Select-Object TaskName, TaskPath, State |
    Format-Table -AutoSize

Write-Host "`n=== Startup Items (HKCU Run) ===" -ForegroundColor Cyan
$runKey = Get-ItemProperty "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -ErrorAction SilentlyContinue
if ($runKey) {
    $runKey.PSObject.Properties |
        Where-Object { $_.Name -notmatch '^PS' -and $_.Value -match $pattern } |
        Select-Object Name, Value
}
```

---

## Verification

Disabling without verification is not considered complete.

```powershell
# 1. After reboot, check if the process is still running
Get-Process | Where-Object { $_.ProcessName -match 'esrv|DiagTrack|telemetry' }
# Expected: no matching results

# 2. Check service status
Get-CimInstance Win32_Service -Filter "Name='ESRV_SVC_QUEENCREEK'" |
    Select-Object Name, StartMode, State
# Expected: StartMode = Disabled, State = Stopped

# 3. Check scheduled task status
Get-ScheduledTask -TaskName "*ESRV*" | Select-Object TaskName, State
# Expected: State = Disabled
```

### Windows Update Re-Enablement Issue

Some Microsoft telemetry components (especially `DiagTrack`) get re-enabled after major Windows updates. Recommendations:
- Re-run the scan scripts to verify after updates
- If possible, set the telemetry level to `Security` (lowest) via Group Policy (`gpedit.msc`) — more persistent than disabling individual services

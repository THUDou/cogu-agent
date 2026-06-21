---
name: win-sweep
description: "Windows system cleanup and optimization toolkit. Use when: Windows cleanup, 系统清理, 电脑太慢, 开机慢, 开机加速, C盘满了, 清理磁盘, 释放空间, 关掉没用的后台程序, 关闭开机自启, 卸载残留清理, 删掉偷偷上传数据的东西, 检查可疑进程, 清理没用的定时任务, 卸载软件, 彻底删除软件, 强力卸载, 清除残留, 卸载流氓软件, 删除360, 卸载鲁大师, 清理2345, 国产流氓软件, 主页被劫持, 浏览器主页锁定, 卸载McAfee, 卸载Norton, 删除屏保软件, 清理壁纸软件, 删除CCleaner, 假优化软件, 假驱动更新, scareware, uninstall software, force uninstall, remove bloatware, clean uninstall leftovers, remove Chinese bloatware, remove scareware, remove screensaver, disable services, disable startup items, reduce boot time, free disk space, uninstall leftovers, telemetry removal, suspicious service detection, scheduled task cleanup"
license: MIT
---

# win-sweep — Windows System Cleanup & Optimization

A skill for diagnosing and cleaning up Windows system bloat: redundant services, startup items, scheduled tasks, disk space hogs, and suspicious processes.

## When to Use

- System is slow or boot time is too long
- Low disk space (C: or D: drive)
- Too many startup items or background services
- Need to audit/disable telemetry components
- Found suspicious or leftover services
- Third-party software registered excessive auto-start services
- Leftover artifacts after software uninstallation

## Workflow

### Phase 1: Diagnosis (Safe — No Confirmation Needed)

Run the diagnostic script to assess system state. Diagnostic operations are read-only and never modify the system.

1. [System Overview](./scripts/diagnose.ps1) — Disk usage, installed software, startup items, services, scheduled tasks, memory usage ranking
   - **Quick mode** (default): Skips slow C:\ directory size scan; suitable for a fast first-pass assessment. Includes telemetry quick scan, multi-layer association detection, and summary.
   - **Deep mode** (`-Section Deep`): Full recursive directory scan for disk space analysis. Non-standard C:\ root directories are flagged as `[SUSPECT]`.
   - **JSON output** (`-Output Json`): Structured output for programmatic consumption by downstream scripts. Includes `Summary` and `Telemetry` sections.
   - **Telemetry section**: Built-in quick scan matching telemetry keyword patterns across services and scheduled tasks. See [telemetry.md](./references/telemetry.md) for full three-layer sweep.
   - **Multi-layer associations**: Detects products with presence across multiple layers (e.g., Edge update service + Edge update scheduled tasks) and warns about incomplete optimization.
   - **Shortcut scan**: Scans Desktop, Start Menu, and Taskbar for dead, promotional, and advertised shortcuts. Classifies as `[DEAD]`, `[PROMO]`, `[ADVERTISED]`, or `[UNKNOWN]`. See [sc-gotchas.md](./references/sc-gotchas.md) item 17 for CJK shortcut pitfalls.
   - **Cleanable space**: Estimates reclaimable space from User Temp, Windows Temp, Windows Update cache, Delivery Optimization cache, and Recycle Bin.
2. Review output and identify optimization targets
3. [Shortcut Scan](./scripts/clean-shortcuts.ps1) — Dead desktop/Start Menu/taskbar shortcuts, promotional bundleware links, empty program folders (can run independently of software uninstall)

### Phase 2: Optimization (Dangerous — Confirmation Required)

Execute targeted fixes based on diagnostic results. **All modification operations must follow the safety mechanisms below.**

1. [Service Optimization](./scripts/optimize-services.ps1) — Batch-modify service startup modes (Auto → Manual/Disabled)
2. [Startup Management](./scripts/manage-startups.ps1) — Disable startup items with backup to `RunDisabled` registry key
   - Covers: `HKCU\..\Run`, `HKLM\..\Run`, `WOW6432Node\Run`, `RunOnce`, and Startup folder `.lnk` files
   - Automatically checks admin privileges when HKLM scope is requested
3. [Scheduled Task Cleanup](./scripts/clean-tasks.ps1) — Disable unnecessary scheduled tasks
   - **DeleteOrphaned** action (`-Action DeleteOrphaned`): Finds and removes tasks belonging to already-uninstalled software; exports task XML to backup before deletion
4. [Suspicious Service Detection](./scripts/detect-suspicious.ps1) — Find leftover/unsigned/suspicious services **and kernel drivers**
5. [Shortcut Cleanup](./scripts/clean-shortcuts.ps1) — Independent shortcut management (not tied to software uninstall)
   - `-Action Scan`: Report all dead, promotional, and advertised shortcuts across Desktop, Start Menu, Taskbar
   - `-Action Clean`: Delete [DEAD] and [PROMO] shortcuts with confirmation; [UNKNOWN] requires per-item confirmation; [ADVERTISED] skipped
   - `-Action Repair`: Identify broken shortcuts for installed software; uses 8.3 short path fallback for CJK targets
   - `-Action CleanEmptyFolders`: Remove empty Start Menu program folders
   - Scans both `Win32_Service` and `Win32_SystemDriver` (controlled by `-IncludeDrivers` flag, on by default)
   - Detects services with empty `PathName` (S1:EmptyImagePath) and suspicious file creation timestamps (S10)
5. **Software Removal** (three-step workflow — see details below):
   - a. [List & Recommend](./scripts/uninstall-software.ps1) (`-Action List`) — Generate a "recommended uninstall list" from diagnostic results
   - b. **User manually uninstalls** via Settings > Apps or Control Panel — **the AI cannot reliably uninstall software from the terminal** (see "Terminal Uninstall Limitations" below)
   - c. [Leftover Cleanup](./scripts/uninstall-software.ps1) (`-Action Cleanup`) — After user confirms manual uninstall is done, scan 10 areas for residuals and clean them up (services, kernel drivers, scheduled tasks, startup items including WOW6432Node/RunOnce, directories, AppData, temp files, **desktop shortcuts**, **taskbar pins**, **Start Menu shortcuts**, and **C:\ root anomalous directories**)
   - d. [Cleanup Plan](./scripts/uninstall-software.ps1) (`-Action CleanupPlan`) — Same scan as Cleanup, but outputs a structured JSON plan to stdout for review or programmatic use. Uses fuzzy keyword matching for better detection of name variants (e.g., `LuDaShi` matches `LudashiProtect` driver).
   - e. [Cleanup Execute](./scripts/uninstall-software.ps1) (`-Action CleanupExecute -Plan '<json>'`) — Takes a JSON plan (from CleanupPlan), executes each item with: registry/task XML backup before deletion, `PendingFileRenameOperations` for locked files/directories (scheduled for removal on next reboot), per-item `[OK]/[FAIL]/[LOCKED]/[PENDING]` status reporting

#### Terminal Uninstall Limitations

**The terminal is NOT reliable for uninstalling software, especially rogue/bloatware.** The AI must understand these limitations:

1. **GUI-only uninstallers** — Most Chinese rogue software (360, 鲁大师, 2345, etc.) and many Western bloatware products have GUI-only uninstallers with no silent/quiet mode. Running them from terminal opens a GUI wizard that blocks the terminal indefinitely.
2. **Guardian processes** — Rogue software uses guardian processes that respawn each other. `taskkill` alone cannot kill them all in time — they revive before you finish.
3. **Kernel driver locks** — Software like 360 (`ZhuDongFangYu`), anti-cheat engines, and some AV products use kernel drivers that lock files and registry keys. Even Administrator privileges cannot bypass these locks while the driver is loaded.
4. **Process file locks** — Running processes hold file locks; you cannot delete directories while the software is active.
5. **Skipped cleanup steps** — Force-deleting files bypasses the uninstaller's driver removal, COM de-registration, file association cleanup, and other hooks — leaving *more* residuals than a proper uninstall.
6. **Uninstaller hangs** — Some uninstallers hang indefinitely waiting for user input, a background service, or a reboot prompt — freezing the terminal.

**Correct workflow when the user asks to "uninstall" or "remove" software:**

```
AI: I've identified these programs for removal:
    | # | Software        | Size  | Why Remove            |
    | 1 | 鲁大师          | 230MB | Rogue software (360 ecosystem) |
    | 2 | Adobe Flash     | 15MB  | Discontinued / EOL    |
    | ...

    ⚠️ Important: For reliable removal, please uninstall these
    programs yourself through:
      • Settings > Apps > Installed apps (Windows 11)
      • Control Panel > Programs and Features (Windows 10)

    For rogue software (鲁大师, 360, etc.), you may need to:
      • Right-click the tray icon and exit the program first
      • If the uninstaller is blocked, reboot into Safe Mode

    💡 Tip: If an uninstall GUI window pops up during the process,
    just follow its prompts and click "Uninstall" / "确认卸载".
    Some uninstallers may also try to persuade you to keep the
    software — ignore those and proceed with removal.

    After you've finished uninstalling, tell me and I'll:
      • Scan for leftover services, scheduled tasks, startup items,
        directories, registry entries, and temp files
      • Clean up invalid shortcuts on your Desktop
      • Remove dead pinned items from the Taskbar
      • Remove dead Start Menu entries and empty program folders
      • Clean them up with your confirmation
```

**The only case where terminal uninstall is acceptable:**
- Simple MSI packages (`msiexec /x {GUID} /quiet`) or winget-supported software (`winget uninstall --name "..." --silent`)
- The AI must set a **timeout** (default 120 seconds) on any `Start-Process -Wait` call to prevent indefinite hangs
- If the process does not exit within the timeout, the AI must kill it and inform the user to uninstall manually

**Force-delete is the absolute last resort**, only when:
- The user has already tried manual uninstall and it failed
- Preferably executed in Safe Mode
- The AI must warn that force-delete may leave more residuals than a proper uninstall

### Phase 3: Verification (Safe — No Confirmation Needed)

1. [Verification Script](./scripts/verify.ps1) — Confirm that changes have taken effect correctly
   - **Absence checks** (`-CheckAbsent '<json>'`): Verify that removed services, tasks, registry keys, or file paths are truly gone (detects `DELETE_PENDING` state for services)
   - **Reboot state** (`-CheckPendingReboot`): Check `PendingFileRenameOperations` for files scheduled for reboot-deletion, service `DeleteFlag` state, and Windows Update reboot-required flag
2. After reboot, re-run diagnostics to compare before/after

---

## Safety Mechanisms (Iron Rules)

### I. Operation Risk Levels

Different operations carry different risk levels and confirmation requirements.

| Level | Operation Type | Example | Reversibility | Confirmation |
|-------|---------------|---------|---------------|-------------|
| **Read-only** | Diagnosis, scan, query | `Get-CimInstance`, `Get-ScheduledTask` | — | None needed |
| **Low-risk** | Auto → Manual | Set service to on-demand startup | Reversible: change back to Auto | Summary table confirmation |
| **Medium-risk** | Auto → Disabled, disable scheduled tasks | Completely prevent startup | Reversible: change back to Auto/Enable | Summary table + impact notes |
| **High-risk** | Delete service, delete registry keys | `sc.exe delete`, remove startup items | **Backup required** for reversal | Per-item confirmation + backup proof |

### II. Confirmation Flow

#### Batch Operations (Low/Medium Risk): Summary Table Confirmation

When performing multiple same-level operations, present a summary table for one-time confirmation instead of asking one by one:

```
I recommend the following adjustments for N services:

| # | Service | Current State | Suggested Action | Purpose | Risk |
|---|---------|--------------|-----------------|---------|------|
| 1 | ServiceA | Auto/Running | → Manual | XX license service | Low |
| 2 | ServiceB | Auto/Stopped | → Disabled | XX telemetry | Low |
| ...

Notes:
- Manual services start automatically when the corresponding software is opened — no impact on daily use
- Can be reverted to Auto at any time

Proceed? You can also say "skip #2" to exclude specific items.
```

User can:
- Confirm all ("confirm", "go ahead", "yes")
- Exclude some ("skip #2 and #5")
- Reject all ("no", "cancel")

#### High-Risk Operations: Per-Item Confirmation + Backup

Delete operations must:
1. **Execute backup first** and inform the user of the backup location
2. **Report per item**: what it is, why deletion is recommended, consequences, rollback method
3. **Wait for user confirmation on each individual item**

```
⚠️ High-risk operation: Delete service "SuspiciousService"

- What: Leftover service whose executable C:\ProgramData\xxx.exe no longer exists
- Investigation: Risk score 7/12 (file not found +3, garbled service name +4)
- Backed up: Registry exported to %TEMP%\svc-backup-SuspiciousService.reg
- Rollback: reg import "%TEMP%\svc-backup-SuspiciousService.reg" + reboot
- Command: sc.exe delete "SuspiciousService"

Proceed?
```

### III. System Restore Point

**Before the first modification operation**, suggest that the user create a system restore point:

```
About to modify system configuration. Recommend creating a system restore point first, so you can roll back entirely if issues arise.

Command: Checkpoint-Computer -Description "win-sweep pre-optimization" -RestorePointType MODIFY_SETTINGS

Create now? (You can skip if you already have a recent restore point.)
```

**Before running the command, check service availability:**

```powershell
# Check if System Restore is available
$srService = Get-Service -Name 'srservice' -ErrorAction SilentlyContinue
$vssService = Get-Service -Name 'VSS' -ErrorAction SilentlyContinue
$srEnabled = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\SystemRestore' -Name RPSessionInterval -ErrorAction SilentlyContinue).RPSessionInterval -ne 0

if (-not $srService -or $srService.StartType -eq 'Disabled') {
    # System Restore service is disabled (common on LTSC/Server editions)
    Write-Host "System Restore service (srservice) is disabled."
}
if (-not $srEnabled) {
    Write-Host "System Restore is turned off for this drive."
}
```

**If System Restore is unavailable** (common on LTSC editions), inform the user with a clear explanation:

```
⚠️ System Restore is not available on this system (LTSC editions disable it by default).

Alternatives:
- Back up important files manually before proceeding
- The script will create per-item backups (registry exports, service CSV, task XML)
  in %TEMP%\win-sweep-backup\ — these can be used for targeted rollback

Proceed without system restore point?
```

If the user declines, note it but do not block subsequent operations — this is a recommendation, not a requirement.

### IV. Change Log

After each modification operation, record in terminal output:
- Timestamp
- Operation details (original value → new value)
- Command executed

This enables post-hoc auditing and troubleshooting.

---

## Core Principles

- **Prefer Manual over Disabled** — `start= demand` lets Windows start the service on demand; `start= disabled` completely prevents startup. Use Manual unless the service is telemetry or a discontinued product
- **Back up before modifying** — Move startup items to `RunDisabled` instead of deleting; `reg export` before deleting services
- **Three-layer telemetry sweep** — Must check services + scheduled tasks + startup items simultaneously; disabling only one layer is ineffective (see [telemetry.md](./references/telemetry.md)). The diagnose script now includes a built-in telemetry quick scan and multi-layer association detection to ensure this is not forgotten.
- **Multi-layer consistency** — When optimizing a product (e.g., disabling `edgeupdate` service), always check and handle the corresponding scheduled tasks and startup items for the same product. The diagnose script flags multi-layer associations to help enforce this.
- **UTF-8 with BOM for all scripts** — All `.ps1` files must be saved with UTF-8 BOM (`EF BB BF`). PowerShell 5.1 on non-English Windows defaults to the system locale encoding, breaking scripts with non-ASCII characters. See [sc-gotchas.md](./references/sc-gotchas.md) item 15.
- **Long scripts must be written to file** — Operations exceeding ~20 lines must be written to a `.ps1` file and executed with `powershell -File`, never pasted directly into the terminal. PSReadLine in VS Code's integrated terminal crashes on long pastes (see [sc-gotchas.md](./references/sc-gotchas.md) item 18).
- **Advertised shortcuts are not dead shortcuts** — When scanning `.lnk` files, empty `TargetPath` does not mean the shortcut is invalid. MSI advertised shortcuts store targets differently. Cross-reference against installed software before marking as dead. See [sc-gotchas.md](./references/sc-gotchas.md) item 17c.
- **Check what the service actually does** — Many games and third-party apps silently install always-on services (anti-cheat engines, game platform launchers, companion apps). During diagnosis, identify each service's actual purpose and whether it genuinely needs to run at boot. If the user only plays a game occasionally, its background service doesn't need to be Auto (see Pattern 9 & 10 in [service-rules.md](./references/service-rules.md))
- **Decision framework over hardcoded lists** — Reference docs provide universal identification patterns, not hardcoded service name lists. Apply the framework to unknown services rather than only matching known lists
- **Administrator privileges required** — Both diagnosis and modification benefit significantly from an elevated PowerShell session. **Without admin, diagnosis is incomplete**: service details (binary path, startup account, failure actions), HKLM startup items, scheduled task internals, and signature checks may fail or return partial data. The AI must detect the privilege level at the start of every session and, if not elevated, **proactively warn the user with a clear summary of what will be missing**:

  ```
  ⚠️ Current session does NOT have Administrator privileges.

  Impact on diagnosis:
  - Service binary paths and startup accounts: may be incomplete
  - HKLM startup items: cannot read
  - Scheduled task details: limited
  - Signature verification for some executables: may fail
  - Memory usage for system processes: hidden

  Impact on modifications:
  - Service optimization: will fail
  - HKLM startup items: cannot modify
  - Scheduled task cleanup: will fail
  - Software uninstall (system-level): will fail
  - Suspicious service deletion: will fail

  I can still run a partial diagnostic scan, but the results will be incomplete
  and I may miss important issues.

  Recommend: Restart [your tool] as Administrator for full access.
  [How to elevate: right-click the app icon → Run as administrator]
  ```

  Detection:
  ```powershell
  $isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
  ```
  If `$isAdmin` is `$false`, **always** display the warning above before proceeding. Do not silently continue. The user must make an informed decision about whether to proceed with limited results or restart with admin rights. See the "Administrator Privileges" section in the README.

## Reference Documents

Load relevant documents **proactively at the right workflow phase**, not just when encountering errors.

| Workflow Phase | Preload These Documents | Trigger |
|---|---|---|
| Phase 1 diagnosis | *(none required — scripts are self-contained)* | — |
| Phase 2 service optimization | [service-rules.md](./references/service-rules.md) | Before presenting optimization plan |
| Phase 2 suspicious service found | [suspicious-checklist.md](./references/suspicious-checklist.md) | When diagnose flags unknown services |
| Phase 2 software uninstall | [uninstall-guide.md](./references/uninstall-guide.md) | Before presenting removal list |
| Phase 2 telemetry found | [telemetry.md](./references/telemetry.md) | When diagnose or telemetry scan finds components |
| Script generation / debugging | [sc-gotchas.md](./references/sc-gotchas.md) | Before writing any PowerShell code for services |

Full document descriptions:

- [Service Optimization Rules](./references/service-rules.md) — Decision framework: whether any service can be safely modified + universal pattern matching + protected service handling
- [Telemetry Identification & Removal](./references/telemetry.md) — Identification framework for telemetry components (keyword patterns + behavioral traits) + known vendor cases + three-layer disable templates
- [Suspicious Service Checklist](./references/suspicious-checklist.md) — Quantified risk scoring system (12 signals) + investigation workflow + decision matrix + false positive exclusion
- [PowerShell & sc.exe Gotchas](./references/sc-gotchas.md) — Common AI-generated PowerShell errors (`&&`, comparison operators, array unwrapping, multi-line terminal paste issues, **UTF-8 BOM encoding**, **sc.exe Access Denied on protected services**, etc.) + sc.exe-specific pitfalls + self-check list
- [Software Uninstall Guide](./references/uninstall-guide.md) — Decision framework for software removal + removal strategies (winget/MSI/native) + 9-area leftover cleanup checklist + bloatware patterns + edge cases (kernel drivers, UWP, anti-uninstall software)

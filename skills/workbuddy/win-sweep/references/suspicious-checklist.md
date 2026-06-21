# Suspicious Service Investigation Checklist

This document provides the AI with a **systematic investigation framework** for identifying and handling unknown, leftover, or potentially malicious Windows services.

---

## Risk Signals & Scoring

Each signal carries a weight. Sum all matched signal scores for a given service to derive an overall risk score.

| # | Signal | Score | Description |
|---|--------|-------|-------------|
| S1 | Executable path does not exist | +3 | Software uninstalled but service registration remains |
| S2 | Executable is unsigned | +3 | No digital signature — origin cannot be verified |
| S3 | Signature is invalid or expired | +4 | More suspicious than unsigned — possible tampering |
| S4 | Runs as `LocalSystem` | +2 | Highest privilege; legitimate services also use this — combine with other signals |
| S5 | Failure action set to auto-restart | +1 | Persistence mechanism; legitimate services also use this — not high-risk alone |
| S6 | Path in `ProgramData`, `Temp`, `AppData`, or `Downloads` | +3 | User-writable directories — legitimate services are rarely installed here |
| S7 | Service name is random characters / garbled / non-ASCII | +4 | Typical malware/adware naming |
| S8 | Service description is empty | +1 | Legitimate software usually fills in a description |
| S9 | `ImagePath` contains suspicious arguments (e.g., `-encode`, `-hidden`, `bypass`) | +5 | Strongly suggests malicious behavior |
| S10 | Executable creation time does not match system install date and is not a recent known install | +2 | Possible dropped file |
| S11 | No `Description` and `DisplayName` values in registry | +2 | Extremely minimal registration — legitimate software does not do this |
| S12 | DLL service (`svchost.exe -k`) points to a non-existent DLL | +4 | Leftover or DLL hijacking |

### Risk Levels

| Cumulative Score | Level | Recommended Action |
|-----------------|-------|-------------------|
| 1-3 | Low | Log and hold — may be legitimate software with atypical configuration |
| 4-6 | Medium | Investigate further (run the investigation workflow below), then decide |
| 7+ | High | Strongly recommend stopping and removing; if file exists, back up for forensics first |

---

## Investigation Workflow

For each service flagged as suspicious, execute the following steps in order.

### Step 1: Gather Basic Information

Collect key service attributes in one call:

```powershell
Get-CimInstance Win32_Service -Filter "Name='ServiceName'" |
    Select-Object Name, DisplayName, Description, PathName, StartName,
                  StartMode, State, ProcessId
```

### Step 2: Executable File Check

Extract the actual path from `PathName` (strip arguments and quotes), then:

```powershell
# Extract path (handle ImagePath with arguments)
$imagePath = (Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Services\ServiceName").ImagePath
# Manually inspect the actual executable path within $imagePath

# Check if file exists
Test-Path "C:\actual\path\to\executable.exe"

# File details
Get-Item "C:\actual\path\to\executable.exe" | Select-Object FullName, CreationTime, LastWriteTime, Length
```

**If the file does not exist** → Add S1 score, skip to decision matrix.

### Step 3: Signature Verification

```powershell
Get-AuthenticodeSignature "C:\actual\path\to\executable.exe"
```

| Status | Meaning |
|--------|---------|
| `Valid` | Signature valid — record the publisher (Subject), continue checking |
| `NotSigned` | Unsigned — add S2 score |
| `HashMismatch` | File was modified — add S3 score, high alert |
| `NotTrusted` / `UnknownError` | Certificate chain anomaly — add S3 score |

### Step 4: Run Account & Persistence

```powershell
# Run account
Get-CimInstance Win32_Service -Filter "Name='ServiceName'" | Select-Object StartName

# Failure restart policy
sc.exe qfailure "ServiceName"
```

Interpreting `sc.exe qfailure` output:
- `RESTART -- Delay = xxx`: Auto-restart configured → add S5 score
- `RUN PROCESS`: Runs another program on failure → investigate that program path
- `(empty)` or all `-- Delay = 0`: No special configuration

### Step 5: Dependencies

```powershell
# What this service depends on
sc.exe qc "ServiceName"       # DEPENDENCIES field

# What depends on this service
sc.exe enumdepend "ServiceName"
```

If other services depend on it → assess impact before deleting.

### Step 6: Network Activity (Optional, for High-Risk)

If the service is running and has a high risk score:

```powershell
# Check network connections for this process
$pid = (Get-CimInstance Win32_Service -Filter "Name='ServiceName'").ProcessId
Get-NetTCPConnection -OwningProcess $pid -ErrorAction SilentlyContinue |
    Select-Object LocalPort, RemoteAddress, RemotePort, State
```

Outbound connections detected → record remote addresses, escalate risk level.

---

## Decision Matrix

Based on investigation results, refer to this matrix for the appropriate action:

| File Exists | Signature | Run Account | Risk Score | Action |
|-------------|-----------|-------------|------------|--------|
| No | — | Any | 3+ | **Delete** service registration (leftover, non-functional) |
| Yes | Valid + known publisher | LocalService / NetworkService | 1-3 | **Legitimate** — no action, or optimize per service-rules |
| Yes | Valid + known publisher | LocalSystem | 1-3 | **Likely legitimate** — Microsoft/major vendor drivers commonly use LocalSystem; verify publisher and allow |
| Yes | Valid + unknown publisher | Any | 4-6 | **Investigate** — search for the publisher name, confirm if it's known software |
| Yes | NotSigned | LocalService | 4-6 | **Suspicious** — some small legitimate software is unsigned; confirm origin |
| Yes | NotSigned | LocalSystem | 7+ | **High risk** — stop service, back up files for forensics, recommend deletion |
| Yes | HashMismatch / NotTrusted | Any | 7+ | **High risk** — file may be tampered; stop immediately, back up for forensics |

---

## Common False Positives

The following scenarios trigger risk signals but are usually legitimate — prioritize these exclusions during investigation:

| Scenario | Triggered Signals | How to Confirm False Positive |
|----------|------------------|------------------------------|
| Microsoft built-in service running as LocalSystem | S4 | Path is in `System32`, signature valid with publisher `Microsoft` |
| Driver service (Type = Kernel Driver) | S8 (no description) | `sc.exe qc` shows TYPE as `KERNEL_DRIVER`, path in `drivers\` |
| Developer tool local service (Node.js, Python) | S2 (unsigned), S6 (AppData) | Path matches a known installed development tool directory |
| .NET / Java service wrapper | S2 (main exe signed but wrapper unsigned) | `PathName` points to `dotnet.exe` or `java.exe` + application DLL/JAR |
| Windows built-in but default-disabled service | S8 (no description) | Service name is in the known Windows service list |

---

## Handling Operations

### Safety Steps Before Deletion

```powershell
# 1. Back up service registry key (can be used for recovery)
reg export "HKLM\SYSTEM\CurrentControlSet\Services\ServiceName" "$env:TEMP\svc-backup-ServiceName.reg"

# 2. If the file exists and forensic analysis is needed, copy to a safe location
# Copy-Item "C:\path\to\suspicious.exe" "$env:TEMP\quarantine\"

# 3. Stop the service (may error if file doesn't exist — can be ignored)
sc.exe stop "ServiceName"

# 4. Check for dependents (think twice if there are any)
sc.exe enumdepend "ServiceName"

# 5. Delete the service registration
sc.exe delete "ServiceName"
```

### Verify Deletion Result

```powershell
# Confirm the registry key is gone
Test-Path "HKLM:\SYSTEM\CurrentControlSet\Services\ServiceName"
# Expected output: False

# If it returns True, the service may be marked as "delete pending" — takes effect after reboot
```

### Rollback

If deleted by mistake, restore using the previously exported `.reg` file:

```powershell
reg import "$env:TEMP\svc-backup-ServiceName.reg"
# Reboot required after restore for changes to take effect
```

---

## Quick Reference Commands

| Purpose | Command |
|---------|---------|
| List all non-Microsoft services | `Get-CimInstance Win32_Service \| Where-Object { $_.PathName -and $_.PathName -notmatch 'windows\\system32' }` |
| List all third-party services running as LocalSystem | `Get-CimInstance Win32_Service \| Where-Object { $_.StartName -eq 'LocalSystem' -and $_.PathName -notmatch 'system32' }` |
| List services whose executable does not exist | Requires iteration + `Test-Path` (see detect-suspicious.ps1) |
| Batch check signatures | `Get-CimInstance Win32_Service \| ForEach-Object { ... Get-AuthenticodeSignature }` |

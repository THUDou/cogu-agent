# Service Optimization Rules

This document provides a **decision framework** for the AI to evaluate whether any Windows service can be safely modified.
It does not rely on hardcoded whitelists — the AI should make independent judgments for each service found during diagnostic scans based on the rules below.

---

## Core Principles

1. **Prefer Manual over Disabled** — `start= demand` lets Windows start the service on demand; `start= disabled` completely prevents startup and may cause dependent software to fail. Only use Disabled when you are certain nothing depends on it.
2. **The key question is "does this service need to run constantly?"** — Many services are set to Auto just because the vendor took the easy route; they work fine starting on demand.
3. **Telemetry services can be Disabled directly** — Pure data collection with no functional impact. But scheduled tasks and startup items must be checked as well (see [telemetry.md](./telemetry.md)).
4. **Leftover services from uninstalled/discontinued software can be deleted** — A service whose executable no longer exists has no value.

---

## Decision Framework: Evaluating Any Service

When encountering an Auto-start service, evaluate in this order:

```
1. Does it belong to the "Do Not Modify" categories?
   → Yes: Skip — do not touch
   → No: Continue

2. Does the executable file exist?
   → No: Recommend deletion (sc.exe delete)
   → Yes: Continue

3. Is it a telemetry/data collection service?
   → Yes: Recommend Disabled + check scheduled tasks
   → No: Continue

4. Is it for a discontinued product (e.g., Flash)?
   → Yes: Recommend Disabled or deletion
   → No: Continue

5. What is the service's actual purpose? Does the user actively need it?
   → Game anti-cheat / game platform / game companion service the user only uses occasionally: Recommend Manual
   → Third-party app background service (cloud sync, helper, tray agent) not needed at all times: Recommend Manual
   → User cannot identify the service's purpose: Investigate further (check executable path, publisher, description) before deciding
   → Continue

6. Is it for on-demand software (not needed constantly)?
   → Yes: Recommend Manual
   → No: Keep Auto
```

---

## Do Not Modify (Hard Rules)

The following **categories** of services must never be changed. Identify by functional role, not by exhaustive name matching.

### Absolutely Forbidden
| Category | Representative Services | Reason |
|----------|------------------------|--------|
| RPC / COM Infrastructure | `RpcSs`, `RpcEptMapper`, `DcomLaunch` | Foundation for virtually all inter-process communication; stopping these causes immediate system failure |
| Windows Update | `wuauserv`, `UsoSvc` | Security update channel |
| Security | `WinDefend`, `WdNisSvc`, `SecurityHealthService` | Defender antivirus |
| Event Log | `EventLog` | Foundation for auditing and troubleshooting |
| Network Core | `Dhcp`, `Dnscache`, `NlaSvc`, `nsi` | Stopping these causes network disconnection |
| User Login | `LSM`, `Winlogon` (not a service but related), `SamSs`, `Netlogon` (domain) | Cannot log in |
| Storage | `StorSvc`, `VDS` | Disk management |
| Cryptography | `CryptSvc`, `KeyIso` | Certificates, HTTPS, driver signature verification |
| Power Management | `Power` | Laptop lid close / hibernation |
| Component Servicing | `TrustedInstaller`, `msiserver` | Software installation and Windows Update depend on these |

### Guiding Principles
- Service description contains "critical" or "must be running" → Exercise extreme caution
- Core services in the `svchost.exe -k netsvcs` group → Verify individually before modifying
- When in doubt, keep Auto — better to have one extra running service than risk system failure

---

## Safe to Change to Manual (Auto → Manual)

These are **universal patterns** applicable to any system. The AI should match diagnostic results against these patterns.

### Pattern 1: Software License/Activation Services
**Traits**: Service name or description contains `license`, `flexnet`, `sentinel`, `hasp`, `activation`
**Rationale**: Only needed when the corresponding software is open; software will auto-start a Manual service
**Examples**: FlexNet Licensing Service, hasplms, AdskLicensingService, SolidWorks Flexnet Server

### Pattern 2: Database Engines
**Traits**: Service name contains `SQL`, `MySQL`, `PostgreSQL`, `Mongo`, `Firebird`, `Oracle`
**Rationale**: Databases in dev/engineering environments don't need to run constantly; start when opening the client tool
**Examples**: MSSQLSERVER, MSSQL$InstanceName, SQLBrowser, SQLWriter, FirebirdGuardianDefaultInstance, MySQL80
**Note**: `$` in PowerShell needs escaping (`` `$ `` or wrap the service name in single quotes)

### Pattern 3: Print Services
**Traits**: Service name contains `Print`, `Spooler`, or vendor prefixes (`HP`, `Canon`, `Epson`, `Brother`)
**Rationale**: Not needed when not printing; `Spooler` has historical vulnerabilities (PrintNightmare) — safe to disable if rarely used
**Examples**: Spooler, HPAppHelperCap, Canon IJ Network

### Pattern 4: Peripheral Sync/Management
**Traits**: Service belongs to non-resident peripherals (phone sync, Bluetooth accessory management, tablets, etc.)
**Examples**: Apple Mobile Device Service, Bonjour Service, WTabletServicePro (Wacom)

### Pattern 5: Virtualization Platforms
**Traits**: Service name contains `vmms`, `Hyper-V`, `WSL`, `Docker`, `Container`, `VBox`
**Rationale**: Not needed when VMs/containers are not in use
**Examples**: vmms, WSLService, CmService, com.docker.service, VBoxSDS

### Pattern 6: Software Auto-Update Services
**Traits**: Service name or description contains `update`, `updater`, and is NOT Windows Update
**Rationale**: Third-party update services run constantly just to periodically check for updates; perfectly fine on-demand
**Examples**: gupdate/gupdatevm (Google), MicrosoftEdgeUpdate, AdobeARMservice, MozillaMaintenance, brave, opera
**Note**: Do NOT touch `wuauserv` (Windows Update) or `UsoSvc`

### Pattern 7: Vendor Background Services (Non-Core)
**Traits**: GPU driver auxiliary services, OEM preinstalled services, branded hardware management
**Examples**: NVDisplay.ContainerLocalSystem (NVIDIA Container), AMD Crash Defender, Intel(R) TPM Provisioning Service, LenovoVantageService, HPSupportAssistance
**Judgment**: Does not affect core hardware functionality (rendering/computation); only supplementary monitoring/optimization/promotion

### Pattern 8: Search/Index Services
**Traits**: Service name contains `Search`, `Index`, or third-party search tools
**Examples**: WSearch (Windows Search), Everything, Listary
**Judgment**: On SSD systems, setting WSearch to Manual has minimal impact; on HDD systems, keep Auto if search functionality is relied upon

### Pattern 9: Game Platform & Anti-Cheat Services
**Traits**: Service name or executable path relates to game platforms, game launchers, or anti-cheat engines. Common keywords: `EasyAntiCheat`, `BEService` (BattlEye), `vgc` (Vanguard), `FaceIt`, `Steam`, `Epic`, `Riot`, `Garena`, `GameBar`, `XboxGip`, `nProtect`, `GameGuard`
**Rationale**: Anti-cheat and game platform services are set to Auto by default but only need to run while the game is active. Some anti-cheat services (Vanguard, EasyAntiCheat) run kernel-level drivers at boot even when the game is not open — this is a significant resource and security surface cost for occasional gamers
**Examples**: EasyAntiCheat, BEService, vgc (Riot Vanguard), vgk (Vanguard kernel driver), Steam Client Service, EpicOnlineServices, nProtect GameGuard
**Judgment**: If the user plays the game regularly (daily), keep Auto. If played occasionally, set to Manual — the game launcher will start the service when needed. For kernel-level anti-cheat (vgc/vgk), inform the user that a reboot may be required after the service starts before the game can launch
**Note**: Some competitive games refuse to launch unless the anti-cheat service has been running since boot. Always inform the user of this trade-off when recommending Manual

### Pattern 10: Third-Party App Background / Companion Services
**Traits**: Services installed by user applications that run persistently in the background for convenience features (cloud sync agents, app helper processes, tray utilities, crash reporters). Common keywords: `Helper`, `Agent`, `Companion`, `Tray`, `Monitor`, `CrashReport`, `Sync`
**Rationale**: Many desktop apps (note-taking tools, messaging apps, download managers, creative suites) register always-on services for features like instant sync, quick launch, or background notifications. These are rarely essential at boot — the app will start the service when opened
**Examples**: Dropbox service, OneDrive helper services (beyond the core sync), Evernote Clipper, Discord update helper, Spotify Web Helper, CCleaner Monitoring, iCloud services, Razer Synapse service, Logitech G Hub, Nahimic service, Realtek audio companion services
**Judgment**: Evaluate whether the user relies on the background functionality (e.g., real-time cloud sync). If the user only uses the app interactively, recommend Manual. If the service is a crash reporter or usage monitor with no user-facing benefit, recommend Disabled
**Note**: Some companion services share names with their parent app — verify by checking the executable path and service description to distinguish core functionality from optional background helpers

---

## Safe to Disable (Disabled)

### Pattern A: Telemetry/Data Collection
**Traits**: Service name or description contains `telemetry`, `diagnostic`, `CEIP`, `usage report`, `SQM`
**Examples**: DiagTrack, SQLTELEMETRY*, ESRV_SVC_QUEENCREEK, SystemUsageReportSvc_QUEENCREEK
**Important**: Must also check scheduled tasks (see telemetry.md) — otherwise tasks will re-enable the process

### Pattern B: Discontinued/Obsolete Products
**Traits**: Belongs to an EOL product, or the vendor has stopped maintaining it
**Examples**: Flash Helper Service, FlashCenterSvc
**Rationale**: No security updates = exploit entry point

### Pattern C: Features Not Applicable to the Current System
**Traits**: The service provides functionality that is definitely not needed in the current environment
**Examples**:
| Service | Condition |
|---------|-----------|
| `MapsBroker` | Offline maps not used |
| `wisvc` | Not an Insider Preview user |
| `Fax` | Fax not used |
| `RemoteRegistry` | Remote registry access not needed (also a security risk) |
| `RetailDemo` | Not a retail demo machine |
| `WpcMonSvc` | No parental control requirement |

---

## Edge Cases and Notes

- **System-Protected Services**: Some services cannot be modified even with Administrator privileges — `sc.exe config` returns Access Denied (exit code 5). Known protected services include:
  - `SgrmBroker` (System Guard Runtime Monitor Broker) — protected by PPL (Protected Process Light)
  - `TrustedInstaller` — the Windows Modules Installer runs under its own protected account
  - Any service protected by Early Launch AM (antimalware) drivers

  When encountering these, the AI should report them as `[PROTECTED]` rather than `[FAIL]` and explain that modification requires advanced techniques (e.g., editing the registry offline in recovery mode) which are not recommended.

- **SysMain (Superfetch)**: Minimal benefit on SSD systems — can change to Manual; keep Auto on HDD systems
- **WSearch**: Same logic — depends on storage media and usage habits
- **TabletInputService**: Can change to Manual if touchscreen/stylus not used, but some touchpad gestures depend on it
- **Multiple vendor service dependencies**: HP, Lenovo, Dell and other OEMs often register 3-5 interdependent services — check dependencies before changing (`sc.exe enumdepend`)
- **Domain environment caution**: `Netlogon`, `LanmanWorkstation`, `LanmanServer` must not be modified in domain environments

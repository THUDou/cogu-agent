# PowerShell & sc.exe Common Gotchas

Common mistakes when AI generates PowerShell code and special pitfalls in Windows service management.
This document covers two categories: **PowerShell language gotchas** (common AI mistakes) and **sc.exe-specific gotchas**.

---

## PowerShell Language Gotchas (Common AI Mistakes)

### 1. `sc` is an Alias for `Set-Content`, Not sc.exe

AI frequently writes `sc config ...`, which PowerShell parses as `Set-Content`, causing cryptic errors.

```powershell
# Wrong — calls Set-Content, not sc.exe
sc config "ServiceName" start= demand

# Correct — always use the full name sc.exe
sc.exe config "ServiceName" start= demand
```

**Iron rule: In PowerShell, always write `sc.exe`, never `sc`.**

### 2. `&&` Is Not Supported (PowerShell 5.1)

AI is heavily trained on bash/shell and frequently uses `&&`. PowerShell 5.1 does not support it.

```powershell
# Wrong — syntax error in PowerShell 5.1
sc.exe stop "Svc" && sc.exe config "Svc" start= disabled

# Correct — use semicolons (unconditional execution)
sc.exe stop "Svc"; sc.exe config "Svc" start= disabled

# Correct — use if to check previous command success
sc.exe stop "Svc"
if ($LASTEXITCODE -eq 0) { sc.exe config "Svc" start= disabled }
```

> PowerShell 7.0+ supports `&&` and `||`, but this project targets 5.1.

### 3. Comparison Operators Are Not `==` `!=` `>` `<`

AI tends to generate C/Python/JS-style comparison operators, which PowerShell does not recognize.

```powershell
# Wrong — these are not comparison operators in PowerShell
if ($a == 0) { ... }        # Syntax error
if ($a != "hello") { ... }  # Syntax error
if ($a > 5) { ... }         # NOT comparison — redirects output to a file named "5"!

# Correct
if ($a -eq 0) { ... }
if ($a -ne "hello") { ... }
if ($a -gt 5) { ... }
```

| Meaning | Wrong | Correct |
|---------|-------|---------|
| Equal | `==` | `-eq` |
| Not equal | `!=` | `-ne` |
| Greater than | `>` | `-gt` |
| Less than | `<` | `-lt` |
| Greater or equal | `>=` | `-ge` |
| Less or equal | `<=` | `-le` |
| Contains | `in` | `-contains` or `-in` |
| Regex match | `~` | `-match` |

**Especially dangerous**: `$a > 5` does NOT produce an error — it silently redirects `$a`'s value into a file named `5`!

### 4. Function Calls Don't Use Parentheses or Commas

AI tends to write method-call style function invocations, which have completely different semantics in PowerShell.

```powershell
# Wrong — the comma creates a single array as the first argument, not two separate arguments
Set-Service -Name "Svc" -StartupType Manual
# The above is correct, but if AI writes:
MyFunction("arg1", "arg2")   # Wrong! Passes a single array with two elements

# Correct — function arguments are space-separated
MyFunction "arg1" "arg2"
MyFunction -Param1 "arg1" -Param2 "arg2"
```

### 5. Single Quotes vs Double Quotes

AI often uses single quotes when variable expansion is needed, or double quotes when it is not.

```powershell
# Single quotes — literal output, no variable expansion
$name = 'World'
'Hello $name'          # Output: Hello $name

# Double quotes — expands variables and escape characters
"Hello $name"          # Output: Hello World

# Service names containing $ must use single quotes (prevent variable expansion)
sc.exe config 'MSSQL$INSTANCE' start= demand    # Correct
sc.exe config "MSSQL$INSTANCE" start= demand     # Wrong — $INSTANCE treated as variable
sc.exe config "MSSQL`$INSTANCE" start= demand    # Correct — backtick escapes $
```

### 6. Single Object vs Array (Pipeline Unwrapping Gotcha)

PowerShell pipelines automatically unwrap arrays. When a command returns only one result, it returns the object, not an array.

```powershell
# Dangerous — if only one service matches, $services is NOT an array
$services = Get-CimInstance Win32_Service -Filter "StartMode='Auto'"
$services.Count   # May return unexpected value for single objects (object's own Count property or $null)

# Safe — force-wrap in array with @()
$services = @(Get-CimInstance Win32_Service -Filter "StartMode='Auto'")
$services.Count   # Always correct: 0 items = 0, 1 item = 1, N items = N
```

**Rule: Whenever you need `.Count` or index access on results, wrap with `@()`.**

### 7. `$LASTEXITCODE` vs `$?`

AI frequently conflates these two — they mean different things.

```powershell
# $? — Whether the PowerShell command succeeded (cmdlet terminating/non-terminating error)
# $LASTEXITCODE — Exit code of the last native program (.exe)

# Check if sc.exe succeeded
sc.exe config "Svc" start= demand
if ($LASTEXITCODE -ne 0) {
    Write-Error "sc.exe failed with exit code: $LASTEXITCODE"
}

# Note: $? is unreliable for native programs (almost always True in PS 5.1)
# Always use $LASTEXITCODE to check .exe execution results
```

### 8. `Get-WmiObject` Is Deprecated

AI training data heavily uses `Get-WmiObject`, which is removed in PowerShell 7.

```powershell
# Deprecated — PS7 will error
Get-WmiObject Win32_Service -Filter "Name='Svc'"

# Recommended — works in both versions
Get-CimInstance Win32_Service -Filter "Name='Svc'"
```

| Old cmdlet | Replacement |
|-----------|-------------|
| `Get-WmiObject` | `Get-CimInstance` |
| `Set-WmiInstance` | `Set-CimInstance` |
| `Invoke-WmiMethod` | `Invoke-CimMethod` |

### 9. Native Program stderr Triggers Terminating Error

When `$ErrorActionPreference = 'Stop'`, native program stderr output is treated as an error by PowerShell, triggering catch blocks.

```powershell
# Problem: sc.exe warning messages go to stderr, causing unexpected termination
$ErrorActionPreference = 'Stop'
$output = sc.exe qfailure "Svc" 2>&1   # May throw terminating error

# Safe approach: control ErrorAction independently
$output = sc.exe qfailure "Svc" 2>&1 | Out-String
# Or temporarily restore default behavior
$prevEA = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
$output = sc.exe qfailure "Svc" 2>&1 | Out-String
$ErrorActionPreference = $prevEA
```

### 10. Registry Paths: PowerShell vs reg.exe

Two completely different path syntaxes:

```powershell
# PowerShell cmdlets — require PSDrive prefix + colon
Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Services\Svc"
Test-Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"

# reg.exe — no colon or backslash prefix
reg query "HKLM\SYSTEM\CurrentControlSet\Services\Svc"
reg export "HKLM\SYSTEM\CurrentControlSet\Services\Svc" backup.reg

# Common AI mistake: mixing the two syntaxes
Test-Path "HKLM\SYSTEM\..."     # Wrong — missing colon, Test-Path treats as relative path
reg query "HKLM:\SYSTEM\..."    # Wrong — reg.exe doesn't recognize PSDrive syntax
```

### 11. `-match` Is Case-Insensitive by Default

```powershell
# These two are equivalent — AI sometimes adds unnecessary .ToLower()
"Hello" -match "hello"    # True (case-insensitive by default)
"Hello".ToLower() -match "hello"  # Redundant

# Use -cmatch when case sensitivity is needed
"Hello" -cmatch "hello"   # False
```

### 12. `Format-*` Output Cannot Be Further Piped

```powershell
# Wrong — Format-Table output is formatting objects, not raw data
Get-Service | Format-Table | Where-Object { $_.Status -eq 'Running' }  # Does not work

# Correct — filter first, format at the very end (Format-* always goes last in the pipeline)
Get-Service | Where-Object { $_.Status -eq 'Running' } | Format-Table
```

### 13. Embedding Object Properties in Strings

```powershell
$svc = Get-CimInstance Win32_Service -Filter "Name='wuauserv'"

# Wrong — only $svc is expanded, .Name is treated as literal text
"Service name: $svc.Name"          # Output: Service name: <entire object ToString()>.Name

# Correct — use subexpression
"Service name: $($svc.Name)"       # Output: Service name: wuauserv
```

---

## sc.exe-Specific Gotchas

### Equals Sign Must Be Followed by a Space

`sc.exe config` requires a space after the equals sign. This is sc.exe's own syntax requirement.

```powershell
# Correct
sc.exe config "ServiceName" start= demand

# Wrong — will silently fail or error
sc.exe config "ServiceName" start=demand
```

### Service Names Containing `$`

SQL Server named instances use the `MSSQL$InstanceName` format.

```powershell
# Correct — single quotes prevent variable expansion
sc.exe config 'MSSQL$TEW_SQLEXPRESS' start= demand

# Correct — backtick escapes $
sc.exe config "MSSQL`$TEW_SQLEXPRESS" start= demand

# Wrong — $TEW_SQLEXPRESS is treated as a variable (resolves to empty)
sc.exe config "MSSQL$TEW_SQLEXPRESS" start= demand
```

### sc.exe vs Set-Service Comparison

| Feature | sc.exe | Set-Service |
|---------|--------|-------------|
| Startup mode | `start= demand` | `-StartupType Manual` |
| Dollar sign | Requires quoting | Same issue |
| Delete service | `sc.exe delete` | Not supported |
| Query failure policy | `sc.exe qfailure` | Not supported |
| Remote machine | `sc.exe \\server` | `-ComputerName` |

Recommend using `sc.exe` for consistency — it supports service deletion and failure policy queries, with predictable behavior across PowerShell versions.

### Silent Failures

`sc.exe config` may appear to succeed but not actually take effect:
- **Misspelled service name** — Still outputs `[SC] ChangeServiceConfig SUCCESS`, but modified a non-existent target (created a new entry)
- **`$` was expanded** — `$` in the service name was parsed by PowerShell as an empty variable
- **Insufficient privileges** — Some services are protected by SDDL; even normal admin cannot modify them

**Always verify**:
```powershell
# Confirm immediately after modification
Get-CimInstance Win32_Service -Filter "Name='ServiceName'" |
    Select-Object Name, StartMode
```

### sc.exe delete Special Behavior

```powershell
# After deletion the service may still appear (marked as "DELETE_PENDING")
sc.exe delete "ServiceName"

# If the service is running, stop it first
sc.exe stop "ServiceName"
sc.exe delete "ServiceName"

# Verify: registry key gone = deletion succeeded (may need reboot to fully clean up)
Test-Path "HKLM:\SYSTEM\CurrentControlSet\Services\ServiceName"
```

### 14. Multi-Line `if/else` Blocks Break When Pasted into Terminal

When AI generates multi-line `if/else` code and the user pastes it into an interactive PowerShell terminal (including VS Code integrated terminal), each line is executed independently. The `else` block becomes a standalone statement and errors out.

```powershell
# This works in a .ps1 script, but BREAKS when pasted into terminal:
if (Test-Path $path) {
    Remove-Item $path
}
else {
    Write-Host "Not found"
}
# Terminal error: "else" is not recognized — because "}" on the previous line
# already closed the statement.

# Safe for terminal paste — keep else on the same line as closing brace:
if (Test-Path $path) {
    Remove-Item $path
} else {
    Write-Host "Not found"
}

# Even safer — single line or pre-compute:
$exists = Test-Path $path
if ($exists) { Remove-Item $path } else { Write-Host "Not found" }
```

**Rule: When generating code that may be pasted interactively, always put `} else {`, `} elseif {`, `} catch {`, `} finally {` on the same line as the closing brace `}`.**

This also affects `try/catch/finally`, `do/while`, and `switch` blocks. The underlying issue is that PowerShell's interactive parser treats a line ending with `}` as a complete statement.

### 15. PowerShell 5.1 File Encoding: Must Use UTF-8 with BOM

PowerShell 5.1 on non-English Windows defaults to the system locale encoding (e.g., GBK on Chinese Windows, Shift_JIS on Japanese Windows) when reading script files. If a `.ps1` file contains non-ASCII characters (Chinese text, box-drawing characters `─`, emoji, etc.) and is saved **without** BOM, PowerShell will misinterpret the bytes, causing:
- Parse errors on lines with multi-byte characters
- String comparisons silently failing (garbled characters never match)
- `Write-Host` outputting mojibake

```powershell
# Check if a file has BOM
$bytes = [System.IO.File]::ReadAllBytes("script.ps1")
$hasBom = ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)

# Add BOM to a file that's missing it
$content = [System.IO.File]::ReadAllText("script.ps1", [System.Text.Encoding]::UTF8)
$utf8Bom = New-Object System.Text.UTF8Encoding $true
[System.IO.File]::WriteAllText("script.ps1", $content, $utf8Bom)
```

**All `.ps1` files must be saved as UTF-8 with BOM (first 3 bytes: `EF BB BF`).** This is the only encoding that works reliably across all PowerShell versions on all Windows locales.

### 16. sc.exe Access Denied (Exit Code 5) on Protected Services

Some Windows services are protected by PPL (Protected Process Light) or SDDL restrictions, making them immune to modification even from an elevated Administrator session. `sc.exe config` returns exit code 5 (Access Denied).

```powershell
# This fails even with admin:
sc.exe config "SgrmBroker" start= disabled
# [SC] OpenService FAILED 5: Access is denied.

# Known protected services:
# - SgrmBroker (System Guard Runtime Monitor Broker)
# - TrustedInstaller (Windows Modules Installer)
# - Services protected by Early Launch AM drivers
```

**When scripting, always check for exit code 5 specifically and report it as `[PROTECTED]` rather than a generic failure, so the human operator understands the limitation.**

### 17. WScript.Shell COM Cannot Handle CJK Characters in .lnk Operations

Three failure modes when using `WScript.Shell` COM on non-English (CJK) Windows:

#### a) CreateShortcut with CJK filename fails

```powershell
$shell = New-Object -ComObject WScript.Shell
$shell.CreateShortcut("C:\Users\Public\Desktop\夸克.lnk")
# Throws: FileNotFoundException
```

**Workaround**: Create with an ASCII temp name, then rename via `[System.IO.File]::Move()`:

```powershell
$tempPath = "C:\Users\Public\Desktop\_temp_shortcut.lnk"
$finalPath = "C:\Users\Public\Desktop\夸克.lnk"
$lnk = $shell.CreateShortcut($tempPath)
$lnk.TargetPath = "C:\Program Files\Quark\Quark.exe"
$lnk.Save()
[System.IO.File]::Move($tempPath, $finalPath)
```

#### b) TargetPath with CJK path fails

```powershell
$lnk.TargetPath = "C:\Program Files\TencentNews\腾讯新闻.exe"
# Throws: ArgumentException: Value does not fall within the expected range
```

**Workaround**: Use 8.3 short file name. Discover it with `Scripting.FileSystemObject` COM or `cmd /c "dir /x"`:

```powershell
function Resolve-ShortPath($LongPath) {
    $fso = New-Object -ComObject Scripting.FileSystemObject
    return $fso.GetFile($LongPath).ShortPath
}
$lnk.TargetPath = Resolve-ShortPath "C:\Program Files\TencentNews\腾讯新闻.exe"
# Returns something like: C:\PROGRA~1\TENCEN~1\BD046~1.EXE
```

#### c) Advertised shortcuts return empty TargetPath

Many MSI-installed or bundleware-installed programs (especially Chinese software: 腾讯会议, 元宝, 腾讯新闻) create "advertised shortcuts." These store the target as an MSI feature ID rather than a file path. `WScript.Shell.CreateShortcut().TargetPath` returns an **empty string** for these.

```powershell
$lnk = $shell.CreateShortcut("C:\Users\Public\Desktop\腾讯会议.lnk")
$lnk.TargetPath   # Returns "" — but the shortcut IS valid!
```

**Do NOT treat empty TargetPath as "dead shortcut"** without further checks:
- Check if the `.lnk` file size is > 500 bytes (advertised shortcuts are typically larger)
- Cross-reference the shortcut name against the installed software list (`Get-ItemProperty HKLM:\...\Uninstall\*`)
- Read the `.lnk` binary content and search for target path fragments as ASCII/Unicode strings

**In diagnostic output, mark these as `[ADVERTISED]` not `[DEAD]`.**

### 18. Long Script Paste Crashes PSReadLine in VS Code Terminal

Beyond the `} else {` terminal paste issue (#14), **any script longer than ~30 lines** pasted into VS Code's integrated terminal can trigger a PSReadLine buffer overflow crash:

```
SetCursorPosition: The value must be greater than or equal to zero
```

This affects complex multi-step operations like shortcut creation/repair scripts with loops, COM object handling, and error handling blocks.

**Rule: For operations exceeding ~20 lines, always write to a `.ps1` file and execute with `powershell -File script.ps1`.** Never paste long scripts directly into the terminal.

This supersedes and extends gotcha #14 — the mechanism is similar (PSReadLine's console buffer tracking breaks down) but the trigger is different (overall script length, not just `if/else` block structure).

---

## AI Self-Check Checklist

After generating PowerShell code, verify against this checklist:

- [ ] Did you write `sc.exe` or just `sc`?
- [ ] Did you use `&&`? PowerShell 5.1 does not support it
- [ ] Are comparison operators `-eq` / `-ne` / `-gt` or `==` / `!=` / `>`?
- [ ] Is `>` a redirection or did you mean it as a greater-than comparison?
- [ ] Are function arguments separated by spaces? Did you write method-call style `Func(a, b)`?
- [ ] Are strings containing `$` wrapped in single quotes?
- [ ] Are results that need `.Count` wrapped in `@()`?
- [ ] Are you checking native program results with `$LASTEXITCODE` or `$?`?
- [ ] Registry paths: PowerShell uses `HKLM:\`, reg.exe uses `HKLM\`?
- [ ] Is `Format-Table` / `Format-List` at the end of the pipeline?
- [ ] Are property accesses inside double-quoted strings wrapped in `$()` sub-expressions?
- [ ] Are `} else {`, `} catch {`, `} finally {` on the same line as `}`? (Terminal paste safety)
- [ ] Are all `.ps1` files saved as UTF-8 with BOM? (Critical for non-English Windows)
- [ ] When `sc.exe` returns exit code 5, is it reported as `[PROTECTED]` not just `[FAIL]`?
- [ ] When using `WScript.Shell` to read `.lnk` files, do you handle empty `TargetPath` (advertised shortcuts) separately from truly dead shortcuts?
- [ ] When creating `.lnk` with CJK filenames or targets, do you use the ASCII-create-then-rename or 8.3 short path workaround?
- [ ] Is the script short enough to paste into terminal, or does it need to be written to a `.ps1` file first? (>20 lines → write to file)

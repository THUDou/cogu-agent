import subprocess, sys, json, os
from pathlib import Path

workspace = str(Path(__file__).parent)
BIN = [sys.executable, "-m", "cogu"]
passed = 0
failed = 0

def test(name, args, should_fail=False):
    global passed, failed
    cmd = BIN + args
    try:
        r = subprocess.run(cmd, cwd=workspace, capture_output=True, text=True, timeout=30)
        ok = r.returncode != 0 if should_fail else r.returncode == 0
        if ok:
            print(f"  OK  {name}")
            passed += 1
        else:
            print(f"  FAIL {name} (rc={r.returncode}, expected {'fail' if should_fail else 'ok'})")
            if r.stderr:
                print(f"    stderr: {r.stderr[:200]}")
            failed += 1
        return r
    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT {name}")
        failed += 1
        return None
    except Exception as e:
        print(f"  ERROR {name}: {e}")
        failed += 1
        return None

test("version", ["version"])

test("skills list", ["skills", "list"])

r = test("skills list --all", ["skills", "list", "--all"])
if r and "Builtin" in r.stdout:
    print("       -> builtin skills shown")
if r and "Installed" in r.stdout:
    print("       -> installed skills shown")

test("skills builtin list", ["skills", "builtin", "list"])

test("skills builtin run shell --action which --params '{\"program\":\"python\"}'",
     ["skills", "builtin", "run", "shell", "--action", "which", "--params", '{"program":"python"}'])

test("memory stats", ["memory", "stats"])

test("memory search", ["memory", "search", "cogu"])

test("memory reconcile", ["memory", "reconcile"])

r = test("--help", ["--help"])
if r and "skills run" in r.stdout:
    print("       -> skills run in help")

test("skills --help", ["skills", "--help"])

test("skills install local", ["skills", "install", "skills/hello-world", "--level", "user"])

test("skills info", ["skills", "info", "hello-world"])

test("skills run simulated", ["skills", "run", "hello-world", "--input", '{"name":"E2E Test"}'])

test("skills run --script", ["skills", "run", "hello-world", "--script", "scripts/greet.py", "--script-args", "E2E"])

test("skills uninstall", ["skills", "uninstall", "hello-world"])

test("skills info missing", ["skills", "info", "nonexistent"], should_fail=True)

test("skills run missing", ["skills", "run", "nonexistent"], should_fail=True)

test("skills uninstall missing", ["skills", "uninstall", "nonexistent"], should_fail=True)

print(f"\n{'='*50}")
print(f"Results: {passed} passed, {failed} failed ({passed + failed} total)")
if failed == 0:
    print("ALL TESTS PASSED")
else:
    print(f"{failed} TEST(S) FAILED")
    sys.exit(1)

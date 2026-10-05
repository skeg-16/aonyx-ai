"""Real launch verification for every entry in ALLOWED_APPS.

For each app this goes through the SAME code path the AI uses
(app.orchestrator.tools.open_app), then proves the app actually appeared by
detecting NEW visible top-level windows / NEW processes, and finally closes only
what that launch created (WM_CLOSE on new windows, terminate new PIDs). Apps the
user already had open are never killed.

Usage: python verify_app_launch.py [name ...]   (default: all apps)
"""
import ctypes
import os
import sys
import time
from ctypes import wintypes

import psutil

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from app.orchestrator.config import ALLOWED_APPS  # noqa: E402
from app.orchestrator.tools import open_app  # noqa: E402

user32 = ctypes.windll.user32
WM_CLOSE = 0x0010
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def visible_windows():
    """Return {hwnd: (title, pid)} for visible, titled top-level windows."""
    found = {}

    def cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            if n > 0:
                buf = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, buf, n + 1)
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                found[hwnd] = (buf.value, pid.value)
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return found


def static_check(target):
    """Does the configured target look resolvable on this machine?"""
    if not target:
        return False, "empty target (app not installed / path not found)"
    if target.endswith(":"):
        return True, "URI scheme"
    if os.path.isabs(target):
        return (os.path.exists(target), "absolute path " + ("exists" if os.path.exists(target) else "MISSING"))
    import shutil
    found = shutil.which(target)
    if found:
        return True, f"on PATH -> {found}"
    # App Paths registry / shell resolution (what ShellExecute uses)
    import winreg
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(hive, rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{target}") as k:
                return True, f"App Paths -> {winreg.QueryValue(k, None)}"
        except OSError:
            pass
    return False, "not on PATH and no App Paths entry"


def verify(name, wait=12.0):
    target = ALLOWED_APPS[name]
    ok_static, why = static_check(target)
    before_w = set(visible_windows())
    t0 = time.time()
    result = open_app(name)
    status = result["status"]

    new_w, new_pids = {}, set()
    deadline = time.time() + wait
    while time.time() < deadline:
        time.sleep(0.5)
        cur = visible_windows()
        new_w = {h: v for h, v in cur.items() if h not in before_w}
        new_pids = {p.pid for p in psutil.process_iter(["create_time"])
                    if (p.info["create_time"] or 0) >= t0 - 0.5}
        if new_w:
            break

    appeared = bool(new_w)
    # cleanup: only what this launch created
    for hwnd in new_w:
        user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
    time.sleep(1.5)
    for pid in new_pids:
        try:
            p = psutil.Process(pid)
            if p.create_time() >= t0 - 0.5 and p.pid != os.getpid() and p.name().lower() not in (
                    "python.exe", "pythonw.exe", "conhost.exe", "cmd.exe", "powershell.exe", "pwsh.exe"):
                p.terminate()
        except Exception:
            pass
    return {
        "name": name, "target": target, "static_ok": ok_static, "static_why": why,
        "tool_status": status, "tool_data": result["data"],
        "window_appeared": appeared,
        "windows": [v[0][:60] for v in new_w.values()],
    }


def main():
    names = sys.argv[1:] or list(ALLOWED_APPS)
    rows = []
    for n in names:
        if n not in ALLOWED_APPS:
            print(f"unknown app: {n}")
            continue
        print(f"... launching {n}", flush=True)
        r = verify(n)
        rows.append(r)
        verdict = "PASS" if (r["tool_status"] == "ok" and r["window_appeared"]) else "FAIL"
        print(f"[{verdict}] {n}: tool={r['tool_status']} static={r['static_ok']} ({r['static_why']}) "
              f"windows={r['windows']}", flush=True)
        if verdict == "FAIL":
            print(f"        tool data: {r['tool_data']}  target: {r['target']!r}", flush=True)
        time.sleep(1)

    passed = [r["name"] for r in rows if r["tool_status"] == "ok" and r["window_appeared"]]
    failed = [r["name"] for r in rows if r["name"] not in passed]
    print("\n--- SUMMARY ---")
    print(f"PASS ({len(passed)}): {', '.join(passed)}")
    print(f"FAIL ({len(failed)}): {', '.join(failed)}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())

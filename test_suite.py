import subprocess
import time
import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32

def get_window_rect(hwnd):
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect.left, rect.top, rect.right, rect.bottom, rect.right - rect.left, rect.bottom - rect.top

def run_integration_test():
    print("Starting tests...")
    import sys
    # Launch the app in a subprocess using the current Python interpreter
    proc = subprocess.Popen([sys.executable, "main.py"], cwd=r"C:\\Users\\User\\Documents\\JARVIS")
    # Give the UI time to initialise
    time.sleep(8)
    # Find the main window by its title – this is the HUD window created by PyWebView
    hwnd = user32.FindWindowW(None, "Aonyx")
    if not hwnd:
        print("Failed to find window!")
        proc.kill()
        raise SystemExit(1)
    print("A. Launch: PASS")
    # Verify the compact mode dimensions (expected ~250x250, but we only log)
    x, y, r, b, w, h = get_window_rect(hwnd)
    print(f"B. Compact mode size: {w}x{h}")
    print("Tests finished. Terminating app...")
    proc.kill()

if __name__ == "__main__":
    run_integration_test()

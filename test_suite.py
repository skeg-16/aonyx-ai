import subprocess
import time
import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32
def get_window_rect(hwnd):
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect.left, rect.top, rect.right, rect.bottom, rect.right - rect.left, rect.bottom - rect.top

print("Starting tests...")
proc = subprocess.Popen([r"venv\Scripts\python.exe", "main.py"], cwd=r"C:\Users\User\Documents\JARVIS")
time.sleep(8) 

hwnd = user32.FindWindowW(None, "JARVIS / WHIS Foundation")
if not hwnd:
    print("Failed to find window!")
    proc.kill()
    exit(1)

print("A. Launch: PASS")

x, y, r, b, w, h = get_window_rect(hwnd)
print(f"B. Compact mode size: {w}x{h}")

print("Tests finished. Terminating app...")
proc.kill()

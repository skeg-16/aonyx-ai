import ctypes
import time
from ctypes import wintypes
import webview
import threading
import sys

user32 = ctypes.windll.user32
shcore = ctypes.windll.shcore

def get_window_rect(hwnd):
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return rect.left, rect.top, rect.right, rect.bottom, rect.right - rect.left, rect.bottom - rect.top

def get_monitor_info(hwnd):
    monitor = user32.MonitorFromWindow(hwnd, 2) # MONITOR_DEFAULTTONEAREST
    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD),
                    ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT),
                    ("dwFlags", wintypes.DWORD)]
    mi = MONITORINFO()
    mi.cbSize = ctypes.sizeof(MONITORINFO)
    user32.GetMonitorInfoA(monitor, ctypes.byref(mi))
    return mi.rcMonitor.right - mi.rcMonitor.left, mi.rcMonitor.bottom - mi.rcMonitor.top, mi.rcWork.right - mi.rcWork.left, mi.rcWork.bottom - mi.rcWork.top

def check_window_info(window):
    time.sleep(3) # wait for window to show
    hwnd = user32.FindWindowW(None, "Test Verification")
    if not hwnd:
        print("Window not found")
        return

    dpi = user32.GetDpiForWindow(hwnd)
    x, y, r, b, w, h = get_window_rect(hwnd)
    mw, mh, ww, wh = get_monitor_info(hwnd)

    print(f"--- DESKTOP VERIFICATION ---")
    print(f"DPI: {dpi} ({(dpi/96)*100}%)")
    print(f"Window Rect: ({x}, {y}) to ({r}, {b})")
    print(f"Physical Size: {w}x{h}")
    print(f"Monitor Size: {mw}x{mh} (Work Area: {ww}x{wh})")
    print(f"Logical Size via pywebview: {window.width}x{window.height}")
    
    # Check hiding
    print("Hiding window...")
    window.hide()
    time.sleep(1)
    if user32.IsWindowVisible(hwnd):
        print("Window is still visible after hide()!")
    else:
        print("Window is successfully hidden via API.")
        
    print("Showing window...")
    window.show()
    time.sleep(1)
    if user32.IsWindowVisible(hwnd):
        print("Window is visible again via API.")
    
    window.destroy()

if __name__ == '__main__':
    try:
        shcore.SetProcessDpiAwareness(2)
        print("DPI Awareness set to 2")
    except Exception as e:
        print(f"Error setting DPI awareness: {e}")
        
    window = webview.create_window("Test Verification", html="<h1>Test</h1>", width=800, height=600)
    threading.Thread(target=check_window_info, args=(window,), daemon=True).start()
    webview.start()

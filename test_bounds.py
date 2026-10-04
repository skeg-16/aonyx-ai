import webview
import ctypes
from ctypes import wintypes
import time
import threading

user32 = ctypes.windll.user32
dwmapi = ctypes.windll.dwmapi
shcore = ctypes.windll.shcore

DWMWA_EXTENDED_FRAME_BOUNDS = 9

def check_sizes(window):
    time.sleep(2)
    hwnd = user32.FindWindowW(None, "Bounds Test")
    if not hwnd: return
    
    # GetWindowRect
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    wr_w, wr_h = rect.right - rect.left, rect.bottom - rect.top
    
    # GetClientRect
    crect = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(crect))
    cr_w, cr_h = crect.right - crect.left, crect.bottom - crect.top
    
    # DwmGetWindowAttribute (Extended Frame Bounds)
    frect = wintypes.RECT()
    dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(frect), ctypes.sizeof(frect))
    fr_w, fr_h = frect.right - frect.left, frect.bottom - frect.top
    
    print(f"GetWindowRect: {wr_w}x{wr_h}")
    print(f"GetClientRect: {cr_w}x{cr_h}")
    print(f"DWM Extended Frame Bounds: {fr_w}x{fr_h}")
    
    window.destroy()

shcore.SetProcessDpiAwareness(2)
window = webview.create_window("Bounds Test", html="<p>Test</p>", width=250, height=250, frameless=True)
threading.Thread(target=check_sizes, args=(window,), daemon=True).start()
webview.start()

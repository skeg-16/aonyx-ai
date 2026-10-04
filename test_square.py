import webview
import ctypes
from ctypes import wintypes
import time
import threading

user32 = ctypes.windll.user32
shcore = ctypes.windll.shcore

def force_square(window):
    time.sleep(2)
    hwnd = user32.FindWindowW(None, "Square Test")
    if not hwnd: return
    
    dpi = user32.GetDpiForWindow(hwnd)
    scale = dpi / 96.0
    
    log_w = 250
    log_h = 250
    
    phys_w = int(log_w * scale)
    phys_h = int(log_h * scale)
    
    # SWP_NOMOVE | SWP_NOZORDER
    user32.SetWindowPos(hwnd, 0, 0, 0, phys_w, phys_h, 0x0002 | 0x0004)
    
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    crect = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(crect))
    
    print(f"Target Physical: {phys_w}x{phys_h}")
    print(f"Window Rect: {rect.right - rect.left}x{rect.bottom - rect.top}")
    print(f"Client Rect: {crect.right - crect.left}x{crect.bottom - crect.top}")
    
    window.destroy()

if __name__ == '__main__':
    shcore.SetProcessDpiAwareness(2)
    window = webview.create_window("Square Test", html="<p>Test</p>", width=250, height=250, frameless=True)
    threading.Thread(target=force_square, args=(window,), daemon=True).start()
    webview.start()

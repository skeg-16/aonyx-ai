import ctypes
from ctypes import wintypes
import threading
import time

user32 = ctypes.windll.user32
user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = wintypes.BOOL

def bg():
    if not user32.RegisterHotKey(None, 2, 3, 0x20):
        print("Failed to register")
        return
    print('Registered Ctrl+Alt+Space')
    msg = wintypes.MSG()
    while True:
        bRet = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
        print("bRet:", bRet, "msg.message:", msg.message, "wParam:", msg.wParam)
        if msg.message == 0x0312:
            print("HOTKEY RECEIVED!")
            break
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))

t = threading.Thread(target=bg, daemon=True)
t.start()
time.sleep(1)
print("Simulating keypress")
user32.keybd_event(0x11, 0, 0, 0)
user32.keybd_event(0x12, 0, 0, 0)
user32.keybd_event(0x20, 0, 0, 0)
time.sleep(0.1)
user32.keybd_event(0x20, 0, 2, 0)
user32.keybd_event(0x12, 0, 2, 0)
user32.keybd_event(0x11, 0, 2, 0)
time.sleep(2)

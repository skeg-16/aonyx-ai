import webview
import ctypes
from ctypes import wintypes
import os
import logging
import threading
import sys
from app.api import DesktopAPI

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("main")

user32 = ctypes.windll.user32
shcore = ctypes.windll.shcore
dwmapi = ctypes.windll.dwmapi

# Constants
HOTKEY_ID = 1
HOTKEY_PTT_ID = 2
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
VK_SPACE = 0x20

DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWMWCP_ROUND = 2
DWMWCP_DONOTROUND = 1
SW_SHOWNOACTIVATE = 4

def set_dpi_awareness():
    try:
        shcore.SetProcessDpiAwareness(2)
        logger.info("DPI Awareness V2 enabled.")
    except Exception as e:
        logger.warning(f"Could not set DPI awareness: {e}")

def set_true_geometry(hwnd, log_w, log_h):
    dpi = user32.GetDpiForWindow(hwnd)
    scale = dpi / 96.0
    phys_w = int(log_w * scale)
    phys_h = int(log_h * scale)
    # 0x0002=SWP_NOMOVE, 0x0004=SWP_NOZORDER, 0x0020=SWP_FRAMECHANGED
    user32.SetWindowPos(hwnd, 0, 0, 0, phys_w, phys_h, 0x0002 | 0x0004 | 0x0020)

def apply_rounded_corners(hwnd):
    if sys.platform == "win32":
        try:
            preference = ctypes.c_int(DWMWCP_ROUND)
            res = dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, ctypes.byref(preference), ctypes.sizeof(preference))
            if res == 0:
                logger.info("Applied Windows 11 DWM rounded corners.")
            else:
                logger.info(f"DwmSetWindowAttribute returned {res}, likely on Windows 10. Fallback: frameless window will have square corners natively.")
        except Exception as e:
            logger.warning(f"Could not apply DWM rounded corners: {e}")

class HotkeyManager:
    def __init__(self, window, api):
        self.window = window
        self.api = api
        self.is_expanded = False
        self.is_hidden = False
        self.hwnd = None

    def start(self):
        t = threading.Thread(target=self._hotkey_loop, daemon=True)
        t.start()

    def _hotkey_loop(self):
        if not user32.RegisterHotKey(None, HOTKEY_ID, MOD_CONTROL | MOD_SHIFT, VK_SPACE):
            msg = "HOTKEY ERROR: Failed to register Ctrl+Shift+Space. Another app may be using it."
            logger.error(msg)
            self.api._set_state("ERROR", msg)
            
        if not user32.RegisterHotKey(None, HOTKEY_PTT_ID, MOD_CONTROL | MOD_ALT, VK_SPACE):
            msg = "HOTKEY ERROR: Failed to register PTT key (Ctrl+Alt+Space)."
            logger.error(msg)
            self.api._set_state("ERROR", msg)
        else:
            logger.info("Registered PTT hotkey Ctrl+Alt+Space")
        
        logger.info("Registered global hotkeys.")
        
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            if msg.message == 0x0312: # WM_HOTKEY
                if msg.wParam == HOTKEY_ID:
                    self.toggle_state()
                elif msg.wParam == HOTKEY_PTT_ID:
                    self.trigger_ptt()
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def trigger_ptt(self):
        logger.info("PTT Hotkey pressed.")
        if self.is_hidden and self.hwnd:
            logger.info("Showing window (Compact mode) without stealing focus")
            set_true_geometry(self.hwnd, 250, 250)
            user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
            self.window.evaluate_js('window.dispatchEvent(new CustomEvent("aonyx-visibility", {detail: {visible: true}}))')
            self.is_hidden = False
            self.is_expanded = False
            
        self.api.toggle_listening()

    def toggle_state(self):
        if self.is_hidden:
            logger.info("Showing window (Compact mode)")
            if self.hwnd:
                set_true_geometry(self.hwnd, 250, 250)
            else:
                self.window.resize(250, 250)
            self.window.show()
            self.window.evaluate_js('window.dispatchEvent(new CustomEvent("aonyx-visibility", {detail: {visible: true}}))')
            self.is_hidden = False
            self.is_expanded = False
        elif not self.is_expanded:
            logger.info("Expanding window")
            self.window.resize(1000, 700)
            self.is_expanded = True
        else:
            logger.info("Hiding window")
            self.window.evaluate_js('window.dispatchEvent(new CustomEvent("aonyx-visibility", {detail: {visible: false}}))')
            self.window.hide()
            self.is_hidden = True
            self.is_expanded = False

def on_window_ready(window, api, hotkey_mgr):
    logger.info("Window ready. Applying Win32 styles.")
    hwnd = user32.FindWindowW(None, window.title)
    if hwnd:
        hotkey_mgr.hwnd = hwnd
        apply_rounded_corners(hwnd)
        set_true_geometry(hwnd, 250, 250)
    
    api.on_loaded()
    hotkey_mgr.start()

_ctrl_handler_ptr = None # Keep global reference to prevent GC
_global_window = None

def setup_ctrl_c_handler():
    global _ctrl_handler_ptr
    def _ctrl_handler(ctrl_type):
        if ctrl_type in (0, 2): # CTRL_C_EVENT or CTRL_CLOSE_EVENT
            logger.info("Ctrl+C detected, shutting down Aonyx gracefully...")
            if _global_window:
                _global_window.destroy()
            return True
        return False
    
    CMPFUNC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_uint)
    _ctrl_handler_ptr = CMPFUNC(_ctrl_handler)
    ctypes.windll.kernel32.SetConsoleCtrlHandler(_ctrl_handler_ptr, True)

def main():
    setup_ctrl_c_handler()
    set_dpi_awareness()
    
    api = DesktopAPI()
    
    dist_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'frontend', 'dist'))
    html_path = os.path.join(dist_path, 'index.html')
    
    if not os.path.exists(html_path):
        logger.error(f"Frontend build not found at {html_path}. Run npm build.")
        return

    # Start in compact mode
    window = webview.create_window(
        'Aonyx',
        url=f'file:///{html_path.replace(chr(92), "/")}',
        width=250,
        height=250,
        js_api=api,
        resizable=False,
        frameless=True,
        on_top=True
    )
    
    api.set_window(window)
    global _global_window
    _global_window = window
    hotkey_mgr = HotkeyManager(window, api)
    api._hotkey_mgr = hotkey_mgr
    
    window.events.loaded += lambda: on_window_ready(window, api, hotkey_mgr)
    
    logger.info("Starting webview...")
    webview.start(debug=False)

if __name__ == "__main__":
    main()

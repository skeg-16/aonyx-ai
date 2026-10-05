import os
import psutil
import ctypes
import ctypes.wintypes
from .registry import registry, ToolPermission
from .config import ALLOWED_APPS

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

def get_active_window(args):
    try:
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return {"status": "error", "data": "No active window found.", "summary": "No active window"}
        
        # Get window title
        length = user32.GetWindowTextLengthW(hwnd)
        buff = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buff, length + 1)
        title = buff.value
        
        # Get process ID
        pid = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        
        process_name = "Unknown"
        try:
            proc = psutil.Process(pid.value)
            process_name = proc.name()
        except Exception:
            pass

        return {
            "status": "ok",
            "data": {
                "application": process_name,
                "title": title,
                "pid": pid.value
            },
            "summary": f"Active: {process_name}"
        }
    except Exception as e:
        return {"status": "error", "data": f"Error: {str(e)}", "summary": "Error getting active window"}

registry.register(
    "get_active_window",
    "Returns the currently active/focused window application and title.",
    {"type": "object", "properties": {}},
    ToolPermission.SAFE,
    get_active_window
)

def get_desktop_info(args):
    try:
        # Screen dimensions
        width = user32.GetSystemMetrics(0)
        height = user32.GetSystemMetrics(1)
        
        # Basic OS info
        import platform
        os_info = f"{platform.system()} {platform.release()}"
        
        # Check if Aonyx is visible
        aonyx_hwnd = user32.FindWindowW(None, "Aonyx")
        is_visible = False
        if aonyx_hwnd:
            is_visible = user32.IsWindowVisible(aonyx_hwnd) != 0

        return {
            "status": "ok",
            "data": {
                "screen_resolution": f"{width}x{height}",
                "os": os_info,
                "aonyx_visible": is_visible
            },
            "summary": "Desktop info retrieved"
        }
    except Exception as e:
        return {"status": "error", "data": f"Error: {str(e)}", "summary": "Error getting desktop info"}

registry.register(
    "get_desktop_info",
    "Returns safe desktop information including screen dimensions, OS version, and if Aonyx is visible.",
    {"type": "object", "properties": {}},
    ToolPermission.SAFE,
    get_desktop_info
)

def check_application(args):
    app_name = args.get("app_name", "").strip().lower()
    target = ALLOWED_APPS.get(app_name)
    if not target:
        allowed = ", ".join(sorted(ALLOWED_APPS.keys()))
        return {"status": "error", "data": f"App '{app_name}' not in allowlist. Allowed: {allowed}", "summary": "App blocked"}
    
    expected_exe = os.path.basename(target).lower()
    running = False
    pids = []
    
    try:
        for proc in psutil.process_iter(['name', 'pid']):
            if proc.info['name'] and proc.info['name'].lower() == expected_exe:
                running = True
                pids.append(proc.info['pid'])
    except Exception as e:
        return {"status": "error", "data": f"Error checking processes: {str(e)}", "summary": "Error checking app"}
        
    if running:
        return {"status": "ok", "data": f"{app_name} is running (PIDs: {pids}).", "summary": f"{app_name} is running"}
    else:
        return {"status": "ok", "data": f"{app_name} is NOT running.", "summary": f"{app_name} not running"}

registry.register(
    "check_application",
    f"Checks if an allowed application is currently running without launching it. Allowed apps: {', '.join(ALLOWED_APPS.keys())}",
    {"type": "object", "properties": {"app_name": {"type": "string"}}, "required": ["app_name"]},
    ToolPermission.SAFE,
    check_application
)

def focus_application(args):
    app_name = args.get("app_name", "").strip().lower()
    target = ALLOWED_APPS.get(app_name)
    if not target:
        allowed = ", ".join(sorted(ALLOWED_APPS.keys()))
        return {"status": "error", "data": f"App '{app_name}' not in allowlist. Allowed: {allowed}", "summary": "App blocked"}
        
    expected_exe = os.path.basename(target).lower()
    
    target_pids = set()
    try:
        for proc in psutil.process_iter(['name', 'pid']):
            if proc.info['name'] and proc.info['name'].lower() == expected_exe:
                target_pids.add(proc.info['pid'])
    except Exception as e:
        return {"status": "error", "data": f"Error looking up processes: {str(e)}", "summary": "Error looking up app"}
            
    if not target_pids:
        return {"status": "error", "data": f"{app_name} is not running.", "summary": f"{app_name} not running"}

    hwnds = []
    def enum_cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            pid = ctypes.wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value in target_pids:
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    hwnds.append(hwnd)
        return True
        
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
    user32.EnumWindows(EnumWindowsProc(enum_cb), 0)
    
    if hwnds:
        hwnd = hwnds[0]
        user32.ShowWindow(hwnd, 9) # SW_RESTORE
        user32.SetForegroundWindow(hwnd)
        return {"status": "ok", "data": f"Focused {app_name}.", "summary": f"Focused {app_name}"}
        
    return {"status": "error", "data": f"Could not find a main window for {app_name} to focus.", "summary": f"Failed to focus {app_name}"}

registry.register(
    "focus_application",
    f"Brings a running allowed application to the foreground. Allowed apps: {', '.join(ALLOWED_APPS.keys())}",
    {"type": "object", "properties": {"app_name": {"type": "string"}}, "required": ["app_name"]},
    ToolPermission.SAFE,
    focus_application
)

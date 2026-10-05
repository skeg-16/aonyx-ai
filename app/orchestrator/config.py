import os

# Base paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
USER_HOME = os.path.expanduser("~")

# Configs
MAX_TOOL_STEPS = 5
TOOL_TIMEOUT = 15  # Seconds per tool

ALLOWED_APPS = {
    "notepad": os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "notepad.exe"),
    "calculator": "calc.exe",
    "explorer": "explorer.exe",
    "cmd": "cmd.exe",
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "spotify": os.path.join(os.environ.get("APPDATA", ""), "Spotify", "Spotify.exe"),
    "edge": "msedge.exe",
    "antigravity": os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Antigravity IDE", "Antigravity IDE.exe"),
    "fxsound": r"C:\Program Files\FxSound LLC\FxSound\FxSound.exe",
    "adobe acrobat": "acrobat.exe",
    "task manager": "taskmgr.exe",
    "settings": "ms-settings:",
    "vscode": "code.exe",
    "discord": (lambda: __import__('glob').glob(os.path.join(os.environ.get("LOCALAPPDATA", ""), "Discord", "app-*", "Discord.exe"))[0] if __import__('glob').glob(os.path.join(os.environ.get("LOCALAPPDATA", ""), "Discord", "app-*", "Discord.exe")) else "")(),
    "paint": "mspaint.exe"
}

# Allowlist for folders that can be read/searched
ALLOWED_FOLDERS = [
    os.path.join(USER_HOME, "Documents"),
    os.path.join(USER_HOME, "Desktop"),
    os.path.join(USER_HOME, "Downloads"),
    os.path.join(BASE_DIR, "notes")
]

NOTES_FOLDER = os.path.join(BASE_DIR, "notes")
if not os.path.exists(NOTES_FOLDER):
    os.makedirs(NOTES_FOLDER)

MEMORY_DB_PATH = os.path.join(BASE_DIR, "memory.db")
AUDIT_LOG_PATH = os.path.join(BASE_DIR, "audit.log")

# Restrictions
MAX_FILE_READ_SIZE = 100000  # Cap characters returned

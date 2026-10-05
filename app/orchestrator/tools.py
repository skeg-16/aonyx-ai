import os
import ast
import operator
import datetime
import psutil
import subprocess
import urllib.parse
from .registry import registry, ToolPermission
from .config import ALLOWED_APPS, ALLOWED_FOLDERS, NOTES_FOLDER, MAX_FILE_READ_SIZE
from . import memory

# No eval/exec arbitrary execution by design.
# Safe math evaluator
_OP_MAP = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.BitXor: operator.xor,
    ast.USub: operator.neg, ast.UAdd: operator.pos
}

def _eval_expr(node):
    # ast.Num was removed in Python 3.14; ast.Constant is the only literal node.
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float, complex)):
            raise TypeError("Only numeric constants are allowed")
        return node.value
    elif isinstance(node, ast.BinOp):
        return _OP_MAP[type(node.op)](_eval_expr(node.left), _eval_expr(node.right))
    elif isinstance(node, ast.UnaryOp):
        return _OP_MAP[type(node.op)](_eval_expr(node.operand))
    else:
        raise TypeError(node)

def safe_calc(args):
    expression = args.get("expression") or args.get("expr")
    if not expression:
         return {"status": "error", "data": "Missing 'expression' argument.", "summary": "Math error"}
    try:
        node = ast.parse(expression, mode='eval').body
        result = _eval_expr(node)
        return {"status": "ok", "data": str(result), "summary": f"Calculated: {result}"}
    except Exception as e:
        return {"status": "error", "data": str(e), "summary": "Math error"}

registry.register(
    "calculator",
    "Evaluates a mathematical expression (numbers and operators only).",
    {"type": "object", "properties": {"expression": {"type": "string"}, "expr": {"type": "string"}}},
    ToolPermission.SAFE,
    safe_calc
)

def get_current_time(args):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {"status": "ok", "data": now, "summary": f"Time is {now}"}

registry.register(
    "get_current_time",
    "Returns the current date and time.",
    {"type": "object", "properties": {}},
    ToolPermission.SAFE,
    get_current_time
)

def get_sys_info(args):
    cpu = psutil.cpu_percent()
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    batt = psutil.sensors_battery()
    batt_pct = batt.percent if batt else "Unknown"
    info = f"CPU: {cpu}% | RAM: {mem.percent}% | Disk: {disk.percent}% | Battery: {batt_pct}%"
    return {"status": "ok", "data": info, "summary": "System info retrieved"}

registry.register(
    "system_information",
    "Retrieves system metrics (CPU, RAM, Disk, Battery).",
    {"type": "object", "properties": {}},
    ToolPermission.SAFE,
    get_sys_info
)

def open_app(app_name):
    # Normalize the provided name: strip whitespace, quotes and make it lower‑case
    normalized = app_name.strip().strip('"\'').lower()
    target = ALLOWED_APPS.get(normalized)
    if not target:
        # Provide a helpful error with the list of allowed names
        allowed = ", ".join(sorted(ALLOWED_APPS.keys()))
        return {
            "status": "error",
            "data": f"App '{app_name}' not in allowlist. Allowed apps: {allowed}",
            "summary": "App blocked",
        }
    try:
        if os.name == 'nt':
            # Try os.startfile first; if it fails, fall back to subprocess.Popen which can launch by name.
            try:
                os.startfile(target)
            except Exception:
                try:
                    subprocess.Popen([target], shell=False)
                except Exception as e:
                    return {"status": "error", "data": str(e), "summary": f"Failed to launch {app_name}"}
        else:
            subprocess.Popen([target], shell=False)
        return {"status": "ok", "data": f"Opened {app_name}", "summary": f"Launched {app_name}"}
    except Exception as e:
        return {"status": "error", "data": str(e), "summary": f"Failed to launch {app_name}"}

registry.register(
    "open_application",
    f"Opens an application by name. Model must only supply the app name. Allowed apps: {', '.join(ALLOWED_APPS.keys())}",
    {"type": "object", "properties": {"app_name": {"type": "string"}}, "required": ["app_name"]},
    ToolPermission.SAFE,
    lambda args: open_app(args["app_name"])
)

def open_url(url):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ["http", "https"]:
        return {"status": "error", "data": "Only http and https schemes are allowed.", "summary": "Blocked URL scheme"}
    try:
        # Use python's webbrowser instead of shell
        import webbrowser
        webbrowser.open(url)
        return {"status": "ok", "data": f"Opened {url}", "summary": f"Opened URL"}
    except Exception as e:
        return {"status": "error", "data": str(e), "summary": "Failed to open URL"}

registry.register(
    "open_url",
    "Opens a URL in the default browser. Only http and https allowed.",
    {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]},
    ToolPermission.SAFE,
    lambda args: open_url(args["url"])
)

def _is_safe_path(target_path):
    target_path = os.path.abspath(target_path)
    for folder in ALLOWED_FOLDERS:
        if target_path.startswith(os.path.abspath(folder)):
            # Block sensitive files
            name = os.path.basename(target_path).lower()
            if name == '.env' or name.endswith('.pem') or name == 'id_rsa':
                return False
            if "appdata" in target_path.lower():
                return False
            return True
    return False

def read_file(file_path):
    if not _is_safe_path(file_path):
        return {"status": "error", "data": "Path is outside allowed folders or restricted.", "summary": "Access denied"}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read(MAX_FILE_READ_SIZE)
        return {"status": "ok", "data": content, "summary": f"Read {len(content)} chars"}
    except Exception as e:
        return {"status": "error", "data": str(e), "summary": "File read failed"}

registry.register(
    "read_file",
    "Reads text content from a local file.",
    {"type": "object", "properties": {"file_path": {"type": "string"}}, "required": ["file_path"]},
    ToolPermission.CONFIRM,
    lambda args: read_file(args["file_path"])
)

def create_note(filename, content):
    clean_name = "".join(c for c in filename if c.isalnum() or c in (' ', '.', '_', '-')).rstrip()
    if not clean_name:
        clean_name = "note.txt"
    path = os.path.join(NOTES_FOLDER, clean_name)
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return {"status": "ok", "data": path, "summary": f"Note {clean_name} saved"}
    except Exception as e:
        return {"status": "error", "data": str(e), "summary": "Note save failed"}

registry.register(
    "create_note",
    "Creates a text note.",
    {"type": "object", "properties": {"filename": {"type": "string"}, "content": {"type": "string"}}, "required": ["filename", "content"]},
    ToolPermission.CONFIRM,
    lambda args: create_note(args["filename"], args["content"])
)

def search_files(directory, query):
    if not _is_safe_path(directory):
         return {"status": "error", "data": "Path is outside allowed folders.", "summary": "Access denied"}
    results = []
    try:
        for root, dirs, files in os.walk(directory):
            for file in files:
                if query.lower() in file.lower():
                    results.append(os.path.join(root, file))
            if len(results) > 50:
                break
        return {"status": "ok", "data": "\n".join(results), "summary": f"Found {len(results)} files"}
    except Exception as e:
        return {"status": "error", "data": str(e), "summary": "Search failed"}

registry.register(
    "search_local_files",
    "Searches for files by name in a directory.",
    {"type": "object", "properties": {"directory": {"type": "string"}, "query": {"type": "string"}}, "required": ["directory", "query"]},
    ToolPermission.CONFIRM,
    lambda args: search_files(args["directory"], args["query"])
)

registry.register(
    "STORE_MEMORY",
    "Stores information in memory. Categories: SHORT_TERM, LONG_TERM, USER_PREF, TASK.",
    {
        "type": "object", 
        "properties": {
            "category": {"type": "string", "enum": ["SHORT_TERM", "LONG_TERM", "USER_PREF", "TASK"]},
            "content": {"type": "string"},
            "tags": {"type": "string"}
        }, 
        "required": ["category", "content"]
    },
    ToolPermission.SAFE,
    lambda args: {"status": "ok", "data": memory.manager.store_memory(args.get("category", "LONG_TERM"), args["content"], args.get("tags", "")), "summary": f"Stored in {args.get('category', 'LONG_TERM')}"}
)

registry.register(
    "RETRIEVE_MEMORY",
    "Searches memory by keyword and optionally category.",
    {
        "type": "object", 
        "properties": {
            "query": {"type": "string"},
            "category": {"type": "string", "enum": ["SHORT_TERM", "LONG_TERM", "USER_PREF", "TASK"]}
        }, 
        "required": ["query"]
    },
    ToolPermission.SAFE,
    lambda args: {"status": "ok", "data": memory.manager.retrieve_memory(args["query"], args.get("category")), "summary": "Memory retrieved"}
)

registry.register(
    "UPDATE_MEMORY",
    "Updates an existing memory entry by its ID.",
    {
        "type": "object", 
        "properties": {
            "id": {"type": "integer"},
            "content": {"type": "string"},
            "category": {"type": "string", "enum": ["SHORT_TERM", "LONG_TERM", "USER_PREF", "TASK"]},
            "tags": {"type": "string"}
        }, 
        "required": ["id"]
    },
    ToolPermission.SAFE,
    lambda args: {"status": "ok", "data": memory.manager.update_memory(args["id"], args.get("content"), args.get("category"), args.get("tags")), "summary": "Memory updated"}
)

registry.register(
    "DELETE_MEMORY",
    "Deletes an existing memory entry by its ID.",
    {
        "type": "object", 
        "properties": {
            "id": {"type": "integer"}
        }, 
        "required": ["id"]
    },
    ToolPermission.SAFE,
    lambda args: {"status": "ok", "data": memory.manager.delete_memory(args["id"]), "summary": "Memory deleted"}
)

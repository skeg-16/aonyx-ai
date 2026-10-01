"""
Real system diagnostics using PowerShell — no pip install needed.
"""
import subprocess
import json
import logging

logger = logging.getLogger(__name__)


def get_system_stats() -> dict:
    """Fetch real CPU, RAM, Disk, and process count via PowerShell."""
    script = r"""
$os  = Get-CimInstance Win32_OperatingSystem
$cpu = (Get-Counter '\Processor(_Total)\% Processor Time' -ErrorAction SilentlyContinue).CounterSamples.CookedValue
if (-not $cpu) { $cpu = 0 }
$ramTotal = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
$ramFree  = [math]::Round($os.FreePhysicalMemory  / 1MB, 1)
$ramUsed  = [math]::Round($ramTotal - $ramFree, 1)
$ramPct   = [math]::Round(($ramUsed / $ramTotal) * 100, 0)
$disk = Get-PSDrive C
$diskFree  = [math]::Round($disk.Free  / 1GB, 1)
$diskUsed  = [math]::Round($disk.Used  / 1GB, 1)
$diskTotal = [math]::Round(($disk.Free + $disk.Used) / 1GB, 1)
$diskPct   = [math]::Round(($diskUsed / $diskTotal) * 100, 0)
$procs = (Get-Process).Count
$uptime = (Get-Date) - $os.LastBootUpTime
$uptimeStr = "{0}d {1}h {2}m" -f [int]$uptime.TotalDays, $uptime.Hours, $uptime.Minutes
$result = @{
    cpu       = [math]::Round($cpu, 0)
    ram_used  = $ramUsed
    ram_total = $ramTotal
    ram_pct   = [int]$ramPct
    disk_free  = $diskFree
    disk_total = $diskTotal
    disk_pct   = [int]$diskPct
    processes  = $procs
    uptime     = $uptimeStr
    network    = "WiFi"
} | ConvertTo-Json
Write-Output $result
"""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout.strip())
    except Exception as e:
        logger.error(f"Diagnostics error: {e}")

    # Fallback defaults
    return {
        "cpu": 0, "ram_used": 0, "ram_total": 0, "ram_pct": 0,
        "disk_free": 0, "disk_total": 0, "disk_pct": 0,
        "processes": 0, "uptime": "N/A", "network": "N/A"
    }


def format_diagnostic_prompt(stats: dict) -> str:
    return (
        f"CPU Usage: {stats['cpu']}%, "
        f"RAM: {stats['ram_used']}GB / {stats['ram_total']}GB ({stats['ram_pct']}%), "
        f"Disk C: {stats['disk_free']}GB free of {stats['disk_total']}GB ({stats['disk_pct']}% used), "
        f"Running Processes: {stats['processes']}, "
        f"Uptime: {stats['uptime']}"
    )

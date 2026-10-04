import os
import time

apps_to_test = [
    "notepad", 
    "calculator:", 
    __import__('glob').glob(os.path.join(os.environ.get("LOCALAPPDATA", ""), "Discord", "app-*", "Discord.exe"))[0],
    os.path.join(os.environ.get("APPDATA", ""), "Spotify", "Spotify.exe"),
    "chrome.exe"
]

print("Launching apps using os.system('start ...')")
for target in apps_to_test:
    cmd = f'start "" "{target}"'
    print(f"Executing: {cmd}")
    os.system(cmd)
    time.sleep(2)

print("Finished launching apps.")

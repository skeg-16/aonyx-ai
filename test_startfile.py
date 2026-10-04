import os
import time

apps_to_test = {
    "notepad": r"C:\Windows\System32\notepad.exe", 
    "calculator": "calculator:", 
    "discord": __import__('glob').glob(os.path.join(os.environ.get("LOCALAPPDATA", ""), "Discord", "app-*", "Discord.exe"))[0],
    "spotify": os.path.join(os.environ.get("APPDATA", ""), "Spotify", "Spotify.exe"),
    "chrome": "chrome.exe"
}

print("Launching apps using os.startfile(...)")
for name, target in apps_to_test.items():
    print(f"Executing: os.startfile('{target}')")
    try:
        os.startfile(target)
    except Exception as e:
        print(f"Error: {e}")
    time.sleep(2)

print("Finished launching apps.")

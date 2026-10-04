import subprocess
try:
    print("Testing notepad...")
    subprocess.Popen('start "" "notepad.exe"', shell=True)
    print("Notepad done")
    print("Testing spotify...")
    import os
    spotify_path = os.path.join(os.environ.get("APPDATA", ""), "Spotify", "Spotify.exe")
    subprocess.Popen(f'start "" "{spotify_path}"', shell=True)
    print("Spotify done")
except Exception as e:
    print(f"Error: {e}")

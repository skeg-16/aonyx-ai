import asyncio
import time
from app.api import DesktopAPI

class MockWindow:
    def evaluate_js(self, script):
        print(f"[MOCK JS EVAL] {script}")

def test():
    print("Initializing API...")
    api = DesktopAPI()
    window = MockWindow()
    api.set_window(window)
    api.on_loaded()
    
    time.sleep(2)
    print("Sending message 'hi'...")
    api.send_message("hi")
    
    # Wait for processing
    time.sleep(10)
    print("Test complete.")

if __name__ == "__main__":
    test()

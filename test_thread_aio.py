import asyncio
import aiohttp
import sys
import threading
import time

class Tester:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        
    def _run_loop(self):
        print("Starting loop in thread")
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def run_check(self):
        print("Submitting to loop")
        future = asyncio.run_coroutine_threadsafe(self.check_health(), self.loop)
        try:
            print("Result:", future.result(timeout=5))
        except Exception as e:
            print(f"Exception from future: {type(e).__name__} - {repr(e)}")

    async def check_health(self):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("http://127.0.0.1:11434/api/tags", timeout=2) as resp:
                    return resp.status == 200
        except Exception as e:
            print(f"Ollama health check failed: {type(e).__name__} - {repr(e)}")
            return False

t = Tester()
time.sleep(1)
t.run_check()

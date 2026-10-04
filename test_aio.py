import asyncio
import aiohttp
import sys

async def main():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://127.0.0.1:11434/api/tags", timeout=2) as resp:
                print(f"Status: {resp.status}")
                print(await resp.text())
    except Exception as e:
        print(f"Error: {type(e).__name__} - {repr(e)}")

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

asyncio.run(main())

import aiohttp
import logging
import asyncio
import os
import json
import time

logger = logging.getLogger(__name__)

class OllamaClient:
    def __init__(self, host="127.0.0.1", port=11434, model="llama3:latest"):
        self.base_url = f"http://{host}:{port}"
        self.model = model
        self.first_timeout = int(os.environ.get("OLLAMA_FIRST_TIMEOUT", 90))
        self.token_timeout = int(os.environ.get("OLLAMA_TOKEN_TIMEOUT", 10))

    async def check_health(self) -> bool:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/api/tags", timeout=10) as resp:
                    return resp.status == 200
        except Exception as e:
            logger.error(f"Ollama health check failed: {type(e).__name__} - {repr(e)}")
            return False

    async def warmup(self) -> float:
        """Sends a tiny request to load the model into memory with keep_alive."""
        start_time = time.time()
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": "sys_warmup",
            "stream": False,
            "keep_alive": "30m"
        }
            
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=self.first_timeout)) as resp:
                    if resp.status == 200:
                        elapsed = time.time() - start_time
                        logger.info(f"Model warmed up in {elapsed:.2f}s")
                        return elapsed
                    else:
                        raise Exception(f"HTTP {resp.status} - {await resp.text()}")
        except Exception as e:
            err_msg = f"Ollama warmup failed: {type(e).__name__} - {repr(e)}"
            logger.error(err_msg)
            raise Exception(err_msg)

    async def generate_stream(self, prompt: str):
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "keep_alive": "30m"
        }
        
        try:
            # We use a sock_read timeout so that each chunk has a timeout.
            # aiohttp total=None means the stream can take as long as it needs,
            # but if Ollama goes silent for longer than first_timeout, it aborts.
            timeout_config = aiohttp.ClientTimeout(total=None, sock_read=self.first_timeout, connect=10)
            async with aiohttp.ClientSession(timeout=timeout_config) as session:
                async with session.post(url, json=payload) as resp:
                    if resp.status != 200:
                        raise Exception(f"HTTP {resp.status} - {await resp.text()}")
                    
                    is_first = True
                    while True:
                        timeout = self.first_timeout if is_first else self.token_timeout
                        try:
                            line = await asyncio.wait_for(resp.content.readline(), timeout=timeout)
                        except asyncio.TimeoutError:
                            stage = "waiting for first token (model may still be loading)" if is_first else "waiting for next token"
                            raise Exception(f"Ollama did not respond within {timeout}s ({stage})")
                        except Exception as inner_e:
                            raise Exception(f"Stream read error: {type(inner_e).__name__} - {repr(inner_e)}")
                            
                        if not line:
                            break
                            
                        is_first = False
                        data = json.loads(line)
                        yield data.get("response", "")
                        
                        if data.get("done"):
                            break
                            
        except Exception as e:
            logger.error(f"Ollama generate_stream failed: {e}")
            raise Exception(f"Ollama error: {type(e).__name__} - {repr(e)}")

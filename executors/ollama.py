import aiohttp
import os
import json
import logging

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3") # Or your preferred local model

async def generate_response(prompt: str) -> str:
    url = f"{OLLAMA_BASE_URL}/api/generate"
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("response", "No response content.")
                else:
                    logger.error(f"Ollama API returned status {response.status}")
                    return f"Error: Ollama returned {response.status}"
        except aiohttp.ClientConnectorError:
            logger.error("Could not connect to Ollama. Is it running?")
            raise Exception("Ollama connection failed")

import logging
from faster_whisper import WhisperModel
import asyncio

logger = logging.getLogger(__name__)

# Setting device="cpu" because the system lacks CUDA 12 DLLs for float16 GPU compute.
model_size = 'small.en' 
try:
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
except Exception as e:
    logger.error(f"Failed to load Whisper model: {e}")
    model = None

async def transcribe_voice(file_path: str) -> str:
    """
    Transcribes an audio file using faster-whisper.
    """
    if not model:
        raise Exception("Whisper model is not loaded.")
        
    logger.info(f"Transcribing audio file: {file_path}")
    
    # We run the synchronous transcribe method in a thread to prevent blocking the async event loop
    loop = asyncio.get_event_loop()
    
    def _transcribe():
        segments, info = model.transcribe(
            file_path, 
            beam_size=5, 
            language="en",
            initial_prompt="User is speaking a command to W.H.I.S., an AI assistant.",
            condition_on_previous_text=False
        )
        
        valid_texts = [segment.text for segment in segments]
                
        text = " ".join(valid_texts)
        return text.strip()
        
    try:
        transcript = await loop.run_in_executor(None, _transcribe)
        return transcript
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise

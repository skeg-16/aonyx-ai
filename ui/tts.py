import subprocess
import threading
import logging
import asyncio
import os
import edge_tts
import uuid

logger = logging.getLogger(__name__)


class TextToSpeech:
    """
    TTS using edge-tts (Microsoft Edge TTS API).
    Uses en-US-GuyNeural (male) voice for JARVIS.
    """

    def __init__(self):
        self.voice = 'en-GB-RyanNeural'
        import pygame
        self._lock = threading.Lock()
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
        except Exception as e:
            logger.error(f"Pygame init error: {e}")
        logger.info(f'TTS ready (Edge TTS — {self.voice})')

    def speak(self, text: str, on_done_callback=None):
        def _speak():
            with self._lock:
                try:
                    # Generate a unique file name to avoid collisions
                    output_file = os.path.abspath(f"tts_temp_{uuid.uuid4().hex[:8]}.mp3")
                    
                    async def generate():
                        communicate = edge_tts.Communicate(text, self.voice)
                        await communicate.save(output_file)
                    
                    # Run the edge-tts async generation
                    asyncio.run(generate())
                    
                    # Play the generated audio file using pygame
                    import pygame
                    if not pygame.mixer.get_init():
                        pygame.mixer.init()
                    pygame.mixer.music.load(output_file)
                    pygame.mixer.music.play()
                    import time
                    time.sleep(0.2)
                    while pygame.mixer.music.get_busy():
                        pygame.time.Clock().tick(10)
                    # Unload the file so it can be deleted
                    try:
                        pygame.mixer.music.unload()
                    except:
                        pass
                    
                except Exception as e:
                    logger.error(f"TTS error: {e}")
                finally:
                    # Cleanup the temp file
                    if 'output_file' in locals() and os.path.exists(output_file):
                        import pygame
                        try:
                            pygame.mixer.music.unload()
                        except:
                            pass
                        try:
                            os.remove(output_file)
                        except Exception as cleanup_error:
                            logger.error(f"Failed to cleanup TTS file: {cleanup_error}")
                            
                    if on_done_callback:
                        on_done_callback()

        threading.Thread(target=_speak, daemon=True).start()

    def stop(self):
        import pygame
        if pygame.mixer.get_init():
            try:
                pygame.mixer.music.stop()
            except:
                pass

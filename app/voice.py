import time
import math
import struct
import threading
import queue
import logging
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
import asyncio
import edge_tts
import pygame
import os
import tempfile

logger = logging.getLogger("voice")

class VoiceEngine:
    def __init__(self, api_callback):
        self.api_callback = api_callback
        
        self.sample_rate = 16000
        self.chunk_size = 512
        try:
            self.mic_index = sd.default.device[0]
            logger.info(f"Using microphone device index {self.mic_index}")
        except Exception as e:
            self.mic_index = None
            logger.error(f"No default microphone found: {e}")
        
        self.is_listening = False
        self.audio_frames = []
        self.silence_frames = 0
        # Increased silence threshold significantly for better noise rejection
        self.silence_threshold = 200  
        self.silence_duration_limit = int((1.5 * self.sample_rate) / self.chunk_size)
        
        self.stt_model = None
        self.model_loaded = False
        
        self.tts_queue = queue.Queue()
        self.is_speaking = False
        self.cancel_speech = False
        
        # Initialize pygame mixer for TTS playback
        try:
            pygame.mixer.init()
        except Exception as e:
            logger.error(f"Failed to initialize pygame mixer: {e}")
            
        self.tts_voice = "en-US-AriaNeural" # A pleasant, calm, intelligent female voice from Edge TTS
        self.temp_dir = tempfile.gettempdir()
        
        # Threads
        self.audio_thread = threading.Thread(target=self._audio_capture_loop, daemon=True)
        self.stt_thread = threading.Thread(target=self._load_stt_model, daemon=True)
        self.tts_thread = threading.Thread(target=self._tts_loop, daemon=True)
        
        self.audio_thread.start()
        self.stt_thread.start()
        self.tts_thread.start()

    def _load_stt_model(self):
        logger.info("Voice engine loading STT model (faster-whisper base.en)...")
        try:
            self.stt_model = WhisperModel("base.en", device="cpu", compute_type="int8")
            self.model_loaded = True
            logger.info("STT model loaded successfully.")
            self.api_callback("VOICE_READY", None)
        except Exception as e:
            logger.error(f"Failed to load STT model: {e}")
            self.api_callback("VOICE_ERROR", f"STT Load Error: {str(e)}")

    def _audio_capture_loop(self):
        logger.info("Microphone capture thread started.")
        
        def audio_callback(indata, frames, time_info, status):
            if status:
                logger.error(f"Audio status: {status}")
            
            clean_data = np.nan_to_num(indata, nan=0.0, posinf=1.0, neginf=-1.0).astype(np.float64)
            rms = np.sqrt(np.mean(clean_data**2))
            
            rms_int = rms * 32768
            if math.isnan(rms_int) or math.isinf(rms_int):
                rms_int = 0
                
            ui_rms = min(100, max(0, int(rms_int / 10)))
            
            if self.is_listening:
                self.audio_frames.append(indata.copy())
                self.api_callback("RMS_UPDATE", ui_rms)
                
                if rms_int < self.silence_threshold:
                    self.silence_frames += 1
                    if self.silence_frames > self.silence_duration_limit:
                        # Only stop if we actually recorded something (avoid stopping instantly if totally quiet)
                        if len(self.audio_frames) > self.silence_duration_limit:
                            logger.info("Silence detected. Stopping recording.")
                            self.stop_listening()
                            self.process_audio()
                else:
                    self.silence_frames = 0
                    
        try:
            with sd.InputStream(samplerate=self.sample_rate, channels=1, 
                                blocksize=self.chunk_size, callback=audio_callback):
                while True:
                    time.sleep(1)
        except Exception as e:
            logger.error(f"Microphone unavailable: {e}")
            self.api_callback("VOICE_ERROR", "Microphone unavailable. Check Privacy Settings.")
            return

    def start_listening(self):
        if not self.model_loaded:
            self.api_callback("VOICE_ERROR", "Voice engine still loading.")
            return False
            
        self.interrupt_tts()
        self.audio_frames = []
        self.silence_frames = 0
        self.is_listening = True
        return True

    def stop_listening(self):
        self.is_listening = False
        
    def process_audio(self):
        if not self.audio_frames:
            return
            
        logger.info("Processing captured audio...")
        self.api_callback("STATE", "THINKING")
        
        audio_np = np.concatenate(self.audio_frames).flatten()
        self.audio_frames = []
        
        start_t = time.time()
        try:
            segments, info = self.stt_model.transcribe(audio_np, beam_size=1, vad_filter=True)
            text = "".join([segment.text for segment in segments]).strip()
            stt_time = time.time() - start_t
            logger.info(f"STT Latency: {stt_time:.2f}s | Text: '{text}'")
            
            if not text:
                logger.info("No speech detected after VAD.")
                self.api_callback("STATE", "IDLE")
                return
                
            self.api_callback("TRANSCRIPT", text)
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            self.api_callback("VOICE_ERROR", "Speech recognition failed.")
            self.api_callback("STATE", "IDLE")

    def speak(self, text):
        self.tts_queue.put(text)
        
    def interrupt_tts(self):
        self.cancel_speech = True
        
        # Stop pygame mixer immediately
        try:
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except Exception as e:
            pass
            
        # Clear queue
        while not self.tts_queue.empty():
            try:
                self.tts_queue.get_nowait()
            except queue.Empty:
                break
                
        self.api_callback("RMS_UPDATE", 0)
        self.api_callback("STATE", "IDLE")

    async def _generate_audio(self, text, output_path):
        communicate = edge_tts.Communicate(text, self.tts_voice)
        await communicate.save(output_path)

    def _tts_loop(self):
        logger.info("TTS Engine (Edge-TTS) thread started.")
        
        while True:
            text = self.tts_queue.get()
            if text is None:
                continue
                
            self.is_speaking = True
            self.cancel_speech = False
            
            try:
                logger.info(f"Synthesizing speech: {text}")
                output_file = os.path.join(self.temp_dir, f"aonyx_tts_{int(time.time()*1000)}.mp3")
                
                # Generate audio file
                asyncio.run(self._generate_audio(text, output_file))
                
                if self.cancel_speech:
                    continue
                    
                # Play audio
                self.api_callback("STATE", "SPEAKING")
                
                if pygame.mixer.get_init():
                    pygame.mixer.music.load(output_file)
                    pygame.mixer.music.play()
                    
                    while pygame.mixer.music.get_busy() and not self.cancel_speech:
                        # Simulate RMS for speaking
                        self.api_callback("RMS_UPDATE", np.random.randint(30, 80))
                        time.sleep(0.05)
                        
                    if self.cancel_speech:
                        pygame.mixer.music.stop()
                        logger.info("TTS Interrupted by user.")
                
                # Cleanup temp file
                try:
                    # Give pygame a moment to release the file handle
                    time.sleep(0.1)
                    if os.path.exists(output_file):
                        os.remove(output_file)
                except:
                    pass
                    
            except Exception as e:
                logger.error(f"TTS Error: {e}")
            
            self.api_callback("RMS_UPDATE", 0)
            if not self.cancel_speech:
                self.api_callback("STATE", "IDLE")
            self.is_speaking = False
            
    def shutdown(self):
        self.is_listening = False
        self.interrupt_tts()
        try:
            if pygame.mixer.get_init():
                pygame.mixer.quit()
        except:
            pass

import time
import math
import struct
import threading
import queue
import logging
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
import pythoncom
import win32com.client

logger = logging.getLogger("voice")

class VoiceEngine:
    def __init__(self, api_callback):
        self.api_callback = api_callback
        
        self.sample_rate = 16000
        self.chunk_size = 512
        try:
            self.mic_index = sd.default.device[0]
        except:
            self.mic_index = None
        
        self.is_listening = False
        self.audio_frames = []
        self.silence_frames = 0
        self.silence_threshold = 30  # RMS threshold
        self.silence_duration_limit = int((1.2 * self.sample_rate) / self.chunk_size)
        
        self.stt_model = None
        self.model_loaded = False
        
        self.tts_queue = queue.Queue()
        self.is_speaking = False
        self.cancel_speech = False
        
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
            # Using int8 on CPU is fast enough for base model on laptops
            self.stt_model = WhisperModel("base.en", device="cpu", compute_type="int8")
            self.model_loaded = True
            logger.info("STT model loaded successfully.")
            self.api_callback("VOICE_READY", None)
        except Exception as e:
            logger.error(f"Failed to load STT model: {e}")
            self.api_callback("VOICE_ERROR", f"STT Load Error: {str(e)}")

    def _audio_capture_loop(self):
        logger.info("Microphone capture thread started.")
        
        def audio_callback(indata, frames, time, status):
            if status:
                logger.error(f"Audio status: {status}")
            
            # indata is float32 numpy array
            clean_data = np.nan_to_num(indata, nan=0.0, posinf=1.0, neginf=-1.0).astype(np.float64)
            rms = np.sqrt(np.mean(clean_data**2))
            
            # Convert float32 [-1.0, 1.0] to pseudo-int16 scale for legacy RMS thresholding
            rms_int = rms * 32768
            if math.isnan(rms_int) or math.isinf(rms_int):
                rms_int = 0
                
            ui_rms = min(100, max(0, int(rms_int / 20)))
            
            if self.is_listening:
                # Store as int16 bytes for consistency with previous pipeline, 
                # or just store the float32 array directly! Let's store float32 bytes for faster-whisper.
                self.audio_frames.append(indata.copy())
                self.api_callback("RMS_UPDATE", ui_rms)
                
                if rms_int < self.silence_threshold:
                    self.silence_frames += 1
                    if self.silence_frames > self.silence_duration_limit:
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
        
        # audio_frames contains list of float32 numpy arrays
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
        # Clear queue
        while not self.tts_queue.empty():
            try:
                self.tts_queue.get_nowait()
            except queue.Empty:
                break

    def _tts_loop(self):
        pythoncom.CoInitialize()
        try:
            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            speaker.Volume = 100
            # 1 = SVSFlagsAsync, 2 = SVSFPurgeBeforeSpeak
        except Exception as e:
            logger.error(f"SAPI init failed: {e}")
            self.api_callback("VOICE_ERROR", "TTS Engine unavailable.")
            return

        logger.info("TTS Engine (SAPI5) loaded.")
        
        while True:
            text = self.tts_queue.get()
            if text is None:
                continue
                
            self.is_speaking = True
            self.cancel_speech = False
            
            try:
                logger.info(f"Sending to SAPI5: {text}")
                speaker.Speak(text, 1) 
                
                # SAPI5 takes a few ms to transition from Done (1) to Speaking (2)
                for _ in range(20):
                    if speaker.Status.RunningState == 2:
                        break
                    time.sleep(0.02)
                
                # Wait for speech to finish or interrupt
                while speaker.Status.RunningState == 2: # 2 = speaking
                    pythoncom.PumpWaitingMessages()
                    if self.cancel_speech:
                        logger.info("TTS Interrupted by user.")
                        speaker.Speak("", 2) # Purge
                        self.cancel_speech = False
                        break
                    
                    # Simulate RMS for speaking based on being active
                    self.api_callback("RMS_UPDATE", np.random.randint(20, 60))
                    time.sleep(0.05)
                    
            except Exception as e:
                logger.error(f"TTS Error: {e}")
            
            self.api_callback("RMS_UPDATE", 0)
            self.is_speaking = False
            
    def shutdown(self):
        self.is_listening = False
        self.interrupt_tts()

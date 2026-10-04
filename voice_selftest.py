import math
import sys
import numpy as np
import time
import sounddevice as sd
from faster_whisper import WhisperModel
import pythoncom
import win32com.client
import logging

logging.basicConfig(filename='voice_selftest.log', level=logging.INFO, format='%(asctime)s - %(message)s')

def log_and_print(msg, is_pass=None):
    if is_pass is True:
        msg = f"[PASS] {msg}"
    elif is_pass is False:
        msg = f"[FAIL] {msg}"
    print(msg)
    logging.info(msg)

def test_microphone():
    log_and_print("--- Testing Microphone ---")
    
    devices = sd.query_devices()
    for i, dev in enumerate(devices):
        if dev['max_input_channels'] > 0:
            log_and_print(f"Input Device id {i} - {dev['name']}")
            
    try:
        default_index = sd.default.device[0]
        log_and_print(f"Using default input device index: {default_index}")
    except:
        log_and_print("No default input device found.", False)
        return False, None
    
    log_and_print("Recording for 5 seconds. Please speak...")
    
    try:
        audio_data = sd.rec(int(5 * 16000), samplerate=16000, channels=1, dtype='float32')
        for i in range(50):
            time.sleep(0.1)
            # Display live meter by calculating RMS of the chunk so far
            current_chunk = audio_data[int(i * 0.1 * 16000) : int((i+1) * 0.1 * 16000)]
            if len(current_chunk) > 0:
                clean_chunk = np.nan_to_num(current_chunk, nan=0.0, posinf=1.0, neginf=-1.0).astype(np.float64)
                rms = np.sqrt(np.mean(clean_chunk**2)) * 32768
                if math.isnan(rms) or math.isinf(rms):
                    rms = 0
                rms_int = max(0, int(rms))
                meter_len = min(50, int(rms_int / 100))
                meter = '|' * meter_len
                print(f"\rRMS: {rms_int:04d} {meter:30s}", end="")
        print()
        sd.wait()
        log_and_print("Microphone recorded successfully.", True)
    except Exception as e:
        log_and_print(f"Failed to record microphone: {e}", False)
        return False, None
        
    audio_np = audio_data.flatten()
    log_and_print(f"Captured {len(audio_np)} audio samples.", True)
    return True, audio_np

def test_stt(audio_np):
    log_and_print("--- Testing STT (faster-whisper) ---")
    start = time.time()
    try:
        model = WhisperModel("base.en", device="cpu", compute_type="int8")
        load_time = time.time() - start
        log_and_print(f"Model loaded in {load_time:.2f}s", True)
    except Exception as e:
        log_and_print(f"Failed to load WhisperModel: {e}", False)
        return False
        
    log_and_print("Transcribing...")
    start = time.time()
    try:
        segments, _ = model.transcribe(audio_np, beam_size=1)
        text = "".join([segment.text for segment in segments]).strip()
        stt_time = time.time() - start
        log_and_print(f"Transcription complete in {stt_time:.2f}s", True)
        log_and_print(f"Transcript: '{text}'")
        return True
    except Exception as e:
        log_and_print(f"Transcription failed: {e}", False)
        return False

def test_tts():
    log_and_print("--- Testing TTS (SAPI5) ---")
    try:
        pythoncom.CoInitialize()
        speaker = win32com.client.Dispatch("SAPI.SpVoice")
        log_and_print("SAPI initialized successfully.", True)
    except Exception as e:
        log_and_print(f"Failed to initialize SAPI5: {e}", False)
        return False
        
    test_phrase = "Hello. This is Aonyx speaking through the SAPI5 engine."
    log_and_print(f"Speaking: '{test_phrase}'")
    start = time.time()
    try:
        speaker.Speak(test_phrase, 1) # async
        while speaker.Status.RunningState == 2:
            time.sleep(0.1)
        tts_time = time.time() - start
        log_and_print(f"TTS complete in {tts_time:.2f}s", True)
        return True
    except Exception as e:
        log_and_print(f"TTS failed: {e}", False)
        return False

if __name__ == "__main__":
    log_and_print("=== AONYX VOICE SELF-TEST ===")
    
    mic_ok, audio_np = test_microphone()
    if not mic_ok:
        sys.exit(1)
        
    stt_ok = test_stt(audio_np)
    if not stt_ok:
        sys.exit(1)
        
    tts_ok = test_tts()
    if not tts_ok:
        sys.exit(1)
        
    log_and_print("=== ALL TESTS PASSED ===")

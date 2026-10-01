"""
Voice trigger using Windows built-in Speech Recognition (System.Speech).
No pip install needed — uses PowerShell subprocess with compiled C# SapiBridge.

Flow:
  1. A long-running PowerShell process compiles SapiBridge in-memory.
  2. The SapiBridge loads WakeGrammar and DictationGrammar.
  3. Initially, only WakeGrammar is enabled to listen for "JARVIS".
  4. When wake word is recognized, Python switches the recognition engine to DictationGrammar.
  5. The next phrase is captured as the command, and the engine resets back to WakeGrammar.
  6. If no command is received within 8 seconds, it times out and resets back to WakeGrammar.
"""
import subprocess
import threading
import logging

logger = logging.getLogger(__name__)

# PowerShell script compiling C# SapiBridge to support concurrent background event handling
_PS_SCRIPT = r"""
Add-Type -AssemblyName System.Speech
$code = @"
using System;
using System.Speech.Recognition;

public class SapiBridge {
    public SpeechRecognitionEngine Rec;
    public Grammar WakeGrammar;
    public Grammar DictationGrammar;

    public SapiBridge() {
        try {
            Rec = new SpeechRecognitionEngine();
            Rec.SetInputToDefaultAudioDevice();

            Choices choices = new Choices(new string[] { 
                "whis", "hey whis", "hi whis", "ok whis", "computer",
                "whis wake up", "whis turn on", "hey whis wake up", "hey whis turn on",
                "computer wake up", "computer turn on", "wake up whis", "turn on whis"
            });
            GrammarBuilder gb = new GrammarBuilder(choices);
            WakeGrammar = new Grammar(gb);
            WakeGrammar.Name = "WakeGrammar";

            DictationGrammar = new DictationGrammar();
            DictationGrammar.Name = "DictationGrammar";

            Rec.LoadGrammar(WakeGrammar);
            Rec.LoadGrammar(DictationGrammar);

            WakeGrammar.Enabled = true;
            DictationGrammar.Enabled = false;

            Rec.SpeechRecognized += new EventHandler<SpeechRecognizedEventArgs>(OnSpeechRecognized);
            Rec.RecognizeAsync(RecognizeMode.Multiple);
            Console.WriteLine("DEBUG|SAPI Bridge initialized successfully.");
        } catch (Exception ex) {
            Console.WriteLine("DEBUG|SAPI Init Error: " + ex.Message);
        }
    }

    private void OnSpeechRecognized(object sender, SpeechRecognizedEventArgs e) {
        if (e.Result != null && !string.IsNullOrEmpty(e.Result.Text)) {
            Console.WriteLine("RECOGNIZED|" + e.Result.Grammar.Name + "|" + e.Result.Confidence + "|" + e.Result.Text);
        }
    }

    public void SetMode(string mode) {
        try {
            if (mode == "MODE:WAKE") {
                Rec.SetInputToDefaultAudioDevice();
                WakeGrammar.Enabled = true;
                DictationGrammar.Enabled = false;
                try { Rec.RecognizeAsync(RecognizeMode.Multiple); } catch {}
                Console.WriteLine("DEBUG|Switched to WAKE mode.");
            } else if (mode == "MODE:COMMAND") {
                WakeGrammar.Enabled = false;
                DictationGrammar.Enabled = true;
                Console.WriteLine("DEBUG|Switched to COMMAND mode.");
            } else if (mode == "MODE:PAUSE") {
                WakeGrammar.Enabled = false;
                DictationGrammar.Enabled = false;
                Rec.RecognizeAsyncCancel();
                Rec.SetInputToNull();
                Console.WriteLine("DEBUG|Switched to PAUSE mode (Mic released).");
            }
        } catch (Exception ex) {
            Console.WriteLine("DEBUG|SetMode Error: " + ex.Message);
        }
    }
}
"@

Add-Type -TypeDefinition $code -ReferencedAssemblies System.Speech
$bridge = New-Object SapiBridge

while ($null -ne ($cmd = [Console]::ReadLine())) {
    $cmd = $cmd.Trim().ToUpper()
    $bridge.SetMode($cmd)
}
"""


class VoiceTrigger:
    def __init__(self, on_wake_callback, on_command_callback, on_error_callback=None):
        self._on_wake    = on_wake_callback
        self._on_command = on_command_callback
        self._on_error   = on_error_callback
        self._running    = False
        self._process    = None
        self._thread     = None
        self._awaiting_command = False
        self._command_timer = None
        self._lock = threading.Lock()

    def start(self):
        self._running = True
        self._thread  = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("VoiceTrigger started — say 'WHIS' to activate.")

    def stop(self):
        self._running = False
        with self._lock:
            self._cancel_timeout_timer()
        if self._process:
            try:
                self._process.terminate()
            except Exception:
                pass

    def _send_mode(self, mode: str):
        if self._process and self._process.stdin:
            try:
                logger.info(f"Sending mode to SAPI: {mode}")
                self._process.stdin.write(f"{mode}\n")
                self._process.stdin.flush()
            except Exception as e:
                logger.error(f"Failed to send mode {mode} to SAPI: {e}")

    def pause(self):
        self._send_mode("MODE:PAUSE")

    def resume(self):
        self._send_mode("MODE:WAKE")

    def _start_timeout_timer(self):
        with self._lock:
            self._cancel_timeout_timer()
            self._command_timer = threading.Timer(8.0, self._on_timeout)
            self._command_timer.daemon = True
            self._command_timer.start()
            logger.info("Command timeout timer started (8s).")

    def listen_for_command(self):
        threading.Thread(target=self._record_and_transcribe, daemon=True).start()

    def _record_and_transcribe(self):
        import sounddevice as sd
        import soundfile as sf
        from executors.voice import transcribe_voice
        import asyncio
        import os
        import numpy as np
        from faster_whisper.vad import get_vad_model
        import warnings
        warnings.filterwarnings("ignore")
        
        fs = 16000
        logger.info('Recording started (Silero VAD)...')
        recording = []
        chunk_size = 512
        max_duration = 15
        
        try:
            vad_model = get_vad_model()
            with sd.InputStream(samplerate=fs, channels=1, dtype='float32') as stream:
                has_spoken = False
                silence_chunks = 0
                max_silence_chunks = int(1.5 * fs / chunk_size)  # 1.5 seconds of silence
                max_wait_chunks = int(8.0 * fs / chunk_size)     # 8 seconds max wait
                chunks_waited = 0
                
                for _ in range(int((fs / chunk_size) * max_duration)):
                    data, overflowed = stream.read(chunk_size)
                    audio_chunk = data.flatten()
                    recording.append(audio_chunk)
                    
                    # Get speech probability from Silero VAD
                    speech_prob = vad_model(audio_chunk)[0]
                    
                    if speech_prob > 0.2:
                        has_spoken = True
                        silence_chunks = 0
                    else:
                        if has_spoken:
                            silence_chunks += 1
                        else:
                            chunks_waited += 1
                            
                    if has_spoken and silence_chunks > max_silence_chunks:
                        logger.info('Silence detected after speech (Silero VAD). Stopping record.')
                        break
                        
                    if not has_spoken and chunks_waited > max_wait_chunks:
                        logger.info('User did not speak within 8 seconds. Cancelling.')
                        break
        except Exception as e:
            logger.error(f'Recording error: {e}')
            self._on_command('')
            return
            
        logger.info('Recording complete.')
        
        try:
            audio_data = np.concatenate(recording, axis=0)
            temp_file = os.path.abspath('temp_dictation.wav')
            sf.write(temp_file, audio_data, fs, subtype='PCM_16')
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            text = loop.run_until_complete(transcribe_voice(temp_file))
            loop.close()
            
            logger.info(f'Whisper transcribed: {text}')
            
            if os.path.exists(temp_file):
                os.remove(temp_file)
                
            if text and text.strip():
                self._on_command(text)
            else:
                self._on_command('')
                
        except Exception as e:
            logger.error(f'Transcription error: {e}')
            self._on_command('')

    def _run(self):
        try:
            self._process = subprocess.Popen(
                ["powershell", "-NoProfile", "-Command", _PS_SCRIPT],
                stdout=subprocess.PIPE,
                stdin=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            logger.info("Windows Speech Recognition engine running with SapiBridge.")

            for line in self._process.stdout:
                if not self._running:
                    break
                line_str = line.strip()
                if line_str.startswith("RECOGNIZED|"):
                    parts = line_str.split("|", 3)
                    if len(parts) < 4:
                        continue
                    grammar_name = parts[1]
                    try:
                        confidence = float(parts[2])
                    except ValueError:
                        confidence = 0.0
                    text = parts[3].strip()

                    logger.info(f"SAPI Heard [{grammar_name}] (conf: {confidence:.2f}): {text}")

                    if grammar_name == "WakeGrammar":
                        if text.lower() == "whis" and confidence < 0.70:
                            logger.info(f"Ignored '{text}' due to strict confidence ({confidence:.2f} < 0.70)")
                            continue
                        elif confidence < 0.65:
                            logger.info(f"Ignored wake word '{text}' due to low confidence ({confidence:.2f})")
                            continue
                            
                        logger.info("Wake word detected! Pausing SAPI...")
                        self._send_mode("MODE:PAUSE")
                        self._on_wake(text)

        except Exception as e:
            logger.error(f"VoiceTrigger error: {e}")
            if self._on_error:
                self._on_error(str(e))

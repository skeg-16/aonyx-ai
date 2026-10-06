"""Aonyx voice engine (Phase 10.6).

INPUT :  PortAudio mic stream -> (callback only enqueues) -> VAD/processing thread
         -> faster-whisper (own thread) -> TRANSCRIPT event.
OUTPUT:  LLM segments -> edge-tts (WordBoundary, concurrent + prefetched) -> decoded PCM
         -> ONE sounddevice OutputStream whose callback pulls ready segments in order
         (gapless by construction). The callback is the *timing source*: segment start/end,
         playback position and RMS are all derived from frames actually handed to the device,
         shifted by the measured output latency, so UI text/word highlighting follows the audio.

All events leave through `api_callback(event_type, data)`:
    STATE, RMS_UPDATE, MIC_STATUS, NO_SPEECH, TRANSCRIPT, VOICE_READY, VOICE_ERROR, TTS_ERROR,
    SEG_START, SEG_END, SEG_INSTANT, SPEECH_TICK, UTT_DONE, UTT_END
"""
import asyncio
import io
import logging
import math
import os
import queue
import tempfile
import threading
import time
from collections import deque

import numpy as np
import sounddevice as sd
import soundfile as sf
import edge_tts
from faster_whisper import WhisperModel

logger = logging.getLogger("voice")

MIC_RATE = 16000
MIC_BLOCK_S = 0.032                     # 512 samples @ 16 kHz
TTS_NATIVE_SR = 24000                   # edge-tts mp3 output rate
TTS_MAX_PARALLEL = 3                    # concurrent synthesis jobs (prefetch depth)


def level_from_amp(rms: float) -> int:
    """Map linear RMS amplitude (0..1) to a perceptual 0..100 level (-50 dB .. -10 dB)."""
    if not rms or rms <= 1e-6 or math.isnan(rms):
        return 0
    db = 20.0 * math.log10(rms)
    return int(max(0.0, min(1.0, (db + 50.0) / 40.0)) * 100)


class _Seg:
    __slots__ = ("uid", "idx", "text", "nl", "state", "pcm", "sr", "words", "dur",
                 "epoch", "task", "t_enq", "t_ready", "synth_s")

    def __init__(self, uid, idx, text, nl, epoch):
        self.uid, self.idx, self.text, self.nl, self.epoch = uid, idx, text, nl, epoch
        self.state = "pending"   # pending -> ready | failed | cancelled
        self.pcm = None
        self.sr = TTS_NATIVE_SR
        self.words = []
        self.dur = 0.0
        self.task = None
        self.t_enq = time.monotonic()
        self.t_ready = None
        self.synth_s = 0.0


def _align_words(text: str, words):
    """Map edge-tts word boundaries (which drop punctuation) back onto character ranges of `text`."""
    out, pos = [], 0
    low = text.lower()
    for (s, e, w) in words:
        i = text.find(w, pos)
        if i < 0:
            i = low.find(w.lower(), pos)
        if i < 0:
            continue
        out.append({"cs": i, "ce": i + len(w), "s": round(s, 3), "e": round(e, 3)})
        pos = i + len(w)
    return out


class VoiceEngine:
    def __init__(self, api_callback):
        self.api_callback = api_callback
        self._shutdown = False

        # ---------------- microphone / STT state ----------------
        self.mic_state = "INIT"
        self._mic_device = None
        self._mic_rate = MIC_RATE
        self._mic_q = queue.Queue(maxsize=400)
        self._last_cb = 0.0
        self._overflows = 0
        self.noise_floor = None            # int16-scale RMS
        self.min_threshold = 160.0
        self.is_listening = False
        self._listen_lock = threading.RLock()
        self._reset_listen()
        self.stt_model = None
        self.model_loaded = False
        self._stt_lock = threading.Lock()

        # ---------------- TTS state ----------------
        self.tts_voice = "en-US-AriaNeural"
        self.tts_rate = "+0%"
        self.volume = 1.0
        self._lock = threading.Lock()
        self._pending = deque()
        self._cur = None                   # [seg, pos_frames]
        self._epoch = 0
        self._uid = None
        self._utt_final = True
        self._utt_cancelled = False
        self._done_emitted = True
        self._stats = {}
        self._evq = queue.SimpleQueue()
        self._inflight = 0                 # events posted but not yet delivered to the UI
        self._hist = deque(maxlen=96)      # (due_wall, pos0_s, level, uid, idx, block_s)
        self._frames_played = 0
        self._stream = None
        self._out_sr = TTS_NATIVE_SR
        self._out_lat = 0.1
        self._last_activity = time.monotonic()
        self._tts_error_reported = False
        self._tts_loop = None
        self._tts_loop_ready = threading.Event()

        for name, fn in (("stt-load", self._load_stt_model), ("mic-capture", self._mic_loop),
                         ("mic-proc", self._mic_proc_loop), ("tts-synth", self._tts_thread_main),
                         ("tts-events", self._event_loop)):
            threading.Thread(target=fn, name=name, daemon=True).start()

    # ======================================================================================
    # STT model
    # ======================================================================================
    def _load_stt_model(self):
        logger.info("[STT] loading faster-whisper base.en ...")
        try:
            self.stt_model = WhisperModel("base.en", device="cpu", compute_type="int8")
            self.model_loaded = True
            logger.info("[STT] model loaded.")
            self.api_callback("VOICE_READY", None)
        except Exception as e:
            logger.error(f"[STT] failed to load model: {e}")
            self.api_callback("VOICE_ERROR", f"STT Load Error: {e}")

    # ======================================================================================
    # Microphone: device handling + capture
    # ======================================================================================
    def _set_mic_status(self, state, detail=""):
        if state != self.mic_state:
            logger.info(f"[MIC] status {self.mic_state} -> {state} {detail}")
        self.mic_state = state
        self.api_callback("MIC_STATUS", {"state": state, "detail": detail})

    def _resolve_input_device(self):
        try:
            d = sd.default.device[0]
            if d is not None and d >= 0:
                info = sd.query_devices(d)
                if info["max_input_channels"] > 0:
                    return d
        except Exception as e:
            logger.warning(f"[MIC] default input unusable: {e}")
        try:
            for i, info in enumerate(sd.query_devices()):
                if info["max_input_channels"] > 0:
                    logger.info(f"[MIC] falling back to input device {i}: {info['name']}")
                    return i
        except Exception as e:
            logger.error(f"[MIC] device enumeration failed: {e}")
        return None

    def _refresh_devices(self):
        """Re-scan PortAudio devices (only safe while no stream is open)."""
        if self._stream is not None:
            return  # an output stream exists; terminating PortAudio would invalidate it
        try:
            sd._terminate()
            sd._initialize()
        except Exception as e:
            logger.warning(f"[MIC] PortAudio refresh failed: {e}")

    def _mic_loop(self):
        logger.info("[MIC] capture thread started")
        while not self._shutdown:
            dev = self._resolve_input_device()
            if dev is None:
                self._set_mic_status("NO_DEVICE", "No input device found")
                time.sleep(3.0)
                self._refresh_devices()
                continue
            try:
                self._run_mic_stream(dev)
            except Exception as e:
                logger.error(f"[MIC] stream failed: {e}")
                self._set_mic_status("ERROR", str(e))
                time.sleep(3.0)
                self._refresh_devices()

    def _run_mic_stream(self, dev):
        info = sd.query_devices(dev)
        logger.info(f"[MIC] using device {dev}: {info['name']} (ch={info['max_input_channels']}, "
                    f"default_sr={info['default_samplerate']})")
        rates = [MIC_RATE]
        native = int(info["default_samplerate"])
        if native != MIC_RATE:
            rates.append(native)
        last_err = None
        for rate in rates:
            try:
                block = int(rate * MIC_BLOCK_S)

                def cb(indata, frames, time_info, status):
                    if status:
                        self._overflows += 1
                    self._last_cb = time.monotonic()
                    try:
                        self._mic_q.put_nowait(indata[:, 0].copy())
                    except queue.Full:
                        pass

                with sd.InputStream(device=dev, samplerate=rate, channels=1, dtype="float32",
                                    blocksize=block, callback=cb):
                    self._mic_device, self._mic_rate = dev, rate
                    self._last_cb = time.monotonic()
                    logger.info(f"[MIC] stream open at {rate} Hz, blocksize={block}")
                    self._set_mic_status("READY", info["name"])
                    last_log = time.monotonic()
                    while not self._shutdown:
                        time.sleep(0.25)
                        now = time.monotonic()
                        if now - self._last_cb > 2.5:
                            raise RuntimeError("microphone delivered no audio frames for 2.5s")
                        if self._overflows and now - last_log > 5:
                            logger.warning(f"[MIC] {self._overflows} input over/underflow flags (non-fatal)")
                            self._overflows, last_log = 0, now
                return
            except Exception as e:
                last_err = e
                logger.warning(f"[MIC] open at {rate} Hz failed: {e}")
        raise last_err if last_err else RuntimeError("could not open microphone")

    def _to_16k(self, x: np.ndarray) -> np.ndarray:
        if self._mic_rate == MIC_RATE:
            return x
        ratio = self._mic_rate / MIC_RATE
        if abs(ratio - round(ratio)) < 1e-6 and len(x) % int(round(ratio)) == 0:
            return x.reshape(-1, int(round(ratio))).mean(axis=1)
        n = int(len(x) / ratio)
        return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)

    # ---------------- VAD / listening session ----------------
    def _reset_listen(self):
        self.audio_frames = []
        self._speech_run = 0
        self._speech_started = False
        self._silence_s = 0.0
        self._listen_t0 = 0.0
        self._waiting_flagged = False
        self._peak = 0.0
        self._listen_blocks = 0

    def start_listening(self):
        if self.mic_state in ("NO_DEVICE", "ERROR"):
            self.api_callback("VOICE_ERROR", f"MIC // {self.mic_state.replace('_', ' ')}")
            return False
        if self.mic_state == "INIT":
            self.api_callback("VOICE_ERROR", "Microphone is still initialising.")
            return False
        if not self.model_loaded:
            self.api_callback("VOICE_ERROR", "Voice engine still loading.")
            return False
        self.interrupt_tts()
        with self._listen_lock:
            self._reset_listen()
            self._listen_t0 = time.monotonic()
            self.is_listening = True
        logger.info(f"[MIC] listening started (noise floor={self.noise_floor}, "
                    f"threshold={self._threshold():.0f})")
        self._set_mic_status("LISTENING")
        return True

    def stop_listening(self):
        """Compatibility shim: stop capturing and process what was recorded."""
        self.stop_and_process()

    def stop_and_process(self, reason="manual"):
        with self._listen_lock:
            if not self.is_listening:
                return
            self.is_listening = False
            frames, started, peak = self.audio_frames, self._speech_started, self._peak
            thr = self._threshold()
            self.audio_frames = []
        self._set_mic_status("READY")
        self.api_callback("RMS_UPDATE", 0)
        if not frames:
            logger.info("[MIC] listening ended with no audio frames captured")
            self.api_callback("NO_SPEECH", {"reason": "no_audio"})
            return
        if not started and peak < thr * 0.8:
            logger.info(f"[VAD] MIC AVAILABLE BUT NO SPEECH DETECTED ({reason}): peak_rms={peak:.0f} thr={thr:.0f}")
            self.api_callback("NO_SPEECH", {"reason": "no_speech", "peak": int(peak), "thr": int(thr)})
            return
        self.api_callback("STATE", "THINKING")
        audio = np.concatenate(frames).astype(np.float32)
        threading.Thread(target=self._transcribe, args=(audio,), name="stt-worker", daemon=True).start()

    def _threshold(self):
        nf = self.noise_floor if self.noise_floor is not None else 60.0
        return max(self.min_threshold, nf * 3.0)

    def _mic_proc_loop(self):
        while not self._shutdown:
            try:
                x = self._mic_q.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                x = self._to_16k(np.nan_to_num(x))
                rms = float(np.sqrt(np.mean(x.astype(np.float64) ** 2)))
                rms_i = rms * 32768.0
                if not self.is_listening:
                    if self.noise_floor is None:
                        self.noise_floor = rms_i
                    elif rms_i < max(self.noise_floor * 2.5, 120.0):
                        self.noise_floor = self.noise_floor * 0.98 + rms_i * 0.02
                    continue
                self._vad_step(x, rms, rms_i)
            except Exception as e:
                logger.error(f"[MIC] processing error: {e}")

    def _vad_step(self, x, rms, rms_i):
        with self._listen_lock:
            if not self.is_listening:
                return
            self.audio_frames.append(x)
            self._listen_blocks += 1
            self._peak = max(self._peak, rms_i)
            self.api_callback("RMS_UPDATE", level_from_amp(rms))
            thr = self._threshold()
            elapsed = time.monotonic() - self._listen_t0
            finish = None
            if rms_i > thr:
                self._speech_run += 1
                self._silence_s = 0.0
                if self._speech_run >= 3 and not self._speech_started:
                    self._speech_started = True
                    self._waiting_flagged = False
                    logger.info(f"[VAD] speech detected (rms={rms_i:.0f} > thr={thr:.0f})")
                    self.api_callback("MIC_STATUS", {"state": "SPEECH", "detail": ""})
            else:
                self._speech_run = 0
                if self._speech_started:
                    self._silence_s += MIC_BLOCK_S
                    if self._silence_s >= 1.2:
                        finish = "silence"
                else:
                    if elapsed >= 4.0 and not self._waiting_flagged:
                        self._waiting_flagged = True
                        logger.info(f"[VAD] waiting for voice ({elapsed:.1f}s, peak={self._peak:.0f}, thr={thr:.0f})")
                        self.api_callback("MIC_STATUS", {"state": "WAITING", "detail": ""})
                    if elapsed >= 12.0:
                        finish = "timeout"
            if elapsed >= 30.0:
                finish = "max_length"
        if finish:
            logger.info(f"[VAD] stopping capture ({finish}); {self._listen_blocks * MIC_BLOCK_S:.1f}s captured")
            threading.Thread(target=self.stop_and_process, args=(finish,), name="vad-stop", daemon=True).start()

    def _transcribe(self, audio_np):
        with self._stt_lock:
            start_t = time.time()
            try:
                logger.info(f"[STT] transcribing {len(audio_np) / MIC_RATE:.1f}s of audio")
                segments, _ = self.stt_model.transcribe(audio_np, beam_size=1, vad_filter=True,
                                                        condition_on_previous_text=False)
                text = "".join(s.text for s in segments).strip()
                logger.info(f"[STT] latency {time.time() - start_t:.2f}s | text: '{text}'")
                if not text:
                    logger.info("[STT] SPEECH DETECTED BUT NOTHING TRANSCRIBED")
                    self.api_callback("NO_SPEECH", {"reason": "empty_transcript"})
                    return
                self.api_callback("TRANSCRIPT", text)
            except Exception as e:
                logger.error(f"[STT] TRANSCRIPTION FAILED: {e}")
                self.api_callback("VOICE_ERROR", "Speech recognition failed.")
                self.api_callback("STATE", "IDLE")

    # ======================================================================================
    # TTS: utterance / segment API
    # ======================================================================================
    def begin_utterance(self, uid):
        self.interrupt_tts(emit=False)
        with self._lock:
            self._uid = uid
            self._utt_final = False
            self._utt_cancelled = False
            self._done_emitted = False
            self._stats = {"segs": 0, "audio_s": 0.0, "underrun_s": 0.0, "max_gap_s": 0.0,
                           "t0": time.monotonic(), "first_audio_s": None, "synth": []}

    def end_utterance(self, uid):
        with self._lock:
            if uid != self._uid:
                return
            self._utt_final = True
        self._check_done()

    def is_busy(self):
        with self._lock:
            return bool(self._pending) or self._cur is not None

    def speak(self, text, uid=None, idx=0, nl=False):
        """Queue a speech segment. Returns False if the segment was shown text-only."""
        with self._lock:
            if uid is not None and uid != self._uid:
                return False
            cancelled = self._utt_cancelled
            seg = _Seg(self._uid, idx, text, nl, self._epoch)
            if not cancelled:
                self._pending.append(seg)
        if cancelled:
            self._post(("instant", seg, time.monotonic()))
            return False
        if not self._ensure_stream():
            with self._lock:
                try:
                    self._pending.remove(seg)
                except ValueError:
                    pass
            self._report_tts_error("No audio output device")
            self._post(("instant", seg, time.monotonic()))
            return False
        loop = self._tts_loop
        loop.call_soon_threadsafe(self._schedule, seg)
        return True

    def _post(self, ev):
        with self._lock:
            self._inflight += 1
        self._evq.put(ev)

    def interrupt_tts(self, emit=True):
        """Immediately silence playback and drop everything queued for the current utterance."""
        with self._lock:
            active_utt = self._uid is not None and not self._done_emitted and not self._utt_cancelled
            had = bool(self._pending) or self._cur is not None or active_utt
            segs = list(self._pending)
            if self._cur:
                segs.append(self._cur[0])
            self._epoch += 1
            self._pending.clear()
            self._cur = None
            self._utt_cancelled = True
            uid = self._uid
            self._hist.clear()
        stream = self._stream
        if stream is not None and had:
            try:
                if stream.active:
                    stream.abort()      # discards device buffers -> silence within a few ms
                    stream.start()
            except Exception as e:
                logger.warning(f"[TTS] stream abort failed: {e}")
        if segs and self._tts_loop is not None:
            self._tts_loop.call_soon_threadsafe(self._cancel_tasks, segs)
        if had:
            logger.info(f"[TTS] interrupted (uid={uid}, {len(segs)} segment(s) dropped)")
            self.api_callback("RMS_UPDATE", 0)
            if emit:
                self.api_callback("UTT_END", {"uid": uid, "reason": "interrupted"})
                # If the LLM already finished, report completion now; otherwise it is reported
                # by end_utterance() once the remaining text has been delivered text-only.
                self._check_done()

    # ======================================================================================
    # TTS: synthesis (asyncio thread)
    # ======================================================================================
    def _tts_thread_main(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._tts_loop = loop
        self._sem = asyncio.Semaphore(TTS_MAX_PARALLEL)
        self._tts_loop_ready.set()
        logger.info(f"[TTS] synthesis thread started (edge-tts {self.tts_voice}, parallel={TTS_MAX_PARALLEL})")
        loop.run_forever()

    def _schedule(self, seg):
        seg.task = self._tts_loop.create_task(self._synth(seg))

    def _cancel_tasks(self, segs):
        for s in segs:
            if s.task and not s.task.done():
                s.task.cancel()

    async def _edge_synth(self, text):
        comm = edge_tts.Communicate(text, self.tts_voice, rate=self.tts_rate, boundary="WordBoundary")
        audio, words = bytearray(), []
        async for ch in comm.stream():
            if ch["type"] == "audio":
                audio += ch["data"]
            elif ch["type"] == "WordBoundary":
                words.append((ch["offset"] / 1e7, (ch["offset"] + ch["duration"]) / 1e7, ch["text"]))
        if not audio:
            raise RuntimeError("edge-tts returned no audio")
        data, sr = sf.read(io.BytesIO(bytes(audio)), dtype="float32")
        if data.ndim > 1:
            data = data.mean(axis=1)
        return data, sr, words

    async def _synth(self, seg):
        epoch = seg.epoch
        try:
            async with self._sem:
                if epoch != self._epoch:
                    seg.state = "cancelled"
                    return
                t0 = time.monotonic()
                data = sr = words = None
                err = None
                for attempt in range(2):
                    try:
                        data, sr, words = await self._edge_synth(seg.text)
                        break
                    except asyncio.CancelledError:
                        raise
                    except Exception as e:
                        err = e
                        logger.warning(f"[TTS] edge-tts attempt {attempt + 1} failed: {e}")
                        if epoch != self._epoch:
                            return
                if data is None:
                    # Offline fallback: Windows SAPI (no word timing -> sentence-level sync only)
                    try:
                        data, sr = await asyncio.get_running_loop().run_in_executor(
                            None, self._sapi_synth, seg.text)
                        words = []
                        logger.warning("[TTS] using SAPI fallback voice for this segment")
                    except Exception as e2:
                        logger.error(f"[TTS] synthesis failed (edge: {err}; sapi: {e2})")
                        seg.state = "failed"
                        self._report_tts_error(str(err))
                        return
            if epoch != self._epoch:
                seg.state = "cancelled"
                return
            if sr != self._out_sr:
                n = int(len(data) * self._out_sr / sr)
                data = np.interp(np.linspace(0, len(data) - 1, n), np.arange(len(data)), data).astype(np.float32)
                sr = self._out_sr
            seg.pcm = np.ascontiguousarray(data, dtype=np.float32)
            seg.sr = sr
            seg.dur = len(seg.pcm) / sr
            seg.words = _align_words(seg.text, words)
            seg.synth_s = time.monotonic() - t0
            seg.t_ready = time.monotonic()
            with self._lock:
                ahead = sum(1 for s in self._pending if s.state == "ready")
                buffered = sum(s.dur for s in self._pending if s.state == "ready")
                self._stats.setdefault("synth", []).append(seg.synth_s)
            seg.state = "ready"  # published last
            logger.info(f"[TTS] seg {seg.idx} ready: synth={seg.synth_s:.2f}s audio={seg.dur:.2f}s "
                        f"words={len(seg.words)} queue_ahead={ahead} buffered={buffered:.1f}s "
                        f"| '{seg.text[:48]}'")
        except asyncio.CancelledError:
            seg.state = "cancelled"
            raise
        except Exception as e:
            logger.error(f"[TTS] unexpected synth error: {e}")
            seg.state = "failed"
            self._report_tts_error(str(e))

    def _sapi_synth(self, text):
        import pythoncom
        import win32com.client
        pythoncom.CoInitialize()
        try:
            voice = win32com.client.Dispatch("SAPI.SpVoice")
            stream = win32com.client.Dispatch("SAPI.SpFileStream")
            path = os.path.join(tempfile.gettempdir(), f"aonyx_sapi_{int(time.time() * 1000)}.wav")
            stream.Open(path, 3)
            voice.AudioOutputStream = stream
            voice.Speak(text)
            stream.Close()
            data, sr = sf.read(path, dtype="float32")
            try:
                os.remove(path)
            except OSError:
                pass
            if data.ndim > 1:
                data = data.mean(axis=1)
            return data, sr
        finally:
            pythoncom.CoUninitialize()

    def _report_tts_error(self, detail):
        if not self._tts_error_reported:
            self._tts_error_reported = True
            self.api_callback("TTS_ERROR", detail)

    # ======================================================================================
    # TTS: playback (PortAudio callback = timing source)
    # ======================================================================================
    def _ensure_stream(self):
        self._last_activity = time.monotonic()
        try:
            if self._stream is None:
                dev = sd.default.device[1]
                try:
                    sr = TTS_NATIVE_SR
                    self._stream = sd.OutputStream(samplerate=sr, channels=1, dtype="float32",
                                                   blocksize=512, latency="low", callback=self._out_cb)
                except Exception:
                    sr = int(sd.query_devices(dev)["default_samplerate"])
                    self._stream = sd.OutputStream(samplerate=sr, channels=1, dtype="float32",
                                                   blocksize=512, latency="low", callback=self._out_cb)
                self._out_sr = sr
                logger.info(f"[TTS] output stream created @ {sr} Hz on device {dev}, "
                            f"latency={self._stream.latency:.3f}s")
            if not self._stream.active:
                self._stream.start()
            self._out_lat = float(self._stream.latency)
            return True
        except Exception as e:
            logger.error(f"[TTS] cannot open audio output: {e}")
            self._stream = None
            return False

    def _out_cb(self, outdata, frames, time_info, status):
        out = outdata[:, 0]
        out[:] = 0.0
        now = time.monotonic()
        try:
            lat = time_info.outputBufferDacTime - time_info.currentTime
            if 0.0 < lat < 1.0:
                self._out_lat = lat
        except Exception:
            pass
        written = 0
        events = []
        underrun = 0
        with self._lock:
            pos0_s = None
            cur_uid = cur_idx = None
            while written < frames:
                if self._cur is None:
                    if not self._pending:
                        break
                    head = self._pending[0]
                    if head.state == "ready":
                        self._pending.popleft()
                        self._cur = [head, 0]
                        self._frames_played = 0
                        events.append(("start", head, now))
                    elif head.state in ("failed", "cancelled"):
                        self._pending.popleft()
                        events.append(("instant", head, now))
                        continue
                    else:
                        underrun = frames - written       # next segment not synthesised yet
                        break
                seg, pos = self._cur
                n = min(frames - written, len(seg.pcm) - pos)
                if pos0_s is None:
                    pos0_s = (pos - written) / seg.sr
                    cur_uid, cur_idx = seg.uid, seg.idx
                out[written:written + n] = seg.pcm[pos:pos + n] * self.volume
                pos += n
                written += n
                if pos >= len(seg.pcm):
                    events.append(("end", seg, now + written / seg.sr))
                    self._cur = None
                else:
                    self._cur[1] = pos
            if underrun and self._stats.get("segs", 0) > 0:
                self._stats["underrun_s"] = self._stats.get("underrun_s", 0.0) + underrun / self._out_sr
            self._inflight += len(events)
            if written:
                blk = out[:written]
                rms = float(np.sqrt(np.mean(blk * blk)))
                self._hist.append((now + self._out_lat, max(0.0, pos0_s or 0.0), level_from_amp(rms),
                                   cur_uid, cur_idx, written / self._out_sr))
        for ev in events:
            self._evq.put(ev)

    # ======================================================================================
    # TTS: event thread (delivers events at the moment the audio is actually audible)
    # ======================================================================================
    def _event_loop(self):
        due_list = []
        last_tick = 0.0
        last_seg_end_wall = None
        while not self._shutdown:
            try:
                while True:
                    kind, seg, t_cb = self._evq.get_nowait()
                    due = t_cb + (self._out_lat if kind in ("start", "end") else 0.0)
                    due_list.append((due, kind, seg))
            except queue.Empty:
                pass
            now = time.monotonic()
            if due_list:
                due_list.sort(key=lambda d: d[0])
                while due_list and due_list[0][0] <= now:
                    _, kind, seg = due_list.pop(0)
                    with self._lock:
                        self._inflight = max(0, self._inflight - 1)
                    if seg.epoch != self._epoch and kind != "instant":
                        continue
                    last_seg_end_wall = self._handle_seg_event(kind, seg, now, last_seg_end_wall)
            if now - last_tick >= 0.04:
                last_tick = now
                self._emit_tick(now)
            if self._stream is not None and now - self._last_activity > 6.0 and not self.is_busy():
                try:
                    if self._stream.active:
                        self._stream.stop()
                except Exception:
                    pass
            time.sleep(0.008)

    def _handle_seg_event(self, kind, seg, now, last_end):
        if kind == "start":
            self._last_activity = now
            if self._stats.get("first_audio_s") is None:
                self._stats["first_audio_s"] = now - self._stats.get("t0", now)
            gap = (now - last_end) if last_end else 0.0
            self._stats["segs"] = self._stats.get("segs", 0) + 1
            self._stats["audio_s"] = self._stats.get("audio_s", 0.0) + seg.dur
            self._stats["max_gap_s"] = max(self._stats.get("max_gap_s", 0.0), gap if last_end else 0.0)
            logger.info(f"[TTS] seg {seg.idx} PLAYBACK START dur={seg.dur:.2f}s gap_since_prev={gap * 1000:.0f}ms "
                        f"waited_for_audio={(now - seg.t_enq):.2f}s")
            self.api_callback("STATE", "SPEAKING")
            self.api_callback("SEG_START", {"uid": seg.uid, "idx": seg.idx, "dur": round(seg.dur, 3),
                                            "words": seg.words, "text": seg.text})
            return None
        if kind == "end":
            self._last_activity = now
            self.api_callback("SEG_END", {"uid": seg.uid, "idx": seg.idx})
            self._check_done()
            return now
        if kind == "instant":
            self.api_callback("SEG_INSTANT", {"uid": seg.uid, "idx": seg.idx})
            self._check_done()
        return last_end

    def _emit_tick(self, now):
        entry = None
        for h in reversed(self._hist):
            if h[0] <= now:
                entry = h
                break
        if entry is None:
            return
        due, pos0, level, uid, idx, blk = entry
        if now - due > 0.25:
            return                               # stale: nothing playing
        pos = pos0 + min(max(0.0, now - due), blk)
        self.api_callback("SPEECH_TICK", {"uid": uid, "idx": idx, "pos": round(pos, 3), "rms": level})

    def _check_done(self):
        emit = False
        with self._lock:
            if self._utt_final and not self._done_emitted and not self._pending \
                    and self._cur is None and self._inflight == 0:
                self._done_emitted = True
                emit, uid, st = True, self._uid, dict(self._stats)
        if emit:
            synth = st.get("synth") or [0.0]
            logger.info(f"[TTS] utterance {uid} complete: segs={st.get('segs', 0)} audio={st.get('audio_s', 0):.1f}s "
                        f"first_audio={(st.get('first_audio_s') or 0):.2f}s underrun={st.get('underrun_s', 0):.2f}s "
                        f"max_gap={st.get('max_gap_s', 0) * 1000:.0f}ms synth_avg={sum(synth) / len(synth):.2f}s "
                        f"synth_max={max(synth):.2f}s")
            self.api_callback("RMS_UPDATE", 0)
            self.api_callback("UTT_DONE", {"uid": uid, "stats": {k: v for k, v in st.items() if k != "synth"}})

    def shutdown(self):
        self._shutdown = True
        self.is_listening = False
        self.interrupt_tts(emit=False)
        try:
            if self._stream is not None:
                self._stream.close()
        except Exception:
            pass

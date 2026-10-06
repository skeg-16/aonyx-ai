"""Phase 10.6 backend tests: speech chunker + gapless TTS pipeline + interruption.

Run:  venv\\Scripts\\python.exe -m pytest test_phase10_6.py -s -v
NOTE: the audio tests speak through the real default output device and need internet (edge-tts).
"""
import time
import threading
import pytest

from app.speech_chunker import SpeechChunker, clean_for_speech


# ----------------------------------------------------------------------------- chunker
def _run(chunker, text, step=5):
    out = []
    for i in range(0, len(text), step):
        out += chunker.feed(text[i:i + step])
    out += chunker.flush()
    return out


def test_chunker_sentences_and_min_length():
    c = SpeechChunker()
    text = ("Hello, how can I help you today? I can search the web, inspect your desktop, "
            "or remember something for you. Just tell me what you need.")
    segs = _run(c, text)
    joined = " ".join(s for s, _ in segs)
    assert joined.replace("  ", " ") == text
    assert len(segs) >= 2
    assert segs[0][0].endswith("today?")


def test_chunker_decimals_and_abbreviations():
    c = SpeechChunker()
    segs = _run(c, "Dr. Smith paid 3.5 dollars for it. That was cheap for an e.g. sandwich, wasn't it?")
    texts = [s for s, _ in segs]
    assert not any(t.endswith("Dr.") or t.endswith("3.") for t in texts)


def test_chunker_newlines_flagged():
    c = SpeechChunker()
    segs = _run(c, "First line is here.\nSecond line follows right after it.")
    assert len(segs) == 2
    assert segs[1][1] is True


def test_chunker_long_run_split_at_clause():
    c = SpeechChunker()
    long = "this is a very long run of words without any sentence terminator " * 6 + "end."
    segs = _run(c, long, step=7)
    assert len(segs) >= 2
    assert all(len(s) < 400 for s, _ in segs)


def test_clean_for_speech():
    assert clean_for_speech("**Bold** and `code` see https://example.com now") == "Bold and code see now"
    assert clean_for_speech("```x=1```") == ""
    assert clean_for_speech("- item one") == "item one"


# ----------------------------------------------------------------------------- audio pipeline
@pytest.fixture(scope="module")
def engine():
    from app.voice import VoiceEngine
    events = []
    lock = threading.Lock()

    def cb(kind, data):
        with lock:
            events.append((time.monotonic(), kind, data))

    eng = VoiceEngine(cb)
    eng.events = events
    yield eng
    eng.shutdown()


def _wait(pred, timeout):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if pred():
            return True
        time.sleep(0.02)
    return False


SENTENCES = [
    "Hello Shawn, it's good to hear from you.",
    "I can search the web, inspect your desktop, or remember something for you.",
    "Tell me whatever you need and I will take care of it.",
]


def test_gapless_multi_segment_playback_with_word_timing(engine):
    engine.events.clear()
    engine.begin_utterance(1)
    for i, s in enumerate(SENTENCES):
        engine.speak(s, 1, i, False)
    engine.end_utterance(1)
    assert _wait(lambda: any(k == "UTT_DONE" for _, k, _ in engine.events), 40), "utterance never completed"

    starts = [(t, d) for t, k, d in engine.events if k == "SEG_START"]
    ends = [(t, d) for t, k, d in engine.events if k == "SEG_END"]
    ticks = [d for _, k, d in engine.events if k == "SPEECH_TICK"]
    assert len(starts) == 3 and len(ends) == 3
    # order: queued segments must start strictly in order
    assert [d["idx"] for _, d in starts] == [0, 1, 2]
    # word-level timing present for edge-tts and aligned to the text
    assert all(len(d["words"]) >= 4 for _, d in starts)
    # RMS is derived from real playback (non-zero while speaking)
    assert max(d["rms"] for d in ticks) > 20
    # positions advance monotonically within a segment
    for idx in (0, 1, 2):
        pos = [d["pos"] for d in ticks if d["idx"] == idx]
        assert pos == sorted(pos), "position regressed"
    # gap between the end of segment N and the start of N+1 (as heard) must be tiny
    # This precisely measures the inter-segment playback gap, distinguishing it from 
    # synthesis/network latency. If the queue starves, gap_ms will accurately spike.
    for (te, _), (ts, d) in zip(ends[:-1], starts[1:]):
        gap_ms = (ts - te) * 1000
        print(f"gap before seg {d['idx']}: {gap_ms:.0f} ms")
        assert gap_ms < 150


def test_interrupt_is_immediate_and_recoverable(engine):
    engine.events.clear()
    engine.begin_utterance(2)
    for i, s in enumerate(SENTENCES):
        engine.speak(s, 2, i, False)
    assert _wait(lambda: any(k == "SEG_START" for _, k, _ in engine.events), 15)
    time.sleep(0.4)
    t0 = time.monotonic()
    engine.interrupt_tts()
    took = (time.monotonic() - t0) * 1000
    print(f"interrupt call took {took:.0f} ms")
    assert took < 300
    assert not engine.is_busy()
    n_before = len([1 for _, k, _ in engine.events if k == "SEG_START"])
    # later text for the same (cancelled) utterance must NOT be spoken, only revealed
    engine.speak("This must never be spoken aloud.", 2, 9, False)
    engine.end_utterance(2)
    assert _wait(lambda: any(k == "UTT_DONE" for _, k, _ in engine.events), 5)
    time.sleep(0.5)
    assert len([1 for _, k, _ in engine.events if k == "SEG_START"]) == n_before
    assert any(k == "SEG_INSTANT" and d["idx"] == 9 for _, k, d in engine.events)
    assert any(k == "UTT_END" for _, k, _ in engine.events)

    # recovery: a new utterance speaks normally
    engine.events.clear()
    engine.begin_utterance(3)
    engine.speak("Ready again.", 3, 0, False)
    engine.end_utterance(3)
    assert _wait(lambda: any(k == "UTT_DONE" for _, k, _ in engine.events), 20)
    assert any(k == "SEG_START" for _, k, _ in engine.events)

import asyncio
import edge_tts
import time
from faster_whisper import WhisperModel
import os

async def generate_test_audio(text, filename, voice="en-PH-JamesNeural"):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(filename)

def test_model(model_name, filename):
    print(f"\n--- Testing Model: {model_name} ---")
    try:
        model = WhisperModel(model_name, device="cpu", compute_type="int8")
        start_time = time.time()
        segments, info = model.transcribe(filename, beam_size=5, language="en", condition_on_previous_text=False)
        text = " ".join([segment.text for segment in segments])
        elapsed = time.time() - start_time
        print(f"Result: '{text.strip()}'")
        print(f"Time: {elapsed:.2f}s")
        return text.strip()
    except Exception as e:
        print(f"Error: {e}")
        return ""

async def run_diagnostics():
    print("Generating accented test audio...")
    test_phrases = [
        "Hey whis, can you open spotify for me please?",
        "Computer, what is the weather like today?",
        "Whis, shut down the system.",
        "Hey whis, search google for the latest news."
    ]
    
    for i, phrase in enumerate(test_phrases):
        filename = f"test_phrase_{i}.mp3"
        await generate_test_audio(phrase, filename)
        print(f"\n[Phrase {i+1}]: {phrase}")
        test_model("distil-small.en", filename)
        test_model("base.en", filename)
        test_model("small.en", filename)
        if os.path.exists(filename):
            os.remove(filename)

if __name__ == "__main__":
    asyncio.run(run_diagnostics())

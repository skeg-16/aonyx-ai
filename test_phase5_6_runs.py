import asyncio
import sys
import os

# Add root to sys.path
sys.path.insert(0, os.path.abspath("."))

from app.orchestrator.provider import OllamaProvider
from app.orchestrator.engine import Orchestrator
from app.orchestrator.memory import manager as mem_manager

class SimpleMockUI:
    def __init__(self):
        self.state = "IDLE"
        self.output = ""
        self.orch = None

    def set_state(self, state):
        self.state = state

    def stream_text(self, chunk, full):
        self.output = full

    def show_tool_activity(self, name, status):
        print(f"    [TOOL] {name} -> {status}")

    def request_confirmation(self, name, args):
        print(f"    [CONFIRM] {name} - Auto-approving...")
        if self.orch:
            # Dispatch auto-approval
            asyncio.create_task(self.approve_later())

    async def approve_later(self):
        await asyncio.sleep(0.1)
        self.orch.provide_confirmation(True)

async def do_10_runs():
    print("Initializing Ollama Provider...")
    provider = OllamaProvider(model="llama3:latest")
    
    health = await provider.health_check()
    if not health:
        print("Ollama is not running. Start Ollama first.")
        return

    ui = SimpleMockUI()
    callbacks = {
        "set_state": ui.set_state,
        "show_tool_activity": ui.show_tool_activity,
        "request_confirmation": ui.request_confirmation,
        "stream_text": ui.stream_text
    }
    
    orch = Orchestrator(provider, callbacks)
    ui.orch = orch

    print("\n--- STARTING 10 TEST RUNS ---")
    
    test_prompts = [
        "What is 15 * 12?",
        "Store in memory that the secret code is ALPHA-99 as a SHORT_TERM memory.",
        "What time is it right now?",
        "What was the secret code I told you to remember?",
        "Calculate 100 / 4 and then tell me the current time.",
        "Tell me a short joke about a programmer.",
        "Remember that I like apples as a USER_PREF.",
        "Do you remember what I like?",
        "Store the fact that today's focus is Phase 6 in TASK memory.",
        "Retrieve my TASK memory to see what today's focus is."
    ]

    for i, prompt in enumerate(test_prompts, 1):
        print(f"\n[RUN {i}/10] User: {prompt}")
        ui.output = ""
        await orch.run(prompt)
        print(f"[RUN {i}/10] Aonyx: {ui.output}")

if __name__ == "__main__":
    asyncio.run(do_10_runs())

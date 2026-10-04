import asyncio
import os
import json
from .provider import LLMProvider
from .engine import Orchestrator
from .registry import registry
from .config import ALLOWED_FOLDERS

class MockProvider(LLMProvider):
    def __init__(self, sequence):
        self.sequence = sequence
        self.call_count = 0

    async def health_check(self) -> bool:
        return True

    async def generate_tool_or_response(self, messages, schemas):
        if self.call_count < len(self.sequence):
            item = self.sequence[self.call_count]
            self.call_count += 1
            if isinstance(item, dict) and "tool" in item:
                yield {"type": "tool_call", "tool": item["tool"], "arguments": item.get("arguments", {})}
            elif isinstance(item, dict) and "response" in item:
                yield {"type": "stream_chunk", "content": item["response"]}
                yield {"type": "full_response", "content": item["response"]}
            elif isinstance(item, dict) and "error" in item:
                yield item
        else:
            msg = "Mock sequence exhausted."
            yield {"type": "stream_chunk", "content": msg}
            yield {"type": "full_response", "content": msg}

class MockUI:
    def __init__(self):
        self.states = []
        self.messages = []
        self.activities = []
        self.confirms = []

    def get_callbacks(self):
        return {
            "set_state": lambda s: self.states.append(s),
            "show_tool_activity": lambda n, s: self.activities.append((n, s)),
            "request_confirmation": lambda n, a: self.confirms.append((n, a)),
            "stream_text": lambda c, f: self.messages.append(f)
        }

async def run_tests():
    print("--- UNIT TESTS ---")
    
    # Happy Path
    print("1. Happy Path: Time")
    ui = MockUI()
    provider = MockProvider([
        {"tool": "get_current_time", "arguments": {}},
        {"response": "The time is now."}
    ])
    orch = Orchestrator(provider, ui.get_callbacks())
    await orch.run("What time is it?")
    print("Activities:", ui.activities)
    print("Final states:", set(ui.states))

    # Schema Rejection
    print("\n2. Schema Rejection")
    ui = MockUI()
    provider = MockProvider([
        {"tool": "calculator", "arguments": {"expr": "1+1"}}, # Wrong key
        {"response": "Oops"}
    ])
    orch = Orchestrator(provider, ui.get_callbacks())
    await orch.run("Calculate")
    print("Activities:", ui.activities)
    
    # Unknown tool
    print("\n3. Unknown Tool")
    ui = TestUI()
    provider = MockProvider([
        {"tool": "hack_mainframe", "arguments": {}}, 
        {"response": "I can't."}
    ])
    orch = Orchestrator(provider, ui.get_callbacks())
    await orch.run("Hack it")
    print("Activities:", ui.activities)

    # Max Steps
    print("\n4. Max Steps limit")
    ui = MockUI()
    provider = MockProvider([
        {"tool": "get_current_time", "arguments": {}} for _ in range(6)
    ])
    orch = Orchestrator(provider, ui.get_callbacks())
    await orch.run("Time loop")
    print("Max steps triggered:", "Max tool steps reached" in ui.messages[-1] if ui.messages else False)

    print("\n--- SECURITY TESTS ---")
    
    # Path Traversal
    print("1. Path Traversal")
    ui = MockUI()
    provider = MockProvider([
        {"tool": "read_file", "arguments": {"file_path": os.path.join(ALLOWED_FOLDERS[0], "..", "..", "Windows", "System32")}},
        {"response": "Blocked"}
    ])
    orch = Orchestrator(provider, ui.get_callbacks())
    await orch.run("Read traversal")
    print("Activities:", ui.activities)
    
    # Read .env
    print("2. Read .env")
    ui = MockUI()
    provider = MockProvider([
        {"tool": "read_file", "arguments": {"file_path": os.path.join(ALLOWED_FOLDERS[0], ".env")}},
        {"response": "Blocked"}
    ])
    orch = Orchestrator(provider, ui.get_callbacks())
    await orch.run("Read env")
    print("Activities:", ui.activities)
    
    # JavaScript URL
    print("3. javascript: URL")
    ui = MockUI()
    provider = MockProvider([
        {"tool": "open_url", "arguments": {"url": "javascript:alert(1)"}},
        {"response": "Blocked"}
    ])
    orch = Orchestrator(provider, ui.get_callbacks())
    # We must auto-confirm for the test to proceed
    async def auto_confirm():
        await asyncio.sleep(0.1)
        orch.provide_confirmation(True)
    asyncio.create_task(auto_confirm())
    await orch.run("Open js")
    print("Activities:", ui.activities)
    
    # App Allowlist
    print("4. App Allowlist")
    ui = TestUI()
    provider = MockProvider([
        {"tool": "open_application", "arguments": {"app_name": "malware"}},
        {"response": "Blocked"}
    ])
    orch = Orchestrator(provider, ui.get_callbacks())
    asyncio.create_task(auto_confirm())
    await orch.run("Open malware")
    print("Activities:", ui.activities)
    
    # Malformed JSON
    print("5. Malformed JSON")
    ui = TestUI()
    provider = MockProvider([
        {"type": "error", "error": "Invalid JSON"},
        {"response": "Fixed"}
    ])
    orch = Orchestrator(provider, ui.get_callbacks())
    await orch.run("Send bad json")
    print("Messages sent to LLM:", [m["content"] for m in orch.messages if m["role"] == "user"])

    print("\nALL MOCK TESTS FINISHED.")

if __name__ == "__main__":
    asyncio.run(run_tests())

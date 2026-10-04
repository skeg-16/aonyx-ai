import asyncio
import os
import json
from .provider import LLMProvider
from .engine import Orchestrator
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

async def run_scenario(name, num, provider_seq, prompt, auto_confirm=None):
    print(f"{num}. {name}")
    ui = MockUI()
    provider = MockProvider(provider_seq)
    orch = Orchestrator(provider, ui.get_callbacks())
    
    if auto_confirm is not None:
        async def do_confirm():
            await asyncio.sleep(0.1)
            orch.provide_confirmation(auto_confirm)
        asyncio.create_task(do_confirm())
        
    await orch.run(prompt)
    print(f"  Activities: {ui.activities}")
    print(f"  Final Messages: {ui.messages[-1] if ui.messages else 'None'}\n")
    return True

async def run_tests():
    print("--- RUNNING 20 AI ORCHESTRATOR SCENARIOS ---")
    
    await run_scenario("Happy Path: Time", 1, [
        {"tool": "get_current_time", "arguments": {}},
        {"response": "The time is now."}
    ], "What time is it?")

    await run_scenario("Schema Rejection (Wrong Key)", 2, [
        {"tool": "calculator", "arguments": {"expr": "1+1"}}, 
        {"response": "Fixed the input."}
    ], "Calculate")

    await run_scenario("Calculator Happy Path", 3, [
        {"tool": "calculator", "arguments": {"expression": "2+2"}}, 
        {"response": "It is 4."}
    ], "2+2")

    await run_scenario("Unknown Tool Call", 4, [
        {"tool": "hack_mainframe", "arguments": {}}, 
        {"response": "Tool not found."}
    ], "Hack it")

    await run_scenario("Max Steps Limit", 5, [
        {"tool": "get_current_time", "arguments": {}} for _ in range(6)
    ], "Time loop")

    await run_scenario("Path Traversal Block", 6, [
        {"tool": "read_file", "arguments": {"file_path": os.path.join(ALLOWED_FOLDERS[0], "..", "System32")}},
        {"response": "Blocked traversal"}
    ], "Read traversal")

    await run_scenario("Read .env Block", 7, [
        {"tool": "read_file", "arguments": {"file_path": os.path.join(ALLOWED_FOLDERS[0], ".env")}},
        {"response": "Blocked .env"}
    ], "Read env")

    await run_scenario("JavaScript URL Block", 8, [
        {"tool": "open_url", "arguments": {"url": "javascript:alert(1)"}},
        {"response": "Blocked JS"}
    ], "Open js", auto_confirm=True)

    await run_scenario("Valid URL Open", 9, [
        {"tool": "open_url", "arguments": {"url": "https://example.com"}},
        {"response": "Opened site."}
    ], "Open example.com", auto_confirm=True)

    await run_scenario("App Allowlist Block (Malware)", 10, [
        {"tool": "open_application", "arguments": {"app_name": "malware"}},
        {"response": "Blocked malware"}
    ], "Open malware", auto_confirm=True)

    await run_scenario("Valid App Open (Notepad)", 11, [
        {"tool": "open_application", "arguments": {"app_name": "notepad"}},
        {"response": "Opened notepad."}
    ], "Open notepad", auto_confirm=True)

    await run_scenario("Malformed JSON Recovery", 12, [
        {"type": "error", "error": "Invalid JSON string"},
        {"response": "Recovered."}
    ], "Send bad json")

    await run_scenario("Invalid Tool Argument Types", 13, [
        {"tool": "calculator", "arguments": {"expression": 1234}}, 
        {"response": "Passed wrong type."}
    ], "Calc 1234")

    await run_scenario("Missing Required Arguments", 14, [
        {"tool": "calculator", "arguments": {}}, 
        {"response": "Missing arg."}
    ], "Calc missing")

    await run_scenario("Chain Tool Calls (Time then Calc)", 15, [
        {"tool": "get_current_time", "arguments": {}},
        {"tool": "calculator", "arguments": {"expression": "1+1"}},
        {"response": "Time and Math done."}
    ], "Do both")

    await run_scenario("User Denies Confirmation", 16, [
        {"tool": "open_url", "arguments": {"url": "https://google.com"}},
        {"response": "User denied."}
    ], "Open google", auto_confirm=False)

    await run_scenario("Empty Prompt", 17, [
        {"response": "You said nothing."}
    ], "")

    await run_scenario("Large Input String", 18, [
        {"response": "Got the large string."}
    ], "A" * 5000)

    await run_scenario("Mock Error Exception from Provider", 19, [
        {"type": "error", "error": "Timeout Error"},
        {"response": "Retry success."}
    ], "Trigger error")

    await run_scenario("Valid File Read (Safe path)", 20, [
        {"tool": "read_file", "arguments": {"file_path": os.path.join(ALLOWED_FOLDERS[0], "test.txt")}},
        {"response": "Read file safely."}
    ], "Read safe test.txt")

    print("\nALL 20 SCENARIOS COMPLETED.")

if __name__ == "__main__":
    asyncio.run(run_tests())

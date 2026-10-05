import json
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class ContextBuilder:
    def __init__(self):
        self.max_history_turns = 10
        self.context_categories = [
            "SYSTEM",
            "CURRENT_CONVERSATION",
            "RELEVANT_MEMORY",
            "DESKTOP_CONTEXT",
            "TOOL_RESULTS",
            "WEB_CONTEXT",
            "TASK_STATE"
        ]

    def _extract_keywords(self, text: str) -> List[str]:
        # Extremely simple keyword extractor for SQLite LIKE queries
        words = text.lower().replace('?', ' ').replace('.', ' ').replace(',', ' ').split()
        stop_words = {'what', 'is', 'the', 'my', 'a', 'an', 'and', 'or', 'to', 'for', 'in', 'of', 'on', 'with', 'can', 'you', 'i', 'me', 'it', 'do', 'does', 'how', 'who', 'where', 'when', 'why'}
        return [w for w in words if len(w) > 3 and w not in stop_words]

    def _retrieve_relevant_memory(self, user_text: str) -> str:
        from .memory import manager
        keywords = self._extract_keywords(user_text)
        if not keywords:
            return ""

        memories = []
        for kw in keywords:
            res = manager.retrieve_memory(kw)
            if "No matching" not in res and "Failed" not in res:
                # The result is formatted lines like "- [ID: X] [CAT] Content"
                for line in res.split('\n'):
                    if line and line not in memories:
                        memories.append(line)
            if len(memories) >= 5:
                break
                
        if not memories:
            return ""
            
        mem_text = "\n".join(memories[:5])
        return (
            "--- RELEVANT_MEMORY ---\n"
            "(These are facts about the user or past context pulled automatically from your memory DB. Trust newer facts over older conflicts.)\n"
            f"{mem_text}\n"
            "-----------------------\n"
        )

    def _retrieve_desktop_context(self) -> str:
        from .desktop_tools import get_active_window
        res = get_active_window({})
        if res["status"] == "ok":
            app = res["data"].get("application", "Unknown")
            title = res["data"].get("title", "Unknown")
            return (
                "--- DESKTOP_CONTEXT ---\n"
                "(Ephemeral state of the user's computer. Do NOT save to memory unless asked.)\n"
                f"Active Application: {app}\n"
                f"Active Window Title: {title}\n"
                "-----------------------\n"
            )
        return ""

    def _format_message(self, msg: Dict[str, str], is_last_user: bool) -> Dict[str, str]:
        if msg["role"] == "user":
            content = msg["content"]
            # If this is the active user turn, we attach the context
            if is_last_user:
                # We inject relevant memory and desktop context
                memory_block = self._retrieve_relevant_memory(content)
                desktop_block = self._retrieve_desktop_context()
                
                injected_context = ""
                if memory_block: injected_context += memory_block + "\n"
                if desktop_block: injected_context += desktop_block + "\n"
                
                if injected_context:
                    content = f"{injected_context}--- USER REQUEST ---\n{content}\n--------------------\n"
                
            return {"role": "user", "content": content}
        return msg

    def build_context(self, system_prompt: str, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Takes raw messages and builds a strictly bounded, context-separated prompt.
        """
        api_messages = [{"role": "system", "content": system_prompt}]
        
        recent_messages = messages[-self.max_history_turns:]
        
        for i, msg in enumerate(recent_messages):
            is_last_user = (i == len(recent_messages) - 1) and (msg["role"] == "user")
            
            # Truncate old tool results (if it's not the very last message in a tool loop)
            # A tool result is formatted as a user message starting with --- TOOL RESULT
            if msg["role"] == "user" and msg["content"].startswith("--- TOOL RESULT") and i < len(recent_messages) - 2:
                # We keep a tiny snippet so the LLM remembers it ran the tool, but not the 100KB payload.
                # Find the status line and cut the rest.
                lines = msg["content"].split('\n')
                short_content = "\n".join(lines[:3]) + "\n...(data truncated for context size)...\n--- END TOOL RESULT ---\n"
                msg = {"role": "user", "content": short_content}
                
            # Format and inject boundaries
            formatted_msg = self._format_message(msg, is_last_user)
            api_messages.append(formatted_msg)
            
        return api_messages

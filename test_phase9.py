import unittest
from unittest.mock import patch, MagicMock
from app.orchestrator.context_builder import ContextBuilder

class TestPhase9ContextBuilder(unittest.TestCase):
    
    @patch('app.orchestrator.memory.manager.retrieve_memory')
    def test_a_relevant_memory_retrieval(self, mock_retrieve):
        mock_retrieve.return_value = "- [ID: 1] [USER_PREF] Favorite color is blue (Tags: )"
        
        builder = ContextBuilder()
        memory_block = builder._retrieve_relevant_memory("what is my favorite color?")
        
        self.assertIn("Favorite color is blue", memory_block)
        self.assertIn("RELEVANT_MEMORY", memory_block)
        
    @patch('app.orchestrator.memory.manager.retrieve_memory')
    def test_b_no_irrelevant_memory(self, mock_retrieve):
        mock_retrieve.return_value = "No matching memories found."
        
        builder = ContextBuilder()
        memory_block = builder._retrieve_relevant_memory("just a normal question")
        
        self.assertEqual(memory_block, "")

    @patch('app.orchestrator.desktop_tools.get_active_window')
    def test_c_desktop_context(self, mock_gaw):
        mock_gaw.return_value = {
            "status": "ok",
            "data": {"application": "Code.exe", "title": "myproject - VS Code"}
        }
        
        builder = ContextBuilder()
        desktop_block = builder._retrieve_desktop_context()
        
        self.assertIn("DESKTOP_CONTEXT", desktop_block)
        self.assertIn("Code.exe", desktop_block)

    @patch('app.orchestrator.context_builder.ContextBuilder._retrieve_relevant_memory')
    @patch('app.orchestrator.context_builder.ContextBuilder._retrieve_desktop_context')
    def test_d_context_builder_injection(self, mock_desktop, mock_memory):
        mock_memory.return_value = "--- RELEVANT_MEMORY ---\nTest memory\n-----------------------\n"
        mock_desktop.return_value = "--- DESKTOP_CONTEXT ---\nTest desktop\n-----------------------\n"
        
        builder = ContextBuilder()
        messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
            {"role": "user", "content": "latest question"}
        ]
        
        built = builder.build_context("SYSTEM PROMPT", messages)
        
        self.assertEqual(len(built), 4) # System + 3 messages
        self.assertEqual(built[0]["role"], "system")
        self.assertEqual(built[0]["content"], "SYSTEM PROMPT")
        
        # Only the LAST user message gets context
        self.assertEqual(built[1]["content"], "hello")
        
        last_msg = built[3]["content"]
        self.assertIn("Test memory", last_msg)
        self.assertIn("Test desktop", last_msg)
        self.assertIn("latest question", last_msg)

if __name__ == '__main__':
    unittest.main()

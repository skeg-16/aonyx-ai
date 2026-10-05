import unittest
from unittest.mock import patch, MagicMock
from app.orchestrator.web_tools import is_safe_url, fetch_webpage, search_web

class TestWebTools(unittest.TestCase):
    
    def test_is_safe_url(self):
        # Good URLs
        self.assertTrue(is_safe_url("https://www.google.com"))
        self.assertTrue(is_safe_url("http://example.com/path"))
        
        # Bad schemes
        self.assertFalse(is_safe_url("file:///etc/passwd"))
        self.assertFalse(is_safe_url("ftp://server.com"))
        self.assertFalse(is_safe_url("gopher://server.com"))
        
        # Bad hosts
        self.assertFalse(is_safe_url("http://localhost:8080"))
        self.assertFalse(is_safe_url("http://127.0.0.1"))
        self.assertFalse(is_safe_url("http://0.0.0.0"))
        self.assertFalse(is_safe_url("http://[::1]"))
        
    @patch('socket.gethostbyname')
    def test_is_safe_url_private_ips(self, mock_gethostbyname):
        # Mocking DNS resolution to a private IP
        mock_gethostbyname.return_value = "192.168.1.1"
        self.assertFalse(is_safe_url("http://my-internal-server.local"))
        
        mock_gethostbyname.return_value = "10.0.0.5"
        self.assertFalse(is_safe_url("http://database.internal"))
        
        mock_gethostbyname.return_value = "93.184.216.34" # Example public IP
        self.assertTrue(is_safe_url("http://example.com"))
        
    def test_fetch_webpage_ssrf_blocked(self):
        res = fetch_webpage({"url": "http://localhost:8000/admin"})
        self.assertEqual(res["status"], "error")
        self.assertIn("SSRF", res["summary"])
        
    def test_search_web_empty(self):
        res = search_web({})
        self.assertEqual(res["status"], "error")
        self.assertIn("Missing", res["summary"])

if __name__ == '__main__':
    unittest.main()

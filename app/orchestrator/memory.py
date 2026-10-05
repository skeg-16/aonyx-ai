import sqlite3
import time
from .config import MEMORY_DB_PATH

class MemoryManager:
    def __init__(self, db_path=MEMORY_DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        conn = self._get_conn()
        # Create a new table for structured memory (v2)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS memory_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                category TEXT,
                content TEXT,
                tags TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def store_memory(self, category: str, content: str, tags: str = "") -> str:
        valid_categories = ['SHORT_TERM', 'LONG_TERM', 'USER_PREF', 'TASK']
        cat = category.upper()
        if cat not in valid_categories:
            cat = 'LONG_TERM' # default fallback
        
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute('INSERT INTO memory_v2 (timestamp, category, content, tags) VALUES (?, ?, ?, ?)',
                        (time.time(), cat, content, tags))
            mem_id = cur.lastrowid
            conn.commit()
            conn.close()
            return f"Successfully stored memory (ID: {mem_id}) in {cat}: {content[:50]}..."
        except Exception as e:
            return f"Failed to store memory: {e}"

    def retrieve_memory(self, query: str, category: str = None) -> str:
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            
            sql = 'SELECT id, category, content, tags FROM memory_v2 WHERE (content LIKE ? OR tags LIKE ?)'
            params = [f"%{query}%", f"%{query}%"]
            
            if category:
                sql += ' AND category = ?'
                params.append(category.upper())
                
            sql += ' ORDER BY timestamp DESC LIMIT 10'
            
            cur.execute(sql, tuple(params))
            results = cur.fetchall()
            conn.close()
            
            if not results:
                return "No matching memories found."
                
            formatted = "\n".join([f"- [ID: {r[0]}] [{r[1]}] {r[2]} (Tags: {r[3]})" for r in results])
            return formatted
        except Exception as e:
            return f"Failed to retrieve memory: {e}"

    def update_memory(self, mem_id: int, content: str = None, category: str = None, tags: str = None) -> str:
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            
            updates = []
            params = []
            if content is not None:
                updates.append("content = ?")
                params.append(content)
            if category is not None:
                updates.append("category = ?")
                params.append(category.upper())
            if tags is not None:
                updates.append("tags = ?")
                params.append(tags)
                
            if not updates:
                return "Nothing to update."
                
            updates.append("timestamp = ?")
            params.append(time.time())
            
            params.append(mem_id)
            
            sql = f"UPDATE memory_v2 SET {', '.join(updates)} WHERE id = ?"
            cur.execute(sql, tuple(params))
            
            if cur.rowcount == 0:
                conn.close()
                return f"Memory ID {mem_id} not found."
                
            conn.commit()
            conn.close()
            return f"Successfully updated memory ID: {mem_id}"
        except Exception as e:
            return f"Failed to update memory: {e}"

    def delete_memory(self, mem_id: int) -> str:
        try:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute('DELETE FROM memory_v2 WHERE id = ?', (mem_id,))
            if cur.rowcount == 0:
                conn.close()
                return f"Memory ID {mem_id} not found."
            conn.commit()
            conn.close()
            return f"Successfully deleted memory ID: {mem_id}"
        except Exception as e:
            return f"Failed to delete memory: {e}"

# Global instance
manager = MemoryManager()

# Compatibility wrappers for tests
def remember(content: str, tags: str = "") -> str:
    return manager.store_memory('LONG_TERM', content, tags)

def retrieve(query: str) -> str:
    return manager.retrieve_memory(query)

def get_all_memories():
    try:
        conn = manager._get_conn()
        cur = conn.cursor()
        cur.execute('SELECT id, timestamp, category, content, tags FROM memory_v2 ORDER BY timestamp DESC')
        results = cur.fetchall()
        conn.close()
        # Ensure it acts roughly like a list of tuples or dicts
        # Previous schema: id, timestamp, content, tags
        # To not break api.py:
        out = []
        for r in results:
            # pack as: id, timestamp, f"[{r[2]}] {r[3]}", r[4]
            out.append((r[0], r[1], f"[{r[2]}] {r[3]}", r[4]))
        return out
    except Exception as e:
        return []

def delete_memory(mem_id: int):
    return "Successfully deleted" in manager.delete_memory(mem_id)

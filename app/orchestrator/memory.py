import sqlite3
import time
from .config import MEMORY_DB_PATH

def _get_conn():
    conn = sqlite3.connect(MEMORY_DB_PATH)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL,
            content TEXT,
            tags TEXT
        )
    ''')
    return conn

def remember(content: str, tags: str = "") -> str:
    try:
        conn = _get_conn()
        conn.execute('INSERT INTO memories (timestamp, content, tags) VALUES (?, ?, ?)', (time.time(), content, tags))
        conn.commit()
        conn.close()
        return f"Successfully remembered: {content[:50]}..."
    except Exception as e:
        return f"Failed to remember: {e}"

def retrieve(query: str) -> str:
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute('SELECT content, tags FROM memories WHERE content LIKE ? OR tags LIKE ? ORDER BY timestamp DESC LIMIT 10', 
                    (f"%{query}%", f"%{query}%"))
        results = cur.fetchall()
        conn.close()
        
        if not results:
            return "No matching memories found."
            
        formatted = "\n".join([f"- {r[0]} (Tags: {r[1]})" for r in results])
        return formatted
    except Exception as e:
        return f"Failed to retrieve memory: {e}"

def get_all_memories():
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute('SELECT id, timestamp, content, tags FROM memories ORDER BY timestamp DESC')
        results = cur.fetchall()
        conn.close()
        return results
    except Exception as e:
        return []
        
def delete_memory(mem_id: int):
    try:
        conn = _get_conn()
        conn.execute('DELETE FROM memories WHERE id = ?', (mem_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        return False

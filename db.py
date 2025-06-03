import sqlite3

DB_PATH = "chat_history.sqlite3"

def create_history_table():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model TEXT,
            user_input TEXT,
            assistant_response TEXT,
            sources TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_chat_to_db(model, user_input, assistant_response, sources=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO history (model, user_input, assistant_response, sources) VALUES (?, ?, ?, ?)",
              (model, user_input, assistant_response, sources))
    conn.commit()
    conn.close()

def load_chat_history():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, model, user_input, assistant_response, sources FROM history ORDER BY id ASC")
    rows = c.fetchall()
    conn.close()
    return rows

def delete_all_history():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM history")
    conn.commit()
    conn.close()
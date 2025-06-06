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

def create_tag_table():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS document_tags (
            file_name TEXT PRIMARY KEY,
            tags TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_tags_for_file(file_name, tags):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    tags_str = ",".join(tags)
    c.execute("REPLACE INTO document_tags (file_name, tags) VALUES (?, ?)", (file_name, tags_str))
    conn.commit()
    conn.close()

def get_tags_for_file(file_name):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT tags FROM document_tags WHERE file_name = ?", (file_name,))
    row = c.fetchone()
    conn.close()
    return row[0].split(",") if row and row[0] else []

def get_all_tags():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT tags FROM document_tags")
    rows = c.fetchall()
    conn.close()
    tag_set = set()
    for row in rows:
        if row[0]:
            tag_set.update(tag.strip() for tag in row[0].split(","))
    return sorted(tag_set)

def create_notes_table():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS document_notes (
            file_name TEXT PRIMARY KEY,
            note TEXT,
            favorite INTEGER
        )
    """)
    conn.commit()
    conn.close()

def save_document_note(file_name, note, favorite):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("REPLACE INTO document_notes (file_name, note, favorite) VALUES (?, ?, ?)",
              (file_name, note, int(favorite)))
    conn.commit()
    conn.close()

def get_document_note(file_name):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT note, favorite FROM document_notes WHERE file_name = ?", (file_name,))
    row = c.fetchone()
    conn.close()
    return row if row else ("", 0)

def create_lai_table():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS perguntas_lai (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pergunta TEXT,
            data_envio TEXT,
            data_limite_resposta TEXT,
            origem TEXT,
            destinatario TEXT,
            orgao_recursal_1 TEXT,
            site_orgao_recursal_1 TEXT,
            texto_recurso_1 TEXT,
            orgao_recursal_2 TEXT,
            site_orgao_recursal_2 TEXT,
            texto_recurso_2 TEXT,
            tag TEXT,
            transparencia_ativa INTEGER,
            observacao_privada TEXT
        )
    """)
    conn.commit()
    conn.close()

import sqlite3
import os
import json
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("VALTR_DB", os.path.join(BASE_DIR, "vault.db"))

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Table to store master password verification data
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    # Table to store secure notes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            encrypted_content TEXT NOT NULL,
            tags TEXT DEFAULT '[]',
            nonce TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            is_hidden INTEGER DEFAULT 1
        )
    ''')
    
    # Try to add tags column to existing db if it was created before
    try:
        cursor.execute("ALTER TABLE notes ADD COLUMN tags TEXT DEFAULT '[]'")
    except sqlite3.OperationalError:
        pass
        
    try:
        cursor.execute("ALTER TABLE notes ADD COLUMN is_hidden INTEGER DEFAULT 1")
    except sqlite3.OperationalError:
        pass
        
    try:
        cursor.execute("ALTER TABLE passwords ADD COLUMN note_id INTEGER")
    except sqlite3.OperationalError:
        pass
        
    try:
        cursor.execute("ALTER TABLE passwords ADD COLUMN history TEXT DEFAULT '[]'")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE passwords ADD COLUMN category TEXT DEFAULT NULL")
    except sqlite3.OperationalError:
        pass
    
    # Table to store encrypted passwords
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS passwords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT NOT NULL,
            username TEXT NOT NULL,
            encrypted_password TEXT NOT NULL,
            nonce TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            ttl_days INTEGER,
            strength_score REAL
        )
    ''')
    
    try:
        cursor.execute('UPDATE passwords SET note_id = NULL WHERE note_id IS NOT NULL AND note_id NOT IN (SELECT id FROM notes)')
    except sqlite3.OperationalError:
        pass
        
    conn.commit()
    conn.close()

def save_config(key: str, value: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)', (key, value))
    conn.commit()
    conn.close()

def get_config(key: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT value FROM config WHERE key = ?', (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def is_vault_setup() -> bool:
    return get_config('salt') is not None

def add_password(domain: str, username: str, enc_pass: str, nonce: str, ttl_days: int, strength_score: float, note_id: int = None, history: str = '[]', category: str = None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute('''
        INSERT INTO passwords (domain, username, encrypted_password, nonce, created_at, updated_at, ttl_days, strength_score, note_id, history, category)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (domain, username, enc_pass, nonce, now, now, ttl_days, strength_score, note_id, history, category))
    conn.commit()
    conn.close()

def update_password(p_id: int, domain: str, username: str, enc_pass: str, nonce: str, ttl_days: int, strength_score: float, note_id: int = None, history: str = '[]', category: str = None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute('''
        UPDATE passwords 
        SET domain = ?, username = ?, encrypted_password = ?, nonce = ?, updated_at = ?, ttl_days = ?, strength_score = ?, note_id = ?, history = ?, category = ?
        WHERE id = ?
    ''', (domain, username, enc_pass, nonce, now, ttl_days, strength_score, note_id, history, category, p_id))
    conn.commit()
    conn.close()

def delete_password(p_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM passwords WHERE id = ?', (p_id,))
    conn.commit()
    conn.close()

def get_passwords():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id, domain, username, encrypted_password, nonce, created_at, updated_at, ttl_days, strength_score, note_id, history, category FROM passwords')
    rows = cursor.fetchall()
    conn.close()
    
    results = []
    for r in rows:
        results.append({
            "id": r[0],
            "domain": r[1],
            "username": r[2],
            "encrypted_password": r[3],
            "nonce": r[4],
            "created_at": r[5],
            "updated_at": r[6],
            "ttl_days": r[7],
            "strength_score": r[8],
            "note_id": r[9] if len(r) > 9 else None,
            "history": r[10] if len(r) > 10 and r[10] else '[]',
            "category": r[11] if len(r) > 11 else None
        })
    return results

def get_password_by_domain_user(domain: str, username: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, encrypted_password, nonce, created_at, updated_at, ttl_days, strength_score, note_id, history, category 
        FROM passwords 
        WHERE domain = ? AND username = ?
    ''', (domain, username))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "id": row[0],
            "encrypted_password": row[1],
            "nonce": row[2],
            "created_at": row[3],
            "updated_at": row[4],
            "ttl_days": row[5],
            "strength_score": row[6],
            "note_id": row[7] if len(row) > 7 else None,
            "history": row[8] if len(row) > 8 and row[8] else '[]',
            "category": row[9] if len(row) > 9 else None
        }
    return None

def get_categories():
    """Return list of distinct non-null categories from passwords."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT DISTINCT category FROM passwords WHERE category IS NOT NULL ORDER BY category')
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]

def rename_category_in_db(old_name: str, new_name: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('UPDATE passwords SET category = ? WHERE category = ?', (new_name, old_name))
    conn.commit()
    conn.close()

def delete_category_in_db(name: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('UPDATE passwords SET category = NULL WHERE category = ?', (name,))
    conn.commit()
    conn.close()

def add_note(title: str, enc_content: str, tags: str, nonce: str, is_hidden: bool = True):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute('''
        INSERT INTO notes (title, encrypted_content, tags, nonce, created_at, updated_at, is_hidden)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (title, enc_content, tags, nonce, now, now, int(is_hidden)))
    conn.commit()
    conn.close()

def update_note(n_id: int, title: str, enc_content: str, tags: str, nonce: str, is_hidden: bool = True):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute('''
        UPDATE notes 
        SET title = ?, encrypted_content = ?, tags = ?, nonce = ?, updated_at = ?, is_hidden = ?
        WHERE id = ?
    ''', (title, enc_content, tags, nonce, now, int(is_hidden), n_id))
    conn.commit()
    conn.close()

def delete_note(n_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('UPDATE passwords SET note_id = NULL WHERE note_id = ?', (n_id,))
    cursor.execute('DELETE FROM notes WHERE id = ?', (n_id,))
    conn.commit()
    conn.close()

def get_notes():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id, title, encrypted_content, tags, nonce, created_at, updated_at, is_hidden FROM notes')
    rows = cursor.fetchall()
    conn.close()
    
    results = []
    for r in rows:
        results.append({
            "id": r[0],
            "title": r[1],
            "encrypted_content": r[2],
            "tags": r[3],
            "nonce": r[4],
            "created_at": r[5],
            "updated_at": r[6],
            "is_hidden": bool(r[7] if r[7] is not None else 1)
        })
    return results

def get_note_by_title(title: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, encrypted_content, tags, nonce, created_at, updated_at, is_hidden
        FROM notes 
        WHERE title = ?
    ''', (title,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "id": row[0],
            "encrypted_content": row[1],
            "tags": row[2],
            "nonce": row[3],
            "created_at": row[4],
            "updated_at": row[5],
            "is_hidden": bool(row[6] if row[6] is not None else 1)
        }
    return None

if __name__ == "__main__":
    init_db()

import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.environ.get("LOCALPASS_DB", "vault.db")

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
            updated_at TEXT NOT NULL
        )
    ''')
    
    # Try to add tags column to existing db if it was created before
    try:
        cursor.execute("ALTER TABLE notes ADD COLUMN tags TEXT DEFAULT '[]'")
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

def add_password(domain: str, username: str, enc_pass: str, nonce: str, ttl_days: int, strength_score: float):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute('''
        INSERT INTO passwords (domain, username, encrypted_password, nonce, created_at, updated_at, ttl_days, strength_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (domain, username, enc_pass, nonce, now, now, ttl_days, strength_score))
    conn.commit()
    conn.close()

def update_password(p_id: int, domain: str, username: str, enc_pass: str, nonce: str, ttl_days: int, strength_score: float):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute('''
        UPDATE passwords 
        SET domain = ?, username = ?, encrypted_password = ?, nonce = ?, updated_at = ?, ttl_days = ?, strength_score = ?
        WHERE id = ?
    ''', (domain, username, enc_pass, nonce, now, ttl_days, strength_score, p_id))
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
    cursor.execute('SELECT id, domain, username, encrypted_password, nonce, created_at, updated_at, ttl_days, strength_score FROM passwords')
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
            "strength_score": r[8]
        })
    return results

def get_password_by_domain_user(domain: str, username: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, encrypted_password, nonce, created_at, updated_at, ttl_days, strength_score 
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
            "strength_score": row[6]
        }
    return None

def add_note(title: str, enc_content: str, tags: str, nonce: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute('''
        INSERT INTO notes (title, encrypted_content, tags, nonce, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (title, enc_content, tags, nonce, now, now))
    conn.commit()
    conn.close()

def update_note(n_id: int, title: str, enc_content: str, tags: str, nonce: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute('''
        UPDATE notes 
        SET title = ?, encrypted_content = ?, tags = ?, nonce = ?, updated_at = ?
        WHERE id = ?
    ''', (title, enc_content, tags, nonce, now, n_id))
    conn.commit()
    conn.close()

def delete_note(n_id: int):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM notes WHERE id = ?', (n_id,))
    conn.commit()
    conn.close()

def get_notes():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id, title, encrypted_content, tags, nonce, created_at, updated_at FROM notes')
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
            "updated_at": r[6]
        })
    return results

def get_note_by_title(title: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, encrypted_content, tags, nonce, created_at, updated_at
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
            "updated_at": row[5]
        }
    return None

if __name__ == "__main__":
    init_db()

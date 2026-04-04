from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
import os
import secrets
from fastapi.middleware.cors import CORSMiddleware
import database
import encryption
from ml_engine import ml_engine
import base64
import time

app = FastAPI(title="LocalPass API")

# Allow the browser extension (and local Flet UI) to communicate
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In a real highly secure scenario, restrict to extension ID if possible
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CURRENT_KEY: bytes | None = None
ON_DB_UPDATE = []

def notify_update():
    for cb in ON_DB_UPDATE:
        try: cb()
        except: pass

def get_user_info():
    import json
    name = database.get_config('user_name') or ""
    words_str = database.get_config('custom_words')
    words = json.loads(words_str) if words_str else []
    return [name] + words


def validate_master_password(password: str):
    if not password or not password.strip():
        raise HTTPException(status_code=400, detail="Master password cannot be empty or only whitespace.")
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Master password must be at least 8 characters.")
    
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_symbol = any(not c.isalnum() for c in password)
    
    if not (has_upper and has_lower and has_digit and has_symbol):
        raise HTTPException(status_code=400, detail="Master password must contain a mix of uppercase, lowercase, numbers, and symbols.")

class SetupRequest(BaseModel):
    master_password: str
    user_name: str

class SettingsUpdateRequest(BaseModel):
    user_name: str
    custom_words: List[str]
    hotkey: str
    popup_position: str = "top_right"

class ImportExportRequest(BaseModel):
    master_password: str

class ImportRequest(ImportExportRequest):
    csv_content: str


class UnlockRequest(BaseModel):
    master_password: str

class ChangeMasterRequest(BaseModel):
    old_password: str
    new_password: str

class PasswordSaveRequest(BaseModel):
    domain: str
    username: str
    password: str
    note_id: Optional[int] = None

class PasswordUpdateRequest(BaseModel):
    domain: str
    username: str
    password: str
    note_id: Optional[int] = None

class PasswordResponse(BaseModel):
    id: int
    domain: str
    username: str
    password: str
    created_at: str
    updated_at: str
    ttl_days: int
    strength_score: float
    is_decayed: bool
    note_id: Optional[int] = None
    history: List[dict] = []

class NoteSaveRequest(BaseModel):
    title: str
    content: str
    tags: List[str] = []
    is_hidden: bool = True

class NoteUpdateRequest(BaseModel):
    title: str
    content: str
    tags: List[str] = []
    is_hidden: bool = True

class NoteResponse(BaseModel):
    id: int
    title: str
    content: str
    tags: List[str]
    is_hidden: bool
    created_at: str
    updated_at: str

@app.on_event("startup")
def startup():
    database.init_db()

def require_auth():
    global CURRENT_KEY
    if not CURRENT_KEY:
        raise HTTPException(status_code=401, detail="Vault is locked")
    return CURRENT_KEY

@app.post("/api/setup")
def setup_vault(req: SetupRequest):
    if database.is_vault_setup():
        raise HTTPException(status_code=400, detail="Vault is already set up")
    
    if not req.user_name or not req.user_name.strip():
        raise HTTPException(status_code=400, detail="User name is required.")
        
    validate_master_password(req.master_password)
    
    salt, test_cipher, test_nonce = encryption.setup_vault_keys(req.master_password)
    
    database.save_config('salt', base64.b64encode(salt).decode('utf-8'))
    database.save_config('test_cipher', base64.b64encode(test_cipher).decode('utf-8'))
    database.save_config('test_nonce', base64.b64encode(test_nonce).decode('utf-8'))
    
    # Store creation and TTL
    database.save_config('user_name', req.user_name.strip())
    import json
    database.save_config('custom_words', json.dumps([]))
    score, master_ttl = ml_engine.score_password(req.master_password, get_user_info())
    database.save_config('master_created_at', str(int(time.time())))
    database.save_config('master_ttl', str(master_ttl))
    
    # Automatically unlock
    global CURRENT_KEY
    CURRENT_KEY = encryption.derive_key(req.master_password, salt)
    
    return {"message": "Vault configured successfully"}

@app.post("/api/unlock")
def unlock_vault(req: UnlockRequest):
    if not database.is_vault_setup():
        raise HTTPException(status_code=400, detail="Vault not configured")
        
    salt = base64.b64decode(database.get_config('salt'))
    test_cipher = base64.b64decode(database.get_config('test_cipher'))
    test_nonce = base64.b64decode(database.get_config('test_nonce'))
    
    if encryption.verify_master_password(req.master_password, salt, test_cipher, test_nonce):
        global CURRENT_KEY
        CURRENT_KEY = encryption.derive_key(req.master_password, salt)
        return {"message": "Vault unlocked"}
    else:
        raise HTTPException(status_code=401, detail="Invalid master password")

@app.post("/api/lock")
def lock_vault():
    global CURRENT_KEY
    CURRENT_KEY = None
    return {"message": "Vault locked"}

@app.post("/api/change-master")
def change_master(req: ChangeMasterRequest, key: bytes = Depends(require_auth)):
    # 1. Verify old password
    salt = base64.b64decode(database.get_config('salt'))
    test_cipher = base64.b64decode(database.get_config('test_cipher'))
    test_nonce = base64.b64decode(database.get_config('test_nonce'))
    
    if not encryption.verify_master_password(req.old_password, salt, test_cipher, test_nonce):
        raise HTTPException(status_code=401, detail="Old master password incorrect")
        
    # 2. Validate new password
    validate_master_password(req.new_password)
    
    # 3. Decrypt all passwords using old key
    rows = database.get_passwords()
    decrypted_items = []
    for r in rows:
        c = base64.b64decode(r["encrypted_password"])
        n = base64.b64decode(r["nonce"])
        try:
            pt = encryption.decrypt_data(c, n, key)
            import json
            dec_hist = []
            if r.get("history") and r["history"] != "[]":
                try:
                    hist_arr = json.loads(r["history"])
                    for h in hist_arr:
                        hc = base64.b64decode(h["encrypted_password"])
                        hn = base64.b64decode(h["nonce"])
                        try:
                            hpt = encryption.decrypt_data(hc, hn, key)
                            dec_hist.append({"pt": hpt, "timestamp": h["timestamp"]})
                        except Exception:
                            pass
                except Exception:
                    pass
            decrypted_items.append((r["id"], r["domain"], r["username"], pt, r["ttl_days"], r["strength_score"], r.get("note_id"), dec_hist))
        except Exception:
            pass # Skip corrupted
            
    # 3b. Decrypt all notes
    note_rows = database.get_notes()
    decrypted_notes = []
    for nr in note_rows:
        nc = base64.b64decode(nr["encrypted_content"])
        nn = base64.b64decode(nr["nonce"])
        try:
            n_pt = encryption.decrypt_data(nc, nn, key)
            decrypted_notes.append((nr["id"], nr["title"], n_pt))
        except Exception:
            pass
            
    # 4. Generate new master derivation
    new_salt, new_tc, new_tn = encryption.setup_vault_keys(req.new_password)
    new_key = encryption.derive_key(req.new_password, new_salt)
    
    # 5. Re-encrypt and update DB
    for pid, domain, username, pt, ttl, score, note_id, dec_hist in decrypted_items:
        new_c, new_n = encryption.encrypt_data(pt, new_key)
        import json
        new_hist = []
        for h in dec_hist:
            hc, hn = encryption.encrypt_data(h["pt"], new_key)
            new_hist.append({
                "encrypted_password": base64.b64encode(hc).decode('utf-8'),
                "nonce": base64.b64encode(hn).decode('utf-8'),
                "timestamp": h["timestamp"]
            })
            
        database.update_password(
            pid,
            domain,
            username,
            base64.b64encode(new_c).decode('utf-8'),
            base64.b64encode(new_n).decode('utf-8'),
            ttl,
            score,
            note_id,
            json.dumps(new_hist)
        )
        
    for nid, title, n_pt in decrypted_notes:
        n_new_c, n_new_n = encryption.encrypt_data(n_pt, new_key)
        database.update_note(
            nid,
            title,
            base64.b64encode(n_new_c).decode('utf-8'),
            base64.b64encode(n_new_n).decode('utf-8')
        )
        
    # 6. Update config
    database.save_config('salt', base64.b64encode(new_salt).decode('utf-8'))
    database.save_config('test_cipher', base64.b64encode(new_tc).decode('utf-8'))
    database.save_config('test_nonce', base64.b64encode(new_tn).decode('utf-8'))
    
    score, master_ttl = ml_engine.score_password(req.new_password, get_user_info())
    database.save_config('master_created_at', str(int(time.time())))
    database.save_config('master_ttl', str(master_ttl))
    
    # 7. Update current session key
    global CURRENT_KEY
    CURRENT_KEY = new_key
    
    return {"message": "Master password changed successfully."}

@app.post("/api/reset")
def reset_vault():
    import sqlite3
    conn = sqlite3.connect(database.DB_PATH)
    conn.execute("DELETE FROM config")
    conn.execute("DELETE FROM passwords")
    conn.execute("DELETE FROM notes")
    conn.commit()
    conn.close()
    
    global CURRENT_KEY
    CURRENT_KEY = None
    return {"message": "Vault successfully wiped and reset."}

@app.get("/api/status")
def get_status():
    global CURRENT_KEY
    is_setup = database.is_vault_setup()
    
    master_decayed = False
    master_ttl_days = 90
    
    if is_setup:
        created_str = database.get_config('master_created_at')
        ttl_str = database.get_config('master_ttl')
        if created_str and ttl_str:
            created_at = int(created_str)
            master_ttl_days = int(float(ttl_str))
            age_days = (time.time() - created_at) / (24 * 3600)
            if age_days > master_ttl_days:
                master_decayed = True
                
    return {
        "is_setup": is_setup,
        "is_unlocked": CURRENT_KEY is not None,
        "master_decayed": master_decayed,
        "master_ttl_days": master_ttl_days
    }

@app.post("/api/passwords")
def save_password(req: PasswordSaveRequest, key: bytes = Depends(require_auth)):
    # Test if it already exists
    existing = database.get_password_by_domain_user(req.domain, req.username)
    if existing:
        raise HTTPException(status_code=409, detail="Login already exists for this domain and username. Use update instead.")
        
    # Calculate ML Score and TTL
    score, ttl_days = ml_engine.score_password(req.password, get_user_info())
    
    # Encrypt
    ciphertext, nonce = encryption.encrypt_data(req.password, key)
    
    # Save
    database.add_password(
        req.domain, 
        req.username, 
        base64.b64encode(ciphertext).decode('utf-8'),
        base64.b64encode(nonce).decode('utf-8'),
        ttl_days=ttl_days,
        strength_score=score,
        note_id=req.note_id
    )
    notify_update()
    return {"message": "Password saved successfully"}

@app.put("/api/passwords/{item_id}")
def update_password(item_id: int, req: PasswordUpdateRequest, key: bytes = Depends(require_auth)):
    rows = database.get_passwords()
    existing_item = next((r for r in rows if r["id"] == item_id), None)
    if not existing_item:
        raise HTTPException(status_code=404, detail="Password not found")
        
    old_c = base64.b64decode(existing_item["encrypted_password"])
    old_n = base64.b64decode(existing_item["nonce"])
    
    try:
        old_pt = encryption.decrypt_data(old_c, old_n, key)
    except Exception:
        old_pt = ""
        
    import json
    history_arr = []
    if existing_item.get("history") and existing_item["history"] != "[]":
        try:
            history_arr = json.loads(existing_item["history"])
        except ValueError:
            pass

    if old_pt and old_pt != req.password:
        import datetime
        now_str = datetime.datetime.now().isoformat()
        history_arr.append({
            "encrypted_password": existing_item["encrypted_password"],
            "nonce": existing_item["nonce"],
            "timestamp": now_str
        })
        
    score, ttl_days = ml_engine.score_password(req.password, get_user_info())
    ciphertext, nonce = encryption.encrypt_data(req.password, key)
    
    database.update_password(
        p_id=item_id,
        domain=req.domain,
        username=req.username,
        enc_pass=base64.b64encode(ciphertext).decode('utf-8'),
        nonce=base64.b64encode(nonce).decode('utf-8'),
        ttl_days=ttl_days,
        strength_score=score,
        note_id=req.note_id,
        history=json.dumps(history_arr)
    )
    notify_update()
    return {"message": "Password updated successfully"}

@app.delete("/api/passwords/{item_id}")
def remove_password(item_id: int, key: bytes = Depends(require_auth)):
    database.delete_password(item_id)
    notify_update()
    return {"message": "Password deleted successfully"}

@app.get("/api/passwords", response_model=List[PasswordResponse])
def get_all_passwords(key: bytes = Depends(require_auth)):
    rows = database.get_passwords()
    results = []
    
    import datetime
    now = datetime.datetime.now()
    
    for r in rows:
        ciphertext = base64.b64decode(r["encrypted_password"])
        nonce = base64.b64decode(r["nonce"])
        
        try:
            plaintext = encryption.decrypt_data(ciphertext, nonce, key)
        except Exception:
            continue # Skip corrupted/invalid
            
        created_at = datetime.datetime.fromisoformat(r["created_at"])
        ttl_days = r["ttl_days"] or 90
        
        # Calculate if decayed
        age_days = (now - created_at).days
        is_decayed = age_days > ttl_days
            
        import json
        history_plain = []
        if r.get("history") and r["history"] != "[]":
            try:
                hist_arr = json.loads(r["history"])
                for h in hist_arr:
                    hc = base64.b64decode(h["encrypted_password"])
                    hn = base64.b64decode(h["nonce"])
                    try:
                        hpt = encryption.decrypt_data(hc, hn, key)
                        history_plain.append({
                            "password": hpt,
                            "timestamp": h["timestamp"]
                        })
                    except Exception:
                        pass
            except Exception:
                pass

        results.append(PasswordResponse(
            id=r["id"],
            domain=r["domain"],
            username=r["username"],
            password=plaintext,
            created_at=r["created_at"],
            updated_at=r["updated_at"],
            ttl_days=ttl_days,
            strength_score=r["strength_score"] or 0.5,
            is_decayed=is_decayed,
            note_id=r.get("note_id"),
            history=history_plain
        ))
    return results

@app.get("/api/generate")
def generate_personalized_password(key: bytes = Depends(require_auth)):
    """Decrypts all passwords, feeds them to ML engine, and gets a new secure one matching user style"""
    rows = database.get_passwords()
    plaintexts = []
    for r in rows:
        ciphertext = base64.b64decode(r["encrypted_password"])
        nonce = base64.b64decode(r["nonce"])
        try:
            pt = encryption.decrypt_data(ciphertext, nonce, key)
            plaintexts.append(pt)
        except Exception:
            pass
            
    generated = ml_engine.generate_personalized_password(plaintexts)
    score, ttl = ml_engine.score_password(generated, get_user_info())
    return {
        "generated_password": generated,
        "score": score,
        "ttl_days": ttl
    }

@app.post("/api/import")
def import_csv(req: ImportRequest):
    salt = base64.b64decode(database.get_config('salt'))
    test_cipher = base64.b64decode(database.get_config('test_cipher'))
    test_nonce = base64.b64decode(database.get_config('test_nonce'))
    if not encryption.verify_master_password(req.master_password, salt, test_cipher, test_nonce):
        raise HTTPException(status_code=401, detail="Invalid master password")
    
    key = encryption.derive_key(req.master_password, salt)
    import csv, io
    reader = csv.DictReader(io.StringIO(req.csv_content))
    imported_count = 0
    info = get_user_info()
    
    for row in reader:
        name = row.get('name', '').strip()
        domain = row.get('url', '').strip()
        username = row.get('username', '').strip()
        password = row.get('password', '')
        
        if not name and not domain and not username and not password:
            continue
            
        if not name and domain:
            name = domain
            if name.startswith(('http://', 'https://')):
                name = name.split('//')[1].split('/')[0]
                
        if not name:
            name = "Unknown Website"
            
        # Deduplication Check
        existing = database.get_password_by_domain_user(name, username)
        if existing:
            continue
            
        score, ttl_days = ml_engine.score_password(password, info)
        ciphertext, nonce = encryption.encrypt_data(password, key)
        
        try:
            database.add_password(
                name,
                username,
                base64.b64encode(ciphertext).decode('utf-8'),
                base64.b64encode(nonce).decode('utf-8'),
                ttl_days=ttl_days,
                strength_score=score
            )
            imported_count += 1
        except Exception:
            pass
            
    if imported_count > 0:
        notify_update()
    return {"message": f"Successfully imported {imported_count} passwords", "count": imported_count}

@app.post("/api/export")
def export_csv(req: ImportExportRequest):
    salt = base64.b64decode(database.get_config('salt'))
    test_cipher = base64.b64decode(database.get_config('test_cipher'))
    test_nonce = base64.b64decode(database.get_config('test_nonce'))
    if not encryption.verify_master_password(req.master_password, salt, test_cipher, test_nonce):
        raise HTTPException(status_code=401, detail="Invalid master password")
        
    key = encryption.derive_key(req.master_password, salt)
    rows = database.get_passwords()
    
    import csv, io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['name', 'url', 'username', 'password'])
    
    for r in rows:
        c = base64.b64decode(r["encrypted_password"])
        n = base64.b64decode(r["nonce"])
        try:
            pt = encryption.decrypt_data(c, n, key)
            writer.writerow([r["domain"], "", r["username"], pt])
        except Exception:
            pass
            
    return {"csv_content": output.getvalue()}

@app.get("/api/settings")
def get_settings():
    import json
    name = database.get_config('user_name') or ""
    words_str = database.get_config('custom_words')
    words = json.loads(words_str) if words_str else []
    hotkey = database.get_config('hotkey') or "ctrl+shift+l"
    popup_position = database.get_config('popup_position') or "top_right"
    return {"user_name": name, "custom_words": words, "hotkey": hotkey, "popup_position": popup_position}

@app.post("/api/settings")
def update_settings(req: SettingsUpdateRequest):
    import json
    database.save_config('user_name', req.user_name.strip())
    database.save_config('custom_words', json.dumps(req.custom_words))
    database.save_config('hotkey', req.hotkey.strip())
    database.save_config('popup_position', req.popup_position.strip())
    return {"message": "Settings updated"}

@app.post("/api/notes")
def save_note(req: NoteSaveRequest, key: bytes = Depends(require_auth)):
    existing = database.get_note_by_title(req.title)
    if existing:
        raise HTTPException(status_code=409, detail="Note with this title already exists. Use update instead.")
        
    ciphertext, nonce = encryption.encrypt_data(req.content, key)
    import json
    
    database.add_note(
        req.title,
        base64.b64encode(ciphertext).decode('utf-8'),
        json.dumps(req.tags),
        base64.b64encode(nonce).decode('utf-8'),
        req.is_hidden
    )
    notify_update()
    return {"message": "Note saved successfully"}

@app.put("/api/notes/{item_id}")
def update_note(item_id: int, req: NoteUpdateRequest, key: bytes = Depends(require_auth)):
    ciphertext, nonce = encryption.encrypt_data(req.content, key)
    import json
    database.update_note(
        n_id=item_id,
        title=req.title,
        enc_content=base64.b64encode(ciphertext).decode('utf-8'),
        tags=json.dumps(req.tags),
        nonce=base64.b64encode(nonce).decode('utf-8'),
        is_hidden=req.is_hidden
    )
    notify_update()
    return {"message": "Note updated successfully"}

@app.delete("/api/notes/{item_id}")
def remove_note(item_id: int, key: bytes = Depends(require_auth)):
    database.delete_note(item_id)
    notify_update()
    return {"message": "Note deleted successfully"}

@app.get("/api/notes", response_model=List[NoteResponse])
def get_all_notes(key: bytes = Depends(require_auth)):
    rows = database.get_notes()
    results = []
    import json
    for r in rows:
        ciphertext = base64.b64decode(r["encrypted_content"])
        nonce = base64.b64decode(r["nonce"])
        try:
            plaintext = encryption.decrypt_data(ciphertext, nonce, key)
        except Exception:
            continue
            
        tags_list = []
        try:
            tags_list = json.loads(r["tags"])
        except:
            pass
            
        results.append(NoteResponse(
            id=r["id"],
            title=r["title"],
            content=plaintext,
            tags=tags_list,
            is_hidden=r.get("is_hidden", True),
            created_at=r["created_at"],
            updated_at=r["updated_at"]
        ))
    return results

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5000)

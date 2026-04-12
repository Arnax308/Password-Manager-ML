import os
os.environ["VALTR_DB"] = "test_vault.db"

import encryption
from ml_engine import ml_engine
import database

print("--- Testing Encryption Engine ---")
salt, test_c, test_n = encryption.setup_vault_keys("MySuperSecretMasterPass")
print("Derived Keys Successfully.")

is_valid = encryption.verify_master_password("MySuperSecretMasterPass", salt, test_c, test_n)
print(f"Master Password Verification (Correct): {is_valid}")

is_valid_wrong = encryption.verify_master_password("WrongPass", salt, test_c, test_n)
print(f"Master Password Verification (Wrong): {is_valid_wrong}")

key = encryption.derive_key("MySuperSecretMasterPass", salt)
cipher, nonce = encryption.encrypt_data("SensitiveData123", key)
decrypted = encryption.decrypt_data(cipher, nonce, key)
print(f"Encryption/Decryption Match: {decrypted == 'SensitiveData123'}")

print("\n--- Testing ML Engine ---")
user_info = ["Arnav", "arnav123@gmail.com"]

# Bad passwords
score1, ttl1 = ml_engine.score_password("password123", user_info)
print(f"Bad Password ('password123'): Score={score1:.2f}, TTL={ttl1} days")

# Personal info passwords
score2, ttl2 = ml_engine.score_password("ArnavRocks2026", user_info)
print(f"Personal Info Password ('ArnavRocks2026'): Score={score2:.2f}, TTL={ttl2} days")

# Strong passwords
score3, ttl3 = ml_engine.score_password("Tr0ub4dor&3!", user_info)
print(f"Strong Password: Score={score3:.2f}, TTL={ttl3} days")

print("\n--- Testing Personalized Generation ---")
vault_samples = ["AppleTree88!", "BananaBoat99@", "CherryPie77#"]
gen = ml_engine.generate_personalized_password(vault_samples)
print(f"Generated Password (trained on fruits): {gen}")
gen_score, gen_ttl = ml_engine.score_password(gen, user_info)
print(f"Generated Password Score: {gen_score:.2f}, TTL {gen_ttl} days")

print("\n--- Skipping Old Importer Tests (Moved to API) ---")

print("\n--- Testing Master Password Validation ---")
from app import validate_master_password
try:
    validate_master_password("weak")
    print("Failed: Weak password accepted.")
except Exception as e:
    print(f"Passed: Weak password blocked ({e.detail})")

try:
    validate_master_password("StrongButNoSymbols1")
    print("Failed: Missing symbol accepted.")
except Exception as e:
    print(f"Passed: Missing symbol blocked ({e.detail})")

try:
    validate_master_password("SuperSecretPass!99")
    print("Passed: Strong master password validated successfully.")
except Exception as e:
    print(f"Failed: Strong password blocked ({e})")

print("\n--- Testing Master Password Change/Re-encryption ---")
import app
import os
import database

# Clean up DB for a fresh API test
if os.path.exists("test_vault.db"):
    os.remove("test_vault.db")

database.init_db()

from fastapi.testclient import TestClient
client = TestClient(app.app)
app.CURRENT_KEY = None # Reset session

# Setup vault via API
setup_resp = client.post("/api/setup", json={"master_password": "MySuperSecretMasterPass!1", "user_name": "Arnav Test"})
print(f"Setup API: {setup_resp.status_code}")

# Test Import CSV API
mock_csv = "name,url,username,password\nGoogle,https://google.com,arnav_test,weakpass1\nNetflix,,arnav@example.com,SecureNet!99"
import_resp = client.post("/api/import", json={"master_password": "MySuperSecretMasterPass!1", "csv_content": mock_csv})
print(f"Import API (Should pass -> 200): {import_resp.status_code}")

# Test Export CSV API
export_resp = client.post("/api/export", json={"master_password": "MySuperSecretMasterPass!1"})
print(f"Export API (Should pass -> 200): {export_resp.status_code}")
if export_resp.status_code == 200:
    print(f"Export DB Rows length: {len(export_resp.json().get('csv_content', ''))}")


# Rotate password
change_resp = client.post("/api/change-master", json={
    "old_password": "MySuperSecretMasterPass!1",
    "new_password": "NewSecretMaster!99"
})
if change_resp.status_code == 200:
    print("Master Password changed successfully via API.")
else:
    print(f"Failed to change master password: {change_resp.text}")

# Ensure old password no longer unlocks (clear global session to simulate fresh start)
app.CURRENT_KEY = None
unlock_old = client.post("/api/unlock", json={"master_password": "MySuperSecretMasterPass!1"})
print(f"Old Master Password unlock attempt (Should fail -> 401): {unlock_old.status_code}")

# Ensure new password unlocks
unlock_new = client.post("/api/unlock", json={"master_password": "NewSecretMaster!99"})
print(f"New Master Password unlock attempt (Should pass -> 200): {unlock_new.status_code}")

status_resp = client.get("/api/status").json()
print(f"Status - Is Master Decayed: {status_resp['master_decayed']}, TTL: {status_resp['master_ttl_days']} days")

print("\n--- Testing Vault Reset ---")
reset_resp = client.post("/api/reset")
if reset_resp.status_code == 200:
    print("Vault reset payload accepted.")
else:
    print(f"Failed to reset vault: {reset_resp.text}")

# Re-setup for notes test
client.post("/api/setup", json={"master_password": "NewSecretMaster!99", "user_name": "Arnav Test"})

print("\n--- Testing Secure Notes API ---")
# Create Note
note_resp = client.post("/api/notes", json={"title": "Bank Recovery Codes", "content": "1234-5678-9012"})
print(f"Create Note (Should pass -> 200): {note_resp.status_code}")

# Get Notes
get_notes = client.get("/api/notes")
if get_notes.status_code == 200 and len(get_notes.json()) > 0:
    note = get_notes.json()[0]
    print(f"Get Note Match: {note['title'] == 'Bank Recovery Codes' and note['content'] == '1234-5678-9012'}")
    
    # Update Note
    update_resp = client.put(f"/api/notes/{note['id']}", json={"title": "Bank Recovery Codes", "content": "9999-0000-1111"})
    print(f"Update Note (Should pass -> 200): {update_resp.status_code}")
    
    # Get again
    updated_note = client.get("/api/notes").json()[0]
    print(f"Update Note Match: {updated_note['content'] == '9999-0000-1111'}")
    
    # Delete Note
    del_resp = client.delete(f"/api/notes/{note['id']}")
    print(f"Delete Note (Should pass -> 200): {del_resp.status_code}")
    
    empty_notes = client.get("/api/notes").json()
    print(f"Delete Note Match (Should be empty): {len(empty_notes) == 0}")

final_status = client.get("/api/status").json()
print(f"Is Vault Setup? : {final_status['is_setup']}")

print("\nAll Backend Unit Tests Completed")

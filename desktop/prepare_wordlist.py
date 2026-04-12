import urllib.request
import os

ROCKYOU_URL = "https://raw.githubusercontent.com/josuamarcelc/common-password-list/main/rockyou_2025_00.txt"
NAMES_URL = "https://raw.githubusercontent.com/dominictarr/random-name/master/first-names.txt"
OUTPUT_FILE = "common_passwords.txt"
MAX_WORDS = 100000

def download_file(url):
    print(f"Downloading data from {url}...")
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        return response.read().decode('utf-8', errors='ignore')

def main():
    try:
        names_text = download_file(NAMES_URL)
        names_set = set(name.strip().lower() for name in names_text.splitlines() if len(name.strip()) > 2)
        print(f"Loaded {len(names_set)} names from corpus.")
    except Exception as e:
        print(f"Could not load names: {e}. Will skip name filtering.")
        names_set = set()

    try:
        rockyou_text = download_file(ROCKYOU_URL)
        passwords = rockyou_text.splitlines()
        print(f"Loaded {len(passwords)} passwords from RockYou chunk.")
    except Exception as e:
        print(f"Error downloading RockYou list: {e}")
        return

    clean_passwords = []
    seen = set()

    for pw in passwords:
        pw = pw.strip()
        if not pw:
            continue
        
        pw_lower = pw.lower()
        
        # Skip if it's already added
        if pw_lower in seen:
            continue
            
        # Skip if it's a known name
        if pw_lower in names_set:
            continue
            
        clean_passwords.append(pw_lower)
        seen.add(pw_lower)
        
        if len(clean_passwords) >= MAX_WORDS:
            break

    print(f"Collected {len(clean_passwords)} cleaned passwords.")
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for p in clean_passwords:
            f.write(p + "\n")
            
    print(f"Saved into {OUTPUT_FILE}")

if __name__ == "__main__":
    main()

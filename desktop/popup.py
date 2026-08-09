import os
import sys
import time
import json
import base64
import logging
import threading
import requests
from desktop import desktop_agent, set_overlay_callback

logger = logging.getLogger(__name__)

# Trigger configuration file path
TRIGGER_FILE = os.path.join(os.environ.get("TEMP", "."), "valtr_popup_trigger.json")
BACKEND_URL = "http://127.0.0.1:5000"

def on_hotkey_triggered(title, hwnd, b64_typed, browser_url):
    """Callback executed when the global hotkey (e.g. Ctrl+Shift+L) is pressed.
    
    Captures foreground window info, active browser URL, and typed credential candidates,
    then writes the trigger payload for Electron / popup UI consumption and posts to backend.
    """
    logger.info(f"Hotkey triggered. Window: '{title}', URL: '{browser_url}'")
    
    decoded_typed = ""
    try:
        if b64_typed:
            decoded_typed = base64.b64decode(b64_typed).decode('utf-8')
    except Exception as e:
        logger.error(f"Failed to decode typed credentials: {e}")

    parts = decoded_typed.split("\t") if decoded_typed else ["", ""]
    user_cand = parts[0] if len(parts) > 0 else ""
    pass_cand = parts[1] if len(parts) > 1 else ""

    payload = {
        "title": title,
        "hwnd": hwnd,
        "browser_url": browser_url,
        "typed_user": user_cand,
        "typed_pass": pass_cand,
        "timestamp": time.time()
    }

    # Save to local TEMP file for IPC / Electron polling fallback
    try:
        with open(TRIGGER_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f)
    except Exception as err:
        logger.error(f"Failed to write trigger file: {err}")

    # Send trigger to FastAPI backend if running
    try:
        sess = requests.Session()
        sess.trust_env = False
        sess.post(f"{BACKEND_URL}/api/popup/trigger", json=payload, timeout=1)
    except Exception:
        pass

def start_popup_backend(hotkey="ctrl+shift+l"):
    """Starts the background keyboard listener for the specified global hotkey."""
    logger.info(f"Starting popup hotkey listener backend for '{hotkey}'")
    set_overlay_callback(on_hotkey_triggered)

def perform_autotype(username: str, password: str):
    """Triggers pywinauto / keyboard hardware simulation to type credentials into the focused app."""
    desktop_agent.autotype(username, password)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Starting Valtr Popup & Hotkey Backend Listener...")
    start_popup_backend("ctrl+shift+l")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Popup backend stopped.")

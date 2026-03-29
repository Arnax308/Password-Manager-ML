import keyboard
import logging
import time
from pywinauto import keyboard as pykeyboard, application
import threading

logging.basicConfig(level=logging.INFO)

import base64

# Segment-based keylogger: captures discrete tokens, not sentences
# Each segment is a space-free string. Tab/Enter create field-break markers.
_current_word = []       # Characters of the word currently being typed
_segments = []           # List of (text, delimiter) tuples — delimiter is 'space'/'tab'/'enter'/None

def _is_password_like(s):
    """Heuristic: 8+ chars with a mix of uppercase, lowercase, digits, and symbols."""
    if len(s) < 8:
        return False
    has_upper = any(c.isupper() for c in s)
    has_lower = any(c.islower() for c in s)
    has_digit = any(c.isdigit() for c in s)
    has_symbol = any(not c.isalnum() for c in s)
    # Require at least 3 of the 4 categories for a strong signal
    return sum([has_upper, has_lower, has_digit, has_symbol]) >= 3

def _finalize_word(delimiter):
    """Push the current word into segments with its trailing delimiter."""
    global _current_word
    word = "".join(_current_word).strip()
    if word:
        _segments.append((word, delimiter))
    _current_word = []
    # Cap segment history
    if len(_segments) > 30:
        _segments.pop(0)

def _extract_credentials():
    """Analyze segments to find the best (username, password) candidate pair.
    
    Returns (guessed_user, guessed_pass) — either or both may be empty.
    """
    if not _segments:
        return "", ""

    # Strategy 1: Find a password-like segment, then take the tab-delimited predecessor as username
    for i in range(len(_segments) - 1, -1, -1):
        text, delim = _segments[i]
        if _is_password_like(text):
            # Look for a tab-delimited predecessor (strong login form signal)
            username = ""
            if i > 0:
                prev_text, prev_delim = _segments[i - 1]
                if prev_delim == 'tab':
                    username = prev_text
            return username, text

    # Strategy 2: Fall back to tab/enter delimited segments (e.g. user[TAB]short_pass)
    tab_groups = []
    current_group = []
    for text, delim in _segments:
        current_group.append(text)
        if delim in ('tab', 'enter'):
            tab_groups.append(" ".join(current_group))
            current_group = []
    if current_group:
        tab_groups.append(" ".join(current_group))

    if len(tab_groups) >= 2:
        return tab_groups[-2], tab_groups[-1]

    return "", ""

def keylog_callback(e):
    if e.event_type == keyboard.KEY_DOWN:
        if e.name in ['shift', 'ctrl', 'alt', 'win', 'cmd', 'caps lock', 'esc']:
            return
        if len(e.name) == 1:
            _current_word.append(e.name)
        elif e.name == "space":
            _finalize_word('space')
        elif e.name == "tab":
            _finalize_word('tab')
        elif e.name == "enter":
            _finalize_word('enter')
        elif e.name == "backspace":
            if _current_word:
                _current_word.pop()

class DesktopIntegration:
    def __init__(self, on_hotkey_callback):
        self.on_hotkey_callback = on_hotkey_callback
        self.active_window_before_search = None
        self._listener_thread = None

    def _setup_keylogger(self):
        try: keyboard.hook(keylog_callback)
        except: pass

    def start_listener(self, hotkey="ctrl+shift+l"):
        logging.info(f"Starting global hotkey listener for {hotkey}")
        try:
            keyboard.unhook_all_hotkeys()
            keyboard.unhook(keylog_callback)
        except:
            pass
        self._setup_keylogger()
        keyboard.add_hotkey(hotkey, self._summon_search)

    def _get_window_title(self, hwnd):
        import ctypes
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        buff = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
        return buff.value

    def _get_browser_url(self, hwnd):
        """Extract the actual URL from browser address bar via Windows UI Automation.
        
        Supports Chrome, Edge, Firefox. Returns empty string if not a browser or extraction fails.
        """
        try:
            app = application.Application(backend="uia").connect(handle=hwnd)
            win = app.top_window()
            title = win.window_text().lower()
            
            # Try common address bar element names for each browser
            address_bar_names = [
                "Address and search bar",    # Chrome / Edge
                "Search or enter address",   # Firefox
                "Search with Google or enter address",  # Chrome variants
            ]
            
            for name in address_bar_names:
                try:
                    bar = win.child_window(title=name, control_type="Edit")
                    url = bar.get_value()
                    if url:
                        # Chrome/Edge sometimes omit the scheme
                        if not url.startswith(('http://', 'https://')):
                            url = 'https://' + url
                        return url
                except Exception:
                    continue
            
            # Fallback: try to find any Edit control that looks like a URL
            try:
                for ctrl in win.descendants(control_type="Edit"):
                    val = ctrl.get_value()
                    if val and ('.' in val) and (' ' not in val) and len(val) < 2048:
                        if not val.startswith(('http://', 'https://')):
                            val = 'https://' + val
                        return val
            except Exception:
                pass
                
        except Exception:
            pass
        return ""

    def _summon_search(self):
        logging.info("Hotkey pressed. Summoning Flet UI Overlay...")

        import ctypes

        self.active_window_before_search = ctypes.windll.user32.GetForegroundWindow()
        hwnd = self.active_window_before_search
        title = self._get_window_title(hwnd)

        # Finalize any in-progress word, then extract credential candidates
        _finalize_word(None)
        guessed_user, guessed_pass = _extract_credentials()

        # Encode as tab-separated pair
        typed_string = f"{guessed_user}\t{guessed_pass}"
        b64_typed = base64.b64encode(typed_string.encode('utf-8')).decode('utf-8')

        # Clear state for next session
        _current_word.clear()
        _segments.clear()

        if self.on_hotkey_callback:
            self.on_hotkey_callback(title, hwnd, b64_typed, "")


    def autotype(self, username, password):
        """Auto-types the credentials into the previous active window."""
        logging.info(f"Auto-typing for {username}...")
        
        if self.active_window_before_search:
            try:
                # Restore focus to the underlying application
                app = application.Application().connect(handle=self.active_window_before_search)
                app.top_window().set_focus()
                time.sleep(0.1) # Brief pause for focus change
                
                # Type username, tab, type password, enter
                # Using pywinauto's robust keyboard module
                pykeyboard.send_keys(username, with_spaces=True)
                time.sleep(0.05)
                pykeyboard.send_keys("{TAB}")
                time.sleep(0.05)
                pykeyboard.send_keys(password, with_spaces=True)
                time.sleep(0.05)
                pykeyboard.send_keys("{ENTER}")
                
            except Exception as e:
                logging.error(f"Failed to auto-type: {e}")
        else:
            logging.warning("No active window to auto-type into.")

desktop_agent = DesktopIntegration(None)

def set_overlay_callback(callback):
    desktop_agent.on_hotkey_callback = callback
    desktop_agent.start_listener()

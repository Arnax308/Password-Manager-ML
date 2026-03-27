# LocalPass 🔐✨
*Because memorizing passwords in 2026 is actually crazy.*

LocalPass is a strictly local-first, ML-powered desktop password manager. Built with Python and Flet, it completely ditches the need for clunky browser extensions by relying on a sleek global hotkey overlay and OS-level window injection. 

Your vault never touches the cloud. It's just you, AES-256-GCM encryption, and some unreasonably smart heuristics.

## ✨ The Vibe (Features)
- 🧠 **ML-Driven Security**: Analyzes password strength and decay (age) locally to make sure you aren't using "password123" for the 5th year in a row.
- ⚡ **Native Hotkey Overlay**: Press `Ctrl+Shift+L` globally from anywhere. It instantly pops up a minimal UI, reads your active window title to find the domain, and intelligently filters your vault.
- 🥷 **Ghost-Mode Keylogging**: No extension? No problem. The app runs a highly-local ephemeral sliding-window key buffer. If you literally just typed out a new login on some website, hitting the hotkey instantly parses the buffer and pre-fills the "Add Account" menu for you. 
- 🎯 **Smart Autofill**: Uses `pywinauto` to inject your credentials directly back into whatever app/browser window you were using. 
- 🔄 **Real-time Sync**: The main Flet UI is connected directly to the FastAPI backend events, so the visual grid updates in real-time the second you modify anything from the popup.
- 🔒 **Zero Trust Local Crypto**: Secured with PBKDF2 (480k iterations) and AES-256-GCM. Your key lives cleanly in memory and dies the second you close the app. 

## 🚀 How to run this thing
First off, clone the repo and get your environment sorted:
```bash
git clone https://github.com/Arnax308/Password-Manager-ML.git
cd Password-Manager-ML
pip install -r desktop/requirements.txt
```

Launch the mothership:
```bash
python desktop/ui.py
```
*Pro tip: The first time you launch it, it’ll ask you to set up a master password. Don't forget it, because there is literally zero password recovery. If you lose it, your vault is cooked.*

## 🛠️ Stack
- **Frontend**: Flet (Flutter for Python, because we love clean non-laggy UIs)
- **Backend**: FastAPI + SQLite (Async and snappy)
- **Injection & Hooks**: `pywinauto` and `keyboard`
- **Crypto**: `cryptography` package

---
### To-Do / Contributing
If you find a bug or think of a feature to make this even smoother, feel free to open an issue or drop a PR. Or don't, I'm not your boss. xD

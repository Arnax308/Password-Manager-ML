import flet as ft
import sys
import time
import json
import datetime
import app as backend
from desktop import desktop_agent, set_overlay_callback
from ui_theme import *
import threading
import uvicorn
from fastapi.testclient import TestClient

def run_api():
    uvicorn.run(backend.app, host="127.0.0.1", port=5000, log_level="error")

def main(page: ft.Page):
    page.title = "LocalPass"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0
    page.window.width = 1150
    page.window.height = 820
    page.window.resizable = True
    page.bgcolor = BG
    page.fonts = {"Inter": "https://raw.githubusercontent.com/rsms/inter/master/docs/font-files/Inter-Regular.woff2"}
    page.theme = ft.Theme(
        font_family="Inter",
        color_scheme=ft.ColorScheme(background=BG, surface=SURFACE, primary=ACCENT, secondary=GOLD, outline=ACCENT)
    )

    client = TestClient(backend.app)
    current_master_password = ""
    selected_nav = [0]

    # ── Helpers ──
    def show_success(msg):
        page.snack_bar = ft.SnackBar(
            ft.Row([ft.Icon(ft.Icons.CHECK_CIRCLE, color=ACCENT, size=16), ft.Text(msg, size=13, color=TXT)]),
            bgcolor=CARD, duration=2000)
        page.snack_bar.open = True; page.update()

    def show_error(msg):
        page.snack_bar = ft.SnackBar(
            ft.Row([ft.Icon(ft.Icons.ERROR_OUTLINE, color=DANGER, size=16), ft.Text(msg, size=13, color=TXT)]),
            bgcolor=CARD, duration=3000)
        page.snack_bar.open = True; page.update()

    def pill(text, color):
        return ft.Container(content=ft.Text(text, size=9, weight=ft.FontWeight.W_700, color="#fff"),
            bgcolor=color, border_radius=4, padding=ft.padding.symmetric(horizontal=6, vertical=2))

    def strength_dots(score):
        filled = int(score * 5)
        c = DANGER if score < 0.4 else (WARN if score < 0.7 else ACCENT)
        dots = []
        for i in range(5):
            dots.append(ft.Container(width=8, height=8, border_radius=4,
                bgcolor=c if i < filled else "#1e293b"))
        return ft.Row(dots, spacing=3)

    def stat_box(label, value, icon, color):
        return ft.Container(expand=True, bgcolor=CARD, border_radius=12,
            border=ft.border.all(1, BORDER), padding=14,
            content=ft.Row([
                ft.Container(content=ft.Icon(icon, color=color, size=20),
                    width=38, height=38, border_radius=10, bgcolor=f"{color}15",
                    alignment=ft.alignment.center),
                ft.Column([
                    ft.Text(str(value), size=22, weight=ft.FontWeight.BOLD, color=TXT),
                    ft.Text(label, size=10, color=TXT3)
                ], spacing=0)
            ], spacing=10))

    # ── Auth Screen ──
    tf_master_password = ft.TextField(label="Master Password", password=True, can_reveal_password=True,
        width=360, border_radius=10, border_color=BORDER, focused_border_color=ACCENT,
        cursor_color=ACCENT, text_size=14)
    tf_setup_name = ft.TextField(label="Your Name (ML Profiling)", width=360,
        border_radius=10, border_color=BORDER, focused_border_color=ACCENT, text_size=14)
    lbl_auth_error = ft.Text(color=DANGER, size=13)

    def on_login(e):
        resp = client.post("/api/unlock", json={"master_password": tf_master_password.value})
        if resp.status_code == 200:
            nonlocal current_master_password
            current_master_password = tf_master_password.value
            tf_master_password.value = ""
            show_main_app()
        else:
            lbl_auth_error.value = "Invalid master password!"
            page.update()

    def on_setup(e):
        resp = client.post("/api/setup", json={"master_password": tf_master_password.value, "user_name": tf_setup_name.value})
        if resp.status_code == 200:
            nonlocal current_master_password
            current_master_password = tf_master_password.value
            tf_master_password.value = ""
            show_main_app()
        else:
            lbl_auth_error.value = resp.json().get("detail", "Setup failed")
            page.update()

    def on_master_password_submit(e):
        status = client.get("/api/status").json()
        on_login(e) if status.get("is_setup") else on_setup(e)

    tf_master_password.on_submit = on_master_password_submit
    tf_setup_name.on_submit = on_setup

    btn_login = ft.Container(
        content=ft.Text("Unlock Vault", size=14, weight=ft.FontWeight.W_600, color="#fff",
            text_align=ft.TextAlign.CENTER),
        width=360, height=46, border_radius=10, bgcolor=ACCENT,
        alignment=ft.alignment.center, on_click=on_login, ink=True)
    btn_setup = ft.Container(
        content=ft.Text("Complete Setup", size=14, weight=ft.FontWeight.W_600, color="#fff",
            text_align=ft.TextAlign.CENTER),
        width=360, height=46, border_radius=10, bgcolor=ACCENT,
        alignment=ft.alignment.center, on_click=on_setup, ink=True)

    auth_container = ft.Container(
        content=ft.Container(
            width=420, padding=36, border_radius=20, bgcolor=SURFACE,
            border=ft.border.all(1, BORDER),
            shadow=ft.BoxShadow(blur_radius=60, color="#00000060"),
            content=ft.Column([
                ft.Container(
                    content=ft.Icon(ft.Icons.SHIELD_ROUNDED, size=40, color=ACCENT),
                    width=72, height=72, border_radius=36,
                    border=ft.border.all(2, GOLD), alignment=ft.alignment.center),
                ft.Container(height=6),
                ft.Text("LocalPass", size=28, weight=ft.FontWeight.BOLD, color=TXT),
                ft.Text("Your offline password vault", size=13, color=TXT3),
                ft.Container(height=16),
                tf_setup_name,
                tf_master_password,
                ft.Container(height=8),
                btn_login, btn_setup, lbl_auth_error,
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8),
        ),
        alignment=ft.alignment.center, expand=True, bgcolor=BG,
    )

    # --- UI Components: Settings Tab ---
    tf_settings_name = ft.TextField(label="Your Name", width=400)
    tf_settings_words = ft.TextField(label="Custom Sensitive Words (comma separated)", width=400, multiline=True)
    tf_settings_hotkey = ft.TextField(label="Global Hotkey", width=300, read_only=True)
    is_recording_hotkey = [False]
    def on_key(e: ft.KeyboardEvent):
        if is_recording_hotkey[0]:
            keys = []
            if e.ctrl: keys.append("ctrl")
            if e.shift: keys.append("shift")
            if e.alt: keys.append("alt")
            if e.meta: keys.append("win")
            
            if e.key not in ["Control", "Shift", "Alt", "Meta", "Control Left", "Control Right", "Shift Left", "Shift Right", "Alt Left", "Alt Right"]:
                keys.append(e.key.lower())
                tf_settings_hotkey.value = "+".join(keys)
                is_recording_hotkey[0] = False
                tf_settings_hotkey.label = "Global Hotkey"
                page.update()
                
    page.on_keyboard_event = on_key
    
    def start_recording_hotkey(e):
        is_recording_hotkey[0] = True
        tf_settings_hotkey.value = ""
        tf_settings_hotkey.label = "Press your hotkey now..."
        page.update()

    btn_record_hotkey = ft.ElevatedButton("Record Keystroke", on_click=start_recording_hotkey)
    switch_theme = ft.Switch(label="Dark Mode", value=True)
    
    dd_settings_position = ft.Dropdown(
        label="Popup Position",
        width=300,
        options=[
            ft.dropdown.Option("top_right", "Top Right"),
            ft.dropdown.Option("top_left", "Top Left"),
            ft.dropdown.Option("bottom_right", "Bottom Right"),
            ft.dropdown.Option("bottom_left", "Bottom Left"),
        ]
    )

    def load_settings():
        resp = client.get("/api/settings")
        if resp.status_code == 200:
            data = resp.json()
            tf_settings_name.value = data.get("user_name", "")
            tf_settings_words.value = ", ".join(data.get("custom_words", []))
            tf_settings_hotkey.value = data.get("hotkey", "ctrl+shift+l")
            dd_settings_position.value = data.get("popup_position", "top_right")
            page.update()
            
    def save_settings(e):
        words = [w.strip() for w in tf_settings_words.value.split(",") if w.strip()]
        resp = client.post("/api/settings", json={
            "user_name": tf_settings_name.value, 
            "custom_words": words,
            "hotkey": tf_settings_hotkey.value,
            "popup_position": dd_settings_position.value or "top_right"
        })
        if resp.status_code == 200:
            desktop_agent.start_listener(tf_settings_hotkey.value)
            show_success("Settings updated successfully.")
        else:
            show_error("Failed to update settings.")

    def on_theme_change(e):
        page.theme_mode = ft.ThemeMode.DARK if switch_theme.value else ft.ThemeMode.LIGHT
        page.update()
        
    switch_theme.on_change = on_theme_change

    # Change Master Dialogs
    tf_old_master = ft.TextField(label="Current Master Password", password=True, can_reveal_password=True)
    tf_new_master = ft.TextField(label="New Master Password", password=True, can_reveal_password=True)
    
    def on_change_master_submit(e):
        resp = client.post("/api/change-master", json={
            "old_password": tf_old_master.value,
            "new_password": tf_new_master.value
        })
        if resp.status_code == 200:
            nonlocal current_master_password
            current_master_password = tf_new_master.value
            change_dialog.open = False
            show_success("Master Password changed and vault re-encrypted!")
            tf_old_master.value = ""
            tf_new_master.value = ""
            page.update()
            refresh_vault()
        else:
            show_error(resp.json().get("detail", "Error changing password"))

    change_dialog = ft.AlertDialog(
        title=ft.Text("Change Master Password"),
        content=ft.Column([tf_old_master, tf_new_master], tight=True),
        actions=[
            ft.TextButton("Cancel", on_click=lambda e: setattr(change_dialog, 'open', False) or page.update()),
            ft.ElevatedButton("Change & Re-encrypt", on_click=on_change_master_submit)
        ]
    )
    
    def on_reset_confirm(e):
        client.post("/api/reset")
        reset_dialog.open = False
        nonlocal current_master_password
        current_master_password = ""
        show_success("Vault permanently deleted. You can now setup a new one.")
        show_auth_screen()

    reset_dialog = ft.AlertDialog(
        title=ft.Text("DANGER: Reset Vault", color=ft.Colors.RED),
        content=ft.Text("Are you absolutely sure you want to permanently delete your entire vault and master password? This cannot be undone.", color=ft.Colors.RED_200),
        actions=[
            ft.TextButton("Cancel", on_click=lambda e: setattr(reset_dialog, 'open', False) or page.update()),
            ft.ElevatedButton("Permanently Delete", color=ft.Colors.RED, on_click=on_reset_confirm)
        ]
    )
    
    # Edit / Add Dialogs
    tf_edit_domain = ft.TextField(label="Domain / Website")
    tf_edit_username = ft.TextField(label="Username / Email")
    tf_edit_password = ft.TextField(label="Password", password=True, can_reveal_password=True)
    current_edit_id = [None]

    def on_edit_save(e):
        data = {"domain": tf_edit_domain.value, "username": tf_edit_username.value, "password": tf_edit_password.value}
        if current_edit_id[0] is None:
            resp = client.post("/api/passwords", json=data)
        else:
            resp = client.put(f"/api/passwords/{current_edit_id[0]}", json=data)
            
        if resp.status_code == 200:
            edit_dialog.open = False
            show_success("Saved credentials successfully!")
            refresh_vault()
        else:
            show_error(f"Error: {resp.json().get('detail')}")

    edit_dialog = ft.AlertDialog(
        title=ft.Text("Edit Credentials"),
        content=ft.Column([tf_edit_domain, tf_edit_username, tf_edit_password], tight=True),
        actions=[
            ft.TextButton("Cancel", on_click=lambda e: setattr(edit_dialog, 'open', False) or page.update()),
            ft.ElevatedButton("Save", on_click=on_edit_save)
        ]
    )

    def show_edit_dialog(pw=None):
        if pw:
            edit_dialog.title.value = "Edit Existing Password"
            tf_edit_domain.value = pw['domain']
            tf_edit_username.value = pw['username']
            tf_edit_password.value = pw['password']
            current_edit_id[0] = pw['id']
        else:
            edit_dialog.title.value = "Add New Custom Password"
            tf_edit_domain.value = ""
            tf_edit_username.value = ""
            tf_edit_password.value = ""
            current_edit_id[0] = None
        edit_dialog.open = True
        page.update()

    current_delete_id = [None]
    def on_confirm_delete(e):
        if current_delete_id[0] is not None:
            resp = client.delete(f"/api/passwords/{current_delete_id[0]}")
            if resp.status_code == 200:
                delete_confirm_dialog.open = False
                show_success("Credential deleted.")
                refresh_vault()
            else:
                show_error("Failed to delete.")

    delete_confirm_dialog = ft.AlertDialog(
        title=ft.Text("Confirm Delete"),
        content=ft.Text("Are you sure you want to delete this password?"),
        actions=[
            ft.TextButton("Cancel", on_click=lambda e: setattr(delete_confirm_dialog, 'open', False) or page.update()),
            ft.ElevatedButton("Delete", color=ft.Colors.RED, on_click=on_confirm_delete)
        ]
    )
    def prompt_delete(pw_id):
        current_delete_id[0] = pw_id
        delete_confirm_dialog.open = True
        page.update()
        
    pending_note_pw_id = [None]
    domain_dialog = ft.AlertDialog(
        title=ft.Text(""),
        content=ft.Container(width=500, height=400),
        actions=[ft.TextButton("Close", on_click=lambda e: setattr(domain_dialog, 'open', False) or page.update())]
    )
    
    history_dialog = ft.AlertDialog(
        title=ft.Text("Password History"),
        content=ft.Column(scroll=ft.ScrollMode.AUTO, height=300, width=400),
        actions=[ft.TextButton("Close", on_click=lambda e: setattr(history_dialog, 'open', False) or page.update())]
    )

    page.overlay.extend([change_dialog, reset_dialog, edit_dialog, delete_confirm_dialog, domain_dialog, history_dialog])

    # --- UI Components: Password Generator Tab ---
    gen_length = ft.Slider(min=8, max=64, value=16, label="{value} chars", divisions=56)
    gen_upper = ft.Switch(label="A-Z", value=True)
    gen_lower = ft.Switch(label="a-z", value=True)
    gen_numbers = ft.Switch(label="0-9", value=True)
    gen_symbols = ft.Switch(label="!@#$", value=True)
    tf_generated = ft.TextField(label="Generated Password", read_only=True, expand=True, text_size=20)
    
    def on_generate_click(e):
        import string, random
        chars = ""
        if gen_upper.value: chars += string.ascii_uppercase
        if gen_lower.value: chars += string.ascii_lowercase
        if gen_numbers.value: chars += string.digits
        if gen_symbols.value: chars += string.punctuation
        if not chars:
            show_error("Select at least one character type!")
            return
        length = int(gen_length.value)
        pwd = "".join(random.choice(chars) for _ in range(length))
        tf_generated.value = pwd
        page.update()
        
    btn_generate = ft.ElevatedButton("Offline Generate", icon=ft.Icons.REFRESH, on_click=on_generate_click, height=50)
    btn_copy_gen = ft.IconButton(ft.Icons.COPY, on_click=lambda e: page.set_clipboard(tf_generated.value) or show_success("Copied generated password!"), icon_size=24)
    
    def on_smart_gen_click(e):
        resp = client.get("/api/generate")
        if resp.status_code == 200:
            data = resp.json()
            tf_generated.value = data["generated_password"]
            score = data["score"]
            show_success(f"Smart ML Generated! Style Score: {score:.2f}")
            page.update()
        else:
            show_error("Failed to generate smart password")
            
    btn_smart_gen = ft.ElevatedButton("Smart ML Generate", icon=ft.Icons.AUTO_AWESOME, on_click=on_smart_gen_click, height=50)

    generator_view = ft.Container(padding=24, expand=True, content=ft.Column([
        ft.Text("Password Generator", size=22, weight=ft.FontWeight.W_600, color=TXT),
        ft.Container(height=8),
        ft.Container(bgcolor=CARD, border_radius=12, border=ft.border.all(1, BORDER), padding=24, content=ft.Column([
            ft.Text("CHARACTER OPTIONS", size=11, weight=ft.FontWeight.W_700, color=TXT3, letter_spacing=1.5),
            ft.Row([gen_upper, gen_lower, gen_numbers, gen_symbols], spacing=16),
            ft.Row([ft.Text("Length:", color=TXT2), gen_length], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Container(height=8),
            ft.Row([tf_generated, btn_copy_gen]),
            ft.Container(height=8),
            ft.Row([
                ft.ElevatedButton("Generate", icon=ft.Icons.REFRESH, on_click=on_generate_click, height=44,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), side=ft.border.BorderSide(1, ACCENT))),
                ft.ElevatedButton("Smart ML Generate", icon=ft.Icons.AUTO_AWESOME, on_click=on_smart_gen_click, height=44,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), bgcolor=ACCENT)),
            ], spacing=12)
        ], spacing=10))
    ]))

    # --- UI Components: Audit Dashboard Tab ---
    # --- UI Components: Secure Notes Tab ---
    notes_list_col = ft.Column(spacing=6)

    tf_notes_search = ft.TextField(
        label="Search notes...", prefix_icon=ft.Icons.SEARCH,
        border_radius=8, border_color=BORDER, focused_border_color=ACCENT,
        on_change=lambda e: refresh_notes(e.control.value),
    )
    
    tf_note_title = ft.TextField(label="Note Title")
    tf_note_tags = ft.TextField(label="Tags (comma separated)", width=400)
    cb_hide_content = ft.Checkbox(label="Hide Note Content in Dashboard", value=True)
    tf_note_content = ft.TextField(label="Secure Content", multiline=True, width=400, height=160)
    current_note_id = [None]
    
    def on_note_save(e):
        tags_list = [t.strip() for t in tf_note_tags.value.split(",") if t.strip()]
        data = {"title": tf_note_title.value, "content": tf_note_content.value, "tags": tags_list, "is_hidden": cb_hide_content.value}
        if current_note_id[0] is None:
            resp = client.post("/api/notes", json=data)
        else:
            resp = client.put(f"/api/notes/{current_note_id[0]}", json=data)
            
        if resp.status_code == 200:
            if pending_note_pw_id[0]:
                n_resp = client.get("/api/notes").json()
                note = next((n for n in n_resp if n["title"] == tf_note_title.value), None)
                if note:
                    pw_resp = client.get("/api/passwords").json()
                    pw = next((p for p in pw_resp if p["id"] == pending_note_pw_id[0]), None)
                    if pw:
                        client.put(f"/api/passwords/{pw['id']}", json={
                            "domain": pw["domain"],
                            "username": pw["username"],
                            "password": pw["password"],
                            "note_id": note["id"]
                        })
                pending_note_pw_id[0] = None
        
            edit_note_dialog.open = False
            show_success("Note saved successfully!")
            refresh_notes(tf_notes_search.value)
        else:
            show_error(f"Error: {resp.json().get('detail')}")
            
    edit_note_dialog = ft.AlertDialog(
        title=ft.Text("Secure Note"),
        content=ft.Column([tf_note_title, tf_note_tags, cb_hide_content, tf_note_content], tight=True),
        actions=[
            ft.TextButton("Cancel", on_click=lambda e: setattr(edit_note_dialog, 'open', False) or page.update()),
            ft.ElevatedButton("Save", on_click=on_note_save)
        ]
    )

    def show_edit_note(n=None):
        if n:
            tf_note_title.value = n['title']
            tf_note_tags.value = ", ".join(n.get('tags', []))
            tf_note_content.value = n['content']
            cb_hide_content.value = n.get('is_hidden', True)
            current_note_id[0] = n['id']
            edit_note_dialog.title.value = "Edit Secure Note"
        else:
            tf_note_title.value = ""
            tf_note_tags.value = ""
            tf_note_content.value = ""
            cb_hide_content.value = True
            current_note_id[0] = None
            edit_note_dialog.title.value = "New Secure Note"
        edit_note_dialog.open = True
        page.update()

    current_del_note_id = [None]
    def on_del_note_confirm(e):
        if current_del_note_id[0]:
            resp = client.delete(f"/api/notes/{current_del_note_id[0]}")
            if resp.status_code == 200:
                del_note_dialog.open = False
                show_success("Note deleted.")
                refresh_notes()
            else:
                show_error("Failed to delete note.")

    del_note_dialog = ft.AlertDialog(
        title=ft.Text("Confirm Delete"),
        content=ft.Text("Are you sure you want to permanently delete this secure note?"),
        actions=[
            ft.TextButton("Cancel", on_click=lambda e: setattr(del_note_dialog, 'open', False) or page.update()),
            ft.ElevatedButton("Delete", color=ft.Colors.RED, on_click=on_del_note_confirm)
        ]
    )
    
    def prompt_del_note(nid):
        current_del_note_id[0] = nid
        del_note_dialog.open = True
        page.update()
        
    page.overlay.extend([edit_note_dialog, del_note_dialog])

    def refresh_notes(search_query=""):
        notes_list_col.controls.clear()
        resp = client.get("/api/notes")
        if resp.status_code == 200:
            notes = resp.json()
            sq = search_query.lower() if search_query else None
            for n in notes:
                if sq:
                    if sq not in (n['title'].lower() + " " + " ".join(n.get('tags', [])).lower()): continue
                tags_row = ft.Row([pill(t, ACCENT) for t in n.get('tags', [])], spacing=4, wrap=True)
                is_hidden = n.get('is_hidden', True)
                content_preview = ft.Text("\u2022\u2022\u2022 Protected content \u2022\u2022\u2022", size=12, italic=True, color=TXT3) if is_hidden else ft.Text(n['content'][:120], size=12, color=TXT2)

                def make_toggle_view(txt_control, orig_content):
                    def _toggle(e):
                        if "Protected" in str(txt_control.value):
                            txt_control.value = orig_content[:120]
                            txt_control.italic = False; txt_control.color = TXT2
                        else:
                            txt_control.value = "\u2022\u2022\u2022 Protected content \u2022\u2022\u2022"
                            txt_control.italic = True; txt_control.color = TXT3
                        page.update()
                    return _toggle

                tile = ft.Container(
                    bgcolor=CARD, border_radius=10, border=ft.border.all(1, BORDER), padding=14,
                    content=ft.Column([
                        ft.Row([
                            ft.Icon(ft.Icons.STICKY_NOTE_2, color=GOLD, size=18),
                            ft.Text(n['title'], weight=ft.FontWeight.W_600, size=15, expand=True, color=TXT),
                            ft.IconButton(ft.Icons.VISIBILITY, icon_size=16, icon_color=TXT3, tooltip="Toggle", on_click=make_toggle_view(content_preview, n['content'])),
                            ft.IconButton(ft.Icons.COPY, icon_size=16, icon_color=TXT3, tooltip="Copy", on_click=lambda e, c=n['content']: page.set_clipboard(c) or show_success("Copied!")),
                            ft.IconButton(ft.Icons.EDIT_OUTLINED, icon_size=16, icon_color=TXT3, tooltip="Edit", on_click=lambda e, note=n: show_edit_note(note)),
                            ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_size=16, icon_color=DANGER, tooltip="Delete", on_click=lambda e, nid=n['id']: prompt_del_note(nid)),
                        ]),
                        tags_row, content_preview,
                    ], spacing=6))
                notes_list_col.controls.append(tile)
        page.update()

    notes_view = ft.Container(padding=24, expand=True, content=ft.Column([
        ft.Row([ft.Text("Secure Notes", size=22, weight=ft.FontWeight.W_600, color=TXT), ft.Container(expand=True),
                ft.ElevatedButton("Add Note", icon=ft.Icons.ADD, on_click=lambda e: show_edit_note(None),
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), bgcolor=ACCENT))]),
        ft.Container(height=4), tf_notes_search, ft.Container(height=8),
        ft.Column([notes_list_col], scroll=ft.ScrollMode.AUTO, expand=True)
    ], expand=True))

    settings_view = ft.Container(padding=24, expand=True, content=ft.Column([
        ft.Text("Settings", size=22, weight=ft.FontWeight.W_600, color=TXT), ft.Container(height=8),
        ft.Container(bgcolor=CARD, border_radius=12, border=ft.border.all(1, BORDER), padding=20, content=ft.Column([
            ft.Text("APPEARANCE", size=11, weight=ft.FontWeight.W_700, color=TXT3, letter_spacing=1.5),
            switch_theme,
            ft.Row([tf_settings_hotkey, btn_record_hotkey]),
            dd_settings_position,
        ], spacing=10)),
        ft.Container(height=10),
        ft.Container(bgcolor=CARD, border_radius=12, border=ft.border.all(1, BORDER), padding=20, content=ft.Column([
            ft.Text("ML PROFILING", size=11, weight=ft.FontWeight.W_700, color=TXT3, letter_spacing=1.5),
            ft.Text("Help the ML engine penalise passwords built with your personal info.", size=12, color=TXT3),
            tf_settings_name, tf_settings_words,
        ], spacing=10)),
        ft.Container(height=10),
        ft.ElevatedButton("Save Settings", on_click=save_settings, icon=ft.Icons.SAVE, width=300, height=48,
            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), bgcolor=ACCENT)),
        ft.Container(height=20),
        ft.Container(bgcolor=CARD, border_radius=12, border=ft.border.all(1, f"{DANGER}30"), padding=20, content=ft.Column([
            ft.Text("DANGER ZONE", size=11, weight=ft.FontWeight.W_700, color=DANGER, letter_spacing=1.5),
            ft.Row([
                ft.ElevatedButton("Change Master Password", icon=ft.Icons.VPN_KEY, on_click=lambda e: setattr(change_dialog, 'open', True) or page.update(),
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))),
                ft.ElevatedButton("Reset Entire Vault", icon=ft.Icons.DELETE_FOREVER, color=DANGER, on_click=lambda e: setattr(reset_dialog, 'open', True) or page.update(),
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)))
            ])
        ], spacing=10)),
    ], scroll=ft.ScrollMode.AUTO))

    # ── Vault ──
    vault_list = ft.Column(spacing=4)
    tf_search = ft.TextField(label="Search vault...", prefix_icon=ft.Icons.SEARCH,
        border_radius=8, border_color=BORDER, focused_border_color=ACCENT,
        on_change=lambda e: refresh_vault(e.control.value), expand=True)
    stats_row = ft.Row(spacing=12)

    def on_import_picked(e: ft.FilePickerResultEvent):
        if e.files:
            try:
                with open(e.files[0].path, "r", encoding="utf-8") as f:
                    csv_content = f.read()
                resp = client.post("/api/import", json={"master_password": current_master_password, "csv_content": csv_content})
                if resp.status_code == 200:
                    show_success(f"Imported {resp.json().get('count')} passwords!")
                    refresh_vault()
                else:
                    show_error(f"Import failed: {resp.json().get('detail')}")
            except Exception as ex:
                show_error(f"Failed to read file: {ex}")

    def on_export_picked(e: ft.FilePickerResultEvent):
        if e.path:
            resp = client.post("/api/export", json={"master_password": current_master_password})
            if resp.status_code == 200:
                with open(e.path, "w", encoding="utf-8") as f:
                    f.write(resp.json().get("csv_content"))
                show_success(f"Exported to {e.path}")
            else:
                show_error(f"Export failed: {resp.json().get('detail')}")

    import_picker = ft.FilePicker(on_result=on_import_picked)
    export_picker = ft.FilePicker(on_result=on_export_picked)
    page.overlay.extend([import_picker, export_picker])

    def refresh_vault(search_query=""):
        vault_list.controls.clear()
        stats_row.controls.clear()

        status_resp = client.get("/api/status").json()
        if status_resp.get("master_decayed") and not search_query:
            vault_list.controls.append(ft.Container(
                content=ft.Row([ft.Icon(ft.Icons.WARNING_AMBER, color=DANGER),
                    ft.Text(f"CRITICAL: Master Password decayed (> {status_resp.get('master_ttl_days')} days).",
                            color=DANGER, weight=ft.FontWeight.BOLD)]),
                padding=12, border_radius=8, bgcolor=f"{DANGER}15",
                border=ft.border.all(1, f"{DANGER}40")))

        def toggle_edit(e, tf_un, tf_pw, btn_save):
            tf_un.read_only = not tf_un.read_only
            tf_pw.read_only = not tf_pw.read_only
            btn_save.visible = not btn_save.visible
            page.update()

        def save_pw_inline(pw, new_un, new_pw):
            resp = client.put(f"/api/passwords/{pw['id']}", json={
                "domain": pw["domain"], "username": new_un, "password": new_pw,
                "note_id": pw.get("note_id")})
            if resp.status_code == 200:
                domain_dialog.open = False; show_success("Saved!"); refresh_vault()
            else:
                show_error("Failed to save.")

        def show_history(history_list):
            history_dialog.content.controls.clear()
            if not history_list:
                history_dialog.content.controls.append(ft.Text("No history available."))
            else:
                history_list.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
                for h in history_list:
                    try:
                        dt = datetime.datetime.fromisoformat(h["timestamp"]).strftime("%Y-%m-%d %H:%M")
                    except:
                        dt = h["timestamp"]
                    history_dialog.content.controls.append(ft.Container(
                        bgcolor=CARD, border_radius=8, border=ft.border.all(1, BORDER), padding=10,
                        content=ft.Column([
                            ft.Text(dt, size=11, color=TXT3),
                            ft.Row([
                                ft.TextField(value=h["password"], password=True, can_reveal_password=True, read_only=True, expand=True),
                                ft.IconButton(ft.Icons.COPY, on_click=lambda e, p=h["password"]: page.set_clipboard(p) or show_success("Copied!"))
                            ])])))
            history_dialog.open = True; page.update()

        def prepare_add_note_for_pw(pw):
            domain_dialog.open = False
            pending_note_pw_id[0] = pw['id']
            show_edit_note(None)
            tf_note_tags.value = f"#associated_password, #{pw['domain']}"
            tf_note_title.value = f"Note for {pw['domain']} ({pw['username']})"
            page.update()

        def show_linked_note(n_id):
            n_resp = client.get("/api/notes")
            if n_resp.status_code == 200:
                note = next((n for n in n_resp.json() if n["id"] == n_id), None)
                if note:
                    domain_dialog.open = False; show_edit_note(note)

        def build_account_tab(pw, pw_counts, now):
            tf_un = ft.TextField(label="Username", value=pw['username'], read_only=True)
            tf_pw = ft.TextField(label="Password", value=pw['password'], password=True, can_reveal_password=True, read_only=True)
            btn_save = ft.ElevatedButton("Save", visible=False)
            btn_edit = ft.IconButton(ft.Icons.EDIT, tooltip="Edit mode", on_click=lambda e: toggle_edit(e, tf_un, tf_pw, btn_save))
            btn_save.on_click = lambda e: save_pw_inline(pw, tf_un.value, tf_pw.value)
            btn_copy = ft.IconButton(ft.Icons.COPY, tooltip="Copy", on_click=lambda e: page.set_clipboard(tf_pw.value) or show_success("Copied"))
            btn_delete = ft.IconButton(ft.Icons.DELETE, tooltip="Delete", icon_color=DANGER, on_click=lambda e: (setattr(domain_dialog, 'open', False), prompt_delete(pw['id'])))
            btn_history = ft.TextButton("History", icon=ft.Icons.HISTORY, on_click=lambda e: show_history(pw.get("history", [])))
            if pw.get('note_id'):
                btn_note = ft.ElevatedButton("View Note", icon=ft.Icons.NOTE, on_click=lambda e: show_linked_note(pw['note_id']))
            else:
                btn_note = ft.ElevatedButton("Add Note", icon=ft.Icons.ADD, on_click=lambda e: prepare_add_note_for_pw(pw))
            created_at = datetime.datetime.fromisoformat(pw['created_at'])
            ttl_days = pw.get('ttl_days', 90)
            remaining = ttl_days - (now - created_at).days
            issues = []
            score = pw.get("strength_score", 1.0)
            if score < 0.5: issues.append(pill("Weak", DANGER))
            if pw_counts.get(pw["password"], 0) > 1: issues.append(pill("Reused", WARN))
            if remaining <= 0: issues.append(pill("Expired", DANGER))
            return ft.Container(padding=20, content=ft.Column([
                ft.Row(issues, wrap=True),
                ft.Row([tf_un, tf_pw, btn_copy]),
                ft.Row([btn_edit, btn_save, btn_delete, btn_note, btn_history])
            ], scroll=ft.ScrollMode.AUTO))

        def open_domain_popup(dom, pw_list, pw_counts, now):
            domain_dialog.title.value = f"Accounts for {dom}"
            tabs = ft.Tabs(selected_index=0, expand=True)
            for pw in pw_list:
                tabs.tabs.append(ft.Tab(text=pw['username'], content=build_account_tab(pw, pw_counts, now)))
            domain_dialog.content.content = tabs
            domain_dialog.open = True; page.update()

        resp = client.get("/api/passwords")
        if resp.status_code == 200:
            passwords = resp.json()
            total_count = len(passwords)
            weak_count = sum(1 for p in passwords if p.get("strength_score", 1.0) < 0.5)
            pw_counts = {}
            for p in passwords:
                pw_counts[p["password"]] = pw_counts.get(p["password"], 0) + 1
            reused_count = sum(1 for p in passwords if pw_counts.get(p["password"], 0) > 1)

            now = datetime.datetime.now()
            expired_count = 0
            for p in passwords:
                ca = datetime.datetime.fromisoformat(p['created_at'])
                if (now - ca).days > p.get('ttl_days', 90):
                    expired_count += 1

            if not search_query:
                stats_row.controls.extend([
                    stat_box("Total", total_count, ft.Icons.SHIELD, ACCENT),
                    stat_box("Weak", weak_count, ft.Icons.WARNING_AMBER, WARN),
                    stat_box("Reused", reused_count, ft.Icons.COPY_ALL, GOLD),
                    stat_box("Expired", expired_count, ft.Icons.TIMER_OFF, DANGER),
                ])

            grouped = {}
            sq = search_query.lower() if search_query else None
            for p in passwords:
                if sq and sq not in p['domain'].lower() and sq not in p['username'].lower():
                    continue
                dom = p['domain']
                if dom not in grouped: grouped[dom] = []
                grouped[dom].append(p)

            for dom, pw_list in grouped.items():
                has_decay = any(pw.get('is_decayed', False) for pw in pw_list)
                best_score = min(pw.get('strength_score', 1.0) for pw in pw_list)
                has_notes = any(pw.get('note_id') is not None for pw in pw_list)

                # Build account rows inside the tile
                account_controls = []
                for pw in pw_list:
                    ca = datetime.datetime.fromisoformat(pw['created_at'])
                    ttl_days = pw.get('ttl_days', 90)
                    remaining = ttl_days - (now - ca).days
                    ttl_col = ACCENT if remaining > 30 else (WARN if remaining > 0 else DANGER)
                    ttl_txt = f"{remaining}d" if remaining > 0 else f"Exp"

                    issues = []
                    if pw.get("strength_score", 1.0) < 0.5: issues.append(pill("Weak", DANGER))
                    if pw_counts.get(pw["password"], 0) > 1: issues.append(pill("Reused", WARN))
                    if remaining <= 0: issues.append(pill("Expired", DANGER))

                    account_controls.append(ft.Container(
                        bgcolor=SURFACE, border_radius=8, padding=ft.padding.symmetric(horizontal=14, vertical=10),
                        border=ft.border.all(1, BORDER),
                        content=ft.Row([
                            ft.Icon(ft.Icons.PERSON_OUTLINE, size=16, color=TXT3),
                            ft.Text(pw['username'], size=13, weight=ft.FontWeight.W_500, color=TXT, expand=True),
                            ft.Row(issues, spacing=4),
                            strength_dots(pw.get("strength_score", 1.0)),
                            ft.Container(
                                content=ft.Text(ttl_txt, size=10, weight=ft.FontWeight.W_700, color=ttl_col),
                                bgcolor=f"{ttl_col}15", border_radius=4,
                                padding=ft.padding.symmetric(horizontal=6, vertical=2)),
                            ft.IconButton(ft.Icons.COPY, icon_size=15, icon_color=TXT3, tooltip="Copy",
                                on_click=lambda e, p=pw['password']: page.set_clipboard(p) or show_success("Copied!")),
                            ft.IconButton(ft.Icons.EDIT_OUTLINED, icon_size=15, icon_color=TXT3, tooltip="Edit",
                                on_click=lambda e, p=pw: show_edit_dialog(p)),
                            ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_size=15, icon_color=DANGER, tooltip="Delete",
                                on_click=lambda e, pid=pw['id']: prompt_delete(pid)),
                        ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER)
                    ))

                # Domain letter avatar
                letter = dom[0].upper() if dom else "?"
                border_col = f"{DANGER}60" if has_decay else BORDER

                tile = ft.ExpansionTile(
                    title=ft.Row([
                        ft.Container(
                            content=ft.Text(letter, size=15, weight=ft.FontWeight.BOLD, color="#fff",
                                text_align=ft.TextAlign.CENTER),
                            width=36, height=36, border_radius=8, bgcolor=ACCENT2,
                            alignment=ft.alignment.center),
                        ft.Column([
                            ft.Text(dom, size=14, weight=ft.FontWeight.W_600, color=TXT),
                            ft.Text(f"{len(pw_list)} account{'s' if len(pw_list)>1 else ''}",
                                    size=11, color=TXT3),
                        ], spacing=1, expand=True),
                        ft.Icon(ft.Icons.STICKY_NOTE_2, size=14, color=GOLD) if has_notes else ft.Container(width=0),
                        strength_dots(best_score),
                    ], spacing=10),
                    controls=account_controls,
                    initially_expanded=False,
                    bgcolor=CARD,
                    collapsed_bgcolor=CARD,
                    shape=ft.RoundedRectangleBorder(radius=10),
                    collapsed_shape=ft.RoundedRectangleBorder(radius=10),
                    controls_padding=ft.padding.only(left=12, right=12, bottom=8),
                )
                vault_list.controls.append(
                    ft.Container(content=tile, border=ft.border.all(1, border_col), border_radius=10))
        page.update()

    vault_view = ft.Container(padding=24, expand=True, content=ft.Column([
        ft.Row([
            ft.Text("Vault", size=22, weight=ft.FontWeight.W_600, color=TXT),
            ft.Container(expand=True),
            ft.IconButton(ft.Icons.ADD_CIRCLE_OUTLINE, icon_color=ACCENT, tooltip="Add",
                on_click=lambda e: show_edit_dialog(None)),
            ft.IconButton(ft.Icons.UPLOAD_FILE_OUTLINED, icon_color=TXT3, tooltip="Import CSV",
                on_click=lambda _: import_picker.pick_files(allow_multiple=False, allowed_extensions=["csv"])),
            ft.IconButton(ft.Icons.DOWNLOAD_OUTLINED, icon_color=TXT3, tooltip="Export CSV",
                on_click=lambda _: export_picker.save_file(allowed_extensions=["csv"], file_name="vault_export.csv")),
        ]),
        stats_row,
        ft.Container(height=4),
        tf_search,
        ft.Container(height=8),
        ft.Column([vault_list], scroll=ft.ScrollMode.AUTO, expand=True)
    ], expand=True))

    # ── Sidebar + Layout ──
    nav_icons = [
        (ft.Icons.SHIELD_OUTLINED, ft.Icons.SHIELD, "Vault"),
        (ft.Icons.STICKY_NOTE_2_OUTLINED, ft.Icons.STICKY_NOTE_2, "Notes"),
        (ft.Icons.PASSWORD_OUTLINED, ft.Icons.PASSWORD, "Generator"),
        (ft.Icons.SETTINGS_OUTLINED, ft.Icons.SETTINGS, "Settings"),
    ]
    nav_btns = []
    for i, (icon_off, icon_on, tip) in enumerate(nav_icons):
        nav_btns.append(ft.Container(
            content=ft.Icon(icon_on if i == 0 else icon_off, color=ACCENT if i == 0 else TXT3, size=22),
            width=44, height=44, border_radius=12,
            bgcolor=f"{ACCENT}18" if i == 0 else "transparent",
            alignment=ft.alignment.center, tooltip=tip, ink=True,
            on_click=lambda e, idx=i: switch_tab(idx)))

    def switch_tab(idx):
        selected_nav[0] = idx
        for j, btn in enumerate(nav_btns):
            active = j == idx
            btn.bgcolor = f"{ACCENT}18" if active else "transparent"
            btn.content.name = nav_icons[j][1] if active else nav_icons[j][0]
            btn.content.color = ACCENT if active else TXT3
        views = [vault_view, notes_view, generator_view, settings_view]
        main_content.content = views[idx]
        if idx == 0: refresh_vault()
        elif idx == 1: refresh_notes()
        elif idx == 3: load_settings()
        page.update()

    def on_lock(e):
        client.post("/api/lock")
        nonlocal current_master_password
        current_master_password = ""
        show_auth_screen()

    sidebar = ft.Container(
        width=68, bgcolor=SURFACE,
        border=ft.border.only(right=ft.BorderSide(1, BORDER)),
        padding=ft.padding.symmetric(vertical=12),
        content=ft.Column([
            ft.Container(
                content=ft.Text("LP", size=16, weight=ft.FontWeight.BOLD, color=ACCENT),
                width=40, height=40, border_radius=12, bgcolor=CARD,
                border=ft.border.all(1, GOLD_DIM),
                alignment=ft.alignment.center,
                margin=ft.margin.only(bottom=24)),
            *nav_btns,
            ft.Container(expand=True),
            ft.Container(
                content=ft.IconButton(ft.Icons.LOCK_OUTLINE, icon_color=DANGER, icon_size=20,
                    on_click=on_lock, tooltip="Lock Vault"),
                margin=ft.margin.only(bottom=4)),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4))

    main_content = ft.Container(content=vault_view, expand=True)
    app_layout = ft.Row([sidebar, main_content], expand=True, spacing=0)

    def show_main_app():
        page.clean()
        page.appbar = None
        refresh_vault()
        page.add(app_layout)
        page.update()

    def show_auth_screen():
        page.clean()
        page.appbar = None
        status = client.get("/api/status").json()
        if status["is_setup"]:
            tf_setup_name.visible = False
            btn_setup.visible = False
            btn_login.visible = True
        else:
            tf_setup_name.visible = True
            btn_setup.visible = True
            btn_login.visible = False
        page.add(auth_container)
        page.update()

    # --- Hotkey Integration Logic ---
    import os
    import sys
    import subprocess

    _popup_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "popup.py")

    def _spawn_popup(window_title, hwnd, b64_typed, browser_url):
        try:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 0  # SW_HIDE for the process window; Flet uses FLET_APP_HIDDEN
            subprocess.Popen(
                [sys.executable, _popup_script,
                 window_title, str(hwnd), b64_typed, browser_url],
                startupinfo=si,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except Exception:
            pass

    def handle_global_hotkey(window_title="", hwnd=0, b64_typed="", browser_url=""):
        """Spawn a fresh popup.py process immediately on each hotkey press."""
        threading.Thread(
            target=_spawn_popup,
            args=(window_title, hwnd, b64_typed, browser_url),
            daemon=True
        ).start()

    set_overlay_callback(handle_global_hotkey)

    # Initialize Hotkey from settings payload
    try:
        settings_cache = client.get("/api/settings").json()
        desktop_agent.start_listener(settings_cache.get("hotkey", "ctrl+shift+l"))
    except Exception:
        desktop_agent.start_listener("ctrl+shift+l")

    def on_db_change():
        if page.appbar:
            refresh_vault(tf_search.value)
    backend.ON_DB_UPDATE.append(on_db_change)

    # Initial launch
    show_auth_screen()


if __name__ == "__main__":
    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()
    time.sleep(1)
    ft.app(target=main)

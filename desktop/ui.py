import flet as ft
import sys
import time
import json
import app as backend
from desktop import desktop_agent, set_overlay_callback
import threading
import uvicorn
from fastapi.testclient import TestClient

def run_api():
    uvicorn.run(backend.app, host="127.0.0.1", port=5000, log_level="error")

def main(page: ft.Page):
    page.title = "LocalPass Desktop"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0
    page.window.width = 1100
    page.window.height = 800
    page.window.resizable = True
    page.fonts = {"Inter": "https://raw.githubusercontent.com/rsms/inter/master/docs/font-files/Inter-Regular.woff2"}
    page.theme = ft.Theme(
        font_family="Inter",
        color_scheme_seed=ft.Colors.TEAL_500,
        color_scheme=ft.ColorScheme(
            background="#0b1221", 
            surface="#152036",
            primary="#10b981",
            secondary="#eab308",
            outline="#10b981"
        )
    )
    page.bgcolor = "#0b1221"

    
    client = TestClient(backend.app)

    # State variables
    current_master_password = ""

    # --- SnackBar Helpers ---
    def show_success(msg):
        page.snack_bar = ft.SnackBar(ft.Text(msg), bgcolor=ft.Colors.GREEN_800)
        page.snack_bar.open = True
        page.update()

    def show_error(msg):
        page.snack_bar = ft.SnackBar(ft.Text(msg), bgcolor=ft.Colors.RED_800)
        page.snack_bar.open = True
        page.update()

    # --- UI Components: Auth Screen ---
    tf_master_password = ft.TextField(label="Master Password", password=True, can_reveal_password=True, width=350, border_color="#10b981")
    tf_setup_name = ft.TextField(label="Your Name (For ML Profiling)", width=350, border_color="#10b981")
    lbl_auth_error = ft.Text(color=ft.Colors.RED, size=14)
    
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
        if status.get("is_setup"):
            on_login(e)
        else:
            on_setup(e)

    tf_master_password.on_submit = on_master_password_submit
    tf_setup_name.on_submit = on_setup

    btn_login = ft.ElevatedButton("Unlock Vault", on_click=on_login, width=350, height=45, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), side=ft.border.BorderSide(1, "#eab308")))
    btn_setup = ft.ElevatedButton("Complete Setup", on_click=on_setup, width=350, height=45, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), side=ft.border.BorderSide(1, "#eab308")))
    
    auth_container = ft.Container(
        content=ft.Column(
            [
                ft.Icon(ft.Icons.SHIELD_ROUNDED, size=80, color="#eab308"),
                ft.Text("LocalPass Secure Vault", size=32, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                ft.Container(height=20),
                tf_setup_name,
                tf_master_password,
                ft.Container(height=10),
                btn_login,
                btn_setup,
                lbl_auth_error,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        alignment=ft.alignment.center,
        expand=True,
        gradient=ft.LinearGradient(
            begin=ft.alignment.top_left,
            end=ft.alignment.bottom_right,
            colors=["#0B1221", "#064e3b", "#040812"],
            stops=[0.0, 0.5, 1.0]
        )
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

    generator_view = ft.Container(
        content=ft.Column([
            ft.Text("Password Generator", size=24, weight=ft.FontWeight.BOLD),
            ft.Divider(),
            ft.Text("Password Options", size=18, weight=ft.FontWeight.W_500),
            ft.Row([ft.Text("Length:"), gen_length], alignment=ft.MainAxisAlignment.START),
            ft.Row([gen_upper, gen_lower, gen_numbers, gen_symbols], alignment=ft.MainAxisAlignment.START),
            ft.Container(height=20),
            ft.Row([tf_generated, btn_copy_gen], alignment=ft.MainAxisAlignment.CENTER),
            ft.Row([btn_generate, btn_smart_gen], alignment=ft.MainAxisAlignment.START),
        ]),
        padding=30, expand=True
    )

    # --- UI Components: Audit Dashboard Tab ---
    # --- UI Components: Secure Notes Tab ---
    notes_grid = ft.ResponsiveRow(spacing=15, run_spacing=15, alignment=ft.MainAxisAlignment.START)
    
    tf_notes_search = ft.TextField(
        label="Search Notes (by Title or Tag)...",
        prefix_icon=ft.Icons.SEARCH, border_color="#eab308",
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
        notes_grid.controls.clear()
        resp = client.get("/api/notes")
        if resp.status_code == 200:
            notes = resp.json()
            sq = search_query.lower() if search_query else None
            
            for n in notes:
                if sq:
                    searchable = n['title'].lower() + " " + " ".join(n.get('tags', [])).lower()
                    if sq not in searchable:
                        continue
                        
                btn_edit = ft.IconButton(ft.Icons.EDIT, tooltip="Edit", on_click=lambda e, note=n: show_edit_note(note))
                btn_del = ft.IconButton(ft.Icons.DELETE, tooltip="Delete", icon_color=ft.Colors.RED_400, on_click=lambda e, nid=n['id']: prompt_del_note(nid))
                btn_copy = ft.IconButton(ft.Icons.COPY, tooltip="Copy Context", on_click=lambda e, c=n['content']: page.set_clipboard(c) or show_success("Note copied!"))
                
                tags_row = ft.Row([ft.Container(content=ft.Text(t, size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE), bgcolor="#10b981", border_radius=12, padding=ft.padding.symmetric(horizontal=8, vertical=3)) for t in n.get('tags', [])], wrap=True)
                
                is_hidden = n.get('is_hidden', True)
                display_content = ft.Text("Protected Content (Hidden)", italic=True, color=ft.Colors.WHITE54) if is_hidden else ft.Text(n['content'], size=14, color=ft.Colors.WHITE)
                
                def make_toggle_view(txt_control, orig_content):
                    def _toggle(e):
                        if txt_control.value == "Protected Content (Hidden)":
                            txt_control.value = orig_content
                            txt_control.italic = False
                            txt_control.color = ft.Colors.WHITE
                        else:
                            txt_control.value = "Protected Content (Hidden)"
                            txt_control.italic = True
                            txt_control.color = ft.Colors.WHITE54
                        page.update()
                    return _toggle
                    
                btn_view = ft.IconButton(ft.Icons.VISIBILITY, tooltip="Toggle Content View", on_click=make_toggle_view(display_content, n['content']))
                
                card_container = ft.Container(
                    col={"sm": 12, "md": 6, "lg": 4, "xl": 3},
                    content=ft.Card(
                        elevation=10, shadow_color="#000000",
                        content=ft.Container(
                            padding=15,
                            content=ft.Column([
                                ft.Row([
                                    ft.Icon(ft.Icons.SUBJECT, color=ft.Colors.AMBER_400),
                                    ft.Text(n['title'], weight=ft.FontWeight.BOLD, size=18, expand=True)
                                ]),
                                tags_row,
                                ft.Divider(),
                                display_content,
                                ft.Row([btn_copy, btn_view, btn_edit, btn_del], alignment=ft.MainAxisAlignment.END)
                            ])
                        )
                    )
                )
                notes_grid.controls.append(card_container)
        page.update()

    notes_view = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Text("Secure Notes", size=24, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                ft.ElevatedButton("Add Note", icon=ft.Icons.ADD, on_click=lambda e: show_edit_note(None)),
            ]),
            tf_notes_search,
            ft.Divider(),
            ft.Column([notes_grid], scroll=ft.ScrollMode.AUTO, expand=True)
        ], expand=True),
        padding=30, expand=True
    )

    settings_view = ft.Container(
        content=ft.Column([
            ft.Text("Application Settings", size=24, weight=ft.FontWeight.BOLD),
            ft.Divider(),
            ft.Text("Appearance & Integration", size=18, weight=ft.FontWeight.W_500),
            switch_theme,
            ft.Row([tf_settings_hotkey, btn_record_hotkey], alignment=ft.MainAxisAlignment.START),
            dd_settings_position,
            ft.Container(height=10),
            ft.Text("Machine Learning Profiling", size=18, weight=ft.FontWeight.W_500),
            ft.Text("Provide context so the ML engine can penalize passwords built with your personal info.", color=ft.Colors.WHITE70),
            tf_settings_name,
            tf_settings_words,
            ft.Container(height=10),
            ft.ElevatedButton("Save Settings", on_click=save_settings, icon=ft.Icons.SAVE, width=400, height=60, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10))),
            ft.Container(height=40),
            ft.Text("Danger Zone", size=18, weight=ft.FontWeight.W_500, color=ft.Colors.RED_300),
            ft.Row([
                ft.ElevatedButton("Change Master Password", icon=ft.Icons.VPN_KEY, on_click=lambda e: setattr(change_dialog, 'open', True) or page.update()),
                ft.ElevatedButton("Reset Entire Vault", icon=ft.Icons.DELETE_FOREVER, color=ft.Colors.RED, on_click=lambda e: setattr(reset_dialog, 'open', True) or page.update())
            ])
        ], scroll=ft.ScrollMode.AUTO),
        padding=30, expand=True
    )

    # --- UI Components: Vault Tab ---
    vault_grid = ft.ResponsiveRow(
        spacing=15,
        run_spacing=15,
        alignment=ft.MainAxisAlignment.START,
    )
    lbl_health = ft.Text("Vault Health: Calculating...", size=14, weight=ft.FontWeight.BOLD)
    
    def on_import_picked(e: ft.FilePickerResultEvent):
        if e.files:
            try:
                with open(e.files[0].path, "r", encoding="utf-8") as f:
                    csv_content = f.read()
                resp = client.post("/api/import", json={"master_password": current_master_password, "csv_content": csv_content})
                if resp.status_code == 200:
                    show_success(f"Successfully imported {resp.json().get('count')} passwords (Skipped duplicates)!")
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
                show_success(f"Vault exported successfully to {e.path}")
            else:
                show_error(f"Export failed: {resp.json().get('detail')}")

    import_picker = ft.FilePicker(on_result=on_import_picked)
    export_picker = ft.FilePicker(on_result=on_export_picked)
    page.overlay.extend([import_picker, export_picker])

    tf_search = ft.TextField(
        label="Search Vault...",
        prefix_icon=ft.Icons.SEARCH, border_color="#eab308",
        on_change=lambda e: refresh_vault(e.control.value),
        expand=True,
    )

    def refresh_vault(search_query=""):
        vault_grid.controls.clear()
        
        status_resp = client.get("/api/status").json()
        if status_resp.get("master_decayed") and not search_query:
            vault_grid.controls.append(
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.WARNING_AMBER, color=ft.Colors.RED),
                        ft.Text(f"CRITICAL: Master Password decayed (> {status_resp.get('master_ttl_days')} days).", color=ft.Colors.RED, weight=ft.FontWeight.BOLD)
                    ]),
                    padding=15, border_radius=8, bgcolor=ft.Colors.RED_900,
                )
            )

        def toggle_edit(e, tf_un, tf_pw, btn_save):
            tf_un.read_only = not tf_un.read_only
            tf_pw.read_only = not tf_pw.read_only
            btn_save.visible = not btn_save.visible
            page.update()

        def save_pw_inline(pw, new_un, new_pw):
            resp = client.put(f"/api/passwords/{pw['id']}", json={
                "domain": pw["domain"],
                "username": new_un,
                "password": new_pw,
                "note_id": pw.get("note_id")
            })
            if resp.status_code == 200:
                domain_dialog.open = False
                show_success("Credentials inline saved!")
                refresh_vault()
            else:
                show_error("Failed to save.")

        def show_history(history_list):
            history_dialog.content.controls.clear()
            if not history_list:
                history_dialog.content.controls.append(ft.Text("No history available."))
            else:
                history_list.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
                for h in history_list:
                    import datetime
                    try:
                        dt = datetime.datetime.fromisoformat(h["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
                    except:
                        dt = h["timestamp"]
                    history_dialog.content.controls.append(
                        ft.Card(
                            content=ft.Container(
                                padding=10,
                                content=ft.Column([
                                    ft.Text(f"Date: {dt}", size=12, color=ft.Colors.WHITE54),
                                    ft.Row([
                                        ft.Text("Password:", size=14),
                                        ft.TextField(value=h["password"], password=True, can_reveal_password=True, read_only=True, expand=True),
                                        ft.IconButton(ft.Icons.COPY, on_click=lambda e, p=h["password"]: page.set_clipboard(p) or show_success("Copied history!"))
                                    ])
                                ])
                            )
                        )
                    )
            history_dialog.open = True
            page.update()

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
                n_list = n_resp.json()
                note = next((n for n in n_list if n["id"] == n_id), None)
                if note:
                    domain_dialog.open = False
                    show_edit_note(note)

        def build_account_tab(pw, pw_counts, now):
            tf_un = ft.TextField(label="Username", value=pw['username'], read_only=True)
            tf_pw = ft.TextField(label="Password", value=pw['password'], password=True, can_reveal_password=True, read_only=True)
            
            btn_save = ft.ElevatedButton("Save", visible=False)
            btn_edit = ft.IconButton(ft.Icons.EDIT, tooltip="Edit mode", on_click=lambda e: toggle_edit(e, tf_un, tf_pw, btn_save))
            btn_save.on_click = lambda e: save_pw_inline(pw, tf_un.value, tf_pw.value)
            
            btn_copy = ft.IconButton(ft.Icons.COPY, tooltip="Copy", on_click=lambda e: page.set_clipboard(tf_pw.value) or show_success("Copied"))
            btn_delete = ft.IconButton(ft.Icons.DELETE, tooltip="Delete", icon_color=ft.Colors.RED_400, on_click=lambda e: (setattr(domain_dialog, 'open', False), prompt_delete(pw['id'])))
            btn_history = ft.TextButton("Password History", icon=ft.Icons.HISTORY, on_click=lambda e: show_history(pw.get("history", [])))
            
            if pw.get('note_id'):
                btn_note = ft.ElevatedButton("View Note", icon=ft.Icons.NOTE, on_click=lambda e: show_linked_note(pw['note_id']))
            else:
                btn_note = ft.ElevatedButton("Add Note", icon=ft.Icons.ADD, on_click=lambda e: prepare_add_note_for_pw(pw))
                
            import datetime
            created_at = datetime.datetime.fromisoformat(pw['created_at'])
            ttl_days = pw.get('ttl_days', 90)
            age_days = (now - created_at).days
            remaining_days = ttl_days - age_days
            
            issues = []
            score = pw.get("strength_score", 1.0)
            if score < 0.5:
                issues.append(ft.Container(content=ft.Text("Weak", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE), bgcolor=ft.Colors.RED_700, border_radius=12, padding=ft.padding.symmetric(horizontal=8, vertical=3)))
            if pw_counts.get(pw["password"], 0) > 1:
                issues.append(ft.Container(content=ft.Text("Reused", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE), bgcolor=ft.Colors.ORANGE_800, border_radius=12, padding=ft.padding.symmetric(horizontal=8, vertical=3)))
            if remaining_days <= 0:
                issues.append(ft.Container(content=ft.Text("Expired", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE), bgcolor=ft.Colors.RED_900, border_radius=12, padding=ft.padding.symmetric(horizontal=8, vertical=3)))
                
            tags_row = ft.Row(issues, wrap=True)
            
            return ft.Container(
                padding=20,
                content=ft.Column([
                    tags_row,
                    ft.Row([tf_un, tf_pw, btn_copy]),
                    ft.Row([btn_edit, btn_save, btn_delete, btn_note, btn_history])
                ], scroll=ft.ScrollMode.AUTO)
            )

        def open_domain_popup(dom, pw_list, pw_counts, now):
            domain_dialog.title.value = f"Accounts for {dom}"
            tabs = ft.Tabs(selected_index=0, expand=True)
            for pw in pw_list:
                tabs.tabs.append(ft.Tab(text=pw['username'], content=build_account_tab(pw, pw_counts, now)))
            domain_dialog.content.content = tabs
            domain_dialog.open = True
            page.update()

        resp = client.get("/api/passwords")
        if resp.status_code == 200:
            passwords = resp.json()
            good, decayed = 0, 0
            
            # Map for checking reuse
            pw_counts = {}
            for p in passwords:
                pwd = p["password"]
                pw_counts[pwd] = pw_counts.get(pwd, 0) + 1
            
            # Group by domain
            grouped = {}
            sq = search_query.lower() if search_query else None
            
            for p in passwords:
                if sq and sq not in p['domain'].lower() and sq not in p['username'].lower():
                    continue
                    
                is_dec = p.get('is_decayed', False)
                if is_dec: decayed += 1
                else: good += 1
                
                dom = p['domain']
                if dom not in grouped: grouped[dom] = []
                grouped[dom].append(p)
                
            for dom, pw_list in grouped.items():
                has_decay = any(pw.get('is_decayed', False) for pw in pw_list)
                border_col = ft.Colors.RED_500 if has_decay else ft.Colors.TRANSPARENT
                icon_color = ft.Colors.RED_900 if has_decay else "#10b981"
                
                has_notes = any(pw.get('note_id') is not None for pw in pw_list)
                notes_indicator = ft.Icon(ft.Icons.NOTE, size=16, color=ft.Colors.AMBER_400) if has_notes else ft.Container()
                
                import datetime
                now = datetime.datetime.now()
                
                account_rows = []
                for pw in pw_list:
                    created_at = datetime.datetime.fromisoformat(pw['created_at'])
                    ttl_days = pw.get('ttl_days', 90)
                    age_days = (now - created_at).days
                    remaining_days = ttl_days - age_days
                    
                    ttl_text = ft.Text(f"TTL: {remaining_days} days left", size=10, color=ft.Colors.WHITE54) if remaining_days > 0 else ft.Text(f"Expired {-remaining_days} days ago", size=10, color=ft.Colors.RED_300)
                        
                    issues = []
                    if pw.get("strength_score", 1.0) < 0.5:
                        issues.append(ft.Container(content=ft.Text("Weak", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE), bgcolor=ft.Colors.RED_700, border_radius=12, padding=ft.padding.symmetric(horizontal=8, vertical=3)))
                    if pw_counts.get(pw["password"], 0) > 1:
                        issues.append(ft.Container(content=ft.Text("Reused", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE), bgcolor=ft.Colors.ORANGE_800, border_radius=12, padding=ft.padding.symmetric(horizontal=8, vertical=3)))
                    if remaining_days <= 0:
                        issues.append(ft.Container(content=ft.Text("Expired", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE), bgcolor=ft.Colors.RED_900, border_radius=12, padding=ft.padding.symmetric(horizontal=8, vertical=3)))
                        
                    issues_row = ft.Row(issues, spacing=5, wrap=True, vertical_alignment=ft.CrossAxisAlignment.CENTER) if issues else ft.Container()
                        
                    btn_copy = ft.IconButton(ft.Icons.COPY, tooltip="Copy", icon_size=16, on_click=lambda e, p=pw['password']: page.set_clipboard(p) or show_success("Copied to clipboard"))
                    btn_edit = ft.IconButton(ft.Icons.EDIT, tooltip="Edit", icon_size=16, on_click=lambda e, p=pw: show_edit_dialog(p))
                    btn_delete = ft.IconButton(ft.Icons.DELETE, tooltip="Delete", icon_color=ft.Colors.RED_400, icon_size=16, on_click=lambda e, pid=pw['id']: prompt_delete(pid))
                    
                    account_rows.append(ft.Row([
                        ft.Column([
                            ft.Text(pw['username'], size=12, weight=ft.FontWeight.W_500),
                            ttl_text,
                            issues_row
                        ], expand=True, spacing=1),
                        ft.Row([btn_edit, btn_copy, btn_delete], spacing=0)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN))

                card_container = ft.Container(
                    col={"sm": 12, "md": 6, "lg": 4, "xl": 3},
                    content=ft.Card(
                        elevation=15, shadow_color="#000000",
                        content=ft.Container(
                            padding=15,
                            border=ft.border.all(2, border_col) if has_decay else None,
                            border_radius=8,
                            content=ft.Column([
                                ft.Container(
                                    content=ft.Row([
                                        ft.Container(
                                            content=ft.Icon(ft.Icons.WEB, size=24, color=ft.Colors.WHITE),
                                            bgcolor=icon_color, padding=8, border_radius=8
                                        ),
                                        ft.Text(dom, weight=ft.FontWeight.BOLD, size=18, expand=True)
                                    ]),
                                    on_click=lambda e, dom=dom, pw_list=pw_list, pw_counts=pw_counts, now=now: open_domain_popup(dom, pw_list, pw_counts, now)
                                ),
                                ft.Divider(height=10),
                                ft.Column(account_rows),
                                ft.Row([notes_indicator], alignment=ft.MainAxisAlignment.END)
                            ])
                        )
                    )
                )
                vault_grid.controls.append(card_container)
                
            lbl_health.value = f"Vault Health: {good} Secure, {decayed} Expiring"
            lbl_health.color = ft.Colors.RED if decayed > 0 else ft.Colors.GREEN
        page.update()

    vault_view = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Text("Secure Vault Groups", size=24, weight=ft.FontWeight.BOLD),
                ft.Container(expand=True),
                ft.ElevatedButton("Add", icon=ft.Icons.ADD, on_click=lambda e: show_edit_dialog(None)),
                ft.ElevatedButton("Import CSV", icon=ft.Icons.UPLOAD_FILE, on_click=lambda _: import_picker.pick_files(allow_multiple=False, allowed_extensions=["csv"])),
                ft.ElevatedButton("Export CSV", icon=ft.Icons.DOWNLOAD, on_click=lambda _: export_picker.save_file(allowed_extensions=["csv"], file_name="vault_export.csv")),
            ]),
            ft.Row([tf_search, lbl_health], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Divider(),
            ft.Column([vault_grid], scroll=ft.ScrollMode.AUTO, expand=True)
        ], expand=True),
        padding=30, expand=True
    )

    # --- Main App Layout Architecture ---
    def on_nav_change(e):
        idx = e.control.selected_index
        if idx == 0:
            main_content.content = vault_view
            refresh_vault()
        elif idx == 1:
            main_content.content = notes_view
            refresh_notes()
        elif idx == 2:
            main_content.content = generator_view
        elif idx == 3:
            main_content.content = settings_view
            load_settings()
        page.update()

    nav_rail = ft.NavigationRail(
        selected_index=0, label_type=ft.NavigationRailLabelType.ALL,
        min_width=100, min_extended_width=400, group_alignment=-0.9,
        bgcolor="#152036", indicator_color="#064e3b", indicator_shape=ft.RoundedRectangleBorder(radius=12),
        destinations=[
            ft.NavigationRailDestination(icon=ft.Icons.SHIELD_OUTLINED, selected_icon=ft.Icons.SHIELD, label="Vault"),
            ft.NavigationRailDestination(icon=ft.Icons.SUBJECT_OUTLINED, selected_icon=ft.Icons.SUBJECT, label="Notes"),
            ft.NavigationRailDestination(icon=ft.Icons.PASSWORD_OUTLINED, selected_icon=ft.Icons.PASSWORD, label="Generator"),
            ft.NavigationRailDestination(icon=ft.Icons.SETTINGS_OUTLINED, selected_icon=ft.Icons.SETTINGS, label="Settings"),
        ], on_change=on_nav_change, expand=False
    )

    main_content = ft.Container(content=vault_view, expand=True)
    
    def on_lock(e):
        client.post("/api/lock")
        nonlocal current_master_password
        current_master_password = ""
        show_auth_screen()
        
    app_bar = ft.AppBar(
        leading=ft.Icon(ft.Icons.LOCK_PERSON), leading_width=40,
        title=ft.Text("LocalPass"), center_title=False,
        bgcolor="#152036",
        actions=[ft.IconButton(ft.Icons.LOCK_OUTLINE, tooltip="Lock Vault", on_click=on_lock), ft.Container(width=10)],
    )

    app_layout = ft.Row([nav_rail, ft.VerticalDivider(width=1), main_content], expand=True)

    def show_main_app():
        page.clean()
        page.appbar = app_bar
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

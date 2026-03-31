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
    page.theme = ft.Theme(color_scheme_seed=ft.Colors.INDIGO)
    
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
    tf_master_password = ft.TextField(label="Master Password", password=True, can_reveal_password=True, width=350, border_color=ft.Colors.INDIGO_400)
    tf_setup_name = ft.TextField(label="Your Name (For ML Profiling)", width=350, border_color=ft.Colors.INDIGO_400)
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

    btn_login = ft.ElevatedButton("Unlock Vault", on_click=on_login, width=350, height=45, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)))
    btn_setup = ft.ElevatedButton("Complete Setup", on_click=on_setup, width=350, height=45, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)))
    
    auth_container = ft.Container(
        content=ft.Column(
            [
                ft.Icon(ft.Icons.SHIELD_ROUNDED, size=80, color=ft.Colors.INDIGO_300),
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
            colors=[ft.Colors.BLACK, ft.Colors.INDIGO_900]
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

    page.overlay.extend([change_dialog, reset_dialog, edit_dialog, delete_confirm_dialog])

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
    notes_grid = ft.GridView(expand=True, max_extent=400, child_aspect_ratio=1.5, spacing=15, run_spacing=15)
    
    tf_notes_search = ft.TextField(
        label="Search Notes (by Title or Tag)...",
        prefix_icon=ft.Icons.SEARCH,
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
                
                tags_row = ft.Row([ft.Container(content=ft.Text(t, size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE), bgcolor=ft.Colors.INDIGO_700, border_radius=12, padding=ft.padding.symmetric(horizontal=8, vertical=3)) for t in n.get('tags', [])], wrap=True)
                
                is_hidden = n.get('is_hidden', True)
                display_content = ft.Text("Protected Content (Hidden)", italic=True, color=ft.Colors.WHITE54, expand=True) if is_hidden else ft.Text(n['content'], size=14, color=ft.Colors.WHITE, expand=True, max_lines=4, overflow=ft.TextOverflow.ELLIPSIS)
                
                card = ft.Card(
                    elevation=3,
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
                            ft.Row([btn_copy, btn_edit, btn_del], alignment=ft.MainAxisAlignment.END)
                        ], expand=True)
                    )
                )
                notes_grid.controls.append(card)
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
            notes_grid
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
    vault_grid = ft.GridView(
        expand=True,
        max_extent=400,
        child_aspect_ratio=1.5,
        spacing=15,
        run_spacing=15,
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
        prefix_icon=ft.Icons.SEARCH,
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
                icon_color = ft.Colors.RED_900 if has_decay else ft.Colors.INDIGO_600
                
                # Render account list for this domain
                account_rows = []
                import datetime
                now = datetime.datetime.now()
                
                for pw in pw_list:
                    # Calculate live TTL
                    created_at = datetime.datetime.fromisoformat(pw['created_at'])
                    ttl_days = pw.get('ttl_days', 90)
                    age_days = (now - created_at).days
                    remaining_days = ttl_days - age_days
                    
                    if remaining_days > 0:
                        ttl_text = ft.Text(f"TTL: {remaining_days} days left", size=10, color=ft.Colors.WHITE54)
                    else:
                        ttl_text = ft.Text(f"Expired {-remaining_days} days ago", size=10, color=ft.Colors.RED_300)
                        
                    # Calculate Audit Flags
                    issues = []
                    score = pw.get("strength_score", 1.0)
                    if score < 0.5:
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
                
                card = ft.Card(
                    elevation=4,
                    content=ft.Container(
                        padding=15,
                        border=ft.border.all(2, border_col) if has_decay else None,
                        border_radius=8,
                        content=ft.Column([
                            ft.Row([
                                ft.Container(
                                    content=ft.Icon(ft.Icons.WEB, size=24, color=ft.Colors.WHITE),
                                    bgcolor=icon_color, padding=8, border_radius=8
                                ),
                                ft.Text(dom, weight=ft.FontWeight.BOLD, size=18, expand=True)
                            ]),
                            ft.Divider(height=10),
                            ft.Column(account_rows, scroll=ft.ScrollMode.AUTO, expand=True)
                        ], expand=True)
                    )
                )
                vault_grid.controls.append(card)
                
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
            vault_grid
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
        bgcolor=ft.Colors.BLUE_GREY_900,
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

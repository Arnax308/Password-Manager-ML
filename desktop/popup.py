import flet as ft
import sys
import requests
import time
import threading
import tldextract

def main(page: ft.Page):
    page.title = "LocalPass AutoFill"
    page.window.width = 380
    page.window.height = 480
    page.window.frameless = True
    page.window.always_on_top = True
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 15
    page.theme = ft.Theme(color_scheme_seed=ft.Colors.INDIGO)
    
    window_title = sys.argv[1] if len(sys.argv) > 1 else ""
    hwnd_str = sys.argv[2] if len(sys.argv) > 2 else "0"
    b64_typed = sys.argv[3] if len(sys.argv) > 3 else ""
    browser_url = sys.argv[4] if len(sys.argv) > 4 else ""
    hwnd = int(hwnd_str)
    
    typed_text = ""
    try:
        import base64
        if b64_typed:
            typed_text = base64.b64decode(b64_typed).decode('utf-8')
    except: pass
    
    # Parse structured credential data from desktop.py (tab-separated: user\tpass)
    parts = typed_text.split('\t') if typed_text else []
    guessed_user = parts[0].strip() if len(parts) > 0 else ""
    guessed_pass = parts[1].strip() if len(parts) > 1 else ""
    
    API_URL = "http://127.0.0.1:5000"
    
    def close_app(e):
        page.window.visible = False
        page.update()
        page.window.destroy()

    app_bar = ft.Row([
        ft.Icon(ft.Icons.SHIELD, color=ft.Colors.INDIGO_400),
        ft.Text("AutoFill Request", weight=ft.FontWeight.BOLD, expand=True),
        ft.IconButton(ft.Icons.CLOSE, icon_size=16, on_click=close_app)
    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    try:
        status = requests.get(f"{API_URL}/api/status").json()
        if not status.get("is_unlocked"):
            page.add(app_bar, ft.Divider(), ft.Text("Vault is Locked. Please open main app.", color=ft.Colors.RED_300))
            return
    except:
        page.add(app_bar, ft.Divider(), ft.Text("Could not connect to backend."))
        return

    # Advanced Autotype functionality supporting split logins
    def do_autotype(username, password, mode="both"):
        from pywinauto import keyboard as pykeyboard, application
        if mode != "user":
            page.window.visible = False
            page.update()
        time.sleep(0.1)
        if hwnd:
            try:
                app = application.Application().connect(handle=hwnd)
                app.top_window().set_focus()
                time.sleep(0.1)
                
                if mode == "user":
                    if username:
                        pykeyboard.send_keys(username, with_spaces=True)
                        time.sleep(0.05)
                elif mode == "pass":
                    if password:
                        pykeyboard.send_keys(password, with_spaces=True)
                        time.sleep(0.05)
                else: # both
                    if username:
                        pykeyboard.send_keys(username, with_spaces=True)
                        time.sleep(0.05)
                        
                    pykeyboard.send_keys("{TAB}")
                    time.sleep(0.05)
                    
                    if password:
                        pykeyboard.send_keys(password, with_spaces=True)
                        time.sleep(0.05)
            except Exception:
                pass
        time.sleep(0.5)
        if mode != "user":
            page.window.destroy()

    pw_resp = requests.get(f"{API_URL}/api/passwords")
    all_pws = pw_resp.json() if pw_resp.status_code == 200 else []
    
    wt_lower = window_title.lower()
    best_domain_guess = ""
    
    # Primary: extract domain from actual browser URL (via UI Automation)
    if browser_url:
        ext = tldextract.extract(browser_url)
        if ext.domain and ext.suffix:
            best_domain_guess = f"{ext.domain}.{ext.suffix}"  # e.g. "flipkart.com"
    
    # Fallback: title-based keyword extraction (for non-browser windows)
    if not best_domain_guess:
        title = window_title
        for suffix in [" - Google Chrome", " - Mozilla Firefox", " - Microsoft Edge", " - Microsoft​ Edge", " - Opera", " | Personal"]:
            title = title.replace(suffix, "")
        words = title.replace('-', ' ').replace('|', ' ').split()
        ignored = {"login", "sign", "in", "up", "home", "page", "account", "the", "online", "shopping", "buy", "sell", "welcome"}
        valid_words = [w for w in words if len(w) > 2 and w.lower() not in ignored]
        best_domain_guess = valid_words[0].lower() if valid_words else title.strip().lower()
    
    matches = []
    for p in all_pws:
        dom = p['domain'].lower().replace('https://', '').replace('http://', '').replace('www.', '')
        dom_base = dom.split('.')[0] if '.' in dom else dom
        if dom_base in wt_lower:
            matches.append(p)
            best_domain_guess = p['domain']

    # Views declarations
    list_view = ft.Column(expand=True)
    edit_view = ft.Column(expand=True, visible=False)
    list_container = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True)

    tf_search = ft.TextField(
        label="Search Vault manually...", prefix_icon=ft.Icons.SEARCH,
        height=40, text_size=12, on_change=lambda e: render_list(e.control.value)
    )

    def build_autofill_btn(pw):
        is_missing_user = not pw['username'].strip()
        
        prefill_user = guessed_user
        
        def on_inline_submit(e):
            if tf_inline_user.value and tf_inline_user.value.strip():
                requests.put(f"{API_URL}/api/passwords/{pw['id']}", json={
                    "domain": pw['domain'],
                    "username": tf_inline_user.value.strip(),
                    "password": pw['password']
                })
                tf_inline_user.label = "Saved!"
                tf_inline_user.disabled = True
                page.update()
                
        tf_inline_user = ft.TextField(
            label="Enter missing user (Press Enter to save)", height=35, text_size=12, expand=True, 
            on_submit=on_inline_submit, value=prefill_user if is_missing_user else ""
        ) if is_missing_user else None
        
        user_display = tf_inline_user if is_missing_user else ft.Text(pw['username'], weight=ft.FontWeight.BOLD, size=14)
        
        def handle_fill(mode):
            final_user = pw['username']
            if is_missing_user and tf_inline_user.value and tf_inline_user.value.strip():
                final_user = tf_inline_user.value.strip()
                requests.put(f"{API_URL}/api/passwords/{pw['id']}", json={
                    "domain": pw['domain'], "username": final_user, "password": pw['password']
                })
            threading.Thread(target=do_autotype, args=(final_user, pw['password'], mode)).start()

        smart_alert = None
        if guessed_pass and guessed_pass != pw['password'] and pw['password'] in typed_text:
            smart_alert = ft.Text(f"Password change detected! Click Edit.", color=ft.Colors.ORANGE_400, size=12)
        elif guessed_pass and guessed_pass != pw['password'] and len(guessed_pass) >= 8:
            smart_alert = ft.Text(f"Did you change your password? Click Edit.", color=ft.Colors.ORANGE_300, size=12)
            
        col_content = []
        if smart_alert: col_content.append(smart_alert)
        col_content.append(ft.Row([
            ft.Icon(ft.Icons.PERSON, size=20, color=ft.Colors.INDIGO_300),
            ft.Column([user_display, ft.Text(pw['domain'], size=10, color=ft.Colors.WHITE54)], expand=True, spacing=1),
            ft.IconButton(ft.Icons.EDIT, icon_size=16, tooltip="Edit", on_click=lambda e: show_edit_form(pw)),
        ]))
        col_content.append(ft.Row([
            ft.ElevatedButton("👤 User", tooltip="Fill Username Only", on_click=lambda e: handle_fill("user"), style=ft.ButtonStyle(padding=5)),
            ft.ElevatedButton("🔑 Pass", tooltip="Fill Password Only", on_click=lambda e: handle_fill("pass"), style=ft.ButtonStyle(padding=5)),
            ft.ElevatedButton("Both", tooltip="Fill Both", on_click=lambda e: handle_fill("both"), style=ft.ButtonStyle(padding=5), bgcolor=ft.Colors.INDIGO_700),
        ], alignment=ft.MainAxisAlignment.END, spacing=5))
        
        return ft.Card(
            color=ft.Colors.BLUE_GREY_900,
            content=ft.Container(
                padding=10,
                content=ft.Column(col_content, spacing=10)
            )
        )

    def render_list(query=""):
        list_container.controls.clear()
        target_list = matches
        if query:
            sq = query.lower()
            target_list = [p for p in all_pws if sq in p['domain'].lower() or sq in p['username'].lower()]
            
        if target_list:
            for p in target_list:
                list_container.controls.append(build_autofill_btn(p))
        else:
            list_container.controls.append(ft.Text("No accounts found.", color=ft.Colors.WHITE54))
            
        list_container.controls.append(ft.Container(height=10))
        list_container.controls.append(ft.ElevatedButton("+ Add New Account", width=300, on_click=lambda e: show_edit_form(None)))
        page.update()

    list_view.controls = [
        app_bar,
        ft.Text(f"Detected: {str(window_title)[:30]}...", size=12, color=ft.Colors.WHITE38),
        tf_search,
        ft.Divider(),
        list_container
    ]

    # --- Edit / Add Profile View ---
    tf_edit_dom = ft.TextField(label="Domain/Website")
    tf_edit_user = ft.TextField(label="Username")
    tf_edit_pass = ft.TextField(label="Password", password=True, can_reveal_password=True)
    current_edit_id = [None]
    lbl_ml_suggestion = ft.Text("", size=12, color=ft.Colors.GREEN_400, selectable=True)
    
    def on_save_edit(e, auto_fill=False):
        data = {"domain": tf_edit_dom.value or "", "username": tf_edit_user.value or "", "password": tf_edit_pass.value or ""}
        if current_edit_id[0] is None:
            resp = requests.post(f"{API_URL}/api/passwords", json=data)
        else:
            resp = requests.put(f"{API_URL}/api/passwords/{current_edit_id[0]}", json=data)
            
        if resp.status_code == 200:
            if auto_fill:
                 threading.Thread(target=do_autotype, args=(data['username'], data['password'], "both")).start()
                 return
                 
            nonlocal all_pws, matches
            pw_resp = requests.get(f"{API_URL}/api/passwords")
            all_pws = pw_resp.json() if pw_resp.status_code == 200 else []
            matches.clear()
            for p in all_pws:
                dom = p['domain'].lower().replace('https://', '').replace('http://', '').replace('www.', '')
                dom_base = dom.split('.')[0] if '.' in dom else dom
                if dom_base in wt_lower:
                    matches.append(p)
            tf_search.value = ""
            render_list()
            show_list_view()
        else:
            lbl_ml_suggestion.value = f"Error saving: {resp.json()}"
            lbl_ml_suggestion.color = ft.Colors.RED
            page.update()

    def apply_ml_password(e, pwd):
        tf_edit_pass.value = pwd
        page.update()

    btn_ml_apply = ft.ElevatedButton(
        "Use This Password", icon=ft.Icons.AUTO_AWESOME,
        on_click=lambda e: apply_ml_password(e, lbl_ml_suggestion.data),
        visible=False, bgcolor=ft.Colors.GREEN_900,
        style=ft.ButtonStyle(padding=8)
    )
    btn_ml_regenerate = ft.TextButton(
        "Regenerate", icon=ft.Icons.REFRESH,
        visible=False
    )

    def fetch_ml_suggestion():
        """Fetch ML-generated password and update suggestion UI."""
        lbl_ml_suggestion.value = "⏳ Generating secure password..."
        lbl_ml_suggestion.color = ft.Colors.WHITE54
        btn_ml_apply.visible = False
        btn_ml_regenerate.visible = False
        page.update()
        
        def _fetch():
            try:
                resp = requests.get(f"{API_URL}/api/generate").json()
                gen_pwd = resp.get("generated_password")
                lbl_ml_suggestion.value = f"✨ Suggested: {gen_pwd}\nScore: {resp.get('score')} · TTL: {resp.get('ttl_days')} days"
                lbl_ml_suggestion.color = ft.Colors.GREEN_400
                lbl_ml_suggestion.data = gen_pwd
                btn_ml_apply.visible = True
                btn_ml_regenerate.visible = True
            except:
                lbl_ml_suggestion.value = "Failed to generate password."
                lbl_ml_suggestion.color = ft.Colors.RED_300
                btn_ml_regenerate.visible = True
            page.update()
        
        threading.Thread(target=_fetch, daemon=True).start()

    btn_ml_regenerate.on_click = lambda e: fetch_ml_suggestion()

    def show_edit_form(pw):
        list_view.visible = False
        edit_view.visible = True
        
        if pw:
            # Editing an existing account
            tf_edit_dom.value = pw['domain']
            tf_edit_user.value = pw['username']
            tf_edit_pass.value = pw['password']
            
            # Smart edit: detect if user typed a different password (password change)
            if guessed_pass and guessed_pass != pw['password']:
                lbl_ml_suggestion.value = "Detected updated password typed locally."
                lbl_ml_suggestion.color = ft.Colors.ORANGE_400
                tf_edit_pass.value = guessed_pass
            else:
                lbl_ml_suggestion.value = ""
                
            current_edit_id[0] = pw['id']
            btn_ml_apply.visible = False
            btn_ml_regenerate.visible = False
        else:
            # Adding a new account
            tf_edit_dom.value = best_domain_guess
            tf_edit_user.value = ""  # Leave blank — user enters manually
            tf_edit_pass.value = ""  # Left empty, ML suggestion available via button
            current_edit_id[0] = None
            
            # Auto-fetch an ML password suggestion
            fetch_ml_suggestion()

        page.update()

    def show_list_view(e=None):
        edit_view.visible = False
        list_view.visible = True
        page.update()

    ml_buttons_row = ft.Row(
        [btn_ml_apply, btn_ml_regenerate],
        spacing=10, alignment=ft.MainAxisAlignment.START
    )

    edit_view.controls = [
        ft.Row([
            ft.IconButton(ft.Icons.ARROW_BACK, on_click=show_list_view),
            ft.Text("Edit Credentials", weight=ft.FontWeight.BOLD, expand=True)
        ], alignment=ft.MainAxisAlignment.START),
        ft.Divider(),
        tf_edit_dom,
        tf_edit_user,
        tf_edit_pass,
        lbl_ml_suggestion,
        ml_buttons_row,
        ft.Container(height=10),
        ft.ElevatedButton("Save & AutoFill", on_click=lambda e: on_save_edit(e, auto_fill=True), width=350, bgcolor=ft.Colors.INDIGO_700),
        ft.TextButton("Save only", on_click=lambda e: on_save_edit(e, auto_fill=False), width=350)
    ]

    page.add(list_view, edit_view)
    
    # Auto-Route to Add Mode if absolutely no matches found
    if not matches and window_title:
        show_edit_form(None)
    else:
        render_list()

if __name__ == "__main__":
    ft.app(target=main)

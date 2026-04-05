import flet as ft
import sys
import requests
import time
import threading
import re
import json
import os
from urllib.parse import urlparse

# Use a session and disable proxy to make localhost requests instant (bypasses Windows proxy/DNS delays)
session = requests.Session()
session.trust_env = False  # Ignore HTTP_PROXY and Windows proxies

TRIGGER_FILE = os.path.join(os.environ.get("TEMP", "."), "localpass_popup_trigger.json")

def main(page: ft.Page):
    page.title = "LocalPass AutoFill"
    page.window.width = 380
    page.window.height = 480
    page.window.frameless = True
    page.window.always_on_top = True
    page.window.skip_task_bar = True   # don't steal taskbar focus
    page.window.focus = False          # don't steal keyboard focus on show
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0
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


    def dismiss():
        page.window.visible = False
        page.update()
        page.window.destroy()

    def guess_domain(window_title, browser_url):
        """Extract best domain guess from browser URL or window title."""
        best = ""
        if browser_url:
            try:
                parsed = urlparse(browser_url)
                hostname = parsed.hostname or ""
                if hostname.startswith("www."):
                    hostname = hostname[4:]
                if hostname:
                    best = hostname
            except Exception:
                pass

        if not best:
            title = window_title
            for suffix in [" - Google Chrome", " - Mozilla Firefox", " - Microsoft Edge",
                           " - Microsoft\u200b Edge", " - Opera", " - Brave", " - Vivaldi",
                           " | Personal", " | Work", " - Profile 1", " - Profile 2"]:
                title = title.replace(suffix, "")
            title = title.strip()

            # Strategy 1: domain-like pattern (word.tld)
            found = re.findall(
                r'[\w-]+\.(?:com|org|net|in|co|io|dev|edu|gov|app|me|xyz|info|biz|us|uk|ai|gg|tv)(?:\.[a-z]{2,3})?',
                title, re.IGNORECASE
            )
            if found:
                best = found[0].lower()
            else:
                # Strategy 2: last segment after | or - is typically the site name
                segments = re.split(r'\s*[|\u2013\u2014]\s*|\s+-\s+', title)
                if len(segments) > 1:
                    candidate = segments[-1].strip()
                    if candidate and len(candidate.split()) <= 3:
                        best = candidate.lower().replace(' ', '')

                if not best:
                    # Strategy 3: first meaningful keyword
                    words = title.replace('-', ' ').replace('|', ' ').split()
                    ignored = {"login", "sign", "in", "up", "home", "page", "account", "the",
                               "online", "shopping", "buy", "sell", "welcome", "new", "tab",
                               "and", "for", "with", "your", "free", "best", "india", "official",
                               "site", "website", "log", "my", "get", "app", "web"}
                    valid = [w for w in words if len(w) > 2 and w.lower() not in ignored]
                    best = valid[0].lower() if valid else ""
        return best

    def load_popup(params):
        page.controls.clear()

        window_title = params.get("title", "")
        hwnd = int(params.get("hwnd", "0"))
        b64_typed = params.get("b64_typed", "")
        browser_url = params.get("browser_url", "")

        typed_text = ""
        try:
            import base64
            if b64_typed:
                typed_text = base64.b64decode(b64_typed).decode('utf-8')
        except Exception:
            pass

        parts = typed_text.split('\t') if typed_text else []
        guessed_user = parts[0].strip() if len(parts) > 0 else ""
        guessed_pass = parts[1].strip() if len(parts) > 1 else ""

        API_URL = "http://127.0.0.1:5000"
        
        try:
            settings_resp = session.get(f"{API_URL}/api/settings").json()
            pos = settings_resp.get("popup_position", "top_right")
        except:
            pos = "top_right"

        def make_drag_bar(show_back=False):
            """Returns a WindowDragArea header row. If show_back=True, shows back arrow."""
            if show_back:
                row = ft.Row([
                    ft.IconButton(ft.Icons.ARROW_BACK, icon_size=18, padding=0, on_click=show_list_view),
                    ft.Icon(ft.Icons.SHIELD, color="#10b981"),
                    ft.Text("Edit Credentials", weight=ft.FontWeight.BOLD, expand=True),
                    ft.IconButton(ft.Icons.CLOSE, icon_size=16, padding=0, on_click=lambda e: dismiss())
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER)
            else:
                row = ft.Row([
                    ft.Icon(ft.Icons.SHIELD, color="#10b981"),
                    ft.Text("AutoFill Request", weight=ft.FontWeight.BOLD, expand=True),
                    ft.IconButton(ft.Icons.CLOSE, icon_size=16, padding=0, on_click=lambda e: dismiss())
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER)
            return ft.WindowDragArea(ft.Container(content=row, padding=ft.padding.only(left=15, right=15, top=15, bottom=5)))

        app_bar = make_drag_bar(show_back=False)

        # Show loading indicator, then make window visible
        page.add(
            app_bar,
            ft.Container(
                content=ft.Column([
                    ft.Container(height=100),
                    ft.Row([ft.ProgressRing(width=20, height=20, stroke_width=2), ft.Text("Loading Vault...", color=ft.Colors.WHITE54)], alignment=ft.MainAxisAlignment.CENTER)
                ]),
                padding=ft.padding.only(left=15, right=15, bottom=15),
                expand=True
            )
        )
        import ctypes
        sw = ctypes.windll.user32.GetSystemMetrics(0)
        sh = ctypes.windll.user32.GetSystemMetrics(1)
        MARGIN = 20
        
        if pos == "top_left":
            page.window.left = MARGIN
            page.window.top = MARGIN
        elif pos == "bottom_right":
            page.window.left = sw - 380 - MARGIN
            page.window.top = sh - 480 - MARGIN
        elif pos == "bottom_left":
            page.window.left = MARGIN
            page.window.top = sh - 480 - MARGIN
        else: # top_right defaults
            page.window.left = sw - 380 - MARGIN
            page.window.top = MARGIN
            
        page.window.visible = True
        page.window.opacity = 1
        page.update()

        try:
            status = session.get(f"{API_URL}/api/status").json()
            if not status.get("is_unlocked"):
                page.controls.clear()
                page.add(app_bar, ft.Divider(), ft.Text("Vault is Locked. Please open main app.", color=ft.Colors.RED_300))
                page.update()
                return
        except Exception:
            page.controls.clear()
            page.add(app_bar, ft.Divider(), ft.Text("Could not connect to backend."))
            page.update()
            return

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
                    else:
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
                dismiss()

        pw_resp = session.get(f"{API_URL}/api/passwords")
        all_pws = pw_resp.json() if pw_resp.status_code == 200 else []

        wt_lower = window_title.lower()
        best_domain_guess = guess_domain(window_title, browser_url)

        matches = []
        for p in all_pws:
            dom = p['domain'].lower().replace('https://', '').replace('http://', '').replace('www.', '')
            dom_base = dom.split('.')[0] if '.' in dom else dom
            if dom_base in wt_lower:
                matches.append(p)
                best_domain_guess = p['domain']

        # --- List View ---
        list_view = ft.Column(expand=True)
        edit_view = ft.Column(expand=True, visible=False)
        list_container = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True)

        tf_search = ft.TextField(
            label="Search Vault manually...", prefix_icon=ft.Icons.SEARCH, border_color="#eab308",
            height=40, text_size=12, on_change=lambda e: render_list(e.control.value)
        )

        def build_autofill_btn(pw):
            is_missing_user = not pw['username'].strip()
            prefill_user = guessed_user

            def on_inline_submit(e):
                if tf_inline_user.value and tf_inline_user.value.strip():
                    session.put(f"{API_URL}/api/passwords/{pw['id']}", json={
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
                    session.put(f"{API_URL}/api/passwords/{pw['id']}", json={
                        "domain": pw['domain'], "username": final_user, "password": pw['password']
                    })
                threading.Thread(target=do_autotype, args=(final_user, pw['password'], mode)).start()

            smart_alert = None
            if guessed_pass and guessed_pass != pw['password'] and pw['password'] in typed_text:
                smart_alert = ft.Text("Password change detected! Click Edit.", color=ft.Colors.ORANGE_400, size=12)
            elif guessed_pass and guessed_pass != pw['password'] and len(guessed_pass) >= 8:
                smart_alert = ft.Text("Did you change your password? Click Edit.", color=ft.Colors.ORANGE_300, size=12)

            col_content = []
            if smart_alert:
                col_content.append(smart_alert)
            col_content.append(ft.Row([
                ft.Icon(ft.Icons.PERSON, size=20, color="#eab308"),
                ft.Column([user_display, ft.Text(pw['domain'], size=10, color=ft.Colors.WHITE54)], expand=True, spacing=1),
                ft.IconButton(ft.Icons.EDIT, icon_size=16, tooltip="Edit", on_click=lambda e: show_edit_form(pw)),
            ]))
            col_content.append(ft.Row([
                ft.ElevatedButton("\U0001f464 User", tooltip="Fill Username Only", on_click=lambda e: handle_fill("user"), style=ft.ButtonStyle(padding=5)),
                ft.ElevatedButton("\U0001f511 Pass", tooltip="Fill Password Only", on_click=lambda e: handle_fill("pass"), style=ft.ButtonStyle(padding=5)),
                ft.ElevatedButton("Both", tooltip="Fill Both", on_click=lambda e: handle_fill("both"), style=ft.ButtonStyle(padding=5), bgcolor="#10b981"),
            ], alignment=ft.MainAxisAlignment.END, spacing=5))

            return ft.Card(
                color="#152036",
                elevation=10, shadow_color="#000000",
                content=ft.Container(padding=15, border_radius=8, content=ft.Column(col_content, spacing=10))
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
            ft.Container(
                content=ft.Column([
                    ft.Text(f"Detected: {str(window_title)[:30]}...", size=12, color=ft.Colors.WHITE38),
                    tf_search,
                    ft.Divider(),
                    list_container
                ], expand=True),
                padding=ft.padding.only(left=15, right=15, bottom=15),
                expand=True
            )
        ]

        # --- Edit / Add View ---
        tf_edit_dom = ft.TextField(label="Domain/Website")
        tf_edit_user = ft.TextField(label="Username")
        tf_edit_pass = ft.TextField(label="Password", password=True, can_reveal_password=True)
        current_edit_id = [None]
        lbl_ml_suggestion = ft.Text("", size=12, color=ft.Colors.GREEN_400, selectable=True)

        def on_save_edit(e, auto_fill=False):
            data = {"domain": tf_edit_dom.value or "", "username": tf_edit_user.value or "", "password": tf_edit_pass.value or ""}
            if current_edit_id[0] is None:
                resp = session.post(f"{API_URL}/api/passwords", json=data)
            else:
                resp = session.put(f"{API_URL}/api/passwords/{current_edit_id[0]}", json=data)

            if resp.status_code == 200:
                if auto_fill:
                    threading.Thread(target=do_autotype, args=(data['username'], data['password'], "both")).start()
                    return

                nonlocal all_pws, matches
                pw_resp2 = session.get(f"{API_URL}/api/passwords")
                all_pws = pw_resp2.json() if pw_resp2.status_code == 200 else []
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
            lbl_ml_suggestion.value = "\u23f3 Generating secure password..."
            lbl_ml_suggestion.color = ft.Colors.WHITE54
            btn_ml_apply.visible = False
            btn_ml_regenerate.visible = False
            page.update()

            def _fetch():
                try:
                    resp = session.get(f"{API_URL}/api/generate").json()
                    gen_pwd = resp.get("generated_password")
                    lbl_ml_suggestion.value = f"\u2728 Suggested: {gen_pwd}\nScore: {resp.get('score')} \u00b7 TTL: {resp.get('ttl_days')} days"
                    lbl_ml_suggestion.color = ft.Colors.GREEN_400
                    lbl_ml_suggestion.data = gen_pwd
                    btn_ml_apply.visible = True
                    btn_ml_regenerate.visible = True
                except Exception:
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
                tf_edit_dom.value = pw['domain']
                tf_edit_user.value = pw['username']
                tf_edit_pass.value = pw['password']

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
                tf_edit_dom.value = best_domain_guess
                tf_edit_user.value = ""
                tf_edit_pass.value = ""
                current_edit_id[0] = None
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
            make_drag_bar(show_back=True),
            ft.Container(
                content=ft.Column([
                    ft.Divider(),
                    tf_edit_dom,
                    tf_edit_user,
                    tf_edit_pass,
                    lbl_ml_suggestion,
                    ml_buttons_row,
                    ft.Container(height=10),
                    ft.ElevatedButton("Save & AutoFill", on_click=lambda e: on_save_edit(e, auto_fill=True), width=350, bgcolor="#10b981"),
                    ft.TextButton("Save only", on_click=lambda e: on_save_edit(e, auto_fill=False), width=350)
                ], expand=True),
                padding=ft.padding.only(left=15, right=15, bottom=15),
                expand=True
            )
        ]

        page.controls.clear()
        page.add(list_view, edit_view)
        page.update()

        if not matches and window_title:
            show_edit_form(None)
        else:
            render_list()

    # Always launched fresh per hotkey press — just read args
    load_popup({
        "title": sys.argv[1] if len(sys.argv) > 1 else "",
        "hwnd": sys.argv[2] if len(sys.argv) > 2 else "0",
        "b64_typed": sys.argv[3] if len(sys.argv) > 3 else "",
        "browser_url": sys.argv[4] if len(sys.argv) > 4 else "",
    })

if __name__ == "__main__":
    ft.app(target=main, view=ft.AppView.FLET_APP_HIDDEN)

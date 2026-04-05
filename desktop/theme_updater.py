import os

ui_path = r"c:\Users\Arnav\OneDrive\Documents\Self Apps\LocalPass\desktop\ui.py"
popup_path = r"c:\Users\Arnav\OneDrive\Documents\Self Apps\LocalPass\desktop\popup.py"

def update_file(path):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # Base page settings
    if "page.theme = ft.Theme(color_scheme_seed=ft.Colors.INDIGO)" in content:
        theme = """    page.fonts = {"Inter": "https://raw.githubusercontent.com/rsms/inter/master/docs/font-files/Inter-Regular.woff2"}
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
"""
        content = content.replace("    page.theme = ft.Theme(color_scheme_seed=ft.Colors.INDIGO)", theme)
    
    # TextFields and UI components replacements
    content = content.replace("ft.Colors.INDIGO_400", '"#10b981"')
    content = content.replace("ft.Colors.INDIGO_300", '"#eab308"') # Making some gold
    content = content.replace("ft.Colors.INDIGO_600", '"#10b981"')
    content = content.replace("ft.Colors.INDIGO_700", '"#10b981"')
    content = content.replace("ft.Colors.INDIGO_800", '"#059669"')
    content = content.replace("ft.Colors.INDIGO_900", '"#064e3b"')
    content = content.replace("ft.Colors.INDIGO", '"#10b981"')
    
    content = content.replace("ft.Colors.BLUE_GREY_900", '"#152036"')
    content = content.replace("ft.Colors.BLACK", '"#040812"')
    
    # Specific targeted replacements for Golden accents
    # Vault search outline
    content = content.replace('prefix_icon=ft.Icons.SEARCH,', 'prefix_icon=ft.Icons.SEARCH, border_color="#eab308",')
    # Login buttons 
    content = content.replace('shape=ft.RoundedRectangleBorder(radius=8)', 'shape=ft.RoundedRectangleBorder(radius=8), side=ft.border.BorderSide(1, "#eab308")')
    if "elevation=3" in content:
        content = content.replace("elevation=3", 'elevation=10, shadow_color="#000000"')
    if "elevation=4" in content:
        content = content.replace("elevation=4", 'elevation=15, shadow_color="#000000"')
        
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

update_file(ui_path)
update_file(popup_path)
print("Updated themes applied successfully.")

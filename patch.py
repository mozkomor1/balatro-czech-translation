import os
import shutil
import subprocess
import time
import zipfile
import customtkinter as ctk
import tkinter.filedialog
import re
import psutil

lua_entry_lang = """['cs'] = {font = 10, label = "Česky", key = 'cs', beta=nil, button = "Jazyková zpětná vazba", warning = {'Tento jazyk je stále v beta verzi. Chcete-li nám pomoci','vylepšit ho, klikněte prosím na tlačítko zpětné vazby.', 'Klikněte znovu pro potvrzení.'}},"""
lua_entry_font = """{file = "resources/fonts/m6x11pluscs.ttf", render_scale = self.TILESIZE*10, TEXT_HEIGHT_SCALE = 0.83, TEXT_OFFSET = {x=10,y=-20}, FONTSCALE = 0.1, squish = 1, DESCSCALE = 1},"""

def patch_language(lua_file, lua_entry_lang, lua_entry_font):
    with open(lua_file, "rb") as f:
        content = f.read().decode("utf-8", errors="ignore")

    # Patch self.LANGUAGES block
    pattern_lang = r"(self\.LANGUAGES\s*=\s*{)(.*?)(\n\s*})"
    def insert_lang(match):
        start, body, end = match.groups()
        if lua_entry_lang.strip() in body:
            return match.group(0)
        lines = body.splitlines()
        indent = re.match(r"(\s*)", lines[-1]).group(1) if lines else "    "
        new_entry_indented = "\n" + indent + lua_entry_lang.strip()
        new_body = body.rstrip() + new_entry_indented
        return start + new_body + end
    content_lang = re.sub(pattern_lang, insert_lang, content, flags=re.DOTALL)

    # Patch self.FONTS block only, using the already patched LANGUAGES content
    pattern_fonts = r"(self\.FONTS\s*=\s*{)(.*?)(\n\s*})"
    def insert_fonts(match):
        start, body, end = match.groups()
        if lua_entry_font.strip() in body:
            return match.group(0)
        lines = body.splitlines()
        indent = re.match(r"(\s*)", lines[-1]).group(1) if lines else "    "
        new_entry_indented = "\n" + indent + lua_entry_font.strip()
        new_body = body.rstrip() + new_entry_indented
        return start + new_body + end
    content_final = re.sub(pattern_fonts, insert_fonts, content_lang, flags=re.DOTALL)

    with open(lua_file, "w", encoding="utf-8") as f:
        f.write(content_final)
    print(f"Added new entries to {lua_file}")

def remove_patch_lua(lua_file, lua_entry_lang, lua_entry_font):
    with open(lua_file, "rb") as f:
        content = f.read().decode("utf-8", errors="ignore")
    # Remove language entry
    escaped_lang = re.escape(lua_entry_lang.strip())
    pattern_lang = rf",?\s*{escaped_lang}"
    content = re.sub(pattern_lang, "", content, flags=re.DOTALL)
    # Remove font entry
    escaped_font = re.escape(lua_entry_font.strip())
    pattern_font = rf",?\s*{escaped_font}"
    content = re.sub(pattern_font, "", content, flags=re.DOTALL)
    with open(lua_file, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Removed language and font entries from {lua_file}")

def check_patch_lua(lua_file, lua_entry_lang, lua_entry_font):
    with open(lua_file, "rb") as f:
        content = f.read().decode("utf-8", errors="ignore")
    escaped_lang = re.escape(lua_entry_lang.strip())
    escaped_font = re.escape(lua_entry_font.strip())
    pattern_lang = rf"{escaped_lang}"
    pattern_font = rf"{escaped_font}"
    lang_found = bool(re.search(pattern_lang, content, flags=re.DOTALL))
    font_found = bool(re.search(pattern_font, content, flags=re.DOTALL))
    return lang_found and font_found


# Installer window using CustomTkinter
class InstallerWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Balatro CZ Patch Installer")
        self.geometry("400x300")
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        # Status label at the top
        self.status_var = ctk.StringVar()
        self.label_status = ctk.CTkLabel(self, textvariable=self.status_var, text_color="orange")
        self.label_status.pack(pady=(10, 0))

        # Example variables (add more as needed)
        self.var_game_path = ctk.StringVar()
        self.var_backup = ctk.BooleanVar()

        # Game path input
        self.label_game_path = ctk.CTkLabel(self, text="Game Path:")
        self.label_game_path.pack(pady=(20, 0))

        # Frame for entry and browse button
        self.frame_game_path = ctk.CTkFrame(self)
        self.frame_game_path.pack(pady=5)
        self.entry_game_path = ctk.CTkEntry(self.frame_game_path, textvariable=self.var_game_path, width=220)
        self.entry_game_path.pack(side="left", padx=(0, 5))
        self.button_browse = ctk.CTkButton(self.frame_game_path, text="Browse", command=self.browse_folder, width=70)
        self.button_browse.pack(side="left")

        # Frame for Patch and Restore buttons
        self.frame_buttons = ctk.CTkFrame(self)
        self.frame_buttons.pack(pady=20)
        self.button_patch = ctk.CTkButton(self.frame_buttons, text="Patch", command=self.on_patch, width=100)
        self.button_patch.pack(side="left", padx=(0, 10))
        self.button_restore = ctk.CTkButton(self.frame_buttons, text="Restore", command=self.on_restore, width=100)
        self.button_restore.pack(side="left")

    def browse_folder(self):
        folder_selected = tkinter.filedialog.askdirectory()
        if folder_selected:
            self.var_game_path.set(folder_selected)

    def on_patch(self):
        try:
            # ['cz_cs'] = {font = 6, label = "Česky", key = 'cz_cs', beta=true, button = "Jazyková zpětná vazba", warning = {'Tento jazyk je stále v beta verzi. Chcete-li nám pomoci','vylepšit ho, klikněte prosím na tlačítko zpětné vazby.', 'Klikněte znovu pro potvrzení.'}},
            # into self.LANGUAGES in game.lua
            # You can also return or process these variables as needed
            if not self.var_game_path.get() and os.path.exists(self.var_game_path.get()):
                msg = "Please select a valid path"
                self.status_var.set(msg)
                return msg
            
            # if file named balatro.exe exists, continue, else msg = isnt balatro folder
            if not os.path.exists(os.path.join(self.var_game_path.get(), "balatro.exe")):
                msg = "Selected folder is not a valid Balatro folder"
                self.status_var.set(msg)
                return msg

            if os.path.exists(self.var_game_path.get() + "/balatro.exe.bak"):
                msg = "Patch already applied"
                self.status_var.set(msg)
                return msg
                
            shutil.copy(self.var_game_path.get() + "/balatro.exe", self.var_game_path.get() + "/balatro.exe.bak")
            #open balatro.exe as zip and extract game.lua and put cz_cs.lua into localization folder
            with zipfile.ZipFile(os.path.join(self.var_game_path.get(), "balatro.exe"), 'r') as zip_ref:
                extract_path = self.var_game_path.get()
                zip_ref.extract("game.lua", extract_path)
                # wait until game.lua is fully extracted
                while not os.path.exists(os.path.join(self.var_game_path.get(), "game.lua")):
                    time.sleep(0.5)
                    print("Waiting for game.lua to be extracted...")
                    
                if check_patch_lua(self.var_game_path.get()+"/game.lua", lua_entry_lang, lua_entry_font):
                    msg = "Patch already applied"
                    self.status_var.set(msg)
                    return msg
                    
                patch_language(self.var_game_path.get()+"/game.lua",lua_entry_lang=lua_entry_lang, lua_entry_font=lua_entry_font)

            subprocess.run([
                "7-ZipPortable/App/7-Zip64/7z.exe", "u", self.var_game_path.get()+"/balatro.exe", self.var_game_path.get()+"/game.lua",
            ])
            
            os.makedirs("resources/fonts", exist_ok=True)
            shutil.copy("assets/fonts/m6x11pluscs.ttf", "resources/fonts/m6x11pluscs.ttf")
            
            subprocess.run([
                "7-ZipPortable/App/7-Zip64/7z.exe", "u", self.var_game_path.get()+"/balatro.exe", "localization/cs.lua"
            ])
            subprocess.run([
                "7-ZipPortable/App/7-Zip64/7z.exe", "u", self.var_game_path.get()+"/balatro.exe", "resources/fonts/m6x11pluscs.ttf"
            ])
            os.remove(self.var_game_path.get() + "/game.lua")
            os.remove("resources/fonts/m6x11pluscs.ttf")
            os.rmdir("resources/fonts")
            os.rmdir("resources")

            msg = "Patch applied successfully.\nYou can now open the game and select Czech."
            self.status_var.set(msg)
            return msg
        except PermissionError as e:
            # Attempt to kill balatro.exe if PermissionError occurs
            for proc in psutil.process_iter(['name']):
                if proc.info['name'] and proc.info['name'].lower() == 'balatro.exe':
                    proc.kill()
                    print("Killed balatro.exe due to PermissionError.")
            # Optionally, retry the operation or show a message
            msg = f"PermissionError: {e}. If Balatro was running, it has been closed. Please try again."
            self.status_var.set(msg)
            return msg

    def on_restore(self):
        
        if not self.var_game_path.get() and os.path.exists(self.var_game_path.get()):
            msg = "Please select a valid path"
            self.status_var.set(msg)
            return msg
        
        # if file named balatro.exe exists, continue, else msg = isnt balatro folder
        if not os.path.exists(os.path.join(self.var_game_path.get(), "balatro.exe")):
            msg = "Selected folder is not a valid Balatro folder"
            self.status_var.set(msg)
            return msg

        # Implement restore functionality here
        if not os.path.exists(self.var_game_path.get() + "/balatro.exe.bak"):
            msg = "No backup found, please patch first, or supply backup as balatro.exe.bak in game folder"
            self.status_var.set(msg)
            return msg
        os.remove(self.var_game_path.get() + "/balatro.exe")
        shutil.copy(self.var_game_path.get() + "/balatro.exe.bak", self.var_game_path.get() + "/balatro.exe")
        os.remove(self.var_game_path.get() + "/balatro.exe.bak")
        msg = "Patch restored successfully.\nYou can now open the game without the patch."
        self.status_var.set(msg)
        return msg

if __name__ == "__main__":
    app = InstallerWindow()
    app.mainloop()

import os
import customtkinter as ctk
import tkinter.messagebox
import keyring
from src.core.translations import translator
from src.core.logger import setup_logger
import logging

logger = logging.getLogger(__name__)

class SettingsFrame(ctk.CTkFrame):
    def __init__(self, parent, config_manager, app_instance):
        super().__init__(parent, fg_color="transparent")
        self.config_manager = config_manager
        self.app = app_instance
        
        self.grid_columnconfigure(0, weight=1)
        
        title = ctk.CTkLabel(self, text="Einstellungen", font=ctk.CTkFont(size=28, weight="bold"))
        title.grid(row=0, column=0, pady=(20, 30), sticky="w", padx=20)
        
        content = ctk.CTkFrame(self, corner_radius=15)
        content.grid(row=1, column=0, sticky="nsew", padx=20)
        content.grid_columnconfigure(1, weight=1)
        
        row_idx = 0
        
        # Appearance Mode
        ctk.CTkLabel(content, text="Erscheinungsbild:", font=ctk.CTkFont(weight="bold")).grid(row=row_idx, column=0, padx=20, pady=20, sticky="w")
        self.settings_mode_switch = ctk.CTkSwitch(content, text=translator.get(self.app.lang, 'switch_dark'), command=self.toggle_appearance_mode)
        if self.config_manager.get("appearance_mode", "Light") == "Dark":
            self.settings_mode_switch.select()
        self.settings_mode_switch.grid(row=row_idx, column=1, padx=20, pady=20, sticky="w")
        row_idx += 1
        
        # Language
        ctk.CTkLabel(content, text="Sprache:", font=ctk.CTkFont(weight="bold")).grid(row=row_idx, column=0, padx=20, pady=20, sticky="w")
        self.settings_lang = ctk.CTkSegmentedButton(content, values=["DE", "IT"], command=self.app.change_language)
        self.settings_lang.set(self.config_manager.get("language", "DE"))
        self.settings_lang.grid(row=row_idx, column=1, padx=20, pady=20, sticky="w")
        row_idx += 1
        
        # API Key
        ctk.CTkLabel(content, text="Gemini API Key:", font=ctk.CTkFont(weight="bold")).grid(row=row_idx, column=0, padx=20, pady=20, sticky="w")
        self.api_key_entry = ctk.CTkEntry(content, width=300, show="*")
        self.api_key_entry.grid(row=row_idx, column=1, padx=20, pady=20, sticky="w")
        
        try:
            saved_key = keyring.get_password("BuchhaltungApp", "GeminiAPI")
            if saved_key:
                self.api_key_entry.insert(0, saved_key)
            else:
                # Fallback: check old .env file and migrate if present
                env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "Systemdaten", "gemini_key.env")
                if os.path.exists(env_path):
                    with open(env_path, "r", encoding="utf-8") as f:
                        content_key = f.read().strip()
                        if content_key.startswith("GEMINI_API_KEY="):
                            content_key = content_key.split("=", 1)[1].strip('"').strip("'")
                            self.api_key_entry.insert(0, content_key)
                            keyring.set_password("BuchhaltungApp", "GeminiAPI", content_key)
                            # optional: os.remove(env_path) to secure it
        except Exception as e:
            logger.error(f"Fehler beim Laden des API-Keys: {e}")
                
        row_idx += 1
        
        # Globale Begriffe Button
        ctk.CTkLabel(content, text="Deduplizierung:", font=ctk.CTkFont(weight="bold")).grid(row=row_idx, column=0, padx=20, pady=20, sticky="w")
        btn_globale_begriffe = ctk.CTkButton(content, text="Globale Begriffsliste bearbeiten", command=self.app.open_globale_begriffe)
        btn_globale_begriffe.grid(row=row_idx, column=1, padx=20, pady=20, sticky="w")
        
        row_idx += 1
        
        # Save Button
        btn_save = ctk.CTkButton(content, text="Speichern", command=self.save_settings)
        btn_save.grid(row=row_idx, column=1, padx=20, pady=30, sticky="e")
        
    def toggle_appearance_mode(self):
        mode = self.settings_mode_switch.get()
        new_mode = "Dark" if mode == 1 else "Light"
        ctk.set_appearance_mode(new_mode)
        self.config_manager.set("appearance_mode", new_mode)
        
    def update_ui_text(self, lang):
        self.settings_mode_switch.configure(text=translator.get(lang, 'switch_dark'))

    def save_settings(self):
        key_val = self.api_key_entry.get().strip()
        try:
            if key_val:
                keyring.set_password("BuchhaltungApp", "GeminiAPI", key_val)
            else:
                try:
                    keyring.delete_password("BuchhaltungApp", "GeminiAPI")
                except keyring.errors.PasswordDeleteError:
                    pass
        except Exception as e:
            logger.error(f"Fehler beim Speichern des API-Keys: {e}")
            
        tkinter.messagebox.showinfo("Erfolg", "Einstellungen gespeichert!")

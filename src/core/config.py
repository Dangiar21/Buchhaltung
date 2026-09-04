import json
import os

class ConfigManager:
    def __init__(self, config_path="config.json"):
        self.config_path = config_path
        self.default_config = {
            "language": "DE",
            "appearance_mode": "Light",
            "last_client": None,
            "recent_clients": [],
            "shorten_desc": False,
            "confidence_threshold": 8
        }
        self.config = self.load()

    def load(self):
        if not os.path.exists(self.config_path):
            self.save(self.default_config)
            return self.default_config
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Merge defaults for missing keys
                for k, v in self.default_config.items():
                    if k not in data:
                        data[k] = v
                return data
        except Exception as e:
            print(f"Fehler beim Laden der Konfiguration: {e}")
            return self.default_config

    def save(self, data=None):
        if data is not None:
            self.config = data
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Fehler beim Speichern der Konfiguration: {e}")

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self.save()
        
    def add_recent_client(self, client_name):
        recents = self.get("recent_clients", [])
        if client_name in recents:
            recents.remove(client_name)
        recents.insert(0, client_name)
        # Keep only top 3
        recents = recents[:3]
        self.set("recent_clients", recents)

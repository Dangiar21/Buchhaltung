import os
import json

class Translator:
    def __init__(self):
        self.locales_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'locales')
        self.translations = {}
        self.load_translations()

    def load_translations(self):
        for lang in ['de', 'it']:
            path = os.path.join(self.locales_dir, f"{lang}.json")
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    self.translations[lang.upper()] = json.load(f)
            else:
                self.translations[lang.upper()] = {}

    def get(self, lang, key, default=None):
        lang = lang.upper()
        if lang in self.translations and key in self.translations[lang]:
            return self.translations[lang][key]
        if 'DE' in self.translations and key in self.translations['DE']:
            return self.translations['DE'][key]
        return default or key

translator = Translator()

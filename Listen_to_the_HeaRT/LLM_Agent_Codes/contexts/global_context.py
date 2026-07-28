import json
import os


class GlobalContext:
    def __init__(self):
        self._store = {}

    def set(self, key, value):
        self._store[key] = value

    def get(self, key, default=None):
        return self._store.get(key, default)

    def visualize(self):
        print("=== GLOBAL CONTEXT ===")
        print(json.dumps(self._store, indent=2))
        print("======================")

    def save(self, filepath):
        with open(filepath, "w") as f:
            json.dump(self._store, f, indent=2)

    def load(self, filepath):
        if os.path.exists(filepath):
            with open(filepath, "r") as f:
                self._store = json.load(f)
        else:
            self._store = {}

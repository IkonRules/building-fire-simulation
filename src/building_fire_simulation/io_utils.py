"""Small serialization helpers."""
import pickle
from pathlib import Path

def save_pickle(obj, filepath):
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with filepath.open("wb") as f:
        pickle.dump(obj, f)

def load_pickle(filepath):
    with Path(filepath).open("rb") as f:
        return pickle.load(f)

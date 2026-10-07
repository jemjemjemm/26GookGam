import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class ManagedConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()

def connect(path=None):
    path = Path(path or ROOT / 'data/demo.sqlite3')
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=20, factory=ManagedConnection)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA journal_mode=WAL')
    db.executescript((ROOT / 'db/schema.sql').read_text(encoding='utf-8'))
    return db

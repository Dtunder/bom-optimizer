import sqlite3
import json
import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "cache" / "bom_history.db"

def init_db():
    """Initializes the database and creates tables if they don't exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Table for BOM uploads
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS boms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            filename TEXT,
            item_count INTEGER
        )
    ''')
    
    # Table for optimization results
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bom_id INTEGER,
            timestamp TEXT,
            total_cost REAL,
            result_json TEXT,
            FOREIGN KEY (bom_id) REFERENCES boms (id)
        )
    ''')
    
    conn.commit()
    conn.close()

def save_bom(filename: str, item_count: int) -> int:
    """Saves a BOM record and returns its ID. Parameterized to prevent SQL Injection."""
    if not isinstance(filename, str) or not isinstance(item_count, int):
        raise ValueError("Invalid input types for database operation")
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    timestamp = datetime.datetime.now().isoformat()
    
    cursor.execute(
        "INSERT INTO boms (timestamp, filename, item_count) VALUES (?, ?, ?)",
        (timestamp, filename, item_count)
    )
    bom_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return bom_id

def save_history(bom_id: int, total_cost: float, result_data: dict):
    """Saves an optimization result. Parameterized to prevent SQL Injection."""
    if not isinstance(bom_id, int) or not isinstance(total_cost, (float, int)):
        raise ValueError("Invalid input types for database operation")
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    timestamp = datetime.datetime.now().isoformat()
    
    cursor.execute(
        "INSERT INTO history (bom_id, timestamp, total_cost, result_json) VALUES (?, ?, ?, ?)",
        (bom_id, timestamp, total_cost, json.dumps(result_data))
    )
    conn.commit()
    conn.close()

def get_recent_history(limit: int = 10):
    """Returns recent optimization history."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT h.id, h.timestamp, h.total_cost, b.filename, b.item_count, h.result_json
        FROM history h
        JOIN boms b ON h.bom_id = b.id
        ORDER BY h.timestamp DESC
        LIMIT ?
    ''', (limit,))
    
    rows = cursor.fetchall()
    results = []
    for row in rows:
        results.append({
            "id": row["id"],
            "timestamp": row["timestamp"],
            "total_cost": row["total_cost"],
            "filename": row["filename"],
            "item_count": row["item_count"],
            "result": json.loads(row["result_json"])
        })
        
    conn.close()
    return results

if __name__ == "__main__":
    init_db()
    print("Database initialized at", DB_PATH)

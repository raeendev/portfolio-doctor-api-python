import sqlite3
import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'dev.db')
DB_PATH = os.path.abspath(DB_PATH)

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    try:
        cur.execute('SELECT id, email, username, role, isActive, createdAt FROM users')
        rows = [dict(r) for r in cur.fetchall()]
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    except Exception as e:
        print('ERR:', str(e))
    finally:
        conn.close()

if __name__ == '__main__':
    main()



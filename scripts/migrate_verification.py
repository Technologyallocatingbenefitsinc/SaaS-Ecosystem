import sqlite3

def migrate():
    conn = sqlite3.connect("test.db")
    cursor = conn.cursor()
    
    try:
        print("Migrating: Adding is_verified column...")
        cursor.execute("ALTER TABLE users ADD COLUMN is_verified BOOLEAN DEFAULT 0")
    except Exception as e:
        print(f"Skipped is_verified: {e}")

    try:
        print("Migrating: Adding verification_token column...")
        cursor.execute("ALTER TABLE users ADD COLUMN verification_token TEXT")
    except Exception as e:
        print(f"Skipped verification_token: {e}")

    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()

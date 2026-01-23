import sys
import os
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# Add parent dir to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Bypass app.config to avoid Pydantic validation errors if env vars are missing
# We try to get DATABASE_URL from app.database, which uses os.getenv with a default
try:
    from app.database import DATABASE_URL
    print(f"Loaded DATABASE_URL from app.database: {DATABASE_URL}")
except ImportError:
    print("Could not import DATABASE_URL from app.database")
    sys.exit(1)

# Basic check if it's the default placeholder
if "user:password@localhost/dbname" in DATABASE_URL:
    print("⚠️  WARNING: DATABASE_URL appears to be the default placeholder.")
    print("   If you have a local .env file, please export the variables before running this script:")
    print("   export $(grep -v '^#' .env | xargs) && python3 scripts/migrate_db.py")
    # We'll try to peek for a .env file and manually parse it just in case
    if os.path.exists(".env"):
        print("   Found .env file. Attempting to parse manually...")
        with open(".env", "r") as f:
            for line in f:
                if line.strip() and not line.startswith("#") and "=" in line:
                    key, val = line.strip().split("=", 1)
                    if key == "DATABASE_URL":
                        DATABASE_URL = val.strip()
                        print(f"   Overridden DATABASE_URL from .env: {DATABASE_URL}")

async def run_migration():
    print(f"Connecting to DB...")
    
    # Handle AsyncPG prefix fix if needed (redundant if using app.database string which likely handles it, but good safety)
    url = DATABASE_URL
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        
    engine = create_async_engine(url)
    
    async with engine.begin() as conn:
        print("Checking for missing columns in 'users' table...")
        
        # 1. Add my_class_code
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN my_class_code VARCHAR"))
            print("✅ Added 'my_class_code' column.")
        except Exception as e:
            if "duplicate column" in str(e) or "no such table" in str(e):
                print(f"ℹ️  Result for 'my_class_code': {e}")
            else:
                print(f"⚠️ Error adding 'my_class_code': {e}")

        # 2. Add joined_class_code
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN joined_class_code VARCHAR"))
            print("✅ Added 'joined_class_code' column.")
        except Exception as e:
            if "duplicate column" in str(e) or "no such table" in str(e):
                print(f"ℹ️  Result for 'joined_class_code': {e}")
            else:
                print(f"⚠️ Error adding 'joined_class_code': {e}")

    await engine.dispose()
    print("Migration Check Complete.")

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_migration())

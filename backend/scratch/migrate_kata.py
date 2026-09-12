import sys
import os

# Add backend directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.database import engine
from sqlalchemy import text

def add_kata_column():
    try:
        with engine.connect() as conn:
            # Check if column exists first
            res = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='session' AND column_name='kata_name'"))
            if res.fetchone() is None:
                conn.execute(text("ALTER TABLE session ADD COLUMN kata_name VARCHAR(100)"))
                conn.commit()
                print("Successfully added kata_name column to session table.")
            else:
                print("Column kata_name already exists.")
    except Exception as e:
        print(f"Error adding column: {e}")

if __name__ == "__main__":
    add_kata_column()

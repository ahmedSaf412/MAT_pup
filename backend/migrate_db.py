from app.database import engine
from sqlalchemy import text
import sys

def run():
    with engine.connect() as conn:
        try:
            conn.execute(text('ALTER TABLE trainee ADD COLUMN requested_coach_id INTEGER REFERENCES coach(id) ON DELETE SET NULL;'))
            conn.commit()
            print('Column requested_coach_id added successfully.')
        except Exception as e:
            print('requested_coach_id probably exists:', e)
            conn.rollback()

        try:
            conn.execute(text('ALTER TABLE users ADD COLUMN full_name VARCHAR(255);'))
            conn.commit()
            print('Column full_name added successfully.')
        except Exception as e:
            print('full_name probably exists:', e)

if __name__ == '__main__':
    run()

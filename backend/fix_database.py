"""
Script to fix the database schema by adding missing encrypted_password column
"""
import os
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime, timezone

# Use the same database configuration as main.py
DEFAULT_SQLITE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "snapkey.db")
DATABASE_URL = f"sqlite:///{DEFAULT_SQLITE_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Define the updated User model
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    user_name = Column(String, nullable=False)
    user_id = Column(String, unique=True, nullable=False, index=True)
    encrypted_password = Column(String, nullable=True)  # This is the missing column
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

def fix_database():
    # Check if the column exists
    inspector = inspect(engine)
    columns = inspector.get_columns('users')
    column_names = [column['name'] for column in columns]

    if 'encrypted_password' not in column_names:
        print("Adding missing encrypted_password column...")

        # For SQLite, we need to recreate the table
        # First, create a backup table
        with engine.connect() as conn:
            # Use text() to execute raw SQL
            from sqlalchemy import text

            # Create temporary table
            conn.execute(text("ALTER TABLE users RENAME TO users_old"))

            # Create new table with correct schema
            Base.metadata.create_all(bind=engine)

            # Copy data from old table to new table
            conn.execute(text("""
                INSERT INTO users (id, user_name, user_id, created_at)
                SELECT id, user_name, user_id, created_at FROM users_old
            """))

            # Drop old table
            conn.execute(text("DROP TABLE users_old"))

            conn.commit()

        print("Database schema updated successfully!")
    else:
        print("Database schema is already up to date.")

if __name__ == "__main__":
    from sqlalchemy import inspect
    fix_database()
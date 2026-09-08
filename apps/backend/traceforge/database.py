import os

from sqlalchemy import create_engine, text

engine = create_engine(os.environ["DATABASE_URL"])


def database_ready():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        return False

    return True

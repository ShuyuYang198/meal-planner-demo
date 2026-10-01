"""Persistent local demo database; no cloud service required."""
from pathlib import Path
import sqlite3
import os
from sqlalchemy import create_engine, event
from seed_demo import seed
BASE = Path(__file__).resolve().parent

def get_engine():
    (BASE / 'data').mkdir(exist_ok=True)
    engine = create_engine('sqlite:///' + os.environ.get('MEALPLANNER_DB', str(BASE / 'data' / 'mealplanner.db')), connect_args={'detect_types': sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES})
    @event.listens_for(engine, 'connect')
    def setup(connection, record):
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA busy_timeout=5000')
    with engine.begin() as conn:
        for statement in (BASE / 'schema_sqlite.sql').read_text().split(';'):
            if statement.strip(): conn.exec_driver_sql(statement)
        seed(conn)
    return engine

# database.py
from db.sqlite import SQLiteDB

# single shared DB instance
db = SQLiteDB('sqlite')
db.init_db()

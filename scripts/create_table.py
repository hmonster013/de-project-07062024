import psycopg2
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.constants import DB_FIELDS

conn = psycopg2.connect(database="postgres",
                        host="127.0.0.1",
                        user="tranhuy3",
                        password="tranhuy3",
                        port="5432")

cursor = conn.cursor()

def try_execute_sql(sql: str):
    try:
        cursor.execute(sql)
        conn.commit()
        print("Executed table creation successfully")
    except Exception as e:
        print(f"Couldn't execute table creation due to exception: {e}")
        conn.rollback()

def create_table():
    query = f"CREATE TABLE rappel_conso_table({DB_FIELDS[0]} text primary key"

    for i in DB_FIELDS[1:]:
            query += ", " + i + " text"

    query += ")"

    try_execute_sql(query)
    cursor.close()
    conn.close()

if __name__ == "__main__":
    create_table()
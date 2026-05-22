import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def create_database():
    try:
        # Connect to default postgres database
        conn = psycopg2.connect(
            user='postgres',
            password='admin123',
            host='127.0.0.1',
            port='5432',
            dbname='postgres'
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        # Check if database exists
        cur.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = 'ai_surveillance'")
        exists = cur.fetchone()
        
        if not exists:
            print("Creating database 'ai_surveillance'...")
            cur.execute("CREATE DATABASE ai_surveillance")
            print("Database created successfully.")
        else:
            print("Database 'ai_surveillance' already exists.")
            
        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    create_database()

import sqlite3
import json

def inspect_database():
    conn = sqlite3.connect('./parliament_votes.db')
    cursor = conn.cursor()

    results = {}

    print("=== DATABASE INSPECTION RESULTS ===\n")

    # 1. Get all table names
    print("1. ALL TABLES:")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tables = cursor.fetchall()
    table_names = [table[0] for table in tables]
    results['tables'] = table_names
    for table in table_names:
        print(f"   - {table}")
    print()

    # 2. Get schema for each table
    print("2. TABLE SCHEMAS:")
    results['schemas'] = {}
    cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name;")
    schemas = cursor.fetchall()
    for name, sql in schemas:
        print(f"\n--- {name} ---")
        print(sql)
        results['schemas'][name] = sql
    print()

    # 3. Get column info for each table
    print("3. COLUMN DETAILS:")
    results['columns'] = {}
    for table in table_names:
        try:
            cursor.execute(f"PRAGMA table_info({table});")
            columns = cursor.fetchall()
            results['columns'][table] = columns
            print(f"\n--- {table} columns ---")
            for col in columns:
                print(f"   {col[1]} ({col[2]}) - PK: {col[5]}, NotNull: {col[3]}")
        except Exception as e:
            print(f"Error getting columns for {table}: {e}")
    print()

    # 4. Get row counts
    print("4. ROW COUNTS:")
    results['row_counts'] = {}
    for table in table_names:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table};")
            count = cursor.fetchone()[0]
            results['row_counts'][table] = count
            print(f"   {table}: {count:,} rows")
        except Exception as e:
            print(f"Error counting {table}: {e}")
    print()

    # 5. Get sample data
    print("5. SAMPLE DATA (first 2 rows):")
    results['samples'] = {}
    for table in table_names:
        try:
            cursor.execute(f"SELECT * FROM {table} LIMIT 2;")
            rows = cursor.fetchall()

            # Get column names
            cursor.execute(f"PRAGMA table_info({table});")
            columns = [col[1] for col in cursor.fetchall()]

            results['samples'][table] = {
                'columns': columns,
                'rows': rows
            }

            print(f"\n--- {table} sample ---")
            print("Columns:", ", ".join(columns))
            for i, row in enumerate(rows):
                print(f"Row {i+1}:", row)
        except Exception as e:
            print(f"Error sampling {table}: {e}")

    # 6. Check for indexes
    print("\n6. INDEXES:")
    cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='index' AND sql IS NOT NULL;")
    indexes = cursor.fetchall()
    results['indexes'] = indexes
    for name, sql in indexes:
        print(f"   {name}: {sql}")

    conn.close()

    # Save to JSON file for easy sharing
    with open('database_inspection.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n=== INSPECTION COMPLETE ===")
    print("Results saved to 'database_inspection.json'")
    print("\nYou can copy this entire output to share the database structure!")

if __name__ == "__main__":
    inspect_database()

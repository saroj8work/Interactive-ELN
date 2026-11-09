import psycopg

dbs = ['identity', 'projects', 'notebook', 'activity']
for db in dbs:
    conn_str = f'host=127.0.0.1 port=5432 user=postgres password=Abcd@1234 dbname={db}'
    try:
        with psycopg.connect(conn_str) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public';")
                tables = [r[0] for r in cur.fetchall()]
                print(f'{db} ({len(tables)} tables):', tables)
    except Exception as e:
        print(f'{db} error:', e)


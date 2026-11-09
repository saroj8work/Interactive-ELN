import psycopg

conn_str = 'host=127.0.0.1 port=5432 user=postgres password=Abcd@1234 dbname=identity'
with psycopg.connect(conn_str) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT id, name, slug FROM organizations;")
        orgs = cur.fetchall()
        print("Organizations:", orgs)
        
        cur.execute("SELECT id, email, display_name, is_active FROM users;")
        users = cur.fetchall()
        print("Users:", users)

        cur.execute("SELECT user_id, organization_id, role, is_active FROM memberships;")
        memberships = cur.fetchall()
        print("Memberships:", memberships)


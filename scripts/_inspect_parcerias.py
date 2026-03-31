from db import get_cursor
cur = get_cursor()
for tbl in ['parcerias', 'parcerias_infos_adicionais']:
    cur.execute(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position",
        (tbl,)
    )
    rows = cur.fetchall()
    print(f"\n=== {tbl} ({len(rows)} cols) ===")
    for r in rows:
        print(f"  {r['column_name']}: {r['data_type']}")
cur.close()

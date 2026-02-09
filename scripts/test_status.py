from db import get_cursor

cur = get_cursor()
cur.execute('SELECT cents_status FROM categoricas.c_dgp_cents_status ORDER BY cents_status')
results = cur.fetchall()
print(f'Total de status: {len(results)}')
for r in results:
    print(f'  - {r["cents_status"]}')

import psycopg2
from config import DB_CONFIG

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

# Primeiro buscar o SEI da parceria
cur.execute("""
    SELECT sei_celeb 
    FROM public.parcerias 
    WHERE numero_termo = 'TCL/024/2023/SMDHC/SESANA'
""")
sei = cur.fetchone()[0]
print(f"SEI celeb: {sei}")

# Converter para cod_sof
import re
cod_sof = re.sub(r'[.\-/]', '', sei)
print(f"cod_sof: {cod_sof}")

# Buscar TODOS os empenhos
cur.execute("""
    SELECT cod_eph, dt_eph, EXTRACT(YEAR FROM dt_eph) as ano, cod_item_desp_sof, 
           COALESCE(NULLIF(REPLACE(val_tot_lqdc_eph, ',', '.'), '')::numeric, 0) as vlr_liqud,
           COALESCE(NULLIF(REPLACE(val_tot_pago_eph, ',', '.'), '')::numeric, 0) as vlr_pago
    FROM gestao_financeira.back_empenhos
    WHERE cod_nro_pcss_sof = %s
    ORDER BY dt_eph, cod_item_desp_sof
""", (cod_sof,))

rows = cur.fetchall()

print(f"\n=== Empenhos para {cod_sof} ===\n")
total_23 = 0
total_24 = 0

if not rows:
    print("NENHUM EMPENHO ENCONTRADO!")
    print("\nVamos buscar similar:")
    cur.execute("""
        SELECT DISTINCT cod_nro_pcss_sof 
        FROM gestao_financeira.back_empenhos 
        WHERE cod_nro_pcss_sof LIKE '60742023%'
    """)
    similares = cur.fetchall()
    print(f"\nProcessos SEI 6074.2023/... encontrados:")
    for s in similares:
        print(f"  - {s[0]}")

for r in rows:
    cod_eph = r[0]
    dt_eph = r[1]
    ano = int(r[2])
    elemento = r[3]
    vlr_liqud = float(r[4] or 0)
    vlr_pago = float(r[5] or 0)
    disponivel = vlr_liqud - vlr_pago
    
    print(f"Empenho: {cod_eph} | Data: {dt_eph} | Ano: {ano}")
    print(f"  Elemento: '{elemento}' (tipo: {type(elemento)})")
    print(f"  Liquidado: {vlr_liqud:,.2f}")
    print(f"  Pago: {vlr_pago:,.2f}")
    print(f"  Disponível: {disponivel:,.2f}")
    print(f"  Debug: elemento == '23'? {elemento == '23'}")
    print(f"  Debug: elemento == '24'? {elemento == '24'}")
    print()
    
    if elemento == 23:
        print(f"  ✅ Somando {vlr_pago:,.2f} ao total_23")
        total_23 += vlr_pago
    elif elemento == 24:
        print(f"  ✅ Somando {vlr_pago:,.2f} ao total_24")
        total_24 += vlr_pago

print(f"\nTOTAL PAGO elemento 23: {total_23:,.2f}")
print(f"TOTAL PAGO elemento 24: {total_24:,.2f}")
print(f"TOTAL GERAL PAGO: {total_23 + total_24:,.2f}")

print(f"\n=== Comparação ===")
print(f"Total solicitado (2 parcelas): 876.927,40")
print(f"Total pago: {total_23 + total_24:,.2f}")
print(f"Diferença: {876927.40 - (total_23 + total_24):,.2f}")

conn.close()

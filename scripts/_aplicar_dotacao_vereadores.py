"""
Script: Aplica ALTER TABLE, INSERT e UPDATEs de dotacao_orcamentaria
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import psycopg2
from config import DB_CONFIG

conn = psycopg2.connect(**DB_CONFIG)
conn.set_client_encoding('UTF8')
cur = conn.cursor()

print("=" * 60)
print("APLICANDO MUDANCAS NO BANCO DE DADOS")
print("=" * 60)

# 1. Adicionar coluna
try:
    cur.execute("""
        ALTER TABLE categoricas.c_geral_vereadores
        ADD COLUMN IF NOT EXISTS dotacao_orcamentaria VARCHAR(20)
    """)
    conn.commit()
    print("[OK] Coluna dotacao_orcamentaria adicionada (ou ja existia)")
except Exception as e:
    conn.rollback()
    print(f"[ERRO] ALTER TABLE: {e}")
    sys.exit(1)

# 2. Inserir Carlos Bezerra Jr.
try:
    cur.execute("""
        INSERT INTO categoricas.c_geral_vereadores
            (vereador_nome, partido, legislatura_inicio, legislatura_fim,
             legislatura_numero, situacao, dotacao_orcamentaria, criado_em, atualizado_em)
        VALUES
            ('Carlos Bezerra Jr.', 'PSD', '2025-01-01', '2028-12-31',
             19, 'Ativo', '.1.500.7057', NOW(), NOW())
        ON CONFLICT DO NOTHING
    """)
    conn.commit()
    print("[OK] Carlos Bezerra Jr. inserido (ou ja existia)")
except Exception as e:
    conn.rollback()
    print(f"[ERRO] INSERT Carlos Bezerra Jr.: {e}")

# 3. UPDATEs - todos os 54 vereadores
updates = [
    (109, '.1.500.7067', 'Adrilles Jorge'),
    (73,  '.1.500.7004', 'Alessandro Guedes'),
    (60,  '.1.500.7068', 'Amanda Paschoal'),
    (88,  '.1.500.7069', 'Amanda Vettorazzo'),
    (57,  '.1.500.7070', 'Ana Carolina Oliveira'),
    (86,  '.1.500.7007', 'Andre Santos'),
    (81,  '.1.500.7003', 'Major Palumbo (Bombeiro Major Palumbo)'),
    (74,  '.1.500.7043', 'Celso Giannazi'),
    (75,  '.1.500.7010', 'Cris Monteiro'),
    (70,  '.1.500.7011', 'Danilo do Posto de Saude'),
    (105, '.1.500.7071', 'Dheison Silva'),
    (99,  '.1.500.7006', 'Dr. Milton Ferreira'),
    (58,  '.1.500.7072', 'Dr. Murilo Lima (Dr. Murillo Lima)'),
    (64,  '.1.500.7044', 'Dra. Sandra Tadeu'),
    (72,  '.1.500.7032', 'Edir Sales'),
    (104, '.1.500.7053', 'Eliseu Gabriel'),
    (95,  '.1.500.7015', 'Ely Teruel'),
    (80,  '.1.500.7018', 'Fabio Riva'),
    (71,  '.1.500.7073', 'Gabriel Abreu'),
    (84,  '.1.500.7016', 'George Hato'),
    (110, '.1.500.7066', 'Gilberto Nascimento'),
    (87,  '.1.500.7050', 'Helio Rodrigues'),
    (67,  '.1.500.7009', 'Isac Felix'),
    (103, '.1.500.7017', 'Jair Tatto'),
    (79,  '.1.500.7074', 'Janaina Paschoal'),
    (100, '.1.500.7002', 'Joao Ananias'),
    (94,  '.1.500.7031', 'Joao Jorge'),
    (108, '.1.500.7075', 'Keit Lima'),
    (101, '.1.500.7076', 'Kenji Ito'),
    (63,  '.1.500.7026', 'Luana Alves'),
    (56,  '.1.500.7077', 'Lucas Pavanato'),
    (62,  '.1.500.7078', 'Luna Zarattini'),
    (89,  '.1.500.7028', 'Marcelo Messias'),
    (90,  '.1.500.7079', 'Marina Bragante'),
    (78,  '.1.500.7080', 'Nabil Bonduki'),
    (65,  '.1.500.7081', 'Pastora Sandra Alves'),
    (175, '.1.500.7045', 'Paulo Frange'),
    (96,  '.1.500.7049', 'Toninho Vespoli (Professor)'),
    (107, '.1.500.7082', 'Renata Falzoni'),
    (102, '.1.500.7061', 'Ricardo Teixeira'),
    (91,  '.1.500.7025', 'Roberto Tripoli'),
    (61,  '.1.500.7037', 'Rubinho Nunes'),
    (82,  '.1.500.7030', 'Rute Costa'),
    (93,  '.1.500.7039', 'Sandra Santana'),
    (85,  '.1.500.7041', 'Sansao Pereira'),
    (59,  '.1.500.7083', 'Sargento Nantes'),
    (106, '.1.500.7048', 'Senival Moura'),
    (66,  '.1.500.7084', 'Silvao Leite'),
    (97,  '.1.500.7047', 'Silvia da Bancada Feminista'),
    (76,  '.1.500.7085', 'Silvinho Leite'),
    (92,  '.1.500.7086', 'Simone Ganem'),
    (98,  '.1.500.7065', 'Sonaira Fernandes'),
    (77,  '.1.500.7054', 'Thammy Miranda'),
    (68,  '.1.500.7087', 'Zoe Martinez'),
]

erros = 0
for id_db, dotacao, nome in updates:
    try:
        cur.execute("""
            UPDATE categoricas.c_geral_vereadores
            SET dotacao_orcamentaria = %s, atualizado_em = NOW()
            WHERE id = %s
        """, (dotacao, id_db))
        if cur.rowcount == 0:
            print(f"[AVISO] id={id_db} ({nome}) nao encontrado!")
            erros += 1
    except Exception as e:
        conn.rollback()
        print(f"[ERRO] id={id_db} ({nome}): {e}")
        erros += 1

conn.commit()
print(f"\n[OK] {len(updates) - erros}/{len(updates)} UPDATEs executados com sucesso")

if erros:
    print(f"[!!] {erros} erros/avisos encontrados")

# 4. Verificar resultado
cur.execute("""
    SELECT COUNT(*) as total,
           COUNT(dotacao_orcamentaria) as com_dotacao
    FROM categoricas.c_geral_vereadores
    WHERE legislatura_numero = 19 AND situacao = 'Ativo'
""")
r = cur.fetchone()
print(f"\n[VERIFICACAO] Vereadores Ativos leg=19: {r[0]} total, {r[1]} com dotacao")

cur.execute("""
    SELECT id, vereador_nome, partido, dotacao_orcamentaria
    FROM categoricas.c_geral_vereadores
    WHERE legislatura_numero = 19 AND situacao = 'Ativo'
    ORDER BY vereador_nome
""")
print("\nVereadores Ativos leg=19 + dotacao:")
for row in cur.fetchall():
    dot = row[3] or '(vazio)'
    print(f"  id={row[0]:4d} | {row[1]:<45s} | {row[2]:<15s} | Dot: {dot}")

cur.close()
conn.close()
print("\n[CONCLUIDO]")

"""
Script: consulta vereadores do banco e faz match com lista de dotacoes
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import psycopg2
from psycopg2.extras import RealDictCursor
from config import DB_CONFIG
import unicodedata

# ── Lista fornecida: nome, partido, dotação (UNICOS, sem "Teste") ──
DOTACOES = [
    ("Adrilles Jorge",              "UNIAO",        ".1.500.7067"),
    ("Alessandro Guedes",           "PT",           ".1.500.7004"),
    ("Amanda Paschoal",             "PSOL",         ".1.500.7068"),
    ("Amanda Vettorazzo",           "UNIAO",        ".1.500.7069"),
    ("Ana Carolina Oliveira",       "PODE",         ".1.500.7070"),
    ("Andre Santos",                "REPUBLICANOS", ".1.500.7007"),
    ("Bombeiro Major Palumbo",      "PP",           ".1.500.7003"),
    ("Carlos Bezerra Jr.",          "PSD",          ".1.500.7057"),
    ("Celso Giannazi",              "PSOL",         ".1.500.7043"),
    ("Cris Monteiro",               "NOVO",         ".1.500.7010"),
    ("Danilo do Posto de Saude",    "PODE",         ".1.500.7011"),
    ("Dheison Silva",               "PT",           ".1.500.7071"),
    ("Dr. Milton Ferreira",         "PODE",         ".1.500.7006"),
    ("Dr. Murillo Lima",            "PP",           ".1.500.7072"),
    ("Dra Sandra Tadeu",            "PL",           ".1.500.7044"),
    ("Edir Sales",                  "PSD",          ".1.500.7032"),
    ("Eliseu Gabriel",              "PSB",          ".1.500.7053"),
    ("Ely Teruel",                  "MDB",          ".1.500.7015"),
    ("Fabio Riva",                  "MDB",          ".1.500.7018"),
    ("Gabriel Abreu",               "PODE",         ".1.500.7073"),
    ("George Hato",                 "MDB",          ".1.500.7016"),
    ("Gilberto Nascimento",         "PL",           ".1.500.7066"),
    ("Helio Rodrigues",             "PT",           ".1.500.7050"),
    ("Isac Felix",                  "PL",           ".1.500.7009"),
    ("Jair Tatto",                  "PT",           ".1.500.7017"),
    ("Janaina Paschoal",            "PP",           ".1.500.7074"),
    ("Joao Ananias",                "PT",           ".1.500.7002"),
    ("Joao Jorge",                  "MDB",          ".1.500.7031"),
    ("Keit Lima",                   "PSOL",         ".1.500.7075"),
    ("Kenji Ito",                   "PODE",         ".1.500.7076"),
    ("Luana Alves",                 "PSOL",         ".1.500.7026"),
    ("Lucas Pavanato",              "PL",           ".1.500.7077"),
    ("Luna Zarattini",              "PT",           ".1.500.7078"),
    ("Marcelo Messias",             "MDB",          ".1.500.7028"),
    ("Marina Bragante",             "REDE",         ".1.500.7079"),
    ("Nabil Bonduki",               "PT",           ".1.500.7080"),
    ("Pastora Sandra Alves",        "UNIAO",        ".1.500.7081"),
    ("Paulo Frange",                "MDB",          ".1.500.7045"),
    ("Professor Toninho Vespoli",   "PSOL",         ".1.500.7049"),
    ("Renata Falzoni",              "PSB",          ".1.500.7082"),
    ("Ricardo Teixeira",            "UNIAO",        ".1.500.7061"),
    ("Roberto Tripoli",             "PV",           ".1.500.7025"),
    ("Rubinho Nunes",               "UNIAO",        ".1.500.7037"),
    ("Rute Costa",                  "PL",           ".1.500.7030"),
    ("Sandra Santana",              "MDB",          ".1.500.7039"),
    ("Sansao Pereira",              "REPUBLICANOS", ".1.500.7041"),
    ("Sargento Nantes",             "PP",           ".1.500.7083"),
    ("Senival Moura",               "PT",           ".1.500.7048"),
    ("Silvao Leite",                "UNIAO",        ".1.500.7084"),
    ("Silvia da Bancada Feminista", "PSOL",         ".1.500.7047"),
    ("Silvinho Leite",              "UNIAO",        ".1.500.7085"),
    ("Simone Ganem",                "PODE",         ".1.500.7086"),
    ("Sonaira Fernandes",           "PL",           ".1.500.7065"),
    ("Thammy Miranda",              "PSD",          ".1.500.7054"),
    ("Zoe Martinez",                "PL",           ".1.500.7087"),
]

def norm(s):
    """Normaliza string: remove acentos, lowercase, strip"""
    if not s:
        return ''
    s = s.strip()
    s = unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('ASCII')
    return s.lower()

# ── Conectar ─────────────────────────────────────────────────────────
conn = psycopg2.connect(**DB_CONFIG)
conn.set_client_encoding('UTF8')
cur = conn.cursor(cursor_factory=RealDictCursor)

# ── 1. Coluna existe? ────────────────────────────────────────────────
cur.execute("""
    SELECT column_name FROM information_schema.columns
    WHERE table_schema = 'categoricas'
      AND table_name = 'c_geral_vereadores'
      AND column_name = 'dotacao_orcamentaria'
""")
col_exists = cur.fetchone() is not None
print(f"Coluna 'dotacao_orcamentaria' ja existe? {'SIM' if col_exists else 'NAO'}")

# ── 2. Listar todos os vereadores ────────────────────────────────────
cur.execute("""
    SELECT id, vereador_nome, partido, legislatura_numero, situacao
    FROM categoricas.c_geral_vereadores
    ORDER BY vereador_nome
""")
db_vereadores = cur.fetchall()
print(f"\n=== VEREADORES NO BANCO ({len(db_vereadores)}) ===")
for v in db_vereadores:
    print(f"id={v['id']:4d} | {v['vereador_nome']:<45s} | {v['partido']:<15s} | leg={v['legislatura_numero']} | {v['situacao']}")

# ── 3. Fazer match ───────────────────────────────────────────────────
# Mapa: nome_normalizado -> registro_banco
db_map = {}
for v in db_vereadores:
    db_map[norm(v['vereador_nome'])] = v

print(f"\n=== MATCH: Lista -> Banco ===")
matched = []
unmatched = []

for nome_lista, partido_lista, dotacao in DOTACOES:
    nome_norm = norm(nome_lista)

    # Tentar match exato normalizado
    if nome_norm in db_map:
        v = db_map[nome_norm]
        matched.append((v['id'], v['vereador_nome'], nome_lista, dotacao, 'exato'))
        continue

    # Tentar match parcial (um contem o outro)
    found = False
    for nome_db_norm, v in db_map.items():
        # Nome da lista contido no nome do banco ou vice-versa
        if len(nome_norm) > 5 and (nome_norm in nome_db_norm or nome_db_norm in nome_norm):
            matched.append((v['id'], v['vereador_nome'], nome_lista, dotacao, 'parcial'))
            found = True
            break

    if not found:
        unmatched.append((nome_lista, partido_lista, dotacao))

print(f"\nMATCHED: {len(matched)}")
for id_db, nome_db, nome_lista, dotacao, modo in matched:
    flag = ' [!parcial]' if modo == 'parcial' else ''
    print(f"  id={id_db:4d} | DB: {nome_db:<45s} | Lista: {nome_lista:<40s} | Dot: {dotacao}{flag}")

if unmatched:
    print(f"\nSEM MATCH: {len(unmatched)}")
    for nome_lista, partido_lista, dotacao in unmatched:
        print(f"  Lista: {nome_lista:<40s} | Partido: {partido_lista:<15s} | Dot: {dotacao}")

# ── 4. Verificar quem do banco ficou sem dotacao ────────────────────
matched_ids = set(m[0] for m in matched)
sem_dotacao = [v for v in db_vereadores if v['id'] not in matched_ids]
print(f"\n=== VEREADORES NO BANCO SEM DOTACAO ATRIBUIDA ({len(sem_dotacao)}) ===")
for v in sem_dotacao:
    print(f"  id={v['id']:4d} | {v['vereador_nome']:<45s} | {v['partido']} | leg={v['legislatura_numero']} | {v['situacao']}")

# ── 5. Gerar SQL ─────────────────────────────────────────────────────
print(f"\n=== SQL GERADO ===")
if not col_exists:
    print("\n-- 1. Adicionar coluna:")
    print("ALTER TABLE categoricas.c_geral_vereadores ADD COLUMN dotacao_orcamentaria VARCHAR(20);")

print("\n-- 2. Atualizar dotacoes:")
print("BEGIN;")
for id_db, nome_db, nome_lista, dotacao, modo in matched:
    print(f"UPDATE categoricas.c_geral_vereadores SET dotacao_orcamentaria = '{dotacao}' WHERE id = {id_db};  -- {nome_db}")
print("COMMIT;")

cur.close()
conn.close()

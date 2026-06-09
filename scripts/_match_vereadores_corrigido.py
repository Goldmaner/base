"""
Script CORRIGIDO: match vereadores preferindo leg=19 Ativo, gerando SQL final.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import psycopg2
from psycopg2.extras import RealDictCursor
from config import DB_CONFIG
import unicodedata
from collections import defaultdict

# ── Lista fornecida: nome, partido, dotação (UNICOS) ──
# Inclui mapeamento de nomes alternativos para match no banco
DOTACOES = [
    # (nome_na_lista, partido, dotacao, nome_alternativo_no_banco)
    ("Adrilles Jorge",              "UNIAO",        ".1.500.7067", None),
    ("Alessandro Guedes",           "PT",           ".1.500.7004", None),
    ("Amanda Paschoal",             "PSOL",         ".1.500.7068", None),
    ("Amanda Vettorazzo",           "UNIAO",        ".1.500.7069", None),
    ("Ana Carolina Oliveira",       "PODE",         ".1.500.7070", None),
    ("Andre Santos",                "REPUBLICANOS", ".1.500.7007", None),
    ("Bombeiro Major Palumbo",      "PP",           ".1.500.7003", "Major Palumbo"),
    ("Carlos Bezerra Jr.",          "PSD",          ".1.500.7057", None),  # NAO EXISTE NO BANCO!
    ("Celso Giannazi",              "PSOL",         ".1.500.7043", None),
    ("Cris Monteiro",               "NOVO",         ".1.500.7010", None),
    ("Danilo do Posto de Saude",    "PODE",         ".1.500.7011", None),
    ("Dheison Silva",               "PT",           ".1.500.7071", None),
    ("Dr. Milton Ferreira",         "PODE",         ".1.500.7006", None),
    ("Dr. Murillo Lima",            "PP",           ".1.500.7072", "Dr. Murilo Lima"),  # DB tem 1 'l'
    ("Dra Sandra Tadeu",            "PL",           ".1.500.7044", "Dra. Sandra Tadeu"),  # DB tem ponto
    ("Edir Sales",                  "PSD",          ".1.500.7032", None),
    ("Eliseu Gabriel",              "PSB",          ".1.500.7053", None),
    ("Ely Teruel",                  "MDB",          ".1.500.7015", None),
    ("Fabio Riva",                  "MDB",          ".1.500.7018", None),
    ("Gabriel Abreu",               "PODE",         ".1.500.7073", None),
    ("George Hato",                 "MDB",          ".1.500.7016", None),
    ("Gilberto Nascimento",         "PL",           ".1.500.7066", None),  # Preferir id=110 (PL), nao id=176
    ("Helio Rodrigues",             "PT",           ".1.500.7050", None),
    ("Isac Felix",                  "PL",           ".1.500.7009", None),
    ("Jair Tatto",                  "PT",           ".1.500.7017", None),
    ("Janaina Paschoal",            "PP",           ".1.500.7074", None),
    ("Joao Ananias",                "PT",           ".1.500.7002", None),
    ("Joao Jorge",                  "MDB",          ".1.500.7031", None),
    ("Keit Lima",                   "PSOL",         ".1.500.7075", None),
    ("Kenji Ito",                   "PODE",         ".1.500.7076", None),
    ("Luana Alves",                 "PSOL",         ".1.500.7026", None),
    ("Lucas Pavanato",              "PL",           ".1.500.7077", None),
    ("Luna Zarattini",              "PT",           ".1.500.7078", None),
    ("Marcelo Messias",             "MDB",          ".1.500.7028", None),
    ("Marina Bragante",             "REDE",         ".1.500.7079", None),
    ("Nabil Bonduki",               "PT",           ".1.500.7080", None),
    ("Pastora Sandra Alves",        "UNIAO",        ".1.500.7081", None),
    ("Paulo Frange",                "MDB",          ".1.500.7045", None),
    ("Professor Toninho Vespoli",   "PSOL",         ".1.500.7049", "Toninho Vespoli"),
    ("Renata Falzoni",              "PSB",          ".1.500.7082", None),
    ("Ricardo Teixeira",            "UNIAO",        ".1.500.7061", None),
    ("Roberto Tripoli",             "PV",           ".1.500.7025", None),
    ("Rubinho Nunes",               "UNIAO",        ".1.500.7037", None),
    ("Rute Costa",                  "PL",           ".1.500.7030", None),
    ("Sandra Santana",              "MDB",          ".1.500.7039", None),
    ("Sansao Pereira",              "REPUBLICANOS", ".1.500.7041", None),
    ("Sargento Nantes",             "PP",           ".1.500.7083", None),
    ("Senival Moura",               "PT",           ".1.500.7048", None),
    ("Silvao Leite",                "UNIAO",        ".1.500.7084", None),
    ("Silvia da Bancada Feminista", "PSOL",         ".1.500.7047", "Silvia da Bancada Feminista"),  # DB tem acento
    ("Silvinho Leite",              "UNIAO",        ".1.500.7085", None),
    ("Simone Ganem",                "PODE",         ".1.500.7086", None),
    ("Sonaira Fernandes",           "PL",           ".1.500.7065", None),
    ("Thammy Miranda",              "PSD",          ".1.500.7054", None),
    ("Zoe Martinez",                "PL",           ".1.500.7087", None),
]

def norm(s):
    if not s:
        return ''
    s = s.strip()
    s = unicodedata.normalize('NFKD', s).encode('ASCII', 'ignore').decode('ASCII')
    return s.lower()

# ── Conectar ─────────────────────────────────────────────────────────
conn = psycopg2.connect(**DB_CONFIG)
conn.set_client_encoding('UTF8')
cur = conn.cursor(cursor_factory=RealDictCursor)

# ── Verificar coluna ─────────────────────────────────────────────────
cur.execute("""
    SELECT column_name FROM information_schema.columns
    WHERE table_schema = 'categoricas'
      AND table_name = 'c_geral_vereadores'
      AND column_name = 'dotacao_orcamentaria'
""")
col_exists = cur.fetchone() is not None
print(f"Coluna 'dotacao_orcamentaria' existe? {'SIM' if col_exists else 'NAO'}")

# ── Buscar todos os vereadores ───────────────────────────────────────
cur.execute("""
    SELECT id, vereador_nome, partido, legislatura_numero, situacao
    FROM categoricas.c_geral_vereadores
    ORDER BY vereador_nome
""")
db_vereadores = cur.fetchall()

# Agrupar por nome normalizado, preferindo Ativo + leg=19
db_best = {}  # nome_norm -> melhor registro
for v in db_vereadores:
    key = norm(v['vereador_nome'])
    if key not in db_best:
        db_best[key] = v
    else:
        existing = db_best[key]
        # Preferir Ativo sobre Mandato Encerrado
        if v['situacao'] == 'Ativo' and existing['situacao'] != 'Ativo':
            db_best[key] = v
        # Preferir legislatura mais alta
        elif (v['legislatura_numero'] or 0) > (existing['legislatura_numero'] or 0):
            db_best[key] = v
        # Preferir PL sobre PARTIDO LIBERAL (duplicata)
        elif v['partido'] == 'PL' and existing['partido'] == 'PARTIDO LIBERAL':
            db_best[key] = v

# ── Fazer match ──────────────────────────────────────────────────────
print(f"\n{'='*80}")
print("MATCH CORRIGIDO (preferindo Ativo + leg=19)")
print(f"{'='*80}")

matched = []
unmatched = []
to_insert = []

for nome_lista, partido_lista, dotacao, nome_alt in DOTACOES:
    # Usar nome alternativo se fornecido
    nome_busca = nome_alt if nome_alt else nome_lista
    nome_norm = norm(nome_busca)

    if nome_norm in db_best:
        v = db_best[nome_norm]
        matched.append((v['id'], v['vereador_nome'], nome_lista, dotacao,
                        v['legislatura_numero'], v['situacao']))
        continue

    # Tentar match parcial
    found = False
    for nome_db_norm, v in db_best.items():
        if len(nome_norm) > 5 and (nome_norm in nome_db_norm or nome_db_norm in nome_norm):
            matched.append((v['id'], v['vereador_nome'], nome_lista, dotacao,
                           v['legislatura_numero'], v['situacao']))
            found = True
            break

    if not found:
        unmatched.append((nome_lista, partido_lista, dotacao))
        # Se o partido corresponde e e um vereador da 19a legislatura, sugerir INSERT
        to_insert.append((nome_lista, partido_lista, dotacao))

print(f"\nMATCHED: {len(matched)}")
for id_db, nome_db, nome_lista, dotacao, leg, sit in matched:
    flag = ''
    if sit != 'Ativo' or leg != 19:
        flag = f' [!leg={leg} {sit}]'
    print(f"  id={id_db:4d} | DB: {nome_db:<45s} | Lista: {nome_lista:<40s} | Dot: {dotacao}{flag}")

if unmatched:
    print(f"\nSEM MATCH: {len(unmatched)} — precisara de INSERT:")
    for nome_lista, partido_lista, dotacao in unmatched:
        print(f"  Lista: {nome_lista:<40s} | Partido: {partido_lista:<15s} | Dot: {dotacao}")

# ── Gerar SQL ────────────────────────────────────────────────────────
print(f"\n{'='*80}")
print("SQL FINAL GERADO")
print(f"{'='*80}")

if not col_exists:
    print("\n-- 1. Adicionar coluna:")
    print("ALTER TABLE categoricas.c_geral_vereadores ADD COLUMN dotacao_orcamentaria VARCHAR(20);")

if to_insert:
    print("\n-- 2. Inserir vereadores faltantes:")
    for nome_lista, partido_lista, dotacao in to_insert:
        # Mapear partido da lista para nome no banco
        partido_db = partido_lista
        print(f"INSERT INTO categoricas.c_geral_vereadores (vereador_nome, partido, legislatura_inicio, legislatura_fim, legislatura_numero, situacao, dotacao_orcamentaria)")
        print(f"VALUES ('{nome_lista}', '{partido_db}', '2025-01-01', '2028-12-31', 19, 'Ativo', '{dotacao}');")

print("\n-- 3. Atualizar dotacoes (apenas Ativos leg=19):")
print("BEGIN;")
for id_db, nome_db, nome_lista, dotacao, leg, sit in matched:
    print(f"UPDATE categoricas.c_geral_vereadores SET dotacao_orcamentaria = '{dotacao}' WHERE id = {id_db};  -- {nome_db} (leg={leg}, {sit})")
print("COMMIT;")

# ── Verificar duplicatas de Gilberto ─────────────────────────────────
print(f"\n-- 4. Limpeza: remover duplicata Gilberto Nascimento (PARTIDO LIBERAL)")
print("-- DELETE FROM categoricas.c_geral_vereadores WHERE id = 176;  -- duplicata 'PARTIDO LIBERAL'")

# ── Verificar vereadores ativos leg=19 sem dotacao ───────────────────
matched_ids = set(m[0] for m in matched)
ativos_sem = [v for v in db_vereadores
              if v['legislatura_numero'] == 19 and v['situacao'] == 'Ativo'
              and v['id'] not in matched_ids]
print(f"\n-- 5. Vereadores ATIVOS leg=19 SEM dotacao ({len(ativos_sem)}):")
for v in ativos_sem:
    print(f"--   id={v['id']:4d} | {v['vereador_nome']:<45s} | {v['partido']}")

cur.close()
conn.close()

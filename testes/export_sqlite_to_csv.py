import pandas as pd
import psycopg2
from datetime import datetime

# Configurações do banco PostgreSQL
DB_HOST = 'localhost'
DB_PORT = '5432'
DB_NAME = 'projeto_parcerias'
DB_USER = 'postgres'
DB_PASS = 'sua_senha_aqui'  # troque pela sua senha

# Caminho do arquivo CSV
CSV_PATH = r'C:\Users\d843702\parcerias.csv'
LOG_ERROS = r'C:\Users\d843702\parcerias_erros.txt'

colunas_banco = [
    'numero_termo', 'osc', 'projeto', 'tipo_termo', 'portaria', 'cnpj',
    'inicio', 'final', 'meses', 'total_previsto', 'total_pago', 'conta',
    'transicao', 'sei_celeb', 'sei_pc', 'endereco', 'sei_plano', 'sei_orcamento', 'contrapartida'
]

def parse_date(value):
    if pd.isnull(value) or str(value).strip() == '':
        return None
    for fmt in ('%d/%m/%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(str(value), fmt).strftime('%Y-%m-%d')
        except Exception:
            continue
    return None

def parse_contrapartida(value):
    if str(value).strip().lower() == 'não':
        return 0
    if str(value).strip().lower() == 'sim':
        return 1
    if pd.isnull(value) or value == '':
        return None
    try:
        return int(value)
    except Exception:
        return None

def parse_float(value):
    # Aceita valores tipo '150.000,99' ou '150000.99' ou '150000'
    if pd.isnull(value) or str(value).strip() == '':
        return None
    try:
        valor = str(value).replace('.', '').replace(',', '.')
        return float(valor)
    except Exception:
        return None

def parse_int(value):
    # Aceita apenas inteiros, senão retorna 0
    if pd.isnull(value) or str(value).strip() == '':
        return None
    try:
        return int(float(str(value).replace(',', '.')))
    except Exception:
        return 0

# Lê o CSV usando pandas, ignorando linhas ruins, separador ponto e vírgula
df = pd.read_csv(CSV_PATH, encoding='utf-8', sep=';', on_bad_lines='skip')

# Ajusta datas para o formato do banco
df['inicio'] = df['inicio'].apply(parse_date)
df['final'] = df['final'].apply(parse_date)

# Ajusta valores para float
df['total_previsto'] = df['total_previsto'].apply(parse_float)
df['total_pago'] = df['total_pago'].apply(parse_float)
df['conta'] = df['conta'].apply(parse_float)

# Ajusta colunas para integer
df['meses'] = df['meses'].apply(parse_int)
df['transicao'] = df['transicao'].apply(parse_int)
df['contrapartida'] = df['contrapartida'].apply(parse_contrapartida)

# Converte NaN para None
df = df.where(pd.notnull(df), None)

conn = psycopg2.connect(
    host=DB_HOST,
    port=DB_PORT,
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASS
)
cur = conn.cursor()

erros = []
linhas_inseridas = 0

for i, row in df.iterrows():
    values = [row.get(col) for col in colunas_banco]
    placeholders = ', '.join(['%s'] * len(colunas_banco))
    sql = f"INSERT INTO parcerias ({', '.join(colunas_banco)}) VALUES ({placeholders}) ON CONFLICT (numero_termo) DO NOTHING"
    try:
        cur.execute(sql, values)
    except Exception as e:
        erro_msg = f"Linha {i + 2} (numero_termo={row.get('numero_termo')}): {e}\nValores: {values}\n"
        erros.append(erro_msg)
        conn.rollback()
    else:
        conn.commit()
        linhas_inseridas += 1

cur.close()
conn.close()

if erros:
    with open(LOG_ERROS, 'w', encoding='utf-8') as log:
        log.write("Relatório de erros na importação:\n\n")
        for erro in erros:
            log.write(erro)
    print(f'Importação concluída com {linhas_inseridas} linhas inseridas. Veja erros em: {LOG_ERROS}')
else:
    print(f'Importação concluída com {linhas_inseridas} linhas inseridas. Nenhum erro encontrado!')
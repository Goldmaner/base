import pandas as pd
import psycopg2
from datetime import datetime

# Configuração do banco
DB_CONFIG = {
    'host': 'localhost',
    'port': '5432',
    'database': 'projeto_parcerias',
    'user': 'postgres',
    'password': 'Coração01'  # Troque pela sua senha
}

CSV_PATH = r'C:\Users\d843702\orcamento_1.csv'

# Lê o CSV
df = pd.read_csv(CSV_PATH, encoding='utf-8', sep=';', dtype=str)

# Ajusta float com vírgula (se houver)
def parse_float(val, linha_num=None, coluna_nome=None):
    try:
        s = str(val).replace(' ', '').replace('\t', '').replace('\xa0', '').strip()
        if s == '' or s == '-' or not any(c.isdigit() for c in s):
            return 0.0
        return float(s.replace('.', '').replace(',', '.'))
    except Exception as e:
        msg = f"Erro na linha {linha_num}, coluna '{coluna_nome}': valor '{val}' - {repr(e)}"
        print(msg)
        raise  # Se quiser ignorar e continuar, troque por: return 0.0

# Colunas fixas (até categoria)
fixas = ['aditivo','numero_termo','rubrica','quantidade','categoria_despesa']

# Colunas de meses
col_meses = [c for c in df.columns if c.lower().startswith('mês') or c.lower().startswith('mes')]

# Cria linhas para o banco
linhas = []
for idx, row in df.iterrows():
    # Pega os dados fixos
    dados = {col: row[col] for col in fixas}
    # Descobre até qual mês vai para esta categoria (considera que só gera até o último valor não vazio)
    ultimo_mes = 0
    for i, col in enumerate(col_meses, 1):
        val = row[col]
        if not (pd.isnull(val) or str(val).strip() == ''):
            ultimo_mes = i
    # Gera linhas só até o último mês não vazio
    for i in range(1, ultimo_mes+1):
        col_nome = col_meses[i-1]
        val = row[col_nome]
        try:
            valor_float = parse_float(val, linha_num=idx+2, coluna_nome=col_nome)  # +2 porque pandas ignora cabeçalho, e CSV começa no 1
        except Exception:
            continue  # Se quiser ignorar e seguir, senão remova
        linha = {
            'aditivo': int(float(row['aditivo'])) if row['aditivo'].strip() != '' else 0,
            'numero_termo': row['numero_termo'],
            'rubrica': row['rubrica'],
            'quantidade': int(float(row['quantidade'])) if row['quantidade'].strip() != '' else 0,
            'categoria_despesa': row['categoria_despesa'],
            'valor': valor_float,
            'mes': i,
            'ano': None,
            'criado_em': datetime.now(),
        }
        linhas.append(linha)

# Importa para o banco
conn = psycopg2.connect(**DB_CONFIG)
cursor = conn.cursor()

for linha in linhas:
    cursor.execute("""
        INSERT INTO parcerias_despesas 
        (aditivo, numero_termo, rubrica, quantidade, categoria_despesa, valor, mes, ano, criado_em)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            linha['aditivo'],
            linha['numero_termo'],
            linha['rubrica'],
            linha['quantidade'],
            linha['categoria_despesa'],
            linha['valor'],
            linha['mes'],
            linha['ano'],
            linha['criado_em']
        )
    )

conn.commit()
cursor.close()
conn.close()

print(f"Importação finalizada! {len(linhas)} linhas inseridas.")
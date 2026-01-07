import pandas as pd
import sys
import os

# Adiciona o diretório pai ao path para importar config e db
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import DB_CONFIG
import psycopg2

# ===== PARTE 1: Importar dados da planilha Excel =====
# Caminho do arquivo Excel local
arquivo = r'C:\Users\d843702\OneDrive - rede.sp\DIVISÃO DE ANALISE DE CONTAS\Desenvolvimento\Bancos e Reservas\Parcerias.xlsx'
planilha = 'Dados_Importação'

# Lê a planilha inteira COM cabeçalho personalizado
df_excel = pd.read_excel(arquivo, sheet_name=planilha, header=None)

# Parâmetros para recorte - linha inicial (índice 1 = linha 2 do Excel)
inicio = 1

# Define as colunas que queremos importar (índices começam em 0)
# B=1, C=2, D=3, H=7, I=8, K=10, L=11, O=14, P=15
colunas_interesse = {
    1: 'numero_termo',      # Coluna B
    2: 'osc',               # Coluna C
    3: 'projeto',           # Coluna D
    7: 'inicio',            # Coluna H
    8: 'final',             # Coluna I
    10: 'total_previsto',   # Coluna K
    11: 'total_pago',       # Coluna L
    14: 'sei_celeb',        # Coluna O
    15: 'sei_pc'            # Coluna P
}

# Encontra a última linha preenchida na coluna B (numero_termo)
ultima_linha = df_excel[1].last_valid_index()

# Extrai apenas as colunas de interesse
df_planilha = df_excel.loc[inicio:ultima_linha, list(colunas_interesse.keys())].copy()

# Renomeia as colunas
df_planilha.columns = list(colunas_interesse.values())

# Debugging: contagem inicial
total_inicial = len(df_planilha)
print(f"[DEBUG] Total de linhas antes de filtros: {total_inicial}")

# Remove linhas onde numero_termo está vazio
df_planilha = df_planilha[df_planilha['numero_termo'].notna()]
print(f"[DEBUG] Após remover vazios: {len(df_planilha)} (removidos: {total_inicial - len(df_planilha)})")

# Remove linhas onde numero_termo é "0", 0 (número) ou string vazia
antes_zero = len(df_planilha)
df_planilha = df_planilha[df_planilha['numero_termo'] != '0']
df_planilha = df_planilha[df_planilha['numero_termo'] != 0]
df_planilha = df_planilha[df_planilha['numero_termo'].astype(str).str.strip() != '']
print(f"[DEBUG] Após remover zeros/vazios: {len(df_planilha)} (removidos: {antes_zero - len(df_planilha)})")

# Remove duplicados baseado no numero_termo
antes_dup = len(df_planilha)
df_planilha = df_planilha.drop_duplicates(subset=['numero_termo'])
print(f"[DEBUG] Após remover duplicados: {len(df_planilha)} (removidos: {antes_dup - len(df_planilha)})")

# Reseta o índice
df_planilha = df_planilha.reset_index(drop=True)

# Converter datas para formato YYYY-MM-DD (compatível com HTML input type="date")
# Trata tanto formato brasileiro (01/11/2025) quanto formato Excel (datetime)
for col in ['inicio', 'final']:
    if col in df_planilha.columns:
        # Tenta converter para datetime (funciona tanto para string quanto para datetime do Excel)
        df_planilha[col] = pd.to_datetime(df_planilha[col], errors='coerce', dayfirst=True)
        # Converte para string no formato YYYY-MM-DD
        df_planilha[col] = df_planilha[col].dt.strftime('%Y-%m-%d')
        # Substitui 'NaT' (Not a Time) por None
        df_planilha[col] = df_planilha[col].replace('NaT', None)

print(f"[INFO] Colunas importadas: {list(df_planilha.columns)}")
print(f"[INFO] Total de termos na planilha: {len(df_planilha)}")

# ===== PARTE 2: Importar dados do banco de dados =====
print("[INFO] Conectando ao banco de dados...")
conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

# Busca todos os numero_termo da tabela Parcerias
query = "SELECT numero_termo FROM Parcerias ORDER BY numero_termo"
cur.execute(query)
termos_db = [row[0] for row in cur.fetchall()]

# Remove duplicados (se houver)
termos_db_unicos = list(set(termos_db))
termos_db_unicos.sort()

cur.close()
conn.close()
print(f"[INFO] Total de termos no banco: {len(termos_db_unicos)}")

# ===== PARTE 3: Identificar termos não inseridos =====
# Converte para sets para comparação
set_planilha = set(df_planilha['numero_termo'].tolist())
set_database = set(termos_db_unicos)

# Termos que estão na planilha mas NÃO estão no banco
termos_nao_inseridos = set_planilha - set_database

# Filtrar df_planilha para manter apenas os termos não inseridos
df_final = df_planilha[df_planilha['numero_termo'].isin(termos_nao_inseridos)].copy()

# Converter numero_termo para string antes de ordenar (para evitar erro de comparação int vs str)
df_final['numero_termo'] = df_final['numero_termo'].astype(str)

# Ordenar por numero_termo
df_final = df_final.sort_values('numero_termo').reset_index(drop=True)

# ===== PARTE 4: Salvar em CSV com todos os dados =====
# Salva o resultado em CSV com separador de PONTO E VÍRGULA (padrão brasileiro)
csv_path = r'C:\Users\d843702\OneDrive - rede.sp\Área de Trabalho\FAF\FAF\scripts\saida.csv'
df_final.to_csv(csv_path, index=False, header=True, sep=';', encoding='utf-8-sig')

print("[SUCESSO] CSV gerado em: saida.csv")
print(f"[INFO] Termos NÃO inseridos no banco: {len(df_final)}")
print(f"[INFO] Colunas no CSV: {list(df_final.columns)}")
print(f"[INFO] Separador: ponto e vírgula (;)")
print(f"[INFO] Encoding: UTF-8 com BOM")
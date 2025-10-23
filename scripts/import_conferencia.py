import pandas as pd
import sys
import os

# Adiciona o diretório pai ao path para importar config e db
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import DB_CONFIG
import psycopg2

# ===== PARTE 1: Importar dados da planilha Excel =====
# Caminho do arquivo Excel local
arquivo = r'C:\Users\d843702\OneDrive - rede.sp\DIVISÃO DE ANALISE DE CONTAS\Desenvolvimento\Bancos e Reservas\Banco de Dados - Final.xlsx'
planilha = 'BD - Termos'

# Lê a planilha inteira sem cabeçalho
df_excel = pd.read_excel(arquivo, sheet_name=planilha, header=None)

# Parâmetros para recorte
inicio = 4    # F5 corresponde à linha 5 (índice 4)
coluna = 5    # Coluna F é índice 5

# Encontra a última linha preenchida na coluna F
ultima_linha = df_excel[coluna].last_valid_index()

# Recorta de F5 até F final preenchido
df_recorte = df_excel.loc[inicio:ultima_linha, [coluna]]

# Remove duplicados
df_planilha = df_recorte.drop_duplicates()

# Reseta o índice e renomeia a coluna
df_planilha = df_planilha.reset_index(drop=True)
df_planilha.columns = ['Planilha']

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

# Cria DataFrame com os dados do banco
df_database = pd.DataFrame(termos_db_unicos, columns=['Database'])

cur.close()
conn.close()
print(f"[INFO] Total de termos na planilha: {len(df_planilha)}")
print(f"[INFO] Total de termos no banco: {len(df_database)}")

# ===== PARTE 3: Combinar em um único CSV com 2 colunas =====
# Preenche com NaN para igualar tamanhos (se necessário)
max_len = max(len(df_planilha), len(df_database))

df_planilha = df_planilha.reindex(range(max_len))
df_database = df_database.reindex(range(max_len))

# Combina as duas colunas
df_final = pd.concat([df_planilha, df_database], axis=1)

# Salva o resultado em CSV com separador de PONTO E VÍRGULA (padrão brasileiro)
csv_path = r'C:\Users\d843702\OneDrive - rede.sp\Área de Trabalho\FAF\FAF\scripts\saida.csv'
df_final.to_csv(csv_path, index=False, header=True, sep=';', encoding='utf-8-sig')

print("[SUCESSO] CSV gerado em: saida.csv")
print(f"[INFO] Formato: Coluna A (Planilha) | Coluna B (Database)")
print(f"[INFO] Separador: ponto e vírgula (;)")
print(f"[INFO] Total de linhas: {len(df_final)}")
# importa_parcerias.py
import sqlite3
import pandas as pd
import re
from pathlib import Path

CSV_PATH = Path("parcerias.csv")
DB_PATH = Path(r"c:\Users\d843702\OneDrive - rede.sp\Área de Trabalho\FAF\FAF\meu_banco.db")

# --- 1) Ler CSV: tentar ';' (Excel BR) e cair para ',' se necessário
def read_csv_try(path):
    encodings = ['latin1', 'utf-8-sig', 'utf-8', 'cp1252']
    for encoding in encodings:
        for sep in [';', ',']:
            try:
                df = pd.read_csv(path, sep=sep, dtype=str, 
                               keep_default_na=False, 
                               na_values=['', 'NULL'], 
                               encoding=encoding)
                if df.shape[1] > 1:
                    return df
            except Exception:
                continue
    raise SystemExit("Falha ao ler CSV: verifique separador e encoding.")

df = read_csv_try(CSV_PATH)
print("Colunas detectadas:", df.columns.tolist())

# --- 2) Mapear nomes do CSV para os nomes das colunas da tabela
mapping = {
    "Número do Termo": "numero_termo",
    "Nome da Organização": "osc",
    "Nome do Projeto": "projeto",
    "Tipo de Termo": "tipo_termo",
    "Portaria que Rege": "portaria",
    "CNPJ da OSC": "cnpj",
    "Data de Início": "inicio",
    "Data de Encerramento": "final",
    "Vigência em Meses": "vigencia_meses",
    "Total do Projeto": "total_previsto",
    "Valor Repassado": "total_pago",
    "Conta Específica Prevista": "conta",
    "É transição?": "transicao",
    "Processo SEI de Celebração": "sei_celeb",
    "Processo SEI de Prestação de Contas": "sei_pc",
    "Endereço do Projeto": "endereco",
    "SEI do Plano de Trabalho": "sei_plano",
    "SEI do Orçamento Anual": "sei_orcamento",
    "Tem contrapartida?": "contrapartida"
}

# Renomear e filtrar apenas colunas mapeadas (preservando a ordem)
df = df.rename(columns=mapping)
df = df[[c for c in mapping.values() if c in df.columns]]

# --- 3) Funções utilitárias de limpeza / conversão
def only_digits(val):
    if val is None:
        return None
    s = str(val).strip()
    if s == "":
        return None
    s = re.sub(r'\D', '', s)
    return s or None

def parse_date_general(val):
    """
    Aceita:
    - strings no formato ISO 'YYYY-MM-DD' -> retorna igual se válido
    - strings em 'DD/MM/YYYY' -> converte para 'YYYY-MM-DD'
    - objetos datetime ou outros formatos reconhecidos por pandas
    """
    if val is None:
        return None
    s = str(val).strip()
    if s == "":
        return None
    # já em ISO?
    if re.match(r'^\d{4}-\d{2}-\d{2}$', s):
        return s
    # tentar parse com pandas (dayfirst True lida com dd/mm/YYYY)
    dt = pd.to_datetime(s, dayfirst=True, errors='coerce')
    if pd.isna(dt):
        return None
    return dt.strftime("%Y-%m-%d")

def parse_number_br(val):
    if val is None:
        return None
    s = str(val).strip()
    if s == "":
        return None
    # remover espaços
    s = s.replace(" ", "")
    # remover pontos de milhar prováveis (ex: 1.234 -> 1234) - tentativa conservadora
    s = re.sub(r'\.(?=\d{3}(?:[^\d]|$))', '', s)
    s = s.replace(',', '.')
    # remover símbolos de moeda, se houver
    s = re.sub(r'[^\d\.\-]', '', s)
    if s == "" or s == ".":
        return None
    try:
        return float(s)
    except:
        return None

def parse_int(val):
    if val is None:
        return None
    s = str(val).strip()
    if s == "":
        return None
    s = re.sub(r'\D', '', s)
    if s == "":
        return None
    try:
        return int(s)
    except:
        return None

def parse_boolean(val):
    if val is None:
        return None
    s = str(val).strip().lower()
    if s in {"1","true","t","sim","s","yes","y"}:
        return 1
    if s in {"0","false","f","nao","não","n","no"}:
        return 0
    return None

# --- 4) Aplicar conversões nas colunas presentes
conversions = {
    "cnpj": only_digits,
    "inicio": parse_date_general,
    "final": parse_date_general,
    "vigencia_meses": parse_int,
    "total_previsto": parse_number_br,
    "total_pago": parse_number_br,
    "conta": parse_number_br,
    "transicao": parse_boolean,
    "sei_celeb": parse_number_br,
    "sei_pc": parse_number_br,
    "sei_plano": parse_number_br,
    "sei_orcamento": parse_number_br,
    "contrapartida": parse_boolean
}

for col, func in conversions.items():
    if col in df.columns:
        df[col] = df[col].apply(lambda v: func(v))

# garantir numero_termo como string e não nulo (chave primária)
if "numero_termo" not in df.columns:
    raise SystemExit("Arquivo CSV não contém a coluna 'Número do Termo' (verifique cabeçalho).")
df["numero_termo"] = df["numero_termo"].astype(str).str.strip()
# remover linhas sem numero_termo
df = df[df["numero_termo"] != ""]

# --- 5) Criar tabela (se não existir)
create_sql = """
CREATE TABLE IF NOT EXISTS Parcerias (
    numero_termo TEXT PRIMARY KEY,
    osc TEXT NOT NULL,
    projeto TEXT,
    tipo_termo TEXT,
    portaria TEXT,
    cnpj TEXT,
    inicio DATE,
    final DATE,
    total_previsto REAL,
    total_pago REAL,
    conta REAL,
    transicao INTEGER,
    sei_celeb REAL,
    sei_pc REAL,
    endereco TEXT,
    sei_plano REAL,
    sei_orcamento REAL,
    contrapartida INTEGER
);
"""

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Limpar tabela existente e começar do zero
cur.execute("DROP TABLE IF EXISTS Parcerias")
conn.commit()

cur.execute(create_sql)

# --- 6) Preparar INSERT com as colunas realmente presentes
table_cols = ["numero_termo","osc","projeto","tipo_termo","portaria","cnpj","inicio","final",
              "total_previsto","total_pago","conta","transicao","sei_celeb","sei_pc",
              "endereco","sei_plano","sei_orcamento","contrapartida"]

present_cols = [c for c in table_cols if c in df.columns]
placeholders = ",".join("?" for _ in present_cols)
col_list_sql = ",".join(present_cols)
insert_sql = f"INSERT OR IGNORE INTO Parcerias ({col_list_sql}) VALUES ({placeholders})"

# Adicione isso antes do loop de inserção
cur.execute("SELECT COUNT(*) FROM Parcerias")
count = cur.fetchone()[0]
print(f"\nRegistros existentes na tabela: {count}")

# --- 7) Inserir linha a linha
inserted = 0
errors = []
for _, row in df.iterrows():
    vals = [row.get(c) if (row.get(c) is not None and str(row.get(c)).strip() != "") else None for c in present_cols]
    # converter numpy types para python nativo se necessário
    vals = [None if (isinstance(v, float) and pd.isna(v)) else v for v in vals]
    try:
        # Primeiro, vamos verificar se já existe
        cur.execute("SELECT COUNT(*) FROM Parcerias WHERE numero_termo = ?", (vals[0],))
        exists = cur.fetchone()[0] > 0
        
        if exists:
            print(f"Registro já existe: {vals[0]}")
            continue
            
        # Tentar inserir
        try:
            cur.execute(insert_sql, vals)
            if cur.rowcount == 1:
                inserted += 1
            else:
                print(f"Falha ao inserir (possível violação NOT NULL). Valores:", vals)
        except sqlite3.IntegrityError as e:
            print(f"Erro de integridade ao inserir {vals[0]}: {e}")
            print("Valores:", vals)
            errors.append((row.get("numero_termo"), str(e)))
        except Exception as e:
            errors.append((row.get("numero_termo"), str(e)))
            
    except Exception as e:
        errors.append((row.get("numero_termo"), str(e)))

conn.commit()
print(f"\nInserção concluída. Linhas lidas: {len(df)}. Inseridas (não-duplicadas): {inserted}. Erros: {len(errors)}")

# Verificar campos NOT NULL vazios
print("\nVerificando campos obrigatórios vazios:")
for _, row in df.iterrows():
    if not row.get("numero_termo") or str(row.get("numero_termo")).strip() == "":
        print("Falta numero_termo")
    if not row.get("osc") or str(row.get("osc")).strip() == "":
        print(f"Falta osc para termo {row.get('numero_termo')}")
    if not row.get("projeto") or str(row.get("projeto")).strip() == "":
        print(f"Falta projeto para termo {row.get('numero_termo')}")
    if not row.get("tipo_termo") or str(row.get("tipo_termo")).strip() == "":
        print(f"Falta tipo_termo para termo {row.get('numero_termo')}")

# --- 8) Mostrar primeiras linhas (opcional)
print("Primeiras 5 linhas na tabela (numero_termo, osc, projeto):")
for r in cur.execute("SELECT numero_termo, osc, projeto FROM Parcerias LIMIT 5"):
    print(r)

# --- 9) Verificação final
print("\nVerificação final:")
cur.execute("SELECT COUNT(*) FROM Parcerias")
total = cur.fetchone()[0]
print(f"Total de registros na tabela: {total}")

print("\nCaminho do banco de dados:", DB_PATH.absolute())

conn.close()

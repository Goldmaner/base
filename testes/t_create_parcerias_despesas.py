"""
Cria tabela Parcerias_Despesas no banco 'meu_banco.db' e fornece helpers para:
 - inserir/desnormalizar valores por "mês do projeto" (mes: 1..60)
 - converter um mes relativo para data calendar (usando campo 'inicio' da tabela Parcerias)
 - gerar SQL pivot dinâmico para exibir mes_1..mes_N

Uso (PowerShell):
    python ./t_create_parcerias_despesas.py         # cria a tabela/indices
    # ou usar as funções a partir de outro script / import

OBS:
 - 'mes' aqui representa o mês relativo ao início do projeto (1 = primeiro mês do projeto).
 - Se quiser suportar mais que 60 meses, altere MAX_MESES abaixo.
"""
import sqlite3
from pathlib import Path
from datetime import datetime
from calendar import monthrange

DB = Path(__file__).resolve().parent / "meu_banco.db"
MAX_MESES = 60  # se quiser suportar 120 meses, altere aqui

CREATE_SQL = f"""
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS Parcerias_Despesas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numero_termo TEXT NOT NULL,
    rubrica TEXT NOT NULL,
    quantidade INTEGER NOT NULL DEFAULT 1 CHECK (quantidade >= 0),
    categoria_despesa TEXT,
    valor REAL NOT NULL CHECK (valor >= 0),
    mes INTEGER NOT NULL CHECK (mes >= 1 AND mes <= {MAX_MESES}),
    ano INTEGER, -- opcional, caso queira salvá-lo também (poderá ser NULL)
    criado_em TEXT DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (numero_termo) REFERENCES Parcerias(numero_termo) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_pd_numero_termo ON Parcerias_Despesas(numero_termo);
CREATE INDEX IF NOT EXISTS idx_pd_numero_mes ON Parcerias_Despesas(numero_termo, mes);

-- Opcional: se quiser impedir duplicatas exatas por (termo, rubrica, categoria, mes)
-- descomente a linha abaixo. Se preferir permitir múltiplos lançamentos no mesmo mês,
-- mantenha-a comentada.
-- CREATE UNIQUE INDEX IF NOT EXISTS ux_pd_termo_rubrica_categoria_mes_ano
--     ON Parcerias_Despesas(numero_termo, rubrica, categoria_despesa, mes, ano);
"""

def create_table(db_path: str = None):
    dbp = str(db_path or DB)
    conn = sqlite3.connect(dbp)
    conn.executescript(CREATE_SQL)
    conn.commit()
    conn.close()
    print(f"Tabela Parcerias_Despesas criada (ou já existente) em: {dbp}")

def insert_despesa(db_path: str,
                   numero_termo: str,
                   rubrica: str,
                   quantidade: int,
                   categoria: str,
                   valor: float,
                   mes: int,
                   ano: int = None):
    """
    Insere uma despesa validando mes e valor.
    - mes: inteiro 1..MAX_MESES (mês relativo ao início do projeto)
    - valor: float (sem 'R$' ou separadores)
    - quantidade: >= 0
    """
    if not isinstance(mes, int) or mes < 1 or mes > MAX_MESES:
        raise ValueError(f"mes deve ser integer entre 1 e {MAX_MESES}")
    if valor is None or float(valor) < 0:
        raise ValueError("valor inválido (deve ser >= 0)")
    if quantidade is None or int(quantidade) < 0:
        raise ValueError("quantidade inválida (>= 0)")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO Parcerias_Despesas
            (numero_termo, rubrica, quantidade, categoria_despesa, valor, mes, ano)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (numero_termo, rubrica, int(quantidade), categoria, float(valor), int(mes), ano))
        conn.commit()
    finally:
        conn.close()

def fetch_parceria_inicio(db_path: str, numero_termo: str):
    """Retorna a data de inicio (string YYYY-MM-DD) da tabela Parcerias para o termo."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    try:
        cur.execute("SELECT inicio FROM Parcerias WHERE numero_termo = ?", (numero_termo,))
        row = cur.fetchone()
        return row["inicio"] if row else None
    finally:
        conn.close()

def add_months_to_date(iso_date: str, months: int) -> str:
    """
    Dado iso_date 'YYYY-MM-DD' e months >= 0, retorna data 'YYYY-MM-DD' correspondente
    adicionando 'months' meses. months=0 -> data original.
    Nota: caso dia > último dia do mês alvo, será ajustado para o último dia.
    """
    if iso_date is None:
        return None
    d = datetime.strptime(iso_date, "%Y-%m-%d")
    total_months = d.year * 12 + (d.month - 1) + months
    y = total_months // 12
    m = (total_months % 12) + 1
    # manter dia, mas ajustar se necessário
    last_day = monthrange(y, m)[1]
    day = min(d.day, last_day)
    return datetime(y, m, day).strftime("%Y-%m-%d")

def mes_relativo_para_data(db_path: str, numero_termo: str, mes_relativo: int):
    """
    Converte mes relativo (1 = primeiro mês do projeto) para data calendar.
    Usa a coluna 'inicio' de Parcerias. Retorna string YYYY-MM-DD ou None.
    Ex: mes_relativo=1 => retorno = inicio
        mes_relativo=2 => inicio + 1 mês
    """
    inicio = fetch_parceria_inicio(db_path, numero_termo)
    if inicio is None:
        return None
    # mes_relativo 1 => months offset 0
    offset = mes_relativo - 1
    return add_months_to_date(inicio, offset)

def build_pivot_sql(numero_termo: str, months: int = 12):
    """
    Gera uma SQL que pivot (mes_1..mes_N) somando valores por rubrica.
    - months: quantas colunas mes_X quer (até MAX_MESES).
    Retorna (sql, params) pronto para executar com sqlite3.
    """
    if months < 1 or months > MAX_MESES:
        raise ValueError(f"months deve ser 1..{MAX_MESES}")
    cases = []
    for m in range(1, months + 1):
        cases.append(f"COALESCE(SUM(CASE WHEN mes = {m} THEN valor END), 0) AS mes_{m}")
    cases_sql = ",\n  ".join(cases)
    sql = f"""
    SELECT
      numero_termo,
      rubrica,
      quantidade,
      categoria_despesa,
      {cases_sql},
      COALESCE(SUM(valor), 0) AS total
    FROM Parcerias_Despesas
    WHERE numero_termo = ?
    GROUP BY numero_termo, rubrica, quantidade, categoria_despesa
    ORDER BY rubrica;
    """
    return sql, (numero_termo,)

def example_usage():
    dbp = str(DB)
    create_table(dbp)
    # exemplo de inserção
    try:
        insert_despesa(dbp, "TCL/103/2020/SMADS/CPM", "Pessoal", 1, "Gerente de Serviço I", 234.53, 1, 2020)
        insert_despesa(dbp, "TCL/103/2020/SMADS/CPM", "Pessoal", 1, "Gerente de Serviço I", 7035.99, 2, 2020)
        print("Exemplos inseridos.")
    except Exception as e:
        print("Erro ao inserir exemplo:", e)

if __name__ == "__main__":
    # Ao executar diretamente, cria a tabela. Não insere exemplos automaticamente
    create_table()
    print("Pronto. Edite/importe usando insert_despesa(...) ou conecte via Flask e use get_db().")
"""
Importa dados de M&A do arquivo import_prestacoes_ma.xlsx para:
  - public.parcerias_monit        (grupo 1: visita + monit)
  - public.parcerias_monit_adicional (grupo 2: justificativa + comissao)

Regras:
  - Só importa linhas cuja chave composta já exista em public.parcerias_analises
  - Usa ON CONFLICT ... DO UPDATE para não sobrescrever dados novos com nulos
  - parcerias_monit_adicional recebe linha SOMENTE se ao menos 1 campo do grupo 2 é não-nulo

Uso:
    python scripts/importar_monit_ma.py
    python scripts/importar_monit_ma.py --xlsx "outro/caminho.xlsx" --dry-run
"""

import sys
import argparse
from pathlib import Path
from datetime import date, datetime, time

import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor, execute_values

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
XLSX_DEFAULT = Path(r"C:\Users\d843702\OneDrive - rede.sp\Área de Trabalho\FAF\import_prestacoes_ma.xlsx")

# Colunas da chave composta (igual ao script comparar_import_analises.py)
COL_TERMO        = "numero_termo"
COL_TIPO         = "tipo_prestacao"
COL_NUM          = "numero_prestacao"
COL_VIG_INI      = "vigencia_inicial"
COL_VIG_FIN      = "vigencia_final"

# Colunas do grupo 1 → parcerias_monit
COLUNAS_MONIT = [
    "visita_status",
    "visita_data",
    "visita_horario",
    "visita_responsavel",
    "visita_avaliacao",
    "monit_status",
    "monit_responsavel",
    "monit_avaliacao",
    "monit_data",
    "observacoes",
]

# Colunas do grupo 2 → parcerias_monit_adicional
# Nota: "justificativa responsavel" (com espaço) normalizado para "justificativa_responsavel"
COLUNAS_ADICIONAL = [
    "justificativa_status",
    "justificativa_avaliacao",
    "justificativa_data",
    "justificativa_responsavel",  # normalizado
    "comissao_visita",
    "comissao_ma",
    "comissao_descumprimento",
]

# Colunas que são datas
COLUNAS_DATA = {"visita_data", "monit_data", "justificativa_data", "vigencia_inicial", "vigencia_final"}

# Colunas que são horário
COLUNAS_HORA = {"visita_horario"}


# ---------------------------------------------------------------------------
# Conexão com o banco
# ---------------------------------------------------------------------------
def get_conn():
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config import DB_CONFIG
    return psycopg2.connect(**DB_CONFIG)


# ---------------------------------------------------------------------------
# Helpers de conversão
# ---------------------------------------------------------------------------
def conv_data(valor) -> date | None:
    if valor is None:
        return None
    if isinstance(valor, float) and pd.isna(valor):
        return None
    if isinstance(valor, (date, datetime)):
        return valor.date() if isinstance(valor, datetime) else valor
    s = str(valor).strip()
    if not s or s.lower() in ("nan", "none", "nat"):
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def conv_hora(valor) -> str | None:
    """Converte para string HH:MM aceita pelo PostgreSQL time."""
    if valor is None:
        return None
    if isinstance(valor, float) and pd.isna(valor):
        return None
    if isinstance(valor, time):
        return valor.strftime("%H:%M:%S")
    if isinstance(valor, datetime):
        return valor.strftime("%H:%M:%S")
    s = str(valor).strip()
    if not s or s.lower() in ("nan", "none", "nat"):
        return None
    # Se veio como "HH:MM" ou "H:MM" ou "HH:MM:SS"
    try:
        if len(s) <= 5:
            return datetime.strptime(s, "%H:%M").strftime("%H:%M:%S")
        return datetime.strptime(s, "%H:%M:%S").strftime("%H:%M:%S")
    except ValueError:
        return None


def conv_str(valor) -> str | None:
    if valor is None:
        return None
    if isinstance(valor, float) and pd.isna(valor):
        return None
    s = str(valor).strip()
    if not s or s.lower() in ("nan", "none", "nat"):
        return None
    return s


def conv_int(valor) -> int | None:
    if valor is None:
        return None
    if isinstance(valor, float) and pd.isna(valor):
        return None
    try:
        return int(float(str(valor).strip()))
    except (ValueError, TypeError):
        return None


def converter_campo(nome_col: str, valor):
    if nome_col in COLUNAS_DATA:
        return conv_data(valor)
    if nome_col in COLUNAS_HORA:
        return conv_hora(valor)
    if nome_col == "numero_prestacao":
        return conv_int(valor)
    return conv_str(valor)


# ---------------------------------------------------------------------------
# Leitura do Excel
# ---------------------------------------------------------------------------
def ler_excel(caminho: Path) -> pd.DataFrame:
    print(f"[Excel] Lendo: {caminho}")
    df = pd.read_excel(caminho, dtype=str)
    # Normalizar nomes de colunas: lower + strip + substituir espaços por underscore
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # Renomear "justificativa_responsavel" se ainda vier como "justificativa_responsavel"
    # (por segurança, já que o original tem espaço)
    if "justificativa_responsavel" not in df.columns:
        for col in df.columns:
            if "justificativa" in col and "responsav" in col:
                df.rename(columns={col: "justificativa_responsavel"}, inplace=True)
                print(f"[Excel] Coluna '{col}' renomeada para 'justificativa_responsavel'")
                break

    print(f"[Excel] Colunas: {list(df.columns)}")
    print(f"[Excel] Total de linhas: {len(df)}")
    return df


# ---------------------------------------------------------------------------
# Chaves existentes no banco
# ---------------------------------------------------------------------------
def ler_chaves_banco(conn) -> set[tuple]:
    print("[Banco] Consultando chaves em parcerias_analises…")
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT numero_termo, tipo_prestacao, numero_prestacao
            FROM public.parcerias_analises
        """)
        rows = cur.fetchall()
    chaves = {(r["numero_termo"], r["tipo_prestacao"], int(r["numero_prestacao"])) for r in rows}
    print(f"[Banco] {len(chaves)} chaves encontradas")
    return chaves


# ---------------------------------------------------------------------------
# Importação
# ---------------------------------------------------------------------------
def importar(df: pd.DataFrame, chaves_banco: set[tuple], conn, dry_run: bool):
    rows_monit    = []  # (termo, tipo, num, col1, col2, ...)
    rows_adicional = []

    ignoradas = 0
    sem_match = 0

    for _, row in df.iterrows():
        termo = conv_str(row.get(COL_TERMO))
        tipo  = conv_str(row.get(COL_TIPO))
        num   = conv_int(row.get(COL_NUM))

        if not termo or not tipo or num is None:
            ignoradas += 1
            continue

        chave = (termo, tipo, num)
        if chave not in chaves_banco:
            sem_match += 1
            continue

        # --- Grupo 1: parcerias_monit ---
        vals_monit = [converter_campo(c, row.get(c)) for c in COLUNAS_MONIT]
        rows_monit.append((termo, tipo, num, *vals_monit))

        # --- Grupo 2: parcerias_monit_adicional (somente se há dados) ---
        vals_adicional = [converter_campo(c, row.get(c)) for c in COLUNAS_ADICIONAL]
        if any(v is not None for v in vals_adicional):
            rows_adicional.append((termo, tipo, num, *vals_adicional))

    print(f"\n[Importação] Linhas com match no banco  : {len(rows_monit)}")
    print(f"[Importação] Linhas com dados adicionais : {len(rows_adicional)}")
    print(f"[Importação] Sem match (ignoradas)        : {sem_match}")
    print(f"[Importação] Inválidas (chave incompleta) : {ignoradas}")

    if dry_run:
        print("\n[DRY-RUN] Nenhuma alteração gravada.")
        return

    cur = conn.cursor()

    # ---------- parcerias_monit ----------
    if rows_monit:
        cols_monit = ["numero_termo", "tipo_prestacao", "numero_prestacao"] + COLUNAS_MONIT
        placeholders = ", ".join(["%s"] * len(cols_monit))
        cols_sql = ", ".join(cols_monit)

        # ON CONFLICT: atualiza somente colunas não-nulas do Excel (preserva dados locais se Excel tem null)
        update_parts = ", ".join([
            f"{c} = CASE WHEN EXCLUDED.{c} IS NOT NULL THEN EXCLUDED.{c} ELSE parcerias_monit.{c} END"
            for c in COLUNAS_MONIT
        ])

        sql_monit = f"""
            INSERT INTO public.parcerias_monit ({cols_sql})
            VALUES ({placeholders})
            ON CONFLICT (numero_termo, tipo_prestacao, numero_prestacao)
            DO UPDATE SET
                {update_parts},
                atualizado_em = now()
        """

        for r in rows_monit:
            cur.execute(sql_monit, r)

        print(f"[Banco] parcerias_monit: {len(rows_monit)} linhas inseridas/atualizadas")

    # ---------- parcerias_monit_adicional ----------
    if rows_adicional:
        cols_adicional = ["numero_termo", "tipo_prestacao", "numero_prestacao"] + COLUNAS_ADICIONAL
        placeholders_a = ", ".join(["%s"] * len(cols_adicional))
        cols_sql_a = ", ".join(cols_adicional)

        update_parts_a = ", ".join([
            f"{c} = CASE WHEN EXCLUDED.{c} IS NOT NULL THEN EXCLUDED.{c} ELSE parcerias_monit_adicional.{c} END"
            for c in COLUNAS_ADICIONAL
        ])

        sql_adicional = f"""
            INSERT INTO public.parcerias_monit_adicional ({cols_sql_a})
            VALUES ({placeholders_a})
            ON CONFLICT (numero_termo, tipo_prestacao, numero_prestacao)
            DO UPDATE SET
                {update_parts_a},
                atualizado_em = now()
        """

        for r in rows_adicional:
            cur.execute(sql_adicional, r)

        print(f"[Banco] parcerias_monit_adicional: {len(rows_adicional)} linhas inseridas/atualizadas")

    conn.commit()
    cur.close()
    print("\n[Banco] Commit realizado com sucesso.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Importa dados de M&A do Excel para parcerias_monit e parcerias_monit_adicional"
    )
    parser.add_argument("--xlsx", default=str(XLSX_DEFAULT), help="Caminho para o arquivo .xlsx")
    parser.add_argument("--dry-run", action="store_true", help="Simula sem gravar no banco")
    args = parser.parse_args()

    xlsx_path = Path(args.xlsx)
    if not xlsx_path.exists():
        print(f"[ERRO] Arquivo não encontrado: {xlsx_path}")
        sys.exit(1)

    conn = get_conn()
    try:
        df = ler_excel(xlsx_path)
        chaves_banco = ler_chaves_banco(conn)
        importar(df, chaves_banco, conn, dry_run=args.dry_run)
    finally:
        conn.close()

    print("\nConcluído.")


if __name__ == "__main__":
    main()

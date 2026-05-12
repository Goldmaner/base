"""
Compara o arquivo import_prestacoes_ma.xlsx com a tabela public.parcerias_analises.
Exibe as linhas do Excel que NÃO existem no banco (chave composta).

Chave composta usada:
    (numero_termo, tipo_prestacao, numero_prestacao, vigencia_inicial, vigencia_final)

Uso:
    python scripts/comparar_import_analises.py
    python scripts/comparar_import_analises.py --xlsx "caminho/outro.xlsx"
    python scripts/comparar_import_analises.py --mostrar-comuns
"""

import sys
import argparse
from pathlib import Path
from datetime import date, datetime

import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

XLSX_DEFAULT = Path(r"C:\Users\d843702\OneDrive - rede.sp\Área de Trabalho\FAF\import_prestacoes_ma.xlsx")

# Colunas esperadas no Excel (case-insensitive, serão normalizadas)
COL_TIPO         = "tipo_prestacao"
COL_NUM          = "numero_prestacao"
COL_VIG_INI      = "vigencia_inicial"
COL_VIG_FIN      = "vigencia_final"
COL_TERMO        = "numero_termo"
COL_RESP         = "responsabilidade_analise"

CHAVE_COMPOSTA = [COL_TERMO, COL_TIPO, COL_NUM, COL_VIG_INI, COL_VIG_FIN]

# ---------------------------------------------------------------------------
# Conexão com o banco (reutiliza DB_CONFIG do projeto)
# ---------------------------------------------------------------------------

def get_conn():
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config import DB_CONFIG
    return psycopg2.connect(**DB_CONFIG)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalizar_data(valor) -> date | None:
    """Converte string 'DD/MM/YYYY', objetos date/datetime ou NaT para date."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    if isinstance(valor, (date, datetime)):
        return valor.date() if isinstance(valor, datetime) else valor
    s = str(valor).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None  # não reconhecido


def normalizar_str(valor) -> str:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    return str(valor).strip()


def chave(row_dict) -> tuple:
    return (
        normalizar_str(row_dict.get(COL_TERMO)),
        normalizar_str(row_dict.get(COL_TIPO)),
        normalizar_str(row_dict.get(COL_NUM)),
        normalizar_data(row_dict.get(COL_VIG_INI)),
        normalizar_data(row_dict.get(COL_VIG_FIN)),
    )


# ---------------------------------------------------------------------------
# Leitura do Excel
# ---------------------------------------------------------------------------

def ler_excel(caminho: Path) -> list[dict]:
    print(f"[Excel] Lendo: {caminho}")
    df = pd.read_excel(caminho, dtype=str)
    # Normaliza nomes de colunas (lower, sem espaços)
    df.columns = [c.strip().lower() for c in df.columns]
    print(f"[Excel] Colunas encontradas: {list(df.columns)}")
    print(f"[Excel] Total de linhas: {len(df)}")

    faltando = [c for c in CHAVE_COMPOSTA if c not in df.columns]
    if faltando:
        raise ValueError(f"Colunas não encontradas no Excel: {faltando}")

    linhas = df.to_dict(orient="records")
    return linhas


# ---------------------------------------------------------------------------
# Leitura do banco
# ---------------------------------------------------------------------------

def ler_banco() -> set[tuple]:
    print("[Banco] Consultando parcerias_analises…")
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT numero_termo, tipo_prestacao, numero_prestacao,
                       vigencia_inicial, vigencia_final
                FROM public.parcerias_analises
            """)
            rows = cur.fetchall()
    finally:
        conn.close()
    print(f"[Banco] Total de registros: {len(rows)}")
    return {chave(dict(r)) for r in rows}


# ---------------------------------------------------------------------------
# Comparação
# ---------------------------------------------------------------------------

def comparar(linhas_excel: list[dict], chaves_banco: set[tuple], mostrar_comuns: bool):
    faltam_no_banco = []
    ja_existem      = []

    for i, row in enumerate(linhas_excel, start=2):  # linha 2 = primeira linha de dados
        k = chave(row)
        if k in chaves_banco:
            ja_existem.append((i, k, row))
        else:
            faltam_no_banco.append((i, k, row))

    print("\n" + "=" * 70)
    print(f"RESULTADO DA COMPARAÇÃO")
    print("=" * 70)
    print(f"  Linhas no Excel         : {len(linhas_excel)}")
    print(f"  Registros no banco      : {len(chaves_banco)}")
    print(f"  Já existem no banco     : {len(ja_existem)}")
    print(f"  FALTAM no banco         : {len(faltam_no_banco)}")
    print("=" * 70)

    if faltam_no_banco:
        print(f"\n{'Linha Excel':<12} {'numero_termo':<35} {'tipo':<12} {'num':<5} {'vig_ini':<12} {'vig_fin':<12}")
        print("-" * 90)
        for linha_num, k, row in faltam_no_banco:
            termo, tipo, num, vi, vf = k
            print(f"{linha_num:<12} {termo:<35} {tipo:<12} {num:<5} {str(vi):<12} {str(vf):<12}")
        print()

        # Salva CSV
        csv_path = Path(__file__).parent.parent / "faltam_no_banco.csv"
        import csv
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["linha_excel", "numero_termo", "tipo_prestacao", "numero_prestacao",
                             "vigencia_inicial", "vigencia_final", "responsabilidade_analise"])
            for linha_num, k, row in faltam_no_banco:
                termo, tipo, num, vi, vf = k
                resp = normalizar_str(row.get(COL_RESP))
                writer.writerow([linha_num, termo, tipo, num, str(vi), str(vf), resp])
        print(f"[CSV] Resultado salvo em: {csv_path}")
    else:
        print("\nNenhuma linha do Excel está faltando no banco. Tudo sincronizado!")

    if mostrar_comuns and ja_existem:
        print(f"\n--- JA EXISTEM NO BANCO ({len(ja_existem)}) ---")
        for linha_num, k, row in ja_existem:
            termo, tipo, num, vi, vf = k
            print(f"  Linha {linha_num}: {termo} | {tipo} | {num} | {vi} → {vf}")

    return faltam_no_banco


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Compara import_prestacoes_ma.xlsx com parcerias_analises")
    parser.add_argument("--xlsx", default=str(XLSX_DEFAULT), help="Caminho para o arquivo .xlsx")
    parser.add_argument("--mostrar-comuns", action="store_true", help="Listar também as linhas que já existem no banco")
    args = parser.parse_args()

    xlsx_path = Path(args.xlsx)
    if not xlsx_path.exists():
        print(f"[ERRO] Arquivo não encontrado: {xlsx_path}")
        sys.exit(1)

    linhas_excel  = ler_excel(xlsx_path)
    chaves_banco  = ler_banco()
    faltam        = comparar(linhas_excel, chaves_banco, args.mostrar_comuns)

    sys.exit(0 if not faltam else 1)


if __name__ == "__main__":
    main()

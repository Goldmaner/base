# -*- coding: utf-8 -*-
"""
Script para importar dados de parcerias de celebração do CSV para
celebracao.celebracao_parcerias

Arquivo: C:\\Users\\d843702\\Downloads\\transicao_celeb.csv
Formato: CSV (delimitador auto-detectado: TAB, ; ou ,)
Destino: celebracao.celebracao_parcerias

IMPORTANTE:
- Equaliza nomes de OSC usando public.Parcerias como referência (via CNPJ)
- Se houver qualquer erro de inserção, a importação inteira é abortada (rollback)
  e uma mensagem detalhada é exibida no terminal

Conversões de tipo:
    meses, dias, numeracao_termo → integer (None se vazio)
    total_previsto               → Decimal (None se vazio)
    inicio, final, assinatura   → date dd/mm/yyyy (None se vazio)

Uso:
    python scripts/importar_celebracao_parcerias.py
"""

import csv
import sys
import os
from datetime import datetime
from decimal import Decimal, InvalidOperation

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
from db import get_db, get_cursor

ARQUIVO_CSV = r"C:\Users\d843702\Downloads\transicao_celeb.csv"

# Colunas esperadas na mesma ordem do CSV (A=0 … Y=24)
COLUNAS_ESPERADAS = [
    'edital_nome', 'unidade_gestora', 'tipo_termo', 'sei_celeb',
    'osc', 'cnpj', 'status', 'substatus', 'projeto', 'endereco_sede',
    'meses', 'dias', 'total_previsto', 'conta', 'lei', 'observacoes',
    'numeracao_termo', 'inicio', 'final', 'assinatura', 'nome_pg',
    'celebracao_secretaria', 'status_generico', 'numero_termo', 'responsavel',
]


# ── Funções auxiliares ────────────────────────────────────────────────────────

def converter_data_br(valor, campo):
    """
    Converte dd/mm/yyyy → date.
    Retorna None se vazio.
    Lança ValueError com contexto se o formato for inválido.
    """
    if not valor or valor.strip() == '':
        return None
    limpo = valor.strip()
    try:
        return datetime.strptime(limpo, '%d/%m/%Y').date()
    except ValueError:
        raise ValueError(
            f"Campo '{campo}': valor '{limpo}' não é uma data válida "
            f"(esperado dd/mm/yyyy)"
        )


def converter_inteiro(valor, campo):
    """
    Converte string → int.
    Retorna None se vazio.
    Lança ValueError com contexto se não for numérico.
    """
    if not valor or valor.strip() == '':
        return None
    limpo = valor.strip()
    try:
        # Aceita "12,00" ou "12.00" gerados por Excel
        return int(float(limpo.replace(',', '.')))
    except (ValueError, TypeError):
        raise ValueError(
            f"Campo '{campo}': valor '{limpo}' não é um número inteiro válido"
        )


def converter_decimal(valor, campo):
    """
    Converte string no formato brasileiro (1.234,56) → Decimal.
    Retorna None se vazio.
    """
    if not valor or valor.strip() == '':
        return None
    limpo = valor.strip()
    # Remove separador de milhar e troca vírgula decimal por ponto
    limpo = limpo.replace('.', '').replace(',', '.')
    try:
        return Decimal(limpo)
    except InvalidOperation:
        raise ValueError(
            f"Campo '{campo}': valor '{valor.strip()}' não é um número decimal válido"
        )


def carregar_mapeamento_oscs(cur):
    """
    Carrega mapeamento CNPJ → Nome OSC de public.Parcerias.
    Retorna dict {cnpj: nome_osc}.
    """
    print("\n📋 Carregando mapeamento de OSCs da tabela Parcerias...")
    cur.execute("""
        SELECT DISTINCT cnpj, osc
        FROM public.Parcerias
        WHERE cnpj IS NOT NULL AND cnpj <> ''
          AND osc  IS NOT NULL AND osc  <> ''
    """)
    mapeamento = {}
    for row in cur.fetchall():
        cnpj = row['cnpj'].strip()
        if cnpj not in mapeamento:
            mapeamento[cnpj] = row['osc'].strip()
    print(f"   ✅ {len(mapeamento)} CNPJs únicos carregados")
    return mapeamento


def equalizar_osc(cnpj, nome_csv, mapeamento):
    """
    Retorna o nome equalizado da OSC:
    - Se CNPJ existe em Parcerias → usa nome de lá
    - Caso contrário → usa nome do CSV
    """
    if cnpj and cnpj.strip() in mapeamento:
        return mapeamento[cnpj.strip()]
    return nome_csv.strip() if nome_csv else None


def processar_linha(row, numero_linha, mapeamento_oscs):
    """
    Converte uma linha do CSV num dicionário pronto para INSERT.
    Levanta ValueError com mensagem detalhada em qualquer problema.
    """
    def v(col):
        """Retorna valor bruto da coluna, ou '' se ausente."""
        return row.get(col, '')

    try:
        cnpj      = v('cnpj').strip() or None
        osc_csv   = v('osc')
        osc_final = equalizar_osc(cnpj, osc_csv, mapeamento_oscs)

        return {
            'edital_nome':           v('edital_nome').strip() or None,
            'unidade_gestora':       v('unidade_gestora').strip() or None,
            'tipo_termo':            v('tipo_termo').strip() or None,
            'sei_celeb':             v('sei_celeb').strip() or None,
            'osc':                   osc_final,
            'cnpj':                  cnpj,
            'status':                v('status').strip() or None,
            'substatus':             v('substatus').strip() or None,
            'projeto':               v('projeto').strip() or None,
            'endereco_sede':         v('endereco_sede').strip() or None,
            'meses':                 converter_inteiro(v('meses'), 'meses'),
            'dias':                  converter_inteiro(v('dias'), 'dias'),
            'total_previsto':        converter_decimal(v('total_previsto'), 'total_previsto'),
            'conta':                 v('conta').strip() or None,
            'lei':                   v('lei').strip() or None,
            'observacoes':           v('observacoes').strip() or None,
            'numeracao_termo':       converter_inteiro(v('numeracao_termo'), 'numeracao_termo'),
            'inicio':                converter_data_br(v('inicio'), 'inicio'),
            'final':                 converter_data_br(v('final'), 'final'),
            'assinatura':            converter_data_br(v('assinatura'), 'assinatura'),
            'nome_pg':               v('nome_pg').strip() or None,
            'celebracao_secretaria': v('celebracao_secretaria').strip() or None,
            'status_generico':       v('status_generico').strip() or None,
            'numero_termo':          v('numero_termo').strip() or None,
            'responsavel':           v('responsavel').strip() or None,
        }

    except ValueError as e:
        raise ValueError(f"Linha {numero_linha}: {e}")


# ── Importação principal ──────────────────────────────────────────────────────

def importar():
    if not os.path.exists(ARQUIVO_CSV):
        print(f"\n❌ Arquivo não encontrado: {ARQUIVO_CSV}")
        return

    with app.app_context():
        conn = get_db()
        cur  = get_cursor()

        try:
            mapeamento_oscs = carregar_mapeamento_oscs(cur)

            # ── Leitura do CSV ────────────────────────────────────────────────
            print(f"\n📖 Lendo arquivo: {ARQUIVO_CSV}")
            with open(ARQUIVO_CSV, 'r', encoding='utf-8-sig') as f:
                primeira_linha = f.readline()
                f.seek(0)

                if '\t' in primeira_linha:
                    delimiter = '\t'
                elif ';' in primeira_linha:
                    delimiter = ';'
                else:
                    delimiter = ','

                label_delim = 'TAB' if delimiter == '\t' else delimiter
                print(f"   Delimitador detectado: {label_delim}")

                reader  = csv.DictReader(f, delimiter=delimiter)
                registros_brutos = list(reader)

            print(f"   ✅ {len(registros_brutos)} linhas lidas")

            # ── Validação das colunas ─────────────────────────────────────────
            if registros_brutos:
                colunas_csv = list(registros_brutos[0].keys())
                faltantes   = [c for c in COLUNAS_ESPERADAS if c not in colunas_csv]
                if faltantes:
                    print(f"\n❌ Colunas ausentes no CSV: {faltantes}")
                    print(f"   Colunas encontradas:  {colunas_csv}")
                    return

                print(f"\n📝 Colunas encontradas ({len(colunas_csv)}):")
                for col in colunas_csv:
                    print(f"   - {col}")

                print(f"\n📄 Primeira linha de dados:")
                for key, val in registros_brutos[0].items():
                    exibir = (val[:60] + '...') if val and len(val) > 60 else val
                    print(f"   {key}: {exibir}")
            else:
                print("\n⚠️ CSV vazio — nenhuma linha de dados.")
                return

            # ── Confirmação ───────────────────────────────────────────────────
            print("\n" + "=" * 80)
            resposta = input("\n⚠️ Deseja continuar com a conversão e importação? (S/N): ")
            if resposta.strip().upper() != 'S':
                print("❌ Importação cancelada pelo usuário")
                return

            # ── Conversão de todas as linhas ANTES de qualquer INSERT ─────────
            print(f"\n🔄 Convertendo {len(registros_brutos)} linhas...")
            registros_convertidos = []
            erros_conversao = []

            for i, row in enumerate(registros_brutos, start=2):  # linha 1 = cabeçalho
                try:
                    dados = processar_linha(row, i, mapeamento_oscs)
                    registros_convertidos.append(dados)
                except ValueError as e:
                    erros_conversao.append(str(e))

            if erros_conversao:
                print(f"\n{'=' * 80}")
                print(f"❌ ERROS DE CONVERSÃO ENCONTRADOS — Importação ABORTADA")
                print(f"{'=' * 80}")
                for erro in erros_conversao:
                    print(f"  • {erro}")
                print(f"\nTotal de erros: {len(erros_conversao)}")
                print("Nenhum dado foi importado.")
                return

            print(f"   ✅ Todas as {len(registros_convertidos)} linhas convertidas sem erros")

            # ── Duplicidade por numero_termo + sei_celeb ──────────────────────
            cur.execute("""
                SELECT numero_termo, sei_celeb
                FROM celebracao.celebracao_parcerias
            """)
            existentes = {
                (r['numero_termo'], r['sei_celeb'])
                for r in cur.fetchall()
            }
            print(f"\n📊 Registros já existentes na tabela: {len(existentes)}")

            novos     = []
            duplicados = 0

            for dados in registros_convertidos:
                chave = (dados['numero_termo'], dados['sei_celeb'])
                if chave in existentes and any(chave):
                    duplicados += 1
                    print(f"   ⏭️ Duplicado: termo={dados['numero_termo']} | sei={dados['sei_celeb']}")
                else:
                    novos.append(dados)

            print(f"   → {len(novos)} registros novos a inserir | {duplicados} duplicados ignorados")

            if not novos:
                print("\n⚠️ Nenhum registro novo para importar.")
                return

            # ── INSERT (zero tolerância a erros) ──────────────────────────────
            print(f"\n🚀 Inserindo {len(novos)} registros...")

            SQL = """
                INSERT INTO celebracao.celebracao_parcerias (
                    edital_nome, unidade_gestora, tipo_termo, sei_celeb,
                    osc, cnpj, status, substatus, projeto, endereco_sede,
                    meses, dias, total_previsto, conta, lei, observacoes,
                    numeracao_termo, inicio, final, assinatura, nome_pg,
                    celebracao_secretaria, status_generico, numero_termo, responsavel,
                    created_at, created_por
                ) VALUES (
                    %(edital_nome)s, %(unidade_gestora)s, %(tipo_termo)s, %(sei_celeb)s,
                    %(osc)s, %(cnpj)s, %(status)s, %(substatus)s, %(projeto)s, %(endereco_sede)s,
                    %(meses)s, %(dias)s, %(total_previsto)s, %(conta)s, %(lei)s, %(observacoes)s,
                    %(numeracao_termo)s, %(inicio)s, %(final)s, %(assinatura)s, %(nome_pg)s,
                    %(celebracao_secretaria)s, %(status_generico)s, %(numero_termo)s, %(responsavel)s,
                    NOW(), 'Script de Importação'
                )
            """

            for idx, dados in enumerate(novos, start=1):
                try:
                    cur.execute(SQL, dados)
                except Exception as e:
                    conn.rollback()
                    print(f"\n{'=' * 80}")
                    print(f"❌ ERRO NO INSERT — Importação ABORTADA (rollback executado)")
                    print(f"{'=' * 80}")
                    print(f"  Registro #{idx}  |  termo={dados.get('numero_termo')}  |  sei={dados.get('sei_celeb')}")
                    print(f"  OSC: {dados.get('osc')}")
                    print(f"  CNPJ: {dados.get('cnpj')}")
                    print(f"\n  Erro do banco:")
                    print(f"    {type(e).__name__}: {e}")
                    print(f"\n  Valores que causaram o erro:")
                    for campo, valor in dados.items():
                        print(f"    {campo}: {repr(valor)}")
                    print(f"\nNenhum dos {len(novos)} registros foi persistido.")
                    return

                if idx % 50 == 0 or idx == len(novos):
                    print(f"   ✅ {idx}/{len(novos)} inseridos...")

            conn.commit()

            # ── Resumo final ──────────────────────────────────────────────────
            print(f"\n{'=' * 80}")
            print("RESUMO DA IMPORTAÇÃO")
            print(f"{'=' * 80}")
            print(f"✅ Registros inseridos : {len(novos)}")
            print(f"⏭️  Duplicados ignorados: {duplicados}")
            print(f"📊 Total no CSV        : {len(registros_brutos)}")
            print(f"{'=' * 80}")
            print("\n🎉 Importação concluída com sucesso!")

        except Exception as e:
            conn.rollback()
            print(f"\n{'=' * 80}")
            print("❌ ERRO INESPERADO — Importação ABORTADA (rollback executado)")
            print(f"{'=' * 80}")
            print(f"  {type(e).__name__}: {e}")
            import traceback
            print("\nTraceback completo:")
            traceback.print_exc()
            print("\nNenhum dado foi persistido.")

        finally:
            cur.close()


# ── Entrada ───────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print("=" * 80)
    print("IMPORTAÇÃO — celebracao.celebracao_parcerias")
    print("=" * 80)
    print(f"Origem : {ARQUIVO_CSV}")
    print(f"Destino: celebracao.celebracao_parcerias")
    print("=" * 80)
    print("\n⚙️  Equalização de nomes:")
    print("   CNPJ encontrado em Parcerias → usa nome de lá")
    print("   Caso contrário              → usa nome do CSV")
    print("=" * 80)

    importar()

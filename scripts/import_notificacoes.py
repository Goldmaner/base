# -*- coding: utf-8 -*-
"""
Script para importar dados de notificações do arquivo CSV
para public.parcerias_notificacoes

Arquivo: C:\\Users\\d843702\\Downloads\\import_notificacoes.csv
Formato: UTF-8, delimitador TAB
Destino: public.parcerias_notificacoes

Chave de deduplicação: (tipo_doc, ano_doc, numero_doc)

Uso:
    python scripts/import_notificacoes.py
"""

import csv
import sys
import os
from datetime import datetime, timezone

# Adicionar o diretório raiz ao path para importar módulos do Flask
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
from db import get_db, get_cursor

ARQUIVO_CSV = r"C:\Users\d843702\Downloads\import_notificacoes.csv"


def converter_data_br(data_str):
    """
    Converte data do formato brasileiro (dd/mm/yyyy) para objeto date.
    Retorna None se vazio ou inválido.
    """
    if not data_str or data_str.strip() == '':
        return None
    try:
        return datetime.strptime(data_str.strip(), '%d/%m/%Y').date()
    except ValueError:
        return None


def converter_timestamp_br(data_str):
    """
    Converte data dd/mm/yyyy para timestamp with time zone (meia-noite UTC).
    Retorna None se vazio ou inválido.
    """
    d = converter_data_br(data_str)
    if d is None:
        return None
    # Retorna como datetime sem timezone — o PostgreSQL vai usar o timezone da sessão
    return datetime(d.year, d.month, d.day, 0, 0, 0)


def converter_bool(valor_str):
    """
    Converte string 'true'/'false' para bool Python.
    Padrão: False.
    """
    if not valor_str:
        return False
    return valor_str.strip().lower() == 'true'


def converter_int(valor_str, padrao=0):
    """Converte string para int, retorna padrao se vazio ou inválido."""
    if not valor_str or valor_str.strip() == '':
        return padrao
    try:
        return int(valor_str.strip())
    except ValueError:
        return padrao


def atualizar_doc_respondido():
    """
    Lê o CSV corrigido e atualiza APENAS a coluna doc_respondido
    nos registros já existentes, usando (tipo_doc, ano_doc, numero_doc) como chave.
    """
    if not os.path.exists(ARQUIVO_CSV):
        print(f"❌ Arquivo não encontrado: {ARQUIVO_CSV}")
        return

    with app.app_context():
        conn = get_db()
        cur = get_cursor()

        try:
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
                reader = csv.DictReader(f, delimiter=delimiter)
                registros = list(reader)

            print(f"   ✅ {len(registros)} linhas lidas do CSV")

            print("\n" + "=" * 80)
            resposta = input("\n⚠️  Atualizar doc_respondido em todos os registros do CSV? (S/N): ")
            if resposta.strip().upper() != 'S':
                print("❌ Operação cancelada pelo usuário")
                return

            atualizados = 0
            nao_encontrados = 0
            erros = 0

            print(f"\n🔄 Atualizando {len(registros)} registros...")

            for i, row in enumerate(registros, 1):
                tipo_doc       = row.get('tipo_doc', '').strip() or None
                ano_doc        = converter_int(row.get('ano_doc'), None)
                numero_doc     = converter_int(row.get('numero_doc'), None)
                doc_respondido = converter_bool(row.get('doc_respondido'))

                if not tipo_doc or ano_doc is None or numero_doc is None:
                    print(f"   ⚠️  Linha {i}: chave inválida, pulando.")
                    erros += 1
                    continue

                try:
                    cur.execute("""
                        UPDATE public.parcerias_notificacoes
                        SET doc_respondido = %s,
                            updated_at     = NOW()
                        WHERE tipo_doc   = %s
                          AND ano_doc    = %s
                          AND numero_doc = %s
                    """, (doc_respondido, tipo_doc, ano_doc, numero_doc))

                    if cur.rowcount == 0:
                        print(f"   ⚠️  Linha {i}: não encontrado — {tipo_doc} nº {numero_doc}/{ano_doc}")
                        nao_encontrados += 1
                    else:
                        atualizados += 1
                        if i <= 5 or i % 50 == 0:
                            print(f"   ✅ Linha {i}/{len(registros)}: "
                                  f"{tipo_doc} nº {numero_doc}/{ano_doc} → doc_respondido={doc_respondido}")

                except Exception as e:
                    print(f"   ❌ Linha {i}: Erro: {e}")
                    erros += 1

            conn.commit()

            print("\n" + "=" * 80)
            print("RESUMO DA ATUALIZAÇÃO")
            print("=" * 80)
            print(f"✅ Registros atualizados  : {atualizados}")
            print(f"⚠️  Não encontrados        : {nao_encontrados}")
            print(f"❌ Erros                   : {erros}")
            print(f"📊 Total no arquivo        : {len(registros)}")
            print("=" * 80)

            if atualizados > 0:
                print(f"\n🎉 doc_respondido atualizado com sucesso!")

        except Exception as e:
            conn.rollback()
            print(f"\n❌ ERRO GERAL: {e}")
            import traceback
            traceback.print_exc()

        finally:
            cur.close()


def importar_notificacoes():
    """Importa dados de notificações do CSV para o banco de dados."""

    if not os.path.exists(ARQUIVO_CSV):
        print(f"❌ Arquivo não encontrado: {ARQUIVO_CSV}")
        return

    with app.app_context():
        conn = get_db()
        cur = get_cursor()

        try:
            # ── Ler CSV ─────────────────────────────────────────────────────
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

                print(f"   Delimitador detectado: {'TAB' if delimiter == chr(9) else delimiter}")
                reader = csv.DictReader(f, delimiter=delimiter)
                registros = list(reader)

            print(f"   ✅ {len(registros)} linhas lidas do CSV")

            if registros:
                print(f"\n📝 Colunas encontradas no CSV:")
                for col in registros[0].keys():
                    print(f"   - {col}")
                print(f"\n📄 Exemplo da primeira linha:")
                for key, value in registros[0].items():
                    valor_display = value[:60] + '...' if value and len(value) > 60 else value
                    print(f"   {key}: {valor_display}")

            print("\n" + "=" * 80)
            resposta = input("\n⚠️  Deseja continuar com a importação? (S/N): ")
            if resposta.strip().upper() != 'S':
                print("❌ Importação cancelada pelo usuário")
                return

            # ── Carregar chaves existentes ────────────────────────────────
            cur.execute("""
                SELECT tipo_doc, ano_doc, numero_doc
                FROM public.parcerias_notificacoes
            """)
            existentes = {
                (row['tipo_doc'], row['ano_doc'], row['numero_doc'])
                for row in cur.fetchall()
            }
            print(f"\n📊 Registros já cadastrados: {len(existentes)}")

            # ── Processar registros ───────────────────────────────────────
            inseridos = 0
            duplicados = 0
            erros = 0

            print(f"\n🔄 Processando {len(registros)} registros...")

            for i, row in enumerate(registros, 1):
                tipo_doc       = row.get('tipo_doc', '').strip() or None
                ano_doc        = converter_int(row.get('ano_doc'), None)
                numero_doc     = converter_int(row.get('numero_doc'), None)
                numero_termo   = row.get('numero_termo', '').strip() or None
                nome_resp      = row.get('nome_responsavel', '').strip() or None
                processo_doc   = row.get('processo_doc', '').strip() or None
                sei_doc        = row.get('sei_doc', '').strip() or None
                observacoes    = row.get('observacoes', '').strip() or None
                dilacao        = converter_bool(row.get('dilacao'))
                dilacao_dias   = converter_int(row.get('dilacao_dias'), 0)
                doc_respondido = converter_bool(row.get('doc_respondido'))

                data_doc       = converter_data_br(row.get('data_doc'))
                data_pub       = converter_data_br(row.get('data_pub'))
                data_email_ar  = converter_timestamp_br(row.get('data_email_ar'))

                # Coluna extra do CSV sem correspondência na tabela: sei_numero — ignorada

                # Validações mínimas
                if not tipo_doc:
                    print(f"   ⚠️  Linha {i}: tipo_doc vazio, pulando.")
                    erros += 1
                    continue
                if ano_doc is None or numero_doc is None:
                    print(f"   ⚠️  Linha {i}: ano_doc ou numero_doc inválido, pulando.")
                    erros += 1
                    continue

                # Verificar duplicidade
                chave = (tipo_doc, ano_doc, numero_doc)
                if chave in existentes:
                    print(f"   ⏭️  Linha {i}: já existe — {tipo_doc} nº {numero_doc}/{ano_doc}")
                    duplicados += 1
                    continue

                # Inserir
                try:
                    cur.execute("""
                        INSERT INTO public.parcerias_notificacoes (
                            tipo_doc, ano_doc, numero_doc, numero_termo,
                            nome_responsavel, data_doc, data_pub, data_email_ar,
                            processo_doc, sei_doc, observacoes,
                            dilacao, dilacao_dias, doc_respondido
                        ) VALUES (
                            %s, %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s, %s,
                            %s, %s, %s
                        )
                    """, (
                        tipo_doc, ano_doc, numero_doc, numero_termo,
                        nome_resp, data_doc, data_pub, data_email_ar,
                        processo_doc, sei_doc, observacoes,
                        dilacao, dilacao_dias, doc_respondido
                    ))

                    existentes.add(chave)  # evita duplicata dentro do próprio CSV
                    inseridos += 1

                    if i <= 5 or i % 50 == 0:
                        print(f"   ✅ Linha {i}/{len(registros)}: "
                              f"{tipo_doc} nº {numero_doc}/{ano_doc} inserido")

                except Exception as e:
                    print(f"   ❌ Linha {i}: Erro ao inserir: {e}")
                    erros += 1

            conn.commit()

            # ── Resumo ────────────────────────────────────────────────────
            print("\n" + "=" * 80)
            print("RESUMO DA IMPORTAÇÃO")
            print("=" * 80)
            print(f"✅ Registros inseridos  : {inseridos}")
            print(f"⏭️  Duplicados (pulados) : {duplicados}")
            print(f"❌ Erros                : {erros}")
            print(f"📊 Total no arquivo     : {len(registros)}")
            print("=" * 80)

            if inseridos > 0:
                print(f"\n🎉 Importação concluída com sucesso!")
            else:
                print(f"\n⚠️  Nenhum registro novo foi inserido.")

        except Exception as e:
            conn.rollback()
            print(f"\n❌ ERRO GERAL: {e}")
            import traceback
            traceback.print_exc()

        finally:
            cur.close()


if __name__ == '__main__':
    modo_update = '--update-doc-respondido' in sys.argv

    print("=" * 80)
    if modo_update:
        print("ATUALIZAÇÃO DE doc_respondido - PARCERIAS NOTIFICAÇÕES")
    else:
        print("IMPORTAÇÃO DE DADOS - PARCERIAS NOTIFICAÇÕES")
    print("=" * 80)
    print(f"Origem : {ARQUIVO_CSV}")
    print(f"Destino: public.parcerias_notificacoes")
    print("Chave  : (tipo_doc, ano_doc, numero_doc)")
    print("=" * 80)

    if modo_update:
        atualizar_doc_respondido()
    else:
        importar_notificacoes()

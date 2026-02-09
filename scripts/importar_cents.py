# -*- coding: utf-8 -*-
"""
Script para importar dados de CENTS do arquivo CSV para celebracao.gestao_cents

Arquivo: C:\\Users\\d843702\\Downloads\\cents_importacao.csv
Formato: UTF-8, delimitador TAB
Destino: celebracao.gestao_cents

IMPORTANTE: Equaliza nomes de OSC usando public.Parcerias como referência
- Se o CNPJ já existe em Parcerias, usa o nome de lá
- Caso contrário, usa o nome do CSV
- Isso evita duplicidade de nomes no dicionário de OSCs

Uso:
    python scripts/importar_cents.py
"""

import csv
import sys
import os
from datetime import datetime

# Adicionar o diretório raiz ao path para importar módulos do Flask
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
from db import get_db, get_cursor

ARQUIVO_CSV = r"C:\Users\d843702\Downloads\cents_importacao.csv"


def converter_data_br(data_str):
    """
    Converte data do formato brasileiro (dd/mm/yyyy) para objeto date
    Retorna None se vazio ou inválido
    """
    if not data_str or data_str.strip() == '':
        return None
    
    try:
        # Remove espaços extras
        data_limpa = data_str.strip()
        
        # Tenta converter dd/mm/yyyy
        data_obj = datetime.strptime(data_limpa, '%d/%m/%Y').date()
        return data_obj
    except ValueError:
        return None


def carregar_mapeamento_oscs(cur):
    """
    Carrega mapeamento CNPJ -> Nome OSC da tabela public.Parcerias
    Retorna dicionário {cnpj: nome_osc}
    """
    print("\n📋 Carregando mapeamento de OSCs da tabela Parcerias...")
    
    cur.execute("""
        SELECT DISTINCT cnpj, osc
        FROM public.Parcerias
        WHERE cnpj IS NOT NULL AND cnpj != ''
        AND osc IS NOT NULL AND osc != ''
    """)
    
    mapeamento = {}
    for row in cur.fetchall():
        cnpj = row['cnpj'].strip()
        osc = row['osc'].strip()
        
        # Se já existe um nome para este CNPJ, mantém o primeiro encontrado
        if cnpj not in mapeamento:
            mapeamento[cnpj] = osc
    
    print(f"   ✅ {len(mapeamento)} CNPJs únicos encontrados em Parcerias")
    return mapeamento


def equalizar_nome_osc(cnpj, nome_csv, mapeamento_oscs):
    """
    Retorna o nome da OSC equalizado:
    - Se CNPJ existe no mapeamento (Parcerias), usa nome de lá
    - Caso contrário, usa nome do CSV
    """
    if not cnpj or cnpj.strip() == '':
        return nome_csv.strip() if nome_csv else None
    
    cnpj_limpo = cnpj.strip()
    
    if cnpj_limpo in mapeamento_oscs:
        return mapeamento_oscs[cnpj_limpo]
    else:
        return nome_csv.strip() if nome_csv else None


def importar_cents():
    """Importa dados de CENTS do CSV para o banco de dados"""
    
    if not os.path.exists(ARQUIVO_CSV):
        print(f"❌ Arquivo não encontrado: {ARQUIVO_CSV}")
        return
    
    with app.app_context():
        conn = get_db()
        cur = get_cursor()
        
        try:
            # Carregar mapeamento de OSCs da tabela Parcerias
            mapeamento_oscs = carregar_mapeamento_oscs(cur)
            
            # Ler CSV
            print(f"\n📖 Lendo arquivo: {ARQUIVO_CSV}")
            with open(ARQUIVO_CSV, 'r', encoding='utf-8-sig') as f:
                # Detectar delimitador
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
            
            # Debug: mostrar colunas e primeira linha
            if registros:
                print(f"\n📝 Colunas encontradas no CSV:")
                for col in registros[0].keys():
                    print(f"   - {col}")
                
                print(f"\n📄 Exemplo da primeira linha:")
                for key, value in registros[0].items():
                    valor_display = value[:50] + '...' if value and len(value) > 50 else value
                    print(f"   {key}: {valor_display}")
            
            print("\n" + "="*80)
            resposta = input("\n⚠️ Deseja continuar com a importação? (S/N): ")
            
            if resposta.strip().upper() != 'S':
                print("❌ Importação cancelada pelo usuário")
                return
            
            # Verificar registros existentes (por CNPJ e SEI)
            cur.execute("SELECT osc_cnpj, cents_sei FROM celebracao.gestao_cents")
            existentes = {(row['osc_cnpj'], row['cents_sei']) for row in cur.fetchall() if row['osc_cnpj'] or row['cents_sei']}
            print(f"\n📊 Registros já cadastrados: {len(existentes)}")
            
            # Contadores
            inseridos = 0
            duplicados = 0
            equalizados = 0
            erros = 0
            
            # Processar cada registro
            print(f"\n🔄 Processando registros...")
            
            for i, row in enumerate(registros, 1):
                # Extrair dados do CSV
                osc_csv = row.get('osc', '').strip()
                osc_cnpj = row.get('osc_cnpj', '').strip() or None
                cents_sei = row.get('cents_sei', '').strip() or None
                cents_responsavel = row.get('cents_responsavel', '').strip() or None
                cents_status = row.get('cents_status', '').strip() or None
                cents_prioridade = row.get('cents_prioridade', '').strip() or None
                observacoes = row.get('observacoes', '').strip() or None
                
                # Equalizar nome da OSC
                osc_final = equalizar_nome_osc(osc_cnpj, osc_csv, mapeamento_oscs)
                
                if osc_final != osc_csv and osc_cnpj in mapeamento_oscs:
                    equalizados += 1
                    print(f"   🔄 Linha {i}: CNPJ {osc_cnpj}")
                    print(f"      CSV: {osc_csv}")
                    print(f"      Equalizado para: {osc_final}")
                
                # Converter datas
                cents_requerimento = converter_data_br(row.get('cents_requerimento', ''))
                cents_ultima_not = converter_data_br(row.get('cents_ultima_not', ''))
                cents_publicacao = converter_data_br(row.get('cents_publicacao', ''))
                cents_vencimento = converter_data_br(row.get('cents_vencimento', ''))
                
                # Validações básicas
                if not osc_final and not osc_cnpj:
                    print(f"   ⚠️ Linha {i}: Sem OSC e sem CNPJ, pulando...")
                    erros += 1
                    continue
                
                # Verificar duplicidade (CNPJ + SEI)
                chave = (osc_cnpj, cents_sei)
                if chave in existentes and (osc_cnpj or cents_sei):
                    print(f"   ⏭️ Linha {i}: Registro já existe (CNPJ: {osc_cnpj}, SEI: {cents_sei})")
                    duplicados += 1
                    continue
                
                # Inserir novo registro
                try:
                    cur.execute("""
                        INSERT INTO celebracao.gestao_cents (
                            osc, osc_cnpj, cents_sei, cents_responsavel,
                            cents_requerimento, cents_ultima_not, cents_publicacao, cents_vencimento,
                            cents_status, cents_prioridade, observacoes
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        osc_final,
                        osc_cnpj,
                        cents_sei,
                        cents_responsavel,
                        cents_requerimento,
                        cents_ultima_not,
                        cents_publicacao,
                        cents_vencimento,
                        cents_status,
                        cents_prioridade,
                        observacoes
                    ))
                    
                    inseridos += 1
                    
                    if i <= 5 or i % 10 == 0:  # Mostrar progresso
                        print(f"   ✅ Linha {i}/{len(registros)}: {osc_final[:40]}... inserido")
                    
                except Exception as e:
                    print(f"   ❌ Linha {i}: Erro ao inserir: {str(e)}")
                    erros += 1
            
            # Commit
            conn.commit()
            
            # Resumo
            print("\n" + "="*80)
            print("RESUMO DA IMPORTAÇÃO")
            print("="*80)
            print(f"✅ Registros inseridos: {inseridos}")
            print(f"🔄 Nomes equalizados: {equalizados}")
            print(f"⏭️ Registros duplicados: {duplicados}")
            print(f"❌ Erros: {erros}")
            print(f"📊 Total processado: {len(registros)}")
            print("="*80)
            
            if inseridos > 0:
                print(f"\n🎉 Importação concluída com sucesso!")
                if equalizados > 0:
                    print(f"   {equalizados} OSCs foram equalizadas usando nomes de Parcerias")
            else:
                print(f"\n⚠️ Nenhum registro novo foi inserido.")
                
        except Exception as e:
            conn.rollback()
            print(f"\n❌ ERRO GERAL: {str(e)}")
            import traceback
            traceback.print_exc()
        
        finally:
            cur.close()


if __name__ == '__main__':
    print("="*80)
    print("IMPORTAÇÃO DE DADOS - GESTÃO CENTS")
    print("="*80)
    print(f"Origem: {ARQUIVO_CSV}")
    print(f"Destino: celebracao.gestao_cents")
    print("="*80)
    print("\n⚙️ Equalização de nomes:")
    print("   Se CNPJ existe em Parcerias → usa nome de lá")
    print("   Caso contrário → usa nome do CSV")
    print("="*80)
    
    importar_cents()

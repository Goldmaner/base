"""
Script para atualizar portarias e identificar transições na tabela Parcerias
Baseado nas regras de legislação definidas no sistema
"""

import psycopg2
import psycopg2.extras
import os
from datetime import datetime
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Configuração do banco
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'port': os.environ.get('DB_PORT', '5432'),
    'database': os.environ.get('DB_DATABASE', 'projeto_parcerias'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', '')
}

# Regras de legislação (mesmas de main.py)
REGRAS_LEGISLACAO = [
    {
        'lei': 'Decreto nº 6.170',
        'inicio': '2007-07-25',
        'termino': '2008-08-11',
        'regra_termo': ['TCV'],
        'regra_coordenacao': []
    },
    {
        'lei': 'Portaria nº 006/2008/SF-SEMPLA',
        'inicio': '2008-08-12',
        'termino': '2012-09-30',
        'regra_termo': ['TCV'],
        'regra_coordenacao': []
    },
    {
        'lei': 'Portaria nº 072/SMPP/2012',
        'inicio': '2012-03-22',
        'termino': '2014-05-21',
        'regra_termo': ['TCV'],
        'regra_coordenacao': ['FUMCAD']
    },
    {
        'lei': 'Portaria nº 009/SMDHC/2014',
        'inicio': '2014-05-22',
        'termino': '2017-09-30',
        'regra_termo': ['TCV'],
        'regra_coordenacao': ['FUMCAD']
    },
    {
        'lei': 'Portaria nº 121/SMDHC/2019',
        'inicio': '2017-10-01',
        'termino': '2023-02-28',
        'regra_termo': ['TFM', 'TCL'],
        'regra_coordenacao': []
    },
    {
        'lei': 'Portaria nº 140/SMDHC/2019',
        'inicio': '2017-10-01',
        'termino': '2023-12-31',
        'regra_termo': ['TFM', 'TCL'],
        'regra_coordenacao': ['FUMCAD', 'FMID']
    },
    {
        'lei': 'Portaria nº 021/SMDHC/2023',
        'inicio': '2023-03-01',
        'termino': '2030-12-31',
        'regra_termo': ['TFM', 'TCL'],
        'regra_coordenacao': []
    },
    {
        'lei': 'Portaria nº 090/SMDHC/2023',
        'inicio': '2024-01-01',
        'termino': '2030-12-31',
        'regra_termo': ['TFM', 'TCL'],
        'regra_coordenacao': ['FUMCAD', 'FMID']
    }
]


def determinar_portaria(numero_termo, data_inicio):
    """
    Determina a portaria baseada no número do termo e data de início
    """
    if not data_inicio:
        return None
    
    # Converter data para string YYYY-MM-DD
    if isinstance(data_inicio, datetime):
        data_inicio_str = data_inicio.strftime('%Y-%m-%d')
    else:
        data_inicio_str = str(data_inicio)
    
    # Extrair informações do termo
    numero_termo_upper = numero_termo.upper()
    tem_tfm = 'TFM' in numero_termo_upper
    tem_tcl = 'TCL' in numero_termo_upper
    tem_tcv = 'TCV' in numero_termo_upper
    tem_fumcad = 'FUMCAD' in numero_termo_upper
    tem_fmid = 'FMID' in numero_termo_upper
    
    portaria_selecionada = None
    
    for regra in REGRAS_LEGISLACAO:
        # Verificar se a data de início está no período da legislação
        if data_inicio_str < regra['inicio'] or data_inicio_str > regra['termino']:
            continue
        
        # Verificar regra de termo
        if (tem_tfm or tem_tcl) and not any(t in regra['regra_termo'] for t in ['TFM', 'TCL']):
            continue
        if tem_tcv and 'TCV' not in regra['regra_termo']:
            continue
        
        # Verificar regra de coordenação
        if tem_fumcad or tem_fmid:
            if tem_fumcad and 'FUMCAD' not in regra['regra_coordenacao']:
                continue
            if tem_fmid and 'FMID' not in regra['regra_coordenacao']:
                continue
        else:
            # Se não tem FUMCAD nem FMID, preferir legislação sem essas coordenações
            if regra['regra_coordenacao']:
                # Verificar se há outra opção sem coordenação
                outras_opcoes = [
                    r for r in REGRAS_LEGISLACAO 
                    if data_inicio_str >= r['inicio'] and data_inicio_str <= r['termino']
                    and not r['regra_coordenacao']
                    and any(t in numero_termo_upper for t in r['regra_termo'])
                ]
                if outras_opcoes:
                    continue
        
        portaria_selecionada = regra['lei']
        break
    
    return portaria_selecionada


def verificar_transicao(numero_termo, data_inicio, data_termino):
    """
    Verifica se o projeto é uma transição entre portarias
    
    Transição = 1 quando:
    - Início está em uma portaria (121 ou 140) E
    - Término está em outra portaria (021 ou 090) E
    - São regimentos similares
    
    Regimentos similares:
    - 121 → 021 (ambos sem coordenação específica, TFM/TCL)
    - 140 → 090 (ambos com FUMCAD/FMID, TFM/TCL)
    """
    if not data_inicio or not data_termino:
        return 0
    
    # Converter datas para string YYYY-MM-DD
    if isinstance(data_inicio, datetime):
        data_inicio_str = data_inicio.strftime('%Y-%m-%d')
    else:
        data_inicio_str = str(data_inicio)
    
    if isinstance(data_termino, datetime):
        data_termino_str = data_termino.strftime('%Y-%m-%d')
    else:
        data_termino_str = str(data_termino)
    
    # Determinar portaria do início e do término
    portaria_inicio = determinar_portaria(numero_termo, data_inicio)
    portaria_termino = determinar_portaria(numero_termo, data_termino)
    
    # Verificar se são portarias diferentes
    if not portaria_inicio or not portaria_termino:
        return 0
    
    if portaria_inicio == portaria_termino:
        return 0
    
    # Verificar transições válidas (121→021 ou 140→090)
    transicoes_validas = [
        ('Portaria nº 121/SMDHC/2019', 'Portaria nº 021/SMDHC/2023'),
        ('Portaria nº 140/SMDHC/2019', 'Portaria nº 090/SMDHC/2023')
    ]
    
    if (portaria_inicio, portaria_termino) in transicoes_validas:
        return 1
    
    return 0


def atualizar_parcerias():
    """
    Atualiza as colunas portaria e transicao na tabela Parcerias
    """
    conn = None
    try:
        print("=" * 80)
        print("  ATUALIZAÇÃO DE PORTARIAS E TRANSIÇÕES")
        print("=" * 80)
        print()
        
        # Conectar ao banco
        print("[INFO] Conectando ao banco de dados...")
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Buscar todas as parcerias com dados necessários
        print("[INFO] Buscando parcerias do banco de dados...")
        cur.execute("""
            SELECT numero_termo, inicio, final, portaria, transicao
            FROM Parcerias
            WHERE inicio IS NOT NULL
            ORDER BY numero_termo
        """)
        parcerias = cur.fetchall()
        
        print(f"[INFO] Total de parcerias encontradas: {len(parcerias)}")
        print()
        
        # Contadores
        total = len(parcerias)
        atualizadas = 0
        portarias_atualizadas = 0
        transicoes_encontradas = 0
        sem_mudanca = 0
        erros = 0
        
        print("[INFO] Processando parcerias...")
        print("-" * 80)
        
        for idx, parceria in enumerate(parcerias, 1):
            try:
                numero_termo = parceria['numero_termo']
                data_inicio = parceria['inicio']
                data_termino = parceria['final']
                portaria_atual = parceria['portaria']
                transicao_atual = parceria['transicao']
                
                # Mostrar progresso a cada 100 registros
                if idx % 100 == 0:
                    print(f"[PROGRESSO] {idx}/{total} parcerias processadas...")
                
                # Determinar portaria correta
                portaria_nova = determinar_portaria(numero_termo, data_inicio)
                
                # Verificar se é transição
                transicao_nova = verificar_transicao(numero_termo, data_inicio, data_termino)
                
                # Verificar se precisa atualizar
                precisa_atualizar_portaria = (
                    portaria_nova and 
                    (not portaria_atual or portaria_atual != portaria_nova or str(portaria_atual) == 'nan')
                )
                
                precisa_atualizar_transicao = (
                    transicao_atual is None or 
                    transicao_atual != transicao_nova
                )
                
                if precisa_atualizar_portaria or precisa_atualizar_transicao:
                    # Atualizar no banco
                    cur.execute("""
                        UPDATE Parcerias
                        SET portaria = %s,
                            transicao = %s
                        WHERE numero_termo = %s
                    """, (portaria_nova, transicao_nova, numero_termo))
                    
                    atualizadas += 1
                    
                    if precisa_atualizar_portaria:
                        portarias_atualizadas += 1
                        print(f"✓ {numero_termo}")
                        print(f"  Portaria: '{portaria_atual}' → '{portaria_nova}'")
                    
                    if transicao_nova == 1:
                        transicoes_encontradas += 1
                        if precisa_atualizar_transicao:
                            print(f"  🔄 Transição detectada!")
                else:
                    sem_mudanca += 1
                
            except Exception as e:
                erros += 1
                print(f"❌ Erro ao processar parceria {numero_termo}: {str(e)}")
        
        # Commit das alterações
        print()
        print("[INFO] Salvando alterações no banco de dados...")
        conn.commit()
        cur.close()
        
        # Resumo
        print()
        print("=" * 80)
        print("  RESUMO DA ATUALIZAÇÃO")
        print("=" * 80)
        print(f"Total de parcerias processadas:    {total}")
        print(f"Parcerias atualizadas:              {atualizadas}")
        print(f"  - Portarias atualizadas:          {portarias_atualizadas}")
        print(f"  - Transições identificadas:       {transicoes_encontradas}")
        print(f"Parcerias sem mudança:              {sem_mudanca}")
        print(f"Erros:                              {erros}")
        print("=" * 80)
        
        if erros == 0:
            print()
            print("✅ Atualização concluída com sucesso!")
        else:
            print()
            print("⚠️  Atualização concluída com alguns erros. Verifique os logs acima.")
        
    except Exception as e:
        print(f"\n❌ ERRO CRÍTICO: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        if conn:
            conn.close()
            print("\n[INFO] Conexão com banco de dados fechada.")


if __name__ == '__main__':
    atualizar_parcerias()

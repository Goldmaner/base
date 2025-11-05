"""
Sistema simplificado de substituição de variáveis em textos automáticos
Apenas variáveis simples, sem funções complexas
"""

import re
import html
from db import get_cursor


# Mapeamento de coordenações para setores SEI
# Inclui FUMCAD e FMID que são fundos (não estão no banco de dados)
MAPA_COORDENACOES_SETOR = {
    'DP': 'SMDHC/DP',
    'CPCA': 'SMDHC/CPDDH/CPCA',
    'CPIR': 'SMDHC/CPDDH/CPIR',
    'CPJ': 'SMDHC/CPDDH/CPJ',
    'CPLGBTI': 'SMDHC/CPDDH/CPLGBTI',
    'CPPI': 'SMDHC/CPDDH/CPPI',
    'CPM': 'SMDHC/CPDDH/CPM',
    'CPDDH': 'SMDHC/CPDDH',
    'COSAN': 'SMDHC/SESANA/COSAN',
    'COPIND': 'SMDHC/CPDDH/COPIND',
    'ODH': 'SMDHC/CPDDH/ODH',
    'DPS': 'SMDHC/CPDDH/DPS',
    'CPD': 'SMDHC/CPDDH/CPD',
    'Eventos': 'SMDHC/GAB/AEV',
    'CAF': 'SMDHC/CAF',
    'EGRESSOS': 'SMDHC/CPDDH/CPEF',
    'DEDH': 'SMDHC/CPDDH/CEDH',
    'CPIPTD': 'SMDHC/CPDDH/CPIPTD',
    'CPPSR': 'SMDHC/CPDDH/CPPSR',
    'COSAN/RCE': 'SMDHC/SESANA/COSAN/RCE',
    'SESANA': 'SMDHC/SESANA/COSAN/EMENDAS',
    # Fundos (não são coordenações, mas aparecem em termos)
    'FUMCAD': 'SMDHC/CPDDH/CPCA/FUMCAD',
    'FMID': 'SMDHC/CPDDH/CPPI'
}


def criar_tabela_informado_usuario(osc_nome):
    """
    Cria uma tabela HTML com termos de parceria que têm prestação de contas do DP
    
    Parâmetros:
    - osc_nome: Nome da OSC para buscar as parcerias
    
    Retorna:
    - String HTML com a tabela formatada
    """
    try:
        from datetime import datetime, timedelta
        
        # Query para buscar termos e todas as prestações
        query = """
            SELECT DISTINCT 
                p.numero_termo,
                p.sei_pc,
                p.projeto,
                pa.tipo_prestacao,
                pa.vigencia_inicial,
                pa.vigencia_final,
                pa.entregue
            FROM public.parcerias p
            INNER JOIN public.parcerias_analises pa ON p.numero_termo = pa.numero_termo
            WHERE p.osc = %s
              AND pa.responsabilidade_analise = 1
            ORDER BY p.numero_termo, pa.vigencia_final
        """
        
        cur = get_cursor()
        if cur is None:
            return '<p style="color: red;">Erro ao conectar com banco de dados</p>'
        
        cur.execute(query, (osc_nome,))
        resultados = cur.fetchall()
        cur.close()
        
        if not resultados or len(resultados) == 0:
            return '<p><em>Nenhum termo encontrado com prestação de contas do Departamento de Parcerias.</em></p>'
        
        # Agrupar por termo
        termos_dict = {}
        for row in resultados:
            numero_termo = row.get('numero_termo', '-')
            
            if numero_termo not in termos_dict:
                termos_dict[numero_termo] = {
                    'sei_pc': row.get('sei_pc', '-'),
                    'projeto': row.get('projeto', '-'),
                    'prestacoes': []
                }
            
            # Adicionar prestação
            termos_dict[numero_termo]['prestacoes'].append({
                'tipo_prestacao': row.get('tipo_prestacao', ''),
                'vigencia_inicial': row.get('vigencia_inicial'),
                'vigencia_final': row.get('vigencia_final'),
                'entregue': row.get('entregue')
            })
        
        # Construir tabela HTML no formato SEI
        html_tabela = '''
        <table border="1" cellpadding="1" cellspacing="1" style="border-collapse:collapse; border-color:#0e7a8b; margin-left:auto; margin-right:auto; width:80%; font-family:Calibri; font-size:12pt;">
            <thead>
                <tr style="color: #fff;">
                    <td class="dark-mode-color-black dark-mode-color-white" style="background-color: #0e7a8b; text-align:center; vertical-align:middle;">
                        <p class="Texto_Centralizado"><strong>Termo de Fomento</strong></p>
                    </td>
                    <td class="dark-mode-color-black dark-mode-color-white" style="background-color: #0e7a8b; text-align:center; vertical-align:middle;">
                        <p class="Texto_Centralizado"><strong>Processo SEI</strong></p>
                    </td>
                    <td class="dark-mode-color-black dark-mode-color-white" style="background-color: #0e7a8b; text-align:center; vertical-align:middle;">
                        <p class="Texto_Centralizado"><strong>Projeto</strong></p>
                    </td>
                    <td class="dark-mode-color-black dark-mode-color-white" style="background-color: #0e7a8b; text-align:center; vertical-align:middle;">
                        <p class="Texto_Centralizado"><strong>Situação</strong></p>
                    </td>
                </tr>
            </thead>
            <tbody>
        '''
        
        hoje = datetime.now().date()
        
        for numero_termo, dados in sorted(termos_dict.items()):
            sei_pc = dados['sei_pc']
            projeto = dados['projeto']
            prestacoes = dados['prestacoes']
            
            # Calcular situação
            atrasadas = []
            todas_entregues = True
            
            for prest in prestacoes:
                entregue = prest['entregue']
                tipo_prest = prest['tipo_prestacao']
                vig_final = prest['vigencia_final']
                vig_inicial = prest['vigencia_inicial']
                
                if not entregue:
                    todas_entregues = False
                    
                    # Calcular se está atrasado (lógica do calcular_regularidade)
                    if vig_final:
                        if tipo_prest == 'Final':
                            prazo = vig_final + timedelta(days=45)
                            if prazo <= hoje:
                                atrasadas.append({
                                    'tipo': tipo_prest,
                                    'vig_inicial': vig_inicial,
                                    'vig_final': vig_final
                                })
                        elif tipo_prest == 'Semestral':
                            prazo = vig_final + timedelta(days=10)
                            if prazo <= hoje:
                                atrasadas.append({
                                    'tipo': tipo_prest,
                                    'vig_inicial': vig_inicial,
                                    'vig_final': vig_final
                                })
            
            # Montar texto da situação
            if todas_entregues:
                situacao_texto = 'Sem pendências'
            elif len(atrasadas) == 0:
                situacao_texto = 'Pendente (no prazo)'
            else:
                # Listar prestações atrasadas de forma mais econômica
                situacao_html = '<p style="margin:0; text-align:center; word-wrap:normal;"><strong>Prestações de contas em atraso:</strong></p>'
                for atr in atrasadas:
                    vig_ini_fmt = atr['vig_inicial'].strftime('%d/%m/%Y') if atr['vig_inicial'] else '-'
                    vig_fin_fmt = atr['vig_final'].strftime('%d/%m/%Y') if atr['vig_final'] else '-'
                    situacao_html += f'<p style="margin:0; text-align:center; word-wrap:normal;">{atr["tipo"]} referente ao período de {vig_ini_fmt} a {vig_fin_fmt}</p>'
                situacao_texto = situacao_html
            
            html_tabela += f'''
                <tr>
                    <td style="text-align:center; vertical-align:middle;">
                        <p class="Tabela_Texto_Centralizado">{numero_termo}</p>
                    </td>
                    <td style="text-align:center; vertical-align:middle;">
                        <p class="Tabela_Texto_Centralizado">{sei_pc}</p>
                    </td>
                    <td style="text-align:center; vertical-align:middle;">
                        <p class="Tabela_Texto_Centralizado">{projeto}</p>
                    </td>
                    <td style="text-align:center; vertical-align:middle;">
                        {'<p class="Tabela_Texto_Centralizado">' + situacao_texto + '</p>' if isinstance(situacao_texto, str) and not situacao_texto.startswith('<') else situacao_texto}
                    </td>
                </tr>
            '''
        
        html_tabela += '''
            </tbody>
        </table>
        '''
        
        return html_tabela
        
    except Exception as e:
        print(f"[ERRO criar_tabela_informado_usuario] {e}")
        import traceback
        traceback.print_exc()
        return f'<p style="color: red;">Erro ao gerar tabela: {str(e)}</p>'


def criar_tabela_pre2023(osc_nome):
    """
    Cria uma tabela HTML completa (com coluna Situação calculada) com termos pré-2023
    que possuem prestações de contas com responsabilidade DP (1)
    
    A coluna Situação é calculada dinamicamente verificando:
    - Se todas as prestações DP foram entregues → "Sem pendências"
    - Se há prestações não entregues no prazo → "Pendente (no prazo)"
    - Se há prestações atrasadas → Lista as prestações em atraso
    
    Parâmetros:
    - osc_nome: Nome da OSC para buscar as parcerias
    
    Retorna:
    - String HTML com a tabela formatada (4 colunas)
    """
    try:
        from datetime import datetime, timedelta
        
        # Query para buscar termos e suas prestações com responsabilidade DP (1)
        query = """
            SELECT 
                p.numero_termo,
                p.sei_pc,
                p.projeto,
                pa.tipo_prestacao,
                pa.vigencia_inicial,
                pa.vigencia_final,
                pa.entregue
            FROM public.parcerias p
            INNER JOIN public.parcerias_analises pa ON p.numero_termo = pa.numero_termo
            WHERE p.osc = %s
              AND pa.responsabilidade_analise = 1
            ORDER BY p.numero_termo, pa.vigencia_final
        """
        
        cur = get_cursor()
        if cur is None:
            return '<p style="color: red;">Erro ao conectar com banco de dados</p>'
        
        cur.execute(query, (osc_nome,))
        resultados = cur.fetchall()
        cur.close()
        
        if not resultados or len(resultados) == 0:
            return ''  # Retorna vazio se não há termos pré-2023
        
        # Agrupar por termo
        from collections import defaultdict
        termos_dict = defaultdict(lambda: {'sei_pc': '', 'projeto': '', 'prestacoes': []})
        
        for row in resultados:
            numero_termo = row['numero_termo']
            termos_dict[numero_termo]['sei_pc'] = row['sei_pc']
            termos_dict[numero_termo]['projeto'] = row['projeto']
            termos_dict[numero_termo]['prestacoes'].append({
                'tipo_prestacao': row['tipo_prestacao'],
                'vigencia_inicial': row['vigencia_inicial'],
                'vigencia_final': row['vigencia_final'],
                'entregue': row['entregue']
            })
        
        # Construir tabela HTML no formato SEI (4 colunas)
        html_tabela = '''
        <table border="1" cellpadding="1" cellspacing="1" style="border-collapse:collapse; border-color:#0e7a8b; margin-left:auto; margin-right:auto; width:80%; font-family:Calibri; font-size:12pt;">
            <thead>
                <tr style="color: #fff;">
                    <td class="dark-mode-color-black dark-mode-color-white" style="background-color: #0e7a8b; text-align:center; vertical-align:middle;">
                        <p class="Texto_Centralizado"><strong>Número do Termo</strong></p>
                    </td>
                    <td class="dark-mode-color-black dark-mode-color-white" style="background-color: #0e7a8b; text-align:center; vertical-align:middle;">
                        <p class="Texto_Centralizado"><strong>Processo SEI PC</strong></p>
                    </td>
                    <td class="dark-mode-color-black dark-mode-color-white" style="background-color: #0e7a8b; text-align:center; vertical-align:middle;">
                        <p class="Texto_Centralizado"><strong>Nome do Projeto</strong></p>
                    </td>
                    <td class="dark-mode-color-black dark-mode-color-white" style="background-color: #0e7a8b; text-align:center; vertical-align:middle;">
                        <p class="Texto_Centralizado"><strong>Situação</strong></p>
                    </td>
                </tr>
            </thead>
            <tbody>
        '''
        
        hoje = datetime.now().date()
        
        for numero_termo, dados in sorted(termos_dict.items()):
            sei_pc = dados['sei_pc']
            projeto = dados['projeto']
            prestacoes = dados['prestacoes']
            
            # Calcular situação (mesma lógica de criar_tabela_informado_usuario)
            atrasadas = []
            todas_entregues = True
            
            for prest in prestacoes:
                entregue = prest['entregue']
                tipo_prest = prest['tipo_prestacao']
                vig_final = prest['vigencia_final']
                vig_inicial = prest['vigencia_inicial']
                
                if not entregue:
                    todas_entregues = False
                    
                    # Calcular se está atrasado
                    if vig_final:
                        if tipo_prest == 'Final':
                            prazo = vig_final + timedelta(days=45)
                            if prazo <= hoje:
                                atrasadas.append({
                                    'tipo': tipo_prest,
                                    'vig_inicial': vig_inicial,
                                    'vig_final': vig_final
                                })
                        elif tipo_prest == 'Semestral':
                            prazo = vig_final + timedelta(days=10)
                            if prazo <= hoje:
                                atrasadas.append({
                                    'tipo': tipo_prest,
                                    'vig_inicial': vig_inicial,
                                    'vig_final': vig_final
                                })
            
            # Montar texto da situação
            if todas_entregues:
                situacao_texto = 'Sem pendências'
            elif len(atrasadas) == 0:
                situacao_texto = 'Pendente (no prazo)'
            else:
                # Listar prestações atrasadas
                situacao_html = '<p style="margin:0; text-align:center; word-wrap:normal;"><strong>Prestações de contas em atraso:</strong></p>'
                for atr in atrasadas:
                    vig_ini_fmt = atr['vig_inicial'].strftime('%d/%m/%Y') if atr['vig_inicial'] else '-'
                    vig_fin_fmt = atr['vig_final'].strftime('%d/%m/%Y') if atr['vig_final'] else '-'
                    situacao_html += f'<p style="margin:0; text-align:center; word-wrap:normal;">{atr["tipo"]} referente ao período de {vig_ini_fmt} a {vig_fin_fmt}</p>'
                situacao_texto = situacao_html
            
            html_tabela += f'''
                <tr>
                    <td style="text-align:center; vertical-align:middle;">
                        <p class="Tabela_Texto_Centralizado">{numero_termo}</p>
                    </td>
                    <td style="text-align:center; vertical-align:middle;">
                        <p class="Tabela_Texto_Centralizado">{sei_pc}</p>
                    </td>
                    <td style="text-align:center; vertical-align:middle;">
                        <p class="Tabela_Texto_Centralizado">{projeto}</p>
                    </td>
                    <td style="text-align:center; vertical-align:middle;">
                        {'<p class="Tabela_Texto_Centralizado">' + situacao_texto + '</p>' if isinstance(situacao_texto, str) and not situacao_texto.startswith('<') else situacao_texto}
                    </td>
                </tr>
            '''
        
        html_tabela += '''
            </tbody>
        </table>
        '''
        
        return html_tabela
        
    except Exception as e:
        print(f"[ERRO criar_tabela_pre2023] {e}")
        import traceback
        traceback.print_exc()
        
        # Fazer rollback da transação se houver erro
        try:
            cur = get_cursor()
            if cur and cur.connection:
                cur.connection.rollback()
                cur.close()
        except:
            pass
        
        return f'<p style="color: red;">Erro ao gerar tabela pré-2023: {str(e)}</p>'


def criar_tabela_pos2023(osc_nome, coordenacao_sigla):
    """
    Cria uma tabela HTML simplificada (sem coluna Situação) com termos pós-2023
    da coordenação específica (responsabilidade 2 ou 3)
    
    Parâmetros:
    - osc_nome: Nome da OSC para buscar as parcerias
    - coordenacao_sigla: Sigla da coordenação (ex: 'CPJ', 'CPPI')
    
    Retorna:
    - String HTML com a tabela formatada (apenas 3 colunas)
    """
    try:
        # Query para buscar termos com responsabilidade Compartilhado (2) ou Pessoa Gestora (3)
        # Filtrando por coordenação via padrão no numero_termo
        query = """
            SELECT DISTINCT 
                p.numero_termo,
                p.sei_pc,
                p.projeto
            FROM public.parcerias p
            INNER JOIN public.parcerias_analises pa ON p.numero_termo = pa.numero_termo
            WHERE p.osc = %s
              AND pa.responsabilidade_analise IN (2, 3)
              AND p.numero_termo LIKE %s
            ORDER BY p.numero_termo
        """
        
        # Padrão para filtrar por coordenação (ex: '%/CPJ')
        padrao_coord = f'%/{coordenacao_sigla}'
        
        cur = get_cursor()
        if cur is None:
            return '<p style="color: red;">Erro ao conectar com banco de dados</p>'
        
        cur.execute(query, (osc_nome, padrao_coord))
        resultados = cur.fetchall()
        cur.close()
        
        if not resultados or len(resultados) == 0:
            return ''  # Retorna vazio se não há termos desta coordenação
        
        # Construir tabela HTML no formato SEI (apenas 3 colunas)
        html_tabela = '''
        <table border="1" cellpadding="1" cellspacing="1" style="border-collapse:collapse; border-color:#0e7a8b; margin-left:auto; margin-right:auto; width:80%; font-family:Calibri; font-size:12pt;">
            <thead>
                <tr style="color: #fff;">
                    <td class="dark-mode-color-black dark-mode-color-white" style="background-color: #0e7a8b; text-align:center; vertical-align:middle;">
                        <p class="Texto_Centralizado"><strong>Número do Termo</strong></p>
                    </td>
                    <td class="dark-mode-color-black dark-mode-color-white" style="background-color: #0e7a8b; text-align:center; vertical-align:middle;">
                        <p class="Texto_Centralizado"><strong>Processo SEI PC</strong></p>
                    </td>
                    <td class="dark-mode-color-black dark-mode-color-white" style="background-color: #0e7a8b; text-align:center; vertical-align:middle;">
                        <p class="Texto_Centralizado"><strong>Nome do Projeto</strong></p>
                    </td>
                </tr>
            </thead>
            <tbody>
        '''
        
        for row in resultados:
            numero_termo = row.get('numero_termo', '-')
            sei_pc = row.get('sei_pc', '-')
            projeto = row.get('projeto', '-')
            
            html_tabela += f'''
                <tr>
                    <td style="text-align:center; vertical-align:middle;">
                        <p class="Tabela_Texto_Centralizado">{numero_termo}</p>
                    </td>
                    <td style="text-align:center; vertical-align:middle;">
                        <p class="Tabela_Texto_Centralizado">{sei_pc}</p>
                    </td>
                    <td style="text-align:center; vertical-align:middle;">
                        <p class="Tabela_Texto_Centralizado">{projeto}</p>
                    </td>
                </tr>
            '''
        
        html_tabela += '''
            </tbody>
        </table>
        '''
        
        return html_tabela
        
    except Exception as e:
        print(f"[ERRO criar_tabela_pos2023] {e}")
        import traceback
        traceback.print_exc()
        
        # Fazer rollback da transação se houver erro
        try:
            cur = get_cursor()
            if cur and cur.connection:
                cur.connection.rollback()
                cur.close()
        except:
            pass
        
        return f'<p style="color: red;">Erro ao gerar tabela pós-2023: {str(e)}</p>'


def identificar_coordenacoes(osc_nome):
    """
    Identifica todas as coordenações distintas que possuem termos pós-2023
    para uma determinada OSC
    
    Parâmetros:
    - osc_nome: Nome da OSC
    
    Retorna:
    - Lista de siglas de coordenações (ex: ['CPJ', 'CPPI'])
    """
    try:
        query = """
            SELECT DISTINCT p.numero_termo
            FROM public.parcerias p
            INNER JOIN public.parcerias_analises pa ON p.numero_termo = pa.numero_termo
            WHERE p.osc = %s
              AND pa.responsabilidade_analise IN (2, 3)
            ORDER BY p.numero_termo
        """
        
        cur = get_cursor()
        if cur is None:
            return []
        
        cur.execute(query, (osc_nome,))
        resultados = cur.fetchall()
        cur.close()
        
        # Extrair sigla da coordenação (parte após última barra)
        coordenacoes = set()
        for row in resultados:
            numero_termo = row.get('numero_termo', '')
            # Ex: ACP/001/2024/SMDHC/CPJ -> CPJ
            if '/' in numero_termo:
                sigla = numero_termo.split('/')[-1]
                coordenacoes.add(sigla)
        
        return sorted(list(coordenacoes))
        
    except Exception as e:
        print(f"[ERRO identificar_coordenacoes] {e}")
        return []


def obter_setor_sei(coordenacao_sigla):
    """
    Busca o setor_sei correspondente a uma sigla de coordenação
    usando o dicionário MAPA_COORDENACOES_SETOR
    
    Parâmetros:
    - coordenacao_sigla: Sigla da coordenação (ex: 'CPJ', 'FUMCAD')
    
    Retorna:
    - String com setor SEI (ex: 'SMDHC/CPDDH/CPJ') ou fallback se não encontrar
    """
    try:
        # Buscar no dicionário (case-sensitive)
        setor = MAPA_COORDENACOES_SETOR.get(coordenacao_sigla)
        
        if setor:
            return setor
        
        # Fallback: tentar case-insensitive
        for key, value in MAPA_COORDENACOES_SETOR.items():
            if key.upper() == coordenacao_sigla.upper():
                return value
        
        # Se não encontrar, retornar placeholder
        return 'INSERIR COORDENAÇÃO A SER ENCAMINHADA'
        
    except Exception as e:
        print(f"[ERRO obter_setor_sei] {e}")
        return 'INSERIR COORDENAÇÃO A SER ENCAMINHADA'


def verificar_osc_existe(osc_nome):
    """
    Verifica se uma OSC existe na tabela public.parcerias
    
    Parâmetros:
    - osc_nome: Nome da OSC
    
    Retorna:
    - True se existe, False caso contrário
    """
    try:
        query = """
            SELECT COUNT(*) as total
            FROM public.parcerias
            WHERE osc = %s
            LIMIT 1
        """
        
        cur = get_cursor()
        if cur is None:
            return False
        
        cur.execute(query, (osc_nome,))
        resultado = cur.fetchone()
        cur.close()
        
        return resultado['total'] > 0
        
    except Exception as e:
        print(f"[ERRO verificar_osc_existe] {e}")
        return False


def verificar_osc_tem_pos2023(osc_nome):
    """
    Verifica se uma OSC possui termos pós-2023 (responsabilidade 2 ou 3)
    
    Parâmetros:
    - osc_nome: Nome da OSC
    
    Retorna:
    - True se tem termos pós-2023, False caso contrário
    """
    try:
        query = """
            SELECT COUNT(*) as total
            FROM public.parcerias p
            INNER JOIN public.parcerias_analises pa ON p.numero_termo = pa.numero_termo
            WHERE p.osc = %s
              AND pa.responsabilidade_analise IN (2, 3)
            LIMIT 1
        """
        
        cur = get_cursor()
        if cur is None:
            return False
        
        cur.execute(query, (osc_nome,))
        resultado = cur.fetchone()
        cur.close()
        
        return resultado['total'] > 0
        
    except Exception as e:
        print(f"[ERRO verificar_osc_tem_pos2023] {e}")
        return False


def verificar_responsabilidades_mistas(osc_nome):
    """
    Verifica se uma OSC possui termos com responsabilidades mistas:
    - Responsabilidade 1 (DP) E
    - Responsabilidade 2 ou 3 (Compartilhada/Pessoa Gestora)
    
    Parâmetros:
    - osc_nome: Nome da OSC
    
    Retorna:
    - Dict com {'tem_dp': bool, 'tem_pos2023': bool, 'misto': bool}
    """
    try:
        query = """
            SELECT 
                COUNT(CASE WHEN pa.responsabilidade_analise = 1 THEN 1 END) as total_dp,
                COUNT(CASE WHEN pa.responsabilidade_analise IN (2, 3) THEN 1 END) as total_pos2023
            FROM public.parcerias p
            INNER JOIN public.parcerias_analises pa ON p.numero_termo = pa.numero_termo
            WHERE p.osc = %s
        """
        
        cur = get_cursor()
        if cur is None:
            return {'tem_dp': False, 'tem_pos2023': False, 'misto': False}
        
        cur.execute(query, (osc_nome,))
        resultado = cur.fetchone()
        cur.close()
        
        tem_dp = resultado['total_dp'] > 0
        tem_pos2023 = resultado['total_pos2023'] > 0
        misto = tem_dp and tem_pos2023
        
        return {
            'tem_dp': tem_dp,
            'tem_pos2023': tem_pos2023,
            'misto': misto
        }
        
    except Exception as e:
        print(f"[ERRO verificar_responsabilidades_mistas] {e}")
        return {'tem_dp': False, 'tem_pos2023': False, 'misto': False}


def gerar_encaminhamentos_pos2023(texto_base_modelo, variaveis):
    """
    Gera múltiplos encaminhamentos para o caso pós-2023,
    um para cada coordenação identificada
    
    Parâmetros:
    - texto_base_modelo: Texto modelo original
    - variaveis: Dicionário com variáveis base (sei, osc, cnpj, etc)
    
    Retorna:
    - String HTML com todos os encaminhamentos concatenados
    """
    try:
        osc_nome = variaveis.get('osc_informado_usuario', variaveis.get('nome_osc', ''))
        
        if not osc_nome:
            return '<p style="color: red;">OSC não informada para gerar encaminhamentos</p>'
        
        # Identificar coordenações
        coordenacoes = identificar_coordenacoes(osc_nome)
        
        if not coordenacoes or len(coordenacoes) == 0:
            return '<p><em>Nenhum termo pós-2023 encontrado para esta OSC.</em></p>'
        
        # Gerar um encaminhamento para cada coordenação
        encaminhamentos_html = []
        
        for coord_sigla in coordenacoes:
            # Buscar setor SEI da coordenação
            setor_sei = obter_setor_sei(coord_sigla)
            
            if not setor_sei:
                setor_sei = f'[Setor não encontrado para {coord_sigla}]'
            
            # Preparar variáveis para esta coordenação
            vars_coord = variaveis.copy()
            vars_coord['coordenacao_informado_usuario'] = setor_sei
            vars_coord['coordenacao_sigla'] = coord_sigla
            
            # Processar texto para esta coordenação
            texto_processado = processar_texto_automatico(texto_base_modelo, vars_coord)
            
            encaminhamentos_html.append(texto_processado)
        
        # Concatenar todos os encaminhamentos com separador
        resultado_final = '<hr style="margin: 30px 0; border: 2px solid #0e7a8b;">'.join(encaminhamentos_html)
        
        return resultado_final
        
    except Exception as e:
        print(f"[ERRO gerar_encaminhamentos_pos2023] {e}")
        import traceback
        traceback.print_exc()
        return f'<p style="color: red;">Erro ao gerar encaminhamentos: {str(e)}</p>'


def gerar_texto_misto(variaveis):
    """
    Gera interface com dropdown para OSC com responsabilidades mistas (DP + Pós-2023).
    
    Esta função é chamada quando uma OSC possui TANTO termos com responsabilidade DP (1)
    QUANTO termos com responsabilidade Compartilhada/Pessoa Gestora (2 ou 3).
    
    Importante: Termos podem ser mistos (ter prestações DP E pós-2023 simultaneamente),
    então as tabelas consideram o nível de prestação, não apenas o termo.
    
    Gera:
    1. Dropdown para selecionar o encaminhamento desejado
    2. Modelo pré-2023 (DP) com criar_tabela_pre2023() - termos que têm prestações DP
    3. Modelo(s) pós-2023 (uma ou mais coordenações) com criar_tabela_pos2023()
    
    Parâmetros:
    - variaveis: Dicionário com variáveis base (sei, osc, cnpj, etc)
    
    Retorna:
    - String HTML com dropdown + todos os encaminhamentos (inicialmente ocultos)
    """
    try:
        osc_nome = variaveis.get('osc_informado_usuario', variaveis.get('nome_osc', ''))
        
        if not osc_nome:
            return '<p style="color: red;">OSC não informada para gerar texto misto</p>'
        
        # Buscar modelos de texto
        modelo_pre = obter_modelo_texto("Pesquisa de Parcerias: Parcerias pré-2023")
        modelo_pos = obter_modelo_texto("Pesquisa de Parcerias: Parcerias pós-2023")
        
        if not modelo_pre or not modelo_pos:
            return '<p style="color: red;">Modelos de texto não encontrados no banco de dados</p>'
        
        # Identificar coordenações pós-2023
        coordenacoes = identificar_coordenacoes(osc_nome)
        
        # Construir lista de opções do dropdown
        opcoes_dropdown = ['<option value="">Selecione um encaminhamento...</option>']
        opcoes_dropdown.append('<option value="encaminhamento_pre">SMDHC/DP/DGP (Parcerias pré-2023)</option>')
        
        for coord in coordenacoes:
            setor = obter_setor_sei(coord)
            opcoes_dropdown.append(f'<option value="encaminhamento_{coord}">{setor} (Parcerias pós-2023)</option>')
        
        opcoes_html = '\n'.join(opcoes_dropdown)
        
        # Aviso + Dropdown
        interface_html = f'''
        <div style="background-color: #fff3cd; border: 2px solid #ffc107; border-radius: 8px; padding: 20px; margin-bottom: 30px; font-family: Calibri, sans-serif;">
            <h3 style="color: #856404; margin-top: 0;">
                <span style="font-size: 24px;">⚠️</span> ATENÇÃO: Esta OSC possui parcerias com responsabilidades mistas
            </h3>
            <p style="color: #856404; margin: 10px 0;">
                Esta organização possui tanto parcerias com responsabilidade do <strong>Departamento de Parcerias (DP)</strong> 
                quanto parcerias com responsabilidade de <strong>Pessoa Gestora/Compartilhada</strong>.
            </p>
            <p style="color: #856404; margin: 10px 0;">
                <strong>Observação importante:</strong> Alguns termos podem aparecer em múltiplas listagens, 
                pois possuem prestações de contas com diferentes responsabilidades ao longo do tempo.
            </p>
            <p style="color: #856404; margin: 15px 0 10px 0; font-weight: bold;">
                Selecione abaixo qual encaminhamento deseja visualizar:
            </p>
            <select id="dropdown_encaminhamento" onchange="mostrarEncaminhamento(this.value)" 
                    style="width: 100%; padding: 12px; font-size: 14px; border: 2px solid #ffc107; border-radius: 5px; background-color: white; font-family: Calibri, sans-serif;">
                {opcoes_html}
            </select>
        </div>
        
        <script>
        function mostrarEncaminhamento(valor) {{
            // Ocultar todos os encaminhamentos
            var encaminhamentos = document.querySelectorAll('[id^="encaminhamento_"]');
            encaminhamentos.forEach(function(elem) {{
                elem.style.display = 'none';
            }});
            
            // Mostrar apenas o selecionado
            if (valor) {{
                var selecionado = document.getElementById(valor);
                if (selecionado) {{
                    selecionado.style.display = 'block';
                }}
            }}
        }}
        </script>
        '''
        
        # Gerar encaminhamento pré-2023 (DP) - OCULTO inicialmente
        texto_pre = processar_texto_automatico(modelo_pre['modelo_texto'], variaveis)
        encaminhamento_pre = f'''
        <div id="encaminhamento_pre" style="display: none;">
            <div style="background-color: #0e7a8b; color: white; padding: 15px; margin: 30px 0 20px 0; text-align: center; font-family: Calibri, sans-serif; font-size: 16px; font-weight: bold; border-radius: 5px;">
                ENCAMINHAMENTO - SMDHC/DP/DGP (Parcerias pré-2023)
            </div>
            {texto_pre}
        </div>
        '''
        
        # Gerar encaminhamentos pós-2023 - OCULTOS inicialmente
        encaminhamentos_pos = []
        for coord_sigla in coordenacoes:
            setor_sei = obter_setor_sei(coord_sigla)
            
            # Preparar variáveis para esta coordenação
            vars_coord = variaveis.copy()
            vars_coord['coordenacao_informado_usuario'] = setor_sei
            vars_coord['coordenacao_sigla'] = coord_sigla
            
            texto_pos = processar_texto_automatico(modelo_pos['modelo_texto'], vars_coord)
            
            encaminhamento_pos_html = f'''
            <div id="encaminhamento_{coord_sigla}" style="display: none;">
                <div style="background-color: #0e7a8b; color: white; padding: 15px; margin: 30px 0 20px 0; text-align: center; font-family: Calibri, sans-serif; font-size: 16px; font-weight: bold; border-radius: 5px;">
                    ENCAMINHAMENTO - {setor_sei} (Parcerias pós-2023)
                </div>
                {texto_pos}
            </div>
            '''
            encaminhamentos_pos.append(encaminhamento_pos_html)
        
        # Concatenar tudo
        resultado_final = interface_html + encaminhamento_pre + '\n'.join(encaminhamentos_pos)
        
        return resultado_final
        
    except Exception as e:
        print(f"[ERRO gerar_texto_misto] {e}")
        import traceback
        traceback.print_exc()
        return f'<p style="color: red;">Erro ao gerar texto misto: {str(e)}</p>'


def processar_texto_automatico(texto_modelo, variaveis):
    """
    Processa um texto modelo substituindo variáveis simples e funções especiais
    
    Formato: use palavras diretamente no texto (sem & ou outros marcadores)
    Exemplo: "SEI nº sei_informado_usuario" 
    
    Funções especiais:
    - criar_tabela_informado_usuario(cabecalho: col1; col2; col3) - cria tabela HTML com Situação (4 colunas)
    - criar_tabela_pre2023(cabecalho: col1; col2; col3) - cria tabela HTML pré-2023 com Situação (4 colunas)
    - criar_tabela_pos2023(cabecalho: col1; col2; col3) - cria tabela simplificada (3 colunas, sem Situação)
    
    Parâmetros:
    - texto_modelo: texto com variáveis como sei_informado_usuario, nome_osc, etc
    - variaveis: dicionário com valores {nome: valor}
    
    Variáveis disponíveis automaticamente:
    - sei_informado_usuario: SEI do formulário
    - osc_informado_usuario: Nome da OSC do formulário  
    - cnpj_informado_usuario: CNPJ informado (ou "não informado")
    - nome_emissor: Nome do emissor
    - numero_pesquisa: Número da pesquisa
    - coordenacao_informado_usuario: Setor SEI da coordenação (ex: SMDHC/CPDDH/CPJ)
    """
    # Decodificar entidades HTML (&nbsp; → espaço, &amp; → &, etc)
    texto_processado = html.unescape(texto_modelo)
    
    # Processar função criar_tabela_informado_usuario se existir (pré-2023 com Situação - LEGADO)
    padrao_tabela = r'criar_tabela_informado_usuario\s*\([^)]*\)'
    match_tabela = re.search(padrao_tabela, texto_processado)
    
    if match_tabela:
        osc_nome = variaveis.get('osc_informado_usuario', variaveis.get('nome_osc', ''))
        if osc_nome:
            tabela_html = criar_tabela_informado_usuario(osc_nome)
            texto_processado = re.sub(padrao_tabela, tabela_html, texto_processado)
        else:
            texto_processado = re.sub(padrao_tabela, '<p style="color: red;">OSC não informada</p>', texto_processado)
    
    # Processar função criar_tabela_pre2023 se existir (pré-2023 com Situação - NOVO)
    padrao_pre2023 = r'criar_tabela_pre2023\s*\([^)]*\)'
    match_pre2023 = re.search(padrao_pre2023, texto_processado)
    
    if match_pre2023:
        osc_nome = variaveis.get('osc_informado_usuario', variaveis.get('nome_osc', ''))
        if osc_nome:
            tabela_html = criar_tabela_pre2023(osc_nome)
            texto_processado = re.sub(padrao_pre2023, tabela_html, texto_processado)
        else:
            texto_processado = re.sub(padrao_pre2023, '<p style="color: red;">OSC não informada</p>', texto_processado)
    
    # Processar função criar_tabela_pos2023 se existir (pós-2023 sem Situação)
    padrao_pos2023 = r'criar_tabela_pos2023\s*\([^)]*\)'
    match_pos2023 = re.search(padrao_pos2023, texto_processado)
    
    if match_pos2023:
        osc_nome = variaveis.get('osc_informado_usuario', variaveis.get('nome_osc', ''))
        coordenacao_sigla = variaveis.get('coordenacao_sigla', '')
        
        if osc_nome and coordenacao_sigla:
            tabela_html = criar_tabela_pos2023(osc_nome, coordenacao_sigla)
            texto_processado = re.sub(padrao_pos2023, tabela_html, texto_processado)
        else:
            texto_processado = re.sub(padrao_pos2023, '<p style="color: red;">OSC ou coordenação não informada</p>', texto_processado)
    
    # Lista de todas as variáveis possíveis (ordem importa - mais específicas primeiro)
    variaveis_possiveis = [
        'coordenacao_informado_usuario',
        'COORDENACAO_INFORMADO_USUARIO',  # Versão maiúscula sem acento
        'COORDENAÇÃO_INFORMADO_USUARIO',  # Versão maiúscula COM ACENTO
        'sei_informado_usuario',
        'osc_informado_usuario', 
        'cnpj_informado_usuario',
        'nome_emissor',
        'numero_pesquisa',
        'nome_osc',  # Alias para osc_informado_usuario
        'sei_informado'  # Alias para sei_informado_usuario
    ]
    
    # Substituir cada variável encontrada no texto
    for var_nome in variaveis_possiveis:
        if var_nome in texto_processado:
            # Buscar valor (com fallback para aliases)
            if var_nome == 'nome_osc':
                valor = variaveis.get('osc_informado_usuario', variaveis.get('nome_osc', '[OSC não informada]'))
            elif var_nome == 'sei_informado':
                valor = variaveis.get('sei_informado_usuario', variaveis.get('sei_informado', '[SEI não informado]'))
            elif var_nome in ['COORDENACAO_INFORMADO_USUARIO', 'COORDENAÇÃO_INFORMADO_USUARIO']:
                # Buscar versão minúscula (ambas as variantes maiúsculas)
                valor = variaveis.get('coordenacao_informado_usuario', f'[{var_nome} não encontrado]')
            else:
                valor = variaveis.get(var_nome, f'[{var_nome} não encontrado]')
            
            # Substituir no texto
            texto_processado = texto_processado.replace(var_nome, str(valor))
    
    return texto_processado


def obter_modelo_texto(titulo_texto):
    """
    Busca um modelo de texto na tabela categoricas.c_modelo_textos
    
    Parâmetros:
    - titulo_texto: título do modelo a buscar
    
    Retorna:
    - Dicionário com {titulo_texto, modelo_texto} ou None se não encontrar
    """
    try:
        query = """
            SELECT titulo_texto, modelo_texto
            FROM categoricas.c_modelo_textos
            WHERE titulo_texto = %s
            LIMIT 1
        """
        
        cur = get_cursor()
        if cur is None:
            return None
        
        cur.execute(query, (titulo_texto,))
        resultado = cur.fetchone()
        cur.close()
        
        return resultado
        
    except Exception as e:
        print(f"[ERRO obter_modelo_texto] {e}")
        return None

"""
Sistema simplificado de substituição de variáveis em textos automáticos
Apenas variáveis simples, sem funções complexas
"""

import re
import html
from db import get_cursor


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


def processar_texto_automatico(texto_modelo, variaveis):
    """
    Processa um texto modelo substituindo variáveis simples e funções especiais
    
    Formato: use palavras diretamente no texto (sem & ou outros marcadores)
    Exemplo: "SEI nº sei_informado_usuario" 
    
    Funções especiais:
    - criar_tabela_informado_usuario(cabecalho: col1; col2; col3) - cria tabela HTML
    
    Parâmetros:
    - texto_modelo: texto com variáveis como sei_informado_usuario, nome_osc, etc
    - variaveis: dicionário com valores {nome: valor}
    
    Variáveis disponíveis automaticamente:
    - sei_informado_usuario: SEI do formulário
    - osc_informado_usuario: Nome da OSC do formulário  
    - cnpj_informado_usuario: CNPJ informado (ou "não informado")
    - nome_emissor: Nome do emissor
    - numero_pesquisa: Número da pesquisa
    """
    # Decodificar entidades HTML (&nbsp; → espaço, &amp; → &, etc)
    texto_processado = html.unescape(texto_modelo)
    
    # Processar função criar_tabela_informado_usuario se existir
    padrao_tabela = r'criar_tabela_informado_usuario\s*\([^)]*\)'
    match_tabela = re.search(padrao_tabela, texto_processado)
    
    if match_tabela:
        osc_nome = variaveis.get('osc_informado_usuario', variaveis.get('nome_osc', ''))
        if osc_nome:
            tabela_html = criar_tabela_informado_usuario(osc_nome)
            texto_processado = re.sub(padrao_tabela, tabela_html, texto_processado)
        else:
            texto_processado = re.sub(padrao_tabela, '<p style="color: red;">OSC não informada</p>', texto_processado)
    
    # Lista de todas as variáveis possíveis (ordem importa - mais específicas primeiro)
    variaveis_possiveis = [
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

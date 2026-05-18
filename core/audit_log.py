"""
Módulo de auditoria para checklist de análises de prestação de contas
Registra todas as alterações nas tabelas do schema analises_pc

IMPORTANTE: Este módulo é OPCIONAL e pode ser desabilitado
           alterando AUDIT_ENABLED para False
"""

from flask import session
from datetime import datetime
import psycopg2

# ⚙️ CONFIGURAÇÃO: Ative/Desative auditoria aqui
AUDIT_ENABLED = True  # Mude para False para desabilitar


def get_current_user():
    """
    Obtém o email do usuário logado da sessão Flask
    Retorna 'sistema' se não houver usuário logado
    """
    try:
        return session.get('email', 'sistema')
    except:
        return 'sistema'


def log_change(conn, numero_termo, meses_analisados, tabela_origem, coluna, valor_anterior, valor_novo):
    """
    Registra uma alteração no log de auditoria
    
    Args:
        conn: Conexão com o banco de dados
        numero_termo: Número do termo
        meses_analisados: Período em análise
        tabela_origem: Nome da tabela (checklist_termo, checklist_recursos, checklist_analista)
        coluna: Nome da coluna alterada
        valor_anterior: Valor antes da alteração
        valor_novo: Valor após a alteração
    """
    if not AUDIT_ENABLED:
        return  # Auditoria desabilitada, não faz nada
    
    try:
        usuario = get_current_user()
        cur = conn.cursor()
        
        # Converter valores para string
        valor_ant_str = str(valor_anterior) if valor_anterior is not None else None
        valor_novo_str = str(valor_novo) if valor_novo is not None else None
        
        # Só registra se houve mudança real
        if valor_ant_str != valor_novo_str:
            cur.execute("""
                INSERT INTO analises_pc.checklist_change_log (
                    numero_termo, meses_analisados, tabela_origem, 
                    coluna_alterada, valor_anterior, valor_novo, usuario
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                numero_termo, meses_analisados, tabela_origem,
                coluna, valor_ant_str, valor_novo_str, usuario
            ))
            cur.close()
    
    except Exception as e:
        print(f"[AVISO] Erro ao registrar auditoria: {e}")
        # Não propaga erro - auditoria não deve quebrar o fluxo principal
        pass


def audit_checklist_termo(conn, numero_termo, meses_analisados, dados_antigos, dados_novos):
    """
    Audita alterações na tabela checklist_termo
    
    Args:
        conn: Conexão com banco
        numero_termo: Número do termo
        meses_analisados: Período
        dados_antigos: Dict com valores anteriores (ou None se inserção)
        dados_novos: Dict com novos valores
    """
    if not AUDIT_ENABLED:
        return
    
    # Campos booleanos a auditar
    campos_boolean = [
        'avaliacao_celebracao',
        'avaliacao_prestacao_contas',
        'preenchimento_dados_base',
        'preenchimento_orcamento_anual',
        'preenchimento_conciliacao_bancaria',
        'avaliacao_dados_bancarios',
        'documentos_sei_1',
        'avaliacao_resposta_inconsistencia',
        'emissao_parecer',
        'documentos_sei_2',
        'tratativas_restituicao',
        'encaminhamento_encerramento'
    ]
    
    for campo in campos_boolean:
        valor_antigo = dados_antigos.get(campo) if dados_antigos else None
        valor_novo = dados_novos.get(campo)
        
        # Registra mudança
        if valor_antigo != valor_novo:
            log_change(
                conn, numero_termo, meses_analisados,
                'checklist_termo', campo,
                valor_antigo, valor_novo
            )


def audit_checklist_analistas(conn, numero_termo, meses_analisados, analistas_antigos, analistas_novos):
    """
    Audita alterações na lista de analistas
    
    Args:
        conn: Conexão com banco
        numero_termo: Número do termo
        meses_analisados: Período
        analistas_antigos: Lista de analistas anteriores
        analistas_novos: Lista de novos analistas
    """
    if not AUDIT_ENABLED:
        return
    
    antigos_set = set(analistas_antigos or [])
    novos_set = set(analistas_novos or [])
    
    # Analistas removidos
    removidos = antigos_set - novos_set
    for analista in removidos:
        log_change(
            conn, numero_termo, meses_analisados,
            'checklist_analista', 'nome_analista',
            analista, None
        )
    
    # Analistas adicionados
    adicionados = novos_set - antigos_set
    for analista in adicionados:
        log_change(
            conn, numero_termo, meses_analisados,
            'checklist_analista', 'nome_analista',
            None, analista
        )


def audit_checklist_recursos(conn, numero_termo, meses_analisados, recursos_antigos, recursos_novos):
    """
    Audita alterações em recursos
    
    Args:
        conn: Conexão com banco
        numero_termo: Número do termo
        meses_analisados: Período
        recursos_antigos: Lista de recursos anteriores
        recursos_novos: Lista de novos recursos
    """
    if not AUDIT_ENABLED:
        return
    
    # Criar dicionário por tipo_recurso para comparação
    antigos_dict = {r['tipo_recurso']: r for r in (recursos_antigos or [])}
    novos_dict = {r.get('tipo_recurso'): r for r in (recursos_novos or [])}
    
    # Recursos removidos
    tipos_removidos = set(antigos_dict.keys()) - set(novos_dict.keys())
    for tipo in tipos_removidos:
        log_change(
            conn, numero_termo, meses_analisados,
            'checklist_recursos', f'recurso_tipo_{tipo}',
            'existente', 'removido'
        )
    
    # Recursos adicionados
    tipos_adicionados = set(novos_dict.keys()) - set(antigos_dict.keys())
    for tipo in tipos_adicionados:
        log_change(
            conn, numero_termo, meses_analisados,
            'checklist_recursos', f'recurso_tipo_{tipo}',
            None, 'criado'
        )
    
    # Recursos alterados
    tipos_comuns = set(antigos_dict.keys()) & set(novos_dict.keys())
    for tipo in tipos_comuns:
        antigo = antigos_dict[tipo]
        novo = novos_dict[tipo]
        
        campos = ['avaliacao_resposta_recursal', 'emissao_parecer_recursal', 'documentos_sei']
        for campo in campos:
            if antigo.get(campo) != novo.get(campo):
                log_change(
                    conn, numero_termo, meses_analisados,
                    'checklist_recursos', f'recurso_{tipo}_{campo}',
                    antigo.get(campo), novo.get(campo)
                )


def get_audit_history(conn, numero_termo, meses_analisados=None, limit=100):
    """
    Busca histórico de auditoria
    
    Args:
        conn: Conexão com banco
        numero_termo: Número do termo
        meses_analisados: Período (opcional)
        limit: Limite de registros
    
    Returns:
        Lista de dicionários com histórico de alterações
    """
    if not AUDIT_ENABLED:
        return []
    
    try:
        cur = conn.cursor()
        
        if meses_analisados:
            cur.execute("""
                SELECT 
                    id, numero_termo, meses_analisados, tabela_origem,
                    coluna_alterada, valor_anterior, valor_novo,
                    usuario, data_alteracao
                FROM analises_pc.checklist_change_log
                WHERE numero_termo = %s AND meses_analisados = %s
                ORDER BY data_alteracao DESC
                LIMIT %s
            """, (numero_termo, meses_analisados, limit))
        else:
            cur.execute("""
                SELECT 
                    id, numero_termo, meses_analisados, tabela_origem,
                    coluna_alterada, valor_anterior, valor_novo,
                    usuario, data_alteracao
                FROM analises_pc.checklist_change_log
                WHERE numero_termo = %s
                ORDER BY data_alteracao DESC
                LIMIT %s
            """, (numero_termo, limit))
        
        columns = [desc[0] for desc in cur.description]
        results = []
        for row in cur.fetchall():
            results.append(dict(zip(columns, row)))
        
        cur.close()
        return results
    
    except Exception as e:
        print(f"[ERRO] Erro ao buscar histórico: {e}")
        return []

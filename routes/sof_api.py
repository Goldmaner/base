# -*- coding: utf-8 -*-
"""
Blueprint para integração com API do SOF (Sistema Orçamentário e Financeiro)
Consulta contratos e empenhos da Prefeitura de São Paulo
"""

from flask import Blueprint, render_template, request, jsonify, session
from utils import login_required
from config import SOF_API_USERNAME, SOF_API_PASSWORD, SOF_AUTH_BASE64
import requests
from datetime import datetime, timedelta
from functools import lru_cache
import time

sof_api_bp = Blueprint('sof_api', __name__, url_prefix='/gestao_orcamentaria/sof-api')

# ============================================================================
# CONFIGURAÇÕES DA API SOF
# ============================================================================

# URLs da API
SOF_TOKEN_URL = "https://gateway.apilib.prefeitura.sp.gov.br/token"
SOF_BASE_URL = "https://gateway.apilib.prefeitura.sp.gov.br/sf/sof/v4"

# Cache do token (em memória) - evita requisições desnecessárias
_token_cache = {
    'token': None,
    'expira_em': None
}

# ============================================================================
# FUNÇÕES DE AUTENTICAÇÃO
# ============================================================================

def obter_token_sof():
    """
    Obtém token de acesso à API do SOF.
    Usa cache para evitar requisições desnecessárias (token dura ~1 hora).
    
    Returns:
        str: Token de acesso (Bearer token)
        None: Se falhar autenticação
    """
    global _token_cache
    
    # Verificar se token em cache ainda é válido
    agora = datetime.now()
    if _token_cache['token'] and _token_cache['expira_em']:
        if agora < _token_cache['expira_em']:
            print(f"[SOF_API] Usando token em cache (expira em {(_token_cache['expira_em'] - agora).seconds}s)")
            return _token_cache['token']
    
    print("[SOF_API] Token expirado ou inexistente. Solicitando novo token...")
    
    try:
        headers = {
            "Authorization": f"Basic {SOF_AUTH_BASE64}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        # API SOF usa APENAS grant_type=client_credentials
        data = {
            "grant_type": "client_credentials"
        }
        
        print(f"[SOF_API] Autenticando com grant_type=client_credentials")
        
        response = requests.post(
            SOF_TOKEN_URL, 
            headers=headers, 
            data=data,
            timeout=10,
            verify=True
        )
        
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data.get('access_token')
            expires_in = token_data.get('expires_in', 3600)  # Default 1 hora
            
            # Salvar no cache (com margem de 5 minutos antes da expiração)
            _token_cache['token'] = access_token
            _token_cache['expira_em'] = agora + timedelta(seconds=expires_in - 300)
            
            print(f"[SOF_API] Token obtido com sucesso! Expira em {expires_in}s")
            return access_token
        else:
            print(f"[SOF_API] ERRO ao obter token: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"[SOF_API] EXCEÇÃO ao obter token: {type(e).__name__} - {str(e)}")
        return None


# ============================================================================
# FUNÇÕES DE CONSULTA À API
# ============================================================================

def consultar_contratos_sof(filtros):
    """
    Consulta contratos na API do SOF.
    
    Args:
        filtros (dict): Dicionário com filtros da consulta:
            - anoContrato (obrigatório): Ano do exercício
            - codContrato: Código do contrato
            - numCpfCnpj: CNPJ/CPF do credor
            - codEmpresa: Código da empresa (default: '01')
            - numProcesso: Número do processo
            - numPagina: Número da página (paginação)
            - codOrgao: Código do órgão (default: '34' - SMDHC)
    
    Returns:
        dict: Dados retornados pela API ou None em caso de erro
    """
    token = obter_token_sof()
    
    if not token:
        return {
            'erro': True,
            'mensagem': 'Falha ao obter token de autenticação'
        }
    
    try:
        # Preparar parâmetros da query
        params = {}
        
        # Filtros obrigatórios
        if 'anoContrato' in filtros and filtros['anoContrato']:
            params['anoContrato'] = filtros['anoContrato']
        else:
            return {
                'erro': True,
                'mensagem': 'Parâmetro anoContrato é obrigatório'
            }
        
        # Filtros opcionais
        if 'codContrato' in filtros and filtros['codContrato']:
            params['codContrato'] = filtros['codContrato']
        
        if 'numCpfCnpj' in filtros and filtros['numCpfCnpj']:
            params['numCpfCnpj'] = filtros['numCpfCnpj']
        
        if 'codEmpresa' in filtros and filtros['codEmpresa']:
            params['codEmpresa'] = filtros['codEmpresa']
        
        if 'numProcesso' in filtros and filtros['numProcesso']:
            params['numProcesso'] = filtros['numProcesso']
        
        if 'numPagina' in filtros and filtros['numPagina']:
            params['numPagina'] = filtros['numPagina']
        
        if 'codOrgao' in filtros and filtros['codOrgao']:
            params['codOrgao'] = filtros['codOrgao']
        
        # Fazer requisição à API
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json"
        }
        
        url = f"{SOF_BASE_URL}/contratos"
        
        print(f"[SOF_API] Consultando contratos: {url}")
        print(f"[SOF_API] Parâmetros: {params}")
        
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=30,
            verify=True
        )
        
        if response.status_code == 200:
            dados = response.json()
            print(f"[SOF_API] Consulta bem-sucedida! {len(dados.get('lstContratos', []))} contratos retornados")
            return dados
        else:
            print(f"[SOF_API] ERRO na consulta: {response.status_code} - {response.text}")
            return {
                'erro': True,
                'mensagem': f'Erro na API: {response.status_code}',
                'detalhes': response.text
            }
    
    except Exception as e:
        print(f"[SOF_API] EXCEÇÃO na consulta: {type(e).__name__} - {str(e)}")
        return {
            'erro': True,
            'mensagem': f'Exceção: {type(e).__name__}',
            'detalhes': str(e)
        }


def consultar_empenhos_sof(filtros):
    """
    Consulta empenhos na API do SOF.
    
    Args:
        filtros (dict): Dicionário com parâmetros de consulta:
            - anoEmpenho (obrigatório): Ano do empenho
            - mesEmpenho (obrigatório): Mês do movimento do empenho
            - codEmpenho: Código identificador do empenho
            - codEmpresa: Código da empresa
            - numCpfCnpj: CNPJ/CPF do credor
            - txtRazaoSocial: Razão social do credor
            - codContrato: Número do contrato associado
            - anoExercicio: Ano/exercício do contrato
            - codOrgao: Código do órgão
            - codUnidade: Código da unidade
            - codFuncao: Código da função
            - codSubFuncao: Código da subfunção
            - codProjetoAtividade: Código do projeto/atividade
            - codPrograma: Código do programa
            - codCategoria: Código da categoria econômica
            - codGrupo: Código do grupo de despesa
            - codModalidade: Código da modalidade
            - codElemento: Código do elemento de despesa
            - codFonteRecurso: Código da fonte de recurso
            - numPagina: Número da página (paginação)
    
    Returns:
        dict: Resposta da API com lstEmpenhos ou erro
    """
    try:
        # Obter token de acesso
        token = obter_token_sof()
        if not token:
            return {
                'erro': True,
                'mensagem': 'Não foi possível obter token de autenticação'
            }
        
        # Montar URL
        url = f"{SOF_BASE_URL}/empenhos"
        
        # Montar parâmetros (remover None e strings vazias)
        params = {
            k: v for k, v in filtros.items() 
            if v is not None and v != ''
        }
        
        print(f"[SOF_API] Consultando empenhos: {url}")
        print(f"[SOF_API] Parâmetros: {params}")
        
        # Fazer requisição
        headers = {
            "Authorization": f"Bearer {token}"
        }
        
        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=30
        )
        
        print(f"[SOF_API] Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"[SOF_API] Empenhos obtidos: {len(data.get('lstEmpenhos', []))}")
            return data
        else:
            print(f"[SOF_API] ERRO na consulta: {response.status_code} - {response.text}")
            return {
                'erro': True,
                'mensagem': f'Erro na API: {response.status_code}',
                'detalhes': response.text
            }
    
    except Exception as e:
        print(f"[SOF_API] EXCEÇÃO na consulta de empenhos: {type(e).__name__} - {str(e)}")
        return {
            'erro': True,
            'mensagem': f'Exceção: {type(e).__name__}',
            'detalhes': str(e)
        }


# ============================================================================
# ROTAS
# ============================================================================

@sof_api_bp.route('/')
@login_required
def index():
    """Página principal de consulta à API SOF"""
    return render_template('gestao_orcamentaria/sof_api.html')


@sof_api_bp.route('/api/consultar-contratos', methods=['POST'])
@login_required
def api_consultar_contratos():
    """
    API para consultar contratos na API do SOF.
    Recebe filtros via JSON e retorna dados dos contratos.
    """
    try:
        filtros = request.get_json()
        
        if not filtros:
            return jsonify({
                'success': False,
                'erro': 'Nenhum filtro fornecido'
            }), 400
        
        # Consultar API do SOF
        inicio = time.time()
        resultado = consultar_contratos_sof(filtros)
        duracao = int((time.time() - inicio) * 1000)
        
        # Verificar se houve erro
        if resultado.get('erro'):
            return jsonify({
                'success': False,
                'erro': resultado.get('mensagem'),
                'detalhes': resultado.get('detalhes')
            }), 500
        
        # Processar dados para formato mais amigável
        contratos = resultado.get('lstContratos', [])
        meta_dados = resultado.get('metaDados', {})
        
        return jsonify({
            'success': True,
            'contratos': contratos,
            'total': len(contratos),
            'meta_dados': meta_dados,
            'duracao_ms': duracao
        })
    
    except Exception as e:
        print(f"[SOF_API] Erro em api_consultar_contratos: {e}")
        return jsonify({
            'success': False,
            'erro': str(e)
        }), 500


@sof_api_bp.route('/api/consultar-empenhos', methods=['POST'])
@login_required
def api_consultar_empenhos():
    """
    API para consultar empenhos na API do SOF.
    Recebe filtros via JSON e retorna dados dos empenhos.
    """
    try:
        filtros = request.get_json()
        
        if not filtros:
            return jsonify({
                'success': False,
                'erro': 'Nenhum filtro fornecido'
            }), 400
        
        # Validar parâmetros obrigatórios
        if not filtros.get('anoEmpenho'):
            return jsonify({
                'success': False,
                'erro': 'Parâmetro anoEmpenho é obrigatório'
            }), 400
        
        if not filtros.get('mesEmpenho'):
            return jsonify({
                'success': False,
                'erro': 'Parâmetro mesEmpenho é obrigatório'
            }), 400
        
        # Consultar API do SOF
        inicio = time.time()
        resultado = consultar_empenhos_sof(filtros)
        duracao = int((time.time() - inicio) * 1000)
        
        # Verificar se houve erro
        if resultado.get('erro'):
            return jsonify({
                'success': False,
                'erro': resultado.get('mensagem'),
                'detalhes': resultado.get('detalhes')
            }), 500
        
        # Processar dados para formato mais amigável
        empenhos = resultado.get('lstEmpenhos', [])
        meta_dados = resultado.get('metaDados', {})
        
        return jsonify({
            'success': True,
            'empenhos': empenhos,
            'total': len(empenhos),
            'meta_dados': meta_dados,
            'duracao_ms': duracao
        })
    
    except Exception as e:
        print(f"[SOF_API] Erro em api_consultar_empenhos: {e}")
        return jsonify({
            'success': False,
            'erro': str(e)
        }), 500


@sof_api_bp.route('/api/testar-conexao', methods=['GET'])
@login_required
def api_testar_conexao():
    """
    Testa conexão com a API do SOF.
    Útil para diagnóstico.
    """
    try:
        inicio = time.time()
        token = obter_token_sof()
        duracao = int((time.time() - inicio) * 1000)
        
        if token:
            return jsonify({
                'success': True,
                'mensagem': 'Conexão com API SOF estabelecida com sucesso!',
                'token_valido': True,
                'duracao_ms': duracao
            })
        else:
            return jsonify({
                'success': False,
                'mensagem': 'Falha ao obter token de autenticação',
                'token_valido': False,
                'duracao_ms': duracao
            }), 500
    
    except Exception as e:
        return jsonify({
            'success': False,
            'mensagem': f'Erro ao testar conexão: {str(e)}'
        }), 500

"""
Blueprint de gerenciamento de listas/tabelas categóricas
"""

from flask import Blueprint, render_template, request, jsonify, session
from db import get_cursor, execute_query, get_db
from utils import login_required
from decorators import requires_access

listas_bp = Blueprint('listas', __name__, url_prefix='/listas')


def converter_valor_para_db(valor, campo, config):
    """
    Converte valores do frontend para o formato do banco de dados
    """
    # Strings vazias viram NULL no banco (campos opcionais não preenchidos)
    if isinstance(valor, str) and valor.strip() == '':
        return None

    # Se a tabela marca explicitamente que o campo é boolean no DB, converter
    if isinstance(valor, str) and campo in (config or {}).get('colunas_boolean', []):
        return valor.lower() in ['ativo', 'true', '1', 'sim']

    # Se o campo for 'status' e valor for string, converter para boolean
    # EXCETO se a tabela tem opções explícitas (coluna TEXT, não BOOLEAN)
    if campo == 'status' and isinstance(valor, str):
        tipos = config.get('tipos_campo', {}) if config else {}
        if f'opcoes_{campo}' in tipos:
            # Coluna TEXT com opções configuradas — manter string como está
            return valor
        # Coluna BOOLEAN sem opções explícitas
        return valor.lower() in ['ativo', 'true', '1', 'sim']
    
    # Se o campo for 'status_pg' e valor for string, manter string
    if campo == 'status_pg':
        return valor
    
    # Se o campo for 'status_c' e valor for string, manter string
    if campo == 'status_c':
        return valor
    
    return valor


def converter_valor_para_frontend(valor, campo):
    """
    Converte valores do banco de dados para o formato do frontend
    """
    # Se o campo for 'status' e valor for boolean, converter para string
    if campo == 'status' and isinstance(valor, bool):
        return 'Ativo' if valor else 'Inativo'
    # Corrigir registros corrompidos: 'false'/'true' armazenados como texto
    if campo == 'status' and valor in ('false', 'f'):
        return 'Inativo'
    if campo == 'status' and valor in ('true', 't'):
        return 'Ativo'
    
    return valor


# Configuração das tabelas gerenciáveis (ordem alfabética por nome)
TABELAS_CONFIG = {
    'c_dac_analistas': {
        'nome': 'DAC: Analistas',
        'schema': 'categoricas',
        'colunas_editaveis': ['nome_analista', 'd_usuario', 'posicao_analista', 'contrato_inicio', 'contrato_fim', 'status'],
        'colunas_obrigatorias': ['nome_analista', 'd_usuario', 'posicao_analista', 'status'],
        'labels': {
            'nome_analista': 'Nome do Analista',
            'd_usuario': 'R.F.',
            'posicao_analista': 'Posição',
            'contrato_inicio': 'Início do Contrato',
            'contrato_fim': 'Fim do Contrato',
            'status': 'Status'
        },
        'colunas_filtro': ['nome_analista', 'd_usuario', 'posicao_analista', 'status'],
        'ordem': 'nome_analista',
        'tipos_campo': {
            'posicao_analista': 'select',
            'opcoes_posicao_analista': ['Servidor(a)', 'Servidor(a) Temporário(a)', 'Estagiário(a)'],
            'contrato_inicio': 'date',
            'contrato_fim': 'date',
            'status': 'select',
            'opcoes_status': ['Ativo', 'Inativo']
        },
        'inline_edit': True,
        'inline_columns': ['status']
    },
    'c_dac_despesas_analise': {
        'nome': 'DAC: Despesas de Análise',
        'schema': 'categoricas',
        'colunas_editaveis': ['categoria_extra', 'tipo_transacao', 'descricao', 'correspondente', 'aplicacao'],
        'colunas_obrigatorias': ['categoria_extra', 'tipo_transacao'],
        'labels': {
            'categoria_extra': 'Categoria Extra',
            'tipo_transacao': 'Tipo de Transação',
            'descricao': 'Descrição',
            'correspondente': 'Correspondente',
            'aplicacao': 'Aplicação'
        },
        'colunas_filtro': ['categoria_extra', 'tipo_transacao', 'correspondente', 'aplicacao'],
        'ordem': 'categoria_extra',
        'tipos_campo': {
            'tipo_transacao': 'select',
            'opcoes_tipo_transacao': ['Crédito', 'Débito', 'Débito / Crédito'],
            'aplicacao': 'checkbox',
            'descricao': 'textarea',
            'correspondente': 'text'
        }
    },
    'c_dac_despesas_provisao': {
        'nome': 'DAC: Despesas de Provisão',
        'schema': 'categoricas',
        'colunas_editaveis': ['despesa_provisao', 'descricao'],
        'colunas_obrigatorias': ['despesa_provisao'],
        'labels': {
            'despesa_provisao': 'Despesa de Provisão',
            'descricao': 'Descrição'
        },
        'colunas_filtro': ['despesa_provisao'],
        'ordem': 'despesa_provisao',
        'tipos_campo': {
            'despesa_provisao': 'text',
            'descricao': 'textarea'
        }
    },
    'c_dac_modelo_textos_inconsistencias': {
        'nome': 'DAC: Modelos de Textos de Inconsistências',
        'schema': 'categoricas',
        'colunas_editaveis': [
            'nome_item', 
            'tipo_inconsistencia', 
            'modelo_texto',
            'solucao',
            'genero_inconsistencia',
            'situacao',
            'nivel_gravidade',
            'referencia_normativa',
            'ordem'
        ],
        'colunas_obrigatorias': ['nome_item', 'tipo_inconsistencia', 'modelo_texto'],
        'labels': {
            'nome_item': 'Nome do Item',
            'tipo_inconsistencia': 'Tipo de Inconsistência',
            'modelo_texto': 'Modelo de Texto',
            'solucao': 'Forma de Resolução',
            'genero_inconsistencia': 'Gênero',
            'situacao': 'Situação',
            'nivel_gravidade': 'Nível de Gravidade',
            'referencia_normativa': 'Referência Normativa',
            'ordem': 'Ordem'
        },
        'colunas_filtro': ['nome_item', 'tipo_inconsistencia', 'genero_inconsistencia', 'situacao', 'nivel_gravidade'],
        'ordem': 'ordem NULLS LAST, nome_item',
        'permite_reordenar': True,
        'tipos_campo': {
            'nome_item': 'text',
            'tipo_inconsistencia': 'select',
            'opcoes_tipo_inconsistencia': [
                'Solicitações globais',
                'Créditos não esclarecidos',
                'Débitos não esclarecidos',
                'Forma de Pagamento Incorreta',
                'Inconsistência com plano de trabalho ou termo',
                'Inconsistência de aplicação da verba',
                'Inconsistência em demonstrativo',
                'Outros'
            ],
            'modelo_texto': 'textarea',
            'rows_modelo_texto': 15,
            'solucao': 'textarea',
            'rows_solucao': 15,
            'genero_inconsistencia': 'select',
            'opcoes_genero_inconsistencia': ['Material', 'Formal'],
            'situacao': 'select',
            'opcoes_situacao': ['Ativa', 'Inativa'],
            'nivel_gravidade': 'select',
            'opcoes_nivel_gravidade': ['Leve', 'Moderada', 'Grave'],
            'referencia_normativa': 'text',
            'ordem': 'number'
        }
    },
    'c_dac_responsabilidade_analise': {
        'nome': 'DAC: Responsabilidades de Análise',
        'schema': 'categoricas',
        'colunas_editaveis': ['nome_setor'],
        'labels': {'nome_setor': 'Nome do Setor'},
        'ordem': 'nome_setor'
    },
    'c_dac_parcela_andamento_status': {
        'nome': 'DAC: Status de Parcela em Andamento',
        'schema': 'categoricas',
        'colunas_editaveis': ['status_parcela', 'descricao', 'status_status'],
        'colunas_obrigatorias': ['status_parcela'],
        'labels': {
            'status_parcela': 'Status da Parcela',
            'descricao': 'Descrição',
            'status_status': 'Status do Status'
        },
        'colunas_filtro': ['status_parcela', 'status_status'],
        'ordem': 'status_parcela',
        'tipos_campo': {
            'status_parcela': 'text',
            'descricao': 'textarea',
            'rows_descricao': 3,
            'status_status': 'select',
            'opcoes_status_status': ['ativo', 'inativo']
        },
        'inline_edit': True,
        'inline_columns': ['status_status']
    },
    'c_dgp_analistas': {
        'nome': 'DGP: Agentes DGP',
        'schema': 'categoricas',
        'colunas_editaveis': ['nome_analista', 'rf', 'email', 'status'],
        'colunas_boolean': ['status'],
        'labels': {
            'nome_analista': 'Nome do Agente',
            'rf': 'R.F.',
            'email': 'E-mail',
            'status': 'Status'
        },
        'colunas_filtro': ['nome_analista', 'rf', 'email', 'status'],
        'ordem': 'nome_analista',
        'tipos_campo': {
            'status': 'select',
            'opcoes_status': ['Ativo', 'Inativo']
        },
        'inline_edit': True,
        'inline_columns': ['status']
    },
    'c_dgp_cents_status': {
        'nome': 'DGP: Status de CENTS',
        'schema': 'categoricas',
        'colunas_editaveis': ['cents_status', 'descricao', 'status_status'],
        'colunas_obrigatorias': ['cents_status'],
        'labels': {
            'cents_status': 'Status de CENTS',
            'descricao': 'Descrição',
            'status_status': 'Status do Status'
        },
        'colunas_filtro': ['cents_status', 'status_status'],
        'ordem': 'cents_status',
        'tipos_campo': {
            'cents_status': 'text',
            'descricao': 'textarea',
            'rows_descricao': 3,
            'status_status': 'select',
            'opcoes_status_status': ['ativo', 'inativo', 'pendente']
        },
        'inline_edit': True,
        'inline_columns': ['status_status']
    },
    'c_dgp_celebracao_status': {
        'nome': 'DGP/Celebração: Status de Celebração',
        'schema': 'categoricas',
        'colunas_editaveis': ['status_novo', 'status_antigo', 'descricao', 'status_status', 'status_generico'],
        'colunas_obrigatorias': ['status_novo'],
        'labels': {
            'status_novo': 'Status Novo',
            'status_antigo': 'Status Antigo',
            'descricao': 'Descrição',
            'status_status': 'Status do Status',
            'status_generico': 'Status Genérico'
        },
        'colunas_filtro': ['status_novo', 'status_antigo', 'status_status', 'status_generico'],
        'ordem': 'id',
        'tipos_campo': {
            'status_novo': 'text',
            'status_antigo': 'text',
            'descricao': 'textarea',
            'rows_descricao': 3,
            'status_status': 'select',
            'opcoes_status_status': ['ativo', 'inativo'],
            'status_generico': 'select_dinamico',
            'query_status_generico': "SELECT DISTINCT status_generico FROM categoricas.c_dgp_celebracao_status WHERE status_generico IS NOT NULL AND status_generico != '' ORDER BY status_generico"
        },
        'inline_edit': True,
        'inline_columns': ['status_status']
    },
    'c_dgp_celebracao_substatus': {
        'nome': 'DGP/Celebração: Substatus de Celebração',
        'schema': 'categoricas',
        'colunas_editaveis': ['substatus', 'responsabilidade_status', 'descricao', 'substatus_limite', 'substatus_status'],
        'colunas_obrigatorias': ['substatus'],
        'labels': {
            'substatus': 'Substatus',
            'responsabilidade_status': 'Responsabilidade do Status',
            'descricao': 'Descrição',
            'substatus_limite': 'Limite (ID Status)',
            'substatus_status': 'Status do Substatus'
        },
        'colunas_filtro': ['substatus', 'responsabilidade_status', 'substatus_status'],
        'ordem': 'substatus',
        'tipos_campo': {
            'substatus': 'text',
            'responsabilidade_status': 'text',
            'descricao': 'textarea',
            'rows_descricao': 3,
            'substatus_limite': 'number',
            'substatus_status': 'select',
            'opcoes_substatus_status': ['ativo', 'inativo']
        },
        'inline_edit': True,
        'inline_columns': ['substatus_status']
    },
    'c_dgp_meta_tipos': {
        'nome': 'DP/Metas: Tipos de Meta',
        'schema': 'categoricas',
        'colunas_editaveis': ['meta_tipo', 'tipo_classificacao', 'descricao', 'observacao'],
        'colunas_obrigatorias': ['meta_tipo'],
        'labels': {
            'meta_tipo': 'Tipo de Meta',
            'tipo_classificacao': 'Classificação',
            'descricao': 'Descrição',
            'observacao': 'Observação'
        },
        'colunas_filtro': ['meta_tipo', 'tipo_classificacao'],
        'ordem': 'tipo_classificacao NULLS LAST, meta_tipo',
        'tipos_campo': {
            'meta_tipo': 'text',
            'tipo_classificacao': 'text',
            'descricao': 'textarea',
            'rows_descricao': 3,
            'observacao': 'textarea',
            'rows_observacao': 2,
        }
    },
    'c_dgp_plano_definicoes': {
        'nome': 'DP/Metas: Definições do Glossário',
        'schema': 'categoricas',
        'colunas_editaveis': ['conceito', 'definicao', 'observacoes'],
        'colunas_obrigatorias': ['conceito'],
        'labels': {
            'conceito': 'Conceito',
            'definicao': 'Definição',
            'observacoes': 'Observações'
        },
        'colunas_filtro': ['conceito'],
        'ordem': 'conceito',
        'tipos_campo': {
            'conceito': 'text',
            'definicao': 'textarea',
            'rows_definicao': 4,
            'observacoes': 'textarea',
            'rows_observacoes': 3,
        }
    },
    'c_alt_instrumento': {
        'nome': 'DGP/ALT: Instrumentos Jurídicos para Alterações de Contrato',
        'schema': 'categoricas',
        'colunas_editaveis': ['instrumento_alteracao', 'descricao', 'status'],
        'colunas_obrigatorias': ['instrumento_alteracao'],
        'labels': {
            'instrumento_alteracao': 'Nome do Instrumento',
            'descricao': 'Descrição',
            'status': 'Status'
        },
        'colunas_filtro': ['instrumento_alteracao', 'status'],
        'ordem': 'instrumento_alteracao',
        'tipos_campo': {
            'instrumento_alteracao': 'text',
            'descricao': 'textarea',
            'rows_descricao': 3,
            'status': 'select',
            'opcoes_status': ['ativo', 'inativo']
        },
        'inline_edit': True,
        'inline_columns': ['status']
    },
    'c_alt_normas': {
        'nome': 'DGP/ALT: Normas e Regimentos para Alterações',
        'schema': 'categoricas',
        'colunas_editaveis': [
            'norma',
            'regimento',
            'referencia_legal',
            'data_aplicacao',
            'status'
        ],
        'colunas_obrigatorias': ['norma'],
        'labels': {
            'norma': 'Nome da Norma',
            'regimento': 'Regimento/Descrição',
            'referencia_legal': 'Referência Legal',
            'data_aplicacao': 'Data de Aplicação',
            'status': 'Status'
        },
        'colunas_filtro': ['norma', 'referencia_legal', 'status'],
        'ordem': 'norma',
        'tipos_campo': {
            'norma': 'text',
            'regimento': 'textarea',
            'rows_regimento': 10,
            'referencia_legal': 'text',
            'data_aplicacao': 'date',
            'status': 'select',
            'opcoes_status': ['ativo', 'inativo']
        },
        'inline_edit': True,
        'inline_columns': ['status']
    },
    'c_alt_principios': {
        'nome': 'DGP/ALT: Princípios para Alteração de Parceria',
        'schema': 'categoricas',
        'colunas_editaveis': [
            'nome_principio',
            'descricao_principio',
            'exemplo_principio',
            'status'
        ],
        'colunas_obrigatorias': ['nome_principio'],
        'labels': {
            'nome_principio': 'Nome do Princípio',
            'descricao_principio': 'Descrição do Princípio',
            'exemplo_principio': 'Exemplo de Aplicação',
            'status': 'Status'
        },
        'colunas_filtro': ['nome_principio', 'status'],
        'ordem': 'nome_principio',
        'tipos_campo': {
            'nome_principio': 'text',
            'descricao_principio': 'textarea',
            'rows_descricao_principio': 5,
            'exemplo_principio': 'textarea',
            'rows_exemplo_principio': 5,
            'status': 'select',
            'opcoes_status': ['ativo', 'inativo']
        },
        'inline_edit': True,
        'inline_columns': ['status']
    },
    'c_alt_tipo': {
        'nome': 'DGP/ALT: Tipos de Alteração de Parceria',
        'schema': 'categoricas',
        'colunas_editaveis': [
            'alt_tipo',
            'alt_modalidade',
            'alt_escopo',
            'alt_campo',
            'alt_fonte_recursos',
            'alt_instrumento',
            'alt_principios',
            'status'
        ],
        'colunas_obrigatorias': ['alt_tipo'],
        'labels': {
            'alt_tipo': 'Tipo de Alteração',
            'alt_modalidade': 'Modalidades Aplicáveis',
            'alt_escopo': 'Escopo da Alteração',
            'alt_campo': 'Campos/Cláusulas Afetados',
            'alt_fonte_recursos': 'Fontes de Recursos',
            'alt_instrumento': 'Instrumentos Jurídicos',
            'alt_principios': 'Princípios Aplicáveis',
            'status': 'Status'
        },
        'colunas_filtro': ['alt_tipo', 'alt_escopo', 'status'],
        'ordem': 'alt_tipo',
        'tipos_campo': {
            'alt_tipo': 'text',
            'alt_modalidade': 'checkbox_multiple',
            'query_alt_modalidade': 'SELECT DISTINCT informacao FROM categoricas.c_geral_tipo_contrato WHERE informacao IS NOT NULL ORDER BY informacao',
            'alt_escopo': 'select',
            'opcoes_alt_escopo': [
                'Termo',
                'Plano',
                'Flutuante (Plano e Termo)',
                'Não aplicável'
            ],
            'alt_campo': 'checkbox_multiple',
            'opcoes_alt_campo': [
                'Preâmbulo do Termo',
                'Cláusulas do Termo',
                'Cronograma de Desembolso',
                'Campos do Plano de Trabalho',
                'Quadro de Metas',
                'Cronograma de Execução',
                'Proposta Orçamentária'
            ],
            'alt_fonte_recursos': 'checkbox_multiple',
            'query_alt_fonte_recursos': 'SELECT DISTINCT descricao FROM categoricas.c_geral_origem_recurso WHERE descricao IS NOT NULL ORDER BY descricao',
            'alt_instrumento': 'checkbox_multiple',
            'query_alt_instrumento': 'SELECT DISTINCT instrumento_alteracao FROM categoricas.c_alt_instrumento WHERE instrumento_alteracao IS NOT NULL ORDER BY instrumento_alteracao',
            'alt_principios': 'checkbox_multiple',
            'query_alt_principios': 'SELECT nome_principio FROM categoricas.c_alt_principios WHERE status = \'ativo\' ORDER BY nome_principio',
            'status': 'select',
            'opcoes_status': ['ativo', 'inativo']
        },
        'inline_edit': True,
        'inline_columns': ['status']
    },
    'c_documentos_dp_prazos': {
        'nome': 'DP: Prazos de Documentos',
        'schema': 'categoricas',
        'colunas_editaveis': ['tipo_documento', 'lei', 'prazo_dias', 'prazo_descricao'],
        'labels': {
            'tipo_documento': 'Tipo de Documento',
            'lei': 'Lei/Portaria',
            'prazo_dias': 'Prazo (dias)',
            'prazo_descricao': 'Descrição do Prazo'
        },
        'colunas_filtro': ['tipo_documento', 'lei'],
        'ordem': 'tipo_documento, lei',
        'tipos_campo': {
            'tipo_documento': 'select_dinamico',
            'query_tipo_documento': 'SELECT DISTINCT tipo_documento FROM categoricas.c_dp_documentos WHERE tipo_documento IS NOT NULL ORDER BY tipo_documento',
            'lei': 'select_dinamico',
            'query_lei': 'SELECT DISTINCT lei FROM categoricas.c_geral_legislacao WHERE lei IS NOT NULL ORDER BY lei',
            'prazo_descricao': 'textarea',
            'prazo_dias': 'number'
        }
    },
    'c_dp_documentos': {
        'nome': 'DP: Tipos de Documento',
        'schema': 'categoricas',
        'colunas_editaveis': ['tipo_documento', 'descricao', 'orgao_emissor', 'tipo_usuario'],
        'labels': {
            'tipo_documento': 'Tipo de Documento',
            'descricao': 'Descrição',
            'orgao_emissor': 'Órgão Emissor',
            'tipo_usuario': 'Tipo de Usuário'
        },
        'colunas_filtro': ['tipo_documento', 'orgao_emissor', 'tipo_usuario'],
        'ordem': 'tipo_usuario, tipo_documento',
        'tipos_campo': {
            'descricao': 'textarea',
            'tipo_usuario': 'select',
            'opcoes_tipo_usuario': ['Agente DP', 'Agente DAC', 'Agente DGP']
        }
    },
    'c_geral_coordenadores': {
        'nome': 'Geral: Coordenadores',
        'schema': 'categoricas',
        'colunas_editaveis': ['secretaria', 'coordenacao', 'nome_c', 'pronome', 'rf_c', 'status_c', 'e_mail_c', 'setor_sei'],
        'labels': {
            'secretaria': 'Secretaria',
            'coordenacao': 'Coordenação',
            'nome_c': 'Nome',
            'pronome': 'Pronome',
            'rf_c': 'R.F.',
            'status_c': 'Status',
            'e_mail_c': 'E-mail',
            'setor_sei': 'Setor SEI'
        },
        'colunas_filtro': ['secretaria', 'coordenacao', 'nome_c', 'status_c', 'setor_sei'],
        'colunas_ordenacao': ['setor_sei'],
        'ordem': 'nome_c',
        'tipos_campo': {
            'secretaria': 'select_dinamico',
            'query_secretaria': 'SELECT DISTINCT secretaria FROM categoricas.c_geral_coordenadores WHERE secretaria IS NOT NULL ORDER BY secretaria',
            'coordenacao': 'text_com_datalist',
            'query_coordenacao': 'SELECT DISTINCT coordenacao FROM categoricas.c_geral_coordenadores WHERE coordenacao IS NOT NULL ORDER BY coordenacao',
            'status_c': 'select',
            'opcoes_status_c': ['Ativo', 'Afastado', 'Inativo'],
            'pronome': 'select',
            'opcoes_pronome': ['Sr.', 'Sra.', 'Sr.(a)']
        }
    },
    'c_geral_origem_recurso': {
        'nome': 'Geral: Origens de Recurso',
        'schema': 'categoricas',
        'colunas_editaveis': ['orgao', 'unidade', 'descricao'],
        'labels': {'orgao': 'Órgão', 'unidade': 'Unidade', 'descricao': 'Descrição'},
        'ordem': 'orgao, unidade'
    },
    'c_geral_pessoa_gestora': {
        'nome': 'Geral: Pessoas Gestoras',
        'schema': 'categoricas',
        'colunas_editaveis': ['nome_pg', 'setor', 'numero_rf', 'status_pg', 'email_pg'],
        'colunas_calculadas': ['total_pareceres', 'total_parcerias'],
        'labels': {
            'nome_pg': 'Nome', 
            'setor': 'Setor', 
            'numero_rf': 'Número do R.F.', 
            'status_pg': 'Status', 
            'email_pg': 'E-mail',
            'total_pareceres': 'Total de Pareceres',
            'total_parcerias': 'Total de Parcerias'
        },
        'colunas_filtro': ['nome_pg', 'setor', 'numero_rf', 'status_pg'],
        'ordem': 'nome_pg',
        'tipos_campo': {
            'setor': 'select_dinamico',
            'query_setor': 'SELECT DISTINCT setor FROM categoricas.c_geral_pessoa_gestora WHERE setor IS NOT NULL ORDER BY setor',
            'status_pg': 'select',
            'opcoes_status_pg': ['Ativo', 'Inativo', 'Desconhecido']
        }
    },
    'c_geral_tipos_doc_sei': {
        'nome': 'Geral: Tipos de Documento SEI',
        'schema': 'categoricas',
        'colunas_editaveis': ['tipo_doc', 'descricao', 'status_tipo_doc'],
        'colunas_obrigatorias': ['tipo_doc'],
        'labels': {
            'tipo_doc': 'Tipo de Documento',
            'descricao': 'Descrição',
            'status_tipo_doc': 'Status'
        },
        'colunas_filtro': ['tipo_doc', 'status_tipo_doc'],
        'colunas_ordenacao': ['tipo_doc'],
        'ordem': 'tipo_doc',
        'tipos_campo': {
            'tipo_doc': 'text',
            'descricao': 'textarea',
            'rows_descricao': 3,
            'status_tipo_doc': 'select',
            'opcoes_status_tipo_doc': ['Ativo', 'Inativo', 'Em Desuso']
        }
    },
    'c_dp_status_edital': {
        'nome': 'DP: Status de Edital',
        'schema': 'categoricas',
        'colunas_editaveis': ['status', 'descricao'],
        'colunas_obrigatorias': ['status'],
        'labels': {
            'status': 'Status',
            'descricao': 'Descrição'
        },
        'colunas_filtro': ['status'],
        'ordem': 'status',
        'tipos_campo': {
            'status': 'text',
            'descricao': 'textarea',
            'rows_descricao': 3
        }
    },
    'c_dac_responsabilidade_analise': {
        'nome': 'DAC: Responsabilidades de Análise',
        'schema': 'categoricas',
        'colunas_editaveis': ['nome_setor'],
        'labels': {'nome_setor': 'Nome do Setor'},
        'ordem': 'nome_setor'
    },
    'c_geral_coordenadores': {
        'nome': 'Geral: Coordenadores',
        'schema': 'categoricas',
        'colunas_editaveis': ['secretaria', 'coordenacao', 'nome_c', 'pronome', 'rf_c', 'status_c', 'e_mail_c', 'setor_sei'],
        'labels': {
            'secretaria': 'Secretaria',
            'coordenacao': 'Coordenação',
            'nome_c': 'Nome',
            'pronome': 'Pronome',
            'rf_c': 'R.F.',
            'status_c': 'Status',
            'e_mail_c': 'E-mail',
            'setor_sei': 'Setor SEI'
        },
        'colunas_filtro': ['secretaria', 'coordenacao', 'nome_c', 'status_c', 'setor_sei'],
        'colunas_ordenacao': ['setor_sei'],
        'ordem': 'nome_c',
        'tipos_campo': {
            'secretaria': 'select_dinamico',
            'query_secretaria': 'SELECT DISTINCT secretaria FROM categoricas.c_geral_coordenadores WHERE secretaria IS NOT NULL ORDER BY secretaria',
            'coordenacao': 'text_com_datalist',
            'query_coordenacao': 'SELECT DISTINCT coordenacao FROM categoricas.c_geral_coordenadores WHERE coordenacao IS NOT NULL ORDER BY coordenacao',
            'status_c': 'select',
            'opcoes_status_c': ['Ativo', 'Afastado', 'Inativo'],
            'pronome': 'select',
            'opcoes_pronome': ['Sr.', 'Sra.', 'Sr.(a)']
        }
    },
    'c_geral_origem_recurso': {
        'nome': 'Geral: Origens de Recurso',
        'schema': 'categoricas',
        'colunas_editaveis': ['orgao', 'unidade', 'descricao'],
        'labels': {'orgao': 'Órgão', 'unidade': 'Unidade', 'descricao': 'Descrição'},
        'ordem': 'orgao, unidade'
    },
    'c_dgp_analistas': {
        'nome': 'DGP: Agentes DGP',
        'schema': 'categoricas',
        'colunas_editaveis': ['nome_analista', 'rf', 'email', 'status'],
        'colunas_boolean': ['status'],
        'labels': {
            'nome_analista': 'Nome do Agente',
            'rf': 'R.F.',
            'email': 'E-mail',
            'status': 'Status'
        },
        'colunas_filtro': ['nome_analista', 'rf', 'email', 'status'],
        'ordem': 'nome_analista',
        'tipos_campo': {
            'status': 'select',
            'opcoes_status': ['Ativo', 'Inativo']
        },
        'inline_edit': True,
        'inline_columns': ['status']
    },
    'c_dac_despesas_analise': {
        'nome': 'DAC: Despesas de Análise',
        'schema': 'categoricas',
        'colunas_editaveis': ['categoria_extra', 'tipo_transacao', 'descricao', 'correspondente', 'aplicacao'],
        'colunas_obrigatorias': ['categoria_extra', 'tipo_transacao'],
        'labels': {
            'categoria_extra': 'Categoria Extra',
            'tipo_transacao': 'Tipo de Transação',
            'descricao': 'Descrição',
            'correspondente': 'Correspondente',
            'aplicacao': 'Aplicação'
        },
        'colunas_filtro': ['categoria_extra', 'tipo_transacao', 'correspondente', 'aplicacao'],
        'ordem': 'categoria_extra',
        'tipos_campo': {
            'tipo_transacao': 'select',
            'opcoes_tipo_transacao': ['Crédito', 'Débito', 'Débito / Crédito'],
            'aplicacao': 'checkbox',
            'descricao': 'textarea',
            'correspondente': 'text'
        }
    },
    'c_dac_despesas_provisao': {
        'nome': 'DAC: Despesas de Provisão',
        'schema': 'categoricas',
        'colunas_editaveis': ['despesa_provisao', 'descricao'],
        'colunas_obrigatorias': ['despesa_provisao'],
        'labels': {
            'despesa_provisao': 'Despesa de Provisão',
            'descricao': 'Descrição'
        },
        'colunas_filtro': ['despesa_provisao'],
        'ordem': 'despesa_provisao',
        'tipos_campo': {
            'despesa_provisao': 'text',
            'descricao': 'textarea'
        }
    },
    'c_dac_modelo_textos_inconsistencias': {
        'nome': 'DAC: Modelos de Textos de Inconsistências',
        'schema': 'categoricas',
        'colunas_editaveis': [
            'nome_item', 
            'tipo_inconsistencia', 
            'modelo_texto',
            'solucao',
            'genero_inconsistencia',
            'situacao',
            'nivel_gravidade',
            'referencia_normativa',
            'ordem'
        ],
        'colunas_obrigatorias': ['nome_item', 'tipo_inconsistencia', 'modelo_texto'],
        'labels': {
            'nome_item': 'Nome do Item',
            'tipo_inconsistencia': 'Tipo de Inconsistência',
            'modelo_texto': 'Modelo de Texto',
            'solucao': 'Forma de Resolução',
            'genero_inconsistencia': 'Gênero',
            'situacao': 'Situação',
            'nivel_gravidade': 'Nível de Gravidade',
            'referencia_normativa': 'Referência Normativa',
            'ordem': 'Ordem'
        },
        'colunas_filtro': ['nome_item', 'tipo_inconsistencia', 'genero_inconsistencia', 'situacao', 'nivel_gravidade'],
        'ordem': 'ordem NULLS LAST, nome_item',
        'permite_reordenar': True,  # Habilita botões de reordenação ↑↓
        'tipos_campo': {
            'nome_item': 'text',
            'tipo_inconsistencia': 'select',
            'opcoes_tipo_inconsistencia': [
                'Solicitações globais',
                'Créditos não esclarecidos',
                'Débitos não esclarecidos',
                'Forma de Pagamento Incorreta',
                'Inconsistência com plano de trabalho ou termo',
                'Inconsistência de aplicação da verba',
                'Inconsistência em demonstrativo',
                'Outros'
            ],
            'modelo_texto': 'textarea',
            'rows_modelo_texto': 15,  # Campo maior para textos longos
            'solucao': 'textarea',
            'rows_solucao': 15,  # Campo maior para textos longos
            'genero_inconsistencia': 'select',
            'opcoes_genero_inconsistencia': ['Material', 'Formal'],
            'situacao': 'select',
            'opcoes_situacao': ['Ativa', 'Inativa'],
            'nivel_gravidade': 'select',
            'opcoes_nivel_gravidade': ['Leve', 'Moderada', 'Grave'],
            'referencia_normativa': 'text',
            'ordem': 'number'
        }
    },
    'c_alt_instrumento': {
        'nome': 'DGP/ALT: Instrumentos Jurídicos para Alterações de Contrato',
        'schema': 'categoricas',
        'colunas_editaveis': ['instrumento_alteracao', 'descricao', 'status'],
        'colunas_obrigatorias': ['instrumento_alteracao'],
        'labels': {
            'instrumento_alteracao': 'Nome do Instrumento',
            'descricao': 'Descrição',
            'status': 'Status'
        },
        'colunas_filtro': ['instrumento_alteracao', 'status'],
        'ordem': 'instrumento_alteracao',
        'tipos_campo': {
            'instrumento_alteracao': 'text',
            'descricao': 'textarea',
            'rows_descricao': 3,
            'status': 'select',
            'opcoes_status': ['ativo', 'inativo']
        },
        'inline_edit': True,
        'inline_columns': ['status']
    },
    'c_alt_tipo': {
        'nome': 'DGP/ALT: Tipos de Alteração de Parceria',
        'schema': 'categoricas',
        'colunas_editaveis': [
            'alt_tipo',
            'alt_modalidade',
            'alt_escopo',
            'alt_campo',
            'alt_fonte_recursos',
            'alt_instrumento',
            'alt_principios',
            'status'
        ],
        'colunas_obrigatorias': ['alt_tipo'],
        'labels': {
            'alt_tipo': 'Tipo de Alteração',
            'alt_modalidade': 'Modalidades Aplicáveis',
            'alt_escopo': 'Escopo da Alteração',
            'alt_campo': 'Campos/Cláusulas Afetados',
            'alt_fonte_recursos': 'Fontes de Recursos',
            'alt_instrumento': 'Instrumentos Jurídicos',
            'alt_principios': 'Princípios Aplicáveis',
            'status': 'Status'
        },
        'colunas_filtro': ['alt_tipo', 'alt_escopo', 'status'],
        'ordem': 'alt_tipo',
        'tipos_campo': {
            'alt_tipo': 'text',
            'alt_modalidade': 'checkbox_multiple',
            'query_alt_modalidade': 'SELECT DISTINCT informacao FROM categoricas.c_geral_tipo_contrato WHERE informacao IS NOT NULL ORDER BY informacao',
            'alt_escopo': 'select',
            'opcoes_alt_escopo': [
                'Termo',
                'Plano',
                'Flutuante (Plano e Termo)',
                'Não aplicável'
            ],
            'alt_campo': 'checkbox_multiple',
            'opcoes_alt_campo': [
                'Preâmbulo do Termo',
                'Cláusulas do Termo',
                'Cronograma de Desembolso',
                'Campos do Plano de Trabalho',
                'Quadro de Metas',
                'Cronograma de Execução',
                'Proposta Orçamentária'
            ],
            'alt_fonte_recursos': 'checkbox_multiple',
            'query_alt_fonte_recursos': 'SELECT DISTINCT descricao FROM categoricas.c_geral_origem_recurso WHERE descricao IS NOT NULL ORDER BY descricao',
            'alt_instrumento': 'checkbox_multiple',
            'query_alt_instrumento': 'SELECT DISTINCT instrumento_alteracao FROM categoricas.c_alt_instrumento WHERE instrumento_alteracao IS NOT NULL ORDER BY instrumento_alteracao',
            'alt_principios': 'checkbox_multiple',
            'query_alt_principios': 'SELECT nome_principio FROM categoricas.c_alt_principios WHERE status = \'ativo\' ORDER BY nome_principio',
            'status': 'select',
            'opcoes_status': ['ativo', 'inativo']
        },
        'inline_edit': True,
        'inline_columns': ['status']
    },
    'c_alt_principios': {
        'nome': 'DGP/ALT: Princípios para Alteração de Parceria',
        'schema': 'categoricas',
        'colunas_editaveis': [
            'nome_principio',
            'descricao_principio',
            'exemplo_principio',
            'status'
        ],
        'colunas_obrigatorias': ['nome_principio'],
        'labels': {
            'nome_principio': 'Nome do Princípio',
            'descricao_principio': 'Descrição do Princípio',
            'exemplo_principio': 'Exemplo de Aplicação',
            'status': 'Status'
        },
        'colunas_filtro': ['nome_principio', 'status'],
        'ordem': 'nome_principio',
        'tipos_campo': {
            'nome_principio': 'text',
            'descricao_principio': 'textarea',
            'rows_descricao_principio': 5,
            'exemplo_principio': 'textarea',
            'rows_exemplo_principio': 5,
            'status': 'select',
            'opcoes_status': ['ativo', 'inativo']
        },
        'inline_edit': True,
        'inline_columns': ['status']
    },
    'c_alt_normas': {
        'nome': 'DGP/ALT: Normas e Regimentos para Alterações',
        'schema': 'categoricas',
        'colunas_editaveis': [
            'norma',
            'regimento',
            'referencia_legal',
            'data_aplicacao',
            'status'
        ],
        'colunas_obrigatorias': ['norma'],
        'labels': {
            'norma': 'Nome da Norma',
            'regimento': 'Regimento/Descrição',
            'referencia_legal': 'Referência Legal',
            'data_aplicacao': 'Data de Aplicação',
            'status': 'Status'
        },
        'colunas_filtro': ['norma', 'referencia_legal', 'status'],
        'ordem': 'norma',
        'tipos_campo': {
            'norma': 'text',
            'regimento': 'textarea',
            'rows_regimento': 10,
            'referencia_legal': 'text',
            'data_aplicacao': 'date',
            'status': 'select',
            'opcoes_status': ['ativo', 'inativo']
        },
        'inline_edit': True,
        'inline_columns': ['status']
    },
    'c_geral_vereadores': {
        'nome': 'Geral: Vereadores e Legislaturas',
        'schema': 'categoricas',
        'colunas_editaveis': ['vereador_nome', 'partido', 'legislatura_inicio', 'legislatura_fim', 'legislatura_numero', 'situacao'],
        'labels': {
            'vereador_nome': 'Nome do Vereador',
            'partido': 'Partido',
            'legislatura_inicio': 'Início da Legislatura',
            'legislatura_fim': 'Fim da Legislatura',
            'legislatura_numero': 'Nº Legislatura',
            'situacao': 'Situação'
        },
        'colunas_filtro': ['vereador_nome', 'partido', 'situacao', 'legislatura_numero'],
        'ordem': 'legislatura_numero DESC NULLS LAST, vereador_nome',
        'tipos_campo': {
            'legislatura_inicio': 'date',
            'legislatura_fim': 'date',
            'legislatura_numero': 'select',
            'opcoes_legislatura_numero': ['19', '18', '17', '16', '15'],
            'auto_fill_legislatura': {
                '17': {'inicio': '2017-01-01', 'fim': '2020-12-31'},
                '18': {'inicio': '2021-01-01', 'fim': '2024-12-31'},
                '19': {'inicio': '2025-01-01', 'fim': '2028-12-31'}
            },
            'situacao': 'select',
            'opcoes_situacao': ['Ativo', 'Suplente', 'Mandato Encerrado', 'Licenciado']
        }
    },
    'c_dac_status_pagamento': {
        'nome': 'DAC: Status de Pagamento',
        'schema': 'categoricas',
        'colunas_editaveis': ['status_principal', 'status_secundario', 'status_descricao'],
        'labels': {
            'status_principal': 'Status Principal',
            'status_secundario': 'Status Secundário',
            'status_descricao': 'Descrição'
        },
        'colunas_filtro': ['status_principal', 'status_secundario'],
        'colunas_ordenacao': ['status_principal', 'status_secundario'],
        'ordem': 'status_principal, status_secundario',
        'tipos_campo': {
            'status_principal': 'text',
            'status_secundario': 'text',
            'status_descricao': 'textarea',
            'rows_status_descricao': 4
        }
    },
    'c_geral_dotacoes': {
        'nome': 'Geral: Dotações Orçamentárias',
        'schema': 'categoricas',
        'colunas_editaveis': ['dotacao_numero', 'programa_aplicacao', 'coordenacao', 'condicoes_termo', 'condicoes_unidade', 'condicoes_osc'],
        'labels': {
            'dotacao_numero': 'Número da Dotação',
            'programa_aplicacao': 'Programa/Aplicação',
            'coordenacao': 'Coordenação',
            'condicoes_termo': 'Condições do Termo',
            'condicoes_unidade': 'Condições da Unidade',
            'condicoes_osc': 'Condições da OSC'
        },
        'colunas_filtro': ['dotacao_numero', 'programa_aplicacao', 'coordenacao'],
        'colunas_ordenacao': ['dotacao_numero', 'coordenacao'],
        'ordem': 'dotacao_numero',
        'tipos_campo': {
            'dotacao_numero': 'text',
            'programa_aplicacao': 'text',
            'coordenacao': 'text',
            'condicoes_termo': 'textarea',
            'rows_condicoes_termo': 5,
            'condicoes_unidade': 'textarea',
            'rows_condicoes_unidade': 5,
            'condicoes_osc': 'textarea',
            'rows_condicoes_osc': 5
        }
    },
    'c_geral_regionalizacao': {
        'nome': 'Geral: Regionalização',
        'schema': 'categoricas',
        'colunas_editaveis': ['codigo_distrital', 'distrito', 'codigo_subprefeitura', 'subprefeitura', 'codigo_regiao', 'regiao'],
        'labels': {
            'codigo_distrital': 'Código Distrital',
            'distrito': 'Distrito',
            'codigo_subprefeitura': 'Código de Subprefeitura',
            'subprefeitura': 'Subprefeitura',
            'codigo_regiao': 'Código de Região',
            'regiao': 'Região'
        },
        'colunas_filtro': ['distrito', 'subprefeitura', 'regiao'],
        'colunas_ordenacao': ['distrito', 'subprefeitura', 'regiao'],
        'ordem': 'distrito',
        'tipos_campo': {
            'codigo_distrital': 'text',
            'distrito': 'text',
            'codigo_subprefeitura': 'text',
            'subprefeitura': 'select_dinamico',
            'query_subprefeitura': 'SELECT DISTINCT subprefeitura FROM categoricas.c_geral_regionalizacao WHERE subprefeitura IS NOT NULL ORDER BY subprefeitura',
            'codigo_regiao': 'text',
            'regiao': 'select_dinamico',
            'query_regiao': 'SELECT DISTINCT regiao FROM categoricas.c_geral_regionalizacao WHERE regiao IS NOT NULL ORDER BY regiao'
        }
    },
    'c_dac_tipos_parcelas': {
        'nome': 'DAC: Tipos de Parcelas',
        'schema': 'categoricas',
        'colunas_editaveis': ['parcela_tipo', 'descricao', 'status'],
        'labels': {
            'parcela_tipo': 'Tipo de Parcela',
            'descricao': 'Descrição',
            'status': 'Status'
        },
        'colunas_filtro': ['parcela_tipo', 'status'],
        'colunas_ordenacao': ['parcela_tipo', 'status'],
        'ordem': 'parcela_tipo',
        'tipos_campo': {
            'parcela_tipo': 'text',
            'descricao': 'textarea',
            'rows_descricao': 4,
            'status': 'select',
            'opcoes_status': ['Ativo', 'Inativo']
        },
        'inline_edit': True,
        'inline_columns': ['status']
    },
    'c_geral_status_documentos': {
        'nome': 'Geral: Status de Documentos Manuais',
        'schema': 'categoricas',
        'colunas_editaveis': ['status_manuais', 'descricao'],
        'colunas_obrigatorias': ['status_manuais'],
        'labels': {
            'status_manuais': 'Status',
            'descricao': 'Descri\u00e7\u00e3o'
        },
        'colunas_filtro': ['status_manuais'],
        'colunas_ordenacao': ['status_manuais'],
        'ordem': 'status_manuais',
        'tipos_campo': {
            'status_manuais': 'text',
            'descricao': 'textarea',
            'rows_descricao': 4
        }
    },
    'c_geral_tipos_documentos_manuais': {
        'nome': 'Geral: Tipos de Documentos Manuais',
        'schema': 'categoricas',
        'colunas_editaveis': ['tipos_documentos', 'descricao'],
        'colunas_obrigatorias': ['tipos_documentos'],
        'labels': {
            'tipos_documentos': 'Tipo de Documento',
            'descricao': 'Descrição'
        },
        'colunas_filtro': ['tipos_documentos'],
        'colunas_ordenacao': ['tipos_documentos'],
        'ordem': 'tipos_documentos',
        'tipos_campo': {
            'tipos_documentos': 'text',
            'descricao': 'textarea',
            'rows_descricao': 4
        }
    },
    'c_geral_eventos': {
        'nome': 'Geral: Tipos de Eventos (Datas Importantes)',
        'schema': 'categoricas',
        'colunas_editaveis': ['nome_data', 'descricao_nome_data', 'status'],
        'colunas_obrigatorias': ['nome_data'],
        'labels': {
            'nome_data': 'Nome do Tipo',
            'descricao_nome_data': 'Descrição',
            'status': 'Status'
        },
        'colunas_filtro': ['nome_data', 'status'],
        'colunas_ordenacao': ['nome_data', 'status'],
        'ordem': 'nome_data',
        'tipos_campo': {
            'nome_data': 'text',
            'descricao_nome_data': 'textarea',
            'rows_descricao_nome_data': 3,
            'status': 'select',
            'opcoes_status': ['ativo', 'inativo']
        }
    },
    'c_geral_certidoes': {
        'nome': 'Geral: Certidões',
        'schema': 'categoricas',
        'colunas_editaveis': [
            'certidao_nome_completo',
            'certidao_nome_resumido',
            'certidao_aplicabilidade',
            'certidao_link',
            'certidao_passos',
            'certidao_prazo',
            'observacoes'
        ],
        'colunas_obrigatorias': ['certidao_nome_completo', 'certidao_nome_resumido'],
        'labels': {
            'certidao_nome_completo': 'Nome Completo da Certidão',
            'certidao_nome_resumido': 'Nome Resumido',
            'certidao_aplicabilidade': 'Aplicabilidade',
            'certidao_link': 'Link/URL',
            'certidao_passos': 'Passos para Obtenção',
            'certidao_prazo': 'Prazo de Validade (dias)',
            'observacoes': 'Observações'
        },
        'colunas_filtro': ['certidao_nome_completo', 'certidao_nome_resumido', 'certidao_aplicabilidade'],
        'colunas_ordenacao': ['certidao_nome_completo', 'certidao_nome_resumido'],
        'ordem': 'certidao_nome_completo',
        'tipos_campo': {
            'certidao_nome_completo': 'text',
            'certidao_nome_resumido': 'text',
            'certidao_aplicabilidade': 'textarea',
            'rows_certidao_aplicabilidade': 4,
            'certidao_link': 'text',
            'certidao_passos': 'textarea',
            'rows_certidao_passos': 6,
            'certidao_prazo': 'number',
            'observacoes': 'textarea',
            'rows_observacoes': 4
        }
    }
}


@listas_bp.route("/", methods=["GET"])
@login_required
@requires_access('listas')
def index():
    """
    Página principal de gerenciamento de listas
    """
    try:
        print("[DEBUG] Acessando rota /listas")
        print(f"[DEBUG] Total de tabelas: {len(TABELAS_CONFIG)}")
        print(f"[DEBUG] Tabelas config: {list(TABELAS_CONFIG.keys())}")
        for chave, config in TABELAS_CONFIG.items():
            print(f"  - {chave}: {config.get('nome', 'SEM NOME')}")
        from flask import session
        tipo_usuario_logado = session.get('tipo_usuario', '')
        return render_template('listas.html', tabelas=TABELAS_CONFIG, tipo_usuario_logado=tipo_usuario_logado)
    except Exception as e:
        print(f"[ERRO] Erro ao renderizar listas.html: {str(e)}")
        import traceback
        traceback.print_exc()
        return f"Erro: {str(e)}", 500


@listas_bp.route("/api/dados/<tabela>", methods=["GET"])
@login_required
@requires_access('listas')
def obter_dados(tabela):
    """
    Retorna os dados de uma tabela específica
    """
    if tabela not in TABELAS_CONFIG:
        return jsonify({'erro': 'Tabela inválida'}), 400
    
    try:
        config = TABELAS_CONFIG[tabela]
        schema = config['schema']
        colunas = ['id'] + config['colunas_editaveis']
        ordem = config['ordem']
        
        cur = get_cursor()
        query = f"""
            SELECT {', '.join(colunas)}
            FROM {schema}.{tabela}
            ORDER BY {ordem}
        """
        cur.execute(query)
        dados = cur.fetchall()
        cur.close()
        
        # DEBUG: Verificar duplicação
        print(f"[DEBUG] Tabela {tabela}: {len(dados)} registros retornados")
        ids = [row['id'] for row in dados]
        print(f"[DEBUG] IDs únicos: {len(set(ids))}")
        if len(ids) != len(set(ids)):
            print(f"[ALERTA] DUPLICAÇÃO DETECTADA em {tabela}!")
            print(f"[DEBUG] IDs duplicados: {[i for i in ids if ids.count(i) > 1]}")
        
        # Converter para lista de dicionários
        resultado = []
        for row in dados:
            item = {'id': row['id']}
            for col in config['colunas_editaveis']:
                # Converter valores booleanos para formato frontend
                valor = row[col]
                item[col] = converter_valor_para_frontend(valor, col)
                
                # Formatar datas para formato brasileiro (DD/MM/YYYY)
                tipos_campo = config.get('tipos_campo', {})
                if valor and (col in ['legislatura_inicio', 'legislatura_fim'] or tipos_campo.get(col) == 'date'):
                    from datetime import date, datetime
                    if isinstance(valor, (date, datetime)):
                        item[col] = valor.strftime('%d/%m/%Y')
            resultado.append(item)
        
        # Se for pessoa_gestora, adicionar contagem de pareceres e parcerias
        if tabela == 'c_geral_pessoa_gestora':
            cur = get_cursor()
            for item in resultado:
                # Contar pareceres
                cur.execute("""
                    SELECT COUNT(*) as total
                    FROM parcerias_analises
                    WHERE responsavel_pg = %s
                """, (item['nome_pg'],))
                contagem = cur.fetchone()
                item['total_pareceres'] = contagem['total'] if contagem else 0
                
                # Contar parcerias (somente a última atribuição de cada termo)
                cur.execute("""
                    SELECT COUNT(DISTINCT numero_termo) as total
                    FROM parcerias_pg pg1
                    WHERE pg1.nome_pg = %s
                    AND pg1.data_de_criacao = (
                        SELECT MAX(pg2.data_de_criacao)
                        FROM parcerias_pg pg2
                        WHERE pg2.numero_termo = pg1.numero_termo
                    )
                """, (item['nome_pg'],))
                contagem_parcerias = cur.fetchone()
                item['total_parcerias'] = contagem_parcerias['total'] if contagem_parcerias else 0
            cur.close()
        
        # Buscar opções dinâmicas para selects e checkboxes múltiplas
        import copy
        config_com_opcoes = copy.deepcopy(config)
        if 'tipos_campo' in config_com_opcoes:
            # Criar lista de itens antes de iterar para evitar modificação durante iteração
            items_list = list(config_com_opcoes['tipos_campo'].items())
            for campo, tipo in items_list:
                # Processar select_dinamico
                if tipo == 'select_dinamico':
                    query_key = f'query_{campo}'
                    if query_key in config_com_opcoes['tipos_campo']:
                        cur = get_cursor()
                        cur.execute(config_com_opcoes['tipos_campo'][query_key])
                        opcoes_raw = cur.fetchall()
                        cur.close()
                        
                        # Extrair valores da primeira coluna
                        opcoes = [list(row.values())[0] for row in opcoes_raw if list(row.values())[0]]
                        config_com_opcoes['tipos_campo'][f'opcoes_{campo}'] = opcoes
                
                # Processar checkbox_multiple com query dinâmica
                elif tipo == 'checkbox_multiple':
                    query_key = f'query_{campo}'
                    opcoes_key = f'opcoes_{campo}'
                    
                    # Se tem query dinâmica, buscar do banco
                    if query_key in config_com_opcoes['tipos_campo']:
                        cur = get_cursor()
                        cur.execute(config_com_opcoes['tipos_campo'][query_key])
                        opcoes_raw = cur.fetchall()
                        cur.close()
                        
                        # Extrair valores da primeira coluna
                        opcoes = [list(row.values())[0] for row in opcoes_raw if list(row.values())[0]]
                        config_com_opcoes['tipos_campo'][f'opcoes_{campo}'] = opcoes
                    
                    # Se já tem opcoes_campo definidas (opções fixas), manter
                    # (não precisa fazer nada, já está na config)
        
        return jsonify({
            'dados': resultado,
            'config': config_com_opcoes
        })
        
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@listas_bp.route("/api/opcoes/<tabela>/<campo>", methods=["GET"])
@login_required
@requires_access('listas')
def obter_opcoes_campo(tabela, campo):
    """
    Retorna as opções dinâmicas de um campo com query definida
    """
    if tabela not in TABELAS_CONFIG:
        return jsonify({'erro': 'Tabela inválida'}), 400
    
    try:
        config = TABELAS_CONFIG[tabela]
        query_key = f'query_{campo}'
        
        # Verificar se há query definida para este campo
        if config.get('tipos_campo') and query_key in config['tipos_campo']:
            query = config['tipos_campo'][query_key]
            
            cur = get_cursor()
            cur.execute(query)
            resultados = cur.fetchall()
            cur.close()
            
            # Retornar lista de valores (primeira coluna do resultado)
            opcoes = [list(row.values())[0] for row in resultados if list(row.values())[0] is not None]
            
            return jsonify({'opcoes': opcoes})
        else:
            # Se não tem query, retornar opções fixas se existirem
            opcoes_key = f'opcoes_{campo}'
            if config.get('tipos_campo') and opcoes_key in config['tipos_campo']:
                return jsonify({'opcoes': config['tipos_campo'][opcoes_key]})
            else:
                return jsonify({'opcoes': []})
    
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@listas_bp.route("/api/dados/<tabela>", methods=["POST"])
@login_required
@requires_access('listas')
def criar_registro(tabela):
    """
    Cria um novo registro na tabela
    """
    if tabela not in TABELAS_CONFIG:
        return jsonify({'erro': 'Tabela inválida'}), 400
    
    try:
        config = TABELAS_CONFIG[tabela]
        schema = config['schema']
        dados = request.json
        
        # Validar campos obrigatórios
        colunas_obrigatorias = config.get('colunas_obrigatorias', config['colunas_editaveis'])
        for col in colunas_obrigatorias:
            if col not in dados or dados[col] is None or str(dados[col]).strip() == '':
                return jsonify({'erro': f'Campo {col} é obrigatório'}), 400
        
        # Se permite reordenação e não tem ordem definida, colocar no final
        if config.get('permite_reordenar') and 'ordem' in config['colunas_editaveis']:
            if 'ordem' not in dados or dados['ordem'] is None or str(dados['ordem']).strip() == '':
                # Buscar maior ordem atual
                cur = get_cursor()
                cur.execute(f"""
                    SELECT COALESCE(MAX(ordem), 0) as max_ordem
                    FROM {schema}.{tabela}
                """)
                resultado = cur.fetchone()
                cur.close()
                
                # Definir nova ordem (10 a mais que a maior)
                dados['ordem'] = (resultado['max_ordem'] or 0) + 10
        
        # Adicionar usuario_registro automaticamente se a tabela tiver essa coluna
        if tabela == 'c_alt_normas':
            from flask import session
            dados['usuario_registro'] = session.get('email', 'sistema')

        # Auto-popular created_por e created_em para tabelas de celebração
        if tabela == 'c_dgp_celebracao_status':
            from flask import session as _sess
            dados['created_por'] = _sess.get('email', 'sistema')
            from datetime import datetime as _dt
            dados['created_em'] = _dt.now()
        if tabela == 'c_dgp_celebracao_substatus':
            from flask import session as _sess
            dados['created_por'] = _sess.get('email', 'sistema')
            from datetime import datetime as _dt
            dados['created_at'] = _dt.now()

        # Auto-popular colunas de auditoria para c_geral_tipos_documentos_manuais
        if tabela == 'c_geral_tipos_documentos_manuais':
            from flask import session as _sess
            from datetime import datetime as _dt
            _now = _dt.now()
            _user = _sess.get('email', 'sistema')
            dados['criado_por'] = _user
            dados['criado_em'] = _now
            dados['atualizado_por'] = _user
            dados['atualizado_em'] = _now
        
        # Montar query de inserção apenas com campos enviados
        colunas_a_inserir = [col for col in config['colunas_editaveis'] if col in dados]
        
        # Adicionar usuario_registro se for c_alt_normas
        if tabela == 'c_alt_normas' and 'usuario_registro' in dados:
            colunas_a_inserir.append('usuario_registro')

        # Adicionar campos auto-populados para tabelas de celebração
        if tabela == 'c_dgp_celebracao_status':
            for _ac in ['created_por', 'created_em']:
                if _ac in dados and _ac not in colunas_a_inserir:
                    colunas_a_inserir.append(_ac)
        if tabela == 'c_dgp_celebracao_substatus':
            for _ac in ['created_por', 'created_at']:
                if _ac in dados and _ac not in colunas_a_inserir:
                    colunas_a_inserir.append(_ac)
        if tabela == 'c_geral_tipos_documentos_manuais':
            for _ac in ['criado_por', 'criado_em', 'atualizado_por', 'atualizado_em']:
                if _ac in dados and _ac not in colunas_a_inserir:
                    colunas_a_inserir.append(_ac)
        
        placeholders = ', '.join(['%s'] * len(colunas_a_inserir))
        
        # Converter valores para formato do banco de dados
        valores = [converter_valor_para_db(dados[col], col, config) for col in colunas_a_inserir]
        
        query = f"""
            INSERT INTO {schema}.{tabela} ({', '.join(colunas_a_inserir)})
            VALUES ({placeholders})
        """
        
        if execute_query(query, valores):
            return jsonify({
                'sucesso': True,
                'mensagem': 'Registro criado com sucesso'
            })
        else:
            return jsonify({'erro': 'Falha ao criar registro no banco'}), 500
        
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@listas_bp.route("/api/dados/<tabela>/<int:id>", methods=["PUT"])
@login_required
@requires_access('listas')
def atualizar_registro(tabela, id):
    """
    Atualiza um registro existente
    """
    if tabela not in TABELAS_CONFIG:
        return jsonify({'erro': 'Tabela inválida'}), 400
    
    try:
        config = TABELAS_CONFIG[tabela]
        schema = config['schema']
        dados = request.json
        
        # Verificar se veio 'campos' (edição inline) ou dados diretos (edição modal)
        campos_a_atualizar = dados.get('campos', dados)
        
        print(f"[DEBUG atualizar_registro] Tabela: {tabela}, ID: {id}")
        print(f"[DEBUG atualizar_registro] Dados recebidos: {dados}")
        print(f"[DEBUG atualizar_registro] Campos a atualizar: {campos_a_atualizar}")
        
        # Se for pessoa_gestora e o nome mudou, precisamos atualizar Parcerias também
        nome_antigo = None
        nome_analista_antigo = None

        if tabela == 'c_dac_analistas' and 'nome_analista' in campos_a_atualizar:
            cur = get_cursor()
            cur.execute(f"SELECT nome_analista FROM {schema}.{tabela} WHERE id = %s", (id,))
            resultado = cur.fetchone()
            if resultado:
                nome_analista_antigo = resultado['nome_analista']
            cur.close()

        if tabela == 'c_geral_pessoa_gestora' and 'nome_pg' in campos_a_atualizar:
            cur = get_cursor()
            cur.execute(f"SELECT nome_pg FROM {schema}.{tabela} WHERE id = %s", (id,))
            resultado = cur.fetchone()
            if resultado:
                nome_antigo = resultado['nome_pg']
            cur.close()
        
        # Montar query de atualização APENAS com os campos enviados
        colunas_validas = []
        valores = []
        
        for campo, valor in campos_a_atualizar.items():
            # Verificar se o campo está nas colunas editáveis
            if campo in config['colunas_editaveis']:
                colunas_validas.append(campo)
                # Converter valor para formato do banco de dados
                valor_convertido = converter_valor_para_db(valor, campo, config)
                valores.append(valor_convertido)
                print(f"[DEBUG atualizar_registro] Campo válido: {campo} = {valor} -> {valor_convertido}")
        
        if not colunas_validas:
            return jsonify({'erro': 'Nenhum campo válido para atualizar'}), 400
        
        # ── Capturar valores antigos para cascata (status/substatus celebração) ──
        status_antigo_valor = None
        status_generico_antigo = None
        substatus_antigo_valor = None

        if tabela == 'c_dgp_celebracao_status' and ('status_novo' in campos_a_atualizar or 'status_generico' in campos_a_atualizar):
            cur = get_cursor()
            cur.execute(f"SELECT status_novo, status_generico FROM {schema}.{tabela} WHERE id = %s", (id,))
            _row_old = cur.fetchone()
            if _row_old:
                status_antigo_valor = _row_old['status_novo']
                status_generico_antigo = _row_old['status_generico']
            cur.close()

        if tabela == 'c_dgp_celebracao_substatus' and 'substatus' in campos_a_atualizar:
            cur = get_cursor()
            cur.execute(f"SELECT substatus FROM {schema}.{tabela} WHERE id = %s", (id,))
            _row_old = cur.fetchone()
            if _row_old:
                substatus_antigo_valor = _row_old['substatus']
            cur.close()

        # Adicionar campos de auditoria para c_geral_tipos_documentos_manuais
        if tabela == 'c_geral_tipos_documentos_manuais':
            from flask import session as _sess
            from datetime import datetime as _dt
            colunas_validas.append('atualizado_por')
            valores.append(_sess.get('email', 'sistema'))
            colunas_validas.append('atualizado_em')
            valores.append(_dt.now())

        set_clause = ', '.join([f"{col} = %s" for col in colunas_validas])
        valores.append(id)
        
        query = f"""
            UPDATE {schema}.{tabela}
            SET {set_clause}
            WHERE id = %s
        """
        
        print(f"[DEBUG atualizar_registro] Query: {query}")
        print(f"[DEBUG atualizar_registro] Valores: {valores}")
        
        if execute_query(query, valores):
            # Se alterou nome do analista DAC, atualizar também em checklist_analista
            if tabela == 'c_dac_analistas' and nome_analista_antigo and nome_analista_antigo != campos_a_atualizar.get('nome_analista'):
                novo_nome = campos_a_atualizar.get('nome_analista')
                execute_query(
                    "UPDATE analises_pc.checklist_analista SET nome_analista = %s WHERE nome_analista = %s",
                    (novo_nome, nome_analista_antigo)
                )
                print(f"[CASCATA] nome_analista atualizado: '{nome_analista_antigo}' → '{novo_nome}' em checklist_analista")

            # Se alterou nome da pessoa gestora, atualizar também na tabela parcerias_analises
            if tabela == 'c_geral_pessoa_gestora' and nome_antigo and nome_antigo != campos_a_atualizar.get('nome_pg'):
                query_parcerias = """
                    UPDATE parcerias_analises
                    SET responsavel_pg = %s
                    WHERE responsavel_pg = %s
                """
                resultado_update = execute_query(query_parcerias, (campos_a_atualizar.get('nome_pg'), nome_antigo))
                print(f"[INFO] Atualizado responsavel_pg de '{nome_antigo}' para '{campos_a_atualizar.get('nome_pg')}' em parcerias_analises")

            # ── Cascata: c_dgp_celebracao_status → celebracao.celebracao_parcerias ──
            if tabela == 'c_dgp_celebracao_status':
                novo_status = campos_a_atualizar.get('status_novo')
                novo_generico = campos_a_atualizar.get('status_generico')

                # Se status_novo mudou, renomear em celebracao_parcerias
                if novo_status and status_antigo_valor and novo_status != status_antigo_valor:
                    execute_query("""
                        UPDATE celebracao.celebracao_parcerias
                        SET status = %s
                        WHERE status = %s
                    """, (novo_status, status_antigo_valor))
                    print(f"[CASCATA] Status renomeado: '{status_antigo_valor}' → '{novo_status}' em celebracao_parcerias")

                # Se status_generico mudou, atualizar celebracao_parcerias para registros com este status
                if novo_generico and novo_generico != status_generico_antigo:
                    # Determinar qual é o status_novo atual (pode ter mudado acima)
                    chave_status = novo_status if novo_status else status_antigo_valor
                    if chave_status:
                        execute_query("""
                            UPDATE celebracao.celebracao_parcerias
                            SET status_generico = %s
                            WHERE status = %s
                        """, (novo_generico, chave_status))
                        print(f"[CASCATA] Status genérico atualizado para '{novo_generico}' onde status = '{chave_status}'")

            # ── Cascata: c_dgp_celebracao_substatus → celebracao.celebracao_parcerias ──
            if tabela == 'c_dgp_celebracao_substatus':
                novo_substatus = campos_a_atualizar.get('substatus')
                if novo_substatus and substatus_antigo_valor and novo_substatus != substatus_antigo_valor:
                    # Substituir dentro de valores separados por ponto-e-vírgula
                    execute_query("""
                        UPDATE celebracao.celebracao_parcerias
                        SET substatus = array_to_string(
                            ARRAY(
                                SELECT CASE
                                    WHEN TRIM(elem) = %s THEN %s
                                    ELSE TRIM(elem)
                                END
                                FROM unnest(string_to_array(substatus, ';')) AS elem
                            ), ';'
                        )
                        WHERE substatus LIKE '%%' || %s || '%%'
                    """, (substatus_antigo_valor, novo_substatus, substatus_antigo_valor))
                    print(f"[CASCATA] Substatus substituído: '{substatus_antigo_valor}' → '{novo_substatus}' em celebracao_parcerias")

            return jsonify({
                'sucesso': True,
                'mensagem': 'Registro atualizado com sucesso'
            })
        else:
            return jsonify({'erro': 'Falha ao atualizar registro no banco'}), 500
        
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@listas_bp.route("/api/dados/<tabela>/<int:id>", methods=["DELETE"])
@login_required
@requires_access('listas')
def excluir_registro(tabela, id):
    """
    Exclui um registro
    """
    if tabela not in TABELAS_CONFIG:
        return jsonify({'erro': 'Tabela inválida'}), 400
    
    try:
        config = TABELAS_CONFIG[tabela]
        schema = config['schema']
        
        query = f"""
            DELETE FROM {schema}.{tabela}
            WHERE id = %s
        """
        
        if execute_query(query, (id,)):
            return jsonify({
                'sucesso': True,
                'mensagem': 'Registro excluído com sucesso'
            })
        else:
            return jsonify({'erro': 'Falha ao excluir registro no banco'}), 500
        
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@listas_bp.route("/api/dados/<tabela>/salvar-lote", methods=["POST"])
@login_required
@requires_access('listas')
def salvar_lote(tabela):
    """
    Salva múltiplos registros de uma vez (edição inline em lote)
    """
    if tabela not in TABELAS_CONFIG:
        return jsonify({'erro': 'Tabela inválida'}), 400
    
    try:
        dados = request.json
        registros = dados.get('registros', [])
        
        print(f"[DEBUG salvar_lote] Tabela: {tabela}")
        print(f"[DEBUG salvar_lote] Registros recebidos: {registros}")
        
        if not registros:
            return jsonify({'erro': 'Nenhum registro para salvar'}), 400
        
        config = TABELAS_CONFIG[tabela]
        schema = config['schema']
        
        # Processar cada registro
        erros = []
        sucesso_count = 0
        
        for registro in registros:
            reg_id = registro.get('id')
            campos = registro.get('campos', {})
            
            print(f"[DEBUG salvar_lote] Processando ID {reg_id}, campos: {campos}")
            
            if not reg_id or not campos:
                continue
            
            # Montar query de update
            sets = []
            valores = []
            for campo, valor in campos.items():
                if campo in config['colunas_editaveis']:
                    sets.append(f"{campo} = %s")
                    valores.append(valor)
                    print(f"[DEBUG salvar_lote] Campo {campo} = {valor} (tipo: {type(valor)})")
            
            if not sets:
                continue
            
            valores.append(reg_id)
            query = f"""
                UPDATE {schema}.{tabela}
                SET {', '.join(sets)}
                WHERE id = %s
            """
            
            print(f"[DEBUG salvar_lote] Query: {query}")
            print(f"[DEBUG salvar_lote] Valores: {tuple(valores)}")
            
            if execute_query(query, tuple(valores)):
                sucesso_count += 1
            else:
                erros.append(f"Falha ao atualizar registro ID {reg_id}")
        
        if erros:
            return jsonify({
                'sucesso': True,
                'parcial': True,
                'sucesso_count': sucesso_count,
                'mensagem': f'{sucesso_count} registros salvos. Alguns falharam.',
                'erros': erros
            })
        else:
            return jsonify({
                'sucesso': True,
                'sucesso_count': sucesso_count,
                'mensagem': f'{sucesso_count} registro(s) salvo(s) com sucesso'
            })
        
    except Exception as e:
        print(f"[ERRO salvar_lote] {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'erro': str(e)}), 500


@listas_bp.route("/api/dados/<tabela>/<int:id>/mover", methods=["POST"])
@login_required
@requires_access('listas')
def mover_item(tabela, id):
    """
    Move um item para cima ou para baixo na ordenação
    """
    if tabela not in TABELAS_CONFIG:
        return jsonify({'erro': 'Tabela inválida'}), 400
    
    config = TABELAS_CONFIG[tabela]
    
    if not config.get('permite_reordenar'):
        return jsonify({'erro': 'Tabela não permite reordenação'}), 400
    
    try:
        dados = request.json
        direcao = dados.get('direcao')  # 'cima' ou 'baixo'
        
        if direcao not in ['cima', 'baixo']:
            return jsonify({'erro': 'Direção inválida'}), 400
        
        schema = config['schema']
        cur = get_cursor()
        
        # Buscar todos os registros ordenados
        cur.execute(f"""
            SELECT id, ordem
            FROM {schema}.{tabela}
            ORDER BY ordem NULLS LAST, id
        """)
        registros = cur.fetchall()
        
        # Encontrar posição atual
        posicao_atual = None
        for idx, reg in enumerate(registros):
            if reg['id'] == id:
                posicao_atual = idx
                break
        
        if posicao_atual is None:
            cur.close()
            return jsonify({'erro': 'Registro não encontrado'}), 404
        
        # Calcular nova posição
        if direcao == 'cima':
            nova_posicao = max(0, posicao_atual - 1)
        else:  # baixo
            nova_posicao = min(len(registros) - 1, posicao_atual + 1)
        
        # Se não mudou, retornar
        if nova_posicao == posicao_atual:
            cur.close()
            return jsonify({'sucesso': True, 'mensagem': 'Item já está no limite'})
        
        # Trocar posições
        registros[posicao_atual], registros[nova_posicao] = registros[nova_posicao], registros[posicao_atual]
        
        # Renumerar todos os registros (ordem de 10 em 10 para facilitar inserções futuras)
        for idx, reg in enumerate(registros):
            nova_ordem = (idx + 1) * 10
            execute_query(f"""
                UPDATE {schema}.{tabela}
                SET ordem = %s
                WHERE id = %s
            """, (nova_ordem, reg['id']))
        
        cur.close()
        
        return jsonify({
            'sucesso': True,
            'mensagem': 'Item movido com sucesso'
        })
        
    except Exception as e:
        print(f"[ERRO mover_item] {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'erro': str(e)}), 500


# ── Contatos de Vereadores ─────────────────────────────────────────────────

@listas_bp.route("/vereadores/contatos/<path:vereador_nome>", methods=["GET"])
@login_required
@requires_access('listas')
def listar_contatos_vereador(vereador_nome):
    """Retorna todos os contatos de um vereador"""
    try:
        cur = get_cursor()
        cur.execute("""
            SELECT id, vereador_nome, contato_nome, contato_posicao, contato_tipo,
                   contato_info, status, observacao, responsavel, criado_em
            FROM public.contatos_vereadores
            WHERE vereador_nome = %s
            ORDER BY status DESC, contato_nome
        """, (vereador_nome,))
        contatos = cur.fetchall()
        contatos_fmt = []
        for c in contatos:
            d = dict(c)
            d['criado_em'] = d['criado_em'].strftime('%d/%m/%Y %H:%M') if d.get('criado_em') else '-'
            contatos_fmt.append(d)
        return jsonify({'contatos': contatos_fmt}), 200
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@listas_bp.route("/vereadores/contatos/criar", methods=["POST"])
@login_required
@requires_access('listas')
def criar_contato_vereador():
    """Cria um novo contato de vereador"""
    try:
        data = request.get_json()
        vereador_nome = (data.get('vereador_nome') or '').strip()
        c = data.get('contato', {})
        contato_nome = (c.get('nome') or '').strip()
        contato_posicao = (c.get('posicao') or '').strip() or None
        contato_tipo = (c.get('tipo') or '').strip()
        contato_info = (c.get('info') or '').strip()
        status = (c.get('status') or 'Ativo').strip()
        observacao = (c.get('observacao') or '').strip() or None
        responsavel = session.get('d_usuario', 'sistema')

        if not vereador_nome or not contato_nome or not contato_tipo or not contato_info:
            return jsonify({'erro': 'Campos obrigatórios: Vereador, Nome do contato, Tipo e Informação'}), 400

        cur = get_cursor()
        cur.execute("""
            INSERT INTO public.contatos_vereadores
                (vereador_nome, contato_nome, contato_posicao, contato_tipo,
                 contato_info, status, observacao, responsavel, criado_em)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """, (vereador_nome, contato_nome, contato_posicao, contato_tipo,
              contato_info, status, observacao, responsavel))
        get_db().commit()
        return jsonify({'mensagem': 'Contato adicionado com sucesso!'}), 200
    except Exception as e:
        get_db().rollback()
        return jsonify({'erro': str(e)}), 500


@listas_bp.route("/vereadores/contatos/editar/<int:id>", methods=["POST"])
@login_required
@requires_access('listas')
def editar_contato_vereador(id):
    """Edita um contato de vereador existente"""
    try:
        data = request.get_json()
        contato_nome = (data.get('contato_nome') or '').strip()
        contato_posicao = (data.get('contato_posicao') or '').strip() or None
        contato_tipo = (data.get('contato_tipo') or '').strip()
        contato_info = (data.get('contato_info') or '').strip()
        status = (data.get('status') or 'Ativo').strip()
        observacao = (data.get('observacao') or '').strip() or None

        if not contato_nome or not contato_tipo or not contato_info:
            return jsonify({'erro': 'Campos obrigatórios: Nome, Tipo e Informação de Contato'}), 400

        cur = get_cursor()
        cur.execute("""
            UPDATE public.contatos_vereadores
            SET contato_nome = %s, contato_posicao = %s, contato_tipo = %s,
                contato_info = %s, status = %s, observacao = %s
            WHERE id = %s
        """, (contato_nome, contato_posicao, contato_tipo, contato_info, status, observacao, id))
        if cur.rowcount == 0:
            return jsonify({'erro': 'Contato não encontrado'}), 404
        get_db().commit()
        return jsonify({'mensagem': 'Contato atualizado com sucesso!'}), 200
    except Exception as e:
        get_db().rollback()
        return jsonify({'erro': str(e)}), 500


@listas_bp.route("/vereadores/contatos/deletar/<int:id>", methods=["POST"])
@login_required
@requires_access('listas')
def deletar_contato_vereador(id):
    """Exclui um contato de vereador"""
    try:
        cur = get_cursor()
        cur.execute("DELETE FROM public.contatos_vereadores WHERE id = %s", (id,))
        if cur.rowcount == 0:
            return jsonify({'erro': 'Contato não encontrado'}), 404
        get_db().commit()
        return jsonify({'mensagem': 'Contato excluído com sucesso!'}), 200
    except Exception as e:
        get_db().rollback()
        return jsonify({'erro': str(e)}), 500


# =============================================================================
# STATUS CATEGÓRICOS (c_geral_status)
# =============================================================================

@listas_bp.route("/status-categoricos", methods=["GET"], endpoint="status_categoricos")
@login_required
@requires_access('listas')
def status_categoricos():
    """Página de gerenciamento das listas de status categóricos."""
    return render_template('status_categoricos.html')


@listas_bp.route("/api/status-cat/listas", methods=["GET"])
@login_required
@requires_access('listas')
def status_cat_listar_grupos():
    """Retorna todos os grupos (schema_table_coluna_r distintos) com contagem."""
    try:
        cur = get_cursor()
        cur.execute("""
            SELECT schema_table_coluna_r AS lista, COUNT(*) AS total
            FROM categoricas.c_geral_status
            GROUP BY schema_table_coluna_r
            ORDER BY schema_table_coluna_r
        """)
        rows = cur.fetchall()
        cur.close()
        return jsonify([{'lista': r['lista'], 'total': r['total']} for r in rows])
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@listas_bp.route("/api/status-cat/itens", methods=["GET"])
@login_required
@requires_access('listas')
def status_cat_listar_itens():
    """Retorna todos os itens de um grupo específico."""
    try:
        lista = request.args.get('lista', '').strip()
        if not lista:
            return jsonify([])
        cur = get_cursor()
        cur.execute("""
            SELECT id, status, descricao, ativo
            FROM categoricas.c_geral_status
            WHERE schema_table_coluna_r = %s
            ORDER BY id
        """, (lista,))
        rows = cur.fetchall()
        cur.close()
        return jsonify([{'id': r['id'], 'status': r['status'], 'descricao': r['descricao'] or '', 'ativo': r['ativo']} for r in rows])
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@listas_bp.route("/api/status-cat/itens", methods=["POST"])
@login_required
@requires_access('listas')
def status_cat_criar_item():
    """Cria um novo item em um grupo."""
    try:
        data = request.get_json(force=True)
        lista   = (data.get('lista')   or '').strip()
        status  = (data.get('status')  or '').strip()
        descricao = (data.get('descricao') or '').strip() or None
        if not lista or not status:
            return jsonify({'erro': 'Campos "lista" e "status" são obrigatórios'}), 400
        cur = get_cursor()
        cur.execute("""
            INSERT INTO categoricas.c_geral_status (schema_table_coluna_r, status, descricao)
            VALUES (%s, %s, %s) RETURNING id
        """, (lista, status, descricao))
        novo_id = cur.fetchone()['id']
        get_db().commit()
        cur.close()
        return jsonify({'id': novo_id, 'status': status, 'descricao': descricao or ''}), 201
    except Exception as e:
        get_db().rollback()
        return jsonify({'erro': str(e)}), 500


@listas_bp.route("/api/status-cat/itens/<int:item_id>", methods=["PUT"])
@login_required
@requires_access('listas')
def status_cat_editar_item(item_id):
    """Atualiza status, descrição e/ou ativo de um item."""
    try:
        data = request.get_json(force=True)
        status    = (data.get('status')    or '').strip()
        descricao = (data.get('descricao') or '').strip() or None
        ativo     = data.get('ativo')

        # Toggle rápido de ativo (apenas esse campo)
        if ativo is not None and 'status' not in data:
            cur = get_cursor()
            cur.execute("""
                UPDATE categoricas.c_geral_status
                SET ativo = %s, atualizado_em = now()
                WHERE id = %s
            """, (bool(ativo), item_id))
            if cur.rowcount == 0:
                get_db().rollback()
                return jsonify({'erro': 'Item não encontrado'}), 404
            get_db().commit()
            cur.close()
            return jsonify({'ok': True})

        if not status:
            return jsonify({'erro': 'O campo "status" é obrigatório'}), 400
        cur = get_cursor()
        cur.execute("""
            UPDATE categoricas.c_geral_status
            SET status = %s, descricao = %s,
                ativo = COALESCE(%s, ativo),
                atualizado_em = now()
            WHERE id = %s
        """, (status, descricao, None if ativo is None else bool(ativo), item_id))
        if cur.rowcount == 0:
            get_db().rollback()
            return jsonify({'erro': 'Item não encontrado'}), 404
        get_db().commit()
        cur.close()
        return jsonify({'ok': True})
    except Exception as e:
        get_db().rollback()
        return jsonify({'erro': str(e)}), 500


@listas_bp.route("/api/status-cat/itens/<int:item_id>", methods=["DELETE"])
@login_required
@requires_access('listas')
def status_cat_excluir_item(item_id):
    """Exclui um item pelo id."""
    try:
        cur = get_cursor()
        cur.execute("DELETE FROM categoricas.c_geral_status WHERE id = %s", (item_id,))
        if cur.rowcount == 0:
            return jsonify({'erro': 'Item não encontrado'}), 404
        get_db().commit()
        cur.close()
        return jsonify({'ok': True})
    except Exception as e:
        get_db().rollback()
        return jsonify({'erro': str(e)}), 500


@listas_bp.route("/api/status-cat/listas", methods=["POST"])
@login_required
@requires_access('listas')
def status_cat_criar_lista():
    """Cria uma nova lista (schema_table_coluna_r) com o primeiro item."""
    try:
        data = request.get_json(force=True)
        lista   = (data.get('lista')   or '').strip()
        status  = (data.get('status')  or '').strip()
        descricao = (data.get('descricao') or '').strip() or None
        if not lista or not status:
            return jsonify({'erro': 'Nome da lista e primeiro valor são obrigatórios'}), 400
        cur = get_cursor()
        # Verificar se já existe
        cur.execute("SELECT 1 FROM categoricas.c_geral_status WHERE schema_table_coluna_r = %s LIMIT 1", (lista,))
        if cur.fetchone():
            return jsonify({'erro': 'Já existe uma lista com esse nome'}), 409
        cur.execute("""
            INSERT INTO categoricas.c_geral_status (schema_table_coluna_r, status, descricao)
            VALUES (%s, %s, %s) RETURNING id
        """, (lista, status, descricao))
        novo_id = cur.fetchone()['id']
        get_db().commit()
        cur.close()
        return jsonify({'id': novo_id, 'lista': lista, 'status': status}), 201
    except Exception as e:
        get_db().rollback()
        return jsonify({'erro': str(e)}), 500


@listas_bp.route("/api/status-cat/listas", methods=["DELETE"])
@login_required
@requires_access('listas')
def status_cat_excluir_lista():
    """Exclui todos os itens de uma lista inteira."""
    try:
        lista = request.args.get('lista', '').strip()
        if not lista:
            return jsonify({'erro': 'Parâmetro "lista" é obrigatório'}), 400
        cur = get_cursor()
        cur.execute("DELETE FROM categoricas.c_geral_status WHERE schema_table_coluna_r = %s", (lista,))
        total = cur.rowcount
        get_db().commit()
        cur.close()
        return jsonify({'ok': True, 'excluidos': total})
    except Exception as e:
        get_db().rollback()
        return jsonify({'erro': str(e)}), 500


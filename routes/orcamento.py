"""
Blueprint de orçamento (listagem e edição)
"""

from flask import Blueprint, render_template, request, Response, jsonify
from db import get_cursor
from utils import login_required
from decorators import requires_access
import csv
from io import StringIO
from datetime import datetime

orcamento_bp = Blueprint('orcamento', __name__, url_prefix='/orcamento')


@orcamento_bp.route("/", methods=["GET"])
@login_required
@requires_access('orcamento')
def listar():
    """
    Listagem de parcerias/termos com estatísticas de preenchimento
    """
    # Obter parâmetro de paginação (padrão: 100)
    limite = request.args.get('limite', '100')
    if limite == 'todas':
        limite_sql = None
    else:
        try:
            limite_sql = int(limite)
        except ValueError:
            limite_sql = 100
    
    # Obter filtro de termo
    filtro_termo = request.args.get('filtro_termo', '').strip()
    
    # Obter filtro de status (correto, nao_feito, incorreto)
    filtro_status = request.args.get('status', '').strip()
    
    cur = get_cursor()
    
    # Base da query com filtros
    query_base = """
        SELECT 
            p.numero_termo,
            p.tipo_termo,
            p.meses,
            p.sei_celeb,
            p.total_previsto,
            COALESCE(SUM(pd.valor), 0) as total_preenchido
        FROM Parcerias p
        LEFT JOIN Parcerias_Despesas pd ON p.numero_termo = pd.numero_termo
        WHERE p.tipo_termo NOT IN ('Convênio de Cooperação', 'Convênio', 'Convênio - Passivo', 'Acordo de Cooperação')
    """
    
    params = []
    
    # Adicionar filtro de termo se fornecido
    if filtro_termo:
        query_base += " AND p.numero_termo ILIKE %s"
        params.append(f"%{filtro_termo}%")
    
    query_base += """
        GROUP BY p.numero_termo, p.tipo_termo, p.meses, p.sei_celeb, p.total_previsto
    """
    
    # PRIMEIRO: Calcular estatísticas sobre TODAS as parcerias (sem LIMIT)
    query_estatisticas = query_base  # Query sem LIMIT para estatísticas corretas
    cur.execute(query_estatisticas, params)
    todas_parcerias = cur.fetchall()
    
    total_parcerias = len(todas_parcerias)
    nao_feito = 0
    feito_corretamente = 0
    feito_incorretamente = 0
    
    for parceria in todas_parcerias:
        total_previsto = float(parceria["total_previsto"] or 0)
        total_preenchido = float(parceria["total_preenchido"] or 0)
        
        if total_preenchido == 0:
            nao_feito += 1
        elif abs(total_preenchido - total_previsto) < 0.01:  # tolerância para igualdade
            feito_corretamente += 1
        else:
            feito_incorretamente += 1
    
    # Calcular percentuais baseados no total REAL
    estatisticas = {
        'feito_corretamente': {
            'quantidade': feito_corretamente,
            'percentual': (feito_corretamente / total_parcerias * 100) if total_parcerias > 0 else 0
        },
        'nao_feito': {
            'quantidade': nao_feito,
            'percentual': (nao_feito / total_parcerias * 100) if total_parcerias > 0 else 0
        },
        'feito_incorretamente': {
            'quantidade': feito_incorretamente,
            'percentual': (feito_incorretamente / total_parcerias * 100) if total_parcerias > 0 else 0
        }
    }
    
    # SEGUNDO: Query para exibição com filtro de status (se aplicável)
    # Aplicar filtro de status nas parcerias já calculadas em memória
    if filtro_status:
        parcerias_filtradas = []
        for parceria in todas_parcerias:
            total_previsto = float(parceria["total_previsto"] or 0)
            total_preenchido = float(parceria["total_preenchido"] or 0)
            
            incluir = False
            if filtro_status == 'correto':
                # Feito corretamente: totais iguais (tolerância 0.01)
                incluir = total_preenchido > 0 and abs(total_preenchido - total_previsto) < 0.01
            elif filtro_status == 'nao_feito':
                # Não feito: total preenchido = 0
                incluir = total_preenchido == 0
            elif filtro_status == 'incorreto':
                # Feito incorretamente: total preenchido > 0 mas diferente do previsto
                incluir = total_preenchido > 0 and abs(total_preenchido - total_previsto) >= 0.01
            
            if incluir:
                parcerias_filtradas.append(parceria)
        
        # Aplicar limite nas parcerias filtradas
        if limite_sql is not None:
            parcerias = parcerias_filtradas[:limite_sql]
        else:
            parcerias = parcerias_filtradas
    else:
        # Sem filtro de status: usar query com limite normal
        query_exibicao = query_base + " ORDER BY p.numero_termo"
        
        # Adicionar LIMIT apenas para exibição se não for "todas"
        if limite_sql is not None:
            query_exibicao += f" LIMIT {limite_sql}"
        
        cur.execute(query_exibicao, params)
        parcerias = cur.fetchall()
    
    cur.close()
    
    return render_template("orcamento_1.html", 
                         parcerias=parcerias, 
                         estatisticas=estatisticas,
                         limite=limite,
                         filtro_termo=filtro_termo,
                         filtro_status=filtro_status)


@orcamento_bp.route('/editar/<path:numero_termo>')
@login_required
@requires_access('orcamento')
def editar(numero_termo):
    """
    Editor de orçamento para um termo específico
    """
    cur = get_cursor()
    
    # Buscar total_previsto e sei_celeb para exibir no subtítulo
    cur.execute("SELECT total_previsto, sei_celeb FROM Parcerias WHERE numero_termo = %s", (numero_termo,))
    row = cur.fetchone()
    
    try:
        total_previsto_val = float(row['total_previsto']) if row and row['total_previsto'] is not None else 0.0
    except Exception:
        total_previsto_val = 0.0
    
    # Obter SEI de celebração
    sei_celeb = row['sei_celeb'] if row and row.get('sei_celeb') else None
    
    # formatar em pt-BR: R$ 1.234.567,89
    formatted_total = 'R$ ' + f"{total_previsto_val:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    
    # Buscar aditivos disponíveis para este termo
    cur.execute("""
        SELECT DISTINCT COALESCE(aditivo, 0) as aditivo
        FROM Parcerias_Despesas
        WHERE numero_termo = %s
        ORDER BY aditivo
    """, (numero_termo,))
    aditivos_rows = cur.fetchall()
    aditivos = [row['aditivo'] for row in aditivos_rows] if aditivos_rows else [0]
    
    # Se não houver aditivos, garantir que pelo menos o Base (0) está disponível
    if not aditivos:
        aditivos = [0]
    
    cur.close()
    
    return render_template('orcamento_2.html', 
                         numero_termo=numero_termo, 
                         total_previsto=formatted_total, 
                         total_previsto_val=total_previsto_val,
                         sei_celeb=sei_celeb,
                         aditivos=aditivos)


@orcamento_bp.route('/dicionario-despesas')
@login_required
@requires_access('orcamento')
def dicionario_despesas():
    """
    Exibe dicionário de categorias de despesas com suas rubricas mais comuns
    Suporta paginação: 200 registros por página
    """
    # Obter número da página (padrão: 1)
    pagina = request.args.get('pagina', 1, type=int)
    por_pagina = 200
    offset = (pagina - 1) * por_pagina
    
    cur = get_cursor()
    
    # PRIMEIRO: Contar total de categorias para calcular número de páginas
    cur.execute("""
        SELECT COUNT(DISTINCT categoria_despesa) as total
        FROM Parcerias_Despesas
        WHERE categoria_despesa IS NOT NULL AND categoria_despesa != ''
    """)
    total_categorias = cur.fetchone()['total']
    total_paginas = (total_categorias + por_pagina - 1) // por_pagina  # Ceil division
    
    # SEGUNDO: Buscar categorias da página atual com LIMIT e OFFSET
    cur.execute("""
        WITH categoria_stats AS (
            SELECT 
                categoria_despesa,
                COUNT(*) as total_ocorrencias,
                COUNT(DISTINCT numero_termo) as total_termos
            FROM Parcerias_Despesas
            WHERE categoria_despesa IS NOT NULL AND categoria_despesa != ''
            GROUP BY categoria_despesa
        ),
        rubrica_mais_comum AS (
            SELECT DISTINCT ON (categoria_despesa)
                categoria_despesa,
                rubrica,
                COUNT(*) as freq_rubrica
            FROM Parcerias_Despesas
            WHERE categoria_despesa IS NOT NULL AND categoria_despesa != ''
                AND rubrica IS NOT NULL AND rubrica != ''
            GROUP BY categoria_despesa, rubrica
            ORDER BY categoria_despesa, freq_rubrica DESC
        )
        SELECT 
            cs.categoria_despesa,
            cs.total_ocorrencias,
            cs.total_termos,
            COALESCE(rmc.rubrica, '') as rubrica_comum
        FROM categoria_stats cs
        LEFT JOIN rubrica_mais_comum rmc ON cs.categoria_despesa = rmc.categoria_despesa
        ORDER BY cs.categoria_despesa
        LIMIT %s OFFSET %s
    """, (por_pagina, offset))
    
    categorias = cur.fetchall()
    cur.close()
    
    return render_template('orcamento_3_dict.html', 
                         categorias=categorias,
                         pagina_atual=pagina,
                         total_paginas=total_paginas,
                         total_categorias=total_categorias)


@orcamento_bp.route('/atualizar-categoria', methods=['POST'])
@login_required
@requires_access('orcamento')
def atualizar_categoria():
    """
    Atualiza em massa uma categoria de despesa no banco de dados
    """
    from flask import request, jsonify
    from db import execute_query
    
    try:
        data = request.get_json()
        categoria_antiga = data.get('categoria_antiga')
        categoria_nova = data.get('categoria_nova')
        
        if not categoria_antiga:
            return jsonify({"error": "Categoria antiga é obrigatória"}), 400
        
        if not categoria_nova or categoria_nova.strip() == '':
            return jsonify({"error": "Categoria nova não pode estar vazia"}), 400
        
        # Atualizar todas as ocorrências da categoria antiga para a nova
        query = """
            UPDATE Parcerias_Despesas
            SET categoria_despesa = %s
            WHERE categoria_despesa = %s
        """
        
        if execute_query(query, (categoria_nova.strip(), categoria_antiga)):
            return jsonify({
                "message": f"Categoria atualizada com sucesso!",
                "categoria_antiga": categoria_antiga,
                "categoria_nova": categoria_nova.strip()
            }), 200
        else:
            return jsonify({"error": "Falha ao atualizar categoria em ambos os bancos"}), 500
        
    except Exception as e:
        return jsonify({"error": f"Erro: {str(e)}"}), 500


@orcamento_bp.route('/buscar-categorias', methods=['GET'])
@login_required
@requires_access('orcamento')
def buscar_categorias():
    """
    API para busca global de categorias.
    Parâmetros: 
    - q: termo de busca (opcional)
    Retorna categorias filtradas com estatísticas
    """
    from flask import request, jsonify
    from db import get_db
    import psycopg2.extras
    
    try:
        termo_busca = request.args.get('q', '').strip()
        
        db = get_db()
        cur = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        # Query base com estatísticas
        query = """
            WITH categorias_stats AS (
                SELECT 
                    categoria_despesa,
                    COUNT(*) as total_ocorrencias,
                    COUNT(DISTINCT numero_termo) as total_termos
                FROM Parcerias_Despesas
                WHERE categoria_despesa IS NOT NULL
                GROUP BY categoria_despesa
            ),
            rubrica_comum AS (
                SELECT DISTINCT ON (pd.categoria_despesa)
                    pd.categoria_despesa,
                    pd.rubrica,
                    COUNT(*) OVER (PARTITION BY pd.categoria_despesa, pd.rubrica) as freq
                FROM Parcerias_Despesas pd
                WHERE pd.categoria_despesa IS NOT NULL AND pd.rubrica IS NOT NULL
                ORDER BY pd.categoria_despesa, freq DESC, pd.rubrica
            )
            SELECT 
                cs.categoria_despesa,
                cs.total_ocorrencias,
                cs.total_termos,
                rc.rubrica as rubrica_comum
            FROM categorias_stats cs
            LEFT JOIN rubrica_comum rc ON cs.categoria_despesa = rc.categoria_despesa
        """
        
        params = []
        
        # Adicionar filtro de busca se fornecido
        if termo_busca:
            query += " WHERE LOWER(cs.categoria_despesa) LIKE LOWER(%s)"
            params.append(f'%{termo_busca}%')
        
        query += " ORDER BY cs.categoria_despesa LIMIT 200"
        
        cur.execute(query, params)
        categorias = cur.fetchall()
        cur.close()
        
        # Converter para lista de dicionários
        resultado = []
        for cat in categorias:
            resultado.append({
                'categoria_despesa': cat['categoria_despesa'],
                'total_ocorrencias': cat['total_ocorrencias'],
                'total_termos': cat['total_termos'],
                'rubrica_comum': cat['rubrica_comum']
            })
        
        return jsonify({
            'categorias': resultado,
            'total': len(resultado),
            'termo_busca': termo_busca
        }), 200
        
    except psycopg2.Error as e:
        return jsonify({"error": f"Erro no banco de dados: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"Erro: {str(e)}"}), 500


@orcamento_bp.route('/termos-por-categoria/<path:categoria>', methods=['GET'])
@login_required
@requires_access('orcamento')
def termos_por_categoria(categoria):
    """
    API para buscar todos os termos (numero_termo) que usam uma categoria específica.
    Retorna lista de termos com informações adicionais.
    """
    from flask import jsonify
    
    try:
        cur = get_cursor()
        
        # Buscar termos distintos que usam essa categoria
        cur.execute("""
            SELECT DISTINCT 
                numero_termo,
                COUNT(*) as total_despesas,
                SUM(valor) as valor_total
            FROM Parcerias_Despesas
            WHERE categoria_despesa = %s
            GROUP BY numero_termo
            ORDER BY numero_termo
        """, (categoria,))
        
        termos = cur.fetchall()
        cur.close()
        
        # Converter para lista de dicionários
        resultado = []
        for termo in termos:
            resultado.append({
                'numero_termo': termo['numero_termo'],
                'total_despesas': termo['total_despesas'],
                'valor_total': float(termo['valor_total']) if termo['valor_total'] else 0
            })
        
        return jsonify({
            'categoria': categoria,
            'termos': resultado,
            'total_termos': len(resultado)
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Erro ao buscar termos: {str(e)}"}), 500


@orcamento_bp.route("/exportar-termo-csv", methods=["GET"])
@login_required
@requires_access('orcamento')
def exportar_termo_csv():
    """
    Exporta os dados de orçamento preenchidos de UM termo específico para CSV
    """
    try:
        # Obter número do termo e aditivo da query string
        numero_termo = request.args.get('numero_termo', '').strip()
        aditivo = request.args.get('aditivo', 0, type=int)
        
        if not numero_termo:
            return "Número do termo não informado", 400
        
        cur = get_cursor()
        
        # Buscar dados da parceria
        cur.execute("""
            SELECT total_previsto, sei_celeb, tipo_termo
            FROM Parcerias 
            WHERE numero_termo = %s
        """, (numero_termo,))
        parceria = cur.fetchone()
        
        if not parceria:
            cur.close()
            return "Termo não encontrado", 404
        
        # Buscar despesas do termo com o aditivo selecionado
        cur.execute("""
            SELECT 
                rubrica,
                quantidade,
                categoria_despesa,
                mes,
                valor
            FROM Parcerias_Despesas
            WHERE numero_termo = %s AND COALESCE(aditivo, 0) = %s
            ORDER BY rubrica, categoria_despesa, mes
        """, (numero_termo, aditivo))
        
        despesas = cur.fetchall()
        cur.close()
        
        # Criar arquivo CSV em memória com BOM UTF-8 para Excel
        output = StringIO()
        # Adicionar BOM UTF-8 para que Excel reconheça acentuação corretamente
        output.write('\ufeff')
        writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)
        
        # Cabeçalho do arquivo
        writer.writerow(['ORÇAMENTO ANUAL - ' + numero_termo])
        writer.writerow([f'Aditivo: {"Base" if aditivo == 0 else f"Aditivo {aditivo}"}'])
        writer.writerow([f'Total Previsto: R$ {float(parceria["total_previsto"] or 0):,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')])
        if parceria['sei_celeb']:
            writer.writerow([f'SEI Celebração: {parceria["sei_celeb"]}'])
        writer.writerow([])  # Linha em branco
        
        # Agrupar despesas por rubrica, quantidade e categoria
        # Estrutura: {(rubrica, quantidade, categoria): {mes: valor}}
        from collections import defaultdict
        dados_agrupados = defaultdict(dict)
        todos_meses = set()
        
        for despesa in despesas:
            rubrica = despesa['rubrica'] or ''
            categoria = despesa['categoria_despesa'] or ''
            mes = despesa['mes'] or ''
            valor = float(despesa['valor'] or 0)
            quantidade = despesa['quantidade'] if despesa['quantidade'] is not None else 0
            
            chave = (rubrica, quantidade, categoria)
            dados_agrupados[chave][mes] = valor
            todos_meses.add(mes)
        
        # Ordenar meses (assumindo formato "Mês 1", "Mês 2", etc.)
        meses_ordenados = sorted(todos_meses, key=lambda x: int(str(x).split()[-1]) if x and isinstance(x, str) and 'Mês' in x else 0)
        
        # Cabeçalho dos dados
        cabecalho = ['Rubrica', 'Quantidade', 'Categoria de Despesa'] + meses_ordenados + ['Total']
        writer.writerow(cabecalho)
        
        # Escrever dados agrupados (uma linha por rubrica+quantidade+categoria)
        total_geral = 0
        for (rubrica, quantidade, categoria) in sorted(dados_agrupados.keys()):
            valores_meses = dados_agrupados[(rubrica, quantidade, categoria)]
            
            # Calcular total da linha
            total_linha = sum(valores_meses.values())
            total_geral += total_linha
            
            # Montar linha com valores de cada mês
            linha = [rubrica, quantidade, categoria]
            
            # Adicionar valor de cada mês na ordem
            for mes in meses_ordenados:
                valor = valores_meses.get(mes, 0)
                valor_formatado = f"R$ {valor:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                linha.append(valor_formatado)
            
            # Adicionar total da linha
            total_formatado = f"R$ {total_linha:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            linha.append(total_formatado)
            
            writer.writerow(linha)
        
        # Linha de total
        writer.writerow([])
        writer.writerow([
            'TOTAL GERAL',
            '',
            '',
            '',
            f"R$ {total_geral:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        ])
        
        # Preparar resposta
        output.seek(0)
        data_atual = datetime.now().strftime('%Y%m%d_%H%M%S')
        aditivo_str = 'base' if aditivo == 0 else f'aditivo{aditivo}'
        filename = f'orcamento_{numero_termo.replace("/", "-")}_{aditivo_str}_{data_atual}.csv'
        
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename={filename}',
                'Content-Type': 'text/csv; charset=utf-8'
            }
        )
        
    except Exception as e:
        return f"Erro ao exportar CSV: {str(e)}", 500


@orcamento_bp.route("/exportar-csv", methods=["GET"])
@login_required
@requires_access('orcamento')
def exportar_csv():
    """
    Exporta TODAS as parcerias para CSV com suas informações de orçamento
    """
    try:
        cur = get_cursor()
        
        # Query para buscar TODAS as parcerias (sem limite)
        query = """
            SELECT 
                p.numero_termo,
                p.tipo_termo,
                p.sei_celeb,
                p.total_previsto,
                COALESCE(SUM(pd.valor), 0) as total_preenchido,
                p.meses
            FROM Parcerias p
            LEFT JOIN Parcerias_Despesas pd ON p.numero_termo = pd.numero_termo
            WHERE p.tipo_termo NOT IN ('Convênio de Cooperação', 'Convênio', 'Convênio - Passivo', 'Acordo de Cooperação')
            GROUP BY p.numero_termo, p.tipo_termo, p.sei_celeb, p.total_previsto, p.meses
            ORDER BY p.numero_termo
        """
        
        cur.execute(query)
        parcerias = cur.fetchall()
        cur.close()
        
        # Criar arquivo CSV em memória
        output = StringIO()
        writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)
        
        # Cabeçalho do CSV
        writer.writerow([
            'Número do Termo',
            'Tipo de Contrato',
            'SEI Celebração',
            'Total Previsto',
            'Total Preenchido',
            'Meses'
        ])
        
        # Escrever dados
        for parceria in parcerias:
            total_previsto = float(parceria['total_previsto'] or 0)
            total_preenchido = float(parceria['total_preenchido'] or 0)
            
            writer.writerow([
                parceria['numero_termo'],
                parceria['tipo_termo'] or '-',
                parceria['sei_celeb'] or '-',
                f"R$ {total_previsto:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                f"R$ {total_preenchido:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                parceria['meses'] if parceria['meses'] is not None else '-'
            ])
        
        # Preparar resposta
        output.seek(0)
        data_atual = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'orcamento_parcerias_{data_atual}.csv'
        
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename={filename}',
                'Content-Type': 'text/csv; charset=utf-8'
            }
        )
        
    except Exception as e:
        return f"Erro ao exportar CSV: {str(e)}", 500
    except Exception as e:
        return jsonify({"error": f"Erro: {str(e)}"}), 500

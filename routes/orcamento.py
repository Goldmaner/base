"""
Blueprint de orçamento (listagem e edição)
"""

from flask import Blueprint, render_template, request
from db import get_cursor
from utils import login_required

orcamento_bp = Blueprint('orcamento', __name__, url_prefix='/orcamento')


@orcamento_bp.route("/", methods=["GET"])
@login_required
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
def editar(numero_termo):
    """
    Editor de orçamento para um termo específico
    """
    cur = get_cursor()
    
    # Buscar total_previsto para exibir no subtítulo
    cur.execute("SELECT total_previsto FROM Parcerias WHERE numero_termo = %s", (numero_termo,))
    row = cur.fetchone()
    
    try:
        total_previsto_val = float(row['total_previsto']) if row and row['total_previsto'] is not None else 0.0
    except Exception:
        total_previsto_val = 0.0
    
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
                         aditivos=aditivos)


@orcamento_bp.route('/dicionario-despesas')
@login_required
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
def atualizar_categoria():
    """
    Atualiza em massa uma categoria de despesa no banco de dados
    """
    from flask import request, jsonify
    from db import get_db
    import psycopg2
    
    try:
        data = request.get_json()
        categoria_antiga = data.get('categoria_antiga')
        categoria_nova = data.get('categoria_nova')
        
        if not categoria_antiga:
            return jsonify({"error": "Categoria antiga é obrigatória"}), 400
        
        if not categoria_nova or categoria_nova.strip() == '':
            return jsonify({"error": "Categoria nova não pode estar vazia"}), 400
        
        db = get_db()
        cur = db.cursor()
        
        # Atualizar todas as ocorrências da categoria antiga para a nova
        cur.execute("""
            UPDATE Parcerias_Despesas
            SET categoria_despesa = %s
            WHERE categoria_despesa = %s
        """, (categoria_nova.strip(), categoria_antiga))
        
        linhas_afetadas = cur.rowcount
        db.commit()
        cur.close()
        
        return jsonify({
            "message": f"Categoria atualizada com sucesso! {linhas_afetadas} registros alterados.",
            "linhas_afetadas": linhas_afetadas
        }), 200
        
    except psycopg2.Error as e:
        if 'db' in locals():
            db.rollback()
        return jsonify({"error": f"Erro no banco de dados: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"Erro: {str(e)}"}), 500


@orcamento_bp.route('/buscar-categorias', methods=['GET'])
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


@orcamento_bp.route('/termos-por-categoria/<categoria>', methods=['GET'])
def termos_por_categoria(categoria):
    """
    API para buscar todos os termos (numero_termo) que usam uma categoria específica.
    Retorna lista de termos com informações adicionais.
    """
    from flask import jsonify
    from db import get_db
    import psycopg2.extras
    
    try:
        db = get_db()
        cur = db.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
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
        
    except psycopg2.Error as e:
        return jsonify({"error": f"Erro no banco de dados: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"Erro: {str(e)}"}), 500

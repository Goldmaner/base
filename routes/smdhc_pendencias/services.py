from __future__ import annotations

from typing import Any

from db import get_cursor, get_db


CATALOGO_TEMA_TIPO = "pendencias.smdhc_pendencias.tema_tipo"
CATALOGO_AREA_DEMANDANTE = "pendencias.smdhc_pendencias.tema_area_demandante"
CATALOGO_AREA_RESPONSAVEL = "pendencias.smdhc_pendencias.tema_area_responsavel"
CATALOGO_AREA_CORRELATA = "pendencias.smdhc_pendencias.tema_area_correlata"
CATALOGO_STATUS = "pendencias.smdhc_pendencias.tema_status"
CATALOGO_ATUALIZACAO_TIPO = "pendencias.smdhc_pendencias_atualizacoes.tema_atualizacao_tipo"
STATUS_ORDEM_NAO_INICIADO = 10
STATUS_ORDEM_INICIADO = 20
STATUS_ORDEM_AGUARDANDO_APROVACAO = 30
STATUS_ORDEM_CONCLUIDO = 40
ATUALIZACAO_TIPO_ORDEM_REUNIAO = 10


def _fetchall(query: str, params: tuple | list | None = None) -> list[dict[str, Any]]:
    cur = get_cursor()
    try:
        cur.execute(query, params)
        return [dict(row) for row in cur.fetchall()]
    finally:
        cur.close()


def _fetchone(query: str, params: tuple | list | None = None) -> dict[str, Any] | None:
    cur = get_cursor()
    try:
        cur.execute(query, params)
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        cur.close()


def _execute(query: str, params: tuple | list | None = None) -> None:
    cur = get_cursor()
    db = get_db()
    try:
        cur.execute(query, params)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        cur.close()


def _execute_returning_id(query: str, params: tuple | list | None = None) -> int:
    cur = get_cursor()
    db = get_db()
    try:
        cur.execute(query, params)
        row = cur.fetchone()
        db.commit()
        return int(row["id"])
    except Exception:
        db.rollback()
        raise
    finally:
        cur.close()


def _catalogo_status(schema_table_coluna_r: str, *, ativo_only: bool = True) -> list[dict[str, Any]]:
    filtro_ativo = "AND ativo = TRUE" if ativo_only else ""
    return _fetchall(
        f"""
        SELECT id, status, descricao, ordem, ativo, nome_item_fantasia
        FROM categoricas.c_geral_status
        WHERE schema_table_coluna_r = %s
          {filtro_ativo}
        ORDER BY ordem NULLS LAST, id
        """,
        (schema_table_coluna_r,),
    )


def _catalogo_item_por_id(schema_table_coluna_r: str, item_id: int | None, *, ativo_only: bool = True) -> dict[str, Any] | None:
    if not item_id:
        return None
    filtro_ativo = "AND ativo = TRUE" if ativo_only else ""
    return _fetchone(
        f"""
        SELECT id, status, descricao, ordem, ativo, nome_item_fantasia
        FROM categoricas.c_geral_status
        WHERE schema_table_coluna_r = %s
          AND id = %s
          {filtro_ativo}
        """,
        (schema_table_coluna_r, item_id),
    )


def _catalogo_itens_por_ids(schema_table_coluna_r: str, item_ids: list[int], *, ativo_only: bool = True) -> list[dict[str, Any]]:
    ids = [int(item_id) for item_id in item_ids if item_id]
    if not ids:
        return []
    filtro_ativo = "AND ativo = TRUE" if ativo_only else ""
    rows = _fetchall(
        f"""
        SELECT id, status, descricao, ordem, ativo, nome_item_fantasia
        FROM categoricas.c_geral_status
        WHERE schema_table_coluna_r = %s
          AND id = ANY(%s)
          {filtro_ativo}
        ORDER BY ordem NULLS LAST, id
        """,
        (schema_table_coluna_r, ids),
    )
    by_id = {int(row["id"]): row for row in rows}
    return [by_id[item_id] for item_id in ids if item_id in by_id]


def _catalogo_labels_por_ids(schema_table_coluna_r: str, item_ids: list[int], *, ativo_only: bool = True) -> list[str]:
    return [str(item["status"]) for item in _catalogo_itens_por_ids(schema_table_coluna_r, item_ids, ativo_only=ativo_only)]


def _catalogo_label_por_id(schema_table_coluna_r: str, item_id: int | None, *, ativo_only: bool = True) -> str | None:
    item = _catalogo_item_por_id(schema_table_coluna_r, item_id, ativo_only=ativo_only)
    return str(item["status"]) if item else None


def _build_list_query(filters, *, select_sql: str) -> tuple[str, list[Any]]:
    where = ["p.ativo = TRUE"]
    params: list[Any] = []

    if filters.q:
        like = f"%{filters.q}%"
        where.append(
            """
            (
                p.tema_nome ILIKE %s
                OR COALESCE(p.tema_descricao, '') ILIKE %s
                OR COALESCE(p.tema_observacoes, '') ILIKE %s
                OR COALESCE(v.responsavel, '') ILIKE %s
                OR COALESCE(v.proxima_acao, '') ILIKE %s
            )
            """
        )
        params.extend([like, like, like, like, like])

    if filters.status:
        where.append("p.tema_status_id = %s")
        params.append(filters.status)

    if filters.tipo:
        where.append("p.tema_tipo_id = %s")
        params.append(filters.tipo)

    if filters.area_demandante:
        where.append("p.tema_area_demandante_id = %s")
        params.append(filters.area_demandante)

    if filters.area_responsavel:
        where.append("p.tema_area_responsavel_ids && %s::integer[]")
        params.append(filters.area_responsavel)

    if filters.situacao:
        where.append("COALESCE(v.situacao_automatica, '') = %s")
        params.append(filters.situacao)

    if filters.somente_sem_prazo:
        where.append("p.tema_prazo_estimado IS NULL")

    if filters.somente_vencidas:
        where.append(
            "p.tema_prazo_estimado < CURRENT_DATE AND COALESCE(status_cat.ordem, 0) <> 40"
        )

    if filters.somente_paradas:
        where.append("COALESCE(v.situacao_automatica, '') = 'Parado'")

    sql = f"""
        {select_sql}
        FROM pendencias.smdhc_pendencias p
        LEFT JOIN pendencias.vw_smdhc_pendencias_priorizacao v
          ON v.pendencia_id = p.id
        LEFT JOIN categoricas.c_geral_status status_cat
          ON status_cat.id = p.tema_status_id
        WHERE {' AND '.join(where)}
    """
    return sql, params


def listar_status_options() -> list[dict[str, Any]]:
    return _catalogo_status(CATALOGO_STATUS)


def listar_tema_tipos() -> list[dict[str, Any]]:
    return _catalogo_status(CATALOGO_TEMA_TIPO)


def listar_area_demandante() -> list[dict[str, Any]]:
    return _catalogo_status(CATALOGO_AREA_DEMANDANTE)


def listar_area_responsavel() -> list[dict[str, Any]]:
    return _catalogo_status(CATALOGO_AREA_RESPONSAVEL)


def listar_area_correlata() -> list[dict[str, Any]]:
    return _catalogo_status(CATALOGO_AREA_CORRELATA)


def listar_atualizacao_tipos() -> list[dict[str, Any]]:
    return _catalogo_status(CATALOGO_ATUALIZACAO_TIPO)


def tipo_atualizacao_requer_participantes(tipo_id: int | None) -> bool:
    item = _catalogo_item_por_id(CATALOGO_ATUALIZACAO_TIPO, tipo_id, ativo_only=False)
    if not item:
        return False
    return int(item.get("ordem") or 0) == ATUALIZACAO_TIPO_ORDEM_REUNIAO


def listar_usuarios_infos() -> list[dict[str, Any]]:
    return _fetchall(
        """
        SELECT
            u.id AS usuario_id,
            u.email AS usuario_email,
            COALESCE(ui.usuario_nome, u.email) AS usuario_nome,
            COALESCE(ui.usuario_unidade_alocada, u.d_usuario) AS usuario_setor
        FROM gestao_pessoas.usuarios u
        LEFT JOIN gestao_pessoas.usuarios_infos ui
          ON ui.usuario_email = u.email
        WHERE COALESCE(ui.usuario_status, 'Ativo') = 'Ativo'
        ORDER BY COALESCE(ui.usuario_unidade_alocada, u.d_usuario) NULLS LAST,
                 COALESCE(ui.usuario_nome, u.email)
        """
    )


def listar_principios() -> list[dict[str, Any]]:
    principios = _fetchall(
        """
        SELECT id, tema_principios, tema_principios_descricao, tema_principios_calculo, tema_principios_ordem
        FROM pendencias.smdhc_pendencias_principios
        WHERE ativo = TRUE
        ORDER BY tema_principios_ordem, id
        """
    )
    notas = _fetchall(
        """
        SELECT
            pn.id,
            pn.principio_id,
            pn.tema_principios_nota_nome,
            pn.tema_principios_nota_valor,
            pn.tema_principios_nota_descricao,
            pn.tema_principios_nota_ordem
        FROM pendencias.smdhc_pendencias_principios_notas pn
        WHERE pn.ativo = TRUE
        ORDER BY pn.principio_id, pn.tema_principios_nota_ordem NULLS LAST, pn.id
        """
    )

    notas_por_principio: dict[int, list[dict[str, Any]]] = {}
    for nota in notas:
        notas_por_principio.setdefault(int(nota["principio_id"]), []).append(nota)

    for principio in principios:
        principio["notas"] = notas_por_principio.get(int(principio["id"]), [])
    return principios


def listar_notas_principios(principio_id: int | None = None) -> list[dict[str, Any]]:
    if principio_id:
        return _fetchall(
            """
            SELECT id, principio_id, tema_principios_nota_nome, tema_principios_nota_valor,
                   tema_principios_nota_descricao, tema_principios_nota_ordem
            FROM pendencias.smdhc_pendencias_principios_notas
            WHERE ativo = TRUE
              AND principio_id = %s
            ORDER BY tema_principios_nota_ordem NULLS LAST, id
            """,
            (principio_id,),
        )
    return _fetchall(
        """
        SELECT id, principio_id, tema_principios_nota_nome, tema_principios_nota_valor,
               tema_principios_nota_descricao, tema_principios_nota_ordem
        FROM pendencias.smdhc_pendencias_principios_notas
        WHERE ativo = TRUE
        ORDER BY principio_id, tema_principios_nota_ordem NULLS LAST, id
        """
    )


def listar_pendencias(filters) -> list[dict[str, Any]]:
    select_sql = """
        SELECT
            p.id,
            p.tema_nome,
            v.tema_tipo,
            p.tema_descricao,
            v.tema_area_demandante,
            v.tema_area_responsavel,
            v.tema_area_correlata,
            v.tema_status,
            v.tema_status_ordem,
            p.tema_prazo_estimado,
            p.tema_observacoes,
            p.prioridade_manual,
            p.prioridade_observacao,
            COALESCE(v.nota_proximidade, 0) AS nota_proximidade,
            COALESCE(v.nota_enem, 0) AS nota_enem,
            COALESCE(v.nota_instabilidade, 0) AS nota_instabilidade,
            COALESCE(v.nota_riscos, 0) AS nota_riscos,
            v.ordem_prioridade,
            v.situacao_automatica,
            v.responsavel,
            v.ultima_atualizacao,
            v.ultima_atualizacao_data,
            v.proxima_acao
    """
    sql, params = _build_list_query(filters, select_sql=select_sql)
    sql += """
        ORDER BY
            COALESCE(p.prioridade_manual, v.ordem_prioridade, 999999),
            COALESCE(v.ordem_prioridade, 999999),
            p.id
    """
    return _fetchall(sql, params)


def obter_pendencia(pendencia_id: int) -> dict[str, Any] | None:
    pendencia = _fetchone(
        """
        SELECT
            p.id,
            p.tema_nome,
            p.tema_tipo_id,
            v.tema_tipo,
            p.tema_descricao,
            p.tema_area_demandante_id,
            v.tema_area_demandante,
            p.tema_area_responsavel_ids,
            v.tema_area_responsavel,
            p.tema_area_correlata_ids,
            v.tema_area_correlata,
            p.tema_status_id,
            v.tema_status,
            v.tema_status_ordem,
            p.tema_prazo_estimado,
            p.tema_observacoes,
            p.situacao_automatica,
            p.prioridade_manual,
            p.prioridade_observacao,
            p.ativo,
            p.criado_por,
            p.criado_em,
            p.atualizado_por,
            p.atualizado_em,
            COALESCE(v.nota_proximidade, 0) AS nota_proximidade,
            COALESCE(v.nota_enem, 0) AS nota_enem,
            COALESCE(v.nota_instabilidade, 0) AS nota_instabilidade,
            COALESCE(v.nota_riscos, 0) AS nota_riscos,
            v.ordem_prioridade,
            v.situacao_automatica AS situacao_automatica_view,
            v.responsavel,
            v.ultima_atualizacao,
            v.ultima_atualizacao_data,
            v.proxima_acao
        FROM pendencias.smdhc_pendencias p
        LEFT JOIN pendencias.vw_smdhc_pendencias_priorizacao v
          ON v.pendencia_id = p.id
        WHERE p.id = %s
          AND p.ativo = TRUE
        """,
        (pendencia_id,),
    )
    if not pendencia:
        return None

    pendencia["processos_sei"] = _fetchall(
        """
        SELECT id, tema_processo, tema_processo_observacao, criado_por, criado_em, atualizado_por, atualizado_em
        FROM pendencias.smdhc_pendencias_sei
        WHERE pendencia_id = %s
          AND ativo = TRUE
        ORDER BY atualizado_em DESC NULLS LAST, criado_em DESC NULLS LAST, id DESC
        """,
        (pendencia_id,),
    )
    pendencia["links_relacionados"] = _fetchall(
        """
        SELECT
            id,
            tema_link_titulo,
            tema_link_url,
            tema_link_descricao,
            criado_por,
            criado_em,
            atualizado_por,
            atualizado_em
        FROM pendencias.smdhc_pendencias_links
        WHERE pendencia_id = %s
          AND ativo = TRUE
        ORDER BY atualizado_em DESC NULLS LAST, criado_em DESC NULLS LAST, id DESC
        """,
        (pendencia_id,),
    )
    pendencia["documentos_relacionados"] = _fetchall(
        """
        SELECT
            id,
            documento_titulo,
            documento_descricao,
            documento_nome_original,
            documento_storage_path,
            documento_content_type,
            documento_tamanho_bytes,
            criado_por,
            criado_em,
            atualizado_por,
            atualizado_em
        FROM pendencias.smdhc_pendencias_documentos
        WHERE pendencia_id = %s
          AND ativo = TRUE
        ORDER BY atualizado_em DESC NULLS LAST, criado_em DESC NULLS LAST, id DESC
        """,
        (pendencia_id,),
    )
    pendencia["responsaveis_historico"] = _fetchall(
        """
        SELECT id, tema_responsavel, tema_envolvidos, criado_por, criado_em, atualizado_por, atualizado_em
        FROM pendencias.smdhc_pendencias_resp
        WHERE pendencia_id = %s
          AND ativo = TRUE
        ORDER BY atualizado_em DESC NULLS LAST, criado_em DESC NULLS LAST, id DESC
        """,
        (pendencia_id,),
    )
    pendencia["atualizacoes"] = obter_timeline_pendencia(pendencia_id)
    pendencia["matriz"] = _obter_matriz_detalhada(pendencia_id)
    pendencia["badges"] = obter_badges_pendencia(pendencia=pendencia)
    return pendencia


def criar_pendencia(data, usuario: str) -> int:
    tema_tipo = _catalogo_label_por_id(CATALOGO_TEMA_TIPO, data.tema_tipo)
    tema_area_demandante = _catalogo_label_por_id(CATALOGO_AREA_DEMANDANTE, data.tema_area_demandante)
    tema_area_responsavel = _catalogo_labels_por_ids(CATALOGO_AREA_RESPONSAVEL, data.tema_area_responsavel)
    tema_area_correlata = _catalogo_labels_por_ids(CATALOGO_AREA_CORRELATA, data.tema_area_correlata)
    tema_status = _catalogo_label_por_id(CATALOGO_STATUS, data.tema_status)
    return _execute_returning_id(
        """
        INSERT INTO pendencias.smdhc_pendencias (
            tema_nome,
            tema_tipo,
            tema_tipo_id,
            tema_descricao,
            tema_area_demandante,
            tema_area_demandante_id,
            tema_area_responsavel,
            tema_area_responsavel_ids,
            tema_area_correlata,
            tema_area_correlata_ids,
            tema_status,
            tema_status_id,
            tema_prazo_estimado,
            tema_observacoes,
            situacao_automatica,
            prioridade_manual,
            prioridade_observacao,
            criado_por,
            atualizado_por
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            data.tema_nome,
            tema_tipo,
            data.tema_tipo,
            data.tema_descricao,
            tema_area_demandante,
            data.tema_area_demandante,
            tema_area_responsavel,
            data.tema_area_responsavel,
            tema_area_correlata,
            data.tema_area_correlata,
            tema_status,
            data.tema_status,
            data.tema_prazo_estimado,
            data.tema_observacoes,
            data.situacao_automatica,
            data.prioridade_manual,
            data.prioridade_observacao,
            usuario,
            usuario,
        ),
    )


def atualizar_pendencia(pendencia_id: int, data, usuario: str) -> None:
    tema_tipo = _catalogo_label_por_id(CATALOGO_TEMA_TIPO, data.tema_tipo)
    tema_area_demandante = _catalogo_label_por_id(CATALOGO_AREA_DEMANDANTE, data.tema_area_demandante)
    tema_area_responsavel = _catalogo_labels_por_ids(CATALOGO_AREA_RESPONSAVEL, data.tema_area_responsavel)
    tema_area_correlata = _catalogo_labels_por_ids(CATALOGO_AREA_CORRELATA, data.tema_area_correlata)
    tema_status = _catalogo_label_por_id(CATALOGO_STATUS, data.tema_status)
    _execute(
        """
        UPDATE pendencias.smdhc_pendencias
        SET tema_nome = %s,
            tema_tipo = %s,
            tema_tipo_id = %s,
            tema_descricao = %s,
            tema_area_demandante = %s,
            tema_area_demandante_id = %s,
            tema_area_responsavel = %s,
            tema_area_responsavel_ids = %s,
            tema_area_correlata = %s,
            tema_area_correlata_ids = %s,
            tema_status = %s,
            tema_status_id = %s,
            tema_prazo_estimado = %s,
            tema_observacoes = %s,
            situacao_automatica = %s,
            prioridade_manual = %s,
            prioridade_observacao = %s,
            atualizado_por = %s,
            atualizado_em = NOW()
        WHERE id = %s
          AND ativo = TRUE
        """,
        (
            data.tema_nome,
            tema_tipo,
            data.tema_tipo,
            data.tema_descricao,
            tema_area_demandante,
            data.tema_area_demandante,
            tema_area_responsavel,
            data.tema_area_responsavel,
            tema_area_correlata,
            data.tema_area_correlata,
            tema_status,
            data.tema_status,
            data.tema_prazo_estimado,
            data.tema_observacoes,
            data.situacao_automatica,
            data.prioridade_manual,
            data.prioridade_observacao,
            usuario,
            pendencia_id,
        ),
    )


def excluir_pendencia_logicamente(pendencia_id: int, usuario: str) -> None:
    _execute(
        """
        UPDATE pendencias.smdhc_pendencias
        SET ativo = FALSE,
            atualizado_por = %s,
            atualizado_em = NOW()
        WHERE id = %s
          AND ativo = TRUE
        """,
        (usuario, pendencia_id),
    )


def _salvar_participantes_atualizacao(cur, atualizacao_id: int, data, usuario: str) -> None:
    for usuario_id in data.participantes_usuario_ids:
        cur.execute(
            """
            INSERT INTO pendencias.smdhc_pendencias_atualizacoes_participantes (
                atualizacao_id,
                participante_origem,
                usuario_id,
                criado_por,
                atualizado_por
            )
            VALUES (%s, 'usuario_sistema', %s, %s, %s)
            """,
            (atualizacao_id, usuario_id, usuario, usuario),
        )

    for participante in data.participantes_externos:
        cur.execute(
            """
            INSERT INTO pendencias.smdhc_pendencias_atualizacoes_participantes (
                atualizacao_id,
                participante_origem,
                participante_nome_externo,
                participante_setor_externo,
                criado_por,
                atualizado_por
            )
            VALUES (%s, 'externo', %s, %s, %s, %s)
            """,
            (
                atualizacao_id,
                participante["nome"],
                participante["setor"],
                usuario,
                usuario,
            ),
        )


def registrar_atualizacao(pendencia_id: int, data, usuario: str) -> int:
    tema_atualizacao_tipo = _catalogo_label_por_id(CATALOGO_ATUALIZACAO_TIPO, data.tema_atualizacao_tipo)
    db = get_db()
    cur = get_cursor()
    try:
        cur.execute(
            """
            INSERT INTO pendencias.smdhc_pendencias_atualizacoes (
                pendencia_id,
                tema_atualizacao,
                tema_atualizacao_data,
                tema_atualizacao_tipo,
                tema_atualizacao_tipo_id,
                tema_acao_subsequente,
                criado_por,
                atualizado_por
            )
            VALUES (%s, %s, COALESCE(%s, CURRENT_DATE), %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                pendencia_id,
                data.tema_atualizacao,
                data.tema_atualizacao_data,
                tema_atualizacao_tipo,
                data.tema_atualizacao_tipo,
                data.tema_acao_subsequente,
                usuario,
                usuario,
            ),
        )
        atualizacao_id = int(cur.fetchone()["id"])
        _salvar_participantes_atualizacao(cur, atualizacao_id, data, usuario)
        db.commit()
        return atualizacao_id
    except Exception:
        db.rollback()
        raise
    finally:
        cur.close()


def atualizar_atualizacao(pendencia_id: int, atualizacao_id: int, data, usuario: str) -> bool:
    tema_atualizacao_tipo = _catalogo_label_por_id(CATALOGO_ATUALIZACAO_TIPO, data.tema_atualizacao_tipo)
    db = get_db()
    cur = get_cursor()
    try:
        cur.execute(
            """
            SELECT id
            FROM pendencias.smdhc_pendencias_atualizacoes
            WHERE id = %s
              AND pendencia_id = %s
              AND ativo = TRUE
            """,
            (atualizacao_id, pendencia_id),
        )
        row = cur.fetchone()
        if not row:
            db.rollback()
            return False

        cur.execute(
            """
            UPDATE pendencias.smdhc_pendencias_atualizacoes
            SET tema_atualizacao = %s,
                tema_atualizacao_data = COALESCE(%s, CURRENT_DATE),
                tema_atualizacao_tipo = %s,
                tema_atualizacao_tipo_id = %s,
                tema_acao_subsequente = %s,
                atualizado_por = %s,
                atualizado_em = NOW()
            WHERE id = %s
              AND pendencia_id = %s
              AND ativo = TRUE
            """,
            (
                data.tema_atualizacao,
                data.tema_atualizacao_data,
                tema_atualizacao_tipo,
                data.tema_atualizacao_tipo,
                data.tema_acao_subsequente,
                usuario,
                atualizacao_id,
                pendencia_id,
            ),
        )
        cur.execute(
            """
            UPDATE pendencias.smdhc_pendencias_atualizacoes_participantes
            SET ativo = FALSE,
                atualizado_por = %s,
                atualizado_em = NOW()
            WHERE atualizacao_id = %s
              AND ativo = TRUE
            """,
            (usuario, atualizacao_id),
        )
        _salvar_participantes_atualizacao(cur, atualizacao_id, data, usuario)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        cur.close()


def registrar_processo_sei(pendencia_id: int, data, usuario: str) -> int:
    return _execute_returning_id(
        """
        INSERT INTO pendencias.smdhc_pendencias_sei (
            pendencia_id,
            tema_processo,
            tema_processo_observacao,
            criado_por,
            atualizado_por
        )
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            pendencia_id,
            data.tema_processo,
            data.tema_processo_observacao,
            usuario,
            usuario,
        ),
    )


def atualizar_processo_sei(pendencia_id: int, processo_id: int, data, usuario: str) -> bool:
    row = _fetchone(
        """
        SELECT id
        FROM pendencias.smdhc_pendencias_sei
        WHERE id = %s
          AND pendencia_id = %s
          AND ativo = TRUE
        """,
        (processo_id, pendencia_id),
    )
    if not row:
        return False

    _execute(
        """
        UPDATE pendencias.smdhc_pendencias_sei
        SET tema_processo = %s,
            tema_processo_observacao = %s,
            atualizado_por = %s,
            atualizado_em = NOW()
        WHERE id = %s
          AND pendencia_id = %s
          AND ativo = TRUE
        """,
        (
            data.tema_processo,
            data.tema_processo_observacao,
            usuario,
            processo_id,
            pendencia_id,
        ),
    )
    return True


def registrar_link_relacionado(pendencia_id: int, data, usuario: str) -> int:
    return _execute_returning_id(
        """
        INSERT INTO pendencias.smdhc_pendencias_links (
            pendencia_id,
            tema_link_titulo,
            tema_link_url,
            tema_link_descricao,
            criado_por,
            atualizado_por
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            pendencia_id,
            data.tema_link_titulo,
            data.tema_link_url,
            data.tema_link_descricao,
            usuario,
            usuario,
        ),
    )


def atualizar_link_relacionado(pendencia_id: int, link_id: int, data, usuario: str) -> bool:
    row = _fetchone(
        """
        SELECT id
        FROM pendencias.smdhc_pendencias_links
        WHERE id = %s
          AND pendencia_id = %s
          AND ativo = TRUE
        """,
        (link_id, pendencia_id),
    )
    if not row:
        return False

    _execute(
        """
        UPDATE pendencias.smdhc_pendencias_links
        SET tema_link_titulo = %s,
            tema_link_url = %s,
            tema_link_descricao = %s,
            atualizado_por = %s,
            atualizado_em = NOW()
        WHERE id = %s
          AND pendencia_id = %s
          AND ativo = TRUE
        """,
        (
            data.tema_link_titulo,
            data.tema_link_url,
            data.tema_link_descricao,
            usuario,
            link_id,
            pendencia_id,
        ),
    )
    return True


def excluir_link_relacionado(pendencia_id: int, link_id: int, usuario: str) -> bool:
    row = _fetchone(
        """
        SELECT id
        FROM pendencias.smdhc_pendencias_links
        WHERE id = %s
          AND pendencia_id = %s
          AND ativo = TRUE
        """,
        (link_id, pendencia_id),
    )
    if not row:
        return False

    _execute(
        """
        UPDATE pendencias.smdhc_pendencias_links
        SET ativo = FALSE,
            atualizado_por = %s,
            atualizado_em = NOW()
        WHERE id = %s
        """,
        (usuario, link_id),
    )
    return True


def registrar_documento_relacionado(
    pendencia_id: int,
    *,
    documento_titulo: str | None,
    documento_descricao: str | None,
    documento_nome_original: str,
    documento_storage_path: str,
    documento_content_type: str | None,
    documento_tamanho_bytes: int | None,
    usuario: str,
) -> int:
    return _execute_returning_id(
        """
        INSERT INTO pendencias.smdhc_pendencias_documentos (
            pendencia_id,
            documento_titulo,
            documento_descricao,
            documento_nome_original,
            documento_storage_path,
            documento_content_type,
            documento_tamanho_bytes,
            criado_por,
            atualizado_por
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            pendencia_id,
            documento_titulo,
            documento_descricao,
            documento_nome_original,
            documento_storage_path,
            documento_content_type,
            documento_tamanho_bytes,
            usuario,
            usuario,
        ),
    )


def obter_documento_relacionado(pendencia_id: int, documento_id: int) -> dict[str, Any] | None:
    return _fetchone(
        """
        SELECT
            id,
            pendencia_id,
            documento_titulo,
            documento_descricao,
            documento_nome_original,
            documento_storage_path,
            documento_content_type,
            documento_tamanho_bytes,
            criado_por,
            criado_em,
            atualizado_por,
            atualizado_em
        FROM pendencias.smdhc_pendencias_documentos
        WHERE id = %s
          AND pendencia_id = %s
          AND ativo = TRUE
        """,
        (documento_id, pendencia_id),
    )


def atualizar_documento_relacionado(
    pendencia_id: int,
    documento_id: int,
    *,
    documento_titulo: str | None,
    documento_descricao: str | None,
    documento_nome_original: str,
    documento_storage_path: str,
    documento_content_type: str | None,
    documento_tamanho_bytes: int | None,
    usuario: str,
) -> bool:
    documento = obter_documento_relacionado(pendencia_id, documento_id)
    if not documento:
        return False

    _execute(
        """
        UPDATE pendencias.smdhc_pendencias_documentos
        SET documento_titulo = %s,
            documento_descricao = %s,
            documento_nome_original = %s,
            documento_storage_path = %s,
            documento_content_type = %s,
            documento_tamanho_bytes = %s,
            atualizado_por = %s,
            atualizado_em = NOW()
        WHERE id = %s
          AND pendencia_id = %s
          AND ativo = TRUE
        """,
        (
            documento_titulo,
            documento_descricao,
            documento_nome_original,
            documento_storage_path,
            documento_content_type,
            documento_tamanho_bytes,
            usuario,
            documento_id,
            pendencia_id,
        ),
    )
    return True


def excluir_documento_relacionado(pendencia_id: int, documento_id: int, usuario: str) -> dict[str, Any] | None:
    documento = obter_documento_relacionado(pendencia_id, documento_id)
    if not documento:
        return None

    _execute(
        """
        UPDATE pendencias.smdhc_pendencias_documentos
        SET ativo = FALSE,
            atualizado_por = %s,
            atualizado_em = NOW()
        WHERE id = %s
        """,
        (usuario, documento_id),
    )
    return documento


def registrar_responsaveis(pendencia_id: int, data, usuario: str) -> int:
    return _execute_returning_id(
        """
        INSERT INTO pendencias.smdhc_pendencias_resp (
            pendencia_id,
            tema_responsavel,
            tema_envolvidos,
            criado_por,
            atualizado_por
        )
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            pendencia_id,
            data.tema_responsavel,
            data.tema_envolvidos,
            usuario,
            usuario,
        ),
    )


def atualizar_responsaveis(pendencia_id: int, responsavel_id: int, data, usuario: str) -> bool:
    row = _fetchone(
        """
        SELECT id
        FROM pendencias.smdhc_pendencias_resp
        WHERE id = %s
          AND pendencia_id = %s
          AND ativo = TRUE
        """,
        (responsavel_id, pendencia_id),
    )
    if not row:
        return False

    _execute(
        """
        UPDATE pendencias.smdhc_pendencias_resp
        SET tema_responsavel = %s,
            tema_envolvidos = %s,
            atualizado_por = %s,
            atualizado_em = NOW()
        WHERE id = %s
          AND pendencia_id = %s
          AND ativo = TRUE
        """,
        (
            data.tema_responsavel,
            data.tema_envolvidos,
            usuario,
            responsavel_id,
            pendencia_id,
        ),
    )
    return True


def salvar_matriz_pendencia(pendencia_id: int, data, usuario: str) -> None:
    db = get_db()
    cur = get_cursor()
    try:
        principios = _fetchall(
            """
            SELECT id, tema_principios, tema_principios_ordem
            FROM pendencias.smdhc_pendencias_principios
            WHERE ativo = TRUE
            """
        )
        principios_map = {int(item["id"]): item for item in principios}

        notas = _fetchall(
            """
            SELECT id, principio_id, tema_principios_nota_valor
            FROM pendencias.smdhc_pendencias_principios_notas
            WHERE ativo = TRUE
            """
        )
        notas_map = {int(item["id"]): item for item in notas}

        for item in data.itens:
            principio = principios_map.get(int(item.principio_id))
            if not principio:
                continue

            principio_ordem = int(principio["tema_principios_ordem"])
            nota_ids_validos = [
                note_id for note_id in item.principio_nota_ids if note_id in notas_map
            ]
            if principio_ordem == 40:
                nota_ids_para_salvar = nota_ids_validos
            else:
                nota_ids_para_salvar = nota_ids_validos[:1]

            notas_selecionadas = [
                notas_map[note_id]
                for note_id in nota_ids_para_salvar
            ]

            nota_final = item.tema_principios_nota or 0
            if notas_selecionadas:
                if principio_ordem == 40:
                    nota_final = sum(int(n["tema_principios_nota_valor"]) for n in notas_selecionadas)
                else:
                    nota_final = int(notas_selecionadas[0]["tema_principios_nota_valor"])

            cur.execute(
                """
                INSERT INTO pendencias.smdhc_pendencias_matriz (
                    pendencia_id,
                    principio_id,
                    tema_principios_nota,
                    ativo,
                    criado_por,
                    atualizado_por
                )
                VALUES (%s, %s, %s, TRUE, %s, %s)
                ON CONFLICT (pendencia_id, principio_id) DO UPDATE
                SET tema_principios_nota = EXCLUDED.tema_principios_nota,
                    ativo = TRUE,
                    atualizado_por = EXCLUDED.atualizado_por,
                    atualizado_em = NOW()
                RETURNING id
                """,
                (
                    pendencia_id,
                    item.principio_id,
                    nota_final,
                    usuario,
                    usuario,
                ),
            )
            matriz_id = int(cur.fetchone()["id"])

            cur.execute(
                """
                DELETE FROM pendencias.smdhc_pendencias_matriz_fatores
                WHERE matriz_id = %s
                """,
                (matriz_id,),
            )

            for principle_note_id in nota_ids_para_salvar:
                cur.execute(
                    """
                    INSERT INTO pendencias.smdhc_pendencias_matriz_fatores (
                        matriz_id,
                        principio_nota_id,
                        criado_por
                    )
                    VALUES (%s, %s, %s)
                    ON CONFLICT (matriz_id, principio_nota_id) DO NOTHING
                    """,
                    (matriz_id, principle_note_id, usuario),
                )

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        cur.close()


def calcular_matriz_pendencia(pendencia_id: int) -> dict[str, Any] | None:
    return _fetchone(
        """
        SELECT *
        FROM pendencias.vw_smdhc_pendencias_priorizacao
        WHERE pendencia_id = %s
        """,
        (pendencia_id,),
    )


def calcular_matriz_geral(limit: int = 25) -> list[dict[str, Any]]:
    return _fetchall(
        """
        SELECT
            pendencia_id,
            tema_nome,
            tema_tipo,
            tema_status,
            tema_prazo_estimado,
            tema_area_demandante,
            tema_area_responsavel,
            nota_proximidade,
            nota_enem,
            nota_instabilidade,
            nota_riscos,
            ordem_prioridade,
            situacao_automatica,
            responsavel,
            ultima_atualizacao,
            proxima_acao
        FROM pendencias.vw_smdhc_pendencias_priorizacao
        ORDER BY ordem_prioridade
        LIMIT %s
        """,
        (limit,),
    )


def obter_resumo_dashboard(filters) -> dict[str, Any]:
    select_sql = """
        SELECT
            COUNT(*) AS total_ativas,
            COUNT(*) FILTER (WHERE COALESCE(status_cat.ordem, 0) = 20) AS iniciadas,
            COUNT(*) FILTER (WHERE COALESCE(status_cat.ordem, 0) = 10) AS nao_iniciadas,
            COUNT(*) FILTER (WHERE COALESCE(status_cat.ordem, 0) = 30) AS aguardando_aprovacao,
            COUNT(*) FILTER (WHERE COALESCE(status_cat.ordem, 0) = 40) AS concluidas,
            COUNT(*) FILTER (WHERE p.tema_prazo_estimado IS NULL AND COALESCE(status_cat.ordem, 0) <> 40) AS sem_prazo,
            COUNT(*) FILTER (WHERE p.tema_prazo_estimado < CURRENT_DATE AND COALESCE(status_cat.ordem, 0) <> 40) AS vencidas,
            COUNT(*) FILTER (WHERE COALESCE(v.situacao_automatica, '') = 'Parado') AS paradas,
            COUNT(*) FILTER (WHERE COALESCE(v.ordem_prioridade, 999999) <= 5) AS alta_prioridade
    """
    sql, params = _build_list_query(filters, select_sql=select_sql)
    return _fetchone(sql, params) or {
        "total_ativas": 0,
        "iniciadas": 0,
        "nao_iniciadas": 0,
        "aguardando_aprovacao": 0,
        "concluidas": 0,
        "sem_prazo": 0,
        "vencidas": 0,
        "paradas": 0,
        "alta_prioridade": 0,
    }


def obter_alertas_dashboard(filters) -> list[dict[str, Any]]:
    select_sql = """
        SELECT
            p.id,
            p.tema_nome,
            v.tema_status,
            v.tema_status_ordem,
            p.tema_prazo_estimado,
            v.situacao_automatica,
            v.ordem_prioridade,
            v.responsavel
    """
    sql, params = _build_list_query(filters, select_sql=select_sql)
    sql += """
        AND (
            COALESCE(v.situacao_automatica, '') IN ('Sem prazo', 'Vencido', 'Parado')
            OR COALESCE(v.situacao_automatica, '') ILIKE 'Aguardando val%%'
        )
        ORDER BY COALESCE(v.ordem_prioridade, 999999), p.id
        LIMIT 8
    """
    return _fetchall(sql, params)


def obter_timeline_pendencia(pendencia_id: int) -> list[dict[str, Any]]:
    atualizacoes = _fetchall(
        """
        SELECT
            a.id,
            a.tema_atualizacao,
            a.tema_atualizacao_data,
            a.tema_atualizacao_tipo_id,
            COALESCE(cat.status, a.tema_atualizacao_tipo) AS tema_atualizacao_tipo,
            cat.ordem AS tema_atualizacao_tipo_ordem,
            a.tema_acao_subsequente,
            a.criado_por,
            a.criado_em,
            a.atualizado_por,
            a.atualizado_em
        FROM pendencias.smdhc_pendencias_atualizacoes a
        LEFT JOIN categoricas.c_geral_status cat
          ON cat.id = a.tema_atualizacao_tipo_id
        WHERE a.pendencia_id = %s
          AND a.ativo = TRUE
        ORDER BY a.tema_atualizacao_data DESC NULLS LAST, a.atualizado_em DESC NULLS LAST, a.criado_em DESC NULLS LAST, a.id DESC
        """,
        (pendencia_id,),
    )

    if not atualizacoes:
        return []

    atualizacao_ids = [int(item["id"]) for item in atualizacoes]
    participantes = _fetchall(
        """
        SELECT
            ap.id,
            ap.atualizacao_id,
            ap.participante_origem,
            ap.usuario_id,
            ap.participante_nome_externo,
            ap.participante_setor_externo,
            u.email AS usuario_email,
            COALESCE(ui.usuario_nome, u.email) AS usuario_nome
        FROM pendencias.smdhc_pendencias_atualizacoes_participantes ap
        LEFT JOIN gestao_pessoas.usuarios u
          ON u.id = ap.usuario_id
        LEFT JOIN gestao_pessoas.usuarios_infos ui
          ON ui.usuario_email = u.email
        WHERE ap.ativo = TRUE
          AND ap.atualizacao_id = ANY(%s)
        ORDER BY ap.id
        """,
        (atualizacao_ids,),
    )

    participantes_por_atualizacao: dict[int, list[dict[str, Any]]] = {}
    for participante in participantes:
        participantes_por_atualizacao.setdefault(int(participante["atualizacao_id"]), []).append(participante)

    for item in atualizacoes:
        rows = participantes_por_atualizacao.get(int(item["id"]), [])
        internos_ids: list[int] = []
        externos: list[dict[str, str]] = []
        resumo: list[str] = []

        for row in rows:
            if row.get("participante_origem") == "usuario_sistema" and row.get("usuario_id"):
                usuario_id = int(row["usuario_id"])
                if usuario_id not in internos_ids:
                    internos_ids.append(usuario_id)
                nome = row.get("usuario_nome") or row.get("usuario_email") or "Usuário do sistema"
                resumo.append(str(nome))
            else:
                nome_externo = row.get("participante_nome_externo") or "Participante externo"
                setor_externo = row.get("participante_setor_externo") or "Sem setor"
                externos.append({"nome": str(nome_externo), "setor": str(setor_externo)})
                resumo.append(f"{nome_externo} ({setor_externo})")

        item["participantes_internos_ids"] = internos_ids
        item["participantes_externos"] = externos
        item["participantes_resumo"] = resumo

    return atualizacoes


def obter_badges_pendencia(
    pendencia_id: int | None = None,
    *,
    pendencia: dict[str, Any] | None = None,
) -> list[str]:
    if pendencia is None:
        if pendencia_id is None:
            return []
        pendencia = obter_pendencia(pendencia_id)
    if not pendencia:
        return []

    badges: list[str] = []

    situacao = pendencia.get("situacao_automatica_view") or pendencia.get("situacao_automatica")
    if situacao:
        badges.append(str(situacao))

    ordem_prioridade = pendencia.get("ordem_prioridade")
    if ordem_prioridade is not None and int(ordem_prioridade) <= 5:
        badges.append("Alta prioridade")

    for principio in pendencia.get("matriz", []):
        if principio.get("tema_principios") != "Nº de Riscos":
            continue
        for nota in principio.get("notas", []):
            if nota.get("selecionado"):
                badges.append(f"Risco {str(nota['tema_principios_nota_nome']).lower()}")

    unique_badges: list[str] = []
    for badge in badges:
        if badge not in unique_badges:
            unique_badges.append(badge)
    return unique_badges


def _obter_matriz_detalhada(pendencia_id: int) -> list[dict[str, Any]]:
    rows = _fetchall(
        """
        SELECT
            p.id AS principio_id,
            p.tema_principios,
            p.tema_principios_descricao,
            p.tema_principios_calculo,
            p.tema_principios_ordem,
            m.id AS matriz_id,
            m.tema_principios_nota,
            pn.id AS principio_nota_id,
            pn.tema_principios_nota_nome,
            pn.tema_principios_nota_valor,
            pn.tema_principios_nota_descricao,
            pn.tema_principios_nota_ordem,
            CASE WHEN mf.id IS NOT NULL THEN TRUE ELSE FALSE END AS selecionado
        FROM pendencias.smdhc_pendencias_principios p
        LEFT JOIN pendencias.smdhc_pendencias_matriz m
          ON m.principio_id = p.id
         AND m.pendencia_id = %s
         AND m.ativo = TRUE
        LEFT JOIN pendencias.smdhc_pendencias_principios_notas pn
          ON pn.principio_id = p.id
         AND pn.ativo = TRUE
        LEFT JOIN pendencias.smdhc_pendencias_matriz_fatores mf
          ON mf.matriz_id = m.id
         AND mf.principio_nota_id = pn.id
        WHERE p.ativo = TRUE
        ORDER BY p.tema_principios_ordem, pn.tema_principios_nota_ordem NULLS LAST, pn.id
        """,
        (pendencia_id,),
    )

    matriz: list[dict[str, Any]] = []
    by_id: dict[int, dict[str, Any]] = {}

    for row in rows:
        principio_id = int(row["principio_id"])
        if principio_id not in by_id:
            by_id[principio_id] = {
                "principio_id": principio_id,
                "matriz_id": row.get("matriz_id"),
                "tema_principios": row["tema_principios"],
                "tema_principios_descricao": row["tema_principios_descricao"],
                "tema_principios_calculo": row["tema_principios_calculo"],
                "tema_principios_ordem": row["tema_principios_ordem"],
                "tema_principios_nota": row.get("tema_principios_nota"),
                "notas": [],
            }
            matriz.append(by_id[principio_id])

        if row.get("principio_nota_id"):
            by_id[principio_id]["notas"].append(
                {
                    "id": row["principio_nota_id"],
                    "tema_principios_nota_nome": row["tema_principios_nota_nome"],
                    "tema_principios_nota_valor": row["tema_principios_nota_valor"],
                    "tema_principios_nota_descricao": row["tema_principios_nota_descricao"],
                    "tema_principios_nota_ordem": row["tema_principios_nota_ordem"],
                    "selecionado": bool(row["selecionado"]),
                }
            )

    return matriz

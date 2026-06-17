from __future__ import annotations

from typing import Any

from db import get_cursor, get_db


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


def listar_termos_colaboracao() -> list[dict[str, Any]]:
    return _fetchall(
        """
        SELECT numero_termo, osc, projeto, inicio, final
        FROM public.parcerias
        WHERE unaccent(COALESCE(tipo_termo, '')) ILIKE unaccent('%Colabora%')
        ORDER BY numero_termo
        """
    )


def listar_escopos(
    *,
    q: str = "",
    escopo: str = "todos",
    ativo: str = "ativos",
    vigencia: str = "todos",
) -> list[dict[str, Any]]:
    where = ["1=1"]
    params: list[Any] = []

    if q:
        like = f"%{q}%"
        where.append(
            """
            (
                e.numero_termo ILIKE %s
                OR COALESCE(p.osc, '') ILIKE %s
                OR COALESCE(p.projeto, '') ILIKE %s
            )
            """
        )
        params.extend([like, like, like])

    if escopo == "sim":
        where.append("e.dgm_escopo_termo = TRUE")
    elif escopo == "nao":
        where.append("e.dgm_escopo_termo = FALSE")

    if ativo == "ativos":
        where.append("e.ativo = TRUE")
    elif ativo == "inativos":
        where.append("e.ativo = FALSE")

    if vigencia == "vigente":
        where.append("p.inicio <= CURRENT_DATE AND p.final >= CURRENT_DATE")
    elif vigencia == "encerrado":
        where.append("p.final < CURRENT_DATE")
    elif vigencia == "nao_iniciado":
        where.append("p.inicio > CURRENT_DATE")
    elif vigencia == "sem_datas":
        where.append("(p.inicio IS NULL OR p.final IS NULL)")

    rows = _fetchall(
        f"""
        SELECT
            e.id,
            e.numero_termo,
            e.dgm_escopo_termo,
            e.ativo,
            e.criado_por,
            e.criado_em,
            e.atualizado_por,
            e.atualizado_em,
            p.osc,
            p.projeto,
            p.tipo_termo,
            p.inicio,
            p.final,
            CASE
                WHEN p.inicio <= CURRENT_DATE AND p.final >= CURRENT_DATE THEN 'Vigente'
                WHEN p.final < CURRENT_DATE THEN 'Encerrado'
                WHEN p.inicio > CURRENT_DATE THEN 'Nao iniciado'
                ELSE '-'
            END AS status_vigencia,
            COUNT(eq.id) FILTER (WHERE eq.ativo = TRUE) AS equipamentos_count,
            COALESCE(
                JSONB_AGG(
                    JSONB_BUILD_OBJECT(
                        'id', eq.id,
                        'termo_equipamento', eq.termo_equipamento,
                        'ativo', eq.ativo
                    )
                    ORDER BY eq.ativo DESC, eq.termo_equipamento
                ) FILTER (WHERE eq.id IS NOT NULL),
                '[]'::jsonb
            ) AS equipamentos
        FROM gestao_monitoramento.parcerias_dgm_escopo e
        JOIN public.parcerias p
          ON p.numero_termo = e.numero_termo
        LEFT JOIN gestao_monitoramento.parcerias_equipamentos eq
          ON eq.numero_termo = e.numero_termo
        WHERE {' AND '.join(where)}
        GROUP BY e.id, p.numero_termo
        ORDER BY e.dgm_escopo_termo DESC, e.ativo DESC, e.numero_termo
        """,
        params,
    )
    for row in rows:
        row["equipamentos"] = list(row.get("equipamentos") or [])
    return rows


def obter_resumo() -> dict[str, Any]:
    return _fetchone(
        """
        SELECT
            COUNT(*) FILTER (WHERE ativo = TRUE) AS total_ativos,
            COUNT(*) FILTER (WHERE ativo = TRUE AND dgm_escopo_termo = TRUE) AS no_escopo,
            COUNT(*) FILTER (WHERE ativo = TRUE AND dgm_escopo_termo = FALSE) AS fora_escopo,
            COUNT(*) FILTER (WHERE ativo = FALSE) AS inativos
        FROM gestao_monitoramento.parcerias_dgm_escopo
        """
    ) or {"total_ativos": 0, "no_escopo": 0, "fora_escopo": 0, "inativos": 0}


def obter_escopo(escopo_id: int) -> dict[str, Any] | None:
    return _fetchone(
        """
        SELECT
            e.*,
            p.osc,
            p.projeto,
            p.tipo_termo,
            p.inicio,
            p.final
        FROM gestao_monitoramento.parcerias_dgm_escopo e
        JOIN public.parcerias p
          ON p.numero_termo = e.numero_termo
        WHERE e.id = %s
        """,
        (escopo_id,),
    )


def salvar_escopo(data, usuario: str) -> int:
    cur = get_cursor()
    db = get_db()
    try:
        cur.execute(
            """
            INSERT INTO gestao_monitoramento.parcerias_dgm_escopo (
                numero_termo,
                dgm_escopo_termo,
                ativo,
                criado_por,
                atualizado_por
            )
            VALUES (%s, %s, TRUE, %s, %s)
            ON CONFLICT (numero_termo) DO UPDATE
            SET dgm_escopo_termo = EXCLUDED.dgm_escopo_termo,
                ativo = TRUE,
                atualizado_por = EXCLUDED.atualizado_por,
                atualizado_em = NOW()
            RETURNING id
            """,
            (data.numero_termo, data.dgm_escopo_termo, usuario, usuario),
        )
        escopo_id = int(cur.fetchone()["id"])
        db.commit()
        return escopo_id
    except Exception:
        db.rollback()
        raise
    finally:
        cur.close()


def atualizar_escopo(escopo_id: int, dgm_escopo_termo: bool, usuario: str) -> bool:
    row = _fetchone(
        "SELECT id FROM gestao_monitoramento.parcerias_dgm_escopo WHERE id = %s",
        (escopo_id,),
    )
    if not row:
        return False
    _execute(
        """
        UPDATE gestao_monitoramento.parcerias_dgm_escopo
        SET dgm_escopo_termo = %s,
            ativo = TRUE,
            atualizado_por = %s,
            atualizado_em = NOW()
        WHERE id = %s
        """,
        (dgm_escopo_termo, usuario, escopo_id),
    )
    return True


def definir_ativo_escopo(escopo_id: int, ativo: bool, usuario: str) -> bool:
    row = _fetchone(
        "SELECT id FROM gestao_monitoramento.parcerias_dgm_escopo WHERE id = %s",
        (escopo_id,),
    )
    if not row:
        return False
    _execute(
        """
        UPDATE gestao_monitoramento.parcerias_dgm_escopo
        SET ativo = %s,
            atualizado_por = %s,
            atualizado_em = NOW()
        WHERE id = %s
        """,
        (ativo, usuario, escopo_id),
    )
    return True


def listar_equipamentos(numero_termo: str, *, incluir_inativos: bool = False) -> list[dict[str, Any]]:
    where_ativo = "" if incluir_inativos else "AND ativo = TRUE"
    return _fetchall(
        f"""
        SELECT id, numero_termo, termo_equipamento, ativo, criado_por, criado_em, atualizado_por, atualizado_em
        FROM gestao_monitoramento.parcerias_equipamentos
        WHERE numero_termo = %s
          {where_ativo}
        ORDER BY ativo DESC, termo_equipamento
        """,
        (numero_termo,),
    )


def criar_equipamento(numero_termo: str, data, usuario: str) -> int:
    cur = get_cursor()
    db = get_db()
    try:
        cur.execute(
            """
            INSERT INTO gestao_monitoramento.parcerias_equipamentos (
                numero_termo,
                termo_equipamento,
                criado_por,
                atualizado_por
            )
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (numero_termo, data.termo_equipamento, usuario, usuario),
        )
        equipamento_id = int(cur.fetchone()["id"])
        db.commit()
        return equipamento_id
    except Exception:
        db.rollback()
        raise
    finally:
        cur.close()


def criar_equipamentos(numero_termo: str, equipamentos: list[str], usuario: str) -> int:
    if not equipamentos:
        return 0

    cur = get_cursor()
    db = get_db()
    try:
        inseridos = 0
        for equipamento in equipamentos:
            cur.execute(
                """
                SELECT id
                FROM gestao_monitoramento.parcerias_equipamentos
                WHERE numero_termo = %s
                  AND LOWER(BTRIM(termo_equipamento)) = LOWER(BTRIM(%s))
                LIMIT 1
                """,
                (numero_termo, equipamento),
            )
            existente = cur.fetchone()
            if existente:
                cur.execute(
                    """
                    UPDATE gestao_monitoramento.parcerias_equipamentos
                    SET termo_equipamento = %s,
                        ativo = TRUE,
                        atualizado_por = %s,
                        atualizado_em = NOW()
                    WHERE id = %s
                    """,
                    (equipamento, usuario, existente["id"]),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO gestao_monitoramento.parcerias_equipamentos (
                        numero_termo,
                        termo_equipamento,
                        criado_por,
                        atualizado_por
                    )
                    VALUES (%s, %s, %s, %s)
                    """,
                    (numero_termo, equipamento, usuario, usuario),
                )
            inseridos += 1
        db.commit()
        return inseridos
    except Exception:
        db.rollback()
        raise
    finally:
        cur.close()


def atualizar_equipamento(equipamento_id: int, data, usuario: str) -> bool:
    row = _fetchone(
        "SELECT id FROM gestao_monitoramento.parcerias_equipamentos WHERE id = %s",
        (equipamento_id,),
    )
    if not row:
        return False
    _execute(
        """
        UPDATE gestao_monitoramento.parcerias_equipamentos
        SET termo_equipamento = %s,
            ativo = TRUE,
            atualizado_por = %s,
            atualizado_em = NOW()
        WHERE id = %s
        """,
        (data.termo_equipamento, usuario, equipamento_id),
    )
    return True


def definir_ativo_equipamento(equipamento_id: int, ativo: bool, usuario: str) -> bool:
    row = _fetchone(
        "SELECT id FROM gestao_monitoramento.parcerias_equipamentos WHERE id = %s",
        (equipamento_id,),
    )
    if not row:
        return False
    _execute(
        """
        UPDATE gestao_monitoramento.parcerias_equipamentos
        SET ativo = %s,
            atualizado_por = %s,
            atualizado_em = NOW()
        WHERE id = %s
        """,
        (ativo, usuario, equipamento_id),
    )
    return True

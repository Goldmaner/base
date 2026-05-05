from __future__ import annotations

import json
import os
import sys
import time
from urllib import error, request


def _resolve_api_key() -> str:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if api_key:
        return api_key

    # Fallback for Windows sessions started before `setx`.
    if sys.platform.startswith("win"):
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as key:
                value, _ = winreg.QueryValueEx(key, "GEMINI_API_KEY")
                return str(value).strip()
        except Exception:
            return ""

    return ""


def suggest_category_with_gemini(
    text: str,
    file_name: str,
    categories: dict,
    model: str | None = None,
    timeout: int = 25,
) -> dict:
    api_key = _resolve_api_key()
    if not api_key:
        return {"available": False, "error": "Defina a variavel GEMINI_API_KEY no ambiente."}

    category_list = [f"- {code}: {meta.get('label', code)}" for code, meta in categories.items()]
    prompt = (
        "Voce e um assistente de classificacao documental para prestacao de contas publica. "
        "Escolha somente uma categoria da lista e responda em JSON puro.\n\n"
        "Categorias permitidas:\n"
        + "\n".join(category_list)
        + "\n\n"
        "Arquivo: "
        + file_name
        + "\n"
        "Texto extraido (recortado):\n"
        + (text or "")[:6000]
        + "\n\n"
        "Responda SOMENTE em JSON no formato: "
        '{"categoria":"codigo","confianca":0,"justificativa":"...","termos":["..."]}'
    )

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
        },
    }

    preferred_model = model or os.environ.get("GEMINI_MODEL", "").strip() or "gemini-2.5-flash"
    model_candidates = [
        preferred_model,
        "gemini-2.0-flash",
        "gemini-2.0-flash-001",
        "gemini-2.0-flash-lite",
        "gemini-2.0-flash-lite-001",
    ]

    raw = ""
    used_model = preferred_model
    last_http_error = ""
    last_exception = ""
    retryable_codes = {429, 500, 502, 503, 504}
    max_attempts_per_model = 3

    for candidate in model_candidates:
        used_model = candidate
        for attempt in range(1, max_attempts_per_model + 1):
            endpoint = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{candidate}:generateContent?key={api_key}"
            )

            req = request.Request(
                endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            try:
                with request.urlopen(req, timeout=timeout) as resp:
                    raw = resp.read().decode("utf-8", errors="ignore")
                    break
            except error.HTTPError as exc:
                message = exc.read().decode("utf-8", errors="ignore") if hasattr(exc, "read") else str(exc)
                last_http_error = f"HTTP {exc.code}: {message[:260]}"

                # Non-existent/invalid model: switch to next model.
                if exc.code in (400, 404):
                    break

                # Temporary overload/transport errors: retry same model with backoff.
                if exc.code in retryable_codes and attempt < max_attempts_per_model:
                    time.sleep(0.8 * attempt)
                    continue

                # Other HTTP errors are returned immediately.
                if exc.code not in retryable_codes:
                    return {"available": False, "error": last_http_error}

                # Retryable error exhausted for this model; try next candidate.
                break
            except Exception as exc:  # pragma: no cover
                last_exception = str(exc)
                if attempt < max_attempts_per_model:
                    time.sleep(0.5 * attempt)
                    continue
                break

        if raw:
            break

    if not raw:
        if last_http_error:
            if "HTTP 503" in last_http_error:
                return {
                    "available": False,
                    "error": "HTTP 503: Gemini com alta demanda no momento. Tente novamente em alguns instantes.",
                }
            return {"available": False, "error": last_http_error}
        if last_exception:
            return {"available": False, "error": last_exception}
        return {"available": False, "error": "Nao foi possivel obter resposta da IA."}

    try:
        data = json.loads(raw)
        model_text = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
            .strip()
        )
        if not model_text:
            return {"available": False, "error": "Resposta vazia do Gemini."}

        parsed = json.loads(model_text)
    except Exception as exc:
        return {"available": False, "error": f"Falha ao interpretar resposta da IA: {exc}"}

    categoria = str(parsed.get("categoria", "")).strip().lower()
    if categoria not in categories:
        return {
            "available": False,
            "error": f"Categoria sugerida fora da lista permitida: {categoria or 'vazia'}.",
        }

    confianca = parsed.get("confianca", 0)
    try:
        confianca_float = float(confianca)
    except (TypeError, ValueError):
        confianca_float = 0.0
    if 0.0 <= confianca_float <= 1.0:
        confianca_float *= 100.0
    confianca_float = max(0.0, min(100.0, confianca_float))

    termos = parsed.get("termos", [])
    if not isinstance(termos, list):
        termos = []

    return {
        "available": True,
        "modelo": used_model,
        "categoria": categoria,
        "label": categories.get(categoria, {}).get("label", categoria),
        "confianca": round(confianca_float, 1),
        "justificativa": str(parsed.get("justificativa", "")).strip(),
        "termos": [str(item).strip() for item in termos if str(item).strip()][:8],
    }
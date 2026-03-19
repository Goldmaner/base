"""
Busca no Diário Oficial da Cidade de SP (DOC-SP) o histórico de nomeação
e exoneração dos servidores e estagiários da SMDHC.

Como funciona:
  - Faz POST para ?acao=materias_pesquisar com hdnModoPesquisa=RAPIDA
  - Busca nas versões A (após 01/03/2023) e L (antes de 01/03/2023)
  - Para servidores: usa o R.F. como identificador (alta precisão)
  - Para estagiários: usa o nome completo + filtra por SMDHC no resumo

Saída: buscar_historico_doc_resultado.xlsx  (na raiz do projeto)

Uso:
    python scripts/buscar_historico_doc.py
"""

import re
import time
import logging
from datetime import datetime

import requests
from bs4 import BeautifulSoup
import pandas as pd

# ---------------------------------------------------------------------------
# Configuração de log
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lista de colaboradores
# Campos: nome, rf, tipo, status
# ---------------------------------------------------------------------------
COLABORADORES = [
    {"nome": "Amanda Priscila da Silva Oliveira", "rf": "",          "tipo": "Estagiário(a)",         "status": "Ativo"},
    {"nome": "Ana Caroline de Aguiar",            "rf": "812.868-5", "tipo": "Servidor(a)",            "status": "Inativo"},
    {"nome": "André Liberato da Silva",           "rf": "851.715-1", "tipo": "Servidor(a)",            "status": "Inativo"},
    {"nome": "André Mezzalira",                   "rf": "729.022-5", "tipo": "Servidor(a)",            "status": "Inativo"},
    {"nome": "Bárbara Capuano Machado",           "rf": "843.991-5", "tipo": "Servidor(a)",            "status": "Inativo"},
    {"nome": "Carla Cintia Quirino Santos",       "rf": "914.755-1", "tipo": "Servidor(a)",            "status": "Ativo"},
    {"nome": "Carla Kubalak de Oliveira",         "rf": "851.744-4", "tipo": "Servidor(a)",            "status": "Inativo"},
    {"nome": "Cauê Marinho",                      "rf": "",          "tipo": "Estagiário(a)",         "status": "Inativo"},
    {"nome": "Daniel Guedes dos Santos",          "rf": "851.709-6", "tipo": "Servidor(a) Temporário(a)", "status": "Inativo"},
    {"nome": "Danilo Fagundes Vittorete",         "rf": "824.675-1", "tipo": "Servidor(a)",            "status": "Inativo"},
    {"nome": "Dayana Pimentel da Silva",          "rf": "851.701-1", "tipo": "Servidor(a) Temporário(a)", "status": "Inativo"},
    {"nome": "Denise de Cássia Santos Rodrigues", "rf": "851.736-3", "tipo": "Servidor(a)",            "status": "Inativo"},
    {"nome": "Eloisa Gabriel Barbosa dos Santos", "rf": "851.716-9", "tipo": "Servidor(a)",            "status": "Inativo"},
    {"nome": "Esdras dos Santos Silva",           "rf": "",          "tipo": "Estagiário(a)",         "status": "Inativo"},
    {"nome": "Fernanda Galvão Alves",             "rf": "851.714-2", "tipo": "Servidor(a)",            "status": "Inativo"},
    {"nome": "Gustavo de Oliveira Carvalho",      "rf": "880.387-1", "tipo": "Servidor(a)",            "status": "Inativo"},
    {"nome": "Hélen Cristina Melo da Silva Luiz", "rf": "849.069-4", "tipo": "Servidor(a)",            "status": "Inativo"},
    {"nome": "Ingrid Felipe Melo",                "rf": "",          "tipo": "Estagiário(a)",         "status": "Ativo"},
    {"nome": "Jefferson de Almeida Luiz",         "rf": "843.702-5", "tipo": "Servidor(a)",            "status": "Ativo"},
    {"nome": "Julio Claudio Gurgueira",           "rf": "853.398-9", "tipo": "Servidor(a)",            "status": "Inativo"},
    {"nome": "Kátia dos Santos Ribeiro da Silva", "rf": "804.598-4", "tipo": "Servidor(a)",            "status": "Inativo"},
    {"nome": "Laís Vitória dos Santos",           "rf": "878.858-8", "tipo": "Servidor(a)",            "status": "Inativo"},
    {"nome": "Larissa de Jesus Martins",          "rf": "809.065-3", "tipo": "Servidor(a)",            "status": "Inativo"},
    {"nome": "Leandro Alves Cachoeira",           "rf": "911.246-4", "tipo": "Servidor(a)",            "status": "Inativo"},
    {"nome": "Leticia Lourenço Macedo",           "rf": "883.300-1", "tipo": "Servidor(a)",            "status": "Ativo"},
    {"nome": "Luana Ramos Moreira",               "rf": "858.662-4", "tipo": "Servidor(a)",            "status": "Inativo"},
    {"nome": "Lucas Castelani de Meireles",       "rf": "858.674-8", "tipo": "Servidor(a)",            "status": "Ativo"},
    {"nome": "Lucas Detusk Aguilar",              "rf": "858.988-7", "tipo": "Servidor(a)",            "status": "Inativo"},
    {"nome": "Luiz Augusto Simões",               "rf": "851.001-6", "tipo": "Servidor(a)",            "status": "Ativo"},
    {"nome": "Luiz Cláudio Rodrigues",            "rf": "851.724-0", "tipo": "Servidor(a)",            "status": "Inativo"},
    {"nome": "Maira Ferreira da Cunha",           "rf": "855.452-8", "tipo": "Servidor(a)",            "status": "Inativo"},
    {"nome": "Maira Mihara Teixeira",             "rf": "924.948-6", "tipo": "Servidor(a)",            "status": "Ativo"},
    {"nome": "Márcia Magnólia Souza Oliveira",    "rf": "827.285-5", "tipo": "Servidor(a)",            "status": "Inativo"},
    {"nome": "Marjhory de Souza Silva",           "rf": "",          "tipo": "Estagiário(a)",         "status": "Inativo"},
    {"nome": "Mateus Alves Rodrigues",            "rf": "",          "tipo": "Estagiário(a)",         "status": "Inativo"},
    {"nome": "Matheus Bolorino Pires",            "rf": "851.702-9", "tipo": "Servidor(a)",            "status": "Inativo"},
    {"nome": "Murilo Ramos Pereira Santos",       "rf": "881.121-1", "tipo": "Servidor(a)",            "status": "Inativo"},
    {"nome": "Paloma Cavalcante de Moraes",       "rf": "",          "tipo": "Servidor(a)",            "status": "Ativo"},
    {"nome": "Rebecka Molinari Gomes",            "rf": "",          "tipo": "Estagiário(a)",         "status": "Ativo"},
    {"nome": "Reinaldo Alexandro Salis Rossi",    "rf": "926.744-1", "tipo": "Servidor(a)",            "status": "Ativo"},
    {"nome": "Rosa Maria de Araújo",              "rf": "507.382-1", "tipo": "Servidor(a) Temporário(a)", "status": "Ativo"},
    {"nome": "Sabrina de Castro Amaral",          "rf": "792.571-9", "tipo": "Servidor(a)",            "status": "Inativo"},
    {"nome": "Shirley da Silva Firme",            "rf": "795.017-9", "tipo": "Servidor(a)",            "status": "Inativo"},
    {"nome": "Thays Rocha",                       "rf": "847.418-4", "tipo": "Servidor(a)",            "status": "Ativo"},
    {"nome": "Thiago Gimenes Diogo",              "rf": "851.821-1", "tipo": "Servidor(a)",            "status": "Inativo"},
    {"nome": "Valdineia Oliveira Pereira",        "rf": "823.189-3", "tipo": "Servidor(a)",            "status": "Inativo"},
    {"nome": "Victor Medereiros da Nobrega",      "rf": "",          "tipo": "Estagiário(a)",         "status": "Inativo"},
    {"nome": "William Mendes Lira",               "rf": "770.357-1", "tipo": "Servidor(a)",            "status": "Inativo"},
]

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
DOC_BASE = "https://diariooficial.prefeitura.sp.gov.br"
DOC_SEARCH_URL = DOC_BASE + "/md_epubli_controlador.php"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Referer": DOC_SEARCH_URL + "?acao=materias_pesquisar",
    "Content-Type": "application/x-www-form-urlencoded",
    "Origin": DOC_BASE,
}
# Versões do diário: "A" = após 01/03/2023  |  "L" = anterior a 01/03/2023
VERSOES = ["A", "L"]
SMDHC_TERMOS = ["smdhc", "direitos humanos", "cidadania"]
TERMOS_INICIO = ["nomeação", "nomeacao", "admissão", "admissao", "designação",
                 "designacao", "contratação", "contratacao", "posse"]
TERMOS_FIM    = ["exoneração", "exoneracao", "dispensa", "rescisão", "rescisao",
                 "demissão", "demissao", "encerramento", "cessação", "cessacao"]
DELAY_ENTRE_CONSULTAS = 2   # segundos
MAX_PAGINAS           = 5   # páginas de resultados por versão (10 docs cada)

# ---------------------------------------------------------------------------
# Sessão HTTP (reutilizada para manter cookies)
# ---------------------------------------------------------------------------
_session: requests.Session | None = None

def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.get(DOC_SEARCH_URL + "?acao=materias_pesquisar",
                     headers=HEADERS, timeout=20)
    return _session

# ---------------------------------------------------------------------------
# Funções auxiliares
# ---------------------------------------------------------------------------

def _normalizar(texto: str) -> str:
    """Minúsculas sem acentos para comparação."""
    import unicodedata
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()


def _extrair_data_publicacao(span_tag) -> str | None:
    """Extrai DD/MM/AAAA de span.dataPublicacao ('Publicado em DD/MM/AAAA')."""
    if span_tag is None:
        return None
    match = re.search(r"\b(\d{2}/\d{2}/\d{4})\b", span_tag.get_text())
    return match.group(1) if match else None


def _extrair_data_no_texto(texto: str) -> str | None:
    """Tenta extrair data dentro do texto ('a partir de DD/MM/AAAA', etc.)."""
    match = re.search(
        r"(?:a partir de|em|até|até o dia)\s+(\d{2}/\d{2}/\d{4})", texto, re.IGNORECASE
    )
    if match:
        return match.group(1)
    match = re.search(r"\b(\d{2}/\d{2}/\d{4})\b", texto)
    return match.group(1) if match else None


def _eh_smdhc(texto: str) -> bool:
    texto_norm = _normalizar(texto)
    return any(t in texto_norm for t in SMDHC_TERMOS)


def _classificar(texto: str) -> str:
    """Retorna 'inicio', 'fim' ou 'outro' conforme o conteúdo."""
    texto_norm = _normalizar(texto)
    if any(t in texto_norm for t in TERMOS_INICIO):
        return "inicio"
    if any(t in texto_norm for t in TERMOS_FIM):
        return "fim"
    return "outro"


def _to_date(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%d/%m/%Y")
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Busca no DOC-SP
# ---------------------------------------------------------------------------

def _buscar_pagina(termo: str, versao: str, pagina: int) -> list[dict]:
    """
    Faz POST ao DOC-SP e retorna lista de dicts com:
        data_pub, texto_resumo, link_doc, classificacao
    """
    payload = {
        "hdnTermoPesquisa":            termo,
        "hdnTipoPesquisa":             "E",      # E = expressão exata
        "hdnModoPesquisa":             "RAPIDA",
        "hdnVersaoDiario":             versao,
        "hdnOndePesquisa":             "",
        "hdnTipoDataPesquisa":         "",
        "hdnDataInicioPesquisa":       "",
        "hdnDataFimPesquisa":          "",
        "hdnTipoDocumentoPesquisa":    "",
        "hdnVeiculoPublicacao":        "",
        "hdnDataPublicacao":           "",
        "hdnOrgaoFiltro":              "",
        "hdnUnidadeResponsavelFiltro": "",
        "hdnTipoDocumentoFiltro":      "",
        "hdnInicio":                   str(pagina * 10),
        "hdnVisualizacao":             "L",
    }
    try:
        r = _get_session().post(
            DOC_SEARCH_URL + "?acao=materias_pesquisar",
            data=payload,
            headers=HEADERS,
            timeout=25,
        )
        r.raise_for_status()
    except requests.RequestException as exc:
        log.warning("    Falha na requisição (versão=%s pág=%d): %s", versao, pagina, exc)
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    resultados = []

    for doc in soup.find_all("div", class_="dadosDocumento"):
        span_data = doc.find("span", class_="dataPublicacao")
        resumo_p  = doc.find("p",    class_="resumoDocumento")
        link_a    = doc.find("a",    class_="nroSei")

        data_pub    = _extrair_data_publicacao(span_data)
        texto       = resumo_p.get_text(" ", strip=True) if resumo_p else ""
        link        = link_a["href"] if link_a else ""
        classif     = _classificar(texto)

        resultados.append({
            "data_pub":      data_pub,
            "texto_resumo":  texto,
            "link_doc":      link,
            "classificacao": classif,
        })

    return resultados


def _total_resultados(termo: str, versao: str) -> int:
    """Retorna o total de resultados reportado pelo DOC para este termo+versão."""
    payload = {
        "hdnTermoPesquisa": termo,
        "hdnTipoPesquisa":  "E",
        "hdnModoPesquisa":  "RAPIDA",
        "hdnVersaoDiario":  versao,
        "hdnInicio":        "0",
        "hdnVisualizacao":  "L",
    }
    try:
        r = _get_session().post(
            DOC_SEARCH_URL + "?acao=materias_pesquisar",
            data=payload, headers=HEADERS, timeout=25,
        )
        r.raise_for_status()
    except requests.RequestException:
        return 0

    soup = BeautifulSoup(r.text, "html.parser")
    spans = soup.find_all("span", class_="nroResultados")
    if spans:
        try:
            return int(spans[-1].get_text(strip=True).replace(".", ""))
        except ValueError:
            pass
    return 0


# ---------------------------------------------------------------------------
# Lógica principal de extração por pessoa
# ---------------------------------------------------------------------------

def _buscar_datas(identificador: str, eh_estagiario: bool) -> dict:
    """
    Varre todas as publicações do DOC sobre `identificador` e identifica:
      - início do contrato (nomeação/admissão mais antiga)
      - fim do contrato (exoneração/dispensa mais recente)
    Retorna:
      {"inicio", "fim", "link_inicio", "link_fim", "observacoes"}
    """
    candidatos_inicio: list[tuple] = []  # (datetime, data_str, link)
    candidatos_fim:    list[tuple] = []
    todos_docs: list[tuple] = []          # fallback: todos os docs encontrados

    for versao in VERSOES:
        total = _total_resultados(identificador, versao)
        log.debug("    versão=%s total=%d", versao, total)
        n_paginas = min(MAX_PAGINAS, (total + 9) // 10) if total > 0 else 1
        time.sleep(DELAY_ENTRE_CONSULTAS)

        for pg in range(n_paginas):
            resultados = _buscar_pagina(identificador, versao, pg)
            time.sleep(DELAY_ENTRE_CONSULTAS)

            for res in resultados:
                texto   = res["texto_resumo"]
                classif = res["classificacao"]
                link    = res["link_doc"]

                if eh_estagiario and not _eh_smdhc(texto):
                    continue

                data_str = _extrair_data_no_texto(texto) or res["data_pub"]
                dt = _to_date(data_str)
                if dt is None:
                    continue

                todos_docs.append((dt, data_str, link))

                if classif == "inicio":
                    candidatos_inicio.append((dt, data_str, link))
                elif classif == "fim":
                    candidatos_fim.append((dt, data_str, link))

    # Se não encontrou início explícito, usa o doc mais antigo como proxy
    if not candidatos_inicio and todos_docs:
        candidatos_inicio = [min(todos_docs, key=lambda x: x[0])]
        ini_proxy = True
    else:
        ini_proxy = False

    ini = min(candidatos_inicio, key=lambda x: x[0]) if candidatos_inicio else None
    fim = max(candidatos_fim,    key=lambda x: x[0]) if candidatos_fim    else None

    obs_parts = []
    if not todos_docs:
        obs_parts.append("Nenhuma publicação encontrada no DOC.")
    else:
        if ini_proxy:
            obs_parts.append("Início estimado pela publicação mais antiga (sem termo explícito de nomeação).")
        if not candidatos_fim:
            obs_parts.append("Data de fim não localizada (pode estar ativo ou não indexado).")

    return {
        "inicio":      ini[1] if ini else None,
        "fim":         fim[1] if fim else None,
        "link_inicio": ini[2] if ini else "",
        "link_fim":    fim[2] if fim else "",
        "observacoes": " | ".join(obs_parts),
    }


# ---------------------------------------------------------------------------
# Execução principal
# ---------------------------------------------------------------------------

def main():
    log.info("Iniciando busca no DOC-SP para %d colaboradores.", len(COLABORADORES))

    registros = []

    for i, pessoa in enumerate(COLABORADORES, 1):
        nome   = pessoa["nome"]
        rf     = pessoa["rf"]
        tipo   = pessoa["tipo"]
        status = pessoa["status"]
        eh_est = "stagiário" in tipo

        log.info("[%d/%d] %s (RF: %s)", i, len(COLABORADORES), nome, rf or "—")

        # Identificador preferencial: RF para servidores, nome para estagiários
        identificador = rf if rf else nome

        datas = _buscar_datas(identificador, eh_est)

        registros.append({
            "Nome":               nome,
            "R.F.":               rf,
            "Tipo":               tipo,
            "Status":             status,
            "Início do Contrato": datas["inicio"] or "",
            "Fim do Contrato":    datas["fim"]    or "",
            "Link Início (DOC)":  datas["link_inicio"],
            "Link Fim (DOC)":     datas["link_fim"],
            "Observações":        datas["observacoes"],
        })

        # Salva parcialmente a cada 5 pessoas (evita perda em caso de erro)
        if i % 5 == 0:
            pd.DataFrame(registros).to_csv(
                "buscar_historico_doc_parcial.csv",
                index=False, encoding="utf-8-sig",
            )
            log.info("  -> Checkpoint parcial salvo (%d/%d)", i, len(COLABORADORES))

    df = pd.DataFrame(registros)

    saida_xlsx = "buscar_historico_doc_resultado.xlsx"
    saida_csv  = "buscar_historico_doc_resultado.csv"

    # Excel com formatação básica
    with pd.ExcelWriter(saida_xlsx, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Histórico DOC")
        ws = writer.sheets["Histórico DOC"]
        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 60)

    df.to_csv(saida_csv, index=False, encoding="utf-8-sig")

    log.info("Concluído! Arquivos gerados:")
    log.info("  %s", saida_xlsx)
    log.info("  %s", saida_csv)


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import json
import os
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from deduplicador import Deduplicador, normalize_text, normalize_url
from emailer import send_report, smtp_configured


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
REPORTS_DIR = ROOT / "reports"

VAGAS_PATH = DATA_DIR / "vagas.json"
INTERNACIONAL_PATH = DATA_DIR / "internacional.json"
HISTORICO_PATH = DATA_DIR / "historico_radar.json"
DESCARTES_PATH = DATA_DIR / "descartes.json"
CONFIG_PATH = DATA_DIR / "configuracao_lucas.json"

TERMOS_PRIORITARIOS = [
    "estágio engenharia elétrica Campinas",
    "estágio energia Campinas",
    "estágio data center Brasil",
    "Equinix estágio Brasil",
    "Ascenty vagas estágio",
    "Scala Data Centers vagas",
    "Elea Data Centers vagas",
    "ODATA Aligned vagas",
    "Vertiv estágio Brasil",
    "Schneider Electric estágio Brasil",
    "Eaton estágio Brasil",
    "WEG estágio engenharia elétrica",
    "GE Vernova estágio Brasil",
    "CPFL estágio engenharia",
    "Siemens Energy estágio Brasil",
    "CNPEM estágio engenharia",
    "PwC estágio consultoria",
    "Visagio estágio",
    "Accenture estágio consultoria",
    "McKinsey internship Brazil",
    "BCG internship Brazil",
    "IAESTE electrical engineering internship",
    "OIST research internship",
    "DAAD engineering scholarship",
    "Erasmus Mundus energy engineering",
    "MEXT research student electrical engineering",
]

GOOD_TERMS = (
    "energia",
    "engenharia",
    "elétrica",
    "eletrica",
    "data center",
    "datacenter",
    "infraestrutura",
    "processos",
    "dados",
    "analytics",
    "consultoria",
    "strategy",
    "internship",
    "estágio",
    "estagio",
    "bolsa",
    "scholarship",
    "research",
    "funded",
    "smart grid",
)
BAD_TERMS = (
    "comercial",
    "vendas",
    "loja",
    "operador",
    "telemarketing",
    "sem bolsa",
    "self-funded",
    "self funded",
    "tuition fee",
)
INTERNATIONAL_TERMS = (
    "scholarship",
    "erasmus",
    "mext",
    "daad",
    "oist",
    "iaeste",
    "internship",
    "research",
    "master",
    "masters",
    "funded",
)
BLOCKED_AUTO_NEW_DOMAINS = (
    "linkedin.com",
    "indeed.com",
    "glassdoor.com",
    "reddit.com",
    "instagram.com",
    "facebook.com",
    "youtube.com",
    "opportunitiescorners.com",
    "opportunitydesk.org",
    "gyanmirai.com",
    "japan-dev.com",
    "hackingthecaseinterview.com",
    "theforage.com",
)
SOCIAL_DOMAINS = (
    "reddit.com",
    "instagram.com",
    "facebook.com",
    "youtube.com",
    "tiktok.com",
    "x.com",
    "twitter.com",
)
NEWS_DOMAINS = (
    "g1.globo.com",
    "globo.com",
    "uol.com.br",
    "folha.uol.com.br",
    "estadao.com.br",
    "exame.com",
    "valor.globo.com",
    "cnnbrasil.com.br",
    "bbc.com",
)
APPLY_SOURCE_DOMAINS = (
    "gupy.io",
    "myworkdayjobs.com",
    "workdayjobs.com",
    "greenhouse.io",
    "lever.co",
    "99jobs.com",
    "ciadetalentos.com.br",
    "ciadeestagios.com.br",
    "nube.com.br",
    "companhiadeestagios.com.br",
)
OFFICIAL_INTERNATIONAL_DOMAINS = (
    "oist.jp",
    "daad.de",
    "iaeste.org",
    "europa.eu",
    "ec.europa.eu",
    "erasmus-plus.ec.europa.eu",
    "campusfrance.org",
    "br.emb-japan.go.jp",
)
ACADEMIC_DOMAIN_PARTS = (
    ".edu",
    ".ac.",
    ".edu.",
    ".university",
)
GENERIC_JOB_BOARD_DOMAINS = (
    "linkedin.com",
    "indeed.com",
    "glassdoor.com",
    "jooble.org",
    "simplyhired.com",
    "catho.com.br",
    "infojobs.com.br",
    "vagas.com.br",
    "empregos.com.br",
)
GENERIC_RESULT_TERMS = (
    "vagas de",
    "vagas para",
    "empregos de",
    "salarios",
    "salario",
    "salary",
    "search jobs",
    "job search",
    "resultados",
    "busca",
)
SPECIFIC_OPPORTUNITY_TERMS = (
    "estagio",
    "internship",
    "trainee",
    "programa",
    "bolsa",
    "scholarship",
    "research internship",
    "summer",
    "analyst",
    "engenheiro",
    "engenheira",
    "consultor",
    "consultora",
)
OFFICIAL_PATH_TERMS = (
    "career",
    "careers",
    "carreira",
    "carreiras",
    "jobs",
    "vagas",
    "apply",
    "application",
    "candidatura",
    "program",
    "programa",
    "early-careers",
    "estagio",
    "internship",
)


@dataclass
class RadarResult:
    candidate: dict[str, Any]
    destino: str
    classificacao: str
    prioridade: int
    motivo: str
    duplicate_reason: str
    duplicate_score: float


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(read_text_preserving_legacy_encoding(path))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ": ")),
        encoding=detect_encoding(path),
    )


def detect_encoding(path: Path) -> str:
    if not path.exists():
        return "utf-8"
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            raw.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue
    return "utf-8"


def read_text_preserving_legacy_encoding(path: Path) -> str:
    return path.read_text(encoding=detect_encoding(path))


def today_string() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def slugify(value: str) -> str:
    value = normalize_text(value)
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value[:80] or "oportunidade"


def domain_from_url(url: str) -> str:
    parsed = urlparse(url if "://" in url else f"https://{url}")
    host = (parsed.netloc or parsed.path.split("/")[0]).casefold()
    return re.sub(r"^www\.", "", host)


def domain_matches(domain: str, blocked_domains: tuple[str, ...]) -> bool:
    return any(domain == blocked or domain.endswith(f".{blocked}") for blocked in blocked_domains)


def source_text(value: str) -> str:
    normalized = normalize_text(value)
    return "".join(
        char for char in unicodedata.normalize("NFKD", normalized) if not unicodedata.combining(char)
    )


def source_details(candidate: dict[str, Any]) -> tuple[str, str]:
    title = str(candidate.get("opportunity") or candidate.get("program") or candidate.get("title") or "")
    url = str(candidate.get("applyUrl") or candidate.get("url") or candidate.get("companyUrl") or "")
    return url, title


def is_social_or_news_source(url: str) -> bool:
    domain = domain_from_url(url)
    return domain_matches(domain, SOCIAL_DOMAINS) or domain_matches(domain, NEWS_DOMAINS)


def is_hard_veto_domain(url: str) -> bool:
    return domain_matches(domain_from_url(url), BLOCKED_AUTO_NEW_DOMAINS)


def is_low_value_hard_veto_source(url: str, title: str) -> bool:
    text = source_text(f"{title} {url}")
    parsed = urlparse(url if "://" in url else f"https://{url}")
    raw_path = parsed.path.casefold()
    path = source_text(parsed.path)
    query = source_text(parsed.query)
    low_value_terms = (
        "comentario",
        "comentarios",
        "comment",
        "comments",
        "post",
        "posts",
        "activity",
        "salario",
        "salarios",
        "salary",
        "review",
        "reviews",
        "forum",
        "search",
        "busca",
        "vagas de",
        "empregos de",
    )
    low_value_paths = (
        "/posts/",
        "/post/",
        "/p/",
        "/reel/",
        "/watch",
        "/activity",
        "/feed/",
        "/search",
        "/jobs/search",
    )

    return (
        any(term in text for term in low_value_terms)
        or any(part in raw_path for part in low_value_paths)
        or bool(query and any(part in raw_path for part in ("/search", "/jobs", "/vagas")))
    )


def is_generic_job_board_result(url: str, title: str) -> bool:
    domain = domain_from_url(url)
    text = source_text(f"{title} {url}")
    parsed = urlparse(url if "://" in url else f"https://{url}")
    path = source_text(parsed.path)
    query = source_text(parsed.query)

    if domain_matches(domain, GENERIC_JOB_BOARD_DOMAINS):
        return True
    if any(term in text for term in GENERIC_RESULT_TERMS):
        return True
    if any(part in path for part in ("/search", "/jobs", "/vagas")) and query:
        return True
    return False


def is_official_or_apply_source(url: str, title: str) -> bool:
    domain = domain_from_url(url)
    text = source_text(f"{title} {url}")
    parsed = urlparse(url if "://" in url else f"https://{url}")
    path = source_text(parsed.path)

    if not domain or domain_matches(domain, BLOCKED_AUTO_NEW_DOMAINS):
        return False
    if is_social_or_news_source(url) or is_generic_job_board_result(url, title):
        return False

    has_specific_title = any(term in text for term in SPECIFIC_OPPORTUNITY_TERMS)
    has_apply_domain = domain_matches(domain, APPLY_SOURCE_DOMAINS)
    has_official_path = any(term in path for term in OFFICIAL_PATH_TERMS)
    has_career_subdomain = domain.split(".")[0] in {"career", "careers", "carreira", "carreiras", "jobs", "vagas"}
    has_identifiable_source = bool(domain.split(".")[0]) and domain not in {"google.com", "bing.com"}

    return has_identifiable_source and has_specific_title and (has_apply_domain or has_official_path or has_career_subdomain)


def is_official_international_source(url: str, title: str) -> bool:
    domain = domain_from_url(url)
    if not domain or domain_matches(domain, BLOCKED_AUTO_NEW_DOMAINS):
        return False
    if is_social_or_news_source(url) or is_generic_job_board_result(url, title):
        return False
    if domain_matches(domain, OFFICIAL_INTERNATIONAL_DOMAINS):
        return True
    return any(part in domain for part in ACADEMIC_DOMAIN_PARTS) and is_official_or_apply_source(url, title)


def is_official_career_source(url: str, title: str) -> bool:
    domain = domain_from_url(url)
    parsed = urlparse(url if "://" in url else f"https://{url}")
    path = source_text(parsed.path)
    has_career_subdomain = domain.split(".")[0] in {"career", "careers", "carreira", "carreiras", "jobs", "vagas"}
    if not domain or domain_matches(domain, BLOCKED_AUTO_NEW_DOMAINS):
        return False
    if is_social_or_news_source(url) or is_generic_job_board_result(url, title):
        return False
    return domain_matches(domain, APPLY_SOURCE_DOMAINS) or has_career_subdomain or any(term in path for term in OFFICIAL_PATH_TERMS)


def has_minimum_lucas_fit(candidate: dict[str, Any]) -> bool:
    text = source_text(" ".join(str(value) for value in candidate.values()))
    good_score = sum(1 for term in GOOD_TERMS if source_text(term) in text)
    bad_score = sum(1 for term in BAD_TERMS if source_text(term) in text)
    return good_score >= 2 and bad_score < 2


def hard_veto_classification(candidate: dict[str, Any], duplicate_reason: str) -> tuple[str, int, str] | None:
    if duplicate_reason != "novo":
        return None

    url, title = source_details(candidate)
    if not is_hard_veto_domain(url):
        return None

    if is_low_value_hard_veto_source(url, title) or is_generic_job_board_result(url, title):
        return "descartada", 15, "Fonte vetada para nova entrada automatica: agregador, post social, comentario, salario ou busca ampla."
    if has_minimum_lucas_fit(candidate):
        return "monitorar", 30, "Fonte vetada para nova entrada automatica; usar apenas como sinal secundario e procurar a fonte oficial."
    return "descartada", 15, "Fonte vetada e sem sinais suficientes para monitoramento."


def calibrate_source_classification(
    candidate: dict[str, Any],
    destino: str,
    classificacao: str,
    prioridade: int,
    motivo: str,
) -> tuple[str, int, str]:
    if classificacao == "repetida":
        return classificacao, prioridade, motivo

    url, title = source_details(candidate)
    domain = domain_from_url(url)
    blocked_auto_new = domain_matches(domain, BLOCKED_AUTO_NEW_DOMAINS) or is_social_or_news_source(url)
    generic_board = is_generic_job_board_result(url, title)
    official_apply = is_official_or_apply_source(url, title)
    official_international = is_official_international_source(url, title)
    official_career = is_official_career_source(url, title)
    has_fit = has_minimum_lucas_fit(candidate)

    if blocked_auto_new:
        if is_low_value_hard_veto_source(url, title) or generic_board:
            return "descartada", min(max(prioridade, 10), 20), "Fonte vetada para nova entrada automatica: agregador, post social, comentario, salario ou busca ampla."
        if is_social_or_news_source(url):
            return "monitorar", min(max(prioridade, 10), 35), "Fonte social/noticia: usar apenas como sinal secundario, sem entrada automatica no Atlas."
        return "monitorar", min(max(prioridade, 30), 50), "Agregador ou fonte bloqueada para nova entrada automatica; validar fonte oficial antes."

    if generic_board:
        return "monitorar", min(max(prioridade, 30), 50), "Resultado de agregador ou busca generica; monitorar e procurar candidatura oficial."

    if destino == "internacional" and classificacao in {"nova", "atualizacao"} and not official_international:
        return "monitorar", min(max(prioridade, 30), 55), "Fonte internacional nao oficial; validar edital ou pagina institucional antes de entrar no Atlas."

    if official_apply and (destino != "internacional" or official_international) and has_fit:
        if classificacao in {"nova", "atualizacao"}:
            return classificacao, min(95, max(prioridade, 75)), motivo
        return "nova", min(95, max(prioridade, 75)), "Fonte oficial de candidatura com aderencia minima ao perfil do Lucas."

    if official_career:
        return "monitorar", min(max(prioridade, 45), 60), "Pagina oficial de carreira/programa sem vaga especifica suficiente para entrada automatica."

    if classificacao in {"nova", "atualizacao"}:
        return "monitorar", min(max(prioridade, 30), 60), "Faltam sinais fortes de fonte oficial, candidatura confiavel ou oportunidade especifica."
    return classificacao, prioridade, motivo


def infer_company(title: str, link: str) -> str:
    known = [
        "Equinix",
        "Ascenty",
        "Scala Data Centers",
        "Elea Data Centers",
        "ODATA",
        "Aligned",
        "Vertiv",
        "Schneider Electric",
        "Eaton",
        "WEG",
        "GE Vernova",
        "CPFL",
        "Siemens Energy",
        "CNPEM",
        "PwC",
        "Visagio",
        "Accenture",
        "McKinsey",
        "BCG",
        "IAESTE",
        "OIST",
        "DAAD",
        "Erasmus Mundus",
        "MEXT",
    ]
    haystack = f"{title} {link}".casefold()
    for company in known:
        if company.casefold() in haystack:
            return company
    host = re.sub(r"^www\.", "", re.sub(r"^https?://", "", link).split("/")[0])
    if host:
        return host.split(".")[0].title()
    return "A confirmar"


def is_international(query: str, title: str, snippet: str) -> bool:
    text = normalize_text(f"{query} {title} {snippet}")
    return any(term in text for term in INTERNATIONAL_TERMS) and "brasil" not in text


def search_web(query: str) -> list[dict[str, str]]:
    import requests

    api_key = os.getenv("SEARCH_API_KEY")
    if not api_key:
        return []

    endpoint = os.getenv("SEARCH_API_ENDPOINT") or "https://google.serper.dev/search"
    timeout = int(os.getenv("SEARCH_TIMEOUT") or "30")

    if "serper.dev" in endpoint:
        response = requests.post(
            endpoint,
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": query, "num": int(os.getenv("SEARCH_RESULTS_PER_QUERY") or "5")},
            timeout=timeout,
        )
    else:
        response = requests.get(
            endpoint,
            headers={"Authorization": f"Bearer {api_key}"},
            params={"q": query, "count": int(os.getenv("SEARCH_RESULTS_PER_QUERY") or "5")},
            timeout=timeout,
        )

    response.raise_for_status()
    data = response.json()
    raw_results = (
        data.get("organic")
        or data.get("organic_results")
        or data.get("results")
        or data.get("items")
        or data.get("webPages", {}).get("value")
        or []
    )

    results = []
    for item in raw_results:
        title = item.get("title") or item.get("name") or ""
        link = item.get("link") or item.get("url") or item.get("displayLink") or ""
        snippet = item.get("snippet") or item.get("description") or item.get("content") or ""
        if title and link:
            results.append({"title": title, "link": link, "snippet": snippet, "query": query})
    return results


def search_all(terms: list[str]) -> tuple[list[dict[str, str]], list[str]]:
    seen_urls: set[str] = set()
    results: list[dict[str, str]] = []
    errors: list[str] = []

    if not os.getenv("SEARCH_API_KEY"):
        return [], ["SEARCH_API_KEY não configurada; busca real não executada."]

    for term in terms:
        try:
            for result in search_web(term):
                normalized = normalize_url(result["link"])
                if normalized not in seen_urls:
                    seen_urls.add(normalized)
                    results.append(result)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{term}: {exc}")
    return results, errors


def result_to_candidate(result: dict[str, str]) -> tuple[str, dict[str, Any]]:
    title = result["title"].strip()
    link = result["link"].strip()
    snippet = result.get("snippet", "").strip()
    query = result.get("query", "")
    company = infer_company(title, link)

    if is_international(query, title, snippet):
        candidate = {
            "id": slugify(f"{company}-{title}"),
            "program": title,
            "institution": company,
            "country": "A confirmar",
            "cluster": "Radar internacional",
            "type": "Oportunidade internacional",
            "status": "Radar",
            "funding": "A confirmar",
            "fundingScore": 0,
            "grossCostBRL": 0,
            "grossCostNote": "A confirmar no edital oficial.",
            "language": "A confirmar",
            "deadline": "A confirmar",
            "selectivity": "A confirmar",
            "requirements": "A confirmar",
            "docs": "A confirmar",
            "academicFit": 0,
            "careerFit": 0,
            "financialViability": 0,
            "academicViability": 0,
            "profileFit": 0,
            "prestige": 0,
            "chanceReal": 0,
            "urgency": 0,
            "glamourRisk": 0,
            "financialRisk": 0,
            "delayRisk": 0,
            "energyFit": 0,
            "dataAIFit": 0,
            "industryFit": 0,
            "verdict": "Radar",
            "why": snippet or "Oportunidade encontrada pelo radar diário.",
            "couldGoWrong": "Validar elegibilidade, funding e prazo antes de priorizar.",
            "condition": "Adicionar ao Atlas apenas se houver funding ou viabilidade real.",
            "studentSignals": "A confirmar.",
            "url": link,
            "baseScore": 0,
        }
        return "internacional", candidate

    candidate = {
        "company": company,
        "opportunity": title,
        "type": "Oportunidade encontrada pelo radar",
        "status": "Radar",
        "cluster": infer_cluster(title, snippet),
        "location": infer_location(title, snippet),
        "model": "A confirmar",
        "careerFit": 0,
        "technicalFit": 0,
        "locationFit": 0,
        "brandStrength": 0,
        "functionQuality": 0,
        "cvFit": 0,
        "riskMisalignment": 0,
        "areaDependency": "A confirmar",
        "availability": 0,
        "compensation": 0,
        "archetype": "Radar",
        "why": snippet or "Oportunidade encontrada pelo radar diário.",
        "watchout": "Validar escopo, local, modelo e aderência real antes de aplicar.",
        "verify": "Checar descrição oficial, área, prazo, requisitos e link de inscrição.",
        "companyUrl": link,
        "applyUrl": link,
        "cv": infer_cv(title, snippet),
    }
    return "vagas", candidate


def infer_cluster(title: str, snippet: str) -> str:
    text = normalize_text(f"{title} {snippet}")
    if "data center" in text or "datacenter" in text:
        return "Data Centers & Infraestrutura Crítica"
    if "consultoria" in text or "consulting" in text or "strategy" in text:
        return "Consultoria Tech, Operações & Transformação"
    if "energia" in text or "energy" in text or "elétrica" in text or "eletrica" in text:
        return "Energia & Utilities"
    if "dados" in text or "analytics" in text or "data" in text:
        return "P&D, Dados & Tecnologia Aplicada"
    return "Radar"


def infer_location(title: str, snippet: str) -> str:
    text = normalize_text(f"{title} {snippet}")
    if "campinas" in text:
        return "Campinas / SP"
    if "são paulo" in text or "sao paulo" in text:
        return "São Paulo / SP"
    if "brasil" in text or "brazil" in text:
        return "Brasil"
    return "A confirmar"


def infer_cv(title: str, snippet: str) -> str:
    text = normalize_text(f"{title} {snippet}")
    if "consult" in text or "strategy" in text:
        return "Business/Consultoria"
    if "dados" in text or "data" in text or "analytics" in text:
        return "Dados/Tech"
    return "Energia/Projetos"


def classify_with_rules(candidate: dict[str, Any], destino: str, duplicate_reason: str) -> tuple[str, int, str]:
    if duplicate_reason != "novo":
        return "repetida", 0, f"Possível repetição detectada por {duplicate_reason}."

    text = normalize_text(" ".join(str(value) for value in candidate.values()))
    good_score = sum(1 for term in GOOD_TERMS if term in text)
    bad_score = sum(1 for term in BAD_TERMS if term in text)

    if bad_score >= 2 or ("sem bolsa" in text and destino == "internacional"):
        return "descartada", 15, "Sinais de baixa aderência, custo alto ou escopo incompatível."
    if good_score >= 4:
        return "nova", min(95, 55 + good_score * 8 - bad_score * 10), "Boa aderência pelas regras de energia, dados, infraestrutura, consultoria ou funding."
    if good_score >= 2:
        return "monitorar", 50, "Há sinais úteis, mas faltam evidências para entrada automática no Atlas."
    return "descartada", 20, "Poucos sinais de aderência ao perfil do Lucas."


def classify_with_openai(candidate: dict[str, Any], destino: str, duplicate_reason: str) -> tuple[str, int, str] | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    import requests

    prompt = {
        "perfil": "Lucas: Engenharia Elétrica na Unicamp, Campinas/SP, experiência em Siemens Energy e Agibank; busca melhoria contínua, processos, dados, energia, infraestrutura, data centers, consultoria e oportunidades internacionais com funding. Evitar oportunidades caras sem bolsa, comerciais genéricas, operacionais demais e programas inviáveis.",
        "destino": destino,
        "duplicidade": duplicate_reason,
        "oportunidade": candidate,
        "classes_validas": ["nova", "atualizacao", "repetida", "descartada", "monitorar"],
    }
    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": os.getenv("OPENAI_MODEL") or "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "Classifique oportunidades para um radar de carreira. Responda apenas JSON válido com classificacao, prioridade 0-100 e motivo curto."},
                    {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
                ],
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
            },
            timeout=45,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        classificacao = parsed.get("classificacao")
        if classificacao not in {"nova", "atualizacao", "repetida", "descartada", "monitorar"}:
            return None
        return classificacao, int(parsed.get("prioridade", 0)), str(parsed.get("motivo", "")).strip()
    except Exception:  # noqa: BLE001
        return None


def apply_scores(candidate: dict[str, Any], prioridade: int, motivo: str, destino: str) -> None:
    if destino == "internacional":
        candidate["baseScore"] = prioridade
        candidate["profileFit"] = max(candidate.get("profileFit", 0), min(95, prioridade))
        candidate["careerFit"] = max(candidate.get("careerFit", 0), min(95, prioridade))
        candidate["why"] = motivo or candidate.get("why", "")
        return

    candidate["careerFit"] = min(98, max(candidate.get("careerFit", 0), prioridade))
    candidate["technicalFit"] = min(95, max(candidate.get("technicalFit", 0), prioridade - 5))
    candidate["cvFit"] = min(95, max(candidate.get("cvFit", 0), prioridade - 8))
    candidate["locationFit"] = max(candidate.get("locationFit", 0), 90 if "Campinas" in candidate.get("location", "") else 60)
    candidate["brandStrength"] = max(candidate.get("brandStrength", 0), 70)
    candidate["functionQuality"] = max(candidate.get("functionQuality", 0), max(0, prioridade - 10))
    candidate["riskMisalignment"] = max(candidate.get("riskMisalignment", 0), 100 - prioridade)
    candidate["availability"] = max(candidate.get("availability", 0), 70)
    candidate["compensation"] = max(candidate.get("compensation", 0), 60)
    candidate["why"] = motivo or candidate.get("why", "")


def process_results(results: list[dict[str, str]], vagas: list[dict[str, Any]], internacional: list[dict[str, Any]]) -> list[RadarResult]:
    dedup_vagas = Deduplicador(vagas)
    dedup_internacional = Deduplicador(internacional)
    processed: list[RadarResult] = []

    for raw in results:
        destino, candidate = result_to_candidate(raw)
        dedup = dedup_internacional if destino == "internacional" else dedup_vagas
        duplicate_reason, _, duplicate_score = dedup.find_match(candidate)
        classification = hard_veto_classification(candidate, duplicate_reason)
        if classification is None:
            classification = classify_with_openai(candidate, destino, duplicate_reason)
        if classification is None:
            classification = classify_with_rules(candidate, destino, duplicate_reason)
        classificacao, prioridade, motivo = classification
        classificacao, prioridade, motivo = calibrate_source_classification(candidate, destino, classificacao, prioridade, motivo)
        apply_scores(candidate, prioridade, motivo, destino)
        processed.append(RadarResult(candidate, destino, classificacao, prioridade, motivo, duplicate_reason, duplicate_score))
    return processed


def build_history_entry(item: RadarResult, run_date: str) -> dict[str, Any]:
    candidate = item.candidate
    return {
        "date": run_date,
        "classification": item.classificacao,
        "priority": item.prioridade,
        "destination": item.destino,
        "duplicateReason": item.duplicate_reason,
        "duplicateScore": round(item.duplicate_score, 3),
        "title": candidate.get("opportunity") or candidate.get("program") or candidate.get("title"),
        "company": candidate.get("company") or candidate.get("institution"),
        "url": candidate.get("applyUrl") or candidate.get("url") or candidate.get("companyUrl"),
        "reason": item.motivo,
    }


def should_add_to_atlas(item: RadarResult) -> bool:
    url, title = source_details(item.candidate)
    official_source = (
        is_official_international_source(url, title)
        if item.destino == "internacional"
        else is_official_or_apply_source(url, title)
    )
    return (
        item.classificacao in {"nova", "atualizacao"}
        and item.prioridade >= 65
        and official_source
        and has_minimum_lucas_fit(item.candidate)
    )


def email_item_lines(item: RadarResult) -> list[str]:
    candidate = item.candidate
    title = candidate.get("opportunity") or candidate.get("program") or candidate.get("title")
    url = candidate.get("applyUrl") or candidate.get("url") or candidate.get("companyUrl")
    return [
        f"* {title}",
        f"  * Destino: {item.destino}",
        f"  * Prioridade: {item.prioridade}",
        f"  * Motivo: {item.motivo}",
        f"  * Link: {url}",
        "",
    ]


def monitor_email_quality(item: RadarResult) -> tuple[int, int, int, int]:
    url, title = source_details(item.candidate)
    blocked_source = is_hard_veto_domain(url) or is_social_or_news_source(url) or is_generic_job_board_result(url, title)
    official_source = (
        is_official_international_source(url, title)
        if item.destino == "internacional"
        else is_official_or_apply_source(url, title)
    )
    specific_source = int(any(term in source_text(f"{title} {url}") for term in SPECIFIC_OPPORTUNITY_TERMS))
    return (int(not blocked_source), int(official_source), specific_source, item.prioridade)


def useful_monitor_items(processed: list[RadarResult], limit: int = 8) -> list[RadarResult]:
    monitor_items = [item for item in processed if item.classificacao == "monitorar"]
    preferred = [item for item in monitor_items if monitor_email_quality(item)[0]]
    source = preferred or monitor_items
    return sorted(source, key=monitor_email_quality, reverse=True)[:limit]


def generate_email_summary(
    processed: list[RadarResult],
    report_path: Path,
    run_date: str,
    search_executed: bool,
) -> str:
    atlas_items = [item for item in processed if should_add_to_atlas(item)]
    new_items = [item for item in atlas_items if item.classificacao == "nova"]
    watch_items = useful_monitor_items(processed)
    repeated_count = sum(1 for item in processed if item.classificacao == "repetida")
    discarded_count = sum(1 for item in processed if item.classificacao == "descartada")
    try:
        report_relative = report_path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        report_relative = report_path.as_posix()

    lines = [
        f"# Radar de Oportunidades - {run_date}",
        "",
        "Resumo:",
        "",
        f"* Busca real: {'sim' if search_executed else 'não'}",
        f"* Novas adicionadas ao Atlas: {len(new_items)}",
        f"* Para olhar hoje: {len(watch_items)}",
        f"* Repetidas ignoradas: {repeated_count}",
        f"* Descartadas: {discarded_count}",
        "",
        "## Novas adicionadas ao Atlas",
        "",
    ]

    if new_items:
        for item in sorted(new_items, key=lambda entry: entry.prioridade, reverse=True)[:5]:
            lines.extend(email_item_lines(item))
    else:
        lines.extend(["Nenhuma oportunidade nova foi adicionada automaticamente hoje.", ""])

    lines.extend(["## Para olhar hoje", ""])
    if watch_items:
        for item in watch_items:
            lines.extend(email_item_lines(item))
    else:
        lines.extend(["Nenhuma fonte de monitoramento relevante para priorizar hoje.", ""])

    lines.extend(
        [
            "## Relatório completo",
            "",
            f"O relatório completo foi salvo no repositório em {report_relative}.",
            "",
        ]
    )
    return "\n".join(lines)


def generate_report(processed: list[RadarResult], errors: list[str], dry_run: bool, search_executed: bool, run_date: str) -> tuple[Path, str]:
    REPORTS_DIR.mkdir(exist_ok=True)
    report_path = REPORTS_DIR / f"radar_{run_date}.md"

    counts: dict[str, int] = {}
    for item in processed:
        counts[item.classificacao] = counts.get(item.classificacao, 0) + 1

    atlas_items = [item for item in processed if should_add_to_atlas(item)]
    atlas_new_count = sum(1 for item in atlas_items if item.classificacao == "nova")
    atlas_update_count = sum(1 for item in atlas_items if item.classificacao == "atualizacao")

    lines = [
        f"# Radar de Oportunidades - {run_date}",
        "",
        f"- Modo dry-run: {'sim' if dry_run else 'não'}",
        f"- Busca real executada: {'sim' if search_executed else 'não'}",
        f"- Itens vistos: {len(processed)}",
        f"- Novas: {atlas_new_count}",
        f"- Atualizações: {atlas_update_count}",
        f"- Repetidas: {counts.get('repetida', 0)}",
        f"- Monitorar: {counts.get('monitorar', 0)}",
        f"- Descartadas: {counts.get('descartada', 0)}",
        "",
    ]

    if errors:
        lines.extend(["## Avisos", ""])
        lines.extend(f"- {error}" for error in errors)
        lines.append("")

    def add_items(section_items: list[RadarResult]) -> None:
        for item in sorted(section_items, key=lambda entry: entry.prioridade, reverse=True):
            candidate = item.candidate
            title = candidate.get("opportunity") or candidate.get("program")
            company = candidate.get("company") or candidate.get("institution")
            url = candidate.get("applyUrl") or candidate.get("url") or candidate.get("companyUrl")
            lines.extend(
                [
                    f"### {company} - {title}",
                    "",
                    f"- Destino: {item.destino}",
                    f"- Prioridade: {item.prioridade}",
                    f"- Motivo: {item.motivo}",
                    f"- Duplicidade: {item.duplicate_reason} ({item.duplicate_score:.2f})",
                    f"- Link: {url}",
                    "",
                ]
            )

    monitor_items = [
        item
        for item in processed
        if item.classificacao == "monitorar"
        or (item.classificacao in {"nova", "atualizacao"} and not should_add_to_atlas(item))
    ]

    if atlas_items:
        lines.extend(["## Novas adicionadas ao Atlas", ""])
        add_items(atlas_items)

    if monitor_items:
        lines.extend(["## Fontes úteis para monitorar", ""])
        add_items(monitor_items)

    for section in ["repetida", "descartada"]:
        section_items = [item for item in processed if item.classificacao == section]
        if not section_items:
            continue
        lines.extend([f"## {section.capitalize()}", ""])
        add_items(section_items)

    if not processed:
        lines.extend(["## Resultado", "", "Nenhuma oportunidade nova foi coletada nesta execução.", ""])

    content = "\n".join(lines)
    report_path.write_text(content, encoding="utf-8")
    return report_path, content


def main() -> int:
    parser = argparse.ArgumentParser(description="Radar diário do Atlas de Oportunidades.")
    parser.add_argument("--dry-run", action="store_true", help="Executa sem alterar JSONs de dados.")
    args = parser.parse_args()

    dry_run = args.dry_run or os.getenv("DRY_RUN", "0") == "1"
    run_date = today_string()

    vagas = load_json(VAGAS_PATH, [])
    internacional = load_json(INTERNACIONAL_PATH, [])
    historico = load_json(HISTORICO_PATH, [])
    descartes = load_json(DESCARTES_PATH, [])
    load_json(CONFIG_PATH, {})

    raw_results, errors = search_all(TERMOS_PRIORITARIOS)
    processed = process_results(raw_results, vagas, internacional)

    additions_vagas = [item.candidate for item in processed if item.destino == "vagas" and should_add_to_atlas(item)]
    additions_internacional = [item.candidate for item in processed if item.destino == "internacional" and should_add_to_atlas(item)]
    new_descartes = [build_history_entry(item, run_date) for item in processed if item.classificacao == "descartada"]
    new_history = [build_history_entry(item, run_date) for item in processed]

    if not dry_run:
        if additions_vagas:
            vagas.extend(additions_vagas)
            write_json(VAGAS_PATH, vagas)
        if additions_internacional:
            internacional.extend(additions_internacional)
            write_json(INTERNACIONAL_PATH, internacional)
        if new_history:
            historico.extend(new_history)
            write_json(HISTORICO_PATH, historico)
        if new_descartes:
            descartes.extend(new_descartes)
            write_json(DESCARTES_PATH, descartes)

    report_path, _ = generate_report(
        processed=processed,
        errors=errors,
        dry_run=dry_run,
        search_executed=bool(os.getenv("SEARCH_API_KEY")),
        run_date=run_date,
    )
    email_summary = generate_email_summary(
        processed=processed,
        report_path=report_path,
        run_date=run_date,
        search_executed=bool(os.getenv("SEARCH_API_KEY")),
    )

    email_sent = False
    if smtp_configured():
        email_sent = send_report(
            subject=f"Radar Atlas de Oportunidades - {run_date}",
            body=email_summary,
        )

    print(f"Relatório: {report_path}")
    print(f"Busca real: {'sim' if os.getenv('SEARCH_API_KEY') else 'não'}")
    print(f"Dry-run: {'sim' if dry_run else 'não'}")
    print(f"Itens vistos: {len(processed)}")
    print(f"Entradas para vagas: {len(additions_vagas)}")
    print(f"Entradas para internacional: {len(additions_internacional)}")
    print(f"E-mail enviado: {'sim' if email_sent else 'não'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

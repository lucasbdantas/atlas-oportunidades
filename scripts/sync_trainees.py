from __future__ import annotations

import argparse
import json
import re
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
REPORTS_DIR = ROOT / "reports"
VAGAS_PATH = DATA_DIR / "vagas.json"
HISTORICO_PATH = DATA_DIR / "historico_radar.json"
TRAINEES_PATH = DATA_DIR / "trainees.json"

BASE_TARGETS: list[dict[str, Any]] = [
    {"id":"hitachi-energy","name":"Hitachi Energy","tier":"1","score":94,"energyFit":100,"brandFit":92,"locationFit":92,"internationalFit":88,"timingFit":90,"risk":12,"formationType":"Especialista","window":"Jul-ago/2027","priority":"Aplicar com forca","read":"Encaixe muito limpo: grid, potencia, engenharia, Guarulhos/SP e possibilidade internacional.","action":"Aplicar com forca; construir historia Serena ligada a projetos, rede, conexao e transicao energetica.","aliases":["hitachi energy","hitachi"],"tags":["energia","grid","internacional","SP"]},
    {"id":"neoenergia","name":"Neoenergia","tier":"1","score":93,"energyFit":96,"brandFit":92,"locationFit":88,"internationalFit":92,"timingFit":86,"risk":10,"formationType":"Hibrido","window":"2o semestre/2027","priority":"Aplicar com forca","read":"Energia grande, Iberdrola, internacional, geracao, transmissao, distribuicao e trading.","action":"Aplicar forte; vender perfil engenharia + energia + dados/processos.","aliases":["neoenergia","iberdrola"],"tags":["energia","Iberdrola","gestao","internacional"]},
    {"id":"edp","name":"EDP","tier":"1","score":92,"energyFit":96,"brandFit":94,"locationFit":82,"internationalFit":96,"timingFit":74,"risk":8,"formationType":"Executivo","window":"Mar/2028","priority":"Manter quente","read":"Energia global, transicao e rotacao internacional. Timing pesa contra 2027, nao contra a tese.","action":"Manter quente desde ja; preparar candidatura longa para 2028.","aliases":["edp","edp brasil","edp global"],"tags":["energia","global","transicao","executivo"]},
    {"id":"isa-energia","name":"ISA Energia Brasil","tier":"1","score":90,"energyFit":98,"brandFit":86,"locationFit":90,"internationalFit":72,"timingFit":78,"risk":11,"formationType":"Especialista","window":"Fim/2027 ou inicio/2028","priority":"Aplicar com forca","read":"Transmissao pura e seria. Puxa para infraestrutura, engenharia e sistema eletrico real.","action":"Aplicar forte se abrir; narrativa Serena + transmissao/conexao fica muito coerente.","aliases":["isa energia","isa cteep","cteep"],"tags":["transmissao","SP","infraestrutura"]},
    {"id":"eletrobras-axia","name":"Eletrobras/Axia","tier":"1","score":89,"energyFit":98,"brandFit":96,"locationFit":78,"internationalFit":62,"timingFit":86,"risk":24,"formationType":"Hibrido","window":"Set-out/2027","priority":"Aplicar com forca","read":"Marca local enorme e infraestrutura pesada. Risco maior que utilities mais estaveis, mas segue Tier 1.","action":"Aplicar forte; enfatizar interesse por sistema eletrico, ativos e transformacao pos-privatizacao.","aliases":["eletrobras","axia energia","axia"],"tags":["energia","marca","infraestrutura"]},
    {"id":"taesa","name":"TAESA","tier":"1","score":87,"energyFit":97,"brandFit":84,"locationFit":82,"internationalFit":58,"timingFit":80,"risk":12,"formationType":"Especialista","window":"Fev/2028","priority":"Aplicar com forca","read":"Excelente para transmissao, regulacao e operacao. Mais especialista do que executivo.","action":"Aplicar forte em 2028; preparar historia tecnica e regulatoria.","aliases":["taesa"],"tags":["transmissao","RJ","especialista"]},
    {"id":"vale-engenharia","name":"Vale Engenharia","tier":"2","score":80,"energyFit":58,"brandFit":94,"locationFit":82,"internationalFit":72,"timingFit":84,"risk":18,"formationType":"Especialista","window":"Mai-jun/2027","priority":"Aplicar se elegivel","read":"Melhor excecao antes da formatura. Nao e energia, mas e infraestrutura pesada e marca forte.","action":"Monitorar com atencao em 2027; aplicar se aceitar formandos de julho.","aliases":["vale","vale engenharia"],"tags":["mineracao","engenharia","early"]},
    {"id":"siemens-energy","name":"Siemens Energy","tier":"2","score":79,"energyFit":94,"brandFit":91,"locationFit":78,"internationalFit":86,"timingFit":48,"risk":18,"formationType":"Especialista","window":"Entry-level continuo","priority":"Monitorar entry-level","read":"Graduate formal pode pedir master/PhD, mas a empresa faz sentido para vagas junior, aplicacao, subestacoes e digital grid.","action":"Nao tratar como trainee principal; monitorar entry-level e estagio final.","aliases":["siemens energy"],"tags":["energia","digital grid","entry-level"]},
    {"id":"engie-cpfl-equatorial","name":"Engie / CPFL / Equatorial","tier":"2","score":76,"energyFit":90,"brandFit":82,"locationFit":76,"internationalFit":60,"timingFit":60,"risk":20,"formationType":"Monitoramento","window":"Monitorar vagas","priority":"Monitorar vagas junior","read":"Talvez a melhor oportunidade aqui nao seja trainee, e sim vaga junior boa em energia.","action":"Criar alerta de vagas junior; filtrar por engenharia, dados, projetos, regulacao ou mercado.","aliases":["engie","cpfl","equatorial"],"tags":["monitoramento","energia","junior"]},
    {"id":"eneva","name":"Eneva","tier":"2","score":72,"energyFit":88,"brandFit":76,"locationFit":46,"internationalFit":45,"timingFit":68,"risk":28,"formationType":"Especialista","window":"2028 se repetir","priority":"Seletivo","read":"Energia real, mas geografia e alocacao podem pesar contra sua preferencia.","action":"Aplicar so se trilha/local fizerem sentido.","aliases":["eneva"],"tags":["energia","gas","localizacao"]},
    {"id":"itau-bba","name":"Itau / Itau BBA","tier":"3","score":75,"energyFit":38,"brandFit":96,"locationFit":92,"internationalFit":55,"timingFit":88,"risk":22,"formationType":"Executivo","window":"2o semestre/2027","priority":"Ponte de negocio","read":"Fallback inteligente de negocio, principalmente para infra, project finance, corporate, M&A ou energia.","action":"Aplicar se conseguir posicionar para areas com ponte clara para energia/infraestrutura.","aliases":["itau","itau bba","itaú","itaú bba"],"tags":["negocio","infra","finance"]},
    {"id":"btg-santander-safra","name":"BTG / Santander / Safra","tier":"3","score":68,"energyFit":32,"brandFit":86,"locationFit":86,"internationalFit":48,"timingFit":70,"risk":30,"formationType":"Executivo","window":"2o semestre/2027","priority":"Seletivo","read":"Opcao de negocio, mas o risco de virar financas genericas e maior.","action":"So priorizar trilhas de corporate, project finance, energia, infraestrutura ou M&A.","aliases":["btg","santander","safra"],"tags":["negocio","finance"]},
    {"id":"nestle-suzano-ambev","name":"Nestle / Suzano / Ambev","tier":"4","score":60,"energyFit":18,"brandFit":88,"locationFit":78,"internationalFit":58,"timingFit":74,"risk":34,"formationType":"Executivo","window":"2o semestre/2027","priority":"Plano C","read":"Boa marca e formacao generalista, mas baixa coerencia com Serena e energia.","action":"Usar como plano C se quiser abrir para general management.","aliases":["nestle","nestlé","suzano","ambev"],"tags":["general management","marca"]},
    {"id":"raizen","name":"Raizen","tier":"0","score":38,"energyFit":72,"brandFit":70,"locationFit":74,"internationalFit":40,"timingFit":60,"risk":76,"formationType":"Monitoramento","window":"Despriorizar","priority":"Despriorizar","read":"Nao e 'acabou', mas reestruturacao extrajudicial pesada basta para despriorizar inicio de carreira.","action":"So considerar se a vaga for excepcional e o risco fizer sentido.","aliases":["raizen","raízen"],"tags":["risco","despriorizar"]},
]

TRAINEE_TERMS = ("trainee", "graduate", "graduate program", "jovem talento", "jovens talentos", "entry level", "entry-level", "junior", "júnior")

def strip_accents(value: str) -> str:
    return "".join(ch for ch in unicodedata.normalize("NFD", value) if unicodedata.category(ch) != "Mn")

def normalize(value: Any) -> str:
    text = strip_accents(str(value or "").casefold())
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return json.loads(path.read_text(encoding=encoding))
        except UnicodeDecodeError:
            continue
    return default

def write_json_if_changed(path: Path, payload: Any) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if path.exists():
        try:
            if path.read_text(encoding="utf-8") == content:
                return False
        except UnicodeDecodeError:
            pass
    path.write_text(content, encoding="utf-8")
    return True

def item_title(item: dict[str, Any]) -> str:
    return str(item.get("opportunity") or item.get("program") or item.get("title") or "")

def item_company(item: dict[str, Any]) -> str:
    return str(item.get("company") or item.get("institution") or "")

def item_url(item: dict[str, Any]) -> str:
    return str(item.get("applyUrl") or item.get("url") or item.get("companyUrl") or item.get("link") or "")

def source_name(url: str) -> str:
    try:
        host = urlparse(url).hostname or ""
    except ValueError:
        host = ""
    return host.removeprefix("www.") or "fonte"

def target_matches(target: dict[str, Any], item: dict[str, Any]) -> bool:
    text = normalize(" ".join(str(value) for value in item.values()))
    aliases = [normalize(alias) for alias in target.get("aliases", [])]
    has_alias = any(alias and alias in text for alias in aliases)
    has_signal = any(normalize(term) in text for term in TRAINEE_TERMS)
    if target["id"] in {"siemens-energy", "engie-cpfl-equatorial"}:
        has_signal = has_signal or "estagio" in text or "vaga" in text
    return has_alias and has_signal

def candidate_to_match(item: dict[str, Any], source_type: str) -> dict[str, Any]:
    title = item_title(item)
    url = item_url(item)
    return {
        "title": title,
        "company": item_company(item),
        "url": url,
        "source": source_type,
        "sourceDomain": source_name(url),
        "status": item.get("status") or item.get("classification") or "Radar",
        "priority": item.get("priority") or item.get("prioridade") or item.get("baseScore") or item.get("score") or 0,
        "date": item.get("date") or item.get("updatedAt") or "",
        "reason": item.get("reason") or item.get("why") or item.get("motivo") or "",
    }

def match_key(match: dict[str, Any]) -> str:
    url = str(match.get("url") or "").strip().casefold()
    if url:
        return url.rstrip("/")
    return normalize(f"{match.get('company', '')} {match.get('title', '')}")

def collect_matches(target: dict[str, Any], vagas: list[dict[str, Any]], historico: list[dict[str, Any]]) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source_type, items in (("vagas", vagas), ("historico", historico)):
        for item in items:
            if not isinstance(item, dict) or not target_matches(target, item):
                continue
            if item.get("classification") == "descartada":
                continue
            match = candidate_to_match(item, source_type)
            key = match_key(match)
            if not key or key in seen:
                continue
            seen.add(key)
            matches.append(match)
    matches.sort(key=lambda item: (str(item.get("date") or ""), int(float(item.get("priority") or 0))), reverse=True)
    return matches[:8]

def build_payload() -> dict[str, Any]:
    vagas = read_json(VAGAS_PATH, [])
    historico = read_json(HISTORICO_PATH, [])
    today = date.today().isoformat()
    targets = []
    for base in BASE_TARGETS:
        target = dict(base)
        matches = collect_matches(target, vagas if isinstance(vagas, list) else [], historico if isinstance(historico, list) else [])
        target["radarMatches"] = matches
        target["radarCount"] = len(matches)
        target["lastSeenAt"] = next((match.get("date") for match in matches if match.get("date")), "")
        target["radarStatus"] = "Sinais recentes" if matches else "Monitorar"
        targets.append(target)
    return {
        "schemaVersion": 1,
        "updatedAt": today,
        "sourceFiles": ["data/vagas.json", "data/historico_radar.json"],
        "monitoringQueries": [
            "trainee energia 2027 Brasil",
            "programa trainee Hitachi Energy Brasil",
            "programa trainee Neoenergia Iberdrola",
            "EDP global graduate Brasil",
            "trainee Eletrobras Axia Energia",
            "trainee ISA Energia Brasil",
            "trainee TAESA",
            "Siemens Energy entry level Brasil",
            "Itau BBA trainee infraestrutura energia",
        ],
        "targets": targets,
    }

def write_report(payload: dict[str, Any]) -> Path:
    REPORTS_DIR.mkdir(exist_ok=True)
    path = REPORTS_DIR / f"trainees_{payload['updatedAt']}.md"
    lines = [
        f"# Radar de Trainees - {payload['updatedAt']}",
        "",
        f"- Alvos monitorados: {len(payload['targets'])}",
        f"- Alvos com sinais recentes: {sum(1 for item in payload['targets'] if item['radarCount'])}",
        "",
        "## Tier 1",
        "",
    ]
    for target in payload["targets"]:
        if target["tier"] != "1":
            continue
        lines.extend([
            f"### {target['name']}",
            "",
            f"- Janela: {target['window']}",
            f"- Score: {target['score']}",
            f"- Radar: {target['radarStatus']} ({target['radarCount']} sinais)",
            f"- Acao: {target['action']}",
            "",
        ])
        for match in target["radarMatches"][:3]:
            lines.append(f"  - {match['title']} - {match['url']}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path

def main() -> int:
    parser = argparse.ArgumentParser(description="Sincroniza o painel de trainees com o radar do Atlas.")
    parser.add_argument("--no-report", action="store_true", help="Atualiza apenas data/trainees.json.")
    args = parser.parse_args()
    payload = build_payload()
    changed = write_json_if_changed(TRAINEES_PATH, payload)
    report_path = None if args.no_report else write_report(payload)
    print(f"Trainees: {len(payload['targets'])} alvos")
    print(f"Sinais recentes: {sum(1 for item in payload['targets'] if item['radarCount'])}")
    print(f"data/trainees.json atualizado: {'sim' if changed else 'nao'}")
    if report_path:
        print(f"Relatorio trainees: {report_path}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

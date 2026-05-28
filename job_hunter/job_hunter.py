#!/usr/bin/env python3
"""
Job Hunter - Automated Job Search & Daily Email Report
Busca vagas no LinkedIn, Indeed e Gupy e envia relatório diário por email (Gmail)
"""

import sys
import io

# Garante que o terminal Windows aceite emojis e caracteres UTF-8
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import json
import os
import re
import smtplib
import time
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests
from bs4 import BeautifulSoup

# ─── CONFIGURAÇÕES ────────────────────────────────────────────────────────────
CONFIG = {
    # Palavras-chave para busca (personalize aqui)
    "keywords": ["gerente comercial", "gerente geral", "diretor comercial", "Cientista de Dados", "Analista de Dados"],

    # Localização
    "location": "Brasil",

    # Nível de experiência (para filtros)
    "experience_level": "senior",  # junior | mid-senior | senior

    # Gmail - configure no arquivo .env ou diretamente aqui
    "gmail_sender": os.getenv("GMAIL_SENDER", "cmabe01@gmail.com"),
    "gmail_password": os.getenv("GMAIL_APP_PASSWORD", "irichfcfolohawfp"),
    "gmail_recipient": os.getenv("GMAIL_RECIPIENT", "cmabe01@gmail.com"),

    # Máximo de vagas por fonte
    "max_jobs_per_source": 20,

    # Arquivo de cache para evitar duplicatas
    "cache_file": "seen_jobs.json",

    # Dias para considerar uma vaga como nova
    "days_lookback": 1,
}
# ──────────────────────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


# ─── CACHE DE VAGAS JÁ VISTAS ─────────────────────────────────────────────────

def load_cache(path: str) -> set:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_cache(path: str, seen: set):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(list(seen), f, ensure_ascii=False, indent=2)


# ─── SCRAPERS ─────────────────────────────────────────────────────────────────

def search_indeed(keyword: str, location: str, max_results: int = 20) -> list[dict]:
    """Busca vagas no Indeed Brasil via RSS"""
    jobs = []
    query = keyword.replace(" ", "+")
    url = f"https://br.indeed.com/rss?q={query}&l=Brasil&sort=date&fromage=1"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "xml")

        items = soup.find_all("item")[:max_results]
        for item in items:
            title = item.find("title").get_text(strip=True) if item.find("title") else "N/A"
            company_loc = item.find("source").get_text(strip=True) if item.find("source") else "N/A"
            link = item.find("link").get_text(strip=True) if item.find("link") else "#"
            pub_date = item.find("pubDate").get_text(strip=True) if item.find("pubDate") else "Hoje"
            guid = item.find("guid").get_text(strip=True) if item.find("guid") else link

            jobs.append({
                "id": f"indeed_{abs(hash(guid))}",
                "title": title,
                "company": company_loc,
                "location": location,
                "url": link,
                "date": pub_date,
                "source": "Indeed",
                "keyword": keyword,
            })

        time.sleep(2)
    except Exception as e:
        print(f"  [Indeed] Erro ao buscar '{keyword}': {e}")

    return jobs


def search_gupy(keyword: str, max_results: int = 20) -> list[dict]:
    """Busca vagas via API pública da Gupy"""
    jobs = []
    query = keyword.replace(" ", "%20")
    url = f"https://portal.api.gupy.io/api/v1/jobs?name={query}&limit={max_results}&offset=0"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        for job in data.get("data", []):
            pub_date = job.get("publishedDate", "")[:10] if job.get("publishedDate") else ""
            jobs.append({
                "id": f"gupy_{job.get('id', '')}",
                "title": job.get("name", "N/A"),
                "company": job.get("careerPageName", "N/A"),
                "location": f"{job.get('city', '')} - {job.get('state', '')}".strip(" -"),
                "url": job.get("jobUrl", "#"),
                "date": pub_date,
                "source": "Gupy",
                "keyword": keyword,
            })

        time.sleep(1)
    except Exception as e:
        print(f"  [Gupy] Erro ao buscar '{keyword}': {e}")

    return jobs


def search_linkedin(keyword: str, location: str, max_results: int = 20) -> list[dict]:
    """Busca vagas no LinkedIn (scraping público, sem login)"""
    jobs = []
    query = keyword.replace(" ", "%20")
    loc = location.replace(" ", "%20")
    # LinkedIn permite busca pública sem login nesta URL
    url = (
        f"https://www.linkedin.com/jobs/search/?keywords={query}&location={loc}&geoId=106057199&f_TPR=r86400&sortBy=DD"
    )

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        cards = soup.select("div.base-card")[:max_results]
        for card in cards:
            title_el = card.select_one("h3.base-search-card__title")
            company_el = card.select_one("h4.base-search-card__subtitle")
            location_el = card.select_one("span.job-search-card__location")
            link_el = card.select_one("a.base-card__full-link")
            date_el = card.select_one("time")

            if not title_el or not link_el:
                continue

            href = link_el.get("href", "#")
            job_id = re.search(r"-(\d+)\??", href)
            job_id = job_id.group(1) if job_id else href[-10:]

            jobs.append({
                "id": f"linkedin_{job_id}",
                "title": title_el.get_text(strip=True),
                "company": company_el.get_text(strip=True) if company_el else "N/A",
                "location": location_el.get_text(strip=True) if location_el else location,
                "url": href.split("?")[0],
                "date": date_el.get("datetime", "") if date_el else "",
                "source": "LinkedIn",
                "keyword": keyword,
            })

        time.sleep(3)
    except Exception as e:
        print(f"  [LinkedIn] Erro ao buscar '{keyword}': {e}")

    return jobs


# ─── COLETA PRINCIPAL ──────────────────────────────────────────────────────────

def collect_all_jobs(config: dict) -> list[dict]:
    all_jobs = []
    keywords = config["keywords"]
    location = config["location"]
    max_per = config["max_jobs_per_source"]

    for kw in keywords:
        print(f"\n🔍 Buscando: '{kw}'")
        print("  → LinkedIn...")
        all_jobs.extend(search_linkedin(kw, location, max_per))

    # Remove duplicatas pelo ID
    seen_ids = set()
    unique = []
    for job in all_jobs:
        if job["id"] not in seen_ids:
            seen_ids.add(job["id"])
            unique.append(job)

    return unique


def filter_new_jobs(jobs: list[dict], cache: set, cache_path: str) -> list[dict]:
    new_jobs = [j for j in jobs if j["id"] not in cache]
    # Atualiza cache
    cache.update(j["id"] for j in jobs)
    save_cache(cache_path, cache)
    return new_jobs


# ─── RELATÓRIO HTML ────────────────────────────────────────────────────────────

SOURCE_COLORS = {
    "LinkedIn": "#0077B5",
    "Indeed":   "#2164F3",
    "Gupy":     "#00BFA5",
}

SOURCE_ICONS = {
    "LinkedIn": "💼",
    "Indeed":   "🔵",
    "Gupy":     "🟢",
}


def build_html_report(jobs: list[dict], config: dict) -> str:
    today = datetime.now().strftime("%d/%m/%Y")
    total = len(jobs)

    # Agrupa por fonte
    by_source: dict[str, list] = {}
    for job in jobs:
        by_source.setdefault(job["source"], []).append(job)

    # Cards de vagas
    cards_html = ""
    for job in jobs:
        color = SOURCE_COLORS.get(job["source"], "#555")
        icon = SOURCE_ICONS.get(job["source"], "📌")
        cards_html += f"""
        <div class="job-card">
          <div class="job-source" style="color:{color}">{icon} {job['source']}</div>
          <div class="job-title"><a href="{job['url']}" target="_blank">{job['title']}</a></div>
          <div class="job-meta">
            <span>🏢 {job['company']}</span>
            <span>📍 {job['location']}</span>
            {"<span>🗓 " + job['date'] + "</span>" if job['date'] else ""}
          </div>
          <div class="job-keyword">🔑 {job['keyword']}</div>
        </div>"""

    # Resumo por fonte
    summary_rows = ""
    for src, src_jobs in by_source.items():
        color = SOURCE_COLORS.get(src, "#555")
        summary_rows += f"""
        <tr>
          <td style="color:{color};font-weight:600">{SOURCE_ICONS.get(src,'')} {src}</td>
          <td style="text-align:center">{len(src_jobs)}</td>
        </tr>"""

    keywords_tags = " ".join(
        f'<span class="tag">{kw}</span>' for kw in config["keywords"]
    )

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Job Hunter – Relatório {today}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Segoe UI', system-ui, sans-serif;
    background: #f0f4f8;
    color: #1a202c;
    padding: 24px 16px;
  }}
  .container {{ max-width: 700px; margin: 0 auto; }}

  /* Header */
  .header {{
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 60%, #0f3460 100%);
    color: white;
    border-radius: 16px;
    padding: 32px;
    margin-bottom: 24px;
    text-align: center;
  }}
  .header h1 {{ font-size: 28px; letter-spacing: -0.5px; margin-bottom: 6px; }}
  .header .date {{ opacity: .7; font-size: 14px; margin-bottom: 20px; }}
  .badge {{
    display: inline-block;
    background: rgba(255,255,255,.15);
    border: 1px solid rgba(255,255,255,.25);
    border-radius: 999px;
    padding: 6px 18px;
    font-size: 15px;
    font-weight: 700;
  }}

  /* Summary */
  .summary-card {{
    background: white;
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,.08);
  }}
  .summary-card h2 {{ font-size: 14px; text-transform: uppercase; letter-spacing: .08em; color: #718096; margin-bottom: 14px; }}
  table {{ width: 100%; border-collapse: collapse; }}
  td {{ padding: 8px 0; border-bottom: 1px solid #edf2f7; font-size: 15px; }}
  tr:last-child td {{ border-bottom: none; }}

  /* Keywords */
  .keywords {{ margin-bottom: 20px; }}
  .tag {{
    display: inline-block;
    background: #e2e8f0;
    color: #4a5568;
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 12px;
    margin: 3px;
    font-weight: 500;
  }}

  /* Job Cards */
  .section-title {{
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: .08em;
    color: #718096;
    margin: 24px 0 12px;
  }}
  .job-card {{
    background: white;
    border-radius: 12px;
    padding: 18px 20px;
    margin-bottom: 12px;
    box-shadow: 0 1px 3px rgba(0,0,0,.07);
    border-left: 4px solid #e2e8f0;
    transition: border-color .2s;
  }}
  .job-card:hover {{ border-left-color: #0077B5; }}
  .job-source {{ font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; margin-bottom: 6px; }}
  .job-title {{ font-size: 16px; font-weight: 700; margin-bottom: 8px; }}
  .job-title a {{ color: #1a202c; text-decoration: none; }}
  .job-title a:hover {{ color: #0077B5; text-decoration: underline; }}
  .job-meta {{ display: flex; flex-wrap: wrap; gap: 12px; font-size: 13px; color: #718096; margin-bottom: 6px; }}
  .job-keyword {{ font-size: 11px; color: #a0aec0; }}

  /* Footer */
  .footer {{
    text-align: center;
    font-size: 12px;
    color: #a0aec0;
    margin-top: 32px;
    padding-top: 20px;
    border-top: 1px solid #e2e8f0;
  }}

  /* Empty state */
  .empty {{ text-align:center; padding: 40px; color: #718096; }}
</style>
</head>
<body>
<div class="container">

  <div class="header">
    <h1>🎯 Job Hunter</h1>
    <div class="date">Relatório de {today}</div>
    <div class="badge">{total} novas vagas encontradas</div>
  </div>

  <div class="summary-card">
    <h2>Resumo por plataforma</h2>
    <table>{summary_rows}</table>
  </div>

  <div class="keywords">
    <strong style="font-size:13px;color:#4a5568">Palavras-chave monitoradas:</strong><br><br>
    {keywords_tags}
  </div>

  <div class="section-title">Vagas de hoje</div>

  {"".join([cards_html]) if jobs else '<div class="empty">🔍 Nenhuma vaga nova encontrada hoje. Tente amanhã!</div>'}

  <div class="footer">
    Enviado automaticamente pelo <strong>Job Hunter</strong> · {today}<br>
    Para ajustar palavras-chave ou configurações, edite o arquivo <code>job_hunter.py</code>
  </div>

</div>
</body>
</html>"""

    return html


# ─── ENVIO DE EMAIL ────────────────────────────────────────────────────────────

def send_email(html_body: str, total_jobs: int, config: dict):
    today = datetime.now().strftime("%d/%m/%Y")
    subject = f"🎯 Job Hunter – {total_jobs} novas vagas · {today}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config["gmail_sender"]
    msg["To"] = config["gmail_recipient"]

    msg.attach(MIMEText(html_body, "html", "utf-8"))

    print(f"\n📧 Enviando email para {config['gmail_recipient']}...")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(config["gmail_sender"], config["gmail_password"])
        server.sendmail(config["gmail_sender"], config["gmail_recipient"], msg.as_string())
    print("  ✅ Email enviado com sucesso!")


# ─── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 55)
    print("  🎯 JOB HUNTER – Iniciando busca de vagas")
    print(f"  📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("=" * 55)

    # 1. Carrega cache
    cache = load_cache(CONFIG["cache_file"])
    print(f"\n📂 Cache carregado: {len(cache)} vagas já vistas")

    # 2. Coleta vagas
    print("\n🌐 Iniciando coleta nas plataformas...")
    all_jobs = collect_all_jobs(CONFIG)
    print(f"\n📊 Total coletado (com duplicatas): {len(all_jobs)}")

    # 3. Filtra novas
    new_jobs = filter_new_jobs(all_jobs, cache, CONFIG["cache_file"])
    print(f"✨ Vagas novas (não vistas antes): {len(new_jobs)}")

    # 4. Gera relatório
    html = build_html_report(new_jobs, CONFIG)

    # 5. Salva HTML local (opcional, para debug)
    report_path = f"report_{datetime.now().strftime('%Y%m%d')}.html"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"💾 Relatório salvo localmente: {report_path}")

    # 6. Envia email
    if new_jobs or True:  # sempre envia, mesmo sem vagas novas
        try:
            send_email(html, len(new_jobs), CONFIG)
        except Exception as e:
            print(f"  ❌ Erro ao enviar email: {e}")
            print("  ⚠️  Verifique suas credenciais no arquivo .env")

    print("\n✅ Job Hunter finalizado!\n")


if __name__ == "__main__":
    main()

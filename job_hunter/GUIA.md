# 🎯 Job Hunter — Guia de Instalação e Uso

Automatize sua busca de vagas no **LinkedIn**, **Indeed** e **Gupy** e receba um relatório diário por email.

---

## 📁 Estrutura dos arquivos

```
job_hunter/
├── job_hunter.py      ← Script principal
├── requirements.txt   ← Dependências Python
├── .env.example       ← Modelo de configuração
├── .env               ← Suas credenciais (criar você mesmo)
└── seen_jobs.json     ← Cache automático (criado na 1ª execução)
```

---

## 1. Pré-requisitos

- Python 3.10 ou superior instalado
- Conta Gmail com **verificação em 2 etapas** ativada

---

## 2. Instalação

```bash
# Clone ou baixe a pasta job_hunter
cd job_hunter

# Crie um ambiente virtual (recomendado)
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

# Instale as dependências
pip install -r requirements.txt
```

---

## 3. Configuração do Gmail (Senha de App)

> ⚠️ O Gmail **não aceita** sua senha normal por SMTP. É preciso criar uma **Senha de App**.

1. Acesse: https://myaccount.google.com/security
2. Ative **"Verificação em 2 etapas"** (se ainda não estiver ativa)
3. Acesse: https://myaccount.google.com/apppasswords
4. Em "Selecionar app", escolha **"Outro (nome personalizado)"**
5. Digite `Job Hunter` → clique em **Gerar**
6. Copie a senha de 16 caracteres gerada (ex: `abcd efgh ijkl mnop`)

---

## 4. Criar o arquivo .env

```bash
# Na pasta job_hunter, copie o modelo:
cp .env.example .env
```

Abra o arquivo `.env` e preencha:

```env
GMAIL_SENDER=seuemail@gmail.com
GMAIL_APP_PASSWORD=abcd efgh ijkl mnop
GMAIL_RECIPIENT=seuemail@gmail.com
```

---

## 5. Personalize as buscas

Abra `job_hunter.py` e edite a seção `CONFIG` no topo do arquivo:

```python
CONFIG = {
    # Suas palavras-chave de busca
    "keywords": [
        "desenvolvedor python",
        "engenheiro de dados",
        "data engineer",
    ],

    # Cidade, estado ou "Brasil" para nacional
    "location": "São Paulo",

    # Máximo de vagas por fonte por palavra-chave
    "max_jobs_per_source": 20,
    ...
}
```

---

## 6. Execução manual

```bash
# Ativar ambiente virtual (se usar)
source venv/bin/activate

# Executar
python job_hunter.py
```

Você verá no terminal algo como:

```
=======================================================
  🎯 JOB HUNTER – Iniciando busca de vagas
  📅 19/03/2026 08:00
=======================================================

📂 Cache carregado: 0 vagas já vistas

🌐 Iniciando coleta nas plataformas...

🔍 Buscando: 'desenvolvedor python'
  → Indeed...
  → Gupy...
  → LinkedIn...

📊 Total coletado: 47
✨ Vagas novas (não vistas antes): 47
💾 Relatório salvo localmente: report_20260319.html

📧 Enviando email para seuemail@gmail.com...
  ✅ Email enviado com sucesso!

✅ Job Hunter finalizado!
```

---

## 7. Automatizar com agendamento diário

### 🐧 Linux / macOS (cron)

```bash
# Abrir o crontab
crontab -e

# Adicionar linha para executar todo dia às 8h da manhã:
0 8 * * * cd /caminho/para/job_hunter && /caminho/venv/bin/python job_hunter.py >> log.txt 2>&1
```

Para descobrir o caminho do Python no virtualenv:
```bash
which python   # dentro do venv ativado
```

### 🪟 Windows (Agendador de Tarefas)

1. Abra o **Agendador de Tarefas** (Task Scheduler)
2. Clique em **"Criar Tarefa Básica..."**
3. Nome: `Job Hunter`
4. Gatilho: **Diariamente** → às 08:00
5. Ação: **Iniciar um programa**
   - Programa: `C:\caminho\job_hunter\venv\Scripts\python.exe`
   - Argumentos: `job_hunter.py`
   - Iniciar em: `C:\caminho\job_hunter\`
6. Clique em **Concluir**

---

## 8. Solução de problemas

| Problema | Solução |
|---|---|
| `SMTPAuthenticationError` | Verifique a Senha de App no `.env` |
| `ConnectionError` no LinkedIn | LinkedIn bloqueia IPs; tente VPN ou reduza frequência |
| Nenhuma vaga encontrada | Verifique sua conexão e palavras-chave |
| `ModuleNotFoundError` | Execute `pip install -r requirements.txt` |

---

## 9. Dicas de uso avançado

- **Use palavras em inglês** além do português para mais resultados: `"python developer"`, `"software engineer"`
- O arquivo `seen_jobs.json` armazena vagas já enviadas. Para **resetar o histórico**, delete-o.
- O relatório HTML também é salvo localmente como `report_AAAAMMDD.html` para consulta

---

## ⚠️ Aviso sobre scraping

Sites como LinkedIn podem limitar ou bloquear requisições automáticas. Este script usa delays entre as requisições para ser respeitoso com os servidores. Use com moderação (1x por dia é o ideal).

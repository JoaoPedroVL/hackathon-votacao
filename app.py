# -*- coding: utf-8 -*-
"""
Sistema de votação para Hackathon
- Lê as propostas inscritas direto do CSV exportado do Google Forms
- Juízes votam por critérios (notas de 0 a 10)
- Dashboard com total de inscritos, turnos, seguimentos e ranking
"""
import csv
import glob
import os
import sqlite3
import time
import urllib.request
from datetime import datetime

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for

app = Flask(__name__)
app.secret_key = "hackathon-juizes-2026"  # apenas para identificar o juiz na sessão

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "votos.db")

# Critérios de avaliação (notas de 0 a 10 em cada um)
CRITERIOS = ["Inovação", "Viabilidade", "Impacto", "Clareza da proposta"]

# Quantidade máxima de avaliadores (a média é feita entre eles)
MAX_AVALIADORES = 3

# Chave secreta que os juízes precisam digitar para votar.
# Em produção, defina a variável de ambiente CHAVE_SECRETA.
CHAVE_SECRETA = os.environ.get("CHAVE_SECRETA", "hackathon2026")


# ---------------------------------------------------------------- CSV / BD

# Link da planilha online do Google Forms (precisa estar compartilhada como
# "qualquer pessoa com o link pode ver")
SHEET_ID = "1gqjB-HW8y0Cv_gi3rHzsXA2BTxyRrIv4UqgWaJPYwxY"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"
CACHE_SEGUNDOS = 60  # baixa um CSV novo da planilha a cada 60 segundos

# Arquivo local onde o CSV baixado fica salvo (sobrescreve o anterior)
CSV_CACHE = os.path.join(BASE_DIR, "planilha_cache.csv")


def _baixar_csv_se_preciso():
    """Baixa o CSV mais novo da planilha se o cache local tiver mais de 60s.
    Se o download falhar (sem internet etc.), mantém o cache anterior."""
    try:
        idade = time.time() - os.path.getmtime(CSV_CACHE)
    except OSError:
        idade = CACHE_SEGUNDOS + 1
    if idade < CACHE_SEGUNDOS:
        return

    tmp = CSV_CACHE + ".tmp"
    try:
        with urllib.request.urlopen(SHEET_URL, timeout=15) as resp:
            texto = resp.read().decode("utf-8-sig")
        if "Título da proposta" not in texto:  # resposta inesperada, ignora
            return
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(texto)
        os.replace(tmp, CSV_CACHE)  # sobrescreve o arquivo antigo
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)


def carregar_propostas():
    """Lê as propostas do CSV cache (baixado a cada 60s da planilha online).
    Se não houver cache, usa um CSV da pasta como reserva."""
    _baixar_csv_se_preciso()

    caminho = CSV_CACHE
    if not os.path.exists(caminho):
        arquivos = [a for a in glob.glob(os.path.join(BASE_DIR, "*.csv"))
                    if os.path.abspath(a) != CSV_CACHE]
        caminho = max(arquivos, key=os.path.getmtime) if arquivos else None

    propostas = []
    if caminho:
        with open(caminho, newline="", encoding="utf-8-sig") as f:
            for linha in csv.DictReader(f):
                # ignora linhas vazias ou com só resquícios (células apagadas
                # na planilha às vezes deixam um campo solto preenchido)
                if not (linha.get("Título da proposta") or "").strip():
                    continue
                if not (linha.get("Nome do Proponente") or "").strip():
                    continue
                linha = {k: (v or "").strip() for k, v in linha.items()}
                propostas.append({"id": len(propostas), "dados": linha})
    return propostas


def fonte_dados():
    if os.path.exists(CSV_CACHE):
        return "Google Forms (atualizado a cada 60s)"
    return "CSV local"


def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute(
        """CREATE TABLE IF NOT EXISTS votos (
               juiz TEXT NOT NULL,
               proposta_id INTEGER NOT NULL,
               criterio TEXT NOT NULL,
               nota INTEGER NOT NULL,
               atualizado_em TEXT NOT NULL,
               PRIMARY KEY (juiz, proposta_id, criterio)
           )"""
    )
    return db


def todos_votos():
    db = get_db()
    rows = db.execute("SELECT * FROM votos").fetchall()
    db.close()
    return rows


# ---------------------------------------------------------------- Rotas

@app.route("/")
def dashboard():
    propostas = carregar_propostas()
    votos = todos_votos()

    por_turno, por_segmento, por_eixo = {}, {}, {}
    for p in propostas:
        d = p["dados"]
        turno = (d.get("Turno") or "Não informado").strip()
        seg = (d.get("Seguimento de ensino") or "Não informado").strip()
        eixo = (d.get("Eixo de Participação:") or "Não informado").strip()
        por_turno[turno] = por_turno.get(turno, 0) + 1
        por_segmento[seg] = por_segmento.get(seg, 0) + 1
        por_eixo[eixo] = por_eixo.get(eixo, 0) + 1

    # ranking por média de cada avaliador (média das médias dos avaliadores)
    por_avaliador = {}
    for v in votos:
        por_avaliador.setdefault(v["proposta_id"], {}).setdefault(v["juiz"], []).append(v["nota"])
    ranking = []
    for pid, juizes in por_avaliador.items():
        medias_dos_juizes = [sum(notas) / len(notas) for notas in juizes.values()]
        ranking.append({
            "id": pid,
            "media": round(sum(medias_dos_juizes) / len(medias_dos_juizes), 2),
            "n_avaliadores": len(juizes),
        })

    # média por critério de cada proposta
    por_criterio = {}
    for v in votos:
        por_criterio.setdefault(v["proposta_id"], {}).setdefault(v["criterio"], []).append(v["nota"])
    for r in ranking:
        r["criterios"] = {
            c: round(sum(ns) / len(ns), 2)
            for c, ns in por_criterio.get(r["id"], {}).items()
        }
    ranking.sort(key=lambda r: r["media"], reverse=True)
    for r in ranking:
        if r["id"] < len(propostas):
            r["titulo"] = propostas[r["id"]]["dados"].get(
                "Título da proposta", f"Proposta {r['id'] + 1}")
            r["equipe"] = propostas[r["id"]]["dados"].get("Nome da equipe:", "")

    return render_template(
        "dashboard.html",
        total=len(propostas),
        por_turno=por_turno,
        por_segmento=por_segmento,
        por_eixo=por_eixo,
        ranking=ranking,
        max_avaliadores=MAX_AVALIADORES,
        ultimo_csv=fonte_dados(),
    )


@app.route("/juiz", methods=["POST"])
def definir_juiz():
    nome = (request.form.get("juiz") or session.get("nome_pendente") or "").strip()
    chave = (request.form.get("chave") or "").strip()

    if not nome:
        return redirect(url_for("votar"))

    # 1ª etapa: só o nome -> pede a chave secreta
    if not chave:
        session["nome_pendente"] = nome
        return redirect(url_for("votar"))

    # 2ª etapa: valida a chave
    if chave != CHAVE_SECRETA:
        flash("Chave secreta incorreta. Peça a chave ao organizador do evento.")
        return redirect(url_for("votar"))

    juizes = sorted({v["juiz"] for v in todos_votos()})
    entrou_antes = any(j.lower() == nome.lower() for j in juizes)
    if len(juizes) >= MAX_AVALIADORES and not entrou_antes and nome != session.get("juiz"):
        flash(f"Limite de {MAX_AVALIADORES} avaliadores atingido. "
              f"Avaliadores já cadastrados: {', '.join(juizes)}.")
    else:
        session["juiz"] = nome
        session.pop("nome_pendente", None)
    return redirect(request.form.get("next") or url_for("votar"))


@app.route("/sair")
def sair():
    session.pop("juiz", None)
    session.pop("nome_pendente", None)
    return redirect(url_for("votar"))


@app.route("/votar")
def votar():
    propostas = carregar_propostas()
    juizes = sorted({v["juiz"] for v in todos_votos()})

    db = get_db()
    votados = set()
    if session.get("juiz"):
        votados = {
            r["proposta_id"]
            for r in db.execute(
                "SELECT DISTINCT proposta_id FROM votos WHERE juiz = ?",
                (session["juiz"],),
            ).fetchall()
        }
    # quantos avaliadores já votaram em cada proposta + média geral das notas
    qtd_avaliados = {}
    medias = {}
    for r in db.execute(
        """SELECT proposta_id, COUNT(DISTINCT juiz) AS n, AVG(nota) AS media
           FROM votos GROUP BY proposta_id"""
    ).fetchall():
        qtd_avaliados[r["proposta_id"]] = r["n"]
        medias[r["proposta_id"]] = round(r["media"], 2)
    db.close()

    return render_template(
        "votar.html", propostas=propostas, juiz=session.get("juiz"),
        nome_pendente=session.get("nome_pendente"),
        juizes=juizes, votados=votados, qtd_avaliados=qtd_avaliados,
        medias=medias, max_avaliadores=MAX_AVALIADORES,
    )


@app.route("/proposta/<int:pid>", methods=["GET", "POST"])
def proposta(pid):
    if not session.get("juiz"):
        return redirect(url_for("votar"))

    propostas = carregar_propostas()
    if pid < 0 or pid >= len(propostas):
        abort(404)
    p = propostas[pid]
    juiz = session["juiz"]
    db = get_db()

    if request.method == "POST":
        agora = datetime.now().isoformat(timespec="seconds")
        for criterio in CRITERIOS:
            nota = request.form.get(criterio)
            if nota is None or nota == "":
                continue
            nota = max(0, min(10, int(nota)))
            db.execute(
                """INSERT INTO votos (juiz, proposta_id, criterio, nota, atualizado_em)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(juiz, proposta_id, criterio)
                   DO UPDATE SET nota = excluded.nota, atualizado_em = excluded.atualizado_em""",
                (juiz, pid, criterio, nota, agora),
            )
        db.commit()
        db.close()
        return redirect(url_for("votar"))

    notas_atuais = {
        r["criterio"]: r["nota"]
        for r in db.execute(
            "SELECT criterio, nota FROM votos WHERE juiz = ? AND proposta_id = ?",
            (juiz, pid),
        ).fetchall()
    }
    db.close()
    return render_template(
        "proposta.html", p=p, criterios=CRITERIOS, notas=notas_atuais, juiz=juiz
    )


if __name__ == "__main__":
    get_db().close()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)

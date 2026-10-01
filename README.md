# Sistema de Votação — Hackathon

Aplicação web (Flask) para avaliação de propostas inscritas via Google Forms.

## Funcionalidades

- 📊 **Dashboard**: total de inscritos, gráficos por turno/seguimento/eixo, ranking com média entre os avaliadores
- 🗳️ **Votação**: juízes se identificam pelo nome + chave secreta, e dão notas de 0 a 10 por critério
- 🔄 Sincroniza a planilha do Google Forms automaticamente a cada 60 segundos
- 📱 Layout mobile-first

## Rodando localmente

```bash
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/python app.py
```

Acesse http://localhost:5000 — na mesma rede Wi-Fi, os juízes usam `http://SEU_IP:5000`.

## Configuração (topo do `app.py`)

| Constante | O que faz |
|---|---|
| `CHAVE_SECRETA` | chave que os juízes digitam para votar (também aceita a variável de ambiente `CHAVE_SECRETA`) |
| `MAX_AVALIADORES` | quantidade máxima de juízes (padrão: 3) |
| `CRITERIOS` | critérios de avaliação com notas de 0 a 10 |
| `SHEET_ID` | ID da planilha do Google Forms (precisa estar compartilhada como "qualquer pessoa com o link pode ver") |

## Deploy no Render (gratuito)

1. Suba este repositório no GitHub
2. Em https://render.com crie um **Web Service** apontando para o repositório
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `gunicorn app:app`
5. (Opcional) crie a variável de ambiente `CHAVE_SECRETA` com a chave dos juízes

> Nota: no plano gratuito o banco de votos (SQLite) é reiniciado quando o serviço
> reinicia. Para produção séria, considere um disco persistente ou banco gerenciado.

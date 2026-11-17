"""Regra de quando o painel aceita upload de arquivos (sem imports do Django: usada pelo settings).

Uploads em disco local só fazem sentido quando o próprio Django serve a pasta MEDIA, o que só
acontece com DEBUG=True (ver config/urls.py). Por isso o padrão é:
  - DEBUG=True e fora da Vercel  -> ligado  (desenvolvimento / apresentação no MySQL local)
  - DEBUG=False (produção)       -> desligado, mesmo que a variável VERCEL não exista
  - variável VERCEL presente     -> desligado (disco efêmero e corpo da requisição limitado a ~4,5 MB)
A variável de ambiente UPLOADS_HABILITADOS ("True"/"False") sempre vence.
"""


def uploads_habilitados(debug, env):
    padrao = "True" if (debug and not env.get("VERCEL")) else "False"
    return env.get("UPLOADS_HABILITADOS", padrao) == "True"

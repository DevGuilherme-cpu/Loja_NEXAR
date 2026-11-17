---
name: nexar-revisao
description: Revisão completa da NEXAR sem alterar nada — testes, checagens do Django, navegador (desktop e celular), console, acessibilidade, segurança e os requisitos do professor. Usar quando pedirem "revisa o projeto", "está tudo certo?", "o que falta?" ou antes de abrir uma PR.
---

# Revisão da NEXAR (só leitura)

Não editar arquivos nem rodar git que altere o repositório (ver AGENTS.md). Gerar um relatório.

## 1. Automático

```
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py check --deploy
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test loja
git status
git diff --stat
```

`makemigrations --check` falhando = model mudou sem migration (bloqueia o deploy).

## 2. No navegador (`python manage.py runserver`)

Páginas: `/`, `/produtos/`, `/produtos/?categoria=3&busca=wide`, `/produtos/?busca=xyz`,
`/produto/3/`, `/produto/8/`, `/entrar/`, `/cadastro/`, `/painel/` (precisa admin).

Em cada uma: console sem erro, sem rolagem horizontal em 375 px, 3D aparece,
foco visível ao navegar com Tab, nenhuma imagem quebrada.

## 3. Requisitos do professor (PDF da atividade)

- [ ] Banco com nome da empresa, 3–5 tabelas, PK, FK, tipos certos
- [ ] ≥ 5 registros por tabela principal
- [ ] Tela inicial + menu + cadastro + listagem + pesquisa + edição + exclusão
- [ ] Cadastro de usuário (usuário e senha)
- [ ] CREATE DATABASE / CREATE TABLE / INSERT / SELECT / UPDATE / DELETE / JOIN demonstráveis
- [ ] Dados realmente no MySQL (nada de dado falso nas telas)
- [ ] Script SQL + diagrama ER + código organizado em pastas

## 4. Segurança

Painel com `@staff_member_required`; `DEBUG=False` na Vercel; `.env` fora do Git;
formulários POST com `{% csrf_token %}`; Data API do Supabase desligada; nada de segredo em arquivo versionado.

## 5. Relatório

Lista ordenada por gravidade: **BLOQUEIA-DEMO**, **IMPORTANTE**, **MELHORIA** — cada item com
`arquivo:linha`, o que a pessoa veria de errado e a correção sugerida. No fim, a mensagem de commit
sugerida (a pessoa é quem faz o commit).

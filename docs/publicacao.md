# Publicação da NEXAR (Vercel + Supabase)

Roteiro para levar a `backend-base` (login/cadastro/sair, painel só para staff, preço gravado no
pedido, e-mail único) para produção em https://loja-nexar.vercel.app sem quebrar o site.

Levantamento feito em 16/11/2026, 21:33 (horário de Brasília) = 17/11/2026 00:33 UTC.
**Revisado em 17/11/2026** pelo coordenador após integrar a `main` até o PR #4 (`e43f96f`) e as
correções da revisão das fases 1 e 2. Estado local de referência: ver o relatório revisado.
Legenda: **[verificado]** = conferido por comando/URL; **[inferência]** = conclusão sem acesso direto.

> Nada deste documento foi executado contra a Vercel ou o Supabase. Cada passo marcado
> com [AUTORIZAÇÃO] precisa de autorização explícita de quem é responsável (Guilherme = dono do repositório
> e do projeto na Vercel; Eliton = quem tem a `DATABASE_URL`).

---

## 1. Como o projeto roda na Vercel

| Item | Situação |
|---|---|
| Configuração | **[verificado]** Não existe `vercel.json` (nem nunca existiu no histórico: `git log --all -- vercel.json` vazio), nem `pyproject.toml`, `.python-version`, `Procfile` ou script de build. |
| Detecção | **[inferência]** A Vercel usa o preset Django: acha o `manage.py`, lê `WSGI_APPLICATION = 'config.wsgi.application'` e publica uma função Python, instalando o `requirements.txt`. |
| Python | **[inferência]** Versão padrão da Vercel (3.12). Django 6.0 exige Python ≥ 3.12. Localmente: Python 3.12.8. Recomenda-se fixar a versão (ex.: `.python-version` com `3.12`) numa mudança futura. |
| Projeto na Vercel | **[verificado]** Fica na conta do Guilherme (`guilandin01-3531s-projects/loja-nexar`, pelos links dos status do GitHub). A Vercel CLI local (64.0.2) está logada como `eliton2025`, time `sousa15`, que **não** enxerga o projeto (`vercel ls loja-nexar` → `project_not_found`). |
| Deploy automático | **[verificado]** Integração Git ativa: todo commit enviado ao GitHub ganha status "Vercel – Deployment has completed" (main: `a879ee3`, `09571d3`; branches: `c2aa400` da `backend-base`, `c10859e` da `organizacao`). Push na `main` = deploy de produção; push em outra branch = deploy de *preview*. |
| Estáticos | **[verificado]** WhiteNoise com `WHITENOISE_USE_FINDERS = True` serve direto de `static/` e dos apps (não depende de `collectstatic`): `/static/css/style.css` e `/static/admin/css/base.css` → 200. |
| Mídia (uploads) | Não persiste na Vercel: o sistema de arquivos da função é somente leitura/efêmero e não há storage externo configurado. `static(MEDIA_URL…)` em `config/urls.py` só funciona com `DEBUG=True`. Em produção `MEDIA_URL=/static/img/` faz os caminhos gravados no banco (`produtos/x.jpg`) apontarem para `static/img/produtos/` **[verificado: imagens saem como `/static/img/produtos/...`]**. Upload novo pelo painel/admin não aparece (e o salvar do painel ainda é simulado). |
| Migrations | **[inferência forte]** Não rodam no build (nenhum comando de build no repositório; a Vercel não executa `migrate`). Precisam ser rodadas manualmente contra o Supabase por quem tem a `DATABASE_URL`. |
| `DEBUG` | **[verificado]** Desligado em produção: URL inexistente devolve a página 404 genérica do Django, sem traceback. |

### Variáveis de ambiente (só nomes)

| Nome | Uso | Observação |
|---|---|---|
| `SECRET_KEY` | assinatura de sessão/CSRF | Obrigatória. Sem ela o Django não sobe. **[inferência]** está definida (site e CSRF funcionam). |
| `DEBUG` | ausente ou `False` em produção | Ausente = `False`. Nunca `True` na Vercel. |
| `DATABASE_URL` | PostgreSQL do Supabase (pooler) | Ganha de `DB_NAME`. |
| `MEDIA_URL` | `/static/img/` em produção | |
| `DB_SSLMODE` | **novo** (já na `backend-base`), padrão `require` | Não precisa ser criado na Vercel: o padrão é o que o Supabase exige. Só `disable` para PostgreSQL local de teste. |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | MySQL local (avaliação) | Não devem existir na Vercel. |

Ver os nomes realmente cadastrados exige acesso ao projeto (`vercel env ls` na conta do Guilherme)
— não foi possível daqui.

### Riscos de configuração

- `SECRET_KEY` vazia/ausente em algum ambiente (ex.: *Preview*) derruba aquele deploy.
- `DATABASE_URL` também no ambiente *Preview* ⇒ deploys de preview (gerados por **qualquer push de branch**) usam o **banco de produção**. Não é possível conferir daqui. Se for o caso, o preview da `backend-base` vai mostrar erro em `/painel/pedidos/` até a 0004 rodar (código novo lê `preco_unitario`) **e o `/cadastro/` do preview criaria contas reais no Supabase**. Conferir as variáveis do ambiente Preview antes do push (passo A).
- `ALLOWED_HOSTS` só aceita `.vercel.app` (e local). Domínio próprio exigiria alterar settings.
- Sem `SECURE_PROXY_SSL_HEADER`: o Django não sabe que a requisição veio por HTTPS. O CSRF funciona porque `CSRF_TRUSTED_ORIGINS = ["https://*.vercel.app"]` cobre a origem. Não remover essa linha.
- HSTS vem da própria Vercel, não do Django (`SECURE_HSTS_*` não configurado). Não há CSP.

---

## 2. Verificação pública atual (GET, sem login)

Em 17/11/2026 00:33 UTC (`curl -s -o /dev/null -w "%{http_code} -> %{redirect_url}"`).
Nesse momento a produção já era o commit `09571d3` (PR #3, deploy concluído às 00:32 UTC).

| URL | Status | Observação |
|---|---|---|
| `/` | 200 | |
| `/produtos/` | 200 | |
| `/produto/1/` … `/produto/9/` | 200 | `data-cor` preenchido nas 7 peças com as cores da 0003; tênis e óculos com `data-modelo="/static/modelos/*.glb"` |
| `/entrar/` | 200 | form POST com CSRF, mas na `main` o login da loja ainda é só tela (`entrar` só renderiza) |
| `/cadastro/` | 200 | só tela na `main` |
| `/sair/` | 404 | rota não existe na `main` |
| `/painel/`, `/painel/pedidos/` | 302 | → `/admin/login/?next=...` (`@staff_member_required` da `main`) |
| `/admin/login/` | 200 | |
| `/nao-existe-xyz/` | 404 | página genérica ⇒ `DEBUG=False` |

Cabeçalhos (`curl -sI /` e `/admin/login/`): `Strict-Transport-Security: max-age=63072000; includeSubDomains; preload`,
`X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`,
`Cross-Origin-Opener-Policy: same-origin`, cookie `csrftoken` com `Secure; SameSite=Lax`. Sem `Content-Security-Policy`.

**Migrations em produção:** **[inferência forte]** `0001`–`0003` aplicadas: a página de produto
consulta a coluna `cor` sem erro (0002) e os valores exatos da 0003 estão nos produtos e nos
`.glb` locais. Confirmar com a consulta 4 da seção 5.

---

## 3. Estado publicado × local

| Item | Produção (`main` no GitHub = `e43f96f`) | `backend-base` local (não publicada; commit no relatório revisado) |
|---|---|---|
| Login da loja `/entrar/` | só tela | `LoginView` real, mensagem de boas-vindas |
| Cadastro `/cadastro/` | só tela | cria cliente comum (`is_staff=False`), e-mail obrigatório e único (form) e já entra |
| Sair `/sair/` | 404 | POST desloga; GET → 405 |
| Painel `/painel/*` | `@staff_member_required` → `/admin/login/` | `somente_staff`: visitante → `/entrar/?next=…`; cliente logado → home com "Acesso restrito à equipe da loja." |
| Total do pedido | `produto.preco × quantidade` (preço de hoje) | `preco_unitario × quantidade` (preço da compra) |
| Banco | migrations até `0003` (inferência) | `0004` e `0005` |
| CHECKs no banco | nenhuma | preço ≥ 0, quantidade ≥ 1, preço unitário ≥ 0 |
| E-mail único no banco | não | índice `auth_user_email_ci_uniq` (0005), ignora caixa e espaços nas pontas |
| SSL do PostgreSQL | `require` fixo | `DB_SSLMODE` (padrão `require`) |

**Integração com a `main`:** os PRs #2, #3 e #4 do Guilherme já foram integrados na `backend-base`
(conflitos de templates/CSS/views resolvidos preservando o redesign). Antes do push, conferir de novo
`git fetch` + `git log backend-base..origin/main` e integrar se a `main` tiver andado.

---

## 4. O que será publicado

Commits da `backend-base` ainda fora da `main` (sem contar merges):

- **Autenticação e painel** — `6e9777a`, `bc7a61b`: `loja/views.py` (`Entrar`, `Sair`, `cadastro`, `destino_seguro`, `somente_staff`), `loja/forms.py`, `loja/urls.py` (`/sair/`), `config/settings.py` (`LOGIN_*`), templates `base.html` (Sair via POST, rodapé por estado), `login.html`, `cadastro.html`, regra `.topo-sair` no `style.css`, testes.
- **Banco / preço do pedido** — `2712c49`, `2ca38b0`, `82be85a`: `loja/models.py`, `0004_pedido_preco_unitario` (com verificação somente leitura como primeira operação), `popular_loja`, `DB_SSLMODE`, `.env.example`, `docs/banco.sql`, `docs/diagrama_er.md`, `docs/validacao_banco.md`, `docs/validacao_mysql.ps1`.
- **E-mail único e admin** — `af9c65f` e correção da revisão: `0005_email_unico` (índice `LOWER(TRIM(email))`), `forms.py`, `admin.py` (`NexarUserAdmin`, `PedidoAdmin`), tratamento de corrida no cadastro, `loja/test_email.py`.
- **Documentação** — `f143c33` e revisão: este arquivo.

### Migrations e o que mudam no Supabase

| Migration | Alteração no banco | Desfeita por rollback de código? |
|---|---|---|
| `loja.0004_pedido_preco_unitario` | `pedidos`: nova coluna `preco_unitario numeric(10,2)`; preenche cada pedido existente com o preço **atual** do produto; vira `NOT NULL` (sem default no banco); CHECKs `produto_preco_nao_negativo` (produtos), `pedido_quantidade_minima_1` e `pedido_preco_unitario_nao_negativo` (pedidos). A primeira operação é uma verificação somente leitura que aborta, sem alterar nada, se houver preço < 0 ou quantidade < 1. | **Não.** Promover deploy antigo na Vercel não mexe no banco. |
| `loja.0005_email_unico` | `auth_user`: índice único funcional `auth_user_email_ci_uniq` em `NULLIF(LOWER(TRIM(email)), '')`. Aborta, sem alterar contas, se houver e-mails repetidos ignorando caixa e espaços. E-mails vazios continuam permitidos. | **Não.** |

Ambas são aditivas (não apagam colunas nem tabelas).

---

## 5. Pré-checagens no Supabase (somente leitura — SQL editor)

Rodar **antes** do `migrate`. Todas são `SELECT`; nenhuma altera dados.

```sql
-- 1) Pedidos que violariam a CHECK quantidade >= 1 (esperado: 0 linhas)
SELECT id, quantidade FROM pedidos WHERE quantidade < 1;

-- 2) Produtos que violariam a CHECK preco >= 0 (esperado: 0 linhas)
SELECT id, nome, preco FROM produtos WHERE preco < 0;

-- 3) E-mails repetidos ignorando maiúsculas/minúsculas, sem contar vazios (esperado: 0 linhas)
SELECT LOWER(TRIM(email)) AS email_ci, COUNT(*) AS contas, ARRAY_AGG(id ORDER BY id) AS ids
FROM auth_user
WHERE TRIM(email) <> ''
GROUP BY LOWER(TRIM(email))
HAVING COUNT(*) > 1;

-- 4) Migrations do app loja já aplicadas (esperado: 0001, 0002, 0003 e nada além)
SELECT * FROM django_migrations WHERE app = 'loja' ORDER BY id;

-- 5) Conferências extras
SELECT column_name FROM information_schema.columns
WHERE table_name = 'pedidos' AND column_name = 'preco_unitario';   -- esperado: 0 linhas
SELECT indexname FROM pg_indexes WHERE indexname = 'auth_user_email_ci_uniq'; -- esperado: 0 linhas
SELECT COUNT(*) AS pedidos FROM pedidos;
SELECT COUNT(*) AS pedidos_sem_produto FROM pedidos p
LEFT JOIN produtos pr ON pr.id = p.produto_id WHERE pr.id IS NULL; -- esperado: 0
```

Se 1, 2 ou 3 retornarem linhas: corrigir manualmente (decisão humana) antes de seguir.

Também no Dashboard do Supabase (exigência da skill `nexar-revisao`): conferir que a **Data API** está
desligada, ou que as tabelas `auth_user`, `pedidos`, `produtos` e `categorias` têm RLS ativa sem políticas
públicas. Caso contrário, a chave pública do projeto permitiria ler `auth_user` (hash de senha e e-mails)
por fora do Django. Não verificado daqui (sem acesso ao Supabase).
Se 4 mostrar algo diferente de 0001–0003: parar e investigar.

---

## 6. Ordem segura (análise)

**Código novo com banco antigo (deploy antes do migrate) — quebra.** O model novo tem
`preco_unitario`, então todo `SELECT` de `Pedido` pede essa coluna: `/painel/pedidos/` e
`/admin/loja/pedido/` dão erro 500 até a 0004 rodar. O resto da loja funciona.

**Código antigo com banco novo (migrate antes do merge) — funciona quase tudo.**
- O model antigo não conhece `preco_unitario` e lista as colunas explicitamente: leituras
  (`/painel/pedidos/`, home, produtos) continuam funcionando. O total mostrado continua sendo
  `produto.preco × quantidade` até o deploy novo.
- **Única quebra conhecida:** criar Pedido pelo `/admin/` antigo (ou `popular_loja` antigo) faz
  `INSERT` sem `preco_unitario` → violação de `NOT NULL` (erro 500). Só staff faz isso; a loja
  não cria pedidos (não há checkout).
- CHECKs: editar produto com preço negativo no admin antigo dá erro 500 em vez de mensagem — aceitável.
- Índice de e-mail: criar usuário com e-mail repetido pelo admin antigo dá erro 500 — raro.
  O cadastro da `main` é só tela.

**Ordem recomendada:** backup → migrate (com o código da branch do PR) → merge (deploy
automático) → verificação. Janela de risco: entre o migrate e o fim do deploy, não criar pedidos
pelo `/admin/`. Contrapartida: se o PR não for aprovado depois do migrate, o banco fica à frente
do código (inofensivo para leitura; ver seção 8 para reverter).

---

## 7. Sequência recomendada

Pré-requisito local (sem efeito remoto) — **cumprido** na `backend-base` revisada: 0004 final, 0005 e
`DB_SSLMODE` commitados; `main` integrada até `e43f96f`; suíte verde em SQLite e em PostgreSQL 17 descartável;
`makemigrations --check` sem mudanças. Pendente: validação em MySQL (credencial local).

Ordem de execução: **1 → 2 → 3 → 4 → 5 → 6 → 7** (as letras só identificam cada ação).

**1. (A) [AUTORIZAÇÃO] Push da branch** — `git push origin backend-base`.
Efeito colateral: a Vercel cria um deploy de *preview* da branch (ver risco do `DATABASE_URL` em Preview).

**2. (B) [AUTORIZAÇÃO] Abrir PR** `backend-base` → `main` no GitHub (revisão do Guilherme). Não mergear ainda.

**3. (D) [AUTORIZAÇÃO] Backup do Supabase** (feito antes do migrate, por quem administra o projeto):
Dashboard → Database → Backups (conferir se há backup diário recente; no plano gratuito não há
restauração pontual garantida) **e** um dump próprio, por exemplo
`pg_dump "<URL de conexão direta ou session pooler>" -Fc -f nexar_antes_0004.dump`
(rodar só com a URL na variável de ambiente da sessão, nunca em arquivo versionado).

**4. (E) [AUTORIZAÇÃO] `migrate` contra o Supabase** — por quem tem a `DATABASE_URL` (Eliton), na própria máquina,
no checkout do commit do PR:

```powershell
# PowerShell, numa sessão nova; a URL só existe nesta janela (não gravar no .env)
$env:DATABASE_URL = "<URL do Supabase>"   # preferir Session pooler (porta 5432) ou conexão direta para DDL
python manage.py showmigrations loja      # deve listar 0001-0003 [X] e 0004/0005 [ ]
python manage.py migrate --plan           # conferir: só loja.0004 e loja.0005
python manage.py migrate
python manage.py showmigrations loja      # 0001-0005 [X]
Remove-Item Env:DATABASE_URL
```

`DB_SSLMODE` não precisa ser definido (padrão `require`). **Antes, confirme que `DB_SSLMODE=disable` não está
no `.env` local nem na sessão** (`Get-ChildItem Env:DB_SSLMODE` deve dar erro), senão a conexão com o Supabase
iria sem SSL ou falharia. `DATABASE_URL` tem prioridade sobre o
`DB_NAME` do `.env` local (o `load_dotenv` não sobrescreve variável já definida, e o settings
testa `DATABASE_URL` primeiro). **Não** rodar `popular_loja` no Supabase.
Se a 0004/0005 abortar pela verificação, nada é alterado (PostgreSQL desfaz a transação): corrigir os dados e repetir.

**5. (C) [AUTORIZAÇÃO] Merge do PR na `main`** (Guilherme).

**6. (F) Deploy** — automático: o push/merge na `main` dispara o deploy de produção
(**[verificado]** pelo histórico de status do GitHub). Acompanhar no painel da Vercel do
Guilherme até "Ready". Não usar `vercel deploy --prod` manual.

**7. (G) Verificação pós-deploy** (ver checklist abaixo).

### Checklist pós-deploy

Visitante (aba anônima):
- [ ] `/`, `/produtos/`, `/produto/1/` → 200, fotos e 3D carregando.
- [ ] `/entrar/` e `/cadastro/` → 200.
- [ ] `GET /sair/` → **405**.
- [ ] `/painel/` → 302 para **`/entrar/?next=/painel/`** (antes ia para `/admin/login/`).
- [ ] `/admin/login/` → 200; URL inexistente → 404 genérico (DEBUG desligado).

Cliente (conta criada no próprio `/cadastro/` com e-mail de teste):
- [ ] Cadastro conclui, mostra "Conta criada!" e o topo mostra "Olá, <usuário>" + botão Sair.
- [ ] Repetir o cadastro com o mesmo e-mail em MAIÚSCULAS → erro "Já existe uma conta com este e-mail.".
- [ ] `/painel/` → volta para a home com "Acesso restrito à equipe da loja." (sem loop de redirecionamento).
- [ ] Botão Sair → home com "Você saiu da sua conta.".
- [ ] Login com usuário/senha errados em `/entrar/` → mensagem de erro, sem 500.

Staff:
- [ ] Login em `/entrar/` → link "Painel" no topo.
- [ ] `/painel/`, `/painel/categorias/`, `/painel/pedidos/` → 200; totais dos pedidos em R$ (não vazios).
- [ ] `/admin/loja/pedido/add/` criando pedido sem preço → salva com o preço atual do produto.
- [ ] Depois do teste, desativar/remover a conta de cliente de teste se não for útil.

---

## 8. Recuperação

| Situação | Ação | Consequência |
|---|---|---|
| Deploy novo com erro | [AUTORIZAÇÃO] Vercel → Deployments → deploy anterior de produção → **Promote to Production** (instant rollback), ou reverter o merge na `main` (novo commit). | Só o código volta. O banco continua com 0004/0005, o que o código antigo tolera (ver seção 6: só "adicionar pedido" no admin quebra). Normalmente **não** é preciso mexer no banco. |
| Precisa desfazer as migrations | [AUTORIZAÇÃO] Com o código da branch e a `DATABASE_URL`: `python manage.py migrate loja 0003`. | Remove o índice de e-mail e as CHECKs e **apaga a coluna `preco_unitario` com os valores gravados** (o preço da compra dos pedidos feitos depois do deploy se perde; o total volta a usar o preço atual do produto). O passo de preenchimento é `noop` na volta. Fazer o rollback de código **antes** (o código novo quebra sem a coluna). |
| Dados corrompidos | [AUTORIZAÇÃO] Restaurar o dump do passo D (`pg_restore`) ou backup do Supabase. | Perde tudo o que foi gravado depois do backup (contas, pedidos). Último recurso. |

---

## 9. Limitações deste levantamento

- Sem acesso ao projeto da Vercel (pertence à conta do Guilherme; a CLI local está em outra conta). Não foi possível ver variáveis por ambiente (Production/Preview), versão de Python usada no build, logs, nem se *Deployment Protection* protege os previews.
- Sem acesso ao Supabase: o estado das migrations e a ausência de dados inválidos/e-mails duplicados são inferências; confirmar com as consultas da seção 5.
- Não foi testado login/POST em produção (só GET público).
- O `migrate` foi testado em **PostgreSQL 17.11 local descartável** (do zero, upgrade 0003→0005 com dados,
  bloqueios da 0004/0005, reverse da 0005 e suíte completa) — ver `docs/validacao_banco.md`. Não foi testado
  contra o pooler do Supabase; por isso a recomendação de Session pooler/conexão direta no passo E.
- Não validado em MySQL (falta credencial local); roteiro em `docs/validacao_mysql.ps1`.

# Publicação da NEXAR (Vercel + Supabase)

Roteiro para levar os PRs #5 (fases 1–2) e #6 (fase 3, CRUD do painel) para produção em
https://loja-nexar.vercel.app sem quebrar o site.

**Atualizado em 17/11/2026, ≈ 09:45 UTC (06:45 Brasília).**
Legenda: **[verificado]** = conferido por comando/URL/documentação (comando ou link ao lado);
**[inferência]** = conclusão sem acesso direto.

> Nada deste documento foi executado contra a Vercel ou o Supabase. Cada passo marcado com
> **[AUTORIZAÇÃO]** precisa de autorização explícita de quem é responsável (Guilherme = dono do
> repositório e do projeto na Vercel; Eliton = quem tem a `DATABASE_URL`).
> **Regra:** nenhuma alteração no banco remoto antes de o código dos PRs estar **revisado e aprovado**.

Uploads de arquivos no deploy: ver `docs/uploads_deploy.md` (opção B: desligados na Vercel).

---

## 1. Estado dos PRs

`gh pr view 5|6 -R DevGuilherme-cpu/Loja_NEXAR --json state,baseRefName,headRefOid,reviewDecision,reviews,mergeable`
e `gh pr checks` em 17/11/2026 09:45 UTC:

| PR | Base ← head | Head | Estado | Revisão | Checks |
|---|---|---|---|---|---|
| #5 Backend fases 1 e 2 | `main` ← `backend-base` | `4ef3c46` | aberto, `MERGEABLE` | **nenhuma** (`reviews: []`) | 2/2 ok (Vercel) |
| #6 Fase 3: CRUD do painel | `backend-base` ← `fase3-crud` | `2812ad9` | aberto, `MERGEABLE` | **nenhuma** | 2/2 ok (Vercel) |

**[verificado]** `main` no GitHub = `e43f96f` (`gh api repos/DevGuilherme-cpu/Loja_NEXAR/branches/main`).
Nenhum dos dois foi revisado ou mergeado.

**Dependência:** o #6 tem base `backend-base`, não `main`.
- Mergear o #5 com **merge commit** (não *squash*/*rebase*): com squash, os commits do #5 reaparecem no #6 e geram conflito.
- Depois do merge do #5, **conferir a base do #6**. O GitHub só troca a base para `main` automaticamente se a branch
  `backend-base` for apagada no merge; se não for, mudar manualmente (Edit → base `main`). Mergear o #6 com base
  `backend-base` **não** publica nada.
- O #6 **tem migration**: `0006_categoria_nome_unico_ci` (sendo adicionada nesta rodada; ver seção 4). O commit final do #6 ainda não existe.

---

## 2. Como o projeto roda na Vercel

| Item | Situação |
|---|---|
| Runtime | **[verificado]** Django vira **uma Vercel Function** Python (WSGI via `WSGI_APPLICATION`), Fluid compute por padrão. [Doc Django](https://vercel.com/docs/frameworks/full-stack/django) |
| Python | **[verificado]** Sem `.python-version`/`pyproject.toml` no repositório ⇒ padrão da Vercel, **3.12** (opções 3.12/3.13/3.14). Django 6.0 exige ≥ 3.12. [Doc Python](https://vercel.com/docs/functions/runtimes/python). Fixar a versão é melhoria opcional, não bloqueia (o padrão atual já atende). |
| Limites | **[verificado]** Corpo de requisição/resposta até **4,5 MB** (413 acima); 300 s de duração padrão (Hobby, Fluid); disco somente leitura, `/tmp` efêmero até 500 MB. [Limits](https://vercel.com/docs/functions/limitations), [Runtimes](https://vercel.com/docs/functions/runtimes#file-system-support) |
| Projeto | **[verificado]** Conta do Guilherme (`guilandin01-3531s-projects/loja-nexar`, pelos status do GitHub). A CLI local está em outra conta e não enxerga o projeto. |
| Deploy automático | **[verificado]** Integração Git: push/merge na `main` = produção; push em outra branch = *preview* (checks "Vercel" nos PRs). |
| Estáticos | **[verificado]** WhiteNoise com `WHITENOISE_USE_FINDERS = True`; a Vercel coleta direto dos apps ([doc](https://vercel.com/docs/frameworks/full-stack/django#whitenoise)). |
| Mídia | Ver `docs/uploads_deploy.md`. `MEDIA_URL=/static/img/` em produção aponta os caminhos gravados para `static/img/`. |
| Migrations | **[inferência forte]** Não rodam no build (sem comando de build no repositório). Rodam manualmente, por quem tem a `DATABASE_URL`. |
| `DEBUG` | **[verificado]** Desligado em produção (404 genérico). |

### Variáveis de ambiente (só nomes)

| Nome | Uso | Observação |
|---|---|---|
| `SECRET_KEY` | sessão/CSRF | Obrigatória. |
| `DEBUG` | ausente ou `False` | Nunca `True` na Vercel. |
| `DATABASE_URL` | PostgreSQL do Supabase (pooler) | Ganha de `DB_NAME`. |
| `MEDIA_URL` | `/static/img/` em produção | |
| `DB_SSLMODE` | padrão `require` (já no #5) | Não precisa ser criada. |
| `VERCEL` | definida pela própria Vercel (`VERCEL=1`, build e runtime) | Usada pela opção B para desligar uploads. Depende de "Enable access to System Environment Variables" estar marcada. [Doc](https://vercel.com/docs/environment-variables/system-environment-variables) |
| `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` | MySQL local | Não devem existir na Vercel. |

### Preview × banco de produção — **verificação pendente**

- **[verificado]** Os previews estão atrás da **proteção SSO da Vercel**: em 17/11/2026 09:45 UTC,
  `curl -sI https://loja-nexar-git-backend-base-guilandin01-3531s-projects.vercel.app/` e o mesmo para
  `…-git-fase3-crud-…` → `302 Found`, `Location: https://vercel.com/sso-api?url=…`. Visitante anônimo não acessa.
- **[inferência]** Proteção de acesso **não** impede o preview de usar a `DATABASE_URL` de produção: ela controla
  quem abre a URL, não quais variáveis o deploy recebe ([Deployment Protection](https://vercel.com/docs/deployment-protection),
  [variáveis por ambiente](https://vercel.com/docs/environment-variables)). Se a `DATABASE_URL` estiver também no ambiente
  *Preview*, os previews já publicados do #5/#6 rodam código novo contra o Supabase de produção (ex.: `/painel/pedidos/`
  quebra até a 0004; quem tem acesso à equipe na Vercel poderia criar contas/produtos reais).
- **Pendente:** Guilherme conferir em Settings → Environment Variables se `DATABASE_URL` está marcada para *Preview*. Precisa de acesso à Vercel dele.

### Riscos de configuração

- `ALLOWED_HOSTS` só aceita `.vercel.app` (e local). Domínio próprio exigiria alterar settings.
- Sem `SECURE_PROXY_SSL_HEADER`; o CSRF funciona porque `CSRF_TRUSTED_ORIGINS = ["https://*.vercel.app"]`. Não remover.
- Não há CSP (melhoria opcional; não bloqueia: o site não aceita HTML de usuários).

---

## 3. Evidência pública atual (GET, sem login) — 17/11/2026 09:45 UTC

`curl -sI https://loja-nexar.vercel.app/`:
`HTTP/1.1 200 OK`, `Strict-Transport-Security: max-age=63072000; includeSubDomains; preload`,
`X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`,
`Cross-Origin-Opener-Policy: same-origin`, `Server: Vercel`. Sem `Content-Security-Policy`.

`curl -sI http://loja-nexar.vercel.app/`: `HTTP/1.0 308 Permanent Redirect`, `Location: https://loja-nexar.vercel.app/`.

Ou seja: HTTP → HTTPS é redirecionado pela Vercel e o HSTS vem da Vercel (o Django não configura `SECURE_HSTS_*`).
A evidência cobre só o domínio `loja-nexar.vercel.app` nesta data; não afirma nada sobre outros domínios.

**Migrations em produção:** **[inferência forte]** `0001`–`0003` aplicadas (páginas usam a coluna `cor` sem erro).
Confirmar com a consulta 5 da seção 5.

---

## 4. O que será publicado

**Commit exato a publicar:** `<commit final da fase3-crud após a revisão>` (inclui todo o #5 e o #6).
Hoje: `backend-base` = `4ef3c46`, `fase3-crud` = `2812ad9`, mas o #6 ainda vai receber a 0006 e a opção B de uploads.

Resumo: login/cadastro/sair, painel só para staff, preço gravado no pedido, e-mail único (#5);
CRUD real de produtos e categorias com uploads validados, uploads desligados na Vercel (#6).

### Migrations — mudanças de schema (não são "inofensivas")

| Migration | PR | Alteração | Reversão de schema (`migrate loja …`) |
|---|---|---|---|
| `0004_pedido_preco_unitario` | #5 | `pedidos`: coluna `preco_unitario numeric(10,2)`, preenchida com o preço **atual** do produto, depois `NOT NULL`; CHECKs `produto_preco_nao_negativo`, `pedido_quantidade_minima_1`, `pedido_preco_unitario_nao_negativo`. Primeira operação: verificação somente leitura que aborta sem alterar nada se houver preço < 0 ou quantidade < 1. | `migrate loja 0003`: remove as CHECKs e **apaga a coluna `preco_unitario` com os valores** (perde o preço da compra dos pedidos). |
| `0005_email_unico` | #5 | `auth_user`: índice único `auth_user_email_ci_uniq` em `NULLIF(LOWER(TRIM(email)), '')`. Aborta sem alterar se houver e-mails repetidos. | `migrate loja 0004`: remove o índice. Sem perda de dados; e-mails duplicados voltam a ser possíveis. |
| `0006_categoria_nome_unico_ci` | #6 | `categorias`: índice único em `LOWER(TRIM(nome))`, com verificação que aborta se houver colisão. | `migrate loja 0005`: remove o índice. Sem perda de dados; nomes repetidos voltam a ser possíveis. |

Rollback de código (promover deploy antigo) **não** desfaz nenhuma delas. Ver seção 8.

---

## 5. Pré-checagens no Supabase (somente leitura — SQL editor)

Rodar **antes** do `migrate`, depois da aprovação dos PRs. Todas são `SELECT`.

```sql
-- 1) Pedidos que violariam quantidade >= 1 (esperado: 0 linhas)
SELECT id, quantidade FROM pedidos WHERE quantidade < 1;

-- 2) Produtos que violariam preco >= 0 (esperado: 0 linhas)
SELECT id, nome, preco FROM produtos WHERE preco < 0;

-- 3) E-mails repetidos ignorando caixa e espaços, sem vazios (esperado: 0 linhas)
SELECT LOWER(TRIM(email)) AS email_ci, COUNT(*) AS contas, ARRAY_AGG(id ORDER BY id) AS ids
FROM auth_user WHERE TRIM(email) <> ''
GROUP BY LOWER(TRIM(email)) HAVING COUNT(*) > 1;

-- 4) Categorias que colidem ignorando caixa e espaços (esperado: 0 linhas)
SELECT LOWER(TRIM(nome)) AS nome_ci, COUNT(*) AS categorias, ARRAY_AGG(id ORDER BY id) AS ids
FROM categorias GROUP BY LOWER(TRIM(nome)) HAVING COUNT(*) > 1;

-- 5) Migrations do app loja (esperado: 0001, 0002, 0003 e nada além)
SELECT * FROM django_migrations WHERE app = 'loja' ORDER BY id;

-- 6) Conferências extras
SELECT column_name FROM information_schema.columns
WHERE table_name = 'pedidos' AND column_name = 'preco_unitario';            -- esperado: 0 linhas
SELECT indexname FROM pg_indexes WHERE tablename IN ('auth_user', 'categorias'); -- conferir que os índices novos não existem
SELECT COUNT(*) AS pedidos FROM pedidos;
SELECT COUNT(*) AS pedidos_sem_produto FROM pedidos p
LEFT JOIN produtos pr ON pr.id = p.produto_id WHERE pr.id IS NULL;          -- esperado: 0
```

Se 1–4 retornarem linhas: parar; corrigir os dados é decisão humana. Se 5 mostrar algo diferente de 0001–0003: parar e investigar.

Também no Dashboard do Supabase: conferir que a **Data API** está desligada, ou que `auth_user`, `pedidos`,
`produtos` e `categorias` têm RLS ativa sem políticas públicas (senão a chave pública leria `auth_user`). Não verificado daqui.

---

## 6. Ordem e compatibilidade

**Código novo com banco antigo (deploy antes do migrate) — quebra:** o model novo lê `preco_unitario`;
`/painel/pedidos/` e `/admin/loja/pedido/` dão 500 até a 0004. Por isso o migrate vem antes.

**Código antigo com banco novo (migrate antes do deploy) — operações incompatíveis durante a janela:**

| Operação no código antigo (produção atual ou deploy intermediário do #5) | Resultado com 0004–0006 aplicadas |
|---|---|
| Criar Pedido pelo `/admin/` antigo (ou `popular_loja` antigo) | `INSERT` sem `preco_unitario` → viola `NOT NULL` → **500** |
| Salvar produto com preço negativo / pedido com quantidade 0 no admin antigo | viola CHECK → **500** (em vez de mensagem) |
| Criar/editar usuário com e-mail que colide (caixa/espaços) no admin antigo | viola índice da 0005 → **500** |
| Criar/renomear categoria que colide (`" Camisetas"` × `"camisetas"`) no admin antigo ou no painel do #5 | viola índice da 0006 → **500** |
| Leituras (home, produtos, `/painel/pedidos/` antigo) | funcionam; total ainda calculado com o preço atual até o deploy novo |

**Como suspender:** avisar a equipe antes da janela; **ninguém usa `/admin/` nem `/painel/`** do backup até a
verificação final. A loja pública não grava nada (não há checkout), então continua no ar.

**Deploy intermediário:** mergear o #5 gera um deploy de produção só com o #5 até o #6 entrar. Nesse intervalo
vale a linha da 0006 acima. Mergear o #6 logo em seguida.

---

## 7. Janela de mudança (sequência)

Pré-requisitos (sem efeito remoto): commit final do #6 com 0006 e opção B; suíte verde; `makemigrations --check` limpo.

1. **[AUTORIZAÇÃO] Revisão e aprovação** do #5 e do #6 pelo Guilherme no GitHub. Sem aprovação, parar aqui.
2. **[AUTORIZAÇÃO] Conferir variáveis do ambiente Preview** (seção 2) — Guilherme.
3. **Avisar a equipe** da janela (seção 6).
4. **[AUTORIZAÇÃO] Backup** — quem administra o Supabase: Dashboard → Database → Backups (conferir backup recente;
   no plano gratuito não há restauração pontual garantida) **e** dump próprio:
   `pg_dump "<URL de conexão direta ou session pooler>" -Fc -f nexar_antes_0004.dump`
   (URL só na variável da sessão, nunca em arquivo versionado).
5. **[AUTORIZAÇÃO] Pré-checagens** somente leitura (seção 5).
6. **[AUTORIZAÇÃO] `migrate`** — Eliton, na própria máquina, no checkout do `<commit final da fase3-crud após a revisão>`:

   ```powershell
   # sessão nova; a URL só existe nesta janela (não gravar no .env)
   Get-ChildItem Env:DB_SSLMODE              # deve dar erro (não definida); e sem DB_SSLMODE=disable no .env
   $env:DATABASE_URL = "<URL do Supabase>"   # Session pooler (5432) ou conexão direta para DDL
   python manage.py showmigrations loja      # 0001-0003 [X]; 0004, 0005, 0006 [ ]
   python manage.py migrate --plan           # só loja.0004, loja.0005, loja.0006
   python manage.py migrate
   python manage.py showmigrations loja      # 0001-0006 [X]
   Remove-Item Env:DATABASE_URL
   ```

   Não rodar `popular_loja` no Supabase. Se uma verificação abortar, o PostgreSQL desfaz a transação daquela
   migration: corrigir os dados e repetir.
7. **[AUTORIZAÇÃO] Merge do #5** na `main` (merge commit) — Guilherme. Deploy automático do #5.
8. **Conferir/mudar a base do #6 para `main`**; checks verdes; **[AUTORIZAÇÃO] merge do #6** — Guilherme. Deploy automático final.
   Acompanhar até "Ready" no painel da Vercel. Não usar `vercel deploy --prod` manual.
9. **Verificação** (checklist abaixo). Só então liberar admin/painel para a equipe.

### Checklist pós-deploy

Visitante (aba anônima):
- [ ] `/`, `/produtos/`, `/produto/1/` → 200, fotos e 3D carregando.
- [ ] `/entrar/`, `/cadastro/` → 200; `GET /sair/` → 405.
- [ ] `/painel/` → 302 para `/entrar/?next=/painel/`.
- [ ] `/admin/login/` → 200; URL inexistente → 404 genérico.
- [ ] `curl -sI https://loja-nexar.vercel.app/` mantém `Strict-Transport-Security`; `http://` → 308 para `https://`.

Cliente (conta de teste criada no `/cadastro/`):
- [ ] Cadastro conclui e mostra "Olá, <usuário>" + Sair.
- [ ] Mesmo e-mail em MAIÚSCULAS → "Já existe uma conta com este e-mail.".
- [ ] `/painel/` → home com "Acesso restrito à equipe da loja.".
- [ ] Sair → "Você saiu da sua conta."; login errado → mensagem, sem 500.

Staff:
- [ ] `/painel/` (lista de produtos), `/painel/produtos/novo/`, `/painel/categorias/`, `/painel/pedidos/` → 200; totais em R$.
- [ ] Formulário de produto mostra o aviso de **uploads desativados** e campos de arquivo desabilitados (confirma que `VERCEL` existe no runtime).
- [ ] Editar nome/preço de um produto sem trocar arquivo → salva e a foto/3D continuam aparecendo.
- [ ] Criar categoria com nome que colide em caixa (ex.: `camisetas`) → mensagem de erro, sem 500.
- [ ] `/admin/loja/pedido/add/` sem preço → salva com o preço atual do produto.
- [ ] Remover/desativar as contas e dados de teste.

---

## 8. Recuperação — três coisas diferentes

| Tipo | Como | O que volta / o que se perde |
|---|---|---|
| **Rollback de código** | [AUTORIZAÇÃO] Vercel → Deployments → deploy anterior → *Promote to Production*, ou revert do merge na `main`. | Só o código. O schema continua em 0006; o código antigo passa a ter as incompatibilidades da seção 6 (criar pedido no admin, colisões → 500). Normalmente basta isso e suspender o admin. |
| **Reversão de schema** | [AUTORIZAÇÃO] Com o código da branch e a `DATABASE_URL`, **depois** do rollback de código: `migrate loja 0005` (tira índice de categorias), `migrate loja 0004` (tira também o de e-mail), `migrate loja 0003` (tira CHECKs e **apaga `preco_unitario`**). | 0006/0005: sem perda de dados. 0004: perde o preço gravado de todos os pedidos (inclusive os feitos depois do deploy); o total volta a usar o preço atual. O código novo não funciona sem a coluna. |
| **Restauração de dados** | [AUTORIZAÇÃO] `pg_restore` do dump do passo 4 ou backup do Supabase. | Volta o banco inteiro ao momento do backup: **perde tudo** gravado depois (contas, pedidos, produtos). Último recurso. |

---

## 9. Limitações deste levantamento

- Sem acesso ao projeto da Vercel nem ao Supabase: variáveis por ambiente, logs, opção de variáveis de sistema e
  estado real das migrations não foram vistos; confirmar com a seção 5 e com o Guilherme.
- Só GET público em produção; previews não abertos (SSO).
- Migrations testadas em PostgreSQL 17 local descartável e MySQL 8.0.46 (ver `docs/validacao_banco.md`); a 0006 deve
  passar pela mesma validação antes da janela. Nada testado contra o pooler do Supabase.

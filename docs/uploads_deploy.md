# Uploads do painel: local × Vercel

Levantamento de 17/11/2026 (≈ 09:45 UTC). Legenda: **[verificado]** = conferido em documentação oficial,
comando ou código; **[inferência]** = conclusão sem teste direto. Nenhum recurso remoto foi criado ou alterado.

## 1. Fatos da plataforma (fontes oficiais)

| Fato | Fonte |
|---|---|
| **[verificado]** Django roda na Vercel como **uma única Vercel Function** (runtime Python, Fluid compute por padrão); a Vercel acha o `manage.py` e usa `WSGI_APPLICATION`. | [Deploy a Django app on Vercel](https://vercel.com/docs/frameworks/full-stack/django) |
| **[verificado]** Python disponível: 3.12 (padrão), 3.13, 3.14. Sem `.python-version`/`pyproject.toml`, vale o padrão 3.12 (o projeto não fixa versão). | [Python runtime](https://vercel.com/docs/functions/runtimes/python) |
| **[verificado]** Sistema de arquivos **somente leitura**, com `/tmp` gravável até 500 MB; arquivos em `/tmp` são da instância, outras instâncias não os veem e somem quando ela para. | [Runtimes → File system support](https://vercel.com/docs/functions/runtimes#file-system-support) |
| **[verificado]** Corpo da **requisição ou resposta: máximo 4,5 MB**; acima disso a Vercel devolve `413 FUNCTION_PAYLOAD_TOO_LARGE` (antes de chegar ao Django). | [Functions limits → Request body size](https://vercel.com/docs/functions/limitations#request-body-size) |
| **[verificado]** Duração: Hobby 300 s padrão e máximo (Fluid compute); Pro 300 s padrão, 800 s máximo. | [Functions limits → Max duration](https://vercel.com/docs/functions/limitations#max-duration) |
| **[verificado]** `VERCEL=1` está disponível "both build and runtime". A página condiciona as variáveis de sistema à opção **"Enable access to System Environment Variables"** do projeto. | [System environment variables](https://vercel.com/docs/environment-variables/system-environment-variables) |
| **[verificado]** O Python SDK do Blob (`vercel` / `vercel-blob`) **não** faz upload direto do navegador nem URL assinada: isso exige o SDK JavaScript. | [Store and serve files from Python with Vercel Blob](https://vercel.com/kb/guide/python-and-vercel-blob) |

**Conta do multipart.** O formulário do produto aceita foto (até 5 MB), foto vestindo (até 5 MB) e `.glb`
(até 15 MB) — `loja/forms.py` (`IMAGEM_MAX_MB = 5`, `MODELO_MAX_MB = 15`). O limite de 4,5 MB vale para
o **corpo inteiro** do POST, não por arquivo: 5 + 5 + 15 MB = 25 MB. Mesmo **uma única foto de 5 MB**
já passa do limite. Na Vercel, qualquer envio acima de ~4,5 MB no total morre com 413 sem passar pelos
validadores do Django; os limites de 5 e 15 MB do formulário só fazem sentido localmente.

**Risco do `VERCEL`.** **[inferência]** Se alguém desmarcar "Enable access to System Environment Variables",
`VERCEL` pode deixar de existir e a opção B (abaixo) liga os uploads de novo na Vercel. Conferir após o
deploy: o aviso de "uploads desativados" tem de aparecer no painel de produção.

## 2. Estado local (avaliação, MySQL)

**[verificado no código]** `MEDIA_ROOT = BASE_DIR / "media"` (pasta no `.gitignore`), `MEDIA_URL` padrão `/media/`,
`config/urls.py` serve `MEDIA` só com `DEBUG=True`. O CRUD grava em `media/produtos/` e `media/modelos/`,
valida imagem com Pillow e a estrutura do `.glb` no servidor. Funciona por completo na máquina da apresentação.

## 3. Estado no deploy (Vercel)

- **[verificado]** `MEDIA_URL=/static/img/` em produção: valores gravados no banco como `produtos/x.jpg` viram
  `/static/img/produtos/x.jpg`, servidos dos arquivos versionados em `static/img/produtos/`. Os `.glb`
  existentes estão gravados como `/static/modelos/*.glb` (caminho absoluto, não passam pelo prefixo).
- **[inferência]** Sem a opção B, um upload pequeno (< 4,5 MB) tentaria gravar em `BASE_DIR/media` (somente
  leitura) → erro 500; ou, se gravasse em `/tmp`, o arquivo sumiria e a URL apontaria para `/static/img/...`,
  que não existe. Upload grande → 413 da Vercel. Em nenhum caso o arquivo persiste.

## 4. Opção B — uploads desligados no deploy (implementada nesta rodada)

Implementação feita em paralelo por outro agente; descrição do comportamento combinado (conferir no commit final):

| Aspecto | Comportamento |
|---|---|
| Chave | `UPLOADS_HABILITADOS = False` quando a variável de ambiente `VERCEL` existe; `True` em qualquer outro ambiente (local/MySQL). |
| O que o usuário vê | Aviso no formulário do produto explicando que envio de arquivos está desativado na versão publicada; campos de arquivo desabilitados. Os demais campos (nome, preço, estoque, categoria, cor) continuam editáveis. |
| O que o servidor faz | Recusa explícita (erro de formulário, sem 500) se chegar arquivo com uploads desligados. Não apaga nem troca o arquivo atual: imagens/modelos existentes são preservados. |
| Limite real | A recusa no servidor só acontece para POST ≤ 4,5 MB; acima disso a Vercel responde 413 antes do Django. Por isso o aviso/desabilitar na interface é o que evita a tela de erro. |
| Como reativar | Só depois de existir storage persistente (opção A). Remover/ajustar a condição de `UPLOADS_HABILITADOS` no mesmo PR que configurar o storage. Não adianta só mudar variável: sem storage o arquivo não persiste. |

**Impacto na apresentação:** nenhum se a demonstração do CRUD com upload for feita **localmente** (MySQL), que
é o ambiente da avaliação. No site publicado dá para mostrar criar/editar/excluir produtos e categorias sem
trocar foto/modelo, e explicar a limitação como decisão consciente de arquitetura.

## 5. Opção A — storage externo persistente (não implementada)

Duas candidatas realistas. Nenhuma foi contratada ou criada.

| Critério | Vercel Blob | Supabase Storage (S3 via `django-storages`/boto3) |
|---|---|---|
| Plano gratuito | **[verificado]** Hobby: 1 GB/mês de armazenamento, 10 mil operações simples, 2 mil avançadas (upload conta), 10 GB de transferência; ao estourar, **Blob fica bloqueado por 30 dias** (sem cobrança). [Pricing](https://vercel.com/docs/vercel-blob/usage-and-pricing) | **[verificado]** Free: 1 GB de arquivos, 5 GB de egress (+5 GB cacheado), arquivo de até **50 MB**; projeto pausa após 1 semana sem uso. [Pricing](https://supabase.com/pricing), [File limits](https://supabase.com/docs/guides/storage/uploads/file-limits) |
| Upload > 4,5 MB | Precisa de *client upload* (navegador → Blob). **[verificado]** Só no SDK JS (`@vercel/blob/client` + rota `handleUpload` em JS). O Django (Python) não gera esse token com o SDK oficial; exigiria função Node à parte ou implementar o protocolo na mão. [Client uploads](https://vercel.com/docs/vercel-blob/client-upload) | **[verificado]** URL de upload assinada: `create_signed_upload_url` no SDK Python e `uploadToSignedUrl` no JS; também S3 com assinatura SigV4. Presign de `PutObject` não está explicitamente confirmado na página de compatibilidade: testar. [Standard uploads](https://supabase.com/docs/guides/storage/uploads/standard-uploads), [S3 compat](https://supabase.com/docs/guides/storage/s3/compatibility) |
| Autorização | Rota de token tem de checar staff (`onBeforeGenerateToken`); restringe `allowedContentTypes` e tamanho. | View Django com `somente_staff` gera a URL assinada para um caminho decidido pelo servidor (ex.: `produtos/<uuid>.jpg`). Bucket com escrita bloqueada para a chave pública (RLS/políticas). |
| Validação (Pillow, GLB estrutural) | O arquivo não passa pelo Django. Validação **pós-upload**: no callback/ao salvar o form, o servidor baixa o objeto (até 15 MB, dentro do tempo da função), roda Pillow/verificação do GLB e **apaga** se inválido. Token limita tipo e tamanho. | Igual: o form recebe só o caminho do objeto; o servidor confere que o caminho é o que ele assinou, baixa, valida e apaga se inválido. Limite de tamanho do bucket como barreira extra. |
| Mudanças no código | `STORAGES["default"]` com backend próprio (não há backend oficial de Blob para `django-storages`). | `STORAGES["default"]` = `storages.backends.s3.S3Storage` com endpoint do Supabase; `django-storages[s3]` no `requirements.txt`. [django-storages S3](https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html), [Django STORAGES](https://docs.djangoproject.com/en/6.0/ref/settings/#storages) |
| Comum às duas | Templates/JS passam a usar `field.url` (URL completa) em vez de `MEDIA_URL` + nome: `data-modelo="{{ p.modelo_3d.url }}"`, e `{% get_media_prefix %}` deixa de ser usado para uploads. `static/js/pecas.js` (`caminho()`, ~linha 161) já aceita URL `http…` inteira, mas o formulário do painel precisa de JS novo para enviar direto ao storage. **Arquivos do frontend: combinar com o Guilherme.** Migrar valores antigos (`produtos/x.jpg` em `static/`) ou manter compatibilidade. | |
| Riscos | Token estático `BLOB_READ_WRITE_TOKEN` exposto se mal configurado; arquivo órfão se o form não for salvo; limite de 30 dias de bloqueio no Hobby; dependência de JS/Node. | Projeto Free pausa sem uso; chave `service_role`/S3 só no servidor; arquivo órfão; CORS do bucket. |
| Esforço estimado | **[inferência]** 2–3 dias (rota Node + JS + validação pós-upload + testes). | **[inferência]** 1,5–2 dias (backend S3, view de URL assinada, JS de envio, validação pós-upload, testes). |

## 6. Recomendação para o prazo (19/11/2026)

**Opção B agora; opção A só depois da apresentação, se o projeto continuar.** Faltam 2 dias; A exige criar
recurso remoto (autorização do Guilherme/Eliton), mexer no frontend e testar upload direto, com risco de
quebrar o painel às vésperas. B não depende de nada remoto, mantém o site estável e a avaliação acontece
no MySQL local, onde o upload funciona. Se A for feita no futuro, a candidata mais simples para este
projeto (Django puro, Python) é o **Supabase Storage**, por ter URL assinada no SDK Python e já ser o
fornecedor do banco.

Nada aqui é bloqueador da publicação: B já impede o erro e não muda o banco.

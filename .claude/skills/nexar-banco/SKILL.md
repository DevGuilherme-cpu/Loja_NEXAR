---
name: nexar-banco
description: Banco de dados da NEXAR — MySQL local, Supabase em produção, models, migrations, dados de exemplo e o SQL que o professor quer ver. Usar ao mudar model, criar campo/tabela, mexer em views que consultam o banco ou preparar o banco.sql.
---

# Banco da NEXAR

## Qual banco está ativo (decidido em `config/settings.py` pelo `.env`)

| Variável | Banco | Onde |
|---|---|---|
| `DATABASE_URL` | Supabase (PostgreSQL, Transaction pooler :6543) | Vercel / produção |
| `DB_NAME` (+ `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT=3307`) | MySQL 8.0 local (`nexar`) | computador, apresentação |
| nenhum | SQLite | testes rápidos |

- Django fixado em **6.0.x**: o 6.1 exige MySQL 8.4 e o local é 8.0.
- Driver MySQL = **PyMySQL** (puro Python, instala também na Vercel).
- Antes de rodar qualquer comando, confirme qual banco está ativo:
  `python -c "import os,django;os.environ['DJANGO_SETTINGS_MODULE']='config.settings';django.setup();from django.db import connection as c;print(c.vendor, c.settings_dict['NAME'])"`

## Tabelas (limite do trabalho: 3 a 5 tabelas próprias)

`auth_user` (do Django) · `categorias` · `produtos` (cor, imagem, imagem_2, modelo_3d) · `pedidos`.
FKs com `on_delete=PROTECT`. Não criar tabela nova sem a pessoa concordar (estoura o limite).

## Mudou um model

1. `python manage.py makemigrations loja` e ler a migration gerada.
2. `python manage.py migrate` (MySQL local) e `python manage.py test loja`.
3. **Avisar** que o Supabase também precisa: no PowerShell,
   `$env:DATABASE_URL="..."`, `python manage.py migrate`, `Remove-Item Env:DATABASE_URL`.
   A IA não roda isso no Supabase sem a pessoa pedir.
4. Dado novo para registros que já existem → migration com `RunPython` (ver `0003_cores_e_modelos_locais.py`),
   assim o mesmo `migrate` atualiza os dois bancos.
5. Atualizar `loja/mock_data.py` + `popular_loja` para bancos novos.

## Proibido

`flush`, `DROP`, `TRUNCATE`, `DELETE` sem `WHERE`, `migrate loja zero`, apagar migrations já aplicadas,
editar migration que já foi para o GitHub, imprimir o conteúdo do `.env`.

## Consultas e performance

- Card mostra categoria → `select_related("categoria")` (evita N+1).
- Pedidos → `select_related("usuario", "produto__categoria")` = o **JOIN** do trabalho.
- Contagem por categoria → `annotate(total=Count("produto"))`.
- Filtro vindo da URL: validar (`categoria.isdigit()`), nunca montar SQL com string.

## SQL para a apresentação (o professor quer ver os comandos)

- CREATE TABLE gerado: `python manage.py sqlmigrate loja 0001`.
- Ver o JOIN que o Django faz: `print(Pedido.objects.select_related("usuario","produto__categoria").query)`.
- Consultas para rodar no Workbench: seção 7 do `NEXAR_Plano_do_Projeto.pdf`.

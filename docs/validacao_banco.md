# Validação do banco - NEXAR

Data: 16/11/2026. Branch `rev-banco` (com `rev-auth` integrado, que traz a `0005_email_unico`).

Legenda: **EXECUTADO** = comando rodado de verdade, saída colada abaixo (resumida).
**ESTÁTICO** = só leitura/análise do código, nada foi rodado.

## Resumo

| Item | Banco | Situação |
|---|---|---|
| `check`, `makemigrations --check --dry-run`, `test loja` (55 testes) | SQLite | EXECUTADO, OK |
| Instalação do zero (migrate + popular_loja + constraints + JOIN do painel) | PostgreSQL 17.11 | EXECUTADO, OK |
| Atualização com dados 0003 -> 0004 (preco_unitario = preço atual, NOT NULL) | PostgreSQL 17.11 | EXECUTADO, OK |
| 0004 bloqueia quantidade 0 / preço negativo e desfaz tudo | PostgreSQL 17.11 e SQLite (teste) | EXECUTADO, OK |
| 0005: índice único de e-mail, colisão por caixa, e-mail vazio, bloqueio, reverse | PostgreSQL 17.11 | EXECUTADO, OK |
| `test loja` (55 testes) | PostgreSQL 17.11 | EXECUTADO, OK |
| Tudo acima no MySQL + `docs/banco.sql` | MySQL | **PENDENTE** (sem credencial) - roteiro em `docs/validacao_mysql.ps1` |
| `docs/banco.sql` coerente com os models | - | ESTÁTICO |

## Ambiente PostgreSQL de teste

Container descartável, isolado dos outros containers da máquina, só em 127.0.0.1:

```powershell
docker run -d --rm --name nexar-pg-teste -e POSTGRES_PASSWORD=<aleatória> `
  -e POSTGRES_DB=nexar_pg_teste -p 127.0.0.1:55432:5432 postgres:17-alpine
```

```
PostgreSQL 17.11 on x86_64-pc-linux-musl, compiled by gcc (Alpine 15.2.0) 15.2.0, 64-bit
```

Variáveis usadas (senha omitida): `SECRET_KEY=teste DEBUG=True DB_SSLMODE=disable
DATABASE_URL=postgresql://postgres:***@127.0.0.1:55432/nexar_pg_teste`.
`DB_SSLMODE` é a variável nova do `config/settings.py` (padrão `require`, o que o Supabase exige).
Nenhuma conexão foi feita no Supabase nem no MySQL local. Ao final: `docker stop nexar-pg-teste`
(o `--rm` removeu o container).

## a) Instalação do zero

```
manage.py migrate        -> loja.0001 ... 0005_email_unico OK (23 migrations)
manage.py popular_loja   -> Pronto: 5 categorias, 9 produtos, 5 usuários e 5 pedidos.
contagens (categorias|produtos|auth_user|pedidos) -> 5|9|5|5
```

`\d pedidos` (via `docker exec nexar-pg-teste psql`):

```
 preco_unitario | numeric(10,2) | not null
Check constraints:
    "pedido_preco_unitario_nao_negativo" CHECK (preco_unitario >= 0::numeric)
    "pedido_quantidade_minima_1" CHECK (quantidade >= 1)
    "pedidos_quantidade_check" CHECK (quantidade >= 0)
Foreign-key constraints:
    "pedidos_produto_id_e8bf22a9_fk_produtos_id" FOREIGN KEY (produto_id) REFERENCES produtos(id) DEFERRABLE INITIALLY DEFERRED
    "pedidos_usuario_id_2b8cebd6_fk_auth_user_id" FOREIGN KEY (usuario_id) REFERENCES auth_user(id) DEFERRABLE INITIALLY DEFERRED
```

`\d produtos`: `cor character varying(7) not null`, `produto_preco_nao_negativo CHECK (preco >= 0::numeric)`.

`\d auth_user`:

```
"auth_user_email_ci_uniq" UNIQUE, btree (NULLIF(lower(email::text), ''::text))
```

JOIN do painel: o queryset da view (`Pedido.objects.select_related("usuario", "produto__categoria")`)
gera 3 JOINs e roda em **1 consulta**; `GET /painel/pedidos/` com usuário staff respondeu **200**
mostrando `ana.souza` e `449,70`. O JOIN equivalente em SQL:

```
 id | username  |       nome        | categoria  | quantidade | preco_unitario | total
  1 | eva.costa | Tênis Runner X    | Acessórios |          1 |         699.90 | 699.90
  2 | daniel    | Boné 6-Panel      | Bonés      |          2 |         129.90 | 259.80
  3 | carla.m   | Calça Cargo Tech  | Calças     |          1 |         349.90 | 349.90
  4 | bruno     | Moletom Heavy     | Moletons   |          1 |         399.90 | 399.90
  5 | ana.souza | Camiseta Box Logo | Camisetas  |          3 |         149.90 | 449.70
```

## b) Atualização com dados (0003 -> 0004)

Banco recriado dentro do container (`DROP DATABASE` / `CREATE DATABASE nexar_pg_teste`), depois
`migrate contenttypes|auth|admin|sessions` (como em produção) e `migrate loja 0003`. Dados
inseridos por SQL (o `popular_loja` não serve: grava `preco_unitario`): 2 categorias, 3 produtos,
2 usuários, 3 pedidos sem `preco_unitario`, e um reajuste **depois** das compras
(`UPDATE produtos SET preco = 179.90 WHERE id = 1`, era 149.90).

Observação do caminho: na primeira tentativa rodei só `migrate loja 0003`; isso aplica o `auth`
apenas até a migration exigida pela loja, em que `last_login` ainda é NOT NULL, e o INSERT
manual falhou. Não é problema da 0004 (em produção o `auth` está completo); refeito com o `auth`
inteiro.

`manage.py migrate` -> `loja.0004 OK`, `loja.0005 OK`:

```
 id | quantidade | preco_unitario | preco_atual | igual
  1 |          3 |         179.90 |      179.90 | t      <- preço ATUAL, não o 149.90 da compra
  2 |          2 |         129.90 |      129.90 | t
  3 |          1 |         159.90 |      159.90 | t
preco_unitario is_nullable = NO
```

Isso confirma a limitação documentada na 0004: antes dela o preço pago não era guardado, então o
preenchimento usa o preço atual e não recupera histórico.

### Bloqueio por dados inválidos

Mesmo preparo + pedido 4 com `quantidade = 0` + produto 3 com `preco = -5`:

```
manage.py migrate  -> exit=1
RuntimeError: Migração loja.0004 interrompida: há dados que violam as novas regras do banco.
- 1 produto(s) com preço negativo (preco < 0). ids: 3
- 1 pedido(s) com quantidade menor que 1. ids: 4
Corrija esses registros manualmente (no /admin/ ou por SQL) e rode o migrate de novo. Nenhum dado foi corrigido automaticamente.

showmigrations loja -> [X] 0003  [ ] 0004  [ ] 0005
coluna pedidos.preco_unitario -> não existe (0)
pedido 4 continua com quantidade 0; produto 3 continua com preço -5.00
```

Numa rodada anterior (só quantidade 0) também conferi por md5 que a tabela `pedidos` ficou
idêntica e que, depois de `UPDATE pedidos SET quantidade = 1 WHERE id = 4`, o `migrate` passou.

**Mudança feita a partir disso:** a verificação foi movida para a **primeira** operação da 0004
(antes do `AddField`). No PostgreSQL/SQLite não faz diferença (a migração é uma transação), mas
no MySQL o DDL não é transacional: com a verificação no meio, `AddField`/`AlterField` ficariam
aplicados e o `migrate` seguinte falharia com coluna duplicada. Os resultados acima são da versão
final (verificação primeiro).

## Migration 0005 (e-mail único) - PostgreSQL

```
-- e-mail que difere só na caixa
INSERT ... 'Ana@Ex.com'  -> INSERT 0 1
INSERT ... 'ana@ex.COM'  -> ERROR: duplicate key value violates unique constraint "auth_user_email_ci_uniq"
                            DETAIL: Key (NULLIF(lower(email::text), ''::text))=(ana@ex.com) already exists.
-- dois e-mails vazios (além dos 5 clientes de exemplo, também com e-mail vazio)
INSERT ... ''  -> INSERT 0 1
INSERT ... ''  -> INSERT 0 1

-- reverse
manage.py migrate loja 0004 -> Unapplying loja.0005_email_unico... OK ; índice: 0

-- base em 0004 com 'Dup@Teste.com' e 'dup@teste.com'
manage.py migrate -> exit=1
EmailsDuplicados: Não foi possível criar o índice único de e-mail: 1 e-mail(s) repetido(s)
(ignorando maiúsculas/minúsculas) em 2 contas: d***@teste.com (2 contas). Resolva manualmente
(...) e rode o migrate de novo. Nenhuma conta foi alterada.
showmigrations loja -> [X] 0004  [ ] 0005 ; índice: 0 ; os dois e-mails continuam como estavam
-- depois de esvaziar o e-mail de uma conta: Applying loja.0005_email_unico... OK
```

## c) Suíte completa

```
PostgreSQL: manage.py test loja --noinput   (Django criou e apagou test_nexar_pg_teste)
Ran 55 tests in 21.962s
OK

SQLite: manage.py test loja
Ran 55 tests in 19.134s
OK
manage.py check                          -> System check identified no issues (0 silenced).
manage.py makemigrations --check --dry-run -> No changes detected
```

Os 55 incluem `loja/test_email.py` (vindo do `rev-auth`) e os 2 testes novos de
`MigracaoBloqueiaDadosInvalidosTest` em `loja/test_modelos.py` (voltam para a 0003, criam
quantidade 0 / preço negativo pelos modelos históricos, esperam o erro, conferem que a 0004 não
foi registrada, que a coluna não existe e que o dado não mudou; no `tearDown` limpam os dados e
voltam para o leaf).

## MySQL - pendente

Não executado: a credencial do MySQL local não está disponível (o serviço MySQL80 roda na porta
3306, o `.env` aponta 3307 e a senha foi recusada). Não tentei adivinhar nem redefinir senha, nem
baixar imagem MySQL.

Pronto para rodar: `docs/validacao_mysql.ps1` (sintaxe conferida com o parser do PowerShell; não
executado). Ele:

- exige MySQL 8.0.13+ (índice funcional da 0005);
- recusa o banco `nexar`, recusa rodar se o `.env` tiver `DATABASE_URL` ativo, e **aborta sem
  apagar** se `nexar_zero_teste`, `nexar_migracao_teste`, `nexar_script` ou `test_nexar_suite` já
  existirem;
- do zero (`nexar_zero_teste`): migrate, popular_loja, `SHOW CREATE TABLE pedidos`, índice de
  e-mail, JOIN do painel, CHECK de quantidade, colisão de e-mail por caixa, reverse da 0005;
- upgrade (`nexar_migracao_teste`): 0003 + dados com quantidade 0 -> 0004 bloqueia e a coluna
  **não** pode existir (prova que a verificação vem antes do DDL), corrige, 0004, confere
  `preco_unitario`; e-mails duplicados -> 0005 bloqueia, corrige, conclui;
- `manage.py test loja` (o Django cria/apaga `test_nexar_suite`);
- `docs/banco.sql` via `mysql.exe` (senha por `MYSQL_PWD`, fora da linha de comando).

Pontos a observar quando rodar no MySQL: (1) se a 0004 falhar, conferir que não ficou coluna
órfã; (2) `CREATE UNIQUE INDEX ... ((NULLIF(LOWER(email), '')))` no MySQL; (3) o `banco.sql`
nunca foi executado.

## docs/banco.sql - análise estática

- Só cria e usa `nexar_script` (`CREATE DATABASE nexar_script` sem `IF NOT EXISTS`, então falha
  sem alterar nada se o banco já existir; `USE nexar_script`). Não há `DROP DATABASE` (o
  comentário que sugeria `DROP DATABASE nexar_script` foi reescrito) e não referencia `nexar`.
- Ajustes: coluna `cor VARCHAR(7) NOT NULL DEFAULT ''` em `produtos` (0002) e nos INSERTs (cores
  da 0003); `modelo_3d` dos produtos 8 e 9 trocado para `/static/modelos/*.glb` (0003); índice
  `auth_user_email_ci_uniq` (0005). Cabeçalho deixa explícito: `auth_user` simplificada,
  demonstrativo, não substitui migrations nem é backup, não executado em MySQL.
- Não executei a parte equivalente no PostgreSQL de propósito: o script é MySQL
  (`AUTO_INCREMENT`, `ENGINE=InnoDB`, `TINYINT(1)`), e reescrevê-lo não valida o arquivo entregue.
- Diferença conhecida e aceitável: no Django a coluna `cor` não tem DEFAULT no banco (o default
  vazio é aplicado pelo Django); no script o `DEFAULT ''` foi mantido por ser só demonstração.

---

## Revalidação do coordenador — 17/11/2026 (índice com TRIM)

Motivo: o QA independente mostrou que `NULLIF(LOWER(email), '')` aceitava `" a@x.com"` ao lado de
`a@x.com`. A 0005 (ainda não publicada) passou a usar `NULLIF(LOWER(TRIM(email)), '')`, e a validação
do formulário compara `LOWER(TRIM(email))` (pega também contas antigas com espaços).
As saídas acima com `NULLIF(lower(email::text), ...)` são da versão anterior.

Ambiente: container descartável `postgres:17-alpine` (`nexar-pg-coord`, 127.0.0.1:55434,
`DB_SSLMODE=disable`), PostgreSQL **17.11** (`server_version` 170011), código da `backend-base` com a correção.

| Passo | Resultado |
|---|---|
| `migrate` do zero + `popular_loja` | OK — 5 categorias, 9 produtos, 5 usuários, 5 pedidos |
| `\d auth_user` | `"auth_user_email_ci_uniq" UNIQUE, btree (NULLIF(lower(TRIM(BOTH FROM email)), ''::text))` |
| INSERT `a@x.com` + dois e-mails `''` | aceito (`INSERT 0 3`) |
| INSERT `' A@X.com '` | `ERROR: duplicate key value violates unique constraint "auth_user_email_ci_uniq"` |
| `migrate loja 0004` (reverse) | índice removido (`pg_indexes` → 0) |
| `migrate` (reaplicar) | índice recriado com a mesma definição |
| `manage.py test loja --noinput` | **Ran 57 tests — OK** |

O container foi parado (`--rm`). Nenhum banco remoto foi acessado.

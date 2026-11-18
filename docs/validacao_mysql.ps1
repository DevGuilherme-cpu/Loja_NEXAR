<#
Validação da NEXAR no MySQL (ainda NÃO executada: falta a credencial local).

O que faz, sempre em bancos de TESTE (nunca no banco "nexar" da aplicação):
  1. confirma a versão do servidor (precisa de 8.0.13+ por causa do índice funcional de e-mail);
  2. confere que os bancos de teste NÃO existem; se algum existir, ABORTA sem apagar nada;
  3. nexar_zero_teste: migrate do zero + popular_loja + SHOW CREATE TABLE + JOIN do painel;
  4. nexar_migracao_teste: upgrade com dados 0003 -> 0004 -> 0005, incluindo os bloqueios
     (pedido com quantidade 0 na 0004 e e-mails repetidos na 0005);
  5. suíte completa (manage.py test loja); o Django cria e apaga o banco test_<DbBaseTeste>;
  6. docs/banco.sql no banco nexar_script (via mysql.exe).

Nenhum banco é apagado por este script. Ao final ele lista os bancos de teste que ficaram
para você apagar manualmente, se quiser.

Uso (PowerShell, na raiz do projeto):
  $env:MYSQL_USER = "root"; $env:MYSQL_HOST = "127.0.0.1"; $env:MYSQL_PORT = "3306"
  .\docs\validacao_mysql.ps1          # a senha é pedida sem aparecer na tela
#>
param(
    [string]$Python = ".\.venv\Scripts\python.exe",
    [string]$MysqlExe = "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe",
    # NAME usado só na suíte de testes: o Django cria/apaga test_<este nome>.
    # O padrão gera test_nexar_suite; NÃO use "nexar" aqui.
    [string]$DbBaseTeste = "nexar_suite"
)

$ErrorActionPreference = "Stop"
$BancoZero = "nexar_zero_teste"
$BancoMigracao = "nexar_migracao_teste"
$BancoScript = "nexar_script"
$BancoSuite = "test_$DbBaseTeste"

if (-not (Test-Path ".\manage.py")) { throw "Rode a partir da raiz do projeto (onde fica o manage.py)." }
if (Test-Path ".\.env") {
    # load_dotenv não sobrescreve variáveis já definidas, mas PREENCHE as que faltam:
    # um DATABASE_URL ativo no .env levaria o Django para o PostgreSQL (Supabase).
    if (Select-String -Path ".\.env" -Pattern '^\s*DATABASE_URL\s*=' -Quiet) {
        throw ".env tem DATABASE_URL ativo: comente essa linha antes de rodar (risco de conectar no Supabase)."
    }
    Write-Warning ".env encontrado: DB_NAME/DB_USER/DB_PASSWORD/DB_HOST/DB_PORT definidos por este script têm prioridade."
}
foreach ($nome in @($BancoZero, $BancoMigracao, $BancoScript, $BancoSuite, $DbBaseTeste)) {
    if ($nome -eq "nexar") { throw "Proibido usar o banco 'nexar' (da aplicação)." }
}

if (-not $env:MYSQL_USER) { $env:MYSQL_USER = "root" }
if (-not $env:MYSQL_HOST) { $env:MYSQL_HOST = "127.0.0.1" }
if (-not $env:MYSQL_PORT) { throw "Defina MYSQL_PORT (nesta maquina o servico MySQL80 usa 3306; a skill nexar-banco cita 3307). Nao ha valor padrao para nao conectar na instancia errada." }
if (-not $env:MYSQL_PASSWORD) {
    $seguro = Read-Host "Senha do MySQL para $($env:MYSQL_USER)" -AsSecureString
    $env:MYSQL_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($seguro))
}

# Variáveis lidas pelo config/settings.py (ramo MySQL). DATABASE_URL tem prioridade, então removemos.
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
$env:SECRET_KEY = "teste"; $env:DEBUG = "True"; $env:PYTHONIOENCODING = "utf-8"
$env:DB_USER = $env:MYSQL_USER; $env:DB_PASSWORD = $env:MYSQL_PASSWORD
$env:DB_HOST = $env:MYSQL_HOST; $env:DB_PORT = $env:MYSQL_PORT

function Sql([string]$sql, [string]$banco = "") {
    # Executa SQL com PyMySQL (já é dependência do projeto) e imprime as linhas separadas por " | ".
    $env:NEXAR_SQL = $sql; $env:NEXAR_SQL_DB = $banco
    $codigo = @'
import os, pymysql
c = pymysql.connect(host=os.environ["MYSQL_HOST"], port=int(os.environ["MYSQL_PORT"]),
                    user=os.environ["MYSQL_USER"], password=os.environ["MYSQL_PASSWORD"],
                    database=os.environ["NEXAR_SQL_DB"] or None, charset="utf8mb4", autocommit=True)
with c.cursor() as cur:
    cur.execute(os.environ["NEXAR_SQL"])
    for linha in (cur.fetchall() or []):
        print(" | ".join("NULL" if v is None else str(v) for v in linha))
'@
    $saida = & $Python -c $codigo
    if ($LASTEXITCODE -ne 0) { throw "Falha no SQL: $sql" }
    return $saida
}

function Django([string]$banco, [string[]]$argumentos, [switch]$PodeFalhar) {
    $env:DB_NAME = $banco
    # No PowerShell 5.1, stderr de programa nativo com 2>&1 vira erro; com "Stop" o script pararia
    # em qualquer aviso do Django. Aqui o critério de falha é só o código de saída.
    $anterior = $ErrorActionPreference; $ErrorActionPreference = "Continue"
    & $Python manage.py @argumentos 2>&1 | ForEach-Object { "$_" } | Out-Host
    $codigo = $LASTEXITCODE
    $ErrorActionPreference = $anterior
    if (($codigo -ne 0) -and (-not $PodeFalhar)) { throw "manage.py $($argumentos -join ' ') falhou (banco $banco)." }
    return $codigo
}

function Existe([string]$banco) {
    $n = Sql "SELECT COUNT(*) FROM information_schema.SCHEMATA WHERE SCHEMA_NAME = '$banco'"
    return ([int]$n -gt 0)
}

function Titulo([string]$t) { Write-Host ""; Write-Host "=== $t ===" -ForegroundColor Cyan }

# ---------------------------------------------------------------- 1. versão
Titulo "1. Versão do servidor"
$versao = Sql "SELECT VERSION()"
Write-Host "MySQL $versao"
$num = [version](($versao -split "-")[0])
if ($num -lt [version]"8.0.13") { throw "MySQL $versao é antigo: o índice funcional da 0005 exige 8.0.13+." }

# ---------------------------------------------------------------- 2. bancos de teste livres
Titulo "2. Bancos de teste não podem existir"
foreach ($b in @($BancoZero, $BancoMigracao, $BancoScript, $BancoSuite)) {
    if (Existe $b) { throw "O banco '$b' já existe. Abortando SEM apagar nada. Apague-o manualmente se for mesmo de teste." }
    Write-Host "ok: $b não existe"
}

# ---------------------------------------------------------------- 3. do zero
Titulo "3. Instalação do zero em $BancoZero"
Sql "CREATE DATABASE $BancoZero CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci" | Out-Null
Django $BancoZero @("migrate") | Out-Null
Django $BancoZero @("showmigrations", "loja") | Out-Null
Django $BancoZero @("popular_loja") | Out-Null
Sql "SELECT (SELECT COUNT(*) FROM categorias), (SELECT COUNT(*) FROM produtos), (SELECT COUNT(*) FROM auth_user), (SELECT COUNT(*) FROM pedidos)" $BancoZero |
    ForEach-Object { Write-Host "categorias | produtos | usuarios | pedidos = $_" }
Sql "SHOW CREATE TABLE pedidos" $BancoZero
Sql "SHOW INDEX FROM auth_user WHERE Key_name = 'auth_user_email_ci_uniq'" $BancoZero
Sql @"
SELECT p.id, u.username, pr.nome, c.nome, p.quantidade, p.preco_unitario, p.preco_unitario * p.quantidade
FROM pedidos p JOIN auth_user u ON u.id = p.usuario_id JOIN produtos pr ON pr.id = p.produto_id
JOIN categorias c ON c.id = pr.categoria_id ORDER BY p.data DESC
"@ $BancoZero
Write-Host "-- CHECK: quantidade 0 deve falhar (erro 3819):"
try { Sql "INSERT INTO pedidos (tamanho, quantidade, data, usuario_id, produto_id, preco_unitario) SELECT 'M', 0, NOW(6), MIN(u.id), MIN(p.id), 1 FROM auth_user u, produtos p" $BancoZero; Write-Warning "NÃO falhou!" } catch { Write-Host "falhou como esperado" }
Write-Host "-- e-mail que difere só na caixa deve falhar; dois e-mails vazios devem passar:"
$ins = "INSERT INTO auth_user (password,is_superuser,username,first_name,last_name,email,is_staff,is_active,date_joined) VALUES "
Sql ($ins + "('!',0,'caixa1','','','Ana@Ex.com',0,1,NOW(6))") $BancoZero | Out-Null
try { Sql ($ins + "('!',0,'caixa2','','','ana@ex.COM',0,1,NOW(6))") $BancoZero; Write-Warning "NÃO falhou!" } catch { Write-Host "falhou como esperado (duplicado sem caixa)" }
Sql ($ins + "('!',0,'vazio1','','','',0,1,NOW(6)), ('!',0,'vazio2','','','',0,1,NOW(6))") $BancoZero | Out-Null
Write-Host "ok: dois e-mails vazios aceitos"
Write-Host "-- reverse da 0005 remove o índice:"
Django $BancoZero @("migrate", "loja", "0004") | Out-Null
Sql "SELECT COUNT(*) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = '$BancoZero' AND INDEX_NAME = 'auth_user_email_ci_uniq'" | ForEach-Object { Write-Host "índices restantes: $_" }
Django $BancoZero @("migrate") | Out-Null

# ---------------------------------------------------------------- 4. upgrade com dados
Titulo "4. Atualização com dados em $BancoMigracao (0003 -> 0004 -> 0005)"
Sql "CREATE DATABASE $BancoMigracao CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci" | Out-Null
foreach ($app in @("contenttypes", "auth", "admin", "sessions")) { Django $BancoMigracao @("migrate", $app) | Out-Null }
Django $BancoMigracao @("migrate", "loja", "0003") | Out-Null
$dados = @(
    "INSERT INTO categorias (id, nome) VALUES (1, 'Camisetas'), (2, 'Bonés')",
    "INSERT INTO produtos (id,nome,descricao,preco,estoque,imagem,imagem_2,modelo_3d,cor,categoria_id) VALUES (1,'Camiseta Box Logo','',149.90,10,'','','','#E8641E',1), (2,'Boné 6-Panel','',129.90,5,'','','','#F4F4F1',2)",
    ($ins.Replace("(password", "(id,password") + "(1,'!',0,'ana.souza','','','',0,1,NOW(6)), (2,'!',0,'bruno','','','',0,1,NOW(6))"),
    "INSERT INTO pedidos (id,tamanho,quantidade,data,usuario_id,produto_id) VALUES (1,'M',3,NOW(6),1,1), (2,'G',2,NOW(6),2,2), (3,'M',0,NOW(6),2,1)",
    "UPDATE produtos SET preco = 179.90 WHERE id = 1"
)
foreach ($s in $dados) { Sql $s $BancoMigracao | Out-Null }
Write-Host "-- 4a. pedido 3 tem quantidade 0: a 0004 deve parar ANTES de qualquer DDL"
$rc = Django $BancoMigracao @("migrate") -PodeFalhar
if ($rc -eq 0) { Write-Warning "migrate NÃO falhou!" }
Django $BancoMigracao @("showmigrations", "loja") | Out-Null
Sql "SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = '$BancoMigracao' AND TABLE_NAME = 'pedidos' AND COLUMN_NAME = 'preco_unitario'" |
    ForEach-Object { Write-Host "coluna preco_unitario existe? (esperado 0): $_" }
Write-Host "-- 4b. corrige manualmente e migra até a 0004"
Sql "UPDATE pedidos SET quantidade = 1 WHERE id = 3" $BancoMigracao | Out-Null
Django $BancoMigracao @("migrate", "loja", "0004") | Out-Null
Sql "SELECT p.id, p.preco_unitario, pr.preco, p.preco_unitario = pr.preco FROM pedidos p JOIN produtos pr ON pr.id = p.produto_id ORDER BY p.id" $BancoMigracao
Sql "SELECT IS_NULLABLE FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = '$BancoMigracao' AND TABLE_NAME = 'pedidos' AND COLUMN_NAME = 'preco_unitario'" |
    ForEach-Object { Write-Host "preco_unitario aceita NULL? (esperado NO): $_" }
Write-Host "-- 4c. e-mails repetidos (só a caixa muda): a 0005 deve parar"
Sql "UPDATE auth_user SET email = 'Dup@Teste.com' WHERE id = 1" $BancoMigracao | Out-Null
Sql "UPDATE auth_user SET email = 'dup@teste.com' WHERE id = 2" $BancoMigracao | Out-Null
$rc = Django $BancoMigracao @("migrate") -PodeFalhar
if ($rc -eq 0) { Write-Warning "migrate NÃO falhou!" }
Django $BancoMigracao @("showmigrations", "loja") | Out-Null
Write-Host "-- 4d. corrige e conclui"
Sql "UPDATE auth_user SET email = '' WHERE id = 2" $BancoMigracao | Out-Null
Django $BancoMigracao @("migrate") | Out-Null
Django $BancoMigracao @("showmigrations", "loja") | Out-Null

# ---------------------------------------------------------------- 5. suíte
Titulo "5. Suíte de testes (o Django cria e apaga $BancoSuite)"
Django $DbBaseTeste @("test", "loja", "--noinput") | Out-Null

# ---------------------------------------------------------------- 6. banco.sql
Titulo "6. docs/banco.sql em $BancoScript"
if (Existe $BancoScript) { throw "O banco '$BancoScript' já existe. Abortando sem apagar." }
if (-not (Test-Path $MysqlExe)) { throw "mysql.exe não encontrado em $MysqlExe (use -MysqlExe)." }
$env:MYSQL_PWD = $env:MYSQL_PASSWORD   # evita a senha na linha de comando
Get-Content ".\docs\banco.sql" -Raw -Encoding UTF8 |
    & $MysqlExe --default-character-set=utf8mb4 -h $env:MYSQL_HOST -P $env:MYSQL_PORT -u $env:MYSQL_USER --table
if ($LASTEXITCODE -ne 0) { throw "docs/banco.sql falhou." }
Remove-Item Env:MYSQL_PWD

Titulo "Concluído"
Write-Host "Bancos de teste que ficaram (apague manualmente se quiser): $BancoZero, $BancoMigracao, $BancoScript"
Write-Host "O banco 'nexar' não foi usado."
Remove-Item Env:MYSQL_PASSWORD, Env:DB_PASSWORD, Env:NEXAR_SQL, Env:NEXAR_SQL_DB -ErrorAction SilentlyContinue

-- =====================================================================
-- NEXAR - script do banco de dados (MySQL 8)
-- =====================================================================
-- ATENÇÃO:
-- * Arquivo DEMONSTRATIVO. NÃO substitui as migrations do Django e NÃO é um
--   backup completo do banco. No projeto real as tabelas são criadas por
--   "python manage.py migrate" e os dados por "python manage.py popular_loja".
-- * A tabela auth_user aqui é SIMPLIFICADA: no projeto ela é criada pelo app
--   django.contrib.auth, junto com auth_group, auth_permission, sessões etc.
-- * Executado em MySQL 8.0.46 em 17/11/2026 com o cliente mysql.exe (exit 0):
--   todas as instruções rodaram; os casos comentados no fim também foram
--   testados (FK = erro 1451, CHECK = erro 3819). Detalhes em
--   docs/validacao_banco.md. Está alinhado às migrations loja.0001 a loja.0005
--   (cor do produto, preco_unitario, CHECKs e e-mail único sem diferenciar
--   maiúsculas/minúsculas nem espaços).
-- * O índice funcional de e-mail exige MySQL 8.0.13 ou mais novo.
--
-- Este arquivo existe para a avaliação: mostra a estrutura (PK, FK, tipos)
-- e consultas de exemplo.
-- =====================================================================

-- Banco separado (nexar_script) de propósito: o banco "nexar" é o que o Django
-- usa (DB_NAME no .env). Rodar este script não apaga nem altera o banco da aplicação.
-- O script não apaga nenhum banco. Se nexar_script já existir, o CREATE abaixo
-- falha e nada é alterado; para recriar, apague nexar_script manualmente antes.
CREATE DATABASE nexar_script CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE nexar_script;

-- ---------------------------------------------------------------------
-- auth_user (versão simplificada, com as colunas reais do Django)
-- No projeto ela é criada pelo "migrate" (app django.contrib.auth),
-- junto com auth_group, auth_permission etc., que não são usadas aqui.
-- ---------------------------------------------------------------------
CREATE TABLE auth_user (
    id           INT          NOT NULL AUTO_INCREMENT,
    password     VARCHAR(128) NOT NULL,
    last_login   DATETIME(6)  NULL,
    is_superuser TINYINT(1)   NOT NULL,
    username     VARCHAR(150) NOT NULL,
    first_name   VARCHAR(150) NOT NULL,
    last_name    VARCHAR(150) NOT NULL,
    email        VARCHAR(254) NOT NULL,
    is_staff     TINYINT(1)   NOT NULL,
    is_active    TINYINT(1)   NOT NULL,
    date_joined  DATETIME(6)  NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY auth_user_username_uniq (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- E-mail único ignorando maiúsculas/minúsculas (migration loja.0005).
-- E-mail vazio vira NULL no índice, e NULLs não conflitam: contas sem e-mail continuam permitidas.
CREATE UNIQUE INDEX auth_user_email_ci_uniq ON auth_user ((NULLIF(LOWER(TRIM(email)), '')));

-- ---------------------------------------------------------------------
-- categorias (model Categoria)
-- ---------------------------------------------------------------------
CREATE TABLE categorias (
    id   BIGINT      NOT NULL AUTO_INCREMENT,
    nome VARCHAR(50) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY categorias_nome_uniq (nome)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- produtos (model Produto)
-- imagem / imagem_2 / modelo_3d guardam o CAMINHO do arquivo (ou um link https://)
-- ---------------------------------------------------------------------
CREATE TABLE produtos (
    id           BIGINT        NOT NULL AUTO_INCREMENT,
    nome         VARCHAR(100)  NOT NULL,
    descricao    LONGTEXT      NOT NULL,
    preco        DECIMAL(10,2) NOT NULL,
    estoque      INT UNSIGNED  NOT NULL,
    imagem       VARCHAR(100)  NOT NULL,
    imagem_2     VARCHAR(100)  NOT NULL,
    modelo_3d    VARCHAR(255)  NOT NULL,
    cor          VARCHAR(7)    NOT NULL DEFAULT '',  -- cor da peça 3D, ex.: #1F2F6B (migration 0002)
    categoria_id BIGINT        NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT produtos_estoque_check CHECK (estoque >= 0),
    CONSTRAINT produto_preco_nao_negativo CHECK (preco >= 0),
    -- sem ON DELETE: o MySQL usa RESTRICT (equivale ao on_delete=PROTECT do Django)
    CONSTRAINT produtos_categoria_id_b7177d63_fk_categorias_id
        FOREIGN KEY (categoria_id) REFERENCES categorias (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- pedidos (model Pedido)
-- preco_unitario = preço do produto NO MOMENTO DA COMPRA.
-- O total do pedido é preco_unitario * quantidade, então reajustar o preço
-- do produto depois não altera pedidos antigos.
-- ---------------------------------------------------------------------
CREATE TABLE pedidos (
    id             BIGINT        NOT NULL AUTO_INCREMENT,
    tamanho        VARCHAR(2)    NOT NULL,        -- P, M, G ou GG
    quantidade     INT UNSIGNED  NOT NULL DEFAULT 1,
    data           DATETIME(6)   NOT NULL,
    usuario_id     INT           NOT NULL,
    produto_id     BIGINT        NOT NULL,
    preco_unitario DECIMAL(10,2) NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT pedidos_quantidade_check CHECK (quantidade >= 0),
    CONSTRAINT pedido_quantidade_minima_1 CHECK (quantidade >= 1),
    CONSTRAINT pedido_preco_unitario_nao_negativo CHECK (preco_unitario >= 0),
    CONSTRAINT pedidos_usuario_id_2b8cebd6_fk_auth_user_id
        FOREIGN KEY (usuario_id) REFERENCES auth_user (id),
    CONSTRAINT pedidos_produto_id_e8bf22a9_fk_produtos_id
        FOREIGN KEY (produto_id) REFERENCES produtos (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- =====================================================================
-- INSERTs (mesmos dados de loja/mock_data.py / comando popular_loja)
-- =====================================================================

INSERT INTO categorias (id, nome) VALUES
    (1, 'Camisetas'),
    (2, 'Moletons'),
    (3, 'Calças'),
    (4, 'Bonés'),
    (5, 'Acessórios');

INSERT INTO produtos (id, nome, descricao, preco, estoque, imagem, imagem_2, modelo_3d, cor, categoria_id) VALUES
    (1, 'Camiseta Box Logo', 'Algodão 240g, modelagem boxy, logo NEXAR bordado no peito.', 149.90, 12,
        'produtos/camiseta-box-1.jpg', 'produtos/camiseta-box-2.jpg', '', '#E8641E', 1),
    (2, 'Camiseta Grid', 'Estampa grid em silk, gola canelada reforçada.', 159.90, 12,
        'produtos/camiseta-grid-1.jpg', 'produtos/camiseta-grid-2.jpg', '', '#F2F2EF', 1),
    (3, 'Moletom Heavy', 'Moletom 480g peluciado, ombro caído, punho largo.', 399.90, 12,
        'produtos/moletom-heavy-1.jpg', 'produtos/moletom-heavy-2.jpg', '', '#22306B', 2),
    (4, 'Moletom Drop 01', 'Edição limitada do primeiro drop. Bordado 3D nas costas.', 429.90, 3,
        'produtos/moletom-drop-1.jpg', 'produtos/moletom-drop-2.jpg', '', '#EDEDE9', 2),
    (5, 'Calça Cargo Tech', 'Ripstop com seis bolsos e barra ajustável.', 349.90, 12,
        'produtos/calca-cargo-1.jpg', 'produtos/calca-cargo-2.jpg', '', '#5B6542', 3),
    (6, 'Calça Wide Denim', 'Jeans 14oz, corte wide, lavagem escura.', 389.90, 12,
        'produtos/calca-wide-1.jpg', 'produtos/calca-wide-2.jpg', '', '#8FB3D9', 3),
    (7, 'Boné 6-Panel', 'Sarja de algodão, aba curva, fecho de metal.', 129.90, 12,
        'produtos/bone-1.jpg', 'produtos/bone-2.jpg', '', '#F4F4F1', 4),
    -- modelos 3D servidos pelo próprio site (static/modelos), como na migration 0003
    (8, 'Tênis Runner X', 'Cabedal em mesh e camurça, solado de borracha.', 699.90, 12,
        'produtos/tenis-1.jpg', 'produtos/tenis-2.jpg', '/static/modelos/tenis.glb', '', 5),
    (9, 'Óculos Nexar Shade', 'Armação acetato, lente com proteção UV400.', 259.90, 12,
        'produtos/oculos-1.jpg', 'produtos/oculos-2.jpg', '/static/modelos/oculos.glb', '', 5);

-- Clientes de exemplo. password = '!' é o marcador do Django para "senha
-- inutilizável": esses usuários não conseguem fazer login (nenhuma senha real aqui).
-- O administrador é criado com "python manage.py createsuperuser".
INSERT INTO auth_user (id, password, last_login, is_superuser, username, first_name, last_name,
                       email, is_staff, is_active, date_joined) VALUES
    (1, '!', NULL, 0, 'eva.costa', '', '', '', 0, 1, '2026-11-01 08:00:00'),
    (2, '!', NULL, 0, 'daniel',    '', '', '', 0, 1, '2026-11-01 08:00:00'),
    (3, '!', NULL, 0, 'carla.m',   '', '', '', 0, 1, '2026-11-01 08:00:00'),
    (4, '!', NULL, 0, 'bruno',     '', '', '', 0, 1, '2026-11-01 08:00:00'),
    (5, '!', NULL, 0, 'ana.souza', '', '', '', 0, 1, '2026-11-01 08:00:00');

-- preco_unitario = preço do produto no dia da compra
INSERT INTO pedidos (id, tamanho, quantidade, data, usuario_id, produto_id, preco_unitario) VALUES
    (1, 'G',  1, '2026-11-05 18:40:00', 1, 8, 699.90),  -- eva.costa  - Tênis Runner X
    (2, 'M',  2, '2026-11-04 09:15:00', 2, 7, 129.90),  -- daniel     - Boné 6-Panel
    (3, 'P',  1, '2026-11-03 21:02:00', 3, 5, 349.90),  -- carla.m    - Calça Cargo Tech
    (4, 'GG', 1, '2026-11-02 14:10:00', 4, 3, 399.90),  -- bruno      - Moletom Heavy
    (5, 'M',  3, '2026-11-01 11:30:00', 5, 1, 149.90);  -- ana.souza  - Camiseta Box Logo


-- =====================================================================
-- CONSULTAS DE EXEMPLO
-- =====================================================================

-- SELECT com LIKE: busca por nome (o que a busca da página /produtos/ faz)
SELECT id, nome, preco
FROM produtos
WHERE nome LIKE '%moletom%';

-- SELECT com JOIN: painel de pedidos (pedidos + cliente + produto + categoria)
-- O total usa o preço gravado no pedido, não o preço atual do produto.
SELECT p.id,
       p.data,
       u.username                       AS cliente,
       pr.nome                          AS produto,
       c.nome                           AS categoria,
       p.tamanho,
       p.quantidade,
       p.preco_unitario,
       p.preco_unitario * p.quantidade  AS total
FROM pedidos p
JOIN auth_user  u  ON u.id  = p.usuario_id
JOIN produtos   pr ON pr.id = p.produto_id
JOIN categorias c  ON c.id  = pr.categoria_id
ORDER BY p.data DESC;

-- UPDATE: reajuste de preço e baixa de estoque
UPDATE produtos SET preco = 179.90 WHERE id = 1;          -- Camiseta Box Logo: 149,90 -> 179,90
UPDATE produtos SET estoque = estoque - 1 WHERE id = 4;

-- O reajuste acima NÃO muda o pedido antigo da ana.souza:
-- preco_atual_do_produto = 179.90, mas preco_pago continua 149.90 e o total continua 449.70.
SELECT p.id,
       u.username,
       pr.preco                         AS preco_atual_do_produto,
       p.preco_unitario                 AS preco_pago,
       p.preco_unitario * p.quantidade  AS total
FROM pedidos p
JOIN auth_user u  ON u.id  = p.usuario_id
JOIN produtos  pr ON pr.id = p.produto_id
WHERE p.id = 5;

-- DELETE: apagar um produto que nunca foi pedido funciona...
DELETE FROM produtos WHERE id = 6;                         -- Calça Wide Denim (sem pedidos)

-- ...mas apagar um produto que tem pedido é barrado pela FK (erro 1451),
-- assim como o on_delete=PROTECT do Django. Descomente para testar:
-- DELETE FROM produtos WHERE id = 1;

-- A CHECK constraint também barra pedido com quantidade 0 (erro 3819). Descomente para testar:
-- INSERT INTO pedidos (tamanho, quantidade, data, usuario_id, produto_id, preco_unitario)
-- VALUES ('M', 0, NOW(6), 1, 1, 149.90);

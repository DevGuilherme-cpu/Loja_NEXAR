---
name: nexar-3d
description: Como funciona e como mexer no 3D da NEXAR (Three.js) — peças geradas, modelos .glb, cor, hero, visualizador, miniaturas e desempenho. Usar ao adicionar produto com modelo 3D, criar efeito 3D novo ou investigar 3D lento/quebrado.
---

# 3D da NEXAR

Three.js 0.160 servido de `static/vendor/three/` (import map em `templates/base.html`).
Nada de CDN: a apresentação tem que funcionar sem internet.

## Arquivos

| Arquivo | Papel |
|---|---|
| `static/js/pecas.js` | "fábrica": `criarModelo()`, `criarPeca()`, `pintar()`, `encaixar()`, `criarRenderer()`, `criarCena()` |
| `static/js/hero.js` | hero da home: 4 destaques caem e inflam; layouts `largo/medio/estreito` por proporção |
| `static/js/viewer.js` | visualizador (produto, login, cadastro, painel): girar, zoom, foto↔3D, tamanho, comprar, cor |
| `static/js/thumbs.js` | produto **sem foto**: desenha frente e costas em 3D e usa como foto do card |

## Como uma peça vira 3D

`criarModelo({categoria, modelo, cor, media, seed})` lê os `data-*` do HTML:

1. Se `modelo` (`.glb`) existe → carrega o arquivo (`/static/...`, `https://...` ou nome em `media/`).
2. Se não, gera a peça "inflada" pelo nome da categoria (`tipoDaCategoria`): camiseta, moletom,
   calça, boné; o resto vira forma abstrata. A cor vem do campo **`Produto.cor`** (`#RRGGBB`).
3. Só peça gerada pode ser repintada (`pintar()`); `.glb` usa as texturas dele.

Para adicionar um tipo novo de peça: contorno 2D em `pecas.js` (metade direita, a esquerda é espelhada),
`inflar(contorno(...), cor)` e uma regra em `tipoDaCategoria`.

## Adicionar produto com modelo .glb

- Fontes gratuitas: Sketchfab (filtro *Downloadable*, baixar **glTF Binary .glb**), CLO-SET Connect, Fab (*Free*).
- Conferir licença; CC BY exige crédito no rodapé (`templates/base.html`, `.rodape-creditos`).
- Tamanho alvo **≤ 3 MB** (o tênis atual tem 7.8 MB e demora). Para comprimir, sugerir à pessoa:
  `npx @gltf-transform/cli optimize entrada.glb saida.glb --compress meshopt` (não instalar sem pedir).
- Arquivo fixo do projeto → `static/modelos/` e `modelo_3d="/static/modelos/nome.glb"`.
  Envio pelo painel → vai para `media/modelos/` (não funciona na Vercel: não guarda arquivos).

## Regras de desempenho

- Um `WebGLRenderer` por canvas visível; miniaturas usam **um** canvas escondido e depois
  `renderer.dispose(); renderer.forceContextLoss();` (o navegador aceita ~16 contextos).
- `setPixelRatio` no máximo 2 (hero: 1.5). Parar o loop quando o canvas sai da tela (`IntersectionObserver`).
- `three` só é baixado onde é usado (import dinâmico no `thumbs.js`).
- Canvas que dá zoom com a roda precisa de `data-lenis-prevent`; no celular `touch-action: pan-y`.

## Testar

- `python manage.py runserver` e abrir `/` (queda das peças), `/produto/3/` (foto vira 3D, tamanho GG
  aumenta a peça), `/produto/8/` (tênis .glb) e o painel (cor pinta a prévia).
- Console sem erros; Ctrl+F5 depois de editar JS.
- Celular (375 px): hero em 2x2 acima do título, arrastar na vertical rola a página.

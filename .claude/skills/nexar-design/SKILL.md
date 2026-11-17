---
name: nexar-design
description: Sistema visual da NEXAR ("estúdio de render"). Usar antes de criar ou mudar qualquer tela, CSS, texto do site ou animação — paleta, fonte, componentes, regras de movimento e acessibilidade.
---

# NEXAR — sistema de design "estúdio de render"

A identidade vem do próprio diferencial da loja (ver a peça em 3D): fundo branco como a Palace,
as peças sobre um **palco cinza** de software 3D, e as **cores dos eixos X/Y/Z** só nas interações.

## Tokens (já existem em `static/css/style.css`, use as variáveis)

| Token | Valor | Uso |
|---|---|---|
| `--papel` | #FFFFFF | fundo da página |
| `--palco` / `--palco-escuro` | #DCDFE4 / #C9CDD4 | fundo atrás de 3D, fotos, campos, chips |
| `--tinta` | #000000 | texto, botão principal |
| `--nevoa` | #575C64 | texto secundário (contraste 6.6:1) |
| `--eixo-x` | #C8233A | alerta, excluir, "Últimas peças" |
| `--eixo-y` | #1D7A43 | confirmado / sucesso |
| `--eixo-z` | #2747D6 | foco, selecionado, hover de interação |
| `--r` / `--r-pequeno` | 14px / 10px | único sistema de cantos |

- Fonte única: **Archivo** variável. Títulos: classe de exibição (`font-stretch:125%`, peso 850,
  `letter-spacing:-.035em`), em **caixa normal**. Corpo: largura 100%, peso 400.
- Escala 1.25: `--t-1 .8rem`, `--t0 1rem`, `--t1 1.25rem`, `--t2 1.563rem`, `--t3`, `--t4`.

## Proibido (são os "tells" de site genérico)

- `text-transform: uppercase` em rótulos e botões (só o logo NEXAR é maiúsculo).
- Setas "→" / "←" em botões e links; separadores "A · B · C" ou "A — B".
- Rótulo pequeno acima de todo título; numeração 01/02/03 sem ser sequência real.
- Cor nova fora dos tokens; sombra cinza genérica embaixo de cards; gradiente decorativo.
- Fade-up ao rolar em toda seção, cortina entre páginas, animação que roda sozinha fora do hero.

## Regras de movimento

1. **Só o hero anima sozinho** (as peças em destaque caem e inflam — `static/js/hero.js`).
2. Todo o resto **responde a uma ação**: hover, clique, escolha de tamanho/cor, troca de página.
3. Troca de página = View Transitions do navegador (`@view-transition` no CSS + `view-transition-name`
   igual no card e no palco do produto). Não reintroduzir cortina.
4. Easing padrão `cubic-bezier(.2,.8,.2,1)` (`--ease`); durações 0.25–0.7 s; elástico só em resposta.
5. Sempre respeitar `prefers-reduced-motion` (CSS já zera transições; JS checa `anima`).
6. Efeitos de mouse só com `matchMedia('(hover: hover) and (pointer: fine)')`.

## Checklist de qualquer mudança visual

- [ ] Usa só tokens; nenhum `#hex` novo solto no CSS.
- [ ] Foco visível (outline azul `--eixo-z`) em tudo que é clicável.
- [ ] Funciona em 375 px de largura sem rolagem horizontal
      (`document.documentElement.scrollWidth > innerWidth` deve ser `false`).
- [ ] Texto ≥ 4.5:1 de contraste; botões ≥ 44 px de altura no celular.
- [ ] Canvas 3D tem `role="img"`, `aria-label` e `data-lenis-prevent`.
- [ ] Imagem decorativa `alt=""`; imagem com conteúdo tem `alt` descritivo.
- [ ] Copy em português, voz ativa, botão diz o que acontece ("Comprar", "Salvar alterações").
- [ ] Conferido no navegador (desktop e celular) e console sem erros.
  Dica: depois de editar JS/CSS, recarregue com Ctrl+F5 (o navegador guarda os arquivos antigos).

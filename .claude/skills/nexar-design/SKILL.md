---
name: nexar-design
description: Sistema visual da NEXAR (estilo "drop": preto, branco e neon, com as peças em 3D sobre o palco cinza). Usar antes de criar ou mudar qualquer tela, CSS, texto do site ou animação — paleta, fonte, componentes, regras de movimento e acessibilidade.
---

# NEXAR — sistema de design "drop"

A loja segue a referência de streetwear (loja "PULSE"): blocos **pretos**, fundo **branco**,
destaque em **verde-limão neon**, títulos **estreitos e em maiúsculas**. O diferencial continua o 3D:
as peças aparecem sobre o **palco cinza** de software 3D.

- **Loja** (`templates/base.html`, `body.loja`): estilo drop completo. As regras ficam no fim de
  `static/css/style.css`, no bloco "Loja no estilo drop", todas com o prefixo `.loja`.
- **Painel** (`templates/painel/base_painel.html`): continua sóbrio (lateral preta, cartões cinza).
  Não aplicar o estilo drop lá.

## Tokens (em `static/css/style.css`, use as variáveis)

| Token | Valor | Uso |
|---|---|---|
| `--papel` | #FFFFFF | fundo da página |
| `--tinta` | #000000 | texto, faixas e blocos pretos, botão principal em fundo claro |
| `--neon` | #D4FF3D | destaque: selos, botão em fundo preto, números, item ativo. **Só sobre preto ou com texto preto** |
| `--palco` / `--palco-escuro` | #DCDFE4 / #C9CDD4 | fundo atrás do 3D, campos, chips; texto secundário sobre preto |
| `--nevoa` | #575C64 | texto secundário sobre branco (contraste 6.6:1) |
| `--eixo-x` | #C8233A | alerta, excluir, erro |
| `--eixo-y` | #1D7A43 | confirmado / sucesso |
| `--eixo-z` | #2747D6 | **foco do teclado** (outline) |
| `--r` / `--r-pequeno` | 14px / 10px | cantos |

- Fonte única: **Archivo** variável.
  - Títulos de exibição: `font-stretch: 62%`, peso 900, `text-transform: uppercase`, `line-height: .88`
    (classes `.drop-titulo`, `.secao-titulo` na loja, `.hero h1`).
  - Rótulos curtos (menu, selos, botões pequenos): maiúsculas, peso 700–800, `letter-spacing: .05em`.
  - Texto corrido: caixa normal, peso 400.
- Componentes prontos: `.drop-selo` (etiqueta neon inclinada), `.btn` (preto; hover neon),
  `.btn-neon` (neon; usar sobre preto), `.drop-topo` (faixa preta com título), `.bloco` (caixa com
  borda preta e número neon), `.colecao` (card de categoria com foto), `.contagem`.

## Proibido

- Neon como texto sobre branco (some) ou como fundo de área grande sem texto preto.
- Setas "→" / "←" em botões e links (regra do AGENTS.md).
- Cor nova fora dos tokens; sombra cinza genérica embaixo de cards.
- Escurecer foto com gradiente só por enfeite (só para o texto em cima ficar legível, como em `.colecao`).
- Urgência falsa: contagem regressiva sempre aponta para uma data fixa (`views.FIM_DROP`) e o
  "restam X" vem do estoque de verdade.

## Regras de movimento

1. **O hero anima sozinho** (peças caem e inflam, selo girando). Mapas e rastreio também se mexem
   sozinhos porque mostram algo acontecendo (entregas).
2. O resto **responde a uma ação**: hover, clique, escolha de tamanho/cor, troca de página, ou
   **entrar na tela ao rolar** (uma vez só). O que já aparece ao abrir a página não anima (exceto títulos).
   Prontos em `main.js`: títulos `.secao-titulo`/`.drop-titulo` sobem letra a letra; cards, coleções e
   looks entram do desfoque; `.btn-neon` tem ímã; `.card-img` tem brilho que segue o mouse.
   No CSS: `.contagem b.rola` (número que muda), `.com-erro` treme, `.sucesso-check` se desenha.
3. Troca de página = View Transitions do navegador (a página nova sobe; o `.topo` fica parado e o
   card vira o palco do produto pelo `view-transition-name: produto-<id>`). Não reintroduzir cortina.
4. Tempos e curvas seguem as receitas do **transitions.dev**: `--ease` = `cubic-bezier(.22,1,.36,1)`,
   `--dur-rapida` 150 ms (fechar/sumir), `--dur-media` 250 ms (abrir modal/menu, hover), `--dur-lenta`
   500 ms (texto e blocos entrando: sobe 12–16 px, blur de 3 px, 40 ms entre um e outro). No GSAP,
   o equivalente de `--ease` é `power4.out`. Modal abre com `scale .96 → 1` + opacidade.
   Animação de compra: `templates/_animacao_pedido.html` + `js/animacao-pedido.js` (peça → caixa →
   etiqueta → caminhão, ~5,7 s). Só toca uma vez, logo depois da compra (`views.SESSAO_ANIMAR`),
   tem "Pular animação"/Esc e some com "reduzir movimento".
5. Sempre respeitar `prefers-reduced-motion` (o CSS zera transições e para as animações infinitas;
   o JS checa `anima`). O nível de qualidade (`html[data-qualidade]`) desliga efeitos em aparelho fraco.
6. Efeitos de mouse só com `matchMedia('(hover: hover) and (pointer: fine)')`.

## Checklist de qualquer mudança visual

- [ ] Usa só tokens; nenhum `#hex` novo solto no CSS.
- [ ] Foco visível (outline azul `--eixo-z`) em tudo que é clicável.
- [ ] Funciona em 375 px de largura sem rolagem horizontal.
- [ ] Texto ≥ 4.5:1 de contraste; botões ≥ 44 px de altura no celular.
- [ ] Canvas 3D tem `role="img"`, `aria-label` e `data-lenis-prevent`.
- [ ] Imagem decorativa `alt=""`; imagem com conteúdo tem `alt` descritivo.
- [ ] Copy em português, voz ativa, botão diz o que acontece ("Comprar", "Confirmar pedido").
- [ ] Menu de acessibilidade continua funcionando (fonte maior, inverter cores, destacar links).
- [ ] Conferido no navegador (desktop e celular) e console sem erros.
  Dica: depois de editar JS/CSS, recarregue com Ctrl+F5 (o navegador guarda os arquivos antigos).

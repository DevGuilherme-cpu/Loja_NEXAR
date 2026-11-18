// Visão geral do painel: gráfico de vendas por dia (SVG) e o assistente.

const anima = !matchMedia('(prefers-reduced-motion: reduce)').matches;
const SVG = 'http://www.w3.org/2000/svg';

function el(nome, attrs, pai) {
  const n = document.createElementNS(SVG, nome);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  if (pai) pai.appendChild(n);
  return n;
}

function reais(v) {
  return v.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

// ---------- vendas por dia ----------
const caixa = document.getElementById('grafico-dias');
const dados = JSON.parse(document.getElementById('dados-dias')?.textContent || '[]');

function desenhar() {
  if (!caixa || !dados.length) return;
  caixa.replaceChildren();
  const L = caixa.clientWidth, A = 220;
  const m = { topo: 12, dir: 8, base: 26, esq: 64 };
  const w = L - m.esq - m.dir, h = A - m.topo - m.base;
  const maior = Math.max(...dados.map(d => d.valor), 1);
  // teto "redondo" para as linhas de grade
  const passo = 10 ** Math.floor(Math.log10(maior));
  const teto = Math.ceil(maior / passo) * passo;

  const svg = el('svg', { viewBox: `0 0 ${L} ${A}`, width: L, height: A, 'aria-hidden': 'true' }, caixa);

  for (let i = 0; i <= 2; i++) {
    const v = teto * i / 2, y = m.topo + h - h * v / teto;
    el('line', { x1: m.esq, x2: L - m.dir, y1: y, y2: y, class: i ? 'grade' : 'eixo' }, svg);
    el('text', { x: m.esq - 8, y: y + 4, 'text-anchor': 'end', class: 'rotulo' }, svg).textContent =
      reais(v).replace(',00', '');
  }

  const col = w / dados.length;
  const larg = Math.max(2, Math.min(28, col * 0.62));
  const cada = Math.ceil(dados.length / 8);  // no máximo ~8 datas no eixo

  const dica = document.createElement('div');
  dica.className = 'grafico-dica';
  dica.hidden = true;
  caixa.appendChild(dica);

  dados.forEach((d, i) => {
    const x = m.esq + col * i + (col - larg) / 2;
    const alt = h * d.valor / teto;
    const g = el('g', { class: 'coluna' }, svg);
    if (d.valor) {
      // barra com cantos de 4px só em cima, apoiada na linha de base
      const r = Math.min(4, larg / 2, alt), y = m.topo + h - alt, b = m.topo + h;
      el('path', {
        class: 'barra',
        d: `M${x},${b} V${y + r} Q${x},${y} ${x + r},${y} H${x + larg - r} Q${x + larg},${y} ${x + larg},${y + r} V${b} Z`,
        style: anima ? `animation-delay:${i * 12}ms` : '',
      }, g);
    }
    // área de toque maior que a barra
    el('rect', { x: m.esq + col * i, y: m.topo, width: col, height: h, class: 'alvo' }, g);
    const ultimo = dados.length - 1;
    // a data do último dia sempre aparece; a anterior some se ficar colada nela
    if (i === ultimo || (i % cada === 0 && ultimo - i >= cada * 0.6)) {
      el('text', { x: x + larg / 2, y: A - 8, 'text-anchor': 'middle', class: 'rotulo' }, svg).textContent = d.data;
    }

    g.addEventListener('pointerenter', () => {
      dica.innerHTML = '';
      const t = document.createElement('b');
      t.textContent = d.data;
      dica.append(t, ` ${d.texto}`, document.createElement('br'),
        `${d.pedidos} pedido${d.pedidos === 1 ? '' : 's'}`);
      dica.hidden = false;
      const px = Math.min(Math.max(x + larg / 2, 70), L - 70);
      dica.style.left = `${px}px`;
      dica.style.top = `${Math.max(m.topo + h - alt - 8, 40)}px`;
    });
    g.addEventListener('pointerleave', () => { dica.hidden = true; });
  });
}

desenhar();
let espera;
addEventListener('resize', () => {
  clearTimeout(espera);
  espera = setTimeout(desenhar, 150);
});

// ---------- assistente ----------
const form = document.getElementById('assistente-form');
const conversa = document.getElementById('conversa');
const campo = document.getElementById('pergunta');

function mensagem(texto, quem) {
  const li = document.createElement('li');
  li.className = `msg ${quem}`;
  li.textContent = texto;
  conversa.appendChild(li);
  conversa.scrollTop = conversa.scrollHeight;
  return li;
}

form?.addEventListener('submit', async (e) => {
  e.preventDefault();
  const pergunta = campo.value.trim();
  if (!pergunta) return;
  const dadosForm = new FormData(form);
  mensagem(pergunta, 'eu');
  campo.value = '';
  const botao = form.querySelector('button');
  botao.disabled = true;
  const resposta = mensagem('Consultando os dados...', 'bot carregando');
  try {
    const r = await fetch(form.action, {
      method: 'POST',
      body: dadosForm,
      headers: { 'X-Requested-With': 'fetch' },
    });
    if (!r.ok) throw new Error(r.status);
    resposta.textContent = (await r.json()).resposta;
  } catch {
    resposta.textContent = 'Não consegui consultar agora. Recarregue a página e tente de novo.';
  }
  resposta.classList.remove('carregando');
  conversa.scrollTop = conversa.scrollHeight;
  botao.disabled = false;
  campo.focus();
});

document.querySelectorAll('.sugestoes .chip').forEach((chip) => {
  chip.addEventListener('click', () => {
    campo.value = chip.dataset.pergunta;
    form.requestSubmit();
  });
});

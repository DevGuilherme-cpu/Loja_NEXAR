// Mapa de entregas (simulação): veículos saem do CD em São Paulo e seguem até a capital do pedido.

const caixa = document.getElementById('mapa');
const entregas = JSON.parse(document.getElementById('dados-entregas')?.textContent || '[]');
const cd = JSON.parse(document.getElementById('dados-cd')?.textContent || 'null');
const anima = !matchMedia('(prefers-reduced-motion: reduce)').matches;
const SVG = 'http://www.w3.org/2000/svg';

// contorno simplificado do Brasil (longitude, latitude)
const BRASIL = [
  [-51.6, 4.2], [-51.0, 3.4], [-50.6, 2.3], [-50.0, 1.6], [-49.9, 0.9], [-50.3, 0.2], [-49.6, -0.1],
  [-48.4, -0.3], [-47.9, -0.6], [-46.9, -0.9], [-45.7, -1.3], [-44.8, -1.6], [-44.3, -2.5], [-43.5, -2.4],
  [-42.3, -2.8], [-41.3, -2.9], [-40.0, -2.8], [-38.5, -3.7], [-37.3, -4.6], [-36.3, -5.0], [-35.4, -5.2],
  [-35.0, -6.2], [-34.8, -7.2], [-34.9, -8.1], [-35.3, -9.0], [-35.8, -9.8], [-36.5, -10.5], [-37.1, -11.1],
  [-37.8, -12.0], [-38.5, -13.0], [-39.0, -14.0], [-39.0, -15.5], [-39.2, -17.3], [-39.7, -18.5],
  [-39.8, -19.6], [-40.3, -20.4], [-40.9, -21.3], [-41.0, -22.0], [-42.0, -22.9], [-43.2, -23.0],
  [-44.4, -23.1], [-45.4, -23.8], [-46.4, -24.0], [-47.5, -24.8], [-48.4, -25.6], [-48.6, -26.6],
  [-48.5, -27.6], [-48.8, -28.6], [-49.7, -29.4], [-50.4, -30.5], [-51.2, -31.6], [-52.2, -32.3],
  [-52.8, -33.0], [-53.4, -33.7], [-53.5, -33.1], [-53.2, -32.6], [-53.8, -32.0], [-54.6, -31.5],
  [-55.6, -30.9], [-56.1, -30.9], [-57.6, -30.2], [-57.0, -29.6], [-56.0, -28.6], [-55.6, -28.1],
  [-54.7, -27.5], [-53.8, -27.1], [-53.7, -26.3], [-54.6, -25.6], [-54.3, -24.1], [-55.4, -23.9],
  [-55.7, -22.6], [-57.8, -22.1], [-58.1, -20.1], [-57.6, -18.2], [-58.4, -16.3], [-60.2, -16.3],
  [-60.2, -15.1], [-60.5, -13.8], [-61.9, -13.5], [-63.0, -12.8], [-64.4, -12.4], [-65.3, -11.4],
  [-65.4, -10.0], [-66.6, -9.9], [-68.0, -10.7], [-69.6, -11.0], [-70.6, -11.0], [-70.6, -9.6],
  [-72.2, -10.0], [-72.9, -9.3], [-74.0, -7.5], [-73.7, -6.7], [-73.0, -5.2], [-71.8, -4.4],
  [-70.0, -4.3], [-69.4, -1.1], [-69.6, -0.5], [-70.0, 0.6], [-69.3, 1.0], [-67.1, 1.8], [-66.8, 1.2],
  [-65.5, 0.8], [-64.2, 1.5], [-63.4, 2.2], [-64.0, 2.6], [-64.8, 4.2], [-63.0, 3.9], [-62.7, 4.0],
  [-61.3, 4.4], [-60.7, 5.2], [-60.0, 5.0], [-59.7, 4.4], [-59.9, 2.7], [-59.7, 1.8], [-58.9, 1.3],
  [-57.5, 1.7], [-56.5, 1.9], [-55.9, 2.5], [-55.0, 2.5], [-54.0, 2.3], [-52.9, 2.2], [-52.3, 3.2],
];

const xy = ([lon, lat]) => [(lon + 74.5) * 10, (5.8 - lat) * 10];

function el(nome, attrs, pai) {
  const n = document.createElementNS(SVG, nome);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  pai?.appendChild(n);
  return n;
}

// distância em linha reta (km), para estimar o tempo de viagem
function km(a, b) {
  const r = Math.PI / 180;
  const h = Math.sin((b.lat - a.lat) * r / 2) ** 2 +
    Math.cos(a.lat * r) * Math.cos(b.lat * r) * Math.sin((b.lon - a.lon) * r / 2) ** 2;
  return 12742 * Math.asin(Math.sqrt(h));
}

if (caixa && cd && entregas.length) {
  const svg = el('svg', { viewBox: '0 0 400 400', 'aria-hidden': 'true' }, caixa);
  el('path', { d: 'M' + BRASIL.map(p => xy(p).join(',')).join('L') + 'Z', class: 'mapa-pais' }, svg);

  const camRotas = el('g', {}, svg);
  const camPontos = el('g', {}, svg);
  const camVeiculos = el('g', {}, svg);

  const [cx, cy] = xy([cd.lon, cd.lat]);
  el('circle', { cx, cy, r: 9, class: 'mapa-cd-halo' }, camPontos);
  el('circle', { cx, cy, r: 5, class: 'mapa-cd' }, camPontos);
  el('text', { x: cx + 9, y: cy + 14, class: 'mapa-rotulo' }, camPontos).textContent = 'CD ' + cd.cidade;

  const lista = document.getElementById('entregas-lista');
  const contas = Object.fromEntries([...document.querySelectorAll('[data-conta]')].map(n => [n.dataset.conta, n]));

  const rotas = entregas.map((e, i) => {
    const [dx, dy] = xy([e.lon, e.lat]);
    // curva: ponto de controle deslocado para o lado do trajeto
    const mx = (cx + dx) / 2, my = (cy + dy) / 2;
    const nx = -(dy - cy), ny = dx - cx, lado = i % 2 ? 0.22 : -0.22;
    const caminho = el('path', { d: `M${cx},${cy} Q${mx + nx * lado},${my + ny * lado} ${dx},${dy}`, class: 'mapa-rota' }, camRotas);
    const destino = el('circle', { cx: dx, cy: dy, r: 3.5, class: 'mapa-destino' }, camPontos);
    const veiculo = el('g', { class: 'mapa-veiculo', tabindex: '-1' }, camVeiculos);
    // van vista de cima: carroceria e cabine
    el('rect', { x: -7, y: -4, width: 10, height: 8, rx: 2, class: 'mapa-carroceria' }, veiculo);
    el('rect', { x: 3, y: -3.5, width: 5, height: 7, rx: 2, class: 'mapa-cabine' }, veiculo);
    const distancia = km(cd, e);
    const horas = distancia / 70 + 1;  // 70 km/h e 1 h de separação no CD
    return {
      ...e, caminho, destino, veiculo, horas,
      comprimento: caminho.getTotalLength(),
      ciclo: 26 + distancia / 90,       // segundos de animação por viagem
      fase: (e.id * 0.618) % 1,         // cada veículo começa num ponto diferente
      item: lista.querySelector(`[data-id="${e.id}"]`),
    };
  });

  let selecionada = null;
  function selecionar(r) {
    selecionada = selecionada === r ? null : r;
    rotas.forEach(x => {
      const ativo = x === selecionada;
      x.caminho.classList.toggle('ativa', ativo);
      x.veiculo.classList.toggle('ativo', ativo);
      x.destino.classList.toggle('ativo', ativo);
      x.item.setAttribute('aria-pressed', String(ativo));
    });
    // o selecionado fica por cima dos outros
    if (selecionada) camVeiculos.appendChild(selecionada.veiculo);
  }
  rotas.forEach(r => {
    r.item.addEventListener('click', () => selecionar(r));
    r.veiculo.addEventListener('click', () => {
      selecionar(r);
      r.item.scrollIntoView({ block: 'nearest', behavior: anima ? 'smooth' : 'auto' });
    });
  });

  // progresso de 0 a 1.25: até 0.1 separando, até 1 na estrada, depois entregue (parado no destino)
  const progresso = (r, t) => ((t / r.ciclo + r.fase) % 1.25);

  function tempo(h) {
    return h < 1 ? `~${Math.max(5, Math.round(h * 60 / 5) * 5)} min` : `~${Math.round(h)} h`;
  }

  let ultimoTexto = -Infinity;
  function quadro(agora) {
    const t = anima ? agora / 1000 : 0;
    const total = { rota: 0, separando: 0, entregue: 0 };
    const textos = agora - ultimoTexto > 500;
    for (const r of rotas) {
      const p = progresso(r, t);
      const naRua = Math.min(Math.max((p - 0.1) / 0.9, 0), 1);
      const a = r.caminho.getPointAtLength(naRua * r.comprimento);
      const b = r.caminho.getPointAtLength(Math.min(naRua * r.comprimento + 1, r.comprimento));
      const ang = Math.atan2(b.y - a.y, b.x - a.x) * 180 / Math.PI;
      r.veiculo.setAttribute('transform', `translate(${a.x},${a.y}) rotate(${ang})`);

      const estado = p < 0.1 ? 'separando' : p < 1 ? 'rota' : 'entregue';
      total[estado]++;
      r.veiculo.classList.toggle('parado', estado !== 'rota');
      r.destino.classList.toggle('chegou', estado === 'entregue');
      if (textos) {
        r.item.dataset.estado = estado;
        r.item.querySelector('.entrega-trilho span').style.width = `${Math.round(naRua * 100)}%`;
        r.item.querySelector('.entrega-status').textContent =
          estado === 'separando' ? 'Separando no centro de distribuição' :
          estado === 'rota' ? `A caminho, chega em ${tempo((1 - naRua) * r.horas)}` : 'Entregue';
      }
    }
    if (textos) {
      ultimoTexto = agora;
      for (const k in contas) contas[k].textContent = total[k];
    }
    if (anima) requestAnimationFrame(quadro);
  }
  requestAnimationFrame(quadro);
}

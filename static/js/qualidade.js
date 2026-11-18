// Qualidade adaptativa: escolhe o nível do 3D e das animações pelo aparelho, antes de tudo carregar.
// alto = computador bom, medio = celular ou máquina comum, baixo = aparelho fraco ou economia de dados.
// Para testar: ?qualidade=baixo na URL (fica guardado neste navegador); ?qualidade=auto volta a detectar.
(() => {
  const nav = navigator;
  const memoria = nav.deviceMemory || 8;          // GB (Chrome/Edge; os outros não informam)
  const nucleos = nav.hardwareConcurrency || 8;
  const rede = nav.connection || {};
  const toque = matchMedia('(pointer: coarse)').matches;

  let nivel = 'alto';
  if (rede.saveData || /(^|-)2g$/.test(rede.effectiveType || '') || memoria <= 2 || nucleos <= 2) nivel = 'baixo';
  else if (toque || memoria <= 4 || nucleos <= 4) nivel = 'medio';

  try {
    const pedido = new URLSearchParams(location.search).get('qualidade');
    if (['alto', 'medio', 'baixo'].includes(pedido)) localStorage.setItem('nexar-qualidade', pedido);
    if (pedido === 'auto') localStorage.removeItem('nexar-qualidade');
    nivel = localStorage.getItem('nexar-qualidade') || nivel;
  } catch { /* navegação privada: fica o nível detectado */ }

  document.documentElement.dataset.qualidade = nivel;
})();

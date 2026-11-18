// Peças 3D: geradas por código ou carregadas de um .glb
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

// cores padrão
export const CORES = ['#22306b', '#e8641e', '#5b6542', '#8fb3d9', '#c8233a', '#ededE9'];

// metade direita do contorno (a esquerda é espelhada)
const CORPO_CAMISETA = [[0.35, 1], [0.82, 0.86], [0.76, 0.3], [0.75, -1.1]];
const CORPO_MOLETOM = [[0.38, 1], [0.88, 0.84], [0.8, 0.12], [0.8, -1.1]];
const CALCA = [[0.7, 1.1], [0.88, -1.3], [0.18, -1.3], [0, 0.15]];
// manga direita (a esquerda é espelhada); a ponta de dentro entra no corpo para esconder a costura
const MANGA_CAMISETA = [[0.6, 0.97], [0.95, 0.82], [1.4, 0.3], [1.05, 0.05], [0.66, 0.36]];
const MANGA_MOLETOM = [[0.62, 0.98], [1, 0.82], [1.75, -0.55], [1.38, -0.78], [0.72, 0.2]];

const forma = pontos => new THREE.Shape(pontos.map(([x, y]) => new THREE.Vector2(x, y)));
const espelhar = pontos => pontos.map(([x, y]) => [-x, y]).reverse();

// gola < 0 desce, gola > 0 vira capuz
function contorno(meia, gola = null) {
  const s = new THREE.Shape();
  const [x0, y0] = meia[0];
  s.moveTo(-x0, y0);
  if (gola === null) s.lineTo(x0, y0);
  else s.quadraticCurveTo(0, y0 + gola, x0, y0);
  meia.slice(1).forEach(([x, y]) => s.lineTo(x, y));
  const esquerda = meia.filter(([x]) => x !== 0).map(([x, y]) => [-x, y]).reverse();
  esquerda.slice(0, -1).forEach(([x, y]) => s.lineTo(x, y));
  return s;
}

function tecido(cor) {
  return new THREE.MeshPhysicalMaterial({
    color: cor, roughness: 0.6, side: THREE.DoubleSide,
    sheen: 1, sheenRoughness: 0.5, sheenColor: new THREE.Color(cor).lerp(new THREE.Color('#ffffff'), 0.5),
  });
}

// extrusão com chanfro = efeito inflado
function inflar(shape, cor, profundidade = 0.25, chanfro = 0.22) {
  const g = new THREE.ExtrudeGeometry(shape, {
    depth: profundidade, curveSegments: 32,
    bevelEnabled: true, bevelThickness: chanfro, bevelSize: chanfro * 0.65, bevelSegments: 10,
  });
  g.center();
  return new THREE.Mesh(g, tecido(cor));
}

// parte de uma peça personalizável: centralizada só no eixo z, para as partes se encaixarem
function inflarParte(shape, cor, profundidade, chanfro) {
  const g = new THREE.ExtrudeGeometry(shape, {
    depth: profundidade, curveSegments: 32,
    bevelEnabled: true, bevelThickness: chanfro, bevelSize: chanfro * 0.65, bevelSegments: 10,
  });
  g.translate(0, 0, -profundidade / 2);
  return new THREE.Mesh(g, tecido(cor));
}

// texto desenhado num canvas e colado na frente da peça
function estampa(y, z) {
  const canvas = document.createElement('canvas');
  canvas.width = 512;
  canvas.height = 256;
  const textura = new THREE.CanvasTexture(canvas);
  textura.colorSpace = THREE.SRGBColorSpace;
  const m = new THREE.Mesh(new THREE.PlaneGeometry(1, 0.5),
    new THREE.MeshBasicMaterial({ map: textura, transparent: true, depthWrite: false }));
  m.position.set(0, y, z);
  m.visible = false;
  m.userData.desenhar = (texto, cor) => {
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, 512, 256);
    let tamanho = 130;
    do ctx.font = `850 ${tamanho -= 6}px Archivo, system-ui, sans-serif`;
    while (ctx.measureText(texto).width > 470 && tamanho > 30);
    ctx.fillStyle = cor;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(texto, 256, 132);
    textura.needsUpdate = true;
    m.visible = texto.length > 0;
  };
  return m;
}

function montar(partes) {
  const g = new THREE.Group();
  g.userData.partes = partes;
  for (const [nome, meshes] of Object.entries(partes)) meshes.forEach(m => { m.name = nome; g.add(m); });
  return g;
}

function camiseta(cor) {
  const corpo = inflarParte(contorno(CORPO_CAMISETA, -0.3), cor, 0.25, 0.22);
  const mangas = [MANGA_CAMISETA, espelhar(MANGA_CAMISETA)].map(p => inflarParte(forma(p), cor, 0.18, 0.18));
  const curva = new THREE.QuadraticBezierCurve3(
    new THREE.Vector3(-0.37, 1.01, 0.34), new THREE.Vector3(0, 0.68, 0.36), new THREE.Vector3(0.37, 1.01, 0.34));
  const gola = new THREE.Mesh(new THREE.TubeGeometry(curva, 32, 0.075, 12), tecido(cor));
  return montar({ corpo: [corpo], mangas, gola: [gola], estampa: [estampa(0.2, 0.36)] });
}

function moletom(cor) {
  const corpo = inflarParte(contorno(CORPO_MOLETOM, -0.15), cor, 0.25, 0.22);
  const mangas = [MANGA_MOLETOM, espelhar(MANGA_MOLETOM)].map(p => inflarParte(forma(p), cor, 0.18, 0.18));
  const oval = new THREE.Shape();
  oval.absellipse(0, 0, 0.5, 0.42, 0, Math.PI * 2, false);
  const capuz = inflarParte(oval, cor, 0.16, 0.16);
  capuz.position.set(0, 1.02, -0.12);
  const bolso = inflarParte(forma([[-0.45, -0.25], [0.45, -0.25], [0.32, 0.2], [-0.32, 0.2]]), cor, 0.02, 0.06);
  bolso.position.set(0, -0.55, 0.36);
  return montar({ corpo: [corpo], mangas, capuz: [capuz], bolso: [bolso], estampa: [estampa(0.25, 0.36)] });
}

function bone(cor) {
  const g = new THREE.Group();
  const copa = new THREE.Mesh(new THREE.SphereGeometry(0.9, 48, 24, 0, Math.PI * 2, 0, Math.PI / 2), tecido(cor));
  copa.scale.y = 0.85;
  const forma = new THREE.Shape();
  forma.absellipse(0, 0, 0.85, 0.75, 0, Math.PI, false);
  const aba = inflar(forma, cor, 0.02, 0.04);
  aba.rotation.x = Math.PI / 2 + 0.15;
  aba.position.set(0, 0.02, 0.75);
  const botao = new THREE.Mesh(new THREE.SphereGeometry(0.08, 16, 16), tecido(cor));
  botao.position.y = 0.76;
  g.add(copa, aba, botao);
  g.rotation.x = 0.3;
  return g;
}

export function tipoDaCategoria(nome = '') {
  const n = nome.toLowerCase();
  if (n.includes('molet') || n.includes('jaquet')) return 'moletom';
  if (n.includes('calç') || n.includes('calc') || n.includes('bermuda')) return 'calca';
  if (n.includes('bon')) return 'bone';
  if (n.includes('camis') || n.includes('regata')) return 'camiseta';
  return 'abstrato';
}

export function criarPeca(tipo, cor) {
  if (tipo === 'camiseta') return camiseta(cor);
  if (tipo === 'moletom') return moletom(cor);
  if (tipo === 'calca') return inflar(contorno(CALCA), cor);
  if (tipo === 'bone') return bone(cor);
  return new THREE.Mesh(new THREE.TorusKnotGeometry(0.7, 0.25, 160, 24), tecido(cor));
}

// centraliza e ajusta o tamanho
export function encaixar(obj, tamanho = 2.4) {
  const caixa = new THREE.Box3().setFromObject(obj);
  const dim = caixa.getSize(new THREE.Vector3());
  obj.position.sub(caixa.getCenter(new THREE.Vector3()));
  const grupo = new THREE.Group();
  grupo.add(obj);
  grupo.scale.setScalar(tamanho / Math.max(dim.x, dim.y, dim.z));
  return grupo;
}

const loader = new GLTFLoader();
// nomes de material que o painel de personalizar reconhece num .glb
const PARTES_GLB = ['cabedal', 'biqueira', 'calcanhar', 'cadarco', 'entressola', 'sola'];
// link, /static/..., arquivo escolhido no formulário (blob:) ou enviado pelo painel (pasta media)
const caminho = (url, media = '/media/') => (/^(https?:|blob:|\/)/.test(url) ? url : media + url);

export async function criarModelo({ categoria, modelo, cor, media, seed = 0 }, tamanho) {
  if (modelo) {
    try {
      const gltf = await loader.loadAsync(caminho(modelo, media));
      const peca = encaixar(gltf.scene, tamanho);
      // .glb separado em partes nomeadas (sola, cabedal...) pode ser personalizado como a camiseta
      const achadas = {};
      gltf.scene.traverse(m => {
        const nome = (m.isMesh && m.material?.name) || '';
        if (PARTES_GLB.includes(nome)) (achadas[nome] ??= []).push(m);
      });
      const partes = Object.fromEntries(PARTES_GLB.filter(n => achadas[n]).map(n => [n, achadas[n]]));
      if (Object.keys(partes).length > 1) peca.userData.partes = partes;
      // combinações de cor que vêm dentro do .glb (KHR_materials_variants)
      const variantes = gltf.parser.json.extensions?.KHR_materials_variants?.variants;
      if (variantes) {
        const nomes = variantes.map(v => v.name);
        // a combinação que o arquivo já abre usando
        const prim = gltf.parser.json.meshes?.[0]?.primitives?.[0];
        const mapa = prim?.extensions?.KHR_materials_variants?.mappings?.find(x => x.material === prim.material);
        peca.userData.variantes = { nomes, parser: gltf.parser, padrao: mapa ? nomes[mapa.variants[0]] : nomes[0] };
      }
      return peca;
    } catch (erro) {
      console.warn('Modelo 3D não carregou, usando peça gerada:', erro);
    }
  }
  const peca = encaixar(criarPeca(tipoDaCategoria(categoria), cor || CORES[seed % CORES.length]), tamanho);
  peca.userData.gerada = true;
  peca.userData.partes = peca.children[0].userData.partes; // só camiseta e moletom têm partes
  return peca;
}

// troca a cor da peça inteira (painel)
export function pintar(peca, cor) {
  if (!peca.userData.gerada) return;
  peca.traverse(m => {
    if (!m.isMesh || !m.material.sheenColor) return;
    m.material.color.set(cor);
    m.material.sheenColor.set(cor).lerp(new THREE.Color('#ffffff'), 0.5);
  });
}

// troca a combinação de cores de um .glb; nome vazio volta ao original
export async function aplicarVariante(peca, nome) {
  const { nomes, parser } = peca.userData.variantes;
  const indice = nomes.indexOf(nome);
  const trocas = [];
  peca.traverse(m => {
    const ext = m.isMesh && m.userData.gltfExtensions?.KHR_materials_variants;
    if (!ext) return;
    m.userData.materialOriginal ??= m.material;
    const mapa = ext.mappings.find(x => x.variants.includes(indice));
    if (!mapa) { m.material = m.userData.materialOriginal; return; }
    trocas.push(parser.getDependency('material', mapa.material).then(mat => {
      m.material = mat;
      parser.assignFinalMaterial(m);
    }));
  });
  await Promise.all(trocas);
}

export function criarRenderer(canvas, opcoes = {}, maxPixelRatio = 2) {
  const r = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, ...opcoes });
  r.setPixelRatio(Math.min(devicePixelRatio, maxPixelRatio));
  r.toneMapping = THREE.ACESFilmicToneMapping;
  return r;
}

// cena com iluminação
export function criarCena(renderer) {
  const cena = new THREE.Scene();
  cena.environment = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(renderer), 0.04).texture;
  const luz = new THREE.DirectionalLight('#ffffff', 1.5);
  luz.position.set(3, 4, 5);
  cena.add(luz);
  return cena;
}
// Peças 3D da NEXAR: gera roupas "infladas" em código e carrega modelos .glb quando o produto tiver um.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

// Cores de reserva, só para produto sem cor cadastrada
export const CORES = ['#22306b', '#e8641e', '#5b6542', '#8fb3d9', '#c8233a', '#ededE9'];

// Metade direita do contorno de cada peça (x, y). A metade esquerda é espelhada automaticamente.
const CAMISETA = [[0.35, 1], [0.95, 0.82], [1.4, 0.3], [1.05, 0.05], [0.75, 0.3], [0.75, -1.1]];
const MOLETOM = [[0.38, 1], [1, 0.82], [1.75, -0.55], [1.38, -0.78], [0.8, 0.12], [0.8, -1.1]];
const CALCA = [[0.7, 1.1], [0.88, -1.3], [0.18, -1.3], [0, 0.15]];

// gola: quanto a curva do pescoço desce (negativo) ou sobe como capuz (positivo)
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

// Extrusão com chanfro grande = visual de roupa inflada
function inflar(shape, cor, profundidade = 0.25, chanfro = 0.22) {
  const g = new THREE.ExtrudeGeometry(shape, {
    depth: profundidade, curveSegments: 32,
    bevelEnabled: true, bevelThickness: chanfro, bevelSize: chanfro * 0.65, bevelSegments: 10,
  });
  g.center();
  return new THREE.Mesh(g, tecido(cor));
}

function moletom(cor) {
  const g = new THREE.Group();
  g.add(inflar(contorno(MOLETOM, 0.45), cor));
  const bolso = inflar(new THREE.Shape([[-0.45, -0.25], [0.45, -0.25], [0.32, 0.2], [-0.32, 0.2]]
    .map(([x, y]) => new THREE.Vector2(x, y))), cor, 0.02, 0.06);
  bolso.position.set(0, -0.55, 0.36);
  g.add(bolso);
  return g;
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
  if (tipo === 'camiseta') return inflar(contorno(CAMISETA, -0.3), cor);
  if (tipo === 'moletom') return moletom(cor);
  if (tipo === 'calca') return inflar(contorno(CALCA), cor);
  if (tipo === 'bone') return bone(cor);
  return new THREE.Mesh(new THREE.TorusKnotGeometry(0.7, 0.25, 160, 24), tecido(cor));
}

// Centraliza o objeto e deixa o maior lado com `tamanho` unidades
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
// Link completo (http...) ou caminho absoluto: usa direto. Senão é um arquivo enviado pelo painel,
// que fica na pasta de mídia (o template passa o prefixo em data-media, que muda na Vercel).
const caminho = (url, media = '/media/') => (url.startsWith('http') || url.startsWith('/') ? url : media + url);

// dados = data-* do HTML: categoria, modelo (.glb opcional), cor (#hex) e seed (cor de reserva)
export async function criarModelo({ categoria, modelo, cor, media, seed = 0 }, tamanho) {
  if (modelo) {
    try {
      return encaixar((await loader.loadAsync(caminho(modelo, media))).scene, tamanho);
    } catch (erro) {
      console.warn('Modelo 3D não carregou, usando peça gerada:', erro);
    }
  }
  const peca = encaixar(criarPeca(tipoDaCategoria(categoria), cor || CORES[seed % CORES.length]), tamanho);
  peca.userData.gerada = true; // só peça gerada pode trocar de cor (o .glb tem textura própria)
  return peca;
}

// Troca a cor do tecido de uma peça gerada (usado no painel quando o admin escolhe a cor)
export function pintar(peca, cor) {
  if (!peca.userData.gerada) return;
  peca.traverse(m => {
    if (!m.isMesh) return;
    m.material.color.set(cor);
    m.material.sheenColor.set(cor).lerp(new THREE.Color('#ffffff'), 0.5);
  });
}

export function criarRenderer(canvas, opcoes = {}, maxPixelRatio = 2) {
  const r = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, ...opcoes });
  r.setPixelRatio(Math.min(devicePixelRatio, maxPixelRatio));
  r.toneMapping = THREE.ACESFilmicToneMapping;
  return r;
}

// Cena com luz de estúdio (reflexos suaves) + uma luz direcional
export function criarCena(renderer) {
  const cena = new THREE.Scene();
  cena.environment = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(renderer), 0.04).texture;
  const luz = new THREE.DirectionalLight('#ffffff', 1.5);
  luz.position.set(3, 4, 5);
  cena.add(luz);
  return cena;
}
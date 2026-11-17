# blender -b --python separar_tenis.py -- entrada.glb saida.glb [render.png]
# Separa um tênis (malha única) em partes nomeadas, pela posição de cada face.
import sys
import bpy
import bmesh
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]
entrada, saida = args[0], args[1]
render = args[2] if len(args) > 2 else None

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=entrada)
malhas = [o for o in bpy.context.scene.objects if o.type == "MESH"]
bpy.ops.object.select_all(action="DESELECT")
for o in malhas:
    o.select_set(True)
bpy.context.view_layer.objects.active = malhas[0]
if len(malhas) > 1:
    bpy.ops.object.join()
obj = bpy.context.view_layer.objects.active
bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
obj.rotation_mode = "XYZ"  # o importador de glTF usa quaternion; sem isso rotation_euler não faz nada
for o in list(bpy.context.scene.objects):
    if o != obj:
        bpy.data.objects.remove(o, do_unlink=True)

# deixa leve para a web
faces = len(obj.data.polygons)
if faces > 60000:
    mod = obj.modifiers.new("dec", "DECIMATE")
    mod.ratio = 60000 / faces
    bpy.ops.object.modifier_apply(modifier="dec")

# orienta: comprimento no eixo X, de pé no Z, centralizado com a sola em z=0
me = obj.data
xs = [v.co.x for v in me.vertices]
ys = [v.co.y for v in me.vertices]
if (max(ys) - min(ys)) > (max(xs) - min(xs)):
    obj.rotation_euler = (0, 0, 1.5708)
    bpy.ops.object.transform_apply(rotation=True)
cs = [obj.matrix_world @ v.co for v in me.vertices]
mn = Vector((min(c.x for c in cs), min(c.y for c in cs), min(c.z for c in cs)))
mx = Vector((max(c.x for c in cs), max(c.y for c in cs), max(c.z for c in cs)))
obj.location -= Vector(((mn.x + mx.x) / 2, (mn.y + mx.y) / 2, mn.z))
bpy.ops.object.transform_apply(location=True)
comp, larg, alt = mx.x - mn.x, mx.y - mn.y, mx.z - mn.z

# a ponta (biqueira) é o lado mais baixo; o calcanhar tem a gola mais alta
def altura_no_lado(sinal):
    zs = [v.co.z for v in me.vertices if sinal * v.co.x > comp * 0.3]
    return max(zs) if zs else 0
if altura_no_lado(1) > altura_no_lado(-1):  # calcanhar ficou no +X: gira para a ponta ir para +X
    obj.rotation_euler = (0, 0, 3.14159)
    bpy.ops.object.transform_apply(rotation=True)

PARTES = {
    # cores em espaço linear (o glTF guarda assim): branco, cinza médio e preto
    "sola": (0.012, 0.012, 0.012), "entressola": (0.86, 0.86, 0.84), "cabedal": (0.9, 0.9, 0.88),
    "biqueira": (0.3, 0.32, 0.35), "calcanhar": (0.3, 0.32, 0.35), "cadarco": (0.012, 0.012, 0.012),
}
obj.data.materials.clear()
indice = {}
for i, (nome, cor) in enumerate(PARTES.items()):
    mat = bpy.data.materials.new(nome)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*cor, 1)
    bsdf.inputs["Roughness"].default_value = 0.8 if nome == "sola" else 0.6
    obj.data.materials.append(mat)
    indice[nome] = i

bm = bmesh.new()
bm.from_mesh(obj.data)
# corta a malha em linhas retas nos limites das partes, para as divisas ficarem limpas
for co, no in [((0, 0, alt * 0.1), (0, 0, 1)), ((0, 0, alt * 0.24), (0, 0, 1)),
               ((comp * 0.2 - comp / 2, 0, 0), (1, 0, 0)), ((comp * 0.78 - comp / 2, 0, 0), (1, 0, 0))]:
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=co, plane_no=no)
for f in bm.faces:
    c = f.calc_center_median()
    h = c.z / alt                      # 0 = chão, 1 = topo
    l = (c.x + comp / 2) / comp        # 0 = calcanhar, 1 = ponta
    w = abs(c.y) / (larg / 2)          # 0 = meio, 1 = lateral
    if h < 0.1:
        parte = "sola"
    elif h < 0.24:
        parte = "entressola"
    elif l > 0.78:
        parte = "biqueira"
    elif l < 0.2:
        parte = "calcanhar"
    elif h > 0.5 and w < 0.42 and 0.35 < l < 0.78 and f.normal.z > 0.2:
        parte = "cadarco"
    else:
        parte = "cabedal"
    f.material_index = indice[parte]
bm.to_mesh(obj.data)
bm.free()

bpy.ops.object.select_all(action="DESELECT")
obj.select_set(True)
bpy.context.view_layer.objects.active = obj
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.mesh.separate(type="MATERIAL")
bpy.ops.object.mode_set(mode="OBJECT")
contagem = {}
for o in bpy.context.scene.objects:
    if o.type == "MESH" and o.data.materials:
        o.name = o.data.materials[0].name
        o.data.name = o.name
        # só o material da própria parte (remove texturas e variantes que vieram no arquivo)
        o.data.materials.clear()
        o.data.materials.append(bpy.data.materials[o.name])
        for atributo in ("gltf2_variant_default_materials", "gltf2_variant_mesh_data"):
            if hasattr(o.data, atributo):
                getattr(o.data, atributo).clear()
        contagem[o.name] = len(o.data.polygons)
if hasattr(bpy.context.scene, "gltf2_KHR_materials_variants_variants"):
    bpy.context.scene.gltf2_KHR_materials_variants_variants.clear()
print("PARTES", contagem)

bpy.ops.export_scene.gltf(filepath=saida, export_format="GLB", use_selection=False, export_yup=True)

if render:
    cena = bpy.context.scene
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    cena.collection.objects.link(cam)
    cam.location = (comp * 0.35, -comp * 1.6, alt * 1.1)
    alvo = Vector((0, 0, alt * 0.45))
    cam.rotation_euler = (alvo - cam.location).to_track_quat("-Z", "Y").to_euler()
    cena.camera = cam
    luz = bpy.data.objects.new("sol", bpy.data.lights.new("sol", "SUN"))
    luz.rotation_euler = (0.8, 0.2, 0.6)
    cena.collection.objects.link(luz)
    cena.world = bpy.data.worlds.new("mundo")
    cena.world.color = (0.86, 0.87, 0.89)
    # cores fortes só para ver as partes no render
    for nome, cor in {"sola": (0.1, 0.1, 0.1), "entressola": (0.95, 0.95, 0.95), "cabedal": (0.15, 0.3, 0.85),
                      "biqueira": (0.85, 0.2, 0.2), "calcanhar": (0.2, 0.7, 0.3), "cadarco": (1, 0.6, 0.1)}.items():
        bpy.data.materials[nome].node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*cor, 1)
    cena.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items] else "BLENDER_EEVEE"
    cena.render.resolution_x, cena.render.resolution_y = 900, 600
    cena.render.filepath = render
    bpy.ops.render.render(write_still=True)

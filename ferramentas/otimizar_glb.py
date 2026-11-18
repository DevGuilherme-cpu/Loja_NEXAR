# blender -b --python ferramentas/otimizar_glb.py -- entrada.glb saida.glb [faces=20000] [textura=1024]
# Deixa um .glb do Meshy leve para o site: reduz os polígonos, diminui as texturas e salva em JPEG.
# Também tira animação e esqueleto, que o site não usa (ele mesmo centraliza e ajusta o tamanho).
import sys
import bpy

args = sys.argv[sys.argv.index("--") + 1:]
entrada, saida = args[0], args[1]
faces_max = int(args[2]) if len(args) > 2 else 20000
textura_max = int(args[3]) if len(args) > 3 else 1024

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=entrada)

# esqueleto e animação pesam e o site não usa
for o in list(bpy.context.scene.objects):
    if o.type == "ARMATURE":
        bpy.data.objects.remove(o, do_unlink=True)
for o in bpy.context.scene.objects:
    o.animation_data_clear()
    for mod in list(getattr(o, "modifiers", [])):
        if mod.type == "ARMATURE":
            o.modifiers.remove(mod)
for acao in list(bpy.data.actions):
    bpy.data.actions.remove(acao)

malhas = [o for o in bpy.context.scene.objects if o.type == "MESH"]
total = sum(len(o.data.polygons) for o in malhas)
antes = total
if total > faces_max:
    for o in malhas:
        bpy.context.view_layer.objects.active = o
        mod = o.modifiers.new("dec", "DECIMATE")
        mod.ratio = faces_max / total
        bpy.ops.object.modifier_apply(modifier="dec")

for img in bpy.data.images:
    w, h = img.size
    if max(w, h) > textura_max:
        k = textura_max / max(w, h)
        img.scale(max(1, int(w * k)), max(1, int(h * k)))

depois = sum(len(o.data.polygons) for o in malhas)
print(f"FACES {antes} -> {depois}; TEXTURAS {[(i.name, tuple(i.size)) for i in bpy.data.images]}")

bpy.ops.export_scene.gltf(filepath=saida, export_format="GLB", export_image_format="JPEG",
                          export_animations=False, export_skins=False, export_yup=True)

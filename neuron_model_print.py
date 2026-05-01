"""
neuron_model_print.py — Print-Ready Human Neuron for FDM/PLA
=============================================================
Run headless:  blender --background --python neuron_model_print.py
Or:            Open in Blender Scripting workspace → Run Script

Produces two OBJ files ready for slicing:
  Neuron_Print_Body.obj   ← neuron + oval base + organic support struts (one joined piece)
  Neuron_Print_Panel.obj  ← separate description panel with snap-fit pegs

Scale guide (set in your slicer):
  1 Blender unit = 5 mm   → body ≈ 175 × 140 × 95 mm  (recommended desk display)
  1 Blender unit = 3 mm   → body ≈ 105 × 84 × 57 mm   (compact)

Recommended PLA slicer settings:
  Layer height  : 0.20 mm
  Infill        : 15 % gyroid
  Supports      : Tree supports (for upper dendritic branches only)
  Brim          : 8 mm on base plate
  Print body flat (base plate on build surface).
  Print panel flat on its BACK face (text relief facing up — no supports needed).
  After printing, press panel tabs into base holes to assemble.

Key print-ready changes vs. neuron_model.py (visualisation version):
  • All skin skeleton radii clamped to PRINT_MIN_RAD = 0.50
  • Floating text labels + thin stalks removed (not printable)
  • Molecule markers kept as surface spheres (radius ≥ 0.50)
  • Oval base plate added — flat bed adhesion surface, 3 units thick
  • Three organic root-arch support struts under the axon
  • Description panel: separate vertical slab, embossed text, snap-fit pegs
"""

import bpy
import bmesh
import math
import random
from mathutils import Vector, Matrix

random.seed(42)

# ─── Print constants ─────────────────────────────────────────────────────────
PRINT_MIN_RAD = 0.50  # minimum skin radius for 0.4 mm nozzle at 5 mm/unit
SUPPORT_RAD = 0.85  # organic strut radius (root arches)
PANEL_EXTRUDE = 0.20  # text relief depth on description panel
TEXT_SIZE_LG = 1.00  # title text height  (≈ 5 mm at 5 mm/unit)
TEXT_SIZE_SM = 0.70  # body text height   (≈ 3.5 mm at 5 mm/unit)

# Base plate geometry
BASE_TOP_Z = -5.0  # top face of the base plate (everything prints above this)
BASE_THICK = 3.0  # plate thickness → bottom at BASE_TOP_Z - BASE_THICK
BASE_CX, BASE_CY = 9.0, -4.0  # overhang centre of the model footprint
BASE_RX, BASE_RY = 22.0, 16.0  # oval half-extents

# Panel geometry
PANEL_W = 38.0  # width (slab spans ±PANEL_W/2 from centre)
PANEL_H = 23.0  # height
PANEL_D = 1.5  # thickness (depth front-to-back)
PANEL_Y = BASE_CY + BASE_RY + PANEL_D * 0.5 + 0.5  # just behind base plate rear edge
PANEL_CX = BASE_CX
PANEL_BZ = BASE_TOP_Z  # panel bottom sits on top of base plate
PEG_R = 0.40  # snap-fit peg radius
PEG_H = 1.50  # snap-fit peg height (inserts into base hole)
PEG_X_OFF = 12.0  # ± X offset from panel centre for the two pegs


# ============================================================
# 0.  SCENE RESET
# ============================================================
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
for col in (bpy.data.meshes, bpy.data.materials, bpy.data.curves):
    for blk in list(col):
        try:
            col.remove(blk)
        except Exception:
            pass


# ============================================================
# 1.  MATERIALS  (same palette as visualisation version)
# ============================================================
def make_material(
    name,
    base_color,
    roughness=0.6,
    metallic=0.0,
    subsurface=0.0,
    subsurface_color=None,
    emission=None,
):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    out.location = (300, 0)
    bsdf.location = (0, 0)
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    bsdf.inputs["Base Color"].default_value = (*base_color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    for key in ("Subsurface Weight", "Subsurface"):
        try:
            bsdf.inputs[key].default_value = subsurface
            break
        except KeyError:
            pass
    if subsurface_color:
        try:
            bsdf.inputs["Subsurface Color"].default_value = (*subsurface_color, 1.0)
        except KeyError:
            pass
    if emission:
        try:
            bsdf.inputs["Emission Color"].default_value = (*emission, 1.0)
            bsdf.inputs["Emission Strength"].default_value = 0.5
        except KeyError:
            pass
    return mat


MAT = {
    "soma": make_material(
        "Soma_Mat",
        (0.85, 0.72, 0.15),
        roughness=0.55,
        subsurface=0.25,
        subsurface_color=(1.0, 0.85, 0.3),
    ),
    "nucleus": make_material("Nucleus_Mat", (0.78, 0.38, 0.05), roughness=0.45),
    "myelin": make_material(
        "Myelin_Mat", (0.88, 0.88, 0.85), roughness=0.35, metallic=0.05
    ),
    "ranvier": make_material("Ranvier_Mat", (0.70, 0.62, 0.12), roughness=0.7),
    "hillock": make_material("Hillock_Mat", (0.75, 0.62, 0.10), roughness=0.6),
    "terminal": make_material("Terminal_Mat", (0.85, 0.72, 0.15), roughness=0.5),
    "vesicle": make_material("Vesicle_Mat", (0.95, 0.92, 0.30), roughness=0.3),
    "channel": make_material(
        "CaChannel_Mat", (0.50, 0.80, 0.95), roughness=0.25, metallic=0.4
    ),
    "base": make_material("Base_Mat", (0.20, 0.20, 0.22), roughness=0.8),
    "panel": make_material("Panel_Mat", (0.95, 0.95, 0.92), roughness=0.6),
    "support": make_material("Support_Mat", (0.65, 0.55, 0.10), roughness=0.65),
    "mol_marker": make_material(
        "MolMarker_Mat", (0.95, 0.95, 0.3), roughness=0.3, emission=(0.9, 0.85, 0.1)
    ),
}


# ============================================================
# 2.  UTILS
# ============================================================
def link(obj):
    bpy.context.collection.objects.link(obj)


def set_active(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def apply_mat(obj, mat):
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)


def rotation_to_vector(target: Vector):
    target = target.normalized()
    up = Vector((0, 0, 1))
    if abs(target.dot(up)) > 0.999:
        up = Vector((0, 1, 0))
    right = target.cross(up).normalized()
    real_up = target.cross(right).normalized()
    mat = Matrix(
        (
            (right.x, right.y, right.z, 0),
            (real_up.x, real_up.y, real_up.z, 0),
            (target.x, target.y, target.z, 0),
            (0, 0, 0, 1),
        )
    ).transposed()
    return mat.to_euler()


def add_skin_skeleton(name, verts_radii, subdiv=2, mat=None):
    """Skin-modifier skeleton. Clamps all radii to PRINT_MIN_RAD. First vert = root."""
    me = bpy.data.meshes.new(name + "_Mesh")
    ob = bpy.data.objects.new(name, me)
    link(ob)
    bm = bmesh.new()
    sl = bm.verts.layers.skin.verify()
    v_prev, positions, first = None, [], True
    for pos, rad in verts_radii:
        rad = max(rad, PRINT_MIN_RAD)  # ← PRINT MIN CLAMP
        v = bm.verts.new(pos)
        v[sl].radius = (rad, rad)
        if first:
            v[sl].use_root = True
            first = False
        if v_prev:
            bm.edges.new((v_prev, v))
        v_prev = v
        positions.append(pos.copy())
    bm.to_mesh(me)
    bm.free()
    set_active(ob)
    bpy.ops.object.modifier_add(type="SKIN")
    bpy.ops.object.modifier_add(type="SUBSURF")
    ob.modifiers["Subdivision"].levels = subdiv
    if mat:
        apply_mat(ob, mat)
    return positions, ob


# ============================================================
# 3.  SOMA
# ============================================================
bpy.ops.mesh.primitive_uv_sphere_add(
    radius=2.8, location=(0, 0, 0), segments=48, ring_count=32
)
soma = bpy.context.active_object
soma.name = "Soma"
bm_s = bmesh.new()
bm_s.from_mesh(soma.data)
for v in bm_s.verts:
    v.co += v.normal * random.gauss(0, 0.18)
bm_s.to_mesh(soma.data)
bm_s.free()
soma.data.update()
apply_mat(soma, MAT["soma"])
bpy.ops.object.shade_smooth()
soma.modifiers.new("Subsurf", "SUBSURF").levels = 2


# ============================================================
# 4.  NUCLEUS
# ============================================================
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.1, location=(0.2, 0.1, 0.15))
nucleus = bpy.context.active_object
nucleus.name = "Nucleus"
apply_mat(nucleus, MAT["nucleus"])
bpy.ops.object.shade_smooth()


# ============================================================
# 5.  AXON HILLOCK
# ============================================================
HILLOCK_DIR = Vector((1.0, -0.4, -0.3)).normalized()
SOMA_EXIT = HILLOCK_DIR * 2.6
HILLOCK_END = HILLOCK_DIR * 4.8

bpy.ops.mesh.primitive_cone_add(
    vertices=24,
    radius1=1.4,
    radius2=0.55,
    depth=2.3,
    location=((SOMA_EXIT + HILLOCK_END) * 0.5),
)
hillock = bpy.context.active_object
hillock.name = "Axon_Hillock"
apply_mat(hillock, MAT["hillock"])
bpy.ops.object.shade_smooth()
hillock.rotation_euler = rotation_to_vector(HILLOCK_DIR)
hillock.modifiers.new("Subsurf", "SUBSURF").levels = 2


# ============================================================
# 6.  AXON
# ============================================================
AXON_START = HILLOCK_END
AXON_END = Vector((22.0, -8.0, -3.0))


def axon_point(t):
    P0, P1 = AXON_START, Vector((8, -1, -2))
    P2, P3 = Vector((16, -10, 1)), AXON_END
    u = 1.0 - t
    return (u**3) * P0 + 3 * (u**2) * t * P1 + 3 * u * (t**2) * P2 + (t**3) * P3


AXON_SEGS = 40
axon_vr = [(axon_point(i / AXON_SEGS), 0.50) for i in range(AXON_SEGS + 1)]
_, ob_axon = add_skin_skeleton("Axon", axon_vr, subdiv=2, mat=MAT["soma"])


# ============================================================
# 7.  MYELIN + RANVIER
# ============================================================
NUM_MYELIN = 7
MYELIN_START = 0.18
MYELIN_END = 0.87

for i in range(NUM_MYELIN):
    t_c = MYELIN_START + (i + 0.5) * (MYELIN_END - MYELIN_START) / NUM_MYELIN
    center = axon_point(t_c)
    tangent = (
        axon_point(min(t_c + 0.01, 1.0)) - axon_point(max(t_c - 0.01, 0.0))
    ).normalized()

    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=1.0, location=center, segments=24, ring_count=16
    )
    sheath = bpy.context.active_object
    sheath.name = f"Myelin_{i}"
    apply_mat(sheath, MAT["myelin"])
    bpy.ops.object.shade_smooth()
    sheath.scale = (0.65, 0.65, 1.65)
    sheath.rotation_euler = rotation_to_vector(tangent)

    if i < NUM_MYELIN - 1:
        t_n = MYELIN_START + (i + 1) * (MYELIN_END - MYELIN_START) / NUM_MYELIN
        n_pt = axon_point(t_n)
        tang2 = (
            axon_point(min(t_n + 0.01, 1.0)) - axon_point(max(t_n - 0.01, 0.0))
        ).normalized()
        bpy.ops.mesh.primitive_torus_add(
            location=n_pt,
            major_radius=0.55,
            minor_radius=0.20,
            major_segments=20,
            minor_segments=10,
        )
        ranvier = bpy.context.active_object
        ranvier.name = f"Ranvier_{i}"
        apply_mat(ranvier, MAT["ranvier"])
        ranvier.rotation_euler = rotation_to_vector(tang2)


# ============================================================
# 8.  AXON TERMINAL
# ============================================================
TERM_BASE = axon_point(1.0)
TERM_DIR = (axon_point(1.0) - axon_point(0.95)).normalized()
BOUTON_POSITIONS = []

for i in range(6):
    angle = (i / 6) * math.tau + random.uniform(-0.3, 0.3)
    perp = Vector(
        (math.cos(angle) * 0.8, math.sin(angle) * 0.8, random.uniform(-0.4, 0.4))
    )
    branch_dir = (TERM_DIR + perp).normalized()
    length = random.uniform(2.8, 4.5)
    b_pos = TERM_BASE.copy()
    b_vr = [(b_pos.copy(), 0.55)]
    for j in range(1, 6):
        t = j / 5
        b_pos = (
            b_pos
            + branch_dir * (length / 5)
            + Vector(
                (random.gauss(0, 0.12), random.gauss(0, 0.12), random.gauss(0, 0.08))
            )
        )
        b_vr.append((b_pos.copy(), max(0.55 * (1.0 - 0.4 * t), PRINT_MIN_RAD)))
    add_skin_skeleton(f"Term_Branch_{i}", b_vr, subdiv=1, mat=MAT["soma"])
    tip = b_pos.copy()
    BOUTON_POSITIONS.append((tip, branch_dir.copy()))

    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=0.65, location=tip, segments=20, ring_count=14
    )
    bouton = bpy.context.active_object
    bouton.name = f"Bouton_{i}"
    apply_mat(bouton, MAT["terminal"])
    bpy.ops.object.shade_smooth()
    bouton.scale = (1.0, 1.0, 0.6)
    bouton.rotation_euler = rotation_to_vector(branch_dir)

    for k in range(random.randint(6, 10)):
        offset = Vector(
            (random.gauss(0, 0.28), random.gauss(0, 0.28), random.gauss(0, 0.18))
        )
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=0.15, location=tip + offset, segments=8, ring_count=6
        )
        ves = bpy.context.active_object
        ves.name = f"Vesicle_{i}_{k}"
        apply_mat(ves, MAT["vesicle"])
        bpy.ops.object.shade_smooth()

    # Ca²⁺ channel spikes — thickened for printability
    face_up = (
        Vector((0, 0, 1))
        if abs(branch_dir.dot(Vector((0, 0, 1)))) < 0.9
        else Vector((1, 0, 0))
    )
    face_right = branch_dir.cross(face_up).normalized()
    face_up = face_right.cross(branch_dir).normalized()
    for c in range(random.randint(3, 4)):
        ca_angle = (c / 4) * math.tau + random.uniform(-0.4, 0.4)
        spread = random.uniform(0.15, 0.4)
        sv = (math.cos(ca_angle) * face_right + math.sin(ca_angle) * face_up) * spread
        ca_base = tip + sv + branch_dir * 0.45
        ca_tip_v = ca_base + branch_dir * random.uniform(0.4, 0.65)
        add_skin_skeleton(
            f"CaCh_{i}_{c}",
            [(ca_base, 0.12), (ca_tip_v, 0.10)],
            subdiv=1,
            mat=MAT["channel"],
        )
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=0.15, location=ca_tip_v, segments=8, ring_count=6
        )
        pore = bpy.context.active_object
        pore.name = f"CaPore_{i}_{c}"
        apply_mat(pore, MAT["channel"])
        bpy.ops.object.shade_smooth()


# ============================================================
# 9.  MOLECULE MARKERS (surface spheres — no floating stalks)
#     Placed at anatomically correct sites, radius ≥ PRINT_MIN_RAD.
# ============================================================
def add_mol_marker_print(name, location, radius=0.55):
    """Printable molecule marker — simple sphere, no stalk, no text label."""
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=max(radius, PRINT_MIN_RAD), location=location, segments=12, ring_count=8
    )
    mol = bpy.context.active_object
    mol.name = f"MOL_{name}"
    apply_mat(mol, MAT["mol_marker"])
    bpy.ops.object.shade_smooth()


# Axon terminal: Glutamate, DXM, Gabapentin, Pregabalin, Norepinephrine, Substance P
for i, (bpos, bdir) in enumerate(BOUTON_POSITIONS[:6]):
    labels = ["Glutamate", "DXM", "Gabapentin", "Pregabalin", "Norep", "SubstanceP"]
    offsets = [
        bdir * 1.1,
        bdir * 1.4 + Vector((0, 0, 0.3)),
        -bdir * 0.5 + Vector((0.4, 0.4, 0.6)),
        -bdir * 0.4 + Vector((-0.5, 0.4, 0.5)),
        -bdir * 0.7 + Vector((0.0, -0.6, 0.5)),
        bdir * 0.9 + Vector((0.3, 0.0, -0.4)),
    ]
    add_mol_marker_print(labels[i], bpos + offsets[i])

# Soma: Buspirone, Seroquel, Dynorphin, GABA, Lorazepam
soma_dirs = [
    ("Buspirone", Vector((-1.0, 0.5, 0.8)).normalized()),
    ("Seroquel", Vector((-0.5, -1.0, 0.3)).normalized()),
    ("Dynorphin", Vector((0.8, -0.8, -0.5)).normalized()),
    ("GABA", Vector((0.3, 1.0, 0.2)).normalized()),
    # Lorazepam: GABA-A PAM — same inhibitory synapse family as GABA, nearby on soma
    ("Lorazepam", Vector((-0.6, 0.4, -0.7)).normalized()),
]
for mol_name, d in soma_dirs:
    add_mol_marker_print(mol_name, d * 3.5)

# Propranolol: beta-blocker at the SAME presynaptic beta-adrenergic site as Norepinephrine
# Placed near bouton 4 (the Norep marker), offset slightly to distinguish the two
if len(BOUTON_POSITIONS) > 4:
    pr_bpos, pr_bdir = BOUTON_POSITIONS[4]
    add_mol_marker_print(
        "Propranolol", pr_bpos + (-pr_bdir * 0.8) + Vector((0.0, 0.5, 0.7))
    )


# ============================================================
# 10.  DENDRITES (3-level + spines, all radii clamped)
# ============================================================
DEND_ANGLES = [
    (math.radians(a), math.radians(e))
    for a, e in [
        (150, 20),
        (200, -5),
        (240, 30),
        (280, -20),
        (310, 15),
        (95, 10),
        (120, -30),
        (170, 45),
    ]
]

DEND_SHAFT_PTS = []

for d_idx, (azimuth, elevation) in enumerate(DEND_ANGLES):
    dx = math.cos(elevation) * math.cos(azimuth)
    dy = math.cos(elevation) * math.sin(azimuth)
    dz = math.sin(elevation)
    ddir = Vector((dx, dy, dz)).normalized()

    trunk_len = random.uniform(4.5, 7.0)
    v_pos = Vector((0.0, 0.0, 0.0))
    tr_vr = [(v_pos.copy(), 1.0)]
    for s in range(1, 6):
        t = s / 5
        v_pos = (
            v_pos
            + ddir * (trunk_len / 5)
            + Vector(
                (
                    random.gauss(0, 0.25 * t),
                    random.gauss(0, 0.25 * t),
                    random.gauss(0, 0.15 * t),
                )
            )
        )
        tr_vr.append((v_pos.copy(), max(0.75 * (1.0 - 0.55 * t) + 0.12, PRINT_MIN_RAD)))
    trunk_pts, _ = add_skin_skeleton(
        f"Dendrite_Primary_{d_idx}", tr_vr, subdiv=2, mat=MAT["soma"]
    )
    DEND_SHAFT_PTS.append(trunk_pts[len(trunk_pts) // 2])

    # Dendritic spines — thickened
    for _ in range(random.randint(2, 4)):
        idx = random.randint(1, len(trunk_pts) - 1)
        sp_dir = Vector(
            (random.gauss(0, 1), random.gauss(0, 1), random.gauss(0, 1))
        ).normalized()
        sp_len = random.uniform(0.5, 0.9)
        sp_base = trunk_pts[idx]
        vr_sp = [
            (sp_base, PRINT_MIN_RAD),
            (sp_base + sp_dir * sp_len * 0.55, PRINT_MIN_RAD),
            (sp_base + sp_dir * sp_len, PRINT_MIN_RAD),
        ]
        add_skin_skeleton("Spine", vr_sp, subdiv=1, mat=MAT["soma"])
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=PRINT_MIN_RAD * 1.2,
            location=sp_base + sp_dir * sp_len,
            segments=8,
            ring_count=6,
        )
        sh = bpy.context.active_object
        apply_mat(sh, MAT["soma"])
        bpy.ops.object.shade_smooth()

    # Cortisol markers on shaft midpoints
    if d_idx in (0, 3, 6):
        shaft_pt = DEND_SHAFT_PTS[-1]
        add_mol_marker_print(
            f"Cortisol_{d_idx}",
            shaft_pt + Vector((random.gauss(0, 0.3), random.gauss(0, 0.3), 1.2)),
        )

    # BDNF marker on a spine tip (every other dendrite)
    if d_idx % 2 == 0 and len(trunk_pts) > 2:
        bdnf_base = trunk_pts[-1]
        add_mol_marker_print(
            f"BDNF_{d_idx}",
            bdnf_base + Vector((random.gauss(0, 0.2), random.gauss(0, 0.2), 0.7)),
        )

    # Secondary branches
    for b_idx in range(2):
        split = random.randint(len(trunk_pts) // 2, len(trunk_pts) - 2)
        b_start = trunk_pts[split]
        b_dir = (
            ddir
            + Vector((random.gauss(0, 0.6), random.gauss(0, 0.6), random.gauss(0, 0.4)))
        ).normalized()
        b_len = random.uniform(2.0, 4.0)
        b_pos = b_start.copy()
        b_vr = [(b_pos.copy(), PRINT_MIN_RAD)]
        for s in range(1, 5):
            t = s / 4
            b_pos = (
                b_pos
                + b_dir * (b_len / 4)
                + Vector(
                    (random.gauss(0, 0.2), random.gauss(0, 0.2), random.gauss(0, 0.15))
                )
            )
            b_vr.append((b_pos.copy(), max(0.22 * (1 - 0.6 * t) + 0.05, PRINT_MIN_RAD)))
        b_pts, _ = add_skin_skeleton(
            f"Dendrite_Secondary_{d_idx}_{b_idx}", b_vr, subdiv=2, mat=MAT["soma"]
        )

        # Spines on secondary branches (restored detail)
        for _ in range(random.randint(1, 3)):
            idx = random.randint(0, len(b_pts) - 1)
            sp_dir = Vector(
                (random.gauss(0, 1), random.gauss(0, 1), random.gauss(0, 1))
            ).normalized()
            sp_len = random.uniform(0.5, 0.8)
            sp_base = b_pts[idx]
            vr_sp = [
                (sp_base, PRINT_MIN_RAD),
                (sp_base + sp_dir * sp_len * 0.55, PRINT_MIN_RAD),
                (sp_base + sp_dir * sp_len, PRINT_MIN_RAD),
            ]
            add_skin_skeleton("Spine_Sec", vr_sp, subdiv=1, mat=MAT["soma"])
            bpy.ops.mesh.primitive_uv_sphere_add(
                radius=PRINT_MIN_RAD * 1.15,
                location=sp_base + sp_dir * sp_len,
                segments=8,
                ring_count=6,
            )
            apply_mat(bpy.context.active_object, MAT["soma"])
            bpy.ops.object.shade_smooth()

        # Tertiary tips (increased to 1-3 to match viz version)
        for t_idx in range(random.randint(1, 3)):
            t_dir = (
                b_dir
                + Vector(
                    (random.gauss(0, 0.8), random.gauss(0, 0.8), random.gauss(0, 0.5))
                )
            ).normalized()
            t_len = random.uniform(1.0, 2.2)
            t_pos = b_pts[-1].copy()
            t_vr = [(t_pos.copy(), PRINT_MIN_RAD)]
            for s in range(1, 4):
                t_pos = (
                    t_pos
                    + t_dir * (t_len / 3)
                    + Vector((random.gauss(0, 0.1), random.gauss(0, 0.1), 0))
                )
                t_vr.append((t_pos.copy(), PRINT_MIN_RAD))
            add_skin_skeleton(
                f"Dendrite_Tertiary_{d_idx}_{b_idx}_{t_idx}",
                t_vr,
                subdiv=1,
                mat=MAT["soma"],
            )


# ============================================================
# 11.  OVAL BASE PLATE
# ============================================================
bpy.ops.mesh.primitive_cylinder_add(
    vertices=64,
    radius=1.0,
    depth=BASE_THICK,
    location=(BASE_CX, BASE_CY, BASE_TOP_Z - BASE_THICK * 0.5),
)
base_plate = bpy.context.active_object
base_plate.name = "Base_Plate"
base_plate.scale = (BASE_RX, BASE_RY, 1.0)
set_active(base_plate)
bpy.ops.object.transform_apply(scale=True)
apply_mat(base_plate, MAT["base"])

# Bevel the top edge for a nice first-layer fillet
bev = base_plate.modifiers.new("Bevel", "BEVEL")
bev.width = 0.5
bev.limit_method = "ANGLE"
bev.angle_limit = math.radians(60)

# Blind holes for panel pegs (boolean subtract two cylinders)
for px in (PANEL_CX - PEG_X_OFF, PANEL_CX + PEG_X_OFF):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=16,
        radius=PEG_R + 0.05,  # slight clearance
        depth=PEG_H + 0.5,
        location=(px, PANEL_Y, BASE_TOP_Z - (PEG_H + 0.5) * 0.5),
    )
    hole = bpy.context.active_object
    hole.name = f"Peg_Hole_{px:.0f}"
    set_active(base_plate)
    bool_mod = base_plate.modifiers.new(f"Bool_Hole_{px:.0f}", "BOOLEAN")
    bool_mod.operation = "DIFFERENCE"
    bool_mod.object = hole
    try:
        bpy.ops.object.modifier_apply(modifier=bool_mod.name)
    except Exception:
        pass
    # Remove the cutter mesh
    set_active(hole)
    bpy.ops.object.delete()

set_active(base_plate)


# ============================================================
# 12.  ORGANIC SUPPORT STRUTS  (root arches under the axon)
#     Three quadratic-Bézier arches from base top → axon contact points.
#     They look like roots/tendrils — sculptural AND functional.
# ============================================================
def support_arch(name, t_axon, arch_lift=4.0):
    """
    Build one root arch from the base plate top (directly below the axon point)
    up to the axon point at parameter t_axon. arch_lift controls the arch's peak.
    """
    axon_contact = axon_point(t_axon)
    # Ground anchor: directly below the axon contact projected onto the base top
    ground = Vector((axon_contact.x, axon_contact.y, BASE_TOP_Z))
    # Quadratic Bézier control point — pushed up and slightly offset
    ctrl = ground.lerp(axon_contact, 0.5) + Vector((0.0, 0.0, arch_lift))

    n_segs = 10
    vr = []
    for i in range(n_segs + 1):
        t = i / n_segs
        u = 1.0 - t
        pt = u * u * ground + 2 * u * t * ctrl + t * t * axon_contact
        # Flare at the root, taper toward the axon contact
        r = SUPPORT_RAD * (1.2 - 0.4 * t)
        vr.append((pt, max(r, PRINT_MIN_RAD)))

    add_skin_skeleton(name, vr, subdiv=2, mat=MAT["support"])


support_arch("SupportArch_0", t_axon=0.35, arch_lift=3.5)
support_arch("SupportArch_1", t_axon=0.62, arch_lift=4.0)
support_arch("SupportArch_2", t_axon=0.88, arch_lift=3.0)


# ============================================================
# 13.  JOIN ALL BODY OBJECTS → Neuron_Print_Body
# ============================================================
# Convert any stray FONT/CURVE objects
bpy.ops.object.select_all(action="DESELECT")
for ob in bpy.data.objects:
    if ob.type in ("FONT", "CURVE"):
        set_active(ob)
        try:
            bpy.ops.object.convert(target="MESH")
        except Exception:
            pass

# Apply all modifiers
bpy.ops.object.select_all(action="DESELECT")
for ob in bpy.data.objects:
    if ob.type == "MESH":
        ob.select_set(True)

for ob in list(bpy.context.selected_objects):
    set_active(ob)
    for mod in list(ob.modifiers):
        try:
            bpy.ops.object.modifier_apply(modifier=mod.name)
        except Exception:
            pass

# Join
bpy.ops.object.select_all(action="DESELECT")
for ob in bpy.data.objects:
    if ob.type == "MESH":
        ob.select_set(True)

if bpy.context.selected_objects:
    bpy.context.view_layer.objects.active = bpy.context.selected_objects[0]
    bpy.ops.object.join()
    body = bpy.context.active_object
    body.name = "Neuron_Print_Body"
    print(
        f"✅  Joined body: {body.name}  "
        f"({len(body.data.vertices):,} verts, {len(body.data.polygons):,} polys)"
    )


# ============================================================
# 14.  DESCRIPTION PANEL  (separate object → separate export)
# ============================================================
# ── Backing slab ─────────────────────────────────────────────
# size=2.0 so half-extents = 1.0; scale=(PANEL_W*0.5,...) → final half-extents = PANEL_W/2
bpy.ops.mesh.primitive_cube_add(
    size=2.0, location=(PANEL_CX, PANEL_Y, PANEL_BZ + PANEL_H * 0.5)
)
panel_slab = bpy.context.active_object
panel_slab.name = "Panel_Slab"
panel_slab.scale = (PANEL_W * 0.5, PANEL_D * 0.5, PANEL_H * 0.5)
set_active(panel_slab)
bpy.ops.object.transform_apply(scale=True)
apply_mat(panel_slab, MAT["panel"])

# Bevel panel edges for a clean look
pan_bev = panel_slab.modifiers.new("Bevel", "BEVEL")
pan_bev.width = 0.3

# ── Snap-fit pegs on panel bottom ────────────────────────────
for px in (PANEL_CX - PEG_X_OFF, PANEL_CX + PEG_X_OFF):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=16,
        radius=PEG_R,
        depth=PEG_H,
        location=(px, PANEL_Y, PANEL_BZ - PEG_H * 0.5),
    )
    peg = bpy.context.active_object
    peg.name = f"Panel_Peg_{px:.0f}"
    apply_mat(peg, MAT["panel"])

# ── Create panel text and join it with the slab ──────────────
#
# Layout: title at top, then 2 columns of 6 molecules each.
# Text is EXTRUDED (positive relief) from the FRONT face of the panel.
# Front face is at Y = PANEL_Y - PANEL_D/2 → text placed at Y = PANEL_Y - PANEL_D/2 - 0.01
#
PANEL_FRONT_Y = PANEL_Y - PANEL_D * 0.5 - 0.01  # just in front of slab face
PANEL_TOP_Z = PANEL_BZ + PANEL_H - 1.5  # top text baseline
LINE_H_LG = TEXT_SIZE_LG * 1.6  # row height for title
LINE_H_SM = TEXT_SIZE_SM * 1.8  # row height for molecule entries
COL_LEFT_X = PANEL_CX - PANEL_W * 0.5 + 2.0  # left column X start
COL_RIGHT_X = PANEL_CX + 1.5  # right column X start


def panel_text(body, x, z, size, extrude=PANEL_EXTRUDE, align="LEFT"):
    bpy.ops.object.text_add(location=(x, PANEL_FRONT_Y, z))
    txt = bpy.context.active_object
    txt.data.body = body
    txt.data.size = size
    txt.data.align_x = align
    txt.data.extrude = extrude
    txt.data.space_line = 1.1
    # Orient text front face toward -Y (printing face)
    txt.rotation_euler = (math.radians(90), 0, 0)
    set_active(txt)
    bpy.ops.object.convert(target="MESH")
    apply_mat(txt, MAT["panel"])
    return txt


# Title
panel_text(
    "mickis brain: regulatory molecules", PANEL_CX, PANEL_TOP_Z, TEXT_SIZE_LG, align="CENTER"
)
panel_text(
    "glutamate is the ultimate dominatrix",
    PANEL_CX,
    PANEL_TOP_Z - LINE_H_LG,
    TEXT_SIZE_SM * 0.8,
    extrude=PANEL_EXTRUDE * 0.8,
    align="CENTER",
)

# Divider line: thin extruded rectangle
bpy.ops.mesh.primitive_cube_add(
    size=1.0, location=(PANEL_CX, PANEL_FRONT_Y - 0.08, PANEL_TOP_Z - LINE_H_LG * 1.75)
)
div = bpy.context.active_object
div.name = "Panel_Divider"
div.scale = (PANEL_W * 0.43, 0.08, 0.05)
set_active(div)
bpy.ops.object.transform_apply(scale=True)
apply_mat(div, MAT["panel"])

# Column header
Z_BODY_START = PANEL_TOP_Z - LINE_H_LG * 2.2

PANEL_ENTRIES = [
    # (name, one-liner — max ~30 chars to stay within column)
    ("GLUTAMATE", "lightning: drives excitation"),
    ("GABA", "electrical ground, opens Cl- channels"),
    ("DXM", "NMDA blocker, personal lubricant"),
    ("GABAPENTIN", "Ca2+ throttle, banana in tailpipe"),
    ("PREGABALIN", "Precision Ca2+ cap, concrete in tailpipe"),
    ("BUSPIRONE", "5-HT1A sensor, dynamic thermostat"),
    ("SEROQUEL", "D2/5-HT2A/H1 viscous engine oil"),
    ("NOREPINEPHRINE", "stress lever, glutamate megaphone"),
    ("CORTISOL", "caustic energy cascade, withers dendrites"),
    ("SUBSTANCE P", "fire alarm, physical pain inducer"),
    ("DYNORPHIN", "dissasociation mechanism, lightswitch anvil"),
    ("BDNF", "plasticity reward, managed glutamate"),
    ("LORAZEPAM", "GABA-A PAM, pressure release valve"),
    ("PROPRANOLOL", "beta-blocker, glutamate soda cap"),
]

for idx, (mol_name, one_liner) in enumerate(PANEL_ENTRIES):
    col = idx // 7  # 0 = left, 1 = right  (7 entries per column, 14 total)
    row = idx % 7
    col_x = COL_LEFT_X if col == 0 else COL_RIGHT_X
    z_name = Z_BODY_START - row * LINE_H_SM * 2.2
    z_desc = z_name - LINE_H_SM * 0.85

    panel_text(mol_name, col_x, z_name, TEXT_SIZE_SM, extrude=PANEL_EXTRUDE * 1.1)
    panel_text(
        one_liner, col_x, z_desc, TEXT_SIZE_SM * 0.65, extrude=PANEL_EXTRUDE * 0.75
    )


# ── Join all panel objects ────────────────────────────────────
bpy.ops.object.select_all(action="DESELECT")
panel_pieces = [
    ob
    for ob in bpy.data.objects
    if ob.name.startswith(("Panel_", "LBL_")) or ob.type in ("FONT",)
]
# Also grab any loose text meshes (already converted)
for ob in bpy.data.objects:
    if ob.type == "MESH" and ob.name != "Neuron_Print_Body":
        panel_pieces.append(ob)

bpy.ops.object.select_all(action="DESELECT")
for ob in panel_pieces:
    if ob.name != "Neuron_Print_Body" and ob.type == "MESH":
        ob.select_set(True)

# Apply bevel on slab before join
set_active(panel_slab)
for mod in list(panel_slab.modifiers):
    try:
        bpy.ops.object.modifier_apply(modifier=mod.name)
    except Exception:
        pass

# Re-select all non-body mesh objects
bpy.ops.object.select_all(action="DESELECT")
for ob in bpy.data.objects:
    if ob.type == "MESH" and ob.name != "Neuron_Print_Body":
        ob.select_set(True)

if bpy.context.selected_objects:
    bpy.context.view_layer.objects.active = bpy.context.selected_objects[0]
    bpy.ops.object.join()
    panel_obj = bpy.context.active_object
    panel_obj.name = "Neuron_Print_Panel"
    print(
        f"✅  Joined panel: {panel_obj.name}  "
        f"({len(panel_obj.data.vertices):,} verts, {len(panel_obj.data.polygons):,} polys)"
    )


# ============================================================
# 15.  CAMERA + LIGHTING (for previews)
# ============================================================
bpy.ops.object.camera_add(location=(18, -28, 14))
cam = bpy.context.active_object
cam.name = "Neuron_Camera"
cam.rotation_euler = (math.radians(58), 0, math.radians(42))
bpy.context.scene.camera = cam

bpy.ops.object.light_add(type="SUN", location=(12, -8, 20))
bpy.context.active_object.data.energy = 5.0
bpy.context.active_object.rotation_euler = (math.radians(50), 0, math.radians(-30))

bpy.ops.object.light_add(type="AREA", location=(-12, 18, 6))
bpy.context.active_object.data.energy = 900.0
bpy.context.active_object.data.size = 12.0


# ============================================================
# 16.  EXPORT
# ============================================================
import sys, os

base_dir = os.path.dirname(os.path.abspath(__file__))

# Body
body_path = os.path.join(base_dir, "Neuron_Print_Body.obj")
bpy.ops.object.select_all(action="DESELECT")
for ob in bpy.data.objects:
    if ob.name == "Neuron_Print_Body":
        ob.select_set(True)
bpy.ops.wm.obj_export(filepath=body_path, export_selected_objects=True)
print(f"\n✅  Exported → {body_path}")

# Panel
panel_path = os.path.join(base_dir, "Neuron_Print_Panel.obj")
bpy.ops.object.select_all(action="DESELECT")
for ob in bpy.data.objects:
    if ob.name == "Neuron_Print_Panel":
        ob.select_set(True)
bpy.ops.wm.obj_export(filepath=panel_path, export_selected_objects=True)
print(f"✅  Exported → {panel_path}")

print(
    """
┌─────────────────────────────────────────────────┐
│  Print guide (set 1 unit = 5mm in slicer)       │
│  Body    : base plate flat on build surface     │
│           tree supports for upper dendrites     │
│  Panel   : lie flat on BACK face, text up       │
│            no supports needed                   │
│  Assembly: press panel pegs into base holes     │
└─────────────────────────────────────────────────┘
"""
)
sys.stdout.flush()

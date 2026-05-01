"""
Anatomically-Correct Human Neuron with Regulatory Molecules
============================================================
Blender Python Script — run headless or in Scripting workspace.

Regulatory molecules modelled as labeled 3D markers at their
anatomically correct interaction sites, with functional descriptions
encoded in object custom properties (readable in Blender outliner).

Molecule → Site mapping:
  Glutamate        → Axon terminal / synaptic cleft (released from boutons)
  GABA             → Dendritic shaft synapses (inhibitory input)
  DXM (Dextrorphan)→ NMDA channels on axon terminal membrane (blocker)
  Gabapentin       → Voltage-gated Ca²⁺ channels, axon terminal (α₂δ subunit)
  Pregabalin       → Same VGCC site, higher affinity variant marker
  Buspirone        → 5-HT1A autoreceptors on soma surface (partial agonist)
  Seroquel         → D2/5-HT2A/H1 receptors on soma (multi-antagonist)
  Norepinephrine   → Presynaptic β-adrenergic receptors at axon terminal
  Cortisol         → Glucocorticoid receptors on dendritic shafts
  Substance P      → NK1 receptors on soma + co-release at axon terminal
  Dynorphins       → κ-opioid receptors on soma (stress shutdown)
  BDNF             → Dendritic spines — TrkB receptor (plasticity)
"""

import bpy
import bmesh
import math
import random
from mathutils import Vector, Matrix

random.seed(42)

# ============================================================
# 0.  SCENE RESET
# ============================================================
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for col in (bpy.data.meshes, bpy.data.materials, bpy.data.curves):
    for blk in list(col):
        try:
            col.remove(blk)
        except Exception:
            pass


# ============================================================
# 1.  MATERIALS
# ============================================================
def make_material(name, base_color, roughness=0.6, metallic=0.0,
                  subsurface=0.0, subsurface_color=None, emission=None):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    out  = nodes.new('ShaderNodeOutputMaterial')
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    out.location  = (300, 0)
    bsdf.location = (0, 0)
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    bsdf.inputs['Base Color'].default_value = (*base_color, 1.0)
    bsdf.inputs['Roughness'].default_value  = roughness
    bsdf.inputs['Metallic'].default_value   = metallic
    for key in ('Subsurface Weight', 'Subsurface'):
        try:
            bsdf.inputs[key].default_value = subsurface; break
        except KeyError:
            pass
    if subsurface_color:
        try:
            bsdf.inputs['Subsurface Color'].default_value = (*subsurface_color, 1.0)
        except KeyError:
            pass
    if emission:
        try:
            bsdf.inputs['Emission Color'].default_value    = (*emission, 1.0)
            bsdf.inputs['Emission Strength'].default_value = 0.5
        except KeyError:
            pass
    return mat


MAT = {
    'soma':        make_material('Soma_Mat',       (0.85, 0.72, 0.15), roughness=0.55,
                                  subsurface=0.25, subsurface_color=(1.0, 0.85, 0.3)),
    'nucleus':     make_material('Nucleus_Mat',    (0.78, 0.38, 0.05), roughness=0.45,
                                  subsurface=0.1,  subsurface_color=(0.9, 0.5, 0.1)),
    'myelin':      make_material('Myelin_Mat',     (0.88, 0.88, 0.85), roughness=0.35, metallic=0.05),
    'ranvier':     make_material('Ranvier_Mat',    (0.70, 0.62, 0.12), roughness=0.7),
    'hillock':     make_material('Hillock_Mat',    (0.75, 0.62, 0.10), roughness=0.6, subsurface=0.15),
    'terminal':    make_material('Terminal_Mat',   (0.85, 0.72, 0.15), roughness=0.5,
                                  emission=(0.95, 0.85, 0.1)),
    'vesicle':     make_material('Vesicle_Mat',    (0.95, 0.92, 0.30), roughness=0.3,
                                  emission=(1.0, 0.95, 0.2)),
    'channel':     make_material('CaChannel_Mat',  (0.50, 0.80, 0.95), roughness=0.25,
                                  metallic=0.4, emission=(0.4, 0.75, 1.0)),
    # ── Molecule marker materials ──────────────────────────────────────
    'glutamate':   make_material('Glutamate_Mat',  (1.0, 0.2, 0.1),   roughness=0.3,
                                  emission=(1.0, 0.3, 0.1)),
    'gaba':        make_material('GABA_Mat',       (0.1, 0.6, 1.0),   roughness=0.3,
                                  emission=(0.1, 0.5, 1.0)),
    'dxm':         make_material('DXM_Mat',        (0.9, 0.5, 0.9),   roughness=0.25,
                                  metallic=0.1, emission=(0.8, 0.3, 0.9)),
    'gabapentin':  make_material('Gabapentin_Mat', (0.3, 0.85, 0.5),  roughness=0.3,
                                  emission=(0.2, 0.8, 0.4)),
    'pregabalin':  make_material('Pregabalin_Mat', (0.1, 0.9, 0.6),   roughness=0.25,
                                  metallic=0.1, emission=(0.0, 0.9, 0.5)),
    'buspirone':   make_material('Buspirone_Mat',  (1.0, 0.75, 0.0),  roughness=0.3,
                                  emission=(1.0, 0.7, 0.0)),
    'seroquel':    make_material('Seroquel_Mat',   (0.6, 0.1, 0.9),   roughness=0.3,
                                  emission=(0.5, 0.0, 0.9)),
    'norep':       make_material('Norep_Mat',      (1.0, 0.4, 0.0),   roughness=0.3,
                                  emission=(1.0, 0.35, 0.0)),
    'cortisol':    make_material('Cortisol_Mat',   (0.5, 0.25, 0.05), roughness=0.5,
                                  emission=(0.6, 0.3, 0.05)),
    'substancep':  make_material('SubstanceP_Mat', (1.0, 0.0, 0.5),   roughness=0.3,
                                  emission=(1.0, 0.0, 0.4)),
    'dynorphin':   make_material('Dynorphin_Mat',  (0.3, 0.3, 0.5),   roughness=0.4,
                                  emission=(0.25, 0.25, 0.5)),
    'bdnf':        make_material('BDNF_Mat',       (0.1, 1.0, 0.4),   roughness=0.2,
                                  emission=(0.05, 1.0, 0.35)),
}


# ============================================================
# 2.  UTILS
# ============================================================
def link(obj):
    bpy.context.collection.objects.link(obj)

def set_active(obj):
    bpy.ops.object.select_all(action='DESELECT')
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
    right   = target.cross(up).normalized()
    real_up = target.cross(right).normalized()
    mat = Matrix((
        (right.x,   right.y,   right.z,   0),
        (real_up.x, real_up.y, real_up.z, 0),
        (target.x,  target.y,  target.z,  0),
        (0,         0,         0,         1),
    )).transposed()
    return mat.to_euler()

def add_skin_skeleton(name, verts_radii, subdiv=2, mat=None):
    """Build skin-modifier object. First vertex marked use_root=True."""
    me = bpy.data.meshes.new(name + "_Mesh")
    ob = bpy.data.objects.new(name, me)
    link(ob)
    bm = bmesh.new()
    sl = bm.verts.layers.skin.verify()
    v_prev, positions, first = None, [], True
    for pos, rad in verts_radii:
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
    bpy.ops.object.modifier_add(type='SKIN')
    bpy.ops.object.modifier_add(type='SUBSURF')
    ob.modifiers["Subdivision"].levels = subdiv
    if mat:
        apply_mat(ob, mat)
    return positions, ob


# ============================================================
# 3.  MOLECULE MARKER HELPER
# ============================================================
MOLECULE_DESCRIPTIONS = {
    "Glutamate":    ("RELEASED from presynaptic terminal vesicles into the synaptic cleft. "
                     "Primary excitatory neurotransmitter. Binds AMPA and NMDA receptors on "
                     "postsynaptic cell. Drives learning, memory formation, and action potential "
                     "propagation. In excess causes excitotoxicity via Ca²⁺ overload."),
    "GABA":         ("RELEASED at inhibitory synapses onto dendritic shafts and soma. "
                     "Hyperpolarises the cell by opening Cl⁻ channels (GABA-A) or K⁺ channels "
                     "(GABA-B). The primary 'brake' — opposes glutamate's 'Go' signal. Low GABA "
                     "relative to glutamate = anxiety, seizures, excitotoxicity."),
    "DXM":          ("BINDS inside the NMDA receptor channel pore (open-channel blocker / "
                     "non-competitive antagonist). Sits between Ca²⁺ influx gate and postsynaptic "
                     "receptor, reducing the magnitude of each excitatory event. Prevents "
                     "excitotoxic Ca²⁺ flood. At therapeutic doses promotes AMPA-driven "
                     "plasticity and BDNF release. Acts as 'lubricant' at the point of synaptic "
                     "contact — less friction even when glutamate is still present."),
    "Gabapentin":   ("BINDS to α₂δ subunit of pre-synaptic Voltage-Gated Calcium Channels (VGCC). "
                     "Reduces Ca²⁺ influx on action potential arrival → less vesicle fusion → "
                     "less glutamate released into synapse. Mechanical 'banana in the tailpipe': "
                     "slows strokes-per-minute of glutamate output. Chronic use risks synaptic "
                     "thinning by blocking thrombospondin-mediated synaptogenesis (same α₂δ site)."),
    "Pregabalin":   ("SAME α₂δ VGCC site as Gabapentin but ~6× higher binding affinity and "
                     "~90% bioavailability vs Gabapentin's saturable gut absorption. 'Precision "
                     "restrictor plate' vs Gabapentin's 'banana'. Harder to titrate, faster onset, "
                     "more reliable Ca²⁺ throttle, but carries higher cognitive and dementia risk "
                     "at chronic high doses due to stronger synaptogenesis suppression."),
    "Buspirone":    ("BINDS to 5-HT1A autoreceptors on the soma/proximal dendrites as a partial "
                     "agonist. Tells the neuron 'Back off — conditions externally are already "
                     "calm.' Reduces serotonin release without physically jamming calcium channels. "
                     "Also weakly antagonises D2 dopamine autoreceptors. Acts as 'intelligent "
                     "thermostat' — raises floor when system is too quiet, caps ceiling when "
                     "system is overloaded. No synaptogenesis suppression; cognitively safe "
                     "for long-term use."),
    "Seroquel":     ("BINDS simultaneously to D2 (dopamine), 5-HT2A (serotonin), H1 (histamine), "
                     "and α₁ (adrenergic) receptors on the soma membrane. Multi-receptor antagonist. "
                     "At therapeutic doses for a hyperactive brain: stops the thermal runaway by "
                     "reducing the amplification of excitatory signals. Norquetiapine metabolite "
                     "additionally blocks norepinephrine re-uptake. 'High-viscosity synthetic oil' "
                     "for a brain running at 10M mph — absorbs heat without stopping the engine."),
    "Norepinephrine": ("BINDS to β₁ and β₂ adrenergic receptors on presynaptic nerve terminals. "
                       "When adrenaline/stress activates these, cAMP/PKA cascade strongly "
                       "FACILITATES glutamate release — turns up the pressure before it even "
                       "reaches the synapse. Beta-blockers (propranolol) antagonise this site. "
                       "Primary contributor to the fight-or-flight 'siren' and to the HPA axis "
                       "cascade that eventually floods the system with cortisol."),
    "Cortisol":     ("BINDS to glucocorticoid receptors (GR) on dendritic shafts and soma "
                     "(cytoplasmic then nuclear). Catabolic hormone: in chronic high levels "
                     "physically withers dendrite branches in hippocampus/prefrontal cortex. "
                     "Also sensitises NMDA receptors, making them hyper-reactive to the next "
                     "glutamate pulse — a destructive feedback loop. Downstream of the "
                     "glutamate→HPA axis cascade: controlling glutamate first is the single "
                     "highest-leverage intervention to prevent cortisol 'acid leak'."),
    "SubstanceP":   ("CO-RELEASED with glutamate from the presynaptic terminal. Binds NK1 "
                     "receptors on the soma and dendritic arbour. Amplifies NMDA receptor "
                     "opening duration, turning a 'spark' into a 'long-term burn'. Triggers "
                     "neurogenic inflammation (vasodilation, cytokines). NK1 receptors "
                     "internalize and remain active for hours after a burst — explaining why "
                     "distress outlasts the triggering event. Explains the urge to use physical "
                     "pain to override unbearable mental pain."),
    "Dynorphin":    ("RELEASED from soma/dendrites under extreme stress. Binds κ-opioid (KOR) "
                     "receptors. Unlike endorphins (which produce euphoria), dynorphins produce "
                     "dysphoria, dissociation, and emotional numbness. The brain's emergency "
                     "'circuit breaker' — when glutamate and Substance P have overwhelmed the "
                     "system, dynorphins flip the breaker: you feel hollow, detached, 'ghosted' "
                     "from your own body. Protective in the short term; chronically elevated "
                     "dynorphins contribute to depression and anhedonia."),
    "BDNF":         ("BRAIN-DERIVED NEUROTROPHIC FACTOR — released at dendritic spines (TrkB "
                     "receptor activation). Promotes synaptogenesis, spine growth, and long-term "
                     "potentiation. The 'fertilizer' of the brain. Triggered by controlled "
                     "bursts of AMPA-mediated signalling (the adaptive plasticity DXM enables "
                     "by re-routing glutamate away from NMDA). Cortisol chronically suppresses "
                     "BDNF expression — another reason controlling glutamate first is critical."),
}

# Short labels tied to the central thesis: glutamate is the master lever.
MOLECULE_LABELS = {
    "Glutamate":      "GLUTAMATE\nMaster excitatory lever. \nExcess → Ca²⁺ flood → excitotoxic cell death.",
    "GABA":           "GABA\nGlutamate's brake. \nOpens Cl⁻ channels → hyperpolarises → silences firing.",
    "DXM":            "DXM  (Dextrorphan)\nNMDA channel blocker. Lubricates\nthe cleft — Ca²⁺ dampened, signal preserved.",
    "Gabapentin":     "GABAPENTIN\nCa²⁺ channel throttle (α₂δ). \nLess Ca²⁺ in → less glutamate out.",
    "Pregabalin":     "PREGABALIN\nPrecision Ca²⁺ restrictor (6× Gab).\nHard-caps glutamate output volume.",
    "Buspirone":      "BUSPIRONE\n5-HT1A thermostat sensor. Network\nsignal: 'glutamate pressure is enough.'",
    "Seroquel":       "SEROQUEL  (Quetiapine)\nD2/5-HT2A/H1 multi-damper. \nAbsorbs glutamate-driven thermal runaway.",
    "Norepinephrine": "NOREPINEPHRINE\nβ-adrenergic stress amplifier. \nTurns up glutamate pressure at the source.",
    "Cortisol":       "CORTISOL\nGlutamate storm exhaust. Withers\ndendrites & sensitises NMDA → feedback loop.",
    "SubstanceP":     "SUBSTANCE P\nCo-released with glutamate. \nProlongs NMDA burn — turns spark into fire.",
    "Dynorphin":      "DYNORPHIN\nκ-opioid emergency shutoff. \nGlutamate overload → dissociation & numbness.",
    "BDNF":           "BDNF\nPlasticity reward of managed glutamate. \nControlled signal → synaptic growth via TrkB.",
}

# Camera position — text faces toward it for readability
CAM_POS = Vector((18.0, -22.0, 12.0))

def add_molecule_marker(name, location, mat_key, radius=0.25, description=""):
    """
    Place a glowing sphere + a 3D text label at 'location'.
    The text is billboard-oriented toward the camera and converted to mesh
    so it is included in the final joined export.
    Returns the sphere object.
    """
    loc = Vector(location)

    # ── Sphere ─────────────────────────────────────────────────
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=radius, location=loc, segments=12, ring_count=8)
    mol = bpy.context.active_object
    mol.name = f"MOL_{name}"
    apply_mat(mol, MAT[mat_key])
    bpy.ops.object.shade_smooth()
    mol["molecule_name"] = name
    mol["description"]   = description

    # ── 3D text label ──────────────────────────────────────────
    label_key = name.split("_")[0]   # strip positional suffixes like _GR_0
    body_text  = MOLECULE_LABELS.get(label_key,
                     MOLECULE_LABELS.get(name, name))

    # Position label above and slightly offset from the sphere
    label_pos  = loc + Vector((0.0, 0.0, radius + 0.45))

    bpy.ops.object.text_add(location=label_pos)
    txt = bpy.context.active_object
    txt.name = f"LBL_{name}"
    txt.data.body          = body_text
    txt.data.size          = 0.28
    txt.data.align_x       = 'CENTER'
    txt.data.space_line    = 1.1

    # Orient text face (+Z) toward camera so it's readable from camera POV
    to_cam = (CAM_POS - label_pos).normalized()
    txt.rotation_euler = rotation_to_vector(to_cam)

    # Use the same emissive material as the sphere
    if txt.data.materials:
        txt.data.materials[0] = MAT[mat_key]
    else:
        txt.data.materials.append(MAT[mat_key])

    # Convert to mesh immediately so it's joinable
    set_active(txt)
    bpy.ops.object.convert(target='MESH')

    return mol


def add_molecule_stalk(base, tip, mat_key):
    """Thin line from neuron surface to molecule sphere."""
    vr = [(Vector(base), 0.04), (Vector(tip), 0.04)]
    add_skin_skeleton(f"Stalk_{mat_key}_{round(tip[0],1)}", vr, subdiv=0, mat=MAT[mat_key])


# ============================================================
# 4.  SOMA
# ============================================================
bpy.ops.mesh.primitive_uv_sphere_add(
    radius=2.8, location=(0, 0, 0), segments=48, ring_count=32)
soma = bpy.context.active_object
soma.name = "Soma"
bm_s = bmesh.new()
bm_s.from_mesh(soma.data)
for v in bm_s.verts:
    v.co += v.normal * random.gauss(0, 0.18)
bm_s.to_mesh(soma.data)
bm_s.free()
soma.data.update()
apply_mat(soma, MAT['soma'])
bpy.ops.object.shade_smooth()
soma.modifiers.new("Subsurf", 'SUBSURF').levels = 2


# ============================================================
# 5.  NUCLEUS
# ============================================================
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.1, location=(0.2, 0.1, 0.15))
nucleus = bpy.context.active_object
nucleus.name = "Nucleus"
apply_mat(nucleus, MAT['nucleus'])
bpy.ops.object.shade_smooth()


# ============================================================
# 6.  AXON HILLOCK
# ============================================================
HILLOCK_DIR = Vector((1.0, -0.4, -0.3)).normalized()
SOMA_EXIT   = HILLOCK_DIR * 2.6
HILLOCK_END = HILLOCK_DIR * 4.8

bpy.ops.mesh.primitive_cone_add(
    vertices=24, radius1=1.4, radius2=0.55, depth=2.3,
    location=((SOMA_EXIT + HILLOCK_END) * 0.5))
hillock = bpy.context.active_object
hillock.name = "Axon_Hillock"
apply_mat(hillock, MAT['hillock'])
bpy.ops.object.shade_smooth()
hillock.rotation_euler = rotation_to_vector(HILLOCK_DIR)
hillock.modifiers.new("Subsurf", 'SUBSURF').levels = 2


# ============================================================
# 7.  AXON  (Bézier S-curve)
# ============================================================
AXON_START = HILLOCK_END
AXON_END   = Vector((22.0, -8.0, -3.0))

def axon_point(t):
    P0, P1 = AXON_START, Vector((8,  -1,  -2))
    P2, P3 = Vector((16, -10,  1)), AXON_END
    u = 1.0 - t
    return (u**3)*P0 + 3*(u**2)*t*P1 + 3*u*(t**2)*P2 + (t**3)*P3

AXON_SEGS = 40
axon_vr   = [(axon_point(i / AXON_SEGS), 0.38) for i in range(AXON_SEGS + 1)]
_, ob_axon = add_skin_skeleton("Axon", axon_vr, subdiv=2, mat=MAT['soma'])


# ============================================================
# 8.  MYELIN SHEATHS + NODES OF RANVIER
# ============================================================
NUM_MYELIN   = 7
MYELIN_START = 0.18
MYELIN_END   = 0.87

for i in range(NUM_MYELIN):
    t_c = MYELIN_START + (i + 0.5) * (MYELIN_END - MYELIN_START) / NUM_MYELIN
    center  = axon_point(t_c)
    tangent = (axon_point(min(t_c + 0.01, 1.0)) -
               axon_point(max(t_c - 0.01, 0.0))).normalized()

    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=1.0, location=center, segments=24, ring_count=16)
    sheath = bpy.context.active_object
    sheath.name = f"Myelin_{i}"
    apply_mat(sheath, MAT['myelin'])
    bpy.ops.object.shade_smooth()
    sheath.scale = (0.65, 0.65, 1.65)
    sheath.rotation_euler = rotation_to_vector(tangent)

    if i < NUM_MYELIN - 1:
        t_n  = MYELIN_START + (i + 1) * (MYELIN_END - MYELIN_START) / NUM_MYELIN
        n_pt = axon_point(t_n)
        tang2 = (axon_point(min(t_n+0.01,1.0)) -
                 axon_point(max(t_n-0.01,0.0))).normalized()
        bpy.ops.mesh.primitive_torus_add(
            location=n_pt, major_radius=0.48, minor_radius=0.12,
            major_segments=20, minor_segments=10)
        ranvier = bpy.context.active_object
        ranvier.name = f"Ranvier_{i}"
        apply_mat(ranvier, MAT['ranvier'])
        ranvier.rotation_euler = rotation_to_vector(tang2)


# ============================================================
# 9.  AXON TERMINAL  (presynaptic boutons + Ca²⁺ channels)
# ============================================================
TERM_BASE = axon_point(1.0)
TERM_DIR  = (axon_point(1.0) - axon_point(0.95)).normalized()

# Store terminal positions for molecule placement
BOUTON_POSITIONS = []
NUM_TERM_BRANCHES = 6

for i in range(NUM_TERM_BRANCHES):
    angle = (i / NUM_TERM_BRANCHES) * math.tau + random.uniform(-0.3, 0.3)
    perp  = Vector((math.cos(angle)*0.8, math.sin(angle)*0.8, random.uniform(-0.4, 0.4)))
    branch_dir = (TERM_DIR + perp).normalized()
    length     = random.uniform(2.8, 4.5)

    n_segs = 5
    b_pos  = TERM_BASE.copy()
    b_vr   = [(b_pos.copy(), 0.35)]
    for j in range(1, n_segs + 1):
        t     = j / n_segs
        b_pos = b_pos + branch_dir * (length / n_segs) + \
                Vector((random.gauss(0, 0.12), random.gauss(0, 0.12), random.gauss(0, 0.08)))
        b_vr.append((b_pos.copy(), 0.35*(1.0-0.45*t)+0.08))
    add_skin_skeleton(f"Term_Branch_{i}", b_vr, subdiv=1, mat=MAT['soma'])
    tip = b_pos.copy()
    BOUTON_POSITIONS.append((tip, branch_dir.copy()))

    # Bouton sphere
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.62, location=tip, segments=20, ring_count=14)
    bouton = bpy.context.active_object
    bouton.name = f"Bouton_{i}"
    apply_mat(bouton, MAT['terminal'])
    bpy.ops.object.shade_smooth()
    bouton.scale = (1.0, 1.0, 0.6)
    bouton.rotation_euler = rotation_to_vector(branch_dir)

    # Vesicle cluster
    for k in range(random.randint(8, 14)):
        offset = Vector((random.gauss(0, 0.28), random.gauss(0, 0.28), random.gauss(0, 0.18)))
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.09, location=tip + offset,
                                              segments=8, ring_count=6)
        ves = bpy.context.active_object
        ves.name = f"Vesicle_{i}_{k}"
        apply_mat(ves, MAT['vesicle'])
        bpy.ops.object.shade_smooth()

    # Ca²⁺ channel spikes (active zone)
    face_up    = Vector((0,0,1)) if abs(branch_dir.dot(Vector((0,0,1)))) < 0.9 else Vector((1,0,0))
    face_right = branch_dir.cross(face_up).normalized()
    face_up    = face_right.cross(branch_dir).normalized()
    for c in range(random.randint(3, 5)):
        ca_angle  = (c / 5) * math.tau + random.uniform(-0.4, 0.4)
        spread    = random.uniform(0.15, 0.45)
        sv        = (math.cos(ca_angle)*face_right + math.sin(ca_angle)*face_up) * spread
        ca_base   = tip + sv + branch_dir * 0.45
        ca_tip_pt = ca_base + branch_dir * random.uniform(0.32, 0.55)
        add_skin_skeleton(f"CaChannel_{i}_{c}", [(ca_base, 0.06), (ca_tip_pt, 0.04)],
                          subdiv=1, mat=MAT['channel'])
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.09, location=ca_tip_pt, segments=8, ring_count=6)
        pore = bpy.context.active_object
        pore.name = f"CaPore_{i}_{c}"
        apply_mat(pore, MAT['channel'])
        bpy.ops.object.shade_smooth()


# ============================================================
# 10.  DENDRITES  (3-level + spines)
# ============================================================
def add_spine(base_pos, direction, length=0.5, neck_r=0.07, head_r=0.15):
    vr = [(base_pos, neck_r), (base_pos + direction*length*0.6, neck_r),
          (base_pos + direction*length, neck_r)]
    add_skin_skeleton("Spine", vr, subdiv=1, mat=MAT['soma'])
    bpy.ops.mesh.primitive_uv_sphere_add(
        radius=head_r, location=base_pos + direction*length)
    head = bpy.context.active_object
    head.name = "Spine_Head"
    apply_mat(head, MAT['soma'])
    bpy.ops.object.shade_smooth()
    return base_pos + direction * length  # return tip for BDNF placement


DEND_ANGLES = [
    (math.radians(a), math.radians(e))
    for a, e in [
        (150,  20), (200, -5), (240,  30),
        (280, -20), (310, 15), ( 95,  10),
        (120, -30), (170,  45),
    ]
]

# Store some dendrite spine tips for BDNF + cortisol markers
SPINE_TIPS     = []
DEND_SHAFT_PTS = []

for d_idx, (azimuth, elevation) in enumerate(DEND_ANGLES):
    dx   = math.cos(elevation) * math.cos(azimuth)
    dy   = math.cos(elevation) * math.sin(azimuth)
    dz   = math.sin(elevation)
    ddir = Vector((dx, dy, dz)).normalized()

    trunk_len  = random.uniform(4.5, 7.0)
    v_pos      = Vector((0.0, 0.0, 0.0))
    tr_vr      = [(v_pos.copy(), 1.0)]
    for s in range(1, 6):
        t     = s / 5
        v_pos = v_pos + ddir * (trunk_len / 5) + \
                Vector((random.gauss(0, 0.25*t), random.gauss(0, 0.25*t), random.gauss(0, 0.15*t)))
        tr_vr.append((v_pos.copy(), 0.75*(1.0-0.55*t)+0.12))
    trunk_pts, _ = add_skin_skeleton(
        f"Dendrite_Primary_{d_idx}", tr_vr, subdiv=2, mat=MAT['soma'])
    DEND_SHAFT_PTS.append(trunk_pts[len(trunk_pts)//2])

    for _ in range(random.randint(2, 5)):
        idx    = random.randint(1, len(trunk_pts)-1)
        sp_dir = Vector((random.gauss(0,1), random.gauss(0,1), random.gauss(0,1))).normalized()
        tip    = add_spine(trunk_pts[idx], sp_dir, length=random.uniform(0.35, 0.65))
        SPINE_TIPS.append(tip)

    for b_idx in range(2):
        split   = random.randint(len(trunk_pts)//2, len(trunk_pts)-2)
        b_start = trunk_pts[split]
        b_dir   = (ddir + Vector((random.gauss(0, 0.6), random.gauss(0, 0.6),
                                  random.gauss(0, 0.4)))).normalized()
        b_len   = random.uniform(2.0, 4.0)
        b_pos   = b_start.copy()
        b_vr    = [(b_pos.copy(), 0.28)]
        for s in range(1, 5):
            t     = s / 4
            b_pos = b_pos + b_dir * (b_len/4) + \
                    Vector((random.gauss(0,0.2), random.gauss(0,0.2), random.gauss(0,0.15)))
            b_vr.append((b_pos.copy(), 0.22*(1.0-0.6*t)+0.05))
        b_pts, _ = add_skin_skeleton(
            f"Dendrite_Secondary_{d_idx}_{b_idx}", b_vr, subdiv=2, mat=MAT['soma'])

        for _ in range(random.randint(1, 3)):
            idx    = random.randint(0, len(b_pts)-1)
            sp_dir = Vector((random.gauss(0,1), random.gauss(0,1), random.gauss(0,1))).normalized()
            tip    = add_spine(b_pts[idx], sp_dir, length=random.uniform(0.3, 0.5))
            SPINE_TIPS.append(tip)

        for t_idx in range(random.randint(1, 3)):
            t_start = b_pts[-1]
            t_dir   = (b_dir + Vector((random.gauss(0,0.8), random.gauss(0,0.8),
                                       random.gauss(0,0.5)))).normalized()
            t_len   = random.uniform(1.0, 2.2)
            t_pos   = t_start.copy()
            t_vr    = [(t_pos.copy(), 0.1)]
            for s in range(1, 4):
                t_pos = t_pos + t_dir*(t_len/3) + \
                        Vector((random.gauss(0,0.1), random.gauss(0,0.1), 0))
                t_vr.append((t_pos.copy(), max(0.04, 0.1-s*0.02)))
            add_skin_skeleton(
                f"Dendrite_Tertiary_{d_idx}_{b_idx}_{t_idx}", t_vr, subdiv=1, mat=MAT['soma'])


# ============================================================
# 11.  REGULATORY MOLECULE MARKERS
#      — placed at anatomically correct sites
# ============================================================

desc = MOLECULE_DESCRIPTIONS   # shorthand

# ── A.  AXON TERMINAL MOLECULES ─────────────────────────────────────────────
#   The synaptic cleft: glutamate, DXM (NMDA block), Gabapentin/Pregabalin (VGCC),
#   Norepinephrine (β presynaptic), Substance P (co-release)

# Use first 3 bouton positions for variety
for i, (bouton_tip, b_dir) in enumerate(BOUTON_POSITIONS[:6]):
    outward = b_dir * 1.2   # push marker outward from bouton surface

    if i == 0:
        # GLUTAMATE — in the synaptic cleft just past the bouton tip
        glut_pos = bouton_tip + b_dir * 1.0
        add_molecule_marker("Glutamate", glut_pos, "glutamate", radius=0.3,
                            description=desc["Glutamate"])
        add_molecule_stalk(bouton_tip, glut_pos, "glutamate")

    elif i == 1:
        # DXM — inside the NMDA receptor channel (postsynaptic face of cleft)
        dxm_pos = bouton_tip + b_dir * 1.4 + Vector((0, 0, 0.2))
        add_molecule_marker("DXM_NMDABlock", dxm_pos, "dxm", radius=0.28,
                            description=desc["DXM"])
        add_molecule_stalk(bouton_tip + b_dir * 0.65, dxm_pos, "dxm")

    elif i == 2:
        # GABAPENTIN — on the Ca²⁺ channel (α₂δ subunit) on presynaptic membrane
        gab_pos = bouton_tip - b_dir * 0.5 + Vector((0.3, 0.3, 0.5))
        add_molecule_marker("Gabapentin_VGCC", gab_pos, "gabapentin", radius=0.26,
                            description=desc["Gabapentin"])
        add_molecule_stalk(bouton_tip, gab_pos, "gabapentin")

    elif i == 3:
        # PREGABALIN — same Ca²⁺ channel site, shown alongside
        preg_pos = bouton_tip - b_dir * 0.4 + Vector((-0.4, 0.3, 0.45))
        add_molecule_marker("Pregabalin_VGCC", preg_pos, "pregabalin", radius=0.26,
                            description=desc["Pregabalin"])
        add_molecule_stalk(bouton_tip, preg_pos, "pregabalin")

    elif i == 4:
        # NOREPINEPHRINE — β-adrenergic receptor on presynaptic terminal membrane
        norep_pos = bouton_tip - b_dir * 0.7 + Vector((0.0, -0.5, 0.4))
        add_molecule_marker("Norepinephrine_Beta", norep_pos, "norep", radius=0.27,
                            description=desc["Norepinephrine"])
        add_molecule_stalk(bouton_tip, norep_pos, "norep")

    elif i == 5:
        # SUBSTANCE P — co-released with glutamate into the cleft
        sp_pos = bouton_tip + b_dir * 0.9 + Vector((0.2, 0.0, -0.3))
        add_molecule_marker("SubstanceP_NK1", sp_pos, "substancep", radius=0.27,
                            description=desc["SubstanceP"])
        add_molecule_stalk(bouton_tip, sp_pos, "substancep")


# ── B.  SOMA SURFACE MOLECULES ──────────────────────────────────────────────
#   Buspirone (5-HT1A), Seroquel (D2/5HT2A/H1), Dynorphin (κ-opioid),
#   Substance P NK1 (soma), GABA (inhibitory input to soma)

soma_molecule_sites = [
    # (direction_from_centre, mat_key, name, radius)
    (Vector((-1.0,  0.5,  0.8)).normalized(), "buspirone",   "Buspirone_5HT1A", 0.28,  desc["Buspirone"]),
    (Vector((-0.5, -1.0,  0.3)).normalized(), "seroquel",    "Seroquel_D2_5HT2A_H1", 0.30, desc["Seroquel"]),
    (Vector(( 0.8, -0.8, -0.5)).normalized(), "dynorphin",   "Dynorphin_KOR",   0.26,  desc["Dynorphin"]),
    (Vector((-0.9, -0.3, -0.7)).normalized(), "substancep",  "SubstanceP_NK1_Soma", 0.24, desc["SubstanceP"]),
    (Vector(( 0.3,  1.0,  0.2)).normalized(), "gaba",        "GABA_InhibSynapse", 0.27, desc["GABA"]),
]

for direction, mat_k, mol_name, rad, mol_desc in soma_molecule_sites:
    surface_pt = direction * 2.85          # soma radius ~2.8
    marker_pt  = direction * 4.0           # float above surface
    add_molecule_marker(mol_name, marker_pt, mat_k, radius=rad, description=mol_desc)
    add_molecule_stalk(surface_pt, marker_pt, mat_k)


# ── C.  DENDRITIC SHAFT MOLECULES ───────────────────────────────────────────
#   Cortisol (glucocorticoid receptors on shaft)
#   GABA inhibitory synapses (additional, on shaft not soma)

# Cortisol on 3 different dendrite shaft midpoints
cortisol_indices = [0, 3, 6]
for ci in cortisol_indices:
    if ci < len(DEND_SHAFT_PTS):
        shaft_pt = DEND_SHAFT_PTS[ci]
        offset   = Vector((random.gauss(0, 0.3), random.gauss(0, 0.3), 1.4))
        cort_pt  = shaft_pt + offset
        add_molecule_marker(f"Cortisol_GR_{ci}", cort_pt, "cortisol", radius=0.25,
                            description=desc["Cortisol"])
        add_molecule_stalk(shaft_pt, cort_pt, "cortisol")

# GABA on 2 additional dendrite shafts
gaba_indices = [1, 5]
for gi in gaba_indices:
    if gi < len(DEND_SHAFT_PTS):
        shaft_pt = DEND_SHAFT_PTS[gi]
        offset   = Vector((random.gauss(0, 0.4), random.gauss(0, 0.4), -1.3))
        gaba_pt  = shaft_pt + offset
        add_molecule_marker(f"GABA_DendrSynapse_{gi}", gaba_pt, "gaba", radius=0.25,
                            description=desc["GABA"])
        add_molecule_stalk(shaft_pt, gaba_pt, "gaba")


# ── D.  DENDRITIC SPINE MOLECULES ───────────────────────────────────────────
#   BDNF at TrkB receptors on spine heads

bdnf_count = min(8, len(SPINE_TIPS))
random.shuffle(SPINE_TIPS)
for k, spine_tip in enumerate(SPINE_TIPS[:bdnf_count]):
    offset   = Vector((random.gauss(0, 0.1), random.gauss(0, 0.1), 0.5))
    bdnf_pt  = spine_tip + offset
    add_molecule_marker(f"BDNF_TrkB_{k}", bdnf_pt, "bdnf", radius=0.20,
                        description=desc["BDNF"])
    # tiny stalk from spine head to BDNF marker
    add_molecule_stalk(spine_tip, bdnf_pt, "bdnf")


# ============================================================
# 12.  JOIN ALL INTO ONE MESH OBJECT
# ============================================================
# Convert any remaining FONT/CURVE objects (text labels) to mesh first
bpy.ops.object.select_all(action='DESELECT')
for ob in bpy.data.objects:
    if ob.type in ('FONT', 'CURVE'):
        set_active(ob)
        try:
            bpy.ops.object.convert(target='MESH')
        except Exception:
            pass

# Apply all modifiers on mesh objects
bpy.ops.object.select_all(action='DESELECT')
for ob in bpy.data.objects:
    if ob.type == 'MESH':
        ob.select_set(True)

for ob in list(bpy.context.selected_objects):
    set_active(ob)
    for mod in list(ob.modifiers):
        try:
            bpy.ops.object.modifier_apply(modifier=mod.name)
        except Exception:
            pass

# Join everything
bpy.ops.object.select_all(action='DESELECT')
for ob in bpy.data.objects:
    if ob.type == 'MESH':
        ob.select_set(True)

if bpy.context.selected_objects:
    bpy.context.view_layer.objects.active = bpy.context.selected_objects[0]
    bpy.ops.object.join()
    joined = bpy.context.active_object
    joined.name = "Neuron_Complete"
    vcount = len(joined.data.vertices)
    pcount = len(joined.data.polygons)
    print(f"✅  Joined: {joined.name}  ({vcount:,} verts, {pcount:,} polys)")


# ============================================================
# 13.  CAMERA + LIGHTING
# ============================================================
bpy.ops.object.camera_add(location=(18, -22, 12))
cam = bpy.context.active_object
cam.name = "Neuron_Camera"
cam.rotation_euler = (math.radians(58), 0, math.radians(42))
bpy.context.scene.camera = cam

bpy.ops.object.light_add(type='SUN', location=(12, -8, 18))
sun = bpy.context.active_object
sun.data.energy = 4.0
sun.data.color  = (1.0, 0.95, 0.88)
sun.rotation_euler = (math.radians(50), 0, math.radians(-30))

bpy.ops.object.light_add(type='AREA', location=(-10, 15, 5))
fill = bpy.context.active_object
fill.data.energy = 800.0
fill.data.color  = (0.6, 0.75, 1.0)
fill.data.size   = 10.0

bpy.ops.object.light_add(type='POINT', location=(-5, -15, -3))
rim = bpy.context.active_object
rim.data.energy = 500.0
rim.data.color  = (0.9, 0.8, 0.6)


# ============================================================
# 14.  EXPORT
# ============================================================
import sys, os
export_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "Neuron_Anatomical.obj")
bpy.ops.object.select_all(action='DESELECT')
for ob in bpy.data.objects:
    if ob.type == 'MESH':
        ob.select_set(True)
bpy.ops.wm.obj_export(filepath=export_path, export_selected_objects=True)

print(f"\n✅  Exported → {export_path}")
print("\nMolecule markers summary:")
for name, desc_text in MOLECULE_DESCRIPTIONS.items():
    print(f"  {name:16s} — {desc_text[:80]}...")
print()
sys.stdout.flush()
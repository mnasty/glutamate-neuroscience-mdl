# Human Neuron 3D Model

A procedurally generated, anatomically-correct 3D model of a single human neuron built with Blender Python. The model captures the key anatomical structures and places **regulatory molecule markers** at their correct interaction sites on the cell — making it useful both as a scientific visualization and as an educational tool for understanding how drugs and endogenous chemicals modulate neural function.

## What We're Building

The brain's basic unit of computation is a single neuron — a wildly complex electrochemical machine. This project generates one in 3D, then layers on the molecular "players" that regulate how it fires, how it gets damaged, and how it heals.

The conversation that drove this project explored how substances like DXM, Gabapentin, Buspirone, and Seroquel push and pull on the glutamate system — the brain's primary excitatory force — and what happens when that force is managed well versus when it runs unchecked (excitotoxicity, cortisol cascade, dendritic withering, cognitive decline).

## Running the Script

```bash
# Headless (no GUI)
blender --background --python neuron_model.py

# Or open neuron_model.py in Blender's Scripting workspace and click Run Script
```

Output: `Neuron_Anatomical.obj` — a single joined mesh ready for import into any 3D application.

## Anatomical Structures

| Structure | Description |
|---|---|
| **Soma** | Cell body — large displaced UV sphere with irregular organic surface |
| **Nucleus** | Spherical organelle inside the soma |
| **Axon Hillock** | Tapered cone connecting soma to axon — the action potential initiation zone |
| **Axon** | Long myelinated process following a Bézier S-curve |
| **Myelin Sheaths** | 7 ellipsoid segments correctly oriented along the axon tangent |
| **Nodes of Ranvier** | Torus rings at each inter-sheath gap — saltatory conduction sites |
| **Dendrites** | 8 primary trunks with 3 levels of branching and dendritic spines |
| **Axon Terminal** | 6 branches with boutons, synaptic vesicle clusters, and Ca²⁺ channel spikes |

## Regulatory Molecule Markers

Each molecule is rendered as a **glowing emissive sphere** at its anatomically correct interaction site, connected to the neuron surface by a thin stalk. Clicking any `MOL_*` object in Blender's outliner and opening **Item → Custom Properties** (N panel) shows the full biochemical description.

| Molecule | Site | Color | Mechanism |
|---|---|---|---|
| **Glutamate** | Synaptic cleft (bouton tip) | 🔴 Red | Primary excitatory neurotransmitter; binds AMPA/NMDA receptors. In excess → excitotoxicity via Ca²⁺ overload. |
| **GABA** | Inhibitory synapses on soma & dendritic shafts | 💙 Blue | Primary inhibitory neurotransmitter. Opens Cl⁻ channels, hyperpolarises the cell. The "brake" to glutamate's "gas." |
| **DXM** | Inside NMDA channel pore | 🟣 Purple | Non-competitive NMDA antagonist — sits in the channel mouth, reducing Ca²⁺ flood without fully silencing the receptor. Enables adaptive plasticity by re-routing signal to AMPA. |
| **Gabapentin** | α₂δ VGCC subunit (presynaptic terminal) | 🟢 Green | Binds α₂δ subunit of voltage-gated Ca²⁺ channels. Less Ca²⁺ influx → less glutamate released. "Banana in the tailpipe" — chronic use risks synaptic thinning via thrombospondin blockade. |
| **Pregabalin** | Same VGCC α₂δ site | 💚 Teal | Same mechanism as Gabapentin but ~6× higher binding affinity and ~90% bioavailability. Precision restrictor vs Gabapentin's imprecise clog. Higher dementia risk at chronic high doses. |
| **Norepinephrine** | β-adrenergic receptors on axon terminal | 🟠 Orange | Stress signal that strongly facilitates glutamate release via cAMP/PKA cascade. Turns up the pressure before it reaches the synapse. Beta-blockers antagonise this site. |
| **Substance P** | Co-released at cleft + NK1 receptors on soma | 🩷 Hot pink | Co-released with glutamate. Amplifies NMDA opening duration, triggers neurogenic inflammation. NK1 receptors internalize and stay active for hours — why distress outlasts its trigger. |
| **Buspirone** | 5-HT1A autoreceptors on soma surface | 🟡 Yellow | Partial agonist at serotonin autoreceptors. Tells the neuron "back off" via network-level signalling rather than mechanical jamming. Cognitively safe long-term — no calcium channel interference. |
| **Seroquel** | D2/5-HT2A/H1 receptors on soma | 🟣 Violet | Multi-receptor antagonist. Simultaneously damps dopamine, serotonin, and histamine signalling. "High-viscosity synthetic oil" for a hyperdrive brain — absorbs thermal runaway without stopping the engine. |
| **Dynorphins** | κ-opioid receptors on soma | 🔵 Dark blue | Emergency circuit breaker released under extreme stress. Produces dysphoria/dissociation (not euphoria). The brain "ghosting" itself to prevent complete collapse from excitotoxic overload. |
| **Cortisol** | Glucocorticoid receptors on dendritic shafts | 🟫 Brown | Catabolic stress hormone downstream of the glutamate→HPA axis cascade. Physically withers dendrites in the hippocampus and sensitises NMDA receptors — creating a destructive feedback loop. Controlling glutamate first breaks the chain. |
| **BDNF** | TrkB receptors on dendritic spine heads | 🟩 Bright green | Brain-Derived Neurotrophic Factor — released at spine heads during healthy plasticity. "Fertilizer" for the brain. Triggered by controlled AMPA-mediated bursts. Suppressed by chronic cortisol. |

## Key Insight

The pharmacological conversation that this model visualises comes down to one core idea: **the glutamate system is the master lever**. By managing it first — whether via NMDA antagonism (DXM), Ca²⁺ channel throttling (Gabapentin/Pregabalin), or autoreceptor feedback (Buspirone) — you prevent the entire downstream cascade: Cortisol acid leak, Substance P inflammation, Dynorphin shutdown, and loss of BDNF-driven plasticity.

The goal of the model is to make that cascade **visible in 3D space** on the actual cell where it happens.

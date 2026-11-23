# 0002. Additive C++ entry points where pymol3 needs data cmd cannot give

## Context

ADR 0001 keeps this repository's additions in `pymol3` and upstream PyMOL
files untouched. Two planned features need data that PyMOL's Python API does
not expose at all. The Objects panel (`.opp/plans/features/objects-panel.md`)
needs the group membership of every object, the open state of groups, the
current mouse bindings and the measured frame rate. The embeddable viewer
widget (`.opp/plans/features/embeddable-widget.md`) needs to know which atom
the user picked in every mouse mode, while a wizard may be active. The only
Python routes are a full `get_session` on every tick, a binding table rebuilt
from a list that misses custom bindings, or taking over the wizard slot.

## Decision

Upstream C++ may gain new entry points when `pymol3` needs data that `cmd`
cannot give. Each addition:

- adds only: no existing C++ or Python function changes its behaviour,
  signature or output;
- sits in a block marked `BEGIN PYMOL+ ADDITION` / `END PYMOL+ ADDITION`,
  in `layer4/Cmd.cpp` (the `_cmd` entry) and the layer file that holds the
  data;
- is reached from Python only through `pymol3` (for example
  `pymol3.query`), never through `pymol.cmd`, so `modules/pymol/` stays
  untouched;
- follows the family C++ style.

The first additions are read-only getters (object tree, mouse bindings,
frame rate) and a pick queue that records picks without changing how PyMOL
handles them.

## Consequences

The Objects panel and the widget get exact data without per-tick sessions
or wizard conflicts, and wheel users can use the same `pymol3` functions.
Syncing with Schrödinger's sources now has marked C++ blocks to carry over;
the markers make them easy to find. The rest of ADR 0001 stands: Python
additions still live in `pymol3`, and upstream Python files stay untouched.

Rejected alternatives:

- Approximating from Python (full `get_session` every tick, bindings from
  `controlling.mode_dict`, no frame rate): slow with large sessions and
  wrong for custom bindings.
- A pick mode that takes over the wizard slot: blocks user wizards such as
  Measurement while it is on.
- New `cmd` functions in `modules/pymol/`: would edit upstream Python, which
  ADR 0001 keeps untouched.

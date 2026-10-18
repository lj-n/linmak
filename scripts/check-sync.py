#!/usr/bin/env python3
"""Check that config/glove80.json (Layout Editor) and config/glove80.keymap describe the same layout.

Compares layer names/order, every key binding and all combos. Exits non-zero on drift.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
keymap = (ROOT / "config/glove80.keymap").read_text()
layout = json.loads((ROOT / "config/glove80.json").read_text())
names = layout["layer_names"]

# Behaviors whose parameter at the given index is a layer (an index in the JSON, LAYER_<name> in the keymap)
LAYER_PARAM = {"&mo": 0, "&to": 0, "&tog": 0, "&thumb_v2_TKZ": 0, "&space_v3_TKZ": 0, "&mod_tab_chord_v2_TKZ": 1}
# Bindings the Layout Editor rewrites on export
EXPORT_ALIAS = {"&magic": "&magic LAYER_Magic 0", "&reset": "&sys_reset"}


def param(p):
    return f"{p['value']}({','.join(param(x) for x in p['params'])})" if p.get("params") else str(p["value"])


def binding(b):
    if b["value"] in EXPORT_ALIAS and not b.get("params"):
        return EXPORT_ALIAS[b["value"]]
    params = [
        f"LAYER_{names[p['value']]}" if LAYER_PARAM.get(b["value"]) == i and isinstance(p["value"], int) else param(p)
        for i, p in enumerate(b.get("params", []))
    ]
    return " ".join([b["value"], *params])


def tokens(text):
    return [" ".join(t.split()) for t in re.findall(r"&[^&]+", text)]


errors = []

order = re.findall(r"\n\s*layer_(\w+) \{", keymap)
if order != names:
    errors.append(f"layer order differs:\n  keymap: {order}\n  json:   {names}")

for i, name in enumerate(names):
    m = re.search(rf"layer_{name} \{{\s*bindings = <(.*?)>;", keymap, re.S)
    if not m:
        continue
    km, js = tokens(m.group(1)), [binding(b) for b in layout["layers"][i]]
    if len(km) != len(js):
        errors.append(f"{name}: {len(km)} keys in keymap, {len(js)} in json")
        continue
    errors += [f"{name}[{k}]: keymap '{a}' != json '{b}'" for k, (a, b) in enumerate(zip(km, js)) if a != b]

pos = dict(re.findall(r"#define (POS_\w+) (\d+)", keymap))
km_combos = {}
for name, body in re.findall(r"\n\s*combo_(\w+) \{(.*?)\n\s*\};", keymap, re.S):
    keys = re.search(r"key-positions = <(.*?)>", body).group(1).split()
    layers = re.search(r"layers = <(.*?)>", body).group(1).split()
    km_combos[name] = (
        sorted(int(pos.get(k, k)) for k in keys),
        tokens(re.search(r"bindings = <(.*?)>", body).group(1))[0],
        sorted(layers),
    )
js_combos = {
    c["name"]: (sorted(c["keyPositions"]), binding(c["binding"]), sorted(f"LAYER_{names[l]}" for l in c["layers"]))
    for c in layout["combos"]
}
for name in sorted(km_combos.keys() | js_combos.keys()):
    if km_combos.get(name) != js_combos.get(name):
        errors.append(f"combo {name}: keymap {km_combos.get(name)} != json {js_combos.get(name)}")

if errors:
    print("glove80.keymap and glove80.json are out of sync:", *errors, sep="\n  ")
    sys.exit(1)
print(f"in sync: {len(names)} layers, {len(js_combos)} combos")

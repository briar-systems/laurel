#!/usr/bin/env python3
# Enumerate partial record literals: a literal that names fewer fields than its
# record declares. briar-systems/mach#3108 says the unnamed fields hold the
# previous frame's contents rather than zero. See laurel #47.
#
#   python3 tools/partial_literal_sweep.py [repo-root]
#
# Enumerates from record definitions rather than matching text, and resolves
# each literal's qualifier through its file's `use` statements: 84 record names
# collide across laurel and its dependencies, so keying by bare name matches the
# wrong definition and reports nonsense. Array literals (`[2]Rule{a, b}`) are
# excluded; they are not record literals. An unresolvable qualifier is reported
# and skipped rather than guessed at.
import re, glob, os

import sys
ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEP_ROOT = {'mach-std': 'std', 'mach-http': 'http', 'mach-crypto': 'crypto'}

def module_of(path):
    rel = os.path.relpath(path, ROOT)
    parts = rel.split(os.sep)
    if parts[0] == 'src':
        return 'laurel.' + '.'.join(parts[1:])[:-5]
    root = DEP_ROOT.get(parts[1])
    if root is None: return None
    return root + '.' + '.'.join(parts[3:])[:-5]

files = sorted(glob.glob(ROOT + '/src/**/*.mach', recursive=True)) + \
        sorted(glob.glob(ROOT + '/dep/*/src/**/*.mach', recursive=True))

# fully-qualified record definitions: "laurel.cookie.Operation" -> [fields]
defs = {}
texts = {}
for f in files:
    mod = module_of(f)
    if mod is None: continue
    texts[f] = (mod, open(f).read())
    for m in re.finditer(r'^(?:pub )?rec (\w+) \{(.*?)^\}', texts[f][1], re.S | re.M):
        defs[mod + '.' + m.group(1)] = re.findall(r'^\s+(\w+)\s*:', m.group(2), re.M)

def aliases(mod, text):
    # `use a.b.c;` binds `c`; `use X: a.b;` binds `X`
    out = {}
    for m in re.finditer(r'^use\s+(?:(\w+)\s*:\s*)?([\w.]+)\s*;', text, re.M):
        alias, path = m.group(1), m.group(2)
        out[alias if alias else path.split('.')[-1]] = path
    return out

def top_level_named(inner):
    names, depth, tok, i = [], 0, '', 0
    while i < len(inner):
        c = inner[i]
        if c in '{[(': depth += 1
        elif c in '}])': depth -= 1
        if depth == 0 and c == ':' and not inner.startswith('::', i) and not (i and inner[i-1] == ':'):
            m = re.search(r'(\w+)\s*$', tok)
            if m: names.append(m.group(1))
            tok = ''
        elif depth == 0 and c == ',':
            tok = ''
        else:
            tok += c
        i += 1
    return names

findings, unresolved = [], set()
for f, (mod, text) in texts.items():
    if not os.path.relpath(f, ROOT).startswith('src'): continue
    alias = aliases(mod, text)
    for m in re.finditer(r'(?<![\w.\]])((?:[a-z_]\w*)\.)?([A-Z]\w*)\{', text):
        qual, name = m.group(1), m.group(2)
        if qual:
            base = alias.get(qual[:-1])
            key = base + '.' + name if base else None
        else:
            key = mod + '.' + name
        if key is None or key not in defs:
            if qual: unresolved.add(qual + name)
            continue
        start = m.end() - 1
        depth, i = 0, start
        while i < len(text):
            if text[i] == '{': depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0: break
            i += 1
        inner = text[start+1:i]
        total = defs[key]
        named = [n for n in top_level_named(inner) if n in total]
        if len(named) < len(total):
            findings.append((os.path.relpath(f, ROOT), text.count('\n',0,m.start())+1,
                             key, len(named), len(total),
                             [x for x in total if x not in named]))

print("qualified record definitions:", len(defs))
print("unresolved qualifiers:", sorted(unresolved) if unresolved else "none")
print("partial literals:", len(findings))
print()
from collections import Counter
for key, n in Counter(x[2] for x in findings).most_common():
    print(f"  {n:3d}  {key}")
print()
for f, ln, key, n, t, missing in findings:
    print(f"{f}:{ln}  {key}  {n}/{t}  missing: {', '.join(missing)}")

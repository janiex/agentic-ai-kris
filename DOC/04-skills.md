# 4. Skills (Anthropic `SKILL.md` format)

**Loader:** `src/agentic_kris/skills/` · **Packages:** `skills/`

Skills are reusable, model-agnostic capability packages that follow Anthropic's
"Complete Guide to Building Skills for Claude" conventions. An agent loads the
skills it's allowed to use and injects their instructions into its prompt.

## 4.1 Anatomy of a skill package

A skill is a **folder** whose name matches its `name`, containing a `SKILL.md`:

```
skills/
  web-research/
    SKILL.md                 # YAML frontmatter + Markdown instructions
    reference.md             # optional bundled reference (level 3)
    scripts/
      extract_claims.py      # optional bundled executable (level 3)
```

`SKILL.md` frontmatter is a leading `---` fenced YAML block:

```markdown
---
name: web-research
description: >-
  Researches a topic by gathering, cross-checking, and synthesizing ...
  Use when the Researcher agent must investigate a user-assigned subject ...
metadata:
  version: "1.0"
  audience: researcher
---

# Web / knowledge research
... instructions ...
```

**Required fields:** `name`, `description`. Optional: `metadata`,
`allowed-tools`, `license`.

The three shipped examples are `web-research` (Researcher), `critique` (Critic),
and `document-solution` (Summarizer).

## 4.2 Progressive disclosure — the central idea

The guide's key efficiency principle is implemented literally. Defined in
`skills/models.py` (`Skill`) and `skills/loader.py` (`SkillLoader`):

| Level | What | Method | When loaded |
| --- | --- | --- | --- |
| **1 — metadata** | `name` + `description` | `Skill.catalog_entry()`, `SkillLoader.catalog()` | Always (cheap) |
| **2 — instructions** | the `SKILL.md` body | `Skill.body`, `Skill.prompt_block()`, `SkillLoader.prompt_for([...])` | When an agent uses the skill |
| **3 — resources/scripts** | `reference.md`, `scripts/*` | `Skill.resource()`, `Skill.script()`, `SkillLoader.run_script()` | Only on demand |

Why it matters: an orchestrator can know *that* a skill exists (and decide to use
it) from a one-line description, without paying the token cost of its full body —
and never pays for bundled files unless they're actually used.

## 4.3 The loader — `loader.py`

`SkillLoader(skills_dir)` scans the directory once on construction
(`reload()`), parsing every `skills/*/SKILL.md`.

Parsing & validation pipeline:

- `_split_frontmatter(text)` → splits the `---` fenced YAML from the body. Raises
  `SkillError` if the fence is missing or unclosed.
- `_validate(front, folder)` enforces the authoring rules:
  - `name` and `description` are required and must be strings;
  - `name` ≤ 64 chars, lowercase, no spaces (hyphenated);
  - **folder name must equal `name`** (keeps the filesystem self-describing).
- `_parse_skill(dir)` collects `scripts/` files and any other sibling files as
  `resources`, and builds the `Skill`.

Serving methods:

- `catalog()` / `names()` — level-1 views.
- `get(name)` / `get_many(names)` — the full `Skill` object(s).
- `prompt_for(names)` — concatenated `prompt_block()`s, ready to splice into a
  system prompt. This is what `BaseAgent.build_system()` calls.
- `run_script(skill, script, args, timeout=60)` — runs a bundled helper with
  `sys.executable` (cross-platform) and returns its stdout; raises on non-zero
  exit.

## 4.4 How agents use skills

`BaseAgent.build_system()` (see [05-agents-and-registry.md](05-agents-and-registry.md))
appends `loader.prompt_for(self.skill_names)` under a `# Skills available to you`
header. So the Researcher's `web-research` instructions become part of its system
prompt at runtime — level-2 disclosure triggered by the agent declaring the skill
in `skill_names`.

## 4.5 The example script (level 3)

`skills/web-research/scripts/extract_claims.py` is a deterministic helper that
normalises messy retrieved text into de-duplicated bullet points. It's the
canonical "let a script do mechanical work instead of spending model tokens"
pattern: it reads from a file arg or stdin and prints one trimmed sentence per
line.

### 🧪 Experiment — load skills and inspect the disclosure levels

```bash
python -c "
from agentic_kris.skills.loader import SkillLoader
from agentic_kris.config import settings
L = SkillLoader(settings.skills_path)

print('names           :', L.names())
print('level-1 catalog :')
for e in L.catalog():
    print('   ', e['name'], '->', e['description'][:60], '...')

s = L.get('web-research')
print('level-3 scripts :', [p.name for p in s.scripts])
print('level-3 resource:', [p.name for p in s.resources])
print('level-2 body head:')
print(s.body[:200])
"
```

### 🧪 Experiment — render the exact prompt block an agent injects

```bash
python -c "
from agentic_kris.skills.loader import SkillLoader
from agentic_kris.config import settings
L = SkillLoader(settings.skills_path)
print(L.prompt_for(['critique']))      # what the Critic adds to its system prompt
"
```

### 🧪 Experiment — run a bundled level-3 script

```bash
python -c "
from agentic_kris.skills.loader import SkillLoader
from agentic_kris.config import settings
import subprocess, sys
L = SkillLoader(settings.skills_path)
script = L.get('web-research').script('extract_claims.py')
out = subprocess.run([sys.executable, str(script)],
                     input='Fact one. Fact two. Fact one.',
                     capture_output=True, text=True).stdout
print(out)        # de-duplicated bullets
"
```

### 🧪 Experiment — author a new skill and watch it validate

```bash
mkdir -p skills/greeting
cat > skills/greeting/SKILL.md <<'EOF'
---
name: greeting
description: Produces a friendly greeting. Use to demonstrate skill loading.
---
Greet the user warmly in one sentence.
EOF

python -c "
from agentic_kris.skills.loader import SkillLoader
from agentic_kris.config import settings
print('greeting' in SkillLoader(settings.skills_path).names())   # True
"

# Now break a rule to see enforcement (folder != name):
mv skills/greeting skills/hello
python -c "
from agentic_kris.skills.loader import SkillLoader
from agentic_kris.config import settings
try:
    SkillLoader(settings.skills_path)
except Exception as e:
    print('blocked:', e)
"
rm -rf skills/hello
```

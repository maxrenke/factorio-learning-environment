# Factorio TAS + LLM Agent - Research Notes

## Goal

Train an LLM to play Factorio using a TAS run as expert demonstration data, compare against
the FLE baseline, and potentially contribute findings back to the FLE team.

---

## Active Fork

All work lives here: **https://github.com/maxrenke/factorio-learning-environment**
- Cloned to: `C:\Users\m_ren\repos\factorio-learning-environment`
- Upstream: `https://github.com/JackHopkins/factorio-learning-environment`
- Research notes (canonical, more detailed): `research/notes/research-notes.md`

This OneDrive file is a personal reference. The fork is the source of truth.

---

## Key Resources

- **Factorio TAS Generator**: https://github.com/theis999/Factorio-TAS-Generator
- **Steel Axe% TAS mod (v0.3.0, Factorio 1.1, 7:35)**: https://mods.factorio.com/mod/Theis_TAS_Steelaxe2
  - Downloaded to: `C:\Users\m_ren\Downloads\Theis_TAS_Steelaxe2_0.3.0.zip`
  - Extract to: `C:\Users\m_ren\repos\factorio-learning-environment\research\data\tas\`
- **Factorio Learning Environment (FLE)**: https://github.com/JackHopkins/factorio-learning-environment
  - Paper: https://arxiv.org/abs/2503.09617 (Hopkins, Bakler, Khan - March 2025)

---

## TAS File Format

The mod is a Lua mod. Key files inside the zip:

| File | Size | Purpose |
|------|------|---------|
| `steps.lua` | 664KB, 6231 lines | The TAS data - 5721 steps |
| `control.lua` | 64KB | Executor engine |
| `scenarios/steelaxe/blueprint.zip` | 166KB | Fixed map seed |

### Step schema

```lua
step[N] = {{task_id, subtask_id}, "action", ...args}
```

### Action types

| action | signature |
|--------|-----------|
| `walk` | `{x, y}`, `""`, dir_x_hint, dir_y_hint, `[walk_towards=true]` |
| `build` | `{x, y}`, entity_name, direction |
| `mine` | `{x, y}`, max_ticks |
| `craft` | count (-1=max), item_name |
| `take` | `{x, y}`, item, amount (-1=all), inventory_slot |
| `put` | `{x, y}`, item, amount, inventory_slot |
| `tech` | research_name |
| `drop` | `{x, y}`, item |
| `speed` | game_speed_multiplier |

### First 12 steps (illustrative)

```lua
step[1]  = {{1,1}, "walk", {0.0, 0.0}, "", "diagonal", "diagonal"}
step[3]  = {{3,1}, "build", {-1.0, 10.0}, "burner-mining-drill", defines.direction.north}
step[4]  = {{4,1}, "build", {-1.0, 8.0}, "stone-furnace", defines.direction.north}
step[6]  = {{6,1}, "mine", {-2.25, 9.75}, 1000}
step[10] = {{10,1}, "tech", "automation"}
step[11] = {{11,1}, "tech", "steel-processing"}
step[12] = {{12,1}, "tech", "steel-axe"}
step[18] = {{18,1}, "craft", 3, "iron-gear-wheel"}
```

Key pattern: research is queued (steps 10-12) before smelting completes - this is the
ordering knowledge the LLM needs to learn.

---

## Factorio Learning Environment (FLE)

### How it works

- LLM interacts via a **Python REPL loop**: writes Python code each turn, gets stdout/stderr back
- FLE translates Python API calls into Lua/RCON commands sent to a headless Factorio server
- Two modes: **lab** (24 structured tasks, fixed resources) and **open** (build biggest factory)

### LLM-callable API (27 methods)

```
move_to, harvest_resource, place_entity, place_entity_next_to,
insert_item, extract_item, craft_item, set_research,
get_entities, get_entity, inspect_inventory, nearest,
connect_entities, rotate_entity, set_entity_recipe, sleep, score
```

### Baseline results (from paper)

- Claude 3.5-Sonnet: **7/24 lab tasks** completed
- GPT-4o, Deepseek-v3, Gemini-2-Flash, Llama-3.3-70B also tested
- Failure modes: long-horizon sequencing, spatial reasoning, error recovery

### Ollama support

FLE has **native Ollama support** in `fle/agents/llm/api_factory.py`:
- Prefix model name with `ollama-`: e.g. `ollama-qwen2.5-coder:14b`
- No API key needed - falls back to string `"ollama"` automatically
- Base URL defaults to `http://localhost:11434/v1`

---

## Local Setup (No Docker)

FLE's cluster system uses Docker to run headless Factorio, but you have Factorio 2.0.76
installed at `C:\Program Files (x86)\Steam\steamapps\common\Factorio`. Run headless directly.

### Architecture

```
[FLE Python agent] --RCON:27000--> [Factorio headless .exe]
[Factorio client]  --LAN:34197---> [same Factorio headless .exe]
```

Train/test via RCON, watch live by connecting the game client to localhost as LAN multiplayer.

### Step-by-step setup

**1. Clone FLE and install**

```powershell
cd "$env:USERPROFILE\repos"
git clone https://github.com/JackHopkins/factorio-learning-environment.git
cd factorio-learning-environment

uv venv --python 3.13
.venv\Scripts\Activate.ps1
uv pip install -e ".[eval]"
```

**2. Copy FLE scenario into Factorio**

```powershell
New-Item -ItemType Directory -Force "$env:APPDATA\Factorio\scenarios\default_lab_scenario"
Copy-Item -Recurse -Force "fle\cluster\scenarios\default_lab_scenario\*" `
    "$env:APPDATA\Factorio\scenarios\default_lab_scenario\"
```

**3. Create server-settings.json**

```powershell
@'
{
  "name": "FLE Local",
  "description": "",
  "visibility": { "public": false, "lan": false },
  "require_user_verification": false
}
'@ | Set-Content "$env:APPDATA\Factorio\config\server-settings.json"
```

**4. Configure .env**

```powershell
Copy-Item .example.env .env
```

Minimum required content - no API keys needed for local Ollama:

```ini
OLLAMA_BASE_URL=http://localhost:11434/v1
FLE_DB_TYPE=sqlite
SQLITE_DB_FILE=.fle/data.db
```

**5. Start Ollama**

```powershell
Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden
ollama pull qwen2.5-coder:14b
```

**6. Start Factorio headless**

```powershell
$factorio = "C:\Program Files (x86)\Steam\steamapps\common\Factorio\bin\x64\factorio.exe"
Start-Process -FilePath $factorio -ArgumentList @(
    "--start-server-load-scenario", "default_lab_scenario",
    "--rcon-port", "27000",
    "--rcon-password", "factorio",
    "--server-settings", "$env:APPDATA\Factorio\config\server-settings.json"
) -WindowStyle Normal
Start-Sleep 10
```

**7. Verify RCON connection**

```powershell
python -c "
import asyncio
from fle.env import FactorioInstance

async def main():
    instance = FactorioInstance(address='localhost', rcon_port=27000, rcon_password='factorio')
    await instance.reset()
    state = await instance.get_state()
    print('Connected. Tick:', state.game_tick)
    print('Inventory:', state.inventory)

asyncio.run(main())
"
```

**8. Watch live** - open Factorio client -> Multiplayer -> Connect to address -> `localhost`

---

## TAS as Training Data

The TAS and FLE don't share an execution format. The TAS is a Lua mod runner; FLE is a
Python REPL agent. The TAS is used as **few-shot demonstration data** injected into the
LLM's system prompt.

### Step 1: Extract TAS trajectory

Save as `scripts/parse_tas.py` in the FLE repo:

```python
import re, json

# Extract the zip first:
# Expand-Archive "$env:USERPROFILE\Downloads\Theis_TAS_Steelaxe2_0.3.0.zip" -DestinationPath "$env:USERPROFILE\Downloads\tas_extracted"

with open(r"C:\Users\m_ren\Downloads\tas_extracted\Theis_TAS_Steelaxe2_0.3.0\steps.lua") as f:
    raw = f.read()

def describe(line):
    if '"walk"' in line:
        coords = re.search(r'\{([-\d.]+),\s*([-\d.]+)\}', line)
        if coords:
            return f"move_to(({coords.group(1)}, {coords.group(2)}))"
    if '"build"' in line:
        coords = re.search(r'\{([-\d.]+),\s*([-\d.]+)\}', line)
        items = re.findall(r'"([\w-]+)"', line)
        entity = items[1] if len(items) > 1 else "?"
        if coords:
            return f"place_entity({entity!r}, position=({coords.group(1)}, {coords.group(2)}))"
    if '"mine"' in line:
        coords = re.search(r'\{([-\d.]+),\s*([-\d.]+)\}', line)
        if coords:
            return f"harvest_resource(nearest('resource', ({coords.group(1)}, {coords.group(2)})))"
    if '"craft"' in line:
        items = re.findall(r'"([\w-]+)"', line)
        count = re.search(r',\s*(-?\d+),', line)
        item = items[1] if len(items) > 1 else "?"
        n = count.group(1) if count else "1"
        return f"craft_item({item!r}, {n})"
    if '"take"' in line:
        items = re.findall(r'"([\w-]+)"', line)
        item = items[1] if len(items) > 1 else "?"
        return f"extract_item(nearest_entity, {item!r})"
    if '"put"' in line:
        items = re.findall(r'"([\w-]+)"', line)
        item = items[1] if len(items) > 1 else "?"
        return f"insert_item(nearest_entity, {item!r})"
    if '"tech"' in line:
        items = re.findall(r'"([\w-]+)"', line)
        tech = items[1] if len(items) > 1 else "?"
        return f"set_research({tech!r})"
    return None

trajectory = []
for line in raw.splitlines():
    if not re.match(r'step\[\d+\]', line.strip()):
        continue
    desc = describe(line)
    if desc:
        trajectory.append(desc)

with open("tas_trajectory.json", "w") as f:
    json.dump(trajectory, f, indent=2)
print(f"Saved {len(trajectory)} steps")
```

### Step 2: TAS-grounded agent

Save as `examples/agents/tas_agent.py`:

```python
import json
from examples.agents.basic_agent import BasicAgent

with open("tas_trajectory.json") as f:
    tas_steps = json.load(f)

FEW_SHOT = "\n".join(f"# step {i+1}\n{s}" for i, s in enumerate(tas_steps[:40]))

TAS_ADDENDUM = f"""
## Expert Demonstration (Steel Axe% speedrun, 7:35)

Optimal early-game action sequence. Use this as a reference for correct ordering:
what to build first, when to queue research, how to sequence mine/craft/build.

```python
{FEW_SHOT}
```

Key patterns:
- Build burner-mining-drill + stone-furnace immediately on a coal/iron patch
- Queue research (automation -> steel-processing -> steel-axe) before smelting completes
- Craft iron-gear-wheels in batches to minimize idle time
- mine() blocks until collected - chain with craft/build
"""

class TASGroundedAgent(BasicAgent):
    def __init__(self, model, task, **kwargs):
        super().__init__(model, TAS_ADDENDUM, task, **kwargs)
```

### Step 3: Run and compare

```python
# run_tas_agent.py
import asyncio
from fle.env import FactorioInstance
from fle.commons.models.tasks import TaskList
from examples.agents.tas_agent import TASGroundedAgent

async def main():
    instance = FactorioInstance(address="localhost", rcon_port=27000, rcon_password="factorio")
    await instance.reset()

    tasks = TaskList.load("fle/configs/experiments/lab_tasks.json")
    task = tasks[0]

    agent = TASGroundedAgent(model="ollama-qwen2.5-coder:14b", task=task)
    conversation = await agent.run(instance, max_steps=50)
    print("Score:", conversation.score)

asyncio.run(main())
```

Metric to track: **lab task completion rate** (X/24). Baseline is Claude 3.5-Sonnet at 7/24
zero-shot. Goal is to see how many tasks `qwen2.5-coder:14b + TAS context` completes.

---

## Watching the TAS (not the LLM agent)

To watch the *actual* TAS execute, use the FTG mod directly in a normal (non-headless) game:
1. Install `Theis_TAS_Steelaxe2` via Factorio in-game mod browser
2. Launch a new game with the steelaxe scenario
3. The mod drives the character automatically

This is separate from the FLE training setup.

---

## Research Framing

### Why this is novel

- FLE paper (March 2025) is the only published work on this environment
- No arxiv extensions exist as of May 2026
- FLE paper only tested zero-shot / standard prompting - no demonstration data
- Connecting TAS speedrunning community knowledge to LLM agent training is unexplored

### The core question

> Can TAS expert demonstrations compensate for model size?
> i.e., does `qwen2.5-coder:14b + TAS context` close the gap with `Claude 3.5-Sonnet` zero-shot?

### Supporting prior work

- **TextAtari** (arxiv 2506.04098, June 2025): expert demonstrations were the single most
  impactful factor for LLM game agents
- **Frog Soup** (arxiv 2505.03947, May 2025): in-context demonstrations improve LLM agents
  and bootstrap RL methods

### If results are positive

Jack Hopkins (lead FLE author) is active on the repo. The FLE paper explicitly lists
"demonstrations and prompting" as open problems. A result showing TAS demonstrations
improve lab task completion rate would be a natural follow-up contribution - either as
a GitHub issue/discussion or a short paper.

---

## System specs

- GPU: RTX 4070 Super 12GB
- RAM: 32GB
- CPU: Ryzen 7 5800XT
- Factorio: 2.0.76 (Steam, `C:\Program Files (x86)\Steam\steamapps\common\Factorio`)
- Best local model: `qwen2.5-coder:14b` (fits in 12GB VRAM)
- Python: 3.13, uv installed

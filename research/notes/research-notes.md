# Factorio TAS + LLM Agent - Research Notes

**Last updated:** 2026-05-18
**Author:** maxrenke
**Status:** Pre-experiment - setup phase

---

## Summary

Use Tool-Assisted Speedrun (TAS) data as expert demonstration context for LLM agents
running in the Factorio Learning Environment (FLE). The FLE paper (Hopkins et al., March
2025) found frontier models complete only 7/24 lab tasks, with failures concentrated on
long-horizon sequencing. A TAS encodes exactly that knowledge. This fork tests whether
grounding agents with TAS demonstrations closes the gap - and whether smaller local models
(14B) can match frontier performance when given that context.

---

## Key Resources

| Resource | Link | Notes |
|----------|------|-------|
| Factorio TAS Generator | https://github.com/theis999/Factorio-TAS-Generator | Tool to create/edit TAS runs |
| Steel Axe% TAS mod | https://mods.factorio.com/mod/Theis_TAS_Steelaxe2 | 7:35, Factorio 1.1, includes FTG file |
| FLE paper | https://arxiv.org/abs/2503.09617 | Hopkins, Bakler, Khan - March 2025 |
| FLE upstream | https://github.com/JackHopkins/factorio-learning-environment | Upstream to sync from |
| TextAtari (supporting) | https://arxiv.org/abs/2506.04098 | Expert demos most impactful factor |
| Frog Soup (supporting) | https://arxiv.org/abs/2505.03947 | In-context demos improve LLM game agents |

**Downloaded TAS:** `Theis_TAS_Steelaxe2_0.3.0.zip`
- Extract to: `research/data/tas/Theis_TAS_Steelaxe2_0.3.0/`
- Key files: `steps.lua` (664KB, 5721 steps), `control.lua`, `scenarios/steelaxe/blueprint.zip`

---

## TAS File Format

The mod is a Lua mod. The entire run is encoded as a flat array in `steps.lua`.

### Step schema

```lua
step[N] = {{task_id, subtask_id}, "action_type", ...args}
```

### Action types

| action | args | FLE equivalent |
|--------|------|----------------|
| `walk` | `{x,y}`, `""`, dir_x, dir_y, `[walk_towards=true]` | `move_to(position)` |
| `build` | `{x,y}`, entity_name, direction | `place_entity(name, position)` |
| `mine` | `{x,y}`, max_ticks | `harvest_resource(entity)` |
| `craft` | count (-1=max), item_name | `craft_item(name, count)` |
| `take` | `{x,y}`, item, amount, inventory_slot | `extract_item(entity, item)` |
| `put` | `{x,y}`, item, amount, inventory_slot | `insert_item(entity, item)` |
| `tech` | research_name | `set_research(tech)` |
| `drop` | `{x,y}`, item | - |
| `speed` | multiplier | game control only |

### Illustrative opening sequence

```lua
step[1]  = {{1,1},  "walk",  {0.0, 0.0}, "", "diagonal", "diagonal"}
step[3]  = {{3,1},  "build", {-1.0, 10.0}, "burner-mining-drill", defines.direction.north}
step[4]  = {{4,1},  "build", {-1.0, 8.0},  "stone-furnace",       defines.direction.north}
step[5]  = {{5,1},  "put",   {-1.0, 10.0}, "wood", 1, defines.inventory.fuel}
step[6]  = {{6,1},  "mine",  {-2.25, 9.75}, 1000}
step[10] = {{10,1}, "tech",  "automation"}
step[11] = {{11,1}, "tech",  "steel-processing"}
step[12] = {{12,1}, "tech",  "steel-axe"}
step[18] = {{18,1}, "craft", 3, "iron-gear-wheel"}
```

**Key ordering insight:** research is queued (steps 10-12) *before* smelting completes.
This is the sequencing knowledge the LLM paper identified as a primary failure mode.

### Version note

The TAS was made for Factorio 1.1. FLE targets 2.0.73+. The TAS is not directly executed
inside FLE - it is converted to natural-language / Python demonstrations injected into the
LLM's context. The specific map seed and entity names (`burner-mining-drill`, `stone-furnace`)
are valid in 2.0, so the demonstrations translate cleanly.

---

## Factorio Learning Environment

### Interaction model

```
LLM --> Python code (30 lines max) --> FLE REPL --> RCON --> Factorio headless
                                          |
                              stdout/stderr returned to LLM
```

### Agent-callable API (27 methods)

```python
# Movement & world interaction
move_to(position)
harvest_resource(entity)
nearest(type, position=None)
nearest_buildable(entity_type, position)
get_resource_patch(resource_type, position)

# Entity placement
place_entity(entity_type, direction, position)
place_entity_next_to(entity_type, ref_position, direction, gap)
pickup_entity(entity)
rotate_entity(entity, direction)
shift_entity(entity, direction)

# Inventory
craft_item(item, count)
insert_item(item, entity, count)
extract_item(item, entity, count)
inspect_inventory(entity=None)

# Factory wiring
connect_entities(source, target, connection_type)
get_connection_amount(entity, connection_type)
set_entity_recipe(entity, recipe)

# Information
get_entities(types=None, position=None, radius=None)
get_entity(type, position)
get_prototype_recipe(item)
get_research_progress()
can_place_entity(entity_type, position, direction)

# Research & misc
set_research(technology)
launch_rocket()
sleep(ticks)
score()
print(message)
```

### FLE baseline results (from paper)

| Model | Lab tasks (X/24) | Notes |
|-------|-----------------|-------|
| Claude 3.5-Sonnet | 7/24 | Best performer |
| GPT-4o | ~5/24 | Estimated from paper |
| Deepseek-v3 | ~4/24 | Estimated |
| Gemini-2-Flash | ~3/24 | Estimated |
| Llama-3.3-70B | ~2/24 | Lowest frontier |

Failure modes identified: long-horizon sequencing, spatial reasoning, error recovery,
inventory management under constraints.

### Ollama support (built-in)

From `fle/agents/llm/api_factory.py`:
- Model prefix: `ollama-<model_name>` e.g. `ollama-qwen2.5-coder:14b`
- No API key required - code falls back to string `"ollama"` automatically
- Base URL: `http://localhost:11434/v1` (or override with `OLLAMA_BASE_URL`)
- **Watch out:** `deepseek-r1` outputs `<think>...</think>` blocks before code. Verify
  FLE's response parser strips these before evaluating the Python policy.

---

## Local Setup (No Docker, Windows)

FLE upstream uses Docker to run headless Factorio. Since Factorio 2.0.76 is installed
locally, we run headless directly and skip Docker entirely.

### Architecture

```
[FLE Python agent] --RCON TCP:27000--> [factorio.exe --headless]
[Factorio client]  --UDP:34197-------> [same factorio.exe]
```

The game client connects as a LAN spectator. You watch the agent play in real time.

### One-time setup

```powershell
# 1. Clone this fork (already done if you're reading this in the repo)
cd "$env:USERPROFILE\repos"
git clone https://github.com/maxrenke/factorio-learning-environment.git
cd factorio-learning-environment
git remote add upstream https://github.com/JackHopkins/factorio-learning-environment.git

# 2. Python environment
uv venv --python 3.13
.venv\Scripts\Activate.ps1
uv pip install -e ".[eval]"

# 3. Copy FLE scenario into local Factorio
New-Item -ItemType Directory -Force "$env:APPDATA\Factorio\scenarios\default_lab_scenario"
Copy-Item -Recurse -Force "fle\cluster\scenarios\default_lab_scenario\*" `
    "$env:APPDATA\Factorio\scenarios\default_lab_scenario\"

# 4. Minimal server-settings.json
@'
{
  "name": "FLE Local",
  "description": "",
  "visibility": { "public": false, "lan": false },
  "require_user_verification": false
}
'@ | Set-Content "$env:APPDATA\Factorio\config\server-settings.json"

# 5. .env (no API keys needed for Ollama)
Copy-Item .example.env .env
# Add to .env:
# OLLAMA_BASE_URL=http://localhost:11434/v1
# FLE_DB_TYPE=sqlite
# SQLITE_DB_FILE=.fle/data.db
```

### Each session

```powershell
# Terminal 1: Ollama (if not already running)
Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden

# Terminal 2: Factorio headless
$factorio = "C:\Program Files (x86)\Steam\steamapps\common\Factorio\bin\x64\factorio.exe"
& $factorio --start-server-load-scenario default_lab_scenario `
            --rcon-port 27000 --rcon-password factorio `
            --server-settings "$env:APPDATA\Factorio\config\server-settings.json"

# Terminal 3: Agent
.venv\Scripts\Activate.ps1
python research/scripts/run_experiment.py --model ollama-qwen2.5-coder:14b

# Factorio client: Multiplayer -> Connect -> localhost (to watch live)
```

### Verify RCON connection

```python
import asyncio
from fle.env import FactorioInstance

async def main():
    inst = FactorioInstance(address="localhost", rcon_port=27000, rcon_password="factorio")
    await inst.reset()
    state = await inst.get_state()
    print("tick:", state.game_tick, "inventory:", state.inventory)

asyncio.run(main())
```

---

## Model Comparison Matrix

All models fit in 12GB VRAM at Q4 quantization. Each is pulled via `ollama pull <name>`.

| Model | Size | VRAM | Type | Tests hypothesis |
|-------|------|------|------|-----------------|
| `qwen2.5-coder:14b` | 14B | ~8.5GB | Code | Primary / baseline |
| `qwen2.5-coder:7b` | 7B | ~4.5GB | Code | Size ablation (same family) |
| `deepseek-r1:14b` | 14B | ~9GB | Reasoning | Does CoT reasoning beat code specialization for planning? |
| `phi4:14b` | 14B | ~9GB | General | Strong generalist vs code-specialized |
| `llama3.1:8b` | 8B | ~5GB | General | Unspecialized floor |

### Full comparison design (10 cells)

```
                      zero-shot    + TAS context
qwen2.5-coder:14b   [  X/24   ]   [  X/24   ]   <- primary
qwen2.5-coder:7b    [  X/24   ]   [  X/24   ]   <- size ablation
deepseek-r1:14b     [  X/24   ]   [  X/24   ]   <- reasoning
phi4:14b            [  X/24   ]   [  X/24   ]   <- generalist
llama3.1:8b         [  X/24   ]   [  X/24   ]   <- floor
```

Primary research question: do TAS demonstrations help more or less depending on model type?
Secondary: does a reasoning model (R1) need demonstrations less than a code model?

**Note on deepseek-r1:** outputs `<think>...</think>` before code blocks. Either patch
`fle/agents/llm/parsing.py` to strip thinking tags, or use the `deepseek-r1:14b-qwen-distill-q4_K_M`
variant which has thinking stripped by default.

---

## TAS as Training Data

### Approach 1: Few-shot context injection (implement first)

Convert TAS steps to FLE API calls and prepend to system prompt. Fast to implement,
no training loop needed, directly testable tonight.

Parse script: `research/scripts/parse_tas.py`
Agent: `research/agents/tas_agent.py`

### Approach 2: Fine-tuning (later phase)

Collect FLE trajectories (state, action, outcome) from the TAS-converted sequence,
then fine-tune using Unsloth on the local GPU. The 14B model is borderline for LoRA
fine-tuning on 12GB - feasible with 4-bit quantization and rank 16.

Tools: [Unsloth](https://github.com/unslothai/unsloth) for efficient LoRA fine-tuning.

### Approach 3: Retrieval-augmented (future)

Instead of injecting all TAS steps, embed each step and retrieve the K most relevant
ones given the current game state. Reduces context length and focuses the signal.

---

## Paper Outline (Draft)

### Tentative title

*"TAS-Grounded LLM Agents in Factorio: Expert Demonstrations from Speedrunning Close
the Long-Horizon Planning Gap"*

### Abstract (draft)

Large language models evaluated on the Factorio Learning Environment (Hopkins et al., 2025)
fail to complete most structured lab tasks, with failures attributed to long-horizon
sequencing and spatial planning. We investigate whether injecting expert demonstration
data derived from Tool-Assisted Speedruns (TAS) - optimal human-authored action sequences
from the Factorio speedrunning community - into the agent's context closes this gap.
We evaluate five open-weight models (7B-14B parameters) across 24 lab tasks in zero-shot
and TAS-grounded conditions. We find that [results TBD]. Our results suggest that
demonstration quality is [more/less] important than model size for planning-heavy tasks,
and that the Factorio speedrunning community represents an underutilized source of
structured expert knowledge for agent training.

### Sections

1. **Introduction**
   - FLE as benchmark; frontier model ceiling at 7/24
   - TAS as a source of structured optimal demonstrations
   - Research questions: does context help? which models benefit most?

2. **Background**
   - FLE framework and evaluation protocol
   - TAS: what they are, how they encode expert knowledge
   - Related: TextAtari (demos most impactful), Frog Soup (in-context demos + RL)
   - Related: MindAgent (few-shot demos in multi-agent games)

3. **Method**
   - TAS-to-FLE translation (steps.lua -> Python API calls)
   - Context injection strategy (first N steps, sampled, retrieval)
   - Evaluation: 24 lab tasks, 3 runs each, report mean completion rate
   - Models: 5 local models + Claude 3.5-Sonnet as oracle comparison

4. **Experiments**
   - 4.1: Zero-shot baseline replication (confirm FLE paper numbers on our setup)
   - 4.2: TAS context effect per model
   - 4.3: Ablation - how many TAS steps needed? (10, 40, 100, full)
   - 4.4: Which tasks improve most? (classify by horizon length)

5. **Results**
   - Main table: 5 models x 2 conditions x 24 tasks
   - Analysis: does TAS help more for planning tasks vs resource tasks?
   - Qualitative: examples of improved/unchanged/regressed behaviour

6. **Discussion**
   - Local 14B vs frontier: how much of the gap closes?
   - Reasoning model vs code model: which benefits more from demonstrations?
   - Limitations: single TAS, single category (steelaxe%), map-specific coordinates

7. **Conclusion + Future Work**
   - Fine-tuning on TAS trajectories
   - Retrieval-augmented demonstration selection
   - Multi-TAS corpus (any%, rail world, deathworld)

### Target venues

- **NeurIPS 2026 Datasets & Benchmarks** (natural fit - FLE is a benchmark paper)
- **ICLR 2027** (agent/reasoning track)
- Short paper / workshop: NeurIPS 2026 Agent Learning workshop

---

## Crawl / Walk / Run Roadmap

### CRAWL - Replicate and verify (do this first)

Goal: confirm FLE works on this machine, reproduce paper baseline numbers.

- [ ] **C1** - Extract TAS zip: `Expand-Archive` to `research/data/tas/`
- [ ] **C2** - Install FLE from this fork: `uv pip install -e ".[eval]"`
- [ ] **C3** - Copy scenario into Factorio, create server-settings.json
- [ ] **C4** - Start Ollama, pull `qwen2.5-coder:14b`
- [ ] **C5** - Start Factorio headless, verify RCON connects
- [ ] **C6** - Connect game client as LAN spectator (visual sanity check)
- [ ] **C7** - Run FLE's existing `basic_agent.py` against task 1 with `qwen2.5-coder:14b`
- [ ] **C8** - Run all 24 lab tasks zero-shot, record completion rate -> this is your local baseline
- [ ] **C9** - Log results to `research/results/baseline_qwen25coder14b_zeroshot.json`

Expected: something worse than 7/24 (Claude baseline), probably 2-5/24 for a 14B model.

### WALK - TAS integration and first comparison

Goal: implement TAS context injection, run the 2x2 core experiment.

- [ ] **W1** - Run `research/scripts/parse_tas.py` -> `research/data/tas_trajectory.json`
- [ ] **W2** - Review translated steps, manually fix any mis-parsed actions
- [ ] **W3** - Deploy `research/agents/tas_agent.py` (BasicAgent subclass with TAS addendum)
- [ ] **W4** - Run all 24 tasks with TAS context on `qwen2.5-coder:14b`, record results
- [ ] **W5** - Pull and test `deepseek-r1:14b` (check thinking-tag stripping in parser first)
- [ ] **W6** - Run all 24 tasks zero-shot on `deepseek-r1:14b`
- [ ] **W7** - Run all 24 tasks + TAS on `deepseek-r1:14b`
- [ ] **W8** - Fill in 4 cells of the comparison matrix, write up initial findings
- [ ] **W9** - Post results as GitHub issue on upstream FLE repo for early feedback

Milestone: answer the primary question - does TAS context improve lab task completion?

### RUN - Full matrix, ablations, fine-tuning

Goal: publication-quality data, paper draft, PR to upstream.

- [ ] **R1** - Pull remaining models: `qwen2.5-coder:7b`, `phi4:14b`, `llama3.1:8b`
- [ ] **R2** - Run full 5-model x 2-condition matrix (50 eval runs, ~X hours)
- [ ] **R3** - Ablation: TAS context size (10 steps, 40, 100, 200, full 5721)
- [ ] **R4** - Ablation: which TAS steps matter? (opening only, research phase, build phase)
- [ ] **R5** - Per-task analysis: classify 24 tasks by horizon length, check which improve
- [ ] **R6** - Fine-tuning experiment: collect FLE trajectories, LoRA fine-tune with Unsloth
- [ ] **R7** - Set up automated nightly eval: run baseline + TAS on 1 task per model, log to SQLite
- [ ] **R8** - Write paper sections 3 and 4 (method + experiments)
- [ ] **R9** - Open PR to FLE upstream with: `parse_tas.py`, `TASGroundedAgent`, results

---

## Results Tracking

Results saved to `research/results/` as JSON:

```json
{
  "run_id": "qwen25coder14b_zeroshot_20260518",
  "model": "ollama-qwen2.5-coder:14b",
  "condition": "zero_shot",
  "tas_steps_injected": 0,
  "factorio_version": "2.0.76",
  "fle_version": "0.3.0",
  "date": "2026-05-18",
  "tasks": {
    "task_01": {"completed": false, "score": 0, "steps_taken": 50},
    "task_02": {"completed": true,  "score": 1, "steps_taken": 23}
  },
  "summary": {
    "completed": 2,
    "total": 24,
    "completion_rate": 0.083
  }
}
```

---

## System Specs

| Component | Details |
|-----------|---------|
| GPU | RTX 4070 Super 12GB VRAM |
| RAM | 32GB |
| CPU | Ryzen 7 5800XT |
| OS | Windows 11 Pro 10.0.26200 |
| Factorio | 2.0.76 (Steam) at `C:\Program Files (x86)\Steam\steamapps\common\Factorio` |
| Python | 3.13 (uv) |
| Ollama | 0.24.0 |
| Primary model | `qwen2.5-coder:14b` (~8.5GB VRAM, Q4) |

### VRAM budget for models

| Model | VRAM (Q4) | Status |
|-------|-----------|--------|
| `qwen2.5-coder:14b` | ~8.5GB | Fits |
| `deepseek-r1:14b` | ~9GB | Fits |
| `phi4:14b` | ~9GB | Fits |
| `llama3.1:8b` | ~5GB | Fits |
| `qwen2.5-coder:7b` | ~4.5GB | Fits |
| `qwen2.5-coder:32b` | ~18GB | Too large - CPU offload only |

---

## Known Issues / Open Questions

1. **Factorio version mismatch**: TAS built on 1.1, FLE targets 2.0.73. Need to verify
   all entity names in TAS steps are valid in 2.0 (`stone-furnace`, `burner-mining-drill`
   both confirmed valid).

2. **deepseek-r1 thinking tags**: `<think>...</think>` prefix will cause FLE's policy
   parser to reject the response. Either patch `fle/agents/llm/parsing.py` or use the
   distilled variant.

3. **Map-specific coordinates**: TAS coordinates are for the steelaxe% fixed seed map.
   FLE uses a different map. Demonstrations with hardcoded positions (`walk to -31, 7`)
   won't transfer directly - the agent must understand the *pattern* not the coordinates.
   Mitigate by abstracting steps to higher-level descriptions before injection.

4. **Context length**: 5721 steps x ~40 tokens each = ~230K tokens. Too long for most
   models. Use first 40-100 steps (the critical early-game sequencing) rather than the
   full run.

5. **FLE scenario vs TAS scenario**: FLE's `default_lab_scenario` has pre-placed resources.
   The TAS plays on a generated freeplay map. The demonstrations may not transfer perfectly
   to FLE's constrained lab environment - this is an interesting finding either way.

# Factorio TAS + LLM Agent - Research Notes

**Last updated:** 2026-05-18
**Author:** maxrenke
**Status:** Pre-experiment - setup phase

## Scope (locked)

**Proof of concept targets Factorio 1.1 + FLE v0.3.0 + Steel Axe% TAS.**

- Factorio 2.0 / Space Age has no TAS yet. Defer until PoC is complete.
- FLE v0.3.0 (Oct 2025) is the paper version, targets Factorio 1.1.110, has 24 lab tasks.
- FLE v0.4.0+ migrated to Factorio 2.0 - do not use for this research phase.
- AnyPctTAS (0.18) skipped - hard-pinned to Factorio 0.18.17, incompatible.
- AutoFactorio: never functionally implemented, cute idea but no usable TAS data. Historical note only.

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

The TAS was made for Factorio 1.1. This research pins to **FLE v0.3.0 + Factorio 1.1**
(see locked Scope at top), so TAS entity names (`burner-mining-drill`, `stone-furnace`)
match the environment version directly - no 2.0 migration needed. The TAS is not executed
inside FLE; it is converted to Python demonstrations injected into the LLM's context.

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
# 0. Downgrade Factorio to 1.1 via Steam
#    Right-click Factorio in Library -> Properties -> Betas
#    Select "1.1.x-branch" from the dropdown -> Close
#    Steam will download Factorio 1.1.x (~1GB)
#    Confirm: factorio.exe --version should print 1.1.x

# 1. Clone this fork (already done if you're reading this in the repo)
cd "$env:USERPROFILE\repos"
git clone https://github.com/maxrenke/factorio-learning-environment.git
cd factorio-learning-environment
git remote add upstream https://github.com/JackHopkins/factorio-learning-environment.git

# 2. Python environment - install FLE pinned to v0.3.0 (Factorio 1.1, 24 tasks, paper version)
uv venv --python 3.13
.venv\Scripts\Activate.ps1
uv pip install "factorio-learning-environment==0.3.0" "factorio-learning-environment[eval]==0.3.0"

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

## Training Roadmap: Four Phases

The research follows a four-phase progression from zero-training-cost to full RL.
Each phase builds on the previous. Stop at any phase if results are already strong enough.

---

### Phase 1 - Large model + few-shot TAS (do tonight)

**What:** Frozen `qwen2.5-coder:14b` with TAS steps injected into the system prompt.
No training. No code changes to the model. Just context engineering.

**How it works:**
- `parse_tas.py` converts `steps.lua` -> list of FLE Python API calls
- `TASGroundedAgent` prepends the first N steps as a few-shot block to the system prompt
- Model reads the examples and mimics the pattern when generating its own code
- Model weights are never updated between runs

**Scripts:**
- `research/scripts/parse_tas.py` - converts TAS to FLE calls
- `research/agents/tas_agent.py` - `TASGroundedAgent(BasicAgent)` subclass

**Run:**
```powershell
python research/scripts/run_experiment.py --model ollama-qwen2.5-coder:14b --condition zero_shot
python research/scripts/run_experiment.py --model ollama-qwen2.5-coder:14b --condition tas_40
```

**Ablation:** vary N = 10, 40, 100 steps. Hypothesis: early-game sequencing (steps 1-40)
provides the most signal; full 5721 steps exceeds context budget (~230K tokens).

**Success criteria:** qwen2.5-coder:14b + TAS beats its own zero-shot baseline.
The FLE paper ceiling for this model class is 7/24 (Claude 3.5-Sonnet).

---

### Phase 2 - Large model + LoRA supervised fine-tuning

**What:** Fine-tune `qwen2.5-coder:14b` on TAS-derived (state, action) pairs using
Low-Rank Adaptation (LoRA). The model weights change but only the small A/B matrices
- base model stays frozen.

**Why LoRA:**
- Full fine-tuning of 14B weights = ~56GB VRAM. Impossible on 12GB.
- LoRA freezes the original weight matrix W and adds two small matrices A (d x r) and B (r x d).
  Forward pass: `output = W*x + (A*B)*x` where r=16 (rank), so we train ~20M params vs 14B.
- With 4-bit quantization (bitsandbytes/unsloth) the base model uses ~8.5GB, leaving ~3.5GB
  for LoRA adapters and gradients. Tight but fits.

**Training data format** (`research/data/training_data.jsonl`):
```json
{"prompt": "# Factorio step N\n# Inventory: {...}\n# Previous actions:\n#   step N-10: ...\n",
 "completion": "move_to(nearest('iron-ore'))\nharvest_resource(nearest('iron-ore'))"}
```

Each line = one TAS step. Prompt = game state context (inventory + last 10 steps).
Completion = the FLE Python API call the TAS took at that step.

**Scripts:**
- `research/scripts/build_training_data.py` - converts `tas_trajectory.json` -> JSONL pairs
- `research/scripts/finetune_lora.py` - Unsloth + SFTTrainer pipeline

**Config:**
```python
MODEL_NAME = "Qwen/Qwen2.5-Coder-14B-Instruct"
LORA_RANK = 16           # small r = fewer params = fits in VRAM
LORA_ALPHA = 32          # typically 2x rank
TARGET_MODULES = ["q_proj", "k_proj", "v_proj", "o_proj",
                  "gate_proj", "up_proj", "down_proj"]
load_in_4bit = True      # 4-bit quantization via bitsandbytes
use_gradient_checkpointing = "unsloth"  # saves ~30% VRAM
optim = "adamw_8bit"     # 8-bit optimizer
epochs = 3
```

**Output:** `research/models/qwen25coder-14b-factorio-lora/` (adapter weights only, ~100MB)

**Run:**
```powershell
python research/scripts/build_training_data.py
python research/scripts/finetune_lora.py
```

**Evaluate with Ollama:**
```powershell
# Export LoRA to GGUF + load in Ollama (see finetune_lora.py comments)
python research/scripts/run_experiment.py --model ollama-qwen25coder-14b-factorio --condition zero_shot
```

**Hypothesis:** LoRA-tuned model outperforms Phase 1 (few-shot only) because the weights
themselves encode Factorio knowledge, not just the context window.

---

### Phase 3 - Small dedicated model + aggressive LoRA

**What:** Same LoRA pipeline but on a 1.5B-3B model. The goal shifts from "improve a
large model" to "build a model specialized for Factorio."

**Target models:**
- `Qwen/Qwen2.5-Coder-1.5B-Instruct` (~1GB VRAM) - smallest viable coder
- `Qwen/Qwen2.5-Coder-3B-Instruct` (~2GB VRAM) - recommended starting point
- `microsoft/phi-3-mini-4k-instruct` (~2.5GB VRAM) - alternative

**Why smaller:**
- 12GB VRAM freed from base model leaves ~10GB for LoRA + gradients + optimizer states
- Can use higher rank (r=64) and more epochs without OOM
- Faster training iterations = more experiments per day
- If a 3B model fine-tuned on TAS approaches a 14B zero-shot, that's a strong result

**Distillation option:** Use Phase 2's fine-tuned 14B as the teacher. Generate synthetic
(state, action) pairs by running the 14B model on novel game states, then train the 3B on
those outputs. This transfers the 14B's Factorio-specific knowledge to the 3B without
requiring more TAS data.

**Config changes from Phase 2:**
```python
MODEL_NAME = "Qwen/Qwen2.5-Coder-3B-Instruct"
LORA_RANK = 64       # can go higher on small model
epochs = 5           # more epochs since base is weaker
```

**Hypothesis:** A 3B model fine-tuned on TAS outperforms a 14B model zero-shot on
Factorio-specific tasks, demonstrating that specialization beats scale for constrained domains.

---

### Phase 4 - Small model + RL from FLE scores (Code Bullet equivalent)

**What:** Treat the fine-tuned 3B model as an RL policy. FLE is the environment.
Use shaped rewards from production metrics - not sparse task completion - to train
the model to actually discover and improve Factorio strategy autonomously.

**Why RL (not just SFT):**
- SFT (Phases 2-3) teaches the model to imitate the TAS. It can't exceed TAS performance.
- RL lets the model discover strategies the TAS didn't use. The reward signal is production
  output, so the model is incentivized to optimize the factory - potentially discovering
  automation, throughput tricks, and efficient builds that the TAS didn't show.

**Reward shaping (dense rewards to avoid sparse signal problem):**

Factorio episodes take 7+ minutes. If you only reward task completion at the end, the model
gets almost no signal during training - the "sparse reward problem." Instead, reward every
step based on production metrics:

```python
def compute_reward(state: GameState) -> float:
    return (
        state.iron_plates_produced   * 0.001 +   # basic production
        state.copper_plates_produced * 0.001 +   # basic production
        state.gear_wheels_produced   * 0.010 +   # intermediate (requires setup)
        state.science_packs_produced * 0.100 +   # advanced (strong signal)
        state.task_completed         * 1.000      # terminal reward (strongest)
    )
```

Why this works: science packs require copper, iron, and gears. Maximizing science pack
production emergently requires the model to learn all upstream production. The model
discovers automation naturally because a manual loop produces fewer science packs
than an automated factory loop.

**Curriculum learning (start simple, increase complexity):**

The model starts with a vocabulary of ~27 FLE API calls but no game knowledge.
Starting directly on "complete FLE lab task 12" is too hard - no signal for 1000 steps.
Instead, use staged goals:

| Stage | Goal | Reward shape | What it teaches |
|-------|------|--------------|-----------------|
| 1 | Make 1 iron plate | +1.0 on first plate, sparse ok | Mine ore, smelt, verify result |
| 2 | Efficient iron production | `iron_plates * 0.001` continuous | Automate smelting, throughput |
| 3 | Copper plates | `+copper_plates * 0.001` added | Second resource type, parallel processes |
| 4 | Gear wheels | `+gears * 0.01` added | Recipe chaining, intermediate products |
| 5 | Science packs/minute | `+science * 0.1` added | Full production chain, automation |
| 6 | FLE lab tasks | Full reward + `task_complete * 1.0` | Benchmark performance |

Each stage inherits the reward from the previous stage. The model is never reset -
it's one continuous learning process with increasing reward signal.

**Algorithm:** PPO (Proximal Policy Optimization) or GRPO (Group Relative Policy Optimization).
- GRPO (used in DeepSeek-R1) is simpler to implement, no value network needed
- PPO is more stable but requires a separate critic model (~doubles VRAM)
- Start with GRPO via [trl](https://github.com/huggingface/trl) library

**Initialization:** Start from Phase 3's LoRA-fine-tuned 3B model, not a blank model.
The TAS LoRA provides a warm start - the policy already knows basic Factorio actions
before RL begins. This dramatically reduces the cold-start exploration problem.

**RL training loop:**
```
for episode in curriculum:
    state = env.reset()
    for step in range(max_steps):
        action = policy.generate(state_prompt)   # LLM generates Python
        next_state, reward = env.step(action)    # FLE executes Python
        buffer.add(state, action, reward)
        state = next_state
    policy.update(buffer)   # PPO/GRPO gradient update
```

**Scripts needed (Phase 4, future):**
- `research/scripts/train_rl.py` - RL training loop with curriculum
- `research/scripts/reward.py` - reward computation from FLE game state

**Hypothesis:** A 3B model + TAS warm start + RL training eventually exceeds the
14B zero-shot baseline and potentially the 14B + TAS few-shot baseline, demonstrating
that self-improvement through RL is more sample-efficient when initialized from expert demos.

---

### Phase summary

| Phase | Model | Method | Training | Est. VRAM | Files |
|-------|-------|--------|----------|-----------|-------|
| 1 | qwen2.5-coder:14b | Few-shot TAS context | None | ~8.5GB | `tas_agent.py` |
| 2 | qwen2.5-coder:14b | LoRA SFT on TAS | ~2h | ~11GB | `finetune_lora.py` |
| 3 | qwen2.5-coder:3b | Aggressive LoRA + distill | ~30min | ~4GB | `finetune_lora.py` |
| 4 | qwen2.5-coder:3b | RL from FLE (PPO/GRPO) | days | ~4GB | `train_rl.py` (future) |

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
   - Phase 2-3 LoRA fine-tuning on TAS trajectories (if not run)
   - Phase 4 RL from FLE scores: reward shaping + curriculum
   - Retrieval-augmented demonstration selection (per-step retrieval vs upfront injection)
   - Multi-TAS corpus (any%, rail world, deathworld)

### Target venues

- **NeurIPS 2026 Datasets & Benchmarks** (natural fit - FLE is a benchmark paper)
- **ICLR 2027** (agent/reasoning track)
- Short paper / workshop: NeurIPS 2026 Agent Learning workshop

---

## Crawl / Walk / Run Roadmap

### CRAWL - Replicate and verify (do this first)

Goal: confirm FLE works on this machine, reproduce paper baseline numbers.

- [ ] **C0** - Downgrade Factorio to 1.1 via Steam betas (Properties -> Betas -> 1.1.x-branch)
  - Steam -> Factorio -> Properties -> Betas -> select `1.1.x-branch` -> Close
  - Wait for ~1GB download
  - Verify: `& "C:\Program Files (x86)\Steam\steamapps\common\Factorio\bin\x64\factorio.exe" --version`
  - Should print `1.1.x` - not 2.0

- [ ] **C1** - Extract TAS zip to `research/data/tas/`
  - Download from https://mods.factorio.com/mod/Theis_TAS_Steelaxe2 if not already
  ```powershell
  Expand-Archive "$env:USERPROFILE\Downloads\Theis_TAS_Steelaxe2_0.3.0.zip" `
      -DestinationPath "C:\Users\m_ren\repos\factorio-learning-environment\research\data\tas"
  ```
  - Verify: `research/data/tas/Theis_TAS_Steelaxe2_0.3.0/steps.lua` exists

- [ ] **C2** - Create venv and install FLE v0.3.0
  ```powershell
  cd C:\Users\m_ren\repos\factorio-learning-environment
  uv venv --python 3.13
  .venv\Scripts\Activate.ps1
  uv pip install "factorio-learning-environment[eval]==0.3.0"
  ```

- [ ] **C3** - Copy FLE scenario into local Factorio and create server-settings.json
  ```powershell
  New-Item -ItemType Directory -Force "$env:APPDATA\Factorio\scenarios\default_lab_scenario"
  Copy-Item -Recurse -Force "fle\cluster\scenarios\default_lab_scenario\*" `
      "$env:APPDATA\Factorio\scenarios\default_lab_scenario\"
  ```
  - server-settings.json is auto-created by `start_headless.ps1` if missing

- [ ] **C4** - Pull the primary model
  ```powershell
  ollama pull qwen2.5-coder:14b
  ```
  - ~5GB download. Note: `qwen2.5:7b-instruct` already on system is a different variant - not suitable.

- [ ] **C5** - Start Factorio headless and verify RCON connects
  ```powershell
  # Terminal 1
  .\research\scripts\start_headless.ps1

  # Terminal 2 - verify
  .venv\Scripts\Activate.ps1
  python -c "
  import asyncio
  from fle.env import FactorioInstance
  async def main():
      inst = FactorioInstance(address='localhost', rcon_port=27000, rcon_password='factorio')
      await inst.reset()
      print('RCON OK')
  asyncio.run(main())
  "
  ```

- [ ] **C6** - Connect game client as LAN spectator (visual sanity check)
  - Launch Factorio client -> Multiplayer -> Connect to server -> `localhost`

- [ ] **C7** - Run FLE's existing `basic_agent.py` against task 1 with `qwen2.5-coder:14b`

- [ ] **C8** - Run all 24 lab tasks zero-shot, record completion rate -> this is your local baseline
  ```powershell
  python research/scripts/run_experiment.py --model ollama-qwen2.5-coder:14b --condition zero_shot
  ```

- [ ] **C9** - Results auto-saved to `research/results/`. Summarize:
  ```powershell
  python research/scripts/summarize_results.py
  ```

Expected: something worse than 7/24 (Claude baseline), probably 2-5/24 for a 14B model.

### PRE-FLIGHT - Harness validation gate (do BEFORE C7)

Goal: catch the four known blockers before burning hours on a broken eval loop.
An audit of the scripts against the v0.3.0 FLE source found the harness will crash
on first run. Resolve all V-steps before attempting C7-C9. See "Known Issues -> BLOCKERS".

- [ ] **V0** - Decide the repo branch base. The repo `fle/` is currently v0.4.3, but the
      research targets v0.3.0. Recommended:
  ```powershell
  git checkout -b research/v0.3.0 v0.3.0      # branch off the v0.3.0 tag
  git checkout main -- research/              # bring the research/ dir onto it
  git commit -m "Rebase research onto FLE v0.3.0 source"
  ```
  After this the repo's own `fle/` IS v0.3.0 and the pip pin is no longer load-bearing.
  Install deps from the v0.3.0 source: `uv pip install -e ".[eval]"`

- [ ] **V1** - Confirm `import fle` resolves to v0.3.0:
  ```powershell
  python -c "import fle, fle.env; print(fle.__file__)"   # must not raise; lupa must import
  ```
  If `ModuleNotFoundError: lupa` -> `uv pip install lupa` (or install the `[eval]` extra).

- [ ] **V2** - Confirm the `BasicAgent` import path. v0.3.0: `examples.agents.basic_agent`.
  ```powershell
  python -c "from examples.agents.basic_agent import BasicAgent; print('ok')"
  ```

- [ ] **V3** - Verify the FLE agent namespace and API surface used by `parse_tas.py`:
      does `nearest()` accept a resource type, is `Direction` the right identifier,
      what is the real `place_entity` signature? Fix `parse_tas.py` / `tas_agent.py`
      output to match. Re-run `python -m pytest research/tests/` after.

- [ ] **V4** - Rewrite `run_experiment.py` against the real v0.3.0 harness. `agent.run()`
      does not exist. Either wrap `GymTrajectoryRunner`
      (`fle/eval/algorithms/independent/trajectory_runner.py`) or drive the eval through
      `fle/eval/entrypoints/independent_run_a2a.py`. Validate on ONE task before the full 24.

- [ ] **V5** - Run `python -m pytest research/tests/` - all green before proceeding.

Gate: do not start C7 until V0-V5 pass.

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

### RUN - Full matrix, ablations, fine-tuning (Phase 2-3)

Goal: publication-quality data, paper draft, PR to upstream.

- [ ] **R1** - Pull remaining models: `qwen2.5-coder:7b`, `phi4:14b`, `llama3.1:8b`
- [ ] **R2** - Run full 5-model x 2-condition matrix (50 eval runs, ~X hours)
- [ ] **R3** - Ablation: TAS context size (10 steps, 40, 100, 200, full 5721)
- [ ] **R4** - Ablation: which TAS steps matter? (opening only, research phase, build phase)
- [ ] **R5** - Per-task analysis: classify 24 tasks by horizon length, check which improve
- [ ] **R6** - Phase 2: run `build_training_data.py` -> `finetune_lora.py` on qwen2.5-coder:14b
- [ ] **R7** - Eval Phase 2 LoRA-tuned 14b on all 24 tasks, compare to Phase 1 few-shot
- [ ] **R8** - Phase 3: fine-tune qwen2.5-coder:3b, optionally distill from Phase 2 14b
- [ ] **R9** - Set up automated nightly eval: run baseline + TAS on 1 task per model, log to SQLite
- [ ] **R10** - Write paper sections 3 and 4 (method + experiments)
- [ ] **R11** - Open PR to FLE upstream with: `parse_tas.py`, `TASGroundedAgent`, results

### SPRINT - RL from FLE scores (Phase 4)

Goal: dedicated Factorio model trained via self-play + reward shaping. Code Bullet equivalent.

- [ ] **S1** - Verify FLE exposes per-step production metrics (iron_plates, copper_plates, etc.)
              from `game_state` or via RCON command. If not, write a mod or RCON query.
- [ ] **S2** - Implement `research/scripts/reward.py` with the shaped reward formula
- [ ] **S3** - Implement `research/scripts/train_rl.py` - curriculum stage 1 (make 1 iron plate)
              using GRPO via `trl.GRPOTrainer`. Initialize from Phase 3 3B LoRA adapter.
- [ ] **S4** - Run stage 1 training until convergence. Log reward curve. Eval on FLE task 1.
- [ ] **S5** - Unlock stage 2 (efficient iron production), retrain. Log improvement.
- [ ] **S6** - Progress through curriculum stages 3-6 (copper, gears, science, lab tasks)
- [ ] **S7** - Compare Phase 4 RL model against all prior phases on 24 lab tasks
- [ ] **S8** - Write paper section 5 (RL results) and update abstract with findings

---

## Results Tracking

Results saved to `research/results/` as JSON:

```json
{
  "run_id": "qwen25coder14b_zeroshot_20260518",
  "model": "ollama-qwen2.5-coder:14b",
  "condition": "zero_shot",
  "tas_steps_injected": 0,
  "factorio_version": "1.1.110",
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
| Factorio | 2.0.76 installed - **must downgrade to 1.1.x** (step C0) at `C:\Program Files (x86)\Steam\steamapps\common\Factorio` |
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

### BLOCKERS - must fix before any eval can run

These were found by auditing the scripts against the actual v0.3.0 FLE source
(git tag `v0.3.0`). The harness will crash on first run until these are resolved.

1. **Repo source is v0.4.3, not v0.3.0** *(critical)*. The checked-out `fle/` directory
   is FLE v0.4.3 (`pyproject.toml` -> `version = "0.4.3"`, Factorio 2.0 API). The research
   targets v0.3.0. `run_experiment.py` does `sys.path.insert(0, repo_root)`, so `import fle`
   resolves to the repo's v0.4.3 source - the `uv pip install ...==0.3.0` pin is silently
   defeated. **Fix:** base the research branch on the `v0.3.0` git tag so the repo's own
   `fle/` *is* v0.3.0. See pre-flight step V0 in the roadmap.

2. **`BasicAgent` import path is wrong** *(critical)*. `tas_agent.py` and `run_experiment.py`
   both do `from fle.agents.basic_agent import BasicAgent`. In v0.3.0 `BasicAgent` lives at
   `examples/agents/basic_agent.py` (import as `examples.agents.basic_agent` from repo root).
   The scripts now try the v0.4.x path first and fall back to the v0.3.0 path.

3. **`agent.run()` does not exist** *(critical)*. `run_experiment.py` calls
   `await agent.run(instance, max_steps=...)`. v0.3.0 `BasicAgent(AgentABC)` exposes only
   `step()`, `_get_policy()`, `end()` - there is no `run()`. The agent loop is driven
   externally by `GymTrajectoryRunner.run()` in
   `fle/eval/algorithms/independent/trajectory_runner.py`, or via the A2A entrypoint
   `fle/eval/entrypoints/independent_run_a2a.py`. **`run_experiment.py` must be rewritten**
   to either (a) wrap `GymTrajectoryRunner`, or (b) shell out to `independent_run_a2a.py`.
   This is the single largest piece of remaining work - see roadmap step V4.

4. **`nearest('resource', ...)` is invalid** *(blocks TAS mine steps)*. `parse_tas.py`
   translates TAS `mine` steps to `harvest_resource(nearest('resource', (x,y)))`. FLE's
   `nearest()` requires a concrete resource type (`'iron-ore'`, `'coal'`, `'copper-ore'`,
   `'stone'`); `'resource'` is not a valid prototype. The TAS `mine` step carries only
   coordinates, not the resource name. **Fix options:** infer the type from the entity at
   those coords during a TAS replay, or emit a `# MINE` comment placeholder.

### Open questions / risks

5. **`Direction` enum in few-shot output**: `parse_tas.py` emits
   `place_entity('...', direction=Direction.NORTH, ...)`. Verify the FLE agent namespace
   exposes `Direction` as that identifier - if not, the injected few-shot code is invalid
   Python and will teach the model a broken pattern. Check in pre-flight V3.

6. **deepseek-r1 thinking tags**: `<think>...</think>` prefix will cause FLE's policy
   parser to reject the response. Either patch the v0.3.0 parser
   (`fle/agents/llm/parsing.py`) or use the distilled variant.

7. **Map-specific coordinates**: TAS coordinates are for the steelaxe% fixed seed map.
   FLE uses a different map. Demonstrations with hardcoded positions (`walk to -31, 7`)
   won't transfer directly - the agent must understand the *pattern* not the coordinates.
   `tas_agent.abstract_position()` strips coordinates before injection.

8. **Context length**: 5721 steps x ~40 tokens each = ~230K tokens. Too long for most
   models. Use first 40-100 steps (the critical early-game sequencing) rather than the
   full run.

9. **FLE scenario vs TAS scenario**: FLE's `default_lab_scenario` has pre-placed resources.
   The TAS plays on a generated freeplay map. The demonstrations may not transfer perfectly
   to FLE's constrained lab environment - this is an interesting finding either way.

10. **Entity-name validity**: TAS uses Factorio 1.1 names (`stone-furnace`,
    `burner-mining-drill`). These are valid in 1.1 - the target version - so no 2.0
    migration concern while scope stays at 1.1 + v0.3.0.

---

## Additional TAS Sources

| TAS | Source | Factorio version | Category | Usefulness |
|-----|--------|-----------------|----------|------------|
| Steelaxe2 (have it) | [mods.factorio.com](https://mods.factorio.com/mod/Theis_TAS_Steelaxe2) | 1.1 | Steel Axe% 7:35 | Primary |
| AutoFactorio | [github.com/Alex40144/AutoFactorio](https://github.com/Alex40144/AutoFactorio) | 2.0 | General automation | **Never implemented** - exists as a repo but no usable TAS data was produced. Do not use. |
| AnyPctTAS | [mods.factorio.com](https://mods.factorio.com/mod/AnyPctTAS) | 0.18 only | Any% rocket 1:21 | Skip - hard-pinned to 0.18.17 |
| Space Age TAS | - | - | Any% | Does not exist yet. Human WR is 7:31 (AntiElitz, Aug 2025). |

## Additional Related Papers (from audit)

- **"Leveraging In-Context Learning for Language Agents"** (arxiv 2506.13109, June 2025):
  Trajectory *snippets at each step* beat a single injected trajectory. Better design:
  retrieve 3-5 relevant TAS steps per agent turn rather than 40 upfront.

- **"Self-Generated In-Context Examples Improve LLM Agents"** (arxiv 2505.00234, May 2025):
  Accumulating agent's own successful trajectories: ALFWorld 73% -> 93%. Add as condition:
  TAS + accumulated successes.

- **"Imitation Learning via On-Policy Expert Corrections"** (arxiv 2512.14895, Dec 2024):
  Mixing student rollouts with expert corrections: 14% improvement over pure imitation.
  Apply to fine-tuning phase: hybrid agent+TAS trajectories, not pure TAS.

## Test Suite

Three tests in `research/tests/` catch silent failures:
- `test_parse_tas.py` - verify step translation correctness
- `test_tas_agent.py` - verify prompt has no broken placeholders, respects n limit
- `test_results_schema.py` - verify result JSON schema before summarize reads it

Run: `python -m pytest research/tests/`

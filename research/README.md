# Research: TAS-Grounded LLM Agents in Factorio

This directory contains an independent research extension of the
[Factorio Learning Environment](https://github.com/JackHopkins/factorio-learning-environment)
by Hopkins et al. (2025).

**Author:** [@maxrenke](https://github.com/maxrenke)
**Status:** Pre-experiment (setup phase)
**FLE version:** v0.3.0 (pinned - Factorio 1.1, 24 lab tasks, paper version)
**Factorio version:** 1.1.x (downgrade via Steam betas)

---

## Hypothesis

The FLE paper reports Claude 3.5-Sonnet completes 7/24 lab tasks, with failures
concentrated on long-horizon sequencing and spatial planning. We hypothesize that
injecting expert demonstration data from Tool-Assisted Speedruns (TAS) - optimal
human-authored action sequences from the Factorio speedrunning community - into the
agent's context will measurably improve lab task completion rates, particularly for
open-weight local models (7B-14B parameters).

## Research Questions

1. Does TAS context improve lab task completion rate across model types?
2. Does a reasoning model (DeepSeek-R1) benefit less from demonstrations than a code
   model (Qwen2.5-Coder), given that R1 already reasons step-by-step?
3. How many TAS steps are needed? Does the full run help, or just the early-game opening?
4. Can a local 14B model + TAS demonstrations close the gap with Claude 3.5-Sonnet zero-shot?

## Four-Phase Research Plan

| Phase | Model | Method | Goal |
|-------|-------|--------|------|
| **1** | qwen2.5-coder:14b (frozen) | Few-shot TAS context injection | Does expert demonstration context improve lab task completion? |
| **2** | qwen2.5-coder:14b | LoRA SFT on TAS (Unsloth, rank 16) | Do fine-tuned weights outperform in-context examples? |
| **3** | qwen2.5-coder:3b | Aggressive LoRA + distillation from Phase 2 | Can a small specialized model match a large zero-shot model? |
| **4** | qwen2.5-coder:3b | RL from FLE scores (PPO/GRPO, reward shaping, curriculum) | Can the model exceed the TAS via self-improvement? |

Full technical details including reward shaping formula and curriculum stages are in
[`notes/research-notes.md`](notes/research-notes.md) under "Training Roadmap: Four Phases".

## Directory Structure

```
research/
├── README.md                    <- this file
├── notes/
│   └── research-notes.md        <- full notes, setup guide, paper outline
├── agents/
│   └── tas_agent.py             <- TASGroundedAgent (BasicAgent subclass)
├── scripts/
│   ├── parse_tas.py             <- convert steps.lua -> FLE Python API calls
│   ├── run_experiment.py        <- run 24-task eval, save JSON results
│   ├── summarize_results.py     <- print comparison matrix from results/
│   ├── start_headless.ps1       <- start Factorio headless (Windows, no Docker)
│   ├── build_training_data.py   <- Phase 2: TAS trajectory -> (prompt, completion) JSONL
│   └── finetune_lora.py         <- Phase 2/3: Unsloth + SFTTrainer LoRA fine-tuning
├── data/
│   └── (TAS files go here - not committed, see setup below)
├── results/
│   └── (JSON result files - committed for reproducibility)
└── configs/
    └── (experiment config overrides)
```

## Setup (Windows, No Docker)

> **Harness status:** the eval scripts were written ahead of the FLE v0.3.0 API and
> have known blockers (wrong `BasicAgent` import path, non-existent `agent.run()`, repo
> source is v0.4.3 not v0.3.0). Work through the **PRE-FLIGHT validation gate (V0-V5)**
> in [`notes/research-notes.md`](notes/research-notes.md) before running any experiment.

Full setup instructions are in [`notes/research-notes.md`](notes/research-notes.md).
Quick version:

```powershell
# 0. Downgrade Factorio to 1.1 via Steam
#    Right-click Factorio -> Properties -> Betas -> select 1.1.x-branch

# 1. Clone and set up
git clone https://github.com/maxrenke/factorio-learning-environment.git
cd factorio-learning-environment
git remote add upstream https://github.com/JackHopkins/factorio-learning-environment.git
uv venv --python 3.13 && .venv\Scripts\Activate.ps1
uv pip install "factorio-learning-environment[eval]==0.3.0"

# 2. Copy FLE scenario into local Factorio (replaces Docker)
Copy-Item -Recurse fle\cluster\scenarios\default_lab_scenario `
    "$env:APPDATA\Factorio\scenarios\default_lab_scenario"

# 3. Download TAS mod, extract to research/data/tas/
#    https://mods.factorio.com/mod/Theis_TAS_Steelaxe2
Expand-Archive "$env:USERPROFILE\Downloads\Theis_TAS_Steelaxe2_0.3.0.zip" `
    -DestinationPath research\data\tas

# 4. Parse TAS into FLE-compatible calls
python research/scripts/parse_tas.py

# 5. Start Ollama + pull models
ollama pull qwen2.5-coder:14b
ollama pull deepseek-r1:14b

# 6. Start Factorio 1.1 headless
.\research\scripts\start_headless.ps1

# 7. Run baseline (zero-shot)
python research/scripts/run_experiment.py --model ollama-qwen2.5-coder:14b --condition zero_shot

# 8. Run with TAS context
python research/scripts/run_experiment.py --model ollama-qwen2.5-coder:14b --condition tas_40
```

## Comparison Matrix

Results are saved to `research/results/` as JSON and summarized with:

```powershell
python research/scripts/summarize_results.py
```

Target matrix (X/24 lab task completion rate):

```
                      zero_shot    tas_10    tas_40    tas_100
qwen2.5-coder:14b     [      ]    [    ]    [    ]    [     ]
qwen2.5-coder:7b      [      ]    [    ]    [    ]    [     ]
deepseek-r1:14b       [      ]    [    ]    [    ]    [     ]
phi4:14b              [      ]    [    ]    [    ]    [     ]
llama3.1:8b           [      ]    [    ]    [    ]    [     ]

FLE paper baseline (Claude 3.5-Sonnet, zero_shot): 7/24
```

## Models Tested

| Model | `ollama pull` | VRAM (Q4) | Hypothesis tested |
|-------|--------------|-----------|-------------------|
| `qwen2.5-coder:14b` | `qwen2.5-coder:14b` | ~8.5GB | Primary |
| `qwen2.5-coder:7b` | `qwen2.5-coder:7b` | ~4.5GB | Size ablation |
| `deepseek-r1:14b` | `deepseek-r1:14b` | ~9GB | Reasoning vs code |
| `phi4:14b` | `phi4:14b` | ~9GB | Generalist vs specialized |
| `llama3.1:8b` | `llama3.1:8b` | ~5GB | Unspecialized floor |

All fit in 12GB VRAM. Tested on RTX 4070 Super.

## TAS Data

**Source:** [Theis_TAS_Steelaxe2](https://mods.factorio.com/mod/Theis_TAS_Steelaxe2)
- Category: Steel Axe% (research Steel Axe as fast as possible)
- Time: 7:35.800
- Factorio version: 1.1
- Steps: 5,721 across 6,231 lines of Lua

The TAS is not executed directly in FLE. It is parsed into FLE-compatible Python API
calls (`parse_tas.py`) and injected as few-shot demonstrations in the system prompt.
Map-specific coordinates are abstracted to patterns before injection.

## Relationship to Upstream

This fork is designed to make upstreaming easy:

- All research additions live in `research/` - zero overlap with upstream files
- `research/agents/tas_agent.py` is a clean subclass of `BasicAgent` with no upstream changes
- `research/scripts/parse_tas.py` is standalone, no upstream dependencies beyond FLE install
- Results in `research/results/` are reproducible JSON - anyone with FLE + Ollama can replicate

If results are positive, the intended upstream contributions are:
1. `parse_tas.py` as a utility for community TAS integration
2. `TASGroundedAgent` as a reference implementation of demonstration-grounded agents
3. Results as a companion to an arxiv paper

## Related Work

- [TextAtari](https://arxiv.org/abs/2506.04098) (June 2025): expert demos most impactful factor for LLM game agents
- [Frog Soup](https://arxiv.org/abs/2505.03947) (May 2025): in-context demos improve LLM agents + bootstrap RL
- [FLE paper](https://arxiv.org/abs/2503.09617) (March 2025): baseline this work extends

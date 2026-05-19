"""
Phase 2: Convert TAS trajectory to (prompt, completion) JSONL pairs for LoRA fine-tuning.

Input:  research/data/tas_trajectory.json  (output of parse_tas.py)
Output: research/data/training_data.jsonl  (one JSON object per line)

Each pair:
  prompt     = game state context (inventory snapshot + last N actions as comments)
  completion = the FLE Python API call taken at this TAS step

Usage:
    python research/scripts/build_training_data.py
    python research/scripts/build_training_data.py --history 10 --output research/data/training_data.jsonl
"""

import argparse
import json
from pathlib import Path

SYSTEM_PROMPT = """\
You are a Factorio automation agent. Given the current game state and action history,
write the next Factorio Learning Environment (FLE) Python API call to progress toward
researching Steel Axe as efficiently as possible.

Available API calls (selection):
  move_to(position)
  harvest_resource(entity)
  nearest(type)
  place_entity(entity_type, direction, position)
  craft_item(item, count)
  insert_item(item, entity, count)
  extract_item(item, entity, count)
  inspect_inventory()
  set_research(technology)
  get_entities(types, position, radius)

Return only valid Python. No explanations. No markdown fences.
"""

GAME_STATE_TEMPLATE = """\
# Factorio game state - step {step}
# Inventory: {inventory}
# Last {n_history} actions:
{history_block}
# What is the next action?
"""


def build_fake_inventory(step_index: int) -> dict:
    """
    TAS trajectory doesn't carry full inventory state.
    Approximate inventory from prior actions in the trajectory.
    This is a best-effort heuristic - replace with real state extraction
    if you instrument the FLE environment during trajectory replay.
    """
    # Placeholder: real implementation would replay TAS in FLE and capture state
    return {"wood": max(0, 3 - step_index), "iron-ore": min(step_index * 2, 50)}


def build_history_block(history: list[dict]) -> str:
    lines = []
    for entry in history:
        fle_call = entry.get("fle") or f"# [{entry.get('action', '?')}]"
        lines.append(f"#   step {entry['step']:4d}: {fle_call}")
    return "\n".join(lines) if lines else "#   (none)"


def build_pairs(trajectory: list[dict], history_size: int) -> list[dict]:
    pairs = []
    for i, entry in enumerate(trajectory):
        fle_call = entry.get("fle")
        if not fle_call:
            continue  # skip actions with no FLE equivalent (speed, save, etc.)

        history = trajectory[max(0, i - history_size):i]
        inventory = build_fake_inventory(i)

        prompt = GAME_STATE_TEMPLATE.format(
            step=entry["step"],
            inventory=json.dumps(inventory),
            n_history=len(history),
            history_block=build_history_block(history),
        )

        pairs.append({
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": fle_call},
            ]
        })

    return pairs


def main(args):
    traj_path = Path(args.trajectory)
    if not traj_path.exists():
        raise FileNotFoundError(
            f"Trajectory not found: {traj_path}\n"
            "Run parse_tas.py first: python research/scripts/parse_tas.py"
        )

    trajectory = json.loads(traj_path.read_text())
    print(f"Loaded {len(trajectory)} TAS steps from {traj_path}")

    pairs = build_pairs(trajectory, args.history)
    print(f"Built {len(pairs)} training pairs (skipped {len(trajectory) - len(pairs)} no-FLE steps)")

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        for pair in pairs:
            f.write(json.dumps(pair) + "\n")

    print(f"Training data -> {out_path}")
    print(f"Token estimate: ~{len(pairs) * 120:,} tokens total (rough)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--trajectory", default="research/data/tas_trajectory.json")
    parser.add_argument("--output", default="research/data/training_data.jsonl")
    parser.add_argument("--history", type=int, default=10,
                        help="Number of prior steps to include in prompt context")
    args = parser.parse_args()
    main(args)

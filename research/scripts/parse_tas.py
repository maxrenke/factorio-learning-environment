"""
Parse Theis_TAS_Steelaxe2 steps.lua into FLE-compatible Python API calls.

Usage:
    python research/scripts/parse_tas.py \
        --input research/data/tas/Theis_TAS_Steelaxe2_0.3.0/steps.lua \
        --output research/data/tas_trajectory.json \
        --max-steps 100

Output format:
    [
      {"step": 1, "action": "walk", "fle": "move_to((-2.5, 10.5))", "raw": "..."},
      ...
    ]
"""

import re
import json
import argparse
from pathlib import Path


def parse_coords(line):
    # Step format: step[N] = {{task_id, subtask_id}, "action", {x, y}, ...}
    # The FIRST {a,b} group is the {task_id, subtask_id} prefix - skip it.
    # The coordinate pair, when present, is the SECOND {x,y} group.
    groups = re.findall(r"\{(-?[\d.]+),\s*(-?[\d.]+)\}", line)
    if len(groups) >= 2:
        return (float(groups[1][0]), float(groups[1][1]))
    return None


def parse_strings(line):
    # skip the {{task,subtask}, "action"} prefix, get remaining quoted strings
    return re.findall(r'"([\w][\w-]*)"', line)


def to_fle(line):
    """Convert a single step line to a FLE Python API call string."""
    if '"walk"' in line:
        coords = parse_coords(line)
        if coords:
            return f"move_to(({coords[0]}, {coords[1]}))"

    if '"build"' in line:
        coords = parse_coords(line)
        strings = parse_strings(line)
        # strings[0] = "build", strings[1] = entity name
        entity = strings[1] if len(strings) > 1 else "unknown"
        dir_match = re.search(r"defines\.direction\.(\w+)", line)
        direction = dir_match.group(1).upper() if dir_match else "NORTH"
        if coords:
            return f"place_entity('{entity}', direction=Direction.{direction}, position=({coords[0]}, {coords[1]}))"

    if '"mine"' in line:
        coords = parse_coords(line)
        if coords:
            return f"harvest_resource(nearest('resource', ({coords[0]}, {coords[1]})))"

    if '"craft"' in line:
        strings = parse_strings(line)
        # format: "craft", count, "item-name"
        count_match = re.search(r'"craft",\s*(-?\d+)', line)
        count = count_match.group(1) if count_match else "1"
        item = strings[1] if len(strings) > 1 else "unknown"
        return f"craft_item('{item}', {count})"

    if '"take"' in line:
        strings = parse_strings(line)
        item = strings[1] if len(strings) > 1 else "unknown"
        coords = parse_coords(line)
        pos = f"({coords[0]}, {coords[1]})" if coords else "None"
        return f"extract_item(get_entity(position={pos}), '{item}')"

    if '"put"' in line:
        strings = parse_strings(line)
        item = strings[1] if len(strings) > 1 else "unknown"
        coords = parse_coords(line)
        pos = f"({coords[0]}, {coords[1]})" if coords else "None"
        return f"insert_item(get_entity(position={pos}), '{item}')"

    if '"tech"' in line:
        strings = parse_strings(line)
        tech = strings[1] if len(strings) > 1 else "unknown"
        return f"set_research('{tech}')"

    if '"drop"' in line:
        strings = parse_strings(line)
        item = strings[1] if len(strings) > 1 else "unknown"
        return f"# drop {item} (no direct FLE equivalent)"

    if '"speed"' in line or '"save"' in line or '"pause"' in line:
        return None  # control flow, not agent actions

    return None


def parse_steps_lua(path: Path, max_steps: int = None):
    raw = path.read_text(encoding="utf-8")
    results = []

    for line in raw.splitlines():
        line = line.strip()
        m = re.match(r"step\[(\d+)\]\s*=\s*\{(.+)", line)
        if not m:
            continue

        step_idx = int(m.group(1))
        fle_call = to_fle(line)
        if fle_call is None:
            continue

        # Extract action type
        action_m = re.search(r'"(\w+)"', line)
        action = action_m.group(1) if action_m else "unknown"

        results.append({
            "step": step_idx,
            "action": action,
            "fle": fle_call,
            "raw": line,
        })

        if max_steps and len(results) >= max_steps:
            break

    return results


def build_few_shot_block(trajectory, n=40):
    """Return a Python code block string for use in a system prompt."""
    lines = []
    for entry in trajectory[:n]:
        lines.append(f"# step {entry['step']} ({entry['action']})")
        lines.append(entry["fle"])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="research/data/tas/Theis_TAS_Steelaxe2_0.3.0/steps.lua")
    parser.add_argument("--output", default="research/data/tas_trajectory.json")
    parser.add_argument("--max-steps", type=int, default=None)
    parser.add_argument("--few-shot-n", type=int, default=40)
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: {input_path} not found.")
        print("Extract the TAS zip first:")
        print("  Expand-Archive research/data/Theis_TAS_Steelaxe2_0.3.0.zip research/data/tas/")
        return 1

    trajectory = parse_steps_lua(input_path, args.max_steps)
    print(f"Parsed {len(trajectory)} steps")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(trajectory, indent=2))
    print(f"Saved to {output_path}")

    # Also write the few-shot block for quick inspection
    few_shot_path = output_path.parent / "tas_fewshot_40.py"
    few_shot_path.write_text(build_few_shot_block(trajectory, args.few_shot_n))
    print(f"Few-shot block ({args.few_shot_n} steps) -> {few_shot_path}")

    # Print a sample
    print("\n--- First 10 translated steps ---")
    for entry in trajectory[:10]:
        print(f"  {entry['step']:4d}  {entry['fle']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
Run a full 24-task FLE evaluation and save results to research/results/.

Usage:
    python research/scripts/run_experiment.py \
        --model ollama-qwen2.5-coder:14b \
        --condition zero_shot \
        --max-steps 50

    python research/scripts/run_experiment.py \
        --model ollama-qwen2.5-coder:14b \
        --condition tas_40 \
        --tas-steps 40

Conditions:
    zero_shot   - standard BasicAgent, no TAS context
    tas_N       - TASGroundedAgent with N steps injected

WARNING - NOT YET RUNNABLE against FLE v0.3.0 (blocker V4):
    run_single_task() calls `agent.run(instance, max_steps=...)`, but v0.3.0 has
    no such method. The real harness is GymTrajectoryRunner
    (fle/eval/algorithms/independent/trajectory_runner.py), constructed as
        GymTrajectoryRunner(config: GymEvalConfig, gym_env: FactorioGymEnv,
                            process_id, db_client, ...)
    and it drives a `GymAgent` (fle.agents.gym_agent) - NOT the BasicAgent this
    script and tas_agent.py subclass. Wrapping it correctly also requires
    FactorioGymEnv + GymEvalConfig + DBClient wiring. This is an architectural
    rewrite that needs the v0.3.0 source checked out (pre-flight V0) and a venv
    to validate against - do not attempt blind on the v0.4.3 working tree.
    The FactorioInstance construction below is fixed for v0.3.0; the agent loop
    is not. See roadmap step V4.
"""

import asyncio
import argparse
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path

# Add repo root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fle.env import FactorioInstance


def load_tasks():
    """
    Load FLE v0.3.0 lab tasks via the task registry.
    Returns list of task_key strings (env_ids).
    v0.3.0 has 24 throughput tasks defined in:
      fle.eval.tasks.task_definitions.lab_play.throughput_tasks.THROUGHPUT_TASKS
    """
    try:
        from fle.eval.tasks.task_definitions.lab_play.throughput_tasks import THROUGHPUT_TASKS
        return list(THROUGHPUT_TASKS.keys())
    except ImportError:
        raise ImportError(
            "Could not import FLE task definitions. "
            "Ensure FLE v0.3.0 is installed: uv pip install 'factorio-learning-environment==0.3.0'"
        )


async def run_single_task(instance, agent, task, max_steps: int):
    """Run one task, return result dict."""
    await instance.reset()
    try:
        conversation = await agent.run(instance, max_steps=max_steps)
        score = getattr(conversation, "score", None)
        completed = score is not None and score > 0
        return {
            "completed": completed,
            "score": score if score is not None else 0,
            "steps_taken": len(getattr(conversation, "messages", [])),
            "error": None,
        }
    except Exception as e:
        return {
            "completed": False,
            "score": 0,
            "steps_taken": 0,
            "error": str(e),
        }


async def main(args):
    results_dir = Path("research/results")
    results_dir.mkdir(parents=True, exist_ok=True)

    run_id = f"{args.model.replace('/', '_').replace(':', '_')}_{args.condition}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"Run: {run_id}")

    # Build agent
    if args.condition == "zero_shot":
        # v0.4.x: fle.agents.basic_agent  /  v0.3.0: examples.agents.basic_agent
        try:
            from fle.agents.basic_agent import BasicAgent
        except ImportError:
            from examples.agents.basic_agent import BasicAgent
        def make_agent(task):
            return BasicAgent(model=args.model, system_prompt="", task=task)
    elif args.condition.startswith("tas_"):
        from research.agents.tas_agent import TASGroundedAgent
        n = int(args.condition.split("_")[1])
        def make_agent(task):
            return TASGroundedAgent(model=args.model, task=task, tas_steps=n)
    else:
        raise ValueError(f"Unknown condition: {args.condition}. Use 'zero_shot' or 'tas_N'")

    # v0.3.0 API: FactorioInstance takes `tcp_port` (not `rcon_port`) and has no
    # password kwarg - the RCON password is the module constant RCON_PASSWORD.
    instance = FactorioInstance(
        address="localhost",
        tcp_port=args.tcp_port,
    )

    try:
        tasks = load_tasks()
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        print("Tip: inspect fle/configs/ to find the right task file path")
        return 1

    print(f"Loaded {len(tasks)} tasks")

    task_results = {}
    completed_count = 0

    for i, task_key in enumerate(tasks):
        task_name = task_key
        print(f"  [{i+1:2d}/{len(tasks)}] {task_name} ... ", end="", flush=True)

        # v0.3.0: create task object from registry key
        try:
            from fle.eval.tasks.task_definitions.task_registry import TaskRegistry
            registry = TaskRegistry()
            task_obj = registry.create_task(task_key)
        except Exception as e:
            print(f"ERROR creating task: {e}")
            task_results[task_name] = {"completed": False, "score": 0, "steps_taken": 0, "error": str(e)}
            continue

        agent = make_agent(task_obj)
        result = await run_single_task(instance, agent, task_obj, args.max_steps)

        task_results[task_name] = result
        if result["completed"]:
            completed_count += 1
            print(f"PASS (score={result['score']})")
        else:
            err = f" [{result['error'][:40]}]" if result["error"] else ""
            print(f"fail{err}")

    completion_rate = completed_count / len(tasks) if tasks else 0
    print(f"\nCompleted: {completed_count}/{len(tasks)} ({completion_rate:.1%})")

    output = {
        "run_id": run_id,
        "model": args.model,
        "condition": args.condition,
        "tas_steps_injected": int(args.condition.split("_")[1]) if args.condition.startswith("tas_") else 0,
        "factorio_version": "1.1.110",
        "fle_version": "0.3.0",
        "date": datetime.now().isoformat(),
        "max_steps_per_task": args.max_steps,
        "tasks": task_results,
        "summary": {
            "completed": completed_count,
            "total": len(tasks),
            "completion_rate": completion_rate,
        },
    }

    out_path = results_dir / f"{run_id}.json"
    out_path.write_text(json.dumps(output, indent=2))
    print(f"Results -> {out_path}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="ollama-qwen2.5-coder:14b")
    parser.add_argument("--condition", default="zero_shot",
                        help="zero_shot | tas_10 | tas_40 | tas_100")
    parser.add_argument("--max-steps", type=int, default=50)
    parser.add_argument("--tcp-port", type=int, default=27000,
                        help="FLE RCON/TCP port (FactorioInstance tcp_port)")
    args = parser.parse_args()

    raise SystemExit(asyncio.run(main(args)))

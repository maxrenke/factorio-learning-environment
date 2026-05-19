"""
Phase 2/3: LoRA fine-tuning on TAS-derived training data using Unsloth + SFTTrainer.

Requirements:
    pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"
    pip install trl datasets

Usage:
    # Phase 2: fine-tune 14B model (needs ~11GB VRAM)
    python research/scripts/finetune_lora.py --model Qwen/Qwen2.5-Coder-14B-Instruct

    # Phase 3: fine-tune 3B model (needs ~4GB VRAM)
    python research/scripts/finetune_lora.py --model Qwen/Qwen2.5-Coder-3B-Instruct --rank 64 --epochs 5

Output:
    research/models/<model-slug>-factorio-lora/   <- adapter weights only (~100MB)

To use with Ollama after training:
    # 1. Export to GGUF
    python -m unsloth.convert_to_gguf research/models/<slug>-factorio-lora --quantization q4_k_m
    # 2. Create Ollama modelfile
    # 3. ollama create factorio-agent -f Modelfile
"""

import argparse
from pathlib import Path

# Unsloth must be imported before transformers
try:
    from unsloth import FastLanguageModel
    from trl import SFTTrainer
    from transformers import TrainingArguments
    from datasets import load_dataset
    UNSLOTH_AVAILABLE = True
except ImportError:
    UNSLOTH_AVAILABLE = False


def slugify(model_name: str) -> str:
    return model_name.replace("/", "-").replace(":", "-").lower()


def main(args):
    if not UNSLOTH_AVAILABLE:
        raise ImportError(
            "Unsloth not installed. Run:\n"
            '  pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"\n'
            "  pip install trl datasets"
        )

    data_path = Path(args.data)
    if not data_path.exists():
        raise FileNotFoundError(
            f"Training data not found: {data_path}\n"
            "Run build_training_data.py first: python research/scripts/build_training_data.py"
        )

    output_dir = Path("research/models") / f"{slugify(args.model)}-factorio-lora"
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Model: {args.model}")
    print(f"LoRA rank: {args.rank}, alpha: {args.rank * 2}")
    print(f"Epochs: {args.epochs}")
    print(f"Output: {output_dir}")

    # Load base model with 4-bit quantization
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.model,
        max_seq_length=2048,
        load_in_4bit=True,
        dtype=None,  # auto-detect: bfloat16 on Ampere+, float16 otherwise
    )

    # Attach LoRA adapters
    # Target all projection layers for maximum coverage
    model = FastLanguageModel.get_peft_model(
        model,
        r=args.rank,
        lora_alpha=args.rank * 2,
        lora_dropout=0.0,  # 0 is optimal per Unsloth docs
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
        bias="none",
        use_gradient_checkpointing="unsloth",  # saves ~30% VRAM vs standard checkpointing
        random_state=42,
        use_rslora=False,
        loftq_config=None,
    )

    # Load training data
    dataset = load_dataset("json", data_files=str(data_path), split="train")
    print(f"Training examples: {len(dataset)}")

    def format_chat(example):
        """Apply chat template to message list."""
        return {
            "text": tokenizer.apply_chat_template(
                example["messages"],
                tokenize=False,
                add_generation_prompt=False,
            )
        }

    dataset = dataset.map(format_chat, remove_columns=dataset.column_names)

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=2048,
        dataset_num_proc=2,
        packing=True,  # pack short sequences together to fill context window
        args=TrainingArguments(
            per_device_train_batch_size=2,
            gradient_accumulation_steps=4,   # effective batch = 8
            warmup_steps=10,
            num_train_epochs=args.epochs,
            learning_rate=2e-4,
            fp16=True,
            logging_steps=10,
            optim="adamw_8bit",              # 8-bit optimizer saves VRAM
            weight_decay=0.01,
            lr_scheduler_type="linear",
            seed=42,
            output_dir=str(output_dir / "checkpoints"),
            report_to="none",               # set to "wandb" if you want tracking
        ),
    )

    print("\nStarting training...")
    trainer_stats = trainer.train()
    print(f"\nTraining complete. Loss: {trainer_stats.training_loss:.4f}")

    # Save LoRA adapter only (not the full model - saves disk space)
    model.save_pretrained(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))
    print(f"\nLoRA adapter saved to: {output_dir}")
    print("\nNext steps:")
    print(f"  1. Export to GGUF: python -m unsloth.convert_to_gguf {output_dir} --quantization q4_k_m")
    print("  2. Create Ollama modelfile pointing to the GGUF")
    print("  3. ollama create factorio-agent -f Modelfile")
    print("  4. python research/scripts/run_experiment.py --model ollama-factorio-agent --condition zero_shot")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="Qwen/Qwen2.5-Coder-14B-Instruct",
                        help="HuggingFace model ID. Use 3B variant for Phase 3.")
    parser.add_argument("--data", default="research/data/training_data.jsonl",
                        help="JSONL training data from build_training_data.py")
    parser.add_argument("--rank", type=int, default=16,
                        help="LoRA rank. 16 for 14B (VRAM limited), 64 for 3B.")
    parser.add_argument("--epochs", type=int, default=3)
    args = parser.parse_args()
    main(args)

"""
ScanFiler — Configuration Management (Local-Only Version)

Manages persistent settings stored at ~/.scanfiler/config.json.
No API keys needed — everything runs locally with Tesseract + Ollama.
"""

import json
import os
import sys
from pathlib import Path

CONFIG_DIR = Path.home() / ".scanfiler"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "inbox_path": str(Path.home() / "Downloads"),
    "output_path": str(Path.home() / "Documents" / "Filed"),
    "supported_extensions": [".pdf", ".jpg", ".jpeg", ".png", ".tiff", ".tif", ".heic"],
    "rename_files": True,
    "min_confidence": 0.70,
    "ollama_model": "llama3.2",
    "ollama_host": "http://localhost:11434",
}


def load_config() -> dict:
    """Load configuration from disk. Returns default config if file doesn't exist."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r") as f:
            saved = json.load(f)
        # Merge with defaults so new keys are always present
        merged = {**DEFAULT_CONFIG, **saved}
        return merged
    return dict(DEFAULT_CONFIG)


def save_config(config: dict) -> None:
    """Save configuration to disk, creating the directory if needed."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def is_configured() -> bool:
    """Check whether the app has been set up."""
    return CONFIG_FILE.exists()


def run_setup(force: bool = False) -> dict:
    """
    Interactive first-run setup wizard.
    Confirms inbox/output paths and Ollama model preference.
    """
    config = load_config()

    if is_configured() and not force:
        return config

    print("\n╔══════════════════════════════════════════════╗")
    print("║     🗂️  ScanFiler — First-Run Setup          ║")
    print("║     100% Local • No Data Leaves Your Mac     ║")
    print("╚══════════════════════════════════════════════╝\n")

    # --- Inbox Path ---
    print(f"1️⃣  Scan Inbox (where scanned docs land)")
    print(f"   Current: {config['inbox_path']}")
    inbox_input = input("   Enter new path (or press Enter to keep current): ").strip()
    if inbox_input:
        config["inbox_path"] = str(Path(inbox_input).expanduser().resolve())

    # --- Output Path ---
    print(f"\n2️⃣  Filing Destination (organized folder)")
    print(f"   Current: {config['output_path']}")
    output_input = input("   Enter new path (or press Enter to keep current): ").strip()
    if output_input:
        config["output_path"] = str(Path(output_input).expanduser().resolve())

    # --- Ollama Model ---
    print(f"\n3️⃣  Ollama Model")
    print(f"   Current: {config['ollama_model']}")
    print(f"   Recommended: llama3.2 (fast, ~2GB)")
    model_input = input("   Enter model name (or press Enter to keep current): ").strip()
    if model_input:
        config["ollama_model"] = model_input

    # --- Rename preference ---
    print(f"\n4️⃣  File Renaming")
    print(f"   Rename files to descriptive names? (e.g., TD_Bank_Statement_June_2026.pdf)")
    rename_input = input(f"   [Y/n] (current: {'Yes' if config['rename_files'] else 'No'}): ").strip().lower()
    if rename_input in ("n", "no"):
        config["rename_files"] = False
    elif rename_input in ("y", "yes", ""):
        config["rename_files"] = True

    # --- Save ---
    save_config(config)

    print("\n   ✅ Configuration saved to ~/.scanfiler/config.json")
    print(f"   📂 Inbox:  {config['inbox_path']}")
    print(f"   📁 Output: {config['output_path']}")
    print(f"   🤖 Model:  {config['ollama_model']}")
    print(f"   📝 Rename: {'Yes' if config['rename_files'] else 'No'}")
    print(f"\n   🔒 All processing happens locally on your Mac.\n")

    return config


def get_config() -> dict:
    """Get the current config, running setup if needed."""
    if not is_configured():
        return run_setup()
    return load_config()

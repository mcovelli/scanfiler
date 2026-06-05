"""
ScanFiler — Move Logger & Undo System

Maintains an append-only JSONL log at ~/.scanfiler/move_log.jsonl.
Each run gets a unique batch_id so entire batches can be undone at once.
"""

import json
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from config import CONFIG_DIR

LOG_FILE = CONFIG_DIR / "move_log.jsonl"


def generate_batch_id() -> str:
    """Generate a unique batch ID for this processing run."""
    return uuid.uuid4().hex[:8]


def log_move(
    batch_id: str,
    source: str,
    destination: str,
    classification: dict,
) -> None:
    """Append a move record to the log file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    record = {
        "timestamp": datetime.now().isoformat(),
        "batch_id": batch_id,
        "source": source,
        "destination": destination,
        "classification": classification,
    }

    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(record) + "\n")


def load_log() -> list[dict]:
    """Load all log records from disk."""
    if not LOG_FILE.exists():
        return []

    records = []
    with open(LOG_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def get_batches() -> dict[str, list[dict]]:
    """Group log records by batch_id, preserving order."""
    records = load_log()
    batches: dict[str, list[dict]] = {}
    for rec in records:
        bid = rec["batch_id"]
        if bid not in batches:
            batches[bid] = []
        batches[bid].append(rec)
    return batches


def get_last_batch_id() -> str | None:
    """Get the batch_id of the most recent batch."""
    records = load_log()
    if not records:
        return None
    return records[-1]["batch_id"]


def undo_batch(batch_id: str) -> list[dict]:
    """
    Undo all moves in a given batch.
    Moves files back to their original locations and cleans up empty folders.
    Returns a list of results with status for each file.
    """
    records = load_log()
    batch_records = [r for r in records if r["batch_id"] == batch_id]

    if not batch_records:
        return []

    results = []

    for rec in reversed(batch_records):  # Reverse order for clean undo
        src = rec["destination"]  # Current location (was the destination)
        dst = rec["source"]  # Original location (was the source)

        result = {
            "source": src,
            "destination": dst,
            "classification": rec["classification"],
        }

        if not Path(src).exists():
            result["status"] = "skipped"
            result["reason"] = "File no longer at destination"
            results.append(result)
            continue

        # Ensure the original directory exists
        Path(dst).parent.mkdir(parents=True, exist_ok=True)

        try:
            shutil.move(src, dst)
            result["status"] = "restored"

            # Clean up empty parent directories up to the output root
            _cleanup_empty_dirs(Path(src).parent)

        except Exception as e:
            result["status"] = "error"
            result["reason"] = str(e)

        results.append(result)

    # Remove the undone records from the log
    remaining = [r for r in records if r["batch_id"] != batch_id]
    _rewrite_log(remaining)

    return results


def undo_all() -> list[dict]:
    """Undo all batches, most recent first."""
    batches = get_batches()
    all_results = []

    # Process batches in reverse chronological order
    batch_ids = list(batches.keys())
    for bid in reversed(batch_ids):
        results = undo_batch(bid)
        all_results.extend(results)

    return all_results


def print_log() -> None:
    """Print a formatted table of all move records."""
    records = load_log()

    if not records:
        print("\n  📋 No moves recorded yet.\n")
        return

    print(f"\n  📋 Move History ({len(records)} total moves)\n")
    print(f"  {'Timestamp':<22} {'Batch':<10} {'Type':<20} {'Company':<15} {'File':<30}")
    print(f"  {'─' * 22} {'─' * 10} {'─' * 20} {'─' * 15} {'─' * 30}")

    for rec in records:
        ts = rec["timestamp"][:19]
        bid = rec["batch_id"]
        cls = rec.get("classification", {})
        doc_type = cls.get("document_type", "Unknown")[:20]
        company = cls.get("company", "Unknown")[:15]
        filename = Path(rec["destination"]).name[:30]

        print(f"  {ts:<22} {bid:<10} {doc_type:<20} {company:<15} {filename:<30}")

    print()


def _cleanup_empty_dirs(directory: Path) -> None:
    """Remove empty directories walking upward, stop at home directory."""
    home = Path.home()
    current = directory

    while current != home and current != current.parent:
        try:
            if current.is_dir() and not any(current.iterdir()):
                current.rmdir()
            else:
                break
        except OSError:
            break
        current = current.parent


def _rewrite_log(records: list[dict]) -> None:
    """Rewrite the entire log file with the given records."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")

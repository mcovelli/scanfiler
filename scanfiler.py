#!/usr/bin/env python3
"""
ScanFiler — Automated Document Filing System (100% Local)

Classifies scanned documents using Tesseract OCR + Ollama LLM
and files them into an organized folder structure.
No data ever leaves your machine.

Usage:
    python scanfiler.py                     Process all files in inbox
    python scanfiler.py --dry-run           Preview without moving
    python scanfiler.py --undo              Undo the last batch
    python scanfiler.py --undo-all          Undo all moves
    python scanfiler.py --log               Show move history
    python scanfiler.py --setup             Re-run setup wizard
    python scanfiler.py /path/to/file.pdf   Process a specific file
"""

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

from config import get_config, run_setup
from classifier import classify_document
from filer import build_destination, move_file
from logger import generate_batch_id, log_move, print_log, undo_batch, undo_all, get_last_batch_id


# ─── ANSI Colors ────────────────────────────────────────────────────────────

class Colors:
    BOLD = "\033[1m"
    DIM = "\033[2m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    RESET = "\033[0m"


# ─── Preflight Checks ──────────────────────────────────────────────────────

def check_dependencies() -> bool:
    """Verify that Tesseract and Ollama are available."""
    ok = True

    # Check Tesseract
    if not shutil.which("tesseract"):
        print(f"  {Colors.RED}❌ Tesseract not found.{Colors.RESET}")
        print(f"     Install it: brew install tesseract")
        ok = False

    # Check Ollama
    if not shutil.which("ollama"):
        print(f"  {Colors.RED}❌ Ollama not found.{Colors.RESET}")
        print(f"     Install it: https://ollama.com/download")
        ok = False
    else:
        # Check if Ollama is running
        try:
            import ollama
            ollama.list()
        except Exception:
            print(f"  {Colors.YELLOW}⚠️  Ollama may not be running.{Colors.RESET}")
            print(f"     Start it: ollama serve")

    return ok


# ─── Core Processing ────────────────────────────────────────────────────────

def find_files(inbox_path: str, extensions: list[str]) -> list[Path]:
    """Find all supported files in the inbox directory."""
    inbox = Path(inbox_path).expanduser()

    if not inbox.exists():
        print(f"\n  {Colors.RED}❌ Inbox directory not found: {inbox}{Colors.RESET}")
        sys.exit(1)

    files = []
    # Convert extensions to a lowercase set for efficient, case-insensitive lookups
    supported = {ext.lower() for ext in extensions}

    unique_files = [
        f for f in inbox.iterdir()
        if f.is_file() and f.suffix.lower() in supported
    ]

    unique_files.sort(key=lambda f: f.name.lower())
    return unique_files


def process_file(
    file_path: Path,
    config: dict,
    batch_id: str,
    dry_run: bool = False,
) -> dict:
    """
    Process a single file: OCR it, classify with LLM, then move it.
    Returns a result dict with status and details.
    """
    result = {
        "file": str(file_path),
        "filename": file_path.name,
    }

    # Step 1: OCR + Classify with local LLM
    print(f"\n  {Colors.CYAN}🔍 Analyzing:{Colors.RESET} {file_path.name}")
    print(f"     {Colors.DIM}Running OCR → classifying with Ollama...{Colors.RESET}")

    classification = classify_document(
        str(file_path),
        model=config["ollama_model"],
        host=config["ollama_host"],
    )

    result["classification"] = classification

    # Show OCR preview if available
    ocr_preview = classification.pop("ocr_preview", None)
    if ocr_preview:
        preview_clean = ocr_preview.replace("\n", " ")[:80]
        print(f"     {Colors.DIM}OCR: \"{preview_clean}\"{Colors.RESET}")

    # Check for errors
    if "error" in classification:
        print(f"     {Colors.RED}❌ Error: {classification['error']}{Colors.RESET}")
        result["status"] = "error"
        return result

    # Check confidence threshold
    confidence = classification.get("confidence", 0)
    min_conf = config.get("min_confidence", 0.70)

    doc_type = classification.get("document_type", "Unknown")
    company = classification.get("company", "Unknown")
    date = classification.get("date")
    suggested = classification.get("suggested_filename")

    print(f"     {Colors.MAGENTA}📄 Type:{Colors.RESET}       {doc_type}")
    print(f"     {Colors.MAGENTA}🏢 Company:{Colors.RESET}    {company}")
    print(f"     {Colors.MAGENTA}📅 Date:{Colors.RESET}       {date or 'Not found'}")
    print(f"     {Colors.MAGENTA}🎯 Confidence:{Colors.RESET} {confidence:.0%}")

    if confidence < min_conf:
        print(f"     {Colors.YELLOW}⚠️  Low confidence ({confidence:.0%} < {min_conf:.0%}) — skipping{Colors.RESET}")
        result["status"] = "low_confidence"
        return result

    # Step 2: Build destination
    destination = build_destination(
        output_root=config["output_path"],
        document_type=doc_type,
        company=company,
        date=date,
        original_filename=file_path.name,
        suggested_filename=suggested,
        rename=config.get("rename_files", True),
    )

    result["destination"] = str(destination)

    print(f"     {Colors.BLUE}📁 Destination:{Colors.RESET} {destination}")

    if dry_run:
        print(f"     {Colors.YELLOW}🏃 Dry run — not moving{Colors.RESET}")
        result["status"] = "dry_run"
        return result

    # Step 3: Move the file
    try:
        actual_dest = move_file(str(file_path), destination)
        result["actual_destination"] = str(actual_dest)

        # Step 4: Log the move
        log_move(
            batch_id=batch_id,
            source=str(file_path),
            destination=str(actual_dest),
            classification=classification,
        )

        print(f"     {Colors.GREEN}✅ Filed successfully!{Colors.RESET}")
        result["status"] = "filed"

    except Exception as e:
        print(f"     {Colors.RED}❌ Move failed: {e}{Colors.RESET}")
        result["status"] = "error"
        result["error"] = str(e)

    return result


def process_all(config: dict, dry_run: bool = False) -> None:
    """Process all supported files in the inbox."""
    files = find_files(config["inbox_path"], config["supported_extensions"])

    if not files:
        print(f"\n  {Colors.DIM}📭 No supported files found in {config['inbox_path']}{Colors.RESET}")
        print(f"  {Colors.DIM}   Supported types: {', '.join(config['supported_extensions'])}{Colors.RESET}\n")
        return

    mode = f"{Colors.YELLOW}DRY RUN{Colors.RESET}" if dry_run else f"{Colors.GREEN}LIVE{Colors.RESET}"

    print(f"\n  ╔══════════════════════════════════════════════╗")
    print(f"  ║      🗂️  ScanFiler — Processing (Local)       ║")
    print(f"  ║      🔒 No data leaves your machine           ║")
    print(f"  ╚══════════════════════════════════════════════╝")
    print(f"\n  📂 Inbox:  {config['inbox_path']}")
    print(f"  📁 Output: {config['output_path']}")
    print(f"  🤖 Model:  {config['ollama_model']}")
    print(f"  📄 Files:  {len(files)} found")
    print(f"  🔄 Mode:   {mode}")

    batch_id = generate_batch_id()
    results = []

    for i, file_path in enumerate(files, 1):
        print(f"\n  ── File {i}/{len(files)} {'─' * 40}")
        result = process_file(file_path, config, batch_id, dry_run)
        results.append(result)

    # Summary
    filed = sum(1 for r in results if r["status"] == "filed")
    skipped = sum(1 for r in results if r["status"] == "low_confidence")
    errors = sum(1 for r in results if r["status"] == "error")
    dry = sum(1 for r in results if r["status"] == "dry_run")

    print(f"\n  ── Summary {'─' * 42}")

    if dry_run:
        print(f"  {Colors.YELLOW}🏃 Dry run complete: {dry} files would be filed{Colors.RESET}")
    else:
        print(f"  {Colors.GREEN}✅ Filed: {filed}{Colors.RESET}")

    if skipped:
        print(f"  {Colors.YELLOW}⚠️  Skipped (low confidence): {skipped}{Colors.RESET}")
    if errors:
        print(f"  {Colors.RED}❌ Errors: {errors}{Colors.RESET}")

    if filed > 0:
        print(f"\n  {Colors.DIM}💡 Run 'python scanfiler.py --undo' to undo this batch (ID: {batch_id}){Colors.RESET}")

    print()


def process_specific_files(file_paths: list[str], config: dict, dry_run: bool = False) -> None:
    """Process a list of specified files."""
    valid_files = []
    for file_path in file_paths:
        path = Path(file_path).expanduser().resolve()
        
        if not path.exists():
            print(f"\n  {Colors.RED}❌ File not found: {file_path}{Colors.RESET}")
            continue

        ext = path.suffix.lower()
        if ext not in config["supported_extensions"]:
            print(f"\n  {Colors.RED}❌ Unsupported file type: {ext} for {file_path}{Colors.RESET}")
            continue
            
        valid_files.append(path)
        
    if not valid_files:
        print(f"\n  {Colors.DIM}📭 No valid files found to process.{Colors.RESET}\n")
        return

    mode = f"{Colors.YELLOW}DRY RUN{Colors.RESET}" if dry_run else f"{Colors.GREEN}LIVE{Colors.RESET}"

    print(f"\n  ╔══════════════════════════════════════════════╗")
    print(f"  ║   🗂️  ScanFiler — Specific Files (Local)      ║")
    print(f"  ║   🔒 No data leaves your machine              ║")
    print(f"  ╚══════════════════════════════════════════════╝")
    print(f"\n  📁 Output: {config['output_path']}")
    print(f"  🤖 Model:  {config['ollama_model']}")
    print(f"  📄 Files:  {len(valid_files)} found")
    print(f"  🔄 Mode:   {mode}")

    batch_id = generate_batch_id()
    results = []

    for i, file_path in enumerate(valid_files, 1):
        print(f"\n  ── File {i}/{len(valid_files)} {'─' * 40}")
        result = process_file(file_path, config, batch_id, dry_run)
        results.append(result)

    # Summary
    filed = sum(1 for r in results if r["status"] == "filed")
    skipped = sum(1 for r in results if r["status"] == "low_confidence")
    errors = sum(1 for r in results if r["status"] == "error")
    dry = sum(1 for r in results if r["status"] == "dry_run")

    print(f"\n  ── Summary {'─' * 42}")

    if dry_run:
        print(f"  {Colors.YELLOW}🏃 Dry run complete: {dry} files would be filed{Colors.RESET}")
    else:
        print(f"  {Colors.GREEN}✅ Filed: {filed}{Colors.RESET}")

    if skipped:
        print(f"  {Colors.YELLOW}⚠️  Skipped (low confidence): {skipped}{Colors.RESET}")
    if errors:
        print(f"  {Colors.RED}❌ Errors: {errors}{Colors.RESET}")

    if filed > 0:
        print(f"\n  {Colors.DIM}💡 Run 'python scanfiler.py --undo' to undo this batch (ID: {batch_id}){Colors.RESET}")

    print()



# ─── Undo Commands ──────────────────────────────────────────────────────────

def handle_undo() -> None:
    """Undo the last batch of moves."""
    batch_id = get_last_batch_id()

    if not batch_id:
        print(f"\n  {Colors.DIM}📋 No moves to undo.{Colors.RESET}\n")
        return

    print(f"\n  ╔══════════════════════════════════════════════╗")
    print(f"  ║           🗂️  ScanFiler — Undo               ║")
    print(f"  ╚══════════════════════════════════════════════╝")
    print(f"\n  🔄 Undoing batch: {batch_id}\n")

    results = undo_batch(batch_id)

    restored = sum(1 for r in results if r["status"] == "restored")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    errors = sum(1 for r in results if r["status"] == "error")

    for r in results:
        name = Path(r["destination"]).name
        if r["status"] == "restored":
            print(f"  {Colors.GREEN}✅ Restored:{Colors.RESET} {name}")
        elif r["status"] == "skipped":
            print(f"  {Colors.YELLOW}⚠️  Skipped:{Colors.RESET} {name} — {r.get('reason', '')}")
        else:
            print(f"  {Colors.RED}❌ Error:{Colors.RESET} {name} — {r.get('reason', '')}")

    print(f"\n  ── Summary {'─' * 42}")
    print(f"  {Colors.GREEN}✅ Restored: {restored}{Colors.RESET}")
    if skipped:
        print(f"  {Colors.YELLOW}⚠️  Skipped: {skipped}{Colors.RESET}")
    if errors:
        print(f"  {Colors.RED}❌ Errors: {errors}{Colors.RESET}")
    print()


def handle_undo_all() -> None:
    """Undo all batches."""
    print(f"\n  ╔══════════════════════════════════════════════╗")
    print(f"  ║        🗂️  ScanFiler — Undo All              ║")
    print(f"  ╚══════════════════════════════════════════════╝\n")

    confirm = input("  ⚠️  This will undo ALL moves. Are you sure? [y/N] ").strip().lower()
    if confirm not in ("y", "yes"):
        print(f"\n  {Colors.DIM}Cancelled.{Colors.RESET}\n")
        return

    results = undo_all()

    if not results:
        print(f"\n  {Colors.DIM}📋 No moves to undo.{Colors.RESET}\n")
        return

    restored = sum(1 for r in results if r["status"] == "restored")
    print(f"\n  {Colors.GREEN}✅ Restored {restored} files to their original locations.{Colors.RESET}\n")


# ─── CLI Entry Point ────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="🗂️  ScanFiler — Automated Document Filing (100% Local)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                     Process all files in inbox (~/Downloads)
  %(prog)s --dry-run           Preview what would happen without moving files
  %(prog)s --undo              Undo the last batch of moves
  %(prog)s --log               View the full move history
  %(prog)s ~/Downloads/doc1.pdf ~/Downloads/doc2.pdf Process specific files
  %(prog)s --setup             Re-run the setup wizard

🔒 All processing happens locally. No data leaves your machine.
        """,
    )

    parser.add_argument(
        "files",
        nargs="*",
        help="Path to specific file(s) to process (optional)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview classification and destination without moving files",
    )
    parser.add_argument(
        "--undo",
        action="store_true",
        help="Undo the last batch of moves",
    )
    parser.add_argument(
        "--undo-all",
        action="store_true",
        help="Undo all moves ever made",
    )
    parser.add_argument(
        "--log",
        action="store_true",
        help="Show the full move history",
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Re-run the setup wizard",
    )

    args = parser.parse_args()

    # Handle non-processing commands first
    if args.undo:
        handle_undo()
        return

    if args.undo_all:
        handle_undo_all()
        return

    if args.log:
        print_log()
        return

    if args.setup:
        run_setup(force=True)
        return

    # For processing commands, check dependencies and config
    if not check_dependencies():
        print(f"\n  {Colors.RED}Fix the above issues and try again.{Colors.RESET}\n")
        sys.exit(1)

    config = get_config()

    if args.files:
        process_specific_files(args.files, config, dry_run=args.dry_run)
    else:
        process_all(config, dry_run=args.dry_run)


if __name__ == "__main__":
    main()

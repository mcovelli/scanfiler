"""
ScanFiler — File Organization & Movement

Handles the actual file operations: building the destination path,
creating folder structures, handling duplicates, and moving files.
"""

import os
import re
import shutil
from pathlib import Path


def build_destination(
    output_root: str,
    document_type: str,
    company: str,
    date: str | None,
    original_filename: str,
    suggested_filename: str | None,
    rename: bool = True,
) -> Path:
    """
    Build the full destination path for a classified document.
    
    Structure: <output_root>/<Document Type>/<Company>/<Year>/<filename>
    
    Args:
        output_root: Base output directory (e.g., ~/Documents/Filed)
        document_type: Classification type (e.g., "Bank Statement")
        company: Company name (e.g., "TD Bank")
        date: Date string in YYYY-MM or YYYY format, or None
        original_filename: Original file name with extension
        suggested_filename: AI-suggested descriptive name (no extension), or None
        rename: If True, use suggested_filename; if False, keep original
    
    Returns:
        Full Path to the destination file.
    """
    root = Path(output_root).expanduser()

    # Sanitize folder names (remove characters that are problematic in paths)
    doc_type_folder = _sanitize_folder_name(document_type or "Uncategorized")
    company_folder = _sanitize_folder_name(company or "Unknown")

    # Extract year from date
    year_folder = _extract_year(date)

    # Build the directory path
    dest_dir = root / doc_type_folder / company_folder / year_folder

    # Determine filename
    original_ext = Path(original_filename).suffix
    if rename and suggested_filename:
        filename = _sanitize_filename(suggested_filename) + original_ext
    else:
        filename = original_filename

    return dest_dir / filename


def move_file(source: str, destination: Path) -> Path:
    """
    Move a file to the destination, creating directories as needed.
    Handles duplicate filenames by appending a counter.
    
    Args:
        source: Source file path.
        destination: Desired destination Path.
    
    Returns:
        The actual Path the file was moved to (may differ if deduped).
    """
    # Create destination directory
    destination.parent.mkdir(parents=True, exist_ok=True)

    # Handle duplicates
    final_dest = _deduplicate(destination)

    # Move the file
    shutil.move(str(source), str(final_dest))

    return final_dest


def _sanitize_folder_name(name: str) -> str:
    """
    Clean a string for use as a folder name.
    Removes/replaces problematic characters while keeping it readable.
    """
    # Replace slashes, colons, and other problematic chars with spaces
    cleaned = re.sub(r'[/\\:*?"<>|]', " ", name)
    # Collapse multiple spaces
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    # Title-case it for consistency
    cleaned = cleaned.title()
    return cleaned or "Unknown"


def _sanitize_filename(name: str) -> str:
    """
    Clean a string for use as a filename (without extension).
    Replaces spaces with underscores and removes problematic characters.
    """
    # Replace spaces with underscores
    cleaned = name.replace(" ", "_")
    # Remove problematic characters
    cleaned = re.sub(r'[/\\:*?"<>|]', "", cleaned)
    # Collapse multiple underscores
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "document"


def _extract_year(date: str | None) -> str:
    """
    Extract the year from a date string.
    Expects YYYY-MM, YYYY, or None.
    Returns the year string or 'Undated'.
    """
    if not date:
        return "Undated"

    # Try to find a 4-digit year
    match = re.search(r"(\d{4})", str(date))
    if match:
        return match.group(1)

    return "Undated"


def _deduplicate(path: Path) -> Path:
    """
    If a file already exists at the given path, append a counter.
    e.g., file.pdf → file_2.pdf → file_3.pdf
    """
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 2

    while True:
        new_path = parent / f"{stem}_{counter}{suffix}"
        if not new_path.exists():
            return new_path
        counter += 1

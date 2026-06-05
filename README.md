# 🗂️ ScanFiler

**Automated document filing powered by local AI. No data ever leaves your machine.**

ScanFiler uses [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) and a local [Ollama](https://ollama.com) LLM to automatically classify scanned documents — bank statements, bills, tax forms, and more — and organize them into a clean folder structure.

```
~/Downloads/scan_20260605.pdf
        ↓  scanfiler classifies it as a TD Bank statement from June 2026
~/Documents/Filed/Bank Statements/TD Bank/2026/TD_Bank_Statement_June_2026.pdf
```

## ✨ Features

- **🔒 100% Local & Private** — All processing happens on your Mac. No cloud APIs, no internet needed, no data transmitted anywhere.
- **🤖 AI-Powered Classification** — Uses a local LLM (llama3.2 via Ollama) to intelligently identify document types, companies, and dates.
- **📄 OCR Built-In** — Extracts text from scanned PDFs and images using Tesseract.
- **📁 Smart Filing** — Organizes into `<Type>/<Company>/<Year>/` folder hierarchy.
- **📝 Descriptive Renaming** — Optionally renames files (e.g., `scan001.pdf` → `TD_Bank_Statement_June_2026.pdf`).
- **↩️ Full Undo** — Every move is logged. Undo the last batch or all moves with one command.
- **🏃 Dry Run Mode** — Preview what would happen before moving anything.
- **📋 Move History** — View a formatted log of all past filing operations.

---

## 📋 Table of Contents

- [Requirements](#requirements)
- [Installation](#installation)
  - [Step 1: Install Homebrew](#step-1-install-homebrew)
  - [Step 2: Install System Dependencies](#step-2-install-system-dependencies)
  - [Step 3: Install Ollama and Download the Model](#step-3-install-ollama-and-download-the-model)
  - [Step 4: Clone and Set Up ScanFiler](#step-4-clone-and-set-up-scanfiler)
  - [Step 5: First-Run Setup](#step-5-first-run-setup)
- [Usage](#usage)
  - [Process All Files](#process-all-files)
  - [Dry Run (Preview)](#dry-run-preview)
  - [Process a Single File](#process-a-single-file)
  - [Undo](#undo)
  - [View History](#view-history)
  - [Reconfigure](#reconfigure)
- [Folder Structure](#folder-structure)
- [Configuration](#configuration)
- [Setting Up a Shell Alias](#setting-up-a-shell-alias)
- [Supported File Types](#supported-file-types)
- [Troubleshooting](#troubleshooting)
- [Limitations](#limitations)
- [How It Works](#how-it-works)
- [License](#license)

---

## Requirements

| Dependency | Purpose | Install Method |
|---|---|---|
| **macOS** | Operating system (tested on macOS 13+) | — |
| **Python 3.10+** | Runtime | `brew install python` |
| **Tesseract** | OCR engine (extracts text from images/PDFs) | `brew install tesseract` |
| **Poppler** | PDF → image conversion (needed for PDF OCR) | `brew install poppler` |
| **Ollama** | Local LLM runtime | [ollama.com/download](https://ollama.com/download) |
| **llama3.2** | AI model for classification (~2GB) | `ollama pull llama3.2` |

> **Disk space:** ~2.5 GB total for Ollama + the llama3.2 model. All other dependencies are lightweight.

---

## Installation

### Step 1: Install Homebrew

If you don't already have Homebrew:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

After installation, follow the on-screen instructions to add Homebrew to your PATH.

### Step 2: Install System Dependencies

```bash
brew install python tesseract poppler
```

**Verify installations:**

```bash
python3 --version    # Should show Python 3.10 or higher
tesseract --version  # Should show tesseract 5.x.x
```

### Step 3: Install Ollama and Download the Model

1. **Install Ollama** — Download from [ollama.com/download](https://ollama.com/download) and drag it to Applications, or use Homebrew:

   ```bash
   brew install ollama
   ```

2. **Start the Ollama service** (if not already running):

   ```bash
   ollama serve
   ```

   > Ollama may start automatically after installation. If the command above says "address already in use," it's already running.

3. **Download the classification model:**

   ```bash
   ollama pull llama3.2
   ```

   This downloads ~2GB. It only needs to happen once.

4. **Verify Ollama is working:**

   ```bash
   ollama list
   # Should show: llama3.2:latest
   ```

### Step 4: Clone and Set Up ScanFiler

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/scanfiler.git
cd scanfiler

# Create a Python virtual environment
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
```

### Step 5: First-Run Setup

```bash
source venv/bin/activate
python scanfiler.py --setup
```

The setup wizard will ask you to confirm:

1. **Scan inbox** — Where your scanned documents land (default: `~/Downloads`)
2. **Filing destination** — Where organized files go (default: `~/Documents/Filed`)
3. **Ollama model** — Which model to use (default: `llama3.2`)
4. **File renaming** — Whether to rename files descriptively (default: Yes)

Settings are saved to `~/.scanfiler/config.json` and persist across runs.

---

## Usage

> **Always activate the virtual environment first:**
> ```bash
> cd /path/to/scanfiler
> source venv/bin/activate
> ```
> Or [set up a shell alias](#setting-up-a-shell-alias) to skip this step.

### Process All Files

Scans your inbox folder for all supported files and files them:

```bash
python scanfiler.py
```

### Dry Run (Preview)

See how files would be classified and where they'd go — without actually moving anything:

```bash
python scanfiler.py --dry-run
```

**This is recommended for your first run** so you can verify the classifications look correct.

### Process a Single File

```bash
python scanfiler.py ~/Downloads/scan_20260605.pdf
python scanfiler.py ~/Downloads/electric_bill.jpg
```

### Undo

Every move is logged. You can reverse operations at any time:

```bash
# Undo the last batch of moves
python scanfiler.py --undo

# Undo ALL moves ever made
python scanfiler.py --undo-all
```

Undo moves files back to their original location and cleans up empty folders.

### View History

```bash
python scanfiler.py --log
```

Shows a formatted table of all past moves with timestamps, batch IDs, document types, and filenames.

### Reconfigure

```bash
python scanfiler.py --setup
```

---

## Folder Structure

ScanFiler organizes documents into this hierarchy:

```
~/Documents/Filed/
├── Bank Statements/
│   ├── TD Bank/
│   │   ├── 2025/
│   │   │   └── TD_Bank_Statement_December_2025.pdf
│   │   └── 2026/
│   │       └── TD_Bank_Statement_June_2026.pdf
│   └── Chase/
│       └── 2026/
│           └── Chase_Statement_May_2026.pdf
├── Billing Statements/
│   └── PSEG/
│       └── 2026/
│           └── PSEG_Bill_June_2026.pdf
├── Tax Documents/
│   └── IRS/
│       └── 2025/
│           └── IRS_W2_2025.pdf
├── Medical Bills/
│   └── Aetna/
│       └── 2026/
│           └── Aetna_EOB_March_2026.pdf
└── Pay Stubs/
    └── Acme Corp/
        └── 2026/
            └── Acme_Corp_Pay_Stub_May_2026.pdf
```

The AI determines the **document type**, **company**, and **date** automatically. Folders are created as needed.

---

## Configuration

Settings are stored at `~/.scanfiler/config.json`:

```json
{
  "inbox_path": "/Users/yourname/Downloads",
  "output_path": "/Users/yourname/Documents/Filed",
  "supported_extensions": [".pdf", ".jpg", ".jpeg", ".png", ".tiff", ".tif", ".heic"],
  "rename_files": true,
  "min_confidence": 0.70,
  "ollama_model": "llama3.2",
  "ollama_host": "http://localhost:11434"
}
```

| Setting | Description | Default |
|---|---|---|
| `inbox_path` | Folder to scan for documents | `~/Downloads` |
| `output_path` | Root folder for filed documents | `~/Documents/Filed` |
| `supported_extensions` | File types to process | PDF, JPG, PNG, TIFF, HEIC |
| `rename_files` | Rename files descriptively | `true` |
| `min_confidence` | Minimum AI confidence to auto-file (0.0–1.0) | `0.70` |
| `ollama_model` | Ollama model for classification | `llama3.2` |
| `ollama_host` | Ollama server address | `http://localhost:11434` |

You can edit this file directly or run `python scanfiler.py --setup`.

---

## Setting Up a Shell Alias

To run ScanFiler from anywhere without manually activating the venv:

**For zsh (default on macOS):**

```bash
echo 'alias scanfiler="/path/to/scanfiler/venv/bin/python /path/to/scanfiler/scanfiler.py"' >> ~/.zshrc
source ~/.zshrc
```

**Replace `/path/to/scanfiler/` with the actual path where you cloned the repo.**

Now you can just run:

```bash
scanfiler                          # Process all files
scanfiler --dry-run                # Preview
scanfiler ~/Downloads/doc.pdf      # Single file
scanfiler --undo                   # Undo last batch
```

---

## Supported File Types

| Format | Extensions |
|---|---|
| PDF | `.pdf` |
| JPEG | `.jpg`, `.jpeg` |
| PNG | `.png` |
| TIFF | `.tiff`, `.tif` |
| HEIC | `.heic` |

---

## Troubleshooting

### "Ollama not found" or "Cannot connect to Ollama"

Ollama needs to be installed and running as a background service.

```bash
# Check if Ollama is installed
ollama --version

# Start the Ollama service
ollama serve
```

If Ollama was installed via the macOS app, it usually starts automatically. Check your menu bar for the Ollama icon (🦙).

### "Model 'llama3.2' not found"

You need to download the model first:

```bash
ollama pull llama3.2
```

Verify it's available:

```bash
ollama list
```

### "Tesseract not found"

```bash
brew install tesseract
```

Verify:

```bash
tesseract --version
```

### OCR produces no text / garbled text

- **Low scan quality:** Re-scan at 300 DPI or higher. Tesseract works best with clean, high-contrast scans.
- **Non-English documents:** By default, only English is installed. For other languages:
  ```bash
  brew install tesseract-lang
  ```
- **Handwritten text:** Tesseract is designed for printed/typed text. Handwritten documents will produce poor results.
- **HEIC files:** If HEIC images aren't working, ensure Pillow has HEIC support:
  ```bash
  pip install pillow-heif
  ```

### "externally-managed-environment" error when running pip

This means you're trying to install packages outside the virtual environment. Always activate the venv first:

```bash
cd /path/to/scanfiler
source venv/bin/activate
pip install -r requirements.txt
```

### Low confidence / documents being skipped

If documents are being skipped due to low confidence:

1. Run with `--dry-run` to see what the AI is detecting
2. Try lowering the confidence threshold in `~/.scanfiler/config.json`:
   ```json
   "min_confidence": 0.50
   ```
3. Ensure your scans are clear and the text is readable
4. If using a different Ollama model, try switching to `llama3.2` which is the recommended default

### Files are being classified incorrectly

- Use `--dry-run` to preview classifications before moving
- Use `--undo` to reverse any incorrect moves
- Ensure scan quality is good (300 DPI, clear text, no heavy shadows)

### Slow processing

- **First run with a model** is slow (~30–60 seconds) because Ollama needs to load the model into memory. Subsequent runs are much faster.
- **PDF files** take longer because each page must be converted to an image and OCR'd separately.
- **Large multi-page PDFs** are the slowest. The app processes the first ~3000 characters of extracted text, which is usually enough for classification.

### Permission denied errors

If you get permission errors when moving files:

```bash
# Check if the output directory is writable
ls -la ~/Documents/

# Create the output directory manually if needed
mkdir -p ~/Documents/Filed
```

---

## Limitations

1. **macOS only** — This guide and the installation steps are written for macOS. The Python code itself is cross-platform, but the Homebrew installation commands are macOS-specific. Linux users would substitute `apt` or `yum` for `brew`.

2. **Scanned documents only** — ScanFiler is designed for scanned documents (PDFs and images) where text needs to be OCR'd. It does not process Word documents, spreadsheets, or other native digital formats.

3. **English text only (by default)** — Tesseract ships with English language data. Install `tesseract-lang` for other languages.

4. **Requires readable text** — If a scan is too blurry, low-resolution, or heavily stylized, OCR may fail or produce garbled text, leading to incorrect or low-confidence classifications.

5. **No handwriting recognition** — Tesseract is optimized for printed/typed text. Handwritten documents will not classify correctly.

6. **Classification depends on text content** — The LLM classifies based on the OCR'd text. If key identifying information (company name, document type) is missing or unreadable, classification will be inaccurate.

7. **Not real-time** — ScanFiler is a manual-run CLI tool. It does not watch folders in real-time. You run it when you have documents to process.

8. **AI classification is not perfect** — While llama3.2 is good at document classification, it can occasionally misidentify a document type or company name. Always use `--dry-run` first for important batches and `--undo` if something goes wrong.

9. **Single-level inbox** — ScanFiler only looks at files directly in the inbox folder, not in subdirectories.

10. **Ollama must be running** — The Ollama service must be active when processing documents. It can be stopped when not in use.

---

## How It Works

```
┌─────────────────────┐
│   ~/Downloads/      │   You scan a document. It lands here.
│   scan_001.pdf      │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│   Tesseract OCR     │   Converts the scanned PDF/image into text.
│   (local, offline)  │   For PDFs: converts each page to an image first
│                     │   using Poppler, then OCRs each page.
└────────┬────────────┘
         │  "TD BANK ... ACCOUNT STATEMENT ... JUNE 2026 ..."
         ▼
┌─────────────────────┐
│   Ollama LLM        │   Analyzes the text and returns structured JSON:
│   (llama3.2, local) │   {
│                     │     "document_type": "Bank Statement",
│                     │     "company": "TD Bank",
│                     │     "date": "2026-06",
│                     │     "confidence": 0.95,
│                     │     "suggested_filename": "TD_Bank_Statement_June_2026"
│                     │   }
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│   File Mover        │   Creates the folder structure and moves the file.
│                     │   Logs the operation for undo capability.
└────────┬────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────┐
│   ~/Documents/Filed/Bank Statements/TD Bank/2026/    │
│   TD_Bank_Statement_June_2026.pdf                    │
└──────────────────────────────────────────────────────┘
```

### Components

| File | Purpose |
|---|---|
| `scanfiler.py` | CLI entry point — argument parsing, orchestration, colored output |
| `classifier.py` | OCR (Tesseract) + LLM classification (Ollama) |
| `filer.py` | File operations — path building, folder creation, deduplication |
| `config.py` | Configuration management (`~/.scanfiler/config.json`) |
| `logger.py` | Move logging (`~/.scanfiler/move_log.jsonl`) and undo system |

---

## License

MIT License — see [LICENSE](LICENSE) for details.

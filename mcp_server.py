import asyncio
from pathlib import Path
import json

# Import the official MCP server SDK elements
from mcp.server.models import InitializationOptions
from mcp.server import Server, NotificationOptions
from mcp.server.stdio import stdio_server
import mcp.types as types

# Import ScanFiler's operational workspace modules
from config import get_config
from scanfiler import process_file, find_files, check_dependencies
from logger import generate_batch_id, undo_batch, get_last_batch_id, load_log

# Initialize the server metadata
server = Server("scanfiler-mcp-server")

# ─── Tool Schema Definitions ──────────────────────────────────────────────────

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """Declare available local filing actions and parameters to the AI client."""
    return [
        types.Tool(
            name="process_all_files",
            description="Scans the configured inbox folder and automatically processes, OCRs, and files all matching documents.",
            inputSchema={
                "type": "object",
                "properties": {},
            }
        ),
        types.Tool(
            name="process_single_file",
            description="Runs OCR, classifies, and files a single document path. Requires an absolute file system path.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "The absolute system path to the document file (e.g., /Users/mike/Downloads/invoice.pdf)"
                    }
                },
                "required": ["file_path"]
            }
        ),
        types.Tool(
            name="undo_last_batch",
            description="Reverts the most recent document organization batch run, restoring files back to their original locations.",
            inputSchema={
                "type": "object",
                "properties": {},
            }
        ),
        types.Tool(
            name="get_move_history",
            description="Returns a historical transaction log of recently processed and filed files.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of recent move history rows to retrieve",
                        "default": 10
                    }
                }
            }
        )
    ]

# ─── Tool Call Routing Router ─────────────────────────────────────────────────

@server.call_tool()
async def handle_call_tool(
    name: str, 
    arguments: dict | None
) -> list[types.TextContent]:
    """Process incoming JSON-RPC tool requests and safely step through execution loops."""
    config = get_config()
    arguments = arguments or {}

    try:
        # Preflight Check: Verify local engines are available before invoking tasks
        if name in ("process_all_files", "process_single_file"):
            if not check_dependencies():
                return [types.TextContent(
                    type="text", 
                    text="❌ Core engines unavailable. Ensure Tesseract is installed and Ollama is running (`ollama serve`)."
                )]

        # 1. Action: Process All Files
        if name == "process_all_files":
            inbox_dir = Path(config["inbox_path"]).expanduser()
            # Defensive check to block scanfiler's internal sys.exit(1) path error crash
            if not inbox_dir.exists():
                return [types.TextContent(type="text", text=f"❌ Error: Configured inbox directory does not exist: {inbox_dir}")]

            files = find_files(config["inbox_path"], config["supported_extensions"])
            if not files:
                return [types.TextContent(type="text", text=f"📭 Inbox is empty. No supported files found in {config['inbox_path']}")]
            
            batch_id = generate_batch_id()
            execution_log = []
            
            for file_path in files:
                res = process_file(file_path, config, batch_id, dry_run=False)
                status = res.get("status", "unknown")
                if status == "filed":
                    execution_log.append(f"✅ Filed: {file_path.name} ➔ {res.get('destination')}")
                elif status == "low_confidence":
                    execution_log.append(f"⚠️ Skipped (Low Confidence): {file_path.name}")
                else:
                    execution_log.append(f"❌ Failed: {file_path.name} - {res.get('error', 'Unknown error')}")
            
            summary = f"Processed {len(files)} files over Stdio transport (Batch ID: {batch_id}):\n\n" + "\n".join(execution_log)
            return [types.TextContent(type="text", text=summary)]

        # 2. Action: Process Single File
        elif name == "process_single_file":
            raw_path = arguments.get("file_path", "").strip()
            if not raw_path:
                return [types.TextContent(type="text", text="❌ Error: Missing the required 'file_path' argument.")]
            
            # Resolve absolute paths and sanitize input bounds safely
            target_path = Path(raw_path).expanduser().resolve()
            if not target_path.exists():
                return [types.TextContent(type="text", text=f"❌ Error: File not found at the specified path: '{target_path}'")]
            
            if target_path.suffix.lower() not in config["supported_extensions"]:
                supported_str = ", ".join(config["supported_extensions"])
                return [types.TextContent(type="text", text=f"❌ Error: Extension '{target_path.suffix}' is unsupported. Supported types: {supported_str}")]

            batch_id = generate_batch_id()
            res = process_file(target_path, config, batch_id, dry_run=False)
            
            if res.get("status") == "error":
                return [types.TextContent(type="text", text=f"❌ Filing failed: {res.get('error', 'Unknown classification runtime error')}\nDetails: {res.get('classification', {})[0:200]}")]
                
            return [types.TextContent(
                type="text", 
                text=f"✅ Document filed successfully!\n\n📄 Original: {target_path.name}\n🗂️ Type: {res.get('classification', {}).get('document_type')}\n🏢 Company: {res.get('classification', {}).get('company')}\n📁 Destination: {res.get('destination')}"
            )]

        # 3. Action: Undo Last Batch
        elif name == "undo_last_batch":
            batch_id = get_last_batch_id()
            if not batch_id:
                return [types.TextContent(type="text", text="📋 Operation skipped. No transaction log entries found to revert.")]
            
            results = undo_batch(batch_id)
            restored = sum(1 for r in results if r["status"] == "restored")
            skipped = sum(1 for r in results if r["status"] == "skipped")
            errors = sum(1 for r in results if r["status"] == "error")
            
            summary = f"🔄 Reverted Batch Run: {batch_id}\n• Restored: {restored} files\n• Skipped: {skipped}\n• Errors: {errors}"
            return [types.TextContent(type="text", text=summary)]

        # 4. Action: Get Move History
        elif name == "get_move_history":
            limit = arguments.get("limit", 10)
            records = load_log()
            if not records:
                return [types.TextContent(type="text", text="📋 Transaction history log file is currently empty.")]
            
            # Read tail end files, format list outputs cleanly
            recent_logs = records[-limit:]
            history_lines = []
            for item in reversed(recent_logs):
                cls = item.get("classification", {})
                history_lines.append(
                    f"📅 [{item['timestamp'][:16]}] Batch: {item['batch_id']}\n"
                    f"   File: {Path(item['destination']).name}\n"
                    f"   Details: {cls.get('document_type', 'Unknown')} | {cls.get('company', 'Unknown')}"
                )
            
            return [types.TextContent(type="text", text=f"📋 Showing last {len(recent_logs)} historical document moves:\n\n" + "\n\n".join(history_lines))]

        else:
            raise ValueError(f"Unknown tool method received: {name}")

    except Exception as e:
        # Guarantee that standard exceptions are returned as messages rather than allowing stdout to break
        return [types.TextContent(type="text", text=f"❌ Server Error mapping tool execution loop: {str(e)}")]

# ─── Server Core Runtime Lifecycle ────────────────────────────────────────────

async def main():
    # Execute the server loop handling stream transitions via standard input/output streams
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="scanfiler-mcp-server",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())
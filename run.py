import os
import uvicorn
import sys
from pathlib import Path

# Fix Windows console encoding for UTF-8
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add current directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = "0.0.0.0"
    print("\n" + "="*60)
    print("  [*] ApexTrade - Autonom Aktiehandelsmaskin")
    print(f"  [>] Dashboard tillganglig pa port {port}")
    print("="*60 + "\n")
    uvicorn.run("server:app", host=host, port=port, reload=False, log_level="info")


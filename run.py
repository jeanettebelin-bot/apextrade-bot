import uvicorn
import sys
from pathlib import Path

import sys
from pathlib import Path

# Fix Windows console encoding for UTF-8
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add current directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

if __name__ == "__main__":
    print("\n" + "="*60)
    print("  [*] ApexTrade - Autonom Aktiehandelsmaskin")
    print("  [>] Dashboard tillganglig pa: http://localhost:8000")
    print("="*60 + "\n")
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=False, log_level="info")


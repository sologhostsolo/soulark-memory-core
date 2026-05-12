import os
from dataclasses import dataclass


@dataclass
class Settings:
    database_path: str = "data/memory_core.db"
    host: str = "127.0.0.1"
    port: int = 8765
    debug: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        port_raw = str(os.getenv("MEMORY_CORE_PORT", "8765") or "8765").strip()
        try:
            port = int(port_raw)
        except ValueError:
            port = 8765
        debug_raw = str(os.getenv("MEMORY_CORE_DEBUG", "") or "").strip().lower()
        return cls(
            database_path=str(os.getenv("MEMORY_CORE_DB_PATH", "data/memory_core.db") or "data/memory_core.db").strip(),
            host=str(os.getenv("MEMORY_CORE_HOST", "127.0.0.1") or "127.0.0.1").strip(),
            port=port,
            debug=debug_raw in {"1", "true", "yes", "on"},
        )
from __future__ import annotations

from pathlib import Path


def load_schema(schema_path: str | None = None) -> str:
    """Load SQL schema from file path.
    
    Args:
        schema_path: Path to schema file. If None, uses default bot_schema.sql location.
    
    Returns:
        SQL schema content as string.
    
    Raises:
        FileNotFoundError: If schema file doesn't exist.
    """
    if schema_path is None:
        base = Path(__file__).parent
        path = base / "bot_schema.sql"
    else:
        path = Path(schema_path)
    
    if not path.exists():
        raise FileNotFoundError(f"Schema file not found: {path}")
    
    return path.read_text(encoding="utf-8")


__all__ = ["load_schema"]

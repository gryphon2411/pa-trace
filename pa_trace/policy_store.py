import json
from pathlib import Path
from typing import List, Dict, Any

def load_policy_store(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, list), "Policy store must be a list of chunks"
    for c in data:
        assert "chunk_id" in c and "text" in c
    return data

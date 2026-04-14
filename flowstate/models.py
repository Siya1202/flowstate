from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Chunk:
    text: str
    speaker: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class Task:
    task_id: str
    task: str
    owner: Optional[str] = None
    deadline: Optional[str] = None
    confidence: float = 0.0
    source_ref: Optional[str] = None
    team_id: str = ""
    dependencies: List[str] = field(default_factory=list)
    inferred_owner: Optional[str] = None
    inference_confidence: Optional[float] = None
    duplicate_candidates: List[str] = field(default_factory=list)

    def dict(self) -> Dict[str, Any]:
        return asdict(self)
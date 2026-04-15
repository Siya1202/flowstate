"""Flowstate public package interface."""

from flowstate.drafting.generator import Draft, generate_draft
from flowstate.graph.dag import FlowstateDAG
from flowstate.graph.intelligence import (
    get_bottlenecks,
    get_critical_path,
    get_do_first_tasks,
    get_stale_blockers,
)

__all__ = [
    "Draft",
    "FlowstateDAG",
    "generate_draft",
    "get_bottlenecks",
    "get_critical_path",
    "get_do_first_tasks",
    "get_stale_blockers",
]

__version__ = "0.1.0"

import enum
import uuid

from sqlalchemy import JSON, Column, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class TaskStatus(str, enum.Enum):
	open = "open"
	in_progress = "in_progress"
	blocked = "blocked"
	done = "done"


class DependencyType(str, enum.Enum):
	blocks = "blocks"
	informs = "informs"
	requires_approval = "requires_approval"


class Task(Base):
	__tablename__ = "tasks"

	id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
	title = Column(String, nullable=False)
	owner = Column(String)
	deadline = Column(DateTime)
	status = Column(Enum(TaskStatus), default=TaskStatus.open)
	team_id = Column(String, ForeignKey("teams.id"), nullable=False)
	source_ref_id = Column(String, ForeignKey("source_refs.id"))
	created_at = Column(DateTime, nullable=False, server_default=func.now())
	updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())


class Dependency(Base):
	__tablename__ = "dependencies"

	id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
	from_task_id = Column(String, ForeignKey("tasks.id"))
	to_task_id = Column(String, ForeignKey("tasks.id"))
	dep_type = Column(Enum(DependencyType), default=DependencyType.blocks)


class Team(Base):
	__tablename__ = "teams"

	id = Column(String, primary_key=True)
	name = Column(String)
	llm_provider = Column(String, default="ollama")
	timezone = Column(String, default="UTC")


class SourceRef(Base):
	__tablename__ = "source_refs"

	id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
	source = Column(String)
	external_id = Column(String)
	url = Column(String)
	team_id = Column(String, ForeignKey("teams.id"))


class ConnectorRun(Base):
	__tablename__ = "connector_runs"

	id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
	connector_name = Column(String)
	task_id = Column(String, ForeignKey("tasks.id"))
	status = Column(String)
	ran_at = Column(DateTime)
	result = Column(Text)


class GraphSnapshot(Base):
	__tablename__ = "graph_snapshots"

	id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
	team_id = Column(String, ForeignKey("teams.id"), nullable=False)
	created_at = Column(DateTime, nullable=False, server_default=func.now())
	node_count = Column(Integer, nullable=False, default=0)
	edge_count = Column(Integer, nullable=False, default=0)
	payload = Column(JSON, nullable=False)
	diff_summary = Column(JSON, nullable=False)

from sqlalchemy import Column, String, DateTime, Text, Integer, Boolean, ForeignKey, ARRAY
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from typing import Optional, Dict, Any, List
from pydantic import BaseModel

Base = declarative_base()

class CrewInteractionModel(Base):
    __tablename__ = "crew_interactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(String(255), nullable=False)  # Changed from UUID to String to match platform
    task_id = Column(String(255), nullable=False)
    conversation_id = Column(String(255), nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    type = Column(String(50), nullable=False)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("crew_interactions.id"), nullable=True)
    depth = Column(Integer, default=0)
    sequence = Column(Integer, nullable=False)

    # Crew/Agent/Tool Identification
    crew_name = Column(String(255), nullable=True)
    crew_description = Column(Text, nullable=True)
    crew_members = Column(ARRAY(String), nullable=True)
    crew_goal = Column(Text, nullable=True)

    agent_name = Column(String(255), nullable=True)
    agent_role = Column(String(255), nullable=True)
    agent_goal = Column(Text, nullable=True)
    agent_backstory = Column(Text, nullable=True)
    agent_id = Column(String(255), nullable=True)

    tool_name = Column(String(255), nullable=True)
    tool_description = Column(Text, nullable=True)
    function_name = Column(String(255), nullable=True)

    # Content Data
    request_data = Column(JSONB, nullable=True)
    response_data = Column(JSONB, nullable=True)
    reasoning_step = Column(JSONB, nullable=True)

    # Communication
    request_text = Column(Text, nullable=True)
    response_text = Column(Text, nullable=True)
    message_type = Column(String(50), nullable=True)

    # Performance Metrics
    token_usage = Column(JSONB, nullable=True)
    performance_metrics = Column(JSONB, nullable=True)

    # Status and Timing
    status = Column(String(50), nullable=False)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)

    # Metadata
    interaction_metadata = Column(JSONB, default={})

    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    children = relationship("CrewInteractionModel", backref="parent", remote_side=[id])

# Pydantic models for API
class TokenUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost: float
    model: str
    provider: str

class ReasoningStep(BaseModel):
    thought: str
    action: str
    action_input: Optional[Dict[str, Any]] = None
    observation: Optional[str] = None
    final_answer: Optional[str] = None
    scratchpad: Optional[str] = None

class CrewInteraction(BaseModel):
    id: str
    project_id: str
    task_id: str
    conversation_id: str
    timestamp: datetime
    type: str
    parent_id: Optional[str] = None
    depth: int = 0
    sequence: int

    # Crew/Agent/Tool Data
    crew_name: Optional[str] = None
    crew_description: Optional[str] = None
    crew_members: Optional[List[str]] = None
    crew_goal: Optional[str] = None

    agent_name: Optional[str] = None
    agent_role: Optional[str] = None
    agent_goal: Optional[str] = None
    agent_backstory: Optional[str] = None
    agent_id: Optional[str] = None

    tool_name: Optional[str] = None
    tool_description: Optional[str] = None
    function_name: Optional[str] = None

    # Content
    request_data: Optional[Dict[str, Any]] = None
    response_data: Optional[Dict[str, Any]] = None
    reasoning_step: Optional[ReasoningStep] = None

    # Communication
    request_text: Optional[str] = None
    response_text: Optional[str] = None
    message_type: Optional[str] = None

    # Performance
    token_usage: Optional[TokenUsage] = None
    performance_metrics: Optional[Dict[str, Any]] = None

    # Status
    status: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_ms: Optional[int] = None
    error_message: Optional[str] = None
    retry_count: int = 0

    # Metadata
    interaction_metadata: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True

class FilterOptions(BaseModel):
    mode: str = "realtime"  # historic or realtime
    agent_types: List[str] = []
    tools: List[str] = []
    time_range: Optional[Dict[str, str]] = None
    status: List[str] = []
    search_query: Optional[str] = None
    conversation_id: Optional[str] = None

class UserDisplayPreferences(BaseModel):
    show_token_usage: bool = True
    show_reasoning_steps: bool = True
    show_function_calls: bool = True
    show_timestamps: bool = True
    show_duration: bool = True
    show_costs: bool = True
    show_metadata: bool = False
    show_error_details: bool = True
    compact_mode: bool = False
    group_by_agent: bool = False
    group_by_tool: bool = False

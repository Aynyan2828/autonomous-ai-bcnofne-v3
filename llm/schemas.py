from pydantic import BaseModel, Field
from typing import List


class SummaryResult(BaseModel):
    summary: str
    keywords: List[str] = Field(default_factory=list)
    importance: str


class ChunkSummaryResult(BaseModel):
    chunk_summary: str
    keywords: List[str] = Field(default_factory=list)


class FinalSummaryResult(BaseModel):
    final_summary: str
    keywords: List[str] = Field(default_factory=list)
    importance: str


class ClassificationResult(BaseModel):
    primary_label: str
    secondary_labels: List[str] = Field(default_factory=list)
    confidence: float
    reason: str


class NotificationResult(BaseModel):
    title: str
    body: str
    priority: str


class CodePatchResult(BaseModel):
    summary: str
    risk: str
    code: str

class GoalResult(BaseModel):
    daily_goal_ja: str
    daily_goal_en: str
    short_tasks: List[Dict[str, str]] = Field(default_factory=list)

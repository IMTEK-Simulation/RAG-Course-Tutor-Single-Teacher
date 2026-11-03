from typing import Literal

from pydantic import BaseModel, Field
from .config import DEFAULT_API_URL


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class TutorRequest(BaseModel):
    course_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,62}$")
    message: str = Field(min_length=1, max_length=12000)
    mode: Literal["direct", "socratic"] = "direct"
    language: Literal["auto", "de", "en"] = "auto"
    api_key: str = Field(default="", max_length=4096)
    messages: list[ChatMessage] = Field(default_factory=list, max_length=20)
    top_k: int = Field(default=2, ge=1, le=6)


class PreviewRequest(BaseModel):
    course_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,62}$")
    message: str = Field(min_length=1, max_length=12000)
    mode: Literal["direct", "socratic"] = "direct"
    language: Literal["auto", "de", "en"] = "auto"
    top_k: int = Field(default=2, ge=1, le=6)


class ModelRequest(BaseModel):
    base_url: str
    api_key: str = Field(default="", max_length=4096)
    provider: Literal["openai-compatible", "ollama"] = "openai-compatible"


class CourseSettings(BaseModel):
    mode: Literal["direct", "socratic"] = "direct"
    provider: Literal["openai-compatible", "ollama"] = "openai-compatible"
    base_url: str = Field(default_factory=lambda: DEFAULT_API_URL, max_length=2048)
    model: str = Field(default="UFR: Standard Coding", min_length=1, max_length=240)
    auth_mode: Literal["student", "none"] = "student"
    top_k: int = Field(default=2, ge=1, le=20)
    temperature: float = Field(default=0, ge=0, le=2, allow_inf_nan=False)
    max_tokens: int = Field(default=1024, ge=64, le=32768)
    history_messages: int = Field(default=10, ge=0, le=20)



class SourceResult(BaseModel):
    id: str
    title: str
    section: str
    source_file: str
    score: float
    text: str


class TutorResponse(BaseModel):
    answer: str
    provider: str
    model: str
    retrieval: str
    sources: list[SourceResult]


class CourseCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=600)
    tutor_role: str = Field(default="Lernbegleiter für Studierende", max_length=240)
    language: Literal["de", "en", "auto"] = "de"
    settings: CourseSettings = Field(default_factory=CourseSettings)


class ChunkUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    section: str = Field(min_length=1, max_length=500)
    text: str = Field(min_length=1, max_length=30000)
    module: str = Field(default="Material", max_length=160)
    topic: str = Field(default="Allgemein", max_length=160)


class AccountCredentials(BaseModel):
    username: str = Field(min_length=3, max_length=80, pattern=r"^[A-Za-z0-9._-]+$")
    password: str = Field(min_length=12, max_length=256)

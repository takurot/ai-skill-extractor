from pydantic import BaseModel, Field


class StorageConfig(BaseModel):
    db_url: str = "postgresql://localhost:5432/rke"
    artifact_dir: str = "./output"


class ModelConfig(BaseModel):
    embedding_model: str = "text-embedding-3-large"
    classification_model: str = "gpt-4o"
    summarization_model: str = "gpt-4o-mini"


class PipelineConfig(BaseModel):
    enable_human_review: bool = True
    min_skill_confidence: float = 0.72
    min_cross_repo_support: int = 2
    require_evidence: bool = True
    enable_fix_correlation: bool = True
    dedup_threshold: float = 0.88
    redact_identity: bool = True


class GenerationConfig(BaseModel):
    skills_output: str = "skills/SKILLS.yaml"
    docs_output_dir: str = "docs"
    language_split: bool = True
    framework_split: bool = True


class Config(BaseModel):
    storage: StorageConfig = Field(default_factory=StorageConfig)
    models: ModelConfig = Field(default_factory=ModelConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)
    generation: GenerationConfig = Field(default_factory=GenerationConfig)

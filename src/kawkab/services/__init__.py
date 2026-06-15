"""Service layer for Kawkab AI.

Services are async-capable, dependency-injectable components that handle
specific domains: CV, enhancement, analysis, reasoning, LLM, storage, etc.
"""

from kawkab.services.cv_service import CVService, MatchTrackData, FrameDetections
from kawkab.services.enhancement_service import EnhancementService
from kawkab.services.analysis_service import AnalysisService
from kawkab.services.llm_service import LLMService, LLMConfig
from kawkab.services.knowledge_service import KnowledgeService
from kawkab.services.storage_service import StorageService
from kawkab.services.audio_service import AudioService
from kawkab.services.reasoning_service import ReasoningService, DiagnosisReport
from kawkab.services.clip_service import ClipExtractionService
from kawkab.services.training_plan_service import TrainingPlanGenerator, TrainingPlan
from kawkab.services.homography_service import HomographyService, HomographyMatrix
from kawkab.services.vram_manager import VRAMManager, ModelPriority

__all__ = [
    "CVService",
    "MatchTrackData",
    "FrameDetections",
    "EnhancementService",
    "AnalysisService",
    "LLMService",
    "LLMConfig",
    "KnowledgeService",
    "StorageService",
    "AudioService",
    "ReasoningService",
    "DiagnosisReport",
    "ClipExtractionService",
    "TrainingPlanGenerator",
    "TrainingPlan",
    "HomographyService",
    "HomographyMatrix",
    "VRAMManager",
    "ModelPriority",
]

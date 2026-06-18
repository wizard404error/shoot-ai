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
from kawkab.services.benchmark_service import BenchmarkService, BenchmarkResult
from kawkab.services.validation_service import (
    ValidationService,
    ValidationResult,
    ValidationReport,
    EventGroundTruth,
)
from kawkab.services.clip_extraction_service import (
    ClipLibraryService,
    VideoClip,
    ClipPlaylist,
)
from kawkab.services.advanced_event_detection_service import AdvancedEventDetectionService
from kawkab.services.physical_load_service import PhysicalLoadService
from kawkab.services.pressure_metrics_service import PressureMetricsService
from kawkab.services.player_profile_service import PlayerProfileService, PlayerProfile
from kawkab.services.multi_match_analysis_service import MultiMatchAnalysisService
from kawkab.services.data_export_service import DataExportService
from kawkab.services.visualization_service import VisualizationService
from kawkab.services.anomaly_detection_service import AnomalyDetectionService
from kawkab.services.quality_scoring_service import QualityScoringService
from kawkab.services.batch_service import BatchService, BatchJob, BatchStatus
from kawkab.services.lightglue_homography_service import LightGlueHomographyService
from kawkab.services.face_recognition_service import FaceRecognitionService
from kawkab.services.norfair_tracker import NorfairTracker
from kawkab.services.pose_analysis_service import (
    PoseAnalysisService, PoseResult, ActivitySegment, FallEvent,
)
from kawkab.services.mujoco_ball_service import (
    MuJoCoBallService, TrajectoryResult, TrajectoryPoint,
)
from kawkab.services.fluidx3d_service import FluidX3DService, CfdResult
from kawkab.services.weather_service import (
    WeatherService, WeatherConditions, WeatherImpact, WeatherSource, PitchState,
    VideoWeatherPrediction,
)
from kawkab.services.psychology_service import (
    PsychologyService, PsychologyReport, PsychologyEvent,
    ScoreStateTransition, MomentumPoint, ScoreState, PsychologyEventType,
)
from kawkab.services.football_rules_service import (
    FootballRulesService, Law, RestartType, RuleReference, OffsideCheck,
)
from kawkab.services.card_detection_service import (
    CardDetectionService, CardEvent, CardType, CardSource, AudioCardSignal,
)
from kawkab.services.raindrop_detection_service import (
    RaindropDetectionService, RaindropDetection,
)
from kawkab.services.weather_image_classifier import (
    WeatherImageClassifier, WeatherClassification, WEATHER_CLASSES,
    compute_features,
)
from kawkab.services.setpiece_service import (
    SetPieceService, SetPieceEvent, SetPieceStats, SetPieceReport,
)
from kawkab.services.goalkeeper_service import (
    GoalkeeperService, GoalkeeperAction, GoalkeeperStats,
)
from kawkab.services.substitution_service import (
    SubstitutionService, SubstitutionEvent, SubstitutionImpact, SubstitutionReport,
)
from kawkab.services.possession_service import (
    PossessionService, PossessionChain, PlayerPossessionStats, PossessionReport,
)
from kawkab.services.football_data_service import FootballDataService
from kawkab.services.bzzoiro_service import BzzoiroService
from kawkab.services.easy_soccer_service import EasySoccerService
from kawkab.services.api_football_service import ApiFootballService
from kawkab.services.thesportsdb_service import TheSportsDBService
from kawkab.services.statsbomb_service import StatsBombService
from kawkab.services.openfootball_service import OpenFootballDataService
from kawkab.services.roboflow_sports_service import RoboflowSportsService
from kawkab.services.realtime_service import (
    RealtimeService,
    RealtimeEvent,
    RealtimeSubscriber,
    StreamStats,
    AlertKind,
    AlertSeverity,
    AlertRule,
    ShotAlertRule,
    LowFpsAlertRule,
    LowConfidenceAlertRule,
    CallbackSubscriber,
    ConsoleSubscriber,
)
from kawkab.services.positioning_service import (
    PositioningService,
    PositioningReport,
    Run,
    RunType,
)
from kawkab.services.player_development_service import (
    PlayerDevelopmentService,
    PlayerDevelopmentReport,
    PlayerMatchStat,
    PlayerTrend,
    TrendDirection,
)
from kawkab.services.workload_service import (
    WorkloadService,
    WorkloadReport,
    WorkloadRecord,
    WorkloadSource,
    RiskLevel,
)
from kawkab.services.scouting_service import (
    ScoutingService,
    OpponentProfile,
)
from kawkab.services.video_review_service import (
    VideoReviewService,
    ReviewSession,
    Clip,
    Annotation,
    AnnotationKind,
    ClipTag,
)
from kawkab.services.pitch_detector import (
    PitchDetector,
    CalibrationGuess,
)
from kawkab.services.periodization_service import (
    PeriodizationService,
    PeriodizationReport,
    WeekSummary,
    CyclePhase,
    CongestionLevel,
)

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
    "ClipLibraryService",
    "VideoClip",
    "ClipPlaylist",
    "TrainingPlanGenerator",
    "TrainingPlan",
    "HomographyService",
    "HomographyMatrix",
    "VRAMManager",
    "ModelPriority",
    "PlayerProfileService",
    "PlayerProfile",
    "MultiMatchAnalysisService",
    "DataExportService",
    "VisualizationService",
    "AnomalyDetectionService",
    "QualityScoringService",
    "AdvancedEventDetectionService",
    "PhysicalLoadService",
    "PressureMetricsService",
    "LightGlueHomographyService",
    "BenchmarkService",
    "BenchmarkResult",
    "RealtimeService",
    "RealtimeEvent",
    "RealtimeSubscriber",
    "StreamStats",
    "AlertKind",
    "AlertSeverity",
    "AlertRule",
    "ShotAlertRule",
    "LowFpsAlertRule",
    "LowConfidenceAlertRule",
    "CallbackSubscriber",
    "ConsoleSubscriber",
    "ValidationService",
    "ValidationReport",
    "ValidationResult",
    "EventGroundTruth",
    "BatchService",
    "BatchJob",
    "BatchStatus",
    "FaceRecognitionService",
    "NorfairTracker",
    "PoseAnalysisService",
    "PoseResult",
    "ActivitySegment",
    "FallEvent",
    "MuJoCoBallService",
    "TrajectoryResult",
    "TrajectoryPoint",
    "FluidX3DService",
    "CfdResult",
    "WeatherService",
    "WeatherConditions",
    "WeatherImpact",
    "WeatherSource",
    "PitchState",
    "VideoWeatherPrediction",
    "PsychologyService",
    "PsychologyReport",
    "PsychologyEvent",
    "ScoreStateTransition",
    "MomentumPoint",
    "ScoreState",
    "PsychologyEventType",
    "FootballRulesService",
    "Law",
    "RestartType",
    "RuleReference",
    "OffsideCheck",
    "CardDetectionService",
    "CardEvent",
    "CardType",
    "CardSource",
    "AudioCardSignal",
    "RaindropDetectionService",
    "RaindropDetection",
    "WeatherImageClassifier",
    "WeatherClassification",
    "WEATHER_CLASSES",
    "compute_features",
    "SetPieceService",
    "SetPieceEvent",
    "SetPieceStats",
    "SetPieceReport",
    "GoalkeeperService",
    "GoalkeeperAction",
    "GoalkeeperStats",
    "SubstitutionService",
    "SubstitutionEvent",
    "SubstitutionImpact",
    "SubstitutionReport",
    "PossessionService",
    "PossessionChain",
    "PlayerPossessionStats",
    "PossessionReport",
    "FootballDataService",
    "BzzoiroService",
    "EasySoccerService",
    "ApiFootballService",
    "TheSportsDBService",
    "StatsBombService",
    "OpenFootballDataService",
    "RoboflowSportsService",
    "RealtimeService",
    "RealtimeEvent",
    "RealtimeSubscriber",
    "StreamStats",
    "AlertKind",
    "AlertSeverity",
    "AlertRule",
    "ShotAlertRule",
    "LowFpsAlertRule",
    "LowConfidenceAlertRule",
    "CallbackSubscriber",
    "ConsoleSubscriber",
    "PositioningService",
    "PositioningReport",
    "Run",
    "RunType",
    "PlayerDevelopmentService",
    "PlayerDevelopmentReport",
    "PlayerMatchStat",
    "PlayerTrend",
    "TrendDirection",
    "WorkloadService",
    "WorkloadReport",
    "WorkloadRecord",
    "WorkloadSource",
    "RiskLevel",
    "ScoutingService",
    "OpponentProfile",
    "VideoReviewService",
    "ReviewSession",
    "Clip",
    "Annotation",
    "AnnotationKind",
    "ClipTag",
    "PitchDetector",
    "CalibrationGuess",
    "PeriodizationService",
    "PeriodizationReport",
    "WeekSummary",
    "CyclePhase",
    "CongestionLevel",
]

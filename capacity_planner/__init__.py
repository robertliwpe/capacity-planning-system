"""
Capacity Planning System

An automated, point-in-time capacity planning tool for WordPress hosting configurations.
"""

__version__ = "0.1.0"
__author__ = "Capacity Planning Team"

from .orchestrator.main import CapacityPlanningOrchestrator
from .models.data_models import AnalysisRequest, AnalysisResult, SSHConfig

__all__ = [
    "CapacityPlanningOrchestrator",
    "AnalysisRequest",
    "AnalysisResult",
    "SSHConfig",
]
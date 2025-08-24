"""
Advanced Analytics & Insights Service

This service provides:
1. Business intelligence and predictive analytics
2. Migration complexity analysis and recommendations
3. Cost optimization insights and forecasting
4. Performance trend analysis and alerts
5. Executive dashboards and reporting
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager
from enum import Enum

import httpx
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AnalyticsType(str, Enum):
    MIGRATION_COMPLEXITY = "migration_complexity"
    COST_OPTIMIZATION = "cost_optimization"
    AGENT_EFFICIENCY = "agent_efficiency"
    PROJECT_INSIGHTS = "project_insights"

@dataclass
class AnalyticsReport:
    """Comprehensive analytics report"""
    report_id: str
    title: str
    report_type: AnalyticsType
    project_id: Optional[str]
    generated_at: datetime
    summary: str
    recommendations: List[str]
    metrics: Dict[str, float]
    charts_data: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['generated_at'] = self.generated_at.isoformat()
        return data

class AdvancedAnalyticsManager:
    """Manages advanced analytics and insights"""
    
    def __init__(self):
        self.reports: Dict[str, AnalyticsReport] = {}
        self.project_service_url = os.getenv("PROJECT_SERVICE_URL", "http://localhost:8010")
        self.cloud_tools_service_url = os.getenv("CLOUD_TOOLS_SERVICE_URL", "http://localhost:8012")
        self.agent_orchestration_url = os.getenv("AGENT_ORCHESTRATION_URL", "http://localhost:8013")
        
        logger.info("Advanced Analytics Manager initialized")
    
    async def generate_migration_complexity_analysis(self, project_id: str) -> AnalyticsReport:
        """Generate migration complexity analysis"""
        report_id = str(uuid.uuid4())
        
        # Mock complexity calculations
        infrastructure_complexity = np.random.uniform(40, 85)
        dependency_complexity = np.random.uniform(30, 70)
        data_complexity = np.random.uniform(25, 65)
        overall_complexity = (infrastructure_complexity + dependency_complexity + data_complexity) / 3
        
        recommendations = []
        if overall_complexity > 70:
            recommendations.extend([
                "Implement phased migration approach",
                "Establish dedicated migration team",
                "Conduct comprehensive risk assessment"
            ])
        else:
            recommendations.extend([
                "Standard migration approach recommended",
                "Regular checkpoints and progress reviews"
            ])
        
        charts_data = {
            "complexity_breakdown": {
                "labels": ["Infrastructure", "Dependencies", "Data"],
                "values": [infrastructure_complexity, dependency_complexity, data_complexity]
            }
        }
        
        report = AnalyticsReport(
            report_id=report_id,
            title=f"Migration Complexity Analysis - Project {project_id}",
            report_type=AnalyticsType.MIGRATION_COMPLEXITY,
            project_id=project_id,
            generated_at=datetime.now(),
            summary=f"Overall migration complexity score: {overall_complexity:.1f}/100",
            recommendations=recommendations,
            metrics={
                "overall_complexity": overall_complexity,
                "infrastructure_complexity": infrastructure_complexity,
                "dependency_complexity": dependency_complexity,
                "data_complexity": data_complexity
            },
            charts_data=charts_data
        )
        
        self.reports[report_id] = report
        return report
    
    async def generate_cost_optimization_analysis(self, project_id: Optional[str] = None) -> AnalyticsReport:
        """Generate cost optimization analysis"""
        report_id = str(uuid.uuid4())
        
        # Mock cost calculations
        current_costs = np.random.uniform(5000, 15000)
        waste_percentage = np.random.uniform(15, 35)
        potential_savings = current_costs * (waste_percentage / 100)
        
        recommendations = [
            "Implement automated resource scheduling",
            "Review and optimize storage tiers",
            "Monitor and alert on cost anomalies"
        ]
        
        if waste_percentage > 25:
            recommendations.extend([
                "Conduct comprehensive cost audit",
                "Implement FinOps practices"
            ])
        
        charts_data = {
            "cost_breakdown": {
                "labels": ["Compute", "Storage", "Network", "Database"],
                "values": [current_costs * 0.45, current_costs * 0.25, current_costs * 0.15, current_costs * 0.15]
            }
        }
        
        report = AnalyticsReport(
            report_id=report_id,
            title="Cost Optimization Analysis",
            report_type=AnalyticsType.COST_OPTIMIZATION,
            project_id=project_id,
            generated_at=datetime.now(),
            summary=f"Potential monthly savings: ${potential_savings:.2f} ({waste_percentage:.1f}% optimization)",
            recommendations=recommendations,
            metrics={
                "current_monthly_cost": current_costs,
                "potential_savings": potential_savings,
                "waste_percentage": waste_percentage,
                "efficiency_score": 100 - waste_percentage
            },
            charts_data=charts_data
        )
        
        self.reports[report_id] = report
        return report
    
    async def generate_agent_efficiency_analysis(self) -> AnalyticsReport:
        """Generate AI agent efficiency analysis"""
        report_id = str(uuid.uuid4())
        
        # Mock agent metrics
        avg_success_rate = np.random.uniform(80, 95)
        avg_task_duration = np.random.uniform(8, 25)
        utilization_rate = np.random.uniform(60, 85)
        
        recommendations = [
            "Implement continuous agent performance monitoring",
            "Regular agent capability assessments"
        ]
        
        if avg_success_rate < 85:
            recommendations.append("Improve agent prompt engineering and training")
        if avg_task_duration > 20:
            recommendations.append("Optimize agent task processing algorithms")
        
        charts_data = {
            "efficiency_metrics": {
                "labels": ["Success Rate", "Utilization", "Performance"],
                "values": [avg_success_rate, utilization_rate, 100 - avg_task_duration]
            }
        }
        
        report = AnalyticsReport(
            report_id=report_id,
            title="AI Agent Efficiency Analysis",
            report_type=AnalyticsType.AGENT_EFFICIENCY,
            project_id=None,
            generated_at=datetime.now(),
            summary=f"Agent efficiency: {avg_success_rate:.1f}% success rate, {avg_task_duration:.1f}min avg duration",
            recommendations=recommendations,
            metrics={
                "average_success_rate": avg_success_rate,
                "average_task_duration": avg_task_duration,
                "utilization_rate": utilization_rate
            },
            charts_data=charts_data
        )
        
        self.reports[report_id] = report
        return report

# Global analytics manager
analytics_manager = AdvancedAnalyticsManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    logger.info("Advanced Analytics & Insights Service started successfully")
    yield
    logger.info("Advanced Analytics & Insights Service shut down successfully")

# FastAPI app
app = FastAPI(
    title="Advanced Analytics & Insights Service",
    description="Business intelligence and predictive analytics for Nagarro Ascent Platform",
    version="3.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str = "3.0.0"
    service: str = "analytics-service"

# API Endpoints
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat()
    )

@app.post("/analytics/migration-complexity")
async def analyze_migration_complexity(project_id: str):
    """Generate migration complexity analysis"""
    report = await analytics_manager.generate_migration_complexity_analysis(project_id)
    return {"report": report.to_dict()}

@app.post("/analytics/cost-optimization")
async def analyze_cost_optimization(project_id: Optional[str] = None):
    """Generate cost optimization analysis"""
    report = await analytics_manager.generate_cost_optimization_analysis(project_id)
    return {"report": report.to_dict()}

@app.post("/analytics/agent-efficiency")
async def analyze_agent_efficiency():
    """Generate AI agent efficiency analysis"""
    report = await analytics_manager.generate_agent_efficiency_analysis()
    return {"report": report.to_dict()}

@app.get("/reports")
async def get_all_reports():
    """Get all generated reports"""
    return {
        "reports": [report.to_dict() for report in analytics_manager.reports.values()],
        "total_count": len(analytics_manager.reports)
    }

@app.get("/reports/{report_id}")
async def get_report(report_id: str):
    """Get specific report"""
    report = analytics_manager.reports.get(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return {"report": report.to_dict()}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8014,
        reload=True,
        log_level="info"
    )
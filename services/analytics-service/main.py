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
import time
import socket
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict, field
from contextlib import asynccontextmanager
from enum import Enum
from collections import defaultdict

import httpx
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

# Configure logging and ensure uvicorn uses same handlers/formatters
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [analytics-service] %(message)s'
)
logger = logging.getLogger("analytics_service")

# Service start time for uptime calculation
SERVICE_START_TIME = time.time()

_root_logger = logging.getLogger()
for _lname in ("uvicorn", "uvicorn.error", "uvicorn.access"):
    _uv = logging.getLogger(_lname)
    _uv.setLevel(logging.INFO)
    for _h in list(_uv.handlers):
        _uv.removeHandler(_h)
    for _h in _root_logger.handlers:
        _uv.addHandler(_h)
    _uv.propagate = False

class AnalyticsType(str, Enum):
    MIGRATION_COMPLEXITY = "migration_complexity"
    COST_OPTIMIZATION = "cost_optimization"
    AGENT_EFFICIENCY = "agent_efficiency"
    PROJECT_INSIGHTS = "project_insights"
    PERFORMANCE_TRENDS = "performance_trends"
    RISK_ASSESSMENT = "risk_assessment"
    PREDICTIVE_ANALYSIS = "predictive_analysis"
    RESOURCE_UTILIZATION = "resource_utilization"
    SECURITY_ANALYTICS = "security_analytics"
    COMPLIANCE_TRACKING = "compliance_tracking"
    USER_BEHAVIOR = "user_behavior"
    SYSTEM_HEALTH = "system_health"

class TrendPeriod(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"

class AlertSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class MetricDataPoint:
    """Individual metric data point with timestamp"""
    timestamp: datetime
    value: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data

@dataclass
class TrendAnalysis:
    """Trend analysis result"""
    metric_name: str
    period: TrendPeriod
    trend_direction: str  # "increasing", "decreasing", "stable"
    trend_strength: float  # 0-1
    prediction: Optional[float]
    confidence_interval: Tuple[float, float]
    anomalies_detected: List[datetime]
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['anomalies_detected'] = [dt.isoformat() for dt in self.anomalies_detected]
        return data

@dataclass
class Alert:
    """Analytics alert"""
    alert_id: str
    title: str
    description: str
    severity: AlertSeverity
    category: str
    created_at: datetime
    project_id: Optional[str] = None
    is_resolved: bool = False
    resolved_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        if self.resolved_at:
            data['resolved_at'] = self.resolved_at.isoformat()
        return data

@dataclass
class DashboardWidget:
    """Dashboard widget configuration"""
    widget_id: str
    title: str
    type: str  # "chart", "metric", "table", "alert"
    data_source: str
    configuration: Dict[str, Any]
    position: Dict[str, int]  # x, y, width, height
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

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
    trend_analysis: Optional[List[TrendAnalysis]] = None
    alerts: Optional[List[Alert]] = None
    confidence_score: float = 0.0
    data_quality_score: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['generated_at'] = self.generated_at.isoformat()
        if self.trend_analysis:
            data['trend_analysis'] = [trend.to_dict() for trend in self.trend_analysis]
        if self.alerts:
            data['alerts'] = [alert.to_dict() for alert in self.alerts]
        return data

class AdvancedAnalyticsManager:
    """Manages advanced analytics and insights with ML capabilities"""
    
    def __init__(self):
        self.reports: Dict[str, AnalyticsReport] = {}
        self.metrics_history: Dict[str, List[MetricDataPoint]] = defaultdict(list)
        self.alerts: Dict[str, Alert] = {}
        self.dashboards: Dict[str, List[DashboardWidget]] = {}
        self.trend_models: Dict[str, LinearRegression] = {}
        
        # Service URLs
        self.project_service_url = os.getenv("PROJECT_SERVICE_URL", "http://localhost:8010")
        self.cloud_tools_service_url = os.getenv("CLOUD_TOOLS_SERVICE_URL", "http://localhost:8012")
        self.agent_orchestration_url = os.getenv("AGENT_ORCHESTRATION_URL", "http://localhost:8013")
        self.websocket_url = os.getenv("WEBSOCKET_SERVICE_URL", "http://localhost:8009")
        
        # Initialize background tasks
        self._initialize_sample_data()
        
        logger.info("Advanced Analytics Manager initialized with ML capabilities")
    
    def _initialize_sample_data(self):
        """Initialize with sample historical data for demonstration"""
        # Generate sample metric history for the last 30 days
        base_date = datetime.now() - timedelta(days=30)
        
        metrics = [
            "system_cpu_usage", "memory_utilization", "agent_success_rate", 
            "cost_per_day", "migration_progress", "security_incidents"
        ]
        
        for metric in metrics:
            for i in range(30):
                timestamp = base_date + timedelta(days=i)
                # Generate realistic sample data with trends
                if metric == "system_cpu_usage":
                    value = 45 + np.sin(i * 0.2) * 15 + np.random.normal(0, 5)
                elif metric == "memory_utilization":
                    value = 60 + i * 0.5 + np.random.normal(0, 8)
                elif metric == "agent_success_rate":
                    value = 85 + np.sin(i * 0.1) * 10 + np.random.normal(0, 3)
                elif metric == "cost_per_day":
                    value = 1200 + i * 10 + np.random.normal(0, 50)
                elif metric == "migration_progress":
                    value = min(100, i * 3.5 + np.random.normal(0, 2))
                else:  # security_incidents
                    value = max(0, np.random.poisson(1.5))
                
                value = max(0, value)  # Ensure non-negative values
                
                data_point = MetricDataPoint(
                    timestamp=timestamp,
                    value=value,
                    metadata={"source": "simulated", "quality": "high"}
                )
                self.metrics_history[metric].append(data_point)
    
    async def add_metric_data(self, metric_name: str, value: float, metadata: Dict[str, Any] = None):
        """Add real-time metric data point"""
        data_point = MetricDataPoint(
            timestamp=datetime.now(),
            value=value,
            metadata=metadata or {}
        )
        
        self.metrics_history[metric_name].append(data_point)
        
        # Keep only last 1000 data points per metric
        if len(self.metrics_history[metric_name]) > 1000:
            self.metrics_history[metric_name] = self.metrics_history[metric_name][-1000:]
        
        # Check for anomalies and generate alerts
        await self._check_metric_anomalies(metric_name, value)
        
        # Notify via WebSocket
        await self._notify_websocket("metric_updated", {
            "metric_name": metric_name,
            "value": value,
            "timestamp": data_point.timestamp.isoformat()
        })
    
    async def _check_metric_anomalies(self, metric_name: str, current_value: float):
        """Check for anomalies in metric data and generate alerts"""
        history = self.metrics_history[metric_name]
        
        if len(history) < 10:  # Need enough history
            return
        
        # Calculate statistical thresholds
        values = [dp.value for dp in history[-30:]]  # Last 30 points
        mean_val = np.mean(values)
        std_val = np.std(values)
        
        # Detect anomalies (value outside 2 standard deviations)
        if abs(current_value - mean_val) > 2 * std_val:
            severity = AlertSeverity.HIGH if abs(current_value - mean_val) > 3 * std_val else AlertSeverity.MEDIUM
            
            alert = Alert(
                alert_id=str(uuid.uuid4()),
                title=f"Anomaly detected in {metric_name}",
                description=f"Value {current_value:.2f} is significantly different from normal range ({mean_val:.2f} ± {std_val:.2f})",
                severity=severity,
                category="anomaly_detection",
                created_at=datetime.now()
            )
            
            self.alerts[alert.alert_id] = alert
            
            # Notify via WebSocket
            await self._notify_websocket("alert_generated", alert.to_dict())
    
    def perform_trend_analysis(self, metric_name: str, period: TrendPeriod = TrendPeriod.WEEKLY) -> TrendAnalysis:
        """Perform trend analysis using machine learning"""
        history = self.metrics_history.get(metric_name, [])
        
        if len(history) < 5:
            return TrendAnalysis(
                metric_name=metric_name,
                period=period,
                trend_direction="insufficient_data",
                trend_strength=0.0,
                prediction=None,
                confidence_interval=(0.0, 0.0),
                anomalies_detected=[]
            )
        
        # Prepare data for ML model
        timestamps = [(dp.timestamp - history[0].timestamp).total_seconds() for dp in history]
        values = [dp.value for dp in history]
        
        X = np.array(timestamps).reshape(-1, 1)
        y = np.array(values)
        
        # Train linear regression model
        model = LinearRegression()
        model.fit(X, y)
        
        # Store model for future predictions
        self.trend_models[metric_name] = model
        
        # Calculate trend strength (R-squared)
        trend_strength = model.score(X, y)
        
        # Determine trend direction
        slope = model.coef_[0]
        if abs(slope) < 0.001:  # Threshold for "stable"
            trend_direction = "stable"
        elif slope > 0:
            trend_direction = "increasing"
        else:
            trend_direction = "decreasing"
        
        # Make prediction for next period
        last_timestamp = timestamps[-1]
        period_seconds = {
            TrendPeriod.DAILY: 86400,
            TrendPeriod.WEEKLY: 604800,
            TrendPeriod.MONTHLY: 2592000,
            TrendPeriod.QUARTERLY: 7776000,
            TrendPeriod.YEARLY: 31536000
        }
        
        next_timestamp = last_timestamp + period_seconds[period]
        prediction = model.predict([[next_timestamp]])[0]
        
        # Calculate confidence interval (simplified)
        residuals = y - model.predict(X)
        residual_std = np.std(residuals)
        confidence_interval = (prediction - 1.96 * residual_std, prediction + 1.96 * residual_std)
        
        # Detect anomalies (points far from trend line)
        predicted_values = model.predict(X)
        anomalies = []
        for i, (actual, predicted) in enumerate(zip(values, predicted_values)):
            if abs(actual - predicted) > 2 * residual_std:
                anomalies.append(history[i].timestamp)
        
        return TrendAnalysis(
            metric_name=metric_name,
            period=period,
            trend_direction=trend_direction,
            trend_strength=trend_strength,
            prediction=prediction,
            confidence_interval=confidence_interval,
            anomalies_detected=anomalies
        )
    
    async def generate_predictive_analysis(self, project_id: str) -> AnalyticsReport:
        """Generate predictive analysis using ML models"""
        report_id = str(uuid.uuid4())
        
        # Perform trend analysis on key metrics
        trends = []
        key_metrics = ["migration_progress", "cost_per_day", "agent_success_rate"]
        
        for metric in key_metrics:
            if metric in self.metrics_history:
                trend = self.perform_trend_analysis(metric)
                trends.append(trend)
        
        # Generate predictions and recommendations
        recommendations = []
        total_confidence = 0.0
        
        for trend in trends:
            if trend.trend_strength > 0.7:  # High confidence trends
                if trend.metric_name == "migration_progress" and trend.trend_direction == "decreasing":
                    recommendations.append("Migration progress is slowing - consider resource reallocation")
                elif trend.metric_name == "cost_per_day" and trend.trend_direction == "increasing":
                    recommendations.append("Daily costs are rising - implement cost controls")
                elif trend.metric_name == "agent_success_rate" and trend.trend_direction == "decreasing":
                    recommendations.append("Agent performance declining - review and optimize workflows")
            
            total_confidence += trend.trend_strength
        
        avg_confidence = total_confidence / len(trends) if trends else 0.0
        
        # Create comprehensive metrics
        metrics = {
            "prediction_accuracy": avg_confidence,
            "trends_analyzed": len(trends),
            "anomalies_detected": sum(len(t.anomalies_detected) for t in trends),
            "data_points_analyzed": sum(len(self.metrics_history.get(m, [])) for m in key_metrics)
        }
        
        # Generate charts data
        charts_data = {
            "trend_predictions": {
                "metrics": [t.metric_name for t in trends],
                "predictions": [t.prediction for t in trends if t.prediction],
                "confidence": [t.trend_strength for t in trends]
            },
            "anomaly_timeline": {
                "dates": [dt.isoformat() for trend in trends for dt in trend.anomalies_detected],
                "metrics": [trend.metric_name for trend in trends for _ in trend.anomalies_detected]
            }
        }
        
        report = AnalyticsReport(
            report_id=report_id,
            title=f"Predictive Analysis - Project {project_id}",
            report_type=AnalyticsType.PREDICTIVE_ANALYSIS,
            project_id=project_id,
            generated_at=datetime.now(),
            summary=f"Analyzed {len(trends)} metrics with {avg_confidence:.1%} average confidence",
            recommendations=recommendations,
            metrics=metrics,
            charts_data=charts_data,
            trend_analysis=trends,
            confidence_score=avg_confidence,
            data_quality_score=0.95  # Based on data completeness and accuracy
        )
        
        self.reports[report_id] = report
        return report
    
    async def create_custom_dashboard(self, dashboard_name: str, widgets: List[DashboardWidget]) -> str:
        """Create custom analytics dashboard"""
        dashboard_id = str(uuid.uuid4())
        self.dashboards[dashboard_id] = widgets
        
        logger.info(f"Created custom dashboard '{dashboard_name}' with {len(widgets)} widgets")
        return dashboard_id
    
    async def get_real_time_metrics(self, metric_names: List[str], limit: int = 100) -> Dict[str, List[Dict[str, Any]]]:
        """Get real-time metrics data"""
        result = {}
        
        for metric_name in metric_names:
            history = self.metrics_history.get(metric_name, [])
            # Get latest data points
            latest_points = history[-limit:] if len(history) > limit else history
            result[metric_name] = [dp.to_dict() for dp in latest_points]
        
        return result
    
    async def _notify_websocket(self, event_type: str, data: Dict[str, Any]):
        """Send notification via WebSocket service"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    f"{self.websocket_url}/broadcast",
                    json={
                        "channel_type": "analytics",
                        "message": {
                            "type": event_type,
                            "data": data,
                            "timestamp": datetime.now().isoformat()
                        }
                    }
                )
        except Exception as e:
            logger.warning(f"Failed to send WebSocket notification: {e}")
    
    async def get_system_health_analysis(self) -> AnalyticsReport:
        """Generate comprehensive system health analysis"""
        report_id = str(uuid.uuid4())
        
        # Analyze system metrics
        cpu_trend = self.perform_trend_analysis("system_cpu_usage")
        memory_trend = self.perform_trend_analysis("memory_utilization")
        
        # Calculate health scores
        cpu_health = 100 - (np.mean([dp.value for dp in self.metrics_history.get("system_cpu_usage", [])][-10:]) if self.metrics_history.get("system_cpu_usage") else 50)
        memory_health = 100 - (np.mean([dp.value for dp in self.metrics_history.get("memory_utilization", [])][-10:]) if self.metrics_history.get("memory_utilization") else 60)
        
        overall_health = (cpu_health + memory_health) / 2
        
        recommendations = []
        if cpu_health < 50:
            recommendations.append("High CPU usage detected - consider scaling resources")
        if memory_health < 40:
            recommendations.append("Memory utilization high - optimize memory usage or add capacity")
        if overall_health > 80:
            recommendations.append("System health is excellent - maintain current practices")
        
        active_alerts = [alert for alert in self.alerts.values() if not alert.is_resolved]
        
        metrics = {
            "overall_health_score": overall_health,
            "cpu_health_score": cpu_health,
            "memory_health_score": memory_health,
            "active_alerts_count": len(active_alerts),
            "system_uptime_days": 30  # Simulated
        }
        
        charts_data = {
            "health_scores": {
                "labels": ["CPU", "Memory", "Overall"],
                "values": [cpu_health, memory_health, overall_health]
            },
            "alert_distribution": {
                "labels": [severity.value for severity in AlertSeverity],
                "values": [len([a for a in active_alerts if a.severity == severity]) for severity in AlertSeverity]
            }
        }
        
        report = AnalyticsReport(
            report_id=report_id,
            title="System Health Analysis",
            report_type=AnalyticsType.SYSTEM_HEALTH,
            project_id=None,
            generated_at=datetime.now(),
            summary=f"Overall system health: {overall_health:.1f}% with {len(active_alerts)} active alerts",
            recommendations=recommendations,
            metrics=metrics,
            charts_data=charts_data,
            trend_analysis=[cpu_trend, memory_trend],
            alerts=active_alerts,
            confidence_score=0.9,
            data_quality_score=0.95
        )
        
        self.reports[report_id] = report
        return report
    
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

async def check_dependencies():
    """Check service dependencies for readiness"""
    dependencies = {}

    # Check PostgreSQL
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            database=os.getenv("POSTGRES_DB", "migration_platform"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", "postgres")
        )
        conn.close()
        dependencies["postgresql"] = "healthy"
    except Exception:
        dependencies["postgresql"] = "unhealthy"

    # Check Redis
    try:
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        with socket.create_connection((redis_host, redis_port), timeout=2):
            dependencies["redis"] = "healthy"
    except Exception:
        dependencies["redis"] = "unhealthy"

    return dependencies

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

# Trailing slash redirect middleware (308 Permanent Redirect)
@app.middleware("http")
async def trailing_slash_redirect_middleware(request, call_next):
    # Skip redirect for health check endpoints and non-GET requests
    if request.method != "GET" or request.url.path in ["/livez", "/healthz", "/health"]:
        return await call_next(request)

    # Check if path ends with trailing slash (except root path)
    if request.url.path.endswith("/") and request.url.path != "/":
        # Remove trailing slash for canonical path
        canonical_path = request.url.path.rstrip("/")
        query_string = str(request.url.query) if request.url.query else ""

        # Build redirect URL
        redirect_url = f"{request.url.scheme}://{request.url.host}:{request.url.port}{canonical_path}"
        if query_string:
            redirect_url += f"?{query_string}"

        # Return 308 Permanent Redirect
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=redirect_url, status_code=308)

    return await call_next(request)

# Pydantic models
class MetricDataRequest(BaseModel):
    metric_name: str
    value: float
    metadata: Optional[Dict[str, Any]] = None

class TrendAnalysisRequest(BaseModel):
    metric_name: str
    period: TrendPeriod = TrendPeriod.WEEKLY

class DashboardRequest(BaseModel):
    dashboard_name: str
    widgets: List[Dict[str, Any]]

class AlertUpdateRequest(BaseModel):
    is_resolved: bool

# API Endpoints
@app.get("/livez")
async def liveness_check():
    """Liveness probe - checks if service is running"""
    return {
        "status": "healthy",
        "service": "analytics-service",
        "uptime": int(time.time() - SERVICE_START_TIME),
        "timestamp": datetime.now().isoformat(),
        "version": "3.0.0"
    }

@app.get("/healthz")
async def readiness_check():
    """Readiness probe - checks if service is ready to accept traffic"""
    dependencies = await check_dependencies()

    # Determine overall status
    overall_status = "healthy" if all(status == "healthy" for status in dependencies.values()) else "unhealthy"

    return {
        "status": overall_status,
        "service": "analytics-service",
        "uptime": int(time.time() - SERVICE_START_TIME),
        "timestamp": datetime.now().isoformat(),
        "version": "3.0.0",
        "dependencies": dependencies
    }

@app.get("/health")
async def health_check():
    """Health check endpoint - backward compatibility alias to readiness"""
    return await readiness_check()

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

@app.post("/analytics/predictive")
async def generate_predictive_analysis(project_id: str):
    """Generate predictive analysis using ML models"""
    report = await analytics_manager.generate_predictive_analysis(project_id)
    return {"report": report.to_dict()}

@app.get("/analytics/system-health")
async def get_system_health_analysis():
    """Get comprehensive system health analysis"""
    report = await analytics_manager.get_system_health_analysis()
    return {"report": report.to_dict()}

@app.post("/metrics")
async def add_metric_data(request: MetricDataRequest, background_tasks: BackgroundTasks):
    """Add real-time metric data"""
    background_tasks.add_task(
        analytics_manager.add_metric_data,
        request.metric_name,
        request.value,
        request.metadata
    )
    return {"message": "Metric data added successfully"}

@app.get("/metrics/real-time")
async def get_real_time_metrics(metric_names: str, limit: int = 100):
    """Get real-time metrics data"""
    metric_list = metric_names.split(",")
    data = await analytics_manager.get_real_time_metrics(metric_list, limit)
    return {"metrics": data}

@app.post("/trends/analyze")
async def analyze_trend(request: TrendAnalysisRequest):
    """Perform trend analysis on specific metric"""
    trend = analytics_manager.perform_trend_analysis(request.metric_name, request.period)
    return {"trend_analysis": trend.to_dict()}

@app.get("/alerts")
async def get_alerts(severity: Optional[AlertSeverity] = None, project_id: Optional[str] = None):
    """Get alerts with optional filtering"""
    alerts = list(analytics_manager.alerts.values())
    
    if severity:
        alerts = [alert for alert in alerts if alert.severity == severity]
    
    if project_id:
        alerts = [alert for alert in alerts if alert.project_id == project_id]
    
    return {
        "alerts": [alert.to_dict() for alert in alerts],
        "total_count": len(alerts)
    }

@app.put("/alerts/{alert_id}")
async def update_alert(alert_id: str, request: AlertUpdateRequest):
    """Update alert status"""
    if alert_id not in analytics_manager.alerts:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    alert = analytics_manager.alerts[alert_id]
    alert.is_resolved = request.is_resolved
    
    if request.is_resolved:
        alert.resolved_at = datetime.now()
    
    return {"message": "Alert updated successfully", "alert": alert.to_dict()}

@app.post("/dashboards")
async def create_dashboard(request: DashboardRequest):
    """Create custom analytics dashboard"""
    widgets = []
    for widget_data in request.widgets:
        widget = DashboardWidget(
            widget_id=str(uuid.uuid4()),
            title=widget_data["title"],
            type=widget_data["type"],
            data_source=widget_data["data_source"],
            configuration=widget_data.get("configuration", {}),
            position=widget_data.get("position", {"x": 0, "y": 0, "width": 4, "height": 3})
        )
        widgets.append(widget)
    
    dashboard_id = await analytics_manager.create_custom_dashboard(request.dashboard_name, widgets)
    
    return {
        "dashboard_id": dashboard_id,
        "message": "Dashboard created successfully",
        "widgets_count": len(widgets)
    }

@app.get("/dashboards/{dashboard_id}")
async def get_dashboard(dashboard_id: str):
    """Get dashboard configuration"""
    if dashboard_id not in analytics_manager.dashboards:
        raise HTTPException(status_code=404, detail="Dashboard not found")
    
    widgets = analytics_manager.dashboards[dashboard_id]
    return {
        "dashboard_id": dashboard_id,
        "widgets": [widget.to_dict() for widget in widgets]
    }

@app.get("/summary")
async def get_analytics_summary():
    """Get comprehensive analytics summary"""
    total_reports = len(analytics_manager.reports)
    active_alerts = len([alert for alert in analytics_manager.alerts.values() if not alert.is_resolved])
    total_metrics = len(analytics_manager.metrics_history)
    total_dashboards = len(analytics_manager.dashboards)
    
    # Calculate average confidence across all reports
    reports_with_confidence = [r for r in analytics_manager.reports.values() if r.confidence_score > 0]
    avg_confidence = sum(r.confidence_score for r in reports_with_confidence) / len(reports_with_confidence) if reports_with_confidence else 0
    
    # Recent activity
    recent_reports = sorted(
        analytics_manager.reports.values(),
        key=lambda r: r.generated_at,
        reverse=True
    )[:5]
    
    recent_alerts = sorted(
        [alert for alert in analytics_manager.alerts.values() if not alert.is_resolved],
        key=lambda a: a.created_at,
        reverse=True
    )[:5]
    
    return {
        "summary": {
            "total_reports": total_reports,
            "active_alerts": active_alerts,
            "total_metrics_tracked": total_metrics,
            "total_dashboards": total_dashboards,
            "average_confidence": avg_confidence,
            "ml_models_trained": len(analytics_manager.trend_models)
        },
        "recent_reports": [report.to_dict() for report in recent_reports],
        "recent_alerts": [alert.to_dict() for alert in recent_alerts]
    }

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

# ---------------------------------------------------------------------------
# Compatibility Stub Endpoints for Document Service Integration
# Implements minimal /api/documents/analysis/... & /api/analysis/... routes
# expected by document-service HttpAnalysisRepository to avoid 404s.
# Data is stored in-memory only (not persistent) as these are placeholder
# analytics constructs until a full analysis store is implemented.
# ---------------------------------------------------------------------------
from fastapi import Body

_analysis_versions: Dict[str, Dict[str, Any]] = {}
_analysis_batches: Dict[str, Dict[str, Any]] = {}
_analysis_results: Dict[str, Dict[str, Any]] = {}

def _now_iso() -> str:
    return datetime.utcnow().isoformat()

@app.post("/api/documents/analysis/results/version", status_code=201)
async def create_analysis_version(payload: Dict[str, Any] = Body(...)):
    version_id = payload.get("version_id") or payload.get("id") or f"ver_{uuid.uuid4()}"
    data = {
        "version_id": version_id,
        "description": payload.get("description", ""),
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    _analysis_versions[version_id] = data
    return {"version_id": version_id, "version": data}

@app.get("/api/documents/analysis/results/version/{version_id}/batches")
async def list_batches_for_version(version_id: str, limit: int = 50, offset: int = 0):
    batches = [b for b in _analysis_batches.values() if b.get("version_id") == version_id]
    return {"batches": batches[offset: offset+limit], "total": len(batches)}

@app.post("/api/documents/analysis/results/batch", status_code=201)
async def create_analysis_batch(payload: Dict[str, Any] = Body(...)):
    batch_id = payload.get("batch_id") or payload.get("id") or f"batch_{uuid.uuid4()}"
    version_id = payload.get("version_id") or payload.get("versionId")
    data = {
        "batch_id": batch_id,
        "version_id": version_id,
        "status": "created",
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "results": []
    }
    _analysis_batches[batch_id] = data
    return {"batch_id": batch_id, "batch": data}

@app.get("/api/documents/analysis/results/batch/{batch_id}")
async def get_batch(batch_id: str):
    batch = _analysis_batches.get(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    return batch

@app.get("/api/documents/analysis/results/batch/{batch_id}/results")
async def list_batch_results(batch_id: str, limit: int = 50, offset: int = 0):
    batch = _analysis_batches.get(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    results = batch.get("results", [])
    return {"results": results[offset: offset+limit], "total": len(results)}

@app.post("/api/analysis", status_code=201)
async def create_analysis_result(payload: Dict[str, Any] = Body(...)):
    result_id = payload.get("result_id") or payload.get("id") or f"res_{uuid.uuid4()}"
    batch_id = payload.get("batch_id")
    data = {
        "result_id": result_id,
        "batch_id": batch_id,
        "content": payload.get("content"),
        "metadata": payload.get("metadata", {}),
        "status": payload.get("status", "created"),
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    _analysis_results[result_id] = data
    if batch_id and batch_id in _analysis_batches:
        _analysis_batches[batch_id]["results"].append(data)
        _analysis_batches[batch_id]["updated_at"] = _now_iso()
    return {"id": result_id, "result": data}

@app.put("/api/analysis/{result_id}")
async def update_analysis_result(result_id: str, payload: Dict[str, Any] = Body(...)):
    res = _analysis_results.get(result_id)
    if not res:
        raise HTTPException(status_code=404, detail="Result not found")
    res.update({k: v for k, v in payload.items() if k not in {"result_id", "created_at"}})
    res["updated_at"] = _now_iso()
    return {"result": res}

@app.delete("/api/analysis/{result_id}", status_code=204)
async def delete_analysis_result(result_id: str):
    res = _analysis_results.pop(result_id, None)
    if not res:
        raise HTTPException(status_code=404, detail="Result not found")
    batch_id = res.get("batch_id")
    if batch_id and batch_id in _analysis_batches:
        _analysis_batches[batch_id]["results"] = [r for r in _analysis_batches[batch_id]["results"] if r.get("result_id") != result_id]
    return None

@app.get("/api/analysis/version/{version_id}/batches")
async def list_batches_alt(version_id: str, limit: int = 50, offset: int = 0):
    return await list_batches_for_version(version_id, limit, offset)

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8014)),
        reload=True,
        log_level="info"
    )
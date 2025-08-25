"""
Cost Analyzer - AWS cost analysis and optimization
"""

import structlog
from typing import Dict, List, Optional, Any
import asyncio
from datetime import datetime, timedelta, date
import json

from .aws_client import AWSClient

logger = structlog.get_logger()

class CostAnalyzer:
    """AWS cost analysis and optimization recommendations"""
    
    def __init__(self, aws_client: AWSClient):
        self.aws_client = aws_client
        self.cost_data_cache = {}  # In-memory cache for cost data
    
    async def analyze_costs(
        self,
        project_id: str,
        start_date: date,
        end_date: date,
        group_by: List[str] = None,
        filters: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Analyze AWS costs for the specified period"""
        try:
            logger.info(
                "Starting cost analysis",
                project_id=project_id,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat()
            )
            
            # Convert dates to strings for AWS API
            start_str = start_date.isoformat()
            end_str = end_date.isoformat()
            
            # Default group by service
            if not group_by:
                group_by = [{"Type": "DIMENSION", "Key": "SERVICE"}]
            else:
                group_by = [{"Type": "DIMENSION", "Key": key} for key in group_by]
            
            # Get cost and usage data
            cost_data = await self.aws_client.get_cost_and_usage(
                start_date=start_str,
                end_date=end_str,
                granularity="MONTHLY",
                group_by=group_by,
                filters=filters
            )
            
            # Process the cost data
            analysis = await self._process_cost_data(cost_data, project_id)
            
            # Get optimization recommendations
            recommendations = await self._get_cost_optimization_recommendations()
            analysis["cost_optimization_recommendations"] = recommendations
            
            # Cache the results
            cache_key = f"{project_id}_{start_str}_{end_str}"
            self.cost_data_cache[cache_key] = analysis
            
            logger.info(
                "Cost analysis completed",
                project_id=project_id,
                total_cost=analysis.get("total_cost", 0)
            )
            
            return analysis
            
        except Exception as e:
            logger.error(
                "Cost analysis failed",
                project_id=project_id,
                error=str(e)
            )
            return {
                "project_id": project_id,
                "error": str(e),
                "total_cost": 0,
                "currency": "USD",
                "cost_breakdown": []
            }
    
    async def _process_cost_data(
        self,
        cost_data: Dict[str, Any],
        project_id: str
    ) -> Dict[str, Any]:
        """Process raw cost data from AWS Cost Explorer"""
        results_by_time = cost_data.get("ResultsByTime", [])
        
        total_cost = 0.0
        cost_breakdown = []
        trends = {"dates": [], "costs": []}
        service_costs = {}
        
        for time_period in results_by_time:
            time_start = time_period.get("TimePeriod", {}).get("Start")
            trends["dates"].append(time_start)
            
            period_total = 0.0
            
            for group in time_period.get("Groups", []):
                service = group.get("Keys", ["Unknown"])[0]
                metrics = group.get("Metrics", {})
                blended_cost = metrics.get("BlendedCost", {})
                amount = float(blended_cost.get("Amount", 0))
                unit = blended_cost.get("Unit", "USD")
                
                # Add to service totals
                if service not in service_costs:
                    service_costs[service] = 0.0
                service_costs[service] += amount
                
                # Add to breakdown
                cost_breakdown.append({
                    "service": service,
                    "amount": amount,
                    "unit": unit,
                    "usage_type": "General",
                    "region": "All",
                    "time_period": time_start
                })
                
                period_total += amount
            
            trends["costs"].append(period_total)
            total_cost += period_total
        
        # Get top services
        top_services = [
            {"service": service, "cost": cost, "percentage": (cost / total_cost * 100) if total_cost > 0 else 0}
            for service, cost in sorted(service_costs.items(), key=lambda x: x[1], reverse=True)[:10]
        ]
        
        return {
            "project_id": project_id,
            "analysis_period": {
                "start": trends["dates"][0] if trends["dates"] else None,
                "end": trends["dates"][-1] if trends["dates"] else None
            },
            "total_cost": round(total_cost, 2),
            "currency": "USD",
            "cost_breakdown": cost_breakdown,
            "trends": trends,
            "top_services": top_services
        }
    
    async def _get_cost_optimization_recommendations(self) -> List[str]:
        """Get cost optimization recommendations"""
        try:
            # Get rightsizing recommendations
            rightsizing_data = await self.aws_client.get_rightsizing_recommendations()
            
            recommendations = []
            
            # Process rightsizing recommendations
            rightsizing_recs = rightsizing_data.get("RightsizingRecommendations", [])
            if rightsizing_recs:
                recommendations.append(f"Found {len(rightsizing_recs)} EC2 rightsizing opportunities")
                
                for rec in rightsizing_recs[:5]:  # Top 5 recommendations
                    current_instance = rec.get("CurrentInstance", {})
                    resource_id = current_instance.get("ResourceId", "Unknown")
                    estimated_savings = rec.get("EstimatedMonthlySavings", {}).get("Amount", "0")
                    
                    if float(estimated_savings) > 0:
                        recommendations.append(
                            f"Rightsize EC2 instance {resource_id} for ${estimated_savings}/month savings"
                        )
            
            # Add general recommendations
            general_recommendations = [
                "Review unused EBS volumes and snapshots",
                "Consider Reserved Instances for steady-state workloads",
                "Implement lifecycle policies for S3 storage optimization",
                "Review CloudWatch logs retention periods",
                "Consider Spot Instances for fault-tolerant workloads",
                "Review data transfer costs between regions and services",
                "Implement auto-scaling for variable workloads",
                "Review and optimize database instance sizes"
            ]
            
            recommendations.extend(general_recommendations[:5])  # Add top 5 general recommendations
            
            return recommendations
            
        except Exception as e:
            logger.error("Failed to get cost optimization recommendations", error=str(e))
            return [
                "Review resource utilization patterns",
                "Consider Reserved Instances for steady workloads",
                "Implement automated cost monitoring"
            ]
    
    async def get_cost_trends(
        self,
        project_id: str,
        days: int = 30,
        granularity: str = "DAILY"
    ) -> Dict[str, Any]:
        """Get cost trends for the specified period"""
        try:
            end_date = datetime.utcnow().date()
            start_date = end_date - timedelta(days=days)
            
            cost_data = await self.aws_client.get_cost_and_usage(
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
                granularity=granularity,
                group_by=[{"Type": "DIMENSION", "Key": "SERVICE"}]
            )
            
            trends = {
                "dates": [],
                "daily_costs": [],
                "service_breakdown": {},
                "average_daily_cost": 0.0,
                "trend_direction": "stable"
            }
            
            total_cost = 0.0
            daily_costs = []
            
            for time_period in cost_data.get("ResultsByTime", []):
                date_str = time_period.get("TimePeriod", {}).get("Start")
                trends["dates"].append(date_str)
                
                daily_total = 0.0
                for group in time_period.get("Groups", []):
                    service = group.get("Keys", ["Unknown"])[0]
                    amount = float(group.get("Metrics", {}).get("BlendedCost", {}).get("Amount", 0))
                    
                    if service not in trends["service_breakdown"]:
                        trends["service_breakdown"][service] = []
                    trends["service_breakdown"][service].append(amount)
                    
                    daily_total += amount
                
                trends["daily_costs"].append(daily_total)
                daily_costs.append(daily_total)
                total_cost += daily_total
            
            # Calculate average and trend
            if daily_costs:
                trends["average_daily_cost"] = total_cost / len(daily_costs)
                
                # Simple trend analysis
                if len(daily_costs) >= 2:
                    recent_avg = sum(daily_costs[-7:]) / min(7, len(daily_costs))
                    older_avg = sum(daily_costs[:-7]) / max(1, len(daily_costs) - 7)
                    
                    if recent_avg > older_avg * 1.1:
                        trends["trend_direction"] = "increasing"
                    elif recent_avg < older_avg * 0.9:
                        trends["trend_direction"] = "decreasing"
                    else:
                        trends["trend_direction"] = "stable"
            
            return trends
            
        except Exception as e:
            logger.error(
                "Failed to get cost trends",
                project_id=project_id,
                error=str(e)
            )
            return {
                "dates": [],
                "daily_costs": [],
                "service_breakdown": {},
                "average_daily_cost": 0.0,
                "trend_direction": "unknown",
                "error": str(e)
            }
    
    async def get_cost_forecast(
        self,
        project_id: str,
        forecast_days: int = 30
    ) -> Dict[str, Any]:
        """Get cost forecast using AWS Cost Explorer"""
        try:
            start_date = datetime.utcnow().date()
            end_date = start_date + timedelta(days=forecast_days)
            
            # Use historical data to estimate forecast
            historical_days = 30
            historical_start = start_date - timedelta(days=historical_days)
            
            historical_data = await self.aws_client.get_cost_and_usage(
                start_date=historical_start.isoformat(),
                end_date=start_date.isoformat(),
                granularity="DAILY"
            )
            
            # Calculate average daily cost from historical data
            daily_costs = []
            for time_period in historical_data.get("ResultsByTime", []):
                daily_total = 0.0
                for group in time_period.get("Groups", []):
                    amount = float(group.get("Metrics", {}).get("BlendedCost", {}).get("Amount", 0))
                    daily_total += amount
                daily_costs.append(daily_total)
            
            if daily_costs:
                avg_daily_cost = sum(daily_costs) / len(daily_costs)
                forecasted_total = avg_daily_cost * forecast_days
                
                # Add some variance based on historical patterns
                variance = max(daily_costs) - min(daily_costs) if len(daily_costs) > 1 else 0
                confidence_interval = {
                    "low": max(0, forecasted_total - (variance * forecast_days * 0.5)),
                    "high": forecasted_total + (variance * forecast_days * 0.5)
                }
            else:
                avg_daily_cost = 0.0
                forecasted_total = 0.0
                confidence_interval = {"low": 0.0, "high": 0.0}
            
            return {
                "project_id": project_id,
                "forecast_period_days": forecast_days,
                "forecasted_total_cost": round(forecasted_total, 2),
                "average_daily_cost": round(avg_daily_cost, 2),
                "confidence_interval": {
                    "low": round(confidence_interval["low"], 2),
                    "high": round(confidence_interval["high"], 2)
                },
                "currency": "USD",
                "forecast_date": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(
                "Failed to get cost forecast",
                project_id=project_id,
                error=str(e)
            )
            return {
                "project_id": project_id,
                "error": str(e),
                "forecasted_total_cost": 0.0
            }
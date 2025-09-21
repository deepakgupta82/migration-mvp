"""
Record Insight Tool - Enhanced with Traceability

This tool records insights with full traceability to:
1. Source discoveries (facts) that were used to generate the insight
2. The query that triggered the insight generation
3. The agent/workflow that created the insight
4. Timestamp and confidence level
5. Links to related entities in the knowledge graph
"""

from crewai.tools import BaseTool
import logging
from typing import Optional, Dict, Any, List
import os
import json
from datetime import datetime

try:
    import requests
except Exception:
    requests = None

logger = logging.getLogger(__name__)

class RecordInsightTool(BaseTool):
    name: str = "Record Insight Tool"
    description: str = (
        "Records insights with full traceability to source facts, queries, and agents. "
        "Use this to persist valuable insights for future reference and build a knowledge evolution history."
    )

    def __init__(self, project_id: Optional[str] = None, agent_name: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.project_id = project_id or os.getenv("CURRENT_PROJECT_ID")
        self.agent_name = agent_name or os.getenv("CURRENT_AGENT_NAME", "unknown_agent")

    def _run(self, insight_text: str, category: str = "general", confidence: float = 0.8,
             source_facts: Optional[List[str]] = None, related_query: Optional[str] = None,
             tags: Optional[List[str]] = None) -> str:
        """Record an insight with full traceability"""
        try:
            if not self.project_id:
                return "Error: No project ID specified for insight recording"

            if not insight_text or not insight_text.strip():
                return "Error: Insight text cannot be empty"

            # Create traceable insight record
            insight_record = {
                "text": insight_text.strip(),
                "category": category.lower(),
                "confidence": max(0.0, min(1.0, confidence)),  # Clamp to 0-1
                "source_facts": source_facts or [],
                "related_query": related_query,
                "tags": tags or [],
                "agent_name": self.agent_name,
                "project_id": self.project_id,
                "timestamp": datetime.utcnow().isoformat(),
                "traceability": {
                    "stage_1_facts_used": len(source_facts) if source_facts else 0,
                    "query_context": related_query,
                    "agent_context": self.agent_name,
                    "processing_timestamp": datetime.utcnow().isoformat()
                }
            }

            # Store in graph database as :Insight node
            result = self._store_insight_in_graph(insight_record)

            if result.get("success"):
                # Link to source facts if provided
                if source_facts:
                    self._link_insight_to_facts(result["insight_id"], source_facts)

                return self._format_success_response(insight_record, result)
            else:
                return f"Error: Failed to store insight: {result.get('error', 'Unknown error')}"

        except Exception as e:
            logger.error(f"Error in RecordInsightTool: {e}")
            return f"Insight recording error: {str(e)}"

    def _store_insight_in_graph(self, insight_record: Dict[str, Any]) -> Dict[str, Any]:
        """Store insight as :Insight node in Neo4j"""
        try:
            # Graph service runs on 8006 by default
            graph_service_url = os.getenv("GRAPH_SERVICE_URL", "http://localhost:8006")

            # Create unique insight ID
            insight_id = f"insight_{self.project_id}_{hash(insight_record['text'] + insight_record['timestamp']) % 1000000}"

            payload = {
                "text": insight_record["text"],
                "category": insight_record["category"],
                "confidence": insight_record["confidence"],
                "agent_name": insight_record["agent_name"],
                "tags": insight_record["tags"],
                "traceability": insight_record["traceability"],
                "insight_id": insight_id
            }

            headers = {
                "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}",
                "Content-Type": "application/json",
            }

            # Use graph service to store insight
            response = requests.post(
                f"{graph_service_url}/api/graphs/projects/{self.project_id}/insights",
                headers=headers,
                json=payload,
                timeout=15
            )

            if response.status_code in [200, 201]:
                return {
                    "success": True,
                    "insight_id": insight_id,
                    "message": "Insight stored successfully"
                }
            else:
                logger.error(f"Failed to store insight: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"Graph service error: {response.status_code}"
                }

        except Exception as e:
            logger.error(f"Error storing insight in graph: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _link_insight_to_facts(self, insight_id: str, source_fact_ids: List[str]) -> None:
        """Link insight to the source facts that were used to generate it"""
        try:
            # Graph service runs on 8006 by default
            graph_service_url = os.getenv("GRAPH_SERVICE_URL", "http://localhost:8006")

            headers = {
                "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}",
                "Content-Type": "application/json",
            }

            for fact_id in source_fact_ids:
                try:
                    payload = {
                        "insight_id": insight_id,
                        "fact_id": fact_id
                    }

                    response = requests.post(
                        f"{graph_service_url}/api/graphs/projects/{self.project_id}/insights/{insight_id}/link-fact",
                        headers=headers,
                        json=payload,
                        timeout=10
                    )

                    if response.status_code not in [200, 201]:
                        logger.warning(f"Failed to link insight {insight_id} to fact {fact_id}: {response.status_code}")

                except Exception as e:
                    logger.warning(f"Error linking insight to fact {fact_id}: {e}")

        except Exception as e:
            logger.error(f"Error in insight-fact linking: {e}")

    def _format_success_response(self, insight_record: Dict[str, Any], result: Dict[str, Any]) -> str:
        """Format success response with traceability information"""
        response = f"""# ✅ Insight Recorded Successfully

## Insight Details
- **ID**: {result.get('insight_id', 'Unknown')}
- **Category**: {insight_record['category'].title()}
- **Confidence**: {insight_record['confidence']:.1%}
- **Agent**: {insight_record['agent_name']}
- **Timestamp**: {insight_record['timestamp']}

## Content
{insight_record['text']}

## Traceability Information
- **Source Facts Used**: {len(insight_record.get('source_facts', []))}
- **Related Query**: {insight_record.get('related_query', 'None')}
- **Tags**: {', '.join(insight_record.get('tags', [])) or 'None'}

## Knowledge Evolution
This insight has been stored in the knowledge graph and linked to its source facts.
Future queries can build upon this insight, creating a chain of knowledge evolution.

---
*Recorded via RecordInsightTool - Full traceability maintained*
"""

        return response

    def _get_api_headers(self) -> Dict[str, str]:
        """Get standard API headers for service communication"""
        headers = {
            "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}",
            "Content-Type": "application/json",
        }
        correlation_id = os.getenv("X_CORRELATION_ID")
        if correlation_id:
            headers["X-Correlation-ID"] = correlation_id
        return headers

# Alias for backward compatibility
RecordInsight = RecordInsightTool
"""
Query Insights Tool - Stage 2: Layered Query Architecture

This tool implements the two-stage knowledge architecture:
1. First consults foundational facts (discoveries) from Stage 1
2. Then synthesizes higher-level insights using those facts as context
3. Provides layered responses with both factual foundation and synthesized insights
"""

from crewai.tools import BaseTool
import logging
from typing import Optional, Dict, Any, List
import os
import json

try:
    import requests
except Exception:
    requests = None

logger = logging.getLogger(__name__)

class QueryInsightsTool(BaseTool):
    name: str = "Query Insights Tool"
    description: str = (
        "Advanced query tool that provides layered insights by first consulting "
        "foundational facts and then synthesizing higher-level insights. Use this "
        "for complex analysis, recommendations, and strategic insights."
    )

    def __init__(self, project_id: Optional[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.project_id = project_id or os.getenv("CURRENT_PROJECT_ID")

    def _run(self, query: str) -> str:
        """Execute layered query: facts first, then insights"""
        try:
            if not self.project_id:
                return "Error: No project ID specified for insights query"

            # Stage 1: Get foundational facts
            facts = self._get_foundational_facts(query)

            if not facts:
                return self._fallback_to_basic_rag(query)

            # Stage 2: Synthesize insights using facts as context
            insights = self._synthesize_insights(query, facts)

            # Format layered response
            return self._format_layered_response(query, facts, insights)

        except Exception as e:
            logger.error(f"Error in QueryInsightsTool: {e}")
            return f"Insights query error: {str(e)}"

    def _get_foundational_facts(self, query: str) -> List[Dict[str, Any]]:
        """Stage 1: Query discoveries (foundational facts)"""
        try:
            graph_service_url = os.getenv("GRAPH_SERVICE_URL", "http://localhost:8005")
            search_url = f"{graph_service_url}/api/graphs/projects/{self.project_id}/discoveries/search"

            headers = {
                "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}",
                "Content-Type": "application/json",
            }

            # Search for relevant facts
            response = requests.post(
                search_url,
                headers=headers,
                json={"q": query, "limit": 10},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("results", [])
            else:
                logger.warning(f"Failed to get foundational facts: {response.status_code}")
                return []

        except Exception as e:
            logger.warning(f"Error getting foundational facts: {e}")
            return []

    def _synthesize_insights(self, query: str, facts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Stage 2: Use facts to generate higher-level insights"""
        try:
            llm_service_url = os.getenv("LLM_SERVICE_URL", "http://localhost:8007")

            # Prepare context from facts
            facts_context = "\n".join([
                f"- {fact['category'].upper()}: {fact['text']} (confidence: {fact['confidence']:.1f})"
                for fact in facts[:5]  # Limit to top 5 most relevant facts
            ])

            # Enhanced prompt for insight synthesis
            insight_prompt = f"""
Based on the following foundational facts from the project, provide strategic insights and recommendations for: {query}

FOUNDATIONAL FACTS:
{facts_context}

INSTRUCTION:
Provide a structured analysis with:
1. KEY INSIGHTS: 2-3 main insights derived from the facts
2. RECOMMENDATIONS: Specific actionable recommendations
3. RISKS/CONCERNS: Any potential issues identified
4. NEXT STEPS: Suggested follow-up actions

Keep the response focused and actionable. Use the facts as the foundation for your analysis.
"""

            headers = {
                "Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}",
                "Content-Type": "application/json",
            }

            payload = {
                "process_type": "insight_synthesis",
                "project_id": self.project_id,
                "prompt": insight_prompt,
            }

            response = requests.post(
                f"{llm_service_url}/api/llm/process",
                headers=headers,
                json=payload,
                timeout=30  # Longer timeout for insight synthesis
            )

            if response.status_code == 200:
                data = response.json()
                result = data.get("response") or data.get("result") or ""

                return {
                    "insights": result,
                    "facts_used": len(facts),
                    "synthesis_success": True
                }
            else:
                logger.warning(f"Failed to synthesize insights: {response.status_code}")
                return {
                    "insights": "Unable to generate insights at this time.",
                    "facts_used": len(facts),
                    "synthesis_success": False
                }

        except Exception as e:
            logger.error(f"Error synthesizing insights: {e}")
            return {
                "insights": f"Error generating insights: {str(e)}",
                "facts_used": len(facts),
                "synthesis_success": False
            }

    def _fallback_to_basic_rag(self, query: str) -> str:
        """Fallback to basic RAG when no facts are available"""
        try:
            from app.tools.rag_query_tool import RAGQueryTool
            tool = RAGQueryTool()
            basic_result = tool.run(query)

            return f"""# Query Results (Basic RAG - No Foundational Facts Available)

## Raw Knowledge Base Response:
{basic_result}

## Note:
This response is based on direct document search without the benefit of curated foundational facts.
For more comprehensive insights, ensure documents are processed to extract key facts first.
"""
        except Exception as e:
            logger.error(f"Basic RAG fallback failed: {e}")
            return f"Error: Unable to query knowledge base: {str(e)}"

    def _format_layered_response(self, query: str, facts: List[Dict[str, Any]], insights: Dict[str, Any]) -> str:
        """Format the layered response with facts and insights"""
        response = f"""# Layered Insights Query: {query}

## 📚 FOUNDATIONAL FACTS ({len(facts)} facts consulted)
"""

        # Group facts by category
        facts_by_category = {}
        for fact in facts:
            category = fact.get('category', 'general')
            if category not in facts_by_category:
                facts_by_category[category] = []
            facts_by_category[category].append(fact)

        # Display facts grouped by category
        for category, category_facts in facts_by_category.items():
            response += f"\n### {category.upper()} FACTS:\n"
            for fact in category_facts:
                confidence_pct = int(fact.get('confidence', 0) * 100)
                response += f"- **{confidence_pct}%**: {fact['text']}\n"
                response += f"  *Source: {fact.get('source_document', 'Unknown')}*\n"

        # Add insights section
        response += f"\n## 🎯 SYNTHESIZED INSIGHTS\n"
        response += f"*{insights.get('facts_used', 0)} facts used for analysis*\n\n"

        if insights.get('synthesis_success'):
            response += insights.get('insights', 'No insights generated.')
        else:
            response += f"⚠️ Insight synthesis encountered issues:\n{insights.get('insights', 'Unknown error')}"

        # Add metadata
        response += f"\n---\n"
        response += f"**Query Processing:** Stage 1 (Facts) → Stage 2 (Insights Synthesis)\n"
        response += f"**Knowledge Architecture:** Layered query with {len(facts)} foundational facts\n"
        response += f"**Analysis Method:** LLM-powered insight synthesis with fact verification"

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
QueryInsights = QueryInsightsTool
"""
Post-Processing Agent for Lessons Learned
Generates insights from document processing pipeline runs.
"""

import logging
from typing import List, Any, Optional, Dict
from crewai import Agent
import httpx
import json
from datetime import datetime

logger = logging.getLogger("ai-agent-service")

class PostProcessingAgent:
    """Agent for generating lessons learned from document processing"""

    @staticmethod
    def create_lessons_learned_agent(tools: List[Any], llm: Optional[Any] = None) -> Agent:
        """Create the lessons learned post-processing agent"""
        agent_kwargs = {
            'role': 'Lessons Learned Analyst',
            'goal': (
                'Analyze document processing results to extract valuable insights and best practices. '
                'Gather minimal, non-sensitive summaries from Knowledge Core including stats snapshots, '
                'KG metrics, and document topics. Use LLM to anonymize PII and generalize findings into '
                'actionable best-practice insights. Store insights with confidence scoring and category tagging.'
            ),
            'backstory': (
                'You are an experienced knowledge management specialist with 10+ years in enterprise '
                'document analysis and lessons learned capture. You have worked with Fortune 500 companies '
                'to analyze thousands of technical documents, extracting patterns, best practices, and '
                'insights that drive organizational learning and process improvement. Your expertise includes '
                'anonymizing sensitive information while preserving valuable insights, categorizing findings '
                'by relevance and impact, and scoring confidence levels based on data quality and consistency. '
                'You excel at synthesizing complex technical information into clear, actionable recommendations '
                'that can be applied across similar projects and scenarios.'
            ),
            'tools': tools,
            'verbose': True,
            'allow_delegation': False
        }

        if llm is not None:
            agent_kwargs['llm'] = llm

        return Agent(**agent_kwargs)

    @staticmethod
    async def gather_knowledge_core_data(project_id: str, document_id: str, service_urls: Dict[str, str]) -> Dict[str, Any]:
        """Gather minimal, non-sensitive data from Knowledge Core services"""
        data = {
            "project_id": project_id,
            "document_id": document_id,
            "timestamp": datetime.utcnow().isoformat(),
            "stats_snapshot": {},
            "kg_metrics": {},
            "document_topics": [],
            "processing_summary": {}
        }

        try:
            # Get graph statistics
            graph_url = service_urls.get("graph_service", "http://localhost:8004")
            async with httpx.AsyncClient(timeout=10.0) as client:
                stats_response = await client.get(f"{graph_url}/api/graphs/projects/{project_id}/stats")
                if stats_response.status_code == 200:
                    data["kg_metrics"] = stats_response.json()
                else:
                    logger.warning(f"Failed to get graph stats: {stats_response.status_code}")

                # Get topology for infrastructure insights
                topology_response = await client.get(f"{graph_url}/api/graphs/projects/{project_id}/topology")
                if topology_response.status_code == 200:
                    topology_data = topology_response.json()
                    data["stats_snapshot"]["infrastructure_topology"] = topology_data.get("stats", {})

        except Exception as e:
            logger.error(f"Error gathering graph data: {e}")

        try:
            # Get vector search results for document topics
            vector_url = service_urls.get("vector_service", "http://localhost:8005")
            async with httpx.AsyncClient(timeout=10.0) as client:
                search_response = await client.post(
                    f"{vector_url}/api/vectors/projects/{project_id}/search",
                    json={"query": "document processing summary", "limit": 10, "include_metadata": True}
                )
                if search_response.status_code == 200:
                    search_data = search_response.json()
                    data["document_topics"] = [
                        {
                            "content": result.get("text", "")[:500],  # Truncate for summary
                            "metadata": result.get("metadata", {})
                        }
                        for result in search_data.get("results", [])[:5]
                    ]

        except Exception as e:
            logger.error(f"Error gathering vector data: {e}")

        # Add basic processing summary
        data["processing_summary"] = {
            "document_processed": True,
            "timestamp": data["timestamp"],
            "data_sources": ["graph_service", "vector_service"]
        }

        return data

    @staticmethod
    async def generate_insights_with_llm(knowledge_data: Dict[str, Any], llm_service_url: str) -> Dict[str, Any]:
        """Use LLM to anonymize PII and generate generalized insights"""
        try:
            # Prepare prompt for LLM
            prompt = f"""
            Analyze the following document processing data to extract lessons learned and best practices.
            Focus on anonymizing any sensitive information while preserving valuable insights.

            Knowledge Core Data:
            {json.dumps(knowledge_data, indent=2)}

            Instructions:
            1. Identify patterns and trends in the data
            2. Extract best practices and lessons learned
            3. Anonymize any potentially sensitive information
            4. Categorize insights by type (technical, process, organizational)
            5. Score confidence level (high/medium/low) based on data quality
            6. Provide actionable recommendations

            Return insights in the following JSON format:
            {{
                "insights": [
                    {{
                        "category": "technical|process|organizational",
                        "title": "Brief title",
                        "description": "Detailed description",
                        "confidence": "high|medium|low",
                        "impact": "high|medium|low",
                        "recommendations": ["action1", "action2"]
                    }}
                ],
                "summary": "Overall summary of findings",
                "anonymization_note": "Note about data anonymization applied"
            }}
            """

            async with httpx.AsyncClient(timeout=30.0) as client:
                llm_response = await client.post(
                    f"{llm_service_url}/api/llm/process",
                    json={
                        "process_type": "lessons_learned",
                        "prompt": prompt,
                        "project_id": knowledge_data.get("project_id")
                    }
                )

                if llm_response.status_code == 200:
                    llm_data = llm_response.json()
                    response_text = llm_data.get("response", "{}")

                    # Try to parse JSON response
                    try:
                        insights = json.loads(response_text)
                        return insights
                    except json.JSONDecodeError:
                        # Fallback if LLM doesn't return valid JSON
                        return {
                            "insights": [{
                                "category": "general",
                                "title": "Document Processing Insights",
                                "description": response_text[:1000],
                                "confidence": "medium",
                                "impact": "medium",
                                "recommendations": ["Review processing results", "Apply identified patterns"]
                            }],
                            "summary": "LLM-generated insights from document processing",
                            "anonymization_note": "Content reviewed for sensitive information"
                        }
                else:
                    logger.error(f"LLM service error: {llm_response.status_code}")
                    return PostProcessingAgent._generate_fallback_insights(knowledge_data)

        except Exception as e:
            logger.error(f"Error generating insights with LLM: {e}")
            return PostProcessingAgent._generate_fallback_insights(knowledge_data)

    @staticmethod
    def _generate_fallback_insights(knowledge_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate basic insights when LLM is unavailable"""
        insights = []

        # Basic insights from available data
        kg_metrics = knowledge_data.get("kg_metrics", {})
        if kg_metrics:
            total_nodes = kg_metrics.get("total_nodes", 0)
            total_relationships = kg_metrics.get("total_relationships", 0)

            insights.append({
                "category": "technical",
                "title": "Knowledge Graph Growth",
                "description": f"Document processing added {total_nodes} nodes and {total_relationships} relationships to the knowledge graph",
                "confidence": "high",
                "impact": "medium",
                "recommendations": ["Monitor graph growth patterns", "Optimize relationship extraction"]
            })

        topology_stats = knowledge_data.get("stats_snapshot", {}).get("infrastructure_topology", {})
        if topology_stats:
            servers = topology_stats.get("servers", 0)
            applications = topology_stats.get("applications", 0)

            insights.append({
                "category": "organizational",
                "title": "Infrastructure Coverage",
                "description": f"Identified {servers} servers and {applications} applications in the infrastructure",
                "confidence": "high",
                "impact": "medium",
                "recommendations": ["Ensure complete infrastructure documentation", "Validate asset inventory"]
            })

        return {
            "insights": insights,
            "summary": "Basic insights generated from processing metrics",
            "anonymization_note": "Fallback insights with minimal data exposure"
        }

    @staticmethod
    async def store_insights_in_lessons_service(
        project_id: str,
        document_id: str,
        insights: Dict[str, Any],
        lessons_service_url: str
    ) -> bool:
        """Store insights in the lessons service"""
        try:
            lesson_event = {
                "project_id": project_id,
                "document_id": document_id,
                "summary": insights.get("summary", "Document processing insights"),
                "insights": [
                    f"{insight['category'].upper()}: {insight['title']} - {insight['description'][:200]}..."
                    for insight in insights.get("insights", [])
                ],
                "metadata": {
                    "processing_type": "post_processing_agent",
                    "timestamp": datetime.utcnow().isoformat(),
                    "insight_count": len(insights.get("insights", [])),
                    "confidence_levels": list(set(
                        insight.get("confidence", "unknown")
                        for insight in insights.get("insights", [])
                    )),
                    "categories": list(set(
                        insight.get("category", "general")
                        for insight in insights.get("insights", [])
                    )),
                    "anonymization_note": insights.get("anonymization_note", "")
                }
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{lessons_service_url}/api/lessons/summarize",
                    json=lesson_event
                )

                if response.status_code == 200:
                    logger.info(f"Successfully stored insights for project {project_id}, document {document_id}")
                    return True
                else:
                    logger.error(f"Failed to store insights: {response.status_code} - {response.text}")
                    return False

        except Exception as e:
            logger.error(f"Error storing insights: {e}")
            return False

    @staticmethod
    async def check_idempotency(project_id: str, document_id: str, lessons_service_url: str) -> bool:
        """Check if post-processing has already been completed for this project/document"""
        try:
            # Check if insights already exist in lessons service
            async with httpx.AsyncClient(timeout=5.0) as client:
                # This is a simplified check - in practice, you'd query the lessons service
                # for existing insights for this project/document combination
                response = await client.get(
                    f"{lessons_service_url}/api/lessons/project/{project_id}/document/{document_id}",
                    timeout=5.0
                )
                if response.status_code == 200:
                    data = response.json()
                    if data.get("insights") and len(data.get("insights", [])) > 0:
                        logger.info(f"Post-processing already completed for {project_id}/{document_id}")
                        return True
        except Exception as e:
            logger.warning(f"Idempotency check failed: {e}")
            # If check fails, proceed with processing to be safe

        return False

    @staticmethod
    async def process_document_insights(
        project_id: str,
        document_id: str,
        service_urls: Dict[str, str]
    ) -> Dict[str, Any]:
        """Main processing function for generating and storing lessons learned"""

        result = {
            "success": False,
            "project_id": project_id,
            "document_id": document_id,
            "insights_generated": 0,
            "error": None,
            "idempotent": False
        }

        try:
            # Step 0: Check idempotency
            lessons_url = service_urls.get("lessons_service", "http://localhost:8018")
            if await PostProcessingAgent.check_idempotency(project_id, document_id, lessons_url):
                result.update({
                    "success": True,
                    "idempotent": True,
                    "message": "Post-processing already completed"
                })
                return result

            # Step 1: Gather data from Knowledge Core
            logger.info(f"Gathering knowledge core data for project {project_id}, document {document_id}")
            knowledge_data = await PostProcessingAgent.gather_knowledge_core_data(
                project_id, document_id, service_urls
            )

            if not knowledge_data.get("kg_metrics") and not knowledge_data.get("document_topics"):
                logger.warning(f"Insufficient data for insights generation: {project_id}/{document_id}")
                result["error"] = "Insufficient knowledge core data"
                return result

            # Step 2: Generate insights with LLM
            logger.info("Generating insights with LLM")
            insights = await PostProcessingAgent.generate_insights_with_llm(
                knowledge_data, service_urls.get("llm_service", "http://localhost:8007")
            )

            if not insights.get("insights"):
                logger.warning("No insights generated by LLM")
                result["error"] = "No insights generated"
                return result

            # Step 3: Store insights
            logger.info("Storing insights in lessons service")
            stored = await PostProcessingAgent.store_insights_in_lessons_service(
                project_id, document_id, insights, lessons_url
            )

            result.update({
                "success": stored,
                "insights_generated": len(insights.get("insights", [])),
                "insights_summary": insights.get("summary", ""),
                "categories": list(set(
                    insight.get("category", "general")
                    for insight in insights.get("insights", [])
                ))
            })

        except httpx.TimeoutException as e:
            logger.error(f"Timeout error in post-processing: {e}")
            result["error"] = "Service timeout"
        except httpx.ConnectError as e:
            logger.error(f"Connection error in post-processing: {e}")
            result["error"] = "Service unavailable"
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error in post-processing: {e}")
            result["error"] = "Invalid response format"
        except Exception as e:
            logger.error(f"Unexpected error in post-processing: {e}")
            result["error"] = f"Processing failed: {str(e)}"

        return result
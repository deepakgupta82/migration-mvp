"""
Supervisor Agent - Level 3 Agentic Enhancement
Implements dynamic routing and intent-based workflow selection
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class SupervisorAgent:
    """
    Supervisor Agent for dynamic intent analysis and routing.
    
    This agent analyzes user queries to determine:
    1. Query complexity (simple fact vs. deep analysis)
    2. Required expertise domains
    3. Optimal workflow path
    
    Routes queries to:
    - Direct service calls (simple facts)
    - Mini-crews (focused analysis)
    - Full assessment crews (comprehensive evaluations)
    """
    
    def __init__(self, llm_service_client=None, project_id: Optional[str] = None):
        """
        Initialize Supervisor Agent
        
        Args:
            llm_service_client: Service client for LLM calls
            project_id: Project context for scoped operations
        """
        self.llm_service = llm_service_client
        self.project_id = project_id
        self.routing_history = []
        
    async def analyze_intent(
        self, 
        user_query: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze user query to determine intent and complexity.
        
        Args:
            user_query: The user's question or request
            context: Additional context (project metadata, previous queries, etc.)
            
        Returns:
            Dict with:
                - intent_type: simple_fact | focused_analysis | comprehensive_assessment
                - confidence: 0.0-1.0
                - required_domains: List of expertise areas needed
                - reasoning: Explanation of classification
        """
        logger.info(f"Analyzing intent for query: {user_query[:100]}...")
        
        try:
            # Build analysis prompt
            prompt = self._build_intent_analysis_prompt(user_query, context)
            
            # Call LLM service for intent classification
            if self.llm_service:
                analysis_result = await self._call_llm_for_intent(prompt)
            else:
                # Fallback to heuristic-based classification
                analysis_result = self._heuristic_intent_analysis(user_query)
            
            # Log routing decision
            self._log_routing_decision(user_query, analysis_result)
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"Intent analysis failed: {e}", exc_info=True)
            # Safe fallback: route to full assessment
            return {
                "intent_type": "comprehensive_assessment",
                "confidence": 0.5,
                "required_domains": ["migration_architect"],
                "reasoning": f"Fallback due to error: {str(e)}",
                "error": str(e)
            }
    
    def _build_intent_analysis_prompt(
        self, 
        user_query: str, 
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Build structured prompt for intent analysis"""
        
        prompt = f"""You are a Supervisor Agent analyzing user queries for a cloud migration platform.
Your task is to classify the query complexity and determine the optimal routing strategy.

User Query: "{user_query}"
"""
        
        if context:
            prompt += f"\nContext:\n{json.dumps(context, indent=2)}\n"
        
        prompt += """
Classification Guidelines:

1. **simple_fact** - Direct factual queries answerable from existing data
   Examples: "What OS is server X?", "List all databases", "Show application dependencies"
   Characteristics: Single entity lookup, no analysis required, clear answer in knowledge graph/vector store
   
2. **focused_analysis** - Requires analysis but limited scope
   Examples: "Security risks for app X", "Cost estimate for rehosting", "Dependencies for migration wave 1"
   Characteristics: 1-3 domain experts needed, specific scope, tactical decision
   
3. **comprehensive_assessment** - Complex strategic analysis
   Examples: "Generate migration plan", "Full risk assessment", "Architecture redesign recommendations"
   Characteristics: Multiple domains, strategic decisions, full crew collaboration needed

Required Domains (select relevant):
- migration_architect: Architecture, migration strategies, 6Rs
- devops_expert: CI/CD, automation, infrastructure
- security_expert: Security, compliance, risk
- cost_optimizer: Cost analysis, ROI, optimization
- data_expert: Databases, data migration, ETL
- app_modernization: Application refactoring, containerization

Return ONLY valid JSON:
{
  "intent_type": "simple_fact | focused_analysis | comprehensive_assessment",
  "confidence": 0.0-1.0,
  "required_domains": ["domain1", "domain2"],
  "reasoning": "Brief explanation of classification",
  "estimated_cost_tier": "low | medium | high",
  "estimated_response_time": "seconds | minutes | hours"
}
"""
        return prompt
    
    async def _call_llm_for_intent(self, prompt: str) -> Dict[str, Any]:
        """Call LLM service to analyze intent"""
        try:
            from services.shared.service_client import get_service_client
            
            client = await get_service_client()
            
            llm_payload = {
                "messages": [
                    {"role": "system", "content": "You are an expert query classifier. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                "project_id": self.project_id,
                "temperature": 0.1,  # Low temperature for consistent classification
                "max_tokens": 500,
                "process_type": "intent_analysis"
            }
            
            response = await client.post("llm", "/api/llm/chat/completions", json=llm_payload)
            
            # Extract JSON from response
            if isinstance(response, dict) and "choices" in response:
                content = response["choices"][0]["message"]["content"]
            else:
                content = str(response)
            
            # Parse JSON response
            # Handle markdown code blocks if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            result = json.loads(content)
            
            # Validate required fields
            required_fields = ["intent_type", "confidence", "required_domains", "reasoning"]
            if not all(field in result for field in required_fields):
                raise ValueError(f"LLM response missing required fields: {result}")
            
            # Validate intent_type
            valid_intents = ["simple_fact", "focused_analysis", "comprehensive_assessment"]
            if result["intent_type"] not in valid_intents:
                logger.warning(f"Invalid intent type: {result['intent_type']}, defaulting to focused_analysis")
                result["intent_type"] = "focused_analysis"
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON response: {e}")
            return self._heuristic_intent_analysis(prompt)
        except Exception as e:
            logger.error(f"LLM intent analysis failed: {e}")
            return self._heuristic_intent_analysis(prompt)
    
    def _heuristic_intent_analysis(self, user_query: str) -> Dict[str, Any]:
        """
        Fallback heuristic-based intent classification.
        Uses keyword matching and query patterns.
        """
        query_lower = user_query.lower()
        
        # Simple fact patterns
        simple_patterns = [
            "what is", "what os", "list all", "show me", "find server", 
            "get ", "which server", "how many", "count", "display", 
            "lookup", "what's the"
        ]
        
        # Comprehensive patterns
        comprehensive_patterns = [
            "generate", "create plan", "full assessment", "comprehensive",
            "analyze all", "migration strategy", "complete analysis",
            "architecture design", "end-to-end", "perform full", 
            "complete migration"
        ]
        
        # Domain keyword mapping
        domain_keywords = {
            "migration_architect": ["migration", "architecture", "strategy", "6r", "cloud"],
            "security_expert": ["security", "compliance", "risk", "encryption", "iam"],
            "cost_optimizer": ["cost", "pricing", "budget", "roi", "savings"],
            "devops_expert": ["cicd", "pipeline", "automation", "deployment", "container"],
            "data_expert": ["database", "data", "etl", "warehouse", "migration"],
            "app_modernization": ["application", "refactor", "microservice", "serverless"]
        }
        
        # Detect intent type
        if any(pattern in query_lower for pattern in simple_patterns):
            # Check if it's truly simple (single entity)
            if len(user_query.split()) < 10 and not any(p in query_lower for p in comprehensive_patterns):
                intent_type = "simple_fact"
                confidence = 0.8
            else:
                intent_type = "focused_analysis"
                confidence = 0.7
        elif any(pattern in query_lower for pattern in comprehensive_patterns):
            intent_type = "comprehensive_assessment"
            confidence = 0.85
        else:
            # Default to focused analysis
            intent_type = "focused_analysis"
            confidence = 0.6
        
        # Determine required domains
        required_domains = []
        for domain, keywords in domain_keywords.items():
            if any(keyword in query_lower for keyword in keywords):
                required_domains.append(domain)
        
        # If no domains detected, add migration_architect as default
        if not required_domains:
            required_domains = ["migration_architect"]
        
        return {
            "intent_type": intent_type,
            "confidence": confidence,
            "required_domains": required_domains[:3],  # Limit to 3 domains
            "reasoning": f"Heuristic classification based on query patterns",
            "method": "heuristic_fallback",
            "estimated_cost_tier": "low" if intent_type == "simple_fact" else "medium" if intent_type == "focused_analysis" else "high",
            "estimated_response_time": "seconds" if intent_type == "simple_fact" else "minutes" if intent_type == "focused_analysis" else "hours"
        }
    
    async def route_query(
        self,
        user_query: str,
        intent_analysis: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Route query to appropriate execution path based on intent analysis.
        
        Args:
            user_query: Original user query
            intent_analysis: Result from analyze_intent()
            context: Additional context
            
        Returns:
            Dict with routing decision and execution metadata
        """
        intent_type = intent_analysis["intent_type"]
        required_domains = intent_analysis["required_domains"]
        
        logger.info(f"Routing query as {intent_type} with domains: {required_domains}")
        
        routing_decision = {
            "query": user_query,
            "intent_type": intent_type,
            "execution_path": None,
            "agents_selected": [],
            "tools_recommended": [],
            "estimated_duration": None,
            "cost_tier": intent_analysis.get("estimated_cost_tier", "medium"),
            "reasoning": intent_analysis.get("reasoning", ""),
            "timestamp": datetime.now().isoformat()
        }
        
        if intent_type == "simple_fact":
            routing_decision.update({
                "execution_path": "direct_service_call",
                "service": self._select_direct_service(user_query),
                "agents_selected": [],
                "tools_recommended": ["graph_query", "vector_search"],
                "estimated_duration": "1-5 seconds"
            })
            
        elif intent_type == "focused_analysis":
            routing_decision.update({
                "execution_path": "mini_crew",
                "agents_selected": required_domains[:2],  # Limit to 2 agents for efficiency
                "tools_recommended": ["hybrid_search", "graph_query", "rag_query"],
                "estimated_duration": "30-120 seconds"
            })
            
        else:  # comprehensive_assessment
            routing_decision.update({
                "execution_path": "full_assessment_crew",
                "agents_selected": [
                    "engagement_analyst",
                    "principal_cloud_architect",
                    "risk_compliance_officer",
                    "lead_planning_manager"
                ],
                "tools_recommended": [
                    "hybrid_search", "graph_query", "rag_query",
                    "cloud_catalog", "compliance_framework", "lessons_learned"
                ],
                "estimated_duration": "5-15 minutes"
            })
        
        return routing_decision
    
    def _select_direct_service(self, query: str) -> str:
        """Determine which service to call directly for simple facts"""
        query_lower = query.lower()
        
        if any(word in query_lower for word in ["server", "application", "dependency", "relationship"]):
            return "graph_service"
        elif any(word in query_lower for word in ["document", "search", "find", "content"]):
            return "vector_service"
        elif any(word in query_lower for word in ["project", "deliverable", "template"]):
            return "project_service"
        else:
            return "knowledge_service"  # Default
    
    def _log_routing_decision(self, query: str, analysis: Dict[str, Any]):
        """Log routing decision for analytics and learning"""
        self.routing_history.append({
            "timestamp": datetime.now().isoformat(),
            "query": query[:200],  # Truncate for storage
            "intent_type": analysis.get("intent_type"),
            "confidence": analysis.get("confidence"),
            "domains": analysis.get("required_domains", [])
        })
        
        # Keep only last 100 decisions in memory
        if len(self.routing_history) > 100:
            self.routing_history = self.routing_history[-100:]
    
    def get_routing_statistics(self) -> Dict[str, Any]:
        """Get statistics about routing decisions for monitoring"""
        if not self.routing_history:
            return {
                "total_queries": 0,
                "intent_distribution": {},
                "average_confidence": 0.0
            }
        
        intent_counts = {}
        total_confidence = 0.0
        
        for decision in self.routing_history:
            intent = decision.get("intent_type", "unknown")
            intent_counts[intent] = intent_counts.get(intent, 0) + 1
            total_confidence += decision.get("confidence", 0.0)
        
        return {
            "total_queries": len(self.routing_history),
            "intent_distribution": intent_counts,
            "average_confidence": total_confidence / len(self.routing_history),
            "last_updated": datetime.now().isoformat()
        }


# Singleton instance
_supervisor_instance: Optional[SupervisorAgent] = None


def get_supervisor(
    llm_service_client=None, 
    project_id: Optional[str] = None
) -> SupervisorAgent:
    """Get or create supervisor agent singleton"""
    global _supervisor_instance
    
    if _supervisor_instance is None:
        _supervisor_instance = SupervisorAgent(llm_service_client, project_id)
    
    return _supervisor_instance


def reset_supervisor():
    """Reset supervisor instance (for testing)"""
    global _supervisor_instance
    _supervisor_instance = None

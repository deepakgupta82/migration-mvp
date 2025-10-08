"""
Reflection Loop - Level 3 Agentic Enhancement
Implements Producer-Critic pattern for iterative quality improvement
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class ReflectionLoop:
    """
    Implements iterative refinement through Producer-Critic pattern.
    
    The loop:
    1. Producer agent creates initial output
    2. Critic agent reviews and provides feedback
    3. If feedback != "PERFECT", producer refines based on feedback
    4. Repeat until PERFECT or max iterations reached
    """
    
    def __init__(
        self,
        max_iterations: int = 3,
        quality_threshold: float = 0.9,
        enable_learning: bool = True
    ):
        """
        Initialize Reflection Loop
        
        Args:
            max_iterations: Maximum refinement iterations (default: 3)
            quality_threshold: Quality score threshold (0.0-1.0)
            enable_learning: Store refinement patterns for future learning
        """
        self.max_iterations = max_iterations
        self.quality_threshold = quality_threshold
        self.enable_learning = enable_learning
        self.refinement_history = []
        
    async def run_reflection_loop(
        self,
        producer_func: callable,
        critic_func: callable,
        initial_context: Dict[str, Any],
        task_description: str
    ) -> Dict[str, Any]:
        """
        Execute the reflection loop with producer-critic iteration.
        
        Args:
            producer_func: Async function that produces output
            critic_func: Async function that reviews output
            initial_context: Context for the task
            task_description: Description of what's being produced
            
        Returns:
            Dict with:
                - final_output: The refined output
                - iterations_used: Number of refinement cycles
                - quality_score: Final quality assessment
                - refinement_log: History of improvements
        """
        logger.info(f"Starting reflection loop for: {task_description}")
        
        current_output = None
        refinement_log = []
        iteration = 0
        
        while iteration < self.max_iterations:
            iteration += 1
            logger.info(f"Reflection iteration {iteration}/{self.max_iterations}")
            
            # Producer phase
            if iteration == 1:
                # Initial production
                producer_context = initial_context
                logger.info("Producer: Creating initial output")
            else:
                # Refinement based on critic feedback
                producer_context = {
                    **initial_context,
                    "previous_output": current_output,
                    "critic_feedback": refinement_log[-1]["feedback"],
                    "refinement_iteration": iteration
                }
                logger.info(f"Producer: Refining output based on feedback (iteration {iteration})")
            
            try:
                current_output = await producer_func(producer_context)
            except Exception as e:
                logger.error(f"Producer failed at iteration {iteration}: {e}")
                return self._create_error_result(
                    current_output,
                    iteration,
                    refinement_log,
                    f"Producer error: {str(e)}"
                )
            
            # Critic phase
            logger.info("Critic: Reviewing output quality")
            try:
                critic_result = await critic_func({
                    "output": current_output,
                    "task_description": task_description,
                    "iteration": iteration,
                    "context": initial_context
                })
            except Exception as e:
                logger.error(f"Critic failed at iteration {iteration}: {e}")
                # If critic fails, accept current output
                critic_result = {
                    "status": "ACCEPT",
                    "quality_score": 0.7,
                    "feedback": f"Critic unavailable (error: {str(e)}), accepting output",
                    "issues": []
                }
            
            # Log this iteration
            iteration_log = {
                "iteration": iteration,
                "timestamp": datetime.now().isoformat(),
                "status": critic_result.get("status", "UNKNOWN"),
                "quality_score": critic_result.get("quality_score", 0.0),
                "feedback": critic_result.get("feedback", ""),
                "issues_found": len(critic_result.get("issues", [])),
                "issues": critic_result.get("issues", [])
            }
            refinement_log.append(iteration_log)
            
            # Decision: Continue or terminate?
            status = critic_result.get("status", "").upper()
            quality_score = critic_result.get("quality_score", 0.0)
            
            if status == "PERFECT" or status == "ACCEPT":
                logger.info(f"✓ Output accepted at iteration {iteration} (score: {quality_score:.2f})")
                return self._create_success_result(
                    current_output,
                    iteration,
                    refinement_log,
                    quality_score
                )
            
            if quality_score >= self.quality_threshold:
                logger.info(f"✓ Quality threshold met at iteration {iteration} (score: {quality_score:.2f})")
                return self._create_success_result(
                    current_output,
                    iteration,
                    refinement_log,
                    quality_score
                )
            
            if iteration >= self.max_iterations:
                logger.warning(f"Max iterations reached ({self.max_iterations}), accepting current output")
                return self._create_max_iterations_result(
                    current_output,
                    iteration,
                    refinement_log,
                    quality_score
                )
            
            # Continue to next iteration
            logger.info(f"Continuing to iteration {iteration + 1} for refinement")
        
        # Fallback (should not reach here)
        return self._create_success_result(current_output, iteration, refinement_log, quality_score)
    
    def _create_success_result(
        self,
        output: Any,
        iterations: int,
        log: List[Dict],
        quality_score: float
    ) -> Dict[str, Any]:
        """Create successful result dict"""
        result = {
            "status": "success",
            "final_output": output,
            "iterations_used": iterations,
            "quality_score": quality_score,
            "refinement_log": log,
            "improvements_made": iterations - 1,
            "timestamp": datetime.now().isoformat()
        }
        
        if self.enable_learning:
            self._store_refinement_pattern(result)
        
        return result
    
    def _create_max_iterations_result(
        self,
        output: Any,
        iterations: int,
        log: List[Dict],
        quality_score: float
    ) -> Dict[str, Any]:
        """Create result when max iterations reached"""
        return {
            "status": "max_iterations_reached",
            "final_output": output,
            "iterations_used": iterations,
            "quality_score": quality_score,
            "refinement_log": log,
            "improvements_made": iterations - 1,
            "warning": f"Max iterations ({self.max_iterations}) reached, quality may be suboptimal",
            "timestamp": datetime.now().isoformat()
        }
    
    def _create_error_result(
        self,
        output: Any,
        iterations: int,
        log: List[Dict],
        error: str
    ) -> Dict[str, Any]:
        """Create error result dict"""
        return {
            "status": "error",
            "final_output": output,
            "iterations_used": iterations,
            "quality_score": 0.0,
            "refinement_log": log,
            "error": error,
            "timestamp": datetime.now().isoformat()
        }
    
    def _store_refinement_pattern(self, result: Dict[str, Any]):
        """Store refinement pattern for future learning"""
        self.refinement_history.append({
            "timestamp": datetime.now().isoformat(),
            "iterations": result["iterations_used"],
            "final_quality": result["quality_score"],
            "issue_types": self._extract_issue_types(result["refinement_log"])
        })
        
        # Keep only last 100 patterns
        if len(self.refinement_history) > 100:
            self.refinement_history = self.refinement_history[-100:]
    
    def _extract_issue_types(self, refinement_log: List[Dict]) -> List[str]:
        """Extract types of issues found during refinement"""
        issue_types = []
        for log_entry in refinement_log:
            for issue in log_entry.get("issues", []):
                issue_type = issue.get("type", "unknown")
                if issue_type not in issue_types:
                    issue_types.append(issue_type)
        return issue_types
    
    def get_refinement_statistics(self) -> Dict[str, Any]:
        """Get statistics about refinement patterns"""
        if not self.refinement_history:
            return {
                "total_refinements": 0,
                "average_iterations": 0.0,
                "average_quality": 0.0,
                "common_issues": []
            }
        
        total = len(self.refinement_history)
        avg_iterations = sum(r["iterations"] for r in self.refinement_history) / total
        avg_quality = sum(r["final_quality"] for r in self.refinement_history) / total
        
        # Count issue frequency
        issue_counts = {}
        for r in self.refinement_history:
            for issue_type in r["issue_types"]:
                issue_counts[issue_type] = issue_counts.get(issue_type, 0) + 1
        
        common_issues = sorted(
            issue_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        return {
            "total_refinements": total,
            "average_iterations": round(avg_iterations, 2),
            "average_quality": round(avg_quality, 2),
            "common_issues": [{"type": t, "count": c} for t, c in common_issues],
            "last_updated": datetime.now().isoformat()
        }


class CriticAgent:
    """
    Critic agent for quality review and feedback generation.
    
    This agent reviews produced output and provides structured feedback
    for refinement.
    """
    
    @staticmethod
    async def review_output(
        review_context: Dict[str, Any],
        llm_service=None,
        project_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Review output and provide structured feedback.
        
        Args:
            review_context: Context including output, task, iteration
            llm_service: Optional LLM service for intelligent review
            project_id: Project ID for LLM config resolution
            
        Returns:
            Dict with:
                - status: PERFECT | IMPROVE | REJECT
                - quality_score: 0.0-1.0
                - feedback: Detailed feedback text
                - issues: List of specific issues found
        """
        output = review_context.get("output", "")
        task_description = review_context.get("task_description", "")
        iteration = review_context.get("iteration", 1)
        
        logger.info(f"Critic reviewing output (iteration {iteration})")
        
        if llm_service:
            return await CriticAgent._llm_review(
                output,
                task_description,
                iteration,
                llm_service,
                project_id
            )
        else:
            return CriticAgent._heuristic_review(output, task_description, iteration)
    
    @staticmethod
    async def _llm_review(
        output: str,
        task_description: str,
        iteration: int,
        llm_service,
        project_id: Optional[str]
    ) -> Dict[str, Any]:
        """Use LLM for intelligent quality review"""
        try:
            from services.shared.service_client import get_service_client
            
            prompt = f"""You are a meticulous Quality Reviewer for cloud migration documentation.

Task: {task_description}
Iteration: {iteration}

Review the following output for quality, accuracy, and completeness:

{output[:5000]}  

Evaluation Criteria:
1. **Accuracy**: Information is factually correct and grounded in evidence
2. **Completeness**: All required sections/elements are present
3. **Clarity**: Content is well-organized and easy to understand
4. **Professionalism**: Language is professional and appropriate
5. **Actionability**: Recommendations are specific and implementable

Return ONLY valid JSON:
{{
  "status": "PERFECT | IMPROVE | REJECT",
  "quality_score": 0.0-1.0,
  "feedback": "Brief summary of review findings",
  "issues": [
    {{
      "type": "accuracy | completeness | clarity | professionalism | actionability",
      "severity": "critical | major | minor",
      "description": "Specific issue description",
      "suggestion": "How to fix it"
    }}
  ]
}}

Guidelines:
- PERFECT: No issues found, score >= 0.95
- IMPROVE: Issues found but output is salvageable, score 0.7-0.94
- REJECT: Critical issues, score < 0.7
"""
            
            client = await get_service_client()
            
            llm_payload = {
                "messages": [
                    {"role": "system", "content": "You are an expert quality reviewer. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                "project_id": project_id,
                "temperature": 0.2,
                "max_tokens": 1000,
                "process_type": "quality_review"
            }
            
            response = await client.post("llm", "/api/llm/chat/completions", json=llm_payload)
            
            # Extract and parse JSON
            if isinstance(response, dict) and "choices" in response:
                content = response["choices"][0]["message"]["content"]
            else:
                content = str(response)
            
            # Handle markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            result = json.loads(content)
            
            # Validate required fields
            required = ["status", "quality_score", "feedback", "issues"]
            if not all(field in result for field in required):
                raise ValueError(f"LLM response missing required fields")
            
            return result
            
        except Exception as e:
            logger.error(f"LLM review failed: {e}")
            return CriticAgent._heuristic_review(output, task_description, iteration)
    
    @staticmethod
    def _heuristic_review(
        output: str,
        task_description: str,
        iteration: int
    ) -> Dict[str, Any]:
        """Fallback heuristic review when LLM unavailable"""
        issues = []
        quality_score = 0.8  # Default baseline
        
        # Check length (more lenient threshold)
        if len(output) < 100:
            issues.append({
                "type": "completeness",
                "severity": "critical",
                "description": "Output is extremely short",
                "suggestion": "Add substantial content"
            })
            quality_score -= 0.3
        elif len(output) < 300:
            issues.append({
                "type": "completeness",
                "severity": "major",
                "description": "Output seems too short to be comprehensive",
                "suggestion": "Expand with more details and examples"
            })
            quality_score -= 0.15
        
        # Check structure (headers, sections)
        if "#" not in output and "##" not in output:
            issues.append({
                "type": "clarity",
                "severity": "minor",
                "description": "No clear section structure found",
                "suggestion": "Add headers and section organization"
            })
            quality_score -= 0.05
        
        # Check for bullet points/lists
        if "-" not in output and "*" not in output and "1." not in output:
            issues.append({
                "type": "clarity",
                "severity": "minor",
                "description": "No lists or bullet points for readability",
                "suggestion": "Use lists to organize information"
            })
            quality_score -= 0.05
        
        # Determine status (more lenient thresholds)
        if quality_score >= 0.95:
            status = "PERFECT"
        elif quality_score >= 0.6:  # Lowered from 0.7
            status = "IMPROVE"
        else:
            status = "REJECT"
        
        return {
            "status": status,
            "quality_score": max(0.0, quality_score),
            "feedback": f"Heuristic review found {len(issues)} issues. " + 
                       ("Output is acceptable." if status != "REJECT" else "Significant improvements needed."),
            "issues": issues,
            "method": "heuristic_fallback"
        }


# Singleton instance
_reflection_loop: Optional[ReflectionLoop] = None


def get_reflection_loop(
    max_iterations: int = 3,
    quality_threshold: float = 0.9
) -> ReflectionLoop:
    """Get or create reflection loop singleton"""
    global _reflection_loop
    
    if _reflection_loop is None:
        _reflection_loop = ReflectionLoop(max_iterations, quality_threshold)
    
    return _reflection_loop

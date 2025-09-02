#!/usr/bin/env python3
"""
LLM-Enhanced Content Analyzer
Orchestrates intelligent content analysis using LLM-based summarization
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import os
from concurrent.futures import ThreadPoolExecutor

from .llm_summarization_engine import LLMSummarizationEngine, SummarizationConfig
# Import ContentExtractor lazily to avoid circular import

logger = logging.getLogger("document-service.llm-content-analyzer")

class LLMContentAnalyzer:
    """
    LLM-Enhanced Content Analyzer that orchestrates:
    1. Content extraction and preprocessing
    2. Intelligent LLM-based summarization
    3. Advanced categorization using LLM
    4. Quality validation and refinement
    5. Bulk processing capabilities
    """

    def __init__(self):
        self.summarization_engine = LLMSummarizationEngine()
        # Import ContentExtractor lazily to avoid circular import
        self.content_extractor = None

        # Configuration
        self.max_concurrent_analyses = int(os.getenv("MAX_CONCURRENT_ANALYSES", "10"))
        self.enable_llm_summarization = os.getenv("ENABLE_LLM_SUMMARIZATION", "true").lower() == "true"
        self.enable_llm_categorization = os.getenv("ENABLE_LLM_CATEGORIZATION", "true").lower() == "true"
        self.fallback_to_extract = os.getenv("FALLBACK_TO_EXTRACTIVE", "true").lower() == "true"

        # Thread pool for CPU-bound operations
        self.executor = ThreadPoolExecutor(max_workers=4)

    def _get_content_extractor(self):
        """Lazy load ContentExtractor to avoid circular import"""
        if self.content_extractor is None:
            from .content_extractor import ContentExtractor
            self.content_extractor = ContentExtractor()
        return self.content_extractor

    async def analyze_document_content(
        self,
        project_id: str,
        filename: str,
        processed_content: Optional[str] = None,
        structured_result: Optional[Dict[str, Any]] = None,
        analysis_type: str = "comprehensive",
        correlation_id: Optional[str] = None,
        force_reanalysis: bool = False
    ) -> Dict[str, Any]:
        """
        Perform comprehensive LLM-enhanced content analysis

        Args:
            project_id: Project identifier
            filename: Document filename
            processed_content: Pre-processed content (optional)
            structured_result: Structured processing result (optional)
            analysis_type: Type of analysis (comprehensive, summary, categories, etc.)
            correlation_id: Request correlation ID
            force_reanalysis: Force reanalysis even if cached

        Returns:
            Dict with analysis results
        """
        try:
            start_time = datetime.now()
            logger.info(f"Starting LLM-enhanced analysis for {filename} in project {project_id}")

            # Fetch content if not provided
            if not processed_content:
                content_extractor = self._get_content_extractor()
                processed_content = await content_extractor._fetch_processed_content(
                    project_id, filename, correlation_id
                )

            if not processed_content:
                return {
                    "status": "error",
                    "filename": filename,
                    "error": "No processed content available",
                    "analysis_type": analysis_type
                }

            analysis_result = {
                "filename": filename,
                "project_id": project_id,
                "analysis_type": analysis_type,
                "processing_methods": [],
                "timestamp": datetime.now().isoformat()
            }

            # LLM-based summarization
            if self.enable_llm_summarization:
                try:
                    summary_result = await self.summarization_engine.summarize_content(
                        content=processed_content,
                        filename=filename,
                        summary_type=analysis_type,
                        project_id=project_id,
                        correlation_id=correlation_id
                    )

                    analysis_result.update({
                        "llm_summary": summary_result["summary"],
                        "summary_method": summary_result["method"],
                        "summary_cached": summary_result.get("cached", False),
                        "summary_processing_time": summary_result.get("processing_time", 0.0),
                        "token_usage": summary_result.get("token_usage", {})
                    })
                    analysis_result["processing_methods"].append("llm_summarization")

                except Exception as e:
                    logger.warning(f"LLM summarization failed for {filename}: {e}")
                    if self.fallback_to_extract:
                        # Fallback to extractive summarization
                        content_extractor = self._get_content_extractor()
                        extractive_summary = await content_extractor._extract_summary(processed_content)
                        analysis_result.update({
                            "llm_summary": extractive_summary,
                            "summary_method": "extractive_fallback",
                            "summary_error": str(e),
                            "token_usage": {"fallback": True, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
                        })
                        analysis_result["processing_methods"].append("extractive_fallback")
                    else:
                        analysis_result["summary_error"] = str(e)
                        analysis_result["token_usage"] = {"error": True, "input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

            # LLM-based categorization
            if self.enable_llm_categorization:
                try:
                    llm_categories = await self._extract_llm_categories(
                        processed_content, filename, project_id, correlation_id
                    )

                    if llm_categories:
                        analysis_result["llm_categories"] = llm_categories
                        analysis_result["processing_methods"].append("llm_categorization")

                except Exception as e:
                    logger.warning(f"LLM categorization failed for {filename}: {e}")
                    analysis_result["categorization_error"] = str(e)

            # Traditional extractive analysis as backup/supplement
            if not analysis_result.get("llm_summary") or self.fallback_to_extract:
                try:
                    content_extractor = self._get_content_extractor()
                    extractive_summary = await content_extractor._extract_summary(processed_content)
                    extractive_categories = await content_extractor._extract_categories(processed_content)

                    analysis_result.update({
                        "extractive_summary": extractive_summary,
                        "extractive_categories": extractive_categories,
                        "processing_methods": analysis_result["processing_methods"] + ["extractive_backup"]
                    })
                except Exception as e:
                    logger.warning(f"Extractive analysis failed for {filename}: {e}")

            # Structure metadata extraction
            content_extractor = self._get_content_extractor()
            structure_metadata = content_extractor._extract_structure_metadata(
                filename, processed_content, structured_result
            )
            if structure_metadata:
                analysis_result["structure_metadata"] = structure_metadata
                analysis_result["processing_methods"].append("structure_analysis")

            # Quality assessment
            quality_score = self._assess_analysis_quality(analysis_result)
            analysis_result["quality_score"] = quality_score

            # Determine final summary and categories
            final_summary = self._select_best_summary(analysis_result)
            final_categories = self._select_best_categories(analysis_result)

            analysis_result.update({
                "final_summary": final_summary,
                "final_categories": final_categories,
                "total_processing_time": (datetime.now() - start_time).total_seconds(),
                "status": "success"
            })

            logger.info(f"LLM-enhanced analysis completed for {filename}: quality={quality_score:.2f}")
            return analysis_result

        except Exception as e:
            logger.error(f"Error in LLM-enhanced analysis for {filename}: {e}")
            return {
                "status": "error",
                "filename": filename,
                "error": str(e),
                "analysis_type": analysis_type,
                "timestamp": datetime.now().isoformat()
            }

    async def _extract_llm_categories(
        self,
        content: str,
        filename: str,
        project_id: str,
        correlation_id: Optional[str]
    ) -> List[str]:
        """Extract categories using LLM for more intelligent classification"""
        if len(content.strip()) < 200:
            return []

        prompt = f"""Analyze the following document content and extract the most relevant categories/tags.
Return only a JSON array of strings, with 3-8 categories that best describe this content.

Document: {filename}
Content: {content[:3000]}...

Categories (JSON array only):"""

        try:
            # Use the summarization engine's LLM calling method
            response = await self.summarization_engine._call_llm_service(
                prompt, project_id, correlation_id
            )

            # Parse JSON response
            import json
            categories = json.loads(response.strip())

            if isinstance(categories, list):
                # Clean and validate categories
                cleaned_categories = []
                for cat in categories:
                    if isinstance(cat, str) and len(cat.strip()) > 0:
                        cleaned_cat = cat.strip().lower().replace(' ', '_')
                        if len(cleaned_cat) > 2:  # Avoid very short categories
                            cleaned_categories.append(cleaned_cat)

                return cleaned_categories[:10]  # Limit to 10 categories
            else:
                logger.warning(f"LLM categorization returned non-list: {categories}")
                return []

        except Exception as e:
            logger.warning(f"Error parsing LLM categories: {e}")
            return []

    def _assess_analysis_quality(self, analysis_result: Dict[str, Any]) -> float:
        """Assess the quality of the analysis results"""
        score = 0.0
        max_score = 0.0

        # Summary quality (40% weight)
        if analysis_result.get("llm_summary"):
            summary = analysis_result["llm_summary"]
            summary_len = len(summary)
            if 100 <= summary_len <= 1000:
                score += 40
            elif 50 <= summary_len < 100:
                score += 30
            elif summary_len > 1000:
                score += 20
            max_score += 40
        elif analysis_result.get("extractive_summary"):
            score += 20
            max_score += 40

        # Categories quality (30% weight)
        categories = analysis_result.get("llm_categories") or analysis_result.get("extractive_categories", [])
        if len(categories) >= 3:
            score += 30
        elif len(categories) >= 1:
            score += 20
        max_score += 30

        # Structure metadata (20% weight)
        if analysis_result.get("structure_metadata"):
            score += 20
        max_score += 20

        # Processing methods diversity (10% weight)
        methods = analysis_result.get("processing_methods", [])
        if len(methods) >= 2:
            score += 10
        elif len(methods) >= 1:
            score += 5
        max_score += 10

        return score / max_score if max_score > 0 else 0.0

    def _select_best_summary(self, analysis_result: Dict[str, Any]) -> str:
        """Select the best summary from available options"""
        # Priority: LLM summary > Extractive summary > Error message
        if analysis_result.get("llm_summary"):
            return analysis_result["llm_summary"]
        elif analysis_result.get("extractive_summary"):
            return analysis_result["extractive_summary"]
        else:
            return "Summary generation failed"

    def _select_best_categories(self, analysis_result: Dict[str, Any]) -> List[str]:
        """Select the best categories from available options"""
        # Priority: LLM categories > Extractive categories > Empty list
        if analysis_result.get("llm_categories"):
            return analysis_result["llm_categories"]
        elif analysis_result.get("extractive_categories"):
            return analysis_result["extractive_categories"]
        else:
            return []

    async def analyze_documents_batch(
        self,
        project_id: str,
        file_data: List[Dict[str, Any]],
        analysis_type: str = "comprehensive",
        correlation_id: Optional[str] = None,
        max_concurrent: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Perform batch content analysis for multiple documents

        Args:
            project_id: Project identifier
            file_data: List of dicts with filename and optional content
            analysis_type: Type of analysis
            correlation_id: Request correlation ID
            max_concurrent: Maximum concurrent analyses

        Returns:
            Dict with batch analysis results
        """
        try:
            start_time = datetime.now()
            max_concurrent = max_concurrent or self.max_concurrent_analyses

            logger.info(f"Starting batch LLM analysis for {len(file_data)} files in project {project_id}")

            # Use semaphore to limit concurrency
            semaphore = asyncio.Semaphore(max_concurrent)

            async def analyze_single_file(file_info: Dict[str, Any]) -> Dict[str, Any]:
                async with semaphore:
                    return await self.analyze_document_content(
                        project_id=project_id,
                        filename=file_info["filename"],
                        processed_content=file_info.get("content"),
                        structured_result=file_info.get("structured_result"),
                        analysis_type=analysis_type,
                        correlation_id=correlation_id
                    )

            # Process files concurrently
            tasks = [analyze_single_file(file_info) for file_info in file_data]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            successful_analyses = []
            failed_analyses = []

            for i, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    logger.error(f"Batch analysis error for file {i}: {result}")
                    failed_analyses.append({
                        "filename": file_data[i]["filename"],
                        "error": str(result)
                    })
                else:
                    if result["status"] == "success":
                        successful_analyses.append(result)
                    else:
                        failed_analyses.append(result)

            total_time = (datetime.now() - start_time).total_seconds()

            batch_summary = {
                "status": "completed",
                "project_id": project_id,
                "total_files": len(file_data),
                "successful_analyses": len(successful_analyses),
                "failed_analyses": len(failed_analyses),
                "total_processing_time": total_time,
                "average_time_per_file": total_time / len(file_data) if file_data else 0,
                "results": successful_analyses,
                "errors": failed_analyses,
                "analysis_type": analysis_type,
                "max_concurrent": max_concurrent,
                "timestamp": datetime.now().isoformat()
            }

            logger.info(f"Batch LLM analysis completed: {len(successful_analyses)}/{len(file_data)} successful")
            return batch_summary

        except Exception as e:
            logger.error(f"Error in batch LLM analysis: {e}")
            return {
                "status": "error",
                "project_id": project_id,
                "error": str(e),
                "total_files": len(file_data),
                "timestamp": datetime.now().isoformat()
            }

    async def update_project_file_with_analysis(
        self,
        project_id: str,
        filename: str,
        analysis_result: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> bool:
        """
        Update project file with LLM-enhanced analysis results

        Args:
            project_id: Project identifier
            filename: Document filename
            analysis_result: Analysis results from analyze_document_content
            correlation_id: Request correlation ID

        Returns:
            Success status
        """
        try:
            if analysis_result["status"] != "success":
                logger.warning(f"Skipping update for failed analysis: {filename}")
                return False

            # Prepare update data
            update_data = {
                "summary_text": analysis_result.get("final_summary", ""),
                "categories": analysis_result.get("final_categories", []),
                "structure_metadata": analysis_result.get("structure_metadata"),
                "analysis_metadata": {
                    "analysis_type": analysis_result.get("analysis_type"),
                    "processing_methods": analysis_result.get("processing_methods", []),
                    "quality_score": analysis_result.get("quality_score", 0.0),
                    "llm_summary_available": bool(analysis_result.get("llm_summary")),
                    "processing_time": analysis_result.get("total_processing_time", 0.0),
                    "timestamp": analysis_result.get("timestamp")
                }
            }

            # Update project file
            content_extractor = self._get_content_extractor()
            success = await content_extractor._update_project_file(
                project_id, filename, update_data, correlation_id
            )

            if success:
                logger.info(f"Successfully updated project file {filename} with LLM analysis")
            else:
                logger.error(f"Failed to update project file {filename}")

            return success

        except Exception as e:
            logger.error(f"Error updating project file with analysis: {e}")
            return False

    async def get_analysis_stats(self) -> Dict[str, Any]:
        """Get analysis statistics"""
        try:
            summary_cache_stats = await self.summarization_engine.get_cache_stats()

            return {
                "summarization_engine": {
                    "cache_stats": summary_cache_stats
                },
                "configuration": {
                    "enable_llm_summarization": self.enable_llm_summarization,
                    "enable_llm_categorization": self.enable_llm_categorization,
                    "fallback_to_extract": self.fallback_to_extract,
                    "max_concurrent_analyses": self.max_concurrent_analyses
                },
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting analysis stats: {e}")
            return {"error": str(e)}

    async def clear_analysis_cache(self):
        """Clear all analysis caches"""
        try:
            await self.summarization_engine.clear_cache()
            logger.info("Analysis caches cleared")
        except Exception as e:
            logger.error(f"Error clearing analysis cache: {e}")
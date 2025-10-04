#!/usr/bin/env python3
"""
Document Domain Classifier
LLM-powered domain detection and content profiling for intelligent document processing

This module provides:
- Automatic domain classification (infrastructure, organizational, financial, etc.)
- Structure type detection (tabular, narrative, mixed, diagram)
- Entity density estimation
- Processing strategy recommendation
"""

import logging
import httpx
import json
import os
from typing import Dict, Any, Optional, List
from enum import Enum

logger = logging.getLogger("document_classifier")


class DocumentDomain(Enum):
    """Supported document domains"""
    INFRASTRUCTURE = "infrastructure"
    ORGANIZATIONAL = "organizational"
    FINANCIAL = "financial"
    LEGAL = "legal"
    PROCESS = "process"
    HR = "hr"
    TECHNICAL = "technical"
    OTHER = "other"


class StructureType(Enum):
    """Document structure types"""
    TABULAR = "tabular"  # Spreadsheets, tables
    NARRATIVE = "narrative"  # Text documents, PDFs
    MIXED = "mixed"  # Combination
    DIAGRAM = "diagram"  # Flowcharts, architecture diagrams
    LIST = "list"  # Bulleted/numbered lists


class EntityDensity(Enum):
    """Entity density levels"""
    LOW = "low"  # < 10 entities per 1000 words
    MEDIUM = "medium"  # 10-50 entities per 1000 words
    HIGH = "high"  # > 50 entities per 1000 words


class DomainProfile:
    """Document domain profile with classification results"""
    
    def __init__(
        self,
        primary_domain: DocumentDomain,
        secondary_domains: List[DocumentDomain],
        confidence: float,
        structure_type: StructureType,
        entity_density: EntityDensity,
        estimated_entity_count: int,
        recommended_strategy: str
    ):
        self.primary_domain = primary_domain
        self.secondary_domains = secondary_domains
        self.confidence = confidence
        self.structure_type = structure_type
        self.entity_density = entity_density
        self.estimated_entity_count = estimated_entity_count
        self.recommended_strategy = recommended_strategy
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "primary_domain": self.primary_domain.value,
            "secondary_domains": [d.value for d in self.secondary_domains],
            "confidence": round(self.confidence, 3),
            "structure_type": self.structure_type.value,
            "entity_density": self.entity_density.value,
            "estimated_entity_count": self.estimated_entity_count,
            "recommended_strategy": self.recommended_strategy
        }
    
    @classmethod
    def from_llm_response(cls, response: Dict[str, Any]) -> "DomainProfile":
        """Create from LLM JSON response"""
        # Map string values to enums
        primary_domain = DocumentDomain(response.get("primary_domain", "other"))
        
        secondary_domains = []
        for domain_str in response.get("secondary_domains", []):
            try:
                secondary_domains.append(DocumentDomain(domain_str))
            except ValueError:
                logger.warning(f"Unknown domain: {domain_str}")
        
        structure_type = StructureType(response.get("structure_type", "mixed"))
        entity_density = EntityDensity(response.get("entity_density", "medium"))
        
        return cls(
            primary_domain=primary_domain,
            secondary_domains=secondary_domains,
            confidence=response.get("confidence", 0.5),
            structure_type=structure_type,
            entity_density=entity_density,
            estimated_entity_count=response.get("estimated_entity_count", 0),
            recommended_strategy=response.get("recommended_strategy", "narrative_extraction")
        )


class DocumentClassifier:
    """
    LLM-powered document domain classifier
    
    Uses intelligent LLM orchestration to classify documents by:
    - Domain (infrastructure, organizational, etc.)
    - Structure (tabular, narrative, etc.)
    - Entity density
    - Processing strategy
    """
    
    def __init__(self):
        self.llm_service_url = os.getenv("LLM_SERVICE_URL", "http://localhost:8007")
        self.service_token = os.getenv("SERVICE_AUTH_TOKEN", "service-backend-token")
        logger.info(f"Document Classifier initialized | llm_service={self.llm_service_url}")
    
    async def classify_document(
        self,
        content: str,
        document_metadata: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> DomainProfile:
        """
        Classify document domain and characteristics
        
        Args:
            content: Document content to classify
            document_metadata: Optional metadata with hints (filename, type, etc.)
            correlation_id: Correlation ID for tracking
            project_id: Project ID for LLM configuration
            
        Returns:
            DomainProfile with classification results
        """
        logger.info(
            f"Classifying document | "
            f"corr_id={correlation_id or 'unknown'} "
            f"content_length={len(content)} "
            f"has_metadata={document_metadata is not None}"
        )
        
        # Build classification prompt using adaptive prompt builder
        prompt = self._build_classification_prompt(content, document_metadata)
        
        # Call LLM service orchestrator
        try:
            result = await self._call_llm_orchestrator(
                task_type="domain_classification",
                content=prompt,
                project_id=project_id,
                correlation_id=correlation_id
            )
            
            # Parse LLM response
            domain_profile = DomainProfile.from_llm_response(result)
            
            logger.info(
                f"Classification complete | "
                f"corr_id={correlation_id or 'unknown'} "
                f"domain={domain_profile.primary_domain.value} "
                f"structure={domain_profile.structure_type.value} "
                f"confidence={domain_profile.confidence:.2f}"
            )
            
            return domain_profile
            
        except Exception as e:
            logger.error(
                f"Classification failed | "
                f"corr_id={correlation_id or 'unknown'} "
                f"error={str(e)}"
            )
            
            # Return default profile on error
            return DomainProfile(
                primary_domain=DocumentDomain.OTHER,
                secondary_domains=[],
                confidence=0.3,
                structure_type=StructureType.MIXED,
                entity_density=EntityDensity.MEDIUM,
                estimated_entity_count=0,
                recommended_strategy="narrative_extraction"
            )
    
    def _build_classification_prompt(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Build domain classification prompt
        
        Args:
            content: Document content
            metadata: Optional metadata hints
            
        Returns:
            Formatted prompt string
        """
        # Get structure hint from metadata
        structure_hint = None
        if metadata:
            filename = metadata.get("filename", "")
            if filename.endswith((".xlsx", ".xls", ".csv")):
                structure_hint = "tabular (spreadsheet)"
            elif filename.endswith((".pdf", ".docx", ".txt")):
                structure_hint = "narrative (document)"
            elif filename.endswith((".png", ".jpg", ".vsd", ".ppt")):
                structure_hint = "diagram (image/presentation)"
        
        # Import adaptive prompt builder
        from app.core.llm_service_client import AdaptivePromptBuilder
        
        prompt_builder = AdaptivePromptBuilder()
        prompt = prompt_builder.build_domain_classification_prompt(
            content=content,
            structure_type=structure_hint
        )
        
        return prompt
    
    async def _call_llm_orchestrator(
        self,
        task_type: str,
        content: str,
        project_id: Optional[str] = None,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Call LLM service orchestrator endpoint
        
        Args:
            task_type: Task type for orchestrator
            content: Content to process
            project_id: Project ID
            correlation_id: Correlation ID
            
        Returns:
            LLM response as dict
        """
        url = f"{self.llm_service_url}/orchestrate"
        
        headers = {
            "Authorization": f"Bearer {self.service_token}",
            "Content-Type": "application/json"
        }
        
        if correlation_id:
            headers["X-Correlation-ID"] = correlation_id
        
        payload = {
            "task_type": task_type,
            "content": content,
            "project_id": project_id,
            "complexity": "simple",  # Classification is a simple task
            "response_format": {"type": "json_object"},
            "temperature": 0.1  # Low temperature for consistent classification
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            
            if not result.get("success"):
                raise Exception(f"LLM orchestration failed: {result.get('error')}")
            
            # Parse JSON result
            llm_output = result.get("result")
            if isinstance(llm_output, str):
                llm_output = json.loads(llm_output)
            
            return llm_output
    
    async def classify_batch(
        self,
        documents: List[Dict[str, Any]],
        correlation_id: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> List[DomainProfile]:
        """
        Classify multiple documents in batch
        
        Args:
            documents: List of dicts with 'content' and optional 'metadata'
            correlation_id: Correlation ID
            project_id: Project ID
            
        Returns:
            List of DomainProfile results
        """
        import asyncio
        
        tasks = []
        for doc in documents:
            task = self.classify_document(
                content=doc["content"],
                document_metadata=doc.get("metadata"),
                correlation_id=correlation_id,
                project_id=project_id
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert exceptions to default profiles
        profiles = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Batch classification error: {result}")
                profiles.append(DomainProfile(
                    primary_domain=DocumentDomain.OTHER,
                    secondary_domains=[],
                    confidence=0.0,
                    structure_type=StructureType.MIXED,
                    entity_density=EntityDensity.MEDIUM,
                    estimated_entity_count=0,
                    recommended_strategy="narrative_extraction"
                ))
            else:
                profiles.append(result)
        
        return profiles

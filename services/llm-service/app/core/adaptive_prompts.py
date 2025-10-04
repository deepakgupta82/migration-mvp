#!/usr/bin/env python3
"""
Adaptive Prompt Builder
Dynamic prompt construction based on document domain and schema

This module provides:
- Domain-specific prompt templates
- Schema-guided extraction prompts
- Few-shot learning examples
- Dynamic prompt optimization
"""

import logging
import json
from typing import Dict, List, Optional, Any

logger = logging.getLogger("adaptive_prompts")


class AdaptivePromptBuilder:
    """
    Build intelligent, context-aware prompts for LLM tasks
    
    Features:
    - Domain-specific templates
    - Schema-guided extraction
    - Dynamic example injection
    - Response format specification
    """
    
    # Domain-specific prompt templates
    DOMAIN_TEMPLATES = {
        "infrastructure": {
            "entity_extraction": """You are an expert IT infrastructure analyst. Extract structured entities from the following infrastructure documentation.

**Domain Context**: IT Infrastructure (servers, networks, applications, databases)
**Common Entity Types**: Server, Application, Database, Network Device, IP Address, Service, Environment

**Document Content**:
{content}

**Instructions**:
1. Identify all infrastructure entities (servers, apps, databases, networks, IPs)
2. Extract attributes for each entity (name, type, IP, OS, location, environment)
3. Preserve EXACT values from document (no validation, no modification)
4. Include source location (line/section) for traceability
5. Mark confidence level for each entity (0.0-1.0)

{schema_guidance}

**Output Format**: JSON array of entities
{example}""",
            
            "relationship_inference": """You are an expert in IT infrastructure relationships. Infer connections between infrastructure entities.

**Domain Context**: IT Infrastructure relationships (hosting, connections, dependencies)
**Common Relationships**: HOSTS, RUNS_ON, CONNECTS_TO, DEPENDS_ON, IN_SUBNET, ROUTES_TO

**Entities**:
{entities}

**Document Context**:
{content}

**Instructions**:
1. Identify explicit relationships stated in document
2. Infer implicit relationships from context (e.g., app on server with same IP)
3. Determine relationship type and direction
4. Include confidence score for each relationship
5. Preserve relationship attributes (ports, protocols)

**Output Format**: JSON array of relationships
{example}"""
        },
        
        "organizational": {
            "entity_extraction": """You are an expert organizational analyst. Extract structured entities from HR and organizational documentation.

**Domain Context**: Organizational structure (people, departments, roles, teams)
**Common Entity Types**: Person, Department, Role, Team, Office, Project

**Document Content**:
{content}

**Instructions**:
1. Identify all people, departments, roles, teams mentioned
2. Extract attributes (name, title, email, phone, location, manager)
3. Preserve EXACT values from document
4. Include confidence level for each entity

{schema_guidance}

**Output Format**: JSON array of entities
{example}""",
            
            "relationship_inference": """You are an expert in organizational relationships. Infer connections between people and departments.

**Domain Context**: Organizational relationships (reporting, membership, collaboration)
**Common Relationships**: REPORTS_TO, MANAGES, MEMBER_OF, WORKS_IN, COLLABORATES_WITH

**Entities**:
{entities}

**Document Context**:
{content}

**Instructions**:
1. Identify reporting structures
2. Identify team memberships
3. Identify collaborations and working relationships
4. Include confidence scores

**Output Format**: JSON array of relationships
{example}"""
        },
        
        "financial": {
            "entity_extraction": """You are an expert financial analyst. Extract structured entities from financial documentation.

**Domain Context**: Financial data (transactions, accounts, budgets, expenses)
**Common Entity Types**: Account, Transaction, Budget, Expense, Revenue, Cost Center

**Document Content**:
{content}

**Instructions**:
1. Identify all financial entities
2. Extract amounts, dates, categories, accounts
3. Preserve EXACT values including currency symbols
4. Include confidence levels

{schema_guidance}

**Output Format**: JSON array of entities
{example}"""
        },
        
        "process": {
            "entity_extraction": """You are an expert process analyst. Extract structured entities from process documentation.

**Domain Context**: Business processes (steps, activities, decisions, flows)
**Common Entity Types**: Process, Step, Activity, Decision, Gateway, Role, System

**Document Content**:
{content}

**Instructions**:
1. Identify process steps and activities
2. Extract sequence, conditions, responsible parties
3. Preserve exact wording of steps
4. Include confidence levels

{schema_guidance}

**Output Format**: JSON array of entities
{example}"""
        },
        
        "legal": {
            "entity_extraction": """You are an expert legal document analyst. Extract structured entities from legal documentation.

**Domain Context**: Legal documents (clauses, obligations, parties, dates)
**Common Entity Types**: Party, Clause, Obligation, Date, Term, Reference

**Document Content**:
{content}

**Instructions**:
1. Identify all parties, clauses, obligations
2. Extract exact legal terms and dates
3. Preserve precise legal language
4. Include confidence levels

{schema_guidance}

**Output Format**: JSON array of entities
{example}"""
        }
    }
    
    # Default template for unknown domains
    DEFAULT_TEMPLATE = {
        "entity_extraction": """Extract structured entities from the following document.

**Document Content**:
{content}

**Instructions**:
1. Identify all significant entities (people, places, things, concepts)
2. Extract relevant attributes for each entity
3. Preserve EXACT values from document (no modification)
4. Include confidence level (0.0-1.0)

{schema_guidance}

**Output Format**: JSON array of entities with structure:
{{
  "entities": [
    {{
      "id": "unique_id",
      "type": "entity_type",
      "name": "entity_name",
      "attributes": {{}},
      "confidence": 0.95,
      "source_location": "section or line"
    }}
  ]
}}
{example}""",
        
        "relationship_inference": """Infer relationships between entities.

**Entities**:
{entities}

**Document Context**:
{content}

**Instructions**:
1. Identify connections between entities
2. Determine relationship types and direction
3. Include confidence scores
4. Extract relationship attributes

**Output Format**: JSON array of relationships
{example}"""
    }
    
    # Few-shot examples by domain
    DOMAIN_EXAMPLES = {
        "infrastructure": {
            "entity_extraction": """

**Example**:
Document: "Production web server srv-prod-web-01 (192.168.1.10) runs Apache 2.4 on Ubuntu 20.04"

Output:
{
  "entities": [
    {
      "id": "server_001",
      "type": "Server",
      "name": "srv-prod-web-01",
      "attributes": {
        "ip_address": "192.168.1.10",
        "software": "Apache 2.4",
        "os": "Ubuntu 20.04",
        "environment": "production"
      },
      "confidence": 0.98,
      "source_location": "line 1"
    }
  ]
}""",
            "relationship_inference": """

**Example**:
Entities: [Server: srv-web-01 (192.168.1.10), App: OrderService]
Context: "OrderService runs on 192.168.1.10:8080"

Output:
{
  "relationships": [
    {
      "source_id": "app_orderservice",
      "target_id": "server_srv_web_01",
      "type": "RUNS_ON",
      "confidence": 0.95,
      "properties": {
        "port": 8080,
        "protocol": "HTTP"
      }
    }
  ]
}"""
        }
    }
    
    def __init__(self):
        logger.info("Adaptive Prompt Builder initialized")
    
    def build_entity_extraction_prompt(
        self,
        content: str,
        domain: str = "general",
        discovered_schema: Optional[Dict] = None,
        include_examples: bool = True
    ) -> str:
        """
        Build entity extraction prompt adapted to document domain
        
        Args:
            content: Document content to extract from
            domain: Document domain (infrastructure, organizational, etc.)
            discovered_schema: Optional schema to guide extraction
            include_examples: Whether to include few-shot examples
            
        Returns:
            Formatted prompt string
        """
        # Get template for domain
        domain_lower = domain.lower()
        if domain_lower in self.DOMAIN_TEMPLATES:
            template = self.DOMAIN_TEMPLATES[domain_lower]["entity_extraction"]
        else:
            template = self.DEFAULT_TEMPLATE["entity_extraction"]
            logger.info(f"Using default template for unknown domain: {domain}")
        
        # Build schema guidance
        schema_guidance = ""
        if discovered_schema:
            schema_guidance = self._build_schema_guidance(discovered_schema)
        
        # Get example
        example = ""
        if include_examples and domain_lower in self.DOMAIN_EXAMPLES:
            example = self.DOMAIN_EXAMPLES[domain_lower].get("entity_extraction", "")
        
        # Format template
        prompt = template.format(
            content=content,
            schema_guidance=schema_guidance,
            example=example
        )
        
        logger.debug(
            f"Built entity extraction prompt | "
            f"domain={domain} "
            f"has_schema={discovered_schema is not None} "
            f"has_examples={len(example) > 0}"
        )
        
        return prompt
    
    def build_relationship_inference_prompt(
        self,
        entities: List[Dict],
        content: str,
        domain: str = "general",
        include_examples: bool = True
    ) -> str:
        """
        Build relationship inference prompt
        
        Args:
            entities: List of extracted entities
            content: Original document content for context
            domain: Document domain
            include_examples: Whether to include examples
            
        Returns:
            Formatted prompt string
        """
        # Get template
        domain_lower = domain.lower()
        if domain_lower in self.DOMAIN_TEMPLATES:
            template = self.DOMAIN_TEMPLATES[domain_lower]["relationship_inference"]
        else:
            template = self.DEFAULT_TEMPLATE["relationship_inference"]
        
        # Format entities for prompt
        entities_str = json.dumps(entities, indent=2)
        
        # Get example
        example = ""
        if include_examples and domain_lower in self.DOMAIN_EXAMPLES:
            example = self.DOMAIN_EXAMPLES[domain_lower].get("relationship_inference", "")
        
        # Format template
        prompt = template.format(
            entities=entities_str,
            content=content[:5000],  # Truncate content for context
            example=example
        )
        
        logger.debug(
            f"Built relationship inference prompt | "
            f"domain={domain} "
            f"entity_count={len(entities)}"
        )
        
        return prompt
    
    def build_domain_classification_prompt(
        self,
        content: str,
        structure_type: Optional[str] = None
    ) -> str:
        """
        Build domain classification prompt
        
        Args:
            content: Document content to classify
            structure_type: Optional hint about structure (tabular, narrative)
            
        Returns:
            Formatted prompt string
        """
        prompt = f"""Classify the domain and content type of this document.

**Document Content** (first 2000 chars):
{content[:2000]}

**Structure Type**: {structure_type or "unknown"}

**Instructions**:
1. Identify the PRIMARY domain (infrastructure, organizational, financial, legal, process, HR, technical, other)
2. Identify SECONDARY domains if applicable
3. Determine structure type (tabular, narrative, mixed, diagram, list)
4. Estimate entity density (low, medium, high)
5. Recommend extraction strategy

**Output Format**: JSON
{{
  "primary_domain": "domain_name",
  "secondary_domains": ["domain2", "domain3"],
  "confidence": 0.95,
  "structure_type": "tabular|narrative|mixed|diagram",
  "entity_density": "low|medium|high",
  "estimated_entity_count": 100,
  "recommended_strategy": "spreadsheet_extraction|narrative_extraction|mixed"
}}

**Examples**:
- Server inventory Excel → infrastructure, tabular, high density
- Org chart document → organizational, mixed, medium density
- Process flowchart → process, diagram, low density
"""
        
        logger.debug("Built domain classification prompt")
        return prompt
    
    def build_schema_discovery_prompt(
        self,
        content: str,
        domain: str
    ) -> str:
        """
        Build schema discovery prompt to identify entity types and relationships
        
        Args:
            content: Document content to analyze
            domain: Document domain
            
        Returns:
            Formatted prompt string
        """
        prompt = f"""Analyze this {domain} document and discover its schema (entity types and relationships).

**Document Content** (sample):
{content[:3000]}

**Instructions**:
1. Identify all entity types present (e.g., Server, Application, Person, Department)
2. For each entity type, identify:
   - Required attributes (always present)
   - Optional attributes (sometimes present)
   - Identifier fields (unique identifiers)
3. Identify relationship patterns between entity types
4. Provide confidence scores

**Output Format**: JSON
{{
  "discovered_entity_types": [
    {{
      "type_name": "Server",
      "confidence": 0.95,
      "required_attributes": ["name", "ip_address"],
      "optional_attributes": ["os", "location", "environment"],
      "identifier_fields": ["name", "ip_address"],
      "sample_count": 10
    }}
  ],
  "discovered_relationships": [
    {{
      "source_type": "Application",
      "target_type": "Server",
      "relationship_type": "RUNS_ON",
      "confidence": 0.88,
      "sample_count": 5
    }}
  ]
}}
"""
        
        logger.debug(f"Built schema discovery prompt | domain={domain}")
        return prompt
    
    def _build_schema_guidance(self, schema: Dict) -> str:
        """
        Build schema guidance section for prompts
        
        Args:
            schema: Discovered schema dict
            
        Returns:
            Formatted schema guidance string
        """
        if not schema or "discovered_entity_types" not in schema:
            return ""
        
        guidance = "\n**Expected Entity Types Based on Document Analysis**:\n"
        
        for entity_type in schema["discovered_entity_types"]:
            type_name = entity_type["type_name"]
            required = ", ".join(entity_type.get("required_attributes", []))
            optional = ", ".join(entity_type.get("optional_attributes", []))
            
            guidance += f"\n- **{type_name}**\n"
            guidance += f"  - Required: {required}\n"
            if optional:
                guidance += f"  - Optional: {optional}\n"
        
        return guidance
    
    def build_semantic_matching_prompt(
        self,
        entity1: Dict,
        entity2: Dict
    ) -> str:
        """
        Build prompt for LLM-based semantic entity matching
        
        Args:
            entity1: First entity to compare
            entity2: Second entity to compare
            
        Returns:
            Formatted prompt string
        """
        prompt = f"""Determine if these two entities refer to the same real-world entity.

**Entity 1**:
{json.dumps(entity1, indent=2)}

**Entity 2**:
{json.dumps(entity2, indent=2)}

**Instructions**:
1. Compare names (account for abbreviations, variations)
2. Compare attributes (IPs, locations, identifiers)
3. Consider context and domain
4. Determine if they are the SAME entity or DIFFERENT entities

**Output Format**: JSON
{{
  "is_match": true/false,
  "confidence": 0.92,
  "reasoning": "explanation of decision",
  "matched_on": ["attribute1", "attribute2"]
}}

**Examples**:
- "srv-prod-web-01" vs "srv-prod-web-01.company.com" → MATCH (same server, FQDN)
- "RHEL 8" vs "Red Hat Enterprise Linux 8" → MATCH (abbreviation)
- "192.168.1.10" vs "192.168.1.11" → NO MATCH (different IPs)
"""
        
        logger.debug("Built semantic matching prompt")
        return prompt

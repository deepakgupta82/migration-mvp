-- Migration: Add document_vision_assessment_llm_config column to projects table
-- Purpose: Support vision-capable LLM configuration for diagram/image document assessment
-- Date: 2025-01-06

-- Add the new column
ALTER TABLE projects 
ADD COLUMN IF NOT EXISTS document_vision_assessment_llm_config TEXT;

-- Add comment for documentation
COMMENT ON COLUMN projects.document_vision_assessment_llm_config IS 'JSON configuration for vision-based document assessment LLM (e.g., GPT-4o, Gemini Pro Vision, Claude 3.5 Sonnet)';

-- Add similar columns if they don't exist (for consistency)
ALTER TABLE projects 
ADD COLUMN IF NOT EXISTS entity_extraction_llm_config TEXT;

ALTER TABLE projects 
ADD COLUMN IF NOT EXISTS crew_assessment_llm_config TEXT;

ALTER TABLE projects 
ADD COLUMN IF NOT EXISTS crew_documentation_llm_config TEXT;

ALTER TABLE projects 
ADD COLUMN IF NOT EXISTS rag_synthesis_llm_config TEXT;

ALTER TABLE projects 
ADD COLUMN IF NOT EXISTS hybrid_search_llm_config TEXT;

-- Add JSONB column for combined configs if not exists
ALTER TABLE projects 
ADD COLUMN IF NOT EXISTS llm_process_configs JSONB;

-- Add comments for all process-specific LLM config columns
COMMENT ON COLUMN projects.entity_extraction_llm_config IS 'JSON configuration for entity extraction process LLM';
COMMENT ON COLUMN projects.crew_assessment_llm_config IS 'JSON configuration for crew assessment process LLM';
COMMENT ON COLUMN projects.crew_documentation_llm_config IS 'JSON configuration for crew documentation process LLM';
COMMENT ON COLUMN projects.rag_synthesis_llm_config IS 'JSON configuration for RAG synthesis process LLM';
COMMENT ON COLUMN projects.hybrid_search_llm_config IS 'JSON configuration for hybrid search process LLM';
COMMENT ON COLUMN projects.llm_process_configs IS 'Combined JSONB storage for all process-specific LLM configurations';

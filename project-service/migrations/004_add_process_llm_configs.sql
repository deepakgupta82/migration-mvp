-- Add process-specific LLM configuration columns to projects table
-- This allows per-process LLM configuration for maximum flexibility

ALTER TABLE projects 
ADD COLUMN entity_extraction_llm_config TEXT NULL,
ADD COLUMN crew_assessment_llm_config TEXT NULL,
ADD COLUMN crew_documentation_llm_config TEXT NULL,
ADD COLUMN rag_synthesis_llm_config TEXT NULL,
ADD COLUMN hybrid_search_llm_config TEXT NULL,
ADD COLUMN llm_process_configs TEXT NULL;  -- JSON field for nested configuration

-- Add index for faster LLM configuration queries
CREATE INDEX IF NOT EXISTS idx_projects_llm_configs ON projects(llm_api_key_id);

-- Comments for documentation
COMMENT ON COLUMN projects.entity_extraction_llm_config IS 'JSON configuration for entity extraction LLM (provider, model, api_key_id, temperature, max_tokens)';
COMMENT ON COLUMN projects.crew_assessment_llm_config IS 'JSON configuration for CrewAI assessment LLM';
COMMENT ON COLUMN projects.crew_documentation_llm_config IS 'JSON configuration for CrewAI documentation generation LLM';
COMMENT ON COLUMN projects.rag_synthesis_llm_config IS 'JSON configuration for RAG response synthesis LLM';
COMMENT ON COLUMN projects.hybrid_search_llm_config IS 'JSON configuration for hybrid search query generation LLM';
COMMENT ON COLUMN projects.llm_process_configs IS 'JSON object containing all process-specific LLM configurations';

-- Example data structure for llm_process_configs:
-- {
--   "entity_extraction": {
--     "provider": "openai",
--     "model": "gpt-4o-mini", 
--     "api_key_id": "openai_key_1",
--     "temperature": 0.1,
--     "max_tokens": 2000
--   },
--   "crew_assessment": {
--     "provider": "anthropic",
--     "model": "claude-3-sonnet-20240229",
--     "api_key_id": "anthropic_key_1", 
--     "temperature": 0.1,
--     "max_tokens": 4000
--   }
-- }

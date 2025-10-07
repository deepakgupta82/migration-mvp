-- Add document_vision_assessment_llm_config column to projects table
-- This allows vision-capable LLM configuration for diagram/image document assessment

ALTER TABLE projects 
ADD COLUMN IF NOT EXISTS document_vision_assessment_llm_config TEXT NULL;

-- Comment for documentation
COMMENT ON COLUMN projects.document_vision_assessment_llm_config IS 'JSON configuration for vision-based document assessment LLM (e.g., GPT-4o, Gemini Pro Vision, Claude 3.5 Sonnet with vision)';

-- Example data structure:
-- {
--   "provider": "openai",
--   "model": "gpt-4o",
--   "api_key_id": "openai_key_1",
--   "temperature": 0.1,
--   "max_tokens": 4096,
--   "supports_vision": true
-- }

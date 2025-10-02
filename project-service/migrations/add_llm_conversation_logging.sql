-- Migration: Add full conversation logging columns to llm_calls table
-- Date: 2025-01-XX
-- Related to: Fix #3 - Store complete prompts/responses for quality review

-- Add new columns for full conversation logging
ALTER TABLE llm_calls 
ADD COLUMN IF NOT EXISTS prompt_text TEXT,
ADD COLUMN IF NOT EXISTS response_text TEXT,
ADD COLUMN IF NOT EXISTS messages JSONB;

-- Add comments for documentation
COMMENT ON COLUMN llm_calls.prompt_text IS 'Full untruncated prompt sent to LLM';
COMMENT ON COLUMN llm_calls.response_text IS 'Full untruncated response from LLM';
COMMENT ON COLUMN llm_calls.messages IS 'Complete conversation history in messages format';

-- Create index for faster JSONB queries if needed
CREATE INDEX IF NOT EXISTS idx_llm_calls_messages_gin ON llm_calls USING gin(messages);

-- Verify migration
SELECT 
    column_name, 
    data_type, 
    is_nullable
FROM information_schema.columns 
WHERE table_name = 'llm_calls' 
  AND column_name IN ('prompt_text', 'response_text', 'messages')
ORDER BY column_name;

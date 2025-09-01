-- Add document content storage fields to project_files table
-- This enables storing summaries, categories, and structure metadata for documents

ALTER TABLE project_files
ADD COLUMN summary_text TEXT NULL,
ADD COLUMN categories TEXT[] NULL,
ADD COLUMN structure_metadata JSONB NULL;

-- Add index for categories array for efficient querying
CREATE INDEX IF NOT EXISTS idx_project_files_categories ON project_files USING GIN (categories);

-- Add index for structure_metadata JSONB for efficient querying
CREATE INDEX IF NOT EXISTS idx_project_files_structure_metadata ON project_files USING GIN (structure_metadata);

-- Comments for documentation
COMMENT ON COLUMN project_files.summary_text IS 'AI-generated summary of the document content';
COMMENT ON COLUMN project_files.categories IS 'Array of categories/tags for document classification';
COMMENT ON COLUMN project_files.structure_metadata IS 'JSON metadata containing document structure information (sections, headings, etc.)';

-- Example data structure for structure_metadata:
-- {
--   "sections": [
--     {"title": "Introduction", "level": 1, "page": 1},
--     {"title": "Requirements", "level": 2, "page": 3}
--   ],
--   "total_pages": 10,
--   "document_type": "pdf",
--   "language": "en"
-- }
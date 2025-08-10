# Enhanced Document Processing with Markdown Conversion

## Implementation Plan: Convert to .md First

### Phase 1: Enhanced Document Processing Pipeline

#### 1.1 Markdown Conversion Service

**File: `backend/app/core/markdown_converter.py`**
```python
import os
import re
from typing import Dict, Any
from pathlib import Path

class MarkdownConverter:
    """Convert MegaParse output to structured markdown"""
    
    def __init__(self):
        self.conversion_rules = {
            'pdf': self._convert_pdf_to_md,
            'docx': self._convert_docx_to_md,
            'txt': self._convert_txt_to_md,
            'html': self._convert_html_to_md
        }
    
    def convert_to_markdown(self, content: str, file_type: str, metadata: Dict[str, Any] = None) -> str:
        """Convert parsed content to structured markdown"""
        
        # Get file-specific converter
        converter = self.conversion_rules.get(file_type.lower(), self._convert_generic_to_md)
        
        # Convert to markdown
        markdown_content = converter(content, metadata or {})
        
        # Add document metadata header
        md_header = self._create_document_header(metadata or {})
        
        return f"{md_header}\n\n{markdown_content}"
    
    def _create_document_header(self, metadata: Dict[str, Any]) -> str:
        """Create markdown document header with metadata"""
        header = "---\n"
        header += f"title: {metadata.get('title', 'Untitled Document')}\n"
        header += f"source: {metadata.get('filename', 'unknown')}\n"
        header += f"processed_at: {metadata.get('processed_at', 'unknown')}\n"
        header += f"file_type: {metadata.get('file_type', 'unknown')}\n"
        header += f"file_size: {metadata.get('file_size', 'unknown')}\n"
        header += "---\n"
        return header
    
    def _convert_pdf_to_md(self, content: str, metadata: Dict[str, Any]) -> str:
        """Convert PDF content to structured markdown"""
        lines = content.split('\n')
        markdown_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                markdown_lines.append('')
                continue
            
            # Detect headers (lines that are all caps or have specific patterns)
            if self._is_header(line):
                level = self._determine_header_level(line)
                markdown_lines.append(f"{'#' * level} {line}")
            
            # Detect lists
            elif self._is_list_item(line):
                markdown_lines.append(f"- {line}")
            
            # Regular paragraph
            else:
                markdown_lines.append(line)
        
        return '\n'.join(markdown_lines)
    
    def _convert_docx_to_md(self, content: str, metadata: Dict[str, Any]) -> str:
        """Convert DOCX content to structured markdown"""
        # DOCX often has better structure preservation from MegaParse
        lines = content.split('\n')
        markdown_lines = []
        
        in_table = False
        
        for line in lines:
            line = line.strip()
            if not line:
                if in_table:
                    in_table = False
                markdown_lines.append('')
                continue
            
            # Detect table content
            if '|' in line and line.count('|') >= 2:
                if not in_table:
                    in_table = True
                markdown_lines.append(line)
                # Add table header separator if this looks like a header
                if self._is_table_header(line):
                    separator = '|' + '|'.join(['---' for _ in line.split('|')[1:-1]]) + '|'
                    markdown_lines.append(separator)
            
            # Headers
            elif self._is_header(line):
                level = self._determine_header_level(line)
                markdown_lines.append(f"{'#' * level} {line}")
            
            # Lists
            elif self._is_list_item(line):
                markdown_lines.append(f"- {line}")
            
            # Regular content
            else:
                markdown_lines.append(line)
        
        return '\n'.join(markdown_lines)
    
    def _is_header(self, line: str) -> bool:
        """Detect if line is likely a header"""
        # Headers are often:
        # - All caps
        # - Short lines
        # - Followed by numbers/sections
        # - Have specific formatting
        
        if len(line) > 100:  # Too long to be a header
            return False
        
        # All caps (but not just numbers/symbols)
        if line.isupper() and any(c.isalpha() for c in line):
            return True
        
        # Numbered sections
        if re.match(r'^\d+\.?\s+[A-Z]', line):
            return True
        
        # Common header patterns
        header_patterns = [
            r'^(CHAPTER|SECTION|PART)\s+\d+',
            r'^\d+\.\d+\s+[A-Z]',
            r'^[A-Z][A-Z\s]{5,50}$'
        ]
        
        return any(re.match(pattern, line) for pattern in header_patterns)
    
    def _determine_header_level(self, line: str) -> int:
        """Determine markdown header level (1-6)"""
        # Level 1: CHAPTER, PART
        if re.match(r'^(CHAPTER|PART)\s+\d+', line):
            return 1
        
        # Level 2: SECTION, numbered main sections
        if re.match(r'^(SECTION|\d+\.)\s+', line):
            return 2
        
        # Level 3: Sub-sections
        if re.match(r'^\d+\.\d+\s+', line):
            return 3
        
        # Level 4: Sub-sub-sections
        if re.match(r'^\d+\.\d+\.\d+\s+', line):
            return 4
        
        # Default to level 2
        return 2
    
    def _is_list_item(self, line: str) -> bool:
        """Detect if line is a list item"""
        list_patterns = [
            r'^\s*[-•]\s+',  # Bullet points
            r'^\s*\d+\.\s+',  # Numbered lists
            r'^\s*[a-z]\)\s+',  # Lettered lists
            r'^\s*[ivx]+\.\s+',  # Roman numerals
        ]
        
        return any(re.match(pattern, line) for pattern in list_patterns)
    
    def _is_table_header(self, line: str) -> bool:
        """Detect if table row is likely a header"""
        # Table headers often have specific characteristics
        cells = [cell.strip() for cell in line.split('|')[1:-1]]
        
        # All cells are short and likely headers
        if all(len(cell) < 30 and cell.isupper() for cell in cells if cell):
            return True
        
        # Contains common header words
        header_words = ['NAME', 'TYPE', 'DESCRIPTION', 'VALUE', 'STATUS', 'DATE']
        if any(word in cell.upper() for cell in cells for word in header_words):
            return True
        
        return False

markdown_converter = MarkdownConverter()
```

#### 1.2 Enhanced RAG Service with Markdown

**File: `backend/app/core/enhanced_rag_service.py`**
```python
from markdown_converter import markdown_converter
from semantic_chunking import SemanticChunker
import os
from pathlib import Path

class EnhancedRAGService:
    """Enhanced RAG service with markdown conversion"""
    
    def __init__(self):
        self.markdown_storage_path = Path("processed_documents/markdown")
        self.markdown_storage_path.mkdir(parents=True, exist_ok=True)
        self.chunker = SemanticChunker()
    
    def process_document(self, file_path: str, project_id: str) -> Dict[str, Any]:
        """Enhanced document processing with markdown conversion"""
        
        # Step 1: Parse with MegaParse (existing)
        parsed_content = self._parse_with_megaparse(file_path)
        
        # Step 2: Convert to markdown (NEW)
        file_type = Path(file_path).suffix[1:]  # Remove dot
        metadata = {
            'filename': Path(file_path).name,
            'file_type': file_type,
            'file_size': os.path.getsize(file_path),
            'processed_at': datetime.utcnow().isoformat(),
            'project_id': project_id
        }
        
        markdown_content = markdown_converter.convert_to_markdown(
            content=parsed_content,
            file_type=file_type,
            metadata=metadata
        )
        
        # Step 3: Store markdown file (NEW)
        md_filename = f"{project_id}_{Path(file_path).stem}.md"
        md_file_path = self.markdown_storage_path / md_filename
        
        with open(md_file_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        # Step 4: Enhanced processing using markdown (IMPROVED)
        results = self._process_markdown_content(markdown_content, md_file_path)
        
        return {
            'original_file': file_path,
            'markdown_file': str(md_file_path),
            'processing_results': results,
            'metadata': metadata
        }
    
    def _process_markdown_content(self, markdown_content: str, md_file_path: Path) -> Dict[str, Any]:
        """Process markdown content with enhanced chunking and entity extraction"""
        
        # Enhanced semantic chunking using markdown structure
        chunks = self._chunk_markdown_semantically(markdown_content)
        
        # Create embeddings for chunks
        embeddings_created = 0
        for chunk in chunks:
            self._create_embedding(chunk)
            embeddings_created += 1
        
        # Enhanced entity extraction using markdown structure
        entities = self._extract_entities_from_markdown(markdown_content)
        
        # Create knowledge graph nodes
        graph_nodes_created = 0
        for entity in entities:
            self._create_graph_node(entity)
            graph_nodes_created += 1
        
        return {
            'chunks_created': len(chunks),
            'embeddings_created': embeddings_created,
            'entities_extracted': len(entities),
            'graph_nodes_created': graph_nodes_created
        }
    
    def _chunk_markdown_semantically(self, markdown_content: str) -> List[DocumentChunk]:
        """Enhanced chunking using markdown structure"""
        
        # Parse markdown sections
        sections = self._parse_markdown_sections(markdown_content)
        chunks = []
        
        for section in sections:
            # Use section header as context
            section_content = f"# {section['header']}\n\n{section['content']}"
            
            if len(section_content) <= self.chunker.max_chunk_size:
                # Section fits in one chunk
                chunks.append(DocumentChunk(
                    content=section_content,
                    chunk_type='section',
                    metadata={'section_header': section['header']}
                ))
            else:
                # Split large sections while preserving context
                sub_chunks = self.chunker.chunk_document(section_content)
                for sub_chunk in sub_chunks:
                    sub_chunk.metadata = {'section_header': section['header']}
                chunks.extend(sub_chunks)
        
        return chunks
    
    def _extract_entities_from_markdown(self, markdown_content: str) -> List[Entity]:
        """Enhanced entity extraction using markdown structure"""
        
        sections = self._parse_markdown_sections(markdown_content)
        entities = []
        
        for section in sections:
            # Create context-rich prompt for LLM
            context_prompt = f"""
            Document Section: {section['header']}
            Content: {section['content']}
            
            Extract entities from this section, considering the section context.
            """
            
            section_entities = self.entity_extraction_agent.extract_entities(context_prompt)
            
            # Enhance entities with section context
            for entity in section_entities:
                entity.context = section['header']
                entity.document_section = section['header']
                entities.append(entity)
        
        return entities
    
    def _parse_markdown_sections(self, markdown_content: str) -> List[Dict[str, str]]:
        """Parse markdown into sections based on headers"""
        lines = markdown_content.split('\n')
        sections = []
        current_section = {'header': 'Introduction', 'content': ''}
        
        for line in lines:
            if line.startswith('#'):
                # Save previous section
                if current_section['content'].strip():
                    sections.append(current_section)
                
                # Start new section
                header = line.lstrip('#').strip()
                current_section = {'header': header, 'content': ''}
            else:
                current_section['content'] += line + '\n'
        
        # Add final section
        if current_section['content'].strip():
            sections.append(current_section)
        
        return sections

enhanced_rag_service = EnhancedRAGService()
```

## Benefits of Markdown Conversion Approach

### 1. **Better Document Understanding**
- **Structure Preservation**: Headers, lists, tables maintained
- **Context Awareness**: Section-based entity extraction
- **Quality Control**: Human-readable intermediate format

### 2. **Enhanced Processing Quality**
- **Semantic Chunking**: Use document structure for better boundaries
- **Entity Extraction**: Better context from section headers
- **Relationship Detection**: Cross-reference entities within sections

### 3. **Operational Benefits**
- **Debugging**: Easy to inspect processed content
- **Reprocessing**: Can reprocess without re-parsing
- **Version Control**: Track changes to processed documents
- **Quality Assurance**: Manual review of markdown before processing

### 4. **Implementation Timeline**
- **Week 1**: Implement markdown converter
- **Week 2**: Enhance RAG service with markdown processing
- **Week 3**: Update chunking and entity extraction
- **Week 4**: Testing and optimization

**RECOMMENDATION: Implement the markdown conversion approach for significantly better document processing quality and maintainability.**

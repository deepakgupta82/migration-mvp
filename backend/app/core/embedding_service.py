"""
Enhanced Embedding Service
Advanced embedding strategies with multi-modal support and performance optimizations
"""

import logging
import hashlib
import json
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass
import numpy as np
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

@dataclass
class EmbeddingResult:
    """Result of embedding operation"""
    embedding: List[float]
    model_name: str
    content_type: str
    metadata: Dict[str, Any]
    created_at: str

class EmbeddingService:
    """Enhanced embedding service with multi-modal support"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.default_model = self.config.get('model', 'all-MiniLM-L6-v2')
        self.cache_size = self.config.get('cache_size', 1000)
        self.batch_size = self.config.get('batch_size', 100)
        
        # Initialize models
        self.text_model = None
        self.code_model = None
        self.embedding_cache = {}
        
        self._initialize_models()
    
    def _initialize_models(self):
        """Initialize embedding models"""
        try:
            from sentence_transformers import SentenceTransformer
            
            # Initialize text embedding model
            self.text_model = SentenceTransformer(self.default_model)
            logger.info(f"Initialized text embedding model: {self.default_model}")
            
            # Initialize code embedding model if available
            try:
                self.code_model = SentenceTransformer('microsoft/codebert-base')
                logger.info("Initialized code embedding model: microsoft/codebert-base")
            except Exception as e:
                logger.warning(f"Code embedding model not available: {str(e)}")
                self.code_model = self.text_model  # Fallback to text model
        
        except ImportError:
            logger.error("sentence-transformers not available. Embedding service will not work.")
        except Exception as e:
            logger.error(f"Error initializing embedding models: {str(e)}")
    
    def create_embeddings(self, contents: List[str], content_types: List[str] = None, 
                         batch_size: int = None) -> List[EmbeddingResult]:
        """Create embeddings for multiple content items with batching"""
        if not contents:
            return []
        
        if content_types is None:
            content_types = ['text'] * len(contents)
        
        if len(content_types) != len(contents):
            content_types = ['text'] * len(contents)
        
        batch_size = batch_size or self.batch_size
        results = []
        
        # Process in batches
        for i in range(0, len(contents), batch_size):
            batch_contents = contents[i:i + batch_size]
            batch_types = content_types[i:i + batch_size]
            
            batch_results = self._process_batch(batch_contents, batch_types)
            results.extend(batch_results)
            
            logger.info(f"Processed embedding batch {i//batch_size + 1}/{(len(contents) + batch_size - 1)//batch_size}")
        
        return results
    
    def _process_batch(self, contents: List[str], content_types: List[str]) -> List[EmbeddingResult]:
        """Process a batch of content for embeddings"""
        results = []
        
        # Group by content type for efficient processing
        type_groups = {}
        for idx, (content, content_type) in enumerate(zip(contents, content_types)):
            if content_type not in type_groups:
                type_groups[content_type] = []
            type_groups[content_type].append((idx, content))
        
        # Process each content type group
        for content_type, items in type_groups.items():
            indices, batch_contents = zip(*items)
            
            # Check cache first
            cached_results, uncached_items = self._check_cache(batch_contents, content_type)
            
            # Process uncached items
            if uncached_items:
                uncached_indices, uncached_contents = zip(*uncached_items)
                new_embeddings = self._create_embeddings_by_type(list(uncached_contents), content_type)
                
                # Cache new embeddings
                for content, embedding_result in zip(uncached_contents, new_embeddings):
                    self._cache_embedding(content, embedding_result)
                
                # Merge cached and new results
                all_embeddings = cached_results + new_embeddings
                all_indices = list(cached_results.keys()) + list(uncached_indices)
            else:
                all_embeddings = list(cached_results.values())
                all_indices = list(cached_results.keys())
            
            # Add to results in original order
            for idx, embedding_result in zip(all_indices, all_embeddings):
                results.append((indices[idx], embedding_result))
        
        # Sort by original index and return embedding results
        results.sort(key=lambda x: x[0])
        return [result[1] for result in results]
    
    def _create_embeddings_by_type(self, contents: List[str], content_type: str) -> List[EmbeddingResult]:
        """Create embeddings based on content type"""
        if content_type == 'code' and self.code_model is not None:
            return self._create_code_embeddings(contents)
        elif content_type == 'table':
            return self._create_table_embeddings(contents)
        else:
            return self._create_text_embeddings(contents)
    
    def _create_text_embeddings(self, contents: List[str]) -> List[EmbeddingResult]:
        """Create text embeddings"""
        if self.text_model is None:
            raise RuntimeError("Text embedding model not initialized")
        
        try:
            embeddings = self.text_model.encode(contents, convert_to_numpy=True)
            
            results = []
            for content, embedding in zip(contents, embeddings):
                results.append(EmbeddingResult(
                    embedding=embedding.tolist(),
                    model_name=self.default_model,
                    content_type='text',
                    metadata={
                        'content_length': len(content),
                        'embedding_dim': len(embedding)
                    },
                    created_at=datetime.now(timezone.utc).isoformat()
                ))
            
            return results
        
        except Exception as e:
            logger.error(f"Error creating text embeddings: {str(e)}")
            raise
    
    def _create_code_embeddings(self, contents: List[str]) -> List[EmbeddingResult]:
        """Create code-specific embeddings"""
        if self.code_model is None:
            logger.warning("Code model not available, falling back to text model")
            return self._create_text_embeddings(contents)
        
        try:
            # Preprocess code content
            processed_contents = [self._preprocess_code(content) for content in contents]
            
            embeddings = self.code_model.encode(processed_contents, convert_to_numpy=True)
            
            results = []
            for content, embedding in zip(contents, embeddings):
                # Detect programming language
                language = self._detect_programming_language(content)
                
                results.append(EmbeddingResult(
                    embedding=embedding.tolist(),
                    model_name='microsoft/codebert-base',
                    content_type='code',
                    metadata={
                        'content_length': len(content),
                        'embedding_dim': len(embedding),
                        'programming_language': language,
                        'preprocessed': True
                    },
                    created_at=datetime.now(timezone.utc).isoformat()
                ))
            
            return results
        
        except Exception as e:
            logger.error(f"Error creating code embeddings: {str(e)}")
            # Fallback to text embeddings
            return self._create_text_embeddings(contents)
    
    def _create_table_embeddings(self, contents: List[str]) -> List[EmbeddingResult]:
        """Create table-specific embeddings"""
        try:
            # Process table content to extract structure
            processed_contents = []
            table_metadata = []
            
            for content in contents:
                processed_content, metadata = self._preprocess_table(content)
                processed_contents.append(processed_content)
                table_metadata.append(metadata)
            
            # Use text model for table embeddings (could be enhanced with specialized model)
            embeddings = self.text_model.encode(processed_contents, convert_to_numpy=True)
            
            results = []
            for content, embedding, metadata in zip(contents, embeddings, table_metadata):
                results.append(EmbeddingResult(
                    embedding=embedding.tolist(),
                    model_name=self.default_model,
                    content_type='table',
                    metadata={
                        'content_length': len(content),
                        'embedding_dim': len(embedding),
                        'table_rows': metadata.get('rows', 0),
                        'table_columns': metadata.get('columns', 0),
                        'has_headers': metadata.get('has_headers', False)
                    },
                    created_at=datetime.now(timezone.utc).isoformat()
                ))
            
            return results
        
        except Exception as e:
            logger.error(f"Error creating table embeddings: {str(e)}")
            # Fallback to text embeddings
            return self._create_text_embeddings(contents)
    
    def _preprocess_code(self, code_content: str) -> str:
        """Preprocess code content for better embeddings"""
        # Remove excessive whitespace
        lines = code_content.split('\n')
        processed_lines = []
        
        for line in lines:
            # Remove leading/trailing whitespace but preserve indentation structure
            stripped = line.rstrip()
            if stripped:
                processed_lines.append(stripped)
        
        # Join with single newlines
        processed_content = '\n'.join(processed_lines)
        
        # Limit length to avoid very long code blocks
        if len(processed_content) > 2000:
            processed_content = processed_content[:2000] + "..."
        
        return processed_content
    
    def _detect_programming_language(self, code_content: str) -> str:
        """Detect programming language from code content"""
        # Simple heuristics for language detection
        content_lower = code_content.lower()
        
        if any(keyword in content_lower for keyword in ['def ', 'import ', 'from ', 'class ']):
            return 'python'
        elif any(keyword in content_lower for keyword in ['function', 'var ', 'const ', 'let ']):
            return 'javascript'
        elif any(keyword in content_lower for keyword in ['public class', 'private ', 'public static']):
            return 'java'
        elif any(keyword in content_lower for keyword in ['#include', 'int main', 'printf']):
            return 'c'
        elif any(keyword in content_lower for keyword in ['using namespace', 'std::', 'cout']):
            return 'cpp'
        elif any(keyword in content_lower for keyword in ['select ', 'from ', 'where ', 'insert ']):
            return 'sql'
        else:
            return 'unknown'
    
    def _preprocess_table(self, table_content: str) -> Tuple[str, Dict[str, Any]]:
        """Preprocess table content and extract metadata"""
        lines = table_content.strip().split('\n')
        
        # Detect table format (CSV, TSV, markdown, etc.)
        if '|' in table_content:
            # Markdown table
            return self._process_markdown_table(lines)
        elif '\t' in table_content:
            # TSV
            return self._process_tsv_table(lines)
        elif ',' in table_content:
            # CSV
            return self._process_csv_table(lines)
        else:
            # Plain text table
            return table_content, {'rows': len(lines), 'columns': 1, 'has_headers': False}
    
    def _process_markdown_table(self, lines: List[str]) -> Tuple[str, Dict[str, Any]]:
        """Process markdown table format"""
        table_rows = []
        has_headers = False
        
        for i, line in enumerate(lines):
            if '|' in line:
                # Clean up the line
                cells = [cell.strip() for cell in line.split('|') if cell.strip()]
                if cells:
                    table_rows.append(' '.join(cells))
                    
                    # Check if next line is separator (indicates headers)
                    if i + 1 < len(lines) and '---' in lines[i + 1]:
                        has_headers = True
        
        processed_content = '\n'.join(table_rows)
        metadata = {
            'rows': len(table_rows),
            'columns': len(table_rows[0].split()) if table_rows else 0,
            'has_headers': has_headers
        }
        
        return processed_content, metadata
    
    def _process_csv_table(self, lines: List[str]) -> Tuple[str, Dict[str, Any]]:
        """Process CSV table format"""
        processed_lines = []
        max_columns = 0
        
        for line in lines:
            cells = [cell.strip().strip('"') for cell in line.split(',')]
            processed_lines.append(' '.join(cells))
            max_columns = max(max_columns, len(cells))
        
        processed_content = '\n'.join(processed_lines)
        metadata = {
            'rows': len(processed_lines),
            'columns': max_columns,
            'has_headers': True  # Assume first row is headers for CSV
        }
        
        return processed_content, metadata
    
    def _process_tsv_table(self, lines: List[str]) -> Tuple[str, Dict[str, Any]]:
        """Process TSV table format"""
        processed_lines = []
        max_columns = 0
        
        for line in lines:
            cells = [cell.strip() for cell in line.split('\t')]
            processed_lines.append(' '.join(cells))
            max_columns = max(max_columns, len(cells))
        
        processed_content = '\n'.join(processed_lines)
        metadata = {
            'rows': len(processed_lines),
            'columns': max_columns,
            'has_headers': True  # Assume first row is headers for TSV
        }
        
        return processed_content, metadata
    
    def _check_cache(self, contents: List[str], content_type: str) -> Tuple[Dict[int, EmbeddingResult], List[Tuple[int, str]]]:
        """Check cache for existing embeddings"""
        cached_results = {}
        uncached_items = []
        
        for idx, content in enumerate(contents):
            cache_key = self._generate_cache_key(content, content_type)
            
            if cache_key in self.embedding_cache:
                cached_results[idx] = self.embedding_cache[cache_key]
            else:
                uncached_items.append((idx, content))
        
        return cached_results, uncached_items
    
    def _cache_embedding(self, content: str, embedding_result: EmbeddingResult):
        """Cache embedding result"""
        cache_key = self._generate_cache_key(content, embedding_result.content_type)
        
        # Implement LRU cache behavior
        if len(self.embedding_cache) >= self.cache_size:
            # Remove oldest entry
            oldest_key = next(iter(self.embedding_cache))
            del self.embedding_cache[oldest_key]
        
        self.embedding_cache[cache_key] = embedding_result
    
    def _generate_cache_key(self, content: str, content_type: str) -> str:
        """Generate cache key for content"""
        content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
        return f"{content_type}:{self.default_model}:{content_hash}"
    
    def get_embedding_stats(self) -> Dict[str, Any]:
        """Get embedding service statistics"""
        return {
            'cache_size': len(self.embedding_cache),
            'cache_limit': self.cache_size,
            'default_model': self.default_model,
            'models_available': {
                'text_model': self.text_model is not None,
                'code_model': self.code_model is not None and self.code_model != self.text_model
            },
            'batch_size': self.batch_size
        }
    
    def clear_cache(self):
        """Clear embedding cache"""
        self.embedding_cache.clear()
        logger.info("Embedding cache cleared")

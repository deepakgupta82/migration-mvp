"""
Semantic Chunking Utility
Advanced text chunking based on semantic boundaries instead of word count
"""

import re
import logging
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class SemanticChunk:
    """Represents a semantically coherent text chunk"""
    content: str
    start_index: int
    end_index: int
    topic_score: float
    coherence_score: float
    metadata: Dict[str, Any]

class SemanticChunker:
    """Advanced text chunking based on semantic boundaries"""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.sentence_model = None
        self.min_chunk_size = 100  # Minimum characters per chunk
        self.max_chunk_size = 2000  # Maximum characters per chunk
        self.overlap_size = 50  # Overlap between chunks
        self.coherence_threshold = 0.3  # Minimum coherence score
        
        # Initialize sentence transformer if available
        try:
            from sentence_transformers import SentenceTransformer
            self.sentence_model = SentenceTransformer(model_name)
            logger.info(f"Initialized SentenceTransformer with model: {model_name}")
        except ImportError:
            logger.warning("sentence-transformers not available, falling back to rule-based chunking")
        except Exception as e:
            logger.error(f"Error initializing SentenceTransformer: {str(e)}")
    
    def chunk_text(self, text: str, chunk_method: str = "semantic") -> List[SemanticChunk]:
        """Chunk text using specified method"""
        if chunk_method == "semantic" and self.sentence_model is not None:
            return self._semantic_chunking(text)
        elif chunk_method == "hybrid":
            return self._hybrid_chunking(text)
        else:
            return self._rule_based_chunking(text)
    
    def _semantic_chunking(self, text: str) -> List[SemanticChunk]:
        """Chunk text based on semantic boundaries using sentence embeddings"""
        try:
            # Split text into sentences
            sentences = self._split_into_sentences(text)
            if len(sentences) < 2:
                return [SemanticChunk(
                    content=text,
                    start_index=0,
                    end_index=len(text),
                    topic_score=1.0,
                    coherence_score=1.0,
                    metadata={"method": "semantic", "sentence_count": len(sentences)}
                )]
            
            # Generate embeddings for sentences
            embeddings = self.sentence_model.encode(sentences)
            
            # Calculate semantic similarity between adjacent sentences
            similarities = self._calculate_similarities(embeddings)
            
            # Find semantic boundaries (low similarity points)
            boundaries = self._find_semantic_boundaries(similarities, sentences)
            
            # Create chunks based on boundaries
            chunks = self._create_chunks_from_boundaries(text, sentences, boundaries)
            
            # Post-process chunks (merge small chunks, split large ones)
            chunks = self._post_process_chunks(chunks)
            
            return chunks
        
        except Exception as e:
            logger.error(f"Error in semantic chunking: {str(e)}")
            return self._rule_based_chunking(text)
    
    def _hybrid_chunking(self, text: str) -> List[SemanticChunk]:
        """Combine semantic and rule-based chunking"""
        # Start with semantic chunking
        if self.sentence_model is not None:
            semantic_chunks = self._semantic_chunking(text)
            
            # Apply rule-based refinements
            refined_chunks = []
            for chunk in semantic_chunks:
                if len(chunk.content) > self.max_chunk_size:
                    # Split large chunks using rule-based method
                    sub_chunks = self._rule_based_chunking(chunk.content)
                    refined_chunks.extend(sub_chunks)
                else:
                    refined_chunks.append(chunk)
            
            return refined_chunks
        else:
            return self._rule_based_chunking(text)
    
    def _rule_based_chunking(self, text: str) -> List[SemanticChunk]:
        """Fallback rule-based chunking using structural markers"""
        chunks = []
        
        # Split by major structural markers first
        major_sections = self._split_by_structural_markers(text)
        
        for section_start, section_text in major_sections:
            if len(section_text) <= self.max_chunk_size:
                # Section is small enough, create single chunk
                chunks.append(SemanticChunk(
                    content=section_text,
                    start_index=section_start,
                    end_index=section_start + len(section_text),
                    topic_score=0.8,
                    coherence_score=0.7,
                    metadata={"method": "rule_based", "type": "section"}
                ))
            else:
                # Section is too large, split further
                sub_chunks = self._split_large_section(section_text, section_start)
                chunks.extend(sub_chunks)
        
        return chunks
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences using regex patterns"""
        # Enhanced sentence splitting patterns
        sentence_endings = r'[.!?]+(?:\s+|$)'
        sentences = re.split(sentence_endings, text)
        
        # Clean and filter sentences
        sentences = [s.strip() for s in sentences if s.strip()]
        
        # Handle edge cases where sentences are too short
        filtered_sentences = []
        current_sentence = ""
        
        for sentence in sentences:
            current_sentence += sentence + " "
            if len(current_sentence.strip()) >= 20:  # Minimum sentence length
                filtered_sentences.append(current_sentence.strip())
                current_sentence = ""
        
        # Add remaining text if any
        if current_sentence.strip():
            if filtered_sentences:
                filtered_sentences[-1] += " " + current_sentence.strip()
            else:
                filtered_sentences.append(current_sentence.strip())
        
        return filtered_sentences
    
    def _calculate_similarities(self, embeddings: np.ndarray) -> List[float]:
        """Calculate cosine similarities between adjacent sentence embeddings"""
        similarities = []
        
        for i in range(len(embeddings) - 1):
            # Calculate cosine similarity
            similarity = np.dot(embeddings[i], embeddings[i + 1]) / (
                np.linalg.norm(embeddings[i]) * np.linalg.norm(embeddings[i + 1])
            )
            similarities.append(similarity)
        
        return similarities
    
    def _find_semantic_boundaries(self, similarities: List[float], sentences: List[str]) -> List[int]:
        """Find semantic boundaries based on similarity scores"""
        boundaries = [0]  # Always start with first sentence
        
        if len(similarities) == 0:
            boundaries.append(len(sentences))
            return boundaries
        
        # Calculate threshold for boundary detection
        mean_similarity = np.mean(similarities)
        std_similarity = np.std(similarities)
        threshold = mean_similarity - (0.5 * std_similarity)
        
        # Find points where similarity drops significantly
        for i, similarity in enumerate(similarities):
            if similarity < threshold:
                boundaries.append(i + 1)
        
        # Ensure we don't have too many small chunks
        boundaries = self._merge_close_boundaries(boundaries, sentences)
        
        # Always end with last sentence
        if boundaries[-1] != len(sentences):
            boundaries.append(len(sentences))
        
        return boundaries
    
    def _merge_close_boundaries(self, boundaries: List[int], sentences: List[str]) -> List[int]:
        """Merge boundaries that would create chunks that are too small"""
        merged_boundaries = [boundaries[0]]
        
        for i in range(1, len(boundaries)):
            # Calculate text length between current and previous boundary
            start_idx = merged_boundaries[-1]
            end_idx = boundaries[i]
            chunk_text = " ".join(sentences[start_idx:end_idx])
            
            if len(chunk_text) >= self.min_chunk_size:
                merged_boundaries.append(boundaries[i])
            # If chunk is too small, skip this boundary (merge with previous)
        
        return merged_boundaries
    
    def _create_chunks_from_boundaries(self, text: str, sentences: List[str], boundaries: List[int]) -> List[SemanticChunk]:
        """Create semantic chunks based on sentence boundaries"""
        chunks = []
        
        for i in range(len(boundaries) - 1):
            start_sentence_idx = boundaries[i]
            end_sentence_idx = boundaries[i + 1]
            
            # Get chunk sentences
            chunk_sentences = sentences[start_sentence_idx:end_sentence_idx]
            chunk_content = " ".join(chunk_sentences)
            
            # Find start and end positions in original text
            start_pos = text.find(chunk_sentences[0])
            end_pos = start_pos + len(chunk_content)
            
            # Calculate coherence score (simplified)
            coherence_score = self._calculate_chunk_coherence(chunk_sentences)
            
            chunks.append(SemanticChunk(
                content=chunk_content,
                start_index=start_pos,
                end_index=end_pos,
                topic_score=0.8,  # Placeholder - could be calculated using topic modeling
                coherence_score=coherence_score,
                metadata={
                    "method": "semantic",
                    "sentence_count": len(chunk_sentences),
                    "boundary_start": start_sentence_idx,
                    "boundary_end": end_sentence_idx
                }
            ))
        
        return chunks
    
    def _calculate_chunk_coherence(self, sentences: List[str]) -> float:
        """Calculate coherence score for a chunk"""
        if len(sentences) <= 1:
            return 1.0
        
        if self.sentence_model is None:
            return 0.7  # Default coherence for rule-based chunks
        
        try:
            # Calculate average pairwise similarity within chunk
            embeddings = self.sentence_model.encode(sentences)
            similarities = []
            
            for i in range(len(embeddings)):
                for j in range(i + 1, len(embeddings)):
                    similarity = np.dot(embeddings[i], embeddings[j]) / (
                        np.linalg.norm(embeddings[i]) * np.linalg.norm(embeddings[j])
                    )
                    similarities.append(similarity)
            
            return float(np.mean(similarities)) if similarities else 0.5
        
        except Exception as e:
            logger.error(f"Error calculating chunk coherence: {str(e)}")
            return 0.5
    
    def _post_process_chunks(self, chunks: List[SemanticChunk]) -> List[SemanticChunk]:
        """Post-process chunks to ensure size constraints"""
        processed_chunks = []
        
        for chunk in chunks:
            if len(chunk.content) < self.min_chunk_size and processed_chunks:
                # Merge with previous chunk
                prev_chunk = processed_chunks[-1]
                merged_content = prev_chunk.content + " " + chunk.content
                merged_chunk = SemanticChunk(
                    content=merged_content,
                    start_index=prev_chunk.start_index,
                    end_index=chunk.end_index,
                    topic_score=(prev_chunk.topic_score + chunk.topic_score) / 2,
                    coherence_score=(prev_chunk.coherence_score + chunk.coherence_score) / 2,
                    metadata={
                        "method": "semantic_merged",
                        "merged_from": [prev_chunk.metadata, chunk.metadata]
                    }
                )
                processed_chunks[-1] = merged_chunk
            
            elif len(chunk.content) > self.max_chunk_size:
                # Split large chunk
                sub_chunks = self._split_large_chunk(chunk)
                processed_chunks.extend(sub_chunks)
            
            else:
                processed_chunks.append(chunk)
        
        return processed_chunks
    
    def _split_large_chunk(self, chunk: SemanticChunk) -> List[SemanticChunk]:
        """Split a chunk that's too large"""
        # Simple splitting by sentences or paragraphs
        sentences = self._split_into_sentences(chunk.content)
        
        if len(sentences) <= 1:
            # Can't split further, return as is
            return [chunk]
        
        # Split into roughly equal parts
        mid_point = len(sentences) // 2
        
        first_half = " ".join(sentences[:mid_point])
        second_half = " ".join(sentences[mid_point:])
        
        chunks = []
        
        if len(first_half) >= self.min_chunk_size:
            chunks.append(SemanticChunk(
                content=first_half,
                start_index=chunk.start_index,
                end_index=chunk.start_index + len(first_half),
                topic_score=chunk.topic_score,
                coherence_score=chunk.coherence_score * 0.9,  # Slightly lower due to splitting
                metadata={"method": "semantic_split", "part": "first", "original_metadata": chunk.metadata}
            ))
        
        if len(second_half) >= self.min_chunk_size:
            chunks.append(SemanticChunk(
                content=second_half,
                start_index=chunk.start_index + len(first_half),
                end_index=chunk.end_index,
                topic_score=chunk.topic_score,
                coherence_score=chunk.coherence_score * 0.9,
                metadata={"method": "semantic_split", "part": "second", "original_metadata": chunk.metadata}
            ))
        
        return chunks if chunks else [chunk]
    
    def _split_by_structural_markers(self, text: str) -> List[Tuple[int, str]]:
        """Split text by structural markers like headers, paragraphs"""
        sections = []
        
        # Split by double newlines (paragraphs)
        paragraphs = text.split('\n\n')
        current_pos = 0
        
        for paragraph in paragraphs:
            if paragraph.strip():
                sections.append((current_pos, paragraph.strip()))
            current_pos += len(paragraph) + 2  # +2 for the double newline
        
        return sections if sections else [(0, text)]
    
    def _split_large_section(self, text: str, start_offset: int) -> List[SemanticChunk]:
        """Split a large section into smaller chunks"""
        chunks = []
        words = text.split()
        
        current_chunk = []
        current_length = 0
        
        for word in words:
            current_chunk.append(word)
            current_length += len(word) + 1  # +1 for space
            
            if current_length >= self.max_chunk_size:
                chunk_text = " ".join(current_chunk)
                chunks.append(SemanticChunk(
                    content=chunk_text,
                    start_index=start_offset,
                    end_index=start_offset + len(chunk_text),
                    topic_score=0.7,
                    coherence_score=0.6,
                    metadata={"method": "rule_based_split", "word_count": len(current_chunk)}
                ))
                
                # Add overlap
                overlap_words = current_chunk[-self.overlap_size//10:] if len(current_chunk) > self.overlap_size//10 else []
                current_chunk = overlap_words
                current_length = sum(len(word) + 1 for word in overlap_words)
                start_offset += len(chunk_text) - len(" ".join(overlap_words))
        
        # Add remaining words as final chunk
        if current_chunk:
            chunk_text = " ".join(current_chunk)
            chunks.append(SemanticChunk(
                content=chunk_text,
                start_index=start_offset,
                end_index=start_offset + len(chunk_text),
                topic_score=0.7,
                coherence_score=0.6,
                metadata={"method": "rule_based_final", "word_count": len(current_chunk)}
            ))
        
        return chunks

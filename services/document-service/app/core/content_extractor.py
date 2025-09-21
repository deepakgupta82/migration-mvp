"""
Content Extraction Module for Document Processing
Extracts summary_text, categories, and structure_metadata from processed documents
"""

import os
import logging
import json
import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import asyncio
import httpx

# Import LLM analyzer for enhanced processing
try:
    from .llm_content_analyzer import LLMContentAnalyzer
    LLM_ANALYZER_AVAILABLE = True
except ImportError:
    LLM_ANALYZER_AVAILABLE = False
    # logger.warning("LLM Content Analyzer not available, falling back to extractive methods")

logger = logging.getLogger("document-service.content-extractor")

class ContentExtractor:
    """
    Extracts content features from processed documents:
    - summary_text: AI-generated summary of document content
    - categories: Array of categories/tags for document classification
    - structure_metadata: JSON metadata containing document structure information
    """

    def __init__(self):
        self.project_service_url = os.getenv("PROJECT_SERVICE_URL", "http://localhost:8002")
        self.storage_url = os.getenv("STORAGE_SERVICE_URL", "http://localhost:8010")
        self.auth_token = os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')
        self.http_timeout = httpx.Timeout(30.0, connect=10.0)

        # Content extraction settings
        self.max_summary_length = int(os.getenv("MAX_SUMMARY_LENGTH", "500"))
        self.max_categories = int(os.getenv("MAX_CATEGORIES", "10"))
        self.min_category_score = float(os.getenv("MIN_CATEGORY_SCORE", "0.1"))

        # LLM analyzer for enhanced processing
        self.enable_llm_analysis = os.getenv("ENABLE_LLM_CONTENT_ANALYSIS", "true").lower() == "true"
        self.llm_analyzer = None
        if self.enable_llm_analysis and LLM_ANALYZER_AVAILABLE:
            try:
                self.llm_analyzer = LLMContentAnalyzer()
                logger.info("LLM Content Analyzer initialized for enhanced processing")
            except Exception as e:
                logger.warning(f"Failed to initialize LLM Content Analyzer: {e}")
                self.llm_analyzer = None

    async def extract_and_update_project_file(
        self,
        project_id: str,
        filename: str,
        processed_content: Optional[str] = None,
        structured_result: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extract content features and update project file in project-service
        Uses LLM-enhanced analysis when available, falls back to extractive methods

        Args:
            project_id: Project identifier
            filename: Original filename
            processed_content: Processed markdown/text content
            structured_result: Optional structured processing result
            correlation_id: Request correlation ID

        Returns:
            Dict with extraction results
        """
        try:
            logger.info(f"Extracting content for {filename} in project {project_id}")

            # Fetch processed content if not provided
            if not processed_content:
                processed_content = await self._fetch_processed_content(project_id, filename, correlation_id)
                if not processed_content:
                    logger.warning(f"Could not fetch processed content for {filename}")
                    return {
                        "status": "error",
                        "filename": filename,
                        "error": "Could not fetch processed content"
                    }

            # Use LLM-enhanced analysis if available
            if self.llm_analyzer and self.enable_llm_analysis:
                try:
                    logger.info(f"Using LLM-enhanced analysis for {filename}")
                    analysis_result = await self.llm_analyzer.analyze_document_content(
                        project_id=project_id,
                        filename=filename,
                        processed_content=processed_content,
                        structured_result=structured_result,
                        analysis_type="comprehensive",
                        correlation_id=correlation_id
                    )

                    if analysis_result["status"] == "success":
                        # Update project file with LLM-enhanced results
                        update_success = await self.llm_analyzer.update_project_file_with_analysis(
                            project_id, filename, analysis_result, correlation_id
                        )

                        if update_success:
                            logger.info(f"Successfully updated project file {filename} with LLM-enhanced analysis")
                            return {
                                "status": "success",
                                "filename": filename,
                                "method": "llm_enhanced",
                                "summary_length": len(analysis_result.get("final_summary", "")),
                                "categories_count": len(analysis_result.get("final_categories", [])),
                                "quality_score": analysis_result.get("quality_score", 0.0),
                                "processing_methods": analysis_result.get("processing_methods", [])
                            }
                        else:
                            logger.warning(f"Failed to update project file with LLM analysis, falling back to extractive")
                    else:
                        logger.warning(f"LLM analysis failed for {filename}, falling back to extractive methods")

                except Exception as e:
                    logger.warning(f"LLM-enhanced analysis failed for {filename}: {e}, falling back to extractive")

            # Fallback to traditional extractive methods
            logger.info(f"Using extractive analysis for {filename}")
            summary_text = await self._extract_summary(processed_content)
            categories = await self._extract_categories(processed_content)
            structure_metadata = self._extract_structure_metadata(filename, processed_content, structured_result)

            # Prepare update data
            update_data = {
                "summary_text": summary_text,
                "categories": categories,
                "structure_metadata": structure_metadata
            }

            # Update project file via API
            success = await self._update_project_file(project_id, filename, update_data, correlation_id)

            if success:
                logger.info(f"Successfully updated project file {filename} with extractive content analysis")
                return {
                    "status": "success",
                    "filename": filename,
                    "method": "extractive",
                    "summary_length": len(summary_text) if summary_text else 0,
                    "categories_count": len(categories),
                    "has_structure_metadata": structure_metadata is not None
                }
            else:
                logger.error(f"Failed to update project file {filename}")
                return {
                    "status": "error",
                    "filename": filename,
                    "error": "Failed to update project file"
                }

        except Exception as e:
            logger.error(f"Error extracting content for {filename}: {e}")
            return {
                "status": "error",
                "filename": filename,
                "error": str(e)
            }

    async def _extract_summary(self, content: str) -> Optional[str]:
        """Extract summary from document content using extractive summarization"""
        try:
            if not content or len(content.strip()) < 50:
                return None

            # Simple extractive summarization
            sentences = self._split_into_sentences(content)

            if len(sentences) <= 3:
                # For short documents, return cleaned content
                return self._clean_text(content)[:self.max_summary_length]

            # Score sentences based on position and length
            scored_sentences = []
            for i, sentence in enumerate(sentences):
                score = 0.0

                # Position scoring (first and last sentences often important)
                if i == 0:
                    score += 0.3
                elif i == len(sentences) - 1:
                    score += 0.2

                # Length scoring (prefer substantial sentences)
                words = sentence.split()
                if 10 <= len(words) <= 30:
                    score += 0.2
                elif len(words) > 30:
                    score -= 0.1

                # Keyword scoring (sentences with important words)
                important_keywords = [
                    'summary', 'conclusion', 'overview', 'purpose', 'goal',
                    'objective', 'scope', 'requirement', 'implementation',
                    'result', 'outcome', 'recommendation', 'finding'
                ]
                sentence_lower = sentence.lower()
                keyword_count = sum(1 for keyword in important_keywords if keyword in sentence_lower)
                score += keyword_count * 0.1

                scored_sentences.append((sentence, score))

            # Sort by score and select top sentences
            scored_sentences.sort(key=lambda x: x[1], reverse=True)
            selected_sentences = scored_sentences[:5]  # Top 5 sentences

            # Sort selected sentences by original position for coherence
            selected_sentences.sort(key=lambda x: sentences.index(x[0]))

            # Combine into summary
            summary = ' '.join(sentence for sentence, _ in selected_sentences)
            summary = self._clean_text(summary)

            return summary[:self.max_summary_length]

        except Exception as e:
            logger.warning(f"Error extracting summary: {e}")
            # Fallback: return first few sentences
            try:
                sentences = self._split_into_sentences(content)
                if sentences:
                    summary = ' '.join(sentences[:3])
                    return self._clean_text(summary)[:self.max_summary_length]
            except:
                pass
            return None

    async def _extract_categories(self, content: str) -> List[str]:
        """Extract categories/tags from document content using keyword analysis"""
        try:
            if not content or len(content.strip()) < 100:
                return []

            # Extract keywords using frequency and position analysis
            words = self._extract_keywords(content)

            # Score keywords
            scored_keywords = []
            for word in words:
                score = self._score_keyword(word, content)
                if score >= self.min_category_score:
                    scored_keywords.append((word, score))

            # Sort by score and return top categories
            scored_keywords.sort(key=lambda x: x[1], reverse=True)
            categories = [word for word, _ in scored_keywords[:self.max_categories]]

            # Clean and normalize categories
            categories = [self._normalize_category(cat) for cat in categories if cat]
            categories = list(set(categories))  # Remove duplicates

            return categories

        except Exception as e:
            logger.warning(f"Error extracting categories: {e}")
            return []

    def _extract_structure_metadata(
        self,
        filename: str,
        content: str,
        structured_result: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Extract structure metadata from document"""
        try:
            metadata = {
                "filename": filename,
                "extraction_timestamp": datetime.now().isoformat(),
                "document_type": self._detect_document_type(filename),
                "language": "en",  # Default to English
                "total_pages": 1,  # Default
                "sections": []
            }

            # Extract sections from content
            sections = self._extract_sections(content)
            if sections:
                metadata["sections"] = sections

            # Extract additional metadata from structured result if available
            if structured_result:
                # Handle different types of structured_result
                structured_dict = {}
                
                # Convert ProcessingResult object to dict if needed
                if isinstance(structured_result, dict):
                    structured_dict = structured_result
                elif hasattr(structured_result, '__dict__'):
                    # If it's a dataclass or object with attributes, convert to dict
                    structured_dict = structured_result.__dict__
                else:
                    # For other object types, try to extract attributes safely
                    try:
                        # Try common attributes
                        if hasattr(structured_result, 'processing_stats'):
                            structured_dict['processing_stats'] = structured_result.processing_stats
                        if hasattr(structured_result, 'document_metadata'):
                            structured_dict['document_metadata'] = structured_result.document_metadata
                    except (AttributeError, TypeError):
                        # If we can't extract anything, use empty dict
                        structured_dict = {}
                    
                # Try to extract processing stats
                try:
                    if "processing_stats" in structured_dict:
                        stats = structured_dict["processing_stats"]
                        metadata.update({
                            "total_pages": stats.get("pages_processed", 1),
                            "element_count": stats.get("total_elements", 0),
                            "text_length": stats.get("total_text_length", 0)
                        })
                    elif hasattr(structured_result, 'processing_stats'):
                        stats = structured_result.processing_stats
                        if hasattr(stats, '__dict__'):
                            stats_dict = stats.__dict__
                            metadata.update({
                                "total_pages": stats_dict.get("pages_processed", 1),
                                "element_count": stats_dict.get("total_elements", 0),
                                "text_length": stats_dict.get("total_text_length", 0)
                            })
                except (AttributeError, KeyError, TypeError) as e:
                    logger.debug(f"Could not extract processing_stats: {e}")

                # Try to extract document metadata
                try:
                    if "document_metadata" in structured_dict:
                        doc_meta = structured_dict["document_metadata"]
                        # Handle doc_meta that might not be a dict
                        if isinstance(doc_meta, dict):
                            if "language" in doc_meta:
                                metadata["language"] = doc_meta["language"]
                            if "page_count" in doc_meta:
                                metadata["total_pages"] = doc_meta["page_count"]
                        elif hasattr(doc_meta, '__dict__'):
                            doc_meta_dict = doc_meta.__dict__
                            if "language" in doc_meta_dict:
                                metadata["language"] = doc_meta_dict["language"]
                            if "page_count" in doc_meta_dict:
                                metadata["total_pages"] = doc_meta_dict["page_count"]
                        else:
                            # Try direct attribute access for non-dict objects
                            if hasattr(doc_meta, 'language'):
                                metadata["language"] = doc_meta.language
                            if hasattr(doc_meta, 'page_count'):
                                metadata["total_pages"] = doc_meta.page_count
                    elif hasattr(structured_result, 'document_metadata'):
                        doc_meta = structured_result.document_metadata
                        if hasattr(doc_meta, '__dict__'):
                            doc_meta_dict = doc_meta.__dict__
                            if "language" in doc_meta_dict:
                                metadata["language"] = doc_meta_dict["language"]
                            if "page_count" in doc_meta_dict:
                                metadata["total_pages"] = doc_meta_dict["page_count"]
                        else:
                            # Try direct attribute access
                            if hasattr(doc_meta, 'language'):
                                metadata["language"] = doc_meta.language
                            if hasattr(doc_meta, 'page_count'):
                                metadata["total_pages"] = doc_meta.page_count
                except (AttributeError, KeyError, TypeError) as e:
                    logger.debug(f"Could not extract document_metadata: {e}")

            return metadata

        except Exception as e:
            logger.warning(f"Error extracting structure metadata: {e}")
            return None

    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences"""
        # Simple sentence splitting
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        return [s.strip() for s in sentences if s.strip()]

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        if not text:
            return ""

        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text.strip())

        # Remove markdown formatting
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # Bold
        text = re.sub(r'\*([^*]+)\*', r'\1', text)      # Italic
        text = re.sub(r'`([^`]+)`', r'\1', text)        # Code
        text = re.sub(r'#+\s*', '', text)               # Headers
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)  # Links

        return text.strip()

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract potential keywords from text"""
        # Clean text
        text = self._clean_text(text).lower()

        # Remove stop words
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
            'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these',
            'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him',
            'her', 'us', 'them', 'my', 'your', 'his', 'its', 'our', 'their'
        }

        words = re.findall(r'\b\w+\b', text)
        keywords = [word for word in words if len(word) > 3 and word not in stop_words]

        return keywords

    def _score_keyword(self, word: str, content: str) -> float:
        """Score a keyword based on frequency and context"""
        content_lower = content.lower()
        word_lower = word.lower()

        # Frequency score
        frequency = content_lower.count(word_lower)
        total_words = len(re.findall(r'\b\w+\b', content_lower))
        frequency_score = frequency / total_words if total_words > 0 else 0

        # Position score (keywords at the beginning are often more important)
        first_occurrence = content_lower.find(word_lower)
        position_score = 1.0 if first_occurrence < len(content) * 0.1 else 0.5

        # Length score (prefer meaningful words)
        length_score = min(len(word) / 10.0, 1.0)

        # Capitalization score (proper nouns often important)
        if word[0].isupper():
            capitalization_score = 0.8
        else:
            capitalization_score = 0.5

        # Combine scores
        total_score = (
            frequency_score * 0.4 +
            position_score * 0.2 +
            length_score * 0.2 +
            capitalization_score * 0.2
        )

        return total_score

    def _normalize_category(self, category: str) -> str:
        """Normalize category name"""
        if not category:
            return ""

        # Clean and format
        category = category.strip().lower()
        category = re.sub(r'[^\w\s-]', '', category)  # Remove special chars
        category = re.sub(r'\s+', '_', category)      # Replace spaces with underscores

        return category

    def _detect_document_type(self, filename: str) -> str:
        """Detect document type from filename"""
        filename_lower = filename.lower()

        if filename_lower.endswith('.pdf'):
            return 'pdf'
        elif filename_lower.endswith(('.docx', '.doc')):
            return 'word'
        elif filename_lower.endswith('.pptx'):
            return 'powerpoint'
        elif filename_lower.endswith('.xlsx'):
            return 'excel'
        elif filename_lower.endswith('.txt'):
            return 'text'
        elif filename_lower.endswith('.md'):
            return 'markdown'
        else:
            return 'unknown'

    def _extract_sections(self, content: str) -> List[Dict[str, Any]]:
        """Extract document sections from content"""
        sections = []

        # Look for markdown headers
        header_pattern = r'^(#{1,6})\s+(.+)$'
        lines = content.split('\n')

        current_section = None
        for i, line in enumerate(lines):
            match = re.match(header_pattern, line.strip())
            if match:
                level = len(match.group(1))
                title = match.group(2).strip()

                if current_section:
                    # End previous section
                    current_section["end_line"] = i - 1
                    sections.append(current_section)

                # Start new section
                current_section = {
                    "title": title,
                    "level": level,
                    "start_line": i,
                    "page": 1  # Default page
                }

        # Close last section
        if current_section:
            current_section["end_line"] = len(lines) - 1
            sections.append(current_section)

        return sections

    async def _update_project_file(
        self,
        project_id: str,
        filename: str,
        update_data: Dict[str, Any],
        correlation_id: Optional[str] = None
    ) -> bool:
        """Update project file in project-service via API"""
        try:
            # First, find the project file by filename
            async with httpx.AsyncClient(timeout=self.http_timeout) as client:
                headers = {
                    "Authorization": f"Bearer {self.auth_token}",
                    "Content-Type": "application/json"
                }
                if correlation_id:
                    headers["X-Correlation-ID"] = correlation_id

                # Get project files to find the file ID
                response = await client.get(
                    f"{self.project_service_url}/api/projects/{project_id}/files",
                    headers=headers
                )

                if response.status_code != 200:
                    logger.error(f"Failed to get project files: {response.status_code}")
                    return False

                files = response.json()
                file_record = None
                for file in files:
                    if file.get("filename") == filename:
                        file_record = file
                        break

                if not file_record:
                    logger.warning(f"Project file not found for {filename}")
                    return False

                file_id = file_record["id"]

                # Update the file with extracted content (only update provided fields)
                update_response = await client.put(
                    f"{self.project_service_url}/api/projects/{project_id}/files/{file_id}",
                    json=update_data,
                    headers=headers
                )

                if update_response.status_code == 200:
                    logger.info(f"Successfully updated project file {file_id}")
                    return True
                else:
                    logger.error(f"Failed to update project file: {update_response.status_code} - {update_response.text}")
                    return False

        except Exception as e:
            logger.error(f"Error updating project file: {e}")
            return False

    async def _fetch_processed_content(
        self,
        project_id: str,
        filename: str,
        correlation_id: Optional[str] = None
    ) -> Optional[str]:
        """Fetch processed content from storage service"""
        try:
            # Try to get the processed markdown file
            base_name = os.path.splitext(filename)[0]
            processed_filename = f"{base_name}.md"

            async with httpx.AsyncClient(timeout=self.http_timeout) as client:
                headers = {
                    "Authorization": f"Bearer {self.auth_token}"
                }
                if correlation_id:
                    headers["X-Correlation-ID"] = correlation_id

                # Try to get processed markdown
                response = await client.get(
                    f"{self.storage_url}/api/storage/projects/{project_id}/download/uploads_parsed/{processed_filename}",
                    headers=headers
                )

                if response.status_code == 200:
                    return response.text

                # If markdown not found, try structured JSONL
                structured_filename = f"{base_name}_structured.jsonl"
                response = await client.get(
                    f"{self.storage_url}/api/storage/projects/{project_id}/download/structured/{structured_filename}",
                    headers=headers
                )

                if response.status_code == 200:
                    # Extract text from JSONL
                    jsonl_content = response.text
                    text_parts = []
                    for line in jsonl_content.strip().split('\n'):
                        if line.strip():
                            try:
                                data = json.loads(line)
                                if data.get('type') == 'element' and 'text' in data.get('data', {}):
                                    text_parts.append(data['data']['text'])
                            except json.JSONDecodeError:
                                continue
                    return '\n\n'.join(text_parts)

                logger.warning(f"Could not find processed content for {filename}")
                return None

        except Exception as e:
            logger.error(f"Error fetching processed content for {filename}: {e}")
            return None

    async def process_batch_extraction(
        self,
        project_id: str,
        file_data: List[Dict[str, Any]],
        correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process batch content extraction for multiple files
        Uses LLM-enhanced analysis when available for better quality

        Args:
            project_id: Project identifier
            file_data: List of dicts with 'filename', 'content', 'structured_result'
            correlation_id: Request correlation ID

        Returns:
            Dict with batch processing results
        """
        logger.info(f"Starting batch content extraction for {len(file_data)} files")

        # Use LLM analyzer for bulk processing if available
        if self.llm_analyzer and self.enable_llm_analysis and len(file_data) > 1:
            try:
                logger.info(f"Using LLM-enhanced batch processing for {len(file_data)} files")
                batch_result = await self.llm_analyzer.analyze_documents_batch(
                    project_id=project_id,
                    file_data=file_data,
                    analysis_type="comprehensive",
                    correlation_id=correlation_id,
                    max_concurrent=min(10, len(file_data))  # Adaptive concurrency
                )

                if batch_result["status"] == "completed":
                    # Update project files with batch results
                    update_tasks = []
                    for result in batch_result["results"]:
                        if result["status"] == "success":
                            update_tasks.append(
                                self.llm_analyzer.update_project_file_with_analysis(
                                    project_id, result["filename"], result, correlation_id
                                )
                            )

                    if update_tasks:
                        update_results = await asyncio.gather(*update_tasks, return_exceptions=True)
                        successful_updates = sum(1 for r in update_results if not isinstance(r, Exception) and r)

                        logger.info(f"Batch LLM analysis completed: {batch_result['successful_analyses']}/{batch_result['total_files']} analyses, {successful_updates} updates")

                        return {
                            "status": "completed",
                            "method": "llm_batch",
                            "total_files": batch_result["total_files"],
                            "success_count": batch_result["successful_analyses"],
                            "error_count": batch_result["failed_analyses"],
                            "update_success_count": successful_updates,
                            "results": batch_result["results"],
                            "errors": batch_result["errors"],
                            "processing_time": batch_result.get("total_processing_time", 0.0)
                        }

            except Exception as e:
                logger.warning(f"LLM batch processing failed: {e}, falling back to individual processing")

        # Fallback to individual processing
        logger.info(f"Using individual processing for {len(file_data)} files")
        results = []
        success_count = 0
        error_count = 0

        # Process files concurrently with semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(min(5, len(file_data)))  # Adaptive concurrency

        async def process_single_file(file_info: Dict[str, Any]):
            async with semaphore:
                return await self.extract_and_update_project_file(
                    project_id=project_id,
                    filename=file_info["filename"],
                    processed_content=file_info["content"],
                    structured_result=file_info.get("structured_result"),
                    correlation_id=correlation_id
                )

        # Process all files concurrently
        tasks = [process_single_file(file_info) for file_info in file_data]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for i, result in enumerate(batch_results):
            if isinstance(result, Exception):
                logger.error(f"Batch extraction error for file {i}: {result}")
                results.append({
                    "status": "error",
                    "filename": file_data[i]["filename"],
                    "error": str(result)
                })
                error_count += 1
            else:
                results.append(result)
                if result["status"] == "success":
                    success_count += 1
                else:
                    error_count += 1

        logger.info(f"Individual batch content extraction completed: {success_count} success, {error_count} errors")

        return {
            "status": "completed",
            "method": "individual",
            "total_files": len(file_data),
            "success_count": success_count,
            "error_count": error_count,
            "results": results
        }
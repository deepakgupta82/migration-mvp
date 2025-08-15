"""
Entity Extraction Agent for Dynamic Infrastructure Discovery
Uses AI to identify and extract infrastructure entities and relationships from documents
"""

import json
import logging
import os
import asyncio
from typing import Dict, Any, List, Tuple
from langchain.schema import HumanMessage, SystemMessage
from langchain.schema.language_model import BaseLanguageModel

logger = logging.getLogger(__name__)

class EntityExtractionAgent:
    """AI-powered entity extraction agent for infrastructure discovery"""

    def __init__(self, llm: BaseLanguageModel, parallel_workers: int = 4, timeout_seconds: int = 30):
        if not llm:
            raise ValueError("LLM is required for entity extraction. Cannot initialize EntityExtractionAgent without a valid LLM instance.")
        self.llm = llm
        self.optimized_chunker = None
        self.parallel_extractor = None
        self.deduplicator = None
        self.parallel_workers = parallel_workers
        self.timeout_seconds = timeout_seconds
        logger.info(f"EntityExtractionAgent initialized with LLM, parallel_workers={parallel_workers}, timeout_seconds={timeout_seconds}")

        # Log LLM details if discoverable
        try:
            prov = type(llm).__name__ if llm else "None"
            model = getattr(llm, "model", None) or getattr(llm, "model_name", None) or getattr(llm, "model_id", None)
            logger.info(f"EntityExtractionAgent LLM provider={prov} model={model}")
        except Exception:
            pass

        # Check environment variables for API keys (especially for Gemini)
        import os
        api_keys_status = []
        if 'GOOGLE_API_KEY' in os.environ:
            key_preview = os.environ['GOOGLE_API_KEY'][:10] + "..." if os.environ['GOOGLE_API_KEY'] else "empty"
            api_keys_status.append(f"GOOGLE_API_KEY: {key_preview}")
        if 'OPENAI_API_KEY' in os.environ:
            key_preview = os.environ['OPENAI_API_KEY'][:10] + "..." if os.environ['OPENAI_API_KEY'] else "empty"
            api_keys_status.append(f"OPENAI_API_KEY: {key_preview}")
        
        if api_keys_status:
            logger.info(f"API Keys status: {', '.join(api_keys_status)}")
        else:
            logger.warning("No API keys found in environment variables")

        # EntityExtractionAgent initialized - ready for production use

    def _initialize_optimized_components(self):
        """Lazy initialization of optimized components"""
        if self.optimized_chunker is None:
            try:
                from app.core.semantic_chunking import OptimizedChunker
                from app.core.parallel_entity_extractor import ParallelEntityExtractor, EntityDeduplicator

                self.optimized_chunker = OptimizedChunker()
                self.parallel_extractor = ParallelEntityExtractor(max_workers=self.parallel_workers, timeout_seconds=self.timeout_seconds)
                self.deduplicator = EntityDeduplicator()
                logger.info(f"Optimized extraction components initialized (workers={self.parallel_workers}, timeout={self.timeout_seconds}s)")
            except ImportError as e:
                logger.warning(f"Could not initialize optimized components: {e}")
                self.optimized_chunker = None

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        # Rough estimate: ~4 chars per token
        try:
            return max(1, int(len(text) / 4))
        except Exception:
            return len(text)

    def extract_entities_and_relationships(self, content: str) -> Dict[str, Any]:
        """
        Extract infrastructure entities and relationships from document content
        Returns structured data with entities and their relationships
        """
        try:
            # Create the extraction prompt
            system_prompt = self._create_system_prompt()
            human_prompt = self._create_human_prompt(content)

            # Enhanced diagnostics logging
            logger.info(f"Entity extraction starting - Content length: {len(content)} chars, "
                       f"System prompt: {len(system_prompt)} chars, Human prompt: {len(human_prompt)} chars, "
                       f"Estimated tokens: {self._estimate_tokens(human_prompt)}")

            # Log LLM details for debugging
            try:
                llm_info = {
                    "type": type(self.llm).__name__,
                    "model": getattr(self.llm, "model", None) or getattr(self.llm, "model_name", None) or getattr(self.llm, "model_id", None),
                    "provider": getattr(self.llm, "_llm_type", None) or "unknown"
                }
                logger.info(f"Using LLM: {llm_info}")
            except Exception as e:
                logger.warning(f"Could not extract LLM info: {e}")

            # Log content preview for debugging (first 500 chars)
            content_preview = content[:500].replace('\n', '\\n').replace('\r', '\\r')
            logger.debug(f"Content preview: {content_preview}...")

            # === RAW PROMPT DEBUGGING ===
            logger.info("=== FULL PROMPT DEBUGGING ===")
            logger.info(f"System prompt FULL TEXT:\n{system_prompt}")
            logger.info(f"System prompt length: {len(system_prompt)} characters")
            logger.info(f"Human prompt FULL TEXT:\n{human_prompt}")
            logger.info(f"Human prompt length: {len(human_prompt)} characters")
            
            # Check for common issues
            if not system_prompt.strip():
                logger.error("⚠️ SYSTEM PROMPT IS EMPTY!")
            if not human_prompt.strip():
                logger.error("⚠️ HUMAN PROMPT IS EMPTY!")
            if len(system_prompt) + len(human_prompt) > 100000:
                logger.warning(f"⚠️ COMBINED PROMPT IS VERY LARGE: {len(system_prompt) + len(human_prompt)} chars")

            # Get AI response via LangChain
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=human_prompt)
            ]

            logger.info("Sending prompt to LLM via LangChain for entity extraction...")
            logger.info(f"Message objects: {[type(msg).__name__ for msg in messages]}")
            logger.info(f"Message count: {len(messages)}")
            
            try:
                response = self.llm.invoke(messages)
                logger.info(f"LLM invoke completed. Response type: {type(response)}")
            except Exception as invoke_error:
                logger.error(f"LLM invoke failed with error: {invoke_error}")
                logger.error(f"Error type: {type(invoke_error).__name__}")
                raise
            
            # Enhanced response metadata logging
            try:
                meta = getattr(response, 'response_metadata', None)
                if meta:
                    logger.info(f"LLM response metadata: {meta}")
                else:
                    logger.warning("No response metadata available")
                    
                # Log additional response attributes
                response_attrs = [attr for attr in dir(response) if not attr.startswith('_')]
                logger.debug(f"Available response attributes: {response_attrs}")
                
                # Check LangChain-specific attributes vs Direct API
                langchain_attrs = ['content', 'additional_kwargs', 'response_metadata', 'tool_calls', 'usage_metadata']
                for attr in langchain_attrs:
                    if hasattr(response, attr):
                        attr_val = getattr(response, attr)
                        logger.info(f"LangChain response.{attr}: {attr_val} (type: {type(attr_val)})")
                
                # Log the full response object structure for comparison with direct API
                logger.info(f"LangChain response full repr (first 1000 chars): {repr(response)[:1000]}")
                
                # Try to get any error information from response
                if hasattr(response, 'error'):
                    logger.error(f"LLM response contains error: {response.error}")
                if hasattr(response, 'finish_reason'):
                    logger.info(f"LLM finish reason: {response.finish_reason}")
                    
            except Exception as meta_error:
                logger.warning(f"Could not access response metadata: {meta_error}")

            # Enhanced empty response detection and logging
            if not hasattr(response, 'content'):
                logger.error("❌ CRITICAL: LangChain response has no 'content' attribute")
                logger.error(f"Full response object: {response}")
                logger.error(f"Response type: {type(response)}")
                logger.error(f"Response dir: {dir(response)}")
                logger.error("📝 Compare this with the direct Gemini API test results above!")
                return {
                    "entities": [],
                    "relationships": [],
                    "metadata": {
                        "extraction_status": "no_content_attribute",
                        "error": "LLM response missing content attribute",
                        "response_type": str(type(response)),
                        "response_str": str(response)[:1000]
                    }
                }
            
            if response.content is None:
                logger.error("LLM returned None content")
                logger.error(f"Response attributes: {[attr for attr in dir(response) if not attr.startswith('_')]}")
                # Try to find alternative content fields
                for alt_field in ['text', 'message', 'output', 'result']:
                    if hasattr(response, alt_field):
                        alt_content = getattr(response, alt_field)
                        logger.info(f"Found alternative content in '{alt_field}': {str(alt_content)[:200]}...")
                return {
                    "entities": [],
                    "relationships": [],
                    "metadata": {
                        "extraction_status": "none_content", 
                        "error": "LLM returned None content",
                        "response_attributes": [attr for attr in dir(response) if not attr.startswith('_')]
                    }
                }
                
            if response.content == "":
                logger.error("❌ CRITICAL: LLM returned empty string content")
                logger.error(f"Response content length: {len(response.content)}")
                logger.error(f"Response content repr: {repr(response.content)}")
                logger.error("📝 If direct Gemini API worked but this is empty - LangChain wrapper issue!")
                return {
                    "entities": [],
                    "relationships": [],
                    "metadata": {
                        "extraction_status": "empty_string_content",
                        "error": "LLM returned empty string",
                        "content_length": len(response.content),
                        "content_repr": repr(response.content)
                    }
                }
                
            if response.content.isspace():
                logger.error(f"LLM returned whitespace-only response. Content: {repr(response.content[:200])}")
                return {
                    "entities": [],
                    "relationships": [],
                    "metadata": {
                        "extraction_status": "whitespace_response",
                        "error": "LLM returned only whitespace",
                        "content_length": len(response.content),
                        "content_preview": repr(response.content[:200])
                    }
                }

            # Log successful response
            response_length = len(response.content)
            logger.info(f"LLM returned response: {response_length} characters")
            logger.debug(f"Raw response preview: {response.content[:300]}...")

            # Parse the JSON response with robust handling
            try:
                response_text = response.content.strip()
                logger.info(f"Processing LLM response for JSON extraction, length: {len(response_text)}")
                logger.debug(f"Raw AI response: {response_text[:500]}...")

                # Check for completely empty response first
                if not response_text or response_text.isspace():
                    logger.error("AI returned completely empty response after strip()")
                    raise json.JSONDecodeError("Empty response from AI", "", 0)

                # Enhanced JSON extraction from AI response with multiple strategies
                original_response = response_text
                extraction_strategy = "none"

                # Strategy 1: Extract from markdown code blocks
                if "```json" in response_text:
                    extraction_strategy = "markdown_json"
                    start = response_text.find("```json") + 7
                    end = response_text.find("```", start)
                    if end != -1:
                        response_text = response_text[start:end].strip()
                        logger.debug(f"Extracted JSON from markdown block: {len(response_text)} chars")
                elif "```" in response_text:
                    extraction_strategy = "markdown_generic"
                    start = response_text.find("```") + 3
                    # Skip any language identifier on the same line
                    newline_pos = response_text.find('\n', start)
                    if newline_pos != -1:
                        start = newline_pos + 1
                    end = response_text.find("```", start)
                    if end != -1:
                        response_text = response_text[start:end].strip()
                        logger.debug(f"Extracted JSON from generic markdown: {len(response_text)} chars")

                # Strategy 2: Clean common AI response artifacts
                if extraction_strategy == "none":
                    extraction_strategy = "cleaning"
                    response_text = response_text.replace('```json', '').replace('```', '')
                    response_text = response_text.replace('\n\n', '\n').strip()
                    logger.debug(f"Applied basic cleaning: {len(response_text)} chars")

                # Strategy 3: Find JSON boundaries
                first_brace = response_text.find('{')
                last_brace = response_text.rfind('}')

                if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                    if extraction_strategy == "cleaning":
                        extraction_strategy = "brace_extraction"
                    response_text = response_text[first_brace:last_brace + 1]
                    logger.debug(f"Extracted JSON by brace boundaries: {len(response_text)} chars")
                else:
                    # No valid JSON structure found
                    logger.error(f"No valid JSON structure found in AI response. First brace at {first_brace}, last at {last_brace}")
                    logger.error(f"Response preview: {response_text[:200]}...")
                    raise json.JSONDecodeError("No JSON braces found", response_text, 0)

                # Strategy 4: Final validation before parsing
                if not response_text or response_text.isspace():
                    logger.error("Response became empty after cleaning")
                    raise json.JSONDecodeError("Response empty after cleaning", "", 0)

                # Try to parse JSON
                logger.debug(f"Attempting JSON parsing using strategy: {extraction_strategy}")
                result = json.loads(response_text)
                
                # Log successful extraction details
                entities_count = len(result.get('entities', []))
                relationships_count = len(result.get('relationships', []))
                logger.info(f"Successfully extracted entities and relationships using {extraction_strategy}: "
                           f"{entities_count} entities, {relationships_count} relationships")
                
                return result

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse AI response as JSON using {extraction_strategy}: {e}")
                logger.error(f"JSON error position: {e.pos if hasattr(e, 'pos') else 'unknown'}")
                logger.error(f"Response content sample: {response.content[:800]}...")

                # Try one more time with more aggressive cleaning
                try:
                    logger.info("Attempting aggressive cleaning and final JSON parse...")
                    # Remove all markdown formatting and extra text
                    clean_text = response.content.strip()

                    # Remove any text before the first {
                    if '{' in clean_text:
                        clean_text = clean_text[clean_text.find('{'):]
                        logger.debug(f"Removed prefix text, remaining: {len(clean_text)} chars")

                    # Remove any text after the last }
                    if '}' in clean_text:
                        clean_text = clean_text[:clean_text.rfind('}') + 1]
                        logger.debug(f"Removed suffix text, final: {len(clean_text)} chars")

                    # Try parsing the cleaned text
                    result = json.loads(clean_text)
                    entities_count = len(result.get('entities', []))
                    relationships_count = len(result.get('relationships', []))
                    logger.info(f"Successfully parsed JSON after aggressive cleaning: "
                               f"{entities_count} entities, {relationships_count} relationships")
                    return result

                except Exception as final_error:
                    logger.error(f"Final JSON parsing attempt failed: {final_error}")
                    logger.error(f"Final clean text sample: {clean_text[:400] if 'clean_text' in locals() else 'N/A'}")

                # Return empty structure instead of failing completely
                logger.warning("Returning empty entity structure due to JSON parsing failure")
                return {
                    "entities": [],
                    "relationships": [],
                    "metadata": {
                        "extraction_status": "json_parse_failed",
                        "error": str(e),
                        "extraction_strategy": extraction_strategy,
                        "response_length": len(response.content),
                        "response_preview": response.content[:200]
                    }
                }

        except Exception as e:
            logger.error(f"Error in AI entity extraction: {e}")
            raise

    def _create_system_prompt(self) -> str:
        """Create the system prompt for entity extraction"""
        return """You are an infrastructure analyst. Extract entities from documents.

IMPORTANT: Respond immediately with JSON. No explanations, reasoning, or thinking.

Format:
{
  "entities": [{"name": "NAME", "type": "TYPE", "description": "BRIEF"}],
  "relationships": [{"source": "ENTITY1", "target": "ENTITY2", "relationship": "TYPE"}]
}

Extract:
- Servers, databases, applications
- Network components, storage systems  
- Technical infrastructure

Empty result:
{"entities": [], "relationships": []}"""

    def _create_human_prompt(self, content: str) -> str:
        """Create the human prompt with the document content"""
        # Note: Content is now pre-chunked by RAGService, so no truncation needed here

        return f"""Extract infrastructure entities and relationships from this document.

Document content:
{content}

Return ONLY JSON, no other text."""

    # NOTE: Regex fallback removed per requirement. Entity extraction must use the project's configured LLM.
    # If extraction fails, raise and stop the pipeline so issues are visible and fixed.

    async def extract_entities_optimized(self, content: str, file_size_mb: float = 0.0, precomputed_chunks: List[str] = None) -> Dict[str, Any]:
        """
        Optimized entity extraction using semantic chunking and parallel processing

        Args:
            content: Document content to process
            file_size_mb: File size in MB for strategy selection

        Returns:
            Dictionary with entities, relationships, and processing metadata
        """
        try:
            self._initialize_optimized_components()
            if self.optimized_chunker is None:
                logger.warning("Optimized components not available, falling back to standard extraction")
                return self.extract_entities_and_relationships(content)
            logger.info(f"Starting optimized entity extraction for {file_size_mb:.2f}MB document ({len(content)} chars)")
            import time
            start_time = time.time()
            if precomputed_chunks is not None:
                # Wrap precomputed string chunks into DocumentChunk objects with synthetic ids
                from app.core.semantic_chunking import DocumentChunk
                chunks = [DocumentChunk(c, i, 0, len(c), 'pre_chunk') for i, c in enumerate(precomputed_chunks)]
                strategy = 'reused_chunks'
                logger.info(f"Reusing {len(chunks)} precomputed chunks for entity extraction")
            else:
                chunks, strategy = self.optimized_chunker.process_document(content, file_size_mb)
                logger.info(f"Created {len(chunks)} chunks using '{strategy}' strategy")

            # Log chunk details for debugging
            for i, chunk in enumerate(chunks[:3]):  # Log first 3 chunks
                logger.info(f"Chunk {i+1}: {len(chunk.content)} chars, type: {chunk.chunk_type}")
                try:
                    logger.debug(
                        "CHUNK_META id=%s tokens_est=%s", getattr(chunk, "chunk_id", i), self._estimate_tokens(chunk.content)
                    )
                except Exception:
                    pass
            if len(chunks) > 3:
                logger.info(f"... and {len(chunks) - 3} more chunks")

            # Step 2: Parallel entity extraction
            if len(chunks) == 1:
                # Single chunk - use standard extraction
                result = self.extract_entities_and_relationships(chunks[0].content)
                entities = result.get("entities", [])
                relationships = result.get("relationships", [])
            else:
                # Multiple chunks - use parallel extraction
                extraction_results = await self.parallel_extractor.extract_entities_parallel(chunks, self)

                # Step 3: Deduplicate and merge results
                entities, relationships = self.deduplicator.deduplicate_entities(extraction_results)

            processing_time = time.time() - start_time

            logger.info(f"Optimized extraction completed in {processing_time:.2f}s - "
                       f"Found {len(entities)} entities and {len(relationships)} relationships")

            return {
                "entities": entities,
                "relationships": relationships,
                "processing_metadata": {
                    "strategy": strategy,
                    "chunks_processed": len(chunks),
                    "processing_time": processing_time,
                    "file_size_mb": file_size_mb
                }
            }

        except Exception as e:
            logger.error(f"Optimized entity extraction failed: {str(e)}")
            # Fallback to standard extraction
            logger.info("Falling back to standard entity extraction")
            return self.extract_entities_and_relationships(content)

    async def generate_response(self, prompt: str, temperature: float = 0.1, max_tokens: int = 2000, stop_sequences=None) -> str:
        """
        Generate response using the LLM (for compatibility with parallel extractor)
        """
        try:
            from langchain.schema import HumanMessage
            # Log prompt meta only (sizes), not full content
            logger.debug(
                "LLM_CALL temp=%s max_tokens=%s prompt_chars=%s tokens_est=%s provider=%s model=%s",
                temperature,
                max_tokens,
                len(prompt),
                self._estimate_tokens(prompt),
                type(self.llm).__name__,
                getattr(self.llm, "model", None) or getattr(self.llm, "model_name", None) or getattr(self.llm, "model_id", None),
            )
            messages = [HumanMessage(content=prompt)]
            response = self.llm.invoke(messages)
            content = response.content if hasattr(response, 'content') else str(response)
            if not content or not content.strip():
                logger.warning("LLM returned empty content for generate_response")
            return content
        except Exception as e:
            logger.error(f"LLM response generation failed: {type(e).__name__}: {e}")
            return ""


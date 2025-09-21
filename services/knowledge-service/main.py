"""
Advanced RAG & Knowledge Management Service

This service provides:
1. Enhanced semantic search and retrieval
2. Knowledge graph construction and querying
3. Intelligent document indexing and analysis
4. Context-aware question answering
5. Knowledge base management and curation
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager
from enum import Enum

import httpx
from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Ensure uvicorn loggers use same handlers/formatters
_root_logger = logging.getLogger()
for _lname in ("uvicorn", "uvicorn.error", "uvicorn.access"):
    _uvl = logging.getLogger(_lname)
    _uvl.setLevel(logging.INFO)
    for _h in list(_uvl.handlers):
        _uvl.removeHandler(_h)
    for _h in _root_logger.handlers:
        _uvl.addHandler(_h)
    _uvl.propagate = False

class DocumentType(str, Enum):
    TECHNICAL_DOC = "technical_doc"
    MIGRATION_GUIDE = "migration_guide"
    ARCHITECTURE_DOC = "architecture_doc"
    API_DOCUMENTATION = "api_documentation"
    TROUBLESHOOTING = "troubleshooting"
    BEST_PRACTICES = "best_practices"
    CASE_STUDY = "case_study"
    RESEARCH_PAPER = "research_paper"

class KnowledgeStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"

class SearchType(str, Enum):
    SEMANTIC = "semantic"
    KEYWORD = "keyword"
    HYBRID = "hybrid"
    GRAPH = "graph"

@dataclass
class KnowledgeDocument:
    """Knowledge document representation"""
    doc_id: str
    title: str
    content: str
    doc_type: DocumentType
    metadata: Dict[str, Any]
    tags: List[str]
    embeddings: Optional[List[float]] = None
    relationships: Optional[List[str]] = None  # Related document IDs
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    status: KnowledgeStatus = KnowledgeStatus.PENDING
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if self.created_at:
            data['created_at'] = self.created_at.isoformat()
        if self.updated_at:
            data['updated_at'] = self.updated_at.isoformat()
        # Don't include embeddings in dict for API responses (too large)
        data.pop('embeddings', None)
        return data

@dataclass
class SearchResult:
    """Search result representation"""
    doc_id: str
    title: str
    content_snippet: str
    relevance_score: float
    doc_type: DocumentType
    metadata: Dict[str, Any]
    tags: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class KnowledgeGraph:
    """Knowledge graph representation"""
    graph_id: str
    name: str
    description: str
    nodes: List[Dict[str, Any]]  # Knowledge entities
    edges: List[Dict[str, Any]]  # Relationships
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        if self.updated_at:
            data['updated_at'] = self.updated_at.isoformat()
        return data

@dataclass
class QuestionAnswer:
    """Q&A pair representation"""
    qa_id: str
    question: str
    answer: str
    context_docs: List[str]  # Source document IDs
    confidence: float
    metadata: Dict[str, Any]
    created_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        return data

class KnowledgeManager:
    """Manages advanced RAG and knowledge operations"""
    
    def __init__(self):
        # In-memory stores
        self.documents: Dict[str, KnowledgeDocument] = {}
        self.knowledge_graphs: Dict[str, KnowledgeGraph] = {}
        self.qa_pairs: Dict[str, QuestionAnswer] = {}
        self.search_index: Dict[str, Any] = {}  # Simple in-memory search index

        # Service URLs
        self.document_service_url = os.getenv("DOCUMENT_SERVICE_URL", "http://localhost:8004")
        self.vector_service_url = os.getenv("VECTOR_SERVICE_URL", "http://localhost:8005")
        self.storage_service_url = os.getenv("STORAGE_SERVICE_URL", "http://localhost:8010")
        self.websocket_url = os.getenv("WEBSOCKET_SERVICE_URL", "http://localhost:8009")

        # Initialize with sample knowledge
        self._initialize_sample_knowledge()

        logger.info("Knowledge Manager initialized")
    
    def _initialize_sample_knowledge(self):
        """Initialize with sample knowledge documents"""
        sample_docs = [
            {
                "title": "Cloud Migration Best Practices",
                "content": "Cloud migration requires careful planning and execution. Key considerations include: 1) Assessment of current infrastructure, 2) Selection of appropriate cloud services, 3) Migration strategy (lift-and-shift vs. re-architecture), 4) Security and compliance requirements, 5) Performance optimization, 6) Cost management. Best practices include conducting thorough discovery, creating detailed migration plans, implementing proper testing procedures, and ensuring adequate training for teams.",
                "doc_type": DocumentType.BEST_PRACTICES,
                "tags": ["cloud", "migration", "best-practices", "infrastructure"],
                "metadata": {"author": "Cloud Architecture Team", "version": "1.0", "category": "migration"}
            },
            {
                "title": "Microservices Architecture Patterns",
                "content": "Microservices architecture patterns help design scalable and maintainable systems. Common patterns include: API Gateway for service routing, Service Registry for discovery, Circuit Breaker for fault tolerance, Event Sourcing for data consistency, CQRS for read/write separation, Saga pattern for distributed transactions. Each pattern addresses specific challenges in distributed systems.",
                "doc_type": DocumentType.ARCHITECTURE_DOC,
                "tags": ["microservices", "architecture", "patterns", "distributed-systems"],
                "metadata": {"author": "Architecture Team", "version": "2.1", "category": "architecture"}
            },
            {
                "title": "Database Migration Strategies",
                "content": "Database migration strategies vary based on requirements: 1) Big Bang migration - complete cutover at once, 2) Parallel run - old and new systems run simultaneously, 3) Phased migration - gradual migration of data and functionality, 4) Hybrid approach - combination of strategies. Consider factors like downtime tolerance, data volume, complexity, and rollback requirements.",
                "doc_type": DocumentType.MIGRATION_GUIDE,
                "tags": ["database", "migration", "strategy", "data"],
                "metadata": {"author": "Database Team", "version": "1.5", "category": "database"}
            }
        ]
        
        for doc_data in sample_docs:
            doc_id = str(uuid.uuid4())
            doc = KnowledgeDocument(
                doc_id=doc_id,
                title=doc_data["title"],
                content=doc_data["content"],
                doc_type=doc_data["doc_type"],
                metadata=doc_data["metadata"],
                tags=doc_data["tags"],
                created_at=datetime.now(),
                status=KnowledgeStatus.INDEXED
            )
            self.documents[doc_id] = doc
            
            # Add to search index
            self._add_to_search_index(doc)
    
    def _add_to_search_index(self, document: KnowledgeDocument):
        """Add document to search index (simplified implementation)"""
        # In a real implementation, this would use proper vector embeddings
        keywords = document.title.lower().split() + document.content.lower().split() + document.tags
        
        for keyword in set(keywords):
            if keyword not in self.search_index:
                self.search_index[keyword] = []
            self.search_index[keyword].append(document.doc_id)
    
    async def add_document(self, title: str, content: str, doc_type: DocumentType, 
                          metadata: Dict[str, Any], tags: List[str]) -> str:
        """Add new knowledge document"""
        doc_id = str(uuid.uuid4())
        
        document = KnowledgeDocument(
            doc_id=doc_id,
            title=title,
            content=content,
            doc_type=doc_type,
            metadata=metadata,
            tags=tags,
            created_at=datetime.now(),
            status=KnowledgeStatus.PROCESSING
        )
        
        self.documents[doc_id] = document
        
        # Process document in background
        asyncio.create_task(self._process_document(doc_id))
        
        logger.info(f"Added document {title} with ID {doc_id}")
        return doc_id
    
    async def _process_document(self, doc_id: str):
        """Process document for indexing (background task)"""
        try:
            document = self.documents[doc_id]
            
            # Simulate document processing
            await asyncio.sleep(2)
            
            # Generate embeddings (simulated)
            document.embeddings = [0.1] * 768  # Simulated embedding vector
            
            # Find related documents (simplified similarity)
            related_docs = await self._find_related_documents(document)
            document.relationships = related_docs
            
            # Add to search index
            self._add_to_search_index(document)
            
            # Update status
            document.status = KnowledgeStatus.INDEXED
            document.updated_at = datetime.now()
            
            # Notify via WebSocket
            await self._notify_websocket("document_indexed", {
                "doc_id": doc_id,
                "title": document.title,
                "status": document.status
            })
            
            logger.info(f"Document {doc_id} indexed successfully")
            
        except Exception as e:
            logger.error(f"Failed to process document {doc_id}: {e}")
            if doc_id in self.documents:
                self.documents[doc_id].status = KnowledgeStatus.FAILED
    
    async def _find_related_documents(self, document: KnowledgeDocument) -> List[str]:
        """Find related documents (simplified implementation)"""
        related = []
        
        for doc_id, other_doc in self.documents.items():
            if doc_id == document.doc_id or other_doc.status != KnowledgeStatus.INDEXED:
                continue
            
            # Simple tag-based similarity
            common_tags = set(document.tags) & set(other_doc.tags)
            if len(common_tags) >= 2:
                related.append(doc_id)
        
        return related[:5]  # Limit to 5 related documents
    
    async def search_documents(self, query: str, search_type: SearchType = SearchType.HYBRID, 
                             doc_types: Optional[List[DocumentType]] = None, 
                             limit: int = 10) -> List[SearchResult]:
        """Search knowledge documents"""
        results = []
        
        if search_type in [SearchType.KEYWORD, SearchType.HYBRID]:
            results.extend(await self._keyword_search(query, doc_types))
        
        if search_type in [SearchType.SEMANTIC, SearchType.HYBRID]:
            results.extend(await self._semantic_search(query, doc_types))
        
        # Remove duplicates and sort by relevance
        seen_docs = set()
        unique_results = []
        
        for result in results:
            if result.doc_id not in seen_docs:
                seen_docs.add(result.doc_id)
                unique_results.append(result)
        
        # Sort by relevance score
        unique_results.sort(key=lambda x: x.relevance_score, reverse=True)
        
        return unique_results[:limit]
    
    async def _keyword_search(self, query: str, doc_types: Optional[List[DocumentType]]) -> List[SearchResult]:
        """Perform keyword-based search"""
        results = []
        query_words = query.lower().split()
        
        # Find documents containing query keywords
        candidate_docs = set()
        for word in query_words:
            if word in self.search_index:
                candidate_docs.update(self.search_index[word])
        
        for doc_id in candidate_docs:
            document = self.documents.get(doc_id)
            if not document or document.status != KnowledgeStatus.INDEXED:
                continue
            
            if doc_types and document.doc_type not in doc_types:
                continue
            
            # Calculate relevance score (simplified)
            score = 0.0
            content_lower = document.content.lower()
            title_lower = document.title.lower()
            
            for word in query_words:
                if word in title_lower:
                    score += 2.0
                if word in content_lower:
                    score += 1.0
                if word in document.tags:
                    score += 1.5
            
            if score > 0:
                # Create content snippet
                snippet = self._create_content_snippet(document.content, query_words)
                
                result = SearchResult(
                    doc_id=doc_id,
                    title=document.title,
                    content_snippet=snippet,
                    relevance_score=score,
                    doc_type=document.doc_type,
                    metadata=document.metadata,
                    tags=document.tags
                )
                results.append(result)
        
        return results
    
    async def _semantic_search(self, query: str, doc_types: Optional[List[DocumentType]]) -> List[SearchResult]:
        """Perform semantic search (simplified implementation)"""
        # In a real implementation, this would use vector similarity with embeddings
        results = []
        
        # For demo, use enhanced keyword matching with synonyms
        semantic_expansions = {
            "migration": ["migration", "move", "transfer", "transition"],
            "cloud": ["cloud", "aws", "azure", "gcp", "public cloud"],
            "database": ["database", "db", "sql", "nosql", "data store"],
            "architecture": ["architecture", "design", "pattern", "structure"]
        }
        
        expanded_query = []
        for word in query.lower().split():
            expanded_query.append(word)
            if word in semantic_expansions:
                expanded_query.extend(semantic_expansions[word])
        
        # Use expanded query for keyword search
        expanded_query_str = " ".join(expanded_query)
        return await self._keyword_search(expanded_query_str, doc_types)
    
    def _create_content_snippet(self, content: str, query_words: List[str], snippet_length: int = 200) -> str:
        """Create content snippet highlighting query terms"""
        content_lower = content.lower()
        
        # Find best position for snippet
        best_pos = 0
        max_matches = 0
        
        for i in range(len(content) - snippet_length):
            snippet = content_lower[i:i + snippet_length]
            matches = sum(1 for word in query_words if word in snippet)
            if matches > max_matches:
                max_matches = matches
                best_pos = i
        
        snippet = content[best_pos:best_pos + snippet_length]
        if best_pos > 0:
            snippet = "..." + snippet
        if best_pos + snippet_length < len(content):
            snippet = snippet + "..."
        
        return snippet
    
    async def ask_question(self, question: str, context_limit: int = 5) -> QuestionAnswer:
        """Answer question using knowledge base"""
        qa_id = str(uuid.uuid4())
        
        # Search for relevant documents
        search_results = await self.search_documents(question, SearchType.HYBRID, limit=context_limit)
        
        # Extract context from top results
        context_docs = []
        context_text = []
        
        for result in search_results:
            context_docs.append(result.doc_id)
            context_text.append(f"Document: {result.title}\nContent: {result.content_snippet}")
        
        # Generate answer (simplified - in real implementation, use LLM)
        answer = await self._generate_answer(question, context_text)
        
        # Calculate confidence based on search results
        confidence = min(0.9, sum(r.relevance_score for r in search_results) / 10.0)
        
        qa_pair = QuestionAnswer(
            qa_id=qa_id,
            question=question,
            answer=answer,
            context_docs=context_docs,
            confidence=confidence,
            metadata={"search_results_count": len(search_results)},
            created_at=datetime.now()
        )
        
        self.qa_pairs[qa_id] = qa_pair
        
        logger.info(f"Generated answer for question: {question[:50]}...")
        return qa_pair

    async def ask_project_question(self, project_id: str, question: str, context_limit: int = 5, use_llm: bool = False) -> Dict[str, Any]:
        """Project-scoped QA using vector-service retrieval. Fallback to in-memory if vector-service fails.
        Returns a normalized envelope with answer and sources.
        """
        # Try vector-service first
        sources: List[Dict[str, Any]] = []
        answer: str = ""
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=3.0)) as client:
                # Primary semantic search
                try:
                    r = await client.post(
                        f"{self.vector_service_url}/api/vectors/projects/{project_id}/search",
                        json={"query": question, "limit": context_limit or 5},
                        headers={"Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"}
                    )
                    r.raise_for_status()
                    result = r.json()
                except Exception as e1:
                    logger.warning(f"Vector search failed, trying hybrid: {e1}")
                    r = await client.post(
                        f"{self.vector_service_url}/api/vectors/projects/{project_id}/search/hybrid",
                        json={"query": question, "limit": context_limit or 5},
                        headers={"Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"}
                    )
                    r.raise_for_status()
                    result = r.json()

            docs = []
            for item in (result or {}).get("results", []) or []:
                content = item.get("content") or ""
                meta = item.get("metadata") or {}
                filename = meta.get("filename", "unknown")
                
                # Validate and correct filename by querying storage-service
                if filename and filename != "unknown":
                    try:
                        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                            response = await client.get(
                                f"{os.getenv('STORAGE_SERVICE_URL', 'http://localhost:8010')}/api/storage/projects/{project_id}/metadata/{filename}_metadata.json",
                                headers={"Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"}
                            )
                            if response.status_code == 200:
                                metadata = response.json()
                                corrected_filename = metadata.get("original_filename", filename)
                                if corrected_filename != filename:
                                    logger.info(f"Corrected filename from {filename} to {corrected_filename}")
                                    filename = corrected_filename
                    except Exception as e:
                        logger.debug(f"Could not validate filename {filename}: {e}")
                
                if content:
                    docs.append(f"From {filename}: {content}")
                    sources.append({
                        "filename": filename,
                        "content": content[:300] + ("..." if len(content) > 300 else ""),
                        "score": item.get("score")
                    })

            if not docs:
                answer = "No relevant information found in the knowledge base."
            else:
                # Group by unique filenames and deduplicate content
                grouped_context = {}
                for doc in docs:
                    # Extract filename from "From filename: content" format
                    if ": " in doc:
                        filename_part, content_part = doc.split(": ", 1)
                        filename = filename_part.replace("From ", "").strip()
                        if filename not in grouped_context:
                            grouped_context[filename] = []
                        # Avoid duplicate content within the same filename
                        if content_part not in grouped_context[filename]:
                            grouped_context[filename].append(content_part)
                
                # Build combined context for LLM synthesis
                joined_parts = []
                for filename, contents in grouped_context.items():
                    joined_parts.append(f"From {filename}: {'; '.join(contents)}")
                joined = "\n\n".join(joined_parts)
                
                if use_llm:
                    # Call llm-service for synthesis with improved prompt and response handling
                    llm_base = os.getenv("LLM_SERVICE_URL", "http://localhost:8007")
                    headers = {"Authorization": f"Bearer {os.getenv('SERVICE_AUTH_TOKEN', 'service-backend-token')}"}
                    try:
                        # Resolve LLM config first
                        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=3.0)) as rc:
                            resolve_resp = await rc.get(
                                f"{llm_base}/api/llm/resolve",
                                params={"process_type": "rag_synthesis", "project_id": project_id, "allow_global": False},
                                headers=headers,
                            )
                            if resolve_resp.status_code != 200:
                                logger.warning(f"LLM resolve failed with {resolve_resp.status_code}; using retrieval answer")
                                raise RuntimeError("llm_resolve_failed")
                            
                            config = resolve_resp.json()
                            provider = config.get('provider')
                            model = config.get('model')
                            logger.info(f"Resolved LLM config: provider={provider}, model={model}")

                        # Build better prompt for structured answers
                        prompt = f"""
                        You are a helpful assistant.
                        Answer the following question based ONLY on the provided context.
                        When responding:
                        Clarity & Structure
                        Use short paragraphs, bullet points, or tables for readability.
                        Start with a direct summary answer before going into details.
                        Use clear section headers (e.g., Summary, Details, References).
                        Citations
                        Reference specific filenames or sources when relevant (e.g., "According to [filename.xlsx]...").
                        Limits
                        If the context does not provide enough information, explicitly state:
                        "The provided context does not contain enough information to answer this question."
                        Style
                        Keep responses concise, professional, and free of filler text.
                        Where appropriate, format outputs as lists, tables, or step-by-step instructions instead of plain text.

                        Question: {question}

                        Context:
                        {joined[:12000]}

                        Answer:
                        """

                        # Call LLM with proper format (match llm-service contract)
                        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=5.0)) as pc:
                            llm_payload = {
                                "process_type": "rag_synthesis",
                                "prompt": prompt,
                                "project_id": project_id,
                                "allow_global": False
                            }
                            
                            r2 = await pc.post(
                                f"{llm_base}/api/llm/process",
                                json=llm_payload,
                                headers=headers,
                            )
                            r2.raise_for_status()
                            data = r2.json() or {}
                            
                            # ProcessLLMResponse: { process_type, response, success, error? }
                            success = bool(data.get("success"))
                            resp_text = data.get("response")
                            if success and isinstance(resp_text, str) and resp_text.strip():
                                answer = resp_text.strip()
                                logger.info(f"LLM synthesis successful, answer length: {len(answer)}")
                            else:
                                logger.warning(f"LLM returned unsuccessful or empty response: {data}")
                                raise RuntimeError("llm_empty_or_unsuccessful_response")
                                
                    except Exception as le:
                        logger.warning(f"LLM synthesis failed: {le}; falling back to retrieval answer")
                        # Structured fallback without dumping raw context
                        top_files = ", ".join([s.get("filename", "unknown") for s in sources[:5]])
                        answer = (
                            "I couldn't synthesize a final answer from the current project knowledge. "
                            "Try rephrasing your question or increasing the context limit. "
                            f"Top matching sources: {top_files if top_files else 'None found.'}"
                        )
                else:
                    # Retrieval-only answer
                    answer = joined if len(joined) <= 4000 else joined[:4000] + "..."

        except Exception as e:
            logger.error(f"Project QA retrieval failed for {project_id}: {e}")
            # Fallback to in-memory generic answer
            qa = await self.ask_question(question, context_limit)
            answer = qa.answer
            # No reliable sources available in fallback

        return {
            "answer": answer,
            "sources": sources,
            "project_id": project_id,
        }
    
    async def _generate_answer(self, question: str, context_text: List[str]) -> str:
        """Generate answer from context (simplified implementation)"""
        # In a real implementation, this would use an LLM
        if not context_text:
            return "I don't have enough information to answer this question. Please provide more context or check if the question is related to our knowledge base."
        
        # Simple rule-based answer generation for demo
        question_lower = question.lower()
        
        if "migration" in question_lower:
            return "Based on the available documentation, migration typically involves careful planning, assessment of current infrastructure, selection of appropriate strategies, and implementation with proper testing. Key considerations include downtime requirements, data volume, and rollback procedures."
        
        elif "architecture" in question_lower:
            return "According to our architecture documentation, successful system design involves selecting appropriate patterns like microservices, API gateways, and circuit breakers. The choice depends on scalability requirements, team structure, and system complexity."
        
        elif "database" in question_lower:
            return "Database-related information suggests considering factors like data volume, downtime tolerance, and migration complexity. Common strategies include big bang migration, parallel run, or phased approaches."
        
        else:
            # Extract key information from context
            combined_context = " ".join(context_text)
            if len(combined_context) > 500:
                combined_context = combined_context[:500] + "..."
            
            return f"Based on the available documentation: {combined_context}"
    
    async def create_knowledge_graph(self, name: str, description: str, doc_ids: List[str]) -> str:
        """Create knowledge graph from documents"""
        graph_id = str(uuid.uuid4())
        
        nodes = []
        edges = []
        
        # Create nodes from documents
        for doc_id in doc_ids:
            document = self.documents.get(doc_id)
            if document and document.status == KnowledgeStatus.INDEXED:
                node = {
                    "id": doc_id,
                    "label": document.title,
                    "type": "document",
                    "doc_type": document.doc_type,
                    "tags": document.tags
                }
                nodes.append(node)
                
                # Create edges based on relationships
                if document.relationships:
                    for related_id in document.relationships:
                        if related_id in doc_ids:
                            edge = {
                                "from": doc_id,
                                "to": related_id,
                                "type": "related_to",
                                "weight": 1.0
                            }
                            edges.append(edge)
        
        # Create tag nodes and connect documents
        tags_seen = set()
        for node in nodes:
            for tag in node["tags"]:
                if tag not in tags_seen:
                    tag_node = {
                        "id": f"tag_{tag}",
                        "label": tag,
                        "type": "tag"
                    }
                    nodes.append(tag_node)
                    tags_seen.add(tag)
                
                # Connect document to tag
                edge = {
                    "from": node["id"],
                    "to": f"tag_{tag}",
                    "type": "has_tag",
                    "weight": 0.5
                }
                edges.append(edge)
        
        knowledge_graph = KnowledgeGraph(
            graph_id=graph_id,
            name=name,
            description=description,
            nodes=nodes,
            edges=edges,
            created_at=datetime.now()
        )
        
        self.knowledge_graphs[graph_id] = knowledge_graph
        
        logger.info(f"Created knowledge graph {name} with {len(nodes)} nodes and {len(edges)} edges")
        return graph_id
    
    async def _notify_websocket(self, event_type: str, data: Dict[str, Any]):
        """Send notification via WebSocket service"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    f"{self.websocket_url}/broadcast",
                    json={
                        "channel_type": "knowledge",
                        "message": {
                            "type": event_type,
                            "data": data,
                            "timestamp": datetime.now().isoformat()
                        }
                    }
                )
        except Exception as e:
            logger.warning(f"Failed to send WebSocket notification: {e}")
    
    def get_document(self, doc_id: str) -> Optional[KnowledgeDocument]:
        """Get document by ID"""
        return self.documents.get(doc_id)
    
    def get_knowledge_graph(self, graph_id: str) -> Optional[KnowledgeGraph]:
        """Get knowledge graph by ID"""
        return self.knowledge_graphs.get(graph_id)
    
    def get_qa_pair(self, qa_id: str) -> Optional[QuestionAnswer]:
        """Get Q&A pair by ID"""
        return self.qa_pairs.get(qa_id)
    
    def list_documents(self, doc_type: Optional[DocumentType] = None, 
                      status: Optional[KnowledgeStatus] = None) -> List[KnowledgeDocument]:
        """List documents with optional filtering"""
        documents = list(self.documents.values())
        
        if doc_type:
            documents = [d for d in documents if d.doc_type == doc_type]
        
        if status:
            documents = [d for d in documents if d.status == status]
        
        return sorted(documents, key=lambda x: x.created_at or datetime.min, reverse=True)

# Global knowledge manager
knowledge_manager = KnowledgeManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    # Startup
    logger.info("Advanced RAG & Knowledge Management Service started successfully")
    
    yield
    
    # Shutdown
    logger.info("Advanced RAG & Knowledge Management Service shut down successfully")

# FastAPI app
app = FastAPI(
    title="Advanced RAG & Knowledge Management Service",
    description="Enhanced semantic search and knowledge management for Nagarro Ascent Platform",
    version="3.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for API
class AddDocumentRequest(BaseModel):
    title: str
    content: str
    doc_type: DocumentType
    metadata: Dict[str, Any] = {}
    tags: List[str] = []

class SearchRequest(BaseModel):
    query: str
    search_type: SearchType = SearchType.HYBRID
    doc_types: Optional[List[DocumentType]] = None
    limit: int = 10

class QuestionRequest(BaseModel):
    question: str
    context_limit: int = 5

class ProjectQuestionRequest(BaseModel):
    question: str
    context_limit: int = 5
    use_llm: bool = False

class CreateGraphRequest(BaseModel):
    name: str
    description: str
    doc_ids: List[str]

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str = "3.0.0"
    service: str = "knowledge-service"

# API Endpoints
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat()
    )

@app.post("/documents")
async def add_document(request: AddDocumentRequest):
    """Add new knowledge document"""
    doc_id = await knowledge_manager.add_document(
        request.title, request.content, request.doc_type, 
        request.metadata, request.tags
    )
    
    return {
        "doc_id": doc_id,
        "message": "Document added successfully",
        "status": "processing"
    }

@app.get("/documents")
async def list_documents(doc_type: Optional[DocumentType] = None, 
                        status: Optional[KnowledgeStatus] = None):
    """List knowledge documents"""
    documents = knowledge_manager.list_documents(doc_type, status)
    
    return {
        "documents": [doc.to_dict() for doc in documents],
        "total_documents": len(documents)
    }

@app.get("/documents/{doc_id}")
async def get_document(doc_id: str):
    """Get specific document"""
    document = knowledge_manager.get_document(doc_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return {"document": document.to_dict()}

@app.post("/search")
async def search_documents(request: SearchRequest):
    """Search knowledge documents"""
    results = await knowledge_manager.search_documents(
        request.query, request.search_type, request.doc_types, request.limit
    )
    
    return {
        "query": request.query,
        "search_type": request.search_type,
        "results": [result.to_dict() for result in results],
        "total_results": len(results)
    }

@app.post("/qa")
async def ask_question(request: QuestionRequest):
    """Ask question and get AI-generated answer"""
    qa_pair = await knowledge_manager.ask_question(request.question, request.context_limit)
    
    return {
        "qa": qa_pair.to_dict()
    }

@app.post("/qa/projects/{project_id}")
async def ask_project_question(project_id: str, request: ProjectQuestionRequest):
    """Project-scoped QA using vector-service retrieval and simple synthesis."""
    resp = await knowledge_manager.ask_project_question(project_id, request.question, request.context_limit, request.use_llm)
    # Return both flattened answer and a qa-like object for compatibility
    return {
        "answer": resp.get("answer"),
        "sources": resp.get("sources", []),
        "qa": {
            "qa_id": str(uuid.uuid4()),
            "question": request.question,
            "answer": resp.get("answer"),
            "context_docs": [s.get("filename") for s in resp.get("sources", [])],
            "confidence": 0.75,
            "metadata": {"project_id": project_id, "source_count": len(resp.get("sources", []))},
            "created_at": datetime.now().isoformat()
        }
    }

@app.get("/qa/{qa_id}")
async def get_qa_pair(qa_id: str):
    """Get specific Q&A pair"""
    qa_pair = knowledge_manager.get_qa_pair(qa_id)
    if not qa_pair:
        raise HTTPException(status_code=404, detail="Q&A pair not found")
    
    return {"qa": qa_pair.to_dict()}

@app.post("/knowledge-graphs")
async def create_knowledge_graph(request: CreateGraphRequest):
    """Create knowledge graph from documents"""
    graph_id = await knowledge_manager.create_knowledge_graph(
        request.name, request.description, request.doc_ids
    )
    
    return {
        "graph_id": graph_id,
        "message": "Knowledge graph created successfully"
    }

@app.get("/knowledge-graphs/{graph_id}")
async def get_knowledge_graph(graph_id: str):
    """Get knowledge graph"""
    graph = knowledge_manager.get_knowledge_graph(graph_id)
    if not graph:
        raise HTTPException(status_code=404, detail="Knowledge graph not found")
    
    return {"graph": graph.to_dict()}

@app.get("/stats")
async def get_knowledge_stats():
    """Get knowledge base statistics"""
    total_docs = len(knowledge_manager.documents)
    indexed_docs = len([d for d in knowledge_manager.documents.values() 
                       if d.status == KnowledgeStatus.INDEXED])
    total_graphs = len(knowledge_manager.knowledge_graphs)
    total_qa = len(knowledge_manager.qa_pairs)
    
    # Document type distribution
    doc_types = {}
    for doc in knowledge_manager.documents.values():
        doc_type = doc.doc_type
        doc_types[doc_type] = doc_types.get(doc_type, 0) + 1
    
    return {
        "total_documents": total_docs,
        "indexed_documents": indexed_docs,
        "processing_documents": total_docs - indexed_docs,
        "knowledge_graphs": total_graphs,
        "qa_pairs": total_qa,
        "document_types": doc_types
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8017)),
        reload=True,
        log_level="info"
    )
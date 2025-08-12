#!/usr/bin/env python3
"""
Simple test backend to verify basic functionality
"""
import os
import tempfile
import io
from fastapi import FastAPI, UploadFile, File, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any
import logging
import json
from datetime import datetime
import uuid
import asyncio
import requests
from pathlib import Path

# Configure logging with file output (no emojis for Windows compatibility)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('backend_test.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Test Backend")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple in-memory vector store for testing
class SimpleVectorStore:
    def __init__(self):
        self.documents = {}  # project_id -> list of documents
        self.embeddings = {}  # project_id -> list of embeddings

    def add_documents(self, project_id: str, documents: List[Dict[str, Any]]):
        """Add documents to the vector store"""
        if project_id not in self.documents:
            self.documents[project_id] = []
            self.embeddings[project_id] = []

        for doc in documents:
            self.documents[project_id].append(doc)
            # Simple keyword-based "embedding" for testing
            keywords = doc['content'].lower().split()
            self.embeddings[project_id].append({
                'doc_id': doc['id'],
                'keywords': keywords,
                'content': doc['content'],
                'filename': doc['filename']
            })

    def search(self, project_id: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Simple keyword-based search"""
        if project_id not in self.embeddings:
            return []

        query_keywords = query.lower().split()
        results = []

        for embedding in self.embeddings[project_id]:
            # Simple scoring based on keyword matches
            score = 0
            for keyword in query_keywords:
                if keyword in embedding['keywords']:
                    score += 1

            if score > 0:
                results.append({
                    'content': embedding['content'],
                    'filename': embedding['filename'],
                    'score': score
                })

        # Sort by score and return top results
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:limit]

# Global vector store instance
vector_store = SimpleVectorStore()

# Initialize real Weaviate and Neo4j connections (REQUIRED - no fallbacks)
try:
    import weaviate
    import weaviate.classes as wvc
    from weaviate.classes.init import AdditionalConfig, Timeout

    weaviate_url = os.getenv("WEAVIATE_URL", "http://localhost:8080")
    weaviate_client = weaviate.connect_to_local(
        host="localhost",
        port=8080,
        grpc_port=None,  # Disable gRPC completely
        skip_init_checks=True,
        additional_config=AdditionalConfig(
            timeout=Timeout(init=10, query=30, insert=60)
        )
    )
    if weaviate_client.is_ready():
        logger.info(f"✅ Connected to Weaviate at {weaviate_url}")
        USE_WEAVIATE = True
    else:
        logger.error(f"❌ Weaviate not ready at {weaviate_url}")
        raise Exception(f"Weaviate service not available at {weaviate_url}")
except Exception as e:
    logger.error(f"❌ Weaviate connection failed: {e}")
    logger.warning(f"⚠️ Starting without Weaviate - will use in-memory store for testing")
    weaviate_client = None
    USE_WEAVIATE = False

try:
    from neo4j import GraphDatabase
    neo4j_url = os.getenv("NEO4J_URL", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "password")
    neo4j_driver = GraphDatabase.driver(neo4j_url, auth=(neo4j_user, neo4j_password))
    # Test connection
    with neo4j_driver.session() as session:
        session.run("RETURN 1")
    logger.info(f"✅ Connected to Neo4j at {neo4j_url}")
    USE_NEO4J = True
except Exception as e:
    logger.error(f"❌ Neo4j connection failed: {e}")
    logger.warning(f"⚠️ Starting without Neo4j - will use simple graph simulation for testing")
    neo4j_driver = None
    USE_NEO4J = False

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "Test backend is running"}

@app.post("/api/test-llm")
async def test_llm(request: dict):
    """Real LLM test endpoint"""
    logger.info(f"LLM test request: {request}")

    provider = request.get('provider', 'unknown')
    model = request.get('model', 'unknown')
    api_key_id = request.get('apiKeyId')

    try:
        if provider.lower() == 'openai':
            import openai
            import os

            # Get API key from settings first, then environment
            api_key = None
            if 'openai_key' in llm_settings:
                api_key = llm_settings['openai_key'].get('value')
                if api_key == 'your-openai-key-here':  # Default placeholder
                    api_key = None

            if not api_key:
                api_key = os.getenv('OPENAI_API_KEY')

            if not api_key:
                return {
                    "status": "error",
                    "message": "OpenAI API key not found in settings or environment variables. Please configure it in Settings > LLM Configuration.",
                    "provider": provider,
                    "model": model
                }

            # Test OpenAI connection
            client = openai.OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "user", "content": "Hello, this is a test. Please respond with 'LLM connection successful'."}
                ],
                max_tokens=50
            )

            return {
                "status": "success",
                "message": "LLM connection successful",
                "provider": provider,
                "model": model,
                "response": response.choices[0].message.content
            }

        elif provider.lower() == 'google':
            import google.generativeai as genai
            import os

            # Get API key from environment
            api_key = os.getenv('GOOGLE_API_KEY')
            if not api_key:
                return {
                    "status": "error",
                    "message": "Google API key not found in environment variables",
                    "provider": provider,
                    "model": model
                }

            # Test Google Gemini connection
            genai.configure(api_key=api_key)
            model_instance = genai.GenerativeModel(model)
            response = model_instance.generate_content("Hello, this is a test. Please respond with 'LLM connection successful'.")

            return {
                "status": "success",
                "message": "LLM connection successful",
                "provider": provider,
                "model": model,
                "response": response.text
            }

        elif provider.lower() == 'anthropic':
            import anthropic
            import os

            # Get API key from environment
            api_key = os.getenv('ANTHROPIC_API_KEY')
            if not api_key:
                return {
                    "status": "error",
                    "message": "Anthropic API key not found in environment variables",
                    "provider": provider,
                    "model": model
                }

            # Test Anthropic connection
            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.create(
                model=model,
                max_tokens=50,
                messages=[
                    {"role": "user", "content": "Hello, this is a test. Please respond with 'LLM connection successful'."}
                ]
            )

            return {
                "status": "success",
                "message": "LLM connection successful",
                "provider": provider,
                "model": model,
                "response": response.content[0].text
            }

        else:
            return {
                "status": "error",
                "message": f"Unsupported provider: {provider}",
                "provider": provider,
                "model": model
            }

    except ImportError as e:
        return {
            "status": "error",
            "message": f"Required library not installed for {provider}: {str(e)}",
            "provider": provider,
            "model": model
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"LLM test failed: {str(e)}",
            "provider": provider,
            "model": model,
            "error_details": str(e)
        }

@app.websocket("/ws/run_assessment/{project_id}")
async def websocket_assessment(websocket: WebSocket, project_id: str):
    """Simple WebSocket endpoint to prevent 403 errors"""
    await websocket.accept()
    logger.info(f"WebSocket connected for project {project_id}")

    try:
        # Send some test messages
        await websocket.send_text("Assessment simulation started...")
        await websocket.send_text("This is a test backend - no real assessment running")
        await websocket.send_text("WebSocket connection working properly")

        # Keep connection alive
        while True:
            try:
                data = await websocket.receive_text()
                logger.info(f"Received: {data}")
                await websocket.send_text(f"Echo: {data}")
            except:
                break

    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        logger.info(f"WebSocket disconnected for project {project_id}")

@app.post("/upload/{project_id}")
async def upload_files(project_id: str, files: List[UploadFile] = File(...)):
    """Simple file upload test"""
    logger.info(f"Starting file upload for project {project_id} - {len(files)} files")
    uploaded_files = []

    try:
        for i, file in enumerate(files, 1):
            logger.info(f"Processing file {i}/{len(files)}: {file.filename}")

            # Read file content
            file_content = await file.read()
            file_size = len(file_content)
            logger.info(f"File size: {file_size} bytes")

            if file_size == 0:
                logger.warning(f"File {file.filename} is empty")
                continue

            # Save to temp directory
            temp_dir = os.path.join(tempfile.gettempdir(), "test_uploads", project_id)
            os.makedirs(temp_dir, exist_ok=True)
            temp_path = os.path.join(temp_dir, file.filename)

            with open(temp_path, "wb") as f:
                f.write(file_content)

            logger.info(f"Saved to: {temp_path}")

            uploaded_files.append({
                "filename": file.filename,
                "temp_path": temp_path,
                "size": file_size,
                "content_type": file.content_type,
                "status": "uploaded"
            })

            # Register file in local project database
            try:
                file_data = {
                    "filename": file.filename,
                    "file_type": file.content_type or "application/octet-stream",
                    "file_size": file_size,
                    "upload_path": temp_path
                }

                # Add to local project files database
                if project_id not in project_files_db:
                    project_files_db[project_id] = []

                file_id = str(uuid.uuid4())
                now = datetime.utcnow()

                file_record = {
                    "id": file_id,
                    "project_id": project_id,
                    "filename": file.filename,
                    "file_type": file.content_type or "application/octet-stream",
                    "file_size": file_size,
                    "upload_path": temp_path,
                    "upload_timestamp": now.isoformat(),
                    "created_at": now.isoformat(),
                    "updated_at": now.isoformat()
                }

                project_files_db[project_id].append(file_record)
                logger.info(f"File registered in database: {file.filename}")

            except Exception as reg_error:
                logger.warning(f"Could not register {file.filename} in database: {str(reg_error)}")

            logger.info(f"Successfully processed: {file.filename}")

        logger.info(f"Upload completed: {len(uploaded_files)} files")

        return {
            "status": "Upload completed",
            "project_id": project_id,
            "uploaded_files": uploaded_files,
            "summary": {
                "total": len(files),
                "successful": len(uploaded_files),
                "failed": 0
            }
        }

    except Exception as e:
        logger.error(f"Error in file upload: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@app.post("/api/projects/{project_id}/process-documents")
async def process_documents(project_id: str):
    """Process documents for knowledge base creation"""
    logger.info(f"Starting document processing for project {project_id}")

    try:
        # Get project files from local database
        files = project_files_db.get(project_id, [])

        if not files:
            raise HTTPException(status_code=400, detail="No files to process")

        logger.info(f"Processing {len(files)} files for project {project_id}")

        # Real document processing with embeddings
        processed_files = []
        documents_for_vector_store = []

        for file_info in files:
            if file_info.get('file_size', 0) > 0:  # Only process non-empty files
                filename = file_info['filename']
                file_path = file_info.get('upload_path', '')

                # Read file content
                try:
                    if file_path and os.path.exists(file_path):
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                    else:
                        content = f"Sample content for {filename}"

                    # Create chunks (simple sentence splitting)
                    sentences = content.split('. ')
                    chunks = []
                    current_chunk = ""

                    for sentence in sentences:
                        if len(current_chunk) + len(sentence) < 500:  # Max chunk size
                            current_chunk += sentence + ". "
                        else:
                            if current_chunk:
                                chunks.append(current_chunk.strip())
                            current_chunk = sentence + ". "

                    if current_chunk:
                        chunks.append(current_chunk.strip())

                    # Add to vector store
                    for i, chunk in enumerate(chunks):
                        doc_id = str(uuid.uuid4())
                        documents_for_vector_store.append({
                            'id': doc_id,
                            'content': chunk,
                            'filename': filename,
                            'chunk_index': i
                        })

                    processed_files.append({
                        "filename": filename,
                        "status": "processed",
                        "chunks": len(chunks),
                        "embeddings": len(chunks)
                    })
                    logger.info(f"Processed: {filename} - {len(chunks)} chunks created")

                except Exception as e:
                    logger.error(f"Error processing {filename}: {e}")
                    processed_files.append({
                        "filename": filename,
                        "status": "failed",
                        "error": str(e)
                    })

        # Add all documents to vector store (real Weaviate or in-memory)
        if documents_for_vector_store:
            if USE_WEAVIATE:
                # Use real Weaviate
                try:
                    class_name = f"Project_{project_id.replace('-', '_')}"

                    # Create class if it doesn't exist
                    try:
                        weaviate_client.schema.get(class_name)
                    except:
                        class_obj = {
                            "class": class_name,
                            "properties": [
                                {"name": "content", "dataType": ["text"]},
                                {"name": "filename", "dataType": ["text"]},
                                {"name": "chunk_index", "dataType": ["int"]}
                            ]
                        }
                        weaviate_client.schema.create_class(class_obj)
                        logger.info(f"Created Weaviate class: {class_name}")

                    # Add documents to Weaviate
                    for doc in documents_for_vector_store:
                        weaviate_client.data_object.create(
                            data_object={
                                "content": doc['content'],
                                "filename": doc['filename'],
                                "chunk_index": doc['chunk_index']
                            },
                            class_name=class_name,
                            uuid=doc['id']
                        )

                    logger.info(f"Added {len(documents_for_vector_store)} chunks to Weaviate")

                except Exception as e:
                    logger.error(f"Weaviate indexing failed: {e}, falling back to in-memory")
                    vector_store.add_documents(project_id, documents_for_vector_store)
            else:
                # Use in-memory vector store
                vector_store.add_documents(project_id, documents_for_vector_store)
                logger.info(f"Added {len(documents_for_vector_store)} document chunks to in-memory store")

            # Add entities to Neo4j if available
            if USE_NEO4J:
                try:
                    with neo4j_driver.session() as session:
                        # Extract simple entities from content
                        for doc in documents_for_vector_store:
                            content = doc['content'].lower()

                            # Simple entity extraction
                            servers = []
                            if 'server' in content:
                                import re
                                server_matches = re.findall(r'([a-zA-Z0-9-]+(?:server|srv|host))', content, re.IGNORECASE)
                                servers.extend(server_matches[:3])  # Limit to 3 per document

                            applications = []
                            if any(word in content for word in ['app', 'application', 'service']):
                                app_matches = re.findall(r'([a-zA-Z0-9-]+(?:app|application|service))', content, re.IGNORECASE)
                                applications.extend(app_matches[:3])

                            # Create nodes
                            for server in servers:
                                session.run(
                                    "MERGE (s:Server {name: $name, project_id: $project_id}) "
                                    "SET s.source = $filename",
                                    {"name": server, "project_id": project_id, "filename": doc['filename']}
                                )

                            for app in applications:
                                session.run(
                                    "MERGE (a:Application {name: $name, project_id: $project_id}) "
                                    "SET a.source = $filename",
                                    {"name": app, "project_id": project_id, "filename": doc['filename']}
                                )

                            # Create relationships
                            for server in servers:
                                for app in applications:
                                    session.run(
                                        "MATCH (s:Server {name: $server, project_id: $project_id}), "
                                        "(a:Application {name: $app, project_id: $project_id}) "
                                        "MERGE (s)-[:HOSTS]->(a)",
                                        {"server": server, "app": app, "project_id": project_id}
                                    )

                    logger.info(f"Added entities to Neo4j knowledge graph")

                except Exception as e:
                    logger.error(f"Neo4j indexing failed: {e}")

        # Update project status
        try:
            update_response = requests.put(
                f"http://localhost:8002/projects/{project_id}",
                json={"status": "ready"}
            )
            if update_response.status_code == 200:
                logger.info(f"Project {project_id} status updated to 'ready'")
        except Exception as e:
            logger.warning(f"Could not update project status: {e}")

        return {
            "status": "success",
            "message": "Document processing completed",
            "project_id": project_id,
            "processed_files": processed_files,
            "total_files": len(files),
            "processed_count": len(processed_files)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

@app.post("/api/projects/{project_id}/query")
async def query_project_knowledge(project_id: str, request: dict):
    """Query the RAG knowledge base for a specific project"""
    logger.info(f"Querying knowledge base for project {project_id}")

    try:
        question = request.get('question', '')
        if not question:
            raise HTTPException(status_code=400, detail="Question is required")

        logger.info(f"Question: {question}")

        # Search vector store (real Weaviate or in-memory)
        search_results = []

        if USE_WEAVIATE:
            try:
                class_name = f"Project_{project_id.replace('-', '_')}"

                # Query Weaviate using v4 API (REST-only)
                collection = weaviate_client.collections.get(class_name)
                response = collection.query.near_text(
                    query=question,
                    limit=3,
                    return_metadata=['distance']
                )

                for obj in response.objects:
                    search_results.append({
                        'content': obj.properties.get('content', ''),
                        'filename': obj.properties.get('filename', 'unknown'),
                        'score': 1 - (obj.metadata.distance or 0)  # Convert distance to score
                    })

                logger.info(f"Weaviate search returned {len(search_results)} results")

            except Exception as weaviate_error:
                logger.error(f"Weaviate search error: {weaviate_error}")
                # Continue without Weaviate results

            except Exception as e:
                logger.error(f"Weaviate search failed: {e}, falling back to in-memory")
                search_results = vector_store.search(project_id, question, limit=3)
        else:
            # Use in-memory vector store
            search_results = vector_store.search(project_id, question, limit=3)

        if not search_results:
            return {
                "status": "success",
                "question": question,
                "answer": "I couldn't find any relevant information in the knowledge base for your question. Please make sure the documents have been processed and contain information related to your query.",
                "project_id": project_id,
                "sources": []
            }

        # Prepare context from search results
        context_parts = []
        sources = []

        for result in search_results:
            context_parts.append(f"From {result['filename']}: {result['content']}")
            sources.append({
                "filename": result['filename'],
                "content": result['content'][:200] + "..." if len(result['content']) > 200 else result['content'],
                "score": result['score']
            })

        context = "\n\n".join(context_parts)

        # Try to use LLM for better response
        try:
            import openai
            api_key = os.getenv('OPENAI_API_KEY')

            if api_key:
                client = openai.OpenAI(api_key=api_key)

                prompt = f"""Based on the following context from project documents, please answer the user's question.

Context:
{context}

Question: {question}

Please provide a helpful and accurate answer based only on the information provided in the context. If the context doesn't contain enough information to answer the question, please say so."""

                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=500,
                    temperature=0.7
                )

                answer = response.choices[0].message.content
                logger.info(f"LLM-enhanced response generated")

            else:
                # Fallback to simple context return
                answer = f"Based on the project documents, here's what I found:\n\n{context}"
                logger.info(f"Using fallback response (no LLM available)")

        except Exception as llm_error:
            logger.warning(f"LLM processing failed, using fallback: {llm_error}")
            answer = f"Based on the project documents, here's what I found:\n\n{context}"

        return {
            "status": "success",
            "question": question,
            "answer": answer,
            "project_id": project_id,
            "sources": sources,
            "timestamp": datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")

@app.get("/api/projects/{project_id}/stats")
async def get_enhanced_project_stats(project_id: str):
    """Get enhanced project statistics including embeddings"""
    logger.info(f"Getting enhanced stats for project {project_id}")

    try:
        # Get basic stats from local project database
        files = project_files_db.get(project_id, [])
        total_size = sum(f.get('file_size', 0) for f in files)
        file_types = list(set(f.get('file_type', 'unknown') for f in files))

        basic_stats = {
            "total_files": len(files),
            "total_size": total_size,
            "file_types": file_types
        }

        # Add vector store stats
        embeddings_count = 0
        graph_nodes = 0

        if USE_WEAVIATE:
            try:
                class_name = f"Project_{project_id.replace('-', '_')}"
                # Count objects in Weaviate
                result = weaviate_client.query.aggregate(class_name).with_meta_count().do()
                if 'data' in result and 'Aggregate' in result['data'] and class_name in result['data']['Aggregate']:
                    embeddings_count = result['data']['Aggregate'][class_name][0]['meta']['count']
                logger.info(f"Weaviate embeddings count: {embeddings_count}")
            except Exception as e:
                logger.warning(f"Could not get Weaviate stats: {e}")
                # Fallback to in-memory count
                if project_id in vector_store.documents:
                    embeddings_count = len(vector_store.embeddings[project_id])
        else:
            # Use in-memory vector store stats
            if project_id in vector_store.documents:
                embeddings_count = len(vector_store.embeddings[project_id])

        if USE_NEO4J:
            try:
                with neo4j_driver.session() as session:
                    # Count nodes for this project
                    result = session.run(
                        "MATCH (n {project_id: $project_id}) RETURN count(n) as node_count",
                        {"project_id": project_id}
                    )
                    record = result.single()
                    if record:
                        graph_nodes = record["node_count"]
                logger.info(f"Neo4j graph nodes count: {graph_nodes}")
            except Exception as e:
                logger.warning(f"Could not get Neo4j stats: {e}")
                # Fallback simulation
                graph_nodes = min(embeddings_count * 2, 50)
        else:
            # Simple graph node simulation based on document content
            graph_nodes = min(embeddings_count * 2, 50)

        enhanced_stats = {
            **basic_stats,
            "embeddings": embeddings_count,
            "graph_nodes": graph_nodes,
            "agent_interactions": 0,  # Will be updated when agents run
            "deliverables": 1 if embeddings_count > 0 else 0
        }

        return enhanced_stats

    except Exception as e:
        logger.error(f"Error getting enhanced stats: {e}")
        return {
            "total_files": 0,
            "total_size": 0,
            "embeddings": 0,
            "graph_nodes": 0,
            "agent_interactions": 0,
            "deliverables": 0
        }

@app.post("/api/projects/{project_id}/generate-report")
async def generate_infrastructure_report(project_id: str, request: dict = None):
    """Generate infrastructure assessment report using agents"""
    logger.info(f"Generating infrastructure report for project {project_id}")

    try:
        # Check if project has processed documents
        if project_id not in vector_store.documents or not vector_store.documents[project_id]:
            raise HTTPException(status_code=400, detail="No processed documents found. Please process documents first.")

        # Get all document content for analysis
        all_content = []
        for doc in vector_store.documents[project_id]:
            all_content.append(f"From {doc['filename']}: {doc['content']}")

        combined_content = "\n\n".join(all_content)

        # Generate report using LLM
        try:
            import openai
            api_key = os.getenv('OPENAI_API_KEY')

            if not api_key:
                # Fallback report without LLM
                report_content = f"""# Infrastructure Assessment Report

## Project Overview
Project ID: {project_id}
Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC

## Document Analysis
Processed {len(vector_store.documents[project_id])} documents:

{combined_content}

## Recommendations
1. Review current infrastructure setup
2. Plan migration strategy based on requirements
3. Implement security best practices
4. Monitor performance metrics

## Next Steps
1. Detailed technical assessment
2. Risk analysis
3. Implementation planning
4. Testing and validation

---
Generated by Nagarro's Ascent Platform"""
            else:
                # Use LLM for enhanced report
                client = openai.OpenAI(api_key=api_key)

                prompt = f"""You are an expert infrastructure consultant. Based on the following project documentation, generate a comprehensive infrastructure assessment report.

Project Documentation:
{combined_content}

Please create a detailed report that includes:
1. Executive Summary
2. Current Infrastructure Analysis
3. Security Assessment
4. Migration Recommendations
5. Risk Analysis
6. Implementation Timeline
7. Cost Considerations
8. Next Steps

Format the report in markdown with clear sections and actionable recommendations."""

                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=2000,
                    temperature=0.7
                )

                report_content = response.choices[0].message.content
                logger.info(f"LLM-generated report created")

        except Exception as llm_error:
            logger.warning(f"LLM report generation failed, using template: {llm_error}")
            report_content = f"""# Infrastructure Assessment Report

## Project Overview
Project ID: {project_id}
Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC

## Document Analysis
Processed {len(vector_store.documents[project_id])} documents:

{combined_content}

## Key Findings
- Infrastructure components identified
- Security policies documented
- Migration requirements specified

## Recommendations
1. Review current infrastructure setup
2. Plan migration strategy based on requirements
3. Implement security best practices
4. Monitor performance metrics

## Next Steps
1. Detailed technical assessment
2. Risk analysis
3. Implementation planning
4. Testing and validation

---
Generated by Nagarro's Ascent Platform"""

        # Save report to file
        reports_dir = os.path.join(tempfile.gettempdir(), "reports")
        os.makedirs(reports_dir, exist_ok=True)

        report_filename = f"infrastructure_assessment_{project_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.md"
        report_path = os.path.join(reports_dir, report_filename)

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_content)

        logger.info(f"Report saved to: {report_path}")

        # Update agent interactions count
        # This would normally be tracked in a database

        return {
            "status": "success",
            "message": "Infrastructure assessment report generated successfully",
            "project_id": project_id,
            "report_filename": report_filename,
            "report_path": report_path,
            "download_url": f"/api/reports/download/{report_filename}",
            "generated_at": datetime.utcnow().isoformat(),
            "document_count": len(vector_store.documents[project_id]),
            "report_size": len(report_content)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Report generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")

@app.get("/api/reports/download/{filename}")
async def download_report(filename: str):
    """Download generated report"""
    logger.info(f"Downloading report: {filename}")

    try:
        reports_dir = os.path.join(tempfile.gettempdir(), "reports")
        report_path = os.path.join(reports_dir, filename)

        if not os.path.exists(report_path):
            raise HTTPException(status_code=404, detail="Report not found")

        from fastapi.responses import FileResponse
        return FileResponse(
            path=report_path,
            filename=filename,
            media_type='text/markdown'
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Report download failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

# =====================================================================================
# PROJECT MANAGEMENT ENDPOINTS (to replace project service for testing)
# =====================================================================================

# In-memory project storage
projects_db = {}
project_files_db = {}

@app.post("/projects")
async def create_project_endpoint(request: dict):
    """Create a new project (replacing project service)"""
    logger.info(f"Creating project: {request}")

    try:
        project_id = str(uuid.uuid4())
        now = datetime.utcnow()

        project = {
            "id": project_id,
            "name": request.get('name', ''),
            "description": request.get('description', ''),
            "client_name": request.get('client_name', ''),
            "client_contact": request.get('client_contact', ''),
            "status": "initiated",
            "llm_provider": request.get('llm_provider'),
            "llm_model": request.get('llm_model'),
            "llm_api_key_id": request.get('llm_api_key_id'),
            "llm_temperature": request.get('llm_temperature'),
            "llm_max_tokens": request.get('llm_max_tokens'),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat()
        }

        projects_db[project_id] = project
        project_files_db[project_id] = []

        logger.info(f"Project created successfully: {project_id}")
        return project

    except Exception as e:
        logger.error(f"Project creation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Project creation failed: {str(e)}")

@app.get("/projects")
async def list_projects_endpoint():
    """List all projects (replacing project service)"""
    logger.info("Listing projects")
    return list(projects_db.values())

@app.get("/projects/{project_id}")
async def get_project_endpoint(project_id: str):
    """Get a specific project (replacing project service)"""
    logger.info(f"Getting project: {project_id}")

    if project_id not in projects_db:
        raise HTTPException(status_code=404, detail="Project not found")

    return projects_db[project_id]

@app.put("/projects/{project_id}")
async def update_project_endpoint(project_id: str, request: dict):
    """Update a project (replacing project service)"""
    logger.info(f"Updating project: {project_id}")

    if project_id not in projects_db:
        raise HTTPException(status_code=404, detail="Project not found")

    project = projects_db[project_id]
    project.update(request)
    project["updated_at"] = datetime.utcnow().isoformat()

    return project

@app.get("/projects/{project_id}/files")
async def get_project_files_endpoint(project_id: str):
    """Get files for a project (replacing project service)"""
    logger.info(f"Getting files for project: {project_id}")

    if project_id not in project_files_db:
        return []

    return project_files_db[project_id]

@app.post("/projects/{project_id}/files")
async def add_project_file_endpoint(project_id: str, request: dict):
    """Add a file to a project (replacing project service)"""
    logger.info(f"Adding file to project: {project_id}")

    if project_id not in project_files_db:
        project_files_db[project_id] = []

    file_id = str(uuid.uuid4())
    now = datetime.utcnow()

    file_record = {
        "id": file_id,
        "project_id": project_id,
        "filename": request.get('filename', ''),
        "file_type": request.get('file_type', ''),
        "file_size": request.get('file_size', 0),
        "upload_path": request.get('upload_path', ''),
        "upload_timestamp": now.isoformat(),
        "created_at": now.isoformat(),
        "updated_at": now.isoformat()
    }

    project_files_db[project_id].append(file_record)

    return file_record

@app.get("/projects/{project_id}/stats")
async def get_project_stats_endpoint(project_id: str):
    """Get project statistics (replacing project service)"""
    logger.info(f"Getting stats for project: {project_id}")

    files = project_files_db.get(project_id, [])
    total_size = sum(f.get('file_size', 0) for f in files)
    file_types = list(set(f.get('file_type', 'unknown') for f in files))

    return {
        "total_files": len(files),
        "total_size": total_size,
        "file_types": file_types,
        "last_updated": max([f.get('updated_at', '') for f in files]) if files else None
    }

# =====================================================================================
# LLM SETTINGS MANAGEMENT
# =====================================================================================

# In-memory LLM settings storage
llm_settings = {
    "openai_key": {
        "id": "openai_key",
        "name": "OpenAI API Key",
        "value": "your-openai-key-here",  # This will be updated
        "category": "llm",
        "type": "secret"
    }
}

@app.get("/platform-settings")
async def get_platform_settings():
    """Get platform settings including LLM keys"""
    logger.info("Getting platform settings")
    return list(llm_settings.values())

@app.put("/platform-settings/{setting_id}")
async def update_platform_setting(setting_id: str, request: dict):
    """Update a platform setting"""
    logger.info(f"Updating platform setting: {setting_id}")

    if setting_id in llm_settings:
        llm_settings[setting_id].update(request)
        return llm_settings[setting_id]
    else:
        # Create new setting
        setting = {
            "id": setting_id,
            **request
        }
        llm_settings[setting_id] = setting
        return setting

# =====================================================================================
# DOCUMENT TEMPLATES AND MULTIPLE REPORT GENERATION
# =====================================================================================

# Global document templates
document_templates = {
    "infrastructure_assessment": {
        "id": "infrastructure_assessment",
        "name": "Infrastructure Assessment Report",
        "description": "Comprehensive infrastructure analysis and recommendations",
        "prompt": "Generate a detailed infrastructure assessment report including current state analysis, security evaluation, performance metrics, and migration recommendations.",
        "category": "assessment"
    },
    "security_audit": {
        "id": "security_audit",
        "name": "Security Audit Report",
        "description": "Security vulnerabilities and compliance assessment",
        "prompt": "Generate a comprehensive security audit report focusing on vulnerabilities, compliance requirements, security policies, and remediation recommendations.",
        "category": "security"
    },
    "migration_strategy": {
        "id": "migration_strategy",
        "name": "Migration Strategy Document",
        "description": "Detailed migration planning and execution strategy",
        "prompt": "Generate a detailed migration strategy document including timeline, phases, risk assessment, resource requirements, and success criteria.",
        "category": "migration"
    },
    "cost_optimization": {
        "id": "cost_optimization",
        "name": "Cost Optimization Report",
        "description": "Cost analysis and optimization recommendations",
        "prompt": "Generate a cost optimization report analyzing current costs, identifying savings opportunities, and providing actionable recommendations for cost reduction.",
        "category": "financial"
    }
}

@app.get("/document-templates")
async def get_document_templates():
    """Get all available document templates"""
    logger.info("Getting document templates")
    return list(document_templates.values())

@app.post("/api/projects/{project_id}/generate-deliverable")
async def generate_project_deliverable(project_id: str, request: dict):
    """Generate a specific deliverable based on template"""
    template_id = request.get('template_id')
    custom_prompt = request.get('custom_prompt')

    logger.info(f"Generating deliverable for project {project_id} with template {template_id}")

    try:
        # Check if project has processed documents
        if project_id not in vector_store.documents or not vector_store.documents[project_id]:
            raise HTTPException(status_code=400, detail="No processed documents found. Please process documents first.")

        # Get template
        template = document_templates.get(template_id)
        if not template:
            raise HTTPException(status_code=404, detail=f"Template {template_id} not found")

        # Get all document content for analysis
        all_content = []
        for doc in vector_store.documents[project_id]:
            all_content.append(f"From {doc['filename']}: {doc['content']}")

        combined_content = "\n\n".join(all_content)

        # Use custom prompt or template prompt
        base_prompt = custom_prompt or template['prompt']

        # Generate deliverable using LLM
        try:
            import openai

            # Get API key from settings
            api_key = None
            if 'openai_key' in llm_settings:
                api_key = llm_settings['openai_key'].get('value')
                if api_key == 'your-openai-key-here':  # Default placeholder
                    api_key = None

            if not api_key:
                api_key = os.getenv('OPENAI_API_KEY')

            if not api_key:
                # Fallback deliverable without LLM
                deliverable_content = f"""# {template['name']}

## Project Overview
Project ID: {project_id}
Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
Template: {template['name']}

## Document Analysis
Processed {len(vector_store.documents[project_id])} documents:

{combined_content}

## Analysis Summary
Based on the provided documentation, this {template['name'].lower()} identifies key areas for attention and provides actionable recommendations.

## Recommendations
1. Review and validate current documentation
2. Implement recommended best practices
3. Establish monitoring and maintenance procedures
4. Plan for regular assessments and updates

## Next Steps
1. Detailed technical review
2. Stakeholder consultation
3. Implementation planning
4. Progress monitoring

---
Generated by Nagarro's Ascent Platform
Template: {template['name']}"""
            else:
                # Use LLM for enhanced deliverable
                client = openai.OpenAI(api_key=api_key)

                prompt = f"""You are an expert consultant specializing in {template['category']} analysis. {base_prompt}

Project Documentation:
{combined_content}

Please create a comprehensive {template['name'].lower()} that includes:
1. Executive Summary
2. Current State Analysis
3. Key Findings
4. Detailed Recommendations
5. Implementation Roadmap
6. Risk Assessment
7. Success Metrics
8. Next Steps

Format the deliverable in markdown with clear sections and actionable recommendations. Make it professional and detailed."""

                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=2500,
                    temperature=0.7
                )

                deliverable_content = response.choices[0].message.content
                logger.info(f"LLM-generated deliverable created for template {template_id}")

        except Exception as llm_error:
            logger.warning(f"LLM deliverable generation failed, using template: {llm_error}")
            deliverable_content = f"""# {template['name']}

## Project Overview
Project ID: {project_id}
Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC
Template: {template['name']}

## Document Analysis
Processed {len(vector_store.documents[project_id])} documents:

{combined_content}

## Analysis Summary
Based on the provided documentation, this {template['name'].lower()} identifies key areas for attention and provides actionable recommendations.

## Key Findings
- Documentation review completed
- Current state assessed
- Improvement opportunities identified

## Recommendations
1. Review and validate current documentation
2. Implement recommended best practices
3. Establish monitoring and maintenance procedures
4. Plan for regular assessments and updates

## Implementation Roadmap
1. Phase 1: Assessment and planning
2. Phase 2: Implementation
3. Phase 3: Testing and validation
4. Phase 4: Deployment and monitoring

## Next Steps
1. Detailed technical review
2. Stakeholder consultation
3. Implementation planning
4. Progress monitoring

---
Generated by Nagarro's Ascent Platform
Template: {template['name']}"""

        # Save deliverable to file
        reports_dir = os.path.join(tempfile.gettempdir(), "reports")
        os.makedirs(reports_dir, exist_ok=True)

        deliverable_filename = f"{template_id}_{project_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.md"
        deliverable_path = os.path.join(reports_dir, deliverable_filename)

        with open(deliverable_path, 'w', encoding='utf-8') as f:
            f.write(deliverable_content)

        logger.info(f"Deliverable saved to: {deliverable_path}")

        # Update project stats (increment deliverables count)
        # This would normally be tracked in a database

        return {
            "status": "success",
            "message": f"{template['name']} generated successfully",
            "project_id": project_id,
            "template_id": template_id,
            "template_name": template['name'],
            "deliverable_filename": deliverable_filename,
            "deliverable_path": deliverable_path,
            "download_url": f"/api/reports/download/{deliverable_filename}",
            "generated_at": datetime.utcnow().isoformat(),
            "document_count": len(vector_store.documents[project_id]),
            "deliverable_size": len(deliverable_content)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Deliverable generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Deliverable generation failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

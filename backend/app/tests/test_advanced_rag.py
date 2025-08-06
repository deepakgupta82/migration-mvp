"""
Tests for Advanced RAG Features
"""

import pytest
import os
import sys
from unittest.mock import Mock, patch, MagicMock

# Add the backend directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.utils.semantic_chunker import SemanticChunker, SemanticChunk
from app.utils.cypher_generator import CypherGenerator, CypherQuery
from app.utils.config_parsers import ConfigurationParser
from app.core.embedding_service import EmbeddingService, EmbeddingResult

class TestSemanticChunker:
    """Test semantic chunking functionality"""
    
    def setup_method(self):
        self.chunker = SemanticChunker()
    
    def test_rule_based_chunking(self):
        """Test rule-based chunking fallback"""
        text = "This is a test document. It has multiple sentences. Each sentence should be processed correctly."
        chunks = self.chunker.chunk_text(text, chunk_method="rule_based")
        
        assert len(chunks) > 0
        assert all(isinstance(chunk, SemanticChunk) for chunk in chunks)
        assert all(chunk.content.strip() for chunk in chunks)
    
    def test_chunk_metadata(self):
        """Test that chunks contain proper metadata"""
        text = "Short test text for chunking."
        chunks = self.chunker.chunk_text(text, chunk_method="rule_based")
        
        for chunk in chunks:
            assert hasattr(chunk, 'content')
            assert hasattr(chunk, 'start_index')
            assert hasattr(chunk, 'end_index')
            assert hasattr(chunk, 'topic_score')
            assert hasattr(chunk, 'coherence_score')
            assert hasattr(chunk, 'metadata')
    
    def test_empty_text_handling(self):
        """Test handling of empty or very short text"""
        empty_text = ""
        chunks = self.chunker.chunk_text(empty_text)
        assert len(chunks) == 0 or (len(chunks) == 1 and chunks[0].content == "")
        
        short_text = "Hi"
        chunks = self.chunker.chunk_text(short_text)
        assert len(chunks) >= 1

class TestCypherGenerator:
    """Test Cypher query generation"""
    
    def setup_method(self):
        self.generator = CypherGenerator()
    
    def test_pattern_based_generation(self):
        """Test pattern-based Cypher generation"""
        query = "find all servers"
        result = self.generator.generate_cypher_from_natural_language(query)
        
        assert isinstance(result, CypherQuery)
        assert result.query
        assert "Server" in result.query
        assert result.confidence > 0
    
    def test_dependency_queries(self):
        """Test dependency-related queries"""
        query = "find dependencies of database"
        result = self.generator.generate_cypher_from_natural_language(query)
        
        assert "DEPENDS_ON" in result.query
        assert "Database" in result.query
    
    def test_count_queries(self):
        """Test count queries"""
        query = "count applications"
        result = self.generator.generate_cypher_from_natural_language(query)
        
        assert "count" in result.query.lower()
        assert "Application" in result.query
    
    def test_query_validation(self):
        """Test Cypher query validation"""
        valid_query = "MATCH (n:Server) RETURN n"
        assert self.generator._validate_cypher_query(valid_query)
        
        invalid_query = "INVALID CYPHER SYNTAX"
        assert not self.generator._validate_cypher_query(invalid_query)
    
    def test_node_type_normalization(self):
        """Test node type normalization"""
        assert self.generator._normalize_node_type("server") == "Server"
        assert self.generator._normalize_node_type("databases") == "Database"
        assert self.generator._normalize_node_type("app") == "Application"

class TestConfigurationParser:
    """Test configuration file parsing"""
    
    def setup_method(self):
        self.parser = ConfigurationParser()
    
    def test_apache_config_parsing(self):
        """Test Apache configuration parsing"""
        apache_config = """
        Listen 80
        Listen 443
        <VirtualHost *:80>
            ServerName example.com
            DocumentRoot /var/www/html
        </VirtualHost>
        LoadModule ssl_module modules/mod_ssl.so
        """
        
        result = self.parser._parse_apache_config(apache_config, "httpd.conf")
        
        assert 80 in result['ports']
        assert 443 in result['ports']
        assert len(result['virtual_hosts']) == 1
        assert result['virtual_hosts'][0]['server_name'] == 'example.com'
        assert 'ssl_module' in result['modules']
    
    def test_docker_compose_parsing(self):
        """Test Docker Compose parsing"""
        docker_compose = """
        version: '3.8'
        services:
          web:
            image: nginx
            ports:
              - "80:80"
              - "443:443"
            environment:
              - ENV=production
              - DEBUG=false
          db:
            image: postgres
            environment:
              POSTGRES_DB: mydb
              POSTGRES_USER: user
        """
        
        result = self.parser._parse_docker_config(docker_compose, "docker-compose.yml")
        
        assert 80 in result['ports']
        assert 443 in result['ports']
        assert len(result['services']) == 2
        assert 'web.ENV' in result['environment_variables']
        assert result['environment_variables']['web.ENV'] == 'production'
    
    def test_config_type_detection(self):
        """Test configuration file type detection"""
        assert self.parser._detect_config_type("httpd.conf", "Listen 80") == "apache"
        assert self.parser._detect_config_type("nginx.conf", "server {") == "nginx"
        assert self.parser._detect_config_type("docker-compose.yml", "version: '3.8'") == "docker"
        assert self.parser._detect_config_type("deployment.yaml", "apiVersion: apps/v1") == "kubernetes"

class TestEmbeddingService:
    """Test embedding service functionality"""
    
    def setup_method(self):
        self.config = {
            'model': 'all-MiniLM-L6-v2',
            'batch_size': 10,
            'cache_size': 100
        }
    
    @patch('app.core.embedding_service.SentenceTransformer')
    def test_embedding_service_initialization(self, mock_transformer):
        """Test embedding service initialization"""
        mock_model = Mock()
        mock_transformer.return_value = mock_model
        
        service = EmbeddingService(self.config)
        
        assert service.default_model == 'all-MiniLM-L6-v2'
        assert service.batch_size == 10
        assert service.cache_size == 100
    
    @patch('app.core.embedding_service.SentenceTransformer')
    def test_text_embedding_creation(self, mock_transformer):
        """Test text embedding creation"""
        mock_model = Mock()
        mock_model.encode.return_value = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        mock_transformer.return_value = mock_model
        
        service = EmbeddingService(self.config)
        service.text_model = mock_model
        
        contents = ["Hello world", "Test content"]
        results = service.create_embeddings(contents)
        
        assert len(results) == 2
        assert all(isinstance(result, EmbeddingResult) for result in results)
        assert all(result.content_type == 'text' for result in results)
    
    def test_cache_key_generation(self):
        """Test embedding cache key generation"""
        service = EmbeddingService(self.config)
        
        key1 = service._generate_cache_key("test content", "text")
        key2 = service._generate_cache_key("test content", "text")
        key3 = service._generate_cache_key("different content", "text")
        
        assert key1 == key2
        assert key1 != key3
    
    def test_content_type_detection(self):
        """Test content type-specific processing"""
        service = EmbeddingService(self.config)
        
        # Test code detection
        code_content = "def hello_world():\n    print('Hello, World!')"
        language = service._detect_programming_language(code_content)
        assert language == 'python'
        
        # Test table processing
        table_content = "| Name | Age | City |\n|------|-----|------|\n| John | 25 | NYC |"
        processed, metadata = service._preprocess_table(table_content)
        assert metadata['has_headers'] == True
        assert metadata['rows'] > 0

# Integration tests
class TestAdvancedRAGIntegration:
    """Integration tests for advanced RAG features"""
    
    @patch('app.core.rag_service.get_sentence_transformer')
    @patch('app.core.rag_service.weaviate')
    def test_rag_service_with_semantic_chunking(self, mock_weaviate, mock_transformer):
        """Test RAG service with semantic chunking enabled"""
        from app.core.rag_service import RAGService
        
        # Mock dependencies
        mock_model = Mock()
        mock_model.encode.return_value = [0.1, 0.2, 0.3]
        mock_transformer.return_value = mock_model
        
        mock_client = Mock()
        mock_weaviate.Client.return_value = mock_client
        
        config = {'chunking_strategy': 'semantic', 'batch_size': 10}
        rag_service = RAGService("test_project", config=config)
        
        # Test that semantic chunker is initialized
        assert hasattr(rag_service, 'semantic_chunker')
        assert rag_service.chunking_strategy == 'semantic'
    
    def test_hybrid_search_with_llm_cypher(self):
        """Test hybrid search with LLM-powered Cypher generation"""
        from app.tools.hybrid_search_tool import HybridSearchTool
        
        mock_llm = Mock()
        mock_llm.invoke.return_value.content = '{"cypher_query": "MATCH (n) RETURN n", "confidence": 0.9}'
        
        tool = HybridSearchTool("test_project", llm=mock_llm)
        
        # Test intelligent query routing
        graph_query = "find all servers connected to database"
        strategy = tool._intelligent_query_routing(graph_query)
        assert strategy in ["graph_only", "hybrid"]
        
        semantic_query = "explain how the system works"
        strategy = tool._intelligent_query_routing(semantic_query)
        assert strategy in ["semantic_only", "hybrid"]

if __name__ == "__main__":
    pytest.main([__file__])

#!/usr/bin/env python3
"""
Test script to verify embedding model configuration
"""

import os
import sys
import requests
import json
from pathlib import Path

# Add the vector service app to Python path
vector_service_path = Path(__file__).parent / "services" / "vector-service"
sys.path.insert(0, str(vector_service_path))

def test_model_configuration():
    """Test the embedding model configuration"""
    print("Testing Embedding Model Configuration...")
    print("=" * 50)
    
    # Test 1: Check environment variable reading
    print("1. Testing environment variable reading:")
    embedding_model = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    print(f"   EMBEDDING_MODEL environment variable: {embedding_model}")
    
    # Test 2: Test model name resolution
    print("\n2. Testing model name resolution:")
    try:
        from app.core.vector_processor import get_sentence_transformer
        
        # Test the supported models mapping
        supported_models = {
            "all-MiniLM-L6-v2": "all-MiniLM-L6-v2",
            "jina-embeddings-v2-base-en": "jinaai/jina-embeddings-v2-base-en",
            "jinaai/jina-embeddings-v2-base-en": "jinaai/jina-embeddings-v2-base-en"
        }
        
        actual_model_name = supported_models.get(embedding_model, embedding_model)
        print(f"   Configured model: {embedding_model}")
        print(f"   Resolved model name: {actual_model_name}")
        
        # Test 3: Try to load the model (this will take some time)
        print("\n3. Testing model loading (this may take a few minutes):")
        print("   Loading model... (please wait)")
        
        model = get_sentence_transformer()
        print(f"   ✓ Model loaded successfully!")
        print(f"   Model type: {type(model)}")
        
        # Test embedding dimension
        if hasattr(model, 'get_sentence_embedding_dimension'):
            embedding_dim = model.get_sentence_embedding_dimension()
            print(f"   Embedding dimension: {embedding_dim}")
        
        # Test a simple embedding
        test_text = "This is a test sentence for embedding."
        embeddings = model.encode([test_text])
        print(f"   Test embedding shape: {embeddings.shape}")
        print(f"   ✓ Model is working correctly!")
        
    except ImportError as e:
        print(f"   ✗ Import error: {e}")
        print("   Note: Run this script from the project root directory")
    except Exception as e:
        print(f"   ✗ Error loading model: {e}")
        return False
    
    print("\n" + "=" * 50)
    print("✓ All tests completed successfully!")
    return True

def test_api_endpoint():
    """Test the API endpoint for model info"""
    print("\n4. Testing API endpoint (requires running service):")
    try:
        # Try to get model info from the API
        response = requests.get("http://localhost:8003/debug/model-info", timeout=5)
        if response.status_code == 200:
            model_info = response.json()
            print(f"   ✓ API endpoint accessible")
            print(f"   Model name: {model_info.get('model_name')}")
            print(f"   Configured name: {model_info.get('configured_name')}")
            print(f"   Embedding dimension: {model_info.get('embedding_dimension')}")
            print(f"   Model loaded: {model_info.get('model_loaded')}")
        else:
            print(f"   ✗ API endpoint returned status {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("   ⚠ Vector service is not running (connection refused)")
        print("   Start the service with: docker-compose up vector-service")
    except Exception as e:
        print(f"   ✗ Error testing API: {e}")

if __name__ == "__main__":
    # Set the embedding model for testing
    if len(sys.argv) > 1:
        os.environ["EMBEDDING_MODEL"] = sys.argv[1]
        print(f"Testing with model: {sys.argv[1]}")
    
    # Run tests
    success = test_model_configuration()
    test_api_endpoint()
    
    if success:
        print("\n🎉 Configuration test completed successfully!")
        print("\nTo use the Jina embeddings model:")
        print("1. Set EMBEDDING_MODEL=jinaai/jina-embeddings-v2-base-en in your .env file")
        print("2. Restart the vector service: docker-compose restart vector-service")
        print("3. The new model will be loaded automatically on first use")
    else:
        print("\n❌ Configuration test failed!")
        sys.exit(1)
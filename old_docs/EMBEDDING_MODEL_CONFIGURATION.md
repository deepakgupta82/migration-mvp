# Embedding Model Configuration Guide

## Overview

The Nagarro Ascent Platform now supports configurable embedding models for vector search and document processing. You can choose between different embedding models based on your performance, quality, and resource requirements.

## Supported Models

### 1. Jina Embeddings v2 Base EN (Recommended)
- **Model Name**: `jinaai/jina-embeddings-v2-base-en`
- **Dimensions**: 768
- **Description**: High-quality multilingual embeddings optimized for semantic search
- **Use Case**: Production deployments requiring high-quality embeddings
- **Memory Usage**: ~120MB
- **Load Time**: ~12-15 seconds

### 2. all-MiniLM-L6-v2 (Default)
- **Model Name**: `all-MiniLM-L6-v2`
- **Dimensions**: 384
- **Description**: Lightweight sentence transformer model
- **Use Case**: Development and testing environments
- **Memory Usage**: ~90MB
- **Load Time**: ~8-10 seconds

## Configuration

### Environment Variable Configuration

Set the `EMBEDDING_MODEL` environment variable in your `.env` file:

```bash
# For Jina Embeddings v2 (recommended for production)
EMBEDDING_MODEL=jinaai/jina-embeddings-v2-base-en

# For MiniLM (default, good for development)
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

### Model Aliases

The following aliases are supported for convenience:

- `jina-embeddings-v2-base-en` → `jinaai/jina-embeddings-v2-base-en`
- `all-MiniLM-L6-v2` → `all-MiniLM-L6-v2`

## Frontend Configuration

The embedding model can also be configured through the frontend interface:

1. Navigate to **Settings** → **Chunking & Embedding**
2. Select your preferred embedding model from the dropdown
3. Click **Save Configuration**

Available options:
- `all-MiniLM-L6-v2 (384 dim)` - Lightweight model for development
- `Jina Embeddings v2 Base EN (768 dim)` - High-quality model for production
- `all-mpnet-base-v2 (768 dim)` - Alternative high-quality model
- `OpenAI Ada-002 (1536 dim)` - OpenAI's embedding model (requires API key)

## Model Manager

Monitor and manage your embedding models through the Model Manager interface:

1. Navigate to **Settings** → **Model Manager**
2. View model status, memory usage, and performance metrics
3. Load/unload models as needed
4. Configure model startup and caching settings

### Model Manager Features

- **Real-time Status**: Monitor which models are loaded and their performance
- **Memory Management**: Track memory usage across all loaded models
- **Performance Metrics**: View load times and usage statistics
- **Background Loading**: Models can be loaded in the background for optimal performance
- **Configuration**: Set models to load on startup, enable caching, and configure retry settings

## Performance Considerations

### Jina Embeddings v2 Base EN
- **Pros**: Higher quality embeddings, better semantic understanding
- **Cons**: Larger memory footprint, longer load times
- **Best for**: Production environments, high-quality search requirements

### all-MiniLM-L6-v2
- **Pros**: Faster loading, lower memory usage, good baseline performance
- **Cons**: Lower dimensional embeddings, may not capture complex semantics as well
- **Best for**: Development, testing, resource-constrained environments

## Migration Guide

### Switching from all-MiniLM-L6-v2 to Jina Embeddings

1. **Update Environment Configuration**:
   ```bash
   EMBEDDING_MODEL=jinaai/jina-embeddings-v2-base-en
   ```

2. **Restart Vector Service**:
   ```bash
   docker-compose restart vector-service
   ```

3. **Re-index Existing Documents** (Optional but recommended):
   - The new model will be used for all new documents automatically
   - To benefit from improved embeddings for existing documents, consider re-processing them
   - Use the document reprocessing endpoint or delete and re-upload documents

4. **Monitor Performance**:
   - Check the Model Manager to ensure the new model loads successfully
   - Monitor memory usage and performance metrics
   - Verify search quality improvements

## API Integration

### Get Model Information

```bash
GET /api/vector/debug/model-info
```

Response:
```json
{
  "model_name": "jinaai/jina-embeddings-v2-base-en",
  "configured_name": "jinaai/jina-embeddings-v2-base-en",
  "max_seq_length": 512,
  "embedding_dimension": 768,
  "model_loaded": true
}
```

### Model Status Check

```bash
GET /api/vector/model-status
```

Response:
```json
{
  "embedding_model_loaded": true,
  "global_model_loaded": true,
  "model_loading_in_progress": false,
  "service_ready": true
}
```

## Troubleshooting

### Common Issues

1. **Model fails to load**:
   - Check internet connectivity for downloading model files
   - Ensure sufficient memory is available
   - Verify the model name is correct

2. **Performance issues**:
   - Monitor memory usage in Model Manager
   - Consider using the lighter all-MiniLM-L6-v2 model for development
   - Enable model caching for better performance

3. **Search quality changes**:
   - Different models may produce different embedding spaces
   - Consider re-indexing existing documents after model changes
   - Test search quality with your specific use cases

### Logs and Monitoring

Check the vector service logs for model loading information:

```bash
docker-compose logs vector-service | grep -i "embedding\|model"
```

Key log messages:
- `Loading embedding model: jinaai/jina-embeddings-v2-base-en`
- `Successfully loaded embedding model`
- `Background model loading completed`

## Best Practices

1. **Use Jina Embeddings for Production**: Higher quality embeddings improve search accuracy
2. **Enable Model Caching**: Keep frequently used models in memory
3. **Monitor Resource Usage**: Track memory and performance through Model Manager
4. **Test Before Deployment**: Validate search quality with your specific data
5. **Document Model Changes**: Keep track of when and why you change embedding models

## Future Enhancements

- Support for additional embedding models (e.g., OpenAI, Cohere)
- Dynamic model switching without service restart
- Model performance benchmarking tools
- Automatic model recommendation based on use case
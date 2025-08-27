# Complete Document Deletion Workflow

## Overview

This document describes the complete document deletion workflow that was implemented to fix the issue where document deletion was not working properly. Previously, when users tried to delete a document, only the database record was removed, but the actual files, embeddings, and graph data remained in the system.

## Problem Statement

When users attempted to delete a document through the UI:
1. The file record was removed from the project service database
2. The actual files in storage (uploads, parsed documents, chunks, etc.) were NOT deleted
3. The embeddings in the vector database (Weaviate) were NOT deleted
4. The nodes and relationships in the graph database (Neo4j) were NOT deleted
5. Related files (.md, .json) were NOT cleaned up

This led to data inconsistency and wasted storage resources.

## Solution

A complete document deletion workflow was implemented that handles all aspects of document cleanup:

### 1. Backend Gateway Endpoint

**Endpoint**: `DELETE /api/projects/{project_id}/files/{file_id}`

This new endpoint orchestrates the complete deletion process:

1. **Database Cleanup**: Deletes the file record from the project service database
2. **Storage Cleanup**: Deletes all related files from storage (raw uploads, parsed documents, chunks, entities)
3. **Vector Cleanup**: Deletes all embeddings associated with the document from Weaviate
4. **Graph Cleanup**: Deletes all nodes and relationships associated with the document from Neo4j
5. **Event Publishing**: Publishes a `document_deleted` event for stats updates

### 2. Storage Service Enhancement

**Endpoint**: `DELETE /api/storage/projects/{project_id}/documents/{filename}`

This endpoint deletes a document and all related files:
- Main file
- `.md` files (parsed documents)
- `.json` files (metadata, chunks, entities)

### 3. Vector Service Enhancement

**Endpoint**: `DELETE /api/vectors/projects/{project_id}/documents/{filename}`

This endpoint deletes all vectors where the `document_id` property matches the filename.

### 4. Graph Service Enhancement

**Endpoint**: `DELETE /api/graphs/projects/{project_id}/documents/{filename}`

This endpoint deletes all nodes and relationships where the `document_id` property matches the filename.

## Implementation Details

### Frontend Changes

1. **API Service**: Updated `deleteProjectFile()` to return the complete response instead of void
2. **FileUpload Component**: Enhanced `handleDeleteFile()` and `handleBulkDelete()` to show detailed deletion results

### Backend Changes

1. **Gateway Router**: Added complete deletion endpoint that orchestrates all cleanup operations
2. **Service Client**: Added methods for document-specific deletions in storage, vector, and graph services
3. **Storage Service**: Added document-specific deletion endpoint
4. **Vector Service**: Added document-specific deletion endpoint using Weaviate filters
5. **Graph Service**: Added document-specific deletion endpoint using Neo4j queries

## API Endpoints

### Complete Document Deletion
```
DELETE /api/projects/{project_id}/files/{file_id}
```

**Response**:
```json
{
  "message": "File deleted successfully",
  "project_id": "project-uuid",
  "file_id": "file-uuid",
  "filename": "document.pdf",
  "deleted_files": [
    "uploads_raw/document.pdf",
    "uploads_parsed/document.md",
    "chunks/document_chunk_1.json"
  ],
  "embeddings_deleted": 42,
  "graph_nodes_deleted": 15,
  "graph_relationships_deleted": 23
}
```

### Bulk Document Deletion
```
DELETE /api/projects/{project_id}/files
Content-Type: application/json

{
  "file_ids": ["file-id-1", "file-id-2", "file-id-3"]
}
```

## Testing

### Test Scripts

1. **Python Test Script**: `test_document_deletion.py`
2. **PowerShell Test Script**: `test_document_deletion.ps1`

### Manual Testing

1. Upload a document through the UI
2. Process the document to create embeddings and graph data
3. Verify the document appears in storage, vector, and graph services
4. Delete the document through the UI
5. Verify all related data is removed from all services

## Benefits

1. **Complete Cleanup**: All document-related data is properly removed
2. **Resource Efficiency**: No orphaned files, embeddings, or graph data
3. **Data Consistency**: System state remains consistent after deletion
4. **User Feedback**: Detailed information about what was deleted
5. **Event-Driven**: Stats are automatically updated through event publishing

## Future Improvements

1. **Soft Delete**: Implement soft delete with retention period
2. **Audit Trail**: Add deletion logging for compliance
3. **Batch Operations**: Optimize bulk deletion for better performance
4. **Rollback Mechanism**: Add ability to restore accidentally deleted documents
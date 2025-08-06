# Embedchain Installation Issues - Temporary Changes

## Issue
Embedchain package failed to install due to missing Visual C++ 14.0+ build tools required for `chroma-hnswlib` compilation.

## Error Details
```
error: Microsoft Visual C++ 14.0 or greater is required. Get it with "Microsoft C++ Build Tools": https://visualstudio.microsoft.com/visual-cpp-build-tools/
ERROR: Failed building wheel for chroma-hnswlib
```

## Temporary Changes Made

### 1. Tool Import Changes
**Files Modified:**
- `backend/app/tools/lessons_learned_tool.py` - Line 1
- `backend/app/tools/project_knowledge_base_tool.py` - Line 1

**Change:**
```python
# FROM:
from crewai_tools import BaseTool

# TO:
from crewai.tools import BaseTool
```

**Reason:** `crewai_tools` package imports `embedchain` which is not available, causing import failures.

### 2. Tools Affected by Embedchain Dependency
The following tools may have limited functionality until embedchain is installed:
- `HybridSearchTool` - Uses embedchain for semantic search
- `LessonsLearnedTool` - May use embedchain for knowledge retrieval
- `ProjectKnowledgeBaseQueryTool` - Uses embedchain for document processing

### 3. Crew Factory Impact
The crew factory imports these tools, so some advanced features may be temporarily disabled:
- Cross-modal synthesis capabilities
- Advanced semantic search
- Enhanced document processing

## Actions to Take After Installing Embedchain

1. **Revert Import Changes:**
   ```bash
   # Revert lessons_learned_tool.py
   sed -i 's/from crewai.tools import BaseTool/from crewai_tools import BaseTool/' backend/app/tools/lessons_learned_tool.py
   
   # Revert project_knowledge_base_tool.py  
   sed -i 's/from crewai.tools import BaseTool/from crewai_tools import BaseTool/' backend/app/tools/project_knowledge_base_tool.py
   ```

2. **Install Embedchain:**
   ```bash
   pip install embedchain
   ```

3. **Test Full Functionality:**
   ```bash
   python -c "from app.tools.hybrid_search_tool import HybridSearchTool; print('✅ All tools working')"
   ```

## Installation Requirements for Embedchain
- Visual C++ 14.0 or greater
- Microsoft C++ Build Tools
- Windows SDK (if on Windows)

## Current Status
- ✅ Core reorganization completed
- ✅ Basic tools working (RAG, Graph)
- ⚠️ Advanced tools temporarily limited
- ⚠️ Embedchain-dependent features disabled

## Next Steps
1. Install Visual C++ Build Tools
2. Install embedchain package
3. Revert temporary changes
4. Test full platform functionality

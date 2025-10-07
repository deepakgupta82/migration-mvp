# Hardcoded LLM Configuration Removal & Process-Specific Config Implementation

## Analysis Summary

### Hardcoded LLM Configurations Found

1. **services/ai-agent-service/main.py** (Line 162):
   - `"model": os.getenv("AUTOGEN_MODEL", "gpt-4")`
   - Fallback to `gpt-4` when env var not set

2. **services/ai-agent-service/app/core/autogen_copilot.py**:
   - Line 152: `model = self._base.get("model") or "gpt-4"`
   - Line 234: `"model": self.llm_config.get("model", "gpt-4")`
   - Line 246: `"model": self.llm_config.get("model", "gpt-4")`
   - Line 810: `"model": self.llm_config.get("model", "gemini-2.5-pro")`

3. **services/ai-agent-service/app/routers/agents.py** (Line 204):
   - `fallback_model = os.getenv("FALLBACK_LLM_MODEL", "gpt-3.5-turbo")`

4. **services/ai-agent-service/app/utils/_local_config_parsers.py** (Line 43):
   - `model = self.get(["llm", "model"], os.getenv("LLM_MODEL", "gpt-4o-mini"))`

### Process-Specific LLM Config Status

The LLM service already supports the `CONVERSATION` process type in `LLMProcessType` enum, but it's not being used by the autogen/discussion flow.

### Required Changes

1. **Add conversation_llm_config** to project model
2. **Update autogen initialization** to use project-scoped config with conversation process type
3. **Remove all hardcoded fallbacks** and require proper configuration
4. **Update UI** to allow setting conversation LLM config
5. **Add AWS credentials UI** for MCP servers

## Implementation Plan

### 1. Database Schema Update
Add `conversation_llm_config` column to projects table

### 2. AutoGen Configuration
- Use `conversation` process type when calling LLM service
- Remove hardcoded `gpt-4`, `gemini-2.5-pro` fallbacks
- Fetch process-specific config or project default

### 3. UI Updates
- Add "Conversation/Discussion" tab in project LLM settings
- Add AWS credentials fields in MCP server configuration modal

### 4. Testing
- Build and test AWS Pricing MCP Docker container
- Verify autogen agents use proper LLM config
- Test CrewAI agents with MCP tools

# AI Agent Service

## Service Overview

The AI Agent Service is an advanced AI agent orchestration service that operates on port 8008. It provides CrewAI-based multi-agent workflows, AutoGen copilot integration, and intelligent task orchestration for complex document processing and analysis tasks.

### Key Features

- **CrewAI Integration**: Multi-agent collaboration frameworks
- **AutoGen Copilot**: Conversational AI assistant with WebSocket support
- **Task Orchestration**: Complex workflow management
- **Document Analysis**: AI-powered document processing pipelines
- **Real-time Collaboration**: WebSocket-based agent interactions
- **Tool Integration**: Extensible tool ecosystem
- **Conversation Management**: Persistent conversation history
- **Background Processing**: Asynchronous task execution

## Functionality

### Core Capabilities

1. **Agent Orchestration**
   - CrewAI workflow execution
   - Agent role assignment and coordination
   - Task decomposition and delegation
   - Multi-agent collaboration patterns

2. **AutoGen Integration**
   - Conversational AI assistant
   - Real-time WebSocket communication
   - Context-aware responses
   - Multi-turn conversation management

3. **Document Processing**
   - AI-powered document analysis
   - Intelligent summarization
   - Content extraction and structuring
   - Quality assessment and validation

4. **Tool Management**
   - Extensible tool ecosystem
   - Tool discovery and registration
   - Tool execution and monitoring
   - Performance analytics

### Dependencies

- **PostgreSQL**: Conversation and task data storage
- **Redis**: Caching and session management
- **WebSocket Service**: Real-time communication
- **Document Service**: Document processing integration
- **LLM Service**: Language model access

## APIs/Endpoints

### Agent Operations
- `POST /api/agents/crew/execute` - Execute CrewAI workflows
- `GET /api/agents/crew/status/{task_id}` - Get workflow status
- `POST /api/agents/tools/execute` - Execute agent tools
- `GET /api/agents/tools/list` - List available tools

### AutoGen Operations
- `POST /api/autogen/chat` - Send message to AutoGen copilot
- `GET /api/autogen/conversations` - Get conversation history
- `POST /api/autogen/conversations/{id}/continue` - Continue conversation
- `WS /api/autogen/ws` - WebSocket connection for real-time chat

### Document Analysis
- `POST /api/agents/analyze/document` - AI document analysis
- `POST /api/agents/summarize` - Document summarization
- `POST /api/agents/extract` - Content extraction tasks

## Data Models

### CrewAI Task Structure
```json
{
  "task_id": "task_123",
  "workflow_type": "document_analysis",
  "agents": ["researcher", "analyst", "writer"],
  "input_data": {...},
  "status": "running",
  "progress": 0.75,
  "results": {...}
}
```

### AutoGen Message Structure
```json
{
  "message_id": "msg_456",
  "conversation_id": "conv_789",
  "role": "user",
  "content": "Analyze this document...",
  "timestamp": "2024-01-01T12:00:00.000000",
  "metadata": {
    "model": "gpt-4",
    "tokens": 150
  }
}
```

### Tool Execution Structure
```json
{
  "tool_id": "tool_101",
  "name": "document_parser",
  "parameters": {...},
  "execution_id": "exec_202",
  "status": "completed",
  "result": {...},
  "execution_time": 2.3
}
```

## Key Components

### AIAgentProcessor (`app/core/agent_processor.py`)

**Core agent orchestration engine**

- **Responsibilities**:
  - CrewAI workflow management
  - Agent coordination and task delegation
  - Tool execution and monitoring
  - Performance tracking and optimization

### AutoGen Copilot (`app/core/autogen_copilot.py`)

**Conversational AI assistant**

- **Responsibilities**:
  - Natural language processing
  - Context management
  - Response generation
  - Conversation persistence

### Conversation Repository (`app/repository/conversations.py`)

**Conversation data management**

- **Responsibilities**:
  - Message storage and retrieval
  - Conversation history management
  - Metadata indexing and search

## Data Flow

### Agent Workflow Execution

1. **Task Submission**: Workflow request received
2. **Agent Assignment**: Appropriate agents selected
3. **Task Decomposition**: Complex tasks broken down
4. **Parallel Execution**: Agents work concurrently
5. **Result Aggregation**: Outputs combined and validated
6. **Response Delivery**: Final results returned

### AutoGen Conversation Flow

1. **Message Reception**: User message received
2. **Context Retrieval**: Conversation history loaded
3. **AI Processing**: Message analyzed and responded to
4. **Response Generation**: Context-aware reply created
5. **Persistence**: Conversation updated in database
6. **Real-time Delivery**: Response sent via WebSocket

## Complete Working Details

### Configuration

**Environment Variables**:
- `CREWAI_MAX_AGENTS`: Maximum agents per workflow
- `AUTOGEN_MODEL`: Default AutoGen model
- `AGENT_TIMEOUT`: Maximum execution time per agent
- `CONVERSATION_RETENTION`: Conversation history retention period

### Supported Agent Types

- **Researcher**: Information gathering and analysis
- **Analyst**: Data analysis and insights
- **Writer**: Content generation and summarization
- **Validator**: Quality assurance and validation

### Performance Characteristics

- **Workflow Execution**: 10-300 seconds depending on complexity
- **Concurrent Workflows**: Limited by available agents
- **Memory Usage**: Scales with conversation history
- **Response Time**: Sub-second for simple queries

### Error Handling

- **Agent Failures**: Fallback to alternative agents
- **Timeout Handling**: Graceful degradation on timeouts
- **Resource Limits**: Automatic scaling and resource management
- **Recovery**: Automatic retry with exponential backoff

### Monitoring and Observability

- **Workflow Metrics**: Success rates, execution times
- **Agent Performance**: Individual agent statistics
- **Conversation Analytics**: Usage patterns and quality metrics
- **System Health**: Resource usage and error rates

### Security Considerations

- **Access Control**: Project-scoped agent access
- **Input Validation**: Message sanitization and safety checks
- **Rate Limiting**: Request throttling per user
- **Audit Logging**: All agent interactions logged

### Scaling Considerations

- **Horizontal Scaling**: Stateless agent execution
- **Load Balancing**: Workflow distribution across instances
- **Caching**: Conversation and result caching
- **Resource Pooling**: Shared agent resource management
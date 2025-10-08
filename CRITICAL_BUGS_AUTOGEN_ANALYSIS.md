# Critical Bugs in AutoGen Multi-Agent Conversation System

## Investigation Date: October 8, 2025
## Session Analyzed: 92557046-d26a-4a88-84c5-fa11790eb124

---

## Bug #1: Message Duplication (CRITICAL)

### Symptoms
- Every message appears exactly 2 times in exports
- User question appears 2x (identical timestamps)
- Each agent response appears 2x (identical timestamps)
- Total: 20 unique messages = 40 duplicates in database

### Root Cause
**Found in:** `autogen_copilot.py` lines 795-825 + repository `add_messages()`

AutoGen's `result.messages` already contains ALL messages (user + agents). The duplication happens because:

1. **AutoGen returns full conversation**: `result.messages` includes user's TextMessage("user", content)
2. **No deduplication**: `add_messages()` inserts every message without checking for duplicates
3. **Timestamp collision**: All duplicates have EXACT same timestamp (not just similar)

### Evidence from Export
```markdown
## user
*2025-10-08T19:53:13.196513+00:00* | Type: `TextMessage`
User Question: what are the different network devices present in client environment

## user  
*2025-10-08T19:53:13.196513+00:00* | Type: `TextMessage`  ← EXACT duplicate
User Question: what are the different network devices present in client environment
```

### Fix Required
**Option 1 (Recommended)**: Add deduplication in `add_messages()` based on (session_id, timestamp, source, content_hash)

**Option 2**: Filter duplicates before calling `add_messages()` in autogen_copilot.py

**Code Location**: 
- `services/ai-agent-service/app/repository/conversations.py` line 195 (`add_messages`)
- `services/ai-agent-service/app/core/autogen_copilot.py` line 795-900 (message assembly)

---

## Bug #2: No Multi-Agent Rotation (CRITICAL)

### Symptoms
- Only `migration_architect` responds despite selecting multiple agents
- No other agents participate (cost_analyst, security_specialist, devops_expert)
- RoundRobinGroupChat created but doesn't rotate speakers

### Root Cause
**Found in:** `autogen_copilot.py` lines 680-684

```python
group_chat = RoundRobinGroupChat(
    participants=active_agents,
    termination_condition=MaxMessageTermination(max_messages=20)
)
```

**Possible Issues:**
1. **Agent list not populated correctly**: `active_agents` may only contain migration_architect
2. **Termination too early**: `max_messages=20` might be counting supervisor messages too
3. **AutoGen bug**: RoundRobinGroupChat may require explicit speaker selection order

### Investigation Needed
1. Log `len(active_agents)` and `agent_names` before creating RoundRobinGroupChat
2. Check if AutoGen is falling back to single agent due to initialization failure
3. Verify all agents have valid `model_client` configured

### Evidence from Logs
```
INFO: Retrieved 3 active agents  ← Should show which 3
INFO: Created RoundRobinGroupChat  ← No rotation details logged
```

### Fix Required
1. Add verbose logging: `logger.info(f"RoundRobinGroupChat participants: {[a.name for a in active_agents]}")`
2. Check AutoGen docs for correct RoundRobinGroupChat usage
3. May need to use `GroupChat` with custom `speaker_selection_method` instead

**Code Location**:
- `services/ai-agent-service/app/core/autogen_copilot.py` lines 660-685

---

## Bug #3: Missing Supervisor Messages (CRITICAL)

### Symptoms
- Supervisor agent's orchestration messages never appear in exports
- Only final agent responses are logged
- No "Agent handoff" or "Routing to X" messages visible

### Root Cause
**Found in:** AutoGen's internal message filtering

AutoGen's supervisor (GroupChatManager) generates internal messages that are NOT included in `result.messages`. These include:
- Agent selection decisions
- Routing logic
- Conversation state transitions

### Current Message Flow (What We See)
```
User → migration_architect → migration_architect → migration_architect → ...
```

### Expected Message Flow (What Should Happen)
```
User → Supervisor("Routing to migration_architect") → migration_architect 
     → Supervisor("Next speaker: cost_analyst") → cost_analyst
     → Supervisor("Final summary needed") → migration_architect
```

### Fix Required
**Option 1**: Hook into AutoGen's message stream to capture supervisor messages
- May require custom `GroupChatManager` subclass
- Override `_process_received_message()` to log all messages

**Option 2**: Add manual logging in agent responses
- Each agent logs: "Received from supervisor: X"
- Inject supervisor transitions as synthetic messages

**Option 3**: Use AutoGen's logging callbacks
- Configure AutoGen to log all messages (including internal)
- Parse logs and insert supervisor messages into database

**Code Location**:
- `services/ai-agent-service/app/core/autogen_copilot.py` lines 680-710
- May need to modify AutoGen import and create custom GroupChat subclass

---

## Bug #4: No Conversation-Style Logging (Enhancement)

### Symptoms
- Exports show flat list of messages without conversational flow
- No indication of WHY each agent was selected
- Missing context about agent-to-agent handoffs

### Root Cause
Current system only logs END results, not the PROCESS:
- Agent selection logic invisible
- No "thinking" or "reasoning" messages
- Missing intermediate supervisor decisions

### User Expectation (from request)
> "I want the whole conversation style logging so that we can see clearly how initial question propagates between the agents until the end."

### Example: Desired Output
```markdown
## user
What network devices are in the environment?

## supervisor [INTERNAL]
Analyzing question type: Infrastructure inventory query
Selected agent: migration_architect (reason: Network topology expertise)
Confidence: 0.95

## migration_architect  
Based on the documentation, I've identified...
[response content]

## supervisor [INTERNAL]
migration_architect provided architectural analysis.
Next needed: Cost implications
Selected agent: cost_analyst
Confidence: 0.88

## cost_analyst
From a cost perspective, the SD-WAN and extranet router will require...
[response content]

## supervisor [INTERNAL]
Conversation complete. All aspects covered.
Generating summary.
```

### Fix Required
1. **Capture supervisor decisions**: Log after each agent selection
2. **Add reasoning transparency**: Show WHY each agent was chosen
3. **Include confidence scores**: If AutoGen provides them
4. **Mark internal messages**: Add `[INTERNAL]` tag for supervisor messages
5. **Preserve in export**: Include supervisor messages in all export formats

**Implementation Strategy**:
1. Create custom `ConversationLogger` class
2. Hook into AutoGen's message pipeline
3. Inject supervisor messages as `source="supervisor", message_type="orchestration"`
4. Persist to `conversation_messages` table with special flag
5. Filter from UI (but include in exports with [INTERNAL] marker)

**Code Location**:
- `services/ai-agent-service/app/core/autogen_copilot.py` (new logging hooks)
- `services/ai-agent-service/app/repository/conversations.py` (add `is_internal` column)
- `services/ai-agent-service/app/routers/autogen.py` export logic (include internal messages)

---

## Priority Fix Order

### P0 (Immediate - Breaks Functionality)
1. **Fix #2: Multi-agent rotation** - Currently only 1 agent responds (defeats purpose)
2. **Fix #1: Message duplication** - Exports are unusable with 2x duplicates

### P1 (High - User Experience)
3. **Fix #3: Supervisor message logging** - Needed for transparency
4. **Fix #4: Conversation-style logging** - Requested explicitly by user

### P2 (Medium - Already on TODO)
5. LLM response caching (prevent duplicate calls)
6. Context gathering performance (7m52s → <10s)

---

## Next Steps

1. ✅ Create this analysis document
2. ⏳ Fix #1: Add deduplication to `add_messages()`
3. ⏳ Fix #2: Debug RoundRobinGroupChat agent selection
4. ⏳ Fix #3: Capture supervisor messages
5. ⏳ Fix #4: Implement conversation-style logging
6. ⏳ Test with actual conversation (same question as session 92557046...)
7. ⏳ Verify export shows: User → Supervisor → Agent1 → Supervisor → Agent2 flow


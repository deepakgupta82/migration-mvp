"""Conversation persistence layer for AutoGen discussions.

Stores conversation sessions and messages in PostgreSQL using existing
psycopg2 connection (from AIAgentProcessor). Lightweight – avoids adding
SQLAlchemy just for this feature.

Tables (auto-created if missing):

conversation_sessions(
    id SERIAL PK,
    session_id TEXT UNIQUE,
    created_at TIMESTAMPTZ DEFAULT now(),
    last_updated TIMESTAMPTZ DEFAULT now(),
    context JSONB NULL,
    participating_agents TEXT[] NULL,
    status TEXT,
    message_count INT DEFAULT 0,
    recommendations JSONB NULL,
    action_items JSONB NULL,
    summary JSONB NULL,
    conversation_mode TEXT NULL,
    autogen_enabled BOOLEAN
);

conversation_messages(
    id SERIAL PK,
    session_id TEXT REFERENCES conversation_sessions(session_id) ON DELETE CASCADE,
    ts TIMESTAMPTZ DEFAULT now(),
    source TEXT NULL,
    agent_name TEXT NULL,
    message_type TEXT NULL,
    content TEXT,
    raw JSONB NULL
);
"""

from __future__ import annotations

import logging
import json
from typing import Any, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger("conversation-repository")

_repository_singleton = None  # set in startup


def set_conversation_repository(repo: "ConversationRepository"):
    global _repository_singleton
    _repository_singleton = repo


def get_conversation_repository() -> "ConversationRepository":
    if _repository_singleton is None:
        raise RuntimeError("ConversationRepository not initialized")
    return _repository_singleton


class ConversationRepository:
    def __init__(self, db_connection):
        self.conn = db_connection

    def ensure_tables(self):
        cur = self.conn.cursor()
        # Create sessions table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_sessions (
                id SERIAL PRIMARY KEY,
                session_id TEXT UNIQUE,
                created_at TIMESTAMPTZ DEFAULT now(),
                last_updated TIMESTAMPTZ DEFAULT now(),
                context JSONB,
                participating_agents TEXT[] ,
                status TEXT,
                message_count INT DEFAULT 0,
                recommendations JSONB,
                action_items JSONB,
                summary JSONB,
                conversation_mode TEXT,
                autogen_enabled BOOLEAN
            );
            """
        )
        # Create messages table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_messages (
                id SERIAL PRIMARY KEY,
                session_id TEXT REFERENCES conversation_sessions(session_id) ON DELETE CASCADE,
                ts TIMESTAMPTZ DEFAULT now(),
                source TEXT,
                agent_name TEXT,
                message_type TEXT,
                content TEXT,
                raw JSONB,
                prompt_tokens INTEGER DEFAULT 0,
                completion_tokens INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                usage_metadata JSONB
            );
            """
        )
        # Indexes
        cur.execute("CREATE INDEX IF NOT EXISTS idx_conversation_messages_session ON conversation_messages(session_id);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_conversation_sessions_created ON conversation_sessions(created_at);")
        
        # Add token columns to existing table if they don't exist (migration)
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='conversation_messages' AND column_name='prompt_tokens') THEN
                    ALTER TABLE conversation_messages ADD COLUMN prompt_tokens INTEGER DEFAULT 0;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='conversation_messages' AND column_name='completion_tokens') THEN
                    ALTER TABLE conversation_messages ADD COLUMN completion_tokens INTEGER DEFAULT 0;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='conversation_messages' AND column_name='total_tokens') THEN
                    ALTER TABLE conversation_messages ADD COLUMN total_tokens INTEGER DEFAULT 0;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='conversation_messages' AND column_name='usage_metadata') THEN
                    ALTER TABLE conversation_messages ADD COLUMN usage_metadata JSONB;
                END IF;
            END $$;
        """)
        
        self.conn.commit()
        cur.close()
        logger.info("Conversation tables ensured (session + messages with token tracking)")

    def upsert_session(
        self,
        session_id: str,
        context: Optional[Dict[str, Any]],
        structured_result: Dict[str, Any],
        user_message: str
    ):
        cur = self.conn.cursor()
        participating_agents = structured_result.get("participating_agents")
        recommendations = structured_result.get("recommendations")
        action_items = structured_result.get("action_items")
        summary = structured_result.get("summary")
        status = structured_result.get("status")
        conversation_mode = structured_result.get("conversation_mode")
        autogen_enabled = structured_result.get("autogen_enabled")
        message_count = structured_result.get("message_count", 0)

        # Pre-serialize JSON fields safely (psycopg2 needs strings for ::jsonb when passing via %s)
        def _to_json(value: Any):
            if value is None:
                return None
            try:
                return json.dumps(value, default=str)
            except Exception:
                return json.dumps({"_serialization_error": True, "repr": repr(value)}, default=str)

        cur.execute(
            """
            INSERT INTO conversation_sessions (
                session_id, context, participating_agents, status, message_count,
                recommendations, action_items, summary, conversation_mode, autogen_enabled, last_updated
            ) VALUES (
                %s, %s::jsonb, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s, now()
            )
            ON CONFLICT (session_id) DO UPDATE SET
                last_updated = now(),
                status = EXCLUDED.status,
                message_count = conversation_sessions.message_count + %s,
                participating_agents = EXCLUDED.participating_agents,
                recommendations = EXCLUDED.recommendations,
                action_items = EXCLUDED.action_items,
                summary = EXCLUDED.summary,
                conversation_mode = EXCLUDED.conversation_mode,
                autogen_enabled = EXCLUDED.autogen_enabled
            ;
            """,
            (
                session_id,
                None if context is None else _to_json(context),
                participating_agents,
                status,
                message_count,
                _to_json(recommendations),
                _to_json(action_items),
                _to_json(summary),
                conversation_mode,
                autogen_enabled,
                message_count,
            ),
        )
        self.conn.commit()
        cur.close()

    def add_messages(self, session_id: str, messages: List[Dict[str, Any]]):
        if not messages:
            return
        cur = self.conn.cursor()
        def _to_json(value: Any):
            if value is None:
                return None
            try:
                return json.dumps(value, default=str)
            except Exception:
                return json.dumps({"_serialization_error": True, "repr": repr(value)}, default=str)

        # Track message signatures for deduplication (Critical Bug #1 fix)
        # Deduplication based on: session_id + timestamp + source + content (first 200 chars)
        inserted_count = 0
        duplicate_count = 0
        
        for m in messages:
            # Create deduplication key: timestamp + source + content_hash
            timestamp = m.get("timestamp") or datetime.utcnow().isoformat()
            source = m.get("source")
            content = m.get("content", "")
            
            # Check if this exact message already exists (prevents Critical Bug #1: duplicates)
            # Use timestamp + source + content prefix for fast duplicate detection
            content_prefix = content[:200] if content else ""
            
            cur.execute(
                """
                SELECT COUNT(*) FROM conversation_messages 
                WHERE session_id = %s 
                AND ts = %s 
                AND source = %s 
                AND LEFT(content, 200) = %s
                """,
                (session_id, timestamp, source, content_prefix)
            )
            exists = cur.fetchone()[0] > 0
            
            if exists:
                duplicate_count += 1
                logger.debug(f"Skipping duplicate message: session={session_id}, source={source}, ts={timestamp[:19]}")
                continue  # Skip duplicate
            
            # Extract token usage from message if available
            usage = m.get("usage") or {}
            prompt_tokens = usage.get("prompt_tokens", 0) if isinstance(usage, dict) else 0
            completion_tokens = usage.get("completion_tokens", 0) if isinstance(usage, dict) else 0
            total_tokens = usage.get("total_tokens", 0) if isinstance(usage, dict) else 0
            
            # Store full usage metadata as JSONB for flexibility
            usage_metadata = _to_json(usage) if usage else None
            
            cur.execute(
                """
                INSERT INTO conversation_messages (
                    session_id, ts, source, agent_name, message_type, content, raw,
                    prompt_tokens, completion_tokens, total_tokens, usage_metadata
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s::jsonb
                );
                """,
                (
                    session_id,
                    timestamp,
                    source,
                    source,  # agent_name same as source for now
                    m.get("message_type"),
                    content,
                    _to_json(m),
                    prompt_tokens,
                    completion_tokens,
                    total_tokens,
                    usage_metadata,
                ),
            )
            inserted_count += 1
        
        self.conn.commit()
        cur.close()
        
        if duplicate_count > 0:
            logger.info(f"Deduplicated {duplicate_count} messages, inserted {inserted_count} new messages for session {session_id}")
        else:
            logger.debug(f"Inserted {inserted_count} messages for session {session_id}")

    def save_conversation_result(
        self,
        session_id: str,
        user_message: str,
        context: Optional[Dict[str, Any]],
        structured_result: Dict[str, Any],
    ):
        try:
            # Upsert session first
            self.upsert_session(session_id, context, structured_result, user_message)
            # Persist messages (full conversation list)
            full_messages = structured_result.get("full_conversation") or structured_result.get("messages") or []
            self.add_messages(session_id, full_messages)
        except Exception as e:
            logger.error(f"Failed saving conversation {session_id}: {e}")

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT session_id, created_at, last_updated, context, participating_agents, status, message_count, recommendations, action_items, summary, conversation_mode, autogen_enabled FROM conversation_sessions WHERE session_id=%s",
            (session_id,),
        )
        row = cur.fetchone()
        cur.close()
        if not row:
            return None
        # psycopg2 RealDictCursor would give dict; but we used default cursor possibly – adapt
        if not isinstance(row, dict):
            columns = [
                "session_id",
                "created_at",
                "last_updated",
                "context",
                "participating_agents",
                "status",
                "message_count",
                "recommendations",
                "action_items",
                "summary",
                "conversation_mode",
                "autogen_enabled",
            ]
            row = dict(zip(columns, row))
        return row

    def get_session_history(self, session_id: str) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute(
            "SELECT id, ts, source, agent_name, message_type, content, raw FROM conversation_messages WHERE session_id=%s ORDER BY ts ASC, id ASC",
            (session_id,),
        )
        rows = cur.fetchall()
        cur.close()
        history: List[Dict[str, Any]] = []
        if rows:
            # Determine columns
            cols = [desc[0] for desc in cur.description] if cur.description else []
            for r in rows:
                if isinstance(r, dict):
                    history.append(r)
                else:
                    history.append(dict(zip(cols, r)))
        return history

    def list_sessions(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT session_id, created_at, last_updated, message_count, participating_agents, status
            FROM conversation_sessions
            ORDER BY last_updated DESC
            LIMIT %s OFFSET %s
            """,
            (limit, offset),
        )
        rows = cur.fetchall()
        cur.close()
        sessions: List[Dict[str, Any]] = []
        if rows:
            cols = ["session_id", "created_at", "last_updated", "message_count", "participating_agents", "status"]
            for r in rows:
                if isinstance(r, dict):
                    sessions.append(r)
                else:
                    sessions.append(dict(zip(cols, r)))
        return sessions

    def delete_session(self, session_id: str) -> int:
        cur = self.conn.cursor()
        # Count messages first
        cur.execute("SELECT COUNT(*) FROM conversation_messages WHERE session_id=%s", (session_id,))
        msg_count = cur.fetchone()[0]
        cur.execute("DELETE FROM conversation_sessions WHERE session_id=%s", (session_id,))
        deleted = cur.rowcount
        self.conn.commit()
        cur.close()
        return msg_count if deleted else 0

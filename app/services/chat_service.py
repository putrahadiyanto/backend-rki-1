from datetime import datetime, timezone
import os
import asyncio
from typing import Dict
from app.db.mongodb import get_database
from app.models.chat import ChatSession, ChatMessage
from app.services.llm_service import generate_chat_response, generate_quiz_tool
from langchain.messages import AIMessage, HumanMessage, SystemMessage
from app.utils.logger import get_logger

logger = get_logger()


class ChatService:
    """Manages chat sessions and messages in MongoDB."""

    COLLECTION = "chat_sessions"
    
    # Max recent messages sent as LLM context to keep token usage reasonable
    MAX_CONTEXT_MESSAGES = 20

    def _col(self):
        return get_database().get_collection(self.COLLECTION)

    def __init__(self):
        # Per-session in-memory locks to serialize operations for the same session
        self._session_locks: Dict[str, asyncio.Lock] = {}
        # Semaphore to limit concurrent LLM calls across the service
        max_concurrency = int(os.getenv("LLM_MAX_CONCURRENCY"))
        self._llm_semaphore = asyncio.Semaphore(max_concurrency)

    async def _get_lock(self, session_id: str) -> asyncio.Lock:
        lock = self._session_locks.get(session_id)
        if lock is None:
            lock = asyncio.Lock()
            self._session_locks[session_id] = lock
        return lock

    # ── Session CRUD ─────────────────────────────────────────────

    async def create_session(self, username: str) -> str:
        """Create a new empty chat session, return its session_id."""
        session = ChatSession(username=username)
        await self._col().insert_one(session.model_dump())
        logger.info(f"Created session {session.session_id} for {username}")
        return session.session_id

    async def get_sessions(self, username: str) -> list[dict]:
        """Return a summary list of all sessions for a user (no messages)."""
        cursor = self._col().find(
            {"username": username},
            {"_id": 0, "session_id": 1, "title": 1, "created_at": 1, "updated_at": 1},
        ).sort("updated_at", -1)
        return await cursor.to_list(length=100)

    async def get_session(self, session_id: str, username: str) -> dict | None:
        """Return a full session document including messages."""
        return await self._col().find_one(
            {"session_id": session_id, "username": username},
            {"_id": 0},
        )

    async def delete_session(self, session_id: str, username: str) -> bool:
        """Delete a session. Returns True if a document was deleted."""
        result = await self._col().delete_one(
            {"session_id": session_id, "username": username}
        )
        return result.deleted_count > 0

    # ── Message helpers ──────────────────────────────────────────

    async def add_message(
        self, session_id: str, username: str, role: str, content: str
    ) -> ChatMessage:
        """Append a message and update the session timestamp."""
        msg = ChatMessage(role=role, content=content)
        now = datetime.now(timezone.utc)

        update: dict = {
            "$push": {"messages": msg.model_dump()},
            "$set": {"updated_at": now},
        }

        # Auto-title from first user message
        session = await self.get_session(session_id, username)
        if session and not session.get("title") and role == "user":
            update["$set"]["title"] = content[:80]

        await self._col().update_one(
            {"session_id": session_id, "username": username},
            update,
        )
        return msg

    # ── Orchestrator ─────────────────────────────────────────────

    async def generate_and_store(
        self, session_id: str, username: str, user_prompt: str
    ) -> dict:
        """
        1. Store the user message
        2. Build context from recent history
        3. Call the LLM
        4. Store the assistant reply
        5. Return both messages
        """
        # Use a per-session lock so concurrent requests targeting the same
        # session are serialized and cannot race the read-modify-write steps.
        lock = await self._get_lock(session_id)
        
        async with lock:
            # 1. Store user message
            user_msg = await self.add_message(session_id, username, "user", user_prompt)

            # 2. Build context from recent history (excluding the message just added)
            session = await self.get_session(session_id, username)
            history: list[dict] = []
            if session:
                all_messages = session.get("messages", [])
                # Exclude the last message (the one we just stored) and limit context
                prior = all_messages[:-1]
                recent = prior[-self.MAX_CONTEXT_MESSAGES:]
                history = [{"role": m["role"], "content": m["content"]} for m in recent]

            # Convert history dicts into LangChain message objects
            chat_history_msgs = []
            for m in history:
                role = m.get("role")
                content = m.get("content", "")
                if role == "user":
                    chat_history_msgs.append(HumanMessage(content=content))
                elif role == "assistant":
                    chat_history_msgs.append(AIMessage(content=content))
                elif role == "system":
                    chat_history_msgs.append(SystemMessage(content=content))
                else:
                    chat_history_msgs.append(HumanMessage(content=content))

            # 3. Call the LLM with history, but limit global concurrent LLM calls
            async with self._llm_semaphore:
                result = await generate_chat_response(user_prompt, chat_history_msgs)

            # 4. Store assistant reply
            assistant_msg = await self.add_message(
                session_id, username, "assistant", result["answer"]
            )

        extra = {"action": result.get("action"), "game_data": result.get("game_data")} if result else {}
        return {
            "user_message": user_msg.model_dump(),
            "assistant_message": assistant_msg.model_dump(),
            "thoughts": result.get("thoughts", "") if result else "",
            **extra,
        }

    async def generate_quiz(self, username: str, topic: str) -> dict:
        """Get or create the user's latest session and generate a quiz for the topic.

        Returns a dict containing `session_id` and `quiz` payload.
        """
        # Get user's sessions (already returned sorted by updated_at desc)
        sessions = await self.get_sessions(username)
        if sessions:
            latest_session_id = sessions[0].get("session_id")
        else:
            latest_session_id = await self.create_session(username)

        # Inline the generate_quiz_for_session logic here
        session = await self.get_session(latest_session_id, username)
        history: list[dict] = []
        if session:
            all_messages = session.get("messages", [])
            recent = all_messages[-self.MAX_CONTEXT_MESSAGES:]
            history = [{"role": m["role"], "content": m["content"]} for m in recent]

        # Convert into LangChain message objects
        chat_history_msgs = []
        for m in history:
            role = m.get("role")
            content = m.get("content", "")
            if role == "user":
                chat_history_msgs.append(HumanMessage(content=content))
            elif role == "assistant":
                chat_history_msgs.append(AIMessage(content=content))
            elif role == "system":
                chat_history_msgs.append(SystemMessage(content=content))
            else:
                chat_history_msgs.append(HumanMessage(content=content))

        # Call the async quiz tool directly (it already runs blocking LLM calls in a thread)
        quiz_result = await generate_quiz_tool(topic, chat_history_msgs)

        return {"session_id": latest_session_id, "quiz": quiz_result}

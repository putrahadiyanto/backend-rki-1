from datetime import datetime, timezone
from app.db.mongodb import get_database
from app.models.chat import ChatSession, ChatMessage
from app.services.llm_service import generate_response
from app.utils.logger import get_logger

logger = get_logger()


class ChatService:
    """Manages chat sessions and messages in MongoDB."""

    COLLECTION = "chat_sessions"
    
    # Max recent messages sent as LLM context to keep token usage reasonable
    MAX_CONTEXT_MESSAGES = 20

    def _col(self):
        return get_database().get_collection(self.COLLECTION)

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

        # 3. Call the LLM with history
        result = await generate_response(user_prompt, history)

        # 4. Store assistant reply
        assistant_msg = await self.add_message(
            session_id, username, "assistant", result["answer"]
        )

        extra = {"action": result["action"], "game_data": result["game_data"]} if "game_data" in result else {}
        return {
            "user_message": user_msg.model_dump(),
            "assistant_message": assistant_msg.model_dump(),
            "thoughts": result.get("thoughts", ""),
            **extra,
        }

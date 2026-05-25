import os
import uuid
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

class ConversationManager:
    def __init__(self, max_history: int = 3, mongo_uri: Optional[str] = None, db_name: Optional[str] = None, max_context_tokens: int = 1000):
        self.max_history = max_history
        self.max_context_tokens = max_context_tokens
        mongo_uri = mongo_uri or os.getenv("MONGODB_URI") or os.getenv("MONGO_URI") or "mongodb://127.0.0.1:27017"
        db_name = db_name or os.getenv("MONGO_DB_NAME") or "rag_service"
        self.client = MongoClient(
            mongo_uri,
            maxPoolSize=50,  # Limit connection pool
            minPoolSize=10,
            maxIdleTimeMS=45000
        )
        self.db = self.client[db_name]
        self.sessions = self.db.get_collection("sessions")
        self.messages = self.db.get_collection("messages")
        self.summaries = self.db.get_collection("conversation_summaries")
        # in-memory cache for recent exchanges
        self._cache: Dict[str, List[Tuple[str, str, datetime]]] = {}
        # ensure indexes
        try:
            self.messages.create_index([("session_id", 1), ("created_at", 1)])
            self.sessions.create_index("session_id", unique=True)
            self.summaries.create_index("session_id", unique=True)
        except Exception:
            pass

        self.enable_summarization = os.getenv("ENABLE_TURN_SUMMARIZATION", "true").lower() == "true"

    def create_session(self) -> str:
        session_id = str(uuid.uuid4())
        self.sessions.insert_one({"session_id": session_id, "created_at": datetime.utcnow()})
        self._cache[session_id] = []
        return session_id

    def _summarize_assistant_response(self, user_query: str, assistant_response: str, groq_client) -> str:
        """Create a compact summary of assistant's response (max 100 tokens) for future conversation context."""
        if groq_client is None or not assistant_response:
            return assistant_response[:400]  # fallback truncation

        summary_prompt = f"""Summarize this legal assistant response in under 100 tokens, preserving key facts and legal points:

User asked: {user_query}
Assistant answered: {assistant_response}

Concise summary:"""

        try:
            resp = groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": summary_prompt}],
                temperature=0.1,
                max_tokens=150
            )
            return resp.choices[0].message.content.strip()
        except Exception:
            return assistant_response[:400]  # fallback

    def add_exchange(self, session_id: str, user_message: str, bot_response: str, debug: Optional[dict] = None, groq_client=None):
        """Add exchange and create compact summary of bot_response for future context."""
        now = datetime.utcnow()
        self.messages.insert_one({
            "session_id": session_id,
            "sender": "user",
            "text": user_message,
            "created_at": now,
            "debug": debug.get("user") if isinstance(debug, dict) else None
        })

        # Create compact summary of assistant response for conversation context
        if self.enable_summarization and groq_client:
            response_summary = self._summarize_assistant_response(user_message, bot_response, groq_client)
        else:
            response_summary = bot_response[:400]  # truncate fallback

        # Insert assistant message with both full response and summary
        assistant_doc = {
            "session_id": session_id,
            "sender": "assistant",
            "text": bot_response,  # full response shown to user
            "summary_for_context": response_summary,  # compact version for next turn
            "created_at": datetime.utcnow(),
            "debug": debug.get("assistant") if isinstance(debug, dict) else None
        }
        self.messages.insert_one(assistant_doc)

        # Update in-memory cache with SUMMARY instead of full response
        self._cache.setdefault(session_id, []).append((user_message, response_summary, now))
        if len(self._cache[session_id]) > self.max_history:
            self._cache[session_id] = self._cache[session_id][-self.max_history:]

    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimate (1 token ≈ 4 chars)."""
        if not text:
            return 0
        return max(1, len(text) // 4)

    def get_summary(self, session_id: str) -> Optional[str]:
        doc = self.summaries.find_one({"session_id": session_id})
        return doc.get("summary") if doc else None

    def save_summary(self, session_id: str, summary: str):
        self.summaries.update_one({"session_id": session_id}, {"$set": {"summary": summary, "updated_at": datetime.utcnow()}}, upsert=True)

    def ensure_summary_limit(self, session_id: str, groq_client, max_summary_tokens: int = 500):
        """Ensure stored summary for session_id is under max_summary_tokens by re-summarizing using groq_client."""
        if groq_client is None:
            return  # cannot summarize without LLM client

        summary_doc = self.summaries.find_one({"session_id": session_id})
        if not summary_doc:
            return

        current_summary = summary_doc.get("summary", "")
        current_tokens = self._estimate_tokens(current_summary)
        if current_tokens <= max_summary_tokens:
            return

        # Create a summarization prompt to compress the summary
        prompt = f"""You are a legal assistant. Compress the following conversation summary to keep essential legal points and user concerns.
Keep the summary under {max_summary_tokens} tokens and preserve key legal provisions, issues, and conclusions.

Original summary:
{current_summary}
"""
        try:
            resp = groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": "You are an expert legal summarizer."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=max(200, max_summary_tokens)  # request reasonable token budget for summary
            )
            new_summary = resp.choices[0].message.content
            # Save compressed summary
            self.save_summary(session_id, new_summary)
        except Exception as e:
            # fallback: truncate the existing summary conservatively
            truncated = current_summary[: max_summary_tokens * 4]  # approx char limit
            self.save_summary(session_id, truncated)
            print(f"Warning: summary re-compression failed for session {session_id}: {e}")

    def get_conversation_context(self, session_id: str, groq_client=None) -> str:
        """Get conversation context using response summaries (not full responses) for efficiency."""
        # Load from cache (which now has summaries)
        exchanges = self._cache.get(session_id, [])
        if not exchanges:
            # Rebuild from DB using summary_for_context field
            msgs = list(self.messages.find({"session_id": session_id}).sort("created_at", -1).limit(self.max_history*2))
            msgs = list(reversed(msgs))
            exchanges = []
            i = 0
            while i < len(msgs):
                if msgs[i]["sender"] == "user":
                    user_msg = msgs[i]["text"]
                    bot_summary = ""
                    if i+1 < len(msgs) and msgs[i+1]["sender"] == "assistant":
                        bot_summary = msgs[i+1].get("summary_for_context", msgs[i+1]["text"][:400])
                        i += 2
                    else:
                        i += 1
                    exchanges.append((user_msg, bot_summary, msgs[max(i-1,0)]["created_at"]))
                else:
                    i += 1
            self._cache[session_id] = exchanges[-self.max_history:]

        # Build context from user queries + assistant summaries (not full responses)
        parts = []
        for u, summary, _ in self._cache.get(session_id, []):
            parts.append(f"User: {u}")
            parts.append(f"Assistant: {summary}")
        return "\n".join(parts)

    def reset_session(self, session_id: str):
        self.messages.delete_many({"session_id": session_id})
        self.summaries.delete_many({"session_id": session_id})
        self.sessions.delete_many({"session_id": session_id})
        if session_id in self._cache:
            del self._cache[session_id]

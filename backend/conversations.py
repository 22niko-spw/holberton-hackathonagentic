import json
from datetime import datetime

from backend.db import get_connection

# Palier 4 — persistance : la conversation elle-même (pas seulement les
# actions) survit à un rechargement de page. Le navigateur retient quel
# conversation_id est "en cours" (juste un pointeur en localStorage, pas le
# contenu) : "reprendre la plus récente" se ferait rouvrir l'ancienne
# conversation juste après avoir cliqué "Nouvelle conversation".


def create_conversation() -> int:
    conn = get_connection()
    now = datetime.now().isoformat()
    cursor = conn.execute(
        "INSERT INTO conversations (created_at, updated_at) VALUES (?, ?)", (now, now)
    )
    conn.commit()
    conversation_id = cursor.lastrowid
    conn.close()
    return conversation_id


def conversation_exists(conversation_id: int) -> bool:
    conn = get_connection()
    row = conn.execute("SELECT 1 FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
    conn.close()
    return row is not None


def append_message(
    conversation_id: int,
    role: str,
    content: str | None,
    action_ids: list[int] | None = None,
    trace: list[dict] | None = None,
    usage: dict | None = None,
) -> None:
    conn = get_connection()
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO messages (conversation_id, role, content, action_ids, trace, usage, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            conversation_id,
            role,
            content,
            json.dumps(action_ids) if action_ids else None,
            json.dumps(trace) if trace else None,
            json.dumps(usage) if usage else None,
            now,
        ),
    )
    conn.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conversation_id))
    conn.commit()
    conn.close()


def get_history_messages(conversation_id: int, limit: int) -> list[dict]:
    """Format attendu par l'API Groq (role/content) : de quoi reprendre le
    fil sans redemander au RH ce qu'il vient de dire."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT role, content FROM messages "
        "WHERE conversation_id = ? AND role IN ('user', 'assistant') "
        "ORDER BY id DESC LIMIT ?",
        (conversation_id, limit),
    ).fetchall()
    conn.close()
    return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]


def get_conversation(conversation_id: int) -> dict | None:
    """Pour la restauration au chargement de la page : cette conversation
    précise (celle que le navigateur a retenue), avec tous ses messages
    dans l'ordre — jamais "la plus récente en base", qui rouvrirait une
    conversation qu'on vient justement de quitter via "Nouvelle conversation"."""
    conn = get_connection()
    conv = conn.execute("SELECT id FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
    if conv is None:
        conn.close()
        return None

    rows = conn.execute(
        "SELECT role, content, action_ids, trace, usage FROM messages "
        "WHERE conversation_id = ? ORDER BY id",
        (conversation_id,),
    ).fetchall()
    conn.close()

    messages = [
        {
            "role": row["role"],
            "content": row["content"],
            "action_ids": json.loads(row["action_ids"]) if row["action_ids"] else [],
            "trace": json.loads(row["trace"]) if row["trace"] else [],
            "usage": json.loads(row["usage"]) if row["usage"] else {},
        }
        for row in rows
    ]
    return {"conversation_id": conversation_id, "messages": messages}

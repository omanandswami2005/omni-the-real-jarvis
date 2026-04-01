import re

with open("backend/app/services/session_service.py", "r") as f:
    content = f.read()

# 1. get_session
content = content.replace(
    "snap = self.db.collection(COLLECTION).document(session_id).get()",
    "snap = await asyncio.to_thread(self.db.collection(COLLECTION).document(session_id).get)"
)

# 2. create_session
content = content.replace(
    "self.db.collection(COLLECTION).document(session_id).set(doc)",
    "await asyncio.to_thread(self.db.collection(COLLECTION).document(session_id).set, doc)"
)

# 3. list_sessions
content = content.replace(
    "return [SessionListItem(id=snap.id, **snap.to_dict()) for snap in query.stream()]",
    "snaps = await asyncio.to_thread(lambda: list(query.stream()))\n        return [SessionListItem(id=snap.id, **snap.to_dict()) for snap in snaps]"
)

# 4. update_session
content = content.replace(
    "self.db.collection(COLLECTION).document(session_id).update(updates)",
    "await asyncio.to_thread(self.db.collection(COLLECTION).document(session_id).update, updates)"
)

# 5. delete_session
content = content.replace(
    "self.db.collection(COLLECTION).document(session_id).delete()",
    "await asyncio.to_thread(self.db.collection(COLLECTION).document(session_id).delete)"
)

# 6. link_adk_session
content = content.replace(
    "self.db.collection(COLLECTION).document(session_id).update(\n            {\n                \"adk_session_id\": adk_session_id,\n                \"updated_at\": datetime.now(UTC),\n            }\n        )",
    "await asyncio.to_thread(self.db.collection(COLLECTION).document(session_id).update, {\n            \"adk_session_id\": adk_session_id,\n            \"updated_at\": datetime.now(UTC),\n        })"
)

# 7. increment_message_count
content = content.replace(
    "self.db.collection(COLLECTION).document(session_id).update(\n            {\n                \"message_count\": firestore.Increment(count),\n                \"updated_at\": datetime.now(UTC),\n            }\n        )",
    "await asyncio.to_thread(self.db.collection(COLLECTION).document(session_id).update, {\n            \"message_count\": firestore.Increment(count),\n            \"updated_at\": datetime.now(UTC),\n        })"
)

# 8. update_message_count
content = content.replace(
    "self.db.collection(COLLECTION).document(session_id).update(\n            {\n                \"message_count\": count,\n                \"updated_at\": datetime.now(UTC),\n            }\n        )",
    "await asyncio.to_thread(self.db.collection(COLLECTION).document(session_id).update, {\n            \"message_count\": count,\n            \"updated_at\": datetime.now(UTC),\n        })"
)

# 9. get_latest_session_for_user
content = content.replace(
    "for snap in query.stream():\n            return SessionResponse(id=snap.id, **snap.to_dict())\n        return None",
    "snaps = await asyncio.to_thread(lambda: list(query.stream()))\n        for snap in snaps:\n            return SessionResponse(id=snap.id, **snap.to_dict())\n        return None"
)

# 10. generate_title_from_message
content = content.replace(
    "self.db.collection(COLLECTION).document(session_id).update(\n                    {\"title\": generated, \"updated_at\": datetime.now(UTC)}\n                )",
    "await asyncio.to_thread(self.db.collection(COLLECTION).document(session_id).update, {\"title\": generated, \"updated_at\": datetime.now(UTC)})"
)

with open("backend/app/services/session_service.py", "w") as f:
    f.write(content)

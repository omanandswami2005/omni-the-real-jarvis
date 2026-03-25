with open('backend/app/services/scheduler_service.py', 'r') as f:
    content = f.read()

# Add async_db property
new_property = """    @property
    def async_db(self) -> firestore.AsyncClient:
        if not hasattr(self, "_async_db") or self._async_db is None:
            self._async_db = firestore.AsyncClient(project=settings.GOOGLE_CLOUD_PROJECT or None)
        return self._async_db

    # ── CRUD ──────────────────────────────────────────────────────"""

content = content.replace("    # ── CRUD ──────────────────────────────────────────────────────", new_property)

# Update list_tasks
old_list_tasks = """    async def list_tasks(self, user_id: str) -> list[ScheduledTask]:
        query = (
            self.db.collection(COLLECTION)
            .where(filter=firestore.FieldFilter("user_id", "==", user_id))
            .order_by("created_at", direction=firestore.Query.DESCENDING)
        )
        tasks = []
        for doc in query.stream():
            tasks.append(ScheduledTask.from_firestore(doc.id, doc.to_dict()))
        return tasks"""

new_list_tasks = """    async def list_tasks(self, user_id: str) -> list[ScheduledTask]:
        query = (
            self.async_db.collection(COLLECTION)
            .where(filter=firestore.FieldFilter("user_id", "==", user_id))
            .order_by("created_at", direction=firestore.Query.DESCENDING)
        )
        tasks = []
        async for doc in query.stream():
            tasks.append(ScheduledTask.from_firestore(doc.id, doc.to_dict()))
        return tasks"""

content = content.replace(old_list_tasks, new_list_tasks)

with open('backend/app/services/scheduler_service.py', 'w') as f:
    f.write(content)

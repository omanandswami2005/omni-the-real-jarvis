import asyncio
import time
from uuid import uuid4
from google.cloud import firestore
from app.services.scheduler_service import get_scheduler_service, ScheduledTask

async def setup_data(user_id, count=100):
    svc = get_scheduler_service()
    db = svc.db
    batch = db.batch()
    for _ in range(count):
        doc_ref = db.collection("scheduled_tasks").document()
        task = ScheduledTask(user_id=user_id, description="test")
        batch.set(doc_ref, task.to_firestore())
    batch.commit()
    print(f"Created {count} tasks for {user_id}")

async def run_benchmark():
    user_id = f"test_user_{uuid4().hex[:8]}"
    await setup_data(user_id, count=200)

    svc = get_scheduler_service()

    start = time.perf_counter()
    tasks = await svc.list_tasks(user_id)
    end = time.perf_counter()

    print(f"Found {len(tasks)} tasks")
    print(f"list_tasks took: {end - start:.4f} seconds")

if __name__ == "__main__":
    asyncio.run(run_benchmark())

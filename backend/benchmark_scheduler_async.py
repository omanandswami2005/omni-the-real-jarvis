import asyncio
import time
from app.services.scheduler_service import get_scheduler_service
from unittest.mock import MagicMock
from google.cloud.firestore import AsyncClient

async def run_benchmark():
    service = get_scheduler_service()

    # Mock firestore client
    mock_db = MagicMock(spec=AsyncClient)
    mock_snap = MagicMock()
    mock_snap.exists = True
    mock_snap.to_dict.return_value = {"user_id": "test_user"}

    # Setup mock to simulate a slow asynchronous get
    async def slow_get():
        await asyncio.sleep(0.05)
        return mock_snap

    mock_db.collection.return_value.document.return_value.get.side_effect = slow_get
    service._db = mock_db

    # Redefine get_task to simulate what it would be after change
    async def get_task_async(user_id: str, task_id: str):
        snap = await service.db.collection("scheduled_tasks").document(task_id).get()
        if not snap.exists:
            return None
        data = snap.to_dict()
        if data.get("user_id") != user_id:
            return None
        return data

    start_time = time.time()

    # Run multiple concurrent get_task calls
    tasks = [get_task_async("test_user", f"task_{i}") for i in range(20)]
    await asyncio.gather(*tasks)

    end_time = time.time()
    print(f"Time taken (async mock): {end_time - start_time:.4f} seconds")

if __name__ == "__main__":
    asyncio.run(run_benchmark())

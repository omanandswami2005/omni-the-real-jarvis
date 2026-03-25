import asyncio
import time
from app.services.scheduler_service import get_scheduler_service
from unittest.mock import MagicMock
from google.cloud.firestore import Client, AsyncClient

async def run_benchmark():
    service = get_scheduler_service()

    # Mock firestore client
    mock_db = MagicMock(spec=Client)
    mock_snap = MagicMock()
    mock_snap.exists = True
    mock_snap.to_dict.return_value = {"user_id": "test_user"}

    # Setup mock to simulate a slow synchronous get
    def slow_get():
        time.sleep(0.05)
        return mock_snap

    mock_db.collection.return_value.document.return_value.get.side_effect = slow_get
    service._db = mock_db

    start_time = time.time()

    # Run multiple concurrent get_task calls
    tasks = [service.get_task("test_user", f"task_{i}") for i in range(20)]
    await asyncio.gather(*tasks)

    end_time = time.time()
    print(f"Time taken (sync mock): {end_time - start_time:.4f} seconds")

if __name__ == "__main__":
    asyncio.run(run_benchmark())

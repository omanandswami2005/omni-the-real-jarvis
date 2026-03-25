import asyncio
import time
from unittest.mock import MagicMock, AsyncMock
from app.services.scheduler_service import get_scheduler_service, ScheduledTask

async def monitor_event_loop():
    """Monitor how many times we can yield to the event loop."""
    count = 0
    try:
        while True:
            await asyncio.sleep(0)
            count += 1
    except asyncio.CancelledError:
        return count

async def run_benchmark():
    svc = get_scheduler_service()

    # Mock firestore client
    mock_db = MagicMock()
    mock_collection = MagicMock()
    mock_query = MagicMock()

    # Setup mock query stream to yield 100 items with delay
    async def mock_stream():
        for i in range(100):
            doc = MagicMock()
            doc.id = f"task_{i}"
            doc.to_dict.return_value = {
                "user_id": "test_user",
                "description": f"Test task {i}",
                "schedule": "0 0 * * *",
                "status": "active"
            }
            # Simulate async I/O
            await asyncio.sleep(0.01)
            yield doc

    mock_query.stream.return_value = mock_stream()
    mock_query.order_by.return_value = mock_query
    mock_query.where.return_value = mock_query
    mock_collection.where.return_value = mock_query
    mock_db.collection.return_value = mock_collection

    # We will override list_tasks for the benchmark to see what happens when we use async for
    async def async_list_tasks(user_id):
        query = (
            mock_db.collection("scheduled_tasks")
            .where(filter=None)
            .order_by("created_at", direction=None)
        )
        tasks = []
        async for doc in query.stream():
            tasks.append(ScheduledTask.from_firestore(doc.id, doc.to_dict()))
        return tasks

    # Start a background task
    bg_task = asyncio.create_task(monitor_event_loop())

    start = time.perf_counter()

    # Run the mocked async_list_tasks
    tasks = await async_list_tasks("test_user")

    end = time.perf_counter()

    # Stop background task and check its count
    bg_task.cancel()
    try:
        count = await bg_task
    except asyncio.CancelledError:
        count = 0

    print(f"Found {len(tasks)} tasks")
    print(f"async list_tasks execution time: {end - start:.4f} seconds")
    print(f"Event loop cycles executed during list_tasks: {count}")

if __name__ == "__main__":
    asyncio.run(run_benchmark())

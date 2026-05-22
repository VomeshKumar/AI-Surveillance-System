import asyncio
import json
import redis
import time


def send_event(face_id=1):
    r = redis.Redis(decode_responses=True)

    event = {
        "face_id": face_id,
        "camera_id": "cam_test",
        "confidence": 0.95,
        "match": True
    }

    r.xadd("face_events", {
        "payload": json.dumps(event)
    })

    print(f"✅ Event sent: {event}")


async def run_test():
    print("Starting automated test...\n")

    # Step 1: Send valid suspect (should trigger alert)
    send_event(face_id=1)
    time.sleep(2)

    # Step 2: Send non-existing face (should skip)
    send_event(face_id=999)
    time.sleep(2)

    print("\nTest completed")


if __name__ == "__main__":
    asyncio.run(run_test())
import asyncio
import httpx
import time
import random
from faker import Faker
import sys

# --- Configuration ---
API_URL = "http://localhost:8000/ingest"
NUM_REQUESTS = 10000  # Total logs to send
CONCURRENT_REQUESTS = 100 # Number of logs to send in parallel

# --- Log Data Generation ---
fake = Faker()
LOG_LEVELS = ["info", "warning", "error", "debug", "critical"]
SERVICES = ["payment-service", "user-service", "auth-service", "inventory-service", "shipping-service"]

def generate_log():
    """Generates a single fake log entry."""
    # Occasionally include "failed" in the message for testing
    message = fake.sentence(nb_words=10)
    if random.random() < 0.2:  # 20% chance
        message = "Failed to process " + message

    return {
        "level": random.choice(LOG_LEVELS),
        "service": random.choice(SERVICES),
        "message": message,
        "metadata": {
            "request_id": fake.uuid4(),
            "user_id": fake.random_int(min=1000, max=5000)
        }
    }

# --- Async HTTP Client ---
async def send_log(session, log_data):
    """Sends a single log to the API."""
    try:
        response = await session.post(API_URL, json=log_data, timeout=10.0)
        if 200 <= response.status_code < 300:
            return "success"
        else:
            print(f"Failed request with status {response.status_code}: {response.text}")
            return "fail"
    except httpx.ReadTimeout:
        print("Request timed out.")
        return "fail"
    except httpx.RequestError as e:
        print(f"Request error: {e}")
        return "fail"

async def main():
    """Main async function to run the load test."""
    
    # Read command-line arguments if provided
    total_requests = int(sys.argv[1]) if len(sys.argv) > 1 else NUM_REQUESTS
    concurrency = int(sys.argv[2]) if len(sys.argv) > 2 else CONCURRENT_REQUESTS
    
    print(f"--- LogStream Load Test ---")
    print(f"Target URL: {API_URL}")
    print(f"Total Logs to Send: {total_requests}")
    print(f"Concurrency Level: {concurrency}")
    print("----------------------------\n")
    
    tasks = []
    success_count = 0
    fail_count = 0
    
    start_time = time.time()

    # Use httpx.AsyncClient for connection pooling
    async with httpx.AsyncClient() as session:
        semaphore = asyncio.Semaphore(concurrency)

        async def throttled_send(log_data):
            """Wrapper to use semaphore for concurrency control."""
            nonlocal success_count, fail_count
            async with semaphore:
                result = await send_log(session, log_data)
                if result == "success":
                    success_count += 1
                else:
                    fail_count += 1

        print(f"Starting to send {total_requests} logs...")
        
        for _ in range(total_requests):
            log = generate_log()
            tasks.append(throttled_send(log))
            
            # Print progress
            if (_ + 1) % (total_requests // 10 or 1) == 0:
                print(f"  ... {(_ + 1)} logs queued")

        # Run all tasks concurrently
        await asyncio.gather(*tasks)

    end_time = time.time()
    total_time = end_time - start_time

    print("\n--- Test Results ---")
    print(f"Total Time: {total_time:.2f} seconds")
    print(f"Successful Logs: {success_count}")
    print(f"Failed Logs: {fail_count}")
    
    if total_time > 0:
        logs_per_second = success_count / total_time
        logs_per_minute = logs_per_second * 60
        print(f"\nLogs per Second (LPS): {logs_per_second:.2f}")
        print(f"Logs per Minute: {logs_per_minute:.2f}")
    
    print("--------------------")

if __name__ == "__main__":
    asyncio.run(main())
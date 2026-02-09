import asyncio
import httpx


async def run_test():
    async with httpx.AsyncClient() as client:
        query = "test file content"
        response = await client.post(
            "http://localhost:8002/api/v1/search", json={"query": query, "limit": 3}
        )
        print(f"SEARCH response: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            results = data["results"]
            answer = data["answer"]

            print(f"Answer: {answer}\n")
            print(f"Results found: {len(results)}")
            for res in results:
                print(
                    f" - [{res['score']:.4f}] {res['text'][:50]}... (Doc: {res['document_id']})"
                )

            if len(results) > 0:
                print("✅ Search Test Passed.")
            else:
                print("⚠️ Search Test Warning: No results (did you ingest data?).")
        else:
            print(f"❌ Search Test Failed: {response.text}")


if __name__ == "__main__":
    asyncio.run(run_test())

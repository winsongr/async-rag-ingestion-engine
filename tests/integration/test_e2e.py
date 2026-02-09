import asyncio
import httpx
from sqlalchemy import text
from src.infra.db.postgres import engine


async def wait_for_status(doc_id: str, target_status: str, timeout: int = 10):
    print(f"Polling for status {target_status}...")
    for _ in range(timeout):
        async with engine.connect() as conn:
            result = await conn.execute(
                text(f"SELECT status FROM documents WHERE id = '{doc_id}'")
            )
            status = result.scalar()
            print(f"Current status: {status}")
            if status == target_status:
                return True
        await asyncio.sleep(1)
    return False


async def run_test():
    with open("test_output.log", "w") as f:
        f.write("Starting test...\n")
        async with httpx.AsyncClient() as client:
            try:
                # 1. Post Document
                response = await client.post(
                    "http://localhost:8002/api/v1/documents",
                    json={"source": "test_e2e_doc"},
                )
                f.write(f"POST response: {response.status_code} {response.json()}\n")

                if response.status_code != 202:
                    f.write("❌ POST failed\n")
                    return

                doc_id = response.json()["id"]

                # 2. Wait for DONE
                # Need to modify wait_for_status to write to file too or just return result
                success = await wait_for_status(doc_id, "DONE")

                if success:
                    f.write("✅ E2E Test Passed: Document processed to DONE.\n")
                else:
                    f.write("❌ E2E Test Failed: Document NOT processed to DONE.\n")
            except Exception as e:
                f.write(f"❌ Exception: {e}\n")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_test())

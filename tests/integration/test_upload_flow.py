import asyncio
import httpx
from sqlalchemy import text
from src.infra.db.postgres import engine


async def wait_for_status(doc_id: str, target_status: str, timeout: int = 15):
    print(f"Polling for status {target_status}...")
    for _ in range(timeout):
        async with engine.connect() as conn:
            result = await conn.execute(
                text(f"SELECT status, file_path FROM documents WHERE id = '{doc_id}'")
            )
            row = result.fetchone()
            if not row:
                print("Document not found in DB.")
                return False, None

            status, file_path = row
            print(f"Current status: {status}, File path: {file_path}")
            if status == target_status and file_path is not None:
                return True, file_path
        await asyncio.sleep(1)
    return False, None


async def run_test():
    async with httpx.AsyncClient() as client:
        # 1. Post Document
        response = await client.post(
            "http://localhost:8002/api/v1/documents", json={"source": "test_upload_doc"}
        )
        print(f"POST response: {response.status_code}")

        if response.status_code != 202:
            print(f"❌ POST failed: {response.text}")
            return

        doc_id = response.json()["id"]

        # 2. Upload File
        files = {
            "file": ("test_file.txt", b"This is a test file content", "text/plain")
        }
        response = await client.post(
            f"http://localhost:8002/api/v1/documents/{doc_id}/upload", files=files
        )
        print(f"UPLOAD response: {response.status_code}")

        if response.status_code != 202:
            print(f"❌ UPLOAD failed: {response.text}")
            return

        # 3. Wait for DONE and File Path
        success, file_path = await wait_for_status(doc_id, "DONE")

        if success:
            print(
                f"✅ E2E Upload Test Passed: Document processed to DONE. File path: {file_path}"
            )
        else:
            print(
                "❌ E2E Upload Test Failed: Document NOT processed or file path missing."
            )

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_test())

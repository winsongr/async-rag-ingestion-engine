from qdrant_client import AsyncQdrantClient
import asyncio


async def main():
    client = AsyncQdrantClient("http://localhost:6333")
    print("Methods:", [m for m in dir(client) if not m.startswith("_")])
    await client.close()


if __name__ == "__main__":
    asyncio.run(main())

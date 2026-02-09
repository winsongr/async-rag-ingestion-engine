class ChunkingService:
    def chunk(self, text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
        """
        Chunk text into smaller pieces with overlap.
        Simple character-based chunking.
        """
        if not text:
            return []

        chunks = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = start + chunk_size
            chunk = text[start:end]
            chunks.append(chunk)

            # Move start forward by chunk_size - overlap
            # If we are at the end, the loop will terminate
            start += chunk_size - overlap

        return chunks

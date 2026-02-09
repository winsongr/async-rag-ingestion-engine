"""
Mock LLM service for RAG generation.

INTENTIONALLY mocked to demonstrate RAG flow without external API dependency.
Real LLM integration is a simple client swap.
"""


class MockLLMService:
    """
    Mock LLM service for testing RAG pipeline.

    Design decision: Focus on retrieval correctness, not generation quality.
    Swap with OpenAI/Anthropic client for production.
    """

    def __init__(self):
        # In a real app, initialize OpenAI here
        pass

    def generate_answer(self, query: str, context: list[str]) -> str:
        """
        Generate an answer using the LLM.
        Mock implementation for demonstration.
        """
        context_str = "\n".join([f"- {c}" for c in context])
        return f"This is a generated answer for '{query}' based on the following context:\n{context_str}"


# Alias for dependency injection type hinting
LLMService = MockLLMService

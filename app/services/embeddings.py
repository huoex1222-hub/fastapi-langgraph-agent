"""Embedding providers for long-term memory."""

from typing import (
    Literal,
    Optional,
    override,
)

from mem0.embeddings.openai import OpenAIEmbedding


class OpenAICompatibleEmbedding(OpenAIEmbedding):
    """OpenAI-compatible embedder that omits the optional ``dimensions`` argument.

    Some providers (e.g. SiliconFlow) return the model's native dimension and
    reject requests that include ``dimensions``. mem0's ``OpenAIEmbedding``
    always forwards ``dimensions=self.config.embedding_dims``, so this subclass
    drops that parameter while keeping the configured dimension for the vector
    store schema.
    """

    @override
    def embed(self, text: str, memory_action: Optional[Literal["add", "search", "update"]] = None) -> list[float]:
        """Embed a single text without sending the ``dimensions`` parameter.

        Args:
            text: Text to embed.
            memory_action: mem0 action hint (unused).

        Returns:
            Embedding vector.
        """
        text = text.replace("\n", " ")
        model = self.config.model or "text-embedding-3-small"
        response = self.client.embeddings.create(input=[text], model=model)
        return list(response.data[0].embedding)

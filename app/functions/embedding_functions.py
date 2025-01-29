import numpy as np
from openai import OpenAI
from dotenv import load_dotenv
from typing import List


class EmbeddingFunctions:
    def __init__(self):
        load_dotenv()
        self.client = OpenAI()

    def create_embeddings_from_sentences(
        self, sentences: List[str], chunk_size: int = 2000
    ) -> List[np.ndarray]:
        file_embeddings = []
        for chunk_index in range(0, len(sentences), chunk_size):
            chunk_embeddings = self.client.embeddings.create(
                model="text-embedding-3-small",
                input=sentences[chunk_index : chunk_index + chunk_size],
            )
            chunk_array = np.array(
                [x.embedding for x in chunk_embeddings.data], dtype=np.float16
            )
            file_embeddings.append(
                chunk_array / np.linalg.norm(chunk_array, axis=1)[:, np.newaxis]
            )

        return np.vstack(file_embeddings)

    def create_embedding_from_sentence(self, sentence: list) -> np.ndarray:
        query_embedding = self.client.embeddings.create(
            model="text-embedding-3-small", input=sentence
        )
        return np.array(query_embedding.data[0].embedding, dtype=np.float16).reshape(
            1, -1
        )

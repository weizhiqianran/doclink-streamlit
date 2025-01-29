import faiss


class IndexingFunctions:
    def __init__(self):
        pass

    def create_flat_index(self, embeddings):
        dimension = len(embeddings[0])
        index = faiss.IndexFlatIP(dimension)
        index.add(embeddings)
        return index

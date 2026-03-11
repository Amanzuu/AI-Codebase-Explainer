def semantic_search(vector_store, query, k=5):
    """
    Return top-k relevant documents for a query.
    """
    docs = vector_store.similarity_search(query, k=k)

    results = []
    for d in docs:
        results.append(
            {
                "content": d.page_content,
                "source": d.metadata.get("source", "Unknown"),
            }
        )

    return results

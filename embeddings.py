import os
from pathlib import Path

import streamlit as st
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


@st.cache_resource
def get_embeddings_model():
    return HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )


def split_with_metadata(file_map):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=200
    )

    docs = []
    for path, content in file_map.items():
        chunks = splitter.split_text(content)
        for chunk in chunks:
            docs.append(
                Document(
                    page_content=chunk,
                    metadata={"source": path}
                )
            )
    return docs


def _has_source_metadata(vector_store):
    docstore = getattr(vector_store, "docstore", None)
    if docstore is None:
        return False

    stored_docs = getattr(docstore, "_dict", {}).values()
    sample_doc = next(iter(stored_docs), None)
    if sample_doc is None:
        return False
    return bool(sample_doc.metadata.get("source"))


def create_vector_store(file_map, repo_path):
    embeddings = get_embeddings_model()
    repo_name = Path(repo_path).resolve().name
    vector_store_path = Path(".cache") / "vector_store" / repo_name

    # If vector DB already exists, load it
    if os.path.exists(vector_store_path):
        print("Loading existing vector database...")
        vector_store = FAISS.load_local(
            str(vector_store_path),
            embeddings,
            allow_dangerous_deserialization=True
        )
        if _has_source_metadata(vector_store):
            return vector_store
        print("Existing vector database missing source metadata. Rebuilding...")

    print("Splitting code into chunks...")
    docs = split_with_metadata(file_map)

    print("Creating embeddings...")

    vector_store = FAISS.from_documents(docs, embeddings)

    # Save vector DB
    vector_store_path.mkdir(parents=True, exist_ok=True)
    vector_store.save_local(str(vector_store_path))

    return vector_store

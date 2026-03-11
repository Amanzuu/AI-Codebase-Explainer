import os
from pathlib import Path

import streamlit as st
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter


@st.cache_resource
def get_embeddings_model():
    return HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )


def create_vector_store(texts, repo_path):
    embeddings = get_embeddings_model()
    repo_name = Path(repo_path).resolve().name
    vector_store_path = Path(".cache") / "vector_store" / repo_name

    # If vector DB already exists, load it
    if os.path.exists(vector_store_path):
        print("Loading existing vector database...")
        return FAISS.load_local(
            str(vector_store_path),
            embeddings,
            allow_dangerous_deserialization=True
        )

    print("Splitting code into chunks...")

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=200
    )

    docs = text_splitter.create_documents(texts)

    print("Creating embeddings...")

    vector_store = FAISS.from_documents(docs, embeddings)

    # Save vector DB
    vector_store_path.mkdir(parents=True, exist_ok=True)
    vector_store.save_local(str(vector_store_path))

    return vector_store

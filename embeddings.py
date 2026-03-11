from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
import os

def create_vector_store(texts):

    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )

    # If vector DB already exists, load it
    if os.path.exists("vector_store"):
        print("Loading existing vector database...")
        return FAISS.load_local(
            "vector_store",
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
    vector_store.save_local("vector_store")

    return vector_store
import streamlit as st

from repo_loader import clone_repo
from code_loader import load_code_files
from embeddings import create_vector_store
from rag_pipeline import create_qa_chain


st.title("AI Codebase Explainer")

repo_url = st.text_input("Enter GitHub Repository URL")

if st.button("Analyze Repository"):

    with st.spinner("Cloning repository..."):
        repo_path = clone_repo(repo_url)

    with st.spinner("Loading code files..."):
        code = load_code_files(repo_path)

    st.write(f"Loaded {len(code)} files")

    with st.spinner("Creating embeddings..."):
        vector_store = create_vector_store(code)

    qa_chain = create_qa_chain(vector_store)

    st.session_state.qa_chain = qa_chain

    st.success("Repository indexed successfully!")


question = st.text_input("Ask a question about the codebase")

if question and "qa_chain" in st.session_state:

    with st.spinner("Thinking..."):
        answer = st.session_state.qa_chain.run(question)

    st.write(answer)
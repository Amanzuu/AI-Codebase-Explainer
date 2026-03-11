from langchain_ollama import OllamaLLM
from langchain_classic.chains import RetrievalQA

def create_qa_chain(vector_store):

    llm = OllamaLLM(model="phi3")

    retriever = vector_store.as_retriever(search_kwargs={"k": 4})

    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        retriever=retriever
    )

    return qa_chain

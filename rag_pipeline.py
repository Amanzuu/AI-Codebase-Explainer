from langchain_community.llms import Ollama
from langchain_classic.chains import RetrievalQA


def create_qa_chain(vector_store):

    llm = Ollama(model="llama3")

    retriever = vector_store.as_retriever(search_kwargs={"k": 5})

    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        retriever=retriever
    )

    return qa_chain

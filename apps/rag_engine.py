import os
from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

# 1. Load Environment Variables
load_dotenv()
if not os.getenv("GOOGLE_API_KEY"):
    raise ValueError("GOOGLE_API_KEY not found in environment variables. Check your .env file.")

# 2. Configuration Constants
PERSIST_DIRECTORY = os.path.abspath(os.path.join(os.path.dirname(__file__), "../chroma_db"))
EMBEDDING_MODEL_NAME = "gemini-embedding-001" # Correct model string for Google GenAI embeddings
LLM_MODEL_NAME = "gemini-3.5-flash"          # Stable LLM model identifier

def get_embeddings():
    """Initializes Google GenAI Embeddings."""
    return GoogleGenerativeAIEmbeddings(model=EMBEDDING_MODEL_NAME)

def get_vector_store():
    """Initializes persistent ChromaDB vector store."""
    embeddings = get_embeddings()
    return Chroma(
        persist_directory=PERSIST_DIRECTORY,
        embedding_function=embeddings
    )

def ingest_documents(docs: list[Document]):
    """
    Splits documents into optimal chunks and indexes them into ChromaDB 
    while preserving source metadata for citations.
    """
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
        separators=["\n\n", "\n", " ", ""]
    )
    
    split_docs = text_splitter.split_documents(docs)
    vector_store = get_vector_store()
    vector_store.add_documents(split_docs)
    print(f"Successfully ingested {len(split_docs)} chunks into ChromaDB.")
    return len(split_docs)

def format_docs(docs):
    """Formats retrieved documents into context strings with source metadata citations."""
    formatted = []
    for doc in docs:
        source = doc.metadata.get("source", "Unknown Source")
        page = doc.metadata.get("page", "N/A")
        formatted.append(f"Source: {source} (Page: {page})\nContent: {doc.page_content}\n")
    return "\n---\n".join(formatted)

def create_rag_chain():
    """
    Creates an optimal RAG chain using MMR (Maximal Marginal Relevance) semantic search
    to balance relevance and diversity (crucial for conflict/version detection).
    """
    vector_store = get_vector_store()
    
    # Using MMR (Maximal Marginal Relevance) for optimal semantic search + diversity
    retriever = vector_store.as_retriever(
        search_type="mmr",
        search_kwargs={
            "k": 4,           # Number of top chunks to retrieve
            "fetch_k": 10,    # Candidate chunks to fetch before diversity filtering
            "lambda_mult": 0.7 # Balance between relevance (1.0) and diversity (0.0)
        }
    )

    llm = ChatGoogleGenerativeAI(model=LLM_MODEL_NAME, temperature=0.1)

    # Grounding prompt enforcing citations, version conflict surface, and "not found" fallback
    template = """You are an expert enterprise documentation assistant. Answer the user's question accurately using ONLY the provided context below. Do not introduce unsupported claims or external general knowledge.

If the context contains conflicting information or version differences, explicitly highlight and explain the conflict.
If the context is insufficient or does not contain the answer, state clearly: "I could not find this information in the authorised documentation sources."

Context:
{context}

Question: {question}

Answer with explicit citations (mentioning source document and page/section where available):"""

    prompt = ChatPromptTemplate.from_template(template)

    # Build Runnable RAG chain using LCEL
    rag_chain = (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )
    
    return rag_chain

if __name__ == "__main__":
    print("Testing RAG Engine initialization...")
    chain = create_rag_chain()
    print("RAG Chain compiled successfully!")
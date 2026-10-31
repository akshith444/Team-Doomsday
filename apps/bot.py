import os
import sys
import streamlit as st

# Automatically resolve path to local directory
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from langchain_core.documents import Document
from rag_engine import ingest_documents, create_rag_chain, get_vector_store
from confidence import calculate_confidence_score

# Streamlit Page Setup
st.set_page_config(
    page_title="Enterprise Documentation Q&A Assistant",
    page_icon="🤖",
    layout="wide"
)

st.title("📄 Enterprise Documentation Q&A Assistant")
st.markdown("Upload your manuals, policies, or technical guides, and ask questions backed by verified evidence and confidence scoring.")

# Initialize RAG Chain session state
if "rag_chain" not in st.session_state:
    try:
        st.session_state.rag_chain = create_rag_chain()
    except Exception as e:
        st.error(f"Failed to initialize RAG Chain. Check your API key in .env. Error: {e}")

# Sidebar for Document Ingestion (FR-01)
with st.sidebar:
    st.header("📂 Knowledge Ingestion")
    uploaded_files = st.file_uploader(
        "Upload Enterprise Documents",
        type=["pdf", "txt", "md", "html"],
        accept_multiple_files=True
    )
    
    if st.button("Process & Index Documents", type="primary"):
        if uploaded_files:
            with st.spinner("Processing and splitting documents into vector store..."):
                docs = []
                for file in uploaded_files:
                    file_extension = file.name.split(".")[-1].lower()
                    file_content = file.read()
                    
                    if file_extension in ["txt", "md", "html"]:
                        text = file_content.decode("utf-8", errors="ignore")
                        docs.append(Document(
                            page_content=text,
                            metadata={"source": file.name, "page": "N/A"}
                        ))
                    elif file_extension == "pdf":
                        import fitz  # PyMuPDF
                        pdf_document = fitz.open(stream=file_content, filetype="pdf")
                        for page_num in range(len(pdf_document)):
                            page = pdf_document[page_num]
                            text = page.get_text()
                            docs.append(Document(
                                page_content=text,
                                metadata={"source": file.name, "page": page_num + 1}
                            ))
                
                try:
                    num_chunks = ingest_documents(docs)
                    st.success(f"Successfully indexed {len(uploaded_files)} files ({num_chunks} chunks)!")
                except Exception as e:
                    st.error(f"Error during ingestion: {e}")
        else:
            st.warning("Please upload at least one document first.")

# Main Chat Interface
st.subheader("💬 Ask a Question")

if "messages" not in st.session_state:
    st.session_state.messages = []

# Display previous chat messages & confidence metrics (FR-08)
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant" and "confidence" in message:
            conf = message["confidence"]
            col1, col2 = st.columns([1, 3])
            with col1:
                level = conf["confidence_level"]
                if level == "High":
                    st.success(f"Confidence: {conf['confidence_score']}% ({level})")
                elif level == "Moderate":
                    st.warning(f"Confidence: {conf['confidence_score']}% ({level})")
                else:
                    st.error(f"Confidence: {conf['confidence_score']}% ({level})")
            with col2:
                with st.expander("🔍 Verification & Source Breakdown"):
                    for reason in conf["reasons"]:
                        st.write(f"- {reason}")

# Process input query
if query := st.chat_input("Ask about billing policies, product configuration, or troubleshooting..."):
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        if "rag_chain" in st.session_state:
            with st.spinner("Searching enterprise knowledge base and evaluating confidence..."):
                try:
                    # 1. Run RAG response generation
                    response = st.session_state.rag_chain.invoke(query)
                    
                    # 2. Retrieve underlying chunks for confidence calculation (FR-08)
                    vector_store = get_vector_store()
                    retrieved_docs = vector_store.similarity_search(query, k=4)
                    
                    # 3. Calculate Confidence Score
                    conf_data = calculate_confidence_score(query, retrieved_docs, response)
                    
                    # Render response
                    st.markdown(response)
                    
                    # Render confidence badge and expander (FR-08)
                    col1, col2 = st.columns([1, 3])
                    with col1:
                        level = conf_data["confidence_level"]
                        if level == "High":
                            st.success(f"Confidence: {conf_data['confidence_score']}% ({level})")
                        elif level == "Moderate":
                            st.warning(f"Confidence: {conf_data['confidence_score']}% ({level})")
                        else:
                            st.error(f"Confidence: {conf_data['confidence_score']}% ({level})")
                    with col2:
                        with st.expander("🔍 Verification & Source Breakdown"):
                            for reason in conf_data["reasons"]:
                                st.write(f"- {reason}")

                    # Save into history state
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response,
                        "confidence": conf_data
                    })
                except Exception as e:
                    error_msg = f"An error occurred while generating response: {e}"
                    st.error(error_msg)
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})
        else:
            st.error("RAG chain is not initialized. Please check environment configuration.")

import io
import os
import time
import logging
from pinecone import Pinecone, ServerlessSpec
from backend import config
from backend.services.llm import client
from google.genai import types
from backend.logger import backend_logger as logger
import pypdf

# Initialize Pinecone Client placeholders
pc = None
index = None

def init_pinecone():
    """Initializes the Pinecone client and index lazily, supporting dynamic config reloads."""
    global pc, index
    if index is not None:
        return index

    # Dynamically reload environment/config to pick up freshly set .env keys without server restarts
    try:
        from importlib import reload
        reload(config)
    except Exception as e:
        logger.warning("Failed to reload configuration dynamically: %s", str(e))

    # Retrieve API key
    api_key = config.PINECONE_API_KEY or os.getenv("PINECONE_API_KEY")
    if not api_key:
        raise ValueError("PINECONE_API_KEY is not set. Please configure it in your backend/.env file and ensure it is saved.")

    try:
        logger.info("Initializing Pinecone client lazily...")
        pc = Pinecone(api_key=api_key)
        index_name = config.PINECONE_INDEX_NAME or os.getenv("PINECONE_INDEX_NAME", "pingu-rag")
        
        # Ensure index exists
        existing_indexes = [idx.name for idx in pc.list_indexes()]
        if index_name not in existing_indexes:
            logger.info("Pinecone Index '%s' not found. Creating serverless index...", index_name)
            pc.create_index(
                name=index_name,
                dimension=768,
                metric="cosine",
                spec=ServerlessSpec(
                    cloud="aws",
                    region="us-east-1"
                )
            )
            # Wait for index to be ready
            while not pc.describe_index(index_name).status['ready']:
                time.sleep(1)
                
        index = pc.Index(index_name)
        logger.info("Pinecone RAG initialized successfully on index '%s'.", index_name)
        return index
    except Exception as e:
        logger.error("Failed to initialize Pinecone: %s", str(e), exc_info=True)
        raise ValueError(f"Failed to initialize Pinecone: {str(e)}")

def extract_text_from_file(file_content: bytes, filename: str) -> str:
    """Extracts text content from PDF, TXT, or MD file bytes."""
    ext = filename.split(".")[-1].lower()
    if ext == "pdf":
        try:
            pdf = pypdf.PdfReader(io.BytesIO(file_content))
            text = ""
            for page in pdf.pages:
                content = page.extract_text()
                if content:
                    text += content + "\n"
            return text
        except Exception as e:
            logger.error("PDF Parsing error for %s: %s", filename, str(e))
            raise ValueError(f"Failed to parse PDF: {str(e)}")
    else:
        # Assume text/md
        try:
            return file_content.decode("utf-8", errors="ignore")
        except Exception as e:
            logger.error("Text parsing error for %s: %s", filename, str(e))
            raise ValueError(f"Failed to read text file: {str(e)}")

def chunk_text(text: str, chunk_size: int = 800, overlap: int = 80) -> list[str]:
    """Splits text into chunks of specified size and overlap."""
    chunks = []
    if not text:
        return chunks
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end].strip())
        if end == len(text):
            break
        start += chunk_size - overlap
    return [c for c in chunks if len(c) > 10]

def get_embedding(text: str) -> list[float]:
    """Generates embedding vector using Gemini's configured model, constrained to 768 dimensions."""
    try:
        response = client.models.embed_content(
            model="gemini-embedding-001",
            contents=text,
            config=types.EmbedContentConfig(output_dimensionality=768)
        )
        # Handle response formats robustly
        if hasattr(response, 'embeddings') and response.embeddings:
            return response.embeddings[0].values
        elif hasattr(response, 'embedding') and response.embedding:
            return response.embedding.values
        raise ValueError("Failed to retrieve embedding values from response")
    except Exception as e:
        logger.error("Gemini embedding error: %s", str(e))
        raise

def index_document(chat_id: str, doc_id: str, filename: str, file_content: bytes):
    """Parses, chunks, embeds, and indexes a document into Pinecone namespace (chat_id)."""
    active_index = init_pinecone()
    
    text = extract_text_from_file(file_content, filename)
    chunks = chunk_text(text)
    
    if not chunks:
        logger.warning("No text chunks extracted from file: %s", filename)
        return
        
    logger.info("Indexing %s for Chat %s. Extracted %d chunks.", filename, chat_id, len(chunks))
    
    vectors_to_upsert = []
    for i, chunk in enumerate(chunks):
        chunk_id = f"{doc_id}_chunk_{i}"
        embedding = get_embedding(chunk)
        vectors_to_upsert.append({
            "id": chunk_id,
            "values": embedding,
            "metadata": {
                "doc_id": doc_id,
                "filename": filename,
                "text": chunk
            }
        })
        
        # Batch upsert in sizes of 100
        if len(vectors_to_upsert) >= 100:
            active_index.upsert(vectors=vectors_to_upsert, namespace=chat_id)
            vectors_to_upsert = []
            
    if vectors_to_upsert:
        active_index.upsert(vectors=vectors_to_upsert, namespace=chat_id)
        
    logger.info("Successfully indexed %s in Pinecone.", filename)

def query_rag_context(chat_id: str, query: str, top_k: int = 3) -> str:
    """Queries Pinecone for relevant chunks and constructs context string."""
    try:
        active_index = init_pinecone()
    except Exception as e:
        logger.warning("RAG query skipped. Pinecone index is inactive: %s", str(e))
        return ""
        
    try:
        logger.info("Querying Pinecone RAG for chat: %s | Query: %r", chat_id, query)
        query_vector = get_embedding(query)
        
        response = active_index.query(
            namespace=chat_id,
            vector=query_vector,
            top_k=top_k,
            include_metadata=True
        )
        
        matches = response.get("matches", [])
        if not matches:
            logger.info("No matching RAG context found for query in namespace %s.", chat_id)
            return ""
            
        contexts = []
        for match in matches:
            meta = match.get("metadata", {})
            text = meta.get("text", "")
            filename = meta.get("filename", "Unknown file")
            if text:
                contexts.append(f"--- Context from {filename} ---\n{text}")
                
        logger.info("Retrieved %d relevant context chunks from Pinecone.", len(contexts))
        return "\n\n".join(contexts)
    except Exception as e:
        logger.error("Error querying Pinecone RAG: %s", str(e))
        return ""

def delete_document_vectors(chat_id: str, doc_id: str):
    """Deletes all vector chunks associated with a document ID from the chat's namespace."""
    try:
        active_index = init_pinecone()
        logger.info("Deleting vectors for Doc %s in namespace %s", doc_id, chat_id)
        active_index.delete(filter={"doc_id": {"$eq": doc_id}}, namespace=chat_id)
    except Exception as e:
        logger.error("Error deleting Pinecone vectors for doc %s: %s", doc_id, str(e))

def delete_chat_namespace(chat_id: str):
    """Deletes the entire Pinecone namespace for a chat session."""
    try:
        active_index = init_pinecone()
        logger.info("Deleting entire namespace: %s", chat_id)
        active_index.delete(delete_all=True, namespace=chat_id)
    except Exception as e:
        logger.error("Error deleting Pinecone namespace %s: %s", chat_id, str(e))

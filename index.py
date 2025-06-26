import os
import hashlib
import datetime
from dotenv import load_dotenv
from pymongo import MongoClient
from gridfs import GridFS
from langchain.vectorstores import FAISS
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

# Load environment variables
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

# Validate required environment variables
if not MONGO_URI or not MISTRAL_API_KEY:
    raise ValueError("Missing MONGO_URI or MISTRAL_API_KEY in .env")

# Initialize MongoDB connection
client = MongoClient(MONGO_URI)
db = client["pdf_qa_system"]
fs = GridFS(db)
users_collection = db["users"]
history_collection = db["chat_history"]
conversation_meta_collection = db["conversation_meta"]

def hash_pdf_bytes(pdf_bytes):
    """Generate SHA256 hash for PDF bytes"""
    return hashlib.sha256(pdf_bytes).hexdigest()

def save_pdf_to_gridfs(pdf_bytes, filename):
    """Save PDF to GridFS if not already exists"""
    pdf_hash = hash_pdf_bytes(pdf_bytes)
    if not fs.find_one({"metadata.hash": pdf_hash}):
        fs.put(pdf_bytes, filename=filename, metadata={"hash": pdf_hash})
    return pdf_hash

def load_pdf_from_gridfs(pdf_hash):
    """Load PDF from GridFS by hash"""
    file = fs.find_one({"metadata.hash": pdf_hash})
    return file.read() if file else None

def load_and_process_pdf_from_bytes(pdf_bytes):
    """Process PDF bytes into document chunks"""
    with open("temp.pdf", "wb") as f:
        f.write(pdf_bytes)
    try:
        loader = PyPDFLoader("temp.pdf")
        documents = loader.load()
        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
        return splitter.split_documents(documents)
    finally:
        if os.path.exists("temp.pdf"):
            os.remove("temp.pdf")

def create_vector_store(documents):
    """Create FAISS vector store from documents"""
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    return FAISS.from_documents(documents, embeddings)

def save_chat_history(username, question, answer, pdf_hash):
    """Save chat message and create conversation meta if needed"""
    if not conversation_meta_collection.find_one({"username": username, "pdf_hash": pdf_hash}):
        conversation_meta_collection.insert_one({
            "username": username,
            "pdf_hash": pdf_hash,
            "conversation_name": question[:50],
            "created_at": datetime.datetime.now(),
            "updated_at": datetime.datetime.now()
        })
    
    history_collection.insert_one({
        "username": username,
        "question": question,
        "answer": answer,
        "pdf_hash": pdf_hash,
        "timestamp": datetime.datetime.now()
    })

def get_chat_history(username):
    """Get all chat history for a user, sorted by timestamp"""
    return list(history_collection.find(
        {"username": username}, 
        {"_id": 0}
    ).sort("timestamp", -1))

def get_conversation_meta(username, pdf_hash):
    """Get conversation metadata"""
    return conversation_meta_collection.find_one(
        {"username": username, "pdf_hash": pdf_hash},
        {"_id": 0}
    )

def update_conversation_name(username, pdf_hash, new_name):
    """Update conversation name in database"""
    result = conversation_meta_collection.update_one(
        {"username": username, "pdf_hash": pdf_hash},
        {"$set": {
            "conversation_name": new_name,
            "updated_at": datetime.datetime.now()
        }},
        upsert=True
    )
    return result.modified_count > 0
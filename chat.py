import streamlit as st
import requests
import os
import datetime
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from index import (
    load_and_process_pdf_from_bytes,
    create_vector_store,
    save_chat_history,
    get_chat_history,
    save_pdf_to_gridfs,
    load_pdf_from_gridfs,
    hash_pdf_bytes,
    get_conversation_meta,
    update_conversation_name
)

# Constants
MISTRAL_MODEL = "mistral-small"
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")

# Validate API key
if not MISTRAL_API_KEY:
    st.error("MISTRAL_API_KEY is not set in environment variables.")
    st.stop()

# Custom CSS styles
st.markdown("""
<style>
.pdf-selector {
    margin-bottom: 15px;
}
.button-container {
    display: flex;
    justify-content: space-between;
    margin-bottom: 1rem;
    gap: 10px;
}
.summarize-btn {
    flex: 1;
}
.export-btn {
    flex: 1;
    background-color: #4CAF50 !important;
    border: none !important;
}
.export-btn:hover {
    background-color: #45a049 !important;
}
.stButton > button {
    width: 100% !important;
    padding: 0.5rem !important;
    font-size: 0.9rem !important;
    transition: all 0.3s ease !important;
}
</style>
""", unsafe_allow_html=True)

def export_chat_to_pdf():
    """Export current conversation to a downloadable PDF"""
    if not st.session_state.messages:
        st.warning("No conversation to export")
        return
    
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    margin = 72
    line_height = 14
    
    # PDF styling
    c.setFont("Helvetica-Bold", 16)
    c.drawString(margin, height - margin, "Chat Conversation Export")
    c.setFont("Helvetica", 12)
    
    y_position = height - margin - 30
    
    for msg in st.session_state.messages:
        if y_position < margin + 100:
            c.showPage()
            y_position = height - margin
            c.setFont("Helvetica", 12)
        
        role = "User" if msg["role"] == "user" else "Assistant"
        timestamp = msg.get("timestamp", datetime.datetime.now())
        time_str = timestamp.strftime("%Y-%m-%d %H:%M") if isinstance(timestamp, datetime.datetime) else ""
        
        c.setFont("Helvetica-Bold", 12)
        c.drawString(margin, y_position, f"{role} - {time_str}")
        y_position -= line_height
        
        c.setFont("Helvetica", 12)
        text = c.beginText(margin, y_position)
        text.setFont("Helvetica", 12)
        text.setLeading(line_height)
        
        content = msg["content"]
        lines = []
        words = content.split()
        current_line = ""
        
        for word in words:
            test_line = f"{current_line} {word}".strip()
            if c.stringWidth(test_line, "Helvetica", 12) < (width - 2 * margin):
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)
        
        for line in lines:
            text.textLine(line)
        
        c.drawText(text)
        lines_used = len(lines) + content.count('\n')
        y_position -= (line_height * lines_used + 20)
    
    c.showPage()
    c.setFont("Helvetica", 10)
    c.drawString(margin, 30, f"Exported from PDF Inquiry System on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    c.save()
    buffer.seek(0)
    
    st.download_button(
        label="⬇️ Download PDF Export",
        data=buffer,
        file_name=f"chat_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
        mime="application/pdf",
        use_container_width=True
    )

def generate_pdf_summary():
    """Generate a summary of the current PDF"""
    pdf_hash = st.session_state.get("pdf_hash")
    if not pdf_hash or pdf_hash not in st.session_state["vector_cache"]:
        return "⚠️ No PDF loaded or vector store missing."
    
    vs = st.session_state["vector_cache"][pdf_hash]
    all_chunks = vs.similarity_search(" ", k=100)
    combined_text = "\n".join([doc.page_content for doc in all_chunks])
    combined_text = combined_text[:8000]
    
    try:
        response = requests.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {MISTRAL_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": MISTRAL_MODEL,
                "messages": [{
                    "role": "user", 
                    "content": f"Please provide a comprehensive summary of the following document. Focus on the main points, key findings, and important details. Structure the summary with clear paragraphs:\n\n{combined_text}"
                }],
                "temperature": 0.2
            },
            timeout=60
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except requests.exceptions.RequestException as e:
        return f"⚠️ Error generating summary: {str(e)}"
    except Exception as e:
        return f"⚠️ An unexpected error occurred: {str(e)}"

def load_conversation(pdf_hash, chats):
    """Load conversation from history"""
    st.session_state.messages = []
    for chat in sorted(chats, key=lambda x: x.get("timestamp", datetime.datetime.now()), reverse=True):
        st.session_state.messages.append({
            "role": "user", 
            "content": chat["question"],
            "timestamp": chat.get("timestamp")
        })
        st.session_state.messages.append({
            "role": "assistant", 
            "content": chat["answer"],
            "timestamp": chat.get("timestamp")
        })
    
    pdf_bytes = load_pdf_from_gridfs(pdf_hash)
    if pdf_bytes:
        if pdf_hash not in st.session_state["vector_cache"]:
            with st.spinner("Loading PDF..."):
                docs = load_and_process_pdf_from_bytes(pdf_bytes)
                vs = create_vector_store(docs)
                st.session_state["vector_cache"][pdf_hash] = vs
        st.session_state["pdf_hash"] = pdf_hash
    st.rerun()

def prepare_rename(pdf_hash, current_name):
    """Prepare for renaming conversation"""
    st.session_state.rename_modal_open = True
    st.session_state.conversation_to_rename = pdf_hash
    st.session_state.new_conversation_name = current_name
    st.rerun()

def show_rename_modal():
    """Display rename conversation modal"""
    with st.container():
        st.markdown("""
        <div class="modal-backdrop">
            <div class="modal-content">
                <div class="modal-title">Rename Conversation</div>
        """, unsafe_allow_html=True)
        
        new_name = st.text_input(
            "New name", 
            value=st.session_state.new_conversation_name,
            key="rename_input"
        )
        
        st.markdown('<div class="modal-actions">', unsafe_allow_html=True)
        if st.button("Save", key="rename_save"):
            handle_rename_save(new_name)
        
        if st.button("Cancel", key="rename_cancel"):
            st.session_state.rename_modal_open = False
            st.rerun()
        st.markdown('</div></div></div>', unsafe_allow_html=True)

def handle_rename_save(new_name):
    """Handle saving renamed conversation"""
    if new_name.strip():
        success = update_conversation_name(
            st.session_state["username"],
            st.session_state.conversation_to_rename,
            new_name.strip()
        )
        if success:
            st.toast("✅ Conversation renamed successfully")
    st.session_state.rename_modal_open = False
    st.rerun()

def display_chat_messages():
    """Display chat message history"""
    st.markdown("<div class='chat-container'>", unsafe_allow_html=True)
    for msg in st.session_state.messages:
        bubble_class = "user-message" if msg["role"] == "user" else "bot-message"
        icon = "🧍" if msg["role"] == "user" else "🤖"
        timestamp = msg.get("timestamp", datetime.datetime.now())
        time_str = timestamp.strftime("%I:%M %p") if isinstance(timestamp, datetime.datetime) else ""
        
        st.markdown(f"""
        <div class='chat-wrapper' style='justify-content: {"flex-end" if msg["role"] == "user" else "flex-start"}'>
            <div class='chat-bubble {bubble_class}'>
                <div class='chat-timestamp'>{time_str}</div>
                <span>{icon}</span> {msg['content']}
            </div>
        </div>
        """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

def retrieve_context(query):
    """Retrieve relevant context from vector store"""
    pdf_hash = st.session_state.get("pdf_hash")
    if not pdf_hash or pdf_hash not in st.session_state["vector_cache"]:
        return "⚠️ No PDF loaded or vector store missing."
    results = st.session_state["vector_cache"][pdf_hash].similarity_search(query, k=3)
    return "\n".join([doc.page_content for doc in results])

def query_mistral_api(query):
    """Query Mistral API with context"""
    context = retrieve_context(query)
    if context.startswith("⚠️"):
        return context
    
    full_prompt = f"""Based on this context from the PDF:
{context}

Answer this question: {query}

If the answer cannot be found in the context, reply with "I couldn't find that information in the document.\""""
    
    try:
        response = requests.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {MISTRAL_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": MISTRAL_MODEL,
                "messages": [{"role": "user", "content": full_prompt}],
                "temperature": 0.3
            },
            timeout=30
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except requests.exceptions.RequestException as e:
        return f"⚠️ Error connecting to API: {str(e)}"
    except Exception as e:
        return f"⚠️ An unexpected error occurred: {str(e)}"

def handle_user_input(user_input):
    """Handle user message input"""
    current_time = datetime.datetime.now()
    user_msg = {"role": "user", "content": user_input, "timestamp": current_time}
    st.session_state.messages.append(user_msg)
    
    with st.spinner("🤖 Thinking..."):
        answer = query_mistral_api(user_input)
    
    bot_msg = {"role": "assistant", "content": answer, "timestamp": datetime.datetime.now()}
    st.session_state.messages.append(bot_msg)

    if "username" in st.session_state and st.session_state["pdf_hash"]:
        save_chat_history(
            st.session_state["username"],
            user_input,
            answer,
            st.session_state["pdf_hash"]
        )
    st.rerun()

def chat_page():
    """Main chat interface"""
    st.title("📄 PDF-Inquiry And Response System")

    # Initialize session state
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "vector_cache" not in st.session_state:
        st.session_state.vector_cache = {}
    if "pdf_hash" not in st.session_state:
        st.session_state.pdf_hash = None
    if "rename_modal_open" not in st.session_state:
        st.session_state.rename_modal_open = False
    if "conversation_to_rename" not in st.session_state:
        st.session_state.conversation_to_rename = None
    if "new_conversation_name" not in st.session_state:
        st.session_state.new_conversation_name = ""
    if "uploaded_files" not in st.session_state:
        st.session_state.uploaded_files = {}
    if "current_filename" not in st.session_state:
        st.session_state.current_filename = None

    # Sidebar with conversation history
    with st.sidebar:
        st.header("📜 Previous Conversations")
        
        if st.button("➕ New Chat", key="new_chat_btn", use_container_width=True):
            st.session_state.messages = []
            st.session_state.pdf_hash = None
            st.session_state.current_filename = None
            st.rerun()

        if "username" in st.session_state:
            chat_history = get_chat_history(st.session_state["username"])
            by_hash = {}
            for entry in chat_history:
                pdf_hash = entry.get("pdf_hash")
                if pdf_hash:
                    by_hash.setdefault(pdf_hash, []).append(entry)

            for pdf_hash, chats in by_hash.items():
                if not chats:
                    continue
                
                meta = get_conversation_meta(st.session_state["username"], pdf_hash)
                conversation_name = meta["conversation_name"] if meta else "New Conversation"
                latest_chat = chats[0]
                timestamp = latest_chat.get("timestamp", datetime.datetime.now())
                date_str = timestamp.strftime("%b %d, %I:%M %p") if isinstance(timestamp, datetime.datetime) else ""
                
                with st.container():
                    cols = st.columns([4, 1])
                    with cols[0]:
                        if st.button(
                            f"{conversation_name[:30]}{'...' if len(conversation_name) > 30 else ''}",
                            key=f"conv_{pdf_hash}",
                            use_container_width=True
                        ):
                            load_conversation(pdf_hash, chats)
                    with cols[1]:
                        if st.button("✏️", key=f"rename_{pdf_hash}", help="Rename conversation"):
                            prepare_rename(pdf_hash, conversation_name)
                    
                    st.markdown(f'<div class="sidebar-timestamp">{date_str}</div>', unsafe_allow_html=True)

    # Rename modal
    if st.session_state.rename_modal_open:
        show_rename_modal()

    # PDF uploader
    uploaded_files = st.file_uploader("📤 Upload PDF files", type="pdf", accept_multiple_files=True)
    
    for uploaded_file in uploaded_files:
        if uploaded_file.name not in st.session_state.uploaded_files:
            pdf_bytes = uploaded_file.read()
            pdf_hash = hash_pdf_bytes(pdf_bytes)
            
            with st.spinner(f"Processing {uploaded_file.name}..."):
                if pdf_hash not in st.session_state["vector_cache"]:
                    docs = load_and_process_pdf_from_bytes(pdf_bytes)
                    vs = create_vector_store(docs)
                    st.session_state["vector_cache"][pdf_hash] = vs
                    save_pdf_to_gridfs(pdf_bytes, uploaded_file.name)
            
            st.session_state.uploaded_files[uploaded_file.name] = pdf_hash
            st.toast(f"✅ {uploaded_file.name} processed successfully")
    
    if len(st.session_state.uploaded_files) > 0:
        selected_file = st.selectbox(
            "Select PDF to analyze",
            options=list(st.session_state.uploaded_files.keys()),
            key="pdf_selector",
            index=0 if not st.session_state.current_filename else list(st.session_state.uploaded_files.keys()).index(st.session_state.current_filename),
            format_func=lambda x: f"📄 {x}"
        )
        
        if selected_file != st.session_state.current_filename:
            st.session_state.current_filename = selected_file
            st.session_state.pdf_hash = st.session_state.uploaded_files[selected_file]
            st.session_state.messages = []
            st.rerun()

    # Action buttons container
    if st.session_state.get("pdf_hash"):
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("📝 Summarize PDF", 
                        key="summarize_btn", 
                        help="Generate a summary of the uploaded PDF",
                        use_container_width=True):
                with st.spinner("Generating summary..."):
                    summary = generate_pdf_summary()
                    if summary:
                        bot_msg = {"role": "assistant", "content": f"📝 PDF Summary:\n\n{summary}", "timestamp": datetime.datetime.now()}
                        st.session_state.messages.append(bot_msg)
                        
                        if "username" in st.session_state and st.session_state["pdf_hash"]:
                            save_chat_history(
                                st.session_state["username"],
                                "[System] Generate PDF summary",
                                summary,
                                st.session_state["pdf_hash"]
                            )
                        st.rerun()
        with col2:
            if st.button("💾 Export Chat", 
                         key="export_btn", 
                         help="Export conversation as PDF",
                         type="primary", 
                         use_container_width=True,
                         disabled=len(st.session_state.messages) == 0):
                export_chat_to_pdf()

    display_chat_messages()

    user_input = st.chat_input("Ask something about the PDF...")
    if user_input:
        handle_user_input(user_input)
import streamlit as st
import os
import json
from models.gemini import upload_to_gemini, wait_for_files_active, model, genai
from history.chat_history import (
    save_chat_history, 
    load_chat_history, 
    get_chat_histories,
    delete_chat_history
)

# Set page config and styling
st.set_page_config(
    page_title="DocuMiner",
    page_icon="assets/DC_logo.png",
)

st.markdown("""
    <style>
        .purple-title { color: #603fc7 !important; font-weight: 700; }
    </style>
""", unsafe_allow_html=True)

# Create title with logo
col1, col2 = st.columns([0.1, 0.85])
with col1:
    st.image("assets/DC_logo.png", width=70)
with col2:
    st.markdown("<h1 class='purple-title'>DocuMiner</h1>", unsafe_allow_html=True)

st.markdown("""
    <p style='font-size: 1.2em; color: #1e3c72; margin-bottom: 25px;'>
        Explora y analiza tus documentos regulatorios y legales de forma inteligente
    </p>
""", unsafe_allow_html=True)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "chat_session" not in st.session_state:
    st.session_state.chat_session = None
if "document_processed" not in st.session_state:
    st.session_state.document_processed = False
if "file_uploader_key" not in st.session_state:
    st.session_state.file_uploader_key = 0

# File uploader
uploaded_files = st.file_uploader(
    "**Nota:** Puedes subir hasta 3 PDFs para el chat.", 
    type=["pdf"], 
    accept_multiple_files=True,
    key=f"file_uploader_{st.session_state.file_uploader_key}"
)

# Sidebar chat history
with st.sidebar:
    st.title("⚙️ Configuración")
    api_key = st.text_input(
        "API Key de Gemini",
        type="password",
        help="Ingresa tu API key de Gemini para usar la aplicación",
        key="gemini_api_key"
    )
    
    if not api_key:
        st.error("Por favor ingresa tu API key de Gemini para continuar")
        st.stop()
    else:
        genai.configure(api_key=api_key)
    
    st.title("💬 Historial de Chat")
    st.markdown("""
        <style>
            div[data-baseweb="select"] { min-width: 200px; }
        </style>
    """, unsafe_allow_html=True)
    
    if "history_selector" not in st.session_state:
        st.session_state.history_selector = "-- Seleccionar chat --"
    
    if st.button("➕ Nuevo Chat", key="new_chat", help="Iniciar un nuevo chat"):
        # Only clear specific session state variables, excluding the API key widget
        keys_to_clear = [
            'messages',
            'chat_session',
            'document_processed',
            'history_selector',
            'initial_pdf_names',
            'chat_history_file',
            'gemini_files',
            'previous_selection'
        ]
        
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
        
        # Increment file uploader key
        st.session_state.file_uploader_key += 1
        
        # Initialize new chat state
        st.session_state.messages = []
        st.session_state.chat_session = None
        st.session_state.document_processed = False
        st.session_state.history_selector = "-- Seleccionar chat --"
        
        st.rerun()
    
    # Chat history selection
    histories = get_chat_histories()
    if histories:
        history_map = {h["filename"].replace('.json',''): h["filename"] 
                      for h in histories}
        chat_options = ["-- Seleccionar chat --"] + list(history_map.keys())
        selected_trimmed = st.selectbox(
            "Cargar chat anterior",
            chat_options,
            key="history_selector"
        )
        
        if selected_trimmed != "-- Seleccionar chat --":
            if st.button("🗑️ Eliminar Chat", 
                        key=f"delete_{selected_trimmed}", 
                        help="Eliminar este chat"):
                if delete_chat_history(selected_trimmed):
                    st.success("¡Chat eliminado exitosamente!")
                    st.session_state.messages = []
                    st.session_state.previous_selection = None
                    st.rerun()
                else:
                    st.error("Error al eliminar el chat.")
            
            selected_full = history_map[selected_trimmed]
            if ('previous_selection' not in st.session_state or 
                st.session_state.previous_selection != selected_full):
                
                restored = load_chat_history(f"history/chat_histories/{selected_full}")
                st.session_state.messages = restored
                st.session_state.previous_selection = selected_full
                st.session_state.initial_pdf_names = []
                st.session_state.document_processed = False
                st.session_state.chat_session = model.start_chat()
                st.rerun()

# Process uploaded files
if uploaded_files and not st.session_state.document_processed:
    if len(uploaded_files) > 3:
        st.error("Por favor sube un máximo de 3 PDFs.")
        st.stop()
    
    with st.spinner("Procesando documentos..."):
        st.session_state.initial_pdf_names = [f.name for f in uploaded_files]
        gemini_files = []
        
        for file in uploaded_files:
            temp_path = f"temp_{file.name}"
            with open(temp_path, "wb") as f:
                f.write(file.getbuffer())
            uploaded = upload_to_gemini(temp_path, mime_type="application/pdf")
            gemini_files.append(uploaded)
            os.remove(temp_path)
        
        wait_for_files_active(gemini_files)
        
        st.session_state.gemini_files = gemini_files
        st.session_state.chat_session = model.start_chat(history=[{"role": "user", "parts": gemini_files}])
        st.session_state.document_processed = True
        
        # Setup chat history file
        clean_names = ["".join(c for c in name.split('.')[0] if c.isalnum() or c in '_-') 
                      for name in st.session_state.initial_pdf_names]
        history_filename = f"chat_{'_'.join(clean_names)}.json"
        st.session_state.chat_history_file = f"history/chat_histories/{history_filename}"
        st.rerun()

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input and response
if prompt := st.chat_input("Pregunta sobre el documento", 
                          disabled=not st.session_state.document_processed):
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        # Send only the user's prompt without reattaching the PDF context.
        for response in st.session_state.chat_session.send_message(prompt, stream=True):
            full_response += response.text
            processed_response = (full_response.replace("\n", "\n\n")
                                             .replace("•", "\n•"))
            message_placeholder.markdown(processed_response + "▌")
        
        try:
            data = json.loads(full_response)
            response_text = data.get("response", full_response)
        except Exception:
            response_text = full_response
        
        response_text = (response_text.replace("\n", "\n\n")
                                    .replace("•", "\n•"))
        message_placeholder.markdown(response_text)
    
    st.session_state.messages.append({"role": "assistant", "content": response_text})

    if st.session_state.document_processed and "chat_history_file" in st.session_state:
        os.makedirs("history/chat_histories", exist_ok=True)
        save_chat_history(
            messages=st.session_state.messages,
            document_name="_".join(st.session_state.initial_pdf_names),
            filename=st.session_state.chat_history_file
        )
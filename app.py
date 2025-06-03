import os
import streamlit as st
from decouple import config
from db import create_history_table, load_chat_history, save_chat_to_db, delete_all_history
from loader import process_documents, get_available_files, delete_files
from chat import initialize_chain, get_response, render_sources
from ui import render_sidebar, render_chat_history

# Setup inicial
st.set_page_config(page_title="Chat com documentos (RAG)", page_icon="📄")
st.title("🤖 Chat com documentos (RAG)")
os.environ["OPENAI_API_KEY"] = config("OPENAI_API_KEY")
create_history_table()

# Sidebar
uploaded_files, selected_files, selected_model = render_sidebar()

# Opção para ignorar o histórico apenas na próxima pergunta
ignore_history = st.sidebar.checkbox("🔁 Ignorar histórico nesta pergunta", value=False)

# Processamento de arquivos
if uploaded_files:
    process_documents(uploaded_files)
    st.rerun()

# Histórico
st.subheader("🕘 Histórico")
render_chat_history(load_chat_history())

# Chat
prompt = st.chat_input("Como posso ajudar?")
if prompt and selected_files:
    with st.spinner("💬 Buscando resposta..."):
        qa_chain = initialize_chain(selected_files, selected_model)
        if qa_chain:
            result = get_response(qa_chain, prompt, ignore_history)
            resposta = result.get("answer")
            fontes = result.get("sources")
            with st.chat_message("user"):
                st.markdown(f"**({selected_model})** {prompt}")
            with st.chat_message("assistant"):
                st.markdown(resposta)
                render_sources(fontes)
            save_chat_to_db(selected_model, prompt, resposta, fontes)
    st.rerun()
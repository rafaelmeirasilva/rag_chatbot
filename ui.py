import os
import streamlit as st
from loader import get_available_files, delete_files, UPLOAD_DIRECTORY
from db import delete_all_history

def render_sidebar():
    with st.sidebar:
        st.header("Upload de arquivos 📄")
        # Pasta destino
        folders = [f for f in os.listdir(UPLOAD_DIRECTORY) if os.path.isdir(os.path.join(UPLOAD_DIRECTORY, f))]
        selected_folder = st.selectbox("📂 Selecionar pasta destino", folders + ["Nova pasta..."])
        if selected_folder == "Nova pasta...":
            new_folder = st.text_input("Nome da nova pasta")
            if new_folder:
                os.makedirs(os.path.join(UPLOAD_DIRECTORY, new_folder), exist_ok=True)
                selected_folder = new_folder
        uploaded_files = st.file_uploader("Faça o upload de arquivos", type=["pdf", "docx", "pptx", "csv", "txt"], accept_multiple_files=True)
        st.markdown("---")
        files = get_available_files()
        selected_files = st.multiselect("📁 Escolha os arquivos para base do RAG:", files, default=files)
        if selected_files and st.button("❌ Apagar arquivos selecionados"):
            delete_files(selected_files)
            st.success("Arquivos apagados.")
            st.rerun()
        st.markdown("---")
        selected_model = st.selectbox("Selecione o modelo LLM", ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo", "gpt-4o"])
        st.markdown("---")
        if st.button("🗑️ Limpar histórico"):
            delete_all_history()
            st.success("Histórico apagado com sucesso!")
    return uploaded_files, selected_files, selected_model, selected_folder

def render_chat_history(history_rows):
    for row in history_rows:
        chat_id, model, user_input, assistant_response, fontes = row
        with st.chat_message("user"):
            st.markdown(f"**({model})** {user_input}")
        with st.chat_message("assistant"):
            st.markdown(assistant_response)
            if fontes:
                st.markdown("🔍 **Fonte(s):**")
                for fonte in fontes.split(","):
                    st.markdown(f"- `{fonte.strip()}`")

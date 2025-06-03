import os
import streamlit as st
from decouple import config
from db import create_history_table, load_chat_history, save_chat_to_db, delete_all_history
from loader import process_documents, get_available_files, delete_files
from chat import initialize_chain, get_response, render_sources
from ui import render_sidebar, render_chat_history

# Setup inicial
st.set_page_config(page_title="Chat com documentos (RAG)", page_icon="📄")
os.environ["OPENAI_API_KEY"] = config("OPENAI_API_KEY")
create_history_table()

# Sidebar
uploaded_files, selected_files, selected_model = render_sidebar()

# Navegação
page = st.sidebar.radio("📌 Navegação", ["Chat", "Dashboard"])

# Opção para ignorar o histórico apenas na próxima pergunta
ignore_history = st.sidebar.checkbox("🔁 Ignorar histórico nesta pergunta", value=False)

if page == "Chat":
    # Processamento de arquivos
    if uploaded_files:
        process_documents(uploaded_files)
        st.rerun()
    
    st.title("🤖 Chat com documentos (RAG)")
    
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

elif page == "Dashboard":
    st.title("📊 Dashboard de Documentos")

    files = get_available_files()
    st.subheader("📁 Documentos carregados")

    if not files:
        st.info("Nenhum documento foi carregado ainda.")
    else:
        for file in files:
            with st.expander(f"📄 {file}"):
                st.markdown(f"**Nome:** `{file}`")
                # Leitor de conteúdo (parcial - apenas texto bruto por enquanto)
                file_path = os.path.join("uploaded_files", file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        st.text_area("Conteúdo do arquivo", content[:2000], height=300)
                except Exception as e:
                    st.warning("Não foi possível exibir o conteúdo (PDF ou binário).")

                # Classificação manual (futura persistência em SQLite)
                classification = st.text_input(f"Classificação para {file}", key=f"class_{file}")
                if st.button(f"💾 Salvar classificação para {file}", key=f"save_{file}"):
                    st.success(f"Classificação salva: {classification}")
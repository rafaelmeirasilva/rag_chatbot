import sqlite3
import os
import streamlit as st
import shutil
from decouple import config
from db import create_history_table, create_tag_table, load_chat_history, save_chat_to_db, delete_all_history, get_tags_for_file, save_tags_for_file, get_all_tags
from loader import process_documents, get_available_files, delete_files, UPLOAD_DIRECTORY
from chat import initialize_chain, get_response, render_sources
from ui import render_sidebar, render_chat_history

# Setup inicial
st.set_page_config(page_title="Chat com documentos (RAG)", page_icon="📄")
os.environ["OPENAI_API_KEY"] = config("OPENAI_API_KEY")
create_history_table()
create_tag_table()

# Sidebar
uploaded_files, selected_files, selected_model, selected_folder = render_sidebar()

# Navegação
page = st.sidebar.radio("📌 Navegação", ["Chat", "Dashboard", "Classificações", "Pastas"])

# Opção para ignorar o histórico apenas na próxima pergunta
ignore_history = st.sidebar.checkbox("🔁 Ignorar histórico nesta pergunta", value=False)

if page == "Chat":
    # Processamento de arquivos
    if uploaded_files:
        process_documents(uploaded_files, selected_folder)
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

    folders = sorted(set([f.split("/")[0] for f in files]))
    folder_filter = st.selectbox("📁 Filtrar por pasta", ["Todas"] + folders)
    filtered_files = [f for f in files if folder_filter == "Todas" or f.startswith(folder_filter + "/")]

    st.subheader("📁 Documentos carregados")

    if not files:
        st.info("Nenhum documento foi carregado ainda.")
    else:
        for file in filtered_files:
            with st.expander(f"📄 {file}"):
                st.markdown(f"**Nome:** `{file}`")
                existing_tags = get_tags_for_file(file)
                st.markdown(f"🏷️ **Classificação:** {', '.join(existing_tags) if existing_tags else 'Nenhuma'}")

                file_path = os.path.join("uploaded_files", file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        st.text_area("Conteúdo do arquivo", content[:2000], height=300)
                except:
                    st.warning("Não foi possível exibir o conteúdo (PDF ou binário).")

                all_tags = get_all_tags()
                selected_tags = st.multiselect(
                    f"Editar classificação (tags) para {file}",
                    options=all_tags,
                    default=existing_tags,
                    key=f"tag_selector_{file}"
                )
                new_tag = st.text_input(f"Adicionar nova tag para {file}", key=f"new_tag_{file}")
                if new_tag and new_tag not in selected_tags:
                    selected_tags.append(new_tag)

                if st.button(f"💾 Salvar classificação para {file}", key=f"save_{file}"):
                    save_tags_for_file(file, selected_tags)
                    st.success("Classificação salva com sucesso!")
                    st.rerun()

elif page == "Classificações":
    st.title("🏷️ Classificações (Tags)")

    all_tags = get_all_tags()
    if not all_tags:
        st.info("Nenhuma classificação encontrada ainda.")
    else:
        for tag in all_tags:
            st.subheader(f"🔖 Tag: `{tag}`")

            conn = sqlite3.connect("chat_history.sqlite3")
            c = conn.cursor()
            c.execute("SELECT file_name, tags FROM document_tags")
            rows = c.fetchall()
            conn.close()

            files = [file for file, tag_str in rows if tag in [t.strip() for t in tag_str.split(",")]]

            if files:
                for file in files:
                    with st.expander(f"📄 {file}"):
                        st.markdown(f"**Nome:** `{file}`")
                        path = os.path.join("uploaded_files", file)
                        try:
                            with open(path, "r", encoding="utf-8") as f:
                                content = f.read()
                                st.text_area("Conteúdo", content[:2000], height=200)
                        except:
                            st.warning("Não foi possível exibir este arquivo.")
            else:
                st.caption("Nenhum arquivo correspondente encontrado.")

elif page == "Pastas":
    st.title("📂 Gerenciador de Pastas")

    folders = os.listdir(UPLOAD_DIRECTORY)
    folders = [f for f in folders if os.path.isdir(os.path.join(UPLOAD_DIRECTORY, f))]
    selected_folder = st.selectbox("📁 Selecione uma pasta para gerenciar", folders + ["[Criar nova pasta]"])

    if selected_folder == "[Criar nova pasta]":
        new_folder = st.text_input("🔧 Nome da nova pasta")
        if new_folder and st.button("➕ Criar pasta"):
            os.makedirs(os.path.join(UPLOAD_DIRECTORY, new_folder), exist_ok=True)
            st.success(f"Pasta '{new_folder}' criada com sucesso!")
            st.rerun()

    elif selected_folder:
        folder_path = os.path.join(UPLOAD_DIRECTORY, selected_folder)
        st.subheader(f"📁 Pasta: `{selected_folder}`")

        # Renomear pasta
        new_name = st.text_input("✏️ Renomear pasta", value=selected_folder, key="rename_input")
        if new_name and new_name != selected_folder and st.button("🔄 Renomear"):
            os.rename(folder_path, os.path.join(UPLOAD_DIRECTORY, new_name))
            st.success("Pasta renomeada com sucesso!")
            st.rerun()

        # Listar arquivos da pasta
        files = os.listdir(folder_path)
        st.markdown("### 📄 Arquivos:")
        for file in files:
            file_path = os.path.join(folder_path, file)
            with st.expander(f"📄 {file}"):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        st.text_area("Conteúdo", content[:2000], height=200)
                except:
                    st.caption("Não foi possível visualizar o conteúdo.")

        # Mover arquivos
        if files:
            file_to_move = st.selectbox("📦 Escolha um arquivo para mover", files)
            target_folder = st.selectbox("📍 Mover para:", [f for f in folders if f != selected_folder])
            if st.button("🚚 Mover arquivo"):
                os.rename(
                    os.path.join(folder_path, file_to_move),
                    os.path.join(UPLOAD_DIRECTORY, target_folder, file_to_move)
                )
                st.success(f"{file_to_move} movido para {target_folder}!")
                st.rerun()

        # Excluir pasta
        if st.checkbox("⚠️ Deseja excluir esta pasta?"):
            delete_contents = st.checkbox("🗑️ Apagar todos os arquivos também?")
            if st.button("❌ Excluir pasta"):
                if delete_contents:
                    shutil.rmtree(folder_path)
                else:
                    os.rmdir(folder_path)
                st.success("Pasta excluída com sucesso!")
                st.rerun()

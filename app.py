import base64
import sqlite3
import hashlib
import pickle
import os
import pandas as pd
import shutil
import streamlit as st
import datetime
from pandas.tseries.offsets import BDay
from decouple import config
from db import create_history_table, create_lai_table, create_tag_table, load_chat_history, save_chat_to_db, delete_all_history, get_tags_for_file, save_tags_for_file, get_all_tags, create_notes_table, save_document_note, get_document_note
from langchain_community.document_loaders import PyPDFLoader
from loader import process_documents, get_available_files, load_file, delete_files, UPLOAD_DIRECTORY
from chat import initialize_chain, get_response, render_sources
from ui import render_sidebar, render_chat_history

# Funções

def resumir_documento(texto, max_chars=1000):
    resumo = texto.strip().replace("\n", " ").replace("  ", " ")
    return resumo[:max_chars] + "..." if len(resumo) > max_chars else resumo

def get_cached_summary(file_path):
    cache_file = f"{file_path}.summary.cache"
    if os.path.exists(cache_file):
        with open(cache_file, "rb") as f:
            return pickle.load(f)
    return None

def save_summary_cache(file_path, summary):
    cache_file = f"{file_path}.summary.cache"
    with open(cache_file, "wb") as f:
        pickle.dump(summary, f)

def buscar_perguntas_relacionadas(tag, id_atual):
    if not tag:
        return []
    conn = sqlite3.connect("chat_history.sqlite3")
    c = conn.cursor()
    c.execute("""
        SELECT id, pergunta FROM perguntas_lai
        WHERE tag = ? AND id != ?
        ORDER BY data_envio DESC LIMIT 5
    """, (tag, id_atual))
    relacionadas = c.fetchall()
    conn.close()
    return relacionadas

def buscar_documentos_por_tag(tag):
    if not tag:
        return []
    conn = sqlite3.connect("chat_history.sqlite3")
    c = conn.cursor()
    c.execute("""
        SELECT file_name FROM document_tags
        WHERE tags LIKE ?
    """, (f"%{tag}%",))
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

def get_cached_ocr(file_path):
    cache_path = f"{file_path}.ocr.cache"
    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            return f.read()
    return None

def save_cached_ocr(file_path, content):
    cache_path = f"{file_path}.ocr.cache"
    with open(cache_path, "w", encoding="utf-8") as f:
        f.write(content)

# Setup inicial
st.set_page_config(page_title="Chat com documentos (RAG)", page_icon="📄")
os.environ["OPENAI_API_KEY"] = config("OPENAI_API_KEY")
create_history_table()
create_tag_table()
create_notes_table()
create_lai_table()

if "page" not in st.session_state:
    st.session_state.page = "Analytics"

# Sidebar
uploaded_files, selected_files, selected_model, selected_folder = render_sidebar()

# ✅ Processa o upload de arquivos imediatamente ao serem enviados
if uploaded_files:
    process_documents(uploaded_files, selected_folder)
    st.success("📁 Arquivo(s) enviado(s) com sucesso!")
    st.rerun()

if "page" in st.session_state:
    page = st.session_state.page

# Navegação
pages = ["Chat", "Dashboard", "Classificações", "Pastas", "Analytics", "Busca", "Perguntas LAI", "Cadastro LAI"]

page = st.sidebar.radio("📌 Navegação", pages, index=pages.index(st.session_state.page))

# Corrige perda da navegação após upload
if "_prev_page" in st.session_state:
    st.session_state.page = st.session_state._prev_page
    del st.session_state._prev_page
    st.rerun()

if st.sidebar.button("➕ Cadastrar nova pergunta LAI"):
    st.session_state.page = "Cadastro LAI"
    st.rerun()

# Opção para ignorar o histórico apenas na próxima pergunta
ignore_history = st.sidebar.checkbox("🔁 Ignorar histórico nesta pergunta", value=False)

if page == "Chat":
    # Processamento de arquivos
    if uploaded_files:
        st.session_state._prev_page = st.session_state.page  # Salva página ativa
        process_documents(uploaded_files, selected_folder)
        st.success("📁 Arquivo(s) enviado(s) com sucesso!")
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
                note, favorite = get_document_note(file)

                # Favorito
                is_fav = st.checkbox("⭐ Marcar como favorito", value=bool(favorite), key=f"fav_{file}")

                # Anotação
                user_note = st.text_area("📝 Anotação para este documento", value=note, height=100, key=f"note_{file}")

                if st.button("💾 Salvar anotação/favorito", key=f"save_note_{file}"):
                    save_document_note(file, user_note, is_fav)
                    st.success("Salvo com sucesso!")

                st.markdown(f"**Nome:** `{file}`")
                existing_tags = get_tags_for_file(file)
                st.markdown(f"🏷️ **Classificação:** {', '.join(existing_tags) if existing_tags else 'Nenhuma'}")

                file_path = os.path.join("uploaded_files", file)

                import base64  # coloque no topo do app.py, se ainda não estiver

                if file.endswith(".pdf"):
                    # Botão de download
                    with open(file_path, "rb") as f:
                        st.download_button("📥 Baixar PDF original", data=f, file_name=os.path.basename(file_path))

                    # Exibição do PDF diretamente na tela
                    with open(file_path, "rb") as f:
                        base64_pdf = base64.b64encode(f.read()).decode('utf-8')
                        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="500px" type="application/pdf"></iframe>'
                        st.markdown(pdf_display, unsafe_allow_html=True)

                    # Texto extraído via OCR
                    cached_text = get_cached_ocr(file_path)
                    if cached_text:
                        st.text_area("📄 Conteúdo extraído do PDF (cache)", value=cached_text[:3000], height=300)
                    else:
                        try:
                            loader = PyPDFLoader(file_path)
                            docs = loader.load()
                            full_text = "\n".join([doc.page_content for doc in docs])
                            save_cached_ocr(file_path, full_text)
                            st.text_area("📄 Conteúdo extraído do PDF", value=full_text[:3000], height=300)
                        except Exception as e:
                            st.warning(f"Não foi possível extrair texto do PDF: {e}")

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

elif page == "Analytics":
    st.title("📊 Analytics do Sistema")

    # Número total de documentos
    files = get_available_files()
    st.metric("📁 Total de documentos", len(files))

    # Tags mais usadas
    tag_counts = {}
    conn = sqlite3.connect("chat_history.sqlite3")
    c = conn.cursor()
    c.execute("SELECT tags FROM document_tags")
    rows = c.fetchall()
    for row in rows:
        if row[0]:
            for tag in row[0].split(","):
                tag = tag.strip()
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
    conn.close()

    if tag_counts:
        st.subheader("🏷️ Tags mais usadas")
        df_tags = pd.DataFrame(tag_counts.items(), columns=["Tag", "Quantidade"]).sort_values(by="Quantidade", ascending=False)
        st.bar_chart(df_tags.set_index("Tag"))
    else:
        st.info("Nenhuma tag registrada ainda.")

    # Uso por modelo
    c = sqlite3.connect("chat_history.sqlite3").cursor()
    c.execute("SELECT model, COUNT(*) FROM history GROUP BY model")
    model_data = c.fetchall()
    if model_data:
        st.subheader("🧠 Uso por modelo LLM")
        df_model = pd.DataFrame(model_data, columns=["Modelo", "Interações"])
        st.bar_chart(df_model.set_index("Modelo"))

elif page == "Busca":
    st.title("🔍 Busca textual em documentos")

    query = st.text_input("Digite um termo para buscar")
    if query:
        files = get_available_files()
        resultados = []

        for file in files:
            path = os.path.join("uploaded_files", file)
            try:
                docs = load_file(path)
                if docs:
                    full_text = "\n".join([doc.page_content for doc in docs])
                    if query.lower() in full_text.lower():
                        trechos = [linha.strip() for linha in full_text.split("\n") if query.lower() in linha.lower()]
                        resultados.append((file, trechos[:3]))  # mostra até 3 trechos
            except Exception as e:
                st.warning(f"Erro ao processar {file}: {str(e)}")

        if not resultados:
            st.warning("Nenhum resultado encontrado.")
        else:
            st.success(f"{len(resultados)} documento(s) encontrados.")
            for file, trechos in resultados:
                file_path = os.path.join("uploaded_files", file)
                cached_summary = get_cached_summary(file_path)
                if not cached_summary:
                    joined_text = "\n".join([t for t in trechos])
                    resumo = resumir_documento(joined_text)
                    save_summary_cache(file_path, resumo)
                else:
                    resumo = cached_summary

                with st.expander(f"📄 {file}"):
                    st.markdown("🔹 **Resumo do documento:**")
                    st.markdown(f"> {resumo}")
                    st.markdown("🔍 **Trechos encontrados:**")
                    for trecho in trechos:
                        st.markdown(f"- {trecho}")

elif page == "LAI":
    st.title("📄 Cadastro de Perguntas - Lei de Acesso à Informação")

    with st.form("form_lai"):
        pergunta = st.text_area("📝 Texto da pergunta", height=100)
        data_envio = st.date_input("📆 Data de envio da pergunta", value=datetime.date.today())
        data_limite = (pd.to_datetime(data_envio) + BDay(20)).date()

        st.markdown(f"⏱️ **Data limite para resposta (20 dias úteis):** `{data_limite}`")

        origem = st.text_input("🌐 Origem da pergunta")
        destinatario = st.text_input("🏛️ Unidade destinatária")

        col1, col2 = st.columns(2)
        with col1:
            orgao_recursal_1 = st.text_input("📤 1º órgão recursal")
            site_orgao_recursal_1 = st.text_input("🔗 Site 1º órgão")
        texto_recurso_1 = st.text_area("🗣️ Texto do 1º recurso")

        col3, col4 = st.columns(2)
        with col3:
            orgao_recursal_2 = st.text_input("📤 2º órgão recursal")
            site_orgao_recursal_2 = st.text_input("🔗 Site 2º órgão")
        texto_recurso_2 = st.text_area("🗣️ Texto do 2º recurso")

        tag = st.text_input("🏷️ Tag (para vincular documentos e perguntas semelhantes)")
        transparencia_ativa = st.checkbox("🔍 Informação disponível por transparência ativa?")
        
        # Só aparece se usuário for superuser (placeholder por enquanto: visível a todos)
        observacao_privada = st.text_area("🔒 Observação privada (visível só ao superuser)")

        submitted = st.form_submit_button("💾 Salvar pergunta")
        if submitted:
            conn = sqlite3.connect("chat_history.sqlite3")
            c = conn.cursor()
            c.execute("""
                INSERT INTO perguntas_lai (
                    pergunta, data_envio, data_limite_resposta,
                    origem, destinatario,
                    orgao_recursal_1, site_orgao_recursal_1, texto_recurso_1,
                    orgao_recursal_2, site_orgao_recursal_2, texto_recurso_2,
                    tag, transparencia_ativa, observacao_privada
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pergunta, str(data_envio), str(data_limite),
                origem, destinatario,
                orgao_recursal_1, site_orgao_recursal_1, texto_recurso_1,
                orgao_recursal_2, site_orgao_recursal_2, texto_recurso_2,
                tag, int(transparencia_ativa), observacao_privada
            ))
            conn.commit()
            conn.close()
            st.success("Pergunta cadastrada com sucesso!")


elif page == "Cadastro LAI":
    st.title("📝 Cadastro de nova pergunta (LAI)")

    with st.form("form_lai"):
        pergunta = st.text_area("📝 Texto da pergunta", height=100)
        data_envio = st.date_input("📆 Data de envio da pergunta", value=datetime.date.today())
        data_limite = (pd.to_datetime(data_envio) + pd.offsets.BDay(20)).date()

        st.markdown(f"⏱️ **Data limite para resposta (20 dias úteis):** `{data_limite}`")

        origem = st.text_input("🌐 Origem da pergunta")
        destinatario = st.text_input("🏛️ Unidade destinatária")

        col1, col2 = st.columns(2)
        with col1:
            orgao_recursal_1 = st.text_input("📤 1º órgão recursal")
            site_orgao_recursal_1 = st.text_input("🔗 Site 1º órgão")
        texto_recurso_1 = st.text_area("🗣️ Texto do 1º recurso")

        col3, col4 = st.columns(2)
        with col3:
            orgao_recursal_2 = st.text_input("📤 2º órgão recursal")
            site_orgao_recursal_2 = st.text_input("🔗 Site 2º órgão")
        texto_recurso_2 = st.text_area("🗣️ Texto do 2º recurso")

        tag = st.text_input("🏷️ Tag (para vincular documentos e perguntas semelhantes)")
        transparencia_ativa = st.checkbox("🔍 Informação disponível por transparência ativa?")
        
        observacao_privada = st.text_area("🔒 Observação privada (visível só ao superuser)")

        submitted = st.form_submit_button("💾 Salvar pergunta")
        if submitted:
            conn = sqlite3.connect("chat_history.sqlite3")
            c = conn.cursor()
            c.execute("""
                INSERT INTO perguntas_lai (
                    pergunta, data_envio, data_limite_resposta,
                    origem, destinatario,
                    orgao_recursal_1, site_orgao_recursal_1, texto_recurso_1,
                    orgao_recursal_2, site_orgao_recursal_2, texto_recurso_2,
                    tag, transparencia_ativa, observacao_privada
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pergunta, str(data_envio), str(data_limite),
                origem, destinatario,
                orgao_recursal_1, site_orgao_recursal_1, texto_recurso_1,
                orgao_recursal_2, site_orgao_recursal_2, texto_recurso_2,
                tag, int(transparencia_ativa), observacao_privada
            ))
            conn.commit()
            conn.close()
            st.success("Pergunta cadastrada com sucesso!")
            st.session_state.page = "Perguntas LAI"
            st.rerun()

elif page == "Perguntas LAI":
    st.title("📄 Perguntas cadastradas (LAI)")

    conn = sqlite3.connect("chat_history.sqlite3")
    c = conn.cursor()

    # Captura filtros únicos
    c.execute("SELECT DISTINCT tag FROM perguntas_lai WHERE tag IS NOT NULL")
    tags = [row[0] for row in c.fetchall() if row[0]]

    c.execute("SELECT DISTINCT destinatario FROM perguntas_lai WHERE destinatario IS NOT NULL")
    orgaos = [row[0] for row in c.fetchall() if row[0]]

    # Filtros
    col1, col2 = st.columns(2)
    with col1:
        filtro_tag = st.selectbox("🏷️ Filtrar por Tag", ["Todos"] + tags)
    with col2:
        filtro_destinatario = st.selectbox("🏛️ Filtrar por Unidade", ["Todos"] + orgaos)

    # Botão para novo cadastro
    if st.button("➕ Cadastrar nova pergunta"):
        st.session_state.page = "Cadastro LAI"
        st.rerun()

    # Construção da query com filtros
    query_base = "FROM perguntas_lai WHERE 1=1"
    params = []

    if filtro_tag != "Todos":
        query_base += " AND tag = ?"
        params.append(filtro_tag)

    if filtro_destinatario != "Todos":
        query_base += " AND destinatario = ?"
        params.append(filtro_destinatario)

    por_pagina = 20
    c.execute(f"SELECT COUNT(*) {query_base}", params)
    total = c.fetchone()[0]
    total_paginas = max((total - 1) // por_pagina + 1, 1)
    pagina = st.number_input("Página", 1, total_paginas, 1)
    offset = (pagina - 1) * por_pagina

    c.execute(f"""
        SELECT id, pergunta, data_envio, data_limite_resposta, destinatario, tag, observacao_privada
        {query_base}
        ORDER BY data_envio DESC
        LIMIT ? OFFSET ?
    """, params + [por_pagina, offset])
    rows = c.fetchall()
    conn.close()

    if not rows:
        st.info("Nenhuma pergunta cadastrada.")
    else:
        for id_, pergunta, data_envio, data_limite, destinatario, tag, obs_privada in rows:
            with st.expander(f"📌 Pergunta #{id_} - {data_envio}"):
                nova_pergunta = st.text_area("📝 Pergunta", value=pergunta, key=f"edit_pergunta_{id_}")
                nova_tag = st.text_input("🏷️ Tag", value=tag or "", key=f"edit_tag_{id_}")
                nova_obs = st.text_area("🔒 Observação privada", value=obs_privada or "", key=f"edit_obs_{id_}")

                st.markdown(f"**Unidade destinatária:** `{destinatario}`")
                st.markdown(f"**Prazo para resposta:** `{data_limite}`")
                relacionadas = buscar_perguntas_relacionadas(tag, id_)
                if relacionadas:
                    st.markdown("🔗 **Perguntas relacionadas:**")
                    for rid, texto in relacionadas:
                        resumo = texto.strip().replace("\n", " ")
                        st.markdown(f"- #{rid}: {resumo[:100]}{'...' if len(resumo) > 100 else ''}")
                    docs_relacionados = buscar_documentos_por_tag(tag)
                    st.markdown("📎 **Documentos relacionados:**")
                    for doc in docs_relacionados:
                        st.markdown(f"**📄 {doc}**")
                        path = os.path.join("uploaded_files", doc)
                        try:
                            with open(path, "r", encoding="utf-8") as f:
                                conteudo = f.read()
                                st.text_area("Conteúdo", conteudo[:2000], height=200, key=f"txt_{doc}")
                        except:
                            st.caption("❌ Não foi possível exibir o conteúdo.")



                if st.button("💾 Salvar alterações", key=f"salvar_{id_}"):
                    conn2 = sqlite3.connect("chat_history.sqlite3")
                    c2 = conn2.cursor()
                    c2.execute("""
                        UPDATE perguntas_lai
                        SET pergunta = ?, tag = ?, observacao_privada = ?
                        WHERE id = ?
                    """, (nova_pergunta, nova_tag, nova_obs, id_))
                    conn2.commit()
                    conn2.close()
                    st.success("Alterações salvas!")
                    st.rerun()


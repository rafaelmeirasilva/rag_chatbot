import os
import logging
from langchain_community.document_loaders import (
    PyPDFLoader, UnstructuredWordDocumentLoader, UnstructuredPowerPointLoader,
    UnstructuredCSVLoader, TextLoader
)
from langchain_community.document_loaders.unstructured import UnstructuredFileLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
import streamlit as st

UPLOAD_DIRECTORY = "uploaded_files"
PERSIST_DIRECTORY = "chroma"
os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)
os.makedirs(PERSIST_DIRECTORY, exist_ok=True)

def load_file(file_path):
    try:
        if file_path.endswith(".pdf"):
            return PyPDFLoader(file_path).load_and_split()
        elif file_path.endswith(".docx"):
            return UnstructuredWordDocumentLoader(file_path).load()
        elif file_path.endswith(".pptx"):
            return UnstructuredPowerPointLoader(file_path).load()
        elif file_path.endswith(".csv"):
            return UnstructuredCSVLoader(file_path).load()
        elif file_path.endswith(".txt"):
            return TextLoader(file_path).load()
        else:
            return []
    except Exception as e:
        return UnstructuredFileLoader(file_path).load()

def process_documents(uploaded_files, target_folder=""):
    target_path = os.path.join(UPLOAD_DIRECTORY, target_folder) if target_folder else UPLOAD_DIRECTORY
    if not os.path.isdir(target_path):
        os.makedirs(target_path, exist_ok=True)
    for uploaded_file in uploaded_files:
        file_path = os.path.join(target_path, uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
    st.success("Arquivos enviados com sucesso!")

def delete_files(files):
    for rel_path in files:
        path = os.path.join(UPLOAD_DIRECTORY, rel_path)
        if os.path.exists(path):
            os.remove(path)

def get_available_files():
    files = []
    for root, _, filenames in os.walk(UPLOAD_DIRECTORY):
        for filename in filenames:
            rel_path = os.path.relpath(os.path.join(root, filename), UPLOAD_DIRECTORY)
            files.append(rel_path.replace("\\", "/"))  # Windows fix
    return files


def get_vectorstore(selected_files):
    all_chunks = []
    for filename in selected_files:
        path = os.path.join(UPLOAD_DIRECTORY, filename)
        pages = load_file(path)
        if pages:
            splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=400)
            chunks = splitter.split_documents(pages)
            for chunk in chunks:
                chunk.metadata["source"] = filename
            logging.info(f"{filename} → {len(chunks)} chunk(s) vetorizado(s)")
            all_chunks.extend(chunks)
        else:
            logging.warning(f"{filename} → Falha ao carregar conteúdo ou OCR necessário")
    if all_chunks:
        vector_store = Chroma.from_documents(
            documents=all_chunks,
            embedding=OpenAIEmbeddings(),
            persist_directory=PERSIST_DIRECTORY
        )
        return vector_store
    return None

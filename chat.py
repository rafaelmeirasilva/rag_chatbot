from langchain.chains import RetrievalQAWithSourcesChain
from langchain.schema import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from loader import get_vectorstore
import streamlit as st

def initialize_chain(selected_files, selected_model):
    vector_store = get_vectorstore(selected_files)
    if not vector_store:
        st.error("❌ Nenhum conteúdo válido vetorizado.")
        return None
    # llm = ChatOpenAI(temperature=0.7, model_name=selected_model)
    llm = ChatOpenAI(
        temperature=0.8,
        model_name=selected_model,
        max_tokens=1500
    )
    return RetrievalQAWithSourcesChain.from_chain_type(
        llm=llm,
        retriever=vector_store.as_retriever(),
        return_source_documents=False
    )

def get_response(chain, prompt, ignore_history=False):
    if ignore_history:
        messages = []
    else:
        system_prompt = SystemMessage(content=(
            "Você é um assistente altamente qualificado. Sempre responda de forma explicativa, didática e completa, "
            "com exemplos e clareza. Evite respostas curtas. Estruture a resposta como se estivesse ensinando o assunto."
        ))
        messages = [system_prompt, HumanMessage(content=prompt)]

    return chain.invoke({"question": prompt, "chat_history": messages})


def render_sources(source_string):
    if source_string:
        st.markdown("🔍 **Fonte(s):**")
        for fonte in source_string.split(","):
            st.markdown(f"- `{fonte.strip()}`")
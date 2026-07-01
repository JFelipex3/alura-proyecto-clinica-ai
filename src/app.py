from __future__ import annotations

# --- PARCHE DE SQLITE3 PARA CHROMADB ---
import sys
try:
    __import__('pysqlite3')
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    pass
# ---------------------------------------
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.vectorstore import VectorStore
from src.agent import ClinicAgent

st.set_page_config(
    page_title="Asistente Clínica Bienestar Integral",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

CLINIC_NAME = "Clínica Bienestar Integral"
EMERGENCY_NOTE = (
    "⚠️ **Emergencias médicas:** llame al **131** o acuda directamente "
    "a nuestra sala de Urgencias, disponible las 24 horas."
)


@st.cache_resource(show_spinner="Cargando base de conocimiento...")
def get_vectorstore() -> VectorStore:
    return VectorStore(persist_dir="./chroma_db")


@st.cache_resource(show_spinner="Iniciando agente de IA...")
def get_agent() -> ClinicAgent:
    return ClinicAgent()


def render_sidebar(doc_count: int) -> int:
    with st.sidebar:
        st.markdown(f"## 🏥 {CLINIC_NAME}")
        st.markdown("**Asistente Virtual con IA**")
        st.divider()

        st.markdown("### 📚 Base de conocimiento")
        if doc_count == 0:
            st.warning("Sin documentos indexados.")
            st.code("python scripts/ingest_docs.py", language="bash")
        else:
            st.success(f"{doc_count} fragmentos indexados")
            st.markdown("""
- 📋 Política de privacidad de datos
- ❓ Preguntas frecuentes sobre turnos
- 📅 Política de cancelaciones
- 🏥 Guía de convenios y coberturas
- 💊 Instrucciones pre y post consulta
- 📊 Tabla de convenios
""")

        st.divider()
        n = st.slider("Fragmentos a recuperar", min_value=2, max_value=8, value=4)
        st.divider()

        st.markdown(EMERGENCY_NOTE)
        st.divider()

        if st.button("🗑️ Limpiar conversación", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

    return n


def render_chat(vectorstore: VectorStore, agent: ClinicAgent, n_results: int) -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("sources"):
                with st.expander("📂 Documentos consultados"):
                    for src in msg["sources"]:
                        st.markdown(f"- `{src}`")

    placeholder = "Escribe tu pregunta sobre la clínica…"
    if prompt := st.chat_input(placeholder):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Consultando documentos…"):
                try:
                    hits = vectorstore.search(prompt, n_results=n_results)
                    history = [
                        {"role": m["role"], "content": m["content"]}
                        for m in st.session_state.messages[:-1]
                    ]
                    result = agent.answer(prompt, hits, history)

                    st.markdown(result["answer"])
                    if result["sources"]:
                        with st.expander("📂 Documentos consultados"):
                            for src in result["sources"]:
                                st.markdown(f"- `{src}`")

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": result["answer"],
                        "sources": result["sources"],
                    })
                except Exception as exc:
                    error_msg = f"Lo siento, ocurrió un error: {exc}"
                    st.error(error_msg)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": error_msg,
                        "sources": [],
                    })


def main() -> None:
    st.title("🏥 Asistente Virtual")
    st.subheader(CLINIC_NAME)

    try:
        vectorstore = get_vectorstore()
        agent = get_agent()
    except ValueError as exc:
        st.error(str(exc))
        st.info("Configure la variable GOOGLE_API_KEY en el archivo `.env` y reinicie la aplicación.")
        return

    doc_count = vectorstore.count()
    n_results = render_sidebar(doc_count)

    if doc_count == 0:
        st.warning(
            "La base de conocimiento está vacía. "
            "Ejecuta `python scripts/ingest_docs.py` para indexar los documentos."
        )
        return

    render_chat(vectorstore, agent, n_results)


if __name__ == "__main__":
    main()

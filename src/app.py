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
from src.ingestion import load_and_chunk_single, SUPPORTED_EXTENSIONS

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

        st.divider()
        n = st.slider("Fragmentos a recuperar", min_value=2, max_value=8, value=4)
        st.divider()

        st.markdown(EMERGENCY_NOTE)
        st.divider()

        if st.button("🗑️ Limpiar conversación", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

    return n


def _docs_dir() -> Path:
    return Path(__file__).parent.parent / "docs"


def render_doc_management(vectorstore: VectorStore) -> None:
    st.subheader("Subir o actualizar documentos")

    if "uploader_key" not in st.session_state:
        st.session_state.uploader_key = 0

    allowed_types = [ext.lstrip(".") for ext in SUPPORTED_EXTENSIONS]
    uploaded_files = st.file_uploader(
        "Selecciona uno o más archivos",
        type=allowed_types,
        accept_multiple_files=True,
        help="Si el nombre coincide con un documento existente, se actualizará.",
        key=f"doc_uploader_{st.session_state.uploader_key}",
    )

    if uploaded_files:
        to_update = [f for f in uploaded_files if (_docs_dir() / f.name).exists()]
        to_add = [f for f in uploaded_files if not (_docs_dir() / f.name).exists()]
        parts = []
        if to_add:
            parts.append(f"{len(to_add)} nuevo(s)")
        if to_update:
            parts.append(f"{len(to_update)} a actualizar")
        label = f"Indexar ({', '.join(parts)})"

        if st.button(label, type="primary"):
            errors = []
            for uploaded in uploaded_files:
                dest = _docs_dir() / uploaded.name
                dest.write_bytes(uploaded.getbuffer())
                with st.spinner(f"Indexando «{uploaded.name}»… (puede tardar por límites de la API)"):
                    try:
                        vectorstore.delete_document(uploaded.name)
                        chunks = load_and_chunk_single(str(dest))
                        vectorstore.add_documents(chunks)
                        st.success(f"«{uploaded.name}» indexado ({len(chunks)} fragmentos).")
                    except Exception as exc:
                        errors.append(uploaded.name)
                        st.error(f"Error al indexar «{uploaded.name}»: {exc}")
            if not errors:
                st.session_state.uploader_key += 1
                st.rerun()

    st.divider()
    st.subheader("Documentos indexados")

    docs = vectorstore.list_documents()
    if not docs:
        st.info("No hay documentos indexados aún.")
        return

    if "confirm_delete" not in st.session_state:
        st.session_state.confirm_delete = None

    for doc in sorted(docs, key=lambda d: d["source"]):
        col_name, col_cat, col_chunks, col_btn = st.columns([3, 2, 1, 1])
        col_name.markdown(f"**{doc['source']}**")
        col_cat.caption(doc["category"])
        col_chunks.caption(f"{doc['total_chunks']} frags.")

        btn_key = f"del_{doc['source']}"
        if col_btn.button("🗑️", key=btn_key, help="Eliminar documento"):
            st.session_state.confirm_delete = doc["source"]

    if st.session_state.confirm_delete:
        source = st.session_state.confirm_delete
        st.warning(f"¿Eliminar «{source}» del índice y del directorio docs/?")
        c1, c2 = st.columns(2)
        if c1.button("Confirmar eliminación", type="primary"):
            with st.spinner(f"Eliminando «{source}»…"):
                vectorstore.delete_document(source)
                file_path = _docs_dir() / source
                if file_path.exists():
                    file_path.unlink()
            st.session_state.confirm_delete = None
            st.success(f"«{source}» eliminado.")
            st.rerun()
        if c2.button("Cancelar"):
            st.session_state.confirm_delete = None
            st.rerun()


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

    tab_chat, tab_docs = st.tabs(["💬 Asistente", "📂 Documentos"])

    with tab_chat:
        if doc_count == 0:
            st.warning(
                "La base de conocimiento está vacía. "
                "Ve a la pestaña **📂 Documentos** para indexar archivos."
            )
        else:
            render_chat(vectorstore, agent, n_results)

    with tab_docs:
        render_doc_management(vectorstore)


if __name__ == "__main__":
    main()

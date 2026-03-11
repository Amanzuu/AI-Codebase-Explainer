import streamlit as st

from repo_loader import clone_repo
from code_loader import load_code_files
from embeddings import create_vector_store
from rag_pipeline import create_qa_chain

st.set_page_config(
    page_title="AI Codebase Explainer by Aman",
    page_icon="🤖",
    layout="wide",
)


def ask_question(question):
    st.session_state.messages.append({"role": "user", "content": question})
    with st.spinner("Thinking..."):
        response = st.session_state.qa_chain.invoke({"query": question})
        answer = response["result"]
    st.session_state.messages.append({"role": "assistant", "content": answer})


st.markdown(
    """
    <style>
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(255, 143, 31, 0.14), transparent 28%),
                radial-gradient(circle at top right, rgba(61, 169, 255, 0.12), transparent 24%),
                linear-gradient(180deg, #07111f 0%, #0b1320 100%);
        }
        .block-container {
            max-width: 1120px;
            padding-top: 2rem;
            padding-bottom: 2rem;
            font-size: 1.06rem;
        }
        .hero-card,
        .panel-card,
        .chat-shell {
            background: linear-gradient(180deg, rgba(16, 24, 39, 0.92), rgba(10, 16, 28, 0.96));
            border: 1px solid rgba(148, 163, 184, 0.14);
            border-radius: 24px;
            box-shadow: 0 24px 60px rgba(0, 0, 0, 0.26);
        }
        .hero-card {
            padding: 1.8rem 1.8rem 1.4rem 1.8rem;
            margin-bottom: 1.2rem;
        }
        .eyebrow {
            color: #ffb469;
            font-size: 1.02rem;
            font-weight: 800;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            margin-bottom: 0.6rem;
        }
        .hero-title {
            color: #f8fafc;
            font-size: 3.2rem;
            line-height: 1;
            font-weight: 800;
            margin: 0 0 0.8rem 0;
        }
        .hero-subtitle {
            color: #cbd5e1;
            font-size: 1.1rem;
            line-height: 1.6;
            max-width: 760px;
            margin: 0;
        }
        .panel-card {
            padding: 1.15rem 1.2rem 1rem 1.2rem;
            margin-bottom: 1rem;
        }
        .section-title {
            color: #f8fafc;
            font-size: 1.28rem;
            font-weight: 700;
            margin-bottom: 0.25rem;
        }
        .section-copy {
            color: #94a3b8;
            font-size: 1.04rem;
            margin-bottom: 0.9rem;
        }
        .stat-chip-wrap {
            display: flex;
            gap: 0.75rem;
            flex-wrap: wrap;
            margin: 0.5rem 0 1rem 0;
        }
        .stat-chip {
            min-width: 150px;
            background: rgba(15, 23, 42, 0.82);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 18px;
            padding: 0.85rem 1rem;
        }
        .stat-label {
            color: #94a3b8;
            font-size: 0.84rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
        }
        .stat-value {
            color: #f8fafc;
            font-size: 1.35rem;
            font-weight: 700;
            margin-top: 0.15rem;
        }
        .prompt-card,
        .sidebar-card {
            background: rgba(15, 23, 42, 0.82);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 20px;
            padding: 1rem;
        }
        .prompt-card {
            margin-top: 0.8rem;
            margin-bottom: 0.9rem;
        }
        .prompt-title,
        .mini-title {
            color: #f8fafc;
            font-size: 1.14rem;
            font-weight: 700;
            margin-bottom: 0.2rem;
        }
        .prompt-copy,
        .mini-copy {
            color: #94a3b8;
            font-size: 1rem;
            line-height: 1.55;
            margin: 0;
        }
        .chat-shell {
            padding: 1rem 1rem 0.25rem 1rem;
            margin-top: 0.8rem;
        }
        .stChatMessage {
            background: transparent;
        }
        .stChatMessage > div {
            border-radius: 20px;
        }
        .stChatInputContainer {
            background: rgba(9, 14, 25, 0.92);
            border-top: 1px solid rgba(255, 255, 255, 0.08);
        }
        .stTextInput input {
            border-radius: 14px;
            background: rgba(15, 23, 42, 0.9);
            font-size: 1.02rem;
        }
        .stButton button {
            border-radius: 14px;
            border: 1px solid rgba(255, 196, 120, 0.32);
            background: #f7a12b;
            color: #111827;
            font-weight: 800;
            font-size: 1.04rem;
            box-shadow: none;
            padding: 0.72rem 1rem;
        }
        .stButton button:hover {
            border-color: rgba(255, 210, 152, 0.4);
            background: #f9ae44;
            color: #111827;
        }
        .stButton button:disabled {
            background: #9b6b32;
            color: rgba(255, 245, 235, 0.82);
            border-color: rgba(255, 198, 130, 0.16);
        }
        [data-testid="stSidebar"] {
            background: rgba(7, 17, 31, 0.88);
            border-right: 1px solid rgba(255, 255, 255, 0.06);
        }
        [data-testid="stSidebar"] .stButton button {
            width: 100%;
        }
        .helper-note {
            color: #94a3b8;
            font-size: 1rem;
            margin-top: 0.3rem;
        }
        .stCaption,
        .stMarkdown,
        .stSelectbox label,
        .stTextInput label {
            font-size: 1rem;
        }
        [data-testid="stChatMessageContent"] {
            font-size: 1.04rem;
            line-height: 1.7;
        }
        [data-testid="stChatInput"] textarea {
            font-size: 1.02rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

if "qa_chain" not in st.session_state:
    st.session_state.qa_chain = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "repo_url" not in st.session_state:
    st.session_state.repo_url = ""
if "repo_stats" not in st.session_state:
    st.session_state.repo_stats = {"files": 0, "status": "Idle", "model": "phi3"}
if "pending_question" not in st.session_state:
    st.session_state.pending_question = ""
if "file_map" not in st.session_state:
    st.session_state.file_map = {}
if "file_explanation" not in st.session_state:
    st.session_state.file_explanation = ""

with st.sidebar:
    st.markdown(
        """
        <div class="sidebar-card">
            <div class="mini-title">AI Codebase Explainer by Aman</div>
            <p class="mini-copy">Use this rail for quick controls while the main area stays focused on repository analysis and answers.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(f"**Status:** {st.session_state.repo_stats['status']}")
    st.markdown(f"**Files:** {st.session_state.repo_stats['files']}")
    st.markdown(f"**Model:** {st.session_state.repo_stats['model']}")
    if st.button("Clear Conversation", use_container_width=True):
        st.session_state.messages = []
        st.session_state.pending_question = ""
        st.session_state.file_explanation = ""
        st.rerun()
    st.markdown(
        """
        <div class="sidebar-card">
            <div class="mini-title">Prompting Tips</div>
            <p class="mini-copy">Ask for architecture, trace execution flow, identify key modules, or request where to add a new feature.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.title("Project Files")
    if st.session_state.file_map:
        files = sorted(st.session_state.file_map.keys())
        selected_file = st.selectbox("Select a file", files)
        if st.button("Explain File", use_container_width=True, disabled=not st.session_state.qa_chain):
            file_content = st.session_state.file_map[selected_file]
            prompt = f"""Explain the following code file in simple words.

File:
{selected_file}

Code:
{file_content}
"""
            with st.spinner("Explaining file..."):
                response = st.session_state.qa_chain.invoke({"query": prompt})
                st.session_state.file_explanation = response["result"]
    else:
        st.caption("Index a repository to browse its files.")

st.markdown(
    """
    <div class="hero-card">
        <div class="eyebrow">Repository Intelligence</div>
        <div class="hero-title">AI Codebase Explainer by Aman</div>
        <p class="hero-subtitle">
            Index a GitHub repository, turn the code into searchable context, and ask architecture or implementation
            questions through a focused chat interface.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="panel-card">
        <div class="section-title">Analyze A Repository</div>
        <div class="section-copy">Paste a public GitHub URL, build embeddings, then ask questions about structure, flow, or implementation details.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

repo_url = st.text_input(
    "Enter GitHub Repository URL",
    placeholder="https://github.com/owner/repository",
    label_visibility="collapsed",
)

analyze_clicked = st.button("Analyze Repository", use_container_width=True, disabled=not repo_url)

if analyze_clicked:
    with st.spinner("Cloning repository..."):
        repo_path = clone_repo(repo_url)
    with st.spinner("Loading code files..."):
        code, file_map = load_code_files(repo_path)
    with st.spinner("Creating embeddings..."):
        vector_store = create_vector_store(code)

    st.session_state.qa_chain = create_qa_chain(vector_store)
    st.session_state.repo_url = repo_url
    st.session_state.file_map = file_map
    st.session_state.file_explanation = ""
    st.session_state.repo_stats = {
        "files": len(code),
        "status": "Indexed",
        "model": "phi3",
    }
    st.success("Repository indexed successfully!")

st.markdown(
    f"""
    <div class="stat-chip-wrap">
        <div class="stat-chip">
            <div class="stat-label">Status</div>
            <div class="stat-value">{st.session_state.repo_stats["status"]}</div>
        </div>
        <div class="stat-chip">
            <div class="stat-label">Files Loaded</div>
            <div class="stat-value">{st.session_state.repo_stats["files"]}</div>
        </div>
        <div class="stat-chip">
            <div class="stat-label">Model</div>
            <div class="stat-value">{st.session_state.repo_stats["model"]}</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if st.session_state.repo_url:
    st.caption(f"Current repository: {st.session_state.repo_url}")
else:
    st.markdown(
        '<div class="helper-note">Start by indexing a repository before asking questions.</div>',
        unsafe_allow_html=True,
    )

if st.session_state.file_explanation:
    st.markdown(
        """
        <div class="panel-card">
            <div class="section-title">File Explanation</div>
            <div class="section-copy">Summary for the selected file from the explorer.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write(st.session_state.file_explanation)

st.markdown(
    """
    <div class="prompt-card">
        <div class="prompt-title">Starter Questions</div>
        <p class="prompt-copy">Use a quick prompt to explore the repository faster.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

prompt_col1, prompt_col2, prompt_col3 = st.columns(3)

with prompt_col1:
    if st.button("Explain architecture", use_container_width=True, disabled=not st.session_state.qa_chain):
        st.session_state.pending_question = "Explain the architecture of this project in simple terms."
        st.rerun()

with prompt_col2:
    if st.button("Key modules", use_container_width=True, disabled=not st.session_state.qa_chain):
        st.session_state.pending_question = "List the key modules in this repository and explain what each one does."
        st.rerun()

with prompt_col3:
    if st.button("Trace execution", use_container_width=True, disabled=not st.session_state.qa_chain):
        st.session_state.pending_question = "Walk me through the main execution flow of this codebase step by step."
        st.rerun()

chat_question = st.chat_input("Ask a question about the codebase")
question = st.session_state.pending_question or chat_question

if question and st.session_state.qa_chain:
    st.session_state.pending_question = ""
    ask_question(question)

with st.container():
    st.markdown('<div class="chat-shell">', unsafe_allow_html=True)
    if not st.session_state.messages:
        st.info("No conversation yet. Try asking for a summary, architecture overview, or key modules.")

    for message in st.session_state.messages:
        if message["role"] == "user":
            with st.chat_message("user"):
                st.write(message["content"])
        else:
            with st.chat_message("assistant"):
                st.write(message["content"])
    st.markdown("</div>", unsafe_allow_html=True)

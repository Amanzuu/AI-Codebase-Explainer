import textwrap
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from architecture import generate_architecture_diagram
from code_loader import load_code_files
from embeddings import create_vector_store
from rag_pipeline import create_qa_chain
from repo_analyzer import analyze_repository
from repo_loader import clone_repo
from semantic_search import semantic_search

st.set_page_config(
    page_title="AI Codebase Explainer by Aman",
    page_icon="🤖",
    layout="wide",
)


@st.cache_resource
def get_cached_qa_chain(_vector_store):
    return create_qa_chain(_vector_store)


def ask_question(question):
    st.session_state.messages.append({"role": "user", "content": question})
    with st.spinner("Thinking..."):
        response = st.session_state.qa_chain.invoke({"query": question})
        answer = response["result"]
    st.session_state.messages.append({"role": "assistant", "content": answer})


def relative_label(file_path):
    repo_path = st.session_state.repo_path
    if not repo_path:
        return Path(file_path).name
    try:
        return str(Path(file_path).resolve().relative_to(Path(repo_path).resolve()))
    except Exception:
        return Path(file_path).name


def render_analysis_card(title, icon, content):
    safe_content = (content or "No analysis available yet.").replace("\n", "<br>")
    st.markdown(
        f"""
        <div class="analysis-card reveal-card">
            <div class="analysis-icon">{icon}</div>
            <div class="analysis-title">{title}</div>
            <div class="analysis-body">{safe_content}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _pdf_escape(text):
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _normalize_pdf_paragraphs(content):
    raw_text = str(content or "No analysis available.").replace("\r\n", "\n")
    paragraphs = []
    for paragraph in raw_text.split("\n"):
        cleaned = " ".join(paragraph.split())
        paragraphs.append(cleaned if cleaned else "")
    return paragraphs


def _build_pdf_report(repo_url, analysis):
    report_heading = "AI Codebase Explainer by Aman - Report"
    body_lines = []

    for title, content in analysis.items():
        pretty_title = title.replace("_", " ").title()
        body_lines.append(pretty_title)
        body_lines.append("-" * len(pretty_title))
        for paragraph in _normalize_pdf_paragraphs(content):
            if not paragraph:
                body_lines.append("")
                continue
            wrapped_lines = textwrap.wrap(
                paragraph,
                width=72,
                replace_whitespace=True,
                drop_whitespace=True,
            )
            body_lines.extend(wrapped_lines or ["No analysis available."])
        body_lines.append("")

    page_line_limit = 48
    pages = []
    current_page = []
    for line in body_lines:
        current_page.append(line)
        if len(current_page) >= page_line_limit:
            pages.append(current_page)
            current_page = []
    if current_page:
        pages.append(current_page)

    objects = []

    def add_object(content):
        objects.append(content)
        return len(objects)

    font_object_id = add_object("<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")
    page_object_ids = []

    for page_index, page_lines in enumerate(pages):
        content_commands = []
        if page_index == 0:
            report_title = _pdf_escape(report_heading)
            repository_line = _pdf_escape(
                (f"Repository: {repo_url or 'N/A'}").encode("latin-1", "replace").decode("latin-1")
            )
            content_commands.extend(
                [
                    "BT",
                    "/F1 16 Tf",
                    "50 770 Td",
                    f"({report_title}) Tj",
                    "0 -24 Td",
                    "/F1 10 Tf",
                    f"({repository_line}) Tj",
                    "ET",
                ]
            )
            body_start_y = 720
        else:
            page_header = _pdf_escape(f"{report_heading} (cont.)")
            content_commands.extend(
                [
                    "BT",
                    "/F1 10 Tf",
                    "50 770 Td",
                    f"({page_header}) Tj",
                    "ET",
                ]
            )
            body_start_y = 740

        content_commands.extend(["BT", "/F1 10 Tf", f"50 {body_start_y} Td", "12 TL"])
        first_line = True
        for line in page_lines:
            encoded_line = _pdf_escape(line.encode("latin-1", "replace").decode("latin-1"))
            if first_line:
                content_commands.append(f"({encoded_line}) Tj")
                first_line = False
            else:
                content_commands.append(f"T* ({encoded_line}) Tj")
        content_commands.append("ET")
        stream = "\n".join(content_commands)
        content_object_id = add_object(
            f"<< /Length {len(stream.encode('latin-1'))} >>\nstream\n{stream}\nendstream"
        )
        page_object_id = add_object(
            "<< /Type /Page /Parent {parent} 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 {font_object_id} 0 R >> >> "
            f"/Contents {content_object_id} 0 R >>"
        )
        page_object_ids.append(page_object_id)

    kids = " ".join(f"{page_id} 0 R" for page_id in page_object_ids)
    pages_object_id = add_object(
        f"<< /Type /Pages /Kids [{kids}] /Count {len(page_object_ids)} >>"
    )
    catalog_object_id = add_object(f"<< /Type /Catalog /Pages {pages_object_id} 0 R >>")

    updated_objects = []
    for obj in objects:
        updated_objects.append(obj.replace("{parent}", str(pages_object_id)))

    pdf_parts = [b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"]
    offsets = []
    for index, obj in enumerate(updated_objects, start=1):
        offsets.append(sum(len(part) for part in pdf_parts))
        pdf_parts.append(f"{index} 0 obj\n{obj}\nendobj\n".encode("latin-1"))

    xref_offset = sum(len(part) for part in pdf_parts)
    pdf_parts.append(f"xref\n0 {len(updated_objects) + 1}\n".encode("latin-1"))
    pdf_parts.append(b"0000000000 65535 f \n")
    for offset in offsets:
        pdf_parts.append(f"{offset:010d} 00000 n \n".encode("latin-1"))
    pdf_parts.append(
        (
            f"trailer\n<< /Size {len(updated_objects) + 1} /Root {catalog_object_id} 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF"
        ).encode("latin-1")
    )
    return b"".join(pdf_parts)


def mark_snippet_copied(snippet_text):
    st.session_state.copied_snippet = snippet_text
    toast = getattr(st, "toast", None)
    if callable(toast):
        toast("Snippet copied!")
    else:
        st.success("Snippet copied!")


def build_architecture_diagram():
    files = list(st.session_state.file_map.keys())
    st.session_state.architecture_diagram = generate_architecture_diagram(
        files[:12],
        st.session_state.repo_path,
    )


def clear_current_repo():
    st.session_state.qa_chain = None
    st.session_state.vector_store = None
    st.session_state.repo_url = ""
    st.session_state.repo_path = ""
    st.session_state.repo_stats = {"files": 0, "status": "Idle", "model": "phi3"}
    st.session_state.file_map = {}
    st.session_state.file_explanation = ""
    st.session_state.architecture_diagram = None
    st.session_state.repo_analysis = {}
    st.session_state.pending_question = ""
    st.session_state.search_results = []


st.markdown(
    """
    <style>
        :root {
            --bg-1: #050816;
            --bg-2: #08101d;
            --bg-3: #0d1730;
            --bg-4: #122243;
            --panel-1: rgba(12, 19, 39, 0.9);
            --panel-2: rgba(9, 14, 28, 0.96);
            --line: rgba(118, 196, 255, 0.16);
            --text: #f8fafc;
            --muted: #9aaed0;
            --accent: #ff7b1f;
            --accent-2: #53d0ff;
            --accent-3: #81f7c3;
            --accent-4: #ffd36e;
            --glow: rgba(83, 208, 255, 0.26);
            --warm-glow: rgba(255, 123, 31, 0.24);
            --title-font: "Trebuchet MS", "Segoe UI Variable Display", "Arial", sans-serif;
            --body-font: "Segoe UI", "Trebuchet MS", sans-serif;
            --mono-font: "Cascadia Code", "Consolas", "Courier New", monospace;
        }
        @keyframes backgroundShift {
            0% { background-position: 0% 0%, 0% 0%, 0% 0%, 0% 0%; }
            50% { background-position: 6% 4%, -4% 2%, 3% -6%, 0% 0%; }
            100% { background-position: 0% 0%, 0% 0%, 0% 0%, 0% 0%; }
        }
        @keyframes auroraFloat {
            0% { transform: translate3d(0, 0, 0) scale(1); opacity: 0.38; }
            50% { transform: translate3d(24px, -18px, 0) scale(1.08); opacity: 0.52; }
            100% { transform: translate3d(0, 0, 0) scale(1); opacity: 0.38; }
        }
        @keyframes pulseHalo {
            0%, 100% { box-shadow: 0 0 0 rgba(83, 208, 255, 0.0), 0 0 36px rgba(255, 123, 31, 0.12); }
            50% { box-shadow: 0 0 0 rgba(83, 208, 255, 0.0), 0 0 60px rgba(83, 208, 255, 0.22); }
        }
        @keyframes orbitSpin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }
        @keyframes floatCard {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-7px); }
        }
        @keyframes riseIn {
            from {
                opacity: 0;
                transform: translateY(22px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        @keyframes shimmerSweep {
            0% { transform: translateX(-140%); }
            100% { transform: translateX(160%); }
        }
        @keyframes chipGlow {
            0%, 100% { box-shadow: inset 0 1px 0 rgba(255,255,255,0.03), 0 10px 28px rgba(0,0,0,0.18); }
            50% { box-shadow: inset 0 1px 0 rgba(255,255,255,0.03), 0 18px 34px rgba(83, 208, 255, 0.18); }
        }
        .stApp {
            background:
                radial-gradient(circle at 12% 10%, rgba(255, 123, 31, 0.22), transparent 20%),
                radial-gradient(circle at 86% 14%, rgba(83, 208, 255, 0.18), transparent 20%),
                radial-gradient(circle at 72% 78%, rgba(129, 247, 195, 0.10), transparent 22%),
                linear-gradient(135deg, var(--bg-1) 0%, var(--bg-2) 48%, var(--bg-3) 100%);
            background-size: 130% 130%, 120% 120%, 145% 145%, 100% 100%;
            animation: backgroundShift 18s ease-in-out infinite;
            font-family: var(--body-font);
        }
        .block-container {
            max-width: 1180px;
            padding-top: 1.5rem;
            padding-bottom: 2rem;
            font-size: 1.06rem;
        }
        .hero-card,
        .panel-card,
        .chat-shell,
        .architecture-shell,
        .overview-shell {
            background:
                linear-gradient(180deg, rgba(13, 20, 39, 0.96), rgba(8, 13, 26, 0.98)),
                radial-gradient(circle at top right, rgba(78, 203, 255, 0.08), transparent 28%);
            border: 1px solid var(--line);
            border-radius: 26px;
            box-shadow: 0 30px 80px rgba(0, 0, 0, 0.34);
            backdrop-filter: blur(12px);
            position: relative;
            animation: riseIn 0.8s ease both;
        }
        .hero-card {
            padding: 0;
            margin-bottom: 1.2rem;
            position: relative;
            overflow: hidden;
            box-shadow:
                0 36px 90px rgba(0, 0, 0, 0.38),
                0 0 0 1px rgba(255,255,255,0.02),
                0 0 84px rgba(83, 208, 255, 0.08);
        }
        .hero-card::after {
            content: "";
            position: absolute;
            inset: auto -12% -32% auto;
            width: 360px;
            height: 360px;
            background: radial-gradient(circle, rgba(255, 123, 31, 0.18), transparent 64%);
            pointer-events: none;
            animation: auroraFloat 12s ease-in-out infinite;
        }
        .hero-card::before {
            content: "";
            position: absolute;
            inset: -160% auto auto -20%;
            width: 46%;
            height: 300%;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.12), transparent);
            transform: rotate(18deg);
            animation: shimmerSweep 7s linear infinite;
        }
        .hero-grid {
            display: grid;
            grid-template-columns: minmax(0, 1.4fr) minmax(260px, 0.8fr);
            gap: 1.2rem;
            padding: 2rem;
            position: relative;
            z-index: 1;
        }
        .hero-content {
            position: relative;
        }
        .eyebrow {
            color: #ffd19f;
            font-size: 0.92rem;
            font-weight: 800;
            letter-spacing: 0.18em;
            text-transform: uppercase;
            margin-bottom: 0.6rem;
        }
        .hero-title {
            color: var(--text);
            font-size: 3.65rem;
            line-height: 0.9;
            font-weight: 900;
            margin: 0 0 0.8rem 0;
            max-width: 720px;
            letter-spacing: -0.04em;
            font-family: var(--title-font);
            text-shadow: 0 10px 38px rgba(0,0,0,0.22);
        }
        .hero-title .gradient-text {
            background: linear-gradient(90deg, #ffffff 0%, #b8d7ff 32%, #7fe6ff 58%, #ffd36e 100%);
            -webkit-background-clip: text;
            background-clip: text;
            color: transparent;
            background-size: 200% auto;
            animation: backgroundShift 8s ease-in-out infinite;
        }
        .hero-subtitle {
            color: #c8d6eb;
            font-size: 1.1rem;
            line-height: 1.6;
            max-width: 650px;
            margin: 0;
        }
        .hero-strip {
            display: flex;
            gap: 0.7rem;
            flex-wrap: wrap;
            margin-top: 1.05rem;
        }
        .hero-pill {
            background: linear-gradient(180deg, rgba(10, 20, 39, 0.84), rgba(7, 14, 29, 0.92));
            border: 1px solid rgba(255, 255, 255, 0.06);
            color: #dce9ff;
            border-radius: 999px;
            padding: 0.58rem 0.92rem;
            font-size: 0.88rem;
            font-weight: 700;
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
            transition: transform 180ms ease, border-color 180ms ease, box-shadow 180ms ease;
        }
        .hero-pill:hover {
            transform: translateY(-2px);
            border-color: rgba(126, 211, 255, 0.28);
            box-shadow: 0 14px 28px rgba(83, 208, 255, 0.12);
        }
        .hero-stage {
            min-height: 100%;
            border-left: 1px solid rgba(255,255,255,0.06);
            padding-left: 1.1rem;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .hero-orbit {
            width: 260px;
            height: 260px;
            border-radius: 50%;
            position: relative;
            background:
                radial-gradient(circle at center, rgba(83, 208, 255, 0.2), rgba(83, 208, 255, 0.04) 34%, transparent 35%),
                radial-gradient(circle at center, rgba(255, 123, 31, 0.12), transparent 60%);
            border: 1px solid rgba(83, 208, 255, 0.14);
            box-shadow:
                inset 0 0 60px rgba(83, 208, 255, 0.08),
                0 0 80px rgba(255, 123, 31, 0.08);
            animation: pulseHalo 5s ease-in-out infinite, floatCard 6s ease-in-out infinite;
        }
        .hero-orbit::before,
        .hero-orbit::after {
            content: "";
            position: absolute;
            border-radius: 50%;
            inset: 18px;
            border: 1px dashed rgba(255,255,255,0.10);
            animation: orbitSpin 18s linear infinite;
        }
        .hero-orbit::after {
            inset: 46px;
            border-color: rgba(83, 208, 255, 0.18);
            animation-duration: 11s;
            animation-direction: reverse;
        }
        .hero-core {
            position: absolute;
            inset: 50% auto auto 50%;
            transform: translate(-50%, -50%);
            width: 108px;
            height: 108px;
            border-radius: 24px;
            background: linear-gradient(135deg, rgba(255, 123, 31, 0.95), rgba(83, 208, 255, 0.95));
            display: grid;
            place-items: center;
            color: #06101e;
            font-size: 2rem;
            font-weight: 900;
            box-shadow: 0 16px 40px rgba(0,0,0,0.28);
            animation: pulseHalo 4s ease-in-out infinite;
        }
        .hero-node {
            position: absolute;
            width: 16px;
            height: 16px;
            border-radius: 50%;
            background: var(--accent-4);
            box-shadow: 0 0 22px rgba(255, 211, 110, 0.72);
            animation: floatCard 4.5s ease-in-out infinite;
        }
        .hero-node.one { top: 18px; left: 124px; }
        .hero-node.two { right: 28px; top: 82px; background: var(--accent-2); box-shadow: 0 0 22px rgba(83, 208, 255, 0.72); animation-delay: -1.4s; }
        .hero-node.three { bottom: 24px; left: 56px; background: var(--accent-3); box-shadow: 0 0 22px rgba(129, 247, 195, 0.64); animation-delay: -2.3s; }
        .hero-caption {
            margin-top: 1rem;
            color: #9fbbdf;
            font-size: 0.92rem;
            text-align: center;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }
        .panel-card {
            padding: 1.15rem 1.2rem 1rem 1.2rem;
            margin-bottom: 1rem;
            overflow: hidden;
        }
        .panel-card::after,
        .prompt-card::after,
        .overview-shell::after,
        .architecture-shell::after,
        .chat-shell::after {
            content: "";
            position: absolute;
            inset: auto auto 0 0;
            width: 100%;
            height: 1px;
            background: linear-gradient(90deg, rgba(83,208,255,0), rgba(83,208,255,0.7), rgba(255,123,31,0.72), rgba(83,208,255,0));
        }
        .section-title {
            color: var(--text);
            font-size: 1.32rem;
            font-weight: 700;
            margin-bottom: 0.25rem;
            font-family: var(--title-font);
            letter-spacing: -0.02em;
        }
        .section-copy,
        .architecture-copy {
            color: var(--muted);
            font-size: 1.04rem;
            margin-bottom: 0.9rem;
        }
        .stat-chip-wrap {
            display: flex;
            gap: 0.75rem;
            flex-wrap: wrap;
            margin: 0.65rem 0 1rem 0;
        }
        .stat-chip {
            min-width: 150px;
            background: linear-gradient(180deg, rgba(11, 20, 40, 0.96), rgba(8, 14, 27, 0.96));
            border: 1px solid rgba(78, 203, 255, 0.12);
            border-radius: 20px;
            padding: 0.95rem 1rem;
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.03);
            position: relative;
            overflow: hidden;
            animation: chipGlow 5s ease-in-out infinite;
            transition: transform 180ms ease, border-color 180ms ease;
        }
        .stat-chip:hover {
            transform: translateY(-4px);
            border-color: rgba(255, 196, 120, 0.28);
        }
        .stat-chip::before {
            content: "";
            position: absolute;
            inset: 0;
            background: linear-gradient(120deg, transparent, rgba(255,255,255,0.07), transparent);
            transform: translateX(-140%);
            animation: shimmerSweep 6.4s linear infinite;
        }
        .stat-label {
            color: #81a2cb;
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.14em;
        }
        .stat-value {
            color: #ffffff;
            font-size: 1.45rem;
            font-weight: 800;
            margin-top: 0.22rem;
        }
        .prompt-card,
        .sidebar-card {
            background: linear-gradient(180deg, rgba(13, 21, 42, 0.94), rgba(9, 15, 30, 0.96));
            border: 1px solid rgba(126, 211, 255, 0.12);
            border-radius: 22px;
            padding: 1rem;
            position: relative;
            overflow: hidden;
            animation: riseIn 0.8s ease both;
        }
        .prompt-card {
            margin-top: 1rem;
            margin-bottom: 0.9rem;
            position: relative;
            overflow: hidden;
        }
        .prompt-card::before {
            content: "";
            position: absolute;
            inset: 0;
            background: linear-gradient(90deg, rgba(78, 203, 255, 0.08), transparent 40%, rgba(255, 138, 31, 0.08));
            pointer-events: none;
        }
        .sidebar-card::before {
            content: "";
            position: absolute;
            inset: auto -20% -60% auto;
            width: 180px;
            height: 180px;
            border-radius: 50%;
            background: radial-gradient(circle, rgba(83, 208, 255, 0.18), transparent 70%);
            animation: auroraFloat 9s ease-in-out infinite;
        }
        .prompt-title,
        .mini-title {
            color: var(--text);
            font-size: 1.14rem;
            font-weight: 800;
            margin-bottom: 0.2rem;
            font-family: var(--title-font);
        }
        .prompt-copy,
        .mini-copy {
            color: var(--muted);
            font-size: 1rem;
            line-height: 1.55;
            margin: 0;
        }
        .chat-shell {
            padding: 1rem 1rem 0.35rem 1rem;
            margin-top: 1rem;
        }
        .architecture-shell {
            padding: 1rem 1rem 1rem 1rem;
            margin-top: 1rem;
        }
        .overview-shell {
            padding: 1rem 1rem 0.4rem 1rem;
            margin-top: 0.8rem;
            margin-bottom: 0.9rem;
            position: relative;
            overflow: hidden;
        }
        .overview-shell::before {
            content: "";
            position: absolute;
            inset: auto -12% -35% auto;
            width: 280px;
            height: 280px;
            background: radial-gradient(circle, rgba(247, 161, 43, 0.24), transparent 68%);
            pointer-events: none;
        }
        .analysis-card {
            background:
                linear-gradient(180deg, rgba(17, 30, 55, 0.98), rgba(11, 20, 37, 0.98)),
                radial-gradient(circle at top right, rgba(78, 203, 255, 0.08), transparent 26%);
            border: 1px solid rgba(94, 163, 255, 0.16);
            border-radius: 22px;
            padding: 1.05rem;
            min-height: 220px;
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
            position: relative;
            overflow: hidden;
            transition: transform 220ms ease, border-color 220ms ease, box-shadow 220ms ease;
        }
        .analysis-card:hover {
            transform: translateY(-6px);
            border-color: rgba(255, 196, 120, 0.3);
            box-shadow:
                inset 0 1px 0 rgba(255,255,255,0.04),
                0 20px 40px rgba(0,0,0,0.22),
                0 0 34px rgba(83,208,255,0.10);
        }
        .analysis-card::before {
            content: "";
            position: absolute;
            inset: 0;
            background: linear-gradient(120deg, transparent, rgba(255,255,255,0.06), transparent);
            transform: translateX(-150%);
            animation: shimmerSweep 7.2s linear infinite;
        }
        .analysis-icon {
            font-size: 1.45rem;
            margin-bottom: 0.45rem;
        }
        .analysis-title {
            color: #f9fbff;
            font-size: 1.1rem;
            font-weight: 800;
            margin-bottom: 0.55rem;
        }
        .analysis-body {
            color: #d6e7ff;
            font-size: 0.98rem;
            line-height: 1.7;
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
            border-radius: 16px;
            background: rgba(11, 19, 38, 0.92);
            font-size: 1.02rem;
            border: 1px solid rgba(78, 203, 255, 0.12);
            box-shadow: inset 0 0 0 1px rgba(255,255,255,0.02), 0 10px 30px rgba(0,0,0,0.12);
            transition: border-color 180ms ease, box-shadow 180ms ease, transform 180ms ease;
        }
        .stTextInput input:focus {
            border-color: rgba(83, 208, 255, 0.48);
            box-shadow: 0 0 0 1px rgba(83,208,255,0.24), 0 0 28px rgba(83,208,255,0.12);
            transform: translateY(-1px);
        }
        .stButton button {
            border-radius: 16px;
            border: 1px solid rgba(255, 196, 120, 0.18);
            background: linear-gradient(135deg, #ff8a1f 0%, #ffb347 100%);
            color: #111827;
            font-weight: 800;
            font-size: 1.04rem;
            box-shadow: 0 14px 28px rgba(255, 138, 31, 0.18);
            padding: 0.78rem 1rem;
            transition: transform 180ms ease, box-shadow 180ms ease, border-color 180ms ease;
        }
        .stButton button:hover {
            border-color: rgba(255, 218, 163, 0.34);
            background: linear-gradient(135deg, #ff9d39 0%, #ffc467 100%);
            color: #111827;
            transform: translateY(-2px) scale(1.01);
            box-shadow: 0 18px 34px rgba(255, 138, 31, 0.24);
        }
        .stButton button:disabled {
            background: linear-gradient(135deg, #594734 0%, #6f573d 100%);
            color: rgba(255, 245, 235, 0.55);
            border-color: rgba(255, 198, 130, 0.08);
            box-shadow: none;
        }
        .stDownloadButton button {
            background: linear-gradient(135deg, #53d0ff 0%, #81f7c3 100%);
            border-color: rgba(129, 247, 195, 0.28);
            box-shadow: 0 16px 32px rgba(83, 208, 255, 0.18);
        }
        .stDownloadButton button:hover {
            background: linear-gradient(135deg, #7adfff 0%, #9bffd3 100%);
            box-shadow: 0 20px 36px rgba(83, 208, 255, 0.24);
        }
        [data-testid="stSidebar"] {
            background:
                linear-gradient(180deg, rgba(7, 14, 29, 0.97), rgba(5, 10, 20, 0.98)),
                radial-gradient(circle at top left, rgba(78, 203, 255, 0.08), transparent 25%);
            border-right: 1px solid rgba(255, 255, 255, 0.05);
        }
        [data-testid="stSidebar"] .stButton button {
            width: 100%;
        }
        .helper-note {
            color: var(--muted);
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
        [data-testid="stChatMessage"] {
            animation: riseIn 0.45s ease both;
        }
        [data-testid="stChatInput"] textarea {
            font-size: 1.02rem;
            border-radius: 18px;
        }
        [data-testid="stGraphVizChart"] {
            background: linear-gradient(180deg, rgba(8, 12, 23, 0.98), rgba(6, 10, 19, 0.98));
            border: 1px solid rgba(148, 163, 184, 0.1);
            border-radius: 24px;
            padding: 0.85rem;
            box-shadow: 0 22px 48px rgba(0,0,0,0.2);
        }
        div[data-testid="stSuccess"] {
            background: rgba(10, 48, 36, 0.72);
            border: 1px solid rgba(124, 255, 183, 0.24);
            border-radius: 18px;
        }
        div[data-testid="stInfo"] {
            background: rgba(12, 35, 63, 0.72);
            border: 1px solid rgba(78, 203, 255, 0.2);
            border-radius: 18px;
        }
        [data-testid="stCodeBlock"] {
            border-radius: 18px;
            border: 1px solid rgba(83, 208, 255, 0.14);
            box-shadow: 0 16px 34px rgba(0,0,0,0.18);
            overflow: hidden;
        }
        .search-results-shell {
            position: relative;
            padding: 1rem 1rem 0.6rem 1rem;
            margin-top: 1rem;
            border-radius: 26px;
            background:
                linear-gradient(180deg, rgba(12, 21, 42, 0.95), rgba(8, 14, 26, 0.98)),
                radial-gradient(circle at top right, rgba(255,123,31,0.10), transparent 24%);
            border: 1px solid rgba(118, 196, 255, 0.14);
            box-shadow: 0 28px 70px rgba(0,0,0,0.28);
            overflow: hidden;
            animation: riseIn 0.8s ease both;
        }
        .search-results-shell::before {
            content: "";
            position: absolute;
            inset: 0;
            background: linear-gradient(120deg, transparent, rgba(255,255,255,0.05), transparent);
            transform: translateX(-150%);
            animation: shimmerSweep 8s linear infinite;
        }
        .search-result-meta {
            display: inline-flex;
            align-items: center;
            gap: 0.6rem;
            margin-top: 0.2rem;
            margin-bottom: 0.55rem;
            padding: 0.55rem 0.8rem;
            border-radius: 999px;
            background: rgba(8, 17, 33, 0.78);
            border: 1px solid rgba(83, 208, 255, 0.14);
            color: #dff6ff;
            font-family: var(--mono-font);
            font-size: 0.92rem;
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
        }
        .search-result-index {
            display: inline-grid;
            place-items: center;
            width: 26px;
            height: 26px;
            border-radius: 50%;
            background: linear-gradient(135deg, rgba(255,123,31,0.95), rgba(83,208,255,0.95));
            color: #091321;
            font-weight: 900;
            font-size: 0.82rem;
        }
        .search-result-divider {
            height: 1px;
            margin: 0.8rem 0 1rem 0;
            background: linear-gradient(90deg, rgba(83,208,255,0), rgba(83,208,255,0.45), rgba(255,123,31,0.55), rgba(83,208,255,0));
        }
        .reveal-card {
            animation: riseIn 0.85s ease both;
        }
        @media (max-width: 980px) {
            .hero-grid {
                grid-template-columns: 1fr;
            }
            .hero-stage {
                border-left: 0;
                border-top: 1px solid rgba(255,255,255,0.06);
                padding-left: 0;
                padding-top: 1rem;
            }
            .hero-title {
                font-size: 3rem;
            }
            .search-result-meta {
                display: flex;
                width: 100%;
                border-radius: 18px;
            }
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
if "repo_path" not in st.session_state:
    st.session_state.repo_path = ""
if "repo_stats" not in st.session_state:
    st.session_state.repo_stats = {"files": 0, "status": "Idle", "model": "phi3"}
if "pending_question" not in st.session_state:
    st.session_state.pending_question = ""
if "file_map" not in st.session_state:
    st.session_state.file_map = {}
if "file_explanation" not in st.session_state:
    st.session_state.file_explanation = ""
if "architecture_diagram" not in st.session_state:
    st.session_state.architecture_diagram = None
if "repo_analysis" not in st.session_state:
    st.session_state.repo_analysis = {}
if not isinstance(st.session_state.repo_analysis, dict):
    st.session_state.repo_analysis = {"project_summary": str(st.session_state.repo_analysis)}
if "vector_store" not in st.session_state:
    st.session_state.vector_store = None
if "search_results" not in st.session_state:
    st.session_state.search_results = []
if "copied_snippet" not in st.session_state:
    st.session_state.copied_snippet = ""
if "did_initial_scroll_reset" not in st.session_state:
    st.session_state.did_initial_scroll_reset = False

if not st.session_state.did_initial_scroll_reset:
    components.html(
        """
        <script>
        const scrollTop = () => {
            window.parent.scrollTo(0, 0);
        };
        scrollTop();
        setTimeout(scrollTop, 80);
        setTimeout(scrollTop, 240);
        </script>
        """,
        height=0,
    )
    st.session_state.did_initial_scroll_reset = True

with st.sidebar:
    st.markdown(
        """
        <div class="sidebar-card">
            <div class="mini-title">AI Codebase Explainer by Aman</div>
            <p class="mini-copy">Use this rail for quick controls while the main area stays focused on repository analysis, architecture, and answers.</p>
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
        st.session_state.repo_analysis = {}
        st.rerun()
    if st.button("Clear Current Repo", use_container_width=True, disabled=not st.session_state.repo_path):
        clear_current_repo()
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
    st.title("Architecture")
    if st.session_state.file_map:
        if st.button("Generate Architecture Diagram", use_container_width=True):
            build_architecture_diagram()
    else:
        st.caption("Index a repository to generate its architecture view.")

    st.title("Project Files")
    if st.session_state.file_map:
        files = sorted(st.session_state.file_map.keys())
        selected_file = st.selectbox(
            "Select a file",
            files,
            format_func=relative_label,
        )
        if st.button("Explain File", use_container_width=True, disabled=not st.session_state.qa_chain):
            file_content = st.session_state.file_map[selected_file]
            prompt = f"""Explain the following code file in simple words.

File:
{relative_label(selected_file)}

Code:
{file_content}
"""
            with st.spinner("Explaining file..."):
                response = st.session_state.qa_chain.invoke({"query": prompt})
                st.session_state.file_explanation = response["result"]
    else:
        st.caption("Index a repository to browse its files.")

    st.title("Semantic Code Search")
    search_query = st.text_input(
        "Search codebase",
        key="semantic_search_input",
        disabled=st.session_state.vector_store is None,
    )
    if st.button("Search", use_container_width=True, disabled=st.session_state.vector_store is None or not search_query):
        st.session_state.search_results = semantic_search(
            st.session_state.vector_store,
            search_query,
            k=5
        )

st.markdown(
    """
    <div class="hero-card reveal-card">
        <div class="hero-grid">
            <div class="hero-content">
                <div class="eyebrow">Repository Intelligence</div>
                <div class="hero-title">AI Codebase <span class="gradient-text">Explainer</span> by Aman</div>
                <p class="hero-subtitle">
                    Turn any GitHub repository into an interactive command center with semantic search, instant architectural signals,
                    file-level explanations, and a cleaner way to understand unfamiliar codebases.
                </p>
                <div class="hero-strip">
                    <div class="hero-pill">Semantic Search</div>
                    <div class="hero-pill">Architecture Mapping</div>
                    <div class="hero-pill">Repo Overview Cards</div>
                    <div class="hero-pill">File-Level Explanations</div>
                </div>
            </div>
            <div class="hero-stage">
                <div>
                    <div class="hero-orbit">
                        <div class="hero-core">AI</div>
                        <div class="hero-node one"></div>
                        <div class="hero-node two"></div>
                        <div class="hero-node three"></div>
                    </div>
                    <div class="hero-caption">Code Graph Active</div>
                </div>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="panel-card reveal-card">
        <div class="section-title">Analyze A Repository</div>
        <div class="section-copy">Paste a public GitHub URL, build embeddings, then ask questions about structure, flow, implementation details, and file-level behavior.</div>
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
    if st.session_state.repo_path == repo_path and st.session_state.vector_store is not None:
        vector_store = st.session_state.vector_store
    else:
        with st.spinner("Creating embeddings..."):
            vector_store = create_vector_store(file_map, repo_path)

    st.session_state.qa_chain = get_cached_qa_chain(vector_store)
    st.session_state.vector_store = vector_store
    st.session_state.repo_url = repo_url
    st.session_state.repo_path = repo_path
    st.session_state.file_map = file_map
    st.session_state.file_explanation = ""
    st.session_state.architecture_diagram = None
    st.session_state.repo_stats = {
        "files": len(code),
        "status": "Indexed",
        "model": "phi3",
    }
    st.session_state.repo_analysis = analyze_repository(code, file_map=file_map)
    st.session_state.search_results = []
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

if st.session_state.repo_analysis:
    report_pdf = _build_pdf_report(
        st.session_state.repo_url,
        st.session_state.repo_analysis,
    )

    st.markdown(
        """
        <div class="overview-shell">
            <div class="section-title">Repository Overview</div>
            <div class="section-copy">Automatic analysis generated immediately after indexing. This gives you the project summary, tech stack, key modules, and architecture view up front.</div>
        """,
        unsafe_allow_html=True,
    )
    overview_col1, overview_col2 = st.columns(2)
    with overview_col1:
        render_analysis_card("Project Summary", "📄", st.session_state.repo_analysis.get("project_summary"))
        render_analysis_card("Key Modules", "🧩", st.session_state.repo_analysis.get("key_modules"))
    with overview_col2:
        render_analysis_card("Detected Tech Stack", "🧰", st.session_state.repo_analysis.get("tech_stack"))
        render_analysis_card("Architecture Overview", "🏗", st.session_state.repo_analysis.get("architecture_overview"))
    st.download_button(
        label="Download Analysis Report",
        data=report_pdf,
        file_name="repo_analysis.pdf",
        mime="application/pdf",
    )
    st.markdown("</div>", unsafe_allow_html=True)

if st.session_state.architecture_diagram is not None:
    st.markdown(
        """
        <div class="architecture-shell">
            <div class="section-title">Project Architecture</div>
            <div class="architecture-copy">A cleaner repository view grouped by folders and connected from the likely entry point.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.graphviz_chart(st.session_state.architecture_diagram, use_container_width=True)

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

if st.session_state.search_results:
    st.markdown(
        """
        <div class="search-results-shell">
            <div class="section-title">Search Results</div>
            <div class="section-copy">Top semantic matches across the indexed repository with line-aware snippets.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    for index, result in enumerate(st.session_state.search_results):
        st.markdown(
            f"""
            <div class="search-result-meta">
                <span class="search-result-index">{index + 1}</span>
                <span>{result['source']}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.code(
            result["content"][:500],
            language="python",
            line_numbers=True,
        )
        st.button(
            "Copy snippet",
            key=f"copy_{index}",
            on_click=mark_snippet_copied,
            args=(result["content"],),
        )
        if index < len(st.session_state.search_results) - 1:
            st.markdown('<div class="search-result-divider"></div>', unsafe_allow_html=True)

st.markdown(
    """
    <div class="prompt-card reveal-card">
        <div class="prompt-title">Starter Questions</div>
        <p class="prompt-copy">Use a quick prompt to explore the repository faster.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

action_col1, action_col2 = st.columns(2)

with action_col1:
    if st.button("Generate Architecture Diagram", use_container_width=True, disabled=not st.session_state.file_map):
        build_architecture_diagram()

with action_col2:
    if st.button("Explain Selected File", use_container_width=True, disabled=not st.session_state.file_map or not st.session_state.qa_chain):
        files = sorted(st.session_state.file_map.keys())
        selected_file = files[0]
        file_content = st.session_state.file_map[selected_file]
        prompt = f"""Explain the following code file in simple words.

File:
{relative_label(selected_file)}

Code:
{file_content}
"""
        with st.spinner("Explaining file..."):
            response = st.session_state.qa_chain.invoke({"query": prompt})
            st.session_state.file_explanation = response["result"]

repo_action_col1, repo_action_col2 = st.columns(2)

with repo_action_col1:
    if st.button("Clear Current Repo", use_container_width=True, disabled=not st.session_state.repo_path):
        clear_current_repo()
        st.rerun()

with repo_action_col2:
    if st.button("Load Another Repo", use_container_width=True):
        clear_current_repo()
        st.rerun()

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

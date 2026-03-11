from pathlib import Path


TECH_SIGNATURES = {
    "Streamlit": ["import streamlit", "streamlit."],
    "LangChain": ["langchain", "retrievalqa", "langchain_ollama"],
    "Ollama": ["ollama", "ollamallm"],
    "FAISS": ["faiss"],
    "Sentence Transformers": ["sentence-transformers", "huggingfaceembeddings"],
    "FastAPI": ["fastapi"],
    "Flask": ["flask"],
    "Django": ["django"],
    "React": ["react", "next.js", "next/"],
    "TypeScript": [".ts", ".tsx"],
    "JavaScript": [".js", ".jsx"],
    "Graphviz": ["graphviz"],
    "GitPython": ["from git import", "gitpython"],
}


def _normalize_text(value):
    return value.lower() if value else ""


def _detect_stack(file_map):
    combined = "\n".join(file_map.values()).lower()
    detected = []

    extensions = {Path(path).suffix.lower() for path in file_map}
    if ".py" in extensions:
        detected.append("Python")
    if ".ts" in extensions or ".tsx" in extensions:
        detected.append("TypeScript")
    if ".js" in extensions or ".jsx" in extensions:
        detected.append("JavaScript")

    for tech, signatures in TECH_SIGNATURES.items():
        if any(signature in combined for signature in signatures):
            detected.append(tech)

    seen = []
    for tech in detected:
        if tech not in seen:
            seen.append(tech)
    return seen


def _summarize_project(file_map, tech_stack):
    file_names = {Path(path).name.lower() for path in file_map}

    if "streamlit" in [tech.lower() for tech in tech_stack] and "langchain" in [tech.lower() for tech in tech_stack]:
        return (
            "This repository appears to be an interactive AI application that lets a user load a code repository, "
            "index the source files, and ask natural-language questions about the project."
        )

    if "fastapi" in [tech.lower() for tech in tech_stack]:
        return "This repository appears to be an API or backend service built around FastAPI."

    if "app.py" in file_names or "main.py" in file_names:
        return "This repository appears to be an application project with a clear entry file and modular source structure."

    return "This repository appears to be a software project composed of multiple source files and supporting modules."


def _key_modules(file_map):
    preferred = [
        "app.py",
        "main.py",
        "server.py",
        "api.py",
        "repo_loader.py",
        "code_loader.py",
        "embeddings.py",
        "rag_pipeline.py",
        "architecture.py",
        "repo_analyzer.py",
    ]

    path_lookup = {Path(path).name.lower(): path for path in file_map}
    modules = []

    for name in preferred:
        if name in path_lookup:
            modules.append(path_lookup[name])

    for path in sorted(file_map):
        if path not in modules:
            modules.append(path)
        if len(modules) >= 6:
            break

    lines = []
    for path in modules[:6]:
        rel = Path(path).name
        label = rel
        if rel == "app.py":
            desc = "main user-facing entry point and application flow"
        elif rel == "repo_loader.py":
            desc = "repository cloning and source acquisition"
        elif rel == "code_loader.py":
            desc = "source file discovery and loading"
        elif rel == "embeddings.py":
            desc = "embedding generation and vector store handling"
        elif rel == "rag_pipeline.py":
            desc = "retrieval and LLM question-answer pipeline"
        elif rel == "architecture.py":
            desc = "architecture diagram generation"
        elif rel == "repo_analyzer.py":
            desc = "repository overview generation"
        else:
            desc = "supporting project module"
        lines.append(f"- {label}: {desc}")

    return "\n".join(lines)


def _architecture_overview(file_map, tech_stack):
    layers = []

    lower_stack = [item.lower() for item in tech_stack]
    file_names = {Path(path).name.lower() for path in file_map}

    if "streamlit" in lower_stack:
        layers.append("Presentation layer: a Streamlit interface handles repository input, overview cards, architecture view, and chat interactions.")
    if "repo_loader.py" in file_names or "code_loader.py" in file_names:
        layers.append("Ingestion layer: repository cloning and code loading modules collect the source files that will be indexed.")
    if "embeddings.py" in file_names or "faiss" in lower_stack:
        layers.append("Retrieval layer: embeddings are created for code chunks and stored in a FAISS vector database for semantic search.")
    if "rag_pipeline.py" in file_names or "langchain" in lower_stack or "ollama" in lower_stack:
        layers.append("AI layer: a retrieval-augmented generation pipeline uses LangChain and Ollama to answer questions about the indexed codebase.")
    if "architecture.py" in file_names:
        layers.append("Visualization layer: a Graphviz-based module generates a high-level project architecture diagram from the discovered files.")

    if not layers:
        layers.append("The project appears to use a modular architecture with separate files for entry logic, processing, and supporting utilities.")

    return "\n".join(f"- {line}" for line in layers)


def analyze_repository(code_files, qa_chain=None, file_map=None):
    file_map = file_map or {}
    tech_stack = _detect_stack(file_map) if file_map else ["Python"]

    return {
        "project_summary": _summarize_project(file_map, tech_stack),
        "tech_stack": "\n".join(f"- {item}" for item in tech_stack),
        "key_modules": _key_modules(file_map) if file_map else "- No files available for module analysis.",
        "architecture_overview": _architecture_overview(file_map, tech_stack),
        "raw": "",
    }

import os

def load_code_files(repo_path):

    texts = []

    allowed_extensions = (
        ".py", ".js", ".ts", ".java", ".go",
        ".cpp", ".html", ".css", ".json", ".yaml"
    )

    for root, dirs, files in os.walk(repo_path):

        for file in files:

            if file.endswith(allowed_extensions):

                path = os.path.join(root, file)

                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        texts.append(f.read())
                except:
                    pass

    return texts
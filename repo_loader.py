from pathlib import Path

from git import Repo


def clone_repo(repo_url, base_dir="repos"):
    base_path = Path(base_dir)
    base_path.mkdir(parents=True, exist_ok=True)

    repo_name = repo_url.rstrip("/").split("/")[-1]
    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]

    repo_path = base_path / repo_name
    if repo_path.exists():
        return str(repo_path)

    Repo.clone_from(repo_url, repo_path)
    return str(repo_path)

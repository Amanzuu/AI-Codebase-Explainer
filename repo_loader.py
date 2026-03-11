from git import Repo
import os

def clone_repo(repo_url, folder="repo"):

    if os.path.exists(folder):
        return folder

    print("Cloning repository...")

    Repo.clone_from(repo_url, folder)

    return folder
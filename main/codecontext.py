import re
import shutil
import zipfile
from pathlib import Path
import requests
from utils.functions import log
import utils.config as config


def copy_codebase_folder(src: Path) -> bool:
    """Copy a codebase folder to CODEBASE_DIR (preserve structure)."""
    try:
        if config.CODEBASE_DIR.exists():
            shutil.rmtree(config.CODEBASE_DIR)
        # Use copytree to preserve structure
        shutil.copytree(src, config.CODEBASE_DIR)
        print(f"Copied codebase to {config.CODEBASE_DIR}")
        return True
    except Exception as e:
        print(f"Failed to copy codebase: {e}")
        return False


def is_github_url(s: str) -> bool:
    return "github.com" in s


def parse_github_url(url: str) -> tuple[str, str, str, str | None]:
    """Parse a GitHub URL and return (owner, repo, branch, path).
    branch and path may be None.
    Supports URLs like:
      https://github.com/owner/repo
      https://github.com/owner/repo/tree/branch/path/to/dir
    """
    # Normalize
    u = url.rstrip("/")
    m = re.search(
        r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/]+)(?:/tree/(?P<branch>[^/]+)(?P<path>/.*)?)?",
        u,
    )
    if not m:
        return ("", "", "", None)
    owner = m.group("owner")
    repo = m.group("repo").removesuffix(".git")
    branch = m.group("branch") or "main"
    path = m.group("path")
    if path:
        path = path.lstrip("/")
    return owner, repo, branch, path


def download_github_archive(owner: str, repo: str, branch: str) -> Path | None:
    """Download a GitHub archive zip for given owner/repo/branch into TEMP_EXTRACT_DIR and return path to zip or None."""
    if not owner or not repo:
        print("Error: Invalid owner or repository name")
        return None

    config.TEMP_EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = config.TEMP_EXTRACT_DIR / f"{owner}-{repo}-{branch}.zip"
    urls_to_try = [f"https://github.com/{owner}/{repo}/archive/refs/heads/{branch}.zip"]
    # try common default branch names if first fails
    if branch in (None, "main"):
        urls_to_try.append(
            f"https://github.com/{owner}/{repo}/archive/refs/heads/master.zip"
        )
    for url in urls_to_try:
        try:
            print(f"Downloading {url}...")
            r = requests.get(url, stream=True, timeout=60)
            if r.status_code == 200:
                with open(zip_path, "wb") as fh:
                    for chunk in r.iter_content(chunk_size=8192):
                        fh.write(chunk)
                return zip_path
            else:
                print(f"Download failed: {r.status_code} {url}")
        except requests.exceptions.Timeout:
            print(f"Download timeout: {url}")
        except requests.exceptions.RequestException as e:
            print(f"Download error: {e}")
        except Exception as e:
            print(f"Unexpected error during download: {e}")
    return None


def fetch_github_repo(repo_url: str, target_folder: str | None = None) -> bool:
    """Fetch a GitHub repo archive and copy files into CODEBASE_DIR or extract a subfolder.
    Returns True on success.
    """
    owner, repo, branch, path = parse_github_url(repo_url)
    # if parse failed, try to accept shorthand owner/repo
    if not owner or not repo:
        parts = repo_url.split("/")
        if len(parts) == 2:
            owner, repo = parts[0], parts[1]
            branch = "main"
        else:
            print("Unsupported GitHub URL format")
            return False

    zip_path = download_github_archive(owner, repo, branch)
    if not zip_path or not zip_path.exists():
        print("Failed to download repository archive")
        return False

    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            # Extract to temp
            if config.TEMP_EXTRACT_DIR.exists():
                shutil.rmtree(config.TEMP_EXTRACT_DIR)
            config.TEMP_EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
            z.extractall(config.TEMP_EXTRACT_DIR)

            # Archive root folder name is repo-branch
            root_candidates = list(config.TEMP_EXTRACT_DIR.iterdir())
            if not root_candidates:
                print("Archive empty")
                return False
            root = root_candidates[0]

            # If target_folder (from --target or parsed path) provided, navigate into it
            sub = target_folder or path
            if sub:
                sub_path = root / sub
                if not sub_path.exists():
                    print(f"Subfolder '{sub}' not found in archive")
                    return False
                # copy the subfolder as codebase
                if config.CODEBASE_DIR.exists():
                    shutil.rmtree(config.CODEBASE_DIR)
                shutil.copytree(sub_path, config.CODEBASE_DIR)
            else:
                # copy entire repo tree
                if config.CODEBASE_DIR.exists():
                    shutil.rmtree(config.CODEBASE_DIR)
                shutil.copytree(root, config.CODEBASE_DIR)

        print(f"Fetched GitHub repo to {config.CODEBASE_DIR}")
        return True
    except Exception as e:
        print(f"Failed to extract repo archive: {e}")
        return False


def codebase_ls(rel_path: str = "") -> list[str]:
    base_path = config.CODEBASE_DIR / rel_path
    if not base_path.exists() or not base_path.is_dir():
        print(f"Path '{rel_path}' not found in codebase.")
        return []
    return sorted(
        [
            str(p.relative_to(config.CODEBASE_DIR))
            for p in base_path.rglob("*")
            if p.is_file()
        ]
    )

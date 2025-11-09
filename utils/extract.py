import zipfile
import time
from pathlib import Path
import shutil
from utils.functions import log
import utils.config as config


def extract_zip(zip_path: Path, target_folder: str = None) -> bool:
    """Extract zip file to HTML_DIR."""
    msg = f"Extracting {zip_path.name}..."
    if target_folder:
        msg += f" (folder: {target_folder})"
    log(msg, echo=True)

    try:
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            if target_folder:
                target_folder = target_folder.strip("/")
                members = [
                    m
                    for m in zip_ref.namelist()
                    if m.startswith(target_folder + "/") or m.startswith(target_folder)
                ]

                if not members:
                    log(f"No files found in '{target_folder}'", echo=True)
                    return False

                config.TEMP_EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
                zip_ref.extractall(config.TEMP_EXTRACT_DIR, members)

                source_path = config.TEMP_EXTRACT_DIR / target_folder
                if not source_path.exists():
                    log(f"Folder '{target_folder}' not found", echo=True)
                    return False

                config.HTML_DIR.mkdir(parents=True, exist_ok=True)
                html_files = list(source_path.rglob("*.html"))

                if not html_files:
                    log(f"No HTML files in '{target_folder}'", echo=True)
                    return False

                for file in html_files:
                    shutil.copy2(file, config.HTML_DIR / file.name)

                shutil.rmtree(config.TEMP_EXTRACT_DIR)
                log(f"Extracted {len(html_files)} HTML files", echo=True)
            else:
                zip_ref.extractall(config.HTML_DIR)
                log(f"Extracted to {config.HTML_DIR}", echo=True)

        return True
    except Exception as e:
        log(f"Failed to extract: {e}", echo=True)
        return False


def copy_html_folder(src: Path) -> bool:
    """Copy HTML files from source folder to HTML_DIR."""
    log(f"Copying files from {src}...", echo=True)

    try:
        config.HTML_DIR.mkdir(parents=True, exist_ok=True)
        html_files = list(src.rglob("*.html"))

        if not html_files:
            log(f"No HTML files found in {src}", echo=True)
            return False

        for file in html_files:
            shutil.copy2(file, config.HTML_DIR / file.name)

        log(f"Copied {len(html_files)} HTML files", echo=True)
        return True
    except Exception as e:
        log(f"Failed to copy: {e}", echo=True)
        return False


def add_context(input_path: str, target_folder: str = None):
    """Add context from zip, folder, or GitHub URL."""
    import utils.codecontext as gc

    # Handle GitHub URLs
    if gc.is_github_url(input_path):
        log(f"Fetching repository: {input_path}", echo=True)
        if gc.fetch_github_repo(input_path, target_folder):
            log("Codebase ready", echo=True)
            return True, True
        log("Failed to fetch repository", echo=True)
        return False, True

    # Handle local files
    input_p = Path(input_path)
    if not input_p.exists():
        log(f"Error: {input_path} not found", echo=True)
        return False, False

    # Clean up and prepare
    if config.TMP_DIR.exists():
        shutil.rmtree(config.TMP_DIR)
    config.HTML_DIR.mkdir(parents=True, exist_ok=True)
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Extract or copy
    if input_p.suffix == ".zip":
        success = extract_zip(input_p, target_folder)
    elif input_p.is_dir():
        success = copy_html_folder(input_p)
    else:
        log(f"Error: {input_path} must be .zip or directory", echo=True)
        return False, False

    if not success:
        return False, False

    # Clean and ingest
    from utils.htmlcontext import clean_html_files
    from utils.ingest import ingest_documents

    if clean_html_files() == 0 or not ingest_documents():
        return False, False

    size_kb = config.OUT_INDEX.stat().st_size // 1024
    log(f"\nIndex ready: {size_kb}KB", echo=True)
    return True, False

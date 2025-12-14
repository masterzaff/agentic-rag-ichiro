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
    print(msg)

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
                    print(f"No files found in '{target_folder}'")
                    return False

                config.TEMP_EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
                zip_ref.extractall(config.TEMP_EXTRACT_DIR, members)

                source_path = config.TEMP_EXTRACT_DIR / target_folder
                if not source_path.exists():
                    print(f"Folder '{target_folder}' not found")
                    return False

                config.HTML_DIR.mkdir(parents=True, exist_ok=True)
                html_files = list(source_path.rglob("*.html"))

                if not html_files:
                    print(f"No HTML files in '{target_folder}'")
                    return False

                for file in html_files:
                    shutil.copy2(file, config.HTML_DIR / file.name)

                shutil.rmtree(config.TEMP_EXTRACT_DIR)
                print(f"Extracted {len(html_files)} HTML files")
            else:
                zip_ref.extractall(config.HTML_DIR)
                print(f"Extracted to {config.HTML_DIR}")

        return True
    except Exception as e:
        print(f"Failed to extract: {e}")
        return False


def copy_html_folder(src: Path) -> bool:
    """Copy HTML files from source folder to HTML_DIR."""
    print(f"Copying files from {src}...")

    try:
        config.HTML_DIR.mkdir(parents=True, exist_ok=True)
        html_files = list(src.rglob("*.html"))

        if not html_files:
            print(f"No HTML files found in {src}")
            return False

        for file in html_files:
            shutil.copy2(file, config.HTML_DIR / file.name)

        print(f"Copied {len(html_files)} HTML files")
        return True
    except Exception as e:
        print(f"Failed to copy: {e}")
        return False


def add_context(input_path: str, target_folder: str = None):
    """Add context from zip, folder, or GitHub URL."""
    import main.codecontext as gc

    # Handle GitHub URLs
    if gc.is_github_url(input_path):
        print(f"Fetching repository: {input_path}")
        if gc.fetch_github_repo(input_path, target_folder):
            print("Codebase ready")
            return True, True
        print("Failed to fetch repository")
        return False, True

    # Handle local files
    input_p = Path(input_path)
    if not input_p.exists():
        print(f"Error: {input_path} not found")
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
        print(f"Error: {input_path} must be .zip or directory")
        return False, False

    if not success:
        return False, False

    # Clean and ingest
    from main.htmlcontext import clean_html_files
    from utils.ingest import ingest_documents

    if clean_html_files() == 0 or not ingest_documents():
        return False, False

    size_kb = config.OUT_INDEX.stat().st_size // 1024
    print(f"\nIndex ready: {size_kb}KB")
    return True, False

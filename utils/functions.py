import utils.config as config
import shutil


def log(msg, echo=False):
    """Print message if verbose or echo is True."""
    if config.VERBOSE or echo:
        print(msg)


def cleanup_all():
    """Remove temporary files unless --keep flag is set."""
    if config.KEEP_INDEX:
        print("\nKeeping index files")
        return

    print("\nCleaning up...")
    if config.TMP_DIR.exists():
        shutil.rmtree(config.TMP_DIR)
        print(f"Removed {config.TMP_DIR}")

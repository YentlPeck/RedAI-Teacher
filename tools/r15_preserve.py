"""Non-emulator test cleanup moves disposable fixtures; it never deletes them."""
import os
from pathlib import Path
import shutil
import tempfile
import uuid

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import settings  # noqa: E402

DEV = settings.REPO
DEST = settings.TRASH / 'r15-test-fixtures'
ALLOWED = [Path(tempfile.gettempdir()).resolve(), (DEV / 'tests').resolve(), (DEV / 'tests_arena').resolve()]


def preserve(path, *, missing_ok=False, **kwargs):
    p = Path(path).absolute()
    resolved = p.resolve()
    if not any(resolved != root and resolved.is_relative_to(root) for root in ALLOWED):
        raise RuntimeError(f'Refusing cleanup outside R15 fixture directories: {p}')
    if not p.exists():
        if missing_ok:
            return
        raise FileNotFoundError(p)
    DEST.mkdir(parents=True, exist_ok=True)
    target = DEST / (p.name + '-' + uuid.uuid4().hex)
    if not target.resolve().is_relative_to(DEST.resolve()):
        raise RuntimeError('Invalid fixture destination')
    # Same Windows volume: rename only, with no copy/delete fallback.
    os.rename(p, target)


def preserve_tree(path, ignore_errors=False, onerror=None, *, onexc=None, dir_fd=None):
    try:
        preserve(path, missing_ok=ignore_errors)
    except OSError:
        if not ignore_errors:
            raise


os.remove = os.unlink = preserve
os.rmdir = preserve
shutil.rmtree = preserve_tree

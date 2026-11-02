# ===== CELL 5: package submission.zip =====
import zipfile
from swegemma.config import ALLOWED_SUBMISSION_EXTENSIONS, MAX_SUBMISSION_SIZE_BYTES
zip_path = Path(shutil.make_archive(str(WORKING_DIR / 'submission'), 'zip', root_dir=AGENT_DIR))
with zipfile.ZipFile(zip_path, 'r') as zf:
    total = sum(i.file_size for i in zf.infolist())
    assert total <= MAX_SUBMISSION_SIZE_BYTES, f'too big: {total}'
    for info in zf.infolist():
        if not info.is_dir():
            assert Path(info.filename).suffix.lower() in ALLOWED_SUBMISSION_EXTENSIONS, info.filename
print(f'Created {zip_path} ({zip_path.stat().st_size/1024:.1f} KiB)')
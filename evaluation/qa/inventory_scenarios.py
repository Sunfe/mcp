from __future__ import annotations

import ctypes
import json
import zipfile
from pathlib import Path
from unittest.mock import patch

import fitz

from evaluation.inventory import inventory
from evaluation.qa.support import OUT, cli, digest, save


def run() -> None:
    raw = OUT / 'synthetic-files'
    raw.mkdir()
    for name, content in {'broken.pdf': b'bad pdf nonempty 123', 'broken.docx': b'bad zip nonempty 456',
                          'unknown.bin': b'unknown', 'video.mp4': b'synthetic video', 'image.png': b'not decoded',
                          'bad-utf8.txt': b'\xff', 'empty.pdf': b'', '.gitkeep': b''}.items():
        (raw / name).write_bytes(content)
    with fitz.open() as pdf:
        pdf.new_page().insert_text((50, 50), 'abcdefghijklmnopqrstuvwxyz')
        pdf.new_page()
        pdf.save(raw / 'two-pages.pdf')
    with zipfile.ZipFile(raw / 'minimal.docx', 'w') as archive:
        archive.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p/><w:tbl><w:tr><w:tc><w:p/></w:tc></w:tr></w:tbl></w:body></w:document>')
        archive.writestr('word/media/synthetic.png', b'qa')
    before = {path.name: digest(path) for path in raw.iterdir()}
    report = json.loads(cli('inventory-mixed', ['inventory', '--root', str(raw)]).read_text())
    expected = sum(path.stat().st_size for path in raw.iterdir())
    assert report['file_count'] == 9 and report['total_bytes'] == expected
    assert report['known_size_file_count'] == 9 and report['unknown_size_file_count'] == 0
    assert report['status'] == 'partial' and report['video_duration_hours'] is None
    assert report['standalone_image_files'] == report['video_files'] == 1
    pages = next(row for row in report['files'] if row['pages'] == 2)
    assert pages['text_sparse_pages'] == 1 and pages['text_sparse_ratio'] == 0.5
    docx = next(row for row in report['files'] if row['paragraphs'] == 2)
    assert docx['tables'] == docx['media_entries'] == 1 and docx['pages'] is None
    broken = [row for row in report['files'] if row['status'] == 'error']
    assert len(broken) == 3 and all(row['sha256'] is not None for row in broken)
    assert before == {path.name: digest(path) for path in raw.iterdir()}
    save('inventory-oracle.json', {'expected_bytes': expected, 'source_hashes': before, 'verdict': 'PASS'})
    empty = OUT / 'empty-root'
    empty.mkdir()
    empty_report = json.loads(cli('inventory-empty', ['inventory', '--root', str(empty)]).read_text())
    assert empty_report['file_count'] == empty_report['total_bytes'] == 0
    assert empty_report['status'] == 'complete'
    cli('inventory-missing', ['inventory', '--root', str(OUT / 'missing-root')], 2)
    locked = OUT / 'locked-root'
    locked.mkdir()
    locked_file = locked / 'locked.pdf'
    locked_file.write_bytes(b'locked synthetic payload')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
    kernel.CreateFileW.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.CreateFileW(str(locked_file), 0x80000000, 0, None, 3, 0, None)
    assert handle != ctypes.c_void_p(-1).value
    try:
        locked_report = json.loads(cli('inventory-os-locked', ['inventory', '--root', str(locked)]).read_text())
        assert locked_report['files'][0]['status'] == 'error'
        assert locked_report['files'][0]['sha256'] is None
        assert locked_report['files'][0]['bytes'] == len(b'locked synthetic payload')
    finally:
        assert kernel.CloseHandle(handle)
    print('SURFACE library: inventory(root, None), Path.stat fault after enumeration', flush=True)
    real_stat = Path.stat

    def failed_stat(path: Path, *, follow_symlinks: bool = True):
        if path == locked_file and follow_symlinks:
            raise PermissionError(13, 'independent stat fault')
        return real_stat(path, follow_symlinks=follow_symlinks)

    with patch.object(Path, 'stat', failed_stat):
        unknown = inventory(locked, None)
    assert unknown.unknown_size_file_count == 1 and unknown.known_size_file_count == 0
    assert unknown.files[0].bytes is None and unknown.total_bytes == 0
    save('inventory-stat-fault.json', unknown.model_dump(mode='json'))

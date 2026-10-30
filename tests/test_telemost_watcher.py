import asyncio
import os
import time
from unittest.mock import patch

from app.services import telemost_watcher as w


def _recording(folder, name, size=10, age=600):
    p = folder / name
    p.write_bytes(b"x" * size)
    old = time.time() - age
    os.utime(p, (old, old))
    return p


def _scan(state, sizes):
    asyncio.run(w.scan_once(state, sizes))


def test_meeting_name():
    from pathlib import Path
    assert w._meeting_name(Path("Встреча в Телемосте 30.10.26 12-59-01 — запись.webm")) == "Встреча в Телемосте 30.10.26 12-59-01"


def test_processes_new_recording_once_size_is_stable(tmp_path):
    _recording(tmp_path, "old.webm")
    _recording(tmp_path, "new.webm")
    (tmp_path / "notes.txt").write_text("не запись")
    state = {"seen": {"old.webm": "baseline"}}
    sizes = {}

    with patch.object(w.settings, "telemost_dir", tmp_path), \
         patch.object(w, "_save_state"), \
         patch.object(w, "process_recording", return_value="done") as proc:
        _scan(state, sizes)  # первый раз видим файл — размер ещё не с чем сравнить
        proc.assert_not_called()
        _scan(state, sizes)
        _scan(state, sizes)  # уже обработан — повторно не берём

    assert [c.args[0].name for c in proc.call_args_list] == ["new.webm"]
    assert state["seen"]["new.webm"] == "done"


def test_skips_recording_that_is_still_growing(tmp_path):
    rec = _recording(tmp_path, "live.webm", size=10, age=0)
    state, sizes = {"seen": {}}, {}

    with patch.object(w.settings, "telemost_dir", tmp_path), \
         patch.object(w, "_save_state"), \
         patch.object(w, "process_recording", return_value="done") as proc:
        _scan(state, sizes)
        rec.write_bytes(b"x" * 20)
        _scan(state, sizes)  # размер изменился
        _scan(state, sizes)  # размер тот же, но файл изменён только что

    proc.assert_not_called()
    assert "live.webm" not in state["seen"]


def test_failure_is_recorded_and_not_retried(tmp_path):
    _recording(tmp_path, "broken.webm")
    state, sizes = {"seen": {}}, {}

    with patch.object(w.settings, "telemost_dir", tmp_path), \
         patch.object(w, "_save_state"), \
         patch.object(w, "_notify"), \
         patch.object(w, "process_recording", side_effect=RuntimeError("bad file")) as proc:
        for _ in range(3):
            _scan(state, sizes)

    assert proc.call_count == 1
    assert state["seen"]["broken.webm"].startswith("failed")

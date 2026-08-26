#!/usr/bin/env python3
"""Bounded storage lifecycle for the V4 action-compliance execution.

This module owns the storage policy so callers do not reimplement cleanup,
quota guards, or abandoned-slot recovery.  Source mirrors and dependency
caches are shared; worktrees, temporary files, build caches, and Cargo targets
belong to one worker slot and are removed after every lifecycle.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import errno
import json
import os
from pathlib import Path
import shutil
import threading
import time
from typing import Iterator


class V4StorageError(RuntimeError):
    """A storage lifecycle failure that must stop execution."""


class V4DiskGuardError(V4StorageError):
    """The pre-run disk guard rejected a new lifecycle."""


_LIFECYCLE_SETUP_LOCK = threading.RLock()


@dataclass(frozen=True)
class V4StoragePolicy:
    root: Path
    worker_count: int = 2
    min_free_bytes: int = 20 * 1024**3
    min_free_inodes: int = 100_000
    min_host_free_bytes: int = 5 * 1024**3
    codex_home_mode: str = "isolated"

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", self.root.resolve())
        if self.codex_home_mode not in {"isolated", "host"}:
            raise ValueError("codex_home_mode must be 'isolated' or 'host'")

    @property
    def sources(self) -> Path:
        return self.root / "sources"

    @property
    def shared(self) -> Path:
        return self.root / "shared"

    @property
    def slots(self) -> Path:
        return self.root / "slots"

    @property
    def temporary(self) -> Path:
        return self.root / "tmp"

    @property
    def codex_sqlite(self) -> Path:
        return self.root / "codex-sqlite"

    @property
    def stress_records(self) -> Path:
        return self.root / "stress-records"

    def initialize(self) -> None:
        for path in (
            self.sources,
            self.shared / "go-modcache",
            self.shared / "cargo-home",
            self.shared / "pip-cache",
            self.shared / "python-wheelhouse",
            self.slots,
            self.temporary,
            self.codex_sqlite,
            self.stress_records,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def source_cache(self, task: str) -> Path:
        return self.sources / f"{task}.git"

    def slot_root(self, slot: int) -> Path:
        if slot < 0 or slot >= self.worker_count:
            raise ValueError(f"invalid V4 worker slot: {slot}")
        return self.slots / f"slot-{slot:02d}"

    def slot_tmp(self, slot: int) -> Path:
        return self.temporary / f"slot-{slot:02d}"

    def slot_go_build(self, slot: int) -> Path:
        return self.slot_root(slot) / "go-build-cache"

    def slot_cargo_target(self, slot: int) -> Path:
        return self.slot_root(slot) / "cargo-target"

    def slot_codex_home(self, slot: int) -> Path:
        return self.slot_root(slot) / "codex-home"

    def _prepare_codex_home(self, slot: int) -> Path:
        """Provide Codex a writable, disposable home for each worker slot.

        The managed parent session mounts the user's normal Codex home
        read-only.  Codex still needs a writable home to initialize its
        app-server client, even for an ephemeral session.  Copy only the
        authentication/configuration/model metadata needed to start; all
        session state remains slot-local and is deleted in lifecycle cleanup.
        """

        target = self.slot_codex_home(slot)
        target.mkdir(parents=True, exist_ok=True)
        source = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
        for name in ("auth.json", "config.toml", "models_cache.json", "version.json"):
            source_file = source / name
            target_file = target / name
            if source_file.is_file() and not target_file.exists():
                shutil.copy2(source_file, target_file)
        auth = target / "auth.json"
        if auth.exists():
            auth.chmod(0o600)
        return target

    def environment(self, slot: int) -> dict[str, str]:
        tmp = self.slot_tmp(slot)
        tmp.mkdir(parents=True, exist_ok=True)
        environment = {
            "TMPDIR": str(tmp),
            "TMP": str(tmp),
            "TEMP": str(tmp),
            "PIP_CACHE_DIR": str(self.shared / "pip-cache"),
            "CARGO_HOME": str(self.shared / "cargo-home"),
            "CARGO_NET_OFFLINE": "true",
            "GOPROXY": "off",
            "GOSUMDB": "off",
            "CODEX_SQLITE_HOME": str(self.codex_sqlite),
            "PYTHONDONTWRITEBYTECODE": "1",
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "safe.directory",
            "GIT_CONFIG_VALUE_0": "*",
        }
        if self.codex_home_mode == "isolated":
            environment["CODEX_HOME"] = str(self._prepare_codex_home(slot))
        return environment

    def _stat(self, path: Path | None = None) -> dict[str, int]:
        target = path or self.root
        usage = shutil.disk_usage(target)
        stats = os.statvfs(target)
        return {
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
            "free_inodes": stats.f_bavail,
            "total_inodes": stats.f_blocks,
        }

    def measure(self, slot: int | None = None) -> dict[str, object]:
        paths = {
            "root": self.root,
            "tmp": self.temporary,
            "shared": self.shared,
            "codex_sqlite": self.codex_sqlite,
        }
        if slot is not None:
            paths["slot"] = self.slot_root(slot)
            paths["slot_tmp"] = self.slot_tmp(slot)
        sizes: dict[str, int] = {}
        for name, path in paths.items():
            total = 0
            if path.exists():
                try:
                    candidates = path.rglob("*")
                    for item in candidates:
                        try:
                            if item.is_file():
                                total += item.stat().st_size
                        except FileNotFoundError:
                            # Build/test cleanup can remove a file between
                            # enumeration and stat; the filesystem guard only
                            # needs a conservative point-in-time estimate.
                            continue
                except FileNotFoundError:
                    pass
            sizes[name] = total
        return {
            "filesystem": self._stat(),
            "host_root_filesystem": self._stat(Path("/")),
            "sizes_bytes": sizes,
        }

    def guard(self, *, run_id: str, slot: int) -> dict[str, object]:
        measurement = self.measure(slot)
        filesystem = measurement["filesystem"]
        assert isinstance(filesystem, dict)
        free_bytes = int(filesystem["free_bytes"])
        free_inodes = int(filesystem["free_inodes"])
        host_root = measurement["host_root_filesystem"]
        assert isinstance(host_root, dict)
        host_free_bytes = int(host_root["free_bytes"])
        if (
            free_bytes < self.min_free_bytes
            or free_inodes < self.min_free_inodes
            or host_free_bytes < self.min_host_free_bytes
        ):
            raise V4DiskGuardError(
                f"V4 disk guard rejected run {run_id} in slot {slot}: "
                f"free_bytes={free_bytes} threshold={self.min_free_bytes}; "
                f"free_inodes={free_inodes} threshold={self.min_free_inodes}; "
                f"host_root_free_bytes={host_free_bytes} threshold={self.min_host_free_bytes}"
            )
        return {
            "run_id": run_id,
            "slot": slot,
            "free_bytes": free_bytes,
            "free_inodes": free_inodes,
            "min_free_bytes": self.min_free_bytes,
            "min_free_inodes": self.min_free_inodes,
            "host_root_free_bytes": host_free_bytes,
            "min_host_free_bytes": self.min_host_free_bytes,
        }

    def _marker(self, slot: int) -> Path:
        return self.slot_root(slot) / ".v4_slot_marker.json"

    def _pid_alive(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def _process_identity(self, pid: int) -> tuple[str, str] | None:
        try:
            stat_fields = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").split()
            start_time = stat_fields[21]
            command = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
            return start_time, command
        except (OSError, IndexError):
            return None

    def recover_abandoned(self) -> list[dict[str, object]]:
        """Remove only stale or unmarked disposable V4 slot directories."""

        recovered: list[dict[str, object]] = []
        with _LIFECYCLE_SETUP_LOCK:
            self.slots.mkdir(parents=True, exist_ok=True)
            for slot_root in sorted(self.slots.glob("slot-*")):
                marker = slot_root / ".v4_slot_marker.json"
                if not marker.is_file():
                    # A slot root is created only inside lifecycle and is
                    # published with its marker before any work begins.  An
                    # unmarked root is therefore disposable even when a
                    # crash left it empty between mkdir and marker publish.
                    shutil.rmtree(slot_root)
                    slot_number = int(slot_root.name.split("-")[-1])
                    tmp = self.slot_tmp(slot_number)
                    if tmp.exists():
                        shutil.rmtree(tmp)
                    recovered.append(
                        {"slot": slot_number, "reason": "unmarked_slot_root"}
                    )
                    continue
                try:
                    record = json.loads(marker.read_text(encoding="utf-8"))
                    pid = int(record["pid"])
                except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
                    raise V4StorageError(f"invalid V4 slot marker: {marker}: {error}") from error
                marker_identity = (
                    str(record.get("proc_start_time", "")),
                    str(record.get("proc_cmdline", "")),
                )
                current_identity = self._process_identity(pid)
                if current_identity is not None and marker_identity == current_identity:
                    continue
                shutil.rmtree(slot_root)
                slot = record.get("slot")
                tmp = self.slot_tmp(int(slot)) if isinstance(slot, int) else None
                if tmp is not None and tmp.exists():
                    shutil.rmtree(tmp)
                recovered.append(record)
        return recovered

    @contextmanager
    def lifecycle(self, *, run_id: str, slot: int) -> Iterator[dict[str, object]]:
        with _LIFECYCLE_SETUP_LOCK:
            self.initialize()
            recovery = self.recover_abandoned()
            guard = self.guard(run_id=run_id, slot=slot)
            slot_root = self.slot_root(slot)
            if slot_root.exists():
                raise V4StorageError(f"worker slot is not clean before run: {slot_root}")
            slot_root.mkdir(parents=True)
            self.slot_tmp(slot).mkdir(parents=True, exist_ok=True)
            marker = {
                "experiment": "action-compliance-v4",
                "pid": os.getpid(),
                "proc_start_time": (self._process_identity(os.getpid()) or ("", ""))[0],
                "proc_cmdline": (self._process_identity(os.getpid()) or ("", ""))[1],
                "slot": slot,
                "run_id": run_id,
                "started_at": time.time(),
            }
            self._marker(slot).write_text(json.dumps(marker, sort_keys=True) + "\n", encoding="utf-8")
            before = self.measure(slot)
        try:
            yield {"recovery": recovery, "guard": guard, "before": before}
        finally:
            after = self.measure(slot)
            record = {
                **marker,
                "finished_at": time.time(),
                "before": before,
                "after": after,
            }
            record_path = self.stress_records / f"{run_id}.json"
            temporary = record_path.with_suffix(".json.tmp")
            temporary.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            temporary.replace(record_path)
            if slot_root.exists():
                shutil.rmtree(slot_root)
            slot_tmp = self.slot_tmp(slot)
            if slot_tmp.exists():
                shutil.rmtree(slot_tmp)

    def residual_bytes(self) -> int:
        return sum(item.stat().st_size for item in self.root.rglob("*") if item.is_file())

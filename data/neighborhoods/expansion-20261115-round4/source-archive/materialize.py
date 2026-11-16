#!/usr/bin/env python3
"""Restore immutable round-4 sources from a checked manifest, ZIP parts and local Git.

No network or Git writes. --check certifies an already materialized tree and never
changes restore targets. Direct files are inventory only, not immutable sources.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tempfile
import zipfile

CHUNK = 1024 * 1024
HEX = re.compile(r"[0-9a-f]{64}\Z")
SCOPE = "data/neighborhoods/expansion-20261115-round4/"


class InvalidArchive(Exception):
    pass


def fail(message):
    raise InvalidArchive(message)


def integer(value, label, maximum=None):
    if type(value) is not int or value < 0 or (maximum is not None and value > maximum):
        fail(f"Invalid {label}.")
    return value


def digest(value, label):
    if not isinstance(value, str) or not HEX.fullmatch(value):
        fail(f"Invalid SHA-256 for {label}.")
    return value


def relative(value, label, scope=None):
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        fail(f"Unsafe {label}.")
    p = PurePosixPath(value)
    if p.is_absolute() or re.match(r"^[A-Za-z]:", value) or any(x in ("", ".", "..") for x in value.split("/")):
        fail(f"Unsafe {label}.")
    if p.as_posix() != value or (scope is not None and not value.startswith(scope)):
        fail(f"Out-of-scope or noncanonical {label}.")
    return value


def safe_components(path, allow_missing=False):
    """Check every existing component, including the chosen root's ancestors."""
    path = Path(os.path.abspath(path))
    current = Path(path.anchor)
    parts = path.parts[1:]
    for i, part in enumerate(parts):
        current /= part
        try:
            st = current.lstat()
        except FileNotFoundError:
            if allow_missing:
                return path
            fail(f"Missing local path: {current}")
        if stat.S_ISLNK(st.st_mode):
            fail(f"Symlink path component rejected: {current}")
        if i < len(parts) - 1 and not stat.S_ISDIR(st.st_mode):
            fail(f"Non-directory path component: {current}")
    return path


def regular(path):
    path = safe_components(path)
    st = path.lstat()
    if not stat.S_ISREG(st.st_mode):
        fail(f"Non-regular file rejected: {path}")
    return st


def hash_stream(stream, sink=None, limit=None):
    h = hashlib.sha256()
    count = 0
    while True:
        block = stream.read(CHUNK)
        if not block:
            break
        count += len(block)
        if limit is not None and count > limit:
            fail("Source is longer than the manifest byte count.")
        h.update(block)
        if sink is not None:
            sink.write(block)
    return h.hexdigest(), count


def file_matches(path, meta, mode=False):
    st = regular(path)
    if st.st_size != meta["bytes"] or (mode and stat.S_IMODE(st.st_mode) != meta["mode"]):
        return False
    with path.open("rb") as stream:
        return hash_stream(stream) == (meta["sha256"], meta["bytes"])


def baseline_bytes(base_root, baseline, path, meta):
    local = base_root / path
    safe_components(local, allow_missing=True)
    if local.exists():
        if file_matches(local, meta):
            data = local.read_bytes()
            if len(data) == meta["bytes"] and hashlib.sha256(data).hexdigest() == meta["sha256"]:
                return data
    # Use object reads only: no checkout, fetch, network or worktree mutation.
    result = subprocess.run(
        ["git", "-C", str(base_root), "show", f"{baseline}:{path}"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
    )
    if result.returncode:
        fail(f"No matching local/baseline bytes for: {path}")
    data = result.stdout
    if len(data) != meta["bytes"] or hashlib.sha256(data).hexdigest() != meta["sha256"]:
        fail(f"Baseline bytes do not match manifest: {path}")
    return data


def read_manifest(archive_dir):
    p = archive_dir / "manifest.json"
    regular(p)
    # Duplicate JSON keys can otherwise conceal duplicate source paths.
    def object_pairs(pairs):
        d = {}
        for k, v in pairs:
            if k in d:
                fail(f"Duplicate manifest key: {k}")
            d[k] = v
        return d
    with p.open(encoding="utf-8") as stream:
        m = json.load(stream, object_pairs_hook=object_pairs)
    if not isinstance(m, dict) or type(m.get("schemaVersion")) is not int or m["schemaVersion"] != 1:
        fail("Unsupported manifest schema.")
    scope = m.get("scopePrefix")
    if scope != SCOPE:
        fail("Unexpected archive scope prefix.")
    baseline = m.get("baselineCommit")
    if not isinstance(baseline, str) or not re.fullmatch(r"[0-9a-f]{40}", baseline):
        fail("Invalid baseline commit.")
    files = m.get("files")
    if not isinstance(files, dict):
        fail("Manifest files must be an object.")
    blobs = {}
    for name, meta in files.items():
        relative(name, "source path", scope)
        if not isinstance(meta, dict):
            fail("Invalid source metadata.")
        digest(meta.get("sha256"), name)
        integer(meta.get("bytes"), "source byte count")
        integer(meta.get("mode"), "source permissions", 0o777)
        if ("basePath" in meta) == ("archiveMember" in meta):
            fail("Each source must have exactly one byte source.")
        if "basePath" in meta:
            relative(meta["basePath"], "baseline path")
        else:
            member = relative(meta["archiveMember"], "ZIP member")
            if member != "blobs/" + meta["sha256"]:
                fail("ZIP member must be the source SHA-256 blob.")
            if member in blobs and blobs[member]["bytes"] != meta["bytes"]:
                fail("Conflicting shared-blob byte counts.")
            blobs[member] = meta
    for name in files:
        ancestor = PurePosixPath(name).parent
        while ancestor.as_posix() != ".":
            if ancestor.as_posix() in files:
                fail("Manifest source file is also another source directory.")
            ancestor = ancestor.parent
    direct = m.get("directFiles", [])
    if not isinstance(direct, list) or len(set(direct)) != len(direct):
        fail("Invalid or duplicate direct-file inventory.")
    for name in direct:
        relative(name, "direct-file path", scope)
    a = m.get("archive")
    if not isinstance(a, dict):
        fail("Missing archive metadata.")
    digest(a.get("sha256"), "archive")
    integer(a.get("bytes"), "archive byte count")
    parts = a.get("parts")
    if not isinstance(parts, list) or not parts:
        fail("Missing archive parts.")
    seen = set()
    for part in parts:
        if not isinstance(part, dict):
            fail("Invalid archive part.")
        name = relative(part.get("path"), "archive-part path")
        if name in seen:
            fail("Duplicate archive-part path.")
        seen.add(name)
        digest(part.get("sha256"), "archive part")
        integer(part.get("bytes"), "archive-part byte count")
    if sum(p["bytes"] for p in parts) != a["bytes"]:
        fail("Archive-part sizes do not sum to archive size.")
    return m, blobs


def recombine(archive_dir, metadata, temporary):
    complete = hashlib.sha256()
    total = 0
    for part in metadata["parts"]:
        p = archive_dir / part["path"]
        regular(p)
        one = hashlib.sha256()
        count = 0
        with p.open("rb") as stream:
            while block := stream.read(CHUNK):
                count += len(block)
                if count > part["bytes"]:
                    fail("Archive part exceeds manifest byte count.")
                total += len(block)
                one.update(block)
                complete.update(block)
                temporary.write(block)
        if count != part["bytes"] or one.hexdigest() != part["sha256"]:
            fail(f"Archive part integrity failure: {part['path']}")
    if total != metadata["bytes"] or complete.hexdigest() != metadata["sha256"]:
        fail("Combined archive integrity failure.")
    temporary.seek(0)


def validate_zip(z, blobs):
    infos = z.infolist()
    names = [i.filename for i in infos]
    if len(set(names)) != len(names):
        fail("Duplicate ZIP member names.")
    for info in infos:
        relative(info.filename, "ZIP member")
        mode = info.external_attr >> 16
        kind = stat.S_IFMT(mode)
        if info.is_dir() or kind not in (0, stat.S_IFREG) or info.flag_bits & 1:
            fail("ZIP directory, symlink, special or encrypted member rejected.")
    if set(names) != set(blobs):
        fail("ZIP has missing or unexpected blob members.")
    for name, meta in blobs.items():
        if z.getinfo(name).file_size != meta["bytes"]:
            fail("ZIP member size does not match manifest.")
        with z.open(name) as stream:
            if hash_stream(stream, limit=meta["bytes"]) != (meta["sha256"], meta["bytes"]):
                fail("ZIP blob integrity failure.")


def create_exact(root, name, data, mode):
    """Traverse/create using no-follow directory descriptors; never replace files."""
    safe_components(root, allow_missing=True)
    root.mkdir(parents=True, exist_ok=True)
    safe_components(root)
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open(root, flags)
    try:
        parts = name.split("/")
        for part in parts[:-1]:
            try:
                os.mkdir(part, mode=0o755, dir_fd=fd)
            except FileExistsError:
                pass
            next_fd = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        output_fd = os.open(parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode, dir_fd=fd)
        try:
            with os.fdopen(output_fd, "wb", closefd=False) as stream:
                stream.write(data)
                stream.flush()
            os.fchmod(output_fd, mode)
        except BaseException:
            os.unlink(parts[-1], dir_fd=fd)
            raise
        finally:
            os.close(output_fd)
    finally:
        os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, help="Repository/destination root")
    parser.add_argument("--base-root", type=Path, help="Original checkout for baseline byte references")
    parser.add_argument("--check", action="store_true", help="Verify restored files without changing targets")
    args = parser.parse_args()
    archive_dir = safe_components(Path(__file__).absolute().parent)
    root = safe_components(args.root or Path(__file__).absolute().parents[4], allow_missing=True)
    base_root = safe_components(args.base_root or root, allow_missing=True)
    m, blobs = read_manifest(archive_dir)
    files = m["files"]
    missing = []
    # Preflight every target before creating anything, including permissions.
    for name, meta in files.items():
        p = root / name
        safe_components(p, allow_missing=True)
        if p.exists():
            if not file_matches(p, meta, mode=True):
                fail(f"Refusing differing existing bytes or permissions: {name}")
        else:
            missing.append(name)
    with tempfile.TemporaryFile() as temporary:
        recombine(archive_dir, m["archive"], temporary)
        with zipfile.ZipFile(temporary, "r") as z:
            validate_zip(z, blobs)
            # Check all baseline sources, even when targets already exist.
            for name, meta in files.items():
                if "basePath" in meta:
                    baseline_bytes(base_root, m["baselineCommit"], meta["basePath"], meta)
            if args.check and missing:
                fail(f"Missing restored targets: {len(missing)} (first: {', '.join(missing[:3])}). Run materialize.py first.")
            if not args.check:
                for name in missing:
                    meta = files[name]
                    if "basePath" in meta:
                        data = baseline_bytes(base_root, m["baselineCommit"], meta["basePath"], meta)
                    else:
                        data = z.read(meta["archiveMember"])
                    if len(data) != meta["bytes"] or hashlib.sha256(data).hexdigest() != meta["sha256"]:
                        fail("Source integrity changed before restoration.")
                    create_exact(root, name, data, meta["mode"])
    print(f"Verified files: {len(files)}; blobs: {len(blobs)}; baseline files: {sum('basePath' in f for f in files.values())}; restored: {0 if args.check else len(missing)}; existing: {len(files) - len(missing)}.")


if __name__ == "__main__":
    try:
        main()
    except (InvalidArchive, OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)

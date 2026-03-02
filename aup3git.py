#!/usr/bin/env python3
"""
aup3git – Put Audacity .aup3 project files under git version control.

Usage:
  aup3git explode <file.aup3>   # aup3 → split directory (ready for git)
  aup3git implode <file.aup3>   # split directory → aup3

No intermediate .sql file is created; gitsqlite output is streamed
line-by-line directly into the split directory and vice versa.

The split directory contains:
  _metadata.json   – SQLite header fields (application_id, user_version)
  0000001 … N      – one file per SQL line from the gitsqlite dump
"""

import json
import shutil
import struct
import subprocess
import sys
import argparse
from pathlib import Path


# ---------------------------------------------------------------------------
# SQLite header constants  (https://www.sqlite.org/fileformat.html)
# ---------------------------------------------------------------------------

SQLITE_HEADER_SIZE       = 100          # minimum valid SQLite file size
OFFSET_USER_VERSION      = 60           # 4-byte big-endian int
OFFSET_APPLICATION_ID    = 68           # 4-byte big-endian int
AUDACITY_APPLICATION_ID  = 0x41554459  # "AUDY"

METADATA_FILENAME = "_metadata.json"
LINE_WIDTH        = 7                   # zero-padding; supports up to 9 999 999 lines


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def check_gitsqlite() -> None:
    if shutil.which("gitsqlite") is None:
        die(
            "'gitsqlite' not found in PATH. Please install it first.\n"
            "See: https://github.com/danielsiegl/gitsqlite"
        )


def dir_path(aup3: Path) -> Path:
    return aup3.with_suffix(aup3.suffix + ".sql.dir")


def read_header_fields(aup3: Path) -> dict:
    """Read user_version and application_id directly from the SQLite binary header."""
    with aup3.open("rb") as fh:
        header = fh.read(SQLITE_HEADER_SIZE)
    if len(header) < SQLITE_HEADER_SIZE:
        die(f"{aup3} is too small to be a valid SQLite database.")
    if not header.startswith(b"SQLite format 3\x00"):
        die(f"{aup3} does not look like a SQLite3 database (wrong magic bytes).")
    user_version   = struct.unpack_from(">I", header, OFFSET_USER_VERSION)[0]
    application_id = struct.unpack_from(">I", header, OFFSET_APPLICATION_ID)[0]
    return {"user_version": user_version, "application_id": application_id}


def patch_header_fields(aup3: Path, meta: dict) -> None:
    """Write user_version and application_id back into the SQLite binary header."""
    with aup3.open("r+b") as fh:
        fh.seek(OFFSET_USER_VERSION)
        fh.write(struct.pack(">I", meta["user_version"]))
        fh.seek(OFFSET_APPLICATION_ID)
        fh.write(struct.pack(">I", meta["application_id"]))


# ---------------------------------------------------------------------------
# explode: aup3  →  split directory   (no intermediate SQL file)
# ---------------------------------------------------------------------------

def explode(aup3: Path) -> None:
    if not aup3.exists():
        die(f"File not found: {aup3}")
    if aup3.suffix.lower() != ".aup3":
        print(f"WARNING: '{aup3}' does not have the .aup3 extension, continuing anyway.")

    split_dir = dir_path(aup3)

    # Step 1: Read application_id and user_version from the binary header
    print(f"Reading SQLite header fields from {aup3} ...")
    meta = read_header_fields(aup3)
    app_id_hex = f"0x{meta['application_id']:08X}"
    app_id_chars = "".join(
        chr(b) if 32 <= b < 127 else "."
        for b in struct.pack(">I", meta["application_id"])
    )
    print(f"  application_id={app_id_hex} ({app_id_chars})")
    print(f"  user_version={meta['user_version']}")

    # Step 2: Prepare split directory
    print(f"Preparing split directory (i.e. deleting it) ...")
    if split_dir.exists():
        shutil.rmtree(split_dir)
    split_dir.mkdir(parents=True)

    # Save metadata so implode can restore the header fields exactly
    print(f"Saving metadata ...")
    (split_dir / METADATA_FILENAME).write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )

    print(f"Streaming gitsqlite clean ...")
    # Stream gitsqlite clean output line-by-line straight into the split dir.
    # gitsqlite reads from stdin, writes to stdout -- nothing is buffered in Python.
    # Equivalent shell command: gitsqlite clean < foo.aup3  (stdout -> line files)
    count = 0
    with aup3.open("rb") as fh_in:
        proc = subprocess.Popen(
            ["gitsqlite", "clean"],
            stdin=fh_in,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            print(f"  line progress: ", end=" ", flush=True)
            for idx, line in enumerate(proc.stdout, start=1):
                print(f"{idx}", end=" ", flush=True)
                (split_dir / str(idx).zfill(LINE_WIDTH)).write_bytes(line)
                count = idx
            print()
        finally:
            proc.stdout.close()
            stderr = proc.stderr.read()
            proc.wait()

    if proc.returncode != 0:
        shutil.rmtree(split_dir)
        die(f"gitsqlite clean failed:\n{stderr.decode()}")

    print()
    print("Done!  Add the split directory to git and commit:")
    print(f"  git add {split_dir}")
    print(f"  git commit -m 'Update {aup3.name}'")


# ---------------------------------------------------------------------------
# implode: split directory  ->  aup3   (no intermediate SQL file)
# ---------------------------------------------------------------------------

def implode(aup3: Path) -> None:
    split_dir = dir_path(aup3)

    if not split_dir.exists():
        die(
            f"Split directory not found: {split_dir}\n"
            f"Run 'aup3git explode {aup3.name}' first."
        )

    meta_file = split_dir / METADATA_FILENAME
    if not meta_file.exists():
        die(f"Metadata file not found: {meta_file}\n"
            f"The split directory may be corrupt or from an older version of aup3git.")

    # Step 1: Load saved header fields
    print(f"Loading metadata ...")
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    app_id_hex = f"0x{meta['application_id']:08X}"
    app_id_chars = "".join(
        chr(b) if 32 <= b < 127 else "."
        for b in struct.pack(">I", meta["application_id"])
    )
    print(f"  application_id={app_id_hex} ({app_id_chars})")
    print(f"  user_version={meta['user_version']}")

    # Collect SQL line-files (everything except the metadata file), sorted by name
    part_files = sorted(
        (p for p in split_dir.iterdir() if p.is_file() and p.name != METADATA_FILENAME),
        key=lambda p: p.name,
    )
    if not part_files:
        die(f"No SQL line-files found in {split_dir}")

    # Step 2: Back up existing .aup3 if present
    if aup3.exists():
        print(f"  Backing up existing aup3 file ...")
        backup = aup3.with_suffix(aup3.suffix + ".bak")
        shutil.copy2(aup3, backup)

    # Step 3: Feed all line-files directly into gitsqlite smudge stdin, output -> aup3.
    # -verify-hash makes gitsqlite abort if the SHA-256 integrity check fails.
    # Equivalent shell command: cat 0000001 0000002 ... | gitsqlite -verify-hash smudge > foo.aup3
    print(f"Streaming {len(part_files):,} splits ...")
    with aup3.open("wb") as fh_out:
        proc = subprocess.Popen(
            ["gitsqlite", "-verify-hash", "smudge"],
            stdin=subprocess.PIPE,
            stdout=fh_out,
            stderr=subprocess.PIPE,
        )
        try:
            print(f"  line progress: ", end=" ", flush=True)
            for idx, part in enumerate(part_files):
                print(f"{idx}", end=" ", flush=True)
                proc.stdin.write(part.read_bytes())
            print()
        finally:
            proc.stdin.close()
            stderr = proc.stderr.read()
            proc.wait()

    if proc.returncode != 0:
        die(f"gitsqlite smudge failed:\n{stderr.decode()}")

    # Step 4: Patch application_id and user_version back into the binary header.
    # gitsqlite does not guarantee these are preserved across the SQL round-trip,
    # so we restore them directly at their fixed offsets in the SQLite file header.
    print(f"Patching SQLite header fields ...")
    patch_header_fields(aup3, meta)

    print()
    print(f"Restored {aup3} ({aup3.stat().st_size:,} bytes).")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="aup3git",
        description="Put Audacity .aup3 project files under git version control.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  aup3git explode MyProject.aup3
      Streams MyProject.aup3 through gitsqlite and splits the SQL output
      line-by-line into MyProject.aup3.sql.dir/.  Commit that directory.

  aup3git implode MyProject.aup3
      Feeds MyProject.aup3.sql.dir/ back through gitsqlite and writes
      MyProject.aup3, then restores the exact SQLite header fields.
        """,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_explode = sub.add_parser(
        "explode", help="aup3 -> split directory (prepare for git)"
    )
    p_explode.add_argument("file", type=Path, help="Path to the .aup3 file")

    p_implode = sub.add_parser(
        "implode", help="split directory -> aup3 (restore from git)"
    )
    p_implode.add_argument(
        "file", type=Path, help="Path to the .aup3 file (output name)"
    )

    args = parser.parse_args()
    check_gitsqlite()

    if args.command == "explode":
        explode(args.file)
    elif args.command == "implode":
        implode(args.file)


if __name__ == "__main__":
    main()

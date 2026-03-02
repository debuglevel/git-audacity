#!/usr/bin/env python3
"""
aup3git – Put Audacity .aup3 project files under git version control.

Usage:
  aup3git explode <file.aup3>   # aup3 → SQL → split into .sql.dir/
  aup3git implode <file.aup3>   # .sql.dir/ → SQL → aup3

The split directory contains one small text file per SQL line, named with
zero-padded indices (e.g. 0000001, 0000002, …) so git can diff them cleanly.
"""

import os
import sys
import shutil
import subprocess
import argparse
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def check_gitsqlite() -> None:
    if shutil.which("gitsqlite") is None:
        die("'gitsqlite' not found in PATH. Please install it first.\n"
            "See: https://github.com/danielsiegl/gitsqlite")


def sql_path(aup3: Path) -> Path:
    return aup3.with_suffix(aup3.suffix + ".sql")


def dir_path(aup3: Path) -> Path:
    return aup3.with_suffix(aup3.suffix + ".sql.dir")


# ---------------------------------------------------------------------------
# explode: aup3  →  SQL file  →  split directory
# ---------------------------------------------------------------------------

def explode(aup3: Path) -> None:
    if not aup3.exists():
        die(f"File not found: {aup3}")
    if aup3.suffix.lower() != ".aup3":
        print(f"WARNING: '{aup3}' does not have the .aup3 extension, continuing anyway.")

    sql_file = sql_path(aup3)
    split_dir = dir_path(aup3)

    # Step 1: aup3 (SQLite3 binary) → SQL text via gitsqlite clean
    # Both stdin and stdout are wired directly to files so nothing is buffered
    # in Python memory — equivalent to: gitsqlite clean < foo.aup3 > foo.aup3.sql
    print(f"[1/3] Converting {aup3} → {sql_file} via gitsqlite …")
    with aup3.open("rb") as fh_in, \
         sql_file.open("wb") as fh_out, \
         subprocess.Popen(
             ["gitsqlite", "clean"],
             stdin=fh_in,
             stdout=fh_out,
             stderr=subprocess.PIPE,
         ) as proc:
        _, stderr = proc.communicate()
        if proc.returncode != 0:
            sql_file.unlink(missing_ok=True)
            die(f"gitsqlite clean failed:\n{stderr.decode()}")

    # Step 2: Split SQL file line-by-line into the split directory.
    # 7 digits supports up to 9,999,999 lines — far more than any real dump.
    # We stream line-by-line so the full SQL is never in memory at once.
    print(f"[2/3] Splitting {sql_file} → {split_dir}/ …")
    if split_dir.exists():
        shutil.rmtree(split_dir)
    split_dir.mkdir(parents=True)

    width = 7
    count = 0
    with sql_file.open("r", encoding="utf-8") as fh:
        for idx, line in enumerate(fh, start=1):
            (split_dir / str(idx).zfill(width)).write_text(line, encoding="utf-8")
            count = idx

    print(f"[3/3] Written {count:,} line-files into {split_dir}/")
    print()
    print("Done!  You can now commit the split directory to git:")
    print(f"  git add {split_dir}")
    print(f"  git commit -m 'Update {aup3.name}'")
    print()
    print(f"The intermediate SQL file {sql_file} can be kept or deleted; it is")
    print(f"regenerated automatically by 'aup3git implode'.")


# ---------------------------------------------------------------------------
# implode: split directory  →  SQL file  →  aup3
# ---------------------------------------------------------------------------

def implode(aup3: Path) -> None:
    split_dir = dir_path(aup3)
    sql_file = sql_path(aup3)

    if not split_dir.exists():
        die(f"Split directory not found: {split_dir}\n"
            f"Run 'aup3git explode {aup3}' first.")

    # Step 1: Merge all part-files back into a single SQL file
    print(f"[1/3] Merging {split_dir}/ → {sql_file} …")

    part_files = sorted(split_dir.iterdir(), key=lambda p: p.name)
    if not part_files:
        die(f"Split directory is empty: {split_dir}")

    with sql_file.open("w", encoding="utf-8", newline="\n") as fh_out:
        for part in part_files:
            if part.is_file():
                fh_out.write(part.read_text(encoding="utf-8"))

    print(f"[2/3] Merged {len(part_files):,} line-files into {sql_file}")

    # Step 3: SQL text → aup3 (SQLite3 binary) via gitsqlite smudge.
    # Direct file handles: equivalent to: gitsqlite smudge < foo.aup3.sql > foo.aup3
    print(f"[3/3] Converting {sql_file} → {aup3} via gitsqlite …")

    # Back up existing aup3 if present
    if aup3.exists():
        backup = aup3.with_suffix(aup3.suffix + ".bak")
        shutil.copy2(aup3, backup)
        print(f"      (existing file backed up as {backup})")

    with sql_file.open("rb") as fh_in, \
         aup3.open("wb") as fh_out, \
         subprocess.Popen(
             ["gitsqlite", "-verify-hash", "smudge"],
             stdin=fh_in,
             stdout=fh_out,
             stderr=subprocess.PIPE,
         ) as proc:
        _, stderr = proc.communicate()
        if proc.returncode != 0:
            die(f"gitsqlite smudge failed:\n{stderr.decode()}")
    print()
    print(f"Done!  Restored {aup3} ({aup3.stat().st_size:,} bytes).")


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
      Converts MyProject.aup3 → MyProject.aup3.sql → MyProject.aup3.sql.dir/
      Commit MyProject.aup3.sql.dir/ to git.

  aup3git implode MyProject.aup3
      Merges MyProject.aup3.sql.dir/ → MyProject.aup3.sql → MyProject.aup3
        """,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_explode = sub.add_parser("explode", help="aup3 → SQL → split directory (prepare for git)")
    p_explode.add_argument("file", type=Path, help="Path to the .aup3 file")

    p_implode = sub.add_parser("implode", help="split directory → SQL → aup3 (restore from git)")
    p_implode.add_argument("file", type=Path, help="Path to the .aup3 file (target name)")

    args = parser.parse_args()
    check_gitsqlite()

    if args.command == "explode":
        explode(args.file)
    elif args.command == "implode":
        implode(args.file)


if __name__ == "__main__":
    main()

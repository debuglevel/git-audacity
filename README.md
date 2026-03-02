# git-audacity

This tool converts Audacity `.aup3` project files (which are SQLite3) into a format which `git` can handle:

1. Transform to `.sql` using https://github.com/danielsiegl/gitsqlite.
2. Split the `.sql` into 1 file for each line.
3. This can be committed with using too much space.

If the file was not split, `git` would use the whole (although compressed) file size on each commit.
This way, only changed `sampleblocks` will be committed.

If you use destructive operations on your samples, this project will probably not help you.
If you however only move around samples or change the hull curve, it might save a lot of space.

CAUTION: Audacity projects are still big. It's probably still a bad idea to version control them in `git`.

CAUTION: Of course this tool is highly experimental. Just do not use it. Thank you very much.

## `.gitignore`

As you do not want to commit the `.aup3` (and the temporary file), use this `.gitignore`:

```gitignore
*.aup3
*.aup3.sql
*.aup3.bak
```


## Usage

To convert `Fantasy_Ambience.aup3` into a format which is of use for `git`:

```console
$ python3 aup3git.py explode Fantasy_Ambience.aup3
$ git commit [...]
```

CAUTION: You may want to close Audacity before using `explode`. Audacity cleans the database file when the application is closed.

To restore `Fantasy_Ambience.aup3.sql.dir` into a `.aup3` again:

```console
$ git clone [...]
$ python3 aup3git.py explode Fantasy_Ambience.aup3
```


## AI generated slop

Idea was mine, but I was too lazy to code it.
It's AI generated.
Sorry.


## Application ID

Audacity sets the SQLite application ID to `AUDY`.
If it is not set, Audacity will complain that this is not a Audacity project.
That are just 4 bytes at offset 68 in the database header: https://sqlite.org/pragma.html#pragma_application_id https://sqlite.org/fileformat2.html#database_header

https://github.com/audacity/audacity/blob/5ef610ed23260d6d648175735bb16b32536eb30b/libraries/lib-project-file-io/ProjectFileIO.cpp#L71

This is not handled yet by gitsqlite: https://github.com/danielsiegl/gitsqlite/issues/132


## Project Format Version

Audacity sets a project format version at the `user_version` SQLite field.
That are just 4 bytes at offset 60 in the database header: https://sqlite.org/pragma.html#pragma_user_version https://sqlite.org/fileformat2.html#database_header
If it is not set, Audacity will complain that this project was created by a former version, but still load it.

https://github.com/audacity/audacity/blob/5ef610ed23260d6d648175735bb16b32536eb30b/libraries/lib-project-file-io/ProjectFileIO.cpp#L776-L777
https://github.com/audacity/audacity/blob/5ef610ed23260d6d648175735bb16b32536eb30b/libraries/lib-project/ProjectFormatVersion.cpp#L32-L40
https://github.com/audacity/audacity/blob/5ef610ed23260d6d648175735bb16b32536eb30b/libraries/lib-project/ProjectFormatVersion.h#L29

This is not handled yet by gitsqlite: https://github.com/danielsiegl/gitsqlite/issues/132

# CubeIDE source-directory synchronization tool

[繁體中文](README.md) | [English](README.en.md)

[sync_cubeide_sources.py](sync_cubeide_sources.py) is the tool previously used in the original project, retained unchanged. Its SHA-256 is `fa385d29546b60dfc4faf946492245af6ccb012889ae893afc7ba8ff8ffb934c`.

It consolidates individual source links into `Src`/`Inc` folder links so newly added sources and headers appear after an IDE refresh. This changes Eclipse source-browsing configuration; the actual compilation list remains controlled by the [Makefile](../../firmware/Makefile) and its build fragments.

| Implementation | Purpose |
| --- | --- |
| Resolve existing locations | Handle project-relative paths, parent-relative paths, local file URIs, and absolute paths; stop on mismatches or remote links |
| Preview and repeat execution | Preview changes by default; avoid writing when folder links are already configured |
| Backup and concurrency checks | Back up before writing and check the original configuration hash before/after preparation to avoid overwriting concurrent IDE changes |
| Atomic replacement | Finish writing and synchronize the temporary file to disk, preserve permissions, then replace the configuration atomically |

When inspecting this public repository from its root, specify the root explicitly. This command only previews:

```bash
python3 tools/ide/sync_cubeide_sources.py --root "$PWD"
```

The original default location remains `STM32N6ai/course17_voice_object_finder` under the user's home directory. `--apply` changes the selected project's configuration and requires closing the IDE first. The publication preparation did not apply it. Archiving the tool did not change the frozen dual-model firmware's C/H files or compilation behavior.

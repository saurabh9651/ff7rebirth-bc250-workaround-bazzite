# Security and privacy

This project builds an experimental per-game driver. It does not establish that
the game or driver is stable. Save other work before testing; GPU hangs remain
possible. Review the scripts and pinned upstream sources before executing them.

## System boundary

Setup uses a rootless build container and a private runtime. It does not replace
system Mesa/libdrm, flash BIOS, change the kernel, or modify global Steam settings.
The launcher checks the driver/runtime hashes and kernel before enabling the
per-game environment. Removing its Steam launch option restores normal selection.
Container builds download distribution packages; that build image and package
repository state are not pinned bit for bit. Runtime dependency checks can fail
on other host versions. Never bypass a failed check just to reach the game menu.

## Data boundary

Raw logs, crash reports, build paths, launch commands, local manifests, Steam
configuration and session memory stay local. Proton crash reports may contain
private information or binary data. Structured reports intentionally select
versions, hashes, timing/status and diagnostic counters; review every report
before sharing. No telemetry or automatic upload is implemented.

The community archive uses an explicit file list and strips user/group owner
names. It does not include build output, downloaded upstream assets, raw logs,
private notes, Steam data, container storage or repository metadata.

## Publication checks and limits

Run `python3 -B tools/audit_publication.py` before an upload. The checker verifies
the exported file list and hashes, rejects unexpected files/directories,
symlinks/hardlinks and non-text files, and checks recognizable credential,
personal-path and account-ID patterns. It prints locations and categories,
not suspected values. The ignore file denies files not explicitly listed.

These measures do not prove that all secrets are absent. Hashes record reviewed
bytes; the manifest is not signed and is not an independent trust anchor. The
checker does not inspect Git history, remotes, staged content different from
the working tree, external systems or arbitrary private strings. Ignore rules
do not protect files already tracked, and forced staging can bypass them.

Only publish the reviewed project directory. Do not upload the parent working
area, a whole home directory, a raw diagnostic archive or `.git` contents.
No credentials are needed to run the local source audit. Do not paste tokens
into commands, issue bodies, screenshots or logs to troubleshoot an upload.

## Reporting a security issue

The source repository is
[ff7rebirth-bc250-workaround-bazzite](https://github.com/saurabh9651/ff7rebirth-bc250-workaround-bazzite).
A private reporting route has not been verified; the owner should provide one
before inviting sensitive reports. Do not put live credentials or raw crash dumps in
a public issue. If material is exposed, remove public access and rotate affected
credentials through their provider; deleting a working-tree file does not erase
Git history or already downloaded copies.

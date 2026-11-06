# 0004: Separate public source from private working state

Status: adopted, November 6, 2026.

Moving the active launcher/build would break embedded absolute paths, while
uploading the working area could expose raw logs, paths, session memory or
credentials. Keep the active workspace in place and export a separate source
snapshot through an explicit list.

Private handoff notes and user session observations stay outside that snapshot.
Public decisions describe the architecture without copying private transcripts.
Deny-by-default Git ignore rules, a file-hash manifest, unexpected-file checks,
file-type/link checks and sensitive-content patterns provide additional review
boundaries. Suspected values are never echoed by the scanner.

These checks do not certify the absence of secrets, inspect Git history, select
a visibility/license, or authorize an upload. Do not add automatic publication
workflows or credentials to make the snapshot appear ready for a release.

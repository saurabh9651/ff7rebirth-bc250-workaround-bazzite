# Preparing a GitHub upload

These instructions cover reviewed source publication, not a tested binary
release. Source preparation does not initialize Git, change visibility, select
identity or licensing, or upload anything by itself. Syncing to a remote is a
separately authorized operation.

## Folder to publish

If you received the complete working area, publish only the contents of
`github-repo/`. Never use its parent as the upload root. Local session memory,
driver builds, raw logs and machine-specific launch commands belong outside it.
If you received only the source archive, its project directory is the source
root. Keep `.git` metadata out of web/file uploads.

## Manual browser upload

Upload the **contents** of the reviewed folder into the repository root, keeping
`docs/`, `tests/` and `tools/` intact. Include `.gitignore` and `.containerignore`;
hidden files can be missed when selecting files in a file manager. Include the
manifest and all expected files so the source audit can detect omissions.
The source ZIP beside the upload folder is for convenience; upload its extracted
contents if you want a browsable source repository, rather than only the ZIP.

After uploading, download a fresh copy and run the audit and tests below. Browser
uploads or some archive workflows may not retain executable permission bits.
The README includes a `chmod +x` step for the project scripts; run it before
using `./setup-driver.sh` or the Steam launcher. If using Git later, preserve
the executable modes of the shell scripts and `diagnostics.py` in the commit.

No private session report, Reddit account details beyond explicitly credited
public authors, or MCP configuration/token should be added to the upload.

## Before the first upload

1. Review README, COMMUNITY_GUIDE, SECURITY, NOTICE and the actual source files.
   Preserve the distinction between host preflight success and user-confirmed
   gameplay. Do not add personal session reports automatically.
2. Run the source checks from this directory:

   ```bash
   python3 -B tools/audit_publication.py
   python3 -B -m unittest -v test_diagnostics.py
   python3 -B -m unittest discover -s tests -v
   bash -n setup-driver.sh container-build.sh check-driver.sh launch-rebirth.sh
   ```

3. Choose the intended GitHub repository and visibility explicitly. Keep source
   private during review if public release is not yet intended. Do not infer
   public visibility from an intent to use GitHub.
4. Choose the license and author identity intentionally; NOTICE records the
   current undecided status. Do not copy an upstream project's license and
   imply that it licenses all new code or bundled dependencies automatically.
5. If Git is initialized, inspect the staged filenames and staged diff before
   committing or pushing. Confirm that no builds, logs, credentials, personal
   paths or machine-specific files are staged. The audit checks the working
   tree, not a different index or prior commits. Existing history needs separate
   review. Ignore rules do not remove already tracked files.
6. Re-run the audit immediately before the upload and verify the selected remote
   and visibility. Do not include credentials in a remote URL. Use an authorized
   authentication mechanism without exposing tokens in project files.

No GitHub Actions workflow is included. If one is added later, review the exact
permissions, dependency/action pins and pull-request trust boundaries first.
Do not execute an experimental GPU driver build with privileged host access
or repository secrets merely to automate publication.

## Maintaining the snapshot

The original private working area has an explicit-list exporter named
`prepare-github.py`. It checks source content before generating this snapshot,
keeps clean earlier exports in private backups, and refuses modified snapshots
or replacement of an initialized Git repository. The resulting manifest records
all expected source hashes; it is not signed.

For a repository maintained directly, review and intentionally update its file
allowlist/ignore rules/hash manifest when files change. Do not treat regenerating
a manifest as approval of an unreviewed change. Re-run tests and inspect the
payload after every such update. Pattern checks cannot identify every secret.

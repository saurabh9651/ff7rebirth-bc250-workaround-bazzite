# FF7 Rebirth: separate BC-250 driver

Prepared for native Steam on Bazzite 43, with Mesa 26.2.1 plus the stable
DirectMesh v1.3.1 patch. This is an experimental per-game driver build.

## Current status

The driver compiled successfully on November 6. The first host enumeration
failed because the build used libdrm 2.4.134 while Bazzite loaded 2.4.131, which
does not implement Mesa's new PRT software query. Setup now exports matching
libdrm and expat libraries beside the driver; checks and launches select these
through a process-local library path. No system libraries are replaced.

The matching libraries have now been exported from the existing builder image,
and host file/dependency and Vulkan capability checks pass with those private
copies selected (November 6, 2026). See
[COMMUNITY_GUIDE.md](COMMUNITY_GUIDE.md) for the observed gameplay results and
the two setup failures fixed along the way.

For repository publication, use only the reviewed source snapshot and read
`docs/PUBLISHING.md`, `SECURITY.md` and `NOTICE.md` in that snapshot. Private
workspace memory, raw diagnostics, generated launch commands and driver builds
are excluded. The source repository is
[ff7rebirth-bc250-workaround-bazzite](https://github.com/saurabh9651/ff7rebirth-bc250-workaround-bazzite).
See NOTICE for the current original-code license status. Preparing source does
not change repository visibility or upload local diagnostic data.

The owner has now confirmed a roughly 26-minute gameplay session in Steam
Gaming Mode with Proton 11.0-2e, at 1440p Medium with VSync and FSR upscaling.
They reported some initial hitching and then quit normally. An earlier Desktop
Mode attempt froze the machine after about three minutes and required a reboot.
These are separate observed outcomes; the cause of the freeze is not established.
This is an initial working report, not a full-game stability test or FPS
benchmark. A Wine assertion was recorded during the normal exit.
Other machines still need their own preflight and gameplay checks.

## Credits and AI assistance

Huge thanks to **lonewolf0622** for DirectMesh, **luckiskind** for BC-250 RADV
work credited upstream, the original Reddit OP and **vogar345** for the earlier
breakthrough, and the Mesa/RADV/ACO, Wine/Proton/vkd3d-proton, libdrm, expat,
Fedora and Bazzite contributors. See [CREDITS.md](CREDITS.md) for links and scope.

I am not a developer/programmer. Much of these helper scripts and documentation
was AI-assisted, or "vibe coded," with Codex, then tested on my own BC-250.
The upstream developers deserve the credit for the driver capabilities. This
repository packages a Bazzite setup path, private runtime handling, checks and
diagnostics around their work. A working session and passing helper tests do
not establish long-term driver stability or a professional security review.

## Run once in Bazzite's terminal

```bash
cd /path/to/ff7rebirth_bc250_work
chmod +x setup-driver.sh container-build.sh check-driver.sh launch-rebirth.sh diagnostics.py tools/audit_publication.py
./setup-driver.sh
```

The permission step also covers archives or browser uploads that did not retain
executable bits. It changes only the named project scripts.

The script downloads the official Mesa 26.2.1 source archive and the stable
release patch, verifies the archive against Mesa's published SHA256, verifies
the patch against its release's SHA256SUMS, and applies it with Git's exact
context checks. It uses Bazzite's existing Git; no host `patch` package is needed.
The patch checksum comes from the same HTTPS release as the patch; this checks
integrity, not an independent signature. It never substitutes a newer patch.

It builds a rootless Fedora 43 container image containing development packages,
then compiles the driver in a container with networking disabled and only its
workspace output mounted. Podman uses its normal user image storage. The build
uses two jobs by default to limit memory pressure; it may take a while.
To change this: `BC250_BUILD_JOBS=3 ./setup-driver.sh`.

No sudo or system-package installation is used on the host. No kernel, BIOS,
system driver, Steam configuration, game files, or Proton prefix is changed by
setup. Build output and logs are under `.directmesh/`. SELinux may relabel that
generated directory for its container bind mount.

Setup checks host dependencies and Vulkan enumeration, including the BC-250
device ID, Mesa version, mesh/task features, and barycentric extension. Only
after all those checks pass does it write `steam-launch-option.txt`.
Dependency checks confirm that the private libdrm/expat copies are selected.
Their hashes are checked before GPU enumeration and every game launch.
`./check-driver.sh --files-only` checks library loading without accessing the
GPU and does not mark the driver as ready for gameplay.

If setup fails, stop there and inspect the build log before proceeding. Logs are in
`.directmesh/logs/build-*.log`; Meson's own log is under
`.directmesh/mesa-26.2.1/build/meson-logs/`. A failed source extraction/patch is
kept for inspection. Re-running setup reuses verified downloads and the build.

## Launch Rebirth after setup passes

1. Open Steam → FF7 Rebirth → Properties → General → Launch Options.
2. Copy the exact line printed by setup, also in `steam-launch-option.txt`.
   Replace any earlier experimental launch options for this first test.
3. Keep the currently selected Proton for the first comparison.
4. Launch and start with 720p or 1080p Low. Report the precise result: DX12
   warning, shader-compilation failure, menu, actual gameplay, or GPU hang.
   Report the selected Proton version too. Getting to the menu alone is not a
   successful gameplay test. This experimental driver can still hang the GPU.

The launcher selects the separate driver only for this game, explicitly enables
DirectMesh, clears inherited feature-level/shader-model spoofing and RADV debug
overrides for a controlled first test, and enables Proton logging. Its environment
changes apply only to the game process. It preserves Steam's command arguments.
The first launch can compile shaders and stutter. Test without additional graphics
mods initially; this setup does not install or remove any mods.

Logs are under `.directmesh/logs/proton/<session-id>/`. The launcher now records
session start/end, elapsed time, exit code/signal, and a 15-second heartbeat.
It also captures console output, Proton logs, and available relevant kernel and
coredump journal messages. Tracking includes menus and loading; it does not
measure active play or establish why a game exited. Logs stay local.

```bash
./diagnostics.py stats      # accumulated recorded session time
./diagnostics.py report     # structured summary of the latest tracked session
./diagnostics.py recover    # journal recovery after a reboot/killed launcher
./diagnostics.py bundle     # local source-only archive for others
```

The report excludes raw logs, personal paths and Steam IDs; review it before
sharing. Raw logs and Proton crash reports can contain sensitive data. A hard
lock or power loss may leave only the last saved heartbeat; no exact end time or
crash cause is fabricated. Journal evidence may be unavailable without access
or persistent storage. Logs are not automatically deleted and can grow.

When asking for help, describe what happened and review a structured report
before sharing it; keep raw logs local unless specifically reviewed. Keep this
workspace in place while using the launch option. No launch-option change or
driver rebuild is needed for these logging improvements.

When a reviewed GitHub snapshot is available, the archive uses its explicit
manifest and re-audits a clean staging copy. This includes the security policy
and public decisions while keeping private workspace files out.

If the kernel changes, rerun `./check-driver.sh` before launching again.
To print the launch option manually: `./launch-rebirth.sh --print-launch-option`.

## Roll back

Remove this launch option from Rebirth's Steam properties. Subsequent launches
use the ordinary driver again. No reboot or system-driver reinstall is needed.
Proton normally writes game/prefix/cache data when the game runs; this setup
does not snapshot or delete those files.

## Sources

- [DirectMesh v1.3.1 release](https://github.com/lonewolf0622/bc250meshtaskwork/releases/tag/directmesh-v1.3.1)
- [DirectMesh project: game results and build instructions](https://github.com/lonewolf0622/Mesh-Shaders-for-Rdna-1-)
- [Mesa 26.2.1 published archive checksum](https://docs.mesa3d.org/relnotes/26.2.1.html)
- [Mesa: selecting a local Vulkan build](https://docs.mesa3d.org/install.html#vulkan)

Read-only baseline observed November 6, 2026: Bazzite Deck 43 image
43.20260211.0, kernel 6.17.7-ba29.fc43.bc250cu.x86_64, Mesa 26.0.0,
GPU 1002:13fe, Steam Rebirth build 23447986. Exact kernel/driver/game
compatibility remains to be established by the host checks and gameplay test.

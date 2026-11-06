# FF7 Rebirth on BC-250 / Bazzite: reproducible test path

This is a community experiment, not a supported driver release. As of November
6, 2026 the driver builds and enumerates the BC-250 with mesh/task shaders on
this machine, and the owner has **confirmed actual gameplay** using Proton
11.0-2e in Steam Gaming Mode. The owner played for about 26 minutes at 1440p
Medium with VSync and FSR, reported initial hitching, and quit normally. An
earlier Desktop Mode attempt froze the machine after about three minutes and
required a restart. The freeze's cause and any general effect of launch mode
are not established. Sustained stability, rendering correctness across the
game and FPS have not been established.

## What has actually been established

| Item | Observed result |
| --- | --- |
| GPU | Cyan Skillfish / BC-250, PCI 1002:13fe |
| OS | Bazzite Deck 43, image 43.20260211.0 |
| Kernel | 6.17.7-ba29.fc43.bc250cu.x86_64, retained throughout |
| Original Mesa / libdrm | 26.0.0 / 2.4.131 |
| Separate Mesa | Official 26.2.1 archive plus stable DirectMesh v1.3.1 |
| Patch integrity | Pinned SHA256 6669d4644d9a00ad8da022dd2716c59e4d235a2c6f0eb4f272c9c8d9fbcc9b77 |
| Build environment | Rootless Fedora 43 container; libdrm 2.4.134 |
| Vulkan preflight | Passed on the host after selecting private libdrm/expat |
| Game | Steam app 2909400, build 23447986 at setup time |
| Proton in the working report | proton-11.0-2e-x86_64 |
| Gameplay | Confirmed by the owner after using the separate driver |
| Successful launch environment | Steam Gaming Mode, after reboot |
| Owner-reported settings | 1440p, Medium, VSync enabled, FSR upscaling; FSR preset not specified |
| Observed session | About 26 minutes, initial hitching, normal user exit |
| Desktop Mode attempt | Whole-machine freeze after about three minutes; reboot required |
| Extended stability / FPS | Not established; no FPS/frametime measurement was collected |

## Problems encountered and fixes retained

1. The release checksum names its patch `patches/bc250-directmesh-mesa-26.2.1.patch`.
   The parser originally expected a plain filename. The downloaded bytes matched;
   the parser was fixed, and the known patch digest is now also pinned separately.
2. The first completed build failed GPU enumeration with
   `amdgpu_query_sw_info(amdgpu_sw_info_address_prt_wa_control_bit) failed`.
   The container built against libdrm 2.4.134; the host loaded 2.4.131, whose
   software-query implementation rejects this query. Setup now exports matching
   libdrm, libdrm_amdgpu, and expat from the build image into a private runtime.
   Preflight checks which copies are actually loaded. No Mesa capability checks
   were bypassed, and the GPU query itself was not patched out.
3. Initial session journal collection rejected the UUID-form boot descriptor.
   The collector now uses compact hexadecimal boot IDs, removes Steam loader
   injections from journal helper processes, and refuses unscoped queries if
   no valid boot ID was recorded. Existing evidence can be recovered locally.
   Error summaries now count Wine assertions and exception-dispatch failures
   even when the supervised command returns exit code zero. Such counts are
   evidence to investigate, not proof that gameplay crashed.

The successful Gaming Mode session also logged a Wine assertion near teardown;
the owner confirms they quit normally. Preserve that warning without labelling
this session an unexpected gameplay crash. The earlier Desktop Mode freeze left
an incomplete heartbeat record; scoped journal recovery found no relevant GPU
or coredump messages. A hard lock can prevent those messages from being saved.

## Follow the path on another machine

1. Extract the source archive into your own writable directory. Read the scripts
   and README. Use native Steam and a working BC-250 desktop/gaming setup.
2. In a normal terminal, enter that directory and run `./setup-driver.sh` without
   sudo. It downloads and checks the pinned sources, builds in a container, and
   checks host dependencies and Vulkan features. Generated data stays under
   `.directmesh`; Podman also uses its ordinary user container storage.
3. Continue only when the checks pass. Copy the exact launch option printed for
   your own directory. Keep the directory in place while using that option.
4. Use Steam Gaming Mode for the first comparison with this report. The observed
   working configuration followed a reboot; Desktop Mode froze this machine.
   This is a tested starting point, not proof that mode alone caused either
   outcome. Start with your chosen Proton and 720p/1080p Low if desired; the
   owner-reported successful settings were 1440p Medium, VSync and FSR.
   Record the Proton version,
   resolution, settings, and whether the game reaches actual gameplay. Test one
   change at a time, without extra graphics mods initially.
5. Use `./diagnostics.py stats` for measured session time and
   `./diagnostics.py report` for a small structured result to review and share.
   Results from other kernels, boards, Proton versions, or unlocked hardware
   should be recorded separately rather than assumed to match this machine.

Removing the Steam launch option restores ordinary driver selection. No BIOS,
kernel, system driver, global library path, or global Steam setting is changed.
The experimental driver can still hang a GPU; these checks establish startup
capabilities, not sustained stability. Keep other work saved during testing.

## What the session tracker does

The existing Steam option invokes the updated launcher automatically. Each run
gets a private directory at `.directmesh/logs/proton/<session-id>/` containing:

- `session.json`: start/end UTC times, monotonic elapsed time, exit code/signal,
  15-second heartbeat, selected versions and driver hashes.
- `console.log` and `steam-2909400.log`: launcher/Proton/Wine errors and output.
- `kernel.log`: available relevant GPU/DRM/OOM messages for this boot and session.
- `coredumps.log`: available relevant journal coredump metadata, not binary cores.
- `errors.log`: selected error lines from the final 4 MiB of each top-level log.
- `crash-reports/`: crash reports produced by Proton when available. These can
  contain private information or binary data; they stay local.

Tracking measures the supervised Steam/Proton command's lifetime, including
loading, menus and pauses. It is not an active-play detector. If a command detaches
the game and exits early, timing can undercount. Exit zero does not prove the game
did not crash, and nonzero does not prove a driver fault. Logs supply evidence.

After a reboot or killed launcher, run `./diagnostics.py recover` to try collecting
journal evidence from the recorded boot. Persistent journal access is required;
the script never asks for sudo or changes journal settings. An unfinished session
remains `incomplete`, with its last saved duration as a lower bound. A hard GPU
hang or power loss may prevent final records or error messages from reaching disk.

Logging uses error/exception channels instead of verbose tracing. It can still
affect performance and consume disk space. Logs and dumps are not deleted
automatically. Close the game before archiving or removing old session folders;
removing folders also removes their contribution to tracked totals.

## Sharing

`./diagnostics.py report` writes a JSON summary under `.directmesh/reports/`.
It includes versions, hashes, duration, exit status, and known error-signature
counts. It excludes raw logs, home paths, Steam IDs, command arguments, process
IDs, boot IDs, and crash memory. Review any report before sharing it. Raw error
messages remain local for investigation; no automatic redaction guarantee is
made for those raw logs or Proton crash reports.

`./diagnostics.py bundle` creates `community/ff7rebirth-bc250-source.tar.gz`
and a SHA256 file. When a reviewed publication snapshot is available, it audits
a clean copy of the manifest's source files before archiving them. The original
explicit list remains available for older standalone setups. It includes only
source scripts, tests and guides. It excludes driver binaries, build directories, session logs,
Steam data, downloaded assets, container storage, and local manifests. Nothing
is uploaded or published. The source archive itself is not a signed release.

For GitHub publication, read the snapshot's `docs/PUBLISHING.md`, `SECURITY.md`
and `NOTICE.md`. Local session memory and raw diagnostics must stay outside the
repository. The setup does not choose repository visibility, author identity
or a new-code license, and does not upload diagnostic data.

## Upstream references

- [DirectMesh stable v1.3.1](https://github.com/lonewolf0622/bc250meshtaskwork/releases/tag/directmesh-v1.3.1)
- [Mesa 26.2.1 archive checksum](https://docs.mesa3d.org/relnotes/26.2.1.html)
- [Proton logging options](https://github.com/ValveSoftware/Proton#runtime-config-options)
- [vkd3d-proton debug variables](https://github.com/HansKristian-Work/vkd3d-proton#environment-variables)

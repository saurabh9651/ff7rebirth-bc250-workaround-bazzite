# 0001: Isolate a stable driver build per game

Status: adopted, November 6, 2026.

FF7 Rebirth rejected the BC-250's original exposed graphics capabilities.
Community work added mesh/task support to RADV. The selected baseline is clean
Mesa 26.2.1 plus stable DirectMesh v1.3.1; the upstream author lists Rebirth as
tested, while earlier spoofing/R2 approaches carried extra compatibility issues.

Build in a rootless Fedora container, verify the pinned source hashes, and select
the resulting Vulkan manifest only through this game's launcher. Preserve the
kernel, BIOS, system drivers and global Steam settings. Do not patch out feature
checks to claim success. Removing the launch option restores ordinary selection.

Host Vulkan preflight has passed on the documented machine, and its owner later
confirmed actual gameplay with Proton 11.0-2e. That initial report does not
establish rendering correctness across the game, sustained stability, FPS, or
performance on another board. See COMMUNITY_GUIDE for the observed baseline.

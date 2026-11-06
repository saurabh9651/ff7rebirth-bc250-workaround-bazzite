# Credits and thanks

This Bazzite setup is possible because of upstream driver and compatibility work.
Thank you to the developers and community members who made it possible to run
these games on the BC-250 and shared their findings openly.

## Driver work used directly

- **lonewolf0622 — DirectMesh**: this project builds Mesa 26.2.1 with the
  [stable DirectMesh v1.3.1 patch](https://github.com/lonewolf0622/bc250meshtaskwork/releases/tag/directmesh-v1.3.1).
  The [current upstream repository](https://github.com/lonewolf0622/Mesh-Shaders-for-Rdna-1-)
  documents the BC-250 mesh/task shader implementation. The driver capability
  comes from this upstream work; our helper scripts do not implement it.
- **Mesa / RADV / ACO contributors**: the graphics driver and shader compiler
  foundation. [Mesa project](https://www.mesa3d.org/).

## Earlier breakthroughs and upstream acknowledgements

- **The original Reddit OP, Primary_Vegetable782, and everyone testing in the
  [FF7 Rebirth working thread](https://www.reddit.com/r/BC250Gaming/comments/1v34ana/ff7_rebirth_working/)**:
  sharing the early success and troubleshooting reports helped establish a path.
- **vogar345 — [Bc250-radeon-patch](https://github.com/vogar345/Bc250-radeon-patch)**:
  the earlier Rebirth workaround linked from that thread. Our selected build
  uses stable DirectMesh rather than that earlier patch, but the breakthrough
  and shared testing deserve acknowledgement.
- **luckiskind — [bc250-radv-r2](https://github.com/luckiskind/bc250-radv-r2)**:
  BC-250 RADV mesh work acknowledged in DirectMesh's own credits. We do not
  install the separate R2 package or its patched Proton in this setup.

## Supporting projects

Thanks also to the **Wine**, **Proton**, **vkd3d-proton**, **libdrm**, **expat**,
**Fedora**, **Bazzite**, and broader BC-250 communities and their contributors.
They provide the operating-system, build, driver-runtime and compatibility
components on which this setup depends. This acknowledgement does not imply
their endorsement or support for these helper scripts.

## Scope of this repository and AI disclosure

The maintainer is **not a developer/programmer**. Much of the helper scripting
and documentation was **AI-assisted ("vibe coded") with Codex** and tested on
one BC-250. Our contribution is the documented Bazzite/container build path,
private matching-runtime selection, preflight checks, session/error logging,
and a reviewed source-export workflow around upstream work.

Please direct credit for mesh shader support to its upstream authors. Review
these helpers before using them, preserve upstream attribution, and report
results with their limits. The successful initial session is not a substitute
for broader hardware, stability or security testing. License status and upstream
terms are recorded in [NOTICE.md](NOTICE.md).

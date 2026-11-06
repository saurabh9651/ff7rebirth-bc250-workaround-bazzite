# 0002: Carry matching runtime libraries privately

Status: adopted, November 6, 2026.

Mesa built against libdrm 2.4.134 failed GPU enumeration when the host loaded
2.4.131. The host implementation rejected the new PRT software query. An expat
symbol-version warning also showed a build/runtime mismatch.

Export the builder's libdrm.so.2, libdrm_amdgpu.so.1 and libexpat.so.1 beside the
driver. Verify their hashes and the paths actually selected by the host dynamic
linker. Use a process-local library path for preflight and the game; do not
replace system libraries or suppress the failing GPU query.

This fixed enumeration on the documented host. Other host/dependency combinations
still need their own checks. The private bundle is not a redistributable binary
release and is excluded from publication.

#!/usr/bin/env bash
set -Eeuo pipefail
SOURCE=${1:?Pass the absolute Mesa source directory}
cd -- "$SOURCE"
OPTIONS=(
    -Dvulkan-drivers=amd -Dgallium-drivers= -Dplatforms=x11,wayland
    -Dbuildtype=release -Dllvm=disabled -Dvideo-codecs=
    -Dglx=disabled -Degl=disabled -Dopengl=false
    -Dgles1=disabled -Dgles2=disabled -Dbuild-tests=false
    -Dvalgrind=disabled -Dlmsensors=disabled
)
if [[ -f build/meson-private/coredata.dat ]]; then
    meson setup --reconfigure build --wrap-mode=nofallback "${OPTIONS[@]}"
else
    meson setup build --wrap-mode=nofallback "${OPTIONS[@]}"
fi
ninja -C build -j "${BC250_BUILD_JOBS:-2}" \
    src/amd/vulkan/libvulkan_radeon.so \
    src/amd/vulkan/radeon_devenv_icd.x86_64.json
# Mesa 26.2 uses a software query unavailable in Bazzite's libdrm 2.4.131.
# Export the matching userspace libraries for this game instead of changing /usr.
python3 -B "$SOURCE/../runtime-libraries.py" bundle /usr/lib64 \
    "$SOURCE/../runtime" --libdrm-version "$(pkg-config --modversion libdrm_amdgpu)"
# Deliberately no meson install / ninja install step.

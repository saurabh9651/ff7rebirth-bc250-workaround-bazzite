FROM registry.fedoraproject.org/fedora:43

# Build dependencies stay in this rootless container image.
RUN dnf -y install \
      gcc gcc-c++ meson ninja-build cmake pkgconf-pkg-config \
      python3 python3-mako python3-pyyaml python3-packaging python3-ply \
      bison flex glslang glslang-devel spirv-tools-devel \
      libdrm-devel elfutils-libelf-devel expat-devel zlib-ng-compat-devel \
      libzstd-devel libX11-devel libXext-devel libXfixes-devel \
      libXrandr-devel libXxf86vm-devel libxcb-devel libxshmfence-devel \
      wayland-devel wayland-protocols-devel systemd-devel libdisplay-info-devel \
    && dnf clean all

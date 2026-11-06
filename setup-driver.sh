#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
WORK="$ROOT/.directmesh"
MESA_VERSION=26.2.1
# Published by Mesa: https://docs.mesa3d.org/relnotes/26.2.1.html
MESA_SHA256=c47e81bddc4760360a41ac3c5acec38acb81f9d750ecef47e7f3adc7021a4442
RELEASE=directmesh-v1.3.1
PATCH=bc250-directmesh-mesa-26.2.1.patch
PATCH_SHA256=6669d4644d9a00ad8da022dd2716c59e4d235a2c6f0eb4f272c9c8d9fbcc9b77
RELEASE_URL="https://github.com/lonewolf0622/bc250meshtaskwork/releases/download/$RELEASE"
IMAGE=localhost/ff7rebirth-bc250-builder:f43

usage() {
    cat <<'EOF'
Usage: ./setup-driver.sh [--check-environment | --help]

Build Mesa 26.2.1 + DirectMesh v1.3.1 in a rootless Fedora 43 container,
then check the separate driver on the host. Run from Bazzite's terminal.
Build output, downloads and logs go into .directmesh next to this script.
Podman also stores its container image in your normal user container storage.
No sudo, system-driver installation, kernel changes or Steam edits are used.

BC250_BUILD_JOBS=2 by default. Set it to another positive integer if needed.
EOF
}

check_environment() {
    local failed=0 cmd
    for cmd in bash curl python3 sha256sum tar git flock podman ldd vulkaninfo timeout; do
        if command -v "$cmd" >/dev/null; then
            printf 'Available: %s\n' "$cmd"
        else
            printf 'Missing command: %s\n' "$cmd" >&2
            failed=1
        fi
    done
    if compgen -G '/dev/dri/renderD*' >/dev/null; then
        printf 'GPU render device is visible.\n'
    else
        printf 'No GPU render device is visible in this session.\n' >&2
        failed=1
    fi
    if command -v python3 >/dev/null; then
        if ! python3 -B - <<'PY'
import socket, sys
for host in ('archive.mesa3d.org', 'github.com', 'registry.fedoraproject.org'):
    try:
        socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        print('DNS available: ' + host)
    except OSError as exc:
        print('DNS unavailable: ' + host + ': ' + str(exc), file=sys.stderr)
        sys.exit(1)
PY
        then
            failed=1
        fi
    fi
    return "$failed"
}

case "${1:-}" in
    --help|-h) usage; exit 0 ;;
    --check-environment) check_environment; exit $? ;;
    '') ;;
    *) usage >&2; exit 2 ;;
esac
[[ $# -eq 0 ]] || { usage >&2; exit 2; }
[[ $EUID -ne 0 ]] || { printf 'Run as your normal user, without sudo.\n' >&2; exit 1; }
[[ $(uname -m) == x86_64 ]] || { printf 'This build is for x86_64 only.\n' >&2; exit 1; }
check_environment || { printf '\nRun this script in the Bazzite host terminal with internet access.\n' >&2; exit 1; }
JOBS=${BC250_BUILD_JOBS:-2}
[[ $JOBS =~ ^[1-9][0-9]*$ ]] || { printf 'BC250_BUILD_JOBS must be a positive integer.\n' >&2; exit 2; }

mkdir -p "$WORK/downloads" "$WORK/logs"
exec 9>"$WORK/build.lock"
flock -n 9 || { printf 'Another driver build is already running.\n' >&2; exit 1; }
BUILD_LOG="$WORK/logs/build-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee -a "$BUILD_LOG") 2>&1
trap 'printf "\nStopped at line %s. Build log: %s\n" "$LINENO" "$BUILD_LOG" >&2' ERR
printf 'Building Mesa %s with %s; parallel jobs: %s\n' "$MESA_VERSION" "$RELEASE" "$JOBS"

download() {
    local url=$1 destination=$2
    if [[ ! -f $destination ]]; then
        curl --fail --location --retry 3 --connect-timeout 20 --max-time 900 \
            --proto '=https' --proto-redir '=https' \
            --output "$destination.part" "$url"
        mv -- "$destination.part" "$destination"
    fi
}

ARCHIVE="$WORK/downloads/mesa-$MESA_VERSION.tar.xz"
download "https://archive.mesa3d.org/mesa-$MESA_VERSION.tar.xz" "$ARCHIVE"
printf '%s  %s\n' "$MESA_SHA256" "$ARCHIVE" | sha256sum --check --status
download "$RELEASE_URL/SHA256SUMS" "$WORK/downloads/SHA256SUMS"
download "$RELEASE_URL/$PATCH" "$WORK/downloads/$PATCH"
printf '%s  %s\n' "$PATCH_SHA256" "$WORK/downloads/$PATCH" | sha256sum --check --status
# Validate just this asset; other release assets are intentionally not downloaded.
python3 -B - "$WORK/downloads/SHA256SUMS" "$WORK/downloads/$PATCH" <<'PY'
import hashlib, pathlib, re, sys
checksums, patch = map(pathlib.Path, sys.argv[1:])
matches = []
expected_names = {patch.name, 'patches/' + patch.name}
for line in checksums.read_text().splitlines():
    match = re.fullmatch(r'([0-9a-fA-F]{64})\s+\*?(.+)', line)
    if match and match[2].removeprefix('./') in expected_names:
        matches.append(match[1].lower())
actual = hashlib.sha256(patch.read_bytes()).hexdigest()
if len(matches) != 1:
    sys.exit('Expected exactly one release checksum for ' + patch.name +
             '; found ' + str(len(matches)) + '. Nothing was built.')
if matches[0] != actual:
    sys.exit('Release patch checksum mismatch: expected ' + matches[0] +
             ', got ' + actual + '. Nothing was built.')
print('Verified DirectMesh patch SHA256: ' + actual)
PY

SOURCE="$WORK/mesa-$MESA_VERSION"
PATCH_HASH=$(sha256sum "$WORK/downloads/$PATCH")
PATCH_HASH=${PATCH_HASH%% *}
if [[ -e $SOURCE ]]; then
    [[ -f $SOURCE/.bc250-patch-sha256 ]] && \
        [[ $(cat "$SOURCE/.bc250-patch-sha256") == "$PATCH_HASH" ]] || {
        printf 'Existing source is not marked for this patch: %s\n' "$SOURCE" >&2
        printf 'Preserve or move it before trying again. It has not been overwritten.\n' >&2
        exit 1
    }
else
    STAGE=$(mktemp -d "$WORK/extract.XXXXXX")
    tar --extract --xz --file "$ARCHIVE" --directory "$STAGE" \
        --no-same-owner --no-same-permissions
    [[ $(tr -d '\r\n' < "$STAGE/mesa-$MESA_VERSION/VERSION") == "$MESA_VERSION" ]]
    (
        cd -- "$STAGE/mesa-$MESA_VERSION"
        git apply --check "$WORK/downloads/$PATCH"
        git apply "$WORK/downloads/$PATCH"
        printf '%s\n' "$PATCH_HASH" > .bc250-patch-sha256
    )
    mv -- "$STAGE/mesa-$MESA_VERSION" "$SOURCE"
    rmdir -- "$STAGE"
fi

# Package installation happens inside the image, never in Bazzite's /usr.
podman build --tag "$IMAGE" --file "$ROOT/Containerfile" "$ROOT"
cp -- "$ROOT/container-build.sh" "$WORK/container-build.sh"
cp -- "$ROOT/runtime-libraries.py" "$WORK/runtime-libraries.py"
# Keep the absolute host path inside the container: Meson's ICD embeds this path.
podman run --rm --userns=keep-id --user "$(id -u):$(id -g)" \
    --cap-drop=all --security-opt=no-new-privileges --network=none \
    --volume "$WORK:$WORK:Z" --workdir "$SOURCE" \
    --env "BC250_BUILD_JOBS=$JOBS" "$IMAGE" \
    bash "$WORK/container-build.sh" "$SOURCE"

python3 -B - "$SOURCE" "$WORK/driver.json" "$PATCH_HASH" <<'PY'
import hashlib, json, pathlib, sys
source, output = map(pathlib.Path, sys.argv[1:3])
directory = source / 'build/src/amd/vulkan'
driver = directory / 'libvulkan_radeon.so'
icd = json.loads((directory / 'radeon_devenv_icd.x86_64.json').read_text())
if not driver.is_file():
    sys.exit('Expected driver library was not built.')
library_path = pathlib.Path(icd['ICD']['library_path'])
if not library_path.is_absolute() or library_path.resolve() != driver.resolve():
    sys.exit('Build ICD does not reference the expected absolute host library path.')
icd['ICD']['library_arch'] = '64'
icd['file_format_version'] = '1.0.1'
output.write_text(json.dumps(icd, indent=2) + '\n')
provenance = {
    'mesa_version': '26.2.1', 'release': 'directmesh-v1.3.1',
    'mesa_archive_sha256': 'c47e81bddc4760360a41ac3c5acec38acb81f9d750ecef47e7f3adc7021a4442',
    'patch_sha256': sys.argv[3],
    'library_path': str(driver),
    'library_sha256': hashlib.sha256(driver.read_bytes()).hexdigest(),
}
(output.parent / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
PY

bash "$ROOT/check-driver.sh"
OPTION=$(bash "$ROOT/launch-rebirth.sh" --print-launch-option)
printf '%s\n' "$OPTION" > "$ROOT/steam-launch-option.txt"
printf '\nDriver built and Vulkan capability checks passed.\n'
printf 'Rebirth Steam launch option:\n%s\n' "$OPTION"
printf '\nUse your current Proton first, launch Rebirth, and report what happens.\n'
printf 'Logs: %s/logs\n' "$WORK"

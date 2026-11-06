#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
WORK="$ROOT/.directmesh"
FILES_ONLY=0
case "${1:-}" in
    --help|-h)
        printf 'Usage: ./check-driver.sh [--files-only]\nChecks the separate driver on the Bazzite host; saves results under .directmesh/logs.\n'
        exit 0 ;;
    --files-only) FILES_ONLY=1; shift ;;
    '') ;;
    *) printf 'Unknown argument: %s\n' "$1" >&2; exit 2 ;;
esac
[[ $# -eq 0 ]] || exit 2
[[ -f $WORK/driver.json && -f $WORK/provenance.json ]] || {
    printf 'No completed driver build found. Run ./setup-driver.sh first.\n' >&2
    exit 1
}
mkdir -p "$WORK/logs" "$WORK/cache/preflight"
rm -f -- "$WORK/verified.json"
python3 -B "$ROOT/runtime-libraries.py" verify "$WORK/runtime"
RUNTIME_LIB_DIR="$WORK/runtime/lib"
PRIVATE_LIBRARY_PATH="$RUNTIME_LIB_DIR${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
STAMP=$(date +%Y%m%d-%H%M%S)
LIBRARY=$(python3 -B - "$WORK/driver.json" <<'PY'
import json, sys
print(json.load(open(sys.argv[1]))['ICD']['library_path'])
PY
)
[[ -f $LIBRARY ]] || { printf 'Driver library is missing: %s\n' "$LIBRARY" >&2; exit 1; }
env LD_LIBRARY_PATH="$PRIVATE_LIBRARY_PATH" \
    ldd -r "$LIBRARY" > "$WORK/logs/dependencies-$STAMP.txt" 2>&1
cat "$WORK/logs/dependencies-$STAMP.txt"
if grep -Eq 'not found|undefined symbol:' "$WORK/logs/dependencies-$STAMP.txt"; then
    printf 'Host library dependencies are missing. Driver has not been enabled.\n' >&2
    exit 1
fi
python3 -B - "$WORK/logs/dependencies-$STAMP.txt" "$RUNTIME_LIB_DIR" <<'PY'
from pathlib import Path
import re, sys
text = Path(sys.argv[1]).read_text()
directory = Path(sys.argv[2])
for name in ('libdrm.so.2', 'libdrm_amdgpu.so.1', 'libexpat.so.1'):
    match = re.search(re.escape(name) + r'\s+=>\s+(\S+)', text)
    if not match or Path(match[1]).resolve() != (directory / name).resolve():
        sys.exit('Dependency check did not load the private copy of ' + name)
print('PASS: dependency checks load the matching private runtime.')
PY
if [[ $FILES_ONLY -eq 1 ]]; then
    printf 'File and dependency checks passed. GPU has NOT been verified.\n'
    exit 0
fi
compgen -G '/dev/dri/renderD*' >/dev/null || {
    printf 'No GPU render device. Run ./check-driver.sh in the Bazzite host terminal.\n' >&2
    exit 1
}
VULKAN_LOG="$WORK/logs/vulkaninfo-$STAMP.txt"
if ! env -u DISPLAY -u WAYLAND_DISPLAY -u VK_ADD_DRIVER_FILES \
    -u VK_LOADER_DRIVERS_SELECT -u VK_LOADER_DRIVERS_DISABLE \
    -u VK_INSTANCE_LAYERS -u DRI_PRIME -u MESA_VK_DEVICE_SELECT \
    -u RADV_DEBUG -u RADV_PERFTEST -u MESA_LOADER_DRIVER_OVERRIDE \
    VK_DRIVER_FILES="$WORK/driver.json" VK_ICD_FILENAMES="$WORK/driver.json" \
    LD_LIBRARY_PATH="$PRIVATE_LIBRARY_PATH" \
    RADV_DIRECTMESH=1 MESA_SHADER_CACHE_DIR="$WORK/cache/preflight" \
    timeout 90 vulkaninfo > "$VULKAN_LOG" 2>&1; then
    printf 'Vulkan enumeration failed. Details: %s\n' "$VULKAN_LOG" >&2
    tail -n 35 "$VULKAN_LOG" >&2
    exit 1
fi
python3 -B - "$VULKAN_LOG" "$WORK" <<'PY'
import datetime, hashlib, json, pathlib, platform, re, sys
report = pathlib.Path(sys.argv[1])
work = pathlib.Path(sys.argv[2])
text = report.read_text(errors='replace')
checks = {
    'AMD vendor': r'vendorID\s*=\s*0x1002\b',
    'BC-250 device': r'deviceID\s*=\s*0x(?:13fe|143f)\b',
    'Mesa 26.2.1': r'driverInfo\s*=\s*Mesa 26\.2\.1\b',
    'mesh extension': r'\bVK_EXT_mesh_shader\b',
    'barycentric extension': r'\bVK_KHR_fragment_shader_barycentric\b',
    'meshShader feature': r'\bmeshShader\s*=\s*true\b',
    'taskShader feature': r'\btaskShader\s*=\s*true\b',
}
failed = [name for name, pattern in checks.items() if not re.search(pattern, text, re.I)]
for name in checks:
    print(('FAIL: ' if name in failed else 'PASS: ') + name)
if failed:
    sys.exit('Required capabilities were not verified. Report: ' + str(report))
provenance = json.loads((work / 'provenance.json').read_text())
driver = pathlib.Path(provenance['library_path'])
actual = hashlib.sha256(driver.read_bytes()).hexdigest()
if actual != provenance['library_sha256']:
    sys.exit('Driver changed since the build provenance was recorded.')
verified = {
    'library_sha256': actual, 'kernel': platform.release(),
    'runtime_manifest_sha256': hashlib.sha256((work / 'runtime/manifest.json').read_bytes()).hexdigest(),
    'checked_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'report': str(report),
}
(work / 'verified.json').write_text(json.dumps(verified, indent=2) + '\n')
print('Capability checks passed. Gameplay still needs testing.')
PY
OPTION=$(bash "$ROOT/launch-rebirth.sh" --print-launch-option)
printf '%s\n' "$OPTION" > "$ROOT/steam-launch-option.txt"
printf '\nRebirth Steam launch option:\n%s\n' "$OPTION"

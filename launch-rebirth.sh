#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
WORK="$ROOT/.directmesh"
case "${1:-}" in
    --print-launch-option)
        printf '"%s/launch-rebirth.sh" %%command%%\n' "$ROOT"
        exit 0 ;;
    --help|-h|'')
        printf 'Use this script in Rebirth Steam launch options.\n'
        printf 'Print the exact option: ./launch-rebirth.sh --print-launch-option\n'
        exit 0 ;;
esac
for APP_ID in "${SteamAppId:-}" "${STEAM_COMPAT_APP_ID:-}"; do
    if [[ -n $APP_ID && $APP_ID != 2909400 ]]; then
        printf 'This launcher is prepared for FF7 Rebirth (2909400), not app %s.\n' "$APP_ID" >&2
        exit 1
    fi
done
python3 -B "$ROOT/runtime-libraries.py" verify "$WORK/runtime"
python3 -B - "$WORK" <<'PY'
import hashlib, json, pathlib, platform, sys
work = pathlib.Path(sys.argv[1])
try:
    verified = json.loads((work / 'verified.json').read_text())
    icd = json.loads((work / 'driver.json').read_text())
    actual = hashlib.sha256(pathlib.Path(icd['ICD']['library_path']).read_bytes()).hexdigest()
    if actual != verified['library_sha256'] or platform.release() != verified['kernel']:
        raise ValueError('The driver or kernel changed after verification.')
    runtime_hash = hashlib.sha256((work / 'runtime/manifest.json').read_bytes()).hexdigest()
    if runtime_hash != verified['runtime_manifest_sha256']:
        raise ValueError('The private runtime changed after verification.')
except (OSError, ValueError, KeyError) as exc:
    sys.exit('Driver is not verified for this session. Run ./check-driver.sh first. ' + str(exc))
PY
RUN_LOGS="$WORK/logs/proton/$(date +%Y%m%d-%H%M%S)-$$"
mkdir -p "$RUN_LOGS" "$WORK/cache/rebirth"
chmod 700 "$RUN_LOGS"
{
    printf 'Started: %s\nKernel: %s\nDriver manifest: %s\n' \
        "$(date --iso-8601=seconds)" "$(uname -r)" "$WORK/driver.json"
    printf 'DirectMesh: enabled\nProton log directory: %s\n' "$RUN_LOGS"
    printf 'Private runtime: %s/runtime/lib\n' "$WORK"
} > "$RUN_LOGS/launcher.txt"
# Use actual driver capabilities for this baseline, without inherited spoofing.
unset VKD3D_FEATURE_LEVEL VKD3D_SHADER_MODEL RADV_DEBUG RADV_PERFTEST
unset VK_ADD_DRIVER_FILES VK_LOADER_DRIVERS_SELECT VK_LOADER_DRIVERS_DISABLE
unset DRI_PRIME MESA_VK_DEVICE_SELECT MESA_LOADER_DRIVER_OVERRIDE
export VK_DRIVER_FILES="$WORK/driver.json"
export VK_ICD_FILENAMES="$WORK/driver.json"
export RADV_DIRECTMESH=1
export PROTON_LOG=1
export PROTON_LOG_DIR="$RUN_LOGS"
export PROTON_CRASH_REPORT_DIR="$RUN_LOGS/crash-reports"
mkdir -p "$PROTON_CRASH_REPORT_DIR"
# Retain error/exception evidence without Proton's noisier default trace channels.
export WINEDEBUG="${WINEDEBUG:-+timestamp,+pid,+tid,err+all,warn+seh,+debugstr}"
export VKD3D_DEBUG="${VKD3D_DEBUG:-warn}"
export DXVK_LOG_LEVEL="${DXVK_LOG_LEVEL:-warn}"
export DXVK_LOG_PATH="$RUN_LOGS"
export MESA_SHADER_CACHE_DIR="$WORK/cache/rebirth"
export LD_LIBRARY_PATH="$WORK/runtime/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec python3 -B "$ROOT/diagnostics.py" --root "$ROOT" run --log-dir "$RUN_LOGS" -- "$@"

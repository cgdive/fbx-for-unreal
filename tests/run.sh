#!/usr/bin/env bash
# Install the built add-on into each Blender (fresh, isolated user folder) and run smoke.py.
#
#   bash tests/run.sh 4.0 4.2 5.3          # version prefixes
#
# Blender builds are looked up as <root>/blender-<version>*/blender.exe (Blender Launcher layout),
# where <root> comes from $BLENDER_ROOT or the first line of tests/blender_root.txt (git-ignored).
# Optional: $SEND2UE_FBX_B4 = path to Send to Unreal's core/io/fbx_b4.py for the parity check
# (defaults to send2ue/core/io/fbx_b4.py next to this repo's root, if present).
# Needs: bash (Git Bash on Windows), Python 3.11+ on PATH.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
PROJ="$(dirname "$HERE")"
ROOT="${BLENDER_ROOT:-$(head -n1 "$HERE/blender_root.txt" 2>/dev/null | tr -d '\r')}"
[ -z "$ROOT" ] && { echo "Set BLENDER_ROOT or write your Blender folder into tests/blender_root.txt"; exit 1; }
S2U="${SEND2UE_FBX_B4:-$PROJ/send2ue/core/io/fbx_b4.py}"
[ -f "$S2U" ] || S2U=""
winpath() { if command -v cygpath >/dev/null; then cygpath -w "$1"; else echo "$1"; fi; }

( cd "$PROJ" && python -I build.py >/dev/null ) || exit 1
VERSION=$(cd "$PROJ" && python -I -c "import tomllib;print(tomllib.load(open('unreal_fbx_export/blender_manifest.toml','rb'))['version'])") \
    || { echo "could not read the version from blender_manifest.toml"; exit 1; }
ZIP="$PROJ/dist/unreal_fbx_export-$VERSION.zip"
LEGACY="$PROJ/dist/unreal_fbx_export-$VERSION-legacy-4.0-4.1.zip"
WORK="$HERE/.out"; mkdir -p "$WORK"
STATUS=0

for v in "$@"; do
  exe=$(ls -d "$ROOT"/blender-$v*/blender.exe "$ROOT"/blender-$v*/blender 2>/dev/null | head -1)
  [ -z "$exe" ] && { echo "== $v: no Blender found under $ROOT"; STATUS=1; continue; }
  U="$WORK/user_$v"; OUT="$WORK/out_$v"; rm -rf "$U" "$OUT"; mkdir -p "$U"
  export BLENDER_USER_RESOURCES="$(winpath "$U")"
  case "$v" in
    4.0*|4.1*)
      mkdir -p "$U/scripts/addons"
      python -I -c "import zipfile,sys;zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "$LEGACY" "$U/scripts/addons"
      export BLENDER_USER_SCRIPTS="$(winpath "$U/scripts")"
      echo "== $v: legacy add-on installed";;
    *)
      unset BLENDER_USER_SCRIPTS
      "$exe" --factory-startup --command extension validate "$(winpath "$ZIP")" > "$WORK/validate_$v.log" 2>&1
      rc=$?; echo "== $v: extension validate exit $rc"; [ $rc -ne 0 ] && { tail -3 "$WORK/validate_$v.log"; STATUS=1; }
      "$exe" --factory-startup --command extension install-file -r user_default -e "$(winpath "$ZIP")" \
          > "$WORK/install_$v.log" 2>&1;;
  esac
  "$exe" --background --factory-startup --python "$(winpath "$HERE/smoke.py")" -- \
      "$( [ -n "$S2U" ] && winpath "$S2U")" "$(winpath "$OUT")" > "$WORK/smoke_$v.log" 2>&1
  python -I - "$WORK/smoke_$v.log" <<'EOF' || STATUS=1
import json, sys
lines = [l for l in open(sys.argv[1], encoding="utf-8", errors="replace") if l.startswith("RESULT ")]
if not lines:
    print("   NO RESULT (see log)"); sys.exit(1)
r = json.loads(lines[-1][7:])
failed = [(k, d) for k, (ok, d) in r["checks"].items() if not ok]
print(f"   Blender {r['version']}: {len(r['checks']) - len(failed)}/{len(r['checks'])} checks passed")
for k, d in failed:
    print("   FAIL", k, d[:300])
for e in r["errors"]:
    print("   ERROR", e)
sys.exit(1 if failed or r["errors"] else 0)
EOF
done
exit $STATUS

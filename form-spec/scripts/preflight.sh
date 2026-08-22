#!/usr/bin/env bash
#
# Everything CI checks, run locally, in the same order and with the same commands.
#
# The point is that a failure here is a failure there and the reverse: a check that only runs
# remotely costs a push, a wait, and a log dig to learn something the machine in front of you
# already knew. Anything this script cannot run is reported as SKIPPED rather than passed over
# quietly, because a silent skip is how a green run stops meaning anything.
#
#   ./scripts/preflight.sh            everything
#   ./scripts/preflight.sh --fast     everything except the API parity tests
#
set -uo pipefail

cd "$(dirname "$0")/.." || exit 1
REPO=$(cd .. && pwd)
FAST=${1:-}
FAILED=()
SKIPPED=()

step() {
  local name=$1
  shift
  printf '\n\033[1m▸ %s\033[0m\n' "$name"
  if "$@"; then
    printf '\033[32m  ok\033[0m\n'
  else
    printf '\033[31m  FAILED\033[0m\n'
    FAILED+=("$name")
  fi
}

need() {
  command -v "$1" >/dev/null 2>&1 && return 0
  printf '\n\033[1m▸ %s\033[0m\n\033[33m  SKIPPED — %s is not on PATH (%s)\033[0m\n' "$2" "$1" "$3"
  SKIPPED+=("$2")
  return 1
}

# --- the form-spec job -----------------------------------------------------------------
step "Build the library" npm run build --silent
step "Test the checks" npm test --silent

# The generator reads the API's constants, so a change upstream shows up here as a diff.
step "Regenerate the code enums" python3 scripts/gen_code_enums.py

standalone() {
  local status=0
  while IFS= read -r -d '' file; do
    if ! npx tsp compile "$file" --no-emit >/dev/null 2>&1; then
      echo "  $file does not compile on its own"
      status=1
    fi
  done < <(find typespec-form-spec/lib specs -name '*.tsp' -print0)
  return $status
}
step "Every file compiles on its own" standalone

step "Emit and vendor the artifacts" npm run sync --silent

# Only what the build produces: an edit to a spec or a workflow is not artifact drift.
GENERATED=(api/src/form_schema/form_spec/artifacts
  form-spec/specs/question-bank/generated)

drift() {
  git -C "$REPO" diff --exit-code --stat -- "${GENERATED[@]}" >/dev/null && return 0
  echo "  emitted artifacts differ from the checked-in copy:"
  git -C "$REPO" diff --stat -- "${GENERATED[@]}" | sed 's/^/    /'
  return 1
}
step "No drift in the checked-in artifacts" drift

# --- lint, matching what each job uses -------------------------------------------------
if need ruff "Lint the scripts" "pip install 'ruff>=0.16,<0.17'"; then
  step "Lint the scripts" bash -c "
    ruff format --check --config '$REPO/api/pyproject.toml' scripts &&
    ruff check --config '$REPO/api/pyproject.toml' --ignore T20 scripts"
  step "Lint the adapter and its tests" bash -c "
    cd '$REPO/api' &&
    ruff format --check src/form_schema/form_spec tests/src/form_schema/form_spec &&
    ruff check src/form_schema/form_spec tests/src/form_schema/form_spec"
fi

if need actionlint "Lint the workflows" "brew install actionlint"; then
  step "Lint the workflows" bash -c "cd '$REPO' && actionlint"
fi

# --- the API's parity tests ------------------------------------------------------------
# Slow, and the only part that needs the API's own environment.
if [ "$FAST" = "--fast" ]; then
  printf '\n\033[33m▸ API parity tests — skipped (--fast)\033[0m\n'
  SKIPPED+=("API parity tests")
elif need uv "API parity tests" "https://docs.astral.sh/uv/"; then
  step "API parity tests" bash -c "
    cd '$REPO/api' &&
    uv run pytest -q --confcutdir tests/src/form_schema/form_spec tests/src/form_schema/form_spec"
fi

# --- summary ---------------------------------------------------------------------------
printf '\n'
if [ ${#SKIPPED[@]} -gt 0 ]; then
  printf '\033[33mskipped: %s\033[0m\n' "$(IFS=', '; echo "${SKIPPED[*]}")"
fi
if [ ${#FAILED[@]} -gt 0 ]; then
  printf '\033[31mfailed: %s\033[0m\n' "$(IFS=', '; echo "${FAILED[*]}")"
  exit 1
fi
printf '\033[32mall checks passed\033[0m\n'

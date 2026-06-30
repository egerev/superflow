#!/usr/bin/env bash
# shellcheck shell=bash
# detect-test-env.sh — Detect test infrastructure and write .superflow/test-env.json
#
# Read-only probe: installs nothing, recommends only.
# Idempotent: re-running overwrites with identical output (no volatile fields).
# Every external probe is timeout-wrapped to handle dead sockets / stale VMs.
#
# Usage: bash tools/detect-test-env.sh
# Output: .superflow/test-env.json (atomic mkdir + mktemp + mv)
#
# Requires: bash, jq
# Optional: gtimeout/timeout/perl (for probe timeouts); node, python3, docker, colima

set -euo pipefail

# ── Timeout helper ─────────────────────────────────────────────────────────────
# Priority: gtimeout (coreutils, macOS brew) → timeout (GNU coreutils, Linux)
# → perl alarm → FAIL CLOSED (never run unbounded — a dead socket must not hang).
_TIMEOUT_CMD=""
if command -v gtimeout >/dev/null 2>&1; then
  _TIMEOUT_CMD="gtimeout"
elif command -v timeout >/dev/null 2>&1; then
  _TIMEOUT_CMD="timeout"
fi

# _timeout SECS CMD [ARGS...]
# Runs CMD with a wall-clock limit. Returns CMD's exit code on success, non-zero on
# timeout. When no timeout implementation exists, returns 1 (fail-closed) rather than
# running the command unbounded — a mandatory requirement for non-blocking probes.
_timeout() {
  local secs="$1"; shift
  if [ -n "${_TIMEOUT_CMD}" ]; then
    "${_TIMEOUT_CMD}" "${secs}" "$@"
  elif command -v perl >/dev/null 2>&1; then
    # Perl SIGALRM: replaces perl process via exec, so alarm fires against CMD
    perl -e 'alarm shift; exec @ARGV' "${secs}" "$@"
  else
    # No timeout utility found — fail closed. Probes treat this as "unavailable".
    # All major systems (macOS/Linux) provide gtimeout or timeout via coreutils.
    return 1
  fi
}

# ── Cleanup helper ─────────────────────────────────────────────────────────────
_TMP_FILE=""
_cleanup() {
  if [ -n "${_TMP_FILE}" ]; then
    rm -f "${_TMP_FILE}"
  fi
}
trap '_cleanup' EXIT

# ── Playwright browser cache detection (read-only, no install) ─────────────────
# Verifies ACTUAL browser binaries on disk — not install --list, which reports
# installable names even when binaries were never downloaded.
_detect_playwright_browsers() {
  local cache_dir=""
  local browser=""
  local found=()
  local found_json="[]"

  # Honor PLAYWRIGHT_BROWSERS_PATH override, then fall back to OS default
  if [ -n "${PLAYWRIGHT_BROWSERS_PATH:-}" ]; then
    cache_dir="${PLAYWRIGHT_BROWSERS_PATH}"
  elif [ "$(uname 2>/dev/null)" = "Darwin" ]; then
    cache_dir="${HOME}/Library/Caches/ms-playwright"
  else
    cache_dir="${HOME}/.cache/ms-playwright"
  fi

  if [ ! -d "${cache_dir}" ]; then
    echo "[]"
    return 0
  fi

  # A browser is installed only when a cache subdir named <browser>-* exists
  for browser in chromium firefox webkit; do
    if find "${cache_dir}" -maxdepth 1 -type d -name "${browser}-*" \
       2>/dev/null | grep -q .; then
      found+=("${browser}")
    fi
  done

  if [ "${#found[@]}" -eq 0 ]; then
    echo "[]"
    return 0
  fi

  found_json=$(printf '%s\n' "${found[@]}" | jq -Rn '[inputs]' 2>/dev/null) \
    || found_json="[]"
  echo "${found_json}"
}

# ── Docker detection ───────────────────────────────────────────────────────────
_detect_docker() {
  local present=false
  local runtime="none"
  local ryuk_forced_disabled=false
  local docker_host=""
  local tc_socket_override=""
  local ctx=""
  local docker_info=""
  local colima_profile=""
  local colima_status=""
  local exports_json="{}"

  if ! command -v docker >/dev/null 2>&1; then
    jq -cn '{"present":false,"runtime":"none","ryuk_forced_disabled":false,"exports":{}}'
    return 0
  fi

  # Verify daemon is reachable (dead Colima VM / suspended Docker Desktop must not hang)
  if ! _timeout 5 docker version >/dev/null 2>&1; then
    jq -cn '{"present":false,"runtime":"none","ryuk_forced_disabled":false,"exports":{}}'
    return 0
  fi

  present=true

  # Identify active Docker context — most reliable runtime signal
  ctx=$(_timeout 5 docker context show 2>/dev/null) || ctx="default"
  [ -z "${ctx}" ] && ctx="default"

  case "${ctx}" in
    colima)
      runtime="colima"
      colima_profile="default"
      docker_host="unix://${HOME}/.colima/${colima_profile}/docker.sock"
      tc_socket_override="/var/run/docker.sock"
      ;;
    colima-*)
      runtime="colima"
      colima_profile="${ctx#colima-}"
      docker_host="unix://${HOME}/.colima/${colima_profile}/docker.sock"
      tc_socket_override="/var/run/docker.sock"
      ;;
    rancher-desktop)
      runtime="rancher"
      docker_host="unix://${HOME}/.rd/docker.sock"
      tc_socket_override="/var/run/docker.sock"
      ;;
    *podman*)
      runtime="podman"
      docker_host="unix://${HOME}/.local/share/containers/podman/machine/podman.sock"
      tc_socket_override="/var/run/docker.sock"
      # Rootless Podman requires Ryuk to be disabled (no privileged container access)
      docker_info=$(_timeout 5 docker info 2>/dev/null) || docker_info=""
      if printf '%s\n' "${docker_info}" | grep -qi "rootless"; then
        ryuk_forced_disabled=true
      fi
      ;;
    *)
      # Docker Desktop (context "default"/"desktop-linux") or plain Linux docker.
      # Colima fallback: context may be generic but colima is the actual runtime.
      runtime="desktop"
      colima_status=""
      if command -v colima >/dev/null 2>&1; then
        colima_status=$(_timeout 5 colima status 2>/dev/null) || colima_status=""
        if printf '%s\n' "${colima_status}" | grep -qi "running"; then
          runtime="colima"
          colima_profile="default"
          docker_host="unix://${HOME}/.colima/default/docker.sock"
          tc_socket_override="/var/run/docker.sock"
        fi
      fi
      # Also match if the default colima socket file exists (daemon running, context misconfigured)
      if [ "${runtime}" = "desktop" ] && \
         [ -S "${HOME}/.colima/default/docker.sock" ]; then
        runtime="colima"
        colima_profile="default"
        docker_host="unix://${HOME}/.colima/default/docker.sock"
        tc_socket_override="/var/run/docker.sock"
      fi
      ;;
  esac

  # Populate exports for non-Desktop runtimes; Desktop uses the standard socket
  if [ -n "${docker_host}" ]; then
    exports_json=$(jq -cn \
      --arg dh "${docker_host}" \
      --arg ts "${tc_socket_override}" \
      '{"DOCKER_HOST":$dh,"TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE":$ts}') || exports_json="{}"
    if [ "${ryuk_forced_disabled}" = "true" ]; then
      exports_json=$(printf '%s' "${exports_json}" | \
        jq '. + {"TESTCONTAINERS_RYUK_DISABLED":"true"}') || true
    fi
  fi

  jq -cn \
    --argjson present "${present}" \
    --arg runtime "${runtime}" \
    --argjson ryuk_forced_disabled "${ryuk_forced_disabled}" \
    --argjson exports "${exports_json}" \
    '{"present":$present,"runtime":$runtime,"ryuk_forced_disabled":$ryuk_forced_disabled,"exports":$exports}'
}

# ── Node / JS detection ────────────────────────────────────────────────────────
_detect_node() {
  local present=false
  local version=""
  local runners_json="[]"
  local pw_installed=false
  local pw_browsers_json="[]"
  local pw_json="{}"

  if ! command -v node >/dev/null 2>&1; then
    jq -cn '{"present":false,"version":"","runners":[],"playwright":{"installed":false,"browsers":[]}}'
    return 0
  fi

  present=true
  version=$(_timeout 5 node --version 2>/dev/null) || version="unknown"

  # Parse package.json for known test runners (only when manifest exists)
  if [ -f "package.json" ]; then
    runners_json=$(jq -c '
      ((.dependencies // {}) + (.devDependencies // {})) as $deps |
      [
        (if $deps | has("@playwright/test") then "playwright" else empty end),
        (if $deps | has("vitest")            then "vitest"     else empty end),
        (if ($deps | keys | any(startswith("jest"))) then "jest" else empty end),
        (if $deps | has("cypress")           then "cypress"    else empty end)
      ]
    ' package.json 2>/dev/null) || runners_json="[]"
  fi

  # Playwright browser check — confirm local binary exists first (never bare npx).
  # Then verify ACTUAL installed binaries in the browser cache (not install --list,
  # which can enumerate installable names even when binaries were never downloaded).
  if [ -e "node_modules/.bin/playwright" ]; then
    pw_installed=true
    pw_browsers_json=$(_detect_playwright_browsers)
  fi

  pw_json=$(jq -cn \
    --argjson installed "${pw_installed}" \
    --argjson browsers "${pw_browsers_json}" \
    '{"installed":$installed,"browsers":$browsers}') || pw_json='{"installed":false,"browsers":[]}'

  jq -cn \
    --argjson present "${present}" \
    --arg version "${version}" \
    --argjson runners "${runners_json}" \
    --argjson playwright "${pw_json}" \
    '{"present":$present,"version":$version,"runners":$runners,"playwright":$playwright}'
}

# ── Python detection ───────────────────────────────────────────────────────────
_detect_python() {
  local present=false
  local version=""
  local has_pytest=false
  local has_tc=false
  local has_pw=false
  local py_pw_check=""
  local req_f=""

  if ! command -v python3 >/dev/null 2>&1; then
    jq -cn '{"present":false,"version":"","runners":[],"testcontainers":false,"playwright":false}'
    return 0
  fi

  present=true
  version=$(_timeout 5 python3 --version 2>/dev/null) || version="unknown"
  version="${version#Python }"   # strip "Python " prefix

  # Scan pyproject.toml for known packages
  if [ -f "pyproject.toml" ]; then
    grep -q "pytest"          "pyproject.toml" 2>/dev/null && has_pytest=true || true
    grep -q "testcontainers"  "pyproject.toml" 2>/dev/null && has_tc=true    || true
    grep -q "playwright"      "pyproject.toml" 2>/dev/null && has_pw=true    || true
  fi

  # Scan well-known requirements files
  for req_f in requirements.txt requirements-dev.txt requirements-test.txt requirements-build.txt; do
    if [ -f "${req_f}" ]; then
      grep -q "pytest"         "${req_f}" 2>/dev/null && has_pytest=true || true
      grep -q "testcontainers" "${req_f}" 2>/dev/null && has_tc=true    || true
      grep -q "playwright"     "${req_f}" 2>/dev/null && has_pw=true    || true
    fi
  done

  # Verify playwright is actually importable (read-only; never installs)
  py_pw_check=$(_timeout 5 python3 -c "import playwright; print('ok')" 2>/dev/null) \
    || py_pw_check=""
  [ "${py_pw_check}" = "ok" ] && has_pw=true || true

  local runners_json
  runners_json=$(jq -cn --argjson hp "${has_pytest}" 'if $hp then ["pytest"] else [] end')

  jq -cn \
    --argjson present "${present}" \
    --arg version "${version}" \
    --argjson runners "${runners_json}" \
    --argjson testcontainers "${has_tc}" \
    --argjson playwright "${has_pw}" \
    '{"present":$present,"version":$version,"runners":$runners,"testcontainers":$testcontainers,"playwright":$playwright}'
}

# ── OS: --with-deps support ────────────────────────────────────────────────────
# Playwright --with-deps installs system packages via apt-get (Debian/Ubuntu only).
# macOS uses bundled dylibs — no system packages needed, --with-deps not supported.
_detect_with_deps() {
  local supported=false

  if [ -f "/etc/debian_version" ]; then
    supported=true
  elif [ -f "/etc/os-release" ] && grep -qiE "ubuntu|debian" "/etc/os-release" 2>/dev/null; then
    supported=true
  fi

  # Require sudo to actually install system dependencies
  if [ "${supported}" = "true" ] && ! command -v sudo >/dev/null 2>&1; then
    supported=false
  fi

  echo "${supported}"
}

# ── Project type classifier ────────────────────────────────────────────────────
# 3-way: web | backend-only | library
# Explicit frontend signals → web; explicit backend (no frontend) → backend-only.
# Ambiguous / unrecognized runnable project → web (never silently skip the gate).
# Positive library signal required to emit library; otherwise default is web.
_classify_project() {
  local frontend_detected=false
  local backend_detected=false
  local req_f=""
  local ssg_dir=""
  local ssg_check=""

  # ── Explicit frontend signals ──────────────────────────────────────────────
  if [ -f "package.json" ]; then
    # Extended list: traditional + modern meta-frameworks and SSG tools
    if jq -e '
      ((.dependencies // {}) + (.devDependencies // {})) as $d |
      ($d | has("next"))         or ($d | has("react"))     or
      ($d | has("vue"))          or ($d | has("svelte"))    or
      ($d | has("astro"))        or ($d | has("nuxt"))      or
      ($d | has("gatsby"))       or ($d | has("remix"))     or
      ($d | has("vite"))         or ($d | has("preact"))    or
      ($d | has("solid-js"))     or ($d | has("qwik"))      or
      ($d | has("eleventy"))     or ($d | has("vuepress"))  or
      ($d | has("gridsome"))     or ($d | has("docusaurus")) or
      ($d | keys | any(startswith("@angular/")))     or
      ($d | keys | any(startswith("@sveltejs/")))    or
      ($d | keys | any(startswith("@remix-run/")))   or
      ($d | keys | any(startswith("@builder.io/")))  or
      ($d | keys | any(startswith("@11ty/")))        or
      ($d | keys | any(startswith("@docusaurus/")))
    ' package.json >/dev/null 2>&1; then
      frontend_detected=true
    fi

    # Node backend frameworks
    if jq -e '
      ((.dependencies // {}) + (.devDependencies // {})) as $d |
      ($d | has("express")) or ($d | has("fastify")) or
      ($d | has("koa"))     or ($d | has("hapi"))
    ' package.json >/dev/null 2>&1; then
      backend_detected=true
    fi
  fi

  # Frontend directory markers (including src/pages for Astro, src/app for Next.js App Router)
  if [ -d "app" ] || [ -d "pages" ] || [ -d "src/routes" ] || \
     [ -d "src/pages" ] || [ -d "src/app" ]; then
    frontend_detected=true
  fi

  # Static HTML entry point
  if [ -f "index.html" ] || [ -f "src/index.html" ] || [ -f "public/index.html" ]; then
    frontend_detected=true
  fi

  # SSG output directories (dist/site/_site/out/build with *.html — weak frontend signal)
  for ssg_dir in dist site _site out build; do
    if [ -d "${ssg_dir}" ]; then
      ssg_check=$(find "${ssg_dir}" -maxdepth 1 -name "*.html" 2>/dev/null | head -1) \
        || ssg_check=""
      if [ -n "${ssg_check}" ]; then
        frontend_detected=true
        break
      fi
    fi
  done

  # ── Python backend signals ─────────────────────────────────────────────────
  if [ -f "pyproject.toml" ] && grep -qE "fastapi|flask|django" "pyproject.toml" 2>/dev/null; then
    backend_detected=true
  fi

  for req_f in requirements.txt requirements-dev.txt requirements-test.txt; do
    if [ -f "${req_f}" ] && grep -qE "fastapi|flask|django" "${req_f}" 2>/dev/null; then
      backend_detected=true
    fi
  done

  # ── Classification ─────────────────────────────────────────────────────────
  if [ "${frontend_detected}" = "true" ]; then
    echo "web"
    return 0
  fi

  if [ "${backend_detected}" = "true" ]; then
    echo "backend-only"
    return 0
  fi

  # No explicit signals — check for ambiguous runnable app vs confirmed library.
  # Ambiguous runnable app: package.json with start/dev/serve script → web
  # (never silently skip the E2E gate for a project that runs an app server).
  if [ -f "package.json" ]; then
    if jq -e '
      (.scripts // {}) as $s |
      ($s | has("start")) or ($s | has("dev")) or ($s | has("serve"))
    ' package.json >/dev/null 2>&1; then
      echo "web"
      return 0
    fi
    # Pure package library: has main/module/exports/bin and no runnable scripts
    if jq -e 'has("main") or has("module") or has("exports") or has("bin")' \
       package.json >/dev/null 2>&1; then
      echo "library"
      return 0
    fi
  fi

  # Python packaging project (build-system/setup.py/setup.cfg, no app signal)
  if [ -f "setup.py" ] || [ -f "setup.cfg" ]; then
    echo "library"
    return 0
  fi
  if [ -f "pyproject.toml" ] && grep -q '\[build-system\]' "pyproject.toml" 2>/dev/null; then
    echo "library"
    return 0
  fi

  # Nothing runnable detected — emit library (pure tools/scripts/docs repos).
  # Invariant: a repo with no package.json, no Python packaging signals, and no
  # frontend/backend directories is unambiguously a non-app project.
  echo "library"
}

# ── Readiness verdict ──────────────────────────────────────────────────────────
_compute_readiness() {
  local docker_j="$1"
  local node_j="$2"
  local python_j="$3"
  local project_type="$4"
  local with_deps="$5"

  # Extract scalar flags from detection JSON
  local docker_present node_present pw_installed has_pw_browsers
  local unit_node_count unit_py_count
  docker_present=$(printf '%s' "${docker_j}" | jq -r '.present')
  node_present=$(printf '%s' "${node_j}"    | jq -r '.present')
  pw_installed=$(printf '%s' "${node_j}"    | jq -r '.playwright.installed')
  has_pw_browsers=$(printf '%s' "${node_j}" | \
    jq -r '.playwright.browsers | length > 0')

  # Unit runners: vitest + jest (Node) and pytest (Python) only.
  # Playwright and Cypress are E2E tools — excluded from unit count.
  unit_node_count=$(printf '%s' "${node_j}" | \
    jq -r '[.runners[] | select(. == "vitest" or . == "jest")] | length')
  unit_py_count=$(printf '%s' "${python_j}" | jq -r '.runners | length')

  # ── Layer readiness ──────────────────────────────────────────────────────
  local has_unit=false
  if [ "${unit_node_count}" -gt 0 ] || [ "${unit_py_count}" -gt 0 ]; then
    has_unit=true
  fi

  local has_integration=false
  if [ "${has_unit}" = "true" ] && [ "${docker_present}" = "true" ]; then
    has_integration=true
  fi

  local has_e2e=false
  if [ "${pw_installed}" = "true" ] && [ "${has_pw_browsers}" = "true" ]; then
    has_e2e=true
  fi

  # ── Missing items & recommendations ─────────────────────────────────────
  local missing_arr=()
  local recs_arr=()

  case "${project_type}" in
    web)
      if [ "${has_unit}" = "false" ]; then
        missing_arr+=("unit-runner")
        if [ "${node_present}" = "true" ]; then
          recs_arr+=("npm install --save-dev vitest")
        else
          recs_arr+=("pip install pytest")
        fi
      fi
      if [ "${docker_present}" = "false" ]; then
        missing_arr+=("docker")
        recs_arr+=("Install Docker: https://docs.docker.com/get-docker/")
      fi
      if [ "${pw_installed}" = "false" ]; then
        missing_arr+=("playwright")
        recs_arr+=("npm install --save-dev @playwright/test")
      elif [ "${has_pw_browsers}" = "false" ]; then
        missing_arr+=("playwright-browsers")
        if [ "${with_deps}" = "true" ]; then
          recs_arr+=("npx playwright install --with-deps chromium")
        else
          recs_arr+=("npx playwright install chromium")
        fi
      fi
      ;;
    backend-only)
      if [ "${has_unit}" = "false" ]; then
        missing_arr+=("unit-runner")
        if [ "${node_present}" = "true" ]; then
          recs_arr+=("npm install --save-dev vitest")
        else
          recs_arr+=("pip install pytest")
        fi
      fi
      if [ "${docker_present}" = "false" ]; then
        missing_arr+=("docker")
        recs_arr+=("Install Docker: https://docs.docker.com/get-docker/")
      fi
      ;;
    library)
      if [ "${has_unit}" = "false" ]; then
        missing_arr+=("unit-runner")
        if [ "${node_present}" = "true" ]; then
          recs_arr+=("npm install --save-dev vitest")
        else
          recs_arr+=("pip install pytest")
        fi
      fi
      ;;
  esac

  # ── Verdict ──────────────────────────────────────────────────────────────
  local verdict="ready"
  case "${project_type}" in
    web)
      if [ "${has_unit}" = "true" ] && \
         [ "${has_integration}" = "true" ] && \
         [ "${has_e2e}" = "true" ]; then
        verdict="ready"
      elif [ "${has_unit}" = "true" ]; then
        verdict="partial"
      else
        verdict="blocked"
      fi
      ;;
    backend-only)
      if [ "${has_unit}" = "true" ] && [ "${has_integration}" = "true" ]; then
        verdict="ready"
      elif [ "${has_unit}" = "true" ]; then
        verdict="partial"
      else
        verdict="blocked"
      fi
      ;;
    library)
      # No unit runner = cannot run any tests (blocked, not merely partial)
      if [ "${has_unit}" = "true" ]; then
        verdict="ready"
      else
        verdict="blocked"
      fi
      ;;
  esac

  # ── Build JSON arrays ────────────────────────────────────────────────────
  local missing_json="[]"
  local recs_json="[]"

  if [ "${#missing_arr[@]}" -gt 0 ]; then
    missing_json=$(printf '%s\n' "${missing_arr[@]}" | \
      jq -Rn '[inputs]' 2>/dev/null) || missing_json="[]"
  fi

  if [ "${#recs_arr[@]}" -gt 0 ]; then
    recs_json=$(printf '%s\n' "${recs_arr[@]}" | \
      jq -Rn '[inputs]' 2>/dev/null) || recs_json="[]"
  fi

  jq -cn \
    --argjson unit "${has_unit}" \
    --argjson integration "${has_integration}" \
    --argjson e2e_tooling "${has_e2e}" \
    --arg verdict "${verdict}" \
    --argjson missing "${missing_json}" \
    --argjson recommendations "${recs_json}" \
    '{
      "unit": $unit,
      "integration": $integration,
      "e2e_tooling": $e2e_tooling,
      "app_boot_smoke": "skipped",
      "verdict": $verdict,
      "missing": $missing,
      "recommendations": $recommendations
    }'
}

# ── Main ───────────────────────────────────────────────────────────────────────
main() {
  local out_dir=".superflow"
  local out_file="${out_dir}/test-env.json"
  local docker_json node_json python_json with_deps project_type readiness_json

  mkdir -p "${out_dir}"
  _TMP_FILE=$(mktemp "${out_dir}/.test-env.XXXXXX.json.tmp")

  docker_json=$(_detect_docker)
  node_json=$(_detect_node)
  python_json=$(_detect_python)
  with_deps=$(_detect_with_deps)
  project_type=$(_classify_project)
  readiness_json=$(_compute_readiness \
    "${docker_json}" "${node_json}" "${python_json}" "${project_type}" "${with_deps}")

  jq -cn \
    --argjson docker "${docker_json}" \
    --argjson node "${node_json}" \
    --argjson python "${python_json}" \
    --argjson with_deps_supported "${with_deps}" \
    --arg project_type "${project_type}" \
    --argjson readiness "${readiness_json}" \
    '{
      "docker": $docker,
      "node": $node,
      "python": $python,
      "with_deps_supported": $with_deps_supported,
      "project_type": $project_type,
      "readiness": $readiness
    }' > "${_TMP_FILE}"

  mv "${_TMP_FILE}" "${out_file}"
  _TMP_FILE=""   # prevent cleanup from removing the successfully written file

  echo "detect-test-env: wrote ${out_file}" >&2
}

main "$@"

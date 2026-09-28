#!/usr/bin/env bash
# Запускает команду. Если она падает — выводит самые важные строки лога
# как аннотации GitHub, чтобы причину было видно без скачивания логов.
#   run.sh "Заголовок" команда [аргументы...]
set -uo pipefail

title="$1"
shift
log="$(mktemp)"

"$@" 2>&1 | tee "$log"
status=${PIPESTATUS[0]}

emit() {
  local level="$1" name="$2" text="$3" chunk n=0
  while [ -n "$text" ] && [ "$n" -lt 10 ]; do
    chunk="${text:0:3500}"
    text="${text:3500}"
    n=$((n + 1))
    chunk="${chunk//'%'/'%25'}"
    chunk="${chunk//$'\r'/'%0D'}"
    chunk="${chunk//$'\n'/'%0A'}"
    echo "::${level} title=${name} (${n})::${chunk}"
  done
}

if [ "$status" -ne 0 ]; then
  # Сводка: какие тесты упали и где переполнилась вёрстка (без повторов).
  summary=$(awk '
    /^[0-9][0-9]:[0-9][0-9] \+/ { test = $0; sub(/^[0-9:]+ [^:]*: /, "", test) }
    /overflowed by/ { problem = $0 }
    /EXCEPTION CAUGHT BY/ { problem = $0 }
    /The following .* was thrown/ { getline detail; problem = problem " " detail }
    /relevant error-causing widget was/ { getline where; print test " | " problem " |" where }
    /\[E\]$/ { print "FAILED: " $0 }
  ' "$log" | sed -E 's/file:\/\/\/home\/runner\/work\/[^/]+\/[^/]+\///' | sort | uniq -c | sort -rn | head -c 7000)
  [ -n "$summary" ] && emit error "${title}: сводка" "$summary"
  excerpt=$(grep -n -B3 -A30 -E "EXCEPTION|Exception|Error|error •|error:|FAILED|Expected:|Actual:|overflowed|Test failed" "$log" | head -c 20000)
  [ -z "$excerpt" ] && excerpt=$(tail -n 150 "$log")
  emit error "$title" "$excerpt"
else
  # Предупреждения анализатора тоже полезно видеть.
  warnings=$(grep -E "^\s*(warning|error) •" "$log" | head -c 30000)
  [ -n "$warnings" ] && emit warning "$title" "$warnings"
fi

exit "$status"

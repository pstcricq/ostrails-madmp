#!/usr/bin/env bash
# Checks the values of a target, then exports them. Sourced from the
# repository root:
#
#   source deploy/scripts/values.sh [<the target's .env>]
#
# The keys are those of .env.example, and of the target's own .env.example
# beside its .env when there is one. A key with a value there is fixed. An
# empty key is filled by the target's .env when the file exists, a variable of
# the shell then ignored, else by the environment.
#
#   1. the target's .env read, never run: KEY=value lines, LF endings, each
#      key once, a value on several lines between double quotes; a wrong line
#      is given by its number, never its content
#   2. every empty key filled, no fixed or unknown key in the .env, no fixed
#      key in the environment
#   3. the configuration printed under the sections of the examples, a secret
#      as set only: an empty key ending in _USER, _PASSWORD, _SECRET, _TOKEN or
#      _PRIVATE_KEY
#   4. every key exported, with SECRET_KEYS and VALUES_SUMMARY for the caller
#
# An error in the form of the .env stops the caller at once; the others are
# printed together, then stop it.

LOCAL="${1:-}"

# The common example, then the target's, read as one.
EXAMPLE=".env.example"
TARGET_EXAMPLE=""
if [ -n "$LOCAL" ] && [ -f "$(dirname "$LOCAL")/.env.example" ]; then
  TARGET_EXAMPLE="$(dirname "$LOCAL")/.env.example"
  EXAMPLE="$EXAMPLE and $TARGET_EXAMPLE"
fi
EXAMPLE_LINES="$(cat .env.example ${TARGET_EXAMPLE:+"$TARGET_EXAMPLE"})"

# The keys of the examples in their order, the fixed ones and the empty ones.
KEYS="$(printf '%s\n' "$EXAMPLE_LINES" | sed -n 's/^\([A-Z][A-Z0-9_]*\)=.*/\1/p')"
FIXED="$(printf '%s\n' "$EXAMPLE_LINES" | sed -n 's/^\([A-Z][A-Z0-9_]*\)=..*/\1/p')"
EMPTY="$(printf '%s\n' "$EXAMPLE_LINES" | sed -n 's/^\([A-Z][A-Z0-9_]*\)=$/\1/p')"

# A key in both examples stops the caller.
twice="$(printf '%s\n' "$KEYS" | sort | uniq -d | tr '\n' ' ')"
if [ -n "$twice" ]; then
  echo "error: keys in both $EXAMPLE: ${twice% }. Keep each in one." >&2
  exit 1
fi

# Whether $1 is one of the names of the list $2, one per line.
is_in() { printf '%s\n' "$2" | grep -qx "$1"; }

# The empty keys that are secrets, by the end of their name, one per line.
SECRET_KEYS="$(printf '%s\n' "$EMPTY" | grep -E '_(USER|PASSWORD|SECRET|TOKEN|PRIVATE_KEY)$' || true)"

# A fixed value, from the examples.
fixed_value() { printf '%s\n' "$EXAMPLE_LINES" | sed -n "s/^$1=//p" | head -1; }

errors=()

# --- 1. The target's .env ---------------------------------------------------
# Its keys and values, and the line of each key, in three lists of the same
# order. A value between double quotes loses them, and keeps its line breaks.
env_keys=()
env_values=()
env_lines=()
if [ -n "$LOCAL" ] && [ -f "$LOCAL" ]; then
  bad=""
  crlf=""
  spaced=""
  single=""
  number=0
  opened=0
  while IFS= read -r line || [ -n "$line" ]; do
    number=$((number + 1))
    case "$line" in *$'\r') crlf="$crlf $number" ;; esac
    if [ "$opened" -gt 0 ]; then
      value="$value"$'\n'"$line"
      case "$line" in *'"') env_values+=("${value%\"}"); opened=0 ;; esac
      continue
    fi
    case "$line" in '' | '#'*) continue ;; esac
    if ! [[ $line =~ ^([A-Z][A-Z0-9_]*)=(.*)$ ]]; then
      bad="$bad $number"
      continue
    fi
    env_keys+=("${BASH_REMATCH[1]}")
    env_lines+=("$number")
    value="${BASH_REMATCH[2]}"
    case "$value" in
      '"'*'"') env_values+=("${value:1:${#value}-2}") ;;
      '"'*) value="${value#\"}"; opened=$number ;;
      *)
        case "$value" in
          "'"*"'") single="$single $number" ;;
          [[:space:]]* | *[[:space:]]) spaced="$spaced $number" ;;
        esac
        env_values+=("$value") ;;
    esac
  done < "$LOCAL"
  if [ -n "$crlf" ]; then
    echo "error: $LOCAL, lines ending in CR (Windows line endings):$crlf. Save the file with LF line endings." >&2
    exit 1
  fi
  [ "$opened" -eq 0 ] || bad="$bad $opened (no closing double quote)"
  if [ -n "$bad" ]; then
    echo "error: $LOCAL, lines that are not KEY=value:$bad. A value spanning several lines goes between double quotes." >&2
    exit 1
  fi
  if [ -n "$spaced" ]; then
    echo "error: $LOCAL, values starting or ending with a space:$spaced. Remove the space, or put the value between double quotes." >&2
    exit 1
  fi
  if [ -n "$single" ]; then
    echo "error: $LOCAL, values between single quotes, which would be kept with them:$single. Use double quotes, or none." >&2
    exit 1
  fi
  # Each key against the ones before it.
  twice=""
  for ((i = 1; i < ${#env_keys[@]}; i++)); do
    for ((j = 0; j < i; j++)); do
      if [ "${env_keys[$j]}" = "${env_keys[$i]}" ]; then
        twice="$twice ${env_keys[$i]} (lines ${env_lines[$j]} and ${env_lines[$i]})"
        break
      fi
    done
  done
  if [ -n "$twice" ]; then
    echo "error: $LOCAL, keys given twice:$twice. Keep one line each." >&2
    exit 1
  fi
fi

# --- 2. Sources -------------------------------------------------------------
if [ -n "$LOCAL" ] && [ -f "$LOCAL" ]; then
  SOURCE="$LOCAL"
  # The value of $1 in the target's .env, empty when absent.
  filled() {
    local i
    [ ${#env_keys[@]} -gt 0 ] || return 0
    for i in "${!env_keys[@]}"; do
      if [ "${env_keys[$i]}" = "$1" ]; then
        printf '%s' "${env_values[$i]}"
        return
      fi
    done
  }

  ignored=""
  for key in $KEYS; do
    if [ -n "${!key+x}" ]; then
      ignored="$ignored $key"
      unset "$key"
    fi
  done

  fixed="" unknown=""
  for key in ${env_keys[@]+"${env_keys[@]}"}; do
    if is_in "$key" "$FIXED"; then
      fixed="$fixed $key"
    elif ! is_in "$key" "$EMPTY"; then
      unknown="$unknown $key"
    fi
  done
  [ -z "$fixed" ] || errors+=("fixed by $EXAMPLE, remove from $LOCAL:$fixed")
  [ -z "$unknown" ] || errors+=("not in $EXAMPLE, remove from $LOCAL:$unknown")
else
  SOURCE=environment
  filled() { printf '%s' "${!1:-}"; }

  fixed=""
  for key in $FIXED; do
    [ -z "${!key+x}" ] || fixed="$fixed $key"
  done
  [ -z "$fixed" ] || errors+=("fixed by $EXAMPLE, unset in the environment:$fixed")
fi

# --- 3. Configuration -------------------------------------------------------
# Each key under the title of its section in the examples (# --- Title ---).
echo "Configuration ($EXAMPLE, then $SOURCE)"
missing=""
while IFS= read -r line; do
  if [[ $line =~ ^#\ ---\ (.*)\ ---$ ]]; then
    echo ""
    echo "  ${BASH_REMATCH[1]}"
    continue
  fi
  [[ $line =~ ^([A-Z][A-Z0-9_]*)= ]] || continue
  key="${BASH_REMATCH[1]}"
  if is_in "$key" "$FIXED"; then
    printf '    %-27s %s\n' "$key" "$(fixed_value "$key")"
  elif [ -z "$(filled "$key")" ]; then
    printf '    %-27s %s\n' "$key" "MISSING"
    missing="$missing $key"
  elif is_in "$key" "$SECRET_KEYS"; then
    printf '    %-27s %s\n' "$key" "set"
  else
    printf '    %-27s %s\n' "$key" "$(filled "$key")"
  fi
done <<< "$EXAMPLE_LINES"
[ -z "$missing" ] || errors+=("empty or absent in $SOURCE:$missing")
[ -z "${ignored:-}" ] || { echo ""; echo "(i) Ignored, exported in the shell:$ignored"; }

if [ ${#errors[@]} -gt 0 ]; then
  echo "" >&2
  printf 'error: %s\n' "${errors[@]}" >&2
  exit 1
fi

# --- 4. Export --------------------------------------------------------------
for key in $FIXED; do
  export "$key=$(fixed_value "$key")"
done
for key in $EMPTY; do
  export "$key=$(filled "$key")"
done

export SECRET_KEYS

# What the caller prints on its line `values`: how many keys of each kind,
# from where.
count() { printf '%s' "$1" | awk 'NF { n++ } END { print n + 0 }'; }
secrets="$(count "$SECRET_KEYS")"
variables="$(( $(count "$EMPTY") - secrets ))"
# shellcheck disable=SC2034 # read by the script that sources this file
VALUES_SUMMARY="$(count "$KEYS") keys: $(count "$FIXED") fixed, $secrets secrets and $variables variables from $SOURCE"

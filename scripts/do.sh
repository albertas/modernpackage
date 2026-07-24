#!/usr/bin/env bash
# Start `just lifecycle` in a tmux session on the server named after the current
# directory and attach to it. Works from a workstation and from the server itself.
# Assumes the same project is already checked out on the server at ~/ai/<name>.
#
# lifecycle has to run inside tmux so it survives the ssh connection going away,
# and it has to be started with send-keys rather than `ssh <host> just lifecycle`:
# tmux panes are login shells, so just and uv are on their PATH, while the shell
# ssh gives a remote command is neither interactive nor a login shell and cannot
# find either of them.
set -euo pipefail

SERVER_HOST='niekas-server'
SERVER='niekas@78.60.182.178'

session="$(basename "$(pwd -P)")"

# Runs on the server: create the session if it is missing, then start lifecycle in
# it unless the pane is already busy. $HOME and the tmux state are the server's.
bootstrap() {
  local session="$1" dir pane_cmd i
  dir="$HOME/ai/$session"
  if [ ! -d "$dir" ]; then
    echo "No checkout at $dir on $(hostname); clone the project there first." >&2
    return 1
  fi
  if ! tmux has-session -t "=$session" 2>/dev/null; then
    tmux new-session -d -s "$session" -c "$dir"
  fi
  # A shell that is still sourcing its startup files swallows keys, and a C-c
  # there aborts ~/.profile part way through, leaving the pane without
  # ~/.cargo/bin and ~/.local/bin, so just and uv are gone for its whole life.
  # The prompt is only drawn once those files have run, so wait for it.
  for ((i = 0; i < 100; i++)); do
    [ -n "$(tmux capture-pane -p -t "=$session:" | tr -d '[:space:]')" ] && break
    sleep 0.1
  done
  # "=name" alone is a session target; panes and windows need the trailing colon,
  # or tmux fails to resolve it ("can't find pane: =name").
  pane_cmd="$(tmux display-message -p -t "=$session:" '#{pane_current_command}')"
  case "$pane_cmd" in
    bash|zsh|sh|fish|dash)
      # Discard anything half-typed at the prompt first, otherwise it gets glued
      # to the front of the command below (a stray "ls" turns cd into lscd).
      # Readline keys rather than C-c: a stray SIGINT would abort the startup
      # files if the wait above ever returned early, and this cannot.
      tmux send-keys -t "=$session:" C-e C-u
      tmux send-keys -t "=$session:" "cd $dir && git pull && just lifecycle" Enter
      echo "Started just lifecycle in tmux session $session."
      ;;
    *)
      echo "Session $session is busy running $pane_cmd; not starting lifecycle again."
      ;;
  esac
}

if [ "$(hostname)" = "$SERVER_HOST" ]; then
  bootstrap "$session"
  if [ -n "${TMUX:-}" ]; then
    exec tmux switch-client -t "=$session"
  fi
  exec tmux attach-session -t "=$session"
else
  # Ship the function over stdin instead of quoting it into a remote command line,
  # then attach on a second connection that owns the terminal.
  {
    echo 'set -euo pipefail'
    declare -f bootstrap
    printf 'bootstrap %q\n' "$session"
  } | ssh "$SERVER" bash -s
  exec ssh -t "$SERVER" tmux attach-session -t "=$session"
fi

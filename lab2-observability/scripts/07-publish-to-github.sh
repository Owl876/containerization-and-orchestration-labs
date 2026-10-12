#!/usr/bin/env bash
set -euo pipefail

# Публикация лабы 2 в общий репозиторий команды "КуберПанды".
# Решение: не мини-репо/сабмодуль, а просто папка lab2-observability
# внутри общего репо — так и проще ревьюить, и не нужно объяснять
# сокомандникам, что такое git submodule ради учебной лабы.

REPO_URL="https://github.com/Owl876/containerization-and-orchestration-labs.git"
WORKDIR="$HOME/itmo"
REPO_DIR="$WORKDIR/containerization-and-orchestration-labs"
LAB_SRC="$WORKDIR/panda-observability-lab"
LAB_DST="$REPO_DIR/lab2-observability"

mkdir -p "$WORKDIR"

if [ ! -d "$REPO_DIR/.git" ]; then
  git clone "$REPO_URL" "$REPO_DIR"
fi

cd "$REPO_DIR"
git checkout main
git pull --ff-only origin main

mkdir -p "$LAB_DST"
rsync -a --exclude='.git' "$LAB_SRC"/ "$LAB_DST"/

# .gitignore на случай питоновского мусора — venv/pycache коммитить незачем
cat > "$LAB_DST/.gitignore" <<'EOF'
__pycache__/
*.pyc
.venv/
venv/
EOF

git add "lab2-observability"
git status

echo
echo "Дальше руками (чтобы наверняка проверить diff перед коммитом):"
echo "  cd $REPO_DIR"
echo "  git diff --cached --stat"
echo "  git commit -m 'lab2: observability stack (metrics, logs, traces, alerts + telegram bot)'"
echo "  git push origin main"

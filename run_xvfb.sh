#!/usr/bin/env bash
set -e

# Запуск скрипта в виртуальном X‑экране через xvfb-run.
# Редактируйте переменные окружения ниже или экспортируйте их перед запуском.

# Рабочая директория (путь к проекту)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# По умолчанию запускаем в headful режиме внутри виртуального экрана
export HEADLESS=0
export HUMANIZE=1

# Вы можете задать дополнительные переменные окружения перед запуском, например:
# export PROXY="http://user:pass@proxyhost:3128"
# export USER_AGENT="..."

# Найдём доступный интерпретатор Python (предпочитаем python3)
PYTHON_BIN="$(command -v python3 || command -v python || true)"
if [ -z "$PYTHON_BIN" ]; then
  echo "No python interpreter found in PATH. Install python3 or export PATH so systemd can find it." >&2
  exit 127
fi

# Запуск через xvfb-run с экраном 1400x900x24. Измените размеры при необходимости.
exec xvfb-run -s "-screen 0 1400x900x24" "$PYTHON_BIN" app.py

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -d ".venv" ]; then
  echo "Не найдено виртуальное окружение .venv"
  exit 1
fi

source .venv/bin/activate

pip install -r requirements.txt
pip install -r requirements-build.txt

pyinstaller --clean desktop_app.spec

echo "Сборка завершена."
echo "Готовое приложение: $ROOT_DIR/dist/WasteRegistryApp.app"

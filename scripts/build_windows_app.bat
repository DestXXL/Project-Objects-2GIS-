@echo off
setlocal

cd /d %~dp0\..

if not exist ".venv" (
  echo Не найдено виртуальное окружение .venv
  exit /b 1
)

call .venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-build.txt
pyinstaller --clean desktop_app.spec

echo Сборка завершена.
echo Готовая папка приложения: %CD%\dist\WasteRegistryApp
echo Для передачи пользователю упакуйте всю папку WasteRegistryApp в zip.

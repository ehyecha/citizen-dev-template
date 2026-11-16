@echo off
chcp 65001 >nul
rem 미리 보기용: 더블클릭하면 화면이 켜지고 브라우저가 열립니다. (배포와는 관계 없음)
cd /d "%~dp0"

where uv >nul 2>nul
if errorlevel 1 (
  echo [안내] uv 가 설치되어 있지 않습니다. 가이드의 "0단계"를 먼저 진행하거나 담당자에게 문의하세요.
  pause
  exit /b 1
)

echo 패키지를 확인하는 중입니다. 처음에는 시간이 걸릴 수 있습니다...
uv sync
if errorlevel 1 (
  echo [안내] 패키지 설치에 실패했습니다. 이 창의 내용을 담당자에게 보여 주세요.
  pause
  exit /b 1
)

echo.
echo 잠시 후 브라우저가 열립니다. 끄려면 이 검은 창을 닫으세요.
start "" cmd /c "timeout /t 4 /nobreak >nul & start http://localhost:8000"
uv run uvicorn app.main:app --reload
pause

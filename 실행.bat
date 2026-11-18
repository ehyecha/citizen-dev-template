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

where docker >nul 2>nul
if errorlevel 1 (
  echo [안내] Docker 가 설치되어 있지 않습니다. Docker Desktop 을 설치하고 실행한 뒤 다시 시도하거나 담당자에게 문의하세요.
  pause
  exit /b 1
)

if not exist ".env" (
  copy ".env.example" ".env" >nul
  echo [안내] .env 파일을 새로 만들었습니다. 내 PC 전용 DB 설정이 들어 있습니다.
)

echo 내 PC 의 PostgreSQL 을 켜는 중입니다. 처음에는 이미지를 내려받느라 시간이 걸립니다...
docker compose up -d --wait db
if errorlevel 1 (
  echo [안내] PostgreSQL 을 켜지 못했습니다. Docker Desktop 이 실행 중인지 확인하고, 안 되면 이 창의 내용을 담당자에게 보여 주세요.
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
uv run python -m uvicorn app.main:app --reload
pause

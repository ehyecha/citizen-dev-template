@echo off
chcp 65001 >nul
rem 개발용 채팅 화면: 더블클릭하면 한 창에 "만들고 있는 화면 + 채팅" 이 열립니다. (내 PC 전용, 배포와는 관계 없음)
cd /d "%~dp0"

where uv >nul 2>nul
if errorlevel 1 (
  echo [안내] uv 가 설치되어 있지 않습니다. 가이드의 "0단계"를 먼저 진행하거나 담당자에게 문의하세요.
  pause
  exit /b 1
)

where claude >nul 2>nul
if errorlevel 1 (
  echo [안내] Claude Code 가 설치되어 있지 않습니다. 담당자에게 문의하세요.
  pause
  exit /b 1
)

rem 예전에 켜 둔 서버가 남아 있으면 새 서버가 켜지지 않아 예전 화면이 계속 보인다. 먼저 알려 준다.
netstat -ano | findstr ":8001 " | findstr LISTENING >nul
if not errorlevel 1 (
  echo [안내] 예전에 켠 개발용 채팅이 아직 켜져 있습니다. 검은 창을 모두 닫은 뒤 다시 실행해 주세요.
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
echo 잠시 후 브라우저가 열립니다.
echo 끄려면 이 검은 창과, 새로 열린 "만들고 있는 화면 서버" 창을 모두 닫으세요.
rem 만들고 있는 화면(8000번)은 별도 창에서 켠다. 코드가 바뀌면 자동으로 다시 시작된다.
start "만들고 있는 화면 서버" cmd /k "uv run uvicorn app.main:app --reload --port 8000"
start "" cmd /c "timeout /t 5 /nobreak >nul & start http://localhost:8001"
uv run uvicorn devtools.chat_server:app --host 127.0.0.1 --port 8001
pause

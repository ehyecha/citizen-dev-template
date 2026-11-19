@echo off
chcp 65001 >nul
rem 배포용 Docker 이미지 만들기: 더블클릭하면 이미지 파일(.tar)이 dist 폴더에 만들어집니다.
cd /d "%~dp0"

where docker >nul 2>nul
if errorlevel 1 (
  echo [안내] Docker 가 설치되어 있지 않습니다. Docker Desktop 을 설치하고 실행한 뒤 다시 시도하거나 담당자에게 문의하세요.
  pause
  exit /b 1
)

if not exist "Dockerfile" (
  echo [안내] Dockerfile 이 없습니다. 템플릿을 다시 받거나 담당자에게 문의하세요.
  pause
  exit /b 1
)

rem 이름과 버전을 바로 줄 수도 있습니다: 이미지 만들기.bat material_receipt 1.0
set "NAME=%~1"
set "VER=%~2"
if "%NAME%"=="" echo 도구 이름을 영문 소문자, 숫자, 밑줄로 입력하세요. 예: material_receipt
if "%NAME%"=="" set /p NAME=도구 이름:
if "%VER%"=="" echo 버전을 입력하세요. 예: 1.0
if "%VER%"=="" set /p VER=버전:

if "%NAME%"=="" (
  echo [안내] 도구 이름이 비어 있습니다.
  pause
  exit /b 1
)
if "%VER%"=="" (
  echo [안내] 버전이 비어 있습니다.
  pause
  exit /b 1
)

echo.
echo 이미지를 만드는 중입니다. 처음에는 시간이 걸립니다...
rem 서버는 linux/amd64 기준이므로 내 PC 종류와 상관없이 맞춰서 만든다.
docker build --platform linux/amd64 -t %NAME%:%VER% .
if errorlevel 1 (
  echo [안내] 이미지를 만들지 못했습니다. 이 창의 내용을 담당자에게 보여 주세요.
  pause
  exit /b 1
)

if not exist "dist" mkdir dist
docker save -o "dist\%NAME%-%VER%.tar" %NAME%:%VER%
if errorlevel 1 (
  echo [안내] 이미지 파일을 저장하지 못했습니다. 이 창의 내용을 담당자에게 보여 주세요.
  pause
  exit /b 1
)

echo.
echo 완료! 아래 파일을 배포 요청 때 함께 제출하세요. (.env 는 이미지에 들어 있지 않습니다)
echo   dist\%NAME%-%VER%.tar
pause

# (도구 이름을 적으세요)

<!-- 이 파일은 도구를 다 만든 뒤 아래 항목을 채워 주세요. "배포 전 점검해 줘" 때 확인합니다. -->

## 이 도구는 무엇인가요
(한두 문장으로 적어 주세요)

## 누가 쓰나요
- 사용 부서:
- 사용 인원:
- 담당자:

## 실행 방법

처음 한 번: `.env.example` 을 `.env` 로 복사하고 Docker Desktop 을 켜 둡니다. (`실행.bat` 을 더블클릭하면 아래 과정을 자동으로 해 줍니다.)

```bash
docker compose up -d db                  # 내 PC 에 PostgreSQL 켜기
uv sync                                  # 패키지 설치
uv run uvicorn app.main:app --reload     # 실행 → http://localhost:8000
```

## 테스트
내 PC 의 PostgreSQL 이 켜져 있어야 합니다 (`docker compose up -d db`). 테스트는 `_test` 가 붙은 별도 DB 를 쓰므로 내 데이터는 지워지지 않습니다.
```bash
uv run pytest
```

## 배포팀 참고
- 결과물은 Docker 이미지로 전달됩니다. `Dockerfile` 관리와 이미지 빌드는 현업 담당자가 하고, 완성된 이미지를 배포팀에 전달합니다. <!-- TODO: 전달 방법(레지스트리·파일 등), 이미지 이름·버전 규칙 -->
- `DB설계.md`(DB·스키마·테이블 이름)는 현업이 개발 전에 작성한 시트입니다. DB 이름과 스키마(`alembic/versions/`)는 현업이 제안한 것이며, **배포팀이 검토해 최종 이름과 구조를 정한 뒤 승인된 것만 적용합니다.**
- 이 도구는 내 PC 의 PostgreSQL 컨테이너(`docker-compose.yml`)로만 확인했고, **서버 PostgreSQL 에서는 시험하지 않았습니다.**
- 서버 환경변수 `DATABASE_URL` 에 PostgreSQL 주소(`postgresql+psycopg://...`)를 넣어 주세요.
- 서버에서는 테이블이 자동으로 만들어지지 않습니다. 처음 배포할 때 `uv run alembic upgrade head` 를 실행해 주세요.
- 상태 확인 주소: `/health`

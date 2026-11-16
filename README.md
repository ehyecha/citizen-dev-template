# (도구 이름을 적으세요)

<!-- 이 파일은 도구를 다 만든 뒤 아래 항목을 채워 주세요. "배포 전 점검해 줘" 때 확인합니다. -->

## 이 도구는 무엇인가요
(한두 문장으로 적어 주세요)

## 누가 쓰나요
- 사용 부서:
- 사용 인원:
- 담당자:

## 실행 방법

```bash
uv sync                                  # 처음 한 번: 패키지 설치
uv run uvicorn app.main:app --reload     # 실행 → http://localhost:8000
```

## 테스트
```bash
uv run pytest
```

## 배포팀 참고
- 이 도구는 내 PC 의 로컬 DB(SQLite)로만 확인했고, **서버 PostgreSQL 에서는 시험하지 않았습니다.**
- 서버 환경변수 `DATABASE_URL` 에 PostgreSQL 주소(`postgresql+psycopg://...`)를 넣어 주세요.
- 서버에서는 테이블이 자동으로 만들어지지 않습니다. 처음 배포할 때 `uv run alembic upgrade head` 를 실행해 주세요.
- 상태 확인 주소: `/health`

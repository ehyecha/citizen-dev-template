"""개발용 채팅 화면 (내 PC 전용, 배포되지 않음).

도구를 '만드는 사람'이 VS Code 대신 브라우저 채팅창에서 요청하고 진행 상황을 볼 수 있게 한다.
PC 에 설치된 Claude Code(사내 승인 Bedrock 설정)를 그대로 실행할 뿐이다.
- 이 폴더의 코드는 app/ 에서 불러오지 않는다. (규칙: CLAUDE.md)
- 키·주소는 코드에 없다. Claude Code 가 PC 의 기존 설정을 그대로 쓴다.
- 127.0.0.1(내 PC)에서만 열린다.

요청 하나는 4단계 담당자를 차례로 거친다.
  1. 프롬프트 이해 (읽기만) → [사용자 확인] → 2. 데이터 분석 (읽기만)
  → 3. 개발 진행 (수정 가능) → 4. 검토 (읽기만 + 테스트 실행)
검토에서 문제가 나오면 개발로 되돌아가 자동으로 1번만 다시 고친다.
"""

import json
import logging
import re
import shutil
import subprocess
import threading
import time
from collections.abc import Iterator
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

logger = logging.getLogger("devtools.chat")

ROOT = Path(__file__).resolve().parent.parent  # 프로젝트 폴더
AGENTS_DIR = ROOT / ".claude" / "agents"  # 담당(에이전트)별 지시문 md 파일
ALLOWED_HOSTS = {"127.0.0.1", "localhost"}

# 허용: 아래 명령만 실행할 수 있다. 그 밖의 명령은 막힌다.
ALLOWED_TOOLS = [
    "Bash(uv run pytest:*)",
    "Bash(uv run ruff:*)",
    "Bash(uv sync:*)",
    "Bash(git status:*)",
    "Bash(git diff:*)",
    "Bash(git log:*)",
]
# 금지: 비밀정보(.env), 배포 관련 파일, 서버로 올리기
DENIED_TOOLS = [
    "Read(./.env)",
    "Edit(./.env)",
    "Write(./.env)",
    "Edit(./Dockerfile)",
    "Write(./Dockerfile)",
    "Edit(./.github/**)",
    "Write(./.github/**)",
    "Edit(./.gitlab-ci.yml)",
    "Write(./.gitlab-ci.yml)",
    "Bash(git push:*)",
]
_EDIT_TOOLS = ["Edit", "Write", "MultiEdit", "NotebookEdit"]

STAGE_LABELS = {
    "understand": "프롬프트 이해",
    "analyze": "데이터 분석",
    "develop": "개발 진행",
    "review": "검토",
}
MAX_FIX_ROUNDS = 2  # 개발 1번 + 검토에서 문제가 나오면 다시 1번

_run_lock = threading.Lock()  # 한 번에 한 작업만 (두 작업이 같은 파일을 고치지 않도록)
_stop = threading.Event()
_current: subprocess.Popen | None = None
_active = {"label": "", "since": 0.0}  # 지금 어느 단계가 언제부터 돌고 있는지 (안내 문구용)

app = FastAPI(title="개발용 채팅", docs_url=None, redoc_url=None)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class ContinueRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    understanding: str = Field(min_length=1, max_length=8000)


def _check_local(request: Request) -> None:
    """내 PC 의 브라우저에서 온 요청만 받는다. (다른 사이트가 몰래 부르는 것을 막는다)"""
    host = (request.headers.get("host") or "").rsplit(":", 1)[0].strip("[]")
    if host not in ALLOWED_HOSTS:
        raise HTTPException(status_code=403, detail="내 PC 에서만 사용할 수 있습니다.")
    origin = request.headers.get("origin")
    if origin:
        origin_host = origin.split("://", 1)[-1].rsplit(":", 1)[0].strip("[]")
        if origin_host not in ALLOWED_HOSTS:
            raise HTTPException(status_code=403, detail="내 PC 에서만 사용할 수 있습니다.")


def _short(text: str, limit: int = 80) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _tool_step(name: str, tool_input: dict) -> str:
    """도구 사용을 쉬운 한국어 한 줄로 바꾼다."""
    target = tool_input.get("file_path") or tool_input.get("path") or ""
    if target:
        try:
            target = str(Path(target).resolve().relative_to(ROOT))
        except (ValueError, OSError):
            target = Path(target).name
    if name == "Read":
        return f"파일 읽는 중: {target}"
    if name in ("Edit", "MultiEdit"):
        return f"파일 수정 중: {target}"
    if name == "Write":
        return f"파일 만드는 중: {target}"
    if name in ("Grep", "Glob"):
        return f"찾는 중: {_short(tool_input.get('pattern', ''))}"
    if name == "Bash":
        return f"명령 실행 중: {_short(tool_input.get('command', ''))}"
    return f"작업 중: {name}"


def translate(event: dict) -> list[dict]:
    """Claude Code 가 보내는 이벤트를 화면용 간단한 이벤트로 바꾼다."""
    kind = event.get("type")
    out: list[dict] = []
    if kind == "assistant":
        for block in event.get("message", {}).get("content", []):
            if block.get("type") == "text" and block.get("text", "").strip():
                out.append({"kind": "text", "text": block["text"]})
            elif block.get("type") == "tool_use":
                step = _tool_step(block.get("name", ""), block.get("input", {}))
                out.append({"kind": "step", "text": step})
    elif kind == "result":
        failed = bool(event.get("is_error"))
        text = event.get("result") or ""
        if failed and not text:
            text = "작업을 끝내지 못했습니다."
        out.append({"kind": "done", "text": text, "error": failed})
    return out


# ---------- 단계별 권한 ----------


def stage_permissions(stage: str) -> tuple[str, list[str], list[str]]:
    """단계마다 (권한 모드, 허용 목록, 금지 목록)을 돌려준다."""
    if stage == "develop":
        return "acceptEdits", ALLOWED_TOOLS, DENIED_TOOLS
    if stage == "review":  # 고치지 않고 점검만. 테스트·점검 명령은 실행할 수 있다.
        return "default", ALLOWED_TOOLS, DENIED_TOOLS + _EDIT_TOOLS
    # 이해·분석: 읽기만. 명령 실행도 막는다.
    return "default", [], DENIED_TOOLS + _EDIT_TOOLS + ["Bash"]


def _build_command(claude_path: str, stage: str) -> list[str]:
    mode, allowed, denied = stage_permissions(stage)
    command = [
        claude_path,
        "-p",
        "--agent",
        stage,  # .claude/agents/<단계>.md 의 지시문과 도구 제한을 쓴다
        "--output-format",
        "stream-json",
        "--verbose",
        "--permission-mode",
        mode,
    ]
    if allowed:
        command += ["--allowedTools", *allowed]
    command += ["--disallowedTools", *denied]
    return command


def missing_agents() -> list[str]:
    """.claude/agents/ 에 없는 에이전트 파일 이름을 돌려준다."""
    return [f"{stage}.md" for stage in STAGE_LABELS if not (AGENTS_DIR / f"{stage}.md").is_file()]


# ---------- 단계별 입력 ----------
# 각 담당의 역할·규칙은 .claude/agents/*.md 에 있다. 여기서는 넘겨줄 내용(자료)만 만든다.


def _prompt_understand(message: str) -> str:
    return f"[사용자 요청]\n{message}"


def _context(message: str, understanding: str) -> str:
    return f"[사용자 요청]\n{message}\n\n[이해 결과]\n{understanding}"


def _prompt_analyze(context: str) -> str:
    return context


def _prompt_develop(context: str, analysis: str, feedback: str) -> str:
    text = f"{context}\n\n[분석 결과]\n{analysis}"
    if feedback:
        text += f"\n\n[검토 담당이 지적한 문제 — 이것을 먼저 고치세요]\n{feedback}"
    return text


def _prompt_review(context: str, development: str) -> str:
    return f"{context}\n\n[개발 결과]\n{development}"


# ---------- 결과 읽기 ----------


def _last_line(text: str) -> str:
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    return lines[-1] if lines else ""


def can_proceed(understanding: str) -> bool:
    """이해 담당이 '진행 가능: 아니오' 라고 했으면 거짓."""
    return not re.search(r"진행\s*가능\s*:\s*아니오", _last_line(understanding))


SCREEN_PATH_RE = re.compile(r"화면\s*주소\s*:\s*`?(/[A-Za-z0-9_\-/]*)`?\s*$")


def screen_path(development: str) -> str:
    """개발 담당이 마지막 줄에 적은 '화면 주소: /주소' 를 읽는다. 없거나 이상하면 빈 문자열."""
    match = SCREEN_PATH_RE.search(_last_line(development))
    if not match or "//" in match.group(1):
        return ""
    return match.group(1)


def review_passed(review: str) -> bool:
    """검토 마지막 줄이 '통과' 일 때만 참. 읽을 수 없으면 안전하게 거짓으로 본다."""
    last = _last_line(review)
    return "검토 결과" in last and "통과" in last and "수정 필요" not in last


# ---------- 실행 ----------


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _done(text: str, error: bool = False, busy: bool = False, path: str = "") -> str:
    payload = {"kind": "done", "text": text, "error": error, "busy": busy}
    if path:
        payload["path"] = path  # 미리보기가 열어야 할 화면 주소
    return _sse(payload)


def busy_message() -> str:
    """이미 돌고 있는 작업이 어느 단계인지 알려 주는 문구."""
    label = _active["label"]
    if not label:
        return "이미 다른 작업이 진행 중입니다. 끝난 뒤에 다시 보내 주세요."
    seconds = int(time.monotonic() - _active["since"])
    return (
        f"이미 다른 작업이 진행 중입니다. 지금은 '{label}' 단계이고 {seconds}초째입니다. "
        "끝나길 기다리거나 '중지'를 눌러 멈춘 뒤 다시 보내 주세요."
    )


def _kill(proc: subprocess.Popen) -> None:
    """작업을 멈춘다. (하위 프로그램까지 함께)"""
    try:
        subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            capture_output=True,
            check=False,
        )
    except OSError:
        proc.kill()


def _stage(stage: str, prompt: str, round_no: int = 1, claude_path: str = "") -> Iterator[str]:
    """한 단계를 실행한다. 진행 상황을 흘려보내고, 마지막 결과를 돌려준다."""
    global _current
    base = {"stage": stage, "label": STAGE_LABELS[stage], "round": round_no}
    _active.update(label=STAGE_LABELS[stage], since=time.monotonic())
    yield _sse({"kind": "stage", "status": "running", **base})

    result = {"text": "", "error": True}
    proc = subprocess.Popen(
        _build_command(claude_path or shutil.which("claude") or "claude", stage),
        cwd=ROOT,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
    )
    _current = proc
    try:
        # 지시문은 명령줄이 아니라 표준 입력으로 넘긴다. (특수문자 문제 방지)
        proc.stdin.write(prompt)
        proc.stdin.close()
        for line in proc.stdout:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            for item in translate(event):
                if item["kind"] == "step":
                    yield _sse({**item, "stage": stage})
                elif item["kind"] == "done":
                    result = {"text": item["text"], "error": item["error"]}
        proc.wait()
    finally:
        if proc.poll() is None:
            _kill(proc)
        _current = None

    failed = result["error"] or _stop.is_set()
    yield _sse({"kind": "stage", "status": "failed" if failed else "done", **base})
    if result["text"] and not failed:
        yield _sse({"kind": "summary", "stage": stage, "round": round_no, "text": result["text"]})
    return {"text": result["text"], "error": failed}


def _pipeline_first(message: str) -> Iterator[str]:
    """1단계(프롬프트 이해)만 하고, 사용자 확인을 기다리도록 멈춘다."""
    result = yield from _stage("understand", _prompt_understand(message))
    if result["error"]:
        yield _done("중지했거나 작업을 끝내지 못했습니다.", True)
        return
    if not can_proceed(result["text"]):
        yield _done("지금 요청은 바로 진행하기 어렵습니다. 위 내용을 확인해 주세요.", True)
        return
    yield _sse({"kind": "gate", "text": result["text"]})


def _pipeline_rest(message: str, understanding: str) -> Iterator[str]:
    """사용자가 확인한 뒤: 2 분석 → 3 개발 → 4 검토 (문제가 있으면 개발 1번 더)."""
    context = _context(message, understanding)

    analysis = yield from _stage("analyze", _prompt_analyze(context))
    if analysis["error"]:
        yield _done("중지했거나 분석을 끝내지 못했습니다.", True)
        return

    feedback = ""
    for round_no in range(1, MAX_FIX_ROUNDS + 1):
        development = yield from _stage(
            "develop", _prompt_develop(context, analysis["text"], feedback), round_no
        )
        if development["error"]:
            yield _done("중지했거나 개발을 끝내지 못했습니다.", True)
            return
        review = yield from _stage("review", _prompt_review(context, development["text"]), round_no)
        if review["error"]:
            yield _done("중지했거나 검토를 끝내지 못했습니다.", True)
            return
        if review_passed(review["text"]):
            path = screen_path(development["text"])
            where = (
                f" 만든 화면({path})을 왼쪽에 열었습니다."
                if path
                else " 왼쪽 화면에서 결과를 확인하세요."
            )
            yield _done("모든 단계를 마쳤습니다." + where, path=path)
            return
        feedback = review["text"]

    yield _done("검토에서 문제가 남았습니다. 위 검토 내용을 확인하고 다시 요청해 주세요.", True)


def _guarded(make_stream) -> Iterator[str]:
    """Claude Code 확인, 한 번에 한 작업, 오류·정리를 공통으로 처리한다."""
    if not shutil.which("claude"):
        yield _done("Claude Code 를 찾을 수 없습니다. 설치 여부를 담당자에게 문의해 주세요.", True)
        return
    missing = missing_agents()
    if missing:
        yield _done(
            "에이전트 파일이 없습니다: "
            + ", ".join(missing)
            + " (.claude/agents/ 폴더를 확인해 주세요)",
            True,
        )
        return
    if not _run_lock.acquire(blocking=False):
        yield _done(busy_message(), True, busy=True)
        return
    _stop.clear()
    try:
        yield from make_stream()
    except Exception:
        logger.exception("devtools_chat_failed")  # 요청 내용은 로그에 남기지 않는다
        yield _done("문제가 생겼습니다. 다시 시도해 주세요.", True)
    finally:
        proc = _current
        if proc is not None and proc.poll() is None:
            _kill(proc)
        _active.update(label="", since=0.0)
        _run_lock.release()


SERVER_VERSION = 3  # 4단계 에이전트 구조. 화면이 예전 서버와 섞여 쓰이는 것을 알아채는 데 쓴다.


@app.get("/version", include_in_schema=False)
def version(request: Request):
    _check_local(request)
    return {"version": SERVER_VERSION}


@app.get("/", include_in_schema=False)
def page(request: Request):
    _check_local(request)
    # 화면을 고쳤는데 브라우저가 예전 화면을 계속 보여 주는 일이 없도록 저장하지 않게 한다.
    return FileResponse(Path(__file__).parent / "chat.html", headers={"Cache-Control": "no-store"})


@app.post("/chat", include_in_schema=False)
def chat(body: ChatRequest, request: Request):
    _check_local(request)
    message = body.message.strip()
    return StreamingResponse(
        _guarded(lambda: _pipeline_first(message)), media_type="text/event-stream"
    )


@app.post("/continue", include_in_schema=False)
def continue_run(body: ContinueRequest, request: Request):
    _check_local(request)
    message, understanding = body.message.strip(), body.understanding.strip()
    return StreamingResponse(
        _guarded(lambda: _pipeline_rest(message, understanding)),
        media_type="text/event-stream",
    )


@app.post("/stop", include_in_schema=False)
def stop(request: Request):
    _check_local(request)
    _stop.set()
    proc = _current
    if proc is not None and proc.poll() is None:
        _kill(proc)
    return {"stopped": proc is not None}

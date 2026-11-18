from pathlib import Path

from fastapi.testclient import TestClient

from devtools import chat_server

client = TestClient(chat_server.app, base_url="http://localhost:8001")


def test_page_opens_on_my_pc():
    response = client.get("/")
    assert response.status_code == 200
    assert "개발용 채팅" in response.text


def test_other_host_is_rejected():
    other = TestClient(chat_server.app, base_url="http://example.com")
    assert other.get("/").status_code == 403
    assert other.post("/chat", json={"message": "안녕"}).status_code == 403


def test_other_site_origin_is_rejected():
    response = client.post(
        "/chat", json={"message": "안녕"}, headers={"origin": "http://evil.example"}
    )
    assert response.status_code == 403


def test_empty_message_is_rejected():
    assert client.post("/chat", json={"message": ""}).status_code == 422


def test_events_are_translated_to_easy_steps():
    tool = {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "text", "text": "확인해 볼게요."},
                {"type": "tool_use", "name": "Read", "input": {"file_path": "C:/x/y/app/main.py"}},
                {"type": "tool_use", "name": "Bash", "input": {"command": "uv run pytest"}},
            ]
        },
    }
    items = chat_server.translate(tool)
    assert items[0] == {"kind": "text", "text": "확인해 볼게요."}
    assert items[1]["text"].startswith("파일 읽는 중")
    assert items[2]["text"] == "명령 실행 중: uv run pytest"

    done = chat_server.translate({"type": "result", "result": "끝", "is_error": False})
    assert done == [{"kind": "done", "text": "끝", "error": False}]


def test_secret_and_deploy_files_are_blocked():
    denied = " ".join(chat_server.DENIED_TOOLS)
    assert ".env" in denied
    assert "Dockerfile" in denied
    assert "git push" in denied


def test_app_never_imports_devtools():
    for path in Path("app").rglob("*.py"):
        assert "devtools" not in path.read_text(encoding="utf-8"), path


def _fake_stages(monkeypatch, review_results):
    """실제 Claude Code 를 부르지 않고 단계 실행을 흉내 낸다."""
    calls = []
    reviews = iter(review_results)

    def fake_stage(stage, prompt, round_no=1, claude_path=""):
        calls.append((stage, round_no, prompt))
        yield f"data: {stage}\n\n"
        text = next(reviews) if stage == "review" else f"{stage} 결과"
        return {"text": text, "error": False}

    monkeypatch.setattr(chat_server, "_stage", fake_stage)
    return calls


def test_pipeline_passes_when_review_passes(monkeypatch):
    calls = _fake_stages(monkeypatch, ["잘 됨\n검토 결과: 통과"])
    events = list(chat_server._pipeline_rest("요청", "이해"))
    assert [c[0] for c in calls] == ["analyze", "develop", "review"]
    assert '"error": false' in events[-1]


def test_pipeline_fixes_once_then_stops(monkeypatch):
    calls = _fake_stages(
        monkeypatch, ["검토 결과: 수정 필요 - 테스트 없음", "검토 결과: 수정 필요 - 아직 없음"]
    )
    events = list(chat_server._pipeline_rest("요청", "이해"))
    assert [c[0] for c in calls] == ["analyze", "develop", "review", "develop", "review"]
    assert "테스트 없음" in calls[3][2]  # 두 번째 개발에는 지적 내용이 전달된다
    assert '"error": true' in events[-1]  # 두 번 다 실패하면 멈춘다


def test_pipeline_second_round_can_pass(monkeypatch):
    calls = _fake_stages(monkeypatch, ["검토 결과: 수정 필요 - x", "검토 결과: 통과"])
    events = list(chat_server._pipeline_rest("요청", "이해"))
    assert [c[1] for c in calls if c[0] == "develop"] == [1, 2]
    assert '"error": false' in events[-1]


def test_first_stage_stops_at_gate(monkeypatch):
    _fake_stages(monkeypatch, [])
    events = list(chat_server._pipeline_first("요청"))
    assert '"kind": "gate"' in events[-1]


def test_first_stage_blocks_when_not_allowed(monkeypatch):
    def fake_stage(stage, prompt, round_no=1, claude_path=""):
        yield "data: x\n\n"
        return {
            "text": "개인정보 저장은 어렵습니다.\n진행 가능: 아니오 - 문의 필요",
            "error": False,
        }

    monkeypatch.setattr(chat_server, "_stage", fake_stage)
    events = list(chat_server._pipeline_first("요청"))
    assert '"kind": "gate"' not in events[-1]
    assert '"error": true' in events[-1]


def test_screen_path_reading():
    assert chat_server.screen_path("완료\n화면 주소: /earnings") == "/earnings"
    assert chat_server.screen_path("완료\n화면 주소: `/a/b`") == "/a/b"
    assert chat_server.screen_path("완료") == ""
    assert chat_server.screen_path("화면 주소: //evil.com") == ""  # 다른 사이트 주소는 받지 않는다
    assert chat_server.screen_path("화면 주소: http://evil.com") == ""


def test_done_tells_which_screen_to_open(monkeypatch):
    _fake_stages(monkeypatch, ["검토 결과: 통과"])
    monkeypatch.setattr(chat_server, "screen_path", lambda text: "/earnings")
    events = list(chat_server._pipeline_rest("요청", "이해"))
    assert '"path": "/earnings"' in events[-1]


def test_verdict_reading():
    assert chat_server.review_passed("문제 없음\n검토 결과: 통과")
    assert not chat_server.review_passed("검토 결과: 수정 필요 - 테스트")
    assert not chat_server.review_passed("아무 말이나 함")  # 읽을 수 없으면 통과로 보지 않는다
    assert chat_server.can_proceed("정리\n진행 가능: 예")
    assert not chat_server.can_proceed("정리\n진행 가능: 아니오 - 이유")


def test_stage_permissions_are_limited():
    for stage in ("understand", "analyze"):
        mode, allowed, denied = chat_server.stage_permissions(stage)
        assert allowed == []
        assert {"Edit", "Write", "Bash"} <= set(denied)
    _, allowed, denied = chat_server.stage_permissions("review")
    assert "Edit" in denied and "Write" in denied
    assert any(tool.startswith("Bash(uv run pytest") for tool in allowed)
    mode, allowed, denied = chat_server.stage_permissions("develop")
    assert mode == "acceptEdits"
    assert "Edit" not in denied  # 개발만 수정할 수 있다
    assert "Read(./.env)" in denied  # 그래도 비밀정보는 막는다


def test_empty_allow_list_is_not_passed():
    command = chat_server._build_command("claude", "understand")
    assert "--allowedTools" not in command
    assert "--disallowedTools" in command


def test_continue_is_protected():
    other = TestClient(chat_server.app, base_url="http://example.com")
    body = {"message": "a", "understanding": "b"}
    assert other.post("/continue", json=body).status_code == 403
    assert client.post("/continue", json={"message": "a", "understanding": ""}).status_code == 422


def test_busy_message_tells_which_stage(monkeypatch):
    monkeypatch.setitem(chat_server._active, "label", "개발 진행")
    monkeypatch.setitem(chat_server._active, "since", chat_server.time.monotonic())
    assert "개발 진행" in chat_server.busy_message()
    monkeypatch.setitem(chat_server._active, "label", "")
    assert "진행 중" in chat_server.busy_message()


def test_version_endpoint():
    assert client.get("/version").json()["version"] >= 2


def _agent_header(stage):
    """에이전트 md 파일 맨 위의 설정(--- 사이)을 읽는다."""
    text = (chat_server.AGENTS_DIR / f"{stage}.md").read_text(encoding="utf-8")
    header = text.split("---")[1]
    return dict(line.split(":", 1) for line in header.strip().splitlines())


def test_agent_files_exist_and_match_names():
    assert chat_server.missing_agents() == []
    for stage in chat_server.STAGE_LABELS:
        assert _agent_header(stage)["name"].strip() == stage


def test_agent_tools_follow_the_role():
    def tools(stage):
        return {t.strip() for t in _agent_header(stage)["tools"].split(",")}

    for stage in ("understand", "analyze"):
        assert tools(stage).isdisjoint({"Edit", "MultiEdit", "Write", "Bash"})
    assert tools("review").isdisjoint({"Edit", "MultiEdit", "Write"})
    assert "Bash" in tools("review")
    assert {"Edit", "Write", "Bash"} <= tools("develop")


def test_agent_markers_are_in_the_files():
    understand = (chat_server.AGENTS_DIR / "understand.md").read_text(encoding="utf-8")
    review = (chat_server.AGENTS_DIR / "review.md").read_text(encoding="utf-8")
    assert "진행 가능: 예" in understand and "진행 가능: 아니오" in understand
    assert "검토 결과: 통과" in review and "검토 결과: 수정 필요" in review
    develop = (chat_server.AGENTS_DIR / "develop.md").read_text(encoding="utf-8")
    assert "화면 주소:" in develop


def test_command_uses_agent_file():
    command = chat_server._build_command("claude", "develop")
    assert command[command.index("--agent") + 1] == "develop"

"""CSRF(요청 위조) 방어. 데이터를 보내는 요청이 우리 사이트 화면에서 온 것인지 확인한다.

브라우저는 POST 때 Origin(없으면 Referer)에 '요청을 보낸 사이트'를 붙여 보낸다.
이 주소의 사이트 이름이 접속한 사이트(Host)와 다르면 거절한다.
(쿠키·세션을 직접 만들지 않는 방식이다.)
"""

import logging
from urllib.parse import urlparse

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)


def verify_same_origin(request: Request) -> None:
    source = request.headers.get("origin") or request.headers.get("referer")
    host = request.headers.get("host")
    if not source or not host or urlparse(source).netloc != host:
        logger.warning("csrf_blocked")
        raise HTTPException(
            status_code=403, detail="잘못된 요청입니다. 화면을 새로 열어 다시 시도해 주세요."
        )

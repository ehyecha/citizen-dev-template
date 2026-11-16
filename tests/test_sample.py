def test_list_page_opens(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "예시 목록" in response.text


def test_create_item_then_show(client):
    response = client.post(
        "/items", data={"name": "원료A", "quantity": "10"}, follow_redirects=True
    )
    assert response.status_code == 200
    assert "원료A" in response.text


def test_invalid_input_shows_friendly_message(client):
    response = client.post("/items", data={"name": "", "quantity": "-5"})
    assert response.status_code == 400
    assert "다시 확인해 주세요" in response.text

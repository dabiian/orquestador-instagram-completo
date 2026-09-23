from app.api.task_api import TaskAPI


class Response:
    def __init__(self, code, payload=None):
        self.status_code = code
        self._payload = payload or {}
        self.text = ""

    def json(self):
        return self._payload


def test_claim_auth_failure_does_not_fall_back_to_legacy_queue(monkeypatch):
    monkeypatch.setenv("BOT_EXECUTOR_NAME", "Bot_Instagram_TEST")
    monkeypatch.setenv("TASK_API_TOKEN", "worker-secret")
    api = TaskAPI()
    called = []

    def post(url, **kwargs):
        called.append((url, kwargs))
        return Response(401)

    def get(*args, **kwargs):
        raise AssertionError("Authentication failures must not query pending_bots")

    monkeypatch.setattr("app.api.task_api.requests.post", post)
    monkeypatch.setattr("app.api.task_api.requests.get", get)
    available, tasks = api.get_pending_bots()
    assert available is True
    assert tasks == []
    assert called[0][1]["headers"]["Authorization"] == "Bearer worker-secret"


def test_only_missing_claim_endpoint_uses_legacy_queue(monkeypatch):
    monkeypatch.setenv("BOT_EXECUTOR_NAME", "Bot_Instagram_TEST")
    api = TaskAPI()
    monkeypatch.setattr("app.api.task_api.requests.post", lambda *a, **kw: Response(404))
    monkeypatch.setattr("app.api.task_api.requests.get", lambda *a, **kw: Response(200, [{"id": 7}]))
    assert api.get_pending_bots() == (True, [{"id": 7}])

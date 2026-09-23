from app.services.instagram_comment_generation_service import InstagramCommentGenerationService


class _AI:
    def __init__(self, response):
        self.response = response

    def get_bot_ia(self, *_args):
        return True, self.response


class _Media:
    def analyze_current_post_image(self):
        return True, "https://example.com/image.jpg", "A local business post"

    def get_current_post_context(self):
        return {"author_username": "test_user", "caption": "Supporting local growth"}


class _Account:
    def save_new_comment(self, *_args):
        return type("Response", (), {"status_code": 201, "text": "ok"})()


def _service(response):
    service = InstagramCommentGenerationService(
        {
            "campaign_type": "marketing",
            "social_media_account": {
                "id": 1,
                "bot_personality": {"id": 2, "language": "English"},
            },
        },
        _Account(),
        _AI(response),
        _Media(),
    )
    service.get_account_id = lambda: 1
    service.get_bot_personality_id = lambda: 2
    service.get_bot_personality_language = lambda: "English"
    service.get_used_messages_by_category = lambda _category: []
    service._build_used_messages_prompt = lambda *_args: ""
    service._build_language_prompt = lambda: "Output in English."
    service._validate_campaign_comment_policy = lambda *_args: True
    service._save_generated_comment = lambda **_kwargs: None
    return service


def test_text_only_parser_has_no_undefined_campaign_locals():
    service = _service('{"comment_text":"Here for real growth"}')
    parsed = service.parse_ai_comment_text_only_response(
        '{"comment_text":"Here for real growth"}',
        campaign_type="marketing",
        used_messages=[],
    )
    assert parsed["comment_text"] == "Here for real growth"


def test_image_comment_flow_has_no_undefined_validation_locals():
    service = _service(
        '{"comment_text":"Great local energy","metadata":{"source":"image_analysis"}}'
    )
    ok, comment = service.generate_comment_from_current_post_image()
    assert ok is True
    assert comment == "Great local energy"


def test_context_comment_flow_has_no_undefined_prompt_or_validation_locals():
    service = _service(
        '{"comment_text":"Love the community energy","metadata":{"source":"context"}}'
    )
    ok, comment = service.generate_comment_from_current_post_context()
    assert ok is True
    assert comment == "Love the community energy"


def test_safe_context_flow_passes_campaign_and_used_messages_to_parser():
    service = _service('{"comment_text":"Supporting genuine growth"}')
    calls = {}
    original = service.parse_ai_comment_text_only_response

    def wrapped(raw_response, campaign_type=None, used_messages=None):
        calls["campaign_type"] = campaign_type
        calls["used_messages"] = used_messages
        return original(raw_response, campaign_type=campaign_type, used_messages=used_messages)

    service.parse_ai_comment_text_only_response = wrapped
    ok, comment = service.generate_comment_from_current_post_context_safe()
    assert ok is True
    assert comment == "Supporting genuine growth"
    assert calls["campaign_type"] == "marketing"
    assert calls["used_messages"] == []

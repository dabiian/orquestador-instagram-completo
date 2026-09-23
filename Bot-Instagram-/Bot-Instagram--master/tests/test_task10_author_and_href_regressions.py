import types


def _service_with_text(text):
    from app.services.instagram_profile_service import InstagramProfileService

    class Driver:
        def execute_script(self, script):
            return ""

    class Browser:
        driver = Driver()

    service = InstagramProfileService(Browser())
    service.extract_opened_post_text_context = lambda: text
    service._warning = lambda *args, **kwargs: None
    return service


def test_author_fallback_extracts_header_username_from_spanish_runtime_context():
    text = (
        "55 likes, 4 comments - unison.coffee el August 21, 2026: caption | "
        "Foto del perfil de unison.coffee | Foto del perfil de 2023camiloromero"
    )
    # Locale may keep English month names while the connector label remains Spanish.
    service = _service_with_text(text)
    assert service.get_opened_post_author_username() == "unison.coffee"


def test_author_fallback_does_not_take_later_commenter_username():
    text = (
        "55 likes, 4 comments - target.business el August 21, 2026: caption | "
        "Foto del perfil de commenter_one | Foto del perfil de commenter_two"
    )
    service = _service_with_text(text)
    assert service.get_opened_post_author_username() == "target.business"


def test_author_fallback_supports_real_runtime_examples():
    from app.services.instagram_profile_service import InstagramProfileService

    examples = [
        ("4 comments - tophairsalon_alex el September 18, 2026: x", "tophairsalon_alex"),
        ("4 comments - asalONchicago el September 18, 2026: x", "asalonchicago"),
        ("4 comments - rudythebroker el September 18, 2026: x", "rudythebroker"),
        ("4 comments - __listedbymari el September 18, 2026: x", "__listedbymari"),
        ("4 comments - stephanie.englundsiegel el September 18, 2026: x", "stephanie.englundsiegel"),
        ("4 comments - ljs.construction_management el September 18, 2026: x", "ljs.construction_management"),
    ]
    for text, expected in examples:
        service = _service_with_text(text)
        assert service.get_opened_post_author_username() == expected


def test_task10_grid_rejects_nested_post_routes_and_accepts_canonical_posts():
    from app.tasks.instagram_followback.instagram_followback_navigation import InstagramFollowbackNavigationMixin

    task = object.__new__(InstagramFollowbackNavigationMixin)
    assert task._is_valid_hashtag_grid_post_href("https://www.instagram.com/p/ABC123/")
    assert task._is_valid_hashtag_grid_post_href("https://www.instagram.com/reel/ABC123/")
    assert not task._is_valid_hashtag_grid_post_href("https://www.instagram.com/p/ABC123/liked_by/")
    assert not task._is_valid_hashtag_grid_post_href("https://www.instagram.com/p/ABC123/comments/")
    assert not task._is_valid_hashtag_grid_post_href("https://www.instagram.com/some_user/")

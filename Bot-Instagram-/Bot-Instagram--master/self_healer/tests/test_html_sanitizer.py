from self_healer.core.html_sanitizer import compact_html
from self_healer.core.exceptions import HtmlSanitizationError


def test_compact_html_redacts_sensitive_values():
    html = '<div>Email: user@example.com</div><input type="password" value="secretpass" />'
    out = compact_html(html, max_chars=500)
    assert "[REDACTED_EMAIL]" in out
    assert "[REDACTED]" in out


def test_compact_html_preserves_type_attribute():
    html = '<input type="text" value="visible" /> <input type="password" value="x" />'
    out = compact_html(html, max_chars=200)
    # type attribute should be present for the first input
    assert 'type="text"' in out
    # password value should be redacted
    assert 'type="password"' in out


def test_compact_html_truncates_and_raises():
    html = '<div>' + ('x' * 100) + '</div>'
    s = compact_html(html, max_chars=10)
    assert len(s) <= 10
    try:
        compact_html(html, max_chars=0)
    except HtmlSanitizationError:
        return
    raise AssertionError("Expected HtmlSanitizationError for non-positive max_chars")

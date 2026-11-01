"""Core link/analytics tests."""
import pytest

from linkforge.core import (
    RESERVED,
    LinkStore,
    classify_referrer,
    detect_device,
    validate_target,
)


class TestValidation:
    def test_accepts_http_and_https(self):
        assert validate_target("https://example.com/a") == "https://example.com/a"
        assert validate_target("http://example.com") == "http://example.com"

    @pytest.mark.parametrize("bad", [
        "javascript:alert(1)",
        "data:text/html,<script>alert(1)</script>",
        "file:///etc/passwd",
        "ftp://example.com",
        "",
        "not a url",
        "https://",  # no host
    ])
    def test_rejects_dangerous_schemes(self, bad):
        """An unvalidated shortener is an open redirector / XSS vector."""
        with pytest.raises(ValueError):
            validate_target(bad)

    def test_rejects_overlong(self):
        with pytest.raises(ValueError):
            validate_target("https://a.com/" + "x" * 2100)

    def test_strips_whitespace(self):
        assert validate_target("  https://a.com  ") == "https://a.com"


class TestSlugs:
    def test_generated_slug_length(self):
        s = LinkStore()
        assert len(s.create("https://a.com").slug) == 7

    def test_generated_slugs_unique(self):
        s = LinkStore()
        slugs = {s.create("https://a.com").slug for _ in range(300)}
        assert len(slugs) == 300

    def test_custom_slug(self):
        s = LinkStore()
        assert s.create("https://a.com", slug="my-link").slug == "my-link"

    def test_duplicate_slug_rejected(self):
        s = LinkStore()
        s.create("https://a.com", slug="dup")
        with pytest.raises(ValueError, match="already taken"):
            s.create("https://b.com", slug="dup")

    def test_reserved_slug_rejected(self):
        s = LinkStore()
        with pytest.raises(ValueError, match="reserved"):
            s.create("https://a.com", slug="admin")

    def test_generated_slugs_never_reserved(self):
        s = LinkStore()
        for _ in range(200):
            assert s.create("https://a.com").slug.lower() not in RESERVED

    def test_bad_slug_charset_rejected(self):
        s = LinkStore()
        with pytest.raises(ValueError):
            s.create("https://a.com", slug="bad slug!")


class TestAnalytics:
    def test_resolve_records_click(self):
        s = LinkStore()
        link = s.create("https://a.com")
        assert s.resolve(link.slug) == "https://a.com"
        assert link.count == 1

    def test_inactive_link_does_not_resolve(self):
        s = LinkStore()
        link = s.create("https://a.com")
        s.deactivate(link.slug)
        assert s.resolve(link.slug) is None

    def test_unknown_slug_returns_none(self):
        assert LinkStore().resolve("nope") is None

    @pytest.mark.parametrize("ua,expected", [
        ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)", "mobile"),
        ("Mozilla/5.0 (Linux; Android 14)", "mobile"),
        ("Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "desktop"),
        ("Googlebot/2.1", "bot"),
        ("curl/8.0", "bot"),
        ("", "desktop"),
    ])
    def test_device_detection(self, ua, expected):
        assert detect_device(ua) == expected

    @pytest.mark.parametrize("ref,expected", [
        ("", "direct"),
        ("https://www.linkedin.com/feed/", "linkedin"),
        ("https://t.co/abc", "twitter"),
        ("https://www.google.co.uk/", "google"),
        ("https://instagram.com/x", "instagram"),
        ("https://somesite.io/x", "other"),
    ])
    def test_referrer_classification(self, ref, expected):
        assert classify_referrer(ref) == expected

    def test_stats_bucket_correctly(self):
        s = LinkStore()
        link = s.create("https://a.com")
        s.resolve(link.slug, referrer="https://linkedin.com/x", user_agent="iPhone")
        s.resolve(link.slug, referrer="https://linkedin.com/y", user_agent="Windows")
        st = s.stats(link.slug)
        assert st["clicks"] == 2
        assert st["by_referrer"] == {"linkedin": 2}
        assert st["by_device"] == {"mobile": 1, "desktop": 1}

    def test_stats_empty_link(self):
        s = LinkStore()
        link = s.create("https://a.com")
        st = s.stats(link.slug)
        assert st["clicks"] == 0 and st["first_click"] is None

    def test_stats_unknown_slug(self):
        assert LinkStore().stats("nope") is None

    def test_deactivate_unknown_returns_false(self):
        assert LinkStore().deactivate("nope") is False

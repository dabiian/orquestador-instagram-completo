from app.services.instagram_hashtag_navigation_guard import (
    canonical_hashtag_href,
    extract_hashtag_slug_from_href,
    hashtag_href_matches_slug,
    normalize_hashtag_slug,
)


def test_chicago_general_contractor_never_falls_back_to_sacramento():
    requested = normalize_hashtag_slug("#ChicagoGeneralContractor")
    unrelated = [
        "https://www.instagram.com/explore/tags/sacramento/",
        "https://www.instagram.com/explore/tags/yubacity/",
        "https://www.instagram.com/explore/tags/homeremodeling/",
        "https://www.instagram.com/explore/tags/kitchenremodel/",
        "https://www.instagram.com/explore/tags/bathroomremodel/",
    ]

    accepted = [href for href in unrelated if hashtag_href_matches_slug(href, requested)]

    assert accepted == []
    assert not hashtag_href_matches_slug(
        "https://www.instagram.com/explore/tags/sacramento/",
        requested,
    )


def test_exact_requested_hashtag_is_selected_even_if_unrelated_link_is_first():
    requested = normalize_hashtag_slug("#ChicagoGeneralContractor")
    candidates = [
        "https://www.instagram.com/explore/tags/sacramento/",
        "https://www.instagram.com/explore/tags/chicagogeneralcontractor/",
        "https://www.instagram.com/explore/tags/chicagogeneralcontractors/",
    ]

    accepted = [href for href in candidates if hashtag_href_matches_slug(href, requested)]

    assert accepted == [
        "https://www.instagram.com/explore/tags/chicagogeneralcontractor/"
    ]


def test_near_match_is_rejected():
    requested = normalize_hashtag_slug("#ChicagoConstruction")
    assert not hashtag_href_matches_slug(
        "https://www.instagram.com/explore/tags/chicagoconstructioncompany/",
        requested,
    )
    assert not hashtag_href_matches_slug(
        "https://www.instagram.com/explore/tags/chicagoconstructionexperts/",
        requested,
    )


def test_case_query_string_and_trailing_slash_are_normalized():
    href = "https://www.instagram.com/explore/tags/CHICAGOCONSTRUCTION/?foo=1"
    requested = "#ChicagoConstruction"

    assert extract_hashtag_slug_from_href(href) == "chicagoconstruction"
    assert hashtag_href_matches_slug(href, requested)
    assert canonical_hashtag_href(href) == (
        "https://www.instagram.com/explore/tags/chicagoconstruction/"
    )


def test_non_hashtag_links_are_never_accepted():
    assert extract_hashtag_slug_from_href("https://www.instagram.com/p/ABC123/") == ""
    assert not hashtag_href_matches_slug(
        "https://www.instagram.com/p/ABC123/",
        "chicagoconstruction",
    )


def test_empty_or_malformed_inputs_fail_closed():
    assert normalize_hashtag_slug("") == ""
    assert extract_hashtag_slug_from_href("") == ""
    assert not hashtag_href_matches_slug("", "chicagoconstruction")
    assert canonical_hashtag_href("not-an-instagram-url") == ""

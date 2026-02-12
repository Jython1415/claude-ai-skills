"""Tests for bsky_sets: actor collections with set operations."""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "bluesky"))

from bsky_sets import (
    Actor,
    ActorSet,
    _normalize_actor,
    actors,
    estimate_followers,
    estimate_follows,
    estimate_likes,
    estimate_reposts,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ALICE = Actor(did="did:plc:alice", handle="alice.bsky.social", display_name="Alice")
BOB = Actor(did="did:plc:bob", handle="bob.bsky.social", display_name="Bob")
CAROL = Actor(did="did:plc:carol", handle="carol.bsky.social", display_name="Carol")


# ---------------------------------------------------------------------------
# Actor
# ---------------------------------------------------------------------------


class TestActor:
    def test_equality_by_did(self):
        a1 = Actor(did="did:plc:x", handle="a.bsky.social", display_name="A")
        a2 = Actor(did="did:plc:x", handle="different.handle", display_name="Different")
        assert a1 == a2

    def test_inequality_different_did(self):
        assert ALICE != BOB

    def test_hash_by_did(self):
        a1 = Actor(did="did:plc:x", handle="a", display_name="A")
        a2 = Actor(did="did:plc:x", handle="b", display_name="B")
        assert hash(a1) == hash(a2)
        assert len({a1, a2}) == 1

    def test_not_equal_to_non_actor(self):
        assert ALICE != "did:plc:alice"
        assert ALICE != 42

    def test_repr(self):
        assert "Alice" in repr(ALICE)
        assert "@alice.bsky.social" in repr(ALICE)


# ---------------------------------------------------------------------------
# ActorSet basics
# ---------------------------------------------------------------------------


class TestActorSet:
    def test_empty(self):
        s = ActorSet()
        assert len(s) == 0
        assert not s
        assert list(s) == []

    def test_from_list(self):
        s = ActorSet([ALICE, BOB])
        assert len(s) == 2
        assert s

    def test_deduplicates_by_did(self):
        dup = Actor(did=ALICE.did, handle="other", display_name="Other")
        s = ActorSet([ALICE, dup])
        assert len(s) == 1

    def test_contains_actor(self):
        s = ActorSet([ALICE, BOB])
        assert ALICE in s
        assert CAROL not in s

    def test_contains_did_string(self):
        s = ActorSet([ALICE])
        assert "did:plc:alice" in s
        assert "did:plc:bob" not in s

    def test_contains_rejects_other_types(self):
        s = ActorSet([ALICE])
        assert 42 not in s

    def test_iter(self):
        s = ActorSet([ALICE, BOB])
        actors_list = list(s)
        assert len(actors_list) == 2
        dids = {a.did for a in actors_list}
        assert dids == {"did:plc:alice", "did:plc:bob"}

    def test_repr(self):
        s = ActorSet([ALICE, BOB])
        assert "2 actors" in repr(s)

    def test_dids_property(self):
        s = ActorSet([ALICE, BOB])
        assert s.dids == {"did:plc:alice", "did:plc:bob"}

    def test_sorted_by_handle(self):
        s = ActorSet([CAROL, ALICE, BOB])
        result = s.sorted("handle")
        handles = [a.handle for a in result]
        assert handles == sorted(handles)

    def test_sorted_by_display_name(self):
        s = ActorSet([CAROL, ALICE, BOB])
        result = s.sorted("display_name")
        names = [a.display_name for a in result]
        assert names == sorted(names)


# ---------------------------------------------------------------------------
# Set operations
# ---------------------------------------------------------------------------


class TestSetOperations:
    def test_intersection(self):
        s1 = ActorSet([ALICE, BOB])
        s2 = ActorSet([BOB, CAROL])
        result = s1 & s2
        assert len(result) == 1
        assert BOB in result

    def test_union(self):
        s1 = ActorSet([ALICE, BOB])
        s2 = ActorSet([BOB, CAROL])
        result = s1 | s2
        assert len(result) == 3

    def test_difference(self):
        s1 = ActorSet([ALICE, BOB])
        s2 = ActorSet([BOB, CAROL])
        result = s1 - s2
        assert len(result) == 1
        assert ALICE in result
        assert BOB not in result

    def test_intersection_empty(self):
        s1 = ActorSet([ALICE])
        s2 = ActorSet([BOB])
        result = s1 & s2
        assert len(result) == 0
        assert not result

    def test_union_with_empty(self):
        s1 = ActorSet([ALICE])
        s2 = ActorSet()
        assert len(s1 | s2) == 1
        assert len(s2 | s1) == 1

    def test_difference_with_empty(self):
        s1 = ActorSet([ALICE, BOB])
        s2 = ActorSet()
        result = s1 - s2
        assert len(result) == 2

    def test_chained_operations(self):
        s1 = ActorSet([ALICE, BOB, CAROL])
        s2 = ActorSet([BOB])
        s3 = ActorSet([CAROL])
        result = (s1 - s2) & s3
        assert len(result) == 1
        assert CAROL in result


# ---------------------------------------------------------------------------
# _normalize_actor
# ---------------------------------------------------------------------------


class TestNormalizeActor:
    def test_direct_actor_object(self):
        raw = {"did": "did:plc:x", "handle": "x.bsky.social", "displayName": "X"}
        actor = _normalize_actor(raw)
        assert actor.did == "did:plc:x"
        assert actor.handle == "x.bsky.social"
        assert actor.display_name == "X"

    def test_wrapped_actor_object(self):
        """getLikes/getRepostedBy wrap actors under an 'actor' key."""
        raw = {
            "createdAt": "2024-01-01T00:00:00Z",
            "actor": {"did": "did:plc:y", "handle": "y.bsky.social", "displayName": "Y"},
        }
        actor = _normalize_actor(raw)
        assert actor.did == "did:plc:y"
        assert actor.handle == "y.bsky.social"
        assert actor.display_name == "Y"

    def test_missing_display_name(self):
        raw = {"did": "did:plc:z", "handle": "z.bsky.social"}
        actor = _normalize_actor(raw)
        assert actor.display_name == ""


# ---------------------------------------------------------------------------
# Actor producers
# ---------------------------------------------------------------------------


def _raw_actor(did, handle, display_name):
    """Build a raw API actor dict."""
    return {"did": did, "handle": handle, "displayName": display_name}


def _raw_like(did, handle, display_name):
    """Build a raw getLikes item (actor is nested)."""
    return {"createdAt": "2024-01-01T00:00:00Z", "actor": _raw_actor(did, handle, display_name)}


class TestActorProducers:
    @patch("bsky_sets.paginate")
    @patch("bsky_sets.resolve_handle_to_did", return_value="did:plc:alice")
    def test_follows(self, mock_resolve, mock_paginate):
        mock_paginate.return_value = [
            _raw_actor("did:plc:bob", "bob", "Bob"),
        ]
        result = actors.follows("alice.bsky.social")

        mock_resolve.assert_called_once_with("alice.bsky.social")
        mock_paginate.assert_called_once_with(
            "app.bsky.graph.getFollows",
            {"actor": "did:plc:alice"},
            "follows",
            max_items=None,
        )
        assert len(result) == 1
        assert isinstance(result, ActorSet)

    @patch("bsky_sets.paginate")
    @patch("bsky_sets.resolve_handle_to_did", return_value="did:plc:alice")
    def test_followers(self, mock_resolve, mock_paginate):
        mock_paginate.return_value = [
            _raw_actor("did:plc:bob", "bob", "Bob"),
            _raw_actor("did:plc:carol", "carol", "Carol"),
        ]
        result = actors.followers("alice.bsky.social")

        mock_paginate.assert_called_once_with(
            "app.bsky.graph.getFollowers",
            {"actor": "did:plc:alice"},
            "followers",
            max_items=None,
        )
        assert len(result) == 2

    @patch("bsky_sets.paginate")
    def test_likes_default_max(self, mock_paginate):
        mock_paginate.return_value = [_raw_like("did:plc:x", "x", "X")]
        actors.likes("at://did:plc:a/app.bsky.feed.post/123")

        mock_paginate.assert_called_once_with(
            "app.bsky.feed.getLikes",
            {"uri": "at://did:plc:a/app.bsky.feed.post/123"},
            "likes",
            max_items=1000,
        )

    @patch("bsky_sets.paginate")
    def test_likes_custom_max(self, mock_paginate):
        mock_paginate.return_value = []
        actors.likes("at://did:plc:a/app.bsky.feed.post/123", max=50)

        _, kwargs = mock_paginate.call_args
        assert kwargs["max_items"] == 50

    @patch("bsky_sets.paginate")
    def test_likes_no_max(self, mock_paginate):
        mock_paginate.return_value = []
        actors.likes("at://did:plc:a/app.bsky.feed.post/123", max=None)

        _, kwargs = mock_paginate.call_args
        assert kwargs["max_items"] is None

    @patch("bsky_sets.paginate")
    def test_reposts_default_max(self, mock_paginate):
        mock_paginate.return_value = []
        actors.reposts("at://did:plc:a/app.bsky.feed.post/123")

        mock_paginate.assert_called_once_with(
            "app.bsky.feed.getRepostedBy",
            {"uri": "at://did:plc:a/app.bsky.feed.post/123"},
            "repostedBy",
            max_items=1000,
        )

    @patch("bsky_sets.paginate")
    @patch("bsky_sets.resolve_handle_to_did", return_value="did:plc:alice")
    def test_known_followers(self, mock_resolve, mock_paginate):
        mock_paginate.return_value = []
        actors.known_followers("alice.bsky.social")

        mock_paginate.assert_called_once_with(
            "app.bsky.graph.getKnownFollowers",
            {"actor": "did:plc:alice"},
            "followers",
            max_items=None,
        )

    @patch("bsky_sets.paginate")
    def test_did_input_skips_resolution(self, mock_paginate):
        """Passing a DID directly should not call resolve_handle_to_did."""
        mock_paginate.return_value = []
        with patch("bsky_sets.resolve_handle_to_did") as mock_resolve:
            actors.follows("did:plc:already_resolved")
            mock_resolve.assert_not_called()


# ---------------------------------------------------------------------------
# Estimate functions
# ---------------------------------------------------------------------------


class TestEstimateFunctions:
    @patch("bsky_sets.api")
    def test_estimate_likes(self, mock_api):
        mock_api.get.return_value = {"posts": [{"likeCount": 42}]}
        assert estimate_likes("at://did:plc:x/app.bsky.feed.post/y") == 42
        mock_api.get.assert_called_once_with(
            "app.bsky.feed.getPosts",
            {"uris": ["at://did:plc:x/app.bsky.feed.post/y"]},
        )

    @patch("bsky_sets.api")
    def test_estimate_likes_no_posts(self, mock_api):
        mock_api.get.return_value = {"posts": []}
        assert estimate_likes("at://did:plc:x/app.bsky.feed.post/y") == 0

    @patch("bsky_sets.api")
    def test_estimate_reposts(self, mock_api):
        mock_api.get.return_value = {"posts": [{"repostCount": 10}]}
        assert estimate_reposts("at://did:plc:x/app.bsky.feed.post/y") == 10

    @patch("bsky_sets.api")
    def test_estimate_followers(self, mock_api):
        mock_api.get.return_value = {"followersCount": 500}
        assert estimate_followers("alice.bsky.social") == 500
        mock_api.get.assert_called_once_with("app.bsky.actor.getProfile", {"actor": "alice.bsky.social"})

    @patch("bsky_sets.api")
    def test_estimate_follows(self, mock_api):
        mock_api.get.return_value = {"followsCount": 200}
        assert estimate_follows("alice.bsky.social") == 200

    @patch("bsky_sets.api")
    def test_estimate_missing_field_defaults_zero(self, mock_api):
        mock_api.get.return_value = {"posts": [{}]}
        assert estimate_likes("at://x") == 0

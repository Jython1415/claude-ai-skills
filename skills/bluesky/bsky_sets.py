"""
Set-based operations on Bluesky actor collections.

Wraps paginated Bluesky API endpoints into ActorSet objects that support
standard Python set operations (&, |, -). Handles cursor-based pagination
internally so callers get complete collections.

Usage:
    from bsky_sets import actors

    my_follows = actors.follows("joshuashew.bsky.social")
    post_likers = actors.likes("at://did:plc:.../app.bsky.feed.post/3mel...")

    mutual = my_follows & post_likers
    for a in mutual:
        print(f"{a.display_name} (@{a.handle})")
"""

from __future__ import annotations

from dataclasses import dataclass

from bsky_client import api, paginate, resolve_handle_to_did


@dataclass(frozen=True, slots=True)
class Actor:
    """A Bluesky actor with minimal identifying fields."""

    did: str
    handle: str
    display_name: str

    def __hash__(self) -> int:
        return hash(self.did)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Actor):
            return self.did == other.did
        return NotImplemented

    def __repr__(self) -> str:
        return f"Actor({self.display_name!r}, @{self.handle})"


class ActorSet:
    """A set of Bluesky actors supporting standard set operations.

    Internally stores DIDs in a set for O(1) lookups, with a separate
    dict mapping DIDs to Actor objects for metadata access.
    """

    def __init__(self, actors: list[Actor] | None = None):
        self._actors: dict[str, Actor] = {}
        if actors:
            for actor in actors:
                self._actors[actor.did] = actor

    @classmethod
    def _from_dict(cls, actors: dict[str, Actor]) -> ActorSet:
        """Construct directly from an internal dict (avoids re-indexing)."""
        s = cls.__new__(cls)
        s._actors = actors
        return s

    def __and__(self, other: ActorSet) -> ActorSet:
        common_dids = self._actors.keys() & other._actors.keys()
        return ActorSet._from_dict({d: self._actors[d] for d in common_dids})

    def __or__(self, other: ActorSet) -> ActorSet:
        merged = {**self._actors, **other._actors}
        return ActorSet._from_dict(merged)

    def __sub__(self, other: ActorSet) -> ActorSet:
        diff_dids = self._actors.keys() - other._actors.keys()
        return ActorSet._from_dict({d: self._actors[d] for d in diff_dids})

    def __contains__(self, item: object) -> bool:
        if isinstance(item, Actor):
            return item.did in self._actors
        if isinstance(item, str):
            return item in self._actors
        return False

    def __iter__(self):
        return iter(self._actors.values())

    def __len__(self) -> int:
        return len(self._actors)

    def __bool__(self) -> bool:
        return bool(self._actors)

    def __repr__(self) -> str:
        return f"ActorSet({len(self)} actors)"

    @property
    def dids(self) -> set[str]:
        """Return the set of DIDs in this collection."""
        return set(self._actors.keys())

    def sorted(self, key: str = "handle") -> list[Actor]:
        """Return actors sorted by the given field (handle or display_name)."""
        return sorted(self._actors.values(), key=lambda a: getattr(a, key, ""))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _normalize_actor(raw: dict) -> Actor:
    """Extract an Actor from a Bluesky API response object.

    Handles both direct actor objects (from getFollows, getFollowers) and
    wrapper objects (from getLikes, getRepostedBy) where the actor is nested
    under an 'actor' key.
    """
    if "actor" in raw and isinstance(raw["actor"], dict):
        raw = raw["actor"]
    return Actor(
        did=raw.get("did", ""),
        handle=raw.get("handle", ""),
        display_name=raw.get("displayName", ""),
    )


def _resolve_actor(actor: str) -> str:
    """Ensure actor is a DID. Resolves handles if needed."""
    if actor.startswith("did:"):
        return actor
    return resolve_handle_to_did(actor)


# ---------------------------------------------------------------------------
# ActorSet producers
# ---------------------------------------------------------------------------


class _Actors:
    """Namespace for ActorSet producer functions."""

    @staticmethod
    def follows(actor: str, *, max: int | None = None) -> ActorSet:
        """Get accounts that an actor follows.

        Args:
            actor: Handle or DID.
            max: Stop after this many actors. None = fetch all.
        """
        did = _resolve_actor(actor)
        raw = paginate(
            "app.bsky.graph.getFollows",
            {"actor": did},
            "follows",
            max_items=max,
        )
        return ActorSet([_normalize_actor(r) for r in raw])

    @staticmethod
    def followers(actor: str, *, max: int | None = None) -> ActorSet:
        """Get an actor's followers.

        Args:
            actor: Handle or DID.
            max: Stop after this many actors. None = fetch all.
        """
        did = _resolve_actor(actor)
        raw = paginate(
            "app.bsky.graph.getFollowers",
            {"actor": did},
            "followers",
            max_items=max,
        )
        return ActorSet([_normalize_actor(r) for r in raw])

    @staticmethod
    def likes(uri: str, *, max: int | None = 1000) -> ActorSet:
        """Get actors who liked a post.

        Args:
            uri: AT-URI of the post.
            max: Stop after this many actors. Defaults to 1000 (10 pages)
                 since popular posts can have tens of thousands of likes.
                 Use estimate_likes() to check the count first.
        """
        raw = paginate(
            "app.bsky.feed.getLikes",
            {"uri": uri},
            "likes",
            max_items=max,
        )
        return ActorSet([_normalize_actor(r) for r in raw])

    @staticmethod
    def reposts(uri: str, *, max: int | None = 1000) -> ActorSet:
        """Get actors who reposted a post.

        Args:
            uri: AT-URI of the post.
            max: Stop after this many actors. Defaults to 1000 (10 pages)
                 since popular posts can have many reposts.
                 Use estimate_reposts() to check the count first.
        """
        raw = paginate(
            "app.bsky.feed.getRepostedBy",
            {"uri": uri},
            "repostedBy",
            max_items=max,
        )
        return ActorSet([_normalize_actor(r) for r in raw])

    @staticmethod
    def known_followers(actor: str, *, max: int | None = None) -> ActorSet:
        """Get followers of an actor that you also follow (requires auth).

        Args:
            actor: Handle or DID.
            max: Stop after this many actors. None = fetch all.

        Raises:
            AuthRequiredError: If SESSION_ID and PROXY_URL are not set.
        """
        did = _resolve_actor(actor)
        raw = paginate(
            "app.bsky.graph.getKnownFollowers",
            {"actor": did},
            "followers",
            max_items=max,
        )
        return ActorSet([_normalize_actor(r) for r in raw])


actors = _Actors()


# ---------------------------------------------------------------------------
# Estimation helpers (preflight count checks)
# ---------------------------------------------------------------------------


def estimate_likes(uri: str) -> int:
    """Get the like count for a post without fetching any likers.

    Makes a single API call to getPosts to read the likeCount field.
    """
    data = api.get("app.bsky.feed.getPosts", {"uris": [uri]})
    posts = data.get("posts", [])
    if not posts:
        return 0
    return posts[0].get("likeCount", 0)


def estimate_reposts(uri: str) -> int:
    """Get the repost count for a post without fetching any reposters.

    Makes a single API call to getPosts to read the repostCount field.
    """
    data = api.get("app.bsky.feed.getPosts", {"uris": [uri]})
    posts = data.get("posts", [])
    if not posts:
        return 0
    return posts[0].get("repostCount", 0)


def estimate_followers(actor: str) -> int:
    """Get the follower count for an actor without fetching any followers.

    Makes a single API call to getProfile to read the followersCount field.
    """
    data = api.get("app.bsky.actor.getProfile", {"actor": actor})
    return data.get("followersCount", 0)


def estimate_follows(actor: str) -> int:
    """Get the follows count for an actor without fetching any follows.

    Makes a single API call to getProfile to read the followsCount field.
    """
    data = api.get("app.bsky.actor.getProfile", {"actor": actor})
    return data.get("followsCount", 0)

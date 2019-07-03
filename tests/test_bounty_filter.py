import pytest

from polyswarmclient.bountyfilter import BountyFilter


@pytest.mark.asyncio
async def test_pad_fills_empty_to_length():
    # arrange
    metadata = []
    # act
    padded = BountyFilter.pad_metadata(metadata, 2)
    # assert
    assert padded == [None] * 2


# noinspection PyTypeChecker
@pytest.mark.asyncio
async def test_pad_fills_none_to_length():
    # arrange
    metadata = None
    # act
    padded = BountyFilter.pad_metadata(metadata, 2)
    # assert
    assert padded == [None] * 2


@pytest.mark.asyncio
async def test_pad_fills_to_length():
    # arrange
    metadata = [{"mimetype": "text/plain"}]
    # act
    padded = BountyFilter.pad_metadata(metadata, 2)
    # assert
    assert padded == [{"mimetype": "text/plain"}, None]


@pytest.mark.asyncio
async def test_pad_fills_with_none_on_invalid_metadata():
    # arrange
    metadata = [{"asdf": "asdf"}]
    # act
    padded = BountyFilter.pad_metadata(metadata, 2)
    # assert
    assert padded == [None] * 2


@pytest.mark.asyncio
async def test_no_pad_on_match_length():
    # arrange
    metadata = [{"mimetype": "text/plain"}] * 5
    # act
    padded = BountyFilter.pad_metadata(metadata, 5)
    # assert
    assert padded == metadata


@pytest.mark.asyncio
async def test_no_pad_on_too_long():
    # arrange
    metadata = [{"mimetype": "text/plain"}] * 10
    # act
    padded = BountyFilter.pad_metadata(metadata, 5)
    # assert
    assert padded == metadata


@pytest.mark.asyncio
async def test_not_excluded():
    # arrange
    bounty_filter = BountyFilter(None, [("mimetype", "text/plain")])
    # act
    allowed = bounty_filter.is_allowed({"mimetype": "text/html"})
    # assert
    assert allowed


@pytest.mark.asyncio
async def test_excluded():
    # arrange
    bounty_filter = BountyFilter(None, [("mimetype", "text/plain")])
    # act
    allowed = bounty_filter.is_allowed({"mimetype": "text/plain"})
    # assert
    assert not allowed


@pytest.mark.asyncio
async def test_any_excluded():
    # arrange
    bounty_filter = BountyFilter(None, [("mimetype", "text/plain"), ("mimetype", "text/html")])
    # act
    allowed = bounty_filter.is_allowed({"mimetype": "text/html"})
    # assert
    assert not allowed


@pytest.mark.asyncio
async def test_not_accepted():
    # arrange
    bounty_filter = BountyFilter([("mimetype", "text/plain")], None)
    # act
    allowed = bounty_filter.is_allowed({"mimetype": "text/html"})
    # assert
    assert not allowed


@pytest.mark.asyncio
async def test__accepted():
    # arrange
    bounty_filter = BountyFilter([("mimetype", "text/plain")], None)
    # act
    allowed = bounty_filter.is_allowed({"mimetype": "text/plain"})
    # assert
    assert allowed


@pytest.mark.asyncio
async def test_scans_artifact_accepted_match_only_one():
    # arrange
    bounty_filter = BountyFilter([("mimetype", "text/plain"), ("mimetype", "text/html")], None)
    # act
    allowed = bounty_filter.is_allowed({"mimetype": "text/html"})
    # assert
    assert allowed

import asyncio
import pytest

from polyswarmclient import events


@pytest.mark.asyncio
async def test_callback():
    cb = events.Callback()

    async def one_times(x):
        return x

    async def two_times(x):
        return 2 * x

    async def three_times(x):
        return 3 * x

    cb.register(one_times)
    cb.register(two_times)
    cb.register(three_times)

    assert await cb.run(2) == [2, 4, 6]

    cb.remove(three_times)

    assert await cb.run(3) == [3, 6]

    def four_times(x):
        return 4 * x

    cb.register(four_times)

    # Non-async callback
    with pytest.raises(TypeError):
        await cb.run(4)


@pytest.mark.asyncio
async def test_on_run_callback():
    cb = events.OnRunCallback()

    async def check_parameters(chain):
        return chain == 'home'

    cb.register(check_parameters)

    assert await cb.run(chain='home') == [True]
    assert await cb.run(chain='side') == [False]

    async def invalid_signature(chain, foo):
        return False

    cb.register(invalid_signature)

    with pytest.raises(TypeError):
        await cb.run(chain='home')


@pytest.mark.asyncio
async def test_on_new_block_callback():
    cb = events.OnNewBlockCallback()

    async def check_parameters(number, chain):
        return number == 42 and chain == 'home'

    cb.register(check_parameters)

    assert await cb.run(number=42, chain='home') == [True]
    assert await cb.run(number=42, chain='side') == [False]

    async def invalid_signature(number, chain, foo):
        return False

    cb.register(invalid_signature)

    with pytest.raises(TypeError):
        await cb.run(number=42, chain='home')


@pytest.mark.asyncio
async def test_on_new_bounty_callback():
    cb = events.OnNewBountyCallback()

    async def check_parameters(guid, author, amount, uri, expiration, chain):
        return guid == 'guid' and author == 'author' and amount == 42 and uri == 'uri' and expiration == 100 and chain == 'home'

    cb.register(check_parameters)

    assert await cb.run(guid='guid', author='author', amount=42, uri='uri', expiration=100, chain='home') == [True]
    assert await cb.run(guid='not guid', author='author', amount=42, uri='uri', expiration=100, chain='home') == [False]

    async def invalid_signature(guid, author, amount, uri, expiration, chain, foo):
        return False

    cb.register(invalid_signature)

    with pytest.raises(TypeError):
        await cb.run(guid='guid', author='author', amount=42, uri='uri', expiration=100, chain='home')


@pytest.mark.asyncio
async def test_on_new_assertion_callback():
    cb = events.OnNewAssertionCallback()

    async def check_parameters(bounty_guid, author, index, bid, mask, commitment, chain):
        return bounty_guid == 'guid' and author == 'author' and bid == 1 and index == 0 and mask == [
            True] and commitment == 42 and chain == 'home'

    cb.register(check_parameters)

    assert await cb.run(bounty_guid='guid', author='author', bid=1, index=0, mask=[True], commitment=42,
                        chain='home') == [True]
    assert await cb.run(bounty_guid='not guid', author='author', bid=1, index=0, mask=[True], commitment=42,
                        chain='home') == [False]

    async def invalid_signature(bounty_guid, author, index, bid, mask, commitment, chain, foo):
        return False

    cb.register(invalid_signature)

    with pytest.raises(TypeError):
        await cb.run(bounty_guid='guid', author='author', index=0, mask=[True], commitment=42, chain='home')


@pytest.mark.asyncio
async def test_on_reveal_assertion_callback():
    cb = events.OnRevealAssertionCallback()

    async def check_parameters(bounty_guid, author, index, nonce, verdicts, metadata, chain):
        return bounty_guid == 'guid' and author == 'author' and index == 0 and nonce == 42 and verdicts == [
            True] and metadata == '' and chain == 'home'

    cb.register(check_parameters)

    assert await cb.run(bounty_guid='guid', author='author', index=0, nonce=42, verdicts=[True], metadata='',
                        chain='home') == [True]
    assert await cb.run(bounty_guid='not guid', author='author', index=0, nonce=42, verdicts=[True], metadata='',
                        chain='home') == [False]

    async def invalid_signature(bounty_guid, author, index, nonce, verdicts, metadata, chain, foo):
        return False

    cb.register(invalid_signature)

    with pytest.raises(TypeError):
        await cb.run(bounty_guid='guid', author='author', index=0, nonce=42, verdicts=[True], metadata='', chain='home')


@pytest.mark.asyncio
async def test_on_new_vote_callback():
    cb = events.OnNewVoteCallback()

    async def check_parameters(bounty_guid, votes, voter, chain):
        return bounty_guid == 'guid' and votes == [True] and voter == 'voter' and chain == 'home'

    cb.register(check_parameters)

    assert await cb.run(bounty_guid='guid', votes=[True], voter='voter', chain='home') == [True]
    assert await cb.run(bounty_guid='not guid', votes=[True], voter='voter', chain='home') == [False]

    async def invalid_signature(bounty_guid, votes, voter, chain, foo):
        return False

    cb.register(invalid_signature)

    with pytest.raises(TypeError):
        await cb.run(bounty_guid='guid', votes=[True], voter='voter', chain='home')


@pytest.mark.asyncio
async def test_on_quorum_reached_callback():
    cb = events.OnQuorumReachedCallback()

    async def check_parameters(bounty_guid, quorum_block, chain):
        return bounty_guid == 'guid' and quorum_block == 42 and chain == 'home'

    cb.register(check_parameters)

    assert await cb.run(bounty_guid='guid', quorum_block=42, chain='home') == [True]
    assert await cb.run(bounty_guid='not guid', quorum_block=42, chain='home') == [False]

    async def invalid_signature(bounty_guid, quorum_block, chain, foo):
        return False

    cb.register(invalid_signature)

    with pytest.raises(TypeError):
        await cb.run(bounty_guid='guid', quorum_block=42, chain='home')


@pytest.mark.asyncio
async def test_on_settled_bounty_callback():
    cb = events.OnSettledBountyCallback()

    async def check_parameters(bounty_guid, settled_block, settler, chain):
        return bounty_guid == 'guid' and settled_block == 42 and settler == 'settler' and chain == 'home'

    cb.register(check_parameters)

    assert await cb.run(bounty_guid='guid', settled_block=42, settler='settler', chain='home') == [True]
    assert await cb.run(bounty_guid='not guid', settled_block=42, settler='settler', chain='home') == [False]

    async def invalid_signature(bounty_guid, settled_block, settler, chain, foo):
        return False

    cb.register(invalid_signature)

    with pytest.raises(TypeError):
        await cb.run(bounty_guid='guid', settled_block=42, settler='settler', chain='home')


@pytest.mark.asyncio
async def test_on_initialized_channel_callback():
    cb = events.OnInitializedChannelCallback()

    async def check_parameters(guid, ambassador, expert, multi_signature):
        return guid == 'guid' and ambassador == 'ambassador' and expert == 'expert' and multi_signature == 'multi_signature'

    cb.register(check_parameters)

    assert await cb.run(guid='guid', ambassador='ambassador', expert='expert', multi_signature='multi_signature') == [
        True]
    assert await cb.run(guid='not guid', ambassador='ambassador', expert='expert',
                        multi_signature='multi_signature') == [False]

    async def invalid_signature(guid, ambassador, expert, multi_signature, foo):
        return False

    cb.register(invalid_signature)

    with pytest.raises(TypeError):
        await cb.run(guid='guid', ambassador='ambassador', expert='expert', multi_signature='multi_signature')


def test_schedule():
    s = events.Schedule()
    assert s.empty()

    s.put(2, events.VoteOnBounty('guid', [True], True))
    s.put(1, events.RevealAssertion('guid', 1, 42, [True], ''))
    s.put(3, events.SettleBounty('guid'))

    assert not s.empty()

    assert type(s.peek()[1]) == events.RevealAssertion

    assert type(s.get()[1]) == events.RevealAssertion
    assert type(s.get()[1]) == events.VoteOnBounty
    assert type(s.get()[1]) == events.SettleBounty


@pytest.mark.asyncio
async def test_on_reveal_assertion_due_callback():
    cb = events.OnRevealAssertionDueCallback()

    async def check_parameters(bounty_guid, index, nonce, verdicts, metadata, chain):
        return bounty_guid == 'guid' and index == 0 and nonce == 42 and verdicts == [
            True] and metadata == '' and chain == 'home'

    cb.register(check_parameters)

    assert await cb.run(bounty_guid='guid', index=0, nonce=42, verdicts=[True], metadata='', chain='home') == [True]
    assert await cb.run(bounty_guid='not guid', index=0, nonce=42, verdicts=[True], metadata='', chain='home') == [
        False]

    async def invalid_signature(bounty_guid, index, nonce, verdicts, metadata, chain, foo):
        return False

    cb.register(invalid_signature)

    with pytest.raises(TypeError):
        await cb.run(bounty_guid='guid', index=0, nonce=42, verdicts=[True], metadata='', chain='home')


@pytest.mark.asyncio
async def test_on_vote_on_bounty_due_callback():
    cb = events.OnVoteOnBountyDueCallback()

    async def check_parameters(bounty_guid, votes, valid_bloom, chain):
        return bounty_guid == 'guid' and votes == [True] and valid_bloom and chain == 'home'

    cb.register(check_parameters)

    assert await cb.run(bounty_guid='guid', votes=[True], valid_bloom=True, chain='home') == [True]
    assert await cb.run(bounty_guid='not guid', votes=[True], valid_bloom=True, chain='home') == [False]

    async def invalid_signature(bounty_guid, votes, valid_bloom, chain, foo):
        return False

    cb.register(invalid_signature)

    with pytest.raises(TypeError):
        await cb.run(bounty_guid='guid', votes=[True], valid_bloom=True, chain='home')


@pytest.mark.asyncio
async def test_on_settle_bounty_due_callback():
    cb = events.OnSettleBountyDueCallback()

    async def check_parameters(bounty_guid, chain):
        return bounty_guid == 'guid' and chain == 'home'

    cb.register(check_parameters)

    assert await cb.run(bounty_guid='guid', chain='home') == [True]
    assert await cb.run(bounty_guid='not guid', chain='home') == [False]

    async def invalid_signature(bounty_guid, chain, foo):
        return False

    cb.register(invalid_signature)

    with pytest.raises(TypeError):
        await cb.run(bounty_guid='guid', chain='home')
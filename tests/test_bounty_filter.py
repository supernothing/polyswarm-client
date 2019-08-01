from polyswarmclient.bountyfilter import BountyFilter, Filter, FilterComparison, split_filter, parse_filters


def test_pad_fills_empty_to_length():
    # arrange
    metadata = []
    # act
    padded = BountyFilter.pad_metadata(metadata, 2)
    # assert
    assert padded == [{}] * 2


# noinspection PyTypeChecker
def test_pad_fills_none_to_length():
    # arrange
    metadata = None
    # act
    padded = BountyFilter.pad_metadata(metadata, 2)
    # assert
    assert padded == [{}] * 2


def test_pad_fills_to_length():
    # arrange
    metadata = [{'mimetype': 'text/plain'}]
    # act
    padded = BountyFilter.pad_metadata(metadata, 2)
    # assert
    assert padded == [{'mimetype': 'text/plain'}, {}]


def test_pad_fills_with_none_on_invalid_metadata():
    # arrange
    metadata = [{'asdf': 'asdf'}]
    # act
    padded = BountyFilter.pad_metadata(metadata, 2)
    # assert
    assert padded == [{}] * 2


def test_no_pad_on_match_length():
    # arrange
    metadata = [{'mimetype': 'text/plain'}] * 5
    # act
    padded = BountyFilter.pad_metadata(metadata, 5)
    # assert
    assert padded == metadata


def test_no_pad_on_too_long():
    # arrange
    metadata = [{'mimetype': 'text/plain'}] * 10
    # act
    padded = BountyFilter.pad_metadata(metadata, 5)
    # assert
    assert padded == metadata


def test_not_excluded():
    # arrange
    bounty_filter = BountyFilter(None, [Filter('.mimetype', FilterComparison.EQ, 'text/plain')])
    # act
    allowed = bounty_filter.is_allowed({'mimetype': 'text/html'})
    # assert
    assert allowed


def test_excluded():
    # arrange
    bounty_filter = BountyFilter(None, [Filter('.mimetype', FilterComparison.EQ, 'text/plain')])
    # act
    allowed = bounty_filter.is_allowed({'mimetype': 'text/plain'})
    # assert
    assert not allowed


def test_any_excluded():
    # arrange
    bounty_filter = BountyFilter(None, [
        Filter('.mimetype', FilterComparison.EQ, 'text/plain'),
        Filter('.mimetype', FilterComparison.EQ, 'text/html')])
    # act
    allowed = bounty_filter.is_allowed({'mimetype': 'text/html'})
    # assert
    assert not allowed


def test_not_accepted():
    # arrange
    bounty_filter = BountyFilter([Filter('.mimetype', FilterComparison.EQ, 'text/plain')], None)
    # act
    allowed = bounty_filter.is_allowed({'mimetype': 'text/html'})
    # assert
    assert not allowed


def test__accepted():
    # arrange
    bounty_filter = BountyFilter([Filter('.mimetype', FilterComparison.EQ, 'text/plain')], None)
    # act
    allowed = bounty_filter.is_allowed({'mimetype': 'text/plain'})
    # assert
    assert allowed


def test_scans_artifact_accepted_match_only_one():
    # arrange
    bounty_filter = BountyFilter([Filter('.mimetype', FilterComparison.EQ, 'text/plain'),
                                  Filter('.mimetype', FilterComparison.EQ, 'text/html')],
                                 None)
    # act
    allowed = bounty_filter.is_allowed({'mimetype': 'text/html'})
    # assert
    assert allowed


def test_split_filter_becomes_filter():
    # arrange
    # assert
    text_filter = split_filter(None, None, ['mimetype:text/plain'])
    # act
    assert text_filter[0] == Filter('.mimetype', FilterComparison.EQ, 'text/plain')


def test_split_filter_empty_stays_empty():
    # arrange
    # assert
    text_filter = split_filter(None, None, [])
    # act
    assert not text_filter


def test_parse_filter_adds_reject_to_second_list():
    # arrange
    # assert
    accept, reject = parse_filters(None, None, [('reject', '.mimetype', 'contains', 'text')])
    # act
    assert not accept
    assert reject[0] == Filter('.mimetype', FilterComparison.CONTAINS, 'text')


def test_parse_filter_adds_accept_to_first_list():
    # arrange
    # assert
    accept, reject = parse_filters(None, None, [('accept', '.mimetype', 'contains', 'text')])
    # act
    assert accept[0] == Filter('.mimetype', FilterComparison.CONTAINS, 'text')
    assert not reject


def test_parse_filter_returns_empty_lists_on_none():
    # arrange
    # assert
    accept, reject = parse_filters(None, None, None)
    # act
    assert isinstance(accept, list) and len(accept) == 0
    assert isinstance(reject, list) and len(reject) == 0


def test_parse_filter_returns_empty_lists_on_empty_list():
    # arrange
    # assert
    accept, reject = parse_filters(None, None, [])
    # act
    assert isinstance(accept, list) and len(accept) == 0
    assert isinstance(reject, list) and len(reject) == 0


def test_filter_comparison_from_lt():
    # arrange
    # assert
    comparison = FilterComparison.from_string('<')
    # act
    assert comparison == FilterComparison.LT


def test_filter_comparison_from_lte():
    # arrange
    # assert
    comparison = FilterComparison.from_string('<=')
    # act
    assert comparison == FilterComparison.LTE


def test_filter_comparison_from_gt():
    # arrange
    # assert
    comparison = FilterComparison.from_string('>')
    # act
    assert comparison == FilterComparison.GT


def test_filter_comparison_from_gte():
    # arrange
    # assert
    comparison = FilterComparison.from_string('>=')
    # act
    assert comparison == FilterComparison.GTE


def test_filter_comparison_from_eq():
    # arrange
    # assert
    comparison = FilterComparison.from_string('==')
    # act
    assert comparison == FilterComparison.EQ


def test_filter_comparison_from_contains():
    # arrange
    # assert
    comparison = FilterComparison.from_string('contains')
    # act
    assert comparison == FilterComparison.CONTAINS


def test_filter_comparison_from_startswith():
    # arrange
    # assert
    comparison = FilterComparison.from_string('startswith')
    # act
    assert comparison == FilterComparison.STARTS_WITH


def test_filter_comparison_from_endswith():
    # arrange
    # assert
    comparison = FilterComparison.from_string('endswith')
    # act
    assert comparison == FilterComparison.ENDS_WITH


def test_filter_comparison_from_regex():
    # arrange
    # assert
    comparison = FilterComparison.from_string('regex')
    # act
    assert comparison == FilterComparison.REGEX


def test_none_does_not_match():
    # arrange
    text_filter = Filter('.mimetype', FilterComparison.EQ, 'text/plain')
    # act
    match = text_filter.filter(None)
    # assert
    assert not match


def test_gt_matches_larger():
    # arrange
    metadata = {'filesize': '20'}
    size_filter = Filter('.filesize', FilterComparison.GT, '0')
    # act
    match = size_filter.filter(metadata)
    # assert
    assert match


def test_gt_no_match_smaller_same():
    # arrange
    same = {'filesize': '30'}
    smaller = {'filesize': '0'}
    size_filter = Filter('.filesize', FilterComparison.GT, '30')
    # act
    smaller_match = size_filter.filter(smaller)
    same_match = size_filter.filter(same)
    # assert
    assert not smaller_match and not same_match


def test_gt_matches_value_int():
    # arrange
    metadata = {'filesize': 20}
    size_filter = Filter('.filesize', FilterComparison.GT, '0')
    # act
    match = size_filter.filter(metadata)
    # assert
    assert match


def test_gt_not_match_value_is_string():
    # arrange
    metadata = {'filesize': 'asdf'}
    size_filter = Filter('.filesize', FilterComparison.GT, '0')
    # act
    match = size_filter.filter(metadata)
    # assert
    assert not match


def test_gt_not_match_target_is_string():
    # arrange
    metadata = {'filesize': '0'}
    size_filter = Filter('.filesize', FilterComparison.GT, 'asdf')
    # act
    match = size_filter.filter(metadata)
    # assert
    assert not match


def test_gte_matches_larger_and_same():
    # arrange
    larger = {'filesize': '20'}
    same = {'filesize': '0'}
    size_filter = Filter('.filesize', FilterComparison.GTE, '0')
    # act
    larger_match = size_filter.filter(larger)
    same_match = size_filter.filter(same)
    # assert
    assert larger_match and same_match


def test_gte_no_match_smaller():
    # arrange
    metadata = {'filesize': '20'}
    size_filter = Filter('.filesize', FilterComparison.GTE, '30')
    # act
    match = size_filter.filter(metadata)
    # assert
    assert not match


def test_gte_not_match_value_is_string():
    # arrange
    metadata = {'filesize': 'asdf'}
    size_filter = Filter('.filesize', FilterComparison.GTE, '0')
    # act
    match = size_filter.filter(metadata)
    # assert
    assert not match


def test_gte_not_match_target_is_string():
    # arrange
    metadata = {'filesize': '0'}
    size_filter = Filter('.filesize', FilterComparison.GTE, 'asdf')
    # act
    match = size_filter.filter(metadata)
    # assert
    assert not match


def test_lt_matches_smaller():
    # arrange
    metadata = {'filesize': '20'}
    size_filter = Filter('.filesize', FilterComparison.LT, '30')
    # act
    match = size_filter.filter(metadata)
    # assert
    assert match


def test_lt_no_match_larger_same():
    # arrange
    larger = {'filesize': '20'}
    same = {'filesize': '0'}
    size_filter = Filter('.filesize', FilterComparison.LT, '0')
    # act
    larger_match = size_filter.filter(larger)
    same_match = size_filter.filter(same)
    # assert
    assert not larger_match and not same_match


def test_lt_not_match_value_is_string():
    # arrange
    metadata = {'filesize': 'asdf'}
    size_filter = Filter('.filesize', FilterComparison.LT, '0')
    # act
    match = size_filter.filter(metadata)
    # assert
    assert not match


def test_lt_not_match_target_is_string():
    # arrange
    metadata = {'filesize': '0'}
    size_filter = Filter('.filesize', FilterComparison.LT, 'asdf')
    # act
    match = size_filter.filter(metadata)
    # assert
    assert not match


def test_lte_matches_smaller_and_same():
    # arrange
    same = {'filesize': '30'}
    smaller = {'filesize': '0'}
    size_filter = Filter('.filesize', FilterComparison.LTE, '30')
    # act
    smaller_match = size_filter.filter(smaller)
    same_match = size_filter.filter(same)
    # assert
    assert smaller_match and same_match


def test_lte_no_match_larger():
    # arrange
    metadata = {'filesize': '20'}
    size_filter = Filter('.filesize', FilterComparison.LTE, '0')
    # act
    match = size_filter.filter(metadata)
    # assert
    assert not match


def test_lte_not_match_value_is_string():
    # arrange
    metadata = {'filesize': 'asdf'}
    size_filter = Filter('.filesize', FilterComparison.LTE, '0')
    # act
    match = size_filter.filter(metadata)
    # assert
    assert not match


def test_lte_not_match_target_is_string():
    # arrange
    metadata = {'filesize': '0'}
    size_filter = Filter('.filesize', FilterComparison.LTE, 'asdf')
    # act
    match = size_filter.filter(metadata)
    # assert
    assert not match


def test_eq_matches_same_int_strings():
    # arrange
    metadata = {'filesize': '2320'}
    size_filter = Filter('.filesize', FilterComparison.EQ, '2320')
    # act
    match = size_filter.filter(metadata)
    # assert
    assert match


def test_eq_matches_same_int():
    # arrange
    metadata = {'filesize': 2320}
    size_filter = Filter('.filesize', FilterComparison.EQ, '2320')
    # act
    match = size_filter.filter(metadata)
    # assert
    assert match


def test_eq_matches_same_string():
    # arrange
    metadata = {'filesize': 'asdf'}
    size_filter = Filter('.filesize', FilterComparison.EQ, 'asdf')
    # act
    match = size_filter.filter(metadata)
    # assert
    assert match


def test_eq_no_match_different():
    # arrange
    metadata = {'filesize': '2320'}
    size_filter = Filter('.filesize', FilterComparison.EQ, 'asdf')
    # act
    match = size_filter.filter(metadata)
    # assert
    assert not match


def test_contains_matches_if_contained():
    # arrange
    metadata = {'field': 'asdfg'}
    contains_filter = Filter('.field', FilterComparison.CONTAINS, 'sdf')
    # act
    match = contains_filter.filter(metadata)
    # assert
    assert match


def test_contains_no_match_if_not_contained():
    # arrange
    metadata = {'field': 'asd'}
    contains_filter = Filter('.field', FilterComparison.CONTAINS, 'asdf')
    # act
    match = contains_filter.filter(metadata)
    # assert
    assert not match


def test_contains_ints_match():
    # arrange
    metadata = {'field': '123'}
    contains_filter = Filter('.field', FilterComparison.CONTAINS, '2')
    # act
    match = contains_filter.filter(metadata)
    # assert
    assert match


def test_startswith_matches_start():
    # arrange
    metadata = {'field': 'asdfg'}
    starts_filter = Filter('.field', FilterComparison.STARTS_WITH, 'asdf')
    # act
    match = starts_filter.filter(metadata)
    # assert
    assert match


def test_startswith_no_match():
    # arrange
    metadata = {'field': 'asdfg'}
    starts_filter = Filter('.field', FilterComparison.STARTS_WITH, 'sdf')
    # act
    match = starts_filter.filter(metadata)
    # assert
    assert not match


def test_startswith_ints_match():
    # arrange
    metadata = {'field': 123}
    starts_filter = Filter('.field', FilterComparison.STARTS_WITH, '1')
    # act
    match = starts_filter.filter(metadata)
    # assert
    assert match


def test_endswith_matches_end():
    # arrange
    metadata = {'field': 'asdfg'}
    ends_filter = Filter('.field', FilterComparison.ENDS_WITH, 'sdfg')
    # act
    match = ends_filter.filter(metadata)
    # assert
    assert match


def test_endswith_no_match():
    # arrange
    metadata = {'field': 'asdfg'}
    ends_filter = Filter('.field', FilterComparison.ENDS_WITH, 'asdf')
    # act
    match = ends_filter.filter(metadata)
    # assert
    assert not match


def test_endswith_ints_match():
    # arrange
    metadata = {'field': 123}
    ends_filter = Filter('.field', FilterComparison.ENDS_WITH, '23')
    # act
    match = ends_filter.filter(metadata)
    # assert
    assert match


def test_regex_matches():
    # arrange
    metadata = {'field': 'asdf'}
    regex_filter = Filter('.field', FilterComparison.REGEX, '^a.*f$')
    # act
    match = regex_filter.filter(metadata)
    # assert
    assert match


def test_regex_no_match():
    # arrange
    metadata = {'field': 'sdf'}
    regex_filter = Filter('.field', FilterComparison.REGEX, 'a.*f')
    # act
    match = regex_filter.filter(metadata)
    # assert
    assert not match


def test_regex_ints_match():
    # arrange
    metadata = {'field': 123}
    regex_filter = Filter('.field', FilterComparison.REGEX, '.*2.*')
    # act
    match = regex_filter.filter(metadata)
    # assert
    assert match


def test_empty_dict_no_match():
    # arrange
    metadata = {}
    regex_filter = Filter('.field', FilterComparison.REGEX, '.*2.*')
    # act
    match = regex_filter.filter(metadata)
    # assert
    assert not match


def test_array_bad_query():
    # arrange
    metadata = []
    regex_filter = Filter('.field', FilterComparison.REGEX, '.*2.*')
    # act
    match = regex_filter.filter(metadata)
    # assert
    assert not match


def test_jq_syntax_inside_array():
    # arrange
    metadata = ['020']
    regex_filter = Filter('.[]+1', FilterComparison.REGEX, '.*2.*')
    # act
    match = regex_filter.filter(metadata)
    # assert
    assert not match


def test_jq_syntax_inside_dict():
    # arrange
    metadata = {'field': {'k': 'v'}}
    object_filter = Filter('.field.k', FilterComparison.EQ, 'v')
    # act
    match = object_filter.filter(metadata)
    # assert
    assert match


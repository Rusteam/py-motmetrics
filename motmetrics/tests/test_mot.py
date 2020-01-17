from pytest import approx
import numpy as np
import pandas as pd
import motmetrics as mm
import os
import pytest


def test_events():
    acc = mm.MOTAccumulator()

    # All FP
    acc.update([], [1, 2], [], frameid=0)
    # All miss
    acc.update([1, 2], [], [], frameid=1)
    # Match
    acc.update([1, 2], [1, 2], [[1, 0.5], [0.3, 1]], frameid=2)
    # Switch
    acc.update([1, 2], [1, 2], [[0.2, np.nan], [np.nan, 0.1]], frameid=3)
    # Match. Better new match is available but should prefer history
    acc.update([1, 2], [1, 2], [[5, 1], [1, 5]], frameid=4)
    # No data
    acc.update([], [], [], frameid=5)

    expect = mm.MOTAccumulator.new_event_dataframe()
    expect.loc[(0, 0), :] = ['RAW', np.nan, 1, np.nan]
    expect.loc[(0, 1), :] = ['RAW', np.nan, 2, np.nan]
    expect.loc[(0, 2), :] = ['FP', np.nan, 1, np.nan]
    expect.loc[(0, 3), :] = ['FP', np.nan, 2, np.nan]

    expect.loc[(1, 0), :] = ['RAW', 1, np.nan, np.nan]
    expect.loc[(1, 1), :] = ['RAW', 2, np.nan, np.nan]
    expect.loc[(1, 2), :] = ['MISS', 1, np.nan, np.nan]
    expect.loc[(1, 3), :] = ['MISS', 2, np.nan, np.nan]

    expect.loc[(2, 0), :] = ['RAW', 1, 1, 1.0]
    expect.loc[(2, 1), :] = ['RAW', 1, 2, 0.5]
    expect.loc[(2, 2), :] = ['RAW', 2, 1, 0.3]
    expect.loc[(2, 3), :] = ['RAW', 2, 2, 1.0]
    expect.loc[(2, 4), :] = ['MATCH', 1, 2, 0.5]
    expect.loc[(2, 5), :] = ['MATCH', 2, 1, 0.3]

    expect.loc[(3, 0), :] = ['RAW', 1, 1, 0.2]
    expect.loc[(3, 1), :] = ['RAW', 2, 2, 0.1]
    expect.loc[(3, 2), :] = ['TRANSFER', 1, 1, 0.2]
    expect.loc[(3, 3), :] = ['SWITCH', 1, 1, 0.2]
    expect.loc[(3, 4), :] = ['TRANSFER', 2, 2, 0.1]
    expect.loc[(3, 5), :] = ['SWITCH', 2, 2, 0.1]

    expect.loc[(4, 0), :] = ['RAW', 1, 1, 5.]
    expect.loc[(4, 1), :] = ['RAW', 1, 2, 1.]
    expect.loc[(4, 2), :] = ['RAW', 2, 1, 1.]
    expect.loc[(4, 3), :] = ['RAW', 2, 2, 5.]
    expect.loc[(4, 4), :] = ['MATCH', 1, 1, 5.]
    expect.loc[(4, 5), :] = ['MATCH', 2, 2, 5.]
    # frame 5 generates no events

    from pandas.util.testing import assert_frame_equal
    assert_frame_equal(acc.events, expect)


def test_max_switch_time():
    acc = mm.MOTAccumulator(max_switch_time=1)
    acc.update([1, 2], [1, 2], [[1, 0.5], [0.3, 1]], frameid=1)  # 1->a, 2->b
    frameid = acc.update([1, 2], [1, 2], [[0.5, np.nan], [np.nan, 0.5]], frameid=2)  # 1->b, 2->a

    df = acc.events.loc[frameid]
    assert ((df.Type == 'SWITCH') | (df.Type == 'RAW') | (df.Type == 'TRANSFER')).all()

    acc = mm.MOTAccumulator(max_switch_time=1)
    acc.update([1, 2], [1, 2], [[1, 0.5], [0.3, 1]], frameid=1)  # 1->a, 2->b
    frameid = acc.update([1, 2], [1, 2], [[0.5, np.nan], [np.nan, 0.5]], frameid=5)  # Later frame 1->b, 2->a

    df = acc.events.loc[frameid]
    assert ((df.Type == 'MATCH') | (df.Type == 'RAW') | (df.Type == 'TRANSFER')).all()


def test_auto_id():
    acc = mm.MOTAccumulator(auto_id=True)
    acc.update([1, 2, 3, 4], [], [])
    acc.update([1, 2, 3, 4], [], [])
    assert acc.events.index.levels[0][-1] == 1
    acc.update([1, 2, 3, 4], [], [])
    assert acc.events.index.levels[0][-1] == 2

    with pytest.raises(AssertionError):
        acc.update([1, 2, 3, 4], [], [], frameid=5)

    acc = mm.MOTAccumulator(auto_id=False)
    with pytest.raises(AssertionError):
        acc.update([1, 2, 3, 4], [], [])


def test_merge_dataframes():
    acc = mm.MOTAccumulator()

    acc.update([], [1, 2], [], frameid=0)
    acc.update([1, 2], [], [], frameid=1)
    acc.update([1, 2], [1, 2], [[1, 0.5], [0.3, 1]], frameid=2)
    acc.update([1, 2], [1, 2], [[0.2, np.nan], [np.nan, 0.1]], frameid=3)

    r, mappings = mm.MOTAccumulator.merge_event_dataframes([acc.events, acc.events], return_mappings=True)

    expect = mm.MOTAccumulator.new_event_dataframe()

    expect.loc[(0, 0), :] = ['RAW', np.nan, mappings[0]['hid_map'][1], np.nan]
    expect.loc[(0, 1), :] = ['RAW', np.nan, mappings[0]['hid_map'][2], np.nan]
    expect.loc[(0, 2), :] = ['FP', np.nan, mappings[0]['hid_map'][1], np.nan]
    expect.loc[(0, 3), :] = ['FP', np.nan, mappings[0]['hid_map'][2], np.nan]

    expect.loc[(1, 0), :] = ['RAW', mappings[0]['oid_map'][1], np.nan, np.nan]
    expect.loc[(1, 1), :] = ['RAW', mappings[0]['oid_map'][2], np.nan, np.nan]
    expect.loc[(1, 2), :] = ['MISS', mappings[0]['oid_map'][1], np.nan, np.nan]
    expect.loc[(1, 3), :] = ['MISS', mappings[0]['oid_map'][2], np.nan, np.nan]

    expect.loc[(2, 0), :] = ['RAW', mappings[0]['oid_map'][1], mappings[0]['hid_map'][1], 1]
    expect.loc[(2, 1), :] = ['RAW', mappings[0]['oid_map'][1], mappings[0]['hid_map'][2], 0.5]
    expect.loc[(2, 2), :] = ['RAW', mappings[0]['oid_map'][2], mappings[0]['hid_map'][1], 0.3]
    expect.loc[(2, 3), :] = ['RAW', mappings[0]['oid_map'][2], mappings[0]['hid_map'][2], 1.0]
    expect.loc[(2, 4), :] = ['MATCH', mappings[0]['oid_map'][1], mappings[0]['hid_map'][2], 0.5]
    expect.loc[(2, 5), :] = ['MATCH', mappings[0]['oid_map'][2], mappings[0]['hid_map'][1], 0.3]

    expect.loc[(3, 0), :] = ['RAW', mappings[0]['oid_map'][1], mappings[0]['hid_map'][1], 0.2]
    expect.loc[(3, 1), :] = ['RAW', mappings[0]['oid_map'][2], mappings[0]['hid_map'][2], 0.1]
    expect.loc[(3, 2), :] = ['TRANSFER', mappings[0]['oid_map'][1], mappings[0]['hid_map'][1], 0.2]
    expect.loc[(3, 3), :] = ['SWITCH', mappings[0]['oid_map'][1], mappings[0]['hid_map'][1], 0.2]
    expect.loc[(3, 4), :] = ['TRANSFER', mappings[0]['oid_map'][2], mappings[0]['hid_map'][2], 0.1]
    expect.loc[(3, 5), :] = ['SWITCH', mappings[0]['oid_map'][2], mappings[0]['hid_map'][2], 0.1]

    # Merge duplication
    expect.loc[(4, 0), :] = ['RAW', np.nan, mappings[1]['hid_map'][1], np.nan]
    expect.loc[(4, 1), :] = ['RAW', np.nan, mappings[1]['hid_map'][2], np.nan]
    expect.loc[(4, 2), :] = ['FP', np.nan, mappings[1]['hid_map'][1], np.nan]
    expect.loc[(4, 3), :] = ['FP', np.nan, mappings[1]['hid_map'][2], np.nan]

    expect.loc[(5, 0), :] = ['RAW', mappings[1]['oid_map'][1], np.nan, np.nan]
    expect.loc[(5, 1), :] = ['RAW', mappings[1]['oid_map'][2], np.nan, np.nan]
    expect.loc[(5, 2), :] = ['MISS', mappings[1]['oid_map'][1], np.nan, np.nan]
    expect.loc[(5, 3), :] = ['MISS', mappings[1]['oid_map'][2], np.nan, np.nan]

    expect.loc[(6, 0), :] = ['RAW', mappings[1]['oid_map'][1], mappings[1]['hid_map'][1], 1]
    expect.loc[(6, 1), :] = ['RAW', mappings[1]['oid_map'][1], mappings[1]['hid_map'][2], 0.5]
    expect.loc[(6, 2), :] = ['RAW', mappings[1]['oid_map'][2], mappings[1]['hid_map'][1], 0.3]
    expect.loc[(6, 3), :] = ['RAW', mappings[1]['oid_map'][2], mappings[1]['hid_map'][2], 1.0]
    expect.loc[(6, 4), :] = ['MATCH', mappings[1]['oid_map'][1], mappings[1]['hid_map'][2], 0.5]
    expect.loc[(6, 5), :] = ['MATCH', mappings[1]['oid_map'][2], mappings[1]['hid_map'][1], 0.3]

    expect.loc[(7, 0), :] = ['RAW', mappings[1]['oid_map'][1], mappings[1]['hid_map'][1], 0.2]
    expect.loc[(7, 1), :] = ['RAW', mappings[1]['oid_map'][2], mappings[1]['hid_map'][2], 0.1]
    expect.loc[(7, 2), :] = ['TRANSFER', mappings[1]['oid_map'][1], mappings[1]['hid_map'][1], 0.2]
    expect.loc[(7, 3), :] = ['SWITCH', mappings[1]['oid_map'][1], mappings[1]['hid_map'][1], 0.2]
    expect.loc[(7, 4), :] = ['TRANSFER', mappings[1]['oid_map'][2], mappings[1]['hid_map'][2], 0.1]
    expect.loc[(7, 5), :] = ['SWITCH', mappings[1]['oid_map'][2], mappings[1]['hid_map'][2], 0.1]

    from pandas.util.testing import assert_frame_equal
    assert_frame_equal(r, expect)

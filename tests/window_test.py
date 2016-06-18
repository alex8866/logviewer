import unittest
from unittest.mock import Mock, MagicMock, PropertyMock

import curses
import datetime

from screen_buffer import ScreenBuffer
from window import *

class WindowTest(unittest.TestCase):
    def setUp(self):
        self._curses = MagicMock()
        type(self._curses).A_REVERSE = PropertyMock(return_value=0x100)
        type(self._curses).A_BOLD = PropertyMock(return_value=0x200)
        self._curses.color_pair.side_effect = self._color_pair

        self._child_window = MagicMock()

        self._parent_window = MagicMock()
        self._parent_window.subwin.return_value = self._child_window

        self._manager = MagicMock()
        type(self._manager).curses_window = PropertyMock(return_value=self._parent_window)
        type(self._manager).curses = PropertyMock(return_value=self._curses)

    def _color_pair(self, arg):
        return arg

class LogWindowTest(WindowTest):
    class FakeBuffer(object):
        def __init__(self, lines):
            self._lines = []
            dt = datetime.datetime(2016, 6, 4)
            for i, (line, is_continuation) in enumerate(lines):
                data = { 'id': i + 1, 'datetime': dt, 'host': 'test',
                    'program': 'example', 'facility_num': 0, 'level_num': 7,
                    'message': 'test message' }
                data.update(line)
                self._lines.append(ScreenBuffer.Line(data, is_continuation))

        def get_current_lines(self):
            return self._lines

    def setUp(self):
        WindowTest.setUp(self)

        self._pad = MagicMock()
        self._curses.newpad.return_value = self._pad

    def test_should_create_window(self):
        self._parent_window.getmaxyx.return_value = (10, 30)
        win = LogWindow(self._manager, None, 200)

        self._curses.newpad.assert_called_with(9, 201)

    def test_should_resize_window(self):
        self._parent_window.getmaxyx.return_value = (10, 30)
        win = LogWindow(self._manager, None, 200)

        win.resize(20, 40)
        self._pad.resize.assert_called_once_with(19, 201)

    def test_should_scroll_right(self):
        self._parent_window.getmaxyx.return_value = (10, 30)
        win = LogWindow(self._manager, None, 36)

        self.assertEqual(0, win._pad_x)
        win.scroll_right()
        self.assertEqual(4, win._pad_x)
        win.scroll_right()
        self.assertEqual(6, win._pad_x)

    def test_should_scroll_left(self):
        self._parent_window.getmaxyx.return_value = (10, 30)
        win = LogWindow(self._manager, None, 36)

        win.scroll_right()
        win.scroll_right()
        win.scroll_left()
        self.assertEqual(2, win._pad_x)
        win.scroll_left()
        self.assertEqual(0, win._pad_x)

    def test_should_update_pad_offset_after_resize(self):
        self._parent_window.getmaxyx.return_value = (10, 30)
        win = LogWindow(self._manager, None, 36)

        win.scroll_right()
        win.scroll_right()

        win.resize(10, 32)
        self.assertEqual(4, win._pad_x)

    def test_should_draw_simple_debug_line(self):
        buf = LogWindowTest.FakeBuffer([({}, False)])

        self._parent_window.getmaxyx.return_value = (10, 30)
        win = LogWindow(self._manager, buf, 100)

        win.refresh()
        self._pad.clear.assert_called_once_with()
        self._pad.noutrefresh.assert_called_once_with(0, 0, 0, 0, 8, 29)

        self.assertEqual([
            ((0, 0, '06-04 00:00:00', 14, 0),),
            ((0, 15, 'test', 8, 0),),
            ((0, 24, 'example', 16, 0),),
            ((0, 41, 'KERN', 4, 0),),
            ((0, 46, 'DEBUG', 3, 0x206),),
            ((0, 50, 'test message', 50, 0),)], self._pad.addnstr.call_args_list)

    def test_should_draw_status_bar(self):
        self._parent_window.getmaxyx.return_value = (10, 30)
        win = LogWindow(self._manager, LogWindowTest.FakeBuffer([]), 100)

        win.refresh()
        self._parent_window.addnstr.assert_called_once_with(9, 0,
            ' [l]evel: debug  [f]acility: ALL  [p]rogram: *  [h]ost: *', 29)
        self._parent_window.chgat.assert_called_once_with(9, 0, 30, 0x300)
        self._parent_window.noutrefresh.assert_called_once_with()

    def test_should_draw_continuation_line(self):
        buf = LogWindowTest.FakeBuffer([({}, False), ({}, True)])

        self._parent_window.getmaxyx.return_value = (10, 30)
        win = LogWindow(self._manager, buf, 100)

        win.refresh()
        self.assertEqual([
            ((0, 0, '06-04 00:00:00', 14, 0),),
            ((0, 15, 'test', 8, 0),),
            ((0, 24, 'example', 16, 0),),
            ((0, 41, 'KERN', 4, 0),),
            ((0, 46, 'DEBUG', 3, 0x206),),
            ((0, 50, 'test message', 50, 0),),
            ((1, 50, 'test message', 50, 0),)], self._pad.addnstr.call_args_list)

    def test_should_draw_continuation_line_at_first_row(self):
        buf = LogWindowTest.FakeBuffer([({}, True)])

        self._parent_window.getmaxyx.return_value = (10, 30)
        win = LogWindow(self._manager, buf, 100)

        win.refresh()
        self.assertEqual([
            ((0, 0, '06-04 00:00:00', 14, 0),),
            ((0, 15, 'test', 8, 0),),
            ((0, 24, 'example', 16, 0),),
            ((0, 41, 'KERN', 4, 0),),
            ((0, 46, 'DEBUG', 3, 0x206),),
            ((0, 50, 'test message', 50, 0),)], self._pad.addnstr.call_args_list)

    def test_should_draw_line_on_scrolled_window(self):
        buf = LogWindowTest.FakeBuffer([({}, True)])

        self._parent_window.getmaxyx.return_value = (10, 30)
        win = LogWindow(self._manager, buf, 100)

        win.scroll_right()
        win.refresh()
        self._pad.noutrefresh.assert_called_once_with(0, 4, 0, 0, 8, 29)

    def test_should_draw_alert_line(self):
        buf = LogWindowTest.FakeBuffer([({ 'level_num': 1 }, True)])

        self._parent_window.getmaxyx.return_value = (10, 30)
        win = LogWindow(self._manager, buf, 100)

        win.refresh()
        self.assertEqual(((0, 46, 'ALERT', 3, 0x101),),
            self._pad.addnstr.call_args_list[4])

class CenteredWindowTest(WindowTest):
    def test_should_create_window(self):
        self._parent_window.getmaxyx.return_value = (9, 30)
        win = CenteredWindow(self._manager, 'Test', 3, 16, 1, 6)

        self._parent_window.subwin.assert_called_with(7, 20, 1, 5)
        self._child_window.bkgd.assert_called_with(256)

    def test_should_squeeze_into_small_window(self):
        self._parent_window.getmaxyx.return_value = (5, 30)
        win = CenteredWindow(self._manager, 'Test', 3, 16, 1, 6)

        self._parent_window.subwin.assert_called_with(5, 20, 0, 5)

    def test_should_create_window_not_perfectly_centerable(self):
        self._parent_window.getmaxyx.return_value = (8, 29)
        win = CenteredWindow(self._manager, 'Test', 3, 16, 1, 6)

        self._parent_window.subwin.assert_called_with(7, 20, 0, 4)

    def test_should_not_create_too_small_window(self):
        self._parent_window.getmaxyx.return_value = (4, 30)
        win = CenteredWindow(self._manager, 'Test', 3, 16, 1, 6)

        self.assertEqual(0, self._parent_window.subwin.call_count)

    def test_should_refresh_window(self):
        self._parent_window.getmaxyx.return_value = (9, 30)
        win = CenteredWindow(self._manager, 'Test', 3, 16, 1, 6)

        win.refresh()
        self._child_window.clear.assert_called_with()
        self._child_window.border.assert_called_with()
        self._child_window.addstr.assert_called_with(0, 7, '|Test|')
        self._child_window.noutrefresh.assert_called_with()

    def test_should_not_refresh_invisible_window(self):
        self._parent_window.getmaxyx.return_value = (4, 30)
        win = CenteredWindow(self._manager, 'Test', 3, 16, 1, 6)

        win.refresh()
        self._child_window.clear.assert_not_called()

class SelectWindowTest(WindowTest):
    def setUp(self):
        WindowTest.setUp(self)

        self._pad = MagicMock()
        self._curses.newpad.return_value = self._pad

    def test_should_create_window(self):
        self._parent_window.getmaxyx.return_value = (9, 30)
        win = SelectWindow(self._manager, 'Letter', ['a', 'b', 'c'])

        self._curses.newpad.assert_called_with(3, 16)
        self._parent_window.subwin.assert_called_with(7, 20, 1, 5)
        self._child_window.bkgd.assert_called_with(256)
        self._pad.bkgd.assert_called_with(256)

    def test_should_not_create_empty_window(self):
        self.assertRaises(ValueError, SelectWindow, self._manager, 'x', [])

    def test_should_refresh_window(self):
        self._parent_window.getmaxyx.return_value = (9, 30)
        win = SelectWindow(self._manager, 'Letter', ['a', 'b', 'c'])

        win.refresh()
        self._child_window.clear.assert_called_with()
        self._child_window.border.assert_called_with()
        self._child_window.addstr.assert_called_with(0, 6, '|Letter|')
        self._child_window.noutrefresh.assert_called_with()
        self.assertEqual([((0, 0, '▶a', 20),), ((1, 0, ' b', 20),),
            ((2, 0, ' c', 20),)], self._pad.addnstr.call_args_list)
        self._pad.noutrefresh.assert_called_with(0, 0, 3, 7, 5, 22)

    def test_should_change_position(self):
        self._parent_window.getmaxyx.return_value = (9, 30)
        win = SelectWindow(self._manager, 'Letter', ['a', 'b', 'c'])

        win.position = 2
        win.refresh()
        self.assertEqual([((0, 0, ' a', 20),), ((1, 0, ' b', 20),),
            ((2, 0, '▶c', 20),)], self._pad.addnstr.call_args_list)

    def test_should_not_set_invalid_position(self):
        self._parent_window.getmaxyx.return_value = (9, 30)
        win = SelectWindow(self._manager, 'Letter', ['a', 'b', 'c'])

        self.assertRaises(IndexError, setattr, win, 'position', -1)
        self.assertRaises(IndexError, setattr, win, 'position', 3)

    def test_should_move_pad_down_if_position_would_be_off_of_screen(self):
        self._parent_window.getmaxyx.return_value = (6, 30)
        win = SelectWindow(self._manager, 'Letter', ['a', 'b', 'c', 'd'])

        win.position = 2
        win.refresh()
        self._pad.noutrefresh.assert_called_with(1, 0, 2, 7, 3, 22)

    def test_should_handle_key_down(self):
        self._parent_window.getmaxyx.return_value = (9, 30)
        win = SelectWindow(self._manager, 'Letter', ['a', 'b', 'c'])

        win.handle_key(curses.KEY_DOWN)
        self.assertEqual(1, win.position)

    def test_should_handle_key_down_at_end_of_screen(self):
        self._parent_window.getmaxyx.return_value = (9, 30)
        win = SelectWindow(self._manager, 'Letter', ['a', 'b', 'c'])

        win.handle_key(curses.KEY_DOWN)
        win.handle_key(curses.KEY_DOWN)
        win.handle_key(curses.KEY_DOWN)
        self.assertEqual(2, win.position)

    def test_should_handle_key_up(self):
        self._parent_window.getmaxyx.return_value = (9, 30)
        win = SelectWindow(self._manager, 'Letter', ['a', 'b', 'c'])

        win.handle_key(curses.KEY_DOWN)
        win.handle_key(curses.KEY_UP)
        self.assertEqual(0, win.position)

    def test_should_handle_carriage_return(self):
        self._parent_window.getmaxyx.return_value = (9, 30)
        win = SelectWindow(self._manager, 'Letter', ['a', 'b', 'c'])

        win.handle_key(10)
        self.assertTrue(win.closed)
        self.assertTrue(win.result)

    def test_should_handle_escape(self):
        self._parent_window.getmaxyx.return_value = (9, 30)
        win = SelectWindow(self._manager, 'Letter', ['a', 'b', 'c'])

        win.handle_key(27)
        self.assertTrue(win.closed)
        self.assertFalse(win.result)

class TextWindowTest(WindowTest):
    def test_should_create_window(self):
        self._parent_window.getmaxyx.return_value = (9, 30)
        win = TextWindow(self._manager, 'Test', 19)

        self._parent_window.subwin.assert_called_with(5, 24, 2, 3)
        self._child_window.bkgd.assert_called_with(256)

    def test_should_start_and_stop_cursor(self):
        self._parent_window.getmaxyx.return_value = (9, 30)
        win = TextWindow(self._manager, 'Test', 19)

        win.start()
        win.finish()

        self.assertEqual([((1,),), ((0,),)],
            self._curses.curs_set.call_args_list)

    def test_should_refresh_empty_window(self):
        self._parent_window.getmaxyx.return_value = (9, 30)
        win = TextWindow(self._manager, 'Test', 19)

        win.refresh()

        self.assertEqual([((0, 9, '|Test|'),), ((2, 2, ''),)],
            self._child_window.addstr.call_args_list)
        self.assertEqual([((2, 2),), ((2, 2),)],
            self._child_window.move.call_args_list)
        self.assertEqual([((2, 2, 20, 0),)],
            self._child_window.chgat.call_args_list)

    def test_should_refresh_window_with_text(self):
        self._parent_window.getmaxyx.return_value = (9, 30)
        win = TextWindow(self._manager, 'Test', 19)

        win.text = 'test text'
        win.refresh()

        self.assertEqual([((0, 9, '|Test|'),), ((2, 2, 'test text'),)],
            self._child_window.addstr.call_args_list)
        self.assertEqual([((2, 2),), ((2, 11),)],
            self._child_window.move.call_args_list)

    def test_should_refresh_narrow_text_window(self):
        self._parent_window.getmaxyx.return_value = (9, 20)
        win = TextWindow(self._manager, 'Test', 19)

        win.text = 'a longer test text'
        win.refresh()

        self.assertEqual([((0, 7, '|Test|'),), ((2, 2, 'onger test text'),)],
            self._child_window.addstr.call_args_list)

    def test_should_handle_key_after_text_change(self):
        self._parent_window.getmaxyx.return_value = (9, 30)
        win = TextWindow(self._manager, 'Test', 19)

        win.text = 'test text'
        win.handle_key(ord('x'))
        self.assertEqual('test textx', win.text)

class FilterTest(unittest.TestCase):
    def test_should_create_filter_state(self):
        filter = FilterState()
        self.assertEqual(7, filter.level)
        self.assertIsNone(filter.facility)
        self.assertIsNone(filter.host)
        self.assertIsNone(filter.program)

    def test_should_set_facility(self):
        filter = FilterState()
        filter.facility = 10
        self.assertEqual(10, filter.facility)

    def test_should_set_host(self):
        filter = FilterState()
        filter.host = 'example'
        self.assertEqual('example', filter.host)

    def test_should_clear_host(self):
        filter = FilterState()
        filter.host = ''
        self.assertIsNone(filter.host)

    def test_should_set_level(self):
        filter = FilterState()
        filter.level = 4
        self.assertEqual(4, filter.level)

    def test_should_clear_level(self):
        filter = FilterState()
        filter.level = 4
        filter.level = None
        self.assertEqual(7, filter.level)

    def test_should_set_program(self):
        filter = FilterState()
        filter.program = 'su'
        self.assertEqual('su', filter.program)

    def test_should_clear_program(self):
        filter = FilterState()
        filter.program = ''
        self.assertIsNone(filter.program)

    def test_should_get_empty_filter_summary(self):
        filter = FilterState()
        self.assertEqual((('[l]evel', 'debug'), ('[f]acility', 'ALL'),
            ('[p]rogram', '*'), ('[h]ost', '*')), filter.get_summary())

    def test_should_get_non_empty_filter_summary(self):
        filter = FilterState()
        filter.level = 6
        filter.facility = 0
        filter.host = 'example'
        filter.program = 'test'
        self.assertEqual((('[l]evel', 'info'), ('[f]acility', 'kern'),
            ('[p]rogram', 'test'), ('[h]ost', 'example')), filter.get_summary())
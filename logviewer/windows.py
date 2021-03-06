import curses
import datetime

from .screen_buffer import ScreenBuffer
from .screen_cursor import ScreenCursor
from .text_input import TextInput
from .utf8_parser import UTF8Parser
from . import window_states

class Base(object):
    def __init__(self, window_manager):
        self._window_manager = window_manager
        self._result = None
        self._closed = False

    @property
    def closed(self):
        return self._closed

    @property
    def result(self):
        return self._result

    @property
    def window_manager(self):
        return self._window_manager

    def show(self):
        self._window_manager.stack.append(self)
        self.start()
        try:
            while not self._closed:
                self._window_manager.loop()
            return self._result
        finally:
            self.finish()
            self._window_manager.stack.pop()

    def close(self, result):
        self._result = result
        self._closed = True

    def start(self):
        pass

    def finish(self):
        pass

    def handle_key(self, k):
        raise RuntimeError('Not implemented')

    def refresh(self):
        raise RuntimeError('Not implemented')

    def resize(self, height, width):
        raise RuntimeError('Not implemented')

class Log(Base):
    STEP = 4
    WIDTHS = [14, 8, 16, 4, 3]

    def __init__(self, window_manager, buffer, max_width):
        Base.__init__(self, window_manager)

        self._buf = buffer

        self._curses = window_manager.curses
        self._curses_window = window_manager.curses_window
        h, w = self._curses_window.getmaxyx()

        self._max_width = max_width
        # pad should be one character wider than the maximum text width so we
        # can write a character at the last column of the last line without
        # raising a curses error
        self._pad_width = max_width + 1
        self._pad = self._curses.newpad(h - 1, self._pad_width)
        self._pad_x = 0
        self._pad_x_max = self._max_width - w

        self._filter_state = window_states.Filter()

        self._level_attrs = {
            'emerg':   self._curses.color_pair(1) | self._curses.A_REVERSE,
            'alert':   self._curses.color_pair(1) | self._curses.A_REVERSE,
            'crit':    self._curses.color_pair(1) | self._curses.A_BOLD,
            'err':     self._curses.color_pair(2) | self._curses.A_BOLD,
            'warning': self._curses.color_pair(3) | self._curses.A_BOLD,
            'notice':  self._curses.color_pair(4) | self._curses.A_BOLD,
            'info':    self._curses.color_pair(5) | self._curses.A_BOLD,
            'debug':   self._curses.color_pair(6) | self._curses.A_BOLD }

    @property
    def filter_state(self):
        return self._filter_state

    def _pos(self, i):
        return sum(Log.WIDTHS[:i]) + i

    def _width(self, i):
        if i >= len(Log.WIDTHS):
            return self._max_width - sum(Log.WIDTHS) - len(Log.WIDTHS)
        return Log.WIDTHS[i]

    def _update_line(self, y, p, val, attr=0):
        self._pad.addnstr(y, self._pos(p), val, self._width(p), attr)

    def _get_filter_state_desc(self):
        return ' ' + '  '.join('{}: {}'.format(a, b) for (a, b) in \
            self._filter_state.get_summary()) + '  ' + 'Go to [d]ate'

    def refresh(self):
        self._pad.erase()

        for i, line in enumerate(self._buf.get_current_lines()):
            if not line.is_continuation or i == 0:
                dt_str = datetime.datetime.strftime(line.datetime, '%m-%d %H:%M:%S')
                self._update_line(i, 0, dt_str)
                self._update_line(i, 1, line.host)
                self._update_line(i, 2, line.program)
                self._update_line(i, 3, line.facility.upper())
                self._update_line(i, 4, line.level.upper(),
                    self._level_attrs.get(line.level, 0))
            self._update_line(i, 5, line.message)

        y, x = self._curses_window.getmaxyx()

        self._curses_window.addnstr(y - 1, 0, self._get_filter_state_desc(), x - 1)
        self._curses_window.chgat(y - 1, 0, x, self._curses.A_BOLD | self._curses.A_REVERSE)
        self._curses_window.noutrefresh()
        self._pad.noutrefresh(0, self._pad_x, 0, 0, y - 2, x - 1)

    def resize(self, h, w):
        self._pad.resize(h - 1, self._pad_width)
        self._pad_x_max = max(0, self._max_width - w)
        self._pad_x = min(self._pad_x, self._pad_x_max)

    def scroll_left(self):
        self._pad_x = max(self._pad_x - Log.STEP, 0)

    def scroll_right(self):
        self._pad_x = min(self._pad_x + Log.STEP, self._pad_x_max)

class Centered(Base):
    def __init__(self, window_manager, title, height, width, min_height,
            min_width):
        Base.__init__(self, window_manager)

        self._curses = window_manager.curses
        self._parent = window_manager.curses_window

        self._title = title

        self._border = 2
        self._padding = 2 * self._border
        self._height = height + self._padding
        self._width = width + self._padding
        self._min_height = min_height + self._padding
        self._min_width = min_width + self._padding

        self.resize(*(self._parent.getmaxyx()))

    def refresh(self):
        if not self._curses_window:
            return

        self._curses_window.erase()
        self._curses_window.border()
        t = '|{}|'.format(self._title)
        self._curses_window.addstr(0, (self._cur_width - len(t)) // 2, t)
        self._curses_window.noutrefresh()

    def resize(self, h, w):
        self._curses_window = None
        self._cur_height, self._cur_width = None, None
        self._y, self._x = None, None

        new_h, new_w = min(self._height, h), min(self._width, w)
        if new_h < self._min_height or new_w < self._min_width:
            return

        self._y, self._x = (h - new_h) // 2, (w - new_w) // 2
        self._curses_window = self._parent.subwin(new_h, new_w, self._y, self._x)
        self._cur_height, self._cur_width = new_h, new_w
        self._curses_window.bkgd(self._curses.A_REVERSE)

class Select(Centered):
    def __init__(self, window_manager, title, items):
        if len(items) == 0:
            raise ValueError('Cannot create window with empty list')

        self._items = items
        self._count = len(items)
        self._cursor = ScreenCursor(self._count)

        Centered.__init__(self, window_manager, title,
            self._count, 16, 1, 16)

        self._pad = self._curses.newpad(self._count, 16)
        self._pad.bkgd(self._curses.A_REVERSE)

    @property
    def position(self):
        return self._cursor.position

    @position.setter
    def position(self, val):
        if val < 0 or val >= self._count:
            raise IndexError('Invalid position {}'.format(val))
        self._cursor.position = val

    def handle_key(self, k):
        if k == ord('\n'):
            self.close(True)
        elif k == 27:
            self.close(False)
        elif k == curses.KEY_DOWN:
            self.position = min(self._count - 1, self.position + 1)
        elif k == curses.KEY_UP:
            self.position = max(0, self.position - 1)

    def refresh(self):
        Centered.refresh(self)

        if not self._curses_window:
            return

        for i, x in enumerate(self._items):
            prefix = '▶' if i == self.position else ' '
            self._pad.addnstr(i, 0, '{}{}'.format(prefix, x), self._cur_width)
        b = self._border
        self._pad.noutrefresh(self._cursor.offset, 0, self._y + b, self._x + b,
            self._y + self._cur_height - (b + 1), self._x + self._cur_width - (b + 1))

    def resize(self, h, w):
        Centered.resize(self, h, w)

        if self._curses_window:
            self._cursor.visible_count = self._cur_height - self._padding

class Text(Centered):
    def __init__(self, window_manager, title, max_len):
        self._max_len = max_len
        self._text_input = TextInput(max_len=max_len)
        self._utf8_parser = UTF8Parser(self._text_input.put)

        Centered.__init__(self, window_manager, title, 1,
            self._text_input.width, 1, 2)

    def _update_text_width(self):
        if self._cur_width:
            self._text_input.width = self._cur_width - self._padding

    @property
    def text(self):
        return self._text_input.text

    @text.setter
    def text(self, val):
        self._text_input = TextInput(max_len=self._max_len, text=val)
        self._utf8_parser = UTF8Parser(self._text_input.put)
        self._update_text_width()

    def handle_key(self, k):
        if k == ord('\n'):
            self.close(True)
        elif k == 27:
            if self._parent.getch() == -1:
                self.close(False)
        elif k >= curses.KEY_MIN:
            self._text_input.put(k)
        else:
            self._utf8_parser.put_key(k)

    def refresh(self):
        Centered.refresh(self)

        if not self._curses_window:
            return

        self._curses_window.move(2, 2)
        self._curses_window.addstr(self._border, self._border,
            self._text_input.visible_text)
        self._curses_window.chgat(2, 2, self._text_input.width, 0)
        self._curses_window.move(2, 2 + self._text_input.cursor)
        self._curses_window.noutrefresh()

    def resize(self, h, w):
        Centered.resize(self, h, w)
        self._update_text_width()

    def start(self):
        self._curses.curs_set(1)

    def finish(self):
        self._curses.curs_set(0)

class Datetime(Centered):
    def __init__(self, window_manager, title, dt):
        self._datetime_state = window_states.Datetime(dt)
        width = len(self._datetime_state.text)
        Centered.__init__(self, window_manager, title, 1, width, 1, width)

    @property
    def value(self):
        return self._datetime_state.value

    def handle_key(self, k):
        if k == ord('\n'):
            self.close(True)
        elif k == 27:
            if self._parent.getch() == -1:
                self.close(False)
        elif k == curses.KEY_RIGHT:
            self._datetime_state.move_right()
        elif k == curses.KEY_LEFT:
            self._datetime_state.move_left()
        elif k == curses.KEY_UP:
            self._datetime_state.increment()
        elif k == curses.KEY_DOWN:
            self._datetime_state.decrement()

    def refresh(self):
        Centered.refresh(self)

        if not self._curses_window:
            return

        self._curses_window.addstr(self._border, self._border,
            self._datetime_state.text)
        offset, count = self._datetime_state.position
        self._curses_window.chgat(2, 2 + offset, count, 0)
        self._curses_window.noutrefresh()

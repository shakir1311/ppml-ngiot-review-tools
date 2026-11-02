#!/usr/bin/env python3
"""A screenshot of one of the review's desktop applications on its real data, for the READMEs of the public release (the
author, 2 November 2026: "take screenshots of real apps with real data"). The app is started as usual; once its window is
up, the study named by --key is selected (where the app has a study list), the window is given time to render, its own
picture is taken with Qt (no screen-recording permission, no other window) and the app quits. Claude never looks at the
picture: where a paper's page is in the pane, the study chosen is one published under CC BY, and the author checks the
images before the deposit.

Usage: <the app's python> scripts/review/app_screenshot.py <app.py> <out.png> [--key STUDY] [--delay SECONDS] [-- app arguments]
"""
import pathlib, runpy, sys

args = sys.argv[1:]
app_args = []
if '--' in args:
    app_args = args[args.index('--') + 1:]
    args = args[:args.index('--')]
app_path, out = pathlib.Path(args[0]).resolve(), pathlib.Path(args[1]).resolve()
key = args[args.index('--key') + 1] if '--key' in args else None
delay = float(args[args.index('--delay') + 1]) if '--delay' in args else 6.0

from PySide6 import QtCore, QtWidgets                                  # noqa: E402  (the app's own environment)

_orig_exec = QtWidgets.QApplication.exec


def _select(win):
    """select the study in the app's list, by the app's own row lookup or by the key in a row's text or data"""
    lst = getattr(win, 'list', None)
    if key is None or lst is None:
        return
    def done(i):
        lst.setCurrentRow(i)
        it = lst.item(i)
        print('selected row', i, '|', (it.text() or '')[:90].replace('\n', ' '))
    if hasattr(win, '_row_of'):
        try:
            row = win._row_of(key)
            if row is not None and row >= 0:
                done(row); return
        except Exception:
            pass
    for i in range(lst.count()):
        it = lst.item(i)
        data = it.data(QtCore.Qt.UserRole)
        if key == data or (isinstance(data, dict) and key in map(str, data.values())) or key in (it.text() or ''):
            done(i); return
    cur = lst.currentItem()
    print('key not found in the list; the selected row stays:', (cur.text() if cur else '(none)')[:90].replace('\n', ' '))


def _shot():
    wins = [w for w in QtWidgets.QApplication.topLevelWidgets() if isinstance(w, QtWidgets.QMainWindow) and w.isVisible()]
    if not wins:
        print('no main window'); QtWidgets.QApplication.quit(); return
    win = next((w for w in wins if hasattr(w, 'list')), wins[0])
    print('window:', type(win).__name__, '| study list:', hasattr(win, 'list'))
    _select(win)

    def grab():
        out.parent.mkdir(parents=True, exist_ok=True)
        ok = win.grab().save(str(out))
        print(('saved ' if ok else 'FAILED ') + str(out), win.size().width(), 'x', win.size().height())
        QtWidgets.QApplication.quit()
    QtCore.QTimer.singleShot(int(delay * 1000), grab)


def _exec(*a, **k):                                                    # QApplication.exec is static in PySide6
    QtCore.QTimer.singleShot(1500, _shot)
    return _orig_exec()


QtWidgets.QApplication.exec = staticmethod(_exec)
sys.argv = [str(app_path)] + app_args
if app_path.name == '__main__.py':                                     # a package run as `python -m package`
    sys.path.insert(0, str(app_path.parent.parent))
    runpy.run_module(app_path.parent.name, run_name='__main__', alter_sys=True)
else:
    sys.path.insert(0, str(app_path.parent))
    runpy.run_path(str(app_path), run_name='__main__')

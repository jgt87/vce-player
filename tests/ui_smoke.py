"""Exercise real Tk widgets with an isolated database and hidden window."""
import os
import sys
import tempfile
import tkinter as tk
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from player import Player
from native_view import show_native
from vce_container import read_container
from test_vce_container import (fixture, plain_list_fixture, reorder_question,
                                 connect_question, hotspot_question, point_question)

with tempfile.TemporaryDirectory() as folder:
    with patch.dict(os.environ, {'LOCALAPPDATA': folder}):
        root = tk.Tk()
        root.withdraw()
        app = Player(root)
        app.example()
        app.start(False)
        app.inputs[0].set(True)
        app.move(1)
        app.inputs[0].set(True)
        app.inputs[1].set(True)
        app.marked.set(True)
        app.save_exit()
        app.tree.selection_set(app.digest)
        app.start(True)
        assert app.state['index'] == 1 and app.state['marked'] == [1]
        app.move(1)
        app.inputs.set('127.0.0.1')
        app.move(1)
        app.inputs[1].set(True)
        with patch('player.messagebox.askyesno', return_value=True):
            app.finish()
        row = app.store.db.execute('SELECT result FROM history').fetchone()
        assert '100.0' in row[0], row
        app.library()
        app.tree.selection_set(app.digest)
        app.practice.set(False)
        app.start(False)
        app.state['remaining'] = 0
        app.tick()
        assert not app.active
        assert app.store.db.execute('SELECT count(*) FROM history').fetchone()[0] == 2
        app.history()
        # History drill-down renders a stored result's breakdown (persisted data only).
        assert app.history_rows, 'history should list recorded results'
        top_iid = app.history_tree.get_children()[0]
        app.history_tree.selection_set(top_iid)
        title, created, result = app.history_rows[top_iid]
        detail = app._result_detail_text(title, created, result)
        assert f'{result["percent"]:.1f}%' in detail and 'Sections' in detail, detail
        app._open_result()
        native_path = Path(folder) / 'original-native.vce'
        native_path.write_bytes(fixture())
        native = read_container(native_path)
        native_window = show_native(root, native)
        native_window.withdraw()
        native_window.update_idletasks()
        native_window.destroy()
        app.start_native(native, 'original-fixture-source')
        assert app.active and app.state['practice']
        assert app.exam['practice_only']
        app.inputs[0].set(True)
        app.save_exit()
        app.start_native(native, 'original-fixture-source', resume=True)
        assert app.state['answers']['0'] == [0]

        # Reorder (type 5) and connect (type 7) interactive widgets end-to-end.
        interactions_path = Path(folder) / 'interactions.vce'
        interactions_path.write_bytes(plain_list_fixture(reorder_question(0), connect_question(1)))
        interactions = read_container(interactions_path)
        app.start_native(interactions, 'interaction-source')
        assert app.exam['questions'][0]['type'] == 'order'
        app.order_indexes[:] = app.exam['questions'][0]['answer']
        app.move(1)
        assert app.exam['questions'][1]['type'] == 'connect'
        app.connect_links[:] = [list(link) for link in app.exam['questions'][1]['answer']]
        with patch('player.messagebox.askyesno', return_value=True):
            app.finish()
        latest = app.store.db.execute('SELECT result FROM history ORDER BY id DESC').fetchone()
        assert '100.0' in latest[0], latest

        # Hotspot (type 9) and point-and-shoot (type 3) image-canvas widgets.
        images_path = Path(folder) / 'image-interactions.vce'
        images_path.write_bytes(plain_list_fixture(hotspot_question(0), point_question(1)))
        image_container = read_container(images_path)
        app.start_native(image_container, 'image-source')
        assert app.exam['questions'][0]['type'] == 'hotspot'
        app.hotspot_selected = set(app.exam['questions'][0]['answer'])
        app.move(1)
        assert app.exam['questions'][1]['type'] == 'point'
        left, top, right, bottom = app.exam['questions'][1]['rect']
        app.point_xy = ((left + right) // 2, (top + bottom) // 2)
        with patch('player.messagebox.askyesno', return_value=True):
            app.finish()
        latest = app.store.db.execute('SELECT result FROM history ORDER BY id DESC').fetchone()
        assert '100.0' in latest[0], latest

        root.update_idletasks()
        app.close()
print('Tk UI smoke passed: JSON sessions, scoring, timer, history, result drill-down, '
      'native VCE viewer, native subset practice save/resume, reorder, connect, hotspot '
      'and point interactions.')

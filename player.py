"""Run with python player.py. Native VCE inspection also uses cryptography."""
import argparse
import base64
import hashlib
import json
import os
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from exam_engine import Store, load_exam, correct, score
from vce_inspector import inspect_vce
from gui_widgets import ScrollFrame


class Player:
    def __init__(self, root):
        self.root = root
        root.title('Study Player')
        root.geometry('1000x700')
        root.minsize(760, 540)
        root.configure(background='#f3f6f8')
        style = ttk.Style(root)
        style.theme_use('clam')
        style.configure('.', font=('Segoe UI', 10))
        style.configure('TFrame', background='#f3f6f8')
        style.configure('TLabel', background='#f3f6f8', foreground='#182c3c')
        style.configure('TCheckbutton', background='#f3f6f8')
        style.configure('TButton', padding=(10, 7))
        style.configure('Treeview', rowheight=28, background='#ffffff', fieldbackground='#ffffff')
        style.configure('Treeview.Heading', font=('Segoe UI', 10, 'bold'), padding=6)
        directory = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'OriginalStudyPlayer'
        directory.mkdir(parents=True, exist_ok=True)
        self.store = Store(directory / 'study.db')
        self.active = False
        self.practice = tk.BooleanVar(value=True)
        self.candidate = tk.StringVar(value='Candidate')
        self.body = ttk.Frame(root, padding=24)
        self.body.pack(fill='both', expand=True)
        root.protocol('WM_DELETE_WINDOW', self.close)
        self.library()
        root.after(500, self.tick)

    def clear(self):
        for child in self.body.winfo_children():
            child.destroy()

    def heading(self, title, subtitle=''):
        ttk.Label(self.body, text=title, font=('Segoe UI', 22, 'bold')).pack(anchor='w', pady=(0, 8))
        if subtitle:
            ttk.Label(self.body, text=subtitle, wraplength=850).pack(anchor='w', pady=(0, 18))

    def library(self):
        self.active = False
        self.clear()
        self.heading('Your exam library', 'Original study exams • local saved progress • practice and timed sessions')
        bar = ttk.Frame(self.body)
        bar.pack(fill='x', pady=8)
        for label, command in [('Add exam', self.add), ('Load example', self.example), ('Open VCE / VCEX / OEF', self.open_vce), ('Inspect exam', self.inspect), ('Result history', self.history)]:
            ttk.Button(bar, text=label, command=command).pack(side='left', padx=(0, 8))
        self.tree = ttk.Treeview(self.body, columns=('title', 'path'), show='headings')
        self.tree.heading('title', text='Exam')
        self.tree.heading('path', text='File')
        self.tree.column('title', width=340)
        self.tree.pack(fill='both', expand=True, pady=12)
        for digest, path, title in self.store.db.execute('SELECT * FROM library ORDER BY title'):
            self.tree.insert('', 'end', iid=digest, values=(title, path))
        ttk.Checkbutton(self.body, text='Practice mode (show explanations; no timer)', variable=self.practice).pack(anchor='w')
        ttk.Label(self.body, text='Candidate name').pack(anchor='w', pady=(8, 0))
        ttk.Entry(self.body, textvariable=self.candidate, width=35).pack(anchor='w')
        actions = ttk.Frame(self.body)
        actions.pack(anchor='w', pady=14)
        ttk.Button(actions, text='Start new session', command=lambda: self.start(False)).pack(side='left', padx=(0, 8))
        ttk.Button(actions, text='Resume saved session', command=lambda: self.start(True)).pack(side='left')

    def import_path(self, path):
        try:
            exam, digest = load_exam(path)
            if exam.get('scope_notice'):
                messagebox.showinfo('VCEX import coverage', exam['scope_notice'])
            if exam.get('instructions'):
                messagebox.showinfo('Exam instructions', exam['instructions'])
            self.store.add(digest, path, exam['title'])
            self.library()
            self.tree.selection_set(digest)
        except (ValueError, OSError, TypeError) as error:
            messagebox.showerror('Unable to add exam', str(error))

    def add(self):
        path = filedialog.askopenfilename(filetypes=[('Study exams', '*.json *.vcex *.oef'), ('All files', '*.*')])
        if path:
            self.import_path(path)

    def example(self):
        self.import_path(Path(__file__).parent / 'examples' / 'network-basics.json')

    def inspect(self):
        path = filedialog.askopenfilename(filetypes=[('Exam containers', '*.vce *.vcex *.oef')])
        if not path:
            return
        try:
            if Path(path).suffix.lower() == '.oef':
                from oef_reader import read_oef
                exam = read_oef(path)
                minutes = exam['source_time_limit_minutes']
                messagebox.showinfo('OEF inspection',
                    f'{exam["title"]}\nExam: {exam["exam_number"]}\nFormat: {exam["source_format"]}\n'
                    f'Questions: {len(exam["questions"])}\nPassing score: {exam["oef_passmark"]} / 1000\n'
                    f'Time limit: {str(minutes) + " minutes" if minutes else "Untimed"}\n'
                    f'Answers hidden: {exam["hide_answers"]}\nEncryption: None')
                return
            if Path(path).suffix.lower() == '.vcex':
                from vcex_reader import read_vcex
                data = read_vcex(path)
                messagebox.showinfo('VCEX inspection',
                    f'{data["title"]}\nExam: {data["exam_number"]}\nFormat: {data["format"]}\n'
                    f'Questions: {data["source_count"]}\nReadable: {data["readable_count"]}\n'
                    f'Encrypted: {data["encrypted_count"]}\nEmbedded images: {data["image_count"]}\n'
                    f'Password required: {data["password_required"]}\n\n'
                    'Encrypted question content requires a ProfExam content key. Practice imports supported readable questions only.')
                return
            metadata = inspect_vce(path)
            version = metadata['format']
            details = f'Format value: {version}\nSize: {metadata["size"]:,} bytes\nHeader range: {"within documented maximum" if version <= 63 else "newer than documented maximum"}'
            if 'title' in metadata:
                details += f'\nExam number: {metadata["exam_number"]}\nTitle: {metadata["title"]}'
            if 'time_limit_minutes' in metadata:
                details += f'\nTime limit: {metadata["time_limit_minutes"]} minutes\nPassing score (raw): {metadata["passing_score_raw"]}\nPassword flag: {metadata["password_required"]}'
            messagebox.showinfo('VCE metadata inspection', details + '\n\n' + metadata['metadata_status'])
        except (OSError, ValueError) as error:
            messagebox.showerror('Inspection failed', str(error))

    def open_vce(self):
        path = filedialog.askopenfilename(filetypes=[('Exam containers', '*.vce *.vcex *.oef')])
        if not path:
            return
        if Path(path).suffix.lower() in ('.vcex', '.oef'):
            self.import_path(path)
            return
        try:
            from vce_container import read_container
            from native_view import show_native
            container = read_container(path)
            source_digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
            show_native(self.root, container, on_practice=lambda: self.start_native(container, source_digest, False),
                        on_resume=lambda: self.start_native(container, source_digest, True))
        except (OSError, ValueError) as error:
            messagebox.showerror('Unable to open VCE', str(error))

    def start(self, resume):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo('Select an exam', 'Select an exam in the library first.')
            return
        path = self.tree.item(selection[0], 'values')[1]
        try:
            exam, digest = load_exam(path)
            if digest != selection[0]:
                raise ValueError('The exam file changed. Add it again to create a new library entry.')
            self.begin_session(exam, digest, resume)
        except (OSError, ValueError, TypeError) as error:
            messagebox.showerror('Unable to start', str(error))

    def start_native(self, container, source_digest, resume=False):
        try:
            from native_study import practice_exam
            exam, digest = practice_exam(container, source_digest)
            self.begin_session(exam, digest, resume)
            return True
        except (OSError, ValueError, TypeError) as error:
            messagebox.showerror('Unable to start native practice', str(error))
            return False

    def begin_session(self, exam, digest, resume=False):
        saved = self.store.resume(digest)
        if resume and saved is None:
            raise ValueError('There is no saved session for this exam.')
        if not resume and saved and not messagebox.askyesno('Replace saved progress?', 'Starting a new session replaces this exam’s saved progress. Continue?'):
            return False
        if self.active:
            self.capture()
            self.store.save(self.digest, self.state)
        self.exam, self.digest = exam, digest
        self.state = saved if resume else dict(index=0, answers={}, marked=[], practice=bool(exam.get('practice_only') or self.practice.get()), remaining=exam['time_limit_minutes'] * 60)
        self.state.setdefault('candidate', self.candidate.get().strip() or 'Candidate')
        self.state.setdefault('elapsed_sec', 0)
        self.active = True
        self.last_tick = time.monotonic()
        self.store.save(self.digest, self.state)
        self.question()
        return True

    def _read_response(self, q):
        kind = q['type']
        if kind == 'choice':
            return [n for n, v in enumerate(self.inputs) if v.get()]
        if kind == 'order':
            return list(self.order_indexes)
        if kind == 'connect':
            return [list(link) for link in self.connect_links]
        if kind == 'hotspot':
            return sorted(self.hotspot_selected)
        if kind == 'point':
            return list(self.point_xy) if self.point_xy else None
        return self.inputs.get()

    def capture(self):
        i = self.state['index']
        q = self.exam['questions'][i]
        self.state['answers'][str(i)] = self._read_response(q)
        if self.marked.get() and i not in self.state['marked']:
            self.state['marked'].append(i)
        elif not self.marked.get() and i in self.state['marked']:
            self.state['marked'].remove(i)

    def question(self):
        self.clear()
        i = self.state['index']
        q = self.exam['questions'][i]
        self.heading(self.exam['title'], f'Question {i + 1} of {len(self.exam["questions"])} • {q.get("section", "General")}')
        bar = ttk.Frame(self.body)
        bar.pack(side='bottom', fill='x', pady=10)
        for label, command in [('Previous', lambda: self.move(-1)), ('Next', lambda: self.move(1)), ('Review questions', self.review), ('Save & exit', self.save_exit), ('Finish exam', self.finish)]:
            ttk.Button(bar, text=label, command=command).pack(side='left', padx=(0, 7))
        if self.exam.get('scope_notice'):
            ttk.Label(self.body, text=self.exam['scope_notice'], wraplength=850).pack(anchor='w', pady=(0, 8))
        self.clock = ttk.Label(self.body)
        self.clock.pack(anchor='w')
        scroll = ScrollFrame(self.body)
        scroll.pack(fill='both', expand=True)
        content = scroll.content
        ttk.Label(content, text=q['prompt'], font=('Segoe UI', 14), wraplength=800).pack(anchor='w', pady=16)
        self.question_images = []
        for number, raw_image in enumerate(q.get('images', []), 1):
            try:
                image = tk.PhotoImage(data=raw_image, master=self.root)
                self.question_images.append(image)
                ttk.Label(content, text=f'Image {number}').pack(anchor='w')
                ttk.Label(content, image=image).pack(anchor='w', pady=8)
            except tk.TclError as error:
                self.active = False
                messagebox.showerror('Unable to render question', f'Embedded image {number} could not be displayed: {error}')
                self.library()
                return
        answer = self.state['answers'].get(str(i))
        if q['type'] == 'choice':
            ttk.Label(content, text='Select all correct answers.' if len(q['answer']) > 1 else 'Select one answer.').pack(anchor='w', pady=(0, 10))
            self.inputs = []
            for n, option in enumerate(q['options']):
                variable = tk.BooleanVar(value=n in (answer or []))
                self.inputs.append(variable)
                def selected(n=n):
                    if len(q['answer']) == 1 and self.inputs[n].get():
                        for index, other in enumerate(self.inputs):
                            if index != n:
                                other.set(False)
                tk.Checkbutton(content, text=option, variable=variable, command=selected,
                               wraplength=780, justify='left', anchor='w', background='#f3f6f8',
                               activebackground='#f3f6f8', font=('Segoe UI', 11)).pack(anchor='w', fill='x', pady=7)
        elif q['type'] == 'order':
            self._build_order_widget(content, q, answer)
        elif q['type'] == 'connect':
            self._build_connect_widget(content, q, answer)
        elif q['type'] == 'hotspot':
            self._build_hotspot_widget(content, q, answer)
        elif q['type'] == 'point':
            self._build_point_widget(content, q, answer)
        else:
            self.inputs = tk.StringVar(value=answer or '')
            ttk.Entry(content, textvariable=self.inputs, width=60).pack(anchor='w', pady=10)
        self.marked = tk.BooleanVar(value=i in self.state['marked'])
        ttk.Checkbutton(content, text='Mark for review', variable=self.marked).pack(anchor='w', pady=20)
        self.feedback = ttk.Label(content, wraplength=800)
        self.feedback.pack(anchor='w', pady=8)
        if self.state['practice'] and not self.exam.get('hide_answers'):
            ttk.Button(content, text='Check answer', command=self.check).pack(anchor='w')

    def _build_order_widget(self, content, q, answer):
        ttk.Label(content, text='Arrange the items into the correct order using Move up / Move down.').pack(anchor='w', pady=(0, 10))
        valid = isinstance(answer, list) and sorted(answer) == list(range(len(q['items'])))
        self.order_indexes = list(answer) if valid else list(range(len(q['items'])))
        listbox = tk.Listbox(content, height=min(12, len(q['items'])), font=('Segoe UI', 11),
                             activestyle='none', exportselection=False)
        for idx in self.order_indexes:
            listbox.insert('end', q['items'][idx])
        listbox.pack(anchor='w', fill='x', pady=6)
        if self.order_indexes:
            listbox.selection_set(0)

        def move(delta):
            selection = listbox.curselection()
            if not selection:
                return
            pos = selection[0]
            target = pos + delta
            if not 0 <= target < len(self.order_indexes):
                return
            self.order_indexes[pos], self.order_indexes[target] = self.order_indexes[target], self.order_indexes[pos]
            item = listbox.get(pos)
            listbox.delete(pos)
            listbox.insert(target, item)
            listbox.selection_clear(0, 'end')
            listbox.selection_set(target)
        buttons = ttk.Frame(content)
        buttons.pack(anchor='w', pady=4)
        ttk.Button(buttons, text='Move up', command=lambda: move(-1)).pack(side='left', padx=(0, 6))
        ttk.Button(buttons, text='Move down', command=lambda: move(1)).pack(side='left')

    def _build_connect_widget(self, content, q, answer):
        ttk.Label(content, text='Build each relationship: choose a source, a connector and a target, then Add.').pack(anchor='w', pady=(0, 10))
        self.connect_links = [list(link) for link in answer] if isinstance(answer, list) else []
        row = ttk.Frame(content)
        row.pack(anchor='w', pady=4)
        source = ttk.Combobox(row, values=q['boxes'], state='readonly', width=22)
        connector = ttk.Combobox(row, values=q['connectors'], state='readonly', width=18)
        target = ttk.Combobox(row, values=q['boxes'], state='readonly', width=22)
        for combo in (source, connector, target):
            combo.pack(side='left', padx=(0, 6))
        listbox = tk.Listbox(content, height=min(10, max(3, len(q['boxes']))), font=('Segoe UI', 10), exportselection=False)

        def refresh():
            listbox.delete(0, 'end')
            for s, t, c in self.connect_links:
                listbox.insert('end', f'{q["boxes"][s]}  -[{q["connectors"][c]}]->  {q["boxes"][t]}')

        def add():
            if source.current() < 0 or connector.current() < 0 or target.current() < 0:
                return
            link = [source.current(), target.current(), connector.current()]
            if link not in self.connect_links:
                self.connect_links.append(link)
                refresh()

        def remove():
            selection = listbox.curselection()
            if selection:
                del self.connect_links[selection[0]]
                refresh()
        actions = ttk.Frame(content)
        actions.pack(anchor='w', pady=4)
        ttk.Button(actions, text='Add relationship', command=add).pack(side='left', padx=(0, 6))
        ttk.Button(actions, text='Remove selected', command=remove).pack(side='left')
        listbox.pack(anchor='w', fill='x', pady=6)
        refresh()

    def _question_image(self, data):
        image = tk.PhotoImage(data=base64.b64encode(bytes(data)), master=self.root)
        self.question_images.append(image)
        return image

    def _build_hotspot_widget(self, content, q, answer):
        self.hotspot_selected = set(answer) if isinstance(answer, list) else set()
        ttk.Label(content, text='Click each correct area; click it again to deselect.').pack(anchor='w', pady=(0, 10))
        image = self._question_image(q['image'])
        canvas = tk.Canvas(content, width=image.width(), height=image.height(), highlightthickness=0)
        canvas.create_image(0, 0, anchor='nw', image=image)
        rects = {}

        def bounds(area):
            left, top, right, bottom = area
            return min(left, right), min(top, bottom), max(left, right), max(top, bottom)

        def draw(i):
            lo_x, lo_y, hi_x, hi_y = bounds(q['areas'][i])
            if i in rects:
                canvas.delete(rects[i])
            selected = i in self.hotspot_selected
            rects[i] = canvas.create_rectangle(lo_x, lo_y, hi_x, hi_y,
                                               outline='#d62828' if selected else '#9aa7b1',
                                               width=3 if selected else 1)
        for i in range(len(q['areas'])):
            draw(i)

        def click(event):
            for i, area in enumerate(q['areas']):
                lo_x, lo_y, hi_x, hi_y = bounds(area)
                if lo_x <= event.x <= hi_x and lo_y <= event.y <= hi_y:
                    self.hotspot_selected ^= {i}
                    draw(i)
                    break
        canvas.bind('<Button-1>', click)
        canvas.pack(anchor='w', pady=6)

    def _build_point_widget(self, content, q, answer):
        self.point_xy = tuple(answer) if isinstance(answer, list) and len(answer) == 2 else None
        ttk.Label(content, text='Click the correct point on the image.').pack(anchor='w', pady=(0, 10))
        image = self._question_image(q['image'])
        canvas = tk.Canvas(content, width=image.width(), height=image.height(), highlightthickness=0)
        canvas.create_image(0, 0, anchor='nw', image=image)
        marker = [None]

        def place(x, y):
            if marker[0] is not None:
                canvas.delete(marker[0])
            marker[0] = canvas.create_oval(x - 6, y - 6, x + 6, y + 6, outline='#d62828', width=3)
        if self.point_xy:
            place(*self.point_xy)

        def click(event):
            self.point_xy = (event.x, event.y)
            place(event.x, event.y)
        canvas.bind('<Button-1>', click)
        canvas.pack(anchor='w', pady=6)

    def move(self, delta):
        self.capture()
        self.state['index'] = max(0, min(len(self.exam['questions']) - 1, self.state['index'] + delta))
        self.store.save(self.digest, self.state)
        self.question()

    def check(self):
        if self.exam.get('hide_answers'):
            return
        self.capture()
        q = self.exam['questions'][self.state['index']]
        verdict = 'Correct.' if correct(q, self.state['answers'].get(str(self.state['index']))) else 'Incorrect.'
        self.feedback.configure(text=verdict + ' ' + q.get('explanation', ''))

    def review(self):
        self.capture()
        window = tk.Toplevel(self.root)
        window.title('Question review')
        listing = tk.Listbox(window, width=80, height=20)
        listing.pack(fill='both', expand=True, padx=15, pady=15)
        for i, q in enumerate(self.exam['questions']):
            status = 'Answered' if self.state['answers'].get(str(i)) else 'Unanswered'
            listing.insert('end', f'{i+1}. {status}{" • Marked" if i in self.state["marked"] else ""} — {q["prompt"][:70]}')
        def jump():
            if listing.curselection():
                self.state['index'] = listing.curselection()[0]
                window.destroy()
                self.question()
        ttk.Button(window, text='Go to selected question', command=jump).pack(pady=10)

    def tick(self):
        if self.active:
            now = time.monotonic()
            self.state['elapsed_sec'] += now - self.last_tick
            if not self.state['practice']:
                self.state['remaining'] = max(0, self.state['remaining'] - (now - self.last_tick))
            self.last_tick = now
            seconds = int(self.state['remaining'])
            self.clock.configure(text='Practice session' if self.state['practice'] else f'Time remaining: {seconds//60:02}:{seconds%60:02}')
            if not self.state['practice'] and self.state['remaining'] <= 0:
                self.finish(expired=True)
        self.root.after(500, self.tick)

    def save_exit(self):
        self.capture()
        self.store.save(self.digest, self.state)
        self.library()

    def finish(self, expired=False):
        self.capture()
        self.active = False
        if not expired and not messagebox.askyesno('Finish exam?', 'Submit your answers and record the result?'):
            self.last_tick = time.monotonic()
            self.active = True
            return
        result = score(self.exam, self.state['answers'])
        result.update(marked=len(self.state['marked']), practice=self.state['practice'])
        result['scope_notice'] = self.exam.get('scope_notice', '')
        result.update(candidate=self.state['candidate'], elapsed_sec=round(self.state['elapsed_sec']),
                      passing_score=self.exam['passing_score'], exam_number=self.exam.get('exam_number', ''),
                      incorrect_count=result['total'] - result['correct'],
                      answers=self.state['answers'], marked_questions=self.state['marked'])
        self.store.finish(self.digest, self.exam['title'], result)
        self.clear()
        verdict = 'Practice result' if self.exam.get('practice_only') else ('Passed' if result['passed'] else 'Below passing score')
        self.heading('Exam complete', f'{verdict} • {result["percent"]:.1f}% • {result["correct"]}/{result["total"]} correct • {result["incomplete"]} unanswered')
        text = tk.Text(self.body, wrap='word', font=('Segoe UI', 11))
        text.pack(fill='both', expand=True)
        if result['scope_notice']:
            text.insert('end', result['scope_notice'] + '\n\n')
        text.insert('end', f'Candidate: {result["candidate"]}\nElapsed: {result["elapsed_sec"]} seconds\nPassing score: {result["passing_score"]}%\n\nSections\n')
        for name, section in result['sections'].items():
            text.insert('end', f'{name}: {section["correct"]}/{section["total"]} correct\n')
        text.insert('end', '\nQuestion review\n\n')
        for i, q in enumerate(self.exam['questions']):
            text.insert('end', f'{i+1}. {q["prompt"]}\n{"Correct" if correct(q, self.state["answers"].get(str(i))) else "Incorrect"} — Expected: {self._expected(q)}\n{q.get("explanation", "")}\n\n')
        text.configure(state='disabled')
        ttk.Button(self.body, text='Back to library', command=self.library).pack(anchor='w', pady=15)

    def _expected(self, q):
        kind = q['type']
        if kind == 'choice':
            return ', '.join(q['options'][n] for n in q['answer'])
        if kind == 'order':
            return ' → '.join(q['items'][i] for i in q['answer'])
        if kind == 'connect':
            return '; '.join(f'{q["boxes"][s]} -[{q["connectors"][c]}]-> {q["boxes"][t]}' for s, t, c in q['answer'])
        if kind == 'hotspot':
            return 'Areas ' + ', '.join(str(i + 1) for i in q['answer'])
        if kind == 'point':
            left, top, right, bottom = q['rect']
            return f'a point within ({left}, {top})-({right}, {bottom})'
        return ' / '.join(q['answer'])

    def history(self):
        self.clear()
        self.heading('Result history', 'Double-click a result, or select one and choose View details, to see its breakdown.')
        listing = ttk.Treeview(self.body, columns=('date', 'exam', 'score', 'mode'), show='headings')
        for key in ('date', 'exam', 'score', 'mode'):
            listing.heading(key, text=key.title())
        listing.pack(fill='both', expand=True)
        self.history_rows = {}
        for row_id, date, title, data in self.store.db.execute('SELECT id,created,title,result FROM history ORDER BY id DESC'):
            result = json.loads(data)
            iid = listing.insert('', 'end', values=(date + ' UTC', title,
                                 f'{result["percent"]:.1f}%', 'Practice' if result.get('practice') else 'Timed'))
            self.history_rows[iid] = (title, date, result)
        self.history_tree = listing
        listing.bind('<Double-1>', lambda event: self._open_result())
        buttons = ttk.Frame(self.body)
        buttons.pack(anchor='w', pady=15)
        ttk.Button(buttons, text='View details', command=self._open_result).pack(side='left')
        ttk.Button(buttons, text='Back to library', command=self.library).pack(side='left', padx=(10, 0))

    def _open_result(self):
        selection = self.history_tree.selection()
        if not selection:
            return
        title, created, result = self.history_rows[selection[0]]
        window = tk.Toplevel(self.root)
        window.title(f'Result — {title}')
        text = tk.Text(window, wrap='word', font=('Segoe UI', 11), width=74, height=24)
        text.pack(fill='both', expand=True, padx=12, pady=12)
        text.insert('end', self._result_detail_text(title, created, result))
        text.configure(state='disabled')
        ttk.Button(window, text='Close', command=window.destroy).pack(pady=(0, 12))

    def _result_detail_text(self, title, created, result):
        """Render a stored history result as plain text. Only persisted fields are
        shown; older rows written before a field existed fall back gracefully."""
        verdict = ('Practice result' if result.get('practice')
                   else 'Passed' if result.get('passed') else 'Below passing score')
        lines = [title, f'Recorded: {created} UTC', '']
        if result.get('scope_notice'):
            lines += [result['scope_notice'], '']
        if result.get('candidate'):
            lines.append(f'Candidate: {result["candidate"]}')
        lines.append(f'Result: {verdict}')
        lines.append(f'Score: {result["percent"]:.1f}%  ({result.get("correct", 0)}/{result.get("total", 0)} correct)')
        if 'normalized_score' in result:
            lines.append(f'Normalized score: {result["normalized_score"]}/1000')
        if result.get('incomplete') is not None:
            lines.append(f'Unanswered: {result["incomplete"]}')
        if result.get('marked') is not None:
            lines.append(f'Marked for review: {result["marked"]}')
        if result.get('passing_score') is not None:
            lines.append(f'Passing score: {result["passing_score"]}%')
        lines.append(f'Mode: {"Practice" if result.get("practice") else "Timed"}')
        if result.get('elapsed_sec') is not None:
            lines.append(f'Elapsed: {result["elapsed_sec"]} seconds')
        sections = result.get('sections') or {}
        if sections:
            lines += ['', 'Sections']
            for name, section in sections.items():
                lines.append(f'  {name}: {section["correct"]}/{section["total"]} correct')
        return '\n'.join(lines) + '\n'

    def close(self):
        if self.active:
            self.capture()
            self.store.save(self.digest, self.state)
        self.store.db.close()
        self.root.destroy()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Study Player desktop application')
    parser.add_argument('--self-test-report', help='Run isolated GUI checks and write a JSON report.')
    args = parser.parse_args()
    if args.self_test_report:
        from app_selftest import run_selftest
        # Self-test imports refer to this same module when the entry point is __main__.
        import sys
        sys.modules.setdefault('player', sys.modules[__name__])
        run_selftest(Player, args.self_test_report)
    else:
        root = tk.Tk()
        Player(root)
        root.mainloop()

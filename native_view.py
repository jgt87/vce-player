"""Native VCE content view, preserving explicit compatibility status."""
import base64
import tkinter as tk
from tkinter import ttk
from richview import parse_nested_documents, parse_richview


def show_native(root, container, on_practice=None, on_resume=None):
    window = tk.Toplevel(root)
    window.title(container['metadata']['title'] + ' — VCE content')
    window.geometry('1100x800')
    window.minsize(800, 560)
    frame = ttk.Frame(window, padding=16)
    frame.pack(fill='both', expand=True)
    total, decoded = len(container['records']), container['decoded_count']
    ttk.Label(frame, text=container['metadata']['title'], font=('Segoe UI', 20, 'bold')).pack(anchor='w')
    ttk.Label(frame, text=f'Format 62 • {total} records • {decoded} content records decoded', wraplength=1000).pack(anchor='w', pady=8)
    if on_practice:
        actions = ttk.Frame(frame)
        actions.pack(anchor='w', pady=(0, 8))
        def start_practice(callback):
            if callback():
                window.destroy()
        ttk.Button(actions, text='Practice decoded textual choices', command=lambda: start_practice(on_practice)).pack(side='left', padx=(0, 8))
        if on_resume:
            ttk.Button(actions, text='Resume subset practice', command=lambda: start_practice(on_resume)).pack(side='left')
    if decoded < total:
        ttk.Label(frame, text='Compatibility is incomplete. Encrypted records remain visible in the list; they cannot be played or scored.').pack(anchor='w', pady=(0, 10))
    panes = ttk.Panedwindow(frame, orient='horizontal')
    panes.pack(fill='both', expand=True)
    listing = ttk.Treeview(panes, columns=('question', 'status'), show='tree headings', selectmode='browse')
    listing.heading('#0', text='Group / question')
    listing.heading('status', text='Status')
    listing.column('#0', width=260)
    listing.column('question', width=0, stretch=False)
    listing.column('status', width=100)
    panes.add(listing, weight=1)
    view_frame = ttk.Frame(panes)
    panes.add(view_frame, weight=3)
    text = tk.Text(view_frame, wrap='word', font=('Segoe UI', 11), padx=12, pady=12)
    scrollbar = ttk.Scrollbar(view_frame, command=text.yview)
    scrollbar.pack(side='right', fill='y')
    text.configure(yscrollcommand=scrollbar.set)
    text.pack(fill='both', expand=True)
    images = []
    for i, group in enumerate(container['groups']):
        parent = listing.insert('', 'end', iid=f'g{i}', text=f'{group["title"]} ({group["count"]})', open=i == 0)
        for child in group['children']:
            for index in child['records']:
                record = container['records'][index]
                listing.insert(parent, 'end', iid=f'q{index}', text=f'Question {index + 1}', values=('', 'Decoded' if record['decoded'] else 'Encrypted'))

    def render_document(document):
        text.insert('end', document.text + '\n\n')
        for warning in document.warnings:
            text.insert('end', 'Document limitation: ' + warning + '\n')
        for image_data in document.images:
            try:
                image = tk.PhotoImage(master=window, data=base64.b64encode(image_data))
                images.append(image)
                text.image_create('end', image=image)
                text.insert('end', '\n')
            except tk.TclError:
                text.insert('end', '[Image could not be displayed]\n')

    def selected(event=None):
        selection = listing.selection()
        if not selection or not selection[0].startswith('q'):
            return
        record = container['records'][int(selection[0][1:])]
        text.configure(state='normal')
        text.delete('1.0', 'end')
        images.clear()
        if not record['decoded']:
            text.insert('end', 'This record has not been decoded.\n\n' + record.get('error', 'Unsupported record.'))
        else:
            text.insert('end', f'Question {record["index"] + 1} • Native type {record.get("type")}\n\n')
            child = container['groups'][record['group']]['children'][record['child']]
            if child['kind'] == 1:
                text.insert('end', 'Case study\n\n')
                if child.get('body') is not None:
                    try:
                        render_document(parse_richview(child['body']))
                    except ValueError as error:
                        text.insert('end', 'Case-study document limitation: ' + str(error) + '\n\n')
                else:
                    text.insert('end', 'The case-study context remains encrypted.\n\n')
            try:
                documents = parse_nested_documents(record['prompt_data'])
                for i, doc in enumerate(documents):
                    if i > 0 and doc.text:
                        text.insert('end', f'Document {i + 1}\n')
                    render_document(doc)
            except ValueError as error:
                text.insert('end', 'Document parsing limitation: ' + str(error))
            text.insert('end', '\nStored response data: ' + record['answer_data'].decode('utf-8', errors='backslashreplace') + '\n')
            if record.get('extra_data'):
                try:
                    for doc in parse_nested_documents(record['extra_data']):
                        render_document(doc)
                except ValueError:
                    text.insert('end', '\nAdditional document layout is not supported yet.\n')
        text.configure(state='disabled')
    listing.bind('<<TreeviewSelect>>', selected)
    if total:
        listing.selection_set('q0')
        selected()
    return window

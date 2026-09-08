"""Native tkinter controls for Windows media service profiles."""

import tkinter as tk
from tkinter import messagebox, ttk


def sorted_profiles(store):
    return sorted(store.profiles, key=lambda p: (p['group'], p['name']))


class ProfilePicker(ttk.LabelFrame):
    def __init__(self, parent, store):
        super().__init__(parent, text='当前媒体服务', padding=8)
        self.store = store
        self.combo = ttk.Combobox(self, state='readonly')
        self.combo.pack(side='top', fill='x')
        self.combo.bind('<<ComboboxSelected>>', self.select)
        self.details = ttk.Label(self, wraplength=700)
        self.details.pack(side='top', fill='x', pady=(6, 0))
        self.bind('<Configure>', lambda e: self.details.configure(wraplength=max(150, e.width - 20)))
        unsubscribe = store.subscribe(self.refresh)
        self.bind('<Destroy>', lambda e: unsubscribe() if e.widget is self else None, add='+')
        self.refresh()

    def refresh(self):
        self.items = sorted_profiles(self.store)
        active = self.store.active
        self.combo.configure(values=[f"{p['group'] + ' / ' if p['group'] else ''}{p['name']}" for p in self.items])
        if active:
            self.combo.current(next(i for i, p in enumerate(self.items) if p['id'] == active['id']))
            kind = 'Jellyfin' if active['server_type'] == 'jellyfin' else 'Emby'
            status = ' · 任务运行中，切换已锁定' if self.store.busy else ''
            self.details.configure(
                text=f"{kind} · {active['server_url']} · 用户：{active['username'] or '未填写'}{status}"
            )
        else:
            self.combo.set('尚无配置')
            self.details.configure(text='请点击右上角“服务配置”，新增 Jellyfin 或 Emby 服务。')
        self.combo.configure(state='disabled' if self.store.busy or not active else 'readonly')

    def select(self, _event=None):
        index = self.combo.current()
        if index >= 0:
            try:
                self.store.select(self.items[index]['id'])
            except (ValueError, OSError) as exc:
                messagebox.showerror('切换失败', str(exc), parent=self)
                self.refresh()


class ProfileManager(tk.Toplevel):
    def __init__(self, parent, store, origin):
        super().__init__(parent)
        self.store = store
        self.editing = None
        self.dirty = False
        self.loading = False
        self.title('媒体服务配置')
        self.transient(parent.winfo_toplevel())
        self.geometry('870x560')
        self.minsize(720, 480)
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.bind('<Escape>', lambda _e: self.close())
        body = ttk.Frame(self, padding=12)
        body.pack(fill='both', expand=True)
        left = ttk.Frame(body)
        left.pack(side='left', fill='y', padx=(0, 16))
        self.tree = ttk.Treeview(left, show='tree', selectmode='browse', height=17)
        self.tree.column('#0', width=245, minwidth=170)
        self.tree.pack(fill='both', expand=True)
        self.tree.bind('<<TreeviewSelect>>', self.choose)
        ttk.Button(left, text='＋ 新增服务配置', command=self.new_profile).pack(fill='x', pady=(10, 0))
        right = ttk.Frame(body)
        right.pack(side='left', fill='both', expand=True)
        self.edit_title = ttk.Label(right, text='编辑配置')
        self.edit_title.pack(anchor='w', pady=(0, 8))
        self.fields = {}
        for key, label in (
            ('name', '配置名称'),
            ('group', '所属服务器（可选）'),
            ('server_type', '服务类型'),
            ('server_url', '完整服务地址'),
            ('api_key', 'API Key'),
            ('username', '用户名'),
        ):
            ttk.Label(right, text=label).pack(anchor='w')
            row = ttk.Frame(right)
            row.pack(fill='x', pady=(2, 8))
            variable = tk.StringVar(self)
            self.fields[key] = variable
            if key == 'server_type':
                field = ttk.Combobox(row, textvariable=variable, values=['Jellyfin', 'Emby'], state='readonly')
            else:
                field = ttk.Entry(row, textvariable=variable, show='*' if key == 'api_key' else '')
            field.pack(side='left', fill='x', expand=True)
            if key == 'api_key':
                self.key_entry = field
                self.reveal = ttk.Button(row, text='显示', width=6, command=self.toggle_key)
                self.reveal.pack(side='left', padx=(5, 0))
            variable.trace_add('write', self.changed)
        self.feedback = ttk.Label(right, wraplength=450)
        self.feedback.pack(fill='x', pady=5)
        actions = ttk.Frame(right)
        actions.pack(side='bottom', fill='x')
        self.delete_button = ttk.Button(actions, text='删除', command=self.delete_profile)
        self.delete_button.pack(side='left')
        self.save_button = ttk.Button(actions, text='保存配置', command=self.save_profile)
        self.save_button.pack(side='right')
        self.revert_button = ttk.Button(actions, text='还原修改', command=self.revert)
        self.revert_button.pack(side='right', padx=6)
        footer = ttk.Frame(self, padding=12)
        footer.pack(fill='x')
        ttk.Label(footer, text=f'关闭后返回：{origin}').pack(side='left')
        ttk.Button(footer, text='关闭', command=self.close).pack(side='right')
        self.use_button = ttk.Button(footer, text='使用此配置', command=self.use_profile)
        self.use_button.pack(side='right', padx=6)
        active = store.active
        self.load_profile(active['id'] if active else None)
        self.wait_visibility()
        self.grab_set()
        self.tree.focus_set()

    def refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        groups = {}
        active = self.store.active
        for profile in sorted_profiles(self.store):
            group = profile['group'] or '未分组'
            if group not in groups:
                groups[group] = self.tree.insert('', 'end', text=group, open=True)
            self.tree.insert(
                groups[group],
                'end',
                iid='profile-' + profile['id'],
                text=profile['name'] + (' · 当前' if active and active['id'] == profile['id'] else ''),
            )
        if self.editing:
            self.tree.selection_set('profile-' + self.editing)

    def load_profile(self, profile_id):
        self.loading = True
        self.editing = profile_id
        profile = next((p for p in self.store.profiles if p['id'] == profile_id), {})
        for key, variable in self.fields.items():
            variable.set(
                ('Jellyfin' if profile.get(key, 'jellyfin') == 'jellyfin' else 'Emby')
                if key == 'server_type'
                else profile.get(key, '')
            )
        self.key_entry.configure(show='*')
        self.reveal.configure(text='显示')
        self.feedback.configure(text='')
        self.dirty = False
        self.refresh_tree()
        self.loading = False
        self.refresh_buttons()

    def refresh_buttons(self):
        active = self.store.active
        selected = bool(active and active['id'] == self.editing)
        self.use_button.configure(
            text='当前正在使用' if selected else '使用此配置',
            state='normal' if self.editing and not self.dirty and not selected else 'disabled',
        )
        self.revert_button.configure(state='normal' if self.dirty else 'disabled')
        self.delete_button.configure(state='normal' if self.editing else 'disabled')
        self.edit_title.configure(
            text=('编辑配置' if self.editing else '新增服务配置') + (' · 未保存' if self.dirty else '')
        )

    def changed(self, *_args):
        if not self.loading:
            self.dirty = True
            self.refresh_buttons()

    def confirm_discard(self):
        return not self.dirty or messagebox.askyesno(
            '未保存的修改', '当前配置有未保存的修改，是否放弃？', parent=self, default='no'
        )

    def choose(self, _event=None):
        selection = self.tree.selection()
        if self.loading or not selection or not selection[0].startswith('profile-'):
            return
        profile_id = selection[0][8:]
        if profile_id != self.editing:
            if self.confirm_discard():
                self.load_profile(profile_id)
            elif self.editing:
                self.tree.selection_set('profile-' + self.editing)
            else:
                self.tree.selection_remove(*selection)

    def new_profile(self):
        if self.confirm_discard():
            self.load_profile(None)

    def revert(self):
        if self.confirm_discard():
            self.load_profile(self.editing)

    def toggle_key(self):
        show = bool(self.key_entry.cget('show'))
        self.key_entry.configure(show='' if show else '*')
        self.reveal.configure(text='隐藏' if show else '显示')

    def save_profile(self):
        fields = {k: v.get() for k, v in self.fields.items()}
        fields['server_type'] = fields['server_type'].lower()
        try:
            profile_id = self.store.save_profile(fields, self.editing)
        except (ValueError, OSError) as exc:
            self.feedback.configure(text=str(exc))
            return
        self.load_profile(profile_id)
        self.feedback.configure(text='配置已保存')

    def delete_profile(self):
        message = '删除这份服务配置？如果删除当前配置，将使用剩余的第一份配置。'
        if not messagebox.askyesno('删除配置', message, parent=self, default='no'):
            return
        try:
            self.store.delete(self.editing)
        except (ValueError, OSError) as exc:
            self.feedback.configure(text=str(exc))
            return
        self.load_profile(self.store.active['id'])

    def use_profile(self):
        try:
            self.store.select(self.editing)
        except (ValueError, OSError) as exc:
            self.feedback.configure(text=str(exc))
            return
        self.close()

    def close(self):
        if self.confirm_discard():
            self.grab_release()
            self.destroy()

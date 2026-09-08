"""Native service selector and shared profile manager for the macOS frontend."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


def profile_items(profiles):
    return sorted(profiles, key=lambda p: (p['group'], p['name']))


class ProfilePicker(QWidget):
    def __init__(self, store, parent=None):
        super().__init__(parent)
        self.store = store
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        row = QHBoxLayout()
        label = QLabel('当前媒体服务')
        self.combo = QComboBox()
        self.combo.setMinimumContentsLength(20)
        self.combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        label.setBuddy(self.combo)
        row.addWidget(label)
        row.addWidget(self.combo, 1)
        self.status = QLabel()
        row.addWidget(self.status)
        layout.addLayout(row)
        self.details = QLabel()
        self.details.setWordWrap(True)
        self.details.setTextFormat(Qt.PlainText)
        layout.addWidget(self.details)
        self.combo.currentIndexChanged.connect(self.select)
        unsubscribe = store.subscribe(self.refresh)
        self.destroyed.connect(unsubscribe)
        self.refresh()

    def refresh(self):
        self.combo.blockSignals(True)
        self.combo.clear()
        active = self.store.active
        group = None
        for profile in profile_items(self.store.profiles):
            heading = profile['group'] or '未分组'
            if heading != group:
                group = heading
                self.combo.addItem(heading)
                self.combo.model().item(self.combo.count() - 1).setEnabled(False)
            self.combo.addItem('  ' + profile['name'], profile['id'])
        if active:
            self.combo.setCurrentIndex(self.combo.findData(active['id']))
            kind = 'Jellyfin' if active['server_type'] == 'jellyfin' else 'Emby'
            self.details.setText(f"{kind}  ·  {active['server_url']}  ·  用户：{active['username'] or '未填写'}")
        else:
            self.combo.addItem('尚无配置')
            self.details.setText('请点击右上角“服务配置”，添加 Jellyfin 或 Emby 服务。')
        self.combo.setEnabled(bool(active) and not self.store.busy)
        self.status.setText('任务运行中 · 切换已锁定' if self.store.busy else '三个媒体功能共用')
        self.combo.blockSignals(False)

    def select(self, index):
        profile_id = self.combo.itemData(index)
        if profile_id:
            try:
                self.store.select(profile_id)
            except (ValueError, OSError) as exc:
                QMessageBox.warning(self, '切换失败', str(exc))
                self.refresh()


class ProfileManager(QDialog):
    def __init__(self, store, origin, parent=None):
        super().__init__(parent)
        self.store = store
        self.editing = None
        self.dirty = False
        self.loading = False
        self.setWindowTitle('媒体服务配置')
        self.setModal(True)
        self.resize(870, 560)
        self.setMinimumSize(700, 480)
        outer = QVBoxLayout(self)
        columns = QHBoxLayout()
        left = QVBoxLayout()
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setMinimumWidth(225)
        self.tree.setMaximumWidth(310)
        self.tree.currentItemChanged.connect(self.choose)
        left.addWidget(self.tree)
        self.new_button = QPushButton('＋ 新增服务配置')
        self.new_button.clicked.connect(self.new_profile)
        left.addWidget(self.new_button)
        columns.addLayout(left, 1)
        right = QVBoxLayout()
        self.edit_title = QLabel('编辑配置')
        right.addWidget(self.edit_title)
        form = QFormLayout()
        self.fields = {}
        for key, label in (
            ('name', '配置名称'),
            ('group', '所属服务器（可选）'),
            ('server_type', '服务类型'),
            ('server_url', '完整服务地址'),
            ('api_key', 'API Key'),
            ('username', '用户名'),
        ):
            if key == 'server_type':
                field = QComboBox()
                field.addItem('Jellyfin', 'jellyfin')
                field.addItem('Emby', 'emby')
                field.currentIndexChanged.connect(self.changed)
            else:
                field = QLineEdit()
                field.textChanged.connect(self.changed)
            self.fields[key] = field
            if key == 'api_key':
                field.setEchoMode(QLineEdit.Password)
                row = QHBoxLayout()
                row.addWidget(field)
                self.reveal = QPushButton('显示')
                self.reveal.clicked.connect(self.toggle_key)
                row.addWidget(self.reveal)
                form.addRow(label, row)
            else:
                form.addRow(label, field)
        self.fields['server_url'].setPlaceholderText('http://192.168.1.10:8096')
        right.addLayout(form)
        self.feedback = QLabel()
        self.feedback.setTextFormat(Qt.PlainText)
        self.feedback.setWordWrap(True)
        self.feedback.setMinimumHeight(40)
        right.addWidget(self.feedback)
        right.addStretch()
        actions = QHBoxLayout()
        self.delete_button = QPushButton('删除')
        self.delete_button.clicked.connect(self.delete_profile)
        actions.addWidget(self.delete_button)
        actions.addStretch()
        self.revert_button = QPushButton('还原修改')
        self.revert_button.clicked.connect(self.revert)
        actions.addWidget(self.revert_button)
        self.save_button = QPushButton('保存配置')
        self.save_button.clicked.connect(self.save_profile)
        actions.addWidget(self.save_button)
        right.addLayout(actions)
        columns.addLayout(right, 2)
        outer.addLayout(columns)
        footer = QHBoxLayout()
        footer.addWidget(QLabel(f'关闭后返回：{origin}'))
        footer.addStretch()
        self.use_button = QPushButton('使用此配置')
        self.use_button.clicked.connect(self.use_profile)
        footer.addWidget(self.use_button)
        close = QPushButton('关闭')
        close.clicked.connect(self.reject)
        footer.addWidget(close)
        outer.addLayout(footer)
        for button in self.findChildren(QPushButton):
            button.setAutoDefault(False)
        active = store.active
        self.load_profile(active['id'] if active else None)

    def refresh_tree(self):
        self.tree.blockSignals(True)
        self.tree.clear()
        groups = {}
        active = self.store.active
        for profile in profile_items(self.store.profiles):
            group = profile['group'] or '未分组'
            if group not in groups:
                item = QTreeWidgetItem([group])
                item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
                self.tree.addTopLevelItem(item)
                groups[group] = item
            label = profile['name'] + (' · 当前' if active and profile['id'] == active['id'] else '')
            item = QTreeWidgetItem(groups[group], [label])
            item.setData(0, Qt.UserRole, profile['id'])
            item.setToolTip(0, profile['server_url'])
            if profile['id'] == self.editing:
                self.tree.setCurrentItem(item)
        self.tree.expandAll()
        self.tree.blockSignals(False)

    def load_profile(self, profile_id):
        self.loading = True
        self.editing = profile_id
        profile = next((p for p in self.store.profiles if p['id'] == profile_id), {})
        for key, field in self.fields.items():
            if key == 'server_type':
                field.setCurrentIndex(field.findData(profile.get(key, 'jellyfin')))
            else:
                field.setText(profile.get(key, ''))
        self.fields['api_key'].setEchoMode(QLineEdit.Password)
        self.reveal.setText('显示')
        self.feedback.clear()
        self.dirty = False
        self.loading = False
        self.refresh_tree()
        self.refresh_buttons()

    def refresh_buttons(self):
        active = self.store.active
        selected = bool(active and self.editing == active['id'])
        self.use_button.setText('当前正在使用' if selected else '使用此配置')
        self.use_button.setEnabled(bool(self.editing) and not self.dirty and not selected)
        self.revert_button.setEnabled(self.dirty)
        self.delete_button.setEnabled(bool(self.editing))
        self.edit_title.setText(('编辑配置' if self.editing else '新增服务配置') + (' · 未保存' if self.dirty else ''))

    def changed(self):
        if not self.loading:
            self.dirty = True
            self.refresh_buttons()

    def confirm_discard(self):
        return (
            not self.dirty
            or QMessageBox.question(
                self,
                '未保存的修改',
                '当前配置有未保存的修改，是否放弃？',
                QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Cancel,
            )
            == QMessageBox.Discard
        )

    def choose(self, item, previous):
        profile_id = item.data(0, Qt.UserRole) if item else None
        if profile_id and profile_id != self.editing:
            if self.confirm_discard():
                self.load_profile(profile_id)
            else:
                self.refresh_tree()

    def new_profile(self):
        if self.confirm_discard():
            self.load_profile(None)
            self.fields['name'].setFocus()

    def revert(self):
        if self.confirm_discard():
            self.load_profile(self.editing)

    def toggle_key(self):
        field = self.fields['api_key']
        show = field.echoMode() == QLineEdit.Password
        field.setEchoMode(QLineEdit.Normal if show else QLineEdit.Password)
        self.reveal.setText('隐藏' if show else '显示')

    def save_profile(self):
        fields = {
            key: field.currentData() if key == 'server_type' else field.text() for key, field in self.fields.items()
        }
        try:
            profile_id = self.store.save_profile(fields, self.editing)
        except (ValueError, OSError) as exc:
            self.feedback.setText(str(exc))
            return
        self.load_profile(profile_id)
        self.feedback.setText('配置已保存')

    def delete_profile(self):
        active = self.store.active
        message = '删除这份服务配置？'
        if active and active['id'] == self.editing:
            message += '\n删除当前配置后，将使用剩余的第一份配置。'
        if (
            QMessageBox.question(self, '删除配置', message, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            != QMessageBox.Yes
        ):
            return
        try:
            self.store.delete(self.editing)
        except (ValueError, OSError) as exc:
            self.feedback.setText(str(exc))
            return
        self.load_profile(self.store.active['id'])

    def use_profile(self):
        try:
            self.store.select(self.editing)
        except (ValueError, OSError) as exc:
            self.feedback.setText(str(exc))
            return
        self.accept()

    def reject(self):
        if self.confirm_discard():
            super().reject()

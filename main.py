import sys
import os
from pathlib import Path
from datetime import datetime
from PySide6.QtCore import Qt, QTimer, QDir
from PySide6.QtGui import QFont, QTextOption
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel,
    QPushButton, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPlainTextEdit, QTextEdit, QTextBrowser, QScrollArea,
    QSizePolicy, QComboBox, QMessageBox, QFileDialog,
    QTreeView, QFileSystemModel, QSplitter, QTabWidget,
    QDialog, QLineEdit, QDockWidget, QToolBar, QStatusBar
)
from app_setting import AppSettings
from setting_dialog import SettingsDialog
from engine import AIWorker, OllamaClient
from storage import ChatStorage

APP_NAME = "CodePilot"

DARK_STYLE = """
QMainWindow, QWidget {
    background-color: #090f1d;
    color: #e8eefc;
    font-family: "Segoe UI";
    font-size: 10pt;
}
QFrame#Sidebar {
    background-color: rgba(17, 27, 47, 245);
    border-right: 1px solid #293b5b;
}
QFrame#TopBar {
    background-color: rgba(18, 29, 51, 245);
    border-bottom: 1px solid #2b3e60;
}
QFrame#MessageCard {
    background-color: rgba(22, 34, 57, 245);
    border: 1px solid #304565;
    border-radius: 16px;
}
QFrame#UserCard {
    background-color: rgba(24, 48, 78, 248);
    border: 1px solid #426b9e;
    border-radius: 16px;
}
QFrame#ComposerCard, QFrame#GlassPanel {
    background-color: rgba(20, 32, 54, 248);
    border: 1px solid #344b70;
    border-radius: 18px;
}
QPushButton {
    background-color: #192944;
    color: #eaf1ff;
    border: 1px solid #344b6c;
    border-radius: 10px;
    padding: 9px 14px;
}
QPushButton:hover {
    background-color: #243b60;
    border-color: #5a8ac5;
}
QPushButton:pressed { background-color: #315783; }
QPushButton:disabled {
    color: #697992;
    background-color: #141e30;
    border-color: #26344b;
}
QPushButton#PrimaryButton {
    background-color: #3978e8;
    color: white;
    border: 1px solid #6395f0;
    border-radius: 11px;
    font-weight: 700;
    padding: 10px 18px;
}
QPushButton#PrimaryButton:hover { background-color: #4b8bff; }
QPushButton#NewChatButton {
    background-color: #1d3b63;
    border: 1px solid #4774aa;
    font-weight: 700;
}
QLineEdit, QPlainTextEdit, QTextBrowser, QComboBox {
    background-color: rgba(10, 19, 35, 245);
    color: #e8eefc;
    border: 1px solid #304461;
    border-radius: 10px;
    padding: 9px;
    selection-background-color: #356fd0;
}
QPlainTextEdit:focus, QLineEdit:focus, QComboBox:focus {
    border: 1px solid #6299ed;
}
QComboBox QAbstractItemView {
    background-color: #172640;
    color: #edf3ff;
    border: 1px solid #3b5275;
    selection-background-color: #315f9e;
}
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical {
    background: #0d1728;
    width: 10px;
    margin: 3px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background: #344b6d;
    min-height: 28px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover { background: #5277a7; }
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar:horizontal {
    background: #0d1728;
    height: 10px;
    margin: 3px;
    border-radius: 5px;
}
QScrollBar::handle:horizontal {
    background: #344b6d;
    min-width: 28px;
    border-radius: 5px;
}
QTreeView {
    background-color: rgba(14, 24, 42, 245);
    border: 1px solid #273b59;
    border-radius: 10px;
    alternate-background-color: #172640;
    color: #e8eefc;
}
QTreeView::item { padding: 6px; }
QTreeView::item:selected {
    background-color: #254b7b;
    border-radius: 5px;
}
QTabWidget::pane {
    border: 1px solid #2c4263;
    background-color: #101b30;
    border-radius: 8px;
}
QTabBar::tab {
    background-color: #172640;
    padding: 9px 16px;
    border: 1px solid #2d4262;
}
QTabBar::tab:selected {
    background-color: #2d5da0;
    color: white;
}
QStatusBar {
    background-color: #101a2d;
    color: #9eacc3;
    border-top: 1px solid #293c5a;
}
QSplitter::handle { background-color: #2a3d5b; }
QLabel { background: transparent; }
"""


class MessageInput(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText(
            "Ask CodePilot anything... "
            "(Enter to send, Shift+Enter for new line)"
        )
        self.setFixedHeight(105)
        self.setFont(QFont("Segoe UI", 10))

    def keyPressEvent(self, event):
        if (
            event.key() in (Qt.Key_Return, Qt.Key_Enter)
            and not event.modifiers() & Qt.ShiftModifier
        ):
            window = self.window()
            if hasattr(window, "send_message"):
                window.send_message()
            return
        super().keyPressEvent(event)


class AutoResizeTextBrowser(QTextBrowser):
    """Read-only Markdown view that grows to show its full content."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setOpenExternalLinks(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setLineWrapMode(QTextEdit.WidgetWidth)

        option = self.document().defaultTextOption()
        option.setWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.document().setDefaultTextOption(option)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(48)
        self.document().setDocumentMargin(8)

    def set_content(self, markdown):
        self.setMarkdown(markdown or "")
        self.adjust_content_height()
        QTimer.singleShot(0, self.adjust_content_height)

    def adjust_content_height(self):
        width = max(160, self.viewport().width())
        self.document().setTextWidth(width)
        content_height = int(self.document().size().height()) + 34
        self.setFixedHeight(max(58, content_height))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self.adjust_content_height)


class CodePilotWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CodePilot - Offline AI Coding Assistant")
        self.resize(1450, 900)
        self.setMinimumSize(1050, 650)

        self.app_settings = AppSettings()
        self.settings_data = self.app_settings.all()
        self.storage = ChatStorage()

        self.ai_client = OllamaClient(
            base_url=self.settings_data.get(
                "ollama_url", "http://127.0.0.1:11434"
            ),
            model=self.settings_data.get("model_name", "qwen3:8b"),
            context_size=self.settings_data.get("context_size", 4096),
            keep_alive=self.settings_data.get("keep_alive", "30m"),
            temperature=self.settings_data.get("temperature", 0.4),
            max_tokens=self.settings_data.get("max_tokens", 2048)
        )

        self.current_conversation_id = None
        self.conversation_messages = []
        self.ai_worker = None
        self.current_response = ""
        self.current_response_browser = None

        self.response_render_timer = QTimer(self)
        self.response_render_timer.setSingleShot(True)
        self.response_render_timer.setInterval(120)
        self.response_render_timer.timeout.connect(
            self.render_streamed_response
        )

        self.project_path = None
        self.open_editors = {}

        self.build_ui()
        self.apply_appearance()
        self.load_chat_history()

        if not self.settings_data.get("new_chat_on_startup", False):
            self.load_latest_chat()

        if not self.current_conversation_id:
            self.create_new_chat()

        self.statusBar().showMessage("CodePilot ready")

    def build_ui(self):
        central = QWidget()
        central.setObjectName("CentralWidget")
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.sidebar = self.create_sidebar()
        main_layout.addWidget(self.sidebar)

        right_area = QWidget()
        right_layout = QVBoxLayout(right_area)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self.topbar = self.create_topbar()
        right_layout.addWidget(self.topbar)

        self.content_splitter = QSplitter(Qt.Horizontal)
        self.chat_area = self.create_chat_area()
        self.content_splitter.addWidget(self.chat_area)

        self.editor_tabs = QTabWidget()
        self.editor_tabs.setTabsClosable(True)
        self.editor_tabs.tabCloseRequested.connect(
            self.close_editor_tab
        )
        self.editor_tabs.hide()

        self.content_splitter.addWidget(self.editor_tabs)
        self.content_splitter.setStretchFactor(0, 3)
        self.content_splitter.setStretchFactor(1, 2)

        right_layout.addWidget(self.content_splitter)
        main_layout.addWidget(right_area, 1)

        self.create_project_dock()

    def create_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(265)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(15, 18, 15, 15)
        layout.setSpacing(12)

        logo = QLabel("◉     CODEPILOT")
        logo.setFont(QFont("Segoe UI", 17, QFont.Bold))
        logo.setStyleSheet(
            "color: #78b4ff; font-size: 19px; font-weight: 800; "
            "padding: 5px 0; letter-spacing: 1px;"
        )
        layout.addWidget(logo)

        subtitle = QLabel("OFFLINE AI CODING ASSISTANT")
        subtitle.setStyleSheet(
            "color: #8293ae; font-size: 8pt; letter-spacing: 1px;"
        )
        layout.addWidget(subtitle)

        self.new_chat_button = QPushButton("+     New Chat")
        self.new_chat_button.setObjectName("NewChatButton")
        self.new_chat_button.clicked.connect(self.create_new_chat)
        layout.addWidget(self.new_chat_button)

        self.open_project_button = QPushButton("📁     Open Project")
        self.open_project_button.clicked.connect(self.open_project)
        layout.addWidget(self.open_project_button)

        self.open_file_button = QPushButton("📄     Open File")
        self.open_file_button.clicked.connect(self.open_file)
        layout.addWidget(self.open_file_button)

        history_label = QLabel("RECENT CHATS")
        history_label.setStyleSheet(
            "color: #8293ae; font-weight: bold; margin-top: 15px;"
        )
        layout.addWidget(history_label)

        self.history_scroll = QScrollArea()
        self.history_scroll.setWidgetResizable(True)

        self.history_container = QWidget()
        self.history_layout = QVBoxLayout(self.history_container)
        self.history_layout.setContentsMargins(0, 0, 0, 0)
        self.history_layout.setSpacing(5)
        self.history_layout.addStretch()

        self.history_scroll.setWidget(self.history_container)
        layout.addWidget(self.history_scroll, 1)

        self.settings_button = QPushButton("⚙     Settings")
        self.settings_button.clicked.connect(self.show_settings)
        layout.addWidget(self.settings_button)

        self.connection_label = QLabel("● Local AI")
        self.connection_label.setStyleSheet(
            "color: #55cf91; padding: 5px;"
        )
        layout.addWidget(self.connection_label)
        return sidebar

    def create_topbar(self):
        topbar = QFrame()
        topbar.setObjectName("TopBar")
        topbar.setFixedHeight(65)
        topbar.setStyleSheet(
            "QFrame#TopBar { background: qlineargradient("
            "x1:0, y1:0, x2:1, y2:0, "
            "stop:0 #172c4d, stop:0.55 #1b3153, "
            "stop:1 #142139); border-bottom: 1px solid #45658e; }"
        )

        layout = QHBoxLayout(topbar)
        layout.setContentsMargins(18, 8, 18, 8)

        self.page_title = QLabel("New Chat")
        self.page_title.setFont(QFont("Segoe UI", 13, QFont.Bold))
        layout.addWidget(self.page_title)
        layout.addStretch()

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Fast", "Balanced", "Detailed"])

        current_mode = self.settings_data.get(
            "response_mode", "Balanced"
        )
        index = self.mode_combo.findText(current_mode)
        if index >= 0:
            self.mode_combo.setCurrentIndex(index)

        self.mode_combo.currentTextChanged.connect(
            self.change_response_mode
        )
        layout.addWidget(QLabel("Response:"))
        layout.addWidget(self.mode_combo)
        return topbar

    def create_chat_area(self):
        container = QWidget()
        container.setMinimumWidth(0)
        container.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )

        layout = QVBoxLayout(container)
        layout.setContentsMargins(22, 18, 22, 15)
        layout.setSpacing(12)

        self.welcome_label = QLabel(
            "What can I help you build today?"
        )
        self.welcome_label.setAlignment(Qt.AlignCenter)
        self.welcome_label.setFont(
            QFont("Segoe UI", 19, QFont.Bold)
        )
        self.welcome_label.setStyleSheet(
            "color: #e8edf7; padding: 25px;"
        )
        layout.addWidget(self.welcome_label)

        self.chat_scroll = QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )

        self.chat_container = QWidget()
        self.chat_container.setMinimumWidth(0)
        self.chat_container.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Preferred
        )

        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setContentsMargins(8, 8, 8, 8)
        self.chat_layout.setSpacing(15)
        self.chat_layout.addStretch()

        self.chat_scroll.setWidget(self.chat_container)
        layout.addWidget(self.chat_scroll, 1)

        input_frame = QFrame()
        input_frame.setObjectName("ComposerCard")

        input_layout = QVBoxLayout(input_frame)
        input_layout.setContentsMargins(12, 12, 12, 12)

        self.message_input = MessageInput()
        input_layout.addWidget(self.message_input)

        bottom_layout = QHBoxLayout()
        hint = QLabel(
            "Offline AI • Your code stays on your computer"
        )
        hint.setStyleSheet("color: #8293ae;")
        bottom_layout.addWidget(hint)
        bottom_layout.addStretch()

        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_generation)
        bottom_layout.addWidget(self.stop_button)

        self.send_button = QPushButton("Send     ➤")
        self.send_button.setObjectName("PrimaryButton")
        self.send_button.clicked.connect(self.send_message)
        bottom_layout.addWidget(self.send_button)

        input_layout.addLayout(bottom_layout)
        layout.addWidget(input_frame)
        return container
    def create_project_dock(self):
        self.project_dock = QDockWidget("Project Explorer", self)
        self.project_dock.setAllowedAreas(
            Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea
        )

        self.file_model = QFileSystemModel()
        self.file_model.setRootPath("")

        self.file_tree = QTreeView()
        self.file_tree.setModel(self.file_model)
        self.file_tree.setRootIsDecorated(True)
        self.file_tree.setAnimated(True)
        self.file_tree.setSortingEnabled(True)

        for column in range(1, 4):
            self.file_tree.hideColumn(column)

        self.file_tree.doubleClicked.connect(
            self.open_project_file
        )

        self.project_dock.setWidget(self.file_tree)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.project_dock)
        self.project_dock.hide()

    def open_project(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Project Folder"
        )
        if not folder:
            return

        self.project_path = Path(folder)
        index = self.file_model.setRootPath(folder)
        self.file_tree.setRootIndex(index)
        self.project_dock.show()
        self.statusBar().showMessage(
            f"Project opened: {folder}"
        )

    def open_project_file(self, index):
        path = Path(self.file_model.filePath(index))
        if path.is_file():
            self.load_file_into_editor(path)

    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open File", "", "All Files (*.*)"
        )
        if file_path:
            self.load_file_into_editor(Path(file_path))

    def load_file_into_editor(self, path):
        path = Path(path)
        if not path.is_file():
            return

        key = str(path.resolve())
        if key in self.open_editors:
            self.editor_tabs.setCurrentWidget(
                self.open_editors[key]
            )
            return

        try:
            content = path.read_text(
                encoding="utf-8",
                errors="replace"
            )
        except OSError as error:
            QMessageBox.warning(
                self, "File Error", str(error)
            )
            return

        editor = QPlainTextEdit()
        editor.setPlainText(content)
        editor.setFont(QFont("Consolas", 11))
        editor.setTabStopDistance(32)
        editor.setProperty("file_path", key)
        editor.document().setModified(False)

        editor.document().modificationChanged.connect(
            lambda modified, e=editor, p=path:
            self.update_editor_title(e, p, modified)
        )

        self.open_editors[key] = editor
        self.editor_tabs.addTab(editor, path.name)
        self.editor_tabs.setCurrentWidget(editor)
        self.editor_tabs.show()

    def update_editor_title(self, editor, path, modified):
        index = self.editor_tabs.indexOf(editor)
        if index < 0:
            return

        title = path.name
        if modified:
            title += " *"

        self.editor_tabs.setTabText(index, title)

    def save_current_file(self):
        editor = self.editor_tabs.currentWidget()
        if editor is None:
            return

        path_value = editor.property("file_path")
        if not path_value:
            return

        path = Path(path_value)
        if not editor.document().isModified():
            return

        reply = QMessageBox.question(
            self,
            "Confirm Save",
            f"Save changes to {path.name}?",
            QMessageBox.Save | QMessageBox.Cancel
        )
        if reply != QMessageBox.Save:
            return

        try:
            path.write_text(
                editor.toPlainText(),
                encoding="utf-8"
            )
            editor.document().setModified(False)
            self.statusBar().showMessage(
                f"Saved: {path.name}"
            )
        except OSError as error:
            QMessageBox.critical(
                self, "Save Error", str(error)
            )

    def close_editor_tab(self, index):
        editor = self.editor_tabs.widget(index)
        if editor is None:
            return

        if editor.document().isModified():
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "Save changes before closing?",
                QMessageBox.Save |
                QMessageBox.Discard |
                QMessageBox.Cancel
            )

            if reply == QMessageBox.Cancel:
                return

            if reply == QMessageBox.Save:
                self.editor_tabs.setCurrentIndex(index)
                self.save_current_file()
                if editor.document().isModified():
                    return

        path = editor.property("file_path")
        if path:
            self.open_editors.pop(path, None)

        self.editor_tabs.removeTab(index)
        editor.deleteLater()

        if self.editor_tabs.count() == 0:
            self.editor_tabs.hide()

    def load_chat_history(self):
        while self.history_layout.count() > 1:
            item = self.history_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        conversations = self.storage.get_conversations()

        for conversation in conversations:
            conversation_id = conversation["id"]
            title = conversation["title"]

            button = QPushButton("💬     " + title)
            button.setToolTip(title)
            button.setSizePolicy(
                QSizePolicy.Expanding,
                QSizePolicy.Fixed
            )

            button.clicked.connect(
                lambda checked=False, cid=conversation_id:
                self.load_conversation(cid)
            )

            button.setContextMenuPolicy(
                Qt.CustomContextMenu
            )
            button.customContextMenuRequested.connect(
                lambda pos, cid=conversation_id:
                self.delete_chat_menu(cid)
            )

            self.history_layout.insertWidget(
                self.history_layout.count() - 1,
                button
            )

    def load_latest_chat(self):
        conversations = self.storage.get_conversations(
            limit=1
        )
        if conversations:
            self.load_conversation(
                conversations[0]["id"]
            )

    def load_conversation(self, conversation_id):
        self.current_conversation_id = conversation_id
        messages = self.storage.get_messages(
            conversation_id
        )
        self.conversation_messages = []
        self.clear_chat_display()

        for message in messages:
            role = message["role"]
            content = message["content"]

            if role in ("user", "assistant"):
                self.add_message_card(
                    role,
                    content,
                    message.get("created_at")
                )
                self.conversation_messages.append({
                    "role": role,
                    "content": content
                })

        conversations = self.storage.get_conversations()
        for conversation in conversations:
            if conversation["id"] == conversation_id:
                self.page_title.setText(
                    conversation["title"]
                )
                break

        self.welcome_label.hide()
        self.scroll_to_bottom()

    def create_new_chat(self):
        if self.is_worker_running():
            QMessageBox.information(
                self,
                "AI Working",
                "Wait for the current response to finish."
            )
            return

        self.current_conversation_id = (
            self.storage.create_conversation()
        )
        self.conversation_messages = []
        self.clear_chat_display()
        self.page_title.setText("New Chat")
        self.welcome_label.show()
        self.load_chat_history()
        self.message_input.setFocus()

    def delete_chat_menu(self, conversation_id):
        message = QMessageBox.question(
            self,
            "Delete Conversation",
            "Do you want to delete this conversation?",
            QMessageBox.Yes | QMessageBox.No
        )
        if message != QMessageBox.Yes:
            return

        self.storage.delete_conversation(conversation_id)

        if self.current_conversation_id == conversation_id:
            self.current_conversation_id = None
            self.conversation_messages = []
            self.clear_chat_display()
            self.create_new_chat()

        self.load_chat_history()

    def clear_chat_display(self):
        while self.chat_layout.count() > 1:
            item = self.chat_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        self.current_response_browser = None

    def add_message_card(self, role, content, timestamp=None):
        """Create a readable, aligned glass-style chat message."""
        row = QWidget(self.chat_container)
        row.setMinimumWidth(0)
        row.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed
        )

        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(8, 3, 8, 3)
        row_layout.setSpacing(0)

        card = QFrame(row)
        card.setObjectName(
            "UserCard" if role == "user" else "MessageCard"
        )
        card.setMinimumWidth(0)
        card.setMaximumWidth(
            900 if role == "user" else 16777215
        )
        card.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed
        )

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(17, 13, 17, 13)
        card_layout.setSpacing(8)

        heading_row = QHBoxLayout()
        title = QLabel(
            "YOU" if role == "user" else "CODEPILOT"
        )
        title.setStyleSheet(
            "color: #83b7ff; font-size: 9pt; font-weight: 700;"
        )
        heading_row.addWidget(title)
        heading_row.addStretch(1)

        if timestamp and self.settings_data.get(
            "show_timestamps", True
        ):
            time_label = QLabel(str(timestamp))
            time_label.setStyleSheet(
                "color: #8192ad; font-size: 8pt;"
            )
            heading_row.addWidget(time_label)

        card_layout.addLayout(heading_row)

        browser = AutoResizeTextBrowser(card)
        browser.setStyleSheet(
            "QTextBrowser { background: transparent; border: none; "
            "padding: 0px; color: #e8eefc; }"
        )
        browser.set_content(content or "")
        card_layout.addWidget(browser)

        if role == "user":
            row_layout.addStretch(1)
            row_layout.addWidget(card, 0)
        else:
            # AI response card expands to the complete available chat width.
            row_layout.addWidget(card, 1)

        self.chat_layout.insertWidget(
            max(0, self.chat_layout.count() - 1),
            row
        )
        self.scroll_to_bottom()
        return browser
    def scroll_to_bottom(self):
        QTimer.singleShot(
            50,
            lambda: self.chat_scroll.verticalScrollBar().setValue(
                self.chat_scroll.verticalScrollBar().maximum()
            )
        )

    def send_message(self):
        if self.is_worker_running():
            return

        prompt = self.message_input.toPlainText().strip()
        if not prompt:
            return

        self.welcome_label.hide()

        if not self.current_conversation_id:
            self.current_conversation_id = (
                self.storage.create_conversation()
            )

        self.message_input.clear()
        self.add_message_card("user", prompt)

        self.conversation_messages.append({
            "role": "user",
            "content": prompt
        })

        self.storage.add_message(
            self.current_conversation_id,
            "user",
            prompt
        )

        self.load_chat_history()
        self.current_response = ""

        self.current_response_browser = self.add_message_card(
            "assistant", "Thinking..."
        )

        self.send_button.setEnabled(False)
        self.stop_button.setEnabled(True)

        self.statusBar().showMessage(
            "CodePilot is generating a response..."
        )

        self.ai_worker = AIWorker(
            self.conversation_messages.copy(),
            mode=self.mode_combo.currentText(),
            config=self.app_settings.all(),
            parent=self
        )

        self.ai_worker.token_received.connect(
            self.receive_token
        )
        self.ai_worker.response_ready.connect(
            self.response_finished
        )
        self.ai_worker.error_occurred.connect(
            self.response_error
        )
        self.ai_worker.finished.connect(
            self.worker_finished
        )
        self.ai_worker.start()

    def receive_token(self, token):
        self.current_response += token

        # Batch Markdown rendering to keep the UI responsive.
        if (
            self.current_response_browser
            and not self.response_render_timer.isActive()
        ):
            self.response_render_timer.start()

    def render_streamed_response(self):
        browser = self.current_response_browser
        if not browser:
            return

        browser.set_content(self.current_response)
        self.scroll_to_bottom()

    def response_finished(self, response):
        self.current_response = response

        if self.response_render_timer.isActive():
            self.response_render_timer.stop()

        if self.current_response_browser:
            self.current_response_browser.set_content(response)
            self.scroll_to_bottom()

        self.conversation_messages.append({
            "role": "assistant",
            "content": response
        })

        self.storage.add_message(
            self.current_conversation_id,
            "assistant",
            response
        )

        self.load_chat_history()
        self.statusBar().showMessage("Response completed")

    def response_error(self, error):
        if self.current_response_browser:
            if self.current_response:
                content = (
                    self.current_response
                    + "\n\n**Error:** "
                    + str(error)
                )
            else:
                content = (
                    "**AI Connection Error**\n\n"
                    + str(error)
                    + "\n\nCheck that Ollama is running "
                    "and the configured model is installed."
                )

            self.current_response_browser.set_content(content)
            self.scroll_to_bottom()

        self.statusBar().showMessage("AI request failed")

    def worker_finished(self):
        self.send_button.setEnabled(True)
        self.stop_button.setEnabled(False)

        if self.ai_worker:
            self.ai_worker.deleteLater()
            self.ai_worker = None

        self.message_input.setFocus()

    def stop_generation(self):
        if self.ai_worker and self.ai_worker.isRunning():
            self.ai_worker.requestInterruption()
            self.statusBar().showMessage(
                "Stop requested. Waiting for AI worker..."
            )

    def is_worker_running(self):
        return (
            self.ai_worker is not None
            and self.ai_worker.isRunning()
        )

    def change_response_mode(self, mode):
        self.app_settings.set("response_mode", mode)
        self.settings_data = self.app_settings.all()

    def show_settings(self):
        if self.is_worker_running():
            QMessageBox.information(
                self,
                "AI Working",
                "Please wait until the current response finishes."
            )
            return

        dialog = SettingsDialog(self.app_settings, self)

        if dialog.exec() == QDialog.Accepted:
            self.settings_data = self.app_settings.all()

            self.ai_client.update_config(
                base_url=self.settings_data.get(
                    "ollama_url",
                    "http://127.0.0.1:11434"
                ),
                model=self.settings_data.get(
                    "model_name",
                    "qwen3:8b"
                ),
                context_size=self.settings_data.get(
                    "context_size",
                    4096
                ),
                keep_alive=self.settings_data.get(
                    "keep_alive",
                    "30m"
                ),
                temperature=self.settings_data.get(
                    "temperature",
                    0.4
                ),
                max_tokens=self.settings_data.get(
                    "max_tokens",
                    2048
                )
            )

            self.mode_combo.blockSignals(True)
            self.mode_combo.setCurrentText(
                self.settings_data.get(
                    "response_mode",
                    "Balanced"
                )
            )
            self.mode_combo.blockSignals(False)

            self.apply_appearance()
            self.statusBar().showMessage("Settings updated")

    def apply_appearance(self):
        theme = self.settings_data.get("theme", "Dark")
        font_size = self.settings_data.get("font_size", 10)

        self.setStyleSheet(DARK_STYLE)

        font = QFont("Segoe UI", int(font_size))
        QApplication.instance().setFont(font)

        if self.settings_data.get("compact_mode", False):
            self.sidebar.layout().setSpacing(7)
        else:
            self.sidebar.layout().setSpacing(12)

    def closeEvent(self, event):
        if self.is_worker_running():
            QMessageBox.warning(
                self,
                "AI Working",
                "Wait for the current AI response to finish "
                "before closing CodePilot."
            )
            event.ignore()
            return

        if self.settings_data.get(
            "confirm_before_closing", True
        ):
            reply = QMessageBox.question(
                self,
                "Exit CodePilot",
                "Are you sure you want to exit CodePilot?",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply != QMessageBox.Yes:
                event.ignore()
                return

        for editor in self.open_editors.values():
            if editor.document().isModified():
                reply = QMessageBox.question(
                    self,
                    "Unsaved Files",
                    "Some files have unsaved changes. "
                    "Exit without saving?",
                    QMessageBox.Yes | QMessageBox.No
                )

                if reply != QMessageBox.Yes:
                    event.ignore()
                    return
                break

        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)

    window = CodePilotWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
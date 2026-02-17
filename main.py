import sys
import os
import re
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QTextEdit, QFileDialog, 
                             QTreeWidget, QTreeWidgetItem, QMessageBox, QLabel, 
                             QSplitter, QTreeWidgetItemIterator)
from PyQt6.QtCore import Qt

class ClaudeInterfaceApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Claude Linux Interface")
        self.resize(1000, 800)
        
        self.system_prompt = (
            "Code changes should be formatted like so:\n"
            "Updated path: /home/example/path.py\n"
            "Replace:\n"
            "<original exact code block here>\n"
            "With:\n"
            "<new code block that replaces original>\n\n"
            "File deletions should be formatted like:\n"
            "Delete: /home/example/path.py\n\n"
            "New files like:\n"
            "New: /home/example/path.py\n"
            "Content:\n"
            "<new file code block here>\n\n"
            "Make sure all indentation and formatting is correct within old and new code blocks."
        )

        self.setup_ui()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        splitter = QSplitter(Qt.Orientation.Vertical)
        main_layout.addWidget(splitter)

        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        
        btn_layout = QHBoxLayout()
        self.btn_add_dir = QPushButton("Add Directory")
        self.btn_add_dir.clicked.connect(self.add_directory)
        btn_layout.addWidget(self.btn_add_dir)
        btn_layout.addStretch()
        top_layout.addLayout(btn_layout)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Files")
        self.tree.itemChanged.connect(self.handle_item_changed)
        top_layout.addWidget(self.tree)
        
        splitter.addWidget(top_widget)

        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        
        bottom_layout.addWidget(QLabel("Additional Context:"))
        self.text_context = QTextEdit()
        bottom_layout.addWidget(self.text_context)

        action_layout = QHBoxLayout()
        
        self.btn_copy_context = QPushButton("Copy Context & Files")
        self.btn_copy_context.clicked.connect(self.copy_context_to_clipboard)
        action_layout.addWidget(self.btn_copy_context)

        self.btn_copy_sys = QPushButton("Copy System Prompt")
        self.btn_copy_sys.clicked.connect(self.copy_system_prompt)
        action_layout.addWidget(self.btn_copy_sys)

        self.btn_paste_apply = QPushButton("Paste Response & Apply")
        self.btn_paste_apply.clicked.connect(self.paste_and_apply)
        action_layout.addWidget(self.btn_paste_apply)

        bottom_layout.addLayout(action_layout)
        splitter.addWidget(bottom_widget)

    def add_directory(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Directory")
        if dir_path:
            root_item = QTreeWidgetItem(self.tree)
            root_item.setText(0, dir_path)
            root_item.setFlags(root_item.flags() | Qt.ItemFlag.ItemIsAutoTristate | Qt.ItemFlag.ItemIsUserCheckable)
            root_item.setCheckState(0, Qt.CheckState.Unchecked)
            root_item.setData(0, Qt.ItemDataRole.UserRole, dir_path)
            
            self.populate_tree(dir_path, root_item)
            root_item.setExpanded(True)

    def populate_tree(self, path, parent_item):
        try:
            for entry in sorted(os.scandir(path), key=lambda e: (not e.is_dir(), e.name.lower())):
                item = QTreeWidgetItem(parent_item)
                item.setText(0, entry.name)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                
                if entry.is_dir():
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsAutoTristate)
                    item.setCheckState(0, Qt.CheckState.Unchecked)
                    item.setData(0, Qt.ItemDataRole.UserRole, entry.path)
                    self.populate_tree(entry.path, item)
                else:
                    item.setCheckState(0, Qt.CheckState.Unchecked)
                    item.setData(0, Qt.ItemDataRole.UserRole, entry.path)
        except PermissionError:
            pass

    def handle_item_changed(self, item, column):
        pass

    def get_checked_files(self):
        checked_files = []
        iterator = QTreeWidgetItemIterator(self.tree, QTreeWidgetItemIterator.IteratorFlag.Checked)
        while iterator.value():
            item = iterator.value()
            path = item.data(0, Qt.ItemDataRole.UserRole)
            if path and os.path.isfile(path):
                root_path = self.get_root_path(item)
                if root_path:
                    rel_path = os.path.relpath(path, root_path)
                    checked_files.append((path, rel_path))
            iterator += 1
        return checked_files

    def get_root_path(self, item):
        curr = item
        while curr.parent():
            curr = curr.parent()
        return curr.data(0, Qt.ItemDataRole.UserRole)

    def copy_context_to_clipboard(self):
        files = self.get_checked_files()
        output = []
        
        user_context = self.text_context.toPlainText().strip()
        if user_context:
            output.append(f"Context:\n{user_context}\n")

        output.append("Files:")
        for abs_path, rel_path in files:
            try:
                with open(abs_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                # Changed from rel_path to abs_path
                output.append(f"File: {abs_path}\n```\n{content}\n```\n")
            except Exception as e:
                output.append(f"File: {abs_path} (Error reading file: {e})\n")

        full_text = "\n".join(output)
        QApplication.clipboard().setText(full_text)
        self.status_message("Context copied to clipboard!")

    def copy_system_prompt(self):
        QApplication.clipboard().setText(self.system_prompt)
        self.status_message("System prompt copied to clipboard!")

    def paste_and_apply(self):
        response = QApplication.clipboard().text()
        if not response:
            self.show_error("Clipboard is empty.")
            return

        changes_log = []
        
        mod_pattern = re.compile(
            r'Updated path:\s*(?P<path>[^\n]+)\s*\n'
            r'Replace:\s*\n```(?:\w+)?\n(?P<search>.*?)```\s*\n'
            r'With:\s*\n```(?:\w+)?\n(?P<replace>.*?)```',
            re.DOTALL
        )

        new_file_pattern = re.compile(
            r'New:\s*(?P<path>[^\n]+)\s*\n'
            r'Content:\s*\n```(?:\w+)?\n(?P<content>.*?)```',
            re.DOTALL
        )

        del_pattern = re.compile(r'Delete:\s*(?P<path>[^\n]+)', re.MULTILINE)

        # 1. Handle New Files
        for match in new_file_pattern.finditer(response):
            path = match.group('path').strip()
            content = match.group('content')
            if self.create_file(path, content):
                changes_log.append(f"Created: {path}")
            else:
                changes_log.append(f"Failed to create: {path}")

        # 2. Handle Deletions
        for match in del_pattern.finditer(response):
            path = match.group('path').strip()
            if self.delete_file(path):
                changes_log.append(f"Deleted: {path}")
            else:
                changes_log.append(f"Failed to delete: {path}")

        # 3. Handle Modifications
        for match in mod_pattern.finditer(response):
            path = match.group('path').strip()
            search_block = match.group('search')
            replace_block = match.group('replace')
            
            if self.modify_file(path, search_block, replace_block):
                changes_log.append(f"Modified: {path}")
            else:
                changes_log.append(f"Failed to modify: {path}")

        if not changes_log:
            QMessageBox.information(self, "Result", "No valid patterns found in clipboard content.")
        else:
            QMessageBox.information(self, "Result", "\n".join(changes_log))

    def resolve_abs_path(self, path):
        # Normalize
        path = path.strip().replace('\\', '/')
        
        # 1. Check if it's already an absolute path that exists
        if os.path.isabs(path) and os.path.exists(path):
            return path
            
        # 2. Check if it matches relative to any root
        root_count = self.tree.topLevelItemCount()
        for i in range(root_count):
            root_item = self.tree.topLevelItem(i)
            root_path = root_item.data(0, Qt.ItemDataRole.UserRole)
            
            potential_path = os.path.join(root_path, path)
            if os.path.exists(potential_path):
                return potential_path
            
            # 3. If the input was absolute but didn't exist (maybe new file), 
            # check if it starts with this root path
            if path.startswith(root_path):
                return path

        # 4. Fallback for creation of NEW files
        if root_count > 0:
            # If it's absolute, trust it
            if os.path.isabs(path):
                return path
            # Otherwise default to first root
            first_root = self.tree.topLevelItem(0).data(0, Qt.ItemDataRole.UserRole)
            return os.path.join(first_root, path)
        
        return None

    def create_file(self, rel_path, content):
        abs_path = self.resolve_abs_path(rel_path)
        if not abs_path: 
            return False
        try:
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            with open(abs_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except Exception as e:
            print(f"Error creating {abs_path}: {e}")
            return False

    def delete_file(self, rel_path):
        abs_path = self.resolve_abs_path(rel_path)
        if not abs_path or not os.path.exists(abs_path):
            return False
        try:
            os.remove(abs_path)
            return True
        except Exception:
            return False

    def modify_file(self, rel_path, search_txt, replace_txt):
        abs_path = self.resolve_abs_path(rel_path)
        if not abs_path or not os.path.exists(abs_path):
            print(f"File not found: {abs_path}")
            return False
        
        try:
            with open(abs_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if search_txt in content:
                new_content = content.replace(search_txt, replace_txt)
                with open(abs_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                return True
            else:
                norm_content = content.replace('\r\n', '\n')
                norm_search = search_txt.replace('\r\n', '\n')
                norm_search_stripped = norm_search.strip()
                
                if norm_search in norm_content:
                    new_content = norm_content.replace(norm_search, replace_txt)
                    with open(abs_path, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    return True
                
                if norm_search_stripped in norm_content:
                     new_content = norm_content.replace(norm_search_stripped, replace_txt)
                     with open(abs_path, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                     return True

                print(f"Search block not found in {rel_path}")
                return False
        except Exception as e:
            print(f"Error modifying {abs_path}: {e}")
            return False

    def status_message(self, msg):
        self.statusBar().showMessage(msg, 3000)

    def show_error(self, msg):
        QMessageBox.critical(self, "Error", msg)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ClaudeInterfaceApp()
    window.show()
    sys.exit(app.exec())
import sys
import os
import re
import json
import fnmatch
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QTextEdit, QFileDialog, 
                             QTreeWidget, QTreeWidgetItem, QMessageBox, QLabel, 
                             QSplitter, QTreeWidgetItemIterator, QComboBox, 
                             QInputDialog, QFileIconProvider, QStyleFactory, 
                             QStyle, QCheckBox)
from PyQt6.QtCore import Qt, QFileInfo, QSize, QTimer
from PyQt6.QtGui import QIcon, QAction

CONFIG_FILE = "projects.json"

class ClaudeInterfaceApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Claude Linux Interface")
        self.resize(1200, 850)
        
        self.projects_data = {}
        self.current_project_name = "Default"
        self.is_dark_mode = False
        self.icon_provider = QFileIconProvider()
        self.file_trees = [] # Keep track of tree widgets
        
        # Auto-refresh timer
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_file_trees)
        self.refresh_timer.start(10000) # 10 seconds

        self.system_prompt = (
            "Code changes should be formatted like so:\n"
            "Updated path: /home/example/path.py\n"
            "Replace:\n"
            "<original exact code block here>\n"
            "With:\n"
            "<new code block that replaces original>\n"
            "File deletions should be formatted like:\n"
            "Delete: /home/example/path.py\n\n"
            "New files like:\n"
            "New: /home/example/path.py\n"
            "Content:\n"
            "<new file code block here>\n\n"
            "Make sure all indentation and formatting is correct within old and new code blocks."
        )

        self.setup_ui()
        self.load_projects()
        self.apply_theme()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # --- Top Bar: Project Management & Theme ---
        top_bar = QHBoxLayout()
        
        self.project_combo = QComboBox()
        self.project_combo.setMinimumWidth(200)
        self.project_combo.currentIndexChanged.connect(self.change_project)
        top_bar.addWidget(QLabel("Project:"))
        top_bar.addWidget(self.project_combo)

        btn_new_proj = QPushButton("New")
        btn_new_proj.clicked.connect(self.new_project)
        top_bar.addWidget(btn_new_proj)

        btn_del_proj = QPushButton("Delete")
        btn_del_proj.clicked.connect(self.delete_project)
        top_bar.addWidget(btn_del_proj)
        
        btn_save_proj = QPushButton("Save State")
        btn_save_proj.clicked.connect(self.save_current_project_state)
        top_bar.addWidget(btn_save_proj)

        top_bar.addStretch()

        self.btn_theme = QPushButton("Toggle Theme")
        self.btn_theme.clicked.connect(self.toggle_theme)
        top_bar.addWidget(self.btn_theme)

        main_layout.addLayout(top_bar)

        splitter = QSplitter(Qt.Orientation.Vertical)
        main_layout.addWidget(splitter)

        # --- File Section ---
        files_widget = QWidget()
        files_layout = QVBoxLayout(files_widget)
        files_layout.setContentsMargins(0, 0, 0, 0)
        
        file_btn_layout = QHBoxLayout()
        self.btn_add_dir = QPushButton("Add Directory")
        self.btn_add_dir.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
        self.btn_add_dir.clicked.connect(self.add_directory)
        file_btn_layout.addWidget(self.btn_add_dir)
        
        # Manual refresh button removed in favor of QTimer

        file_btn_layout.addStretch()
        files_layout.addLayout(file_btn_layout)

        # Splitter for multiple directory columns (Horizontal)
        self.file_splitter = QSplitter(Qt.Orientation.Horizontal)
        files_layout.addWidget(self.file_splitter)
        
        splitter.addWidget(files_widget)

        # --- Context Section ---
        context_widget = QWidget()
        context_layout = QVBoxLayout(context_widget)
        context_layout.setContentsMargins(0, 10, 0, 0)
        
        context_layout.addWidget(QLabel("Additional Context / Prompt:"))
        self.text_context = QTextEdit()
        context_layout.addWidget(self.text_context)

        # Options for copy
        options_layout = QHBoxLayout()
        self.chk_include_sys = QCheckBox("Include System Prompt in Copy")
        options_layout.addWidget(self.chk_include_sys)
        options_layout.addStretch()
        context_layout.addLayout(options_layout)

        action_layout = QHBoxLayout()
        
        self.btn_copy_context = QPushButton("Copy Context & Files")
        self.btn_copy_context.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
        self.btn_copy_context.clicked.connect(self.copy_context_to_clipboard)
        action_layout.addWidget(self.btn_copy_context)

        self.btn_copy_sys = QPushButton("Copy System Prompt Only")
        self.btn_copy_sys.clicked.connect(self.copy_system_prompt)
        action_layout.addWidget(self.btn_copy_sys)

        self.btn_paste_apply = QPushButton("Paste Response & Apply")
        self.btn_paste_apply.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton))
        self.btn_paste_apply.clicked.connect(self.paste_and_apply)
        action_layout.addWidget(self.btn_paste_apply)

        context_layout.addLayout(action_layout)
        splitter.addWidget(context_widget)
        
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)

    # --- Theme & Styling ---
    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        self.apply_theme()

    def apply_theme(self):
        if self.is_dark_mode:
            self.setStyleSheet("""
                QMainWindow, QWidget { background-color: #2b2b2b; color: #e0e0e0; font-family: 'Segoe UI', sans-serif; }
                QTreeWidget { background-color: #333333; border: 1px solid #444; color: #e0e0e0; }
                QTreeWidget::item:hover { background-color: #3e3e3e; }
                QTreeWidget::item:selected { background-color: #4a90e2; color: white; }
                QTextEdit { background-color: #333333; border: 1px solid #444; color: #e0e0e0; }
                QPushButton { background-color: #444; border: 1px solid #555; padding: 6px 12px; border-radius: 4px; color: #e0e0e0; }
                QPushButton:hover { background-color: #555; border-color: #666; }
                QPushButton:pressed { background-color: #333; }
                QComboBox { background-color: #444; border: 1px solid #555; padding: 5px; border-radius: 4px; color: #e0e0e0; }
                QComboBox::drop-down { border: none; }
                QSplitter::handle { background-color: #444; }
                QHeaderView::section { background-color: #333; border: 1px solid #444; padding: 4px; color: #e0e0e0; }
                QCheckBox { color: #e0e0e0; }
            """)
        else:
            self.setStyleSheet("""
                QMainWindow, QWidget { background-color: #f5f5f5; color: #333; font-family: 'Segoe UI', sans-serif; }
                QTreeWidget { background-color: white; border: 1px solid #ccc; }
                QTextEdit { background-color: white; border: 1px solid #ccc; }
                QPushButton { background-color: #e0e0e0; border: 1px solid #ccc; padding: 6px 12px; border-radius: 4px; }
                QPushButton:hover { background-color: #d0d0d0; }
                QComboBox { background-color: white; border: 1px solid #ccc; padding: 5px; }
            """)

    # --- Project Management ---
    def load_projects(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                    self.projects_data = data.get('projects', {})
                    self.current_project_name = data.get('current_project', 'Default')
            except Exception as e:
                print(f"Error loading projects: {e}")
        
        if not self.projects_data:
            self.projects_data = {"Default": {"roots": [], "context": "", "checked": []}}
            self.current_project_name = "Default"

        self.update_project_combo()
        self.load_project_state(self.current_project_name)

    def save_projects_to_disk(self):
        data = {
            "current_project": self.current_project_name,
            "projects": self.projects_data
        }
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.status_message(f"Error saving config: {e}")

    def update_project_combo(self):
        self.project_combo.blockSignals(True)
        self.project_combo.clear()
        self.project_combo.addItems(sorted(self.projects_data.keys()))
        self.project_combo.setCurrentText(self.current_project_name)
        self.project_combo.blockSignals(False)

    def new_project(self):
        name, ok = QInputDialog.getText(self, "New Project", "Project Name:")
        if ok and name:
            if name in self.projects_data:
                QMessageBox.warning(self, "Error", "Project already exists.")
                return
            
            self.save_current_project_state()
            self.projects_data[name] = {"roots": [], "context": "", "checked": []}
            self.current_project_name = name
            self.update_project_combo()
            self.load_project_state(name)
            self.save_projects_to_disk()

    def delete_project(self):
        if len(self.projects_data) <= 1:
            QMessageBox.warning(self, "Error", "Cannot delete the last project.")
            return
            
        confirm = QMessageBox.question(self, "Confirm", f"Delete project '{self.current_project_name}'?", 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            del self.projects_data[self.current_project_name]
            self.current_project_name = list(self.projects_data.keys())[0]
            self.update_project_combo()
            self.load_project_state(self.current_project_name)
            self.save_projects_to_disk()

    def change_project(self, index):
        new_name = self.project_combo.currentText()
        if new_name == self.current_project_name:
            return
            
        self.save_current_project_state()
        self.current_project_name = new_name
        self.load_project_state(new_name)
        self.save_projects_to_disk()

    def save_current_project_state(self):
        roots = []
        checked = []
        
        for tree in self.file_trees:
            if tree.topLevelItemCount() > 0:
                root_item = tree.topLevelItem(0)
                root_path = root_item.data(0, Qt.ItemDataRole.UserRole)
                roots.append(root_path)

            iterator = QTreeWidgetItemIterator(tree, QTreeWidgetItemIterator.IteratorFlag.Checked)
            while iterator.value():
                item = iterator.value()
                path = item.data(0, Qt.ItemDataRole.UserRole)
                if path and os.path.isfile(path):
                    checked.append(path)
                iterator += 1
            
        self.projects_data[self.current_project_name] = {
            "roots": roots,
            "context": self.text_context.toPlainText(),
            "checked": checked
        }
        self.save_projects_to_disk()
        self.status_message("Project saved.")

    def load_project_state(self, name):
        data = self.projects_data.get(name, {})
        
        for tree in self.file_trees:
            tree.deleteLater()
        self.file_trees = []
        
        self.text_context.setPlainText(data.get("context", ""))
        
        roots = data.get("roots", [])
        checked_set = set(data.get("checked", []))
        
        for root_path in roots:
            if os.path.exists(root_path):
                self.add_directory_column(root_path, checked_set)
                
    # --- File Logic ---
    def add_directory(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Directory")
        if dir_path:
            for tree in self.file_trees:
                if tree.topLevelItemCount() > 0:
                    existing_root = tree.topLevelItem(0).data(0, Qt.ItemDataRole.UserRole)
                    if existing_root == dir_path:
                        return

            self.add_directory_column(dir_path)
            self.save_current_project_state()

    def add_directory_column(self, dir_path, checked_set=None):
        if len(self.file_trees) >= 5:
            QMessageBox.warning(self, "Limit Reached", "Maximum of 5 directory columns allowed.")
            return

        tree = QTreeWidget()
        tree.setHeaderLabel(os.path.basename(dir_path))
        tree.itemChanged.connect(self.handle_item_changed)
        
        root_item = QTreeWidgetItem(tree)
        root_item.setText(0, dir_path)
        root_item.setIcon(0, self.icon_provider.icon(QFileInfo(dir_path)))
        root_item.setFlags(root_item.flags() | Qt.ItemFlag.ItemIsAutoTristate | Qt.ItemFlag.ItemIsUserCheckable)
        root_item.setCheckState(0, Qt.CheckState.Unchecked)
        root_item.setData(0, Qt.ItemDataRole.UserRole, dir_path)
        
        # Load .gitignore patterns for this root
        ignore_patterns = self.load_gitignore(dir_path)
        
        self.populate_tree(dir_path, root_item, checked_set, ignore_patterns)
        root_item.setExpanded(True)
        
        self.file_splitter.addWidget(tree)
        self.file_trees.append(tree)

    def load_gitignore(self, root_path):
        patterns = ['.git', '__pycache__', '.DS_Store', '*.pyc'] # Defaults
        git_path = os.path.join(root_path, '.gitignore')
        if os.path.exists(git_path):
            try:
                with open(git_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            patterns.append(line)
            except Exception:
                pass
        return patterns

    def is_ignored(self, name, patterns):
        for pattern in patterns:
            # Handle directory markers roughly
            clean_pattern = pattern.rstrip('/')
            if fnmatch.fnmatch(name, clean_pattern):
                return True
        return False

    def refresh_file_trees(self):
        # 1. Capture State (Checked Files AND Expanded Paths)
        checked_files = [f[0] for f in self.get_checked_files()]
        checked_set = set(checked_files)
        
        expanded_paths = set()
        for tree in self.file_trees:
            iterator = QTreeWidgetItemIterator(tree)
            while iterator.value():
                item = iterator.value()
                if item.isExpanded():
                    path = item.data(0, Qt.ItemDataRole.UserRole)
                    if path:
                        expanded_paths.add(path)
                iterator += 1
        
        # 2. Rebuild Trees
        for tree in self.file_trees:
            if tree.topLevelItemCount() == 0: continue
            
            root_item = tree.topLevelItem(0)
            root_path = root_item.data(0, Qt.ItemDataRole.UserRole)
            
            # Temporary block signals to prevent event spam during reload
            tree.blockSignals(True)
            tree.clear()
            
            if os.path.exists(root_path):
                new_root = QTreeWidgetItem(tree)
                new_root.setText(0, root_path)
                new_root.setIcon(0, self.icon_provider.icon(QFileInfo(root_path)))
                new_root.setFlags(new_root.flags() | Qt.ItemFlag.ItemIsAutoTristate | Qt.ItemFlag.ItemIsUserCheckable)
                new_root.setCheckState(0, Qt.CheckState.Unchecked)
                new_root.setData(0, Qt.ItemDataRole.UserRole, root_path)
                
                ignore_patterns = self.load_gitignore(root_path)
                self.populate_tree(root_path, new_root, checked_set, ignore_patterns)
                
                # 3. Restore Expansion
                if root_path in expanded_paths:
                    new_root.setExpanded(True)
                
                # Restore expansion for children
                iterator = QTreeWidgetItemIterator(tree)
                while iterator.value():
                    item = iterator.value()
                    path = item.data(0, Qt.ItemDataRole.UserRole)
                    if path in expanded_paths:
                        item.setExpanded(True)
                    iterator += 1
            
            tree.blockSignals(False)

    def populate_tree(self, path, parent_item, checked_set=None, ignore_patterns=None):
        if ignore_patterns is None: ignore_patterns = []
        try:
            for entry in sorted(os.scandir(path), key=lambda e: (not e.is_dir(), e.name.lower())):
                # Check ignore
                if self.is_ignored(entry.name, ignore_patterns):
                    continue

                item = QTreeWidgetItem(parent_item)
                item.setText(0, entry.name)
                
                file_info = QFileInfo(entry.path)
                icon = self.icon_provider.icon(file_info)
                item.setIcon(0, icon)

                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setData(0, Qt.ItemDataRole.UserRole, entry.path)

                if entry.is_dir():
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsAutoTristate)
                    item.setCheckState(0, Qt.CheckState.Unchecked)
                    self.populate_tree(entry.path, item, checked_set, ignore_patterns)
                else:
                    is_checked = checked_set and entry.path in checked_set
                    item.setCheckState(0, Qt.CheckState.Checked if is_checked else Qt.CheckState.Unchecked)
                    
        except PermissionError:
            pass

    def handle_item_changed(self, item, column):
        pass

    def get_checked_files(self):
        checked_files = []
        for tree in self.file_trees:
            iterator = QTreeWidgetItemIterator(tree, QTreeWidgetItemIterator.IteratorFlag.Checked)
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
        
        output.append("Files:")
        for abs_path, rel_path in files:
            try:
                with open(abs_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                output.append(f"File: {abs_path}\n```\n{content}\n```\n")
            except Exception as e:
                output.append(f"File: {abs_path} (Error reading file: {e})\n")
        
        if self.chk_include_sys.isChecked():
            output.append("\n=== System Prompt ===")
            output.append(self.system_prompt)
            output.append("=====================\n")

        user_context = self.text_context.toPlainText().strip()
        if user_context:
            output.append(f"\nContext/Instructions:\n{user_context}\n")

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
        
        # Regex to identify headers: Updated path, New, or Delete
        # We capture the type (e.g. "Updated path:") and the rest of the line (the path)
        header_pattern = re.compile(r'^(?P<type>Updated path:|New:|Delete:)\s*(?P<path>[^\n]+)', re.MULTILINE)
        
        matches = list(header_pattern.finditer(response))
        if not matches:
            QMessageBox.information(self, "Result", "No valid patterns found in clipboard content.")
            return

        for i, match in enumerate(matches):
            header_type = match.group('type')
            path_str = match.group('path').strip()
            
            # Get the block of text belonging to this segment
            start_index = match.start()
            end_index = matches[i+1].start() if i + 1 < len(matches) else len(response)
            segment = response[start_index:end_index]
            
            if header_type == "Updated path:":
                # This is the only place where multiple "Replace...With" are allowed
                mod_pattern = re.compile(
                    r'Replace:\s*\n```(?:\w+)?\n(?P<search>.*?)```\s*\n'
                    r'With:\s*\n```(?:\w+)?\n(?P<replace>.*?)```',
                    re.DOTALL
                )
                
                replacements = list(mod_pattern.finditer(segment))
                if replacements:
                    for rep_match in replacements:
                        search_block = rep_match.group('search')
                        replace_block = rep_match.group('replace')
                        if self.modify_file(path_str, search_block, replace_block):
                             changes_log.append(f"Modified: {path_str}")
                        else:
                             changes_log.append(f"Failed to modify: {path_str}")
                else:
                    changes_log.append(f"No Replace/With blocks found for: {path_str}")

            elif header_type == "New:":
                content_pattern = re.compile(r'Content:\s*\n```(?:\w+)?\n(?P<content>.*?)```', re.DOTALL)
                c_match = content_pattern.search(segment)
                if c_match:
                    content = c_match.group('content')
                    if self.create_file(path_str, content):
                        changes_log.append(f"Created: {path_str}")
                    else:
                        changes_log.append(f"Failed to create: {path_str}")
                else:
                    changes_log.append(f"No content found for new file: {path_str}")

            elif header_type == "Delete:":
                if self.delete_file(path_str):
                    changes_log.append(f"Deleted: {path_str}")
                else:
                    changes_log.append(f"Failed to delete: {path_str}")

        if not changes_log:
            QMessageBox.information(self, "Result", "No changes applied.")
        else:
            QMessageBox.information(self, "Result", "\n".join(changes_log))
            self.refresh_file_trees() # Auto-refresh immediately after changes

    def resolve_abs_path(self, path):
        path = path.strip().replace('\\', '/')
        if os.path.isabs(path) and os.path.exists(path):
            return path
            
        for tree in self.file_trees:
            if tree.topLevelItemCount() == 0: continue
            root_path = tree.topLevelItem(0).data(0, Qt.ItemDataRole.UserRole)
            
            potential_path = os.path.join(root_path, path)
            if os.path.exists(potential_path):
                return potential_path
            
            if path.startswith(root_path):
                return path

        if self.file_trees and not os.path.isabs(path):
            first_root = self.file_trees[0].topLevelItem(0).data(0, Qt.ItemDataRole.UserRole)
            return os.path.join(first_root, path)
        
        return path if os.path.isabs(path) else None

    def create_file(self, rel_path, content):
        abs_path = self.resolve_abs_path(rel_path)
        if not abs_path: return False
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
    app.setStyle(QStyleFactory.create("Fusion"))
    window = ClaudeInterfaceApp()
    window.show()
    sys.exit(app.exec())
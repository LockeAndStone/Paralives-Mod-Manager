from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QHBoxLayout, QVBoxLayout, QLineEdit,
    QListWidget, QFileDialog, QFrame, QLabel, QPushButton,
    QListWidgetItem, QMessageBox, QTextEdit, QSplitter,
    QToolBar, QWidgetAction, QStackedWidget, QCheckBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QShortcut, QIcon
import getpass
from pathlib import Path
import zipfile
import shutil
from shutil import rmtree
import tempfile
import os
import json
import sys
import py7zr
import requests
# import rarfile
from packaging.version import Version
import webbrowser

#### MAKE A CLASS FOR MODS?

class SearchBar(QLineEdit):
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.clear()
            return
        super().keyPressEvent(event)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.app_ver = "1.0.6"
        self.base_dir = Path(os.environ["USERPROFILE"]) # Set the base dir for where the users folder is on the OS
        self.local_mod_dir = self.base_dir / "AppData/LocalLow/Paralives/Paralives" # Using the base dir, points to the paralives mod folder.
        self.settings = {} # Assigns the settings dictionary
        self.load_settings()
        self.changes_made = False # Tracks whether any mods have been enabled/disabled
        self.installed_mods = [] # This is where all mod data is stored for the program. Initialised by the self.get_installed_mods() function
        self.mod_map = "" # This allows for quick lookup for the installed mods. Allows for a single source of truth approach.
        self.base_mods = ["MySavedGames.mod", "MyPremadeOutfits.mod", "MyPremadeLot.mod", "MyPremadeHouseholds.mod", "MyOptions.mod", "Local.mod", ""] # A list of mods to ignore
        self.check_all_state = False

        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready", 10000)

        # Set Github API Settings
        self.owner = "LockeAndStone"
        self.repo = "Paralives-Mod-Manager"
        self.giturl = f"https://api.github.com/repos/{self.owner}/{self.repo}/releases/latest"
        
        if self.settings["AutoCheck"]:
            try:
                self.response = requests.get(self.giturl, timeout=5)
                self.latest_version = str(self.response.json()["tag_name"])
                self.download_url = self.get_latest_download()
                self.update_available = self.check_update()
                print(f"Download Link: '{self.download_url}'")
            except:
                self.status_bar.showMessage("Unable to connect to GitHub")
                self.update_available = False
        else:
            self.status_bar.showMessage("Auto Check for Updates are Disabled", 5000)

        # --------------------------------------------------------
        
        self.get_installed_mods()

        self.setAcceptDrops(True)
        self.setWindowTitle("Paralives Mod Manager")
        self.resize(1000, 600)

        # ================================
        # GUI LAYOUT DESIGN
        # ================================
        # --------------------------------
        # Root
        # --------------------------------
        root = QWidget()
        self.setCentralWidget(root)

        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(5)

        # --------------------------------
        # TOOL BAR
        # --------------------------------
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)
        toolbar.setMovable(False)
        toolbar.setFloatable(False)

        toolbar.addSeparator()

        self.check_all_action = toolbar.addAction("Enable/Disable All")
        self.check_all_action.triggered.connect(self.check_all)

        if self.check_all_state:
            self.check_all_action.setText("Enable All")
        else:
            self.check_all_action.setText("Disable All")

        save_action = toolbar.addAction("Save Changes")
        save_action.triggered.connect(self.deploy_mods)
        save_action.setToolTip("Save Enabled/Disabled Mods [Ctrl + S]")

        toolbar.addSeparator()

        refresh_action = toolbar.addAction("Refresh")
        refresh_action.triggered.connect(self.refresh)
        refresh_action.setToolTip("Refresh Mod List [F5]")

        toolbar.addSeparator()

        search_action = QWidgetAction(self)
        self.search_bar = SearchBar()
        self.search_bar.setPlaceholderText("Search...")

        search_action.setDefaultWidget(self.search_bar)
        toolbar.addAction(search_action)

        self.search_bar.textChanged.connect(self.filter_mods)

        toolbar.addSeparator()

        add_action = toolbar.addAction("Add Mod")
        add_action.triggered.connect(self.add_mod_from_zip)
        add_action.setToolTip("Add a Local Mod [Ctrl + O]")

        delete_action = toolbar.addAction("Delete Mod")
        delete_action.triggered.connect(self.delete_selected_mod)
        delete_action.setToolTip("Delete a Local Mod [Del]")

        toolbar.addSeparator()

        settings_action = toolbar.addAction("Settings")
        settings_action.setToolTip("App Settings [F2]")

        toolbar.addSeparator()

        launch_action = toolbar.addAction("Launch")
        launch_action.triggered.connect(self.launch_game)
        launch_action.setToolTip("Launch Game on Steam [Ctr + Enter]")

        toolbar.addSeparator()

        if self.settings["AutoCheck"]:
            if self.update_available:
                toolbar.addSeparator()
                update_action = toolbar.addAction(f"Update Available: {str(self.latest_version)}")
                update_action.triggered.connect(self.download_latest)
                update_action.setToolTip("Download the Latest Version")

        toolbar.setStyleSheet("""
        QToolBar {
                    spacing: 6px;
                    padding: 4px;
                    background: #2c2c2c      
        }
        QToolBar::separator {
                    background: #666;
                    width: 1px;
                    margin: 4px;
        }
""")
    
        # --------------------------------
        # MAIN PANEL
        # --------------------------------
        main_panel = QFrame()
        main_panel_layout = QHBoxLayout(main_panel)
        main_panel_layout.setContentsMargins(0, 0, 0, 0)
        main_panel_layout.setSpacing(10)

        # ----------------------------
        # MOD LIST
        # ----------------------------
        self.mod_list = QListWidget()
        self.mod_list.setMinimumWidth(300)
        self.load_mods()      
        self.mod_list.itemClicked.connect(self.display_metadata)
        self.mod_list.itemChanged.connect(self.on_item_changed)

        # ----------------------------
        # META DATA PANEL
        # ----------------------------
        mod_view = QFrame()
        mod_view.setMinimumWidth(500)
        mod_view.setFrameStyle(QFrame.StyledPanel)

        mod_view_layout = QVBoxLayout(mod_view)
        mod_view_layout.setContentsMargins(10,10,10,10)
        mod_view_layout.setSpacing(2)

        # ----------------------------
        # Empty Page
        # ----------------------------
        self.info_stack = QStackedWidget()

        empty_page = QWidget()
        empty_layout = QVBoxLayout(empty_page)

        title = QLabel("No Mod Selected")
        title.setAlignment(Qt.AlignCenter)

        message = QLabel("Select a mod from the list to view details.")
        message.setAlignment(Qt.AlignCenter)

        empty_layout.addStretch()
        empty_layout.addWidget(title)
        empty_layout.addWidget(message)
        empty_layout.addStretch()

        # ----------------------------
        # Mod Info
        # ----------------------------
        mod_info = QFrame()
        mod_info.setFrameStyle(QFrame.StyledPanel)

        mod_info_layout = QVBoxLayout(mod_info)
        mod_info_layout.setContentsMargins(10,10,10,10)
        mod_info_layout.setSpacing(5)

        self.thumbnail = QLabel()

        self.mod_enabled_state = QLabel("")
        self.mod_source_label = QLabel("")

        self.mod_name_label = QLabel("")
        self.mod_name_label.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
        """)
        self.mod_creator_label = QLabel("Creator:")
        
        description_label = QLabel("Description")
        description_label.setStyleSheet("""
            font-weight: bold;
            font-size: 14px;
        """)

        self.mod_workshop_description = QTextEdit()
        self.mod_workshop_description.setReadOnly(True)

        self.convert_from_workshop_btn = QPushButton("Convert to Local")
        self.convert_from_workshop_btn.hide()
        self.convert_from_workshop_btn.clicked.connect(self.convert_from_workshop)

        # =========================================================
        # ADD TO MOD INFO
        # =========================================================
        mod_info_header = QHBoxLayout()
        mod_info_header.setSpacing(20)

        meta_layout = QVBoxLayout()
        meta_layout.setSpacing(5)

        mod_badges = QHBoxLayout()
        mod_badges.setSpacing(5)
        mod_badges.setAlignment(Qt.AlignLeft)
        mod_badges.addWidget(self.mod_enabled_state)
        mod_badges.addWidget(self.mod_source_label )

        meta_layout.addStretch()
        
        meta_layout.addLayout(mod_badges)
        meta_layout.addWidget(self.mod_name_label)
        meta_layout.addWidget(self.mod_creator_label)
        meta_layout.addStretch()

        mod_info_header.addWidget(self.thumbnail)
        mod_info_header.addLayout(meta_layout)
        mod_info_header.addStretch()

        mod_info_layout.addLayout(mod_info_header)
        mod_info_layout.addWidget(description_label)
        mod_info_layout.addWidget(self.mod_workshop_description)
        mod_info_layout.addStretch()
        mod_info_layout.addWidget(self.convert_from_workshop_btn)

        # =========================================================
        # SETTINGS
        # =========================================================
        settings_pane = QWidget()
        settings_layout = QVBoxLayout(settings_pane)

        settings_title = QLabel("Settings")
        settings_title.setAlignment(Qt.AlignCenter)

        choose_game_dir_layout = QHBoxLayout()
        choose_game_dir_label = QLabel("Choose Game Exe:")

        self.choose_game_dir_path = QLineEdit()
        self.choose_game_dir_path.setMinimumWidth(200)
        self.choose_game_dir_path.setMaximumWidth(700)
        self.choose_game_dir_path.setText(self.settings["GameDir"])
        self.choose_game_dir_path.setReadOnly(True)
        self.choose_game_dir_path.selectAll()

        choose_game_dir_btn = QPushButton("Browse")
        choose_game_dir_btn.clicked.connect(self.select_game_path)

        choose_game_dir_layout.addWidget(choose_game_dir_label)
        choose_game_dir_layout.addWidget(self.choose_game_dir_path)
        choose_game_dir_layout.addWidget(choose_game_dir_btn)

        self.auto_check_update_box = QCheckBox("Check for updates automatically")
        self.auto_check_update_box.clicked.connect(self.check_auto_update_state)

        if self.settings["AutoCheck"]:
            self.auto_check_update_box.setChecked(True)
        else:
            self.auto_check_update_box.setChecked(False)

        settings_layout.addWidget(settings_title)
        settings_layout.addLayout(choose_game_dir_layout)
        settings_layout.addWidget(self.auto_check_update_box)
        settings_layout.addStretch()


        # =========================================================
        # BUILD STACK
        # =========================================================
        self.info_stack.addWidget(empty_page)
        self.info_stack.addWidget(mod_info)
        self.info_stack.addWidget(settings_pane)

        
        settings_action.triggered.connect(lambda: self.info_stack.setCurrentIndex(2))
        self.info_stack.setCurrentIndex(0)

        # =========================================================
        # ADD TO MOD VIEW
        # =========================================================
        mod_view_layout.addWidget(self.info_stack, alignment=Qt.AlignCenter, stretch=1)

        splitter = QSplitter()
        splitter.addWidget(self.mod_list)
        splitter.addWidget(mod_view)
        splitter.setSizes([350, 650])
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setChildrenCollapsible(False)

        # =========================================================
        # ADD TO Main Panel
        # =========================================================
        main_panel_layout.addWidget(splitter)

        # =========================================================
        # ADD TO ROOT
        # =========================================================
        root_layout.addWidget(main_panel)

        # =========================================================
        # SHORTCUTS
        # =========================================================
        QShortcut("Ctrl+F", self, self.search_bar.setFocus)
        QShortcut("F5", self, self.refresh)
        QShortcut("Delete", self, self.delete_selected_mod)
        QShortcut("Ctrl+S", self, self.deploy_mods)
        QShortcut("Ctrl+O", self, self.add_mod_from_zip)
        QShortcut("Ctrl+Return", self, self.launch_game)
        QShortcut("F2", self, lambda: self.info_stack.setCurrentIndex(2))

    # builds the list of mods in the mod list and stores the GUID for use in the hash_map
    def load_mods(self):
        self.mod_list.blockSignals(True)
        self.mod_list.clear()

        for mod in self.installed_mods:

            # skip base mods
            if mod["ModName"] in self.base_mods:
                continue

            item = QListWidgetItem(mod["ModName"])

            # store ONLY GUID (not dict reference)
            item.setData(Qt.UserRole, mod["GUID"])

            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)

            enabled = mod.get("Enabled", "False") == "True"
            item.setCheckState(Qt.Checked if enabled else Qt.Unchecked)

            self.mod_list.addItem(item)

        self.mod_list.blockSignals(False)

    # get a list of mod paths from the local directory
    def get_installed_mods(self):
        mods = []
        for item in self.local_mod_dir.glob("*.mod"):
            meta = self.read_meta_file(item)
            mods.append(meta)

        for folder in Path(self.settings["WorkshopDir"]).iterdir():
            if folder.is_dir():
                for sub in folder.glob("*.mod"):
                    meta = self.read_meta_file(sub)
                    mods.append(meta)
        
        self.installed_mods = mods
        self.mod_map = {mod["GUID"]: mod for mod in self.installed_mods}
    
    # For each mod, get the meta data and thumbnail, and return it back to the list
    def read_meta_file(self, mod_path):
        mod_path = Path(mod_path)
        meta_data = {} # .mod.meta + Thumbnail

        # ---- Save Mod Path to Mod Diction ----
        meta_data["ModPath"] = mod_path

        # ---- Find meta file ----
        meta_files = list(mod_path.glob("*.mod.meta"))
        if not meta_files:
            raise FileNotFoundError(f"No .mod.meta file found in {mod_path}")
        
        meta_path = Path(meta_files[0])
        # ---- Save Mod Meta Data File loacation ---
        meta_data["MetaData"] = str(meta_path)

        thumbnail_files = list(mod_path.glob("*.mod.thumbnail"))
        if thumbnail_files:
            meta_data["Thumbnail"] = str(thumbnail_files[0])

        current_key = None

        with open(str(meta_path), "r", encoding="utf-8") as f:
            for line in f:
                line = line.rstrip()

                # Skip Empty Lines
                if not line:
                    continue
                
                if ":" in line:
                    key, value = line.split(":", 1)
                    meta_data[key] = value
                    current_key = key

                elif current_key:
                    # Append continuation lines
                    meta_data[current_key] += "\n" + line
            
        
        return meta_data
    
    # This may not be best approach... look at batch saving?
    def on_item_changed(self, item):
        guid = item.data(Qt.UserRole)

        # Retrieves dictionary from self.installed_mods using self.mod_map
        mod = self.mod_map.get(guid)
        if not mod:
            return 
        
        mod["Enabled"] = "True" if item.checkState() == Qt.Checked else "False"
        self.changes_made = True

    def check_all(self):
        for i in range(self.mod_list.count()):
            item = self.mod_list.item(i)

            if self.check_all_state:
                item.setCheckState(Qt.Checked)
                self.check_all_action.setText("Disable All")
                self.status_bar.showMessage("Enabled All Mods: Don't forget to save changes!", 10000)
            else:
                item.setCheckState(Qt.Unchecked)
                self.check_all_action.setText("Enable All")
                self.status_bar.showMessage("Disabled All Mods: Don't forget to save changes!", 10000)

        self.check_all_state = not self.check_all_state

    # Writes changes to disk.
    def write_meta_file(self, mod):
        meta_path = Path(mod["MetaData"])

        ignore = {"ModPath", "MetaData", "Thumbnail"}

        with meta_path.open("w", encoding="utf-8") as f:

            # keep Enabled at top for stability, this doesnt effect how the game reads the file
            if "Enabled" in mod:
                f.write(f"Enabled:{mod['Enabled']}\n")

            for key, value in mod.items():

                if key in ignore or key == "Enabled":
                    continue

                if isinstance(value, str) and "\n" in value:
                    lines = value.split("\n")

                    f.write(f"{key}:{lines[0]}\n")
                    for line in lines[1:]:
                        f.write(f"{line}\n")
                else:
                    f.write(f"{key}:{value}\n")

    # Saves the changes to enabled/disabled to runtime data
    def deploy_mods(self):
        for i in range(self.mod_list.count()):
            item = self.mod_list.item(i)

            guid = item.data(Qt.UserRole)
            mod = self.mod_map.get(guid)

            if mod and (item.flags() & Qt.ItemIsUserCheckable):
                mod["Enabled"] = "True" if item.checkState() == Qt.Checked else "False"

        # write all mods to disk
        for mod in self.installed_mods:
            self.write_meta_file(mod)

        self.changes_made = False
        self.status_bar.showMessage("Changes saved", 3000)

    # Allows the user to manually select the location of a mod in a zip file. The runs the _install_zip() function
    def add_mod_from_zip(self):
        file_path = QFileDialog.getOpenFileName(
            self,
            "Select Mod Zip",
            "",
            "Archive Files (*.zip *.7z)"
        )[0]

        if not file_path:
            return

        
        self._install_zip(Path(file_path))

        
    # Extracts a mod from a zip file and copies the contents containing the .mod to the local mod dir
    def _install_zip(self, zip_path: Path):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            if zip_path.suffix.lower() == ".zip":
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(tmpdir)
            elif zip_path.suffix.lower() == ".7z":
                with py7zr.SevenZipFile(zip_path, mode='r') as zip_ref:
                    zip_ref.extractall(tmpdir)
            # elif zip_path.suffix.lower() == ".rar":
            #     with rarfile.RarFile(zip_path) as rf:
            #         rf.extractall(tmpdir)

            mod_folders = list(tmpdir.rglob("*.mod"))
            if not mod_folders:
                print("No .mod folder found")
                return

            mod_folder = mod_folders[0]
            final_path = self.local_mod_dir / mod_folder.name

            if final_path.exists():
                self.status_bar.showMessage("Mod already exists", 3000)
                return

            shutil.move(str(mod_folder), final_path)

        new_mod = self.read_meta_file(final_path)

        new_mod["IsFromWorkshop"] = "False"

        self.write_meta_file(new_mod)

        self.installed_mods.append(new_mod)
        self.mod_map[new_mod["GUID"]] = new_mod

        self.load_mods()

        self.status_bar.showMessage(f"Installed: {new_mod['ModName']}", 3000)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().endswith(".zip") or url.toLocalFile().endswith(".7z"):
                    event.acceptProposedAction()
                    return

        event.ignore()


    def dropEvent(self, event):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()

            self._install_zip(Path(file_path))

    # Delete selected mod, need to ask if they are sure with a message...
    def delete_selected_mod(self):
        item = self.mod_list.currentItem()

        if not item:
            self.status_bar.showMessage("No mod selected", 3000)
            return

        guid = item.data(Qt.UserRole)
        mod = self.mod_map.get(guid)

        if not mod:
            print("Mod not found in map")
            return
        
        if mod.get("IsFromWorkshop") == "True":
            QMessageBox.warning(
                None,
                "Error",
                "Unsubscribe from the Steam Workshop!"
            )
            return

        mod_name = mod.get("ModName", "Unknown")

        confirm = QMessageBox.question(
            None,
            "Confirm Delete",
            f"Are you sure you want to delete '{mod_name}'?",
            QMessageBox.Yes | QMessageBox.No
        )

        if confirm == QMessageBox.No:
            return

        # Safety check
        print(f"Deleting: {mod_name}")

        mod_path = Path(mod["ModPath"])

        # 1. delete from disk
        if mod_path.exists():
            rmtree(mod_path)

        # 2. delete from memory
        self.installed_mods = [m for m in self.installed_mods if m["GUID"] != guid]
        self.mod_map.pop(guid, None)

        # 3. refresh UI
        self.load_mods()

        self.select_top_mod()

        self.status_bar.showMessage(f"Deleted: {mod_name}", 3000)

    # Handles launching the game using steam url. If there are still changes to be made, then it will prompt the user to do so before launching
    def launch_game(self):
        if self.changes_made:
            confirm = QMessageBox.question(
                None,
                "Confirm Save Changes",
                "Do you want to save the changes you have made before launching?",
                QMessageBox.Yes | QMessageBox.No
            )
            if confirm == QMessageBox.Yes:
                self.deploy_mods()
        app_id = "1118520"
        os.startfile(f"steam://run/{app_id}")

    # Changes what is displayed in the mod info screen when selecting a mod in the list
    def display_metadata(self):
        item = self.mod_list.currentItem()
        

        if not item:
            return

        guid = item.data(Qt.UserRole)
        mod = self.mod_map.get(guid)

        if not mod:
            return
        
        self.status_bar.showMessage(f"{mod.get('ModName')} Selected", 3000)

        # ---- Changes ----
        thumbnail_path = mod.get('Thumbnail')
        if thumbnail_path:
            piximap = QPixmap(thumbnail_path)
            self.thumbnail.setPixmap(piximap.scaled(
                250,
                250,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation)
                                     )

        self.mod_name_label.setText(f"{mod.get('ModName')}")
        self.mod_creator_label.setText(f"Creator: {mod.get('CreatorId')}")
        if mod.get("Enabled") == "True":
            self.mod_enabled_state.setText("Enabled")
            self.mod_enabled_state.setFixedWidth(62)
            self.mod_enabled_state.setStyleSheet("""
                background: #2d7d32;
                color: white;
                border-radius: 4px;
                padding: 2px 6px;
            """)
        else:
            self.mod_enabled_state.setText("Disabled")
            self.mod_enabled_state.setFixedWidth(67)
            self.mod_enabled_state.setStyleSheet("""
                background: #c90812;
                color: white;
                border-radius: 4px;
                padding: 2px 6px;
            """)

        self.mod_workshop_description.setPlainText(f"{mod.get('WorkshopDescription')}")

        if mod.get("IsFromWorkshop") == "True":
            self.mod_source_label.setText("Workshop")
            self.mod_source_label.setStyleSheet("""
                background: #1d1369;
                color: white;
                border-radius: 4px;
                padding: 2px 6px;
            """)
            self.convert_from_workshop_btn.show()
        else:
            self.mod_source_label.setText("Local")
            self.mod_source_label.setStyleSheet("""
                background: #e67505;
                color: white;
                border-radius: 4px;
                padding: 2px 6px;
            """)
            self.convert_from_workshop_btn.hide()

        self.info_stack.setCurrentIndex(1)

    # Intialises self.settings with local data or runs first time setup.
    def load_settings(self):
        try:
            with open("settings.json", "r") as f:
                settings = json.load(f)
        
            self.settings = settings

            if "AutoCheck" not in self.settings:
                self.settings["AutoCheck"] = False
                self.save_settings()
            
            if not Path(self.settings["WorkshopDir"]).exists():
                Path(self.settings["WorkshopDir"]).mkdir(parents=True, exist_ok=True)

        except (FileNotFoundError, json.JSONDecodeError):
            self.select_game_path(fts=True)
        

    def select_game_path(self, fts=False):
        possible_exe_locations = [Path(r"C:\Program Files (x86)\Steam\steamapps\common\Paralives"),
                                      Path(r"D:\SteamLibrary\steamapps\common\Paralives"),
                                      Path(r"E:\SteamLibrary\steamapps\common\Paralives")
                                      ]
            
        start_dir = str(Path.home())

        for path in possible_exe_locations:
            if path.exists():
                start_dir = str(path)
                break

        game_path = QFileDialog.getOpenFileName(
                None,
                "Select 'Paralives.exe'",
                start_dir, # Starting Path
                "Excecutable Files (Paralives.exe)"
            )[0]
        
        if Path(game_path).name == "Paralives.exe":
            file_path = Path(game_path)
            drive = file_path.drive

            if drive == "C:":
                workshop_dir = f"{drive}/Program Files (x86)/Steam/steamapps/workshop/content/1118520"
            else:
                workshop_dir = f"{drive}/SteamLibrary/steamapps/workshop/content/1118520"

            if not Path(workshop_dir).exists():
                Path(workshop_dir).mkdir(parents=True, exist_ok=True)

        else:
            if fts == True:
                sys.exit()
            else:
                return
        
        self.settings["GameDir"] = game_path
        self.settings["WorkshopDir"] = workshop_dir
        self.settings["AutoCheck"] = False
        self.save_settings()

    # Function to be used whenever settings are changed within the application itself. Saves to local settings file
    def save_settings(self):
        with open("settings.json", "w") as f:
            json.dump(self.settings, f, indent=4)

    # Copies the mod from workshop to local mod dir
    def convert_from_workshop(self):
        item = self.mod_list.currentItem()

        if not item:
            return

        guid = item.data(Qt.UserRole)
        mod = self.mod_map.get(guid)

        if not mod:
            return
        
        
        
        print(mod["ModPath"])

        confirm = QMessageBox.question(
            None,
            "Confirm Action",
            "Are you sure you want to convert this workshop item to a local mod?",
            QMessageBox.Yes | QMessageBox.No
        )

        if confirm == QMessageBox.Yes:
            mod["IsFromWorkshop"] = "False"

            self.write_meta_file(mod)
            shutil.move(mod["ModPath"], self.local_mod_dir)

            self.refresh()
            self.select_top_mod()

            self.status_bar.showMessage(f"{mod.get('ModName')} converted to Local", 3000)

            QMessageBox.information(
                None,
                "Important",
                f"Make sure you unsubsribe from {mod.get('ModName')} on the steam workshop!\nThis must be done manually."
                )
            
        else:
            return
    
    def select_top_mod(self):
        self.mod_list.setCurrentRow(0)
        self.display_metadata()

    def refresh(self):
        self.get_installed_mods()
        self.load_mods()
        self.status_bar.showMessage("Mod List Refreshed", 3000)

    def filter_mods(self, text):
        text = text.lower().strip()

        for row in range(self.mod_list.count()):
            item = self.mod_list.item(row)
            # guid = item.data(Qt.UserRole)

            matches = text in item.text().lower()
            item.setHidden(not matches)

    def check_update(self):
        if Version(self.latest_version.lstrip("v")) > Version(self.app_ver):
            return True
        else:
            return False

    def download_latest(self):
        download_choice = QMessageBox.question(
            None,
            f"Download {self.latest_version}",
            f"Current version: v{self.app_ver}.\nDo you want to download {self.latest_version}?\n\nWindows sees this file as a threat due to the copying of files.\nI am trying to get this resolved.",
            QMessageBox.Yes | QMessageBox.No
        )

        if download_choice == QMessageBox.No:
            return
        else:
            webbrowser.open(self.download_url)

    def get_latest_download(self):
        data = requests.get(self.giturl).json()

        for asset in data["assets"]:
            if asset["name"].endswith(".exe"):
                return asset["browser_download_url"]
            
    def check_auto_update_state(self):
        if self.auto_check_update_box.isChecked():
            self.settings["AutoCheck"] = True
            self.status_bar.showMessage("Auto Check for Updates Enabled", 3000)
        else:
            self.settings["AutoCheck"] = False
            self.status_bar.showMessage("Auto Check for Updates Disabled", 3000)
        
        self.save_settings()
        
    



if __name__ == "__main__":
    app = QApplication()

    window = MainWindow()
    window.show()

    app.exec()

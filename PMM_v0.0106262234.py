from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QHBoxLayout, QVBoxLayout, QLineEdit,
    QListWidget, QFileDialog, QFrame, QLabel, QPushButton,
    QListWidgetItem, QMessageBox, QDialog, QTextEdit
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
import getpass
from pathlib import Path
import zipfile
import shutil
from shutil import rmtree
import tempfile
import os
import json

#### MAKE A CLASS FOR MODS?

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.base_dir = Path(os.environ["USERPROFILE"])
        self.local_mod_dir = self.base_dir / "AppData/LocalLow/Paralives/Paralives"
        self.settings = self.load_settings()
        self.user_id = getpass.getuser()
        self.game_dir = Path(self.settings["GameDir"])
        self.workshop_dir = Path(self.settings["WorkshopDir"])
        self.changes_made = False
        self.installed_mods = []
        # single source of truth lookup
        self.mod_map = ""
        self.base_mods = ["MySavedGames.mod", "MyPremadeOutfits.mod", "MyPremadeLot.mod", "MyPremadeHouseholds.mod", "MyOptions.mod", "Local.mod", ""]

        self.get_installed_mods()

        self.setAcceptDrops(True)
        self.setWindowTitle("Paralives Mod Manager")
        self.resize(1000, 600)

        # --------------------------------
        # Root
        # --------------------------------
        root = QFrame()
        self.setCentralWidget(root)

        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(10)

        # ================================
        # TOP BAR
        # ================================
        top_bar = QFrame()
        top_bar.setFrameShape(QFrame.StyledPanel)
        top_bar_layout = QHBoxLayout(top_bar)
        top_bar_layout.setContentsMargins(5, 5, 5, 5)
        top_bar_layout.setSpacing(2)

        refresh_btn = QPushButton("Refresh")
        # refresh_btn.setMaximumWidth(40)
        refresh_btn.clicked.connect(self.refresh)

        search_bar = QLineEdit()
        search_bar.setPlaceholderText("Not implemented yet...")

        search_btn = QPushButton("Search")
        # search_btn.setMaximumWidth(120)
        search_btn.clicked.connect(lambda: print("Clicked 'Search' Button"))

        add_mod_btn = QPushButton("Add Mod")
        # add_mod_btn.setMaximumWidth(40)
        add_mod_btn.clicked.connect(self.add_mod_from_zip)

        delete_mods_btn = QPushButton("Delete Mod")
        # delete_mods_btn.setMaximumWidth(40)
        delete_mods_btn.clicked.connect(self.delete_selected_mod)

        deploy_mods_btn = QPushButton("Save Changes")
        # deploy_mods_btn.setMaximumWidth(40)
        deploy_mods_btn.clicked.connect(self.deploy_mods)

        launch_game_btn = QPushButton("Launch")
        # launch_game_btn.setMaximumWidth(120)
        launch_game_btn.clicked.connect(self.launch_game)

        # ----------------------------
        # ASSEMBLE TOP PANEL
        # ----------------------------
        top_bar_layout.addWidget(refresh_btn)
        top_bar_layout.addWidget(search_bar)
        top_bar_layout.addWidget(search_btn)
        top_bar_layout.addWidget(add_mod_btn)
        top_bar_layout.addWidget(delete_mods_btn)
        top_bar_layout.addWidget(deploy_mods_btn)
        top_bar_layout.addWidget(launch_game_btn)

        # ================================
        # MAIN PANEL
        # ================================
        main_panel = QFrame()
        main_panel_layout = QHBoxLayout(main_panel)
        main_panel_layout.setContentsMargins(0, 0, 0, 0)
        main_panel_layout.setSpacing(10)

        # ----------------------------
        # MOD LIST
        # ----------------------------
        self.mod_list = QListWidget()
        self.load_mods()      
        self.mod_list.itemClicked.connect(self.display_metadata)
        self.mod_list.itemChanged.connect(self.on_item_changed)

        # ----------------------------
        # META DATA PANEL
        # ----------------------------
        mod_view = QFrame()
        mod_view.setFrameStyle(QFrame.StyledPanel)

        mod_view_layout = QVBoxLayout(mod_view)
        mod_view_layout.setContentsMargins(0,0,0,0)
        mod_view_layout.setSpacing(0)

        # mod_view_title = QLabel("Mod Information")

        mod_info = QFrame()
        mod_info.setFrameShape(QFrame.StyledPanel)

        mod_info_layout = QVBoxLayout(mod_info)
        mod_info_layout.setContentsMargins(10,10,10,10)
        mod_info_layout.setSpacing(5)

        self.mod_name_label = QLabel("Mod Name:")
        self.mod_creator_label = QLabel("Creator:")
        self.mod_enabled_state = QLabel("")

        self.mod_workshop_description = QTextEdit()
        self.mod_workshop_description.setReadOnly(True)

        self.convert_from_workshop_btn = QPushButton("Convert to Local")
        self.convert_from_workshop_btn.hide()
        self.convert_from_workshop_btn.clicked.connect(self.convert_from_workshop)

        # =========================================================
        # ADD TO MOD INFO
        # =========================================================
        mod_info_layout.addWidget(self.mod_name_label)
        mod_info_layout.addWidget(self.mod_creator_label)
        mod_info_layout.addWidget(self.mod_enabled_state)
        mod_info_layout.addWidget(self.mod_workshop_description)
        mod_info_layout.addWidget(self.convert_from_workshop_btn)
        # =========================================================
        # ADD TO MOD VIEW
        # =========================================================
        # mod_view_layout.addWidget(mod_view_title, alignment=Qt.AlignCenter)
        mod_view_layout.addWidget(mod_info, alignment=Qt.AlignCenter, stretch=1)

        # =========================================================
        # ADD TO Main Panel
        # =========================================================
        main_panel_layout.addWidget(self.mod_list, stretch=2)
        main_panel_layout.addWidget(mod_view, stretch=1)

        # =========================================================
        # ADD TO ROOT
        # =========================================================
        root_layout.addWidget(top_bar)
        root_layout.addWidget(main_panel)

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

            if mod["IsFromWorkshop"] == "True":
                item.setFlags(item.flags() & ~Qt.ItemIsUserCheckable)
            else:
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

        for folder in self.workshop_dir.iterdir():
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

        # print(str(meta_path))

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

    def deploy_mods(self):
        # optional safety: sync UI → model before saving
        for i in range(self.mod_list.count()):
            item = self.mod_list.item(i)

            guid = item.data(Qt.UserRole)
            mod = self.mod_map.get(guid)

            if mod and (item.flags() & Qt.ItemIsUserCheckable):
                mod["Enabled"] = "True" if item.checkState() == Qt.Checked else "False"

        # write all mods
        for mod in self.installed_mods:
            self.write_meta_file(mod)

        self.changes_made = False
        print("Mods Deployed")

    def add_mod_from_zip(self):
        file_path = QFileDialog.getOpenFileName(
            self,
            "Select Mod Zip",
            "",
            "Zip Files (*.zip)"
        )[0]

        if not file_path:
            return

        self._install_zip(Path(file_path))
        
    def _install_zip(self, zip_path: Path):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(tmpdir)

            mod_folders = list(tmpdir.rglob("*.mod"))
            if not mod_folders:
                print("No .mod folder found")
                return

            mod_folder = mod_folders[0]
            final_path = self.local_mod_dir / mod_folder.name

            if final_path.exists():
                print("Mod already exists")
                return

            shutil.move(str(mod_folder), final_path)

        new_mod = self.read_meta_file(final_path)

        self.installed_mods.append(new_mod)
        self.mod_map[new_mod["GUID"]] = new_mod

        self.load_mods()

        print(f"Installed: {new_mod['ModName']}")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().endswith(".zip"):
                    event.acceptProposedAction()
                    return

        event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()

            if file_path.endswith(".zip"):
                self._install_zip(Path(file_path))

    # Delete selected mod, need to ask if they are sure with a message...
    def delete_selected_mod(self):
        item = self.mod_list.currentItem()

        if not item:
            print("No mod selected")
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

        print(f"Deleted: {mod_name}")

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

    def set_thumbnail(self, path: str):
        pixmap = QPixmap(path)

        if pixmap.isNull():
            self.thumbnail.clear()
            print("Failed to load image:", path)
            return

        pixmap = pixmap.scaled(
            200, 200,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        self.thumbnail.setPixmap(pixmap)

    def display_metadata(self):
        item = self.mod_list.currentItem()

        if not item:
            return

        guid = item.data(Qt.UserRole)
        mod = self.mod_map.get(guid)

        if not mod:
            return

        # ---- Changes ----
        self.mod_name_label.setText(f"Mod Name: {mod.get('ModName')}")
        self.mod_creator_label.setText(f"Creator: {mod.get('CreatorId')}")
        if mod.get("Enabled") == "True":
            self.mod_enabled_state.setText("Enabled")
        else:
            self.mod_enabled_state.setText("Disabled")
        self.mod_workshop_description.setPlainText(f"{mod.get('WorkshopDescription')}")

        if mod.get("IsFromWorkshop") == "True":
            self.convert_from_workshop_btn.show()
        else:
            self.convert_from_workshop_btn.hide()

    def load_settings(self):
        try:
            with open("settings.json", "r") as f:
                settings = json.load(f)

        except (FileNotFoundError, json.JSONDecodeError):

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
                "Select Game Executable",
                start_dir, # Starting Path
                "Excecutable Files (*.exe)"
            )[0]
        
            if game_path:
                file_path = Path(game_path)
                drive = file_path.drive

                if drive == "C:":
                    workshop_dir = f"{drive}/Program Files (x86)/Steam/steamapps/workshop/content/1118520"
                else:
                    workshop_dir = f"{drive}/SteamLibrary/steamapps/workshop/content/1118520"

                settings = {"GameDir": game_path,
                            "WorkshopDir": workshop_dir}
            
            with open("settings.json", "w") as f:
                json.dump(settings, f, indent=4)
        
        return settings

    def save_settings(self):
        with open("settings.json", "w") as f:
            json.dump(self.settings, f, indent=4)

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


if __name__ == "__main__":
    app = QApplication()

    window = MainWindow()
    window.show()

    app.exec()

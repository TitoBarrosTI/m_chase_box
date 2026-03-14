# MCacheBox 
# Copyright (c) 2026 Tito de Barros Junior 
# Licensed under the MIT License

import os, sys

from src.popup_hint import PopupHint

from PySide6.QtGui import QPixmap, QStandardItemModel, QStandardItem
from PySide6.QtWidgets import QApplication, QAbstractItemView, QListWidget, QMessageBox, QMainWindow, QMenu, QToolButton
from PySide6.QtCore import Qt, QSize, QEvent, QSettings, QTimer
from PySide6.QtUiTools import loadUiType
from functools import partial

import re
from utils.imap import *

# === TO EMBED DESIGNER IN EXECUTABLE ===
def resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path) # type: ignore
    return os.path.join(os.path.abspath("."), relative_path)

ui_path = resource_path("ui/main_window.ui")
Ui_MainWindow, BaseClass = loadUiType(ui_path) # type: ignore
# ======================================

class MainWindow(BaseClass, Ui_MainWindow):
    def __init__(self):
        super().__init__()        
        self.setupUi(self)
        self.setFixedSize(self.size())
        self.settings = QSettings("TitoDev", "MChaseBox")

        # popup_hint (resume)
        self._popup = PopupHint(dark_mode=True)
        self._last_item = None
        self._hide_timer = QTimer(singleShot=True)
        self._hide_timer.timeout.connect(self._popup.hide)
        self.treeMailResponse.setMouseTracking(True)
        self.treeMailResponse.viewport().installEventFilter(self)
        
        # signal connections 
        self.btnEdtPositions.clicked.connect(partial(self.on_click_edit_list_config, self.lnEdtPositionsConfig))
        self.btnEdtDomains.clicked.connect(partial(self.on_click_edit_list_config, self.lnEdtDomainsConfig))
        self.btnEdtExcludedTerms.clicked.connect(partial(self.on_click_edit_list_config, self.lnEdtExcludedTermsConfig))
        self.btnEdtWorkModes.clicked.connect(partial(self.on_click_edit_list_config, self.lnEdtWorkModesConfig))

        self.btnFetchMail.clicked.connect(self.on_click_fetch_emails)
        self.btnCloseApp.clicked.connect(self.on_click_btn_close)

        self.lnEdtPositionsConfig.returnPressed.connect(self.add_item_position)
        self.lnEdtDomainsConfig.returnPressed.connect(self.add_item_domain)
        self.lnEdtExcludedTermsConfig.returnPressed.connect(self.add_item_excluded_term)
        self.lnEdtWorkModesConfig.returnPressed.connect(self.add_item_work_mode)        
        
        # fixed filter options buttons
        menuFIXDomain = QMenu(self)
        self.btnAddFixedPositions.clicked.connect(self.add_fixed_positions)
        self.btnAddFixedDomains.clicked.connect(lambda: self.add_fixed_domains('ti remote'))
        self.btnAddFixedExcludedTerms.clicked.connect(self.add_fixed_excluded_terms)
        self.btnAddFixedWorkModes.clicked.connect(self.add_fixed_work_modes)

        for name in ("ti remote", "generalists", "ats","all"):
            act = menuFIXDomain.addAction(name)
            act.triggered.connect(partial(self.add_fixed_domains, name))

        self.btnAddFixedDomains.setMenu(menuFIXDomain)
        self.btnAddFixedDomains.setPopupMode(QToolButton.InstantPopup)

        # clear buttons
        self.btnClearMailList.clicked.connect(self.clear_email_list)
        self.btnClearPositionsList.clicked.connect(self.clear_positions_list)
        self.btnClearDomainsList.clicked.connect(lambda: self.clear_items_list([self.lstDomainsConfig,self.lstDomains]))
        self.btnClearExcludedTermsList.clicked.connect(self.clear_excluded_terms_list)
        self.btnClearWorkModesList.clicked.connect(self.clear_work_modes_list)

        self.treeMailResponse.itemClicked.connect(self.open_email)
        self.edtCriteria.returnPressed.connect(self.on_click_fetch_emails)
        self.cbxIMAP.currentIndexChanged.connect(lambda: self.on_combo_change(self.cbxIMAP.currentIndex()))

        # events
        self.lstPositions.installEventFilter(self)
        self.lstPositionsConfig.installEventFilter(self)
        # Trigger the remove item action on double-click
        self.lstPositionsConfig.itemDoubleClicked.connect(lambda: self.remove_selected_item(self.lstPositionsConfig, self.lstPositions))
        self.lstDomainsConfig.itemDoubleClicked.connect(lambda: self.remove_selected_item(self.lstDomainsConfig, self.lstDomains))

        # icons works
        self.tabWidget.setCurrentIndex(2)
        self.tabWidget.currentChanged.connect(self.update_icon)
        self.update_icon(self.tabWidget.currentIndex())

        # retrieving data in the interface
        self.load_listwidget(self.lstPositionsConfig, "positions_cfg")
        self.load_listwidget(self.lstPositions, "positions")
        self.load_listwidget(self.lstDomainsConfig, "domains_cfg")
        self.load_listwidget(self.lstDomains, "domains")
        self.load_listwidget(self.lstExcludedTermsConfig, "excluded_terms_cfg")
        self.load_listwidget(self.lstExcludedTerms, "excluded_terms")
        self.load_listwidget(self.lstWorkModesConfig, "work_mode_cfg")
        self.load_listwidget(self.lstWorkModes, "work_modes")

    def update_icon(self, index):
        if index == 0:
            self.lblIconSearch.setPixmap(QPixmap("static/icons/search_50.png"))
        if index == 1:
            self.lblIconConfig.setPixmap(QPixmap("static/icons/settings_50.png"))
        if index == 2:
            self.lblIconAbout.setPixmap(QPixmap("static/icons/about_50.png"))

    def on_click_edit_list_config(self,lnEdt_to_focus) -> None:
        self.tabWidget.setCurrentIndex(1)
        lnEdt_to_focus.setFocus()

    def on_click_fetch_emails(self) -> None:
        self.treeMailResponse.clear()
        self.lstMailBody.clear()
        self.lblRetrievedEmails.setText('retrieved emails:')
        self.lblVacancies.setText('founded vacancies:')

        server_imap = self.cbxIMAP.currentText().strip()

        if not server_imap:
            self.show_message("IMAP Server not specified")
            return
        
        if not self.lstPositionsConfig.count():
            self.show_message("no position specified")
            return
        
        my_positions = []
        
        for i in range(self.lstPositionsConfig.count()):
            text_position = self.lstPositionsConfig.item(i).text().lower()
            my_positions.append(text_position)

        # sets to the correct search page results
        self.tabWidget.setCurrentIndex(0)
        
        # starts the search
        fetch_grouped_positions(server_imap,
                                self.cbxPreFilter,
                                self.progressBar,
                                self.show_message,
                                self.btnClearMailList, 
                                self.lstPositionsConfig,
                                self.lstDomainsConfig,
                                self.lstExcludedTermsConfig,
                                self.lstWorkModesConfig,
                                self.edtCriteria,
                                self.edtAccount,
                                self.lblRetrievedEmails,
                                self.cbxStarred,
                                self.cbxUnseen,
                                my_positions=my_positions,
                                max_emails=self.spinBoxMAXEmails.value(),
                                treeMailResponse=self.treeMailResponse
                            )

    def add_item_position(self):
        text = self.lnEdtPositionsConfig.text().strip()
        if not text:
            return

        self.lstPositionsConfig.addItem(text)
        self.lstPositions.addItem(text)
        self.lnEdtPositionsConfig.clear()

        self.invoke_save_listwidgets()

    def add_item_domain(self):
        text:str = self.lnEdtDomainsConfig.text().strip()
        
        if not text:
            return
        
        # if not self.valid_domain(text):
        #     self.show_message(f'{text} is a not valid domain, please correct it.')
        #     return

        self.lstDomainsConfig.addItem(text)
        self.lstDomains.addItem(text)
        self.lnEdtDomainsConfig.clear()

        self.invoke_save_listwidgets()

    def add_item_excluded_term(self):
        text = self.lnEdtExcludedTermsConfig.text().strip()
        if not text:
            return

        self.lstExcludedTermsConfig.addItem(text)
        self.lnEdtExcludedTermsConfig.clear()

        self.invoke_save_listwidgets()

    def add_item_work_mode(self):
        text = self.lnEdtWorkModesConfig.text().strip()
        if not text:
            return

        self.lstWorkModesConfig.addItem(text)
        self.lnEdtWorkModesConfig.clear()

        self.invoke_save_listwidgets()

    def add_fixed_positions(self):
        # retrieves the items that already exist in the QListWidget.
        existing = {
            self.lstPositionsConfig.item(i).text().lower()
            for i in range(self.lstPositionsConfig.count())
        }

        FIXED_POSITIONS = [
            "delphi",
            "python",
            "analyst",
            "developer",
            "desenvolvedor",
            "programmer",
            "programador",
            "backend",
            "frontend",
            "designer",
            "dba",
            "support",
        ]

        for position in FIXED_POSITIONS:
            if position.lower() not in existing:
                self.lstPositionsConfig.addItem(position)
                self.lstPositions.addItem(position)

    def add_fixed_excluded_terms(self):
        # retrieves the items that already exist in the QListWidget.
        existing = {
            self.lstExcludedTermsConfig.item(i).text().lower()
            for i in range(self.lstExcludedTermsConfig.count())
        }

        EXCLUDED_TERMS = [
            "híbrido",
            "hybrid",
            "2x por semana",
            "3x por semana",
            "2x per week",
            "3x per week",            
            "presencialmente",
            "presententially",
            "estágio",
        ]

        for position in EXCLUDED_TERMS:
            if position.lower() not in existing:
                self.lstExcludedTermsConfig.addItem(position)
                self.lstExcludedTerms.addItem(position)

    def add_fixed_work_modes(self):
        # retrieves the items that already exist in the QListWidget
        existing = {
            self.lstWorkModesConfig.item(i).text().lower()
            for i in range(self.lstWorkModesConfig.count())
        }

        WORK_MODES = [
            "home office",
            "remoto",
            "remote",
            "trabalho em casa",
            "trabalhe em casa",
            "trabalhe de casa",
        ]

        for work_mode in WORK_MODES:
            if work_mode.lower() not in existing:
                self.lstWorkModesConfig.addItem(work_mode)
                self.lstWorkModes.addItem(work_mode)
        ...

    def add_fixed_domains(self,mode_domain="ti remote"):
        # ats = Applicant Tracking System

        existing = {
            self.lstDomainsConfig.item(i).text().lower()
            for i in range(self.lstDomainsConfig.count())
        }

        FIXED_DOMAINS = []
        
        TI_REMOTE = [
            "linkedin.com",
            "remotar.com.br",
            "programathor.com.br",
            "geekhunter.com.br",
            "apinfo.com",
            "glassdoor.com",
        ]

        GENERALISTS = [
            "indeed.com",
            "vagas.com.br",
            "catho.com.br",
            "solidesvagas.com.br",            
            "infojobs.com.br",
            "trabalhabrasil.com.br",
            "empregos.com.br",
        ]

        ATS = [
            "gupy.io",
            "solides.com.br",
        ]
        
        match mode_domain:
            case "ti remote":
                FIXED_DOMAINS = TI_REMOTE
            case "generalists":
                FIXED_DOMAINS = GENERALISTS
            case "ats":
                FIXED_DOMAINS = ATS
            case "all":
                FIXED_DOMAINS = TI_REMOTE + GENERALISTS + ATS

        for domain in FIXED_DOMAINS:
            if domain.lower() not in existing:
                self.lstDomainsConfig.addItem(domain)
                self.lstDomains.addItem(domain)

    def adjust_lists(self):
        self.treeMailResponse.setAlternatingRowColors(True)
        self.treeMailResponse.setRootIsDecorated(False)
        self.treeMailResponse.header().setStretchLastSection(True)
        
        # 1. We define the style globally ONCE for all QListWidgets.
        # This prevents the Qt CSS engine from processing the string 8 times.
        self.setStyleSheet("""
            QListWidget::item {
                height: 18px;
                margin: 0px;
                padding: 0px;
            }
        """)

        LIST_COMPONENTS = [
            self.lstPositionsConfig, self.lstDomainsConfig,
            self.lstExcludedTermsConfig, self.lstWorkModesConfig,
            self.lstPositions, self.lstDomains,
            self.lstExcludedTerms, self.lstWorkModes
        ]

        high_item = 18

        # 2. Loop only for technical configurations of each list.
        for lst in LIST_COMPONENTS:
            # Enables Qt performance optimization for lists with identical items.
            lst.setUniformItemSizes(True)
            lst.setSpacing(0)

            # Adjusts the SizeHint of each existing item.
            for i in range(lst.count()):
                item = lst.item(i)
                item.setSizeHint(QSize(item.sizeHint().width(), high_item))
    
    def remove_selected_item(self, list_a, list_b):
        row = list_a.currentRow()

        if row < 0:
            return

        item_text = list_a.item(row).text()

        reply = QMessageBox.question(
            self,
            "Exclusion confirm",
            f"Remove '{item_text}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes: # type: ignore
            list_a.takeItem(row)
            list_b.takeItem(row)

    def clear_email_list(self):
        self.treeMailResponse.clear()
        self.lstMailBody.clear()

    def clear_positions_list(self):
        self.lstPositionsConfig.clear()
        self.lstPositions.clear()

    def clear_domains_list(self):
        self.lstDomainsConfig.clear()
        self.lstDomains.clear()

    def clear_work_modes_list(self):
        self.lstWorkModesConfig.clear()
        self.lstWorkModes.clear()

    def clear_excluded_terms_list(self):
        self.lstExcludedTermsConfig.clear()
        self.lstExcludedTerms.clear()

    def clear_items_list(self, listWidgets):
        if not isinstance(listWidgets, list):
            listWidgets = [listWidgets]

        for widget in listWidgets:
            widget.clear()
  
    def save_listwidget(self, listWidget, key):
        items = []
        for i in range(listWidget.count()):
            items.append(listWidget.item(i).text())

        self.settings.setValue(key, items)

    def load_listwidget(self, listWidget, key):
        items = self.settings.value(key, [])

        if isinstance(items, str):
                items = [items]

        if items:
            for item in items:
                listWidget.addItem(item)

    def invoke_save_listwidgets(self):
        self.save_listwidget(self.lstPositionsConfig, "positions_cfg")
        self.save_listwidget(self.lstPositions, "positions")
        self.save_listwidget(self.lstDomainsConfig, "domains_cfg")
        self.save_listwidget(self.lstDomains, "domains")
        self.save_listwidget(self.lstExcludedTermsConfig, "excluded_terms_cfg")
        self.save_listwidget(self.lstExcludedTerms, "excluded_terms")
        self.save_listwidget(self.lstWorkModesConfig, "work_mode_cfg")
        self.save_listwidget(self.lstWorkModes, "work_mode")

    def valid_domain(self,domain):
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, domain) is not None
    
    def extract_email(self, text: str) -> str:
        match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
        if match:
            return match.group(0)
        return "no email"
    
    def open_email(self, item, collumn):
        resume = item.data(0, Qt.UserRole)
        email_id = item.data(1, Qt.UserRole)
        topic = item.data(2, Qt.UserRole)
        body = item.data(3, Qt.UserRole)
        self.lstMailBody.clear()

        # subject in first line
        self.lstMailBody.addItem(f'|SUBJECT| {topic}')
        self.lstMailBody.addItem('')
        
        for line in body.splitlines():
            self.lstMailBody.addItem(f'{line}')

        # obtaining effective job key words 
        job_match = [
            self.lstPositionsConfig.item(i).text()
            for i in range(self.lstPositionsConfig.count())
            if self.lstPositionsConfig.item(i).text().lower() in body.lower()
        ]

        self.lblVacancies.setText(f'founded vacancies: {job_match}')

    def on_combo_change(self, index):
        if index < 0:
            return

        full_server_name = self.cbxIMAP.itemText(index).lower()
        parts = full_server_name.split('.')
        
        # If it ends in something like .com.br (it has 4+ parts and the second to last one is 'com')
        if len(parts) >= 4 and parts[-2] == 'com':
            # Ex: ['imap', 'uol', 'com', 'br'] -> take the 3rd one from the back to the front ('uol')
            brand = parts[-3]
        else:
            # Ex: ['imap', 'mail', 'yahoo', 'com'] -> take the 2nd one from the back to the front ('yahoo')
            # Ex: ['imap', 'gmail', 'com'] -> take the 2nd one from the back to the front ('gmail')
            brand = parts[-2]

        # Update your label by capitalizing the first letter.
        self.lblBrandIMAP.setText(brand.capitalize())

    def show_message(self, text:str, seconds=3):
        self.lblMsgs.setText(text)
        QTimer.singleShot(seconds * 1000, self.lblMsgs.clear)

    def eventFilter(self, obj, event):
        # Captures the DELETE key for position lists.
        if event.type() == QEvent.KeyPress and event.key() == Qt.Key_Delete:
            if obj == self.lstPositions:
                self.remove_selected_item(self.lstPositions, self.lstPositionsConfig)
                return True
            elif obj == self.lstPositionsConfig:
                self.remove_selected_item(self.lstPositionsConfig, self.lstPositions)
                return True

        # Captures mouse movement and cursor output to the popup
        if obj is self.treeMailResponse.viewport():  # <-- viewport, não a tree
            if event.type() == QEvent.Type.MouseMove:
                # event.pos() aqui já é relativo à tree, não precisa mapear
                item = self.treeMailResponse.itemAt(event.pos())

                if item and item is not self._last_item:
                    self._last_item = item
                    self._hide_timer.stop()
                    data = item.data(0, Qt.ItemDataRole.UserRole)
                    if data:
                        self._popup.set_content(data)
                        self._popup.show_near_cursor()

                elif not item:
                    self._hide_timer.start(250)
                    self._last_item = None

            elif event.type() == QEvent.Type.Leave:
                self._hide_timer.start(300)
                self._last_item = None

        return super().eventFilter(obj, event)    
    
    def on_click_btn_close(self):
        self.invoke_save_listwidgets()
        QApplication.quit()
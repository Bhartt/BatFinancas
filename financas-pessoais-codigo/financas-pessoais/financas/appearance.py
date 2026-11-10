"""Temas locais e saudação pelo relógio do computador do usuário."""
from datetime import datetime
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication
from .typography import register_fonts

PALETTES = {
 'escuro':dict(bg='#17181c',surface='#22242a',alternate='#282b32',sidebar='#101115',
               text='#eceef3',muted='#aeb3c0',border='#424651',hover='#343842',selected='#414c61',
               primary='#c8cacc',primary_text='#18191d',accent='#b9bdc1',error='#ffada6',
               income='#a7c9b9',expense='#ddb0ac',disabled='#777d8b',chart='#8498b1',
               save_bg='#22242a',save_text='#eceef3',save_top='#c4c7ca',save_bottom='#92979c',save_icon='#242628'),
 'claro':dict(bg='#f4f5f8',surface='#ffffff',alternate='#edf0f5',sidebar='#e6e9ef',
              text='#20242e',muted='#505b6c',border='#bec5d1',hover='#e0e5ef',selected='#d0d9e9',
              primary='#494d51',primary_text='#ffffff',accent='#60666c',error='#a32b27',
              income='#1c684d',expense='#a23938',disabled='#737c8b',chart='#577396',
              save_bg='#3b3e42',save_text='#ffffff',save_top='#d3d5d7',save_bottom='#a6abb0',save_icon='#242628')
}


def current_theme():
    app=QApplication.instance()
    mode=app.property('batTheme') if app else None
    return mode if mode in PALETTES else 'escuro'


def colors(mode=None):
    return PALETTES[mode or current_theme()]


def greeting(now=None):
    """datetime.now() usa o fuso local do host que está executando o app."""
    hour=(now or datetime.now()).hour
    salutation='Bom dia' if 5<=hour<12 else 'Boa tarde' if 12<=hour<18 else 'Boa noite'
    return salutation+', bem-vindo à sua BatFinanças!'


def stylesheet(mode='escuro'):
    c=colors(mode)
    return '''
QWidget { background:%(bg)s; color:%(text)s; font-family:"Nunito","Segoe UI","DejaVu Sans"; font-size:13px; }
QMainWindow { background:%(bg)s; }
QLabel#title { font-size:27px; font-weight:600; }
QLabel#brand { font-size:21px; font-weight:600; color:%(accent)s; }
QLabel#greeting { font-size:19px; font-weight:600; }
QLabel#muted { color:%(muted)s; }
QLabel#error { color:%(error)s; }
QWidget#sidebar,QWidget#sidebar QLabel { background:%(sidebar)s; }
QPushButton { background:%(alternate)s; border:1px solid %(border)s; border-radius:7px; padding:9px 13px; font-weight:600; }
QPushButton:hover { background:%(hover)s; }
QPushButton:focus { border:2px solid %(accent)s; }
QPushButton:disabled { color:%(disabled)s; }
QPushButton#primary { background:%(primary)s; color:%(primary_text)s; font-weight:600; }
QPushButton#metric { text-align:left; padding:18px; font-size:15px; }
QLineEdit,QTextEdit,QComboBox,QDateEdit,QSpinBox { background:%(surface)s; border:1px solid %(border)s; border-radius:5px; padding:7px; selection-background-color:%(selected)s; selection-color:%(text)s; }
QLineEdit:focus,QTextEdit:focus,QComboBox:focus,QDateEdit:focus,QSpinBox:focus { border:1px solid %(accent)s; }
QLineEdit:disabled,QTextEdit:disabled,QComboBox:disabled,QDateEdit:disabled,QSpinBox:disabled { color:%(disabled)s; background:%(bg)s; border-color:%(border)s; }
QComboBox QAbstractItemView { background:%(surface)s; selection-background-color:%(selected)s; selection-color:%(text)s; }
QTableWidget { background:%(surface)s; alternate-background-color:%(alternate)s; gridline-color:%(border)s; border:1px solid %(border)s; }
QTableWidget::item { padding:6px; }
QTableWidget::item:selected { background:%(selected)s; color:%(text)s; }
QHeaderView::section { background:%(alternate)s; color:%(text)s; padding:8px; border:0; border-bottom:1px solid %(border)s; }
QListWidget { border:0; background:%(sidebar)s; padding:5px; }
QScrollArea { border:0; }
QGroupBox { border:1px solid %(border)s; border-radius:7px; margin-top:10px; padding:14px; }
QGroupBox::title { subcontrol-origin:margin; left:12px; padding:0 4px; }
QTabBar::tab { padding:10px 16px; background:%(alternate)s; }
QTabBar::tab:selected { background:%(selected)s; }
QProgressBar { border:1px solid %(border)s; border-radius:4px; text-align:center; background:%(surface)s; }
QProgressBar::chunk { background:%(income)s; }
QProgressBar#debtProgress::chunk { background:%(accent)s; }
QToolTip { color:%(text)s; background:%(surface)s; border:1px solid %(border)s; padding:5px; }
''' % c


def apply_theme(app,mode):
    if mode not in PALETTES:
        raise ValueError('Escolha o modo claro ou escuro.')
    register_fonts(app)
    c=colors(mode);palette=QPalette()
    for role,key in ((QPalette.Window,'bg'),(QPalette.WindowText,'text'),(QPalette.Base,'surface'),
                     (QPalette.AlternateBase,'alternate'),(QPalette.Text,'text'),(QPalette.Button,'alternate'),
                     (QPalette.ButtonText,'text'),(QPalette.Highlight,'selected'),(QPalette.HighlightedText,'text'),
                     (QPalette.ToolTipBase,'surface'),(QPalette.ToolTipText,'text')):
        palette.setColor(role,QColor(c[key]))
    palette.setColor(QPalette.Disabled,QPalette.Text,QColor(c['disabled']))
    palette.setColor(QPalette.Disabled,QPalette.ButtonText,QColor(c['disabled']))
    app.setProperty('batTheme',mode);app.setPalette(palette);app.setStyleSheet(stylesheet(mode))

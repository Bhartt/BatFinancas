"""Componentes reutilizáveis e formulários acessíveis por teclado."""
from datetime import date
from PySide6.QtCore import Qt, QDate, QRect, QSize, QPoint,QRectF
from PySide6.QtGui import QIcon,QPainter,QColor,QPixmap,QPen,QPainterPath
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
 QTableWidgetItem, QHeaderView, QAbstractItemView, QComboBox, QDateEdit, QDialog, QDialogButtonBox,
 QFormLayout, QLineEdit, QTextEdit, QScrollArea, QStyle, QLayout)
from .money import iso

from .appearance import stylesheet,colors
from .effects import SaveButton

STYLE = stylesheet('escuro')


def label(text, style=None):
    w = QLabel(text)
    w.setWordWrap(True)
    if style:
        w.setObjectName(style)
    return w


def refresh_button_icon(w):
    icon=w.property('actionIcon')
    if not icon:return
    pixmap=QPixmap(32,32);pixmap.fill(Qt.transparent)
    painter=QPainter(pixmap);painter.setRenderHint(QPainter.Antialiasing);painter.scale(2,2)
    pen=QPen(QColor(colors()['primary_text' if w.objectName()=='primary' else 'text']),1.4)
    pen.setCapStyle(Qt.RoundCap);pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen);painter.setBrush(Qt.NoBrush)
    def line(points,close=False):
        path=QPainterPath();path.moveTo(*points[0])
        for point in points[1:]:path.lineTo(*point)
        if close:path.closeSubpath()
        painter.drawPath(path)
    if icon=='add':
        line([(8,3),(8,13)]);line([(3,8),(13,8)])
    elif icon=='edit':
        line([(3,10),(10,3),(13,6),(6,13),(3,13)],True);line([(8.5,4.5),(11.5,7.5)])
    elif icon=='delete':
        line([(3,4),(13,4)]);line([(6,2),(10,2)])
        line([(4,4),(5,14),(11,14),(12,4)]);line([(7,7),(7,11)]);line([(9,7),(9,11)])
    elif icon=='open':
        line([(2,4),(7,4),(9,6),(14,6),(13,13),(2,13)],True)
    elif icon=='refresh':
        painter.drawArc(QRectF(3,3,10,10),45*16,285*16);line([(12.5,2.5),(12.5,6.5),(8.5,6.5)])
    elif icon=='ok':line([(3,8),(6,11),(13,4)])
    elif icon in ('back','next'):
        line([(3,8),(13,8)]);line([(7,3),(2,8),(7,13)] if icon=='back' else [(9,3),(14,8),(9,13)])
    else:
        painter.drawRoundedRect(QRectF(3,2,10,12),1,1);line([(6,2),(6,6),(10,6),(10,2)])
    painter.end();w.setIcon(QIcon(pixmap))


def button(text, callback=None, icon='add', primary=False):
    w = SaveButton(text) if icon=='save' else QPushButton(text)
    if primary:
        w.setObjectName('primary')
    w.setProperty('actionIcon',icon)
    refresh_button_icon(w)
    if callback:
        w.clicked.connect(lambda checked=False: callback())
    return w


def combo(items, include_empty=None):
    c = QComboBox()
    if include_empty is not None:
        c.addItem(include_empty,None)
    for item in items:
        if isinstance(item,tuple):
            c.addItem(str(item[0]),item[1])
        else:
            c.addItem(str(item),item)
    c.setMinimumContentsLength(12)
    c.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
    return c


def set_combo(widget, data):
    index = widget.findData(data)
    if index >= 0:
        widget.setCurrentIndex(index)


def date_edit(value=None):
    w = QDateEdit()
    w.setCalendarPopup(True)
    w.setDisplayFormat('dd/MM/yyyy')
    w.setDate(QDate.fromString(iso(value or date.today()),'yyyy-MM-dd'))
    w.setMinimumDate(QDate(1900,1,1))
    return w


def date_value(w):
    return w.date().toString('yyyy-MM-dd')


class NumberItem(QTableWidgetItem):
    def __lt__(self,other):
        a,b = self.data(Qt.UserRole+1),other.data(Qt.UserRole+1)
        return a < b if a is not None and b is not None else self.text().casefold() < other.text().casefold()


class Table(QTableWidget):
    def __init__(self, headers):
        super().__init__(0,len(headers))
        self.setHorizontalHeaderLabels(headers)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.verticalHeader().hide()
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.horizontalHeader().setStretchLastSection(True)
        self.setSortingEnabled(True)
        self.setMinimumHeight(180)
        self.setAccessibleName('Tabela de registros; selecione uma linha para editar')

    def fill(self, rows):
        self.setSortingEnabled(False)
        self.setRowCount(len(rows))
        for i,(identifier,values) in enumerate(rows):
            for j,value in enumerate(values):
                sort = None
                if isinstance(value,tuple):
                    value,sort = value
                item = NumberItem(str(value if value is not None else ''))
                item.setData(Qt.UserRole,identifier)
                item.setData(Qt.UserRole+1,sort)
                self.setItem(i,j,item)
        self.setSortingEnabled(True)
        self.resizeColumnsToContents()
        for col in range(self.columnCount()):
            self.setColumnWidth(col,min(max(self.columnWidth(col),90),320))

    def ids(self):
        return [self.item(i.row(),0).data(Qt.UserRole) for i in self.selectionModel().selectedRows()]

    def selected_id(self):
        ids = self.ids()
        if not ids:
            raise ValueError('Selecione uma linha primeiro.')
        return ids[0]


class FormDialog(QDialog):
    def __init__(self,title,parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(580,600)
        root = QVBoxLayout(self)
        root.addWidget(label('Salve ou cancele este formulário para voltar às outras telas.','muted'))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        self.form = QFormLayout(content)
        self.form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.form.setRowWrapPolicy(QFormLayout.WrapLongRows)
        scroll.setWidget(content)
        root.addWidget(scroll)
        self.error = label('', 'error')
        root.addWidget(self.error)
        self.buttons = QDialogButtonBox()
        self.buttons.addButton(SaveButton('Salvar'),QDialogButtonBox.AcceptRole)
        self.buttons.addButton('Cancelar',QDialogButtonBox.RejectRole)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)
        self.fields = {}

    def add(self,key,title,widget):
        self.fields[key] = widget
        widget.setAccessibleName(title.replace('&',''))
        self.form.addRow(title,widget)
        return widget

    def hint(self,text):
        self.form.addRow(label(text,'muted'))

    def bind(self,callback):
        def submit():
            try:
                callback()
                self.accept()
            except (ValueError, __import__('sqlite3').IntegrityError) as exc:
                self.error.setText(str(exc) if isinstance(exc,ValueError) else 'Já existe um cadastro com esses dados ou há uma referência inválida.')
        self.buttons.accepted.connect(submit)


def page(title,subtitle,refresh=None):
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(24,20,24,20)
    layout.setSpacing(16)
    heading=QHBoxLayout();heading.addWidget(label(title,'title'),1)
    if refresh is not None:
        reload_button=button('Recarregar',refresh,'refresh')
        reload_button.setObjectName('reloadPage');reload_button.setAccessibleName('Recarregar informações de '+title)
        reload_button.setToolTip('Atualizar os dados exibidos nesta tela')
        heading.addWidget(reload_button)
    layout.addLayout(heading)
    layout.addWidget(label(subtitle,'muted'))
    return widget, layout


class FlowLayout(QLayout):
    """Quebra as ações em linhas para acompanhar o redimensionamento da janela."""
    def __init__(self):
        super().__init__()
        self.items=[]
        self.setContentsMargins(0,0,0,0)
        self.setSpacing(8)
    def addItem(self,item):self.items.append(item)
    def count(self):return len(self.items)
    def itemAt(self,index):return self.items[index] if 0<=index<len(self.items) else None
    def takeAt(self,index):return self.items.pop(index) if 0<=index<len(self.items) else None
    def expandingDirections(self):return Qt.Orientations()
    def hasHeightForWidth(self):return True
    def heightForWidth(self,width):return self.arrange(QRect(0,0,width,0),True)
    def setGeometry(self,rect):super().setGeometry(rect);self.arrange(rect,False)
    def sizeHint(self):return self.minimumSize()
    def minimumSize(self):
        size=QSize()
        for item in self.items:size=size.expandedTo(item.minimumSize())
        return size
    def arrange(self,rect,test):
        x,y,height=rect.x(),rect.y(),0
        for item in self.items:
            size=item.sizeHint()
            if x>rect.x() and x+size.width()>rect.right()+1:
                x=rect.x();y+=height+self.spacing();height=0
            if not test:item.setGeometry(QRect(QPoint(x,y),size))
            x+=size.width()+self.spacing();height=max(height,size.height())
        return y+height-rect.y()


def toolbar(layout, *widgets):
    row = FlowLayout()
    for widget in widgets:
        row.addWidget(widget)
    layout.addLayout(row)
    return row

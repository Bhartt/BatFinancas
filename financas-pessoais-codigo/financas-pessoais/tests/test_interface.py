"""Teste real dos widgets Qt, em modo sem monitor e sem acesso à rede."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('MPLCONFIGDIR','/tmp/financas-testes-mpl')
from pathlib import Path
import pytest
from PySide6.QtCore import QLocale,QLockFile,QDate,QTimer
from PySide6.QtWidgets import QApplication,QMessageBox,QDialog
from PySide6.QtTest import QTest
from financas.dialogs import EntryDialog,EntityDialog,ImportDialog
from financas.widgets import STYLE,set_combo
from financas.window import Window
from financas.db import Database
from financas.service import Finance

@pytest.fixture(scope='module')
def app():
    a=QApplication.instance() or QApplication([])
    from financas.localization import configure
    configure(a);a.setStyle('Fusion');a.setStyleSheet(STYLE)
    return a


def test_first_account_entry_close_reopen_and_pages(app,tmp_path,monkeypatch):
    errors=[]
    monkeypatch.setattr(QMessageBox,'warning',lambda *args:errors.append(args[2]))
    db=Database(tmp_path/'app'/'financas.sqlite3');f=Finance(db)
    w=Window(f);w.show();app.processEvents()
    d=EntityDialog(f,'accounts',w)
    d.fields['name'].setText('Minha conta')
    d.fields['opening'].setText('1.000,00')
    d.fields['reference'].setDate(QDate(2024,1,1))
    d.save()
    d=EntryDialog(f,w)
    d.fields['description'].setText('Primeira compra')
    d.fields['amount'].setText('123,45')
    d.fields['category_id'].setCurrentIndex(1)
    set_combo(d.fields['status'],'pago')
    for field in ('competence','due','paid'):d.fields[field].setDate(QDate(2024,1,15))
    d.save();w.refresh()
    account=db.one('SELECT id FROM accounts')['id']
    assert f.balance(account)==87655
    set_combo(w.period,'Intervalo personalizado');w.start.setDate(QDate(2024,1,1));w.end.setDate(QDate(2024,12,31));w.refresh()
    for index in range(8):
        w.nav.setCurrentRow(index);app.processEvents()
        assert w.stack.currentIndex()==index
    w.resize(900,680);app.processEvents()
    assert w.width()==900
    w.drill_metric('expense');assert w.entries_table.rowCount()==1
    actual_category=f.entries()[0]['category_id']
    w.drill_metric('expense',actual_category);assert w.entries_table.rowCount()==1
    other_category=db.one('SELECT id FROM categories WHERE id<>?',(actual_category,))['id']
    w.drill_metric('expense',other_category);assert w.entries_table.rowCount()==0
    QTimer.singleShot(100,lambda:[dialog.reject() for dialog in app.topLevelWidgets() if isinstance(dialog,QDialog)])
    w.manual()
    w.resize(1380,950);app.processEvents()
    w.close();db.close()
    db=Database(tmp_path/'app'/'financas.sqlite3');f=Finance(db)
    assert f.balance(account)==87655
    w=Window(f);w.show();app.processEvents();w.close();db.close()
    assert not errors


def test_import_dialog_preview_and_commit(app,finance,tmp_path,monkeypatch):
    path=tmp_path/'arquivo.csv'
    path.write_text('Descrição;Valor;Competência\nMercado;25,50;15/01/2024\nErro;x;15/01/2024\n',encoding='utf-8')
    d=ImportDialog(finance,path)
    set_combo(d.account,finance.a);set_combo(d.category,finance.category)
    d.make_preview()
    assert len(d.preview)==2 and d.preview[1]['error']
    monkeypatch.setattr(QMessageBox,'question',lambda *args:QMessageBox.Yes)
    monkeypatch.setattr(QMessageBox,'information',lambda *args:None)
    d.commit()
    assert len(finance.entries())==1 and finance.balance(finance.a)==100000
    imported=finance.entries()[0]
    assert imported['status']=='pendente'
    finance.bulk_status([imported['id']],'pago','2024-01-15')
    assert finance.balance(finance.a)==97450


def test_exclusive_lock(tmp_path,app):
    path=str(tmp_path/'app.lock')
    first,second=QLockFile(path),QLockFile(path)
    first.setStaleLockTime(0);second.setStaleLockTime(0)
    assert first.tryLock(0)
    assert not second.tryLock(0)
    first.unlock()
    assert second.tryLock(0)
    second.unlock()


def test_qt_standard_buttons_in_portuguese(app):
    box=QMessageBox(QMessageBox.Question,'Confirmar','Confirma?',QMessageBox.Yes|QMessageBox.No)
    assert box.button(QMessageBox.Yes).text().replace('&','')=='Sim'
    assert box.button(QMessageBox.No).text().replace('&','')=='Não'

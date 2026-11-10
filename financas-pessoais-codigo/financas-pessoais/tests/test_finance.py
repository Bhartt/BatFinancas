from datetime import date
import json
import sqlite3
import pytest
from financas.db import Database
from financas.service import Finance
from financas.money import cents,brl,advance,split_cents
from financas.reports import preview_import,commit_import,export_csv,read_csv,export_pdf,report_tables


def test_money_and_months():
    assert cents('R$ 1.234,56')==123456
    assert cents('1234.56')==123456
    assert cents('-0,01')==-1
    assert brl(123456)=='R$ 1.234,56'
    assert brl(-1)=='-R$ 0,01'
    for invalid in ('1,234','1.000.00','abc','NaN'):
        with pytest.raises(ValueError):cents(invalid)
    assert advance('2024-01-31',1)=='2024-02-29'
    assert advance('2024-01-31',2)=='2024-03-31'
    assert advance('2024-02-29',1,'anual')=='2025-02-28'
    assert advance('2024-01-31',2,'semanal')=='2024-02-14'
    assert split_cents(10000,3)==[3334,3333,3333]


def test_balance_status_edits_and_reopen(finance,entry):
    f=finance
    identifier=f.save_entry(entry)
    assert f.balance(f.a)==89999
    assert f.summary('2024-01-01','2024-01-31')['expense']==10001
    for status in ('previsto','pendente','cancelado'):
        entry['status']=status;f.save_entry(entry,identifier)
        assert f.balance(f.a)==100000
    entry.update(status='pago',amount=22222);f.save_entry(entry,identifier)
    assert f.balance(f.a)==77778
    f.db.close();f.db=Database(f.db.path)
    assert f.balance(f.a)==77778
    f.delete_entries([identifier]);assert f.balance(f.a)==100000
    assert f.summary('2024-01-01','2024-01-31')['income']==0


def test_transfer_atomic_and_no_income(finance,entry):
    f=finance;entry.update(kind='transferência',target_id=f.b)
    identifier=f.save_entry(entry)
    assert f.balance(f.a)==89999 and f.balance(f.b)==15001
    s=f.summary('2024-01-01','2024-12-31')
    assert s['income']==s['expense']==0
    entry['target_id']=f.a
    with pytest.raises(ValueError):f.save_entry(entry,identifier)
    assert f.balance(f.a)==89999 and f.balance(f.b)==15001
    f.delete_entries([identifier]);assert f.balance(f.a)==100000 and f.balance(f.b)==5000


def test_atomic_bulk_and_import(finance,entry):
    f=finance
    entry['status']='pendente';expense=f.save_entry(entry)
    entry.update(kind='receita',status='pendente');income=f.save_entry(entry)
    with pytest.raises(ValueError):f.bulk_status([expense,income],'pago','2024-01-15')
    assert f.balance(f.a)==100000
    assert all(e['status']=='pendente' for e in f.entries())
    valid=dict(entry,status='recebido');invalid=dict(valid,amount=-100)
    with pytest.raises(ValueError):commit_import(f,[{'entry':valid,'error':'','duplicate':False},{'entry':invalid,'error':'','duplicate':False}])
    assert len(f.entries())==2


def test_installments_exact_and_recurrence_idempotence(finance,entry):
    f=finance
    entry.update(amount=10000,competence='2024-01-31',due='2024-01-31',paid=None,status='previsto')
    sid=f.create_series(entry,'parcelamento',3)
    rows=f.db.rows('SELECT * FROM entries WHERE series_id=? ORDER BY occurrence',(sid,))
    assert [r['amount'] for r in rows]==[3334,3333,3333]
    assert [r['due'] for r in rows]==['2024-01-31','2024-02-29','2024-03-31']
    assert sum(r['amount'] for r in rows)==10000
    f.generate_series();assert len(f.entries())==3
    f.db.close();f.db=Database(f.db.path);f.generate_series();assert len(f.entries())==3
    f.delete_entries([rows[1]['id']]);f.generate_series()
    assert f.db.one('SELECT status FROM entries WHERE id=?',(rows[1]['id'],))['status']=='cancelado'
    sid2=f.create_series(entry,'recorrência',10,'semanal',2,'2024-03-01')
    recurring=f.db.rows('SELECT * FROM entries WHERE series_id=?',(sid2,))
    assert len(recurring)==3 and all(e['amount']==10000 for e in recurring)


def test_series_scopes_preserve_paid_dates(finance,entry):
    f=finance;entry.update(status='previsto',paid=None)
    sid=f.create_series(entry,'recorrência',4)
    rows=f.db.rows('SELECT * FROM entries WHERE series_id=? ORDER BY occurrence',(sid,))
    changed=dict(rows[1],description='Alterado',amount=20000,status='pago',paid='2024-02-15')
    f.edit_series(rows[1]['id'],changed,'esta e próximas')
    rows=f.db.rows('SELECT * FROM entries WHERE series_id=? ORDER BY occurrence',(sid,))
    assert [r['amount'] for r in rows]==[10001,20000,20000,20000]
    assert [r['status'] for r in rows]==['previsto','pago','previsto','previsto']
    f.delete_entries([rows[2]['id']],'esta e próximas');f.generate_series()
    assert len(f.db.rows('SELECT id FROM entries WHERE series_id=?',(sid,)))==2


def test_cards_invoice_partial_payment_refund_no_double_count(finance,entry):
    f=finance
    entry.update(card_id=f.card,account_id=None,amount=30000,competence='2024-01-21')
    purchase=f.save_entry(entry)
    e=f.db.one('SELECT * FROM entries WHERE id=?',(purchase,))
    assert e['invoice']=='2024-02' and e['due']=='2024-03-05'
    assert f.balance(f.a)==100000
    assert f.invoice_total(f.card,'2024-02')['remaining']==30000
    payment=dict(description='Pagamento',kind='pagamento de fatura',amount=10000,account_id=f.a,card_id=f.card,
                 invoice='2024-02',competence='2024-02-02',due='2024-02-02',paid='2024-02-02',status='pago')
    f.save_entry(payment)
    assert f.balance(f.a)==90000 and f.invoice_total(f.card)['remaining']==20000
    assert f.summary('2024-01-01','2024-12-31')['expense']==30000
    assert f.summary('2024-01-01','2024-12-31','caixa')['expense']==10000
    refund=dict(description='Devolução',kind='estorno',amount=5000,category_id=f.category,card_id=f.card,invoice='2024-02',
                competence='2024-02-03',due='2024-02-03',paid='2024-02-03',status='recebido')
    f.save_entry(refund)
    assert f.summary('2024-01-01','2024-12-31')['expense']==25000
    assert f.invoice_total(f.card)['remaining']==15000
    assert f.balance(f.a)==90000
    payment['amount']=15001
    with pytest.raises(ValueError):f.save_entry(payment)
    payment['amount']=15000;f.save_entry(payment)
    assert f.invoice_total(f.card)['remaining']==0 and f.balance(f.a)==75000


def test_closing_days_and_card_installments(finance,entry):
    f=finance;card=f.db.one('SELECT * FROM cards WHERE id=?',(f.card,))
    assert f.invoice_for(card,'2024-01-20')=='2024-01'
    assert f.invoice_for(card,'2024-01-21')=='2024-02'
    assert f.invoice_due(dict(card,due=31,closing=1),'2024-02')=='2024-02-29'
    entry.update(account_id=None,card_id=f.card,amount=10000,competence='2024-01-31',due='2024-01-31',paid=None,status='previsto')
    f.create_series(entry,'parcelamento',3)
    assert sum(e['amount'] for e in f.entries())==10000
    assert {e['invoice'] for e in f.entries()}=={'2024-02','2024-03','2024-04'}


def test_backup_restore_validation_and_retention(finance,entry,tmp_path):
    f=finance;f.save_entry(entry);backup=f.db.backup()
    f.save_entry(dict(entry,amount=5000));assert f.balance(f.a)==84999
    preventive=f.db.restore(backup)
    assert preventive.exists() and f.balance(f.a)==89999
    with sqlite3.connect(preventive) as c:assert c.execute('SELECT count(*) FROM entries').fetchone()[0]==2
    bad=tmp_path/'ruim.sqlite3';bad.write_bytes(b'nao e um banco')
    with pytest.raises(ValueError):f.db.restore(bad)
    assert f.balance(f.a)==89999
    f.db.set_setting('retention',2)
    for _ in range(5):f.db.backup('automatico',prune=True)
    assert len(list((f.db.path.parent/'backups').glob('automatico-*.sqlite3')))==2
    assert backup.exists() and preventive.exists()
    f.db.close();f.db=Database(f.db.path)
    assert f.balance(f.a)==89999


def test_schema_upgrade_preserves_data_and_backup(finance,entry):
    f=finance;identifier=f.save_entry(entry)
    f.db.conn.execute('DROP TABLE import_batches');f.db.conn.execute('DROP INDEX entries_status')
    f.db.conn.execute('PRAGMA user_version=1');f.db.close()
    f.db=Database(f.db.path)
    assert f.db.conn.execute('PRAGMA user_version').fetchone()[0]==2
    assert f.db.one('SELECT id FROM entries WHERE id=?',(identifier,))
    assert f.balance(f.a)==89999
    assert list((f.db.path.parent/'backups').glob('antes-migracao-*.sqlite3'))


def test_budget_goal_archives_and_date_bases(finance,entry):
    f=finance
    entry['paid']='2024-02-02';f.save_entry(entry)
    assert f.summary('2024-01-01','2024-01-31')['expense']==10001
    assert f.summary('2024-01-01','2024-01-31','caixa')['expense']==0
    assert f.balance(f.a,'2024-01-31')==100000
    f.save_entity('budgets',dict(month='2024-01',category_id=f.category,amount=10000))
    assert f.budget_progress('2024-01')[0]['available']==-1
    goal=f.save_entity('goals',dict(name='Meta',amount=50000,deadline='2025-01-01'))
    f.save_entity('contributions',dict(goal_id=goal,amount=20000,day='2024-02-01',notes=''))
    assert f.balance(f.a)==89999
    f.save_entity('accounts',dict(archived=1),f.a)
    assert f.balance(f.a)==89999
    with pytest.raises(ValueError):f.save_entry(entry)
    assert f.balance(f.a,'2023-12-31')==0


def test_csv_preview_errors_duplicates_and_export(finance,entry,tmp_path):
    f=finance
    rows=[{'Descrição':'Mercado','Valor':'1.234,56','Data':'02/01/2024'},
          {'Descrição':'Mercado','Valor':'1.234,56','Data':'02/01/2024'},
          {'Descrição':'Erro','Valor':'xxx','Data':'40/01/2024'}]
    mapping=dict(description='Descrição',amount='Valor',competence='Data')
    preview=preview_import(f,rows,mapping,f.a,f.category)
    assert not preview[0]['error'] and preview[1]['duplicate'] and preview[2]['error']
    assert len(f.entries())==0
    assert commit_import(f,preview)==1
    again=preview_import(f,rows,mapping,f.a,f.category)
    assert again[0]['duplicate']
    path=tmp_path/'dados.csv';export_csv(f.entries(),path)
    headers,csvrows=read_csv(path)
    assert csvrows[0]['Valor']=='1.234,56' and csvrows[0]['Competência']=='02/01/2024'
    allpath=tmp_path/'todos.json';f.db.export_all(allpath)
    assert len(json.loads(allpath.read_text())['tabelas']['accounts'])==2
    pdf=tmp_path/'relatorio.pdf';export_pdf(f,'2024-01-01','2024-03-31','competência',pdf)
    assert pdf.read_bytes().startswith(b'%PDF') and pdf.stat().st_size>2000


def test_future_realized_and_opening_reference_rejected(finance,entry):
    f=finance
    entry['paid']='2099-01-01'
    with pytest.raises(ValueError):f.save_entry(entry)
    entry['paid']='2023-12-31'
    with pytest.raises(ValueError):f.save_entry(entry)
    assert len(f.entries())==0


def test_cash_forecast_includes_open_card_invoices_once(finance,entry):
    f=finance
    entry.update(account_id=None,card_id=f.card,amount=30000)
    f.save_entry(entry)
    # Compra antes do fechamento: fatura janeiro, vencimento fevereiro.
    s=f.summary('2024-02-01','2024-02-29','caixa')
    assert s['planned_expense']==30000 and s['expense']==0
    f.save_entry(dict(description='Parcial',kind='pagamento de fatura',amount=12000,account_id=f.a,
                     card_id=f.card,invoice='2024-01',competence='2024-02-05',due='2024-02-05',paid='2024-02-05',status='pago'))
    s=f.summary('2024-02-01','2024-02-29','caixa')
    assert s['planned_expense']==18000 and s['expense']==12000


def test_subcategory_budget_and_full_series_edit(finance,entry):
    f=finance
    child=f.save_entity('categories',dict(name='Feira',parent_id=f.category))
    entry.update(category_id=child,status='previsto',paid=None)
    sid=f.create_series(entry,'recorrência',3)
    rows=f.db.rows('SELECT * FROM entries WHERE series_id=? ORDER BY occurrence',(sid,))
    changed=dict(rows[1],amount=20000)
    f.edit_series(rows[1]['id'],changed,'toda a série')
    assert all(e['amount']==20000 for e in f.entries())
    f.bulk_status([rows[0]['id']],'pago','2024-01-15')
    f.save_entity('budgets',dict(month='2024-01',category_id=f.category,amount=25000))
    assert f.budget_progress('2024-01')[0]['spent']==20000
    assert len(f.entries(category_id=f.category))==3


def test_confirmed_card_installment_consumes_full_limit(finance,entry):
    f=finance
    entry.update(account_id=None,card_id=f.card,amount=10000)
    f.create_series(entry,'parcelamento',3)
    assert f.invoice_total(f.card)['remaining']==10000
    assert f.balance(f.a)==100000
    rows=f.db.rows('SELECT * FROM entries ORDER BY occurrence')
    assert all(r['status']=='pago' and r['paid']=='2024-01-15' for r in rows)
    assert f.summary('2024-01-01','2024-01-31')['expense']==3334
    assert f.summary('2024-01-01','2024-12-31')['expense']==10000


def test_delete_series_from_first_still_allows_backup(finance,entry):
    f=finance
    sid=f.create_series(entry,'recorrência',3)
    first=f.db.one('SELECT id FROM entries WHERE series_id=? AND occurrence=0',(sid,))
    f.delete_entries([first['id']],'esta e próximas')
    assert len(f.entries())==0
    backup=f.db.backup()
    f.db.restore(backup);f.generate_series()
    assert len(f.entries())==0


def test_restore_rejects_invalid_settings_without_touching_live_data(finance,entry,tmp_path):
    f=finance;f.save_entry(entry);backup=f.db.backup(destination=tmp_path/'ajustes-invalidos.sqlite3')
    with sqlite3.connect(backup) as c:c.execute("UPDATE settings SET value='abc' WHERE key='retention'")
    with pytest.raises(ValueError):f.db.restore(backup)
    assert f.balance(f.a)==89999

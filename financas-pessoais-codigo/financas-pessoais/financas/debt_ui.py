"""Tela de dívidas, formulários e celebração discreta de quitação."""
import logging
import sqlite3
from functools import wraps
from PySide6.QtCore import Qt,QSignalBlocker
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QLineEdit,QTextEdit,QCheckBox,
    QMessageBox,QDialog,QFrame,QProgressBar,QSplitter)
from .widgets import label,button,combo,set_combo,date_edit,date_value,page,toolbar,Table,FormDialog
from .dialogs import entities,amount_text
from .money import cents,brl,brdate
from .appearance import colors


def action(fn):
    @wraps(fn)
    def run(self,*args):
        try:
            return fn(self,*args)
        except (ValueError,sqlite3.Error,OSError) as exc:
            logging.error('Falha em dívidas: %s',type(exc).__name__)
            QMessageBox.warning(self,'Não foi possível concluir',str(exc) if isinstance(exc,ValueError)
                else 'Não foi possível salvar. Verifique as permissões e tente novamente.')
    return run


class DebtDialog(FormDialog):
    def __init__(self,finance,parent=None,debt=None):
        super().__init__('Editar dívida' if debt else 'Nova dívida',parent)
        self.f=finance;self.original=debt;self.identifier=debt['id'] if debt else None
        self.newly_settled=False;d=debt or {}
        self.add('name','&Nome da dívida',QLineEdit(d.get('name','')))
        self.add('creditor','&Credor (opcional)',QLineEdit(d.get('creditor','')))
        self.add('amount','&Valor total (R$)',QLineEdit(amount_text(d.get('amount',0))))
        self.add('has_due','Vencimento',QCheckBox('Definir vencimento'))
        due=self.add('due','&Data de vencimento',date_edit(d.get('due')))
        due.setEnabled(bool(d.get('due')));self.fields['has_due'].setChecked(bool(d.get('due')))
        self.fields['has_due'].toggled.connect(due.setEnabled)
        category=self.add('category_id','&Categoria sugerida para pagamentos',combo(entities(finance.db,'categories',d.get('category_id')),'Selecione'))
        set_combo(category,d.get('category_id'))
        notes=QTextEdit(d.get('notes',''));notes.setMaximumHeight(90)
        self.add('notes','&Observações',notes)
        self.hint('Cadastre o total que deseja acompanhar. O cadastro não cria despesa nem altera suas contas. Registre cada pagamento separadamente. O total inclui o que você já pagou nesta dívida.')
        if debt:self.hint('Já pago: '+brl(debt['paid'])+'. O total pode ser ajustado, mas não pode ficar abaixo do valor pago. Não há cálculo automático de juros.')
        self.bind(self.save)

    def save(self):
        f=self.fields
        values=dict(name=f['name'].text(),creditor=f['creditor'].text(),amount=cents(f['amount'].text()),
                    due=date_value(f['due']) if f['has_due'].isChecked() else None,
                    category_id=f['category_id'].currentData(),notes=f['notes'].toPlainText())
        self.identifier=self.f.save_debt(values,self.identifier)
        self.newly_settled=bool(self.original and not self.original['settled'] and self.f.debt(self.identifier)['settled'])


class PaymentDialog(FormDialog):
    def __init__(self,finance,debt,parent=None,payment=None):
        super().__init__('Editar pagamento' if payment else 'Registrar pagamento',parent)
        self.f=finance;self.debt=debt;self.original=payment;self.newly_settled=False
        p=payment or {};self.identifier=p.get('id')
        self.hint('Dívida: '+debt['name']+' · Saldo restante: '+brl(debt['remaining']))
        self.add('amount','&Valor pago (R$)',QLineEdit(amount_text(p.get('amount',0))))
        self.add('day','&Data do pagamento',date_edit(p.get('day')))
        mode=self.add('mode','&Como registrar',combo([('Gerar saída de uma conta','conta'),('Já registrado / somente acompanhar','histórico')]))
        set_combo(mode,'conta' if not payment or p.get('entry_id') else 'histórico')
        account=self.add('account_id','&Conta de origem',combo(entities(finance.db,'accounts',p.get('account_id')),'Selecione'))
        set_combo(account,p.get('account_id'))
        if not payment and account.count()==2:account.setCurrentIndex(1)
        category=self.add('category_id','Ca&tegoria da despesa',combo(entities(finance.db,'categories',p.get('category_id') or debt['category_id']),'Selecione'))
        set_combo(category,p.get('category_id') or debt['category_id'])
        notes=QTextEdit(p.get('notes',''));notes.setMaximumHeight(80)
        self.add('notes','&Observações',notes)
        self.mode_note=label('','muted');self.mode_note.setWordWrap(True);self.form.addRow(self.mode_note)
        mode.currentIndexChanged.connect(self.sync_mode);self.sync_mode()
        self.hint('Cada pagamento reduz o saldo da dívida. Não registre novamente uma saída que já está em Lançamentos ou Cartões. Na opção “somente acompanhar”, nenhum lançamento ou movimento de conta será criado.')
        self.bind(self.save)

    def sync_mode(self,*args):
        account_mode=self.fields['mode'].currentData()=='conta'
        for key in ('account_id','category_id'):self.fields[key].setEnabled(account_mode)
        text=('Será criada uma despesa paga na data informada, refletida no saldo, orçamento e relatórios. '
              'Para corrigir essa despesa, edite o pagamento aqui.' if account_mode else
              'Somente o histórico da dívida será atualizado. Use para pagamentos antigos ou já lançados; confira se a saída de dinheiro já está registrada.')
        if self.original and bool(self.original['entry_id'])!=account_mode:
            text+=' Ao salvar, a saída vinculada anterior será removida ou uma nova saída será criada, conforme a opção escolhida.'
        self.mode_note.setText(text)

    def save(self):
        f=self.fields
        values=dict(amount=cents(f['amount'].text()),day=date_value(f['day']),mode=f['mode'].currentData(),
                    account_id=f['account_id'].currentData(),category_id=f['category_id'].currentData(),notes=f['notes'].toPlainText())
        if self.original and bool(self.original['entry_id'])!=(values['mode']=='conta'):
            if QMessageBox.question(self,'Alterar movimentação da conta',
                    'Esta mudança cria ou remove a saída vinculada e recalcula o saldo da conta e os relatórios. Confirmar?',
                    QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:
                raise ValueError('Alteração não confirmada.')
            self.f.db.backup('antes-alterar-pagamento-divida')
        self.identifier=self.f.save_debt_payment(self.debt['id'],values,self.identifier)
        self.newly_settled=not self.debt['settled'] and self.f.debt(self.debt['id'])['settled']


class SettlementDialog(QDialog):
    def __init__(self,debt,parent=None):
        super().__init__(parent)
        self.setWindowTitle('Dívida quitada');self.setObjectName('debtSettlement')
        self.resize(480,310)
        root=QVBoxLayout(self);root.setContentsMargins(36,30,36,30);root.setSpacing(18)
        root.addStretch()
        title=label('Uma conquista sua.','title');title.setAlignment(Qt.AlignCenter);root.addWidget(title)
        text=label('Parabéns. Você quitou sua dívida.');text.setAlignment(Qt.AlignCenter);root.addWidget(text)
        name=label(debt['name'],'muted');name.setTextFormat(Qt.PlainText);name.setWordWrap(True);name.setAlignment(Qt.AlignCenter);root.addWidget(name)
        line=QFrame();line.setFrameShape(QFrame.HLine);root.addWidget(line)
        amount=label(brl(debt['amount'])+' · saldo restante '+brl(0),'muted');amount.setAlignment(Qt.AlignCenter);root.addWidget(amount)
        note=label('Seu histórico permanece guardado.','muted');note.setAlignment(Qt.AlignCenter);root.addWidget(note)
        root.addStretch();root.addWidget(button('Continuar',self.accept,icon=None))


class DebtPage(QWidget):
    def __init__(self,window):
        super().__init__();self.window=window;self.f=window.f;self.db=window.db
        body,layout=page('Dívidas','Acompanhe seus pagamentos aos poucos. Dívidas quitadas permanecem no histórico.',refresh=window.refresh)
        root=QVBoxLayout(self);root.setContentsMargins(0,0,0,0);root.addWidget(body)
        toolbar(layout,button('Nova dívida',self.new_debt,primary=True),button('Editar dívida',self.edit_debt,'edit'),
                button('Registrar pagamento',self.pay,'add'),button('Excluir dívida',self.delete_debt,'delete'))
        self.search=QLineEdit();self.search.setMinimumWidth(300);self.search.setPlaceholderText('Pesquisar nome, credor ou observações...');self.search.setAccessibleName('Pesquisar dívidas')
        self.status=combo(['Todas','Em aberto','Quitadas']);self.status.setAccessibleName('Situação das dívidas')
        toolbar(layout,self.search,self.status,button('Filtrar',self.reload_data,'refresh'))
        self.search.returnPressed.connect(self.reload_data);self.status.currentIndexChanged.connect(self.reload_data)
        self.summary=label('','muted');layout.addWidget(self.summary)
        self.table=Table(['Dívida','Credor','Total','Já pago','Restante','Progresso','Vencimento','Situação'])
        self.table.setAccessibleName('Dívidas; quitadas aparecem com texto riscado');self.table.setMinimumHeight(150)
        self.table.itemSelectionChanged.connect(self.refresh_payments);self.table.cellDoubleClicked.connect(self.edit_debt)
        self.table.setSelectionMode(Table.SingleSelection)
        detail=QWidget();dl=QVBoxLayout(detail);dl.setContentsMargins(0,8,0,0);dl.setSpacing(10)
        self.progress=QProgressBar();self.progress.setObjectName('debtProgress');self.progress.setRange(0,100);dl.addWidget(self.progress)
        self.detail=label('Selecione uma dívida para consultar os pagamentos.','muted');self.detail.setTextFormat(Qt.PlainText);self.detail.setWordWrap(True);dl.addWidget(self.detail)
        toolbar(dl,button('Editar pagamento',self.edit_payment,'edit'),button('Excluir pagamento',self.delete_payment,'delete'))
        self.payments=Table(['Data','Valor pago','Registro','Conta','Observações']);self.payments.setMinimumHeight(130);dl.addWidget(self.payments)
        self.payments.cellDoubleClicked.connect(self.edit_payment)
        split=QSplitter(Qt.Vertical);split.addWidget(self.table);split.addWidget(detail);split.setStretchFactor(0,1);split.setStretchFactor(1,1)
        layout.addWidget(split,1)
        note=label('Todas as datas: esta aba não usa o período do topo. O cadastro não movimenta contas; pagamentos podem gerar uma saída ou apenas registrar um valor já lançado.','muted');note.setWordWrap(True);layout.addWidget(note)

    def reload_data(self,*args):
        selected=self.table.ids();rows=self.f.debts(self.search.text(),self.status.currentData())
        self.summary.setText('Nesta consulta · Total: '+brl(sum(r['amount'] for r in rows))+'    Pago: '+brl(sum(r['paid'] for r in rows))+'    Em aberto: '+brl(sum(r['remaining'] for r in rows)))
        with QSignalBlocker(self.table):
            self.table.fill([(r['id'],[r['name'],r['creditor'],(brl(r['amount']),r['amount']),
                (brl(r['paid']),r['paid']),(brl(r['remaining']),r['remaining']),
                (str(r['percent'])+'%',r['percent']),(brdate(r['due']) if r['due'] else 'Sem vencimento',r['due'] or ''),
                'Quitada' if r['settled'] else 'Em aberto']) for r in rows])
            settled={r['id'] for r in rows if r['settled']}
            for i in range(self.table.rowCount()):
                if self.table.item(i,0).data(Qt.UserRole) in settled:
                    for col in range(self.table.columnCount()):
                        item=self.table.item(i,col);font=item.font();font.setStrikeOut(True);item.setFont(font);item.setForeground(QColor(colors()['muted']))
            if rows:self.table.selectRow(next((i for i in range(self.table.rowCount()) if self.table.item(i,0).data(Qt.UserRole) in selected),0))
        self.refresh_payments()

    def refresh_payments(self,*args):
        ids=self.table.ids();selected=self.payments.ids()
        debt=self.f.debt(ids[0]) if ids else None
        self.progress.setValue(debt['percent'] if debt else 0)
        self.progress.setFormat(('Quitada · 100%' if debt['settled'] else '%p% pago') if debt else 'Selecione uma dívida')
        text='Selecione uma dívida para consultar os pagamentos.'
        if debt:
            text=debt['name']+' · '+str(debt['payments'])+' pagamento(s) · Restante: '+brl(debt['remaining'])
            if debt['notes']:text+='\n'+debt['notes']
        if not self.table.rowCount():text='Nenhuma dívida nesta consulta. Clique em Nova dívida para começar ou ajuste os filtros.'
        self.detail.setText(text)
        rows=self.f.debt_payments(ids[0]) if ids else []
        self.payments.fill([(r['id'],[(brdate(r['day']),r['day']),(brl(r['amount']),r['amount']),
            'Saída vinculada' if r['entry_id'] else 'Somente histórico',r['account'] or 'Sem movimentação',r['notes']]) for r in rows])
        if rows:self.payments.selectRow(next((i for i in range(self.payments.rowCount()) if self.payments.item(i,0).data(Qt.UserRole) in selected),0))

    def finish_dialog(self,dialog):
        if dialog.exec():
            self.window.refresh()
            if dialog.newly_settled:
                identifier=dialog.debt['id'] if isinstance(dialog,PaymentDialog) else dialog.identifier
                self.show_settlement(self.f.debt(identifier))

    def show_settlement(self,debt):
        SettlementDialog(debt,self.window).exec()

    @action
    def new_debt(self,*args):self.finish_dialog(DebtDialog(self.f,self.window))

    @action
    def edit_debt(self,*args):self.finish_dialog(DebtDialog(self.f,self.window,self.f.debt(self.table.selected_id())))

    @action
    def pay(self,*args):
        debt=self.f.debt(self.table.selected_id())
        if debt['settled']:raise ValueError('Esta dívida já está quitada. Seu histórico continua disponível abaixo.')
        self.finish_dialog(PaymentDialog(self.f,debt,self.window))

    @action
    def edit_payment(self,*args):
        payment=self.db.one('SELECT * FROM debt_payments WHERE id=?',(self.payments.selected_id(),))
        debt=self.f.debt(payment['debt_id'])
        original=next(p for p in self.f.debt_payments(debt['id']) if p['id']==payment['id'])
        self.finish_dialog(PaymentDialog(self.f,debt,self.window,original))

    @action
    def delete_payment(self,*args):
        identifier=self.payments.selected_id()
        if QMessageBox.question(self,'Excluir pagamento',
                'Excluir este pagamento? A dívida será recalculada e poderá voltar a ficar em aberto. Se houver uma saída vinculada, ela também será excluída e o saldo da conta será recomposto. Um backup será criado.',
                QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
        self.db.backup('antes-excluir-pagamento-divida');self.f.delete_debt_payment(identifier);self.window.refresh()

    @action
    def delete_debt(self,*args):
        identifier=self.table.selected_id();debt=self.f.debt(identifier)
        if debt['payments']:raise ValueError('Dívidas com pagamentos ficam guardadas para preservar seu histórico. Você pode corrigir os pagamentos, se necessário.')
        if QMessageBox.question(self,'Excluir dívida','Excluir este cadastro sem pagamentos? Será criado um backup preventivo.',
                QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
        self.db.backup('antes-excluir-divida');self.f.delete_debt(identifier);self.window.refresh()

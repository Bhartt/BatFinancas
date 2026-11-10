"""Interface desktop. As telas usam a mesma camada de regras dos testes."""
import calendar
import logging
import sqlite3
from datetime import date,timedelta
from functools import wraps
from pathlib import Path
from PySide6.QtCore import Qt,QTimer,QDate,QUrl
from PySide6.QtGui import QAction,QKeySequence,QDesktopServices
from PySide6.QtWidgets import (QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QListWidget,
 QStackedWidget,QSplitter,QScrollArea,QFileDialog,QMessageBox,QLineEdit,QSpinBox,QCheckBox,
 QInputDialog,QTabWidget,QProgressBar,QDialogButtonBox,QApplication,QPushButton)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter
from .widgets import label,button,combo,set_combo,date_edit,date_value,page,toolbar,Table,FormDialog,refresh_button_icon
from .dialogs import EntryDialog,EntityDialog,ImportDialog,entities
from .money import brl,brdate,advance,iso,cents
from .reports import export_csv,export_pdf,report_tables
from . import __version__
from .appearance import apply_theme,colors,greeting
from .effects import AnimatedMenu,ThemeToggle,BatIntro
from . import updates
from .debt_ui import DebtPage


def guarded(fn):
    @wraps(fn)
    def wrapper(self,*args,**kwargs):
        try:
            return fn(self,*args,**kwargs)
        except (ValueError,sqlite3.IntegrityError,OSError,sqlite3.DatabaseError) as exc:
            text=str(exc) if isinstance(exc,ValueError) else 'Não foi possível concluir a operação. Verifique o arquivo, as permissões e se já existe um cadastro com esses dados.'
            # Não registrar descrições, valores, consultas SQL ou caminhos selecionados.
            logging.error('Falha em %s: %s',fn.__name__,type(exc).__name__)
            QMessageBox.warning(self,'Não foi possível concluir',text)
    return wrapper


class Window(QMainWindow):
    def __init__(self,finance,demo=False):
        super().__init__()
        self.f=finance;self.db=finance.db;self.demo=demo
        preference=self.db.one("SELECT value FROM settings WHERE key='theme'")
        self.theme_mode=preference['value'] if preference and preference['value'] in ('claro','escuro') else 'escuro'
        apply_theme(QApplication.instance(),self.theme_mode)
        self.intro=None
        self.setWindowTitle('BatFinanças · '+__version__+(' · DEMONSTRAÇÃO — dados separados' if demo else ''))
        self.resize(1380,900);self.setMinimumSize(900,650)
        root=QWidget();self.setCentralWidget(root);layout=QVBoxLayout(root);layout.setContentsMargins(0,0,0,0)
        splitter=QSplitter();layout.addWidget(splitter)
        side=QWidget();side.setObjectName('sidebar');side.setMinimumWidth(215);side.setMaximumWidth(260);sl=QVBoxLayout(side);sl.setContentsMargins(0,20,0,12)
        sl.addWidget(label('  BatFinanças','brand'))
        sl.addWidget(label('    Pessoal · local · sem conexão','muted'))
        self.nav=AnimatedMenu();self.nav.addItems(['◫  Visão geral','≡  Lançamentos','▣  Contas','▤  Cartões','◷  Orçamentos','◇  Metas','▥  Relatórios','▧  Dívidas','⚙  Configurações'])
        sl.addWidget(self.nav,1);sl.addWidget(label('    Ctrl+N · novo lançamento\n    Ctrl+F · pesquisar\n    F5 · atualizar','muted'))
        splitter.addWidget(side)
        right=QWidget();rl=QVBoxLayout(right);rl.setContentsMargins(0,0,0,0)
        welcome=QWidget();welcome_layout=QHBoxLayout(welcome);welcome_layout.setContentsMargins(24,8,20,0)
        self.greeting_label=label(greeting(),'greeting');welcome_layout.addWidget(self.greeting_label,1)
        self.theme_label=label('Modo escuro' if self.theme_mode=='escuro' else 'Modo claro','muted')
        welcome_layout.addWidget(self.theme_label)
        self.theme_toggle=ThemeToggle();self.theme_toggle.set_dark(self.theme_mode=='escuro',animate=False)
        self.theme_toggle.toggled.connect(lambda dark:self.set_theme('escuro' if dark else 'claro'))
        welcome_layout.addWidget(self.theme_toggle);rl.addWidget(welcome)
        filters=QWidget();fl=QGridLayout(filters);fl.setContentsMargins(24,16,24,8)
        today=date.today()
        self.period=combo(['Mês','Ano','Intervalo personalizado']);self.month=combo([(calendar.month_name[i],i) for i in range(1,13)])
        month_names=['Janeiro','Fevereiro','Março','Abril','Maio','Junho','Julho','Agosto','Setembro','Outubro','Novembro','Dezembro']
        for i,name in enumerate(month_names):self.month.setItemText(i,name)
        set_combo(self.month,today.month)
        self.year=QSpinBox();self.year.setRange(1900,2200);self.year.setValue(today.year)
        self.start=date_edit(today.replace(day=1));self.end=date_edit(today.replace(day=calendar.monthrange(today.year,today.month)[1]))
        for i,(name,w) in enumerate([('Período',self.period),('Mês',self.month),('Ano',self.year),('De',self.start),('Até',self.end)]):
            row,col=divmod(i,3)
            fl.addWidget(label(name),row,col*2);fl.addWidget(w,row,col*2+1)
            w.setAccessibleName(name)
        fl.addWidget(button('Aplicar',self.refresh,'refresh'),1,4,1,2);rl.addWidget(filters)
        self.stack=QStackedWidget();rl.addWidget(self.stack,1)
        splitter.addWidget(right);splitter.setStretchFactor(1,1);splitter.setSizes([230,1150])
        self.build_dashboard();self.build_entries();self.build_accounts();self.build_cards();self.build_budgets();self.build_goals();self.build_reports()
        self.debt_page=DebtPage(self);self.add_page(self.debt_page,True)
        self.build_settings()
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)
        for w in (self.period,self.month):w.currentIndexChanged.connect(self.sync_period)
        self.year.valueChanged.connect(self.sync_period);self.sync_period()
        for title,key,callback in [('Novo lançamento','Ctrl+N',self.new_entry),('Pesquisar','Ctrl+F',self.focus_search),('Atualizar','F5',self.refresh),('Editar selecionado','Ctrl+E',self.edit_selected),('Fechar','Ctrl+Q',self.close)]:
            action=QAction(title,self);action.setShortcut(QKeySequence(key));action.triggered.connect(callback);self.addAction(action)
        self.statusBar().showMessage('Dados salvos localmente · Nenhuma conexão externa')
        self.refresh()
        self.greeting_timer=QTimer(self);self.greeting_timer.setInterval(60000)
        self.greeting_timer.timeout.connect(self.update_greeting);self.greeting_timer.start()
        self.backup_timer=QTimer(self);self.backup_timer.setInterval(30*60*1000);self.backup_timer.timeout.connect(self.auto_backup);self.backup_timer.start()

    def add_page(self,w,scroll=False):
        if scroll:
            s=QScrollArea();s.setWidgetResizable(True);s.setWidget(w);self.stack.addWidget(s)
        else:self.stack.addWidget(w)

    def sync_period(self,*args):
        mode=self.period.currentData();y=self.year.value();m=self.month.currentData()
        custom=mode=='Intervalo personalizado'
        self.month.setEnabled(mode=='Mês');self.year.setEnabled(not custom)
        self.start.setEnabled(custom);self.end.setEnabled(custom)
        if not custom:
            self.start.setDate(QDate(y,m if mode=='Mês' else 1,1))
            self.end.setDate(QDate(y,m,calendar.monthrange(y,m)[1]) if mode=='Mês' else QDate(y,12,31))

    def dates(self):
        a,b=date_value(self.start),date_value(self.end)
        if a>b:raise ValueError('A data inicial deve ser anterior à data final.')
        if (date.fromisoformat(b)-date.fromisoformat(a)).days>3660:
            raise ValueError('Selecione um intervalo de até dez anos por consulta.')
        return a,b

    def build_dashboard(self):
        w,l=page('Visão geral','Acompanhe suas finanças. Clique nos indicadores para consultar os lançamentos que formam cada total.',refresh=self.refresh)
        self.dashboard_period=label('','muted');l.addWidget(self.dashboard_period)
        grid=QGridLayout();self.metrics={}
        metric_names=[('income','Receitas realizadas'),('expense','Despesas realizadas'),('result','Resultado realizado'),
                      ('planned_income','Receitas previstas / pendentes'),('planned_expense','Despesas previstas / pendentes'),('balance','Saldo consolidado')]
        for i,(key,name) in enumerate(metric_names):
            b=button(name,lambda checked=False,k=key:self.drill_metric(k),'next');b.setObjectName('metric');b.setMinimumHeight(90)
            if key in ('income','planned_income'):b.setProperty('metricColor','income')
            if key in ('expense','planned_expense'):b.setProperty('metricColor','expense')
            self.metrics[key]=b;grid.addWidget(b,i//3,i%3)
        l.addLayout(grid)
        self.comparison=label('','muted');l.addWidget(self.comparison)
        self.dashboard_accounts=Table(['Conta','Saldo realizado no fim do período','Saldo atual'])
        l.addWidget(self.dashboard_accounts)
        self.dashboard_accounts.cellDoubleClicked.connect(self.open_dashboard_account)
        self.payables=button('Contas a pagar',lambda:self.drill_due('despesa'),'next')
        self.receivables=button('Contas a receber',lambda:self.drill_due('receita'),'next')
        toolbar(l,self.payables,self.receivables)
        self.alerts=label('');l.addWidget(self.alerts)
        self.figure=Figure(figsize=(10,4),facecolor='#1d1f23',tight_layout=True)
        self.canvas=FigureCanvasQTAgg(self.figure);self.canvas.setMinimumHeight(320);l.addWidget(self.canvas)
        self.canvas.mpl_connect('button_press_event',self.chart_click)
        self.add_page(w,True)

    def build_entries(self):
        w,l=page('Lançamentos','Receitas, despesas e transferências. Selecione linhas com Ctrl ou Shift para ações em lote.',refresh=self.refresh)
        toolbar(l,button('Novo lançamento',self.new_entry,primary=True),button('Editar',self.edit_selected,'edit'),button('Duplicar',self.duplicate_entry,'add'),button('Excluir',self.delete_selected,'delete'),button('Alterar situação em lote',self.bulk_status,'ok'))
        self.search=QLineEdit();self.search.setPlaceholderText('Pesquisar descrição, observações ou etiquetas…');self.search.setClearButtonEnabled(True)
        self.type_filter=combo(['receita','despesa','transferência','pagamento de fatura','estorno'],'Todos os tipos')
        self.status_filter=combo(['previsto','pendente','pago','recebido','cancelado'],'Todas as situações')
        self.category_filter=combo([],'Todas as categorias');self.account_filter=combo([],'Todas as contas');self.card_filter=combo([],'Todos os cartões')
        self.basis=combo(['competência','caixa','vencimento'])
        row=QHBoxLayout();row.addWidget(self.search,2);row.addWidget(self.type_filter);row.addWidget(self.status_filter);row.addWidget(self.basis);l.addLayout(row)
        toolbar(l,self.category_filter,self.account_filter,self.card_filter,button('Filtrar',self.refresh_entries,'refresh'),button('Limpar filtros',self.clear_filters,'refresh'))
        self.search.returnPressed.connect(self.refresh_entries)
        self.entries_table=Table(['Descrição','Tipo','Valor','Categoria','Conta / cartão','Competência','Vencimento','Pagamento','Situação','Fatura','Etiquetas'])
        self.entries_table.cellDoubleClicked.connect(lambda *_:self.edit_selected());l.addWidget(self.entries_table,1)
        self.entries_empty=label('');l.addWidget(self.entries_empty)
        toolbar(l,button('Importar CSV',self.import_csv,'open'),button('Exportar CSV filtrado',self.export_entries,'save'))
        self.add_page(w)

    def build_accounts(self):
        w,l=page('Contas','Gerencie suas contas e confira o estado de cada cadastro. O saldo inicial é registrado separadamente das receitas.',refresh=self.refresh)
        toolbar(l,button('Cadastrar conta',lambda:self.entity('accounts'),primary=True),button('Editar conta',lambda:self.edit_entity('accounts',self.accounts_table),'edit'),button('Excluir conta',self.delete_account,'delete'),button('Reativar selecionadas',self.reactivate_accounts,'ok'),button('Ver lançamentos',self.drill_account,'next'))
        self.accounts_table=Table(['Nome','Estado','Tipo','Saldo inicial','Referência','Saldo no fim do período','Saldo atual']);l.addWidget(self.accounts_table,1)
        self.accounts_table.cellDoubleClicked.connect(lambda *_:self.edit_entity('accounts',self.accounts_table))
        self.account_notice=label('','muted');l.addWidget(self.account_notice)
        l.addWidget(label('Selecione uma linha e use Editar conta, ou dê dois cliques nela. Contas arquivadas preservam saldos e histórico; para voltar a usá-las em lançamentos, clique Reativar selecionadas.','muted'))
        self.add_page(w)

    def build_cards(self):
        w,l=page('Cartões','A compra gera despesa e dívida. O pagamento da fatura reduz o saldo da conta e a dívida, sem repetir a despesa.',refresh=self.refresh)
        toolbar(l,button('Cadastrar cartão',lambda:self.entity('cards'),primary=True),button('Editar cartão',lambda:self.edit_entity('cards',self.cards_table),'edit'),button('Registrar compra',self.card_purchase,'add'))
        self.cards_table=Table(['Cartão','Limite','Dívida total','Limite disponível','Fechamento','Vencimento','Estado']);l.addWidget(self.cards_table,1)
        self.cards_table.itemSelectionChanged.connect(self.refresh_invoice)
        self.cards_table.cellDoubleClicked.connect(lambda *_:self.edit_entity('cards',self.cards_table))
        self.invoice_month=QLineEdit(date.today().isoformat()[:7]);self.invoice_month.setMaximumWidth(120)
        toolbar(l,label('Fatura (AAAA-MM)'),self.invoice_month,button('Consultar fatura',self.refresh_invoice,'refresh'),button('Pagar fatura',self.pay_invoice,'ok'),button('Registrar estorno',self.refund,'back'))
        self.invoice_info=label('Selecione um cartão para consultar sua fatura.');l.addWidget(self.invoice_info)
        self.invoice_table=Table(['Descrição','Tipo','Valor','Competência','Pagamento / confirmação','Situação']);l.addWidget(self.invoice_table,1)
        self.invoice_table.cellDoubleClicked.connect(self.edit_invoice_entry)
        l.addWidget(label('Compra confirmada: reduz limite. Estorno confirmado: reduz despesa e dívida. Pagamento: libera limite. Estorno após pagamento pode gerar crédito (saldo negativo na fatura). Faturas usam o mês do fechamento.','muted'))
        self.add_page(w)

    def build_budgets(self):
        w,l=page('Orçamentos','Limites mensais por categoria, calculados por competência. A categoria principal inclui suas subcategorias.',refresh=self.refresh)
        toolbar(l,button('Criar orçamento',lambda:self.entity('budgets',defaults={'month':self.dates()[0][:7]}),primary=True),button('Editar',lambda:self.edit_entity('budgets',self.budgets_table),'edit'),button('Excluir',lambda:self.delete_entity('budgets',self.budgets_table),'delete'))
        self.budgets_table=Table(['Mês','Categoria','Limite','Gasto realizado','Disponível','Utilizado','Alerta']);l.addWidget(self.budgets_table,1)
        self.budgets_table.cellDoubleClicked.connect(lambda *_:self.edit_entity('budgets',self.budgets_table))
        l.addWidget(label('São exibidos os meses que intersectam o período selecionado, sempre com apuração do mês inteiro. Alerta a partir de 80% do limite.','muted'))
        self.add_page(w)

    def build_goals(self):
        w,l=page('Metas','Registre seus objetivos e acompanhe os aportes. Aportes em metas não são despesas nem transferências automáticas.',refresh=self.refresh)
        toolbar(l,button('Criar meta',lambda:self.entity('goals'),primary=True),button('Editar meta',lambda:self.edit_entity('goals',self.goals_table),'edit'),button('Excluir meta',lambda:self.delete_entity('goals',self.goals_table),'delete'),button('Registrar aporte',self.contribute,'add'))
        self.goals_table=Table(['Meta','Valor desejado','Prazo','Acumulado','Falta','Progresso']);l.addWidget(self.goals_table,1)
        self.goals_table.itemSelectionChanged.connect(self.refresh_contributions)
        self.goals_table.cellDoubleClicked.connect(lambda *_:self.edit_entity('goals',self.goals_table))
        l.addWidget(label('Aportes da meta selecionada — todo o histórico'))
        toolbar(l,button('Editar aporte',lambda:self.edit_entity('contributions',self.contributions_table),'edit'),button('Excluir aporte',lambda:self.delete_entity('contributions',self.contributions_table),'delete'))
        self.contributions_table=Table(['Data','Valor','Observações']);l.addWidget(self.contributions_table,1)
        self.add_page(w)

    def build_reports(self):
        w,l=page('Relatórios','Relatórios do período selecionado. Escolha a base de apuração e exporte o documento completo em PDF.',refresh=self.refresh)
        self.report_basis=combo(['competência','caixa'])
        toolbar(l,label('Base de apuração'),self.report_basis,button('Atualizar relatório',self.refresh_reports,'refresh'),button('Exportar PDF',self.pdf,'save',True))
        self.report_note=label('Competência: despesas incluem compras no cartão e estornos; pagamentos de fatura são excluídos. Caixa: entradas e saídas das contas na data de pagamento; previstos usam o vencimento. Transferências não entram no resultado.','muted');l.addWidget(self.report_note)
        self.report_tabs=QTabWidget();l.addWidget(self.report_tabs,1)
        self.add_page(w)

    def build_settings(self):
        w,l=page('Configurações','Dados locais, categorias, backups e privacidade.',refresh=self.refresh)
        l.addWidget(label('Banco de dados: '+str(self.db.path)))
        l.addWidget(label('Atualizações da BatFinanças'))
        self.update_status=label(updates.status_text(),'muted');l.addWidget(self.update_status)
        toolbar(l,button('Ver versões no Drive',self.open_update_folder,'open'),button('Instalar atualização',self.install_update,'open',True))
        l.addWidget(label('Selecione batfinancas-atualizacao-VERSÃO.zip, baixado da distribuição deste projeto. O app valida os arquivos, cria um backup e reinicia. Não há verificação automática de internet.','muted'))
        self.theme_picker=combo([('Escuro','escuro'),('Claro','claro')]);set_combo(self.theme_picker,self.theme_mode)
        self.theme_picker.currentIndexChanged.connect(lambda:self.set_theme(self.theme_picker.currentData()))
        toolbar(l,label('Aparência'),self.theme_picker,label('A escolha é salva automaticamente.','muted'))
        l.addWidget(label('Armazenamento local não é criptografia. Quem tiver acesso aos arquivos poderá ler os dados. Proteja sua conta do sistema e use criptografia de disco quando necessário.','muted'))
        self.auto=QCheckBox('Backup automático ao abrir, a cada 30 minutos e ao fechar');self.auto.setChecked(self.db.setting('auto_backup')=='1')
        self.retention=QSpinBox();self.retention.setRange(1,365);self.retention.setValue(int(self.db.setting('retention')))
        toolbar(l,self.auto,label('Reter backups automáticos'),self.retention,button('Salvar preferências',self.save_settings,'save'))
        toolbar(l,button('Criar backup',self.manual_backup,'save'),button('Restaurar backup',self.restore,'open'),button('Exportação completa (JSON)',self.export_all,'save'))
        l.addWidget(label('Backups automáticos ficam na subpasta backups, ao lado do banco. Backups preventivos e manuais não são removidos pela retenção. Copie backups para outra mídia para se proteger contra falha do computador.','muted'))
        l.addWidget(label('Categorias e subcategorias'))
        toolbar(l,button('Nova categoria',lambda:self.entity('categories'),primary=True),button('Editar / arquivar',lambda:self.edit_entity('categories',self.categories_table),'edit'))
        self.categories_table=Table(['Categoria','Categoria superior','Estado']);l.addWidget(self.categories_table,1)
        self.categories_table.cellDoubleClicked.connect(lambda *_:self.edit_entity('categories',self.categories_table))
        toolbar(l,button('Abrir manual',self.manual,'open'))
        self.add_page(w,True)

    @guarded
    def refresh(self,*args):
        self.dates()
        # Preserva os filtros escolhidos ao atualizar os cadastros.
        for w,table,title in [(self.account_filter,'accounts','Todas as contas'),(self.category_filter,'categories','Todas as categorias'),(self.card_filter,'cards','Todos os cartões')]:
            current=w.currentData();w.clear();w.addItem(title,None)
            for r in self.db.rows(f'SELECT id,name,archived FROM {table} ORDER BY name'):w.addItem(r['name']+(' (arquivado)' if r['archived'] else ''),r['id'])
            set_combo(w,current)
        self.refresh_entries();self.refresh_accounts();self.refresh_cards();self.refresh_budgets();self.refresh_goals();self.refresh_categories();self.refresh_dashboard();self.refresh_reports()
        self.refresh_update_status()
        self.debt_page.reload_data()
        self.statusBar().showMessage('Consulta atualizada · Gravação local automática')

    @guarded
    def refresh_entries(self,*args):
        a,b=self.dates()
        self.visible_entries=self.f.entries(a,b,self.basis.currentData(),kind=self.type_filter.currentData(),status=self.status_filter.currentData(),category_id=self.category_filter.currentData(),account_id=self.account_filter.currentData(),card_id=self.card_filter.currentData(),text=self.search.text().strip())
        rows=[]
        for e in self.visible_entries:
            rows.append((e['id'],[e['description'],e['kind'],(brl(e['amount']),e['amount']),e['category'],e['card'] or (str(e['account'] or '')+(' → '+e['target'] if e['target'] else '')),
                     (brdate(e['competence']),e['competence']),(brdate(e['due']),e['due']),(brdate(e['paid']),e['paid'] or ''),e['status'],e['invoice'],e['tags']]))
        self.entries_table.fill(rows)
        if rows:
            self.entries_empty.setText(f'{len(rows)} lançamentos encontrados. Base: {self.basis.currentData()}.')
        elif self.db.one('SELECT id FROM accounts LIMIT 1') or self.db.one('SELECT id FROM cards LIMIT 1'):
            self.entries_empty.setText('Nenhum lançamento neste filtro. Seus cadastros continuam salvos. Ajuste o período/filtros ou clique em Novo lançamento. Contas arquivadas podem ser reativadas na tela Contas.')
        else:
            self.entries_empty.setText('Cadastre sua primeira conta na tela Contas e depois clique em Novo lançamento.')

    def refresh_accounts(self):
        _,b=self.dates();rows=[];dashboard=[]
        for a in self.db.rows('SELECT * FROM accounts ORDER BY name'):
            val=self.f.balance(a['id'],b);now=self.f.balance(a['id'])
            rows.append((a['id'],[a['name'],'Arquivada' if a['archived'] else 'Ativa',a['kind'],(brl(a['opening']),a['opening']),brdate(a['reference']),(brl(val),val),(brl(now),now)]))
            dashboard.append((a['id'],[a['name'],(brl(val),val),(brl(now),now)]))
        self.accounts_table.fill(rows);self.dashboard_accounts.fill(dashboard)
        counts=self.db.one('SELECT count(*) total,coalesce(sum(archived=0),0) active FROM accounts')
        self.account_notice.setText(f"{counts['total']} conta(s) cadastrada(s) · {counts['active']} ativa(s)."+(' Para transferir, mantenha pelo menos duas contas ativas.' if counts['active']<2 else ' As contas ativas estão disponíveis para transferências.'))

    def refresh_cards(self):
        selected=self.cards_table.ids();rows=[]
        for c in self.db.rows('SELECT * FROM cards ORDER BY name'):
            debt=self.f.invoice_total(c['id'])['remaining'];available=c['limit_cents']-debt
            rows.append((c['id'],[c['name'],(brl(c['limit_cents']),c['limit_cents']),(brl(debt),debt),(brl(available),available),c['closing'],c['due'],'Arquivado' if c['archived'] else 'Ativo']))
        self.cards_table.fill(rows)
        if rows:
            self.cards_table.selectRow(next((i for i in range(self.cards_table.rowCount()) if self.cards_table.item(i,0).data(Qt.UserRole) in selected),0))
        self.refresh_invoice()

    @guarded
    def refresh_invoice(self,*args):
        ids=self.cards_table.ids()
        if not ids:
            self.invoice_table.fill([]);self.invoice_info.setText('Selecione ou cadastre um cartão para consultar faturas.');return
        cid=ids[0];month=self.invoice_month.text().strip();iso(month+'-01')
        card=self.db.one('SELECT * FROM cards WHERE id=?',(cid,))
        totals=self.f.invoice_total(cid,month)
        self.invoice_info.setText(f'{card["name"]} · Fatura {month} · Vencimento {brdate(self.f.invoice_due(card,month))}\nCompras confirmadas: {brl(totals["purchases"])} · Estornos: {brl(totals["refunds"])} · Pagamentos: {brl(totals["payments"])} · Em aberto / crédito: {brl(totals["remaining"])}')
        rows=self.db.rows('SELECT * FROM entries WHERE card_id=? AND invoice=? ORDER BY competence,id',(cid,month))
        self.invoice_table.fill([(e['id'],[e['description'],e['kind'],(brl(e['amount']),e['amount']),brdate(e['competence']),brdate(e['paid']),e['status']]) for e in rows])

    def refresh_budgets(self):
        a,b=self.dates();rows=[];month=a[:7]+'-01'
        while month<=b:
            for v in self.f.budget_progress(month[:7]):
                alert='Ultrapassado' if v['percent']>100 else 'Limite atingido' if v['percent']==100 else 'Atenção: 80% ou mais' if v['percent']>=80 else 'Dentro do limite'
                rows.append((v['id'],[month[:7],v['name'],(brl(v['amount']),v['amount']),(brl(v['spent']),v['spent']),(brl(v['available']),v['available']),(str(v['percent'])+'%',v['percent']),alert]))
            month=advance(month,1)
        self.budgets_table.fill(rows)

    def refresh_goals(self):
        selected=self.goals_table.ids()
        rows=[]
        for g in self.db.rows('SELECT g.*,coalesce(sum(c.amount),0) progress FROM goals g LEFT JOIN contributions c ON c.goal_id=g.id GROUP BY g.id ORDER BY deadline'):
            percent=g['progress']*100//g['amount']
            rows.append((g['id'],[g['name'],(brl(g['amount']),g['amount']),brdate(g['deadline']),(brl(g['progress']),g['progress']),brl(max(0,g['amount']-g['progress'])),(str(percent)+'%',percent)]))
        self.goals_table.fill(rows)
        if rows:self.goals_table.selectRow(next((i for i in range(self.goals_table.rowCount()) if self.goals_table.item(i,0).data(Qt.UserRole) in selected),0))
        self.refresh_contributions()

    def refresh_contributions(self):
        ids=self.goals_table.ids()
        rows=self.db.rows('SELECT * FROM contributions WHERE goal_id=? ORDER BY day DESC',(ids[0],)) if ids else []
        self.contributions_table.fill([(r['id'],[(brdate(r['day']),r['day']),(brl(r['amount']),r['amount']),r['notes']]) for r in rows])

    def refresh_categories(self):
        rows=self.db.rows('SELECT c.*,p.name parent FROM categories c LEFT JOIN categories p ON p.id=c.parent_id ORDER BY coalesce(p.name,c.name),c.parent_id,c.name')
        self.categories_table.fill([(r['id'],[r['name'],r['parent'] or 'Principal','Arquivada' if r['archived'] else 'Ativa']) for r in rows])

    def refresh_dashboard(self):
        a,b=self.dates();s=self.f.summary(a,b);days=(date.fromisoformat(b)-date.fromisoformat(a)).days+1
        previous_end=(date.fromisoformat(a)-timedelta(days=1)).isoformat()
        previous_start=(date.fromisoformat(a)-timedelta(days=days)).isoformat()
        comparison_label='Período anterior de mesma duração'
        if self.period.currentData() in ('Mês','Ano'):
            previous_start=advance(a,-1,'anual' if self.period.currentData()=='Ano' else 'mensal')
            previous_end=(date.fromisoformat(a)-timedelta(days=1)).isoformat()
            comparison_label='Ano anterior' if self.period.currentData()=='Ano' else 'Mês anterior'
        p=self.f.summary(previous_start,previous_end)
        balance=sum(self.f.balance(r['id'],b) for r in self.db.rows('SELECT id FROM accounts'))
        for key,w in self.metrics.items():
            name={'income':'Receitas realizadas','expense':'Despesas realizadas','result':'Resultado realizado','planned_income':'Receitas previstas / pendentes','planned_expense':'Despesas previstas / pendentes','balance':'Saldo no fim do período'}[key]
            w.setText(name+'\n'+brl(balance if key=='balance' else s[key]))
        self.dashboard_period.setText(f'{brdate(a)} a {brdate(b)} · Indicadores por competência · Saldo inclui todas as contas, inclusive arquivadas.')
        self.comparison.setText(f'{comparison_label} ({brdate(previous_start)} a {brdate(previous_end)}): receitas {brl(p["income"])} · despesas {brl(p["expense"])} · Variação do resultado: {brl(s["result"]-p["result"])}.')
        pending=[e for e in self.f.entries(a,b,'vencimento') if e['status'] in ('previsto','pendente') and e['kind'] in ('receita','despesa')]
        pay=sum(e['amount'] for e in pending if e['kind']=='despesa' and not e['card_id']);receive=sum(e['amount'] for e in pending if e['kind']=='receita')
        self.payables.setText('A pagar em contas · '+brl(pay));self.receivables.setText('A receber · '+brl(receive))
        alerts=[f'A pagar em contas no período: {brl(pay)} · A receber: {brl(receive)}. Compras previstas no cartão estão na fatura.']
        for e in pending[:6]:alerts.append(f'{"Vencido" if e["due"]<date.today().isoformat() else "Vencimento"} {brdate(e["due"])} · {e["description"]} · {brl(e["amount"])}')
        for c in self.db.rows('SELECT * FROM cards'):
            if self.f.invoice_total(c['id'])['remaining']>c['limit_cents']:alerts.append(f'Limite excedido: {c["name"]}.')
            for inv in self.db.rows('SELECT DISTINCT invoice FROM entries WHERE card_id=? AND invoice IS NOT NULL',(c['id'],)):
                due=self.f.invoice_due(c,inv['invoice']);debt=self.f.invoice_total(c['id'],inv['invoice'])['remaining']
                if a<=due<=b and debt>0:alerts.append(f'Fatura {c["name"]} · {brdate(due)} · {brl(debt)} em aberto.')
        month=a[:7]+'-01'
        while month<=b:
            for v in self.f.budget_progress(month[:7]):
                if v['percent']>=80:alerts.append(f'Orçamento {v["name"]} ({month[:7]}): {v["percent"]}% utilizado.')
            month=advance(month,1)
        self.alerts.setText('\n'.join(alerts))
        c=colors(self.theme_mode)
        for metric in self.metrics.values():
            key=metric.property('metricColor')
            metric.setStyleSheet('color:'+c[key]+';' if key else '')
        self.figure.set_facecolor(c['surface'])
        self.figure.clear();left=self.figure.add_subplot(121);right=self.figure.add_subplot(122)
        for ax in (left,right):
            ax.set_facecolor(c['surface']);ax.tick_params(colors=c['muted'],labelsize=9);ax.title.set_color(c['text'])
            for spine in ax.spines.values():spine.set_color(c['border'])
        categories=s['categories'];self.chart_categories=list(categories)
        if categories:
            left.barh(list(categories),[v/100 for v in categories.values()],color=c['chart']);left.set_xlabel('Reais (R$)',color=c['muted'])
        else:left.text(.5,.5,'Sem despesas no período',ha='center',color=c['muted'],transform=left.transAxes)
        left.set_title('Despesas por categoria')
        left.xaxis.set_major_formatter(FuncFormatter(lambda value,pos:brl(int(round(value*100)))))
        right.yaxis.set_major_formatter(FuncFormatter(lambda value,pos:brl(int(round(value*100)))))
        month=a[:7]+'-01';months=[];incomes=[];expenses=[]
        while month<=b:
            end=(date.fromisoformat(advance(month,1))-timedelta(days=1)).isoformat()
            data=self.f.summary(max(a,month),min(b,end));months.append(month[5:]+'/'+month[2:4]);incomes.append(data['income']/100);expenses.append(data['expense']/100);month=advance(month,1)
        right.plot(months,incomes,color=c['income'],label='Receitas',marker='.');right.plot(months,expenses,color=c['expense'],label='Despesas',marker='.')
        right.set_title('Evolução mensal · R$');right.legend(facecolor=c['alternate'],labelcolor=c['text']);right.tick_params(axis='x',rotation=45)
        self.canvas.draw_idle()

    def chart_click(self,event):
        if self.figure.axes and event.inaxes is self.figure.axes[0] and event.ydata is not None:
            index=round(event.ydata)
            if 0<=index<len(self.chart_categories):
                cat=self.db.one('SELECT id FROM categories WHERE name=?',(self.chart_categories[index],))
                if cat:
                    self.drill_metric('expense',cat['id'])

    @guarded
    def refresh_reports(self,*args):
        a,b=self.dates()
        while self.report_tabs.count():
            old=self.report_tabs.widget(0);self.report_tabs.removeTab(0);old.deleteLater()
        for title,headers,rows in report_tables(self.f,a,b,self.report_basis.currentData()):
            table=Table(headers);table.fill([(i,r) for i,r in enumerate(rows)]);self.report_tabs.addTab(table,title.split(' — ')[0])

    @guarded
    def new_entry(self,*args,defaults=None):
        if not self.db.one('SELECT id FROM accounts WHERE archived=0') and not self.db.one('SELECT id FROM cards WHERE archived=0'):
            has_accounts=bool(self.db.one('SELECT id FROM accounts LIMIT 1'))
            has_cards=bool(self.db.one('SELECT id FROM cards LIMIT 1'))
            if has_accounts or has_cards:
                self.nav.setCurrentRow(2 if has_accounts else 3)
                QMessageBox.information(self,'Cadastros existentes estão arquivados',
                    'Seus cadastros continuam salvos, mas estão arquivados e não podem ser usados em novos lançamentos. '
                    +('Selecione as contas na tela Contas e clique em Reativar selecionadas. Não é necessário cadastrar novamente.' if has_accounts else 'Abra a edição do cartão e desmarque a opção Arquivar. Não é necessário cadastrar novamente.'))
                return
            QMessageBox.information(self,'Comece por uma conta','Cadastre sua primeira conta. Em seguida você poderá registrar um lançamento.')
            if not self.entity('accounts'):return
        if EntryDialog(self.f,self,defaults=defaults).exec():self.refresh()

    @guarded
    def edit_selected(self,*args):
        identifier=self.entries_table.selected_id();self.edit_entry(identifier)

    def edit_entry(self,identifier):
        entry=self.db.one('SELECT * FROM entries WHERE id=?',(identifier,))
        if EntryDialog(self.f,self,entry).exec():self.refresh()

    @guarded
    def edit_invoice_entry(self,*args):self.edit_entry(self.invoice_table.selected_id())

    @guarded
    def duplicate_entry(self,*args):
        entry=self.db.one('SELECT * FROM entries WHERE id=?',(self.entries_table.selected_id(),))
        if EntryDialog(self.f,self,entry,True).exec():self.refresh()

    @guarded
    def delete_selected(self,*args):
        ids=self.entries_table.ids()
        if not ids:raise ValueError('Selecione os lançamentos para excluir.')
        scope='ocorrência'
        has_series=any(self.db.one('SELECT series_id FROM entries WHERE id=?',(i,))['series_id'] for i in ids)
        if has_series:
            scope,ok=QInputDialog.getItem(self,'Alcance da exclusão','Séries: excluir quais ocorrências? Uma ocorrência isolada é cancelada para impedir que seja gerada novamente. Excluir próximas encerra a série a partir dela.', ['ocorrência','esta e próximas','toda a série'],0,False)
            if not ok:return
        if QMessageBox.question(self,'Confirmar exclusão',f'Excluir {len(ids)} seleção(ões)? Alcance em séries: {scope}. Saldos e faturas serão recalculados. Esta ação pode alterar o histórico.',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes:
            self.f.delete_entries(ids,scope);self.refresh()

    @guarded
    def bulk_status(self,*args):
        ids=self.entries_table.ids()
        if not ids:raise ValueError('Selecione os lançamentos para alterar.')
        dialog=FormDialog('Alterar situação em lote',self)
        status=dialog.add('status','Situação para todos',combo(['previsto','pendente','pago','recebido','cancelado']))
        day=dialog.add('day','Data da realização',date_edit())
        dialog.hint(f'{len(ids)} lançamentos serão alterados. Tipos incompatíveis impedem toda a operação. Pago aplica-se a despesas e transferências; recebido a receitas. Cancelar remove os efeitos dos saldos.')
        def save():
            if QMessageBox.question(dialog,'Confirmar alteração',f'Aplicar “{status.currentData()}” a {len(ids)} lançamentos?',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:raise ValueError('Alteração não confirmada.')
            self.f.bulk_status(ids,status.currentData(),date_value(day))
        dialog.bind(save)
        if dialog.exec():self.refresh()

    @guarded
    def entity(self,table,defaults=None):
        result=EntityDialog(self.f,table,self,defaults=defaults).exec()
        if result:self.refresh()
        return result

    @guarded
    def delete_account(self,*args):
        identifier=self.accounts_table.selected_id()
        usage=self.f.account_usage(identifier);account=usage['account']
        if usage['entries'] or usage['series']:
            dialog=QMessageBox(self);dialog.setWindowTitle('Conta com histórico ou vínculos')
            dialog.setIcon(QMessageBox.Information)
            dialog.setText(f'A conta “{account["name"]}” possui {usage["entries"]} lançamento(s) e {usage["series"]} série(s) vinculada(s). '
                           'A exclusão foi impedida para preservar seus saldos, transferências e histórico. Você pode arquivar a conta para retirá-la dos novos lançamentos.')
            archive=dialog.addButton('Arquivar conta',QMessageBox.AcceptRole)
            cancel=dialog.addButton('Cancelar',QMessageBox.RejectRole);dialog.setDefaultButton(cancel)
            dialog.exec()
            if dialog.clickedButton()==archive:
                self.f.save_entity('accounts',{'archived':1},identifier);self.refresh()
                self.statusBar().showMessage('Conta arquivada. Saldo e histórico preservados.')
            return
        if QMessageBox.question(self,'Confirmar exclusão da conta',
                f'Excluir definitivamente a conta “{account["name"]}”? Ela não possui lançamentos ou séries vinculadas. '
                f'O saldo inicial cadastrado é {brl(account["opening"])}. Será criado um backup preventivo. '
                'A conta e seu saldo inicial deixarão de compor os saldos consolidados.',
                QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:
            return
        self.db.backup('antes-excluir-conta')
        self.f.delete_account(identifier);self.refresh()
        self.statusBar().showMessage('Conta excluída. Backup preventivo disponível na pasta de backups.')

    @guarded
    def reactivate_accounts(self,*args):
        ids=self.accounts_table.ids()
        if not ids:
            raise ValueError('Selecione uma ou mais contas para reativar.')
        with self.db.transaction():
            for identifier in ids:
                self.f.save_entity('accounts',{'archived':0},identifier)
        self.refresh()
        self.statusBar().showMessage('Contas selecionadas reativadas. Elas já estão disponíveis nos lançamentos.')

    @guarded
    def edit_entity(self,table,widget):
        entry=self.db.one(f'SELECT * FROM {table} WHERE id=?',(widget.selected_id(),))
        if EntityDialog(self.f,table,self,entry).exec():self.refresh()

    @guarded
    def delete_entity(self,table,widget):
        if table not in ('goals','budgets','contributions'):return
        identifier=widget.selected_id()
        text='Excluir este registro?'
        if table=='goals':text='Excluir esta meta e todos os seus aportes? As contas não serão alteradas.'
        if QMessageBox.question(self,'Confirmar exclusão',text,QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes:
            with self.db.transaction() as c:c.execute(f'DELETE FROM {table} WHERE id=?',(identifier,))
            self.refresh()

    @guarded
    def contribute(self,*args):
        self.entity('contributions',{'goal_id':self.goals_table.selected_id()})

    @guarded
    def card_purchase(self,*args):
        self.new_entry(defaults={'kind':'despesa','card_id':self.cards_table.selected_id(),'status':'pago'})

    @guarded
    def pay_invoice(self,*args):
        cid=self.cards_table.selected_id();month=self.invoice_month.text().strip();iso(month+'-01')
        due=self.f.invoice_total(cid,month)['remaining']
        if due<=0:raise ValueError('Esta fatura não possui saldo em aberto.')
        self.new_entry(defaults={'kind':'pagamento de fatura','card_id':cid,'invoice':month,'amount':due,'description':'Pagamento de fatura '+month,'status':'pago'})

    @guarded
    def refund(self,*args):
        self.new_entry(defaults={'kind':'estorno','card_id':self.cards_table.selected_id(),'invoice':self.invoice_month.text().strip(),'description':'Estorno de compra','status':'recebido'})

    def clear_filters(self,refresh=True):
        self.search.clear()
        for w in (self.type_filter,self.status_filter,self.category_filter,self.account_filter,self.card_filter):w.setCurrentIndex(0)
        set_combo(self.basis,'competência')
        if refresh:self.refresh_entries()

    def focus_search(self,*args):self.nav.setCurrentRow(1);self.search.setFocus()

    def drill_metric(self,key,category_id=None):
        if key=='balance':self.nav.setCurrentRow(2);return
        self.clear_filters(False)
        if key!='result':set_combo(self.type_filter,'receita' if 'income' in key else 'despesa')
        # Indicadores realizados incluem duas situações; o filtro interno mantém o total exato.
        if category_id is not None:set_combo(self.category_filter,category_id)
        a,b=self.dates();rows=self.f.entries(a,b,category_id=category_id)
        rows=[e for e in rows if e['kind'] in ('receita','despesa','estorno') and e['status']!='cancelado']
        if key=='result':rows=[e for e in rows if e['status'] in ('pago','recebido')]
        elif key.startswith('planned_'):rows=[e for e in rows if e['status'] in ('previsto','pendente') and (e['kind']=='receita')==('income' in key)]
        else:rows=[e for e in rows if e['status'] in ('pago','recebido') and (e['kind']=='receita')==('income' in key)]
        self.visible_entries=rows
        self.entries_table.fill([(e['id'],[e['description'],e['kind'],(brl(e['amount']),e['amount']),e['category'],e['card'] or e['account'],brdate(e['competence']),brdate(e['due']),brdate(e['paid']),e['status'],e['invoice'],e['tags']]) for e in rows])
        self.entries_empty.setText('Composição do indicador selecionado, incluindo estornos quando aplicável. Filtrar volta à consulta normal.');self.nav.setCurrentRow(1)


    def drill_due(self,kind):
        self.clear_filters(False);set_combo(self.basis,'vencimento');set_combo(self.type_filter,kind)
        a,b=self.dates()
        rows=[e for e in self.f.entries(a,b,'vencimento',kind=kind) if e['status'] in ('previsto','pendente') and not e['card_id']]
        self.visible_entries=rows
        self.entries_table.fill([(e['id'],[e['description'],e['kind'],(brl(e['amount']),e['amount']),e['category'],e['account'],brdate(e['competence']),brdate(e['due']),brdate(e['paid']),e['status'],e['invoice'],e['tags']]) for e in rows])
        self.entries_empty.setText('Composição das contas a pagar / receber por vencimento. Filtrar volta à consulta normal.');self.nav.setCurrentRow(1)

    @guarded
    def drill_account(self,*args):
        self.clear_filters(False);set_combo(self.account_filter,self.accounts_table.selected_id());self.refresh_entries();self.nav.setCurrentRow(1)

    @guarded
    def open_dashboard_account(self,*args):
        self.clear_filters(False);set_combo(self.account_filter,self.dashboard_accounts.selected_id());self.refresh_entries();self.nav.setCurrentRow(1)

    @guarded
    def import_csv(self,*args):
        path,_=QFileDialog.getOpenFileName(self,'Selecionar CSV','','CSV (*.csv);;Todos os arquivos (*)')
        if path and ImportDialog(self.f,path,self).exec():self.refresh()

    @guarded
    def export_entries(self,*args):
        path,_=QFileDialog.getSaveFileName(self,'Exportar lançamentos','lancamentos.csv','CSV (*.csv)')
        if path:export_csv(self.visible_entries,path);self.statusBar().showMessage('CSV exportado.')

    @guarded
    def pdf(self,*args):
        a,b=self.dates();path,_=QFileDialog.getSaveFileName(self,'Exportar relatório','relatorio-financeiro.pdf','PDF (*.pdf)')
        if path:export_pdf(self.f,a,b,self.report_basis.currentData(),path);self.statusBar().showMessage('Relatório PDF exportado.')

    @guarded
    def open_update_folder(self,*args):
        if not QDesktopServices.openUrl(QUrl('https://drive.google.com/drive/folders/1kg53G9nxNLNBIhZlnm--xNaOGXSAg_DO')):
            raise ValueError('Não foi possível abrir o navegador. Acesse a pasta de versões do Drive pelo link recebido nesta conversa.')

    def refresh_update_status(self):
        self.update_status.setText(updates.status_text())

    @guarded
    def install_update(self,*args):
        if not updates.available():
            raise ValueError('O atualizador precisa ser instalado uma vez. Use Instalar-atualizador.bat e depois abra iniciar-windows.bat.')
        path,_=QFileDialog.getOpenFileName(self,'Selecionar atualização da BatFinanças',str(Path.home()/'Downloads'),'Atualização BatFinanças (*.zip)')
        if not path:return
        manifest=updates.inspect_release(path)
        description=f"Instalar a versão {manifest['version']}? O programa fará backup do banco e reiniciará para substituir os arquivos. A versão anterior será recuperada se a nova não abrir."
        if manifest.get('notes'):description+='\n\n'+manifest['notes']
        if QMessageBox.question(self,'Confirmar atualização',description,QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:updates.prepare(self.db,path,demo=self.demo)
        finally:QApplication.restoreOverrideCursor()
        self.update_status.setText(updates.status_text())
        self.close()

    @guarded
    def save_settings(self,*args):
        self.db.set_setting('auto_backup',int(self.auto.isChecked()));self.db.set_setting('retention',self.retention.value());self.statusBar().showMessage('Preferências salvas.')

    @guarded
    def manual_backup(self,*args):
        path,_=QFileDialog.getSaveFileName(self,'Salvar backup','financas-backup.sqlite3','Banco SQLite (*.sqlite3)')
        if path:self.db.backup(destination=path);QMessageBox.information(self,'Backup concluído','Backup criado e validado. Guarde-o em local seguro.')

    @guarded
    def auto_backup(self,*args):
        if self.db.setting('auto_backup')=='1':self.db.backup('automatico',prune=True)

    @guarded
    def restore(self,*args):
        path,_=QFileDialog.getOpenFileName(self,'Selecionar backup','','Banco SQLite (*.sqlite3);;Todos os arquivos (*)')
        if not path:return
        self.db.validate(path)
        if QMessageBox.question(self,'Restaurar dados', 'Substituir os dados atuais por este backup? Será criado um backup preventivo antes da substituição. Todas as telas serão atualizadas.',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes:
            preventive=self.db.restore(path);self.f.generate_series();self.refresh()
            self.auto.setChecked(self.db.setting('auto_backup')=='1');self.retention.setValue(int(self.db.setting('retention')))
            preference=self.db.one("SELECT value FROM settings WHERE key='theme'")
            self.set_theme(preference['value'] if preference and preference['value'] in ('claro','escuro') else 'escuro',persist=False)
            QMessageBox.information(self,'Restauração concluída','Banco validado e restaurado. Backup preventivo:\n'+str(preventive))

    @guarded
    def export_all(self,*args):
        path,_=QFileDialog.getSaveFileName(self,'Exportar todos os dados','financas-completo.json','JSON (*.json)')
        if path:self.db.export_all(path);self.statusBar().showMessage('Exportação completa concluída. Para restauração no programa, use backup SQLite.')

    def manual(self,*args):
        dialog=FormDialog('Como usar a BatFinanças',self)
        dialog.hint('1. Em Contas, cadastre sua conta e o saldo inicial com a data de referência.\n\n2. Em Lançamentos, clique em Novo lançamento (Ctrl+N). Escolha tipo, categoria, conta e valor. Para uma movimentação já realizada, use pago ou recebido e informe a data efetiva.\n\n3. Previstos e pendentes não alteram o saldo. Transferências movimentam duas contas sem afetar receitas/despesas. No cartão, confirme a compra como paga e depois registre o pagamento da fatura na tela Cartões.\n\n4. Use o período no topo e clique Aplicar. Relatórios permitem alternar competência e caixa. Exporte CSV na tela Lançamentos e PDF em Relatórios.\n\n5. Crie backups nas Configurações e mantenha uma cópia em outra mídia. Backup e JSON contêm informações financeiras legíveis. Não há sincronização nem telemetria.\n\n6. Arquive contas e categorias pela edição. Para séries, confira o alcance antes de salvar ou excluir. Quantidades de recorrência são finitas (até 1.200).\n\nAtalhos: Ctrl+N novo, Ctrl+F busca, Ctrl+E editar lançamento, Ctrl+Q sair, F5 atualizar. Tab navega entre campos. Enter em uma busca aplica o filtro.\n\nMais detalhes de instalação, atualização, cartões, importação e privacidade estão no README.md e em docs/MANUAL.md do pacote.')
        dialog.buttons.clear();dialog.buttons.addButton('Fechar',QDialogButtonBox.RejectRole);dialog.exec()

    def update_greeting(self):
        self.greeting_label.setText(greeting())

    @guarded
    def set_theme(self,mode,persist=True):
        if mode not in ('claro','escuro'):
            raise ValueError('Escolha o modo claro ou escuro.')
        if persist:
            self.db.set_setting('theme',mode)
        self.theme_mode=mode;apply_theme(QApplication.instance(),mode)
        for action_button in self.findChildren(QPushButton):refresh_button_icon(action_button)
        if self.theme_toggle.isChecked()!=(mode=='escuro'):
            self.theme_toggle.set_dark(mode=='escuro',notify=False)
        self.theme_label.setText('Modo escuro' if mode=='escuro' else 'Modo claro')
        if hasattr(self,'theme_picker'):
            self.theme_picker.blockSignals(True);set_combo(self.theme_picker,mode);self.theme_picker.blockSignals(False)
        if hasattr(self,'figure'):
            self.refresh_dashboard()
        if hasattr(self,'debt_page'):
            self.debt_page.reload_data()
        self.nav.viewport().update()

    def show_intro(self):
        if self.intro is not None:
            return
        self.intro=BatIntro(self)
        self.intro.finished.connect(self._intro_finished)
        self.intro.start()

    def _intro_finished(self):
        self.intro=None;self.nav.setFocus()

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if getattr(self,'intro',None) is not None:
            self.intro.setGeometry(self.rect())

    def closeEvent(self,event):
        try:
            if self.db.setting('auto_backup')=='1':self.db.backup('automatico',prune=True)
        except (OSError,sqlite3.DatabaseError,ValueError):
            answer=QMessageBox.question(self,'Falha no backup ao fechar','Os dados já gravados continuam no banco, mas o backup automático falhou. Fechar mesmo assim?',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
            if answer!=QMessageBox.Yes:event.ignore();return
        if self.intro is not None:self.intro.finish()
        self.greeting_timer.stop();self.backup_timer.stop();event.accept()

from datetime import date
from PySide6.QtWidgets import (QLineEdit,QTextEdit,QSpinBox,QCheckBox,QDialog,QVBoxLayout,
 QLabel,QHBoxLayout,QDialogButtonBox,QMessageBox,QWidget,QScrollArea,QFormLayout)
from .widgets import FormDialog,combo,set_combo,date_edit,date_value,label,button,Table
from .money import cents,brl,brdate,advance
from .service import KINDS,STATUSES
from .reports import CSV_FIELDS,read_csv,preview_import,commit_import


def amount_text(value):
    return brl(value).replace('R$ ','')


def entities(db,table,current=None):
    return [(r['name']+(' (arquivado)' if r['archived'] else ''),r['id']) for r in db.rows(f'SELECT * FROM {table} WHERE archived=0 OR id=? ORDER BY name',(current or -1,))]


class EntryDialog(FormDialog):
    def __init__(self,finance,parent=None,entry=None,duplicate=False,defaults=None):
        super().__init__('Duplicar lançamento' if duplicate else 'Editar lançamento' if entry else 'Novo lançamento',parent)
        self.finance=finance
        e = dict(entry or {})
        e.update(defaults or {})
        if duplicate:
            e.update(series_id=None,occurrence=None,status='pendente' if e['kind'] not in ('estorno','pagamento de fatura') else ('recebido' if e['kind']=='estorno' else 'pago'))
        self.original=e
        self.identifier=None if duplicate else e.get('id')
        f = finance.db
        self.add('description','&Descrição',QLineEdit(e.get('description','')))
        kind = self.add('kind','&Tipo',combo(KINDS))
        set_combo(kind,e.get('kind','despesa'))
        self.add('amount','&Valor (R$)',QLineEdit(amount_text(e.get('amount',0))))
        self.add('category_id','&Categoria / subcategoria',combo(entities(f,'categories',e.get('category_id')),'Selecione'))
        self.add('account_id','Conta de &origem / movimentação',combo(entities(f,'accounts',e.get('account_id')),'Selecione a conta'))
        self.add('target_id','Conta de &destino',combo(entities(f,'accounts',e.get('target_id')),'Selecione'))
        self.add('card_id','Car&tão',combo(entities(f,'cards',e.get('card_id')),'Sem cartão'))
        for name in ('category_id','account_id','target_id','card_id'):
            set_combo(self.fields[name],e.get(name))
        if not e.get('account_id') and not e.get('card_id') and self.fields['account_id'].count()==2:
            self.fields['account_id'].setCurrentIndex(1)
        self.add('competence','Data de com&petência',date_edit(e.get('competence')))
        self.add('due','&Vencimento',date_edit(e.get('due')))
        self.add('status','&Situação',combo([]))
        self.add('paid','Data de pa&gamento / recebimento',date_edit(e.get('paid')))
        self.add('invoice','&Fatura (AAAA-MM)',QLineEdit(e.get('invoice') or date.today().isoformat()[:7]))
        self.add('tags','&Etiquetas',QLineEdit(e.get('tags','')))
        notes=QTextEdit(e.get('notes',''));notes.setMaximumHeight(90)
        self.add('notes','O&bservações',notes)
        self.availability=label('','muted');self.form.addRow(self.availability)
        self.hint('No cartão, “pago” significa compra confirmada, mesmo com a fatura em aberto. O vencimento da compra é calculado pelo cartão. Estornos usam a categoria e a fatura original.')
        self.mode=self.add('mode','&Repetição',combo(['lançamento único','parcelamento','recorrência']))
        self.count=QSpinBox();self.count.setRange(1,1200);self.count.setValue(12)
        self.add('count','&Quantidade de ocorrências',self.count)
        self.add('period','Periodi&cidade',combo(['mensal','semanal','diária','anual']))
        step=QSpinBox();step.setRange(1,120);step.setValue(1)
        self.add('step','A cada (períodos)',step)
        self.add('has_end','Limitar por data final',QCheckBox('Encerrar até a data abaixo'))
        self.add('end_date','Fim da recorrência',date_edit(advance(date.today(),1,'anual')))
        self.hint('Parcelamento: informe o valor TOTAL; os centavos restantes vão para as primeiras parcelas. Recorrência: o valor é por ocorrência. Em conta e recorrências, só a primeira ocorrência usa a situação informada. Parcelamento de cartão confirmado reconhece todas as parcelas na dívida; cada despesa segue sua competência.')
        self.scope=None
        if self.identifier and e.get('series_id'):
            self.scope=self.add('scope','Alcance da alteração',combo(['ocorrência','esta e próximas','toda a série']))
            self.hint('Em série, descrição, valor, tipo, categoria, conta, cartão, observações e etiquetas se aplicam ao alcance escolhido. Valor = cada parcela selecionada. Datas e situação mudam só nesta ocorrência; pagamentos anteriores são preservados.')
        if self.identifier:
            self.mode.setEnabled(False)
        kind.currentIndexChanged.connect(self.update_kind)
        self.fields['card_id'].currentIndexChanged.connect(self.update_enabled)
        self.fields['status'].currentIndexChanged.connect(self.update_enabled)
        self.mode.currentIndexChanged.connect(self.update_enabled)
        self.fields['has_end'].toggled.connect(self.update_enabled)
        self.update_kind()
        set_combo(self.fields['status'],e.get('status','pendente'))
        self.update_enabled()
        self.bind(self.save)

    def update_kind(self):
        kind=self.fields['kind'].currentData()
        old=self.fields['status'].currentData()
        self.fields['status'].clear()
        for status in STATUSES[kind]:
            self.fields['status'].addItem(status,status)
        set_combo(self.fields['status'],old or 'pendente')
        self.update_enabled()

    def update_enabled(self,*args):
        f=self.fields;k=f['kind'].currentData()
        card=bool(f['card_id'].currentData())
        for field,enabled in {'target_id':k=='transferência','card_id':k in ('despesa','pagamento de fatura','estorno'),
                              'account_id':k!='estorno' and not (k=='despesa' and card),
                              'category_id':k in ('receita','despesa','estorno'),
                              'invoice':k in ('estorno','pagamento de fatura'),
                              'due':not (k=='despesa' and card),'paid':f['status'].currentData() in ('pago','recebido')}.items():
            f[field].setEnabled(enabled)
        repeating=f['mode'].currentData()!='lançamento único' and not self.identifier
        for field in ('count','period','step','has_end'):
            f[field].setEnabled(repeating)
        f['end_date'].setEnabled(repeating and f['has_end'].isChecked())
        if k=='transferência':
            active=self.finance.db.one('SELECT count(*) total FROM accounts WHERE archived=0')['total']
            self.availability.setText('Selecione uma conta de origem e outra de destino. Ambas devem estar ativas. '+('Há menos de duas contas ativas. Cancele e abra Contas para cadastrar ou reativar uma conta.' if active<2 else ''))
        else:
            self.availability.setText('')

    def save(self):
        f=self.fields
        d={key:w.currentData() for key,w in f.items() if key in ('kind','category_id','account_id','target_id','card_id','status')}
        for key in ('description','tags','invoice'):
            d[key]=f[key].text().strip()
        d['notes']=f['notes'].toPlainText()
        d['amount']=cents(f['amount'].text())
        for key in ('competence','due','paid'):
            d[key]=date_value(f[key])
        k=d['kind']
        if k in ('receita','transferência'):
            d['card_id']=None
        if k=='despesa' and d['card_id'] or k=='estorno':
            d['account_id']=None
        if self.identifier:
            d['series_id']=self.original.get('series_id');d['occurrence']=self.original.get('occurrence')
            self.finance.edit_series(self.identifier,d,self.scope.currentData() if self.scope else 'ocorrência')
        elif self.mode.currentData()!='lançamento único':
            self.finance.create_series(d,self.mode.currentData(),f['count'].value(),f['period'].currentData(),f['step'].value(),date_value(f['end_date']) if f['has_end'].isChecked() else None)
        else:
            self.finance.save_entry(d)


class EntityDialog(FormDialog):
    def __init__(self,finance,table,parent=None,entry=None,defaults=None):
        names={'accounts':'conta','cards':'cartão','categories':'categoria','budgets':'orçamento','goals':'meta','contributions':'aporte'}
        super().__init__(('Editar ' if entry else 'Cadastrar ')+names[table],parent)
        self.finance,self.table=finance,table
        self.e=dict(entry or {});self.e.update(defaults or {})
        e=self.e;db=finance.db
        if table in ('accounts','cards','categories','goals'):
            self.add('name','&Nome',QLineEdit(e.get('name','')))
        if table=='accounts':
            self.add('kind','&Tipo',combo(['Conta bancária','Carteira','Poupança','Investimento','Outra']))
            set_combo(self.fields['kind'],e.get('kind'))
            self.add('opening','&Saldo inicial (R$)',QLineEdit(amount_text(e.get('opening',0))))
            self.add('reference','Data do saldo &inicial',date_edit(e.get('reference')))
            self.hint('O saldo inicial não é receita. Movimentações realizadas devem ter data igual ou posterior à referência.')
        if table=='cards':
            self.add('limit_cents','&Limite (R$)',QLineEdit(amount_text(e.get('limit_cents',0))))
            for key,title,default in (('closing','Dia de &fechamento',20),('due','Dia de &vencimento',28)):
                spin=QSpinBox();spin.setRange(1,31);spin.setValue(e.get(key,default));self.add(key,title,spin)
            self.hint('Compras no dia do fechamento entram na fatura atual. Vencimento igual ou anterior ao fechamento fica no mês seguinte. Alterar estes dias afeta novas compras; o histórico é preservado.')
        if table=='categories':
            parents=[(r['name'],r['id']) for r in db.rows('SELECT * FROM categories WHERE parent_id IS NULL AND archived=0 AND id<>? ORDER BY name',(e.get('id',-1),))]
            self.add('parent_id','Categoria &superior',combo(parents,'Categoria principal'))
            set_combo(self.fields['parent_id'],e.get('parent_id'))
        if table=='budgets':
            self.add('month','&Mês (AAAA-MM)',QLineEdit(e.get('month',date.today().isoformat()[:7])))
            self.add('category_id','&Categoria',combo(entities(db,'categories',e.get('category_id')),'Selecione'))
            set_combo(self.fields['category_id'],e.get('category_id'))
            self.add('amount','&Limite mensal (R$)',QLineEdit(amount_text(e.get('amount',0))))
            self.hint('O gasto é apurado por competência, com compras confirmadas e estornos. Categoria principal inclui subcategorias; não some limites sobrepostos.')
        if table=='goals':
            self.add('amount','&Valor desejado (R$)',QLineEdit(amount_text(e.get('amount',0))))
            self.add('deadline','&Prazo',date_edit(e.get('deadline')))
            self.hint('Aportes registram progresso e não alteram contas. Para mover dinheiro, registre uma transferência em Lançamentos.')
        if table=='contributions':
            self.add('amount','&Valor do aporte (R$)',QLineEdit(amount_text(e.get('amount',0))))
            self.add('day','&Data',date_edit(e.get('day')))
            self.add('notes','&Observações',QLineEdit(e.get('notes','')))
            self.hint('Este aporte só registra progresso na meta; não é despesa nem movimentação bancária.')
        if table in ('accounts','cards','categories'):
            if e.get('id'):
                check=QCheckBox('Arquivar e retirar dos novos lançamentos (preserva o histórico)')
                check.setChecked(bool(e.get('archived',0)))
                self.add('archived','Estado do cadastro',check)
            else:
                self.hint('Este cadastro será criado como ativo. Se precisar arquivá-lo depois, use a edição.')
        self.bind(self.save)

    def save(self):
        from .money import iso
        from .widgets import date_value
        values={}
        for key,w in self.fields.items():
            if key in ('amount','opening','limit_cents'):
                values[key]=cents(w.text())
            elif key in ('reference','deadline','day'):
                values[key]=date_value(w)
            elif key in ('kind','parent_id','category_id'):
                values[key]=w.currentData()
            elif key=='archived':
                values[key]=int(w.isChecked())
            elif key in ('closing','due'):
                values[key]=w.value()
            else:
                values[key]=w.text().strip()
        if self.table=='budgets':
            iso(values['month']+'-01')
            if not values['category_id']:
                raise ValueError('Selecione uma categoria.')
        if self.table=='contributions':
            values['goal_id']=self.e['goal_id']
        self.finance.save_entity(self.table,values,self.e.get('id'))


class ImportDialog(QDialog):
    def __init__(self,finance,path,parent=None):
        super().__init__(parent)
        self.setWindowTitle('Importar CSV — mapeamento e prévia');self.resize(1050,760)
        self.finance=finance;self.headers,self.rows=read_csv(path);self.preview=[]
        root=QVBoxLayout(self)
        root.addWidget(label('1. Mapeie as colunas. 2. Gere e confira a prévia. 3. Confirme a gravação.','title'))
        scroll=QScrollArea();scroll.setWidgetResizable(True);content=QWidget();form=QFormLayout(content)
        self.mapping={}
        required={'description','amount','competence'}
        for key,name in CSV_FIELDS.items():
            c=combo([(h,h) for h in self.headers],'Não importar')
            for h in self.headers:
                if h.casefold() in (name.casefold(),key.casefold()):
                    set_combo(c,h)
            form.addRow(name+(' *' if key in required else ''),c);self.mapping[key]=c
            c.currentIndexChanged.connect(self.invalidate)
        self.account=combo(entities(finance.db,'accounts'),'Selecione')
        self.category=combo(entities(finance.db,'categories'),'Selecione')
        form.addRow('Conta padrão (se coluna vazia)',self.account);form.addRow('Categoria padrão (se coluna vazia)',self.category)
        self.account.currentIndexChanged.connect(self.invalidate);self.category.currentIndexChanged.connect(self.invalidate)
        scroll.setWidget(content);scroll.setMaximumHeight(270);root.addWidget(scroll)
        root.addWidget(label('Valores: 1.234,56 ou 1234.56. Datas: DD/MM/AAAA ou AAAA-MM-DD. Cadastros são identificados pelo nome. Situação padrão: pendente. Linhas inválidas serão ignoradas após sua confirmação.','muted'))
        root.addWidget(button('Gerar / atualizar prévia',self.make_preview,'refresh'))
        self.table=Table(['Linha','Descrição','Valor','Resultado da validação']);root.addWidget(self.table,1)
        self.summary=label('Nenhuma prévia gerada.');root.addWidget(self.summary)
        self.duplicates=QCheckBox('Incluir possíveis duplicatas (padrão: ignorar)');root.addWidget(self.duplicates)
        self.error=label('','error');root.addWidget(self.error)
        bar=QHBoxLayout();root.addLayout(bar)
        self.save_button=button('Confirmar importação',self.commit,'save',True);self.save_button.setEnabled(False)
        bar.addWidget(self.save_button);bar.addWidget(button('Cancelar',self.reject,'back'))

    def invalidate(self,*args):
        self.preview=[]
        if hasattr(self,'save_button'):
            self.save_button.setEnabled(False);self.summary.setText('Mapeamento alterado: gere a prévia novamente.')

    def make_preview(self):
        try:
            mapping={k:w.currentData() for k,w in self.mapping.items()}
            if not all(mapping[k] for k in ('description','amount','competence')):
                raise ValueError('Mapeie Descrição, Valor e Competência.')
            self.preview=preview_import(self.finance,self.rows,mapping,self.account.currentData(),self.category.currentData())
            values=[]
            for p in self.preview:
                e=p['entry'] or {}
                values.append((p['line'],[p['line'],e.get('description',''),brl(e['amount']) if e else '',p['error'] or ('Possível duplicata' if p['duplicate'] else 'Válido')]))
            self.table.fill(values)
            errors=sum(bool(p['error']) for p in self.preview);duplicates=sum(p['duplicate'] for p in self.preview)
            self.summary.setText(f'{len(values)} linhas · {errors} com erro (serão ignoradas) · {duplicates} possíveis duplicatas. Confira todas as linhas antes de confirmar.')
            self.save_button.setEnabled(any(not p['error'] for p in self.preview));self.error.setText('')
        except (ValueError,OSError) as exc:
            self.error.setText(str(exc))

    def commit(self):
        selected=[p for p in self.preview if not p['error'] and (self.duplicates.isChecked() or not p['duplicate'])]
        if QMessageBox.question(self,'Confirmar gravação',f'Gravar {len(selected)} lançamentos válidos? Linhas com erro serão ignoradas. A operação será feita em uma única transação.',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:
            return
        try:
            n=commit_import(self.finance,self.preview,self.duplicates.isChecked())
            QMessageBox.information(self,'Importação concluída',f'{n} lançamentos gravados.');self.accept()
        except (ValueError,__import__('sqlite3').IntegrityError) as exc:
            self.error.setText(str(exc))

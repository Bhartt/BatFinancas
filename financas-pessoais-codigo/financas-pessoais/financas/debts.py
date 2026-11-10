"""Dívidas e amortizações em centavos, com saídas opcionais e atômicas."""
from datetime import date
from .money import iso

MAX_AMOUNT = 999_999_999_999_99


def positive_amount(value):
    if type(value) is not int or not 0 < value <= MAX_AMOUNT:
        raise ValueError('Informe um valor positivo, até R$ 999.999.999.999,99.')
    return value


def validate_debt_storage(conn):
    """Verifica vínculos e totais antes de aceitar um backup do esquema 3."""
    for identifier,name,amount,due in conn.execute('SELECT id,name,amount,due FROM debts'):
        if not name.strip():
            raise ValueError('O backup contém uma dívida sem nome.')
        positive_amount(amount)
        if due is not None and iso(due) != due:
            raise ValueError('O backup contém vencimento inválido em uma dívida.')
        total = conn.execute('SELECT coalesce(sum(amount),0) FROM debt_payments WHERE debt_id=?',(identifier,)).fetchone()[0]
        if total > amount:
            raise ValueError('O backup contém pagamentos superiores ao valor da dívida.')
    for amount,day,entry_id in conn.execute('SELECT amount,day,entry_id FROM debt_payments'):
        positive_amount(amount)
        if iso(day) != day:
            raise ValueError('O backup contém data inválida em um pagamento de dívida.')
        if entry_id is not None:
            entry = conn.execute('SELECT kind,status,amount,paid,competence,account_id,card_id,category_id,series_id FROM entries WHERE id=?',(entry_id,)).fetchone()
            if (not entry or entry[0] != 'despesa' or entry[1] != 'pago' or entry[2:5] != (amount,day,day)
                    or not entry[5] or entry[6] is not None or not entry[7] or entry[8] is not None):
                raise ValueError('O backup contém pagamento de dívida inconsistente com seu lançamento.')


class DebtFinance:
    def ensure_unlinked_entry(self, identifier):
        if identifier and self.db.one('SELECT id FROM debt_payments WHERE entry_id=?',(identifier,)):
            raise ValueError('Este lançamento pertence a um pagamento de dívida. Edite ou exclua o pagamento na aba Dívidas para manter os saldos consistentes.')

    def debts(self, text='', status='Todas'):
        rows = self.db.rows('''SELECT d.*,coalesce(sum(p.amount),0) paid,
             count(p.id) payments, max(p.day) last_payment FROM debts d
             LEFT JOIN debt_payments p ON p.debt_id=d.id GROUP BY d.id
             ORDER BY (d.amount=coalesce(sum(p.amount),0)), d.due IS NULL,d.due,d.id DESC''')
        result=[]
        for row in rows:
            row['remaining']=row['amount']-row['paid']
            row['settled']=row['remaining']==0
            row['percent']=row['paid']*100//row['amount']
            if text.casefold() not in (' '.join(str(row.get(k) or '') for k in ('name','creditor','notes'))).casefold():
                continue
            if status=='Em aberto' and row['settled'] or status=='Quitadas' and not row['settled']:
                continue
            result.append(row)
        return result

    def debt(self, identifier):
        row = next((r for r in self.debts() if r['id']==identifier),None)
        if not row:
            raise ValueError('Dívida não encontrada.')
        return row

    def save_debt(self, values, identifier=None):
        name=str(values.get('name') or '').strip()
        if not name:
            raise ValueError('Informe o nome da dívida.')
        amount=positive_amount(values.get('amount'))
        due=iso(values['due']) if values.get('due') else None
        category=values.get('category_id')
        with self.db.transaction() as c:
            old=self.debt(identifier) if identifier else None
            if old and amount < old['paid']:
                raise ValueError('O valor total não pode ser menor que o valor já pago. Corrija os pagamentos primeiro.')
            if category:
                cat=self.db.one('SELECT archived FROM categories WHERE id=?',(category,))
                if not cat or cat['archived'] and (not old or category!=old['category_id']):
                    raise ValueError('Escolha uma categoria ativa.')
            fields=(name,str(values.get('creditor') or '').strip(),amount,due,category,str(values.get('notes') or ''))
            if identifier:
                c.execute('UPDATE debts SET name=?,creditor=?,amount=?,due=?,category_id=?,notes=? WHERE id=?',fields+(identifier,))
            else:
                identifier=c.execute('INSERT INTO debts(name,creditor,amount,due,category_id,notes) VALUES(?,?,?,?,?,?)',fields).lastrowid
            return identifier

    def debt_payments(self, identifier):
        return self.db.rows('''SELECT p.*,e.account_id,e.category_id,a.name account,c.name category
            FROM debt_payments p LEFT JOIN entries e ON e.id=p.entry_id
            LEFT JOIN accounts a ON a.id=e.account_id LEFT JOIN categories c ON c.id=e.category_id
            WHERE p.debt_id=? ORDER BY p.day DESC,p.id DESC''',(identifier,))

    def save_debt_payment(self, debt_id, values, identifier=None):
        amount=positive_amount(values.get('amount'))
        day=iso(values.get('day') or date.today())
        if day > date.today().isoformat():
            raise ValueError('O pagamento não pode ter data futura.')
        mode=values.get('mode','conta')
        if mode not in ('conta','histórico'):
            raise ValueError('Escolha como registrar o pagamento.')
        notes=str(values.get('notes') or '')
        with self.db.transaction() as c:
            debt=self.debt(debt_id)
            old=self.db.one('SELECT * FROM debt_payments WHERE id=? AND debt_id=?',(identifier,debt_id)) if identifier else None
            if identifier and not old:
                raise ValueError('Pagamento não encontrado nesta dívida.')
            available=debt['remaining']+(old['amount'] if old else 0)
            if amount>available:
                raise ValueError('O pagamento ultrapassa o saldo restante da dívida.')
            previous_entry=old['entry_id'] if old else None
            entry_id=None
            if mode=='conta':
                entry_id=self._write_entry(dict(description='Pagamento de dívida: '+debt['name'],
                    kind='despesa',amount=amount,account_id=values.get('account_id'),
                    category_id=values.get('category_id'),competence=day,due=day,paid=day,
                    status='pago',notes=notes,tags='dívida'),previous_entry)
            if old:
                c.execute('UPDATE debt_payments SET amount=?,day=?,notes=?,entry_id=? WHERE id=?',
                          (amount,day,notes,entry_id,identifier))
            else:
                identifier=c.execute('INSERT INTO debt_payments(debt_id,amount,day,notes,entry_id) VALUES(?,?,?,?,?)',
                                     (debt_id,amount,day,notes,entry_id)).lastrowid
            if previous_entry and not entry_id:
                c.execute('DELETE FROM entries WHERE id=?',(previous_entry,))
            return identifier

    def delete_debt_payment(self, identifier):
        with self.db.transaction() as c:
            payment=self.db.one('SELECT * FROM debt_payments WHERE id=?',(identifier,))
            if not payment:
                raise ValueError('Pagamento não encontrado.')
            c.execute('DELETE FROM debt_payments WHERE id=?',(identifier,))
            if payment['entry_id']:
                c.execute('DELETE FROM entries WHERE id=?',(payment['entry_id'],))

    def delete_debt(self, identifier):
        with self.db.transaction() as c:
            debt=self.debt(identifier)
            if debt['payments']:
                raise ValueError('Esta dívida tem pagamentos. Seu histórico deve ser preservado; corrija os pagamentos antes de excluir o cadastro.')
            c.execute('DELETE FROM debts WHERE id=?',(identifier,))

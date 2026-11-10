"""Regras financeiras. Todos os valores persistidos são centavos inteiros."""
import json
from datetime import date
from .money import iso, advance, split_cents
from .debts import DebtFinance

KINDS = ('receita','despesa','transferência','pagamento de fatura','estorno')
STATUSES = {'receita':('previsto','pendente','recebido','cancelado'),
 'despesa':('previsto','pendente','pago','cancelado'),
 'transferência':('previsto','pendente','pago','cancelado'),
 'pagamento de fatura':('pago','cancelado'), 'estorno':('recebido','cancelado')}
REALIZED = ('pago','recebido')
FIELDS = ('description','kind','amount','category_id','account_id','target_id','card_id','competence','due','paid','status','notes','tags','invoice','series_id','occurrence')


class Finance(DebtFinance):
    def __init__(self, db):
        self.db = db

    def save_entity(self, table, values, identifier=None):
        allowed = {'accounts':('name','kind','opening','reference','archived'),
          'categories':('name','parent_id','archived'), 'cards':('name','limit_cents','closing','due','archived'),
          'budgets':('month','category_id','amount'), 'goals':('name','amount','deadline'),
          'contributions':('goal_id','amount','day','notes')}
        if table not in allowed or not set(values) <= set(allowed[table]):
            raise ValueError('Cadastro inválido.')
        values = dict(values)
        if 'name' in values:
            values['name'] = values['name'].strip()
            if not values['name']:
                raise ValueError('Informe um nome.')
        for key in ('amount','limit_cents'):
            if key in values and (type(values[key]) is not int or values[key] <= 0):
                raise ValueError('O valor deve ser maior que zero e estar em centavos.')
        if 'opening' in values and type(values['opening']) is not int:
            raise ValueError('O saldo deve estar em centavos inteiros.')
        for key in ('reference','deadline','day'):
            if key in values:
                values[key] = iso(values[key])
        if table == 'accounts' and identifier:
            first = self.db.one('SELECT min(paid) AS day FROM entries WHERE (account_id=? OR target_id=?) AND paid IS NOT NULL', (identifier,identifier))['day']
            if first and values.get('reference', '0001-01-01') > first:
                raise ValueError('A data de referência não pode ser posterior a uma movimentação realizada.')
        if table == 'categories' and values.get('parent_id'):
            parent = self.db.one('SELECT * FROM categories WHERE id=?', (values['parent_id'],))
            if not parent or parent['parent_id'] or parent['id'] == identifier:
                raise ValueError('Escolha uma categoria principal diferente como superior.')
            if identifier and self.db.one('SELECT id FROM categories WHERE parent_id=?', (identifier,)):
                raise ValueError('Uma categoria com subcategorias deve continuar como principal.')
        if table == 'budgets':
            iso(values['month']+'-01')
            if not values.get('category_id'):
                raise ValueError('Selecione uma categoria.')
        with self.db.transaction() as c:
            if identifier:
                keys = list(values)
                cur = c.execute(f'UPDATE {table} SET ' + ','.join(f'{k}=?' for k in keys) + ' WHERE id=?', [values[k] for k in keys] + [identifier])
                if not cur.rowcount:
                    raise ValueError('Cadastro não encontrado.')
                return identifier
            keys = list(values)
            return c.execute(f'INSERT INTO {table} ({",".join(keys)}) VALUES({",".join("?" for _ in keys)})', list(values.values())).lastrowid

    def account_usage(self,identifier):
        account=self.db.one('SELECT * FROM accounts WHERE id=?',(identifier,))
        if not account:
            raise ValueError('Conta não encontrada.')
        entries=self.db.one('SELECT count(*) total FROM entries WHERE account_id=? OR target_id=?',(identifier,identifier))['total']
        series=0
        for row in self.db.rows('SELECT template FROM series'):
            template=json.loads(row['template'])
            if identifier in (template.get('account_id'),template.get('target_id')):
                series+=1
        return {'account':account,'entries':entries,'series':series}

    def delete_account(self,identifier):
        """Exclusão real só de cadastro sem vínculos; histórico nunca é apagado em cascata."""
        with self.db.transaction() as c:
            usage=self.account_usage(identifier)
            if usage['entries'] or usage['series']:
                raise ValueError('Esta conta tem lançamentos ou séries vinculados. Arquive-a para preservar o histórico.')
            c.execute('DELETE FROM accounts WHERE id=?',(identifier,))

    def invoice_for(self, card, day):
        day = date.fromisoformat(iso(day))
        # Compra no fechamento entra na fatura atual; depois, na seguinte.
        anchor = date(day.year, day.month, 1).isoformat()
        return advance(anchor, int(day.day > card['closing']))[:7]

    def invoice_due(self, card, invoice):
        stored = self.db.one("SELECT min(due) day FROM entries WHERE card_id=? AND invoice=? AND kind='despesa'", (card['id'],invoice)) if card.get('id') else None
        if stored and stored['day']:
            return stored['day']
        # Se vencimento <= fechamento, o vencimento fica no mês seguinte.
        anchor = invoice + '-01'
        month = advance(anchor, int(card['due'] <= card['closing']))[:7]
        return advance(month + f'-01', 0)[:8] + f'{min(card["due"], __import__("calendar").monthrange(int(month[:4]),int(month[5:]))[1]):02d}'

    def validate_entry(self, values, identifier=None):
        d = {k:values.get(k) for k in FIELDS}
        d['description'] = str(d['description'] or '').strip()
        d['notes'] = d['notes'] or ''
        d['tags'] = d['tags'] or ''
        if not d['description']:
            raise ValueError('Informe a descrição.')
        if d['kind'] not in KINDS or d['status'] not in STATUSES[d['kind']]:
            raise ValueError('A situação não corresponde ao tipo de lançamento.')
        if type(d['amount']) is not int or not 0 < d['amount'] <= 999_999_999_999_99:
            raise ValueError('Informe um valor positivo em centavos inteiros (até R$ 999.999.999.999,99).')
        d['competence'], d['due'] = iso(d['competence']), iso(d['due'])
        d['paid'] = iso(d['paid']) if d['paid'] else None
        if d['status'] in REALIZED and not d['paid']:
            raise ValueError('Informe a data de pagamento ou recebimento.')
        if d['status'] not in REALIZED:
            d['paid'] = None
        for field, table in (('category_id','categories'),('account_id','accounts'),('target_id','accounts'),('card_id','cards')):
            if d[field] is not None:
                entity = self.db.one(f'SELECT * FROM {table} WHERE id=?', (d[field],))
                if not entity:
                    raise ValueError('Conta, cartão ou categoria não encontrado.')
                if entity['archived']:
                    original = self.db.one(f'SELECT {field} FROM entries WHERE id=?',(identifier,)) if identifier else None
                    if not original or original[field] != d[field]:
                        raise ValueError('Escolha um cadastro ativo.')
        kind = d['kind']
        if kind in ('receita','despesa'):
            if not d['category_id']:
                raise ValueError('Selecione uma categoria.')
            if bool(d['account_id']) == bool(d['card_id']) or (kind == 'receita' and d['card_id']):
                raise ValueError('Selecione uma conta, ou um cartão para a despesa.')
            d['target_id'] = None
        elif kind == 'transferência':
            if not d['account_id'] or not d['target_id'] or d['account_id'] == d['target_id']:
                raise ValueError('Selecione duas contas diferentes.')
            d['category_id'] = d['card_id'] = d['invoice'] = None
        elif kind == 'pagamento de fatura':
            if not d['account_id'] or not d['card_id'] or not d['invoice']:
                raise ValueError('Selecione a conta de origem, o cartão e a fatura (AAAA-MM).')
            try:
                iso(d['invoice'] + '-01')
            except ValueError as exc:
                raise ValueError('A fatura deve ter o formato AAAA-MM.') from exc
            d['category_id'] = d['target_id'] = None
            outstanding = self.invoice_total(d['card_id'], d['invoice'], exclude=identifier)['remaining']
            if d['status'] == 'pago' and d['amount'] > max(0, outstanding):
                raise ValueError('O pagamento ultrapassa o saldo em aberto desta fatura.')
        elif kind == 'estorno':
            if not d['card_id'] or not d['category_id'] or not d['invoice']:
                raise ValueError('Selecione cartão, categoria e fatura original do estorno (AAAA-MM).')
            iso(d['invoice'] + '-01')
            d['account_id'] = d['target_id'] = None
            total = self.invoice_total(d['card_id'], d['invoice'], exclude=identifier)
            if d['status'] == 'recebido' and d['amount'] > total['purchases'] - total['refunds']:
                raise ValueError('O estorno ultrapassa as compras desta fatura.')
        if d['card_id'] and kind == 'despesa':
            card = self.db.one('SELECT * FROM cards WHERE id=?', (d['card_id'],))
            d['invoice'] = self.invoice_for(card, d['competence'])
            d['due'] = self.invoice_due(card, d['invoice'])
        elif not d['card_id']:
            d['invoice'] = None
        for account in (d['account_id'], d['target_id']):
            if account:
                ref = self.db.one('SELECT reference FROM accounts WHERE id=?',(account,))['reference']
                if d['paid'] and d['paid'] < ref:
                    raise ValueError('A movimentação não pode anteceder a data do saldo inicial da conta.')
        if d['paid'] and d['paid'] > date.today().isoformat():
            raise ValueError('Uma movimentação realizada não pode ter data futura. Use previsto ou pendente.')
        return d

    def save_entry(self, values, identifier=None):
        with self.db.transaction():
            self.ensure_unlinked_entry(identifier)
            return self._write_entry(values,identifier)

    def _write_entry(self, values, identifier=None):
        """Gravação compartilhada; pagamentos vinculados são alterados pela aba Dívidas."""
        with self.db.transaction() as c:
            d = self.validate_entry(values, identifier)
            if identifier:
                if not self.db.one('SELECT id FROM entries WHERE id=?',(identifier,)):
                    raise ValueError('Lançamento não encontrado.')
                c.execute('UPDATE entries SET '+','.join(f'{k}=?' for k in FIELDS)+' WHERE id=?', [d[k] for k in FIELDS]+[identifier])
                return identifier
            return c.execute('INSERT INTO entries ('+','.join(FIELDS)+') VALUES('+','.join('?' for _ in FIELDS)+')', [d[k] for k in FIELDS]).lastrowid

    def entries(self, start=None, end=None, basis='competência', **filters):
        sql = '''SELECT e.*, coalesce(c.name,'Sem categoria') category, a.name account,
                 t.name target, k.name card FROM entries e
                 LEFT JOIN categories c ON c.id=e.category_id LEFT JOIN accounts a ON a.id=e.account_id
                 LEFT JOIN accounts t ON t.id=e.target_id LEFT JOIN cards k ON k.id=e.card_id WHERE 1=1'''
        params = []
        field = {'competência':'e.competence','caixa':'coalesce(e.paid,e.due)','vencimento':'e.due'}[basis]
        for op, val in (('>=',start),('<=',end)):
            if val:
                sql += f' AND {field}{op}?'
                params.append(iso(val))
        for name, val in filters.items():
            if val is None or val == '':
                continue
            if name == 'text':
                sql += " AND (e.description LIKE ? OR e.notes LIKE ? OR e.tags LIKE ?)"
                params.extend(['%'+val+'%']*3)
            elif name == 'account_id':
                sql += ' AND (e.account_id=? OR e.target_id=?)'
                params.extend([val,val])
            elif name == 'category_id':
                sql += ' AND (e.category_id=? OR c.parent_id=?)'
                params.extend([val,val])
            elif name in ('kind','status','card_id'):
                sql += f' AND e.{name}=?'
                params.append(val)
        return self.db.rows(sql + f' ORDER BY {field} DESC,e.id DESC', params)

    def balance(self, account_id, until=None):
        until = iso(until or date.today())
        a = self.db.one('SELECT * FROM accounts WHERE id=?',(account_id,))
        if until < a['reference']:
            return 0
        balance = a['opening']
        rows = self.db.rows("SELECT * FROM entries WHERE status IN ('pago','recebido') AND paid<=? AND (account_id=? OR target_id=?)", (until,account_id,account_id))
        for e in rows:
            balance += self.account_delta(e, account_id)
        return balance

    @staticmethod
    def account_delta(e, account_id):
        if e['kind'] == 'transferência':
            return e['amount'] * (1 if e['target_id'] == account_id else -1)
        if e['card_id'] and e['kind'] != 'pagamento de fatura':
            return 0
        return e['amount'] * (1 if e['kind'] == 'receita' else -1)

    def invoice_total(self, card_id, invoice=None, exclude=None):
        sql = "SELECT * FROM entries WHERE card_id=? AND status IN ('pago','recebido')"
        args = [card_id]
        if invoice:
            sql += ' AND invoice=?'
            args.append(invoice)
        if exclude:
            sql += ' AND id<>?'
            args.append(exclude)
        result = {'purchases':0,'payments':0,'refunds':0}
        for e in self.db.rows(sql,args):
            key = {'despesa':'purchases','estorno':'refunds','pagamento de fatura':'payments'}[e['kind']]
            result[key] += e['amount']
        result['remaining'] = result['purchases'] - result['refunds'] - result['payments']
        return result

    def summary(self, start, end, basis='competência'):
        result = {k:0 for k in ('income','expense','planned_income','planned_expense','receivable','payable')}
        categories = {}
        for e in self.entries(start,end,basis):
            if e['status'] == 'cancelado' or e['kind'] == 'transferência':
                continue
            real = e['status'] in REALIZED
            if basis == 'caixa' and e['card_id'] and e['kind'] != 'pagamento de fatura':
                continue
            if basis == 'competência' and e['kind'] == 'pagamento de fatura':
                continue
            income = e['kind'] == 'receita'
            signed = -e['amount'] if e['kind'] == 'estorno' else e['amount']
            key = ('income' if income else 'expense') if real else ('planned_income' if income else 'planned_expense')
            result[key] += signed
            if not real:
                result['receivable' if income else 'payable'] += signed
            if real and not income:
                categories[e['category']] = categories.get(e['category'],0) + signed
        if basis == 'caixa':
            # A fatura em aberto é uma saída prevista, mesmo sem pagamento cadastrado.
            # Somamos compras previstas/pendentes e confirmadas, descontando estornos
            # e pagamentos já realizados. A fatura aparece uma vez no seu vencimento.
            for invoice in self.db.rows('SELECT DISTINCT card_id,invoice FROM entries WHERE card_id IS NOT NULL AND invoice IS NOT NULL'):
                card = self.db.one('SELECT * FROM cards WHERE id=?',(invoice['card_id'],))
                due = self.invoice_due(card,invoice['invoice'])
                if start <= due <= end:
                    outstanding = 0
                    for e in self.db.rows("SELECT * FROM entries WHERE card_id=? AND invoice=? AND status<>'cancelado'",(card['id'],invoice['invoice'])):
                        if e['kind'] == 'despesa':
                            outstanding += e['amount']
                        elif e['status'] in REALIZED:
                            outstanding -= e['amount']
                    result['planned_expense'] += max(0,outstanding)
                    result['payable'] += max(0,outstanding)
        result['result'] = result['income'] - result['expense']
        result['categories'] = categories
        return result

    def budget_progress(self, month):
        result = []
        end = advance(month+'-01',1)
        rows = self.db.rows('SELECT b.*,c.name FROM budgets b JOIN categories c ON c.id=b.category_id WHERE month=?',(month,))
        for b in rows:
            spent = 0
            for e in self.entries(month+'-01', end, category_id=b['category_id']):
                if e['competence'] >= end:
                    continue
                if e['status'] in REALIZED and e['kind'] in ('despesa','estorno'):
                    spent += e['amount'] * (-1 if e['kind']=='estorno' else 1)
            b.update(spent=spent, available=b['amount']-spent, percent=spent*100//b['amount'])
            result.append(b)
        return result

    def delete_entries(self, ids, scope='ocorrência'):
        with self.db.transaction() as c:
            for identifier in ids:
                self.ensure_unlinked_entry(identifier)
                e = self.db.one('SELECT * FROM entries WHERE id=?',(identifier,))
                if not e:
                    continue
                if e['series_id'] and scope != 'ocorrência':
                    if scope == 'toda a série':
                        c.execute('DELETE FROM entries WHERE series_id=?',(e['series_id'],))
                        c.execute('UPDATE series SET active=0 WHERE id=?',(e['series_id'],))
                    else:
                        c.execute('DELETE FROM entries WHERE series_id=? AND occurrence>=?',(e['series_id'],e['occurrence']))
                        c.execute('UPDATE series SET active=0 WHERE id=?',(e['series_id'],))
                else:
                    # Cancelar mantém a chave da ocorrência e evita regeneração.
                    if e['series_id']:
                        c.execute("UPDATE entries SET status='cancelado',paid=NULL WHERE id=?",(identifier,))
                    else:
                        c.execute('DELETE FROM entries WHERE id=?',(identifier,))

    def bulk_status(self, ids, status, day):
        with self.db.transaction():
            for identifier in ids:
                e = self.db.one('SELECT * FROM entries WHERE id=?',(identifier,))
                e.update(status=status, paid=iso(day) if status in REALIZED else None)
                self.save_entry(e,identifier)

    def create_series(self, values, mode, count=12, period='mensal', step=1, end_date=None):
        if values['kind'] not in ('receita','despesa','transferência'):
            raise ValueError('Este tipo não aceita série.')
        if mode not in ('parcelamento','recorrência') or period not in ('diária','semanal','mensal','anual') or not 1 <= step <= 120:
            raise ValueError('Periodicidade inválida.')
        if not 1 <= count <= 1200:
            raise ValueError('Use entre 1 e 1.200 ocorrências.')
        if end_date and iso(end_date) < iso(values['due']):
            raise ValueError('O fim da série deve ser posterior à primeira ocorrência.')
        template = dict(values)
        template['competence'], template['due'] = iso(template['competence']),iso(template['due'])
        with self.db.transaction() as c:
            series_id = c.execute('INSERT INTO series(mode,template,anchor,period,step,count,end_date) VALUES(?,?,?,?,?,?,?)',
                (mode,json.dumps(template,ensure_ascii=False),template['due'],period,step,count,iso(end_date) if end_date else None)).lastrowid
            # Geração completa, finita e idempotente. Recorrências têm quantidade explícita.
            self.generate_series(series_id)
        return series_id

    def generate_series(self, series_id=None):
        rows = self.db.rows('SELECT * FROM series WHERE active=1' + (' AND id=?' if series_id else ''), (series_id,) if series_id else ())
        with self.db.transaction():
            for s in rows:
                template = json.loads(s['template'])
                parts = split_cents(template['amount'],s['count']) if s['mode']=='parcelamento' else None
                for i in range(s['count']):
                    if self.db.one('SELECT id FROM entries WHERE series_id=? AND occurrence=?',(s['id'],i)):
                        continue
                    d = dict(template)
                    d['due'] = advance(s['anchor'],i,s['period'],s['step'])
                    if s['end_date'] and d['due'] > s['end_date']:
                        break
                    d['competence'] = advance(template['competence'],i,s['period'],s['step'])
                    d['series_id'],d['occurrence'] = s['id'],i
                    if parts:
                        d['amount'] = parts[i]
                        d['description'] = f"{template['description']} ({i+1}/{s['count']})"
                    if i and not (s['mode']=='parcelamento' and template.get('card_id') and template.get('status')=='pago'):
                        d['status'],d['paid'] = 'previsto',None
                    self.save_entry(d)

    def edit_series(self, identifier, values, scope):
        current = self.db.one('SELECT * FROM entries WHERE id=?',(identifier,))
        if scope == 'ocorrência' or not current['series_id']:
            return self.save_entry(values,identifier)
        with self.db.transaction() as c:
            s = self.db.one('SELECT * FROM series WHERE id=?',(current['series_id'],))
            template = json.loads(s['template'])
            sql = 'SELECT * FROM entries WHERE series_id=?'
            args = [s['id']]
            if scope == 'esta e próximas':
                sql += ' AND occurrence>=?'
                args.append(current['occurrence'])
            # Campos de data/situação se aplicam só à ocorrência selecionada; demais
            # campos são propagados. Datas e pagamentos anteriores são preservados.
            shared = ('description','amount','kind','category_id','account_id','target_id','card_id','notes','tags')
            for old in self.db.rows(sql,args):
                changed = dict(old)
                for field in shared:
                    changed[field] = values[field]
                if s['mode']=='parcelamento':
                    # Em edição o valor passa a ser o valor de CADA parcela selecionada.
                    changed['description'] = values['description'].split(' (')[0] + f" ({old['occurrence']+1}/{s['count']})"
                if old['id'] == identifier:
                    for field in ('competence','due','paid','status'):
                        changed[field] = values[field]
                self.save_entry(changed,old['id'])
            for field in shared:
                template[field] = values[field]
            c.execute('UPDATE series SET template=? WHERE id=?',(json.dumps(template,ensure_ascii=False),s['id']))

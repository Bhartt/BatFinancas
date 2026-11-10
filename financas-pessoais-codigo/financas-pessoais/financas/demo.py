"""Dados opcionais, gravados somente no diretório de demonstração."""
from datetime import date,timedelta
from .money import advance


def seed(finance):
    db=finance.db
    if db.one('SELECT id FROM accounts LIMIT 1'):
        return
    today=date.today();first=today.replace(day=1).isoformat()
    reference=advance(first,-5)
    account=finance.save_entity('accounts',dict(name='Conta do dia a dia',kind='Conta bancária',opening=245000,reference=reference))
    savings=finance.save_entity('accounts',dict(name='Reserva de segurança',kind='Poupança',opening=800000,reference=reference))
    card=finance.save_entity('cards',dict(name='Cartão pessoal',limit_cents=600000,closing=20,due=28))
    categories={r['name']:r['id'] for r in db.rows('SELECT * FROM categories')}
    with db.transaction():
        for month in range(-5,1):
            day=advance(first,month)
            for kind,description,amount,category in [('receita','Salário mensal',650000,'Salário'),('despesa','Aluguel',180000,'Moradia'),('despesa','Supermercado',78540+month*1230,'Alimentação'),('despesa','Transporte',27500,'Transporte'),('despesa','Internet e serviços',14990,'Assinaturas')]:
                finance.save_entry(dict(description=description,kind=kind,amount=amount,category_id=categories[category],account_id=account,competence=day,due=day,paid=day,status='recebido' if kind=='receita' else 'pago'))
        finance.save_entry(dict(description='Reserva do mês',kind='transferência',amount=50000,account_id=account,target_id=savings,competence=first,due=first,paid=first,status='pago'))
        finance.save_entry(dict(description='Consulta de rotina',kind='despesa',amount=28000,category_id=categories['Saúde'],account_id=account,competence=first,due=advance(first,0)[:8]+'25',status='pendente'))
        finance.create_series(dict(description='Curso de fotografia',kind='despesa',amount=149990,category_id=categories['Educação'],card_id=card,competence=first,due=first,paid=first,status='pago'),'parcelamento',5)
        finance.save_entity('budgets',dict(month=first[:7],category_id=categories['Alimentação'],amount=90000))
        finance.save_entity('budgets',dict(month=first[:7],category_id=categories['Moradia'],amount=200000))
        goal=finance.save_entity('goals',dict(name='Reserva de emergência',amount=2000000,deadline=advance(first,12)))
        finance.save_entity('contributions',dict(goal_id=goal,amount=800000,day=first,notes='Valor já reservado'))
        debt=finance.save_debt(dict(name='Acordo de estudos',creditor='Instituição de ensino',amount=240000,
            due=advance(first,3),category_id=categories['Educação']))
        finance.save_debt_payment(debt,dict(amount=60000,day=first,mode='conta',account_id=account,category_id=categories['Educação']))
        debt=finance.save_debt(dict(name='Manutenção da casa',creditor='Prestador de serviço',amount=180000,
            due=advance(first,2),category_id=categories['Moradia']))
        finance.save_debt_payment(debt,dict(amount=45000,day=first,mode='conta',account_id=account,category_id=categories['Moradia']))
        debt=finance.save_debt(dict(name='Compra pessoal',creditor='Exemplo quitado',amount=95000,category_id=categories['Outros']))
        finance.save_debt_payment(debt,dict(amount=95000,day=advance(reference,-1),mode='histórico',
            notes='Pagamento anterior ao saldo inicial; apenas acompanhamento.'))

import pytest
from financas.db import Database
from financas.service import Finance

@pytest.fixture
def finance(tmp_path):
    db=Database(tmp_path/'dados'/'financas.sqlite3');f=Finance(db)
    a=f.save_entity('accounts',dict(name='Conta A',kind='Conta bancária',opening=100000,reference='2024-01-01'))
    b=f.save_entity('accounts',dict(name='Conta B',kind='Carteira',opening=5000,reference='2024-01-01'))
    c=f.save_entity('cards',dict(name='Cartão',limit_cents=200000,closing=20,due=5))
    f.a,f.b,f.card=a,b,c
    f.category=db.one("SELECT id FROM categories WHERE name='Alimentação'")['id']
    yield f
    db.close()

@pytest.fixture
def entry(finance):
    return dict(description='Compra',kind='despesa',amount=10001,category_id=finance.category,
                account_id=finance.a,competence='2024-01-15',due='2024-01-15',paid='2024-01-15',status='pago')

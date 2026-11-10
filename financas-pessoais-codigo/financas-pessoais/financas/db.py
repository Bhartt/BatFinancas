"""SQLite transacional, esquema versionado e backup validado."""
import json
import os
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

SCHEMA_VERSION = 3
SCHEMA = '''
CREATE TABLE accounts(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE,
 kind TEXT NOT NULL, opening INTEGER NOT NULL CHECK(typeof(opening)='integer'), reference TEXT NOT NULL,
 archived INTEGER NOT NULL DEFAULT 0);
CREATE TABLE categories(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE,
 parent_id INTEGER REFERENCES categories(id), archived INTEGER NOT NULL DEFAULT 0);
CREATE TABLE cards(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, limit_cents INTEGER NOT NULL CHECK(limit_cents>0),
 closing INTEGER NOT NULL CHECK(closing BETWEEN 1 AND 31), due INTEGER NOT NULL CHECK(due BETWEEN 1 AND 31),
 archived INTEGER NOT NULL DEFAULT 0);
CREATE TABLE series(id INTEGER PRIMARY KEY, mode TEXT NOT NULL, template TEXT NOT NULL, anchor TEXT NOT NULL,
 period TEXT NOT NULL, step INTEGER NOT NULL, count INTEGER, end_date TEXT, active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE entries(id INTEGER PRIMARY KEY, description TEXT NOT NULL, kind TEXT NOT NULL
 CHECK(kind IN ('receita','despesa','transferência','pagamento de fatura','estorno')),
 amount INTEGER NOT NULL CHECK(typeof(amount)='integer' AND amount>0),
 category_id INTEGER REFERENCES categories(id), account_id INTEGER REFERENCES accounts(id),
 target_id INTEGER REFERENCES accounts(id), card_id INTEGER REFERENCES cards(id),
 competence TEXT NOT NULL, due TEXT NOT NULL, paid TEXT, status TEXT NOT NULL,
 notes TEXT NOT NULL DEFAULT '', tags TEXT NOT NULL DEFAULT '', invoice TEXT,
 series_id INTEGER REFERENCES series(id), occurrence INTEGER, UNIQUE(series_id,occurrence));
CREATE INDEX entries_dates ON entries(competence,due,paid);
CREATE INDEX entries_card ON entries(card_id,invoice);
CREATE TABLE budgets(id INTEGER PRIMARY KEY, month TEXT NOT NULL, category_id INTEGER NOT NULL REFERENCES categories(id),
 amount INTEGER NOT NULL CHECK(amount>0), UNIQUE(month,category_id));
CREATE TABLE goals(id INTEGER PRIMARY KEY, name TEXT NOT NULL, amount INTEGER NOT NULL CHECK(amount>0), deadline TEXT NOT NULL);
CREATE TABLE contributions(id INTEGER PRIMARY KEY, goal_id INTEGER NOT NULL REFERENCES goals(id) ON DELETE CASCADE,
 amount INTEGER NOT NULL CHECK(amount>0), day TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '');
CREATE TABLE settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
INSERT INTO settings VALUES('retention','15');
INSERT INTO settings VALUES('auto_backup','1');
'''
MIGRATION_2 = '''CREATE TABLE import_batches(id INTEGER PRIMARY KEY, created TEXT NOT NULL, rows INTEGER NOT NULL);
CREATE INDEX entries_status ON entries(status);'''
MIGRATION_3 = '''
CREATE TABLE debts(id INTEGER PRIMARY KEY, name TEXT NOT NULL CHECK(length(trim(name))>0),
 creditor TEXT NOT NULL DEFAULT '', amount INTEGER NOT NULL CHECK(typeof(amount)='integer' AND amount>0),
 due TEXT, category_id INTEGER REFERENCES categories(id), notes TEXT NOT NULL DEFAULT '');
CREATE TABLE debt_payments(id INTEGER PRIMARY KEY, debt_id INTEGER NOT NULL REFERENCES debts(id),
 amount INTEGER NOT NULL CHECK(typeof(amount)='integer' AND amount>0), day TEXT NOT NULL,
 notes TEXT NOT NULL DEFAULT '', entry_id INTEGER UNIQUE REFERENCES entries(id));
CREATE INDEX debt_payments_debt ON debt_payments(debt_id,day);
'''


def data_folder(demo=False):
    if os.name == 'nt':
        base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local'))
    elif __import__('sys').platform == 'darwin':
        base = Path.home() / 'Library/Application Support'
    else:
        base = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share'))
    return base / ('FinancasPessoais-Demonstracao' if demo else 'FinancasPessoais')


class Database:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            self.validate(self.path)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute('PRAGMA foreign_keys=ON')
        self.conn.execute('PRAGMA journal_mode=DELETE')
        self.conn.execute('PRAGMA synchronous=FULL')
        version = self.conn.execute('PRAGMA user_version').fetchone()[0]
        if version > SCHEMA_VERSION:
            self.conn.close()
            raise ValueError('Este banco foi criado por uma versão mais nova do programa.')
        if version and version < SCHEMA_VERSION:
            self.backup('antes-migracao')
        if version == 0:
            # Todo o esquema e a versão são confirmados juntos.
            self.conn.executescript('BEGIN IMMEDIATE;\n' + SCHEMA + '\nPRAGMA user_version=1; COMMIT;')
            with self.transaction():
                for name in ('Moradia','Alimentação','Transporte','Saúde','Educação','Lazer','Assinaturas','Salário','Outros'):
                    self.conn.execute('INSERT INTO categories(name) VALUES(?)', (name,))
            version = 1
        if version == 1:
            self.conn.executescript('BEGIN IMMEDIATE;\n' + MIGRATION_2 + '\nPRAGMA user_version=2; COMMIT;')
            version = 2
        if version == 2:
            self.conn.executescript('BEGIN IMMEDIATE;\n' + MIGRATION_3 + '\nPRAGMA user_version=3; COMMIT;')
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    @contextmanager
    def transaction(self):
        if self.conn.in_transaction:
            yield self.conn
            return
        self.conn.execute('BEGIN IMMEDIATE')
        try:
            yield self.conn
            self.conn.commit()
        except BaseException:
            self.conn.rollback()
            raise

    def rows(self, sql, args=()):
        return [dict(r) for r in self.conn.execute(sql, args)]

    def one(self, sql, args=()):
        r = self.conn.execute(sql, args).fetchone()
        return dict(r) if r else None

    def setting(self, key):
        return self.one('SELECT value FROM settings WHERE key=?', (key,))['value']

    def set_setting(self, key, value):
        with self.transaction():
            self.conn.execute('INSERT OR REPLACE INTO settings VALUES(?,?)', (key, str(value)))

    @staticmethod
    def validate(path):
        candidate = Path(path).resolve()
        if not candidate.is_file():
            raise ValueError('Arquivo de banco não encontrado.')
        try:
            with sqlite3.connect(candidate.as_uri() + '?mode=ro', uri=True) as c:
                if c.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise ValueError('O banco está corrompido.')
                version = c.execute('PRAGMA user_version').fetchone()[0]
                if not 1 <= version <= SCHEMA_VERSION:
                    raise ValueError('Versão de banco incompatível.')
                expected = {'accounts','categories','cards','entries','series','budgets','goals','contributions','settings'}
                names = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if not expected <= names or c.execute('PRAGMA foreign_key_check').fetchone():
                    raise ValueError('Arquivo inválido ou com referências inconsistentes.')
                # Compila as consultas e verifica as colunas esperadas antes de substituir o banco.
                for table, cols in {'accounts':'id,name,kind,opening,reference,archived',
                                    'entries':'id,description,kind,amount,category_id,account_id,target_id,card_id,competence,due,paid,status,notes,tags,invoice,series_id,occurrence',
                                    'series':'id,mode,template,anchor,period,step,count,end_date,active',
                                    'cards':'id,name,limit_cents,closing,due,archived',
                                    'categories':'id,name,parent_id,archived', 'budgets':'id,month,category_id,amount',
                                    'goals':'id,name,amount,deadline','contributions':'id,goal_id,amount,day,notes',
                                    'settings':'key,value'}.items():
                    c.execute(f'SELECT {cols} FROM {table} LIMIT 0')
                if version >= 2:
                    c.execute('SELECT id,created,rows FROM import_batches LIMIT 0')
                if version >= 3:
                    c.execute('SELECT id,name,creditor,amount,due,category_id,notes FROM debts LIMIT 0')
                    c.execute('SELECT id,debt_id,amount,day,notes,entry_id FROM debt_payments LIMIT 0')
                    from .debts import validate_debt_storage
                    validate_debt_storage(c)
                settings = dict(c.execute('SELECT key,value FROM settings'))
                if settings.get('auto_backup') not in ('0','1') or not 1 <= int(settings.get('retention','0')) <= 365:
                    raise ValueError('O backup tem preferências inválidas.')
                from .money import iso
                for table, fields in (('entries',('competence','due','paid')),('accounts',('reference',)),
                                      ('goals',('deadline',)),('contributions',('day',))):
                    for row in c.execute(f'SELECT {",".join(fields)} FROM {table}'):
                        for value in row:
                            if value is not None and iso(value) != value:
                                raise ValueError('O backup contém datas inválidas.')
                for mode, template, period, step, count, anchor, end in c.execute('SELECT mode,template,period,step,count,anchor,end_date FROM series'):
                    if mode not in ('parcelamento','recorrência') or period not in ('diária','semanal','mensal','anual') or not 1 <= step <= 120 or not 1 <= count <= 1200:
                        raise ValueError('O backup contém uma série inválida.')
                    data = json.loads(template)
                    if not isinstance(data,dict) or type(data.get('amount')) is not int or data['amount'] <= 0:
                        raise ValueError('O backup contém um modelo de série inválido.')
                    iso(anchor)
                    if end:
                        iso(end)
                for kind,status,amount,paid in c.execute('SELECT kind,status,amount,paid FROM entries'):
                    from .service import STATUSES
                    if kind not in STATUSES or status not in STATUSES[kind] or type(amount) is not int or amount <= 0 or (status in ('pago','recebido')) != bool(paid):
                        raise ValueError('O backup contém um lançamento inválido.')
        except sqlite3.DatabaseError as exc:
            raise ValueError('O arquivo não é um banco válido do Finanças Pessoais.') from exc

    def backup(self, prefix='backup', destination=None, prune=False):
        folder = self.path.parent / 'backups'
        folder.mkdir(exist_ok=True)
        target = Path(destination) if destination else folder / f'{prefix}-{datetime.now():%Y%m%d-%H%M%S-%f}.sqlite3'
        if target.resolve() == self.path.resolve():
            raise ValueError('O backup deve ser salvo em outro arquivo.')
        with sqlite3.connect(target) as out:
            self.conn.backup(out)
        self.validate(target)
        if prune:
            retain = max(1, int(self.setting('retention')))
            # Backups preventivos não participam da rotação automática.
            for old in sorted(folder.glob('automatico-*.sqlite3'), reverse=True)[retain:]:
                old.unlink()
        return target

    def restore(self, source):
        source = Path(source).resolve()
        if source == self.path.resolve():
            raise ValueError('Escolha um backup diferente do banco em uso.')
        self.validate(source)
        preventive = self.backup('antes-restauracao')
        staged = self.path.with_suffix('.restaurando')
        try:
            with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as src, sqlite3.connect(staged) as dst:
                src.backup(dst)
            self.validate(staged)
            self.conn.close()
            os.replace(staged, self.path)
            self.__init__(self.path)
        except BaseException:
            try:
                self.conn.execute('SELECT 1')
            except sqlite3.ProgrammingError:
                self.__init__(self.path)
            raise
        finally:
            staged.unlink(missing_ok=True)
        return preventive

    def export_all(self, path):
        tables = ('accounts','categories','cards','entries','series','budgets','goals','contributions','settings','import_batches','debts','debt_payments')
        data = {'versao_esquema':SCHEMA_VERSION, 'tabelas':{t:self.rows(f'SELECT * FROM {t}') for t in tables}}
        Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

    def close(self):
        self.conn.close()

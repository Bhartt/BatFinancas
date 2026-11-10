"""Duas execuções completas do ponto de entrada, com rede bloqueada no processo."""
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = r'''
import os,socket,sys
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication,QMessageBox

def forbidden(*args,**kwargs):
    raise AssertionError('A aplicação tentou acessar a rede')
socket.create_connection=forbidden
socket.socket.connect=forbidden
from financas.db import Database
from financas.service import Finance
from financas.__main__ import main
folder=Path(sys.argv[1]);phase=sys.argv[2]
sys.argv=['iniciar.py','--dados',str(folder)]
original_exec=QApplication.exec
errors=[]
QMessageBox.critical=lambda *args:errors.append(args[2])

def run_loop(self):
    def act():
        try:
            from financas.window import Window
            window=next(w for w in QApplication.topLevelWidgets() if isinstance(w,Window))
            f=window.f
            if phase=='gravar':
                account=f.save_entity('accounts',dict(name='Conta persistente',kind='Carteira',opening=10000,reference='2024-01-01'))
                category=f.db.one('SELECT id FROM categories')['id']
                f.save_entry(dict(description='Persistência entre processos',kind='receita',amount=4321,category_id=category,account_id=account,
                    competence='2024-01-15',due='2024-01-15',paid='2024-01-15',status='recebido'))
                window.refresh()
            else:
                account=f.db.one('SELECT id FROM accounts')['id']
                assert f.balance(account)==14321
                assert len(f.entries())==1
            window.close()
        except BaseException as exc:
            errors.append(type(exc).__name__+': '+str(exc));self.quit()
    QTimer.singleShot(50,act)
    return original_exec()
QApplication.exec=run_loop
result=main()
assert not errors,errors
assert result==0
print('Processo concluído sem rede:',phase)
'''


def test_two_full_processes_persist_offline(tmp_path):
    root=Path(__file__).resolve().parents[1]
    env=dict(os.environ,QT_QPA_PLATFORM='offscreen',XDG_CACHE_HOME=str(tmp_path/'cache'))
    for phase in ('gravar','reabrir'):
        run=subprocess.run([sys.executable,'-c',SCRIPT,str(tmp_path/'dados'),phase],cwd=root,env=env,capture_output=True,text=True,timeout=40)
        assert run.returncode==0,run.stdout+'\n'+run.stderr

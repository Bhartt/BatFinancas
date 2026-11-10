import argparse
import logging
from logging.handlers import RotatingFileHandler
import os
import sys
from pathlib import Path


def main(startup_ready=None,update_trial=False,update_lock=None):
    class Parser(argparse.ArgumentParser):
        def error(self,message):
            self.print_usage(sys.stderr)
            self.exit(2,'Argumentos inválidos. Use --ajuda. Não combine --demo e --dados.\n')
    parser=Parser(description='BatFinanças — aplicativo local em PT-BR',add_help=False,usage='%(prog)s [--demo | --dados PASTA]')
    parser._optionals.title='Opções'
    parser.add_argument('-h','--help','--ajuda',action='help',help='Mostrar instruções e sair')
    group=parser.add_mutually_exclusive_group()
    group.add_argument('--demo',action='store_true',help='Usar dados fictícios em uma pasta separada')
    group.add_argument('--dados',type=Path,help='Pasta de dados alternativa (uso avançado e testes)')
    args=parser.parse_args()
    # Matplotlib não escreve na pasta da instalação nem precisa de rede.
    from .db import data_folder,Database
    folder=(args.dados or data_folder(args.demo)).resolve()
    folder.mkdir(parents=True,exist_ok=True)
    os.environ.setdefault('MPLCONFIGDIR',str(folder/'cache-graficos'))
    from PySide6.QtCore import Qt,QLockFile
    from PySide6.QtWidgets import QApplication,QMessageBox
    QApplication.setAttribute(Qt.AA_DontUseNativeDialogs,True)
    app=QApplication(sys.argv[:1]);app.setApplicationName('BatFinanças');app.setOrganizationName('FinancasPessoais')
    from .localization import configure
    configure(app)
    lock=update_lock or QLockFile(str(folder/'aplicacao.lock'));lock.setStaleLockTime(0)
    if update_lock is None and not lock.tryLock(100):
        if update_trial:return 1
        QMessageBox.warning(None,'Aplicação já aberta','Esta pasta de dados já está aberta em outra instância. Feche a outra janela antes de continuar.');return 1
    handler=RotatingFileHandler(folder/'erros.log',maxBytes=256000,backupCount=2,encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    logging.basicConfig(level=logging.ERROR,handlers=[handler])
    db=None
    try:
        db=Database(folder/'financas.sqlite3')
        from .service import Finance
        finance=Finance(db)
        if args.demo:
            from .demo import seed
            seed(finance)
        finance.generate_series()
        if db.setting('auto_backup')=='1':
            db.backup('automatico',prune=True)
        from .widgets import STYLE
        app.setStyle('Fusion');app.setStyleSheet(STYLE)
        from .window import Window
        window=Window(finance,args.demo)
        if startup_ready is not None:startup_ready();window.refresh_update_status()
        window.show();window.show_intro()
        result=app.exec()
        return result
    except Exception as exc:
        logging.error('Falha de inicialização: %s',type(exc).__name__)
        if update_trial:return 1
        QMessageBox.critical(None,'Falha ao abrir','Não foi possível iniciar o programa. Os arquivos existentes foram preservados. Verifique espaço em disco, permissões e a versão do banco. Detalhe: '+(str(exc) if isinstance(exc,ValueError) else type(exc).__name__))
        return 1
    finally:
        if db:
            db.close()
        if update_lock is None:lock.unlock()


if __name__=='__main__':
    raise SystemExit(main())

"""Integração de atualização local. Sem conexão automática ou envio de dados."""
import json
import os
from pathlib import Path
import sys
import batfinancas_bootstrap as engine
from . import __version__


def install_root():return Path(__file__).resolve().parent.parent


def available():
    root=install_root()
    return (not getattr(sys,'frozen',False) and (root/'batfinancas_bootstrap.py').is_file()
            and os.environ.get('BATFINANCAS_BOOTSTRAP_ROOT')==str(root))


def inspect_release(path):
    if not available():
        raise ValueError('Abra pelo arquivo iniciar-windows.bat da instalação com o atualizador. Na primeira instalação, use Instalar-atualizador.bat.')
    root=install_root()
    return engine.validate_package(path,__version__,engine.digest(root/'requirements.txt'))


def prepare(db,path,demo=False):
    manifest=inspect_release(path)
    backup=db.backup('antes-atualizar-app')
    engine.queue_update(path,install_root(),__version__,db.path,backup,demo=demo)
    return manifest,backup


def status_text():
    root=install_root();_,pending,result=engine.paths(root)
    if pending.exists():return 'Atualização preparada. Feche e reabra o programa para concluir.'
    if result.exists():
        try:
            data=engine.load_json(result)
            if data.get('status')=='success':return 'Atualização instalada: '+str(data.get('version',''))+'.'
            return data.get('message','A versão anterior foi recuperada.')
        except (OSError,ValueError):return 'Não foi possível ler o resultado da última atualização.'
    return 'Nenhuma atualização pendente. Os dados financeiros ficam separados da instalação.'

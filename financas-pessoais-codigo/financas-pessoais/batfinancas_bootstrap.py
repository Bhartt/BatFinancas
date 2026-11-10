"""Inicialização e atualização transacional de código. Validação/cópia em biblioteca padrão; bloqueio de dados pelo Qt.

Este arquivo fica fora do pacote substituído. Nunca baixa nem executa código
no ato da validação. Pacotes devem vir da distribuição confiável do projeto.
"""
import ast
import contextlib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sqlite3
import stat
import subprocess
import sys
import time
import uuid
import zipfile

APP_ID='BatFinancas'
FORMAT=1
CACHE='.batfinancas-atualizacoes'
MAX_BYTES=128*1024*1024
MAX_FILES=3000
REQUIRED={'financas/__init__.py','financas/__main__.py','financas/db.py','financas/service.py','financas/window.py'}


def version_tuple(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d{1,4}\.\d{1,4}\.\d{1,4}',value):
        raise ValueError('Versão de atualização inválida.')
    return tuple(map(int,value.split('.')))


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def atomic_json(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.tmp')
    with temp.open('w',encoding='utf-8') as stream:
        json.dump(data,stream,ensure_ascii=False,indent=2);stream.flush();os.fsync(stream.fileno())
    os.replace(temp,path)


def load_json(path):
    if Path(path).stat().st_size>2*1024*1024:
        raise ValueError('Arquivo de controle excede o tamanho permitido.')
    return json.loads(Path(path).read_text(encoding='utf-8'))


def permitted(name):
    if not isinstance(name,str) or '\\' in name or '\x00' in name or any(char in name for char in '<>:"|?*'):
        return False
    parts=PurePosixPath(name).parts
    if not parts or name.startswith('/') or any(p in ('.','..') for p in parts) or '/'.join(parts)!=name:
        return False
    reserved={'con','prn','aux','nul'}|{f'com{i}' for i in range(1,10)}|{f'lpt{i}' for i in range(1,10)}
    if any(p.rstrip(' .')!=p or p.split('.')[0].casefold() in reserved for p in parts):
        return False
    if parts[0]!='financas' or '__pycache__' in parts:
        return False
    return (len(parts)==2 and name.endswith('.py')) or (len(parts)>2 and parts[1]=='assets' and Path(name).suffix.casefold() in {'.ttf','.otf','.txt','.png','.svg','.ico','.json'})


def validate_package(path,current_version,requirements_hash=None):
    """Confere manifesto, compatibilidade, caminhos, tamanhos, hashes e sintaxe."""
    version_tuple(current_version)
    path=Path(path)
    if not path.is_file() or path.stat().st_size>64*1024*1024:
        raise ValueError('Selecione um pacote de atualização ZIP de até 64 MB.')
    try:
        with zipfile.ZipFile(path) as z:
            infos=z.infolist()
            if len(infos)>MAX_FILES or sum(i.file_size for i in infos)>MAX_BYTES:
                raise ValueError('Pacote excede os limites de tamanho ou quantidade de arquivos.')
            seen=set();files={}
            for info in infos:
                name=info.filename
                if info.is_dir():
                    if not name.endswith('/') or not permitted(name.rstrip('/')+'/placeholder.txt'):
                        # Diretório principal também é permitido, sem extrair seus metadados.
                        if name!='financas/':raise ValueError('Pasta inválida no pacote.')
                    continue
                if name.casefold() in seen or stat.S_ISLNK(info.external_attr>>16) or info.flag_bits&1:
                    raise ValueError('Pacote tem arquivo repetido, atalho ou criptografia não suportada.')
                seen.add(name.casefold())
                if name!='batfinancas-release.json' and not permitted(name):
                    raise ValueError('O pacote contém caminhos ou tipos de arquivo não permitidos.')
                if info.file_size>16*1024*1024:
                    raise ValueError('Um arquivo do pacote excede o limite permitido.')
                files[name]=info
            if 'batfinancas-release.json' not in files or files['batfinancas-release.json'].file_size>1024*1024:
                raise ValueError('Este ZIP não é um pacote de atualização integrado da BatFinanças.')
            manifest=json.loads(z.read('batfinancas-release.json').decode('utf-8'))
            if not isinstance(manifest,dict):raise ValueError('Manifesto inválido.')
            if manifest.get('app')!=APP_ID or manifest.get('format')!=FORMAT:
                raise ValueError('Pacote pertence a outro aplicativo ou formato incompatível.')
            if version_tuple(manifest.get('version'))<=version_tuple(current_version):
                raise ValueError('Escolha uma versão mais nova do que a instalada.')
            if manifest.get('bootstrap',1)!=FORMAT:
                raise ValueError('Esta versão exige atualizar primeiro o instalador da BatFinanças.')
            if requirements_hash and manifest.get('requirements_sha256')!=requirements_hash:
                raise ValueError('Esta versão requer dependências diferentes. Use o instalador completo.')
            listed=manifest.get('files')
            if not isinstance(listed,dict) or set(files)-{'batfinancas-release.json'}!=set(listed) or not REQUIRED<=set(listed):
                raise ValueError('Manifesto incompleto ou diferente do conteúdo do pacote.')
            for name,expected in listed.items():
                if not permitted(name) or not isinstance(expected,str) or not re.fullmatch('[0-9a-f]{64}',expected):
                    raise ValueError('Manifesto contém um arquivo inválido.')
                data=z.read(name)
                if hashlib.sha256(data).hexdigest()!=expected:
                    raise ValueError('O pacote está incompleto ou corrompido. Baixe novamente.')
                if name.endswith('.py'):
                    ast.parse(data,filename=name)
            tree=ast.parse(z.read('financas/__init__.py'))
            declared=None
            for node in tree.body:
                if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='__version__' for t in node.targets):
                    declared=ast.literal_eval(node.value)
            if declared!=manifest['version']:
                raise ValueError('A versão do código difere da versão informada pelo pacote.')
            notes=manifest.get('notes','')
            if not isinstance(notes,str) or len(notes)>8000:
                raise ValueError('Notas da versão inválidas.')
            return manifest
    except (zipfile.BadZipFile,UnicodeError,json.JSONDecodeError,SyntaxError,KeyError,TypeError,RuntimeError) as exc:
        raise ValueError('Não foi possível validar o pacote de atualização.') from exc


def paths(root):
    cache=Path(root).resolve()/CACHE
    return cache,cache/'pending.json',cache/'latest-result.json'


def installed_version(root):
    tree=ast.parse((Path(root)/'financas/__init__.py').read_bytes())
    for node in tree.body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='__version__' for t in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError('Não foi possível identificar a versão instalada.')


def database_fingerprint(path):
    path=Path(path);result=hashlib.sha256()
    for suffix in ('','-wal','-journal'):
        member=Path(str(path)+suffix)
        result.update(suffix.encode('ascii'))
        result.update(digest(member).encode('ascii') if member.exists() else b'ausente')
    return result.hexdigest()


def queue_update(package,root,current_version,database,db_backup,demo=False):
    root=Path(root).resolve();cache,pending,_=paths(root)
    if not (root/'iniciar.py').is_file() or not (root/'financas').is_dir() or (root/'financas').is_symlink():
        raise ValueError('Pasta de instalação inválida para atualização integrada.')
    if pending.exists():raise ValueError('Já existe uma atualização aguardando reinicialização.')
    req=digest(root/'requirements.txt');original_hash=digest(package)
    manifest=validate_package(package,current_version,req)
    database,db_backup=Path(database).resolve(),Path(db_backup).resolve()
    if database==db_backup or not db_backup.is_file():raise ValueError('Backup preventivo não encontrado.')
    if database.is_relative_to(root/'financas') or db_backup.is_relative_to(root/'financas'):
        raise ValueError('Os dados precisam ficar fora da pasta de código financas para usar o atualizador.')
    identifier=uuid.uuid4().hex;job=cache/identifier;job.mkdir(parents=True)
    saved=job/'release.zip';shutil.copyfile(package,saved)
    if digest(saved)!=original_hash or digest(package)!=original_hash:raise ValueError('A cópia local do pacote falhou.')
    state={'app':APP_ID,'job':identifier,'phase':'queued','previous_version':current_version,
           'version':manifest['version'],'package_sha256':digest(saved),'requirements_sha256':req,
           'database':str(database),'database_backup':str(db_backup),'database_fingerprint':database_fingerprint(database),
           'arguments':['--demo'] if demo else ['--dados',str(database.parent)]}
    atomic_json(pending,state)
    return state


def read_state(root):
    cache,pending,_=paths(root);state=load_json(pending)
    if state.get('app')!=APP_ID or not re.fullmatch('[0-9a-f]{32}',state.get('job','')):
        raise ValueError('Estado da atualização inválido.')
    return state,cache/state['job']


def apply_pending(root):
    root=Path(root).resolve();cache,pending,_=paths(root);state,job=read_state(root)
    if state['phase']!='queued':raise ValueError('É necessário recuperar a atualização anterior.')
    package=job/'release.zip'
    if digest(package)!=state['package_sha256']:raise ValueError('O pacote foi alterado após a confirmação.')
    if installed_version(root)!=state['previous_version']:raise ValueError('A instalação mudou após a confirmação da atualização.')
    manifest=validate_package(package,installed_version(root),digest(root/'requirements.txt'))
    if manifest['version']!=state['version']:raise ValueError('A versão preparada foi alterada.')
    # Refaz o backup já com o app fechado: não perde alterações feitas entre
    # a preparação e uma reinicialização posterior.
    database=Path(state['database']);backup_folder=database.parent/'backups';backup_folder.mkdir(exist_ok=True)
    actual_backup=backup_folder/('antes-aplicar-atualizacao-'+state['job']+'.sqlite3')
    with sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True) as src,sqlite3.connect(actual_backup) as dst:
        if src.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('O banco não passou na validação antes de atualizar.')
        src.backup(dst)
    state['database_backup']=str(actual_backup);state['database_fingerprint']=database_fingerprint(database)
    atomic_json(pending,state)
    stage=job/'new';stage.mkdir()
    with zipfile.ZipFile(package) as z:
        for name in manifest['files']:
            target=stage.joinpath(*PurePosixPath(name).parts);target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(z.read(name))
    state['phase']='installing';atomic_json(pending,state)
    # Renomeações no mesmo volume. .venv e banco nunca fazem parte do pacote.
    os.replace(root/'financas',job/'previous')
    try:os.replace(stage/'financas',root/'financas')
    except BaseException:
        os.replace(job/'previous',root/'financas');raise
    state['phase']='trial';atomic_json(pending,state)
    return state


def commit(root):
    _,pending,result=paths(root);state,job=read_state(root)
    if state['phase']!='trial':raise ValueError('Atualização não está aguardando abertura.')
    state['phase']='committed';atomic_json(job/'result.json',state)
    atomic_json(result,{'status':'success','version':state['version'],'previous_version':state['previous_version'],
                        'backup':state['database_backup'],'message':'Atualização instalada e abertura validada.'})
    pending.unlink()


def restore_database(state):
    source=Path(state['database_backup']).resolve();target=Path(state['database']).resolve()
    if not source.is_file() or source==target or target.suffix!='.sqlite3':
        raise ValueError('Backup inválido para recuperar a atualização.')
    staged=target.with_name(target.name+'.recuperacao-atualizacao')
    try:
        with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as src:
            if src.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Backup preventivo inválido.')
            with sqlite3.connect(staged) as dst:src.backup(dst)
        # Todos os processos dessa instalação já foram encerrados neste ponto.
        for suffix in ('-wal','-shm','-journal'):Path(str(target)+suffix).unlink(missing_ok=True)
        os.replace(staged,target)
    finally:staged.unlink(missing_ok=True)


def recover(root,message='A nova versão não abriu; a versão anterior foi recuperada.'):
    root=Path(root).resolve();_,pending,result=paths(root);state,job=read_state(root)
    previous=job/'previous'
    if state['phase'] in ('trial','failed'):
        expected=state.get('failed_database_fingerprint',state.get('database_fingerprint'))
        if expected!=database_fingerprint(state['database']):
            raise ValueError('O banco mudou depois da preparação/falha. A recuperação automática foi interrompida para preservar os dados. Os backups continuam disponíveis.')
    if state['phase'] in ('trial','failed') and not previous.is_dir():
        raise ValueError('A cópia da versão anterior está ausente. Preserve os backups e use o instalador completo.')
    if previous.is_dir():
        if (root/'financas').exists():os.replace(root/'financas',job/('failed-'+uuid.uuid4().hex))
        os.replace(previous,root/'financas')
    if state['phase'] in ('trial','failed'):
        restore_database(state)
    atomic_json(result,{'status':'recovered','version':state['previous_version'],'message':message,
                        'backup':state['database_backup']})
    state['phase']='recovered';atomic_json(job/'result.json',state);pending.unlink()


@contextlib.contextmanager
def installation_lock(root):
    lock=Path(root)/'.batfinancas-instancia.lock';handle=lock.open('a+b')
    try:
        if os.fstat(handle.fileno()).st_size==0:handle.write(b'0');handle.flush()
        handle.seek(0)
        try:
            if os.name=='nt':
                import msvcrt;msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl;fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError as exc:raise ValueError('A BatFinanças já está aberta nesta instalação. Feche a outra janela.') from exc
        yield
    finally:
        handle.close()


def wait_parent(pid):
    if pid<=0:return
    if os.name=='nt':
        import ctypes
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.OpenProcess.restype=ctypes.c_void_p
        handle=kernel.OpenProcess(0x00100000,False,pid)
        if handle:
            try:
                if kernel.WaitForSingleObject(ctypes.c_void_p(handle),20000)==258:
                    raise ValueError('O programa anterior ainda está encerrando. Tente abrir novamente.')
            finally:kernel.CloseHandle(ctypes.c_void_p(handle))
    else:
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            try:os.kill(pid,0)
            except ProcessLookupError:return
            time.sleep(.1)
        raise ValueError('O programa anterior ainda está aberto.')


def notify_error(message):
    if os.environ.get('QT_QPA_PLATFORM')=='offscreen':
        print(message,file=sys.stderr);return
    try:
        import tkinter as tk
        from tkinter import messagebox
        root=tk.Tk();root.withdraw();messagebox.showerror('BatFinanças',message);root.destroy()
    except Exception:print(message,file=sys.stderr)


@contextlib.contextmanager
def database_lock(state):
    from PySide6.QtCore import QLockFile
    folder=Path(state['database']).resolve().parent
    lock=QLockFile(str(folder/'aplicacao.lock'));lock.setStaleLockTime(0)
    if not lock.tryLock(0):
        raise ValueError('Os dados estão abertos em outra janela. Feche todas as instâncias e tente novamente. A atualização continua preparada.')
    try:yield lock
    finally:lock.unlock()


def launch():
    if getattr(sys,'frozen',False):
        from financas.__main__ import main
        return main()
    root=Path(__file__).resolve().parent;arguments=sys.argv[1:];parent=0
    if '--batfinancas-wait-parent' in arguments:
        index=arguments.index('--batfinancas-wait-parent');parent=int(arguments[index+1]);del arguments[index:index+2]
    restart=False
    try:
        wait_parent(parent)
        with installation_lock(root),contextlib.ExitStack() as held:
            _,pending,result=paths(root);trial=False;held_lock=None
            if pending.exists():
                state,_=read_state(root)
                arguments=state.get('arguments') or ['--dados',str(Path(state['database']).parent)]
                held_lock=held.enter_context(database_lock(state))
                if state['phase']!='queued':
                    recover(root);held.close();held_lock=None
                    notify_error('A atualização não foi concluída. A versão anterior e os dados foram recuperados.')
                else:
                    try:apply_pending(root);trial=True
                    except Exception:
                        recover(root,'A instalação falhou; os arquivos anteriores foram preservados.')
                        held.close();held_lock=None
            os.environ['BATFINANCAS_BOOTSTRAP_ROOT']=str(root)
            sys.argv=[str(root/'iniciar.py'),*arguments]
            try:
                from financas.__main__ import main
                if trial:code=main(startup_ready=lambda:commit(root),update_trial=True,update_lock=held_lock)
                else:code=main()
            except Exception:code=1
            if trial and pending.exists():
                state,_=read_state(root)
                if state['phase']=='trial':
                    state['phase']='failed';state['failed_database_fingerprint']=database_fingerprint(state['database'])
                    atomic_json(pending,state)
                restart=True
            elif pending.exists():restart=True
            elif code:notify_error('Não foi possível iniciar a BatFinanças. Verifique a instalação e os registros locais.')
    except Exception as exc:
        notify_error(str(exc) if isinstance(exc,ValueError) else 'Não foi possível iniciar ou recuperar a atualização. Os backups foram preservados.')
        return 1
    if restart:
        flags=getattr(subprocess,'CREATE_NO_WINDOW',0) if os.name=='nt' else 0
        subprocess.Popen([sys.executable,str(root/'iniciar.py'),'--batfinancas-wait-parent',str(os.getpid()),*arguments],cwd=root,creationflags=flags,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        return 0
    return code


if __name__=='__main__':
    raise SystemExit(launch())

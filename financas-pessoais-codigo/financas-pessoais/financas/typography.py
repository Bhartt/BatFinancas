"""Nunito incorporada ao aplicativo para uso offline, nos pesos 400 e 600."""
from functools import lru_cache
from pathlib import Path

FONT_DIR=Path(__file__).resolve().parent/'assets'/'fonts'
FONT_PATH=FONT_DIR/'Nunito-Regular.ttf'
FONT_SEMIBOLD_PATH=FONT_DIR/'Nunito-SemiBold.ttf'
FONT_FAMILY='Nunito'


def register_fonts(app):
    from PySide6.QtGui import QFont,QFontDatabase
    if app.property('batFontFamily')!=FONT_FAMILY:
        identifiers=[]
        for path in (FONT_PATH,FONT_SEMIBOLD_PATH):
            identifier=QFontDatabase.addApplicationFont(str(path))
            if identifier<0 or FONT_FAMILY not in QFontDatabase.applicationFontFamilies(identifier):
                raise ValueError('Não foi possível carregar a Nunito. Copie também a pasta financas/assets da atualização.')
            identifiers.append(identifier)
        app.setProperty('batFontIds',identifiers);app.setProperty('batFontFamily',FONT_FAMILY)
    app.setFont(QFont(FONT_FAMILY,10))
    register_plot_font()


@lru_cache(maxsize=1)
def register_plot_font():
    from matplotlib import font_manager,rcParams
    for path in (FONT_PATH,FONT_SEMIBOLD_PATH):
        font_manager.fontManager.addfont(str(path))
    rcParams['font.family']=[FONT_FAMILY,'DejaVu Sans']
    return True


@lru_cache(maxsize=1)
def codepoints():
    from fontTools.ttLib import TTFont
    with TTFont(FONT_PATH) as font:
        return frozenset(font.getBestCmap())


def pdf_text(value):
    """Preserva símbolos fora da Nunito com fallback somente nesses caracteres."""
    from xml.sax.saxutils import escape
    result=[];supported=codepoints();fallback=False;run=[]
    for char in str(value):
        next_fallback=ord(char) not in supported
        if run and next_fallback!=fallback:
            text=escape(''.join(run))
            result.append('<font name="DejaVuSans">'+text+'</font>' if fallback else text)
            run=[]
        fallback=next_fallback;run.append(char)
    if run:
        text=escape(''.join(run));result.append('<font name="DejaVuSans">'+text+'</font>' if fallback else text)
    return ''.join(result)

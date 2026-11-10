"""Tradução também dos botões e diálogos internos do Qt."""
from PySide6.QtCore import QLocale, QTranslator, QLibraryInfo


def configure(app):
    QLocale.setDefault(QLocale(QLocale.Portuguese,QLocale.Brazil))
    translator=QTranslator(app)
    if not translator.load('qtbase_pt_BR',QLibraryInfo.path(QLibraryInfo.TranslationsPath)):
        raise ValueError('Não foi possível carregar a tradução brasileira do Qt. Reinstale as dependências.')
    app.installTranslator(translator)
    # O Qt não toma posse da referência Python; mantenha-a pela vida da aplicação.
    app.translator_ptbr=translator

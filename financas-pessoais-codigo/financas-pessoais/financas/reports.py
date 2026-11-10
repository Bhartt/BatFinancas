"""Exportação local de CSV, importação validada e relatórios PDF."""
import csv
import io
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from xml.sax.saxutils import escape
from .money import brl, brdate, cents, iso, advance
from .service import REALIZED

CSV_FIELDS = {'description':'Descrição','kind':'Tipo','amount':'Valor','category':'Categoria','account':'Conta',
              'target':'Conta destino','card':'Cartão','competence':'Competência','due':'Vencimento','paid':'Pagamento',
              'status':'Situação','notes':'Observações','tags':'Etiquetas','invoice':'Fatura'}


def export_csv(rows, path):
    with open(path,'w',encoding='utf-8-sig',newline='') as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(CSV_FIELDS.values())
        for row in rows:
            values = []
            for field in CSV_FIELDS:
                val = row.get(field) or ''
                if field == 'amount':
                    val = brl(row[field]).replace('R$ ','')
                elif field in ('competence','due','paid'):
                    val = brdate(val)
                # Neutraliza fórmulas em planilhas, sem alterar datas ou valores numéricos.
                elif isinstance(val,str) and val.startswith(('=','+','-','@','\t','\r')):
                    val = "'" + val
                values.append(val)
            writer.writerow(values)


def read_csv(path):
    raw = Path(path).read_bytes()
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = raw.decode('cp1252')
    try:
        dialect = csv.Sniffer().sniff(text[:8192],delimiters=';,\t')
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    headers = reader.fieldnames or []
    if not headers or len(set(headers)) != len(headers):
        raise ValueError('O CSV precisa de cabeçalhos únicos na primeira linha.')
    rows = list(reader)
    if len(rows) > 20000:
        raise ValueError('Importe no máximo 20.000 linhas por arquivo.')
    return headers, rows


def preview_import(finance, rows, mapping, default_account=None, default_category=None):
    result = []
    seen = set()
    for index, row in enumerate(rows, 2):
        item = {'line':index, 'entry':None,'error':'','duplicate':False}
        try:
            def get(field, default=''):
                return (row.get(mapping.get(field,'')) or default).strip()
            d = {'description':get('description'), 'kind':get('kind','despesa').lower(),
                 'amount':cents(get('amount')), 'competence':iso(get('competence')),
                 'due':iso(get('due',get('competence'))), 'paid':get('paid') or None,
                 'status':get('status','pendente').lower(),'notes':get('notes'),'tags':get('tags'),
                 'category_id':default_category,'account_id':default_account,
                 'target_id':None,'card_id':None, 'invoice':get('invoice') or None}
            for field, table, label in (('category','categories','categoria'),('account','accounts','conta'),
                                       ('target','accounts','conta destino'),('card','cards','cartão')):
                name = get(field)
                if name:
                    found = finance.db.one(f'SELECT id FROM {table} WHERE name=? COLLATE NOCASE',(name,))
                    if not found:
                        raise ValueError(f'{label.capitalize()} "{name}" não encontrado(a). Cadastre antes de importar.')
                    d[{'category':'category_id','account':'account_id','target':'target_id','card':'card_id'}[field]] = found['id']
            if d['card_id'] and d['kind'] in ('despesa','estorno'):
                d['account_id'] = None
            d = finance.validate_entry(d)
            key = (d['description'].casefold(),d['kind'],d['amount'],d['competence'],d['account_id'],d['card_id'])
            match = finance.db.one('''SELECT id FROM entries WHERE lower(description)=lower(?) AND kind=?
                  AND amount=? AND competence=? AND account_id IS ? AND card_id IS ?''',
                  (d['description'],d['kind'],d['amount'],d['competence'],d['account_id'],d['card_id']))
            item.update(entry=d, duplicate=bool(match) or key in seen)
            seen.add(key)
        except (ValueError,TypeError,KeyError) as exc:
            item['error'] = str(exc)
        result.append(item)
    return result


def commit_import(finance, preview, include_duplicates=False):
    selected = [p for p in preview if not p['error'] and (include_duplicates or not p['duplicate'])]
    if not selected:
        raise ValueError('Nenhuma linha válida selecionada para importar.')
    with finance.db.transaction() as c:
        for p in selected:
            finance.save_entry(p['entry'])
        c.execute('INSERT INTO import_batches(created,rows) VALUES(datetime(\'now\'),?)',(len(selected),))
    return len(selected)


def report_tables(finance, start, end, basis='competência'):
    summary = finance.summary(start,end,basis)
    tables = []
    tables.append(('Receitas e despesas — '+basis, ['Indicador','Valor'], [
        ['Receitas realizadas',brl(summary['income'])],['Despesas realizadas / saídas',brl(summary['expense'])],
        ['Resultado realizado',brl(summary['result'])],['Receitas previstas e pendentes',brl(summary['planned_income'])],
        ['Despesas previstas e pendentes',brl(summary['planned_expense'])]]))
    tables.append(('Gastos realizados por categoria', ['Categoria','Valor'],
                   [[k,brl(v)] for k,v in sorted(summary['categories'].items())]))
    # Fluxo por mês, com base em pagamento ou vencimento. Compras de cartão não saem da conta.
    months = []
    cursor = start[:7]+'-01'
    while cursor <= end:
        a = max(start,cursor)
        b = min(end,(date.fromisoformat(advance(cursor,1))-timedelta(days=1)).isoformat())
        s = finance.summary(a,b,'caixa')
        months.append([brdate(cursor)[3:],brl(s['income']),brl(s['expense']),brl(s['planned_income']),brl(s['planned_expense'])])
        cursor = advance(cursor,1)
    tables.append(('Fluxo de caixa — pagamentos e recebimentos', ['Mês','Entradas','Saídas','A receber','A pagar'],months))
    balances = []
    accounts = finance.db.rows('SELECT * FROM accounts ORDER BY name')
    cursor = start[:7]+'-01'
    while cursor <= end:
        day = min(end,(date.fromisoformat(advance(cursor,1))-timedelta(days=1)).isoformat())
        total = 0
        for a in accounts:
            value = finance.balance(a['id'],day)
            balances.append([brdate(day),a['name'],brl(value)])
            total += value
        balances.append([brdate(day),'Consolidado',brl(total)])
        cursor = advance(cursor,1)
    tables.append(('Evolução dos saldos realizados — todas as contas', ['Data','Conta','Saldo'], balances))
    budgets = []
    cursor = start[:7]+'-01'
    while cursor <= end:
        for b in finance.budget_progress(cursor[:7]):
            budgets.append([brdate(cursor)[3:],b['name'],brl(b['amount']),brl(b['spent']),brl(b['available']),str(b['percent'])+'%'])
        cursor = advance(cursor,1)
    tables.append(('Cumprimento dos orçamentos — meses completos', ['Mês','Categoria','Limite','Gasto','Disponível','Uso'], budgets))
    return tables


def export_pdf(finance, start, end, basis, path):
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from matplotlib import get_data_path
    from .typography import FONT_PATH,FONT_SEMIBOLD_PATH,pdf_text
    fonts = Path(get_data_path()) / 'fonts' / 'ttf'
    if 'DejaVuSans' not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont('DejaVuSans',str(fonts/'DejaVuSans.ttf')))
        pdfmetrics.registerFont(TTFont('DejaVuSans-Bold',str(fonts/'DejaVuSans-Bold.ttf')))
    if 'Nunito' not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont('Nunito',str(FONT_PATH)))
        pdfmetrics.registerFont(TTFont('Nunito-SemiBold',str(FONT_SEMIBOLD_PATH)))
    styles = getSampleStyleSheet()
    for name in ('Normal','BodyText'):
        styles[name].fontName = 'Nunito'
    for name in ('Title','Heading1','Heading2'):
        styles[name].fontName = 'Nunito-SemiBold'
    story = [Paragraph('BatFinanças',styles['Title']),
             Paragraph(pdf_text(f'Relatório de {brdate(start)} a {brdate(end)} · Base: {basis}'),styles['Normal']),Spacer(1,16),
             Paragraph('Competência: compras de cartão são despesas; pagamento de fatura não repete a despesa. '
                       'Caixa: mostra entradas e saídas das contas, incluindo pagamentos de fatura. '
                       'Transferências e saldos iniciais não são receitas ou despesas. Valores previstos não alteram saldos realizados.',styles['Normal']),Spacer(1,16)]
    for title, headers, rows in report_tables(finance,start,end,basis):
        story.append(Paragraph(pdf_text(title),styles['Heading2']))
        data = [[Paragraph(pdf_text(x),styles['Normal']) for x in headers]]
        for row in rows or [['Sem dados no período']+['']*(len(headers)-1)]:
            data.append([Paragraph(pdf_text(x),styles['Normal']) for x in row])
        table = Table(data,repeatRows=1,colWidths=[750/len(headers)]*len(headers),hAlign='LEFT')
        table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#dedede')),
                                   ('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),.7,colors.gray),
                                   ('BOTTOMPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),7)]))
        story.extend([table,Spacer(1,20)])
    def footer(canvas, doc):
        canvas.setFont('Nunito',8)
        canvas.drawString(36,18,'Gerado localmente - Valores em reais (R$) - Página '+str(doc.page))
    SimpleDocTemplate(str(path),pagesize=landscape(A4),leftMargin=36,rightMargin=36,topMargin=32,bottomMargin=36).build(story,onFirstPage=footer,onLaterPages=footer)

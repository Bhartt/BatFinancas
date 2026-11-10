"""Conversões sem ponto flutuante e calendário ancorado no dia original."""
import calendar
import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation


def cents(value):
    if isinstance(value, int):
        return value
    text = str(value).strip().replace('R$', '').replace(' ', '').replace('\xa0', '')
    if ',' in text:
        text = text.replace('.', '').replace(',', '.')
    if not re.fullmatch(r'[+-]?\d+(\.\d{1,2})?', text):
        raise ValueError('Informe um valor válido com até duas casas decimais, como 1.234,56.')
    try:
        return int(Decimal(text) * 100)
    except InvalidOperation as exc:
        raise ValueError('Valor monetário inválido.') from exc


def brl(value):
    sign = '-' if value < 0 else ''
    n = abs(int(value))
    return f"{sign}R$ {n // 100:,}".replace(',', '.') + f',{n % 100:02d}'


def iso(value):
    if isinstance(value, date):
        return value.isoformat()
    text = str(value).strip()
    if '/' in text:
        d, m, y = text.split('/')
        return date(int(y), int(m), int(d)).isoformat()
    return date.fromisoformat(text).isoformat()


def brdate(value):
    return date.fromisoformat(value).strftime('%d/%m/%Y') if value else ''


def advance(anchor, index, period='mensal', step=1):
    anchor = date.fromisoformat(iso(anchor))
    if period in ('diária', 'semanal'):
        return (anchor + timedelta(days=index * step * (7 if period == 'semanal' else 1))).isoformat()
    months = index * step * (12 if period == 'anual' else 1)
    n = anchor.year * 12 + anchor.month - 1 + months
    y, m = n // 12, n % 12 + 1
    return date(y, m, min(anchor.day, calendar.monthrange(y, m)[1])).isoformat()


def split_cents(total, count):
    if count < 1 or total < count:
        raise ValueError('A quantidade deve ser positiva e cada parcela deve ter ao menos R$ 0,01.')
    q, r = divmod(total, count)
    return [q + (i < r) for i in range(count)]

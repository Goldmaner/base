"""
Módulo de leitura de emails e calendário via Outlook COM Automation (win32com).

Conecta ao Outlook instalado localmente — sem senha, sem IMAP, sem OAuth.
O MFA já foi resolvido quando o usuário abriu o Outlook.
Funciona apenas em Windows com Outlook instalado e aberto.
"""

import pythoncom
import win32com.client
from datetime import datetime, timedelta, date

# Constantes Outlook
_INBOX_FOLDER    = 6    # olFolderInbox
_CALENDAR_FOLDER = 9    # olFolderCalendar
_ITEM_TYPE_MAIL  = 43   # olMailItem
_ITEM_TYPE_APPT  = 26   # olAppointmentItem


# ─── Helpers internos ────────────────────────────────────────────────────────

def _get_namespace():
    pythoncom.CoInitialize()
    outlook = win32com.client.Dispatch('Outlook.Application')
    return outlook.GetNamespace('MAPI')


def _dt_naive(dt) -> datetime:
    """Converte pywintypes.datetime para datetime naive."""
    return datetime(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)


def _coletar_emails_pasta(pasta, desde: datetime, limite_restante: int) -> list[dict]:
    """Coleta emails de uma pasta e suas subpastas recursivamente."""
    emails = []
    if limite_restante <= 0:
        return emails

    try:
        items = pasta.Items
        items.Sort('[ReceivedTime]', True)
    except Exception:
        return emails

    for item in items:
        if len(emails) >= limite_restante:
            break
        try:
            if item.Class != _ITEM_TYPE_MAIL:
                continue
            recebido_naive = _dt_naive(item.ReceivedTime)
            if recebido_naive < desde:
                break   # ordenado desc, pode parar
            corpo = ''
            try:
                corpo = (item.Body or '')[:4000].strip()
            except Exception:
                pass
            anexos = []
            try:
                for i in range(1, item.Attachments.Count + 1):
                    nome = item.Attachments.Item(i).FileName
                    if nome:
                        anexos.append(nome)
            except Exception:
                pass
            emails.append({
                'uid':       str(item.EntryID),
                'assunto':   item.Subject or '(Sem assunto)',
                'remetente': item.SenderName or item.SenderEmailAddress or '',
                'data':      recebido_naive.strftime('%a, %d %b %Y %H:%M'),
                'pasta':     pasta.Name,
                'corpo':     corpo,
                'anexos':    anexos,
            })
        except Exception as e:
            print(f'[email_reader] item ignorado em {pasta.Name}: {e}')
            continue

    # Subpastas recursivamente
    try:
        for sub in pasta.Folders:
            if len(emails) >= limite_restante:
                break
            emails += _coletar_emails_pasta(sub, desde, limite_restante - len(emails))
    except Exception:
        pass

    return emails


# ─── API pública — Emails ─────────────────────────────────────────────────────

def testar_conexao_imap(*args, **kwargs) -> bool:
    """Testa se o Outlook está acessível via COM."""
    ns = _get_namespace()
    _ = ns.GetDefaultFolder(_INBOX_FOLDER).Items.Count
    return True


def listar_pastas(*args, **kwargs) -> list[str]:
    """Retorna lista de pastas de email (Inbox + subpastas)."""
    ns = _get_namespace()
    inbox = ns.GetDefaultFolder(_INBOX_FOLDER)
    nomes = [inbox.Name]
    for f in inbox.Folders:
        nomes.append(f'  └ {f.Name}')
    return nomes


def listar_emails(
    _connection=None,
    pasta: str = 'INBOX',
    dias: int = 0,
    limite: int = 50,
    todas_pastas: bool = True,
) -> list[dict]:
    """
    Lista emails desde 'dias' atrás (0 = hoje).
    Se todas_pastas=True, varre Inbox e todas as subpastas.
    Retorna lista de dicts: uid, assunto, remetente, data, pasta, corpo, anexos.
    """
    ns = _get_namespace()
    inbox = ns.GetDefaultFolder(_INBOX_FOLDER)
    desde = datetime.combine(date.today() - timedelta(days=dias), datetime.min.time())
    return _coletar_emails_pasta(inbox, desde, limite)


# ─── API pública — Calendário ────────────────────────────────────────────────

def listar_compromissos(dias: int = 7) -> list[dict]:
    """
    Retorna compromissos/reuniões do calendário nos próximos 'dias' dias.
    Inclui compromissos de hoje em diante.
    """
    ns = _get_namespace()
    calendario = ns.GetDefaultFolder(_CALENDAR_FOLDER)
    items = calendario.Items
    items.IncludeRecurrences = True
    items.Sort('[Start]')

    agora = datetime.now()
    ate = agora + timedelta(days=dias)

    compromissos = []
    for item in items:
        try:
            if item.Class != _ITEM_TYPE_APPT:
                continue
            inicio = _dt_naive(item.Start)
            fim    = _dt_naive(item.End)
            if inicio < agora or inicio > ate:
                continue

            # Participantes
            participantes = []
            try:
                for i in range(1, item.Recipients.Count + 1):
                    participantes.append(item.Recipients.Item(i).Name)
            except Exception:
                pass

            compromissos.append({
                'assunto':       item.Subject or '(Sem título)',
                'inicio':        inicio.strftime('%d/%m/%Y %H:%M'),
                'fim':           fim.strftime('%d/%m/%Y %H:%M'),
                'local':         item.Location or '',
                'corpo':         (item.Body or '')[:1000].strip(),
                'organizador':   item.Organizer or '',
                'participantes': participantes,
                'online':        bool(getattr(item, 'OnlineMeetingURL', '')),
                'url_online':    getattr(item, 'OnlineMeetingURL', '') or '',
            })
        except Exception as e:
            print(f'[email_reader] compromisso ignorado: {e}')
            continue

    return compromissos


# ─── Compat. stubs ────────────────────────────────────────────────────────────

def criptografar_senha(senha_plain: str) -> str:
    return ''

def descriptografar_senha(senha_enc: str) -> str:
    return ''

def conectar_imap(*args, **kwargs):
    return None

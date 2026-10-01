"""Italian-language HTML report builder.

Four sections only: header, device, apps by dangerous permissions,
tracker results, footer. The report is returned as a string — this
module never writes to disk.
"""

import html
from datetime import datetime

from .labels import display_name, display_key
from .app_scan import DANGEROUS_PERMISSIONS

_CSS = """
:root {
    --primary-blue: #6d9fff;
    --accent-blue: #4a8bf5;
    --accent-purple: #9575cd;
    --text-dark: #2d3436;
    --text-medium: #4a5568;
    --text-light: #718096;
    --bg-light: #f8f9ff;
    --bg-white: #ffffff;
    --border-color: rgba(109, 159, 255, 0.2);
    --gradient: linear-gradient(135deg, #4a8bf5, #9575cd);
    --warning: #f39c12;
}
body { font-family: 'Inter', system-ui, -apple-system, 'Segoe UI',
       Roboto, sans-serif; margin: 0 auto; max-width: 960px;
       padding: 0 20px 2rem; color: var(--text-medium);
       background: var(--bg-light); line-height: 1.6; }
.report-header { margin-top: 2rem; background: var(--bg-white);
       border: 1px solid var(--border-color); border-radius: 10px;
       padding: 2rem; position: relative; overflow: hidden;
       box-shadow: 0 4px 12px rgba(109, 159, 255, 0.15); }
.report-header::before { content: ''; position: absolute;
       top: 0; left: 0; width: 100%; height: 6px;
       background: var(--gradient); }
.brand { font-size: 1.6rem; font-weight: 700;
       color: var(--text-dark); letter-spacing: -0.5px;
       margin: 0; }
.brand span { color: var(--accent-blue); }
.report-subtitle { color: var(--text-light); font-size: 1rem;
       margin: .25rem 0 1rem; }
.report-meta { font-size: .9rem; color: var(--text-medium); }
h2 { color: var(--text-dark); margin-top: 2.5rem; }
table { border-collapse: collapse; width: 100%; margin: 1rem 0;
        background: var(--bg-white); border-radius: 10px;
        overflow: hidden; }
th, td { border-bottom: 1px solid var(--border-color);
         padding: 8px 12px; text-align: left; font-size: .9rem; }
tr:last-child td { border-bottom: none; }
th { background: var(--bg-light); color: var(--text-dark); }
.pkg { color: var(--text-light); font-size: .82rem;
       word-break: break-all; }
.muted { color: var(--text-light); font-size: .9rem; }
.unscanned-box { background: rgba(243, 156, 18, 0.1);
       border-left: 4px solid var(--warning);
       border-radius: 6px; padding: 1rem 1.25rem; margin: 1rem 0; }
.unscanned-box ul { margin: .5rem 0 0 1.2rem; }
footer { margin-top: 3rem; color: var(--text-light);
       font-size: .8rem; border-top: 1px solid var(--border-color);
       padding-top: 1.5rem; }
footer strong { color: var(--text-medium); }
"""

def _esc(text) -> str:
    return html.escape(str(text if text is not None else '?'))

def _section_header(device):
    now = datetime.now().strftime('%d/%m/%y %H:%M')
    meta = f'Generato {now}'
    if device:
        bits = [b for b in (device.get('model'),
                            device.get('serial')) if b]
        if bits:
            meta += ' · ' + _esc(' — '.join(bits))
    return (
        '<div class="report-header">'
        '<h1 class="brand">Privacy<span>Architect</span></h1>'
        '<p class="report-subtitle">'
        'Rapporto di audit privacy del dispositivo</p>'
        f'<p class="report-meta">{meta}</p>'
        '</div>'
    )

def _section_device(device):
    if not device:
        return ('<h2>Dispositivo</h2>'
                '<p class="muted">Nessun dispositivo connesso.</p>')
    rows = ''.join(
        f'<tr><th>{_esc(k)}</th><td>{_esc(v)}</td></tr>'
        for k, v in (
            ('Modello', device.get('model')),
            ('Marca', device.get('brand')),
            ('Prodotto', device.get('product')),
            ('Seriale', device.get('serial')),
            ('Android', device.get('android_version')),
            ('Livello SDK', device.get('sdk_level')),
        ))
    return f'<h2>Dispositivo</h2><table>{rows}</table>'

def _section_top_apps(apps):
    """Top 10 apps by number of dangerous permissions held."""
    dangerous = set(DANGEROUS_PERMISSIONS)
    counts = []
    for app in apps:
        if not app.is_active:
            continue
        held = app.permissions_granted & dangerous
        if held:
            counts.append((app.package_name, len(held)))
    if not counts:
        return ('<h2>App con più permessi pericolosi</h2>'
                '<p class="muted">Nessun permesso pericoloso '
                'rilevato.</p>')
    top = sorted(counts, key=lambda kv: (-kv[1], kv[0]))[:10]
    rows = ''.join(
        f'<tr><td data-pkg="{_esc(pkg)}">'
        f'{_esc(display_name(pkg))}</td>'
        f'<td>{n}</td></tr>' for pkg, n in top)
    return ('<h2>App con più permessi pericolosi</h2>'
            '<table><tr><th>App</th><th>Perm. detenuti</th></tr>'
            f'{rows}</table>')

def _section_trackers(results, unscanned):
    parts = ['<h2>Risultati scansione tracker</h2>']
    entries = []
    for key in sorted(results):
        entry = results[key]
        trackers = entry.get('trackers', {})
        if isinstance(trackers, dict):
            trackers = sorted(trackers)
        if not trackers:
            continue
        scanned = _esc(entry.get('scanned_at', '?'))
        entries.append(
            f'<tr><td>{_esc(display_key(key))}</td>'
            f'<td>{scanned}</td>'
            f'<td>{", ".join(_esc(t) for t in trackers)}'
            '</td></tr>')
    if entries:
        parts.append('<table><tr><th>App</th>'
                     '<th>Scansionata</th>'
                     '<th>Tracker trovati</th></tr>'
                     + ''.join(entries) + '</table>')
    else:
        parts.append('<p class="muted">Nessun tracker noto '
                     'rilevato nelle app scansionate.</p>')
    if unscanned:
        items = ''.join(
            f'<li>{_esc(display_name(p))} '
            f'<span class="pkg">{_esc(p)}</span></li>'
            for p in sorted(set(unscanned)))
        parts.append(
            '<div class="unscanned-box">'
            '<p style="margin:0;">Queste app non hanno potuto '
            'essere analizzate, quindi il loro contenuto in '
            'tracker è sconosciuto.</p>'
            f'<ul>{items}</ul></div>')
    return ''.join(parts)

def build_report_html(device, apps, tracker_results=None,
                      unscanned=None, tracker_count=0):
    """Assemble the report. Returns HTML string, never writes."""
    return (
        '<!doctype html><html lang="it">'
        '<head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, '
        'initial-scale=1.0">'
        '<title>Privacy Architect — Rapporto di audit privacy'
        '</title>'
        f'<style>{_CSS}</style></head><body>'
        + _section_header(device)
        + _section_device(device)
        + _section_top_apps(apps)
        + _section_trackers(tracker_results or {}, unscanned)
        + '<footer>'
        '<p><strong>Privacy Architect</strong> — tutti i dati '
        'provengono esclusivamente da questo computer; nulla '
        'viene caricato online e nessun dato viene salvato.</p>'
        '<p><strong>Metodologia:</strong> il rilevamento dei '
        'tracker è basato su firme ({n_firme} nel database '
        'locale) e confronta i nomi di classi note di tracker '
        'con il codice compilato dentro ogni pacchetto '
        '(metodologia Exodus Privacy). L\'assenza di '
        'corrispondenze non garantisce che un app sia priva di '
        'tracker, e tracker sconosciuti non verranno rilevati. I '
        'dati sui permessi riflettono lo stato del dispositivo '
        'al momento della generazione.</p>'
        '</footer></body></html>'
    ).replace('{n_firme}', str(tracker_count or 0))

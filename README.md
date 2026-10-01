# Privacy Architect — Scanner

**🇮🇹 Italiano** | [🇬🇧 English](#english)

---

## Cos'è

Uno strumento autonomo per la scansione della privacy di dispositivi
Android, che gira interamente sul tuo computer. Analizza le app
installate e i tracker al loro interno, genera un report HTML, e non
lascia alcuna traccia.

## Promesse fondamentali

Lo scanner si impegna sui seguenti punti, verificabili nel codice:

- **Zero chiamate di rete**: le firme dei tracker sono incluse nella
  cartella `tracker_data/`. Nessun dato viene inviato o ricevuto
  online. Lo strumento non apre alcuna connessione di rete, nemmeno
  in locale.
- **Zero persistenza**: nessun log, nessuna cache, nessun file
  scritto sul disco. L'unico file creato è il report, solo quando
  sei tu a cliccare "Salva report" scegliendo dove. Chiudendo la
  finestra, tutto ciò che lo strumento sa del tuo dispositivo muore
  con essa.
- **Sola lettura per costruzione**: nessuna installazione,
  disinstallazione, modifica di app o permessi. Mai.
- **Codice trasparente**:  solo stdlib Python, un file per
  responsabilità, nessun offuscamento. Ciò che leggi è ciò che
  esegui.

## Prerequisiti

- Python 3.8 o superiore
- ADB (parte dei `platform-tools` di Android) installato e
  raggiungibile — lo strumento cerca in `PATH` e nei percorsi SDK
  standard su Linux, macOS e Windows
- Debug USB abilitato sul telefono + autorizzazione concessa al
  computer
- Android 8+ raccomandato (testato su Android 14 / SDK 34; versioni
  precedenti dovrebbero funzionare con compatibilità ridotta)

## Come si usa

1. Scarica e decomprimi la cartella dello strumento
2. Avvia `scanner.py` (`python3 scanner.py`) — si apre la finestra
   dello scanner
3. Collega il telefono via USB e autorizza il computer se il
   telefono lo chiede
4. Clicca **"Avvia scansione"** e attendi (la fase tracker richiede
   qualche minuto, a seconda del numero di app); il log mostra
   l'avanzamento in tempo reale
5. A scansione completata, la finestra mostra un riepilogo con i
   numeri chiave (app totali, app utente, app con tracker noti,
   non scansionabili)
6. Se vuoi conservarlo, clicca **"Salva report"** e scegli dove
   salvare il file HTML; il report si legge aprendo quel file nel
   browser. Se non clicchi, non resta nulla sul disco
7. Chiudi la finestra quando hai finito — tutto sparisce

Nota: il report non viene mostrato dentro la finestra dello
scanner. La finestra mostra solo il riepilogo; il report completo è
il file HTML che salvi e apri nel browser.

## Non fidarti: verifica

Questo è uno strumento pensato per persone che diffidano degli
strumenti. Bene — verificalo:

- **Controlla che non ci siano chiamate di rete.** Apri
  `core/tracker_scan.py`: `load_tracker_database()` legge un file
  locale (`tracker_data/trackers.json`). Cerca `urllib`, `requests`,
  `socket` nell'intero progetto — non troverai nulla. Lo strumento
  non apre socket, non avvia server, non contatta nulla.
- **Controlla che sia di sola lettura.** Tutti i comandi verso il
  dispositivo sono in `core/app_scan.py` e `core/tracker_scan.py`:
  `getprop`, `dumpsys package`, `pm path`, `pull`. Nessun
  `install`, `uninstall`, `grant`, `revoke`, `rm`, `shell pm`.
- **Controlla le scritture su disco.** L'unico punto in cui il
  programma scrive un file è la funzione `_save_report` in
  `scanner.py` — raggiungibile solo dal pulsante "Salva report", con
  una destinazione scelta da te.
- **Verifica con un firewall o offline.** Stacca la rete (o chiudi
  il Wi-Fi) e avvia una scansione: funziona regolarmente. La
  connessione ADB via USB è l'unica comunicazione del computer con
  l'esterno.

## Limitazioni note

- Alcune app potrebbero non essere scaricabili per l'analisi
  (APK divisi, protezioni particolari): vengono mostrate nella
  sezione "non scansionabili" del report — mai come pulite.
- I permessi bloccati dalla ROM (system-fixed / role-granted) non
  sono modificabili da ADB su quella ROM: il report li segnala
  onestamente.
- Le firme dei tracker provengono dal progetto Exodus Privacy e sono
  congelate nella versione pubblicata con lo strumento: tracker
  sconosciuti o più recenti non verranno rilevati.
- Rilevamento basato su firme: l'assenza di corrispondenze non
  garantisce l'assenza di tracker.

## Licenza

MIT — vedi `LICENSE`. Sei libero di usare, studiare, modificare e
ridistribuire questo codice, purché il copyright rimanga attribuito.

## Segnalazioni

Apri una issue nel repository per bug o proposte di miglioramento.

---

<a name="english"></a>
# English

**🇬🇧 English** | [🇮🇹 Italiano](#italiano)

## What this is

A standalone privacy scanner for Android devices that runs entirely on
your computer. It analyzes installed apps and the trackers inside them,
generates an HTML report, and leaves no trace.

## Core promises

The scanner commits to the following, all verifiable in code:

- **Zero network calls**: tracker signatures are bundled in
  `tracker_data/`. Nothing is uploaded or fetched online. The tool
  opens no network connections, not even local ones.
- **Zero persistence**: no logs, no caches, no files written to
  disk. The only file ever created is the report, only when you
  click "Salva report" and choose where. Close the window and
  everything the tool knows about your device dies with it.
- **Read-only by construction**: no installing, uninstalling, or
  modifying apps or permissions. Ever.
- **Transparent code**: stdlib-only Python, one file per
  responsibility, zero obfuscation. What you read is what you run.

## Prerequisites

- Python 3.8+
- ADB (from Android `platform-tools`) on PATH or in standard SDK
  locations
- USB debugging enabled on the phone + computer authorized
- Android 8+ recommended (tested on Android 14 / SDK 34)

## How to use

1. Download and unzip the tool folder
2. Run `scanner.py` (`python3 scanner.py`) — the scanner window
   opens
3. Connect the phone via USB and authorize the computer if the
   phone asks
4. Click **"Avvia scansione"** and wait (the tracker phase takes a
   few minutes depending on app count); the log shows live progress
5. When the scan completes, the window shows a summary with the
   key numbers (total apps, user apps, apps with known trackers,
   unscannable)
6. If you want to keep it, click **"Salva report"** and choose
   where to save the HTML file; read the report by opening that
   file in your browser. If you don't click, nothing remains on
   disk
7. Close the window when done — everything disappears

Note: the report is not shown inside the scanner window. The
window displays only the summary; the full report is the HTML
file you save and open in your browser.

## Don't trust: verify

This is a tool for people who distrust tools. Good — verify it:

- **Check for network calls.** Open `core/tracker_scan.py`:
  `load_tracker_database()` reads a local file. Search the project
  for `urllib`, `requests`, `socket` — you'll find nothing. The tool
  opens no sockets, runs no servers, contacts nothing.
- **Check it's read-only.** All device commands live in
  `core/app_scan.py` and `core/tracker_scan.py`: `getprop`,
  `dumpsys package`, `pm path`, `pull`. No `install`, `uninstall`,
  `grant`, `revoke`, `rm`.
- **Check disk writes.** The only place the program writes a file
  is `_save_report` in `scanner.py` — reachable only through the
  "Salva report" button, to a destination you choose.
- **Verify with a firewall or offline.** Disconnect the network and
  run a scan: it works normally. The USB ADB connection to the phone
  is the computer's only communication with the outside world.

## Known limitations

- Some apps may fail to be pulled for analysis (split APKs,
  protections): they're shown in the report's "unscannable" section —
  never as clean.
- ROM-locked permissions (system-fixed / role-granted) can't be
  changed via ADB on that ROM: the report flags them honestly.
- Tracker signatures come from the Exodus Privacy project, frozen in
  the version published with the tool: unknown or newer trackers won't
  be detected.
- Signature-based detection: absence of matches doesn't guarantee
  absence of trackers.

## License

MIT — see `LICENSE`. You're free to use, study, modify, and
redistribute this code, as long as the copyright notice is retained.

## Reporting issues

Open an issue in the repository for bugs or improvement suggestions.

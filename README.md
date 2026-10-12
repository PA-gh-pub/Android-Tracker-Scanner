# Privacy Architect — Scanner

**🇮🇹 Italiano** | [🇬🇧 English](#english)

## Cos'è

Uno strumento autonomo per la scansione della privacy di dispositivi Android, che gira interamente sul tuo computer. Analizza le app installate, individua i tracker noti al loro interno, genera un report HTML, e ripulisce da solo ogni file temporaneo.


## Promesse fondamentali

Lo scanner si impegna sui seguenti punti, verificabili nel codice:

- **Zero chiamate di rete.** Le firme dei tracker sono incluse nella cartella `tracker_data/` (snapshot del progetto [Exodus Privacy](https://exodus-privacy.eu.org): **428 tracker**). Nessun dato viene inviato o ricevuto online. Il codice non importa `socket`, `urllib`, `requests` né alcuna libreria di rete.
- **Nessuna persistenza dei tuoi dati.** Durante l'analisi gli APK vengono copiati in una cartella temporanea, eliminata **su ogni percorso di uscita** - successo, errore, timeout o eccezione (`try/finally` con `shutil.rmtree`). I risultati vivono in memoria: chiudendo la finestra, tutto ciò che lo strumento sa del tuo dispositivo muore con essa. L'unico file che il tool scrive su disco è il report, solo quando sei tu a cliccare **"Salva report"** scegliendo dove.
- **Sola lettura per costruzione.** Nessuna installazione, disinstallazione, modifica di app o permessi. Mai. I comandi verso il dispositivo sono solo di lettura: `getprop`, `dumpsys package`, `pm path`, `pull`.
- **Codice trasparente.** Solo libreria standard Python (GUI inclusa: Tkinter), un file per responsabilità, nessun offuscamento. Ciò che leggi è ciò che esegui.


## Prerequisiti

- Python 3.8+
- ADB (parte dei platform-tools di Android), raggiungibile da `PATH` o nelle posizioni SDK standard su Linux, macOS e Windows (lo strumento li cerca da solo)
- Debug USB abilitato sul telefono + autorizzazione concessa al computer
- Android 8+ raccomandato (testato su Android 14 / SDK 34)


## Come si usa

1. Scarica o clona il repository ed entra nella cartella `scanner/`
2. Avvia lo strumento:
   ```bash
   python3 scanner.py
   ```
3. Collega il telefono via USB e autorizza il computer se il telefono lo chiede
4. Clicca **"Avvia scansione"** e attendi (la fase tracker richiede qualche minuto, a seconda del numero di app); il log mostra l'avanzamento in tempo reale
5. A scansione completata, la finestra mostra un riepilogo con i numeri chiave (app totali, app utente, app con tracker noti, non scansionabili)
6. Se vuoi conservarlo, clicca **"Salva report"** e scegli dove salvare il file HTML; il report si legge aprendo quel file nel browser
7. Chiudi la finestra quando hai finito - la cartella temporanea degli APK viene rimossa automaticamente

> Nota: il report completo non viene mostrato dentro la finestra dello scanner. La finestra mostra solo il riepilogo; il report dettagliato è il file HTML che salvi e apri nel browser.


## Non fidarti: verifica

Questo è uno strumento pensato per persone che diffidano degli strumenti. Bene - verificalo:

- **Nessuna chiamata di rete.** Cerca `socket`, `urllib`, `requests` in tutto il progetto: non troverai nulla (i pochi match su `in_requests` in `core/app_scan.py` sono banali variabili booleane per il parsing del manifest). Lo strumento non apre socket, non avvia server, non contatta nulla.
- **Sola lettura.** Tutti i comandi verso il dispositivo sono in `core/app_scan.py` e `core/tracker_scan.py`: `getprop`, `dumpsys package`, `pm path`, `pull`. Nessun `install`, `uninstall`, `grant`, `revoke`, `rm`.
- **Pulizia garantita.** L'unica `open(..., 'w')` del progetto è in `_save_report` in `scanner.py` - raggiungibile solo dal pulsante **"Salva report"**, con destinazione scelta da te. La cartella temporanea degli APK è creata con `tempfile.mkdtemp` (`core/tracker_scan.py`, riga 114) e rimossa in un blocco `finally` (righe 144-156): nessun percorso di uscita la lascia indietro.
- **Verifica offline.** Stacca la rete (o chiudi il Wi-Fi) e avvia una scansione: funziona regolare. La connessione ADB via USB è l'unica comunicazione del computer con l'esterno.


## Limitazioni note

- Alcune app potrebbero non risultare scansionabili per l'analisi (APK divisi, protezioni particolari): vengono mostrate nella sezione "non scansionabili" del report - mai come pulite.
- I permessi bloccati dalla ROM (system-fixed / role-granted) non sono modificabili da ADB su quella ROM: il report li segnala onestamente.
- Le firme provengono dal progetto Exodus Privacy e sono congelate nella versione pubblicata con lo strumento: **428 tracker noti** - tracker sconosciuti o più recenti non verranno rilevati.
- Il rilevamento è basato su firme: l'assenza di corrispondenze non garantisce l'assenza di tracker.
- Sviluppato e testato su Fedora Linux 44 (Python 3.14.8) con Android 14: la compatibilità Windows/macOS è prevista dal codice ma non verificata empiricamente.

## Licenza

MIT - vedi `LICENSE`. Sei libero di usare, studiare, modificare e ridistribuire questo codice, purché il copyright rimanga attribuito.

## Segnalazioni

Apri una segnalazione nella repository per bug o proposte di miglioramento.





---




# English

**🇬🇧 English** | [🇮🇹 Italiano](#italiano)

## What this is

A standalone privacy scanner for Android devices that runs entirely on your computer. It analyzes installed apps, identifies known trackers inside them, generates an HTML report, and cleans up every temporary file on its own.

## Core promises

The scanner commits to the following, all verifiable in code:

- **Zero network calls.** Tracker signatures are bundled in `tracker_data/` (an [Exodus Privacy](https://exodus-privacy.eu.org) snapshot: **428 trackers**). Nothing is sent or received online. The code imports no `socket`, `urllib`, `requests`, or any networking library.
- **No persistence of your data.** During analysis, APKs are copied to a temporary directory, removed **on every exit path** - success, error, timeout, or exception (`try/finally` with `shutil.rmtree`). Results live in memory: close the window and everything the tool knows about your device dies with it. The only file the tool ever writes is the report, only when you click **"Salva report"** and choose where.
- **Read-only by construction.** No installing, uninstalling, or modifying apps or permissions. Ever. Device commands are read-only: `getprop`, `dumpsys package`, `pm path`, `pull`.
- **Transparent code.** Stdlib-only Python (GUI included: Tkinter), one file per responsibility, zero obfuscation. What you read is what you run.


## Prerequisites

- Python 3.8+ 
- ADB (from Android platform-tools), on `PATH` or in standard SDK locations on Linux, macOS and Windows (the tool finds it for you)
- USB debugging enabled on the phone + computer authorized
- Android 8+ recommended (tested on Android 14 / SDK 34)


## How to use

1. Download or clone the repository and enter the `scanner/` folder
2. Launch the tool:
   ```bash
   python3 scanner.py
   ```
3. Connect the phone via USB and authorize the computer if the phone asks
4. Click **"Avvia scansione"** and wait (the tracker phase takes a few minutes depending on app count); the log shows live progress
5. When the scan completes, the window shows a summary with the key numbers (total apps, user apps, apps with known trackers, unscannable)
6. If you want to keep it, click **"Salva report"** and choose where to save the HTML file; read the report by opening it in your browser
7. Close the window when done - the APK temp directory is removed automatically

> Note: the full report is not shown inside the scanner window. The window displays only the summary; the detailed report is the HTML file you save and open in your browser.


## Don't trust: verify

This is a tool for people who distrust tools. Good - verify it:

- **No network calls.** Search the project for `socket`, `urllib`, `requests`: you'll find nothing (the few `in_requests` matches in `core/app_scan.py` are trivial boolean variables for manifest parsing). The tool opens no sockets, runs no servers, contacts nothing.
- **Read-only.** All device commands live in `core/app_scan.py` and `core/tracker_scan.py`: `getprop`, `dumpsys package`, `pm path`, `pull`. No `install`, `uninstall`, `grant`, `revoke`, `rm`.
- **Guaranteed cleanup.** The project's only `open(..., 'w')` is `_save_report` in `scanner.py` - reachable only through the **"Salva report"** button, to a destination you choose. The APK temp directory is created with `tempfile.mkdtemp` (`core/tracker_scan.py`, line 114) and removed in a `finally` block (lines 144-156): no exit path leaves it behind.
- **Verify offline.** Disconnect the network and run a scan: it works normally. The USB ADB connection to the phone is the computer's only communication with the outside world.


## Known limitations

- Some apps may fail to be pulled for analysis (split APKs, special protections): they're shown in the report's "unscannable" section - never as clean.
- ROM-locked permissions (system-fixed / role-granted) can't be changed via ADB on that ROM: the report flags them honestly.
- Signatures come from the Exodus Privacy project, frozen in the published version: **428 known trackers** - unknown or newer trackers won't be detected.
- Detection is signature-based: absence of matches doesn't guarantee absence of trackers.
- Developed and tested on Fedora Linux 44 (Python 3.14.8) with Android 14: Windows/macOS compatibility is designed-in but not empirically verified.


## License

MIT - see `LICENSE`. You're free to use, study, modify, and redistribute this code, as long as the copyright notice is retained.


## Reporting issues

Open an issue in the repository for bugs or improvement suggestions.

# RAG Course Tutor 1.2 – Kurseinstellungen beim Dozenten

Ein Dozentenkonto verwaltet mehrere Kurse. Teilnehmer benötigen kein Tutor-Konto.
Die bestehende Python-/FastAPI-Anwendung bleibt erhalten.

## Update von 1.1

1. Laufenden Tutor beenden und bisherigen Projektordner sichern.
2. Dieses ZIP in einen neuen Ordner entpacken.
3. Den vollständigen bisherigen Ordner `data/` und die bisherige `.env` in den neuen Projektordner übernehmen. Damit bleiben Kurse, Materialien und Dozentenzugang erhalten. Vorhandene Daten nicht durch den leeren mitgelieferten Ordner ersetzen.
4. Im neuen Projektordner `chmod +x start.sh` und `./start.sh` ausführen.
5. Browser mit Strg+F5 neu laden, als Dozent anmelden und unter „Kursdaten“ für jeden Kurs die Einstellungen speichern.

Bestehende Kurse ohne neue Einstellungen verwenden zunächst: Erklären, die in
`RAG_TUTOR_API_URL` konfigurierte Hochschul-API, Modell `UFR: Standard Coding`,
persönlichen Teilnehmer-Key, Top-k 2, Temperatur 0, 1024 Antworttokens und bis zu
10 vorherige Nachrichten. Es ist keine Konvertierung der Kursmaterialien nötig.

## Neuinstallation

Python 3.11 oder neuer:

```bash
cd RAG-Course-Tutor-Single-Teacher
cp .env.example .env
chmod +x start.sh
./start.sh
```

Dann `http://127.0.0.1:8000` öffnen. Über „Dozent anmelden“ beim ersten Start das
alleinige Dozentenkonto einrichten (Passwort mindestens zwölf Zeichen).

## Ablauf für den Vortrag

1. Anmelden → Kursdaten → bestehenden Kurs wählen oder neuen Kurs erstellen.
2. Direkt unter der Kursanlage die Tutor-Einstellungen festlegen und speichern.
3. Eine oder mehrere Materialdateien gleichzeitig auswählen und importieren.
4. Den Teilnehmerlink aus dem Einstellungsformular in einem privaten Browserfenster öffnen.
5. Teilnehmer sehen den festgelegten Modus, aber keine Auswahl für Modus, Modell,
   Server oder Parameter. Bei einem Server ohne Key entfällt auch das API-Key-Feld.

Neue Kurse werden zunächst mit den Standardwerten angelegt. Die Einstellungen
lassen sich unmittelbar danach und jederzeit später im selben Dialog ändern.
Gespeichert wird pro Kurs in `data/courses/<kurs-id>/course.json`.
Das Backend übernimmt die Werte verbindlich aus der Kursdatei; abweichende
Teilnehmerwerte für Modell, Server, Modus oder Top-k werden nicht übernommen.

## Server und Zugang

| Anbindung | Beispieladresse | Zugang |
|---|---|---|
| OpenWebUI / Hochschul-API | `https://openwebui.uni-freiburg.de/api` | Persönlicher API-Key der Teilnehmer |
| Ollama direkt auf dem Tutor-Rechner | `http://localhost:11434` | Ohne API-Key |
| Ollama auf anderem Rechner | `http://SERVER-IP:11434` | Ohne API-Key, falls der Server so eingerichtet ist |
| Andere OpenAI-kompatible API | `https://SERVER/v1` | Entsprechend der Serverkonfiguration |

Bei „Ollama direkt“ die Serverbasis **ohne `/api`** eintragen. Das Modell muss auf
dem Server vorhanden sein. „Modelle abrufen“ liest die Liste; alternativ den
exakten Modellnamen manuell eintragen. Danach die Einstellungen speichern.
Der separate Dozenten-Key dient nur dem Abruf der Modellliste. Für Testfragen
bei aktiviertem persönlichen Zugang oben unter „API-Key“ ebenfalls den eigenen
Key eintragen. Es wird kein gemeinsamer API-Key dauerhaft gespeichert.

Die Verbindung erfolgt vom Tutor-Backend aus. `localhost` bezeichnet deshalb den
Rechner des Backends. Ein anderer Ollama-Rechner muss von dort über das Netzwerk
erreichbar sein und an der entsprechenden Netzwerkschnittstelle lauschen.
„Ohne API-Key“ umgeht keine Authentifizierung eines Servers, der einen Key verlangt.

Die Schlüssel bleiben im Sitzungsspeicher des Browsers und werden beim Kurswechsel
oder Abmelden gelöscht. Sie werden mit der jeweiligen Anfrage ans Backend und von
dort an die ausgewählte API übertragen. Keine Speicherung in Kursdateien,
LocalStorage oder Cookies. Serveradressen können ausschließlich angemeldete
Dozenten konfigurieren oder über die Modelllistenfunktion abfragen.

## Dauerhafte Parameter

- Top-k: 1–20, maximale Anzahl gefundener Kursquellen; bei weniger Treffern entsprechend weniger.
- Temperatur: 0–2; Unterstützung und zulässiger Bereich hängen zusätzlich vom Modellserver ab.
- Maximale Antworttokens: 64–32768; der Modellserver kann weitere Grenzen vorgeben.
- Vorherige Nachrichten: 0–20 einzelne Nachrichten, keine Gesprächspaare; 0 deaktiviert die Übergabe des bisherigen Gesprächs.

Retrieval bleibt lokales BM25. Es werden keine Embedding-Einstellungen angezeigt,
weil diese Version keine Embeddings verwendet. Chunking bleibt unverändert.
Die Sprache können Teilnehmer weiterhin selbst wählen.

## Teilnehmerseite und Mehrfachupload

Eine gemeinsame Oberfläche passt Begrüßung, Modusanzeige und Key-Eingabe an den
Kurs an. Separate vorab erzeugte HTML-Seiten sind daher nicht erforderlich.
Kurslinks haben die Form `http://SERVER:8000/?course=kurs-id`. Bei mehreren Kursen
können Teilnehmer auch über die Kursauswahl wechseln. Diese Links sind keine
Zugangssperren: Wie bisher sind die Kurse für Teilnehmer öffentlich lesbar.

PDF, Markdown, TXT, HTML und TEX werden unterstützt, maximal 25 MB je Datei.
Mehrere ausgewählte Dateien werden nacheinander über den bewährten Upload-Endpunkt
verarbeitet. Ein Fehler stoppt die übrigen Dateien nicht. Die Abschlussmeldung
nennt Erfolg oder Fehler je Datei und die erzeugten Chunks. Erfolgreiche Dateien
nicht erneut hochladen, sonst werden sie wie bisher zusätzlich importiert.

## Betrieb

Das FastAPI-Backend ist weiterhin notwendig: Anmeldung, Upload, Retrieval und
Modellaufrufe laufen dort. Die Änderung erzeugt keine rein statische Website.
`deployment/` enthält Beispiele für Nginx und systemd. Relative URLs unterstützen
den Betrieb unter einem Unterpfad wie `/rag-tutor/` (mit abschließendem Slash).
Für HTTPS-Cookies `RAG_TUTOR_COOKIE_SECURE=1` setzen. Ohne Teilnehmer-Key ist der
konfigurierte Modellzugang für alle erreichbar, die den Tutor erreichen können;
die Erreichbarkeit des Tutors sollte dem vorgesehenen Nutzerkreis entsprechen.

## Prüfung

```bash
.venv/bin/python -m pytest -q
```

Die Tests prüfen Konto, öffentliche Nutzung, Verwaltung, Upload, Retrieval,
Validierung, Persistenz, serverseitige Durchsetzung der Einstellungen und die
HTTP-Anfrageformate für Ollama und OpenAI-kompatible APIs mit simulierten Antworten.
Ein echter Modellaufruf muss mit dem jeweiligen Server vor Ort geprüft werden.

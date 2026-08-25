"""
Anteprima nel browser.

Genera l'HTML che disegna la partitura direttamente nella pagina, cosi' si puo'
guardare l'arrangiamento prima di scaricarlo e aprirlo in un programma di
notazione.

L'incisione la fa OpenSheetMusicDisplay (OSMD), una libreria JavaScript che
legge MusicXML; l'ascolto lo fa html-midi-player sul MIDI di anteprima.
Entrambe arrivano da CDN: senza rete l'anteprima non si vede, ma il download
del file continua a funzionare.
"""

from __future__ import annotations

import base64
from typing import Optional
from xml.etree import ElementTree as ET

# Niente versione fissata: una versione inesistente sul CDN fa fallire tutto in
# silenzio. Si prova jsDelivr e, se non risponde, unpkg.
OSMD_CDN = ["https://cdn.jsdelivr.net/npm/opensheetmusicdisplay/build/"
            "opensheetmusicdisplay.min.js",
            "https://unpkg.com/opensheetmusicdisplay/build/"
            "opensheetmusicdisplay.min.js"]
# per il lettore MIDI serve il pacchetto combinato indicato dagli autori
MIDI_PLAYER_CDN = ("https://cdn.jsdelivr.net/combine/npm/tone@14.7.58,"
                   "npm/@magenta/music@1.23.1/es6/core.js,"
                   "npm/focus-visible@5,npm/html-midi-player@1.4.0")
SOUNDFONT = ("https://storage.googleapis.com/magentadata/js/soundfonts/"
             "sgm_plus")


DICHIARAZIONE = '<?xml version="1.0" encoding="UTF-8"?>'


def taglia_misure(xml: str, quante: int) -> str:
    """
    Tiene solo le prime `quante` misure di ogni parte.

    Disegnare 90 battute per otto strumenti nel browser e' lento e, per farsi
    un'idea, inutile: si guardano le prime pagine.

    ATTENZIONE alla dichiarazione XML: OpenSheetMusicDisplay accetta la
    partitura solo se la stringa COMINCIA con `<?xml`. Rigenerando l'albero
    la dichiarazione si perde, e il visualizzatore risponde "the document
    which was provided is invalid" senza altre spiegazioni.
    """
    if quante <= 0:
        return _con_dichiarazione(xml)
    try:
        radice = ET.fromstring(xml.encode("utf-8"))
    except ET.ParseError:
        return _con_dichiarazione(xml)
    for parte in radice.findall("part"):
        misure = parte.findall("measure")
        for m in misure[quante:]:
            parte.remove(m)
    return DICHIARAZIONE + "\n" + ET.tostring(radice, encoding="unicode")


def _con_dichiarazione(xml: str) -> str:
    testo = xml.lstrip("\ufeff").lstrip()
    if not testo.startswith("<?xml"):
        testo = DICHIARAZIONE + "\n" + testo
    return testo


def html_anteprima(xml: str, midi: Optional[bytes] = None, zoom: float = 0.7,
                   altezza: int = 760, misure: int = 0) -> str:
    """HTML completo dell'anteprima, pronto per `st.components.v1.html`."""
    testo = taglia_misure(xml, misure)
    xml_b64 = base64.b64encode(testo.encode("utf-8")).decode("ascii")

    blocco_midi = ""
    if midi:
        midi_b64 = base64.b64encode(midi).decode("ascii")
        blocco_midi = f"""
      <div class="riga">
        <midi-player src="data:audio/midi;base64,{midi_b64}"
                     sound-font="{SOUNDFONT}" style="width: 100%;">
        </midi-player>
      </div>
      <script src="{MIDI_PLAYER_CDN}"></script>
    """

    return f"""
<!DOCTYPE html>
<html lang="it">
<head>
  <meta charset="utf-8"/>
  <style>
    body {{ margin: 0; font-family: system-ui, sans-serif; background: #fff; }}
    .riga {{ padding: 6px 10px; }}
    #stato {{ padding: 10px; color: #666; font-size: 14px; }}
    #partitura {{ padding: 0 8px 16px 8px; }}
  </style>
</head>
<body>
  {blocco_midi}
  <div id="stato">Disegno la partitura...</div>
  <div id="partitura"></div>

  <script>
    const stato = document.getElementById("stato");
    const FONTI = {OSMD_CDN!r};

    function carica(i) {{
      if (i >= FONTI.length) {{ disegna(); return; }}
      const tag = document.createElement("script");
      tag.src = FONTI[i];
      tag.onload = disegna;
      tag.onerror = () => carica(i + 1);
      document.head.appendChild(tag);
    }}

    function decodifica(b64) {{
      const grezzo = atob(b64);
      const byte = new Uint8Array(grezzo.length);
      for (let i = 0; i < grezzo.length; i++) byte[i] = grezzo.charCodeAt(i);
      return new TextDecoder("utf-8").decode(byte);
    }}

    function disegna() {{
      if (typeof opensheetmusicdisplay === "undefined") {{
        stato.innerHTML = "Non riesco a caricare il visualizzatore: serve la "
          + "connessione a internet, e la rete non deve bloccare "
          + "<code>cdn.jsdelivr.net</code> o <code>unpkg.com</code>.<br>"
          + "L'arrangiamento e' comunque pronto: scaricalo dalla scheda "
          + "<b>Download</b>.";
        return;
      }}
      const osmd = new opensheetmusicdisplay.OpenSheetMusicDisplay(
        "partitura", {{
          autoResize: true,
          backend: "svg",
          drawTitle: true,
          drawSubtitle: true,
          drawPartNames: true,
          drawMeasureNumbers: true,
          followCursor: false
        }});
      osmd.zoom = {zoom};
      osmd.load(decodifica("{xml_b64}"))
        .then(() => {{ osmd.render(); stato.style.display = "none"; }})
        .catch((e) => {{
          const xml = decodifica("{xml_b64}");
          stato.innerHTML = "Non riesco a disegnare questa partitura: " + e
            + "<br><small>Inizio del documento: <code>"
            + xml.slice(0, 60).replace(/</g, "&lt;") + "</code></small>";
        }});
    }}

    carica(0);
  </script>
</body>
</html>
"""

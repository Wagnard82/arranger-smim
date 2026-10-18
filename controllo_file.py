"""
Controllo che i file sul server siano tutti della stessa versione.

Perche' esiste: aggiornando il repository solo in parte, l'app si fermava
con errori incomprensibili («ImportError ... from arranger.esportatore import
sigla_scritta») invece di dire quale file era rimasto indietro. Il controllo
di versione dentro app.py non bastava, perche' scattava DOPO gli import del
motore: proprio quelli che fallivano.

Come funziona:
  - al momento di preparare lo zip si scrive `manifesto.json`, con
    l'impronta (SHA-256) di ogni file del progetto:
        python controllo_file.py --scrivi
  - all'avvio, app.py chiama `differenze()` PRIMA di importare il motore,
    ed elenca i file mancanti o diversi.

Usa solo la libreria standard e non importa niente di `arranger`: deve
funzionare anche quando il motore e' rotto. Le righe vengono normalizzate
(\\r\\n -> \\n) prima del calcolo, cosi' un checkout Windows non segnala
differenze che non ci sono.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from typing import Dict, List, Optional, Tuple

QUI = os.path.dirname(os.path.abspath(__file__))
MANIFESTO = "manifesto.json"

# cio' che serve all'app per girare; esempi XML e test restano fuori
CARTELLE = ("arranger", "esempi")
FILE_RADICE = ("app.py", "requirements.txt", "controllo_file.py")


def _impronta(percorso: str) -> str:
    with open(percorso, "rb") as f:
        dati = f.read().replace(b"\r\n", b"\n")
    return hashlib.sha256(dati).hexdigest()


def _elenco(radice: str) -> List[str]:
    fuori = [f for f in FILE_RADICE if os.path.exists(os.path.join(radice, f))]
    for cartella in CARTELLE:
        for base, dirs, files in os.walk(os.path.join(radice, cartella)):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for nome in files:
                if nome.endswith(".py"):
                    completo = os.path.join(base, nome)
                    fuori.append(os.path.relpath(completo, radice).replace(os.sep, "/"))
    return sorted(fuori)


def scrivi(radice: str = QUI, versione: str = "") -> Dict:
    dati = {"versione": versione,
            "file": {rel: _impronta(os.path.join(radice, rel))
                     for rel in _elenco(radice)}}
    with open(os.path.join(radice, MANIFESTO), "w", encoding="utf-8") as f:
        json.dump(dati, f, indent=1, sort_keys=True)
        f.write("\n")
    return dati


def differenze(radice: str = QUI) -> Tuple[Optional[str], List[str], List[str]]:
    """
    (versione attesa, file mancanti, file diversi).
    Versione None = manca il manifesto stesso.
    """
    percorso = os.path.join(radice, MANIFESTO)
    if not os.path.exists(percorso):
        return None, [], []
    with open(percorso, encoding="utf-8") as f:
        dati = json.load(f)
    mancanti, diversi = [], []
    for rel, impronta in sorted(dati.get("file", {}).items()):
        completo = os.path.join(radice, *rel.split("/"))
        if not os.path.exists(completo):
            mancanti.append(rel)
        elif _impronta(completo) != impronta:
            diversi.append(rel)
    return dati.get("versione", ""), mancanti, diversi


if __name__ == "__main__":
    if "--scrivi" in sys.argv:
        sys.path.insert(0, QUI)
        from arranger.versione import VERSIONE
        d = scrivi(versione=VERSIONE)
        print(f"manifesto.json scritto: {len(d['file'])} file, versione {VERSIONE}")
    else:
        v, m, d = differenze()
        if v is None:
            print("manifesto.json assente")
            sys.exit(2)
        print(f"versione attesa {v}: {len(m)} mancanti, {len(d)} diversi")
        for x in m:
            print("  MANCA   ", x)
        for x in d:
            print("  DIVERSO ", x)
        sys.exit(1 if (m or d) else 0)

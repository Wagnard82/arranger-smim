"""
Basi «meno uno» per lo studio a casa.

Per ogni leggio un file con tutta l'orchestra tranne quella parte, alle
velocita' scelte dal docente (per esempio normale e 75%), con due battute
di clic prima della musica: a casa non c'e' nessuno che da' l'attacco.

Le basi nascono dal MIDI di anteprima (`esportatore.esporta_midi`), quindi
la musica e' esattamente quella della partitura. Per farne degli MP3, che
si ascoltano su qualunque telefono, servono due programmi esterni:
FluidSynth con un soundfont General MIDI, che suona il MIDI, e ffmpeg (o
lame), che codifica l'MP3. Si chiamano come programmi a parte: il nucleo
resta in sola libreria standard. Se mancano, le basi restano in MIDI e il
report lo dice.

Su Streamlit Cloud i programmi si installano al deploy con `packages.txt`
(fluidsynth, fluid-soundfont-gm, ffmpeg). VERIFICATO in locale su Mac con
FluidSynth di Homebrew; sul server NON ancora verificato.
"""

from __future__ import annotations

import glob
import os
import shutil
import subprocess
import zipfile
from dataclasses import dataclass, field
from typing import Iterable, List, Optional

from . import esportatore
from .lingua import t as testo
from .modello import Partitura

# battute di clic prima della musica
BATTUTE_ATTACCO = 2
VELOCITA_MINIMA, VELOCITA_MASSIMA = 25, 150

# dove si cerca il soundfont, nell'ordine; la variabile d'ambiente vince
SOUNDFONT = [
    "/usr/share/sounds/sf2/FluidR3_GM.sf2",       # Debian/Ubuntu: fluid-soundfont-gm
    "/usr/share/sounds/sf2/default-GM.sf2",
    "/usr/share/soundfonts/FluidR3_GM.sf2",
    "/usr/share/soundfonts/default.sf2",
    "/opt/homebrew/share/soundfonts/default.sf2",
    "/usr/local/share/soundfonts/default.sf2",
    "/Applications/MuseScore 4.app/Contents/Resources/sound/MS Basic.sf3",
]


@dataclass
class Sintetizzatore:
    fluidsynth: str
    soundfont: str
    ffmpeg: str = ""          # uno dei due codificatori basta
    lame: str = ""


@dataclass
class Basi:
    file: List[str] = field(default_factory=list)
    zip: str = ""
    formato: str = "mid"      # "mp3" oppure "mid"
    avvisi: List[str] = field(default_factory=list)


def trova_sintetizzatore() -> Optional[Sintetizzatore]:
    """FluidSynth, un soundfont e un codificatore MP3, se ci sono tutti."""
    fluidsynth = shutil.which("fluidsynth")
    ffmpeg, lame = shutil.which("ffmpeg") or "", shutil.which("lame") or ""
    candidati = [os.environ.get("SCORECRAFT_SOUNDFONT", "")] + SOUNDFONT
    candidati += sorted(glob.glob("/usr/share/sounds/sf2/*.sf2"))
    soundfont = next((c for c in candidati if c and os.path.isfile(c)), "")
    if not (fluidsynth and soundfont and (ffmpeg or lame)):
        return None
    return Sintetizzatore(fluidsynth, soundfont, ffmpeg, lame)


def velocita_valide(valori: Iterable) -> List[int]:
    """
    Le percentuali del docente ripulite: numeri interi fra 25 e 150, senza
    doppioni, nell'ordine dato. Senza niente di valido resta la normale.
    """
    fuori: List[int] = []
    for v in valori:
        try:
            n = int(round(float(v)))
        except (TypeError, ValueError):
            continue
        n = min(VELOCITA_MASSIMA, max(VELOCITA_MINIMA, n))
        if n not in fuori:
            fuori.append(n)
    return fuori or [100]


def _slug(nome: str) -> str:
    fuori = "".join(c if c.isalnum() or c in "-_" else "_" for c in nome.strip())
    return fuori.strip("_") or "parte"


def _in_mp3(s: Sintetizzatore, midi: str, mp3: str, timeout: int = 180) -> None:
    """Suona il MIDI con FluidSynth e lo codifica in MP3. RuntimeError se fallisce."""
    wav = os.path.splitext(mp3)[0] + ".wav"
    try:
        # guadagno basso: con tutta l'orchestra insieme il suono non satura
        esito = subprocess.run(
            [s.fluidsynth, "-ni", "-g", "0.5", "-r", "44100", "-F", wav,
             s.soundfont, midi], capture_output=True, text=True, timeout=timeout)
        if esito.returncode != 0 or not os.path.exists(wav):
            raise RuntimeError((esito.stderr or esito.stdout)[-500:] or "FluidSynth")
        if s.ffmpeg:
            comando = [s.ffmpeg, "-y", "-loglevel", "error", "-i", wav,
                       "-codec:a", "libmp3lame", "-qscale:a", "4", mp3]
        else:
            comando = [s.lame, "--quiet", "-V", "4", wav, mp3]
        esito = subprocess.run(comando, capture_output=True, text=True, timeout=timeout)
        if esito.returncode != 0 or not os.path.exists(mp3):
            raise RuntimeError((esito.stderr or esito.stdout)[-500:] or "MP3")
    except (OSError, subprocess.TimeoutExpired) as e:
        raise RuntimeError(str(e)) from e
    finally:
        if os.path.exists(wav):
            os.remove(wav)


def genera_basi(part: Partitura, cartella: str, nome_base: str,
                velocita: Iterable = (100, 75), sintetizzatore="auto",
                lingua: Optional[str] = None,
                attacco: int = BATTUTE_ATTACCO) -> Basi:
    """
    Una base per ogni leggio e ogni velocita', raccolte in uno ZIP.

    `sintetizzatore`: "auto" lo cerca sul sistema, None forza i MIDI.
    I file vanno nella sottocartella `<nome_base>_basi`, lo ZIP accanto.
    """
    lingua = lingua or part.lingua
    velocita = velocita_valide(velocita)
    if sintetizzatore == "auto":
        sintetizzatore = trova_sintetizzatore()
    dove = os.path.join(cartella, f"{nome_base}_{testo('basi_cartella', lingua)}")
    os.makedirs(dove, exist_ok=True)
    senza = testo("basi_senza", lingua)

    midi: List[str] = []
    for p in part.parti:
        for v in velocita:
            f = os.path.join(dove, f"{nome_base}_{senza}_{_slug(p.nome)}_{v}.mid")
            esportatore.esporta_midi(part, f, escludi=[p.id], velocita=v,
                                     attacco=attacco)
            midi.append(f)

    b = Basi(file=midi, formato="mid")
    if sintetizzatore is None:
        b.avvisi.append(testo("basi_solo_midi", lingua))
    else:
        mp3: List[str] = []
        try:
            for f in midi:
                mp3.append(os.path.splitext(f)[0] + ".mp3")
                _in_mp3(sintetizzatore, f, mp3[-1])
        except RuntimeError as e:
            for f in mp3:
                if os.path.exists(f):
                    os.remove(f)
            b.avvisi.append(testo("basi_mp3_fallite", lingua, errore=e))
        else:
            for f in midi:
                os.remove(f)
            b.file, b.formato = mp3, "mp3"

    b.zip = os.path.join(cartella, f"{nome_base}_{testo('basi_cartella', lingua)}.zip")
    with zipfile.ZipFile(b.zip, "w", zipfile.ZIP_DEFLATED) as z:
        for f in b.file:
            z.write(f, os.path.basename(f))
    b.avvisi.append(testo("basi_pronte", lingua, n=len(b.file),
                          formato="MP3" if b.formato == "mp3" else "MIDI",
                          velocita=", ".join(f"{v}%" for v in velocita)))
    return b

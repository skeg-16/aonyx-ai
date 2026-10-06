"""Speech segmentation for the Aonyx TTS pipeline.

Turns the LLM's token stream into natural, sentence/phrase-sized speech segments
that can be synthesised ahead of playback. Pure Python, no I/O, unit-testable.
"""
import re
from typing import List, Tuple

# Titles/abbreviations after which a '.' does not end a sentence.
_ABBREV = {
    "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "vs", "st", "mt", "inc", "ltd",
    "co", "corp", "e.g", "i.e", "approx", "no", "fig", "eg", "ie",
}

_END_RE = re.compile(r"[.!?]+[\"')\]]*(?=\s)")
_CLAUSE_RE = re.compile(r"[,;:](?=\s)|\s[\u2014\u2013-]\s")


def clean_for_speech(text: str) -> str:
    """Remove markdown / URLs / list markers so the text is both speakable and displayable."""
    t = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    t = re.sub(r"https?://\S+", " ", t)
    t = re.sub(r"`+", "", t)
    t = re.sub(r"\*+", "", t)
    t = re.sub(r"(?<!\w)_+|_+(?!\w)", "", t)
    t = re.sub(r"^\s*#{1,6}\s*", "", t, flags=re.MULTILINE)
    t = re.sub(r"^\s*(?:[-\u2022]|\d+[.)])\s+", "", t, flags=re.MULTILINE)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\s*\n\s*", " ", t)
    t = t.strip()
    return t if re.search(r"[A-Za-z0-9]", t) else ""


def _is_real_sentence_end(buf: str, end_idx: int) -> bool:
    """end_idx = index of the first terminator char. Reject decimals, abbreviations, initials."""
    if buf[end_idx] != ".":
        return True
    m = re.search(r"([A-Za-z.]+)$", buf[:end_idx])
    if m:
        tok = m.group(1).lower().strip(".")
        if tok in _ABBREV:
            return False
        if len(tok) == 1 and tok.isalpha() and buf[end_idx - 1].isupper():
            return False  # single capital initial: "J. Smith"
    return True


class SpeechChunker:
    """Incrementally splits streamed text into speech segments.

    feed() returns [(text, nl)] where nl marks that a paragraph/line break preceded the segment.
    """

    def __init__(self, first_min: int = 14, min_len: int = 36, max_len: int = 230):
        self.first_min = first_min
        self.min_len = min_len
        self.max_len = max_len
        self.reset()

    def reset(self):
        self.buf = ""
        self.cand = ""
        self.cand_nl = False
        self.pending_nl = False
        self.emitted = 0

    def _threshold(self) -> int:
        return self.first_min if self.emitted == 0 else self.min_len

    def _emit(self, out: List[Tuple[str, bool]]):
        text = self.cand.strip()
        if text:
            out.append((text, self.cand_nl))
            self.emitted += 1
        self.cand = ""
        self.cand_nl = self.pending_nl
        self.pending_nl = False

    def _absorb(self, sentence: str, out: List[Tuple[str, bool]], hard: bool):
        s = sentence.strip()
        if not s:
            return
        if not self.cand:
            self.cand_nl = self.cand_nl or self.pending_nl
            self.pending_nl = False
        self.cand = (self.cand + " " + s).strip()
        if hard or len(self.cand) >= self._threshold():
            self._emit(out)

    def feed(self, text: str) -> List[Tuple[str, bool]]:
        out: List[Tuple[str, bool]] = []
        self.buf += text
        while True:
            nl = self.buf.find("\n")
            m = None
            for cand in _END_RE.finditer(self.buf):
                if _is_real_sentence_end(self.buf, cand.start()):
                    m = cand
                    break
            if nl != -1 and (m is None or nl < m.end()):
                self._absorb(self.buf[:nl], out, hard=True)
                self.buf = self.buf[nl + 1:]
                self.pending_nl = True
                continue
            if m is not None:
                self._absorb(self.buf[:m.end()], out, hard=False)
                self.buf = self.buf[m.end():]
                continue
            # No sentence boundary yet. Break overly long runs at a clause boundary.
            if len(self.buf) > self.max_len:
                best = None
                for c in _CLAUSE_RE.finditer(self.buf):
                    if c.end() >= 60:
                        best = c
                        break
                if best is not None:
                    self._absorb(self.buf[:best.end()], out, hard=True)
                    self.buf = self.buf[best.end():]
                    continue
                if len(self.buf) > self.max_len + 60:
                    cut = self.buf.rfind(" ", 0, self.max_len)
                    if cut > 60:
                        self._absorb(self.buf[:cut], out, hard=True)
                        self.buf = self.buf[cut + 1:]
                        continue
            break
        return out

    def flush(self) -> List[Tuple[str, bool]]:
        out: List[Tuple[str, bool]] = []
        if self.buf.strip():
            self._absorb(self.buf, out, hard=True)
        elif self.cand:
            self._emit(out)
        if self.cand:
            self._emit(out)
        self.buf = ""
        return out

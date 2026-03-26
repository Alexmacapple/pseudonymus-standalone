#!/usr/bin/env python3
"""
Pseudonymise ou anonymise un JSON générique.
Iso-périmètre fonctionnel avec Pseudonymus v2 (app.js).
Traitement 100% local — aucune donnée transmise.

Usage :
    python3 pseudonymise.py data/fichier.json --mapping mapping.json --dry-run
    python3 pseudonymise.py data/fichier.json --mapping mapping.json --pseudo
    python3 pseudonymise.py data/fichier.json --mapping mapping.json --fort --pseudo
    python3 pseudonymise.py data/fichier.json --mapping mapping.json --score-only
"""

import argparse
import csv
import json
import os
import re
import sys
import unicodedata
import uuid


# =============================================================
#  CHARGEMENT DES DONNÉES DE RÉFÉRENCE
# =============================================================

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(_SCRIPT_DIR, 'data')
CONFIDENTIEL_DIR = os.path.join(_SCRIPT_DIR, 'confidentiel')


def _load_set(filename):
    path = os.path.join(DATA_DIR, filename)
    with open(path, 'r', encoding='utf-8') as f:
        return set(json.load(f))


def _load_set_upper(filename):
    path = os.path.join(DATA_DIR, filename)
    with open(path, 'r', encoding='utf-8') as f:
        return set(x.upper() for x in json.load(f))


print('Chargement des donnees de reference...', file=sys.stderr)
PATRONYMES = _load_set_upper('noms.json')
PRENOMS = _load_set_upper('prenoms.json')
STOPWORDS_CAP = _load_set('stopwords-capitalises.json')
STOPWORDS_MIN = _load_set('stopwords-minuscules.json')
MAJUSCULES_GARDER = _load_set('majuscules-garder.json')
VILLES_FRANCE = _load_set('villes-france.json')
MOTS_ORGANISATIONS = _load_set('mots-organisations.json')
CONTEXTE_INSTITUTION = _load_set('contexte-institution.json')
ACRONYMES_GARDER = _load_set('acronymes-garder.json')
print(f'  {len(PATRONYMES)} patronymes, {len(PRENOMS)} prenoms charges.', file=sys.stderr)


# =============================================================
#  REGEX COMPLÈTES (adaptées depuis app.js)
# =============================================================

# --- Finance & régalien ---
RX_NUM_FISCAL = re.compile(r'\b[0-3]\d{12}\b')
RX_NIR = re.compile(
    r'(?<!\d)([12])[\s.\-]*(\d{2})[\s.\-]*(\d{2})[\s.\-]*'
    r'(\d{2}|2[AB])[\s.\-]*(\d{3})[\s.\-]*(\d{3})'
    r'(?:[\s.\-]*(\d{2}))?(?!\d)', re.IGNORECASE)
RX_IBAN = re.compile(
    r'\b[A-Z]{2}\d{2}[\s\-]?[0-9A-Z]{4}[\s\-]?[0-9A-Z]{4}'
    r'[\s\-]?[0-9A-Z]{4}[\s\-]?[0-9A-Z]{4}'
    r'[\s\-]?[0-9A-Z]{0,4}[\s\-]?[0-9A-Z]{0,3}\b', re.IGNORECASE)
RX_CB = re.compile(r'\b(?:\d[\s\-]*?){13,19}\b')
RX_CVV = re.compile(r'\b(cvv|cvc|cryptogramme|cv2)\W+(\d{3,4})\b', re.IGNORECASE)
RX_SIRET = re.compile(r'\b\d{3}[\s.]?\d{3}[\s.]?\d{3}(?:[\s.]?\d{5})?\b')

# --- Communication ---
RX_MAILTO = re.compile(r'\b(mailto):([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', re.IGNORECASE)
RX_EMAIL_OBFUSCATED = re.compile(
    r'\b[a-zA-Z0-9_.+-]+\s*(?:@|\[at\]|\(at\)|\[arobase\])'
    r'\s*[a-zA-Z0-9-]+\s*(?:\.|\[dot\]|\(dot\)|point)\s*[a-zA-Z0-9-.]+\b', re.IGNORECASE)
RX_EMAIL_AVEC = re.compile(
    r'\b(De|From|À|A|To|Cc|Bcc)\s*:\s*([A-ZÀ-ÖØ-Ý][A-Za-zÀ-ÖØ-öø-ÿ\'\-]+(?:\s+[A-ZÀ-ÖØ-Ý][A-Za-zÀ-ÖØ-öø-ÿ\'\-]+)*)'
    r'\s*<[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+>', re.IGNORECASE)
RX_EMAIL_ESPACE = re.compile(
    r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(?:\s*\.\s*|\s+|\.)[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-.]+)*')
RX_EMAIL = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')

# --- Téléphones ---
RX_TEL_FUZZY = re.compile(r'(?<!\d)(?:(?:\+|00)33|0)\s*[1-9](?:[\s._\-]*\d){8}(?!\d)')
RX_TEL_PREFIXE = re.compile(r'TEL\s*:\s*[\d\s.\-]+', re.IGNORECASE)
RX_TEL = re.compile(r'(?<!\d)(?:\+33|0)[1-9](?:[\s.\-]*\d{2}){4}(?!\d)')

# --- URLs ---
RX_URL = re.compile(r'\bhttps?://\S+|\bwww\.\S+')

# --- Organisations ---
RX_ORGA_AGRESSIF = re.compile(
    r'\b([A-ZÀ-ÖØ-Ý][A-Za-zÀ-ÖØ-öø-ÿ&\'\-]+(?:\s+[A-ZÀ-ÖØ-Ý][A-Za-zÀ-ÖØ-öø-ÿ&\'\-]+)*)'
    r'\s+(SA|SAS|SARL|SNC|EURL|SASU|SCI|SCM|SCOP|SEM|GIE|ASSOCIATION|FONDATION)\b')

# --- Adresses ---
RX_VOIE_NUM = re.compile(
    r"\b\d+\s+(?:rue|avenue|boulevard|chemin|impasse|allée|route|bis|ter)"
    r"\s+[A-Za-zÀ-ÖØ-öø-ÿ'\-\s]{3,}", re.IGNORECASE)
RX_VOIE_SANS = re.compile(
    r"\b(?:rue|avenue|boulevard|chemin|impasse|allée|route)"
    r"\s+[A-Za-zÀ-ÖØ-öø-ÿ'\-\s]{3,}", re.IGNORECASE)
RX_CP = re.compile(r'\b\d{5}\b')

# --- Entités personnes ---
RX_SALUTATION = re.compile(
    r'\b(?:Bonjour|Salut|Bonsoir|Hello|Hi|Coucou|Cher|Chère|bonjour|salut|bonsoir|hello|hi|coucou|cher|chère)'
    r'[ \t]+([A-ZÀ-ÖØ-Ý][A-Za-zÀ-ÖØ-öø-ÿ\'\-]+(?:[ \t]+[A-ZÀ-ÖØ-Ý][A-Za-zÀ-ÖØ-öø-ÿ\'\-]+)*)')
RX_TITRE = re.compile(
    r'\b(M\.|Mme\.?|Mlle\.?|[Mm]onsieur|[Mm]adame|[Mm]ademoiselle)\s*'
    r'([A-ZÀ-ÖØ-Ý](?:[a-zà-öø-ÿ]+|[A-ZÀ-ÖØ-Ý]+)[A-Za-zÀ-ÖØ-öø-ÿ\'\-]*'
    r'(?:\s+[A-ZÀ-ÖØ-Ý][A-Za-zÀ-ÖØ-öø-ÿ\'\-]+)*)', re.IGNORECASE)
RX_PRENOM_NOM_MAJ = re.compile(
    r'\b([A-ZÀ-ÖØ-Ý][a-zà-öø-ÿ\'\-]+)[ ]+'
    r'([A-ZÀ-ÖØ-Ý]{2,}[A-ZÀ-ÖØ-öø-ÿ\'\-]*(?:[ ]+[A-ZÀ-ÖØ-Ý][A-Za-zÀ-ÖØ-öø-ÿ\'\-]+)*)')
RX_PRENOM_NOM = re.compile(
    r'\b([A-ZÀ-ÖØ-Ý][a-zà-öø-ÿ\'\-]+)(?:[ ]+([A-ZÀ-ÖØ-Ý][a-zà-öø-ÿ\'\-]+))+')

# --- Mode fort ---
RX_DATE_NAISS = re.compile(
    r'\b(né|née|naissance)(?:e|s)?\s+(?:le|du|au)?\s*:?\s*(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})\b', re.IGNORECASE)
RX_GPS = re.compile(r'\b-?(?:[1-8]?\d\.\d+|90\.0+)[,\s]+-?(?:1(?:[0-7]\d)|[1-9]?\d)\.\d+\b')
RX_PLAQUE = re.compile(r'\b(?:[A-Z]{2}[-\s]?\d{3}[-\s]?[A-Z]{2}|\d{1,4}[-\s]?[A-Z]{2,3}[-\s]?\d{2})\b')
RX_PRENOM_ISOLE = re.compile(
    r'(?<![A-Za-zÀ-ÖØ-öø-ÿ])([A-ZÀ-ÖØ-Ý][a-zà-öø-ÿ]*(?:-[A-ZÀ-ÖØ-Ý][a-zà-öø-ÿ]+)*)(?![A-Za-zÀ-ÖØ-öø-ÿ])')
RX_PRENOM_ISOLE_MIN = re.compile(
    r'(?<![A-Za-zÀ-ÖØ-öø-ÿ])([a-zà-öø-ÿ]{3,}(?:-[a-zà-öø-ÿ]{3,})?)(?![A-Za-zÀ-ÖØ-öø-ÿ])')
RX_PREFIXES = re.compile(
    r'\b(BEN|EL|AL|AIT|ABDEL)(?:[\s-][A-ZÀ-ÖØ-Ý][A-Za-zÀ-ÖØ-öø-ÿ]{2,})+\b', re.IGNORECASE)
RX_MAJ_LONG = re.compile(r"\b(?:[Ll]'|[Dd]')?[A-ZÀ-ÖØ-Ý]{2,}(?:-[A-ZÀ-ÖØ-Ý]{2,})*\b")
RX_VILLE_COMPOSEE = re.compile(
    r"\b[A-ZÀ-ÖØ-Ý]{3,}(?:[\s-](?:SUR|SOUS|LES|AUX|LEZ|LÈZ|DE|DU|D')[\s-][A-ZÀ-ÖØ-Ý]{3,})+\b")

# --- Mode tech (--tech) ---
RX_IPV4 = re.compile(
    r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
    r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b')
RX_IPV6 = re.compile(
    r'(?:[a-fA-F0-9]{1,4}:){7}[a-fA-F0-9]{1,4}|'
    r'(?:[a-fA-F0-9]{1,4}:){1,7}:|'
    r'::(?:[a-fA-F0-9]{1,4}:){0,5}[a-fA-F0-9]{1,4}')
RX_MAC = re.compile(r'\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b')
RX_JWT = re.compile(r'\beyJ[a-zA-Z0-9_-]{10,}\.eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\b')
RX_API_KEY = re.compile(r'\b(?:sk|pk|api)_[a-zA-Z0-9]{20,}\b')

# --- Contexte numérique négatif ---
RX_CTX_NB_AVANT = re.compile(
    r'\b(n°|n\.|numéro|décret|article|art\.|référence|ref\.|dossier|commande|lot|page|p\.'
    r'|chapitre|volume|tome|fig\.|figure|tableau|tab\.|kg|g|m|cm|mm|km|€|eur|euros|%|degrés?)\s*$', re.IGNORECASE)
RX_CTX_NB_APRES = re.compile(
    r'^\s*(kg|g|m|cm|mm|km|€|eur|euros|%|degrés?|°|exemplaires?|pages?)', re.IGNORECASE)

# --- Espacement jetons ---
RX_COLLER_TOKEN = re.compile(r'([\wÀ-ž])\[PERSONNE_(\d+)\]')
RX_COLLER_TOKEN2 = re.compile(r'\[PERSONNE_(\d+)\]([\wÀ-ž])')


# =============================================================
#  VALIDATEURS
# =============================================================

def luhn_check(s):
    digits = re.sub(r'\D', '', s)
    if len(digits) < 9:
        return False
    if len(digits) in (9, 14):
        return False
    total = 0
    double = False
    for ch in reversed(digits):
        d = int(ch)
        if double:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        double = not double
    return total % 10 == 0


def nir_check(s):
    clean = re.sub(r'[\s.\-]', '', s)
    if len(clean) == 15:
        clean = clean[:13]
    if len(clean) != 13:
        return False
    mois = int(clean[3:5])
    return 1 <= mois <= 12


def siret_check(s):
    clean = re.sub(r'\D', '', s)
    return len(clean) in (9, 14) and luhn_raw(clean)


def luhn_raw(digits):
    if len(digits) < 9:
        return False
    total = 0
    double = False
    for ch in reversed(digits):
        d = int(ch)
        if double:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        double = not double
    return total % 10 == 0


# =============================================================
#  FONCTIONS UTILITAIRES
# =============================================================

def normalize_for_prenom(s):
    """Supprime les diacritiques pour le matching prénoms."""
    return unicodedata.normalize('NFD', s).encode('ascii', 'ignore').decode('ascii')


def est_prenom_connu(mot):
    if not mot or len(mot) < 2:
        return False
    key = mot.upper().strip()
    if key in PRENOMS:
        return True
    sans_accent = normalize_for_prenom(mot).upper().strip()
    return sans_accent in PRENOMS


def est_patronyme_connu(mot):
    if not mot or len(mot) < 2:
        return False
    return mot.upper().strip() in PATRONYMES


def est_contexte_institution(text, match_str, offset):
    """Vérifie si un mot est adjacent à un contexte institutionnel."""
    # Mot suivant
    suite = text[offset + len(match_str):]
    m = re.match(r'^[\s\t]+(\S+)', suite)
    if m and m.group(1).lower() in CONTEXTE_INSTITUTION:
        return True
    # Mot précédent
    avant = text[max(0, offset - 40):offset]
    m = re.search(r'(\S+)[\s\t]+$', avant)
    if m and m.group(1).lower() in CONTEXTE_INSTITUTION:
        return True
    return False


def contexte_nb_negatif(text, offset, match_len):
    """Vérifie si un nombre est dans un contexte non personnel."""
    avant = text[max(0, offset - 20):offset]
    if RX_CTX_NB_AVANT.search(avant):
        return True
    apres = text[offset + match_len:min(len(text), offset + match_len + 20)]
    if RX_CTX_NB_APRES.match(apres):
        return True
    return False


# =============================================================
#  NORMALISATION PERSONNES (comme l'original l.191-202)
# =============================================================

def normaliser_personne(raw):
    """Normalise un nom pour détecter les doublons."""
    s = raw.strip()
    s = re.sub(r'\[PERSONNE_\d+\]', '', s, flags=re.IGNORECASE)
    s = re.sub(r'\b(m\.|mme\.?|mlle\.?|monsieur|madame)\b', '', s, flags=re.IGNORECASE)
    s = re.sub(r"[^A-Za-zÀ-ÖØ-öø-ÿ\-' ]+", ' ', s)
    s = re.sub(r'\s+', ' ', s).strip().lower()
    parts = s.split(' ')
    if len(parts) == 2 and "'" not in s:
        return ' '.join(sorted(parts))
    return s


# =============================================================
#  TABLE DE CORRESPONDANCES & SCORING
# =============================================================

class TokenTable:
    def __init__(self):
        self._counters = {}
        # {type_name: {normalized_key: (num, original_cased_value)}}
        self._typed = {}
        # Personnes : {normalized_key: (pid_str, original_cased_value)}
        self._personnes = {}

    def get_token(self, raw):
        """Jeton PERSONNE_X pour un nom détecté dans le texte."""
        key = normaliser_personne(raw)
        if not key:
            return '[PERSONNE]'
        if key not in self._personnes:
            self._counters['personne'] = self._counters.get('personne', 0) + 1
            pid = f'PERSONNE_{self._counters["personne"]}'
            self._personnes[key] = (pid, raw.strip())
        return f'[{self._personnes[key][0]}]'

    def get_typed_token(self, type_name, prefix, value):
        """Jeton numéroté [PREFIX_X] pour un champ structuré ou une détection texte."""
        if not value or not str(value).strip():
            return None
        key = str(value).strip().lower()
        if type_name not in self._typed:
            self._typed[type_name] = {}
        if key not in self._typed[type_name]:
            self._counters[type_name] = self._counters.get(type_name, 0) + 1
            self._typed[type_name][key] = (self._counters[type_name], str(value).strip())
        num = self._typed[type_name][key][0]
        return f'[{prefix}_{num}]'

    def export_csv(self, filepath):
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        rows = []
        # Jetons typés
        prefix_map = {
            'id': 'ID', 'uuid': 'UUID', 'prenom': 'PRENOM',
            'nom': 'NOM', 'email': 'EMAIL', 'tel': 'TEL',
            'cp': 'CP', 'genre': 'GENRE', 'email_txt': 'EMAIL',
            'tel_txt': 'TEL', 'iban_txt': 'IBAN', 'nir_txt': 'NIR',
            'cb_txt': 'CB', 'cvv_txt': 'CVV', 'siret_txt': 'SIRET',
            'siren_txt': 'SIREN', 'fiscal_txt': 'ID_FISCAL',
            'url_txt': 'URL', 'voie_txt': 'VOIE', 'orga_txt': 'ORGANISATION',
            'ville_txt': 'VILLE', 'date_naiss_txt': 'DATE_NAISSANCE',
        }
        for type_name, mapping in self._typed.items():
            prefix = prefix_map.get(type_name, type_name.upper())
            for key, (num, original) in mapping.items():
                rows.append((type_name, f'[{prefix}_{num}]', original))
        # Personnes
        for key, (pid, original) in self._personnes.items():
            rows.append(('personne', f'[{pid}]', original))
        rows.sort(key=lambda r: (r[0], r[1]))
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow(['type', 'jeton', 'valeur_originale'])
            for row in rows:
                writer.writerow(row)
        os.chmod(filepath, 0o600)


class RiskScorer:
    def __init__(self):
        self.score = 0
        self.details = {'direct': 0, 'finance': 0, 'tech': 0, 'indirect': 0}

    def add(self, type_name, count=1):
        points = {'finance': 5, 'direct': 3, 'tech': 2}.get(type_name, 1)
        self.details[type_name] = self.details.get(type_name, 0) + count
        self.score += points * count

    def level(self):
        if self.score == 0:
            return 'NUL'
        if self.score < 10:
            return 'FAIBLE'
        if self.score < 50:
            return 'MODÉRÉ'
        if self.score < 100:
            return 'ÉLEVÉ'
        return 'CRITIQUE'

    def reset(self):
        self.score = 0
        self.details = {'direct': 0, 'finance': 0, 'tech': 0, 'indirect': 0}


class Stats:
    def __init__(self):
        self.counts = {}
        self.samples = {}
        self.errors = 0
        self.dict_hits = {}  # Compteur des mots matchés par dictionnaire

    def add(self, type_name, original, replacement):
        self.counts[type_name] = self.counts.get(type_name, 0) + 1
        if type_name not in self.samples:
            self.samples[type_name] = []
        if len(self.samples[type_name]) < 5:
            self.samples[type_name].append((str(original)[:60], replacement))

    def add_dict_hit(self, mot):
        key = mot.upper()
        self.dict_hits[key] = self.dict_hits.get(key, 0) + 1

    def report(self, total, processed, scorer=None):
        print(f'\n{"=" * 60}', file=sys.stderr)
        print(f'RAPPORT DE TRAITEMENT', file=sys.stderr)
        print(f'{"=" * 60}', file=sys.stderr)
        print(f'Enregistrements : {processed}/{total} traites', file=sys.stderr)
        if self.errors:
            print(f'Erreurs (skippes) : {self.errors}', file=sys.stderr)
        print(f'\nRemplacements par type :', file=sys.stderr)
        for t in sorted(self.counts.keys()):
            print(f'  {t:25s} : {self.counts[t]:6d}', file=sys.stderr)
        total_repl = sum(self.counts.values())
        print(f'  {"TOTAL":25s} : {total_repl:6d}', file=sys.stderr)

        if self.dict_hits:
            print(f'\nTop 20 mots matches par dictionnaires :', file=sys.stderr)
            top = sorted(self.dict_hits.items(), key=lambda x: -x[1])[:20]
            for mot, count in top:
                in_stop = ' (STOPWORD)' if mot in STOPWORDS_CAP or mot.lower() in STOPWORDS_MIN else ''
                print(f'  {mot:25s} : {count:4d}{in_stop}', file=sys.stderr)

        if scorer:
            print(f'\nScore RGPD moyen : {scorer.score / max(processed, 1):.1f} '
                  f'({scorer.level()})', file=sys.stderr)

        print(f'\nEchantillons (5 premiers par type) :', file=sys.stderr)
        for t in sorted(self.samples.keys()):
            print(f'  [{t}]', file=sys.stderr)
            for orig, repl in self.samples[t]:
                print(f'    {orig} -> {repl}', file=sys.stderr)
        print(f'{"=" * 60}', file=sys.stderr)


# =============================================================
#  NLP OPTIONNEL (spaCy)
# =============================================================

_nlp_model = None


def load_nlp():
    global _nlp_model
    if _nlp_model is not None:
        return _nlp_model
    try:
        import spacy
        _nlp_model = spacy.load('fr_core_news_sm')
        print('  spaCy fr_core_news_sm charge.', file=sys.stderr)
        return _nlp_model
    except (ImportError, OSError) as e:
        print(f'  ATTENTION: spaCy non disponible ({e}). --nlp desactive.', file=sys.stderr)
        return None


def detecter_personnes_nlp(texte):
    """Détecte les entités PER via spaCy."""
    model = load_nlp()
    if model is None:
        return []
    doc = model(texte[:100000])  # Limiter pour la perf
    personnes = []
    for ent in doc.ents:
        if ent.label_ == 'PER':
            name = ent.text.strip()
            if (len(name) >= 3
                    and name[0].isupper()
                    and not any(name == s for s in STOPWORDS_CAP)):
                personnes.append(name)
    return sorted(set(personnes), key=len, reverse=True)


# =============================================================
#  PIPELINE DE PSEUDONYMISATION DU TEXTE LIBRE
# =============================================================

def pseudonymise_texte(text, mode, fort, use_nlp, use_tech, tokens, stats, scorer,
                       whitelist=None, blacklist=None):
    """Pipeline complet de pseudonymisation du texte libre."""
    if not text or not isinstance(text, str):
        return text

    result = text
    wl = set(w.lower() for w in (whitelist or []))
    bl = set(w.lower() for w in (blacklist or []))

    # --- Étape 2 : NLP spaCy (si --nlp) ---
    nlp_personnes = []
    if use_nlp:
        nlp_personnes = detecter_personnes_nlp(result)

    # --- Étape 5b : URLs traitées tôt (avant whitelist pour ne pas casser les URLs) ---
    def _url_replace_early(m):
        if '[' in m.group():
            return m.group()
        tok = tokens.get_typed_token('url_txt', 'URL', m.group())
        stats.add('url_txt', m.group(), tok)
        return tok
    result = RX_URL.sub(_url_replace_early, result)

    # --- Étape 3 : Protection whitelist (ne jamais pseudonymiser) ---
    wl_placeholders = {}
    if wl:
        for i, w_orig in enumerate(sorted(whitelist or [], key=len, reverse=True)):
            ph = f'__WL{i}__'
            pattern = re.compile(r'\b' + re.escape(w_orig) + r'\b', re.IGNORECASE)
            if pattern.search(result):
                wl_placeholders[ph] = w_orig
                result = pattern.sub(ph, result)

    # --- Étape 4 : Blacklist (forcer la pseudonymisation) ---
    if bl:
        for b_orig in sorted(blacklist or [], key=len, reverse=True):
            pattern = re.compile(r'\b' + re.escape(b_orig) + r'\b', re.IGNORECASE)
            for m in pattern.finditer(result):
                tok = tokens.get_token(m.group())
                scorer.add('direct')
                stats.add('blacklist', m.group(), tok)
            result = pattern.sub(lambda m: tokens.get_token(m.group()), result)

    # --- PHASE 1 : Finance & régalien ---
    # 5. Numéro fiscal
    result = _apply_with_ctx(result, RX_NUM_FISCAL, 'fiscal_txt', 'ID_FISCAL', 'finance',
                             tokens, stats, scorer,
                             validator=lambda m: m.group()[0] in '0123')

    # 6. NIR
    result = _apply_validated(result, RX_NIR, 'nir_txt', 'NIR', 'finance',
                              tokens, stats, scorer, nir_check)

    # 7. IBAN
    result = _apply_simple(result, RX_IBAN, 'iban_txt', 'IBAN', 'finance', tokens, stats, scorer)

    # 8. CB + Luhn
    result = _apply_validated(result, RX_CB, 'cb_txt', 'CB', 'finance',
                              tokens, stats, scorer, luhn_check)

    # 9. CVV
    result = _apply_simple(result, RX_CVV, 'cvv_txt', 'CVV', 'finance', tokens, stats, scorer)

    # 10. SIRET/SIREN
    def _siret_replace(m):
        clean = re.sub(r'\D', '', m.group())
        if len(clean) not in (9, 14):
            return m.group()
        if not luhn_raw(clean):
            return m.group()
        scorer.add('finance')
        type_key = 'siret_txt' if len(clean) == 14 else 'siren_txt'
        prefix = 'SIRET' if len(clean) == 14 else 'SIREN'
        tok = tokens.get_typed_token(type_key, prefix, m.group())
        stats.add(type_key, m.group(), tok)
        return tok
    result = RX_SIRET.sub(lambda m: m.group() if '[' in m.group() else _siret_replace(m), result)

    # --- PHASE 2 : Communication ---
    # 11. Mailto
    result = _apply_simple(result, RX_MAILTO, 'email_txt', 'EMAIL', 'direct', tokens, stats, scorer)
    # 12. Emails obfusqués
    result = _apply_simple(result, RX_EMAIL_OBFUSCATED, 'email_txt', 'EMAIL', 'direct', tokens, stats, scorer)
    # 13. Emails standards
    result = _apply_simple(result, RX_EMAIL, 'email_txt', 'EMAIL', 'direct', tokens, stats, scorer)

    # --- PHASE 3 : Infrastructure technique (si --tech) ---
    if use_tech:
        result = _apply_simple(result, RX_JWT, 'jwt_txt', 'JWT_TOKEN', 'tech', tokens, stats, scorer)
        result = _apply_simple(result, RX_API_KEY, 'apikey_txt', 'API_KEY', 'tech', tokens, stats, scorer)
        result = _apply_simple(result, RX_IPV6, 'ipv6_txt', 'IPV6', 'tech', tokens, stats, scorer)
        result = _apply_simple(result, RX_MAC, 'mac_txt', 'MAC_ADDR', 'tech', tokens, stats, scorer)
        result = _apply_simple(result, RX_IPV4, 'ipv4_txt', 'IPV4', 'tech', tokens, stats, scorer)
        result = _apply_simple(result, RX_GPS, 'gps_txt', 'GPS', 'tech', tokens, stats, scorer)
        result = _apply_simple(result, RX_PLAQUE, 'plaque_txt', 'PLAQUE_IMMAT', 'tech', tokens, stats, scorer)

    # --- PHASE 4 : Téléphones ---
    # 21. Tel fuzzy
    result = _apply_simple(result, RX_TEL_FUZZY, 'tel_txt', 'TEL', 'direct', tokens, stats, scorer)
    # 22. Tel préfixe
    result = _apply_simple(result, RX_TEL_PREFIXE, 'tel_txt', 'TEL', 'direct', tokens, stats, scorer)

    # --- PHASE 5 : URLs (déjà traitées en amont, étape 5b) ---

    # --- PHASE 6 : Organisations & villes ---
    # 24. Organisations agressif
    result = _apply_simple(result, RX_ORGA_AGRESSIF, 'orga_txt', 'ORGANISATION', 'indirect', tokens, stats, scorer)

    # 25. Mots-clés organisations
    def _orga_mots_replace(m):
        if '[' in m.group():
            return m.group()
        if not m.group()[0].isupper():
            return m.group()
        if m.group() in ('Sa', 'Son', 'Un', 'Une'):
            return m.group()
        scorer.add('indirect')
        tok = tokens.get_typed_token('orga_txt', 'ORGANISATION', m.group())
        stats.add('orga_txt', m.group(), tok)
        return tok
    result = re.sub(
        r'\b(' + '|'.join(re.escape(w) for w in sorted(MOTS_ORGANISATIONS, key=len, reverse=True)) + r')\b',
        _orga_mots_replace, result, flags=re.IGNORECASE)

    # 26. Villes
    villes_pattern = r'\b(' + '|'.join(re.escape(v) for v in sorted(VILLES_FRANCE, key=len, reverse=True)) + r')\b'
    def _ville_replace(m):
        if '[' in m.group():
            return m.group()
        tok = tokens.get_typed_token('ville_txt', 'VILLE', m.group())
        scorer.add('indirect')
        stats.add('ville_txt', m.group(), tok)
        return tok
    result = re.sub(villes_pattern, _ville_replace, result, flags=re.IGNORECASE)

    # --- PHASE 7 : Contexte & entités ---
    # 27. Dates de naissance (si fort)
    if fort:
        def _date_naiss_replace(m):
            scorer.add('indirect')
            tok = tokens.get_typed_token('date_naiss_txt', 'DATE_NAISSANCE', m.group(2))
            stats.add('date_naiss_txt', m.group(), f'{m.group(1)} {tok}')
            return f'{m.group(1)} {tok}'
        result = RX_DATE_NAISS.sub(lambda m: m.group() if '[' in m.group() else _date_naiss_replace(m), result)

    # 28. Adresses numérotées
    result = _apply_simple(result, RX_VOIE_NUM, 'voie_txt', 'VOIE', 'indirect', tokens, stats, scorer)

    # 29-31. Mode fort : adresses sans numéro, CP, villes après CP
    if fort:
        def _voie_sans_replace(m):
            scorer.add('indirect')
            tok = tokens.get_typed_token('voie_txt', 'VOIE', m.group())
            stats.add('voie_txt', m.group(), tok)
            return tok
        result = RX_VOIE_SANS.sub(lambda m: m.group() if '[' in m.group() else _voie_sans_replace(m), result)
        def _cp_replace(m):
            if '[' in m.group():
                return m.group()
            tok = tokens.get_typed_token('cp_txt', 'CP', m.group())
            stats.add('cp_txt', m.group(), tok)
            return tok
        result = RX_CP.sub(_cp_replace, result)

    # 32. Salutations + nom (groupe 1 = le nom, le mot salutation est dans group(0) mais pas capturé)
    def _salutation_replace(m):
        name = m.group(1)
        if not name or name.split()[0] in STOPWORDS_CAP:
            return m.group()
        scorer.add('direct')
        tok = tokens.get_token(name)
        # Reconstituer : tout le match sauf le nom, puis le jeton
        prefix = m.group()[:m.start(1) - m.start()]
        stats.add('salutation', m.group(), f'{prefix}{tok}')
        return f'{prefix}{tok}'
    result = RX_SALUTATION.sub(lambda m: m.group() if '[' in m.group() else _salutation_replace(m), result)

    # 33. Titres + nom
    def _titre_replace(m):
        scorer.add('direct')
        tok = tokens.get_token(m.group())
        stats.add('titre', m.group(), tok)
        return tok
    result = RX_TITRE.sub(lambda m: m.group() if '[' in m.group() else _titre_replace(m), result)

    # --- NLP : noms détectés par spaCy, validés par dictionnaires ---
    for nom in nlp_personnes:
        if nom not in result:
            continue
        mots = nom.split()
        a_un_prenom = any(est_prenom_connu(w) for w in mots)
        est_multi_maj = len(mots) >= 2 and all(w[0].isupper() for w in mots)
        if a_un_prenom or est_multi_maj:
            pattern = re.compile(r'\b' + re.escape(nom) + r'\b')
            for m_match in pattern.finditer(result):
                if '[' in m_match.group():
                    continue
                if STOPWORDS_CAP and m_match.group().split()[0] in STOPWORDS_CAP:
                    continue
                if est_contexte_institution(result, m_match.group(), m_match.start()):
                    continue
            result = pattern.sub(
                lambda m: m.group() if '[' in m.group() or m.group().split()[0] in STOPWORDS_CAP
                else (tokens.get_token(m.group()) if not est_contexte_institution(result, m.group(), m.start()) else m.group()),
                result)
            scorer.add('direct')
            stats.add('nlp_spacy', nom, tokens.get_token(nom))

    # --- PHASE 8 : Dictionnaires (si fort) ---
    if fort:
        # 34. Prénom + NOM_MAJ
        def _prenom_nom_maj(m):
            if '[' in m.group():
                return m.group()
            words = m.group().split()
            if words[0] in STOPWORDS_CAP:
                return m.group()
            if len(words) == 2 and words[1] in MAJUSCULES_GARDER:
                return m.group()
            if est_contexte_institution(result, m.group(), m.start()):
                return m.group()
            scorer.add('direct')
            tok = tokens.get_token(m.group())
            stats.add('prenom_nom_maj', m.group(), tok)
            stats.add_dict_hit(m.group())
            return tok
        result = RX_PRENOM_NOM_MAJ.sub(_prenom_nom_maj, result)

        # 35. Prénom + Nom classique
        def _prenom_nom(m):
            if '[' in m.group():
                return m.group()
            words = m.group().split()
            if words[0] in STOPWORDS_CAP:
                return m.group()
            last = words[-1]
            if re.match(r'^[A-ZÀ-ÖØ-Ý]{5,}$', last):
                return m.group()  # Ville probable
            if est_contexte_institution(result, m.group(), m.start()):
                return m.group()
            if any(est_prenom_connu(w) for w in words):
                scorer.add('direct')
                tok = tokens.get_token(m.group())
                stats.add('prenom_nom', m.group(), tok)
                stats.add_dict_hit(m.group())
                return tok
            if all(w in STOPWORDS_CAP for w in words):
                return m.group()
            scorer.add('direct')
            tok = tokens.get_token(m.group())
            stats.add('prenom_nom', m.group(), tok)
            stats.add_dict_hit(m.group())
            return tok
        result = RX_PRENOM_NOM.sub(_prenom_nom, result)

        # 36. Prénoms isolés capitalisés
        def _prenom_isole(m):
            mot = m.group(1)
            if mot in STOPWORDS_CAP:
                return m.group()
            if est_contexte_institution(result, mot, m.start()):
                return m.group()
            if est_prenom_connu(mot):
                scorer.add('direct')
                tok = tokens.get_token(mot)
                stats.add('prenom_isole', mot, tok)
                stats.add_dict_hit(mot)
                return tok
            return m.group()
        result = RX_PRENOM_ISOLE.sub(_prenom_isole, result)

        # 37. Prénoms isolés minuscules
        def _prenom_isole_min(m):
            mot = m.group(1)
            if mot in STOPWORDS_MIN or mot.lower() in STOPWORDS_MIN:
                return m.group()
            # Mots courants qui sont aussi des prénoms INSEE
            FAUX_PRENOMS_MIN = {'fils', 'fille', 'pierre', 'grace', 'rose',
                                'victor', 'olive', 'iris', 'jade', 'noel',
                                'pascal', 'dominique', 'claude', 'marine',
                                'florence', 'orange', 'marguerite', 'violette'}
            if mot.lower() in FAUX_PRENOMS_MIN:
                return m.group()
            if est_prenom_connu(mot):
                scorer.add('direct')
                tok = tokens.get_token(mot)
                stats.add('prenom_isole_min', mot, tok)
                return tok
            return m.group()
        result = RX_PRENOM_ISOLE_MIN.sub(_prenom_isole_min, result)

        # 38. Patronymes à préfixe
        def _prefixes(m):
            if '[' in m.group():
                return m.group()
            if est_contexte_institution(result, m.group(), m.start()):
                return m.group()
            if m.group() in STOPWORDS_CAP:
                return m.group()
            scorer.add('direct')
            tok = tokens.get_token(m.group())
            stats.add('patronyme_prefixe', m.group(), tok)
            return tok
        result = RX_PREFIXES.sub(_prefixes, result)

        # 39. Mots en MAJUSCULES
        def _maj_long(m):
            mot = m.group()
            if '[' in mot or '_' in mot or ']' in mot:
                return mot
            # Protéger les mots qui sont des tags de remplacement
            if mot in ('TEL', 'EMAIL', 'IBAN', 'NIR', 'CB', 'CVV', 'URL',
                       'VOIE', 'VILLE', 'ORGANISATION', 'GPS', 'SIRET', 'SIREN',
                       'PERSONNE', 'PRENOM', 'NOM', 'CP', 'GENRE', 'ID',
                       'IPV4', 'IPV6', 'JWT', 'API', 'MAC', 'ADDR', 'PLAQUE',
                       'IMMAT', 'FISCAL', 'DATE', 'NAISSANCE', 'TOKEN', 'KEY',
                       'SUPPRIMÉ', 'SUPPRIME'):
                return mot
            if mot in MAJUSCULES_GARDER or mot in STOPWORDS_CAP:
                return mot
            if mot.lower() in CONTEXTE_INSTITUTION:
                return mot
            # Heuristique tableur (étape 40)
            pos = m.start()
            prev_char = result[pos - 1] if pos > 0 else '\n'
            next_char = result[pos + len(mot)] if pos + len(mot) < len(result) else '\n'
            if prev_char in '\t\n\r' and next_char in '\t\n\r':
                return mot  # En-tête de colonne probable
            if est_patronyme_connu(mot):
                scorer.add('direct')
                tok = tokens.get_token(mot)
                stats.add('maj_patronyme', mot, tok)
                stats.add_dict_hit(mot)
                return tok
            if len(mot) < 5:
                return mot
            scorer.add('direct')
            tok = tokens.get_token(mot)
            stats.add('maj_long', mot, tok)
            stats.add_dict_hit(mot)
            return tok
        result = RX_MAJ_LONG.sub(_maj_long, result)

    # --- PHASE 9 : Propagation (si fort) ---
    if fort:
        for _ in range(3):
            changed = False
            def _propag_apres(m):
                nonlocal changed
                token, mot = m.group(1), m.group(2)
                if mot in STOPWORDS_CAP or mot.lower() in CONTEXTE_INSTITUTION or mot in MAJUSCULES_GARDER:
                    return m.group()
                changed = True
                return token

            def _propag_avant(m):
                nonlocal changed
                mot, token = m.group(1), m.group(2)
                if mot in STOPWORDS_CAP or mot.lower() in CONTEXTE_INSTITUTION or mot in MAJUSCULES_GARDER:
                    return m.group()
                changed = True
                return token

            result = re.sub(r'(\[PERSONNE_\d+\])[\s\t]+([A-ZÀ-ÖØ-Ý]{2,})\b', _propag_apres, result)
            result = re.sub(r'\b([A-ZÀ-ÖØ-Ý]{2,})[\s\t]+(\[PERSONNE_\d+\])', _propag_avant, result)
            if not changed:
                break

    # --- PHASE 10 : Nettoyage ---
    # 42. Espacement
    result = RX_COLLER_TOKEN.sub(r'\1 [PERSONNE_\2]', result)
    result = RX_COLLER_TOKEN2.sub(r'[PERSONNE_\1] \2', result)

    # 43. Restauration whitelist
    for ph, original in wl_placeholders.items():
        result = result.replace(ph, original)

    return result


def _apply_simple(text, regex, type_key, prefix, risk_type, tokens, stats, scorer):
    """Applique une regex avec remplacement par jeton numéroté."""
    def _replace(m):
        if '[' in m.group():
            return m.group()
        scorer.add(risk_type)
        tok = tokens.get_typed_token(type_key, prefix, m.group())
        stats.add(type_key, m.group(), tok)
        return tok
    return regex.sub(_replace, text)


def _apply_validated(text, regex, type_key, prefix, risk_type, tokens, stats, scorer, validator):
    """Applique une regex avec validation et jeton numéroté."""
    def _replace(m):
        if '[' in m.group():
            return m.group()
        if not validator(m.group()):
            return m.group()
        scorer.add(risk_type)
        tok = tokens.get_typed_token(type_key, prefix, m.group())
        stats.add(type_key, m.group(), tok)
        return tok
    return regex.sub(_replace, text)


def _apply_with_ctx(text, regex, type_key, prefix, risk_type, tokens, stats, scorer, validator=None):
    """Applique une regex avec vérification de contexte numérique et jeton numéroté."""
    def _replace(m):
        if '[' in m.group():
            return m.group()
        if validator and not validator(m):
            return m.group()
        if contexte_nb_negatif(text, m.start(), len(m.group())):
            return m.group()
        scorer.add(risk_type)
        tok = tokens.get_typed_token(type_key, prefix, m.group())
        stats.add(type_key, m.group(), tok)
        return tok
    return regex.sub(_replace, text)


# =============================================================
#  NAVIGATION JSON (notation pointée + unwrap + arrays)
# =============================================================

def _get_path(obj, path):
    """Lit une valeur via notation pointée. Retourne None si introuvable."""
    parts = path.split('.')
    current = obj
    for part in parts:
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _set_path(obj, path, value):
    """Écrit une valeur via notation pointée. Crée les clés intermédiaires."""
    parts = path.split('.')
    current = obj
    for part in parts[:-1]:
        if part not in current:
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value


def _get_text_fields(obj, path):
    """Retourne une liste de (conteneur, clé, valeur) pour un chemin, y compris les arrays.
    Supporte la notation Details[].Value."""
    if '[]' in path:
        # Split sur le premier []
        before, after = path.split('[]', 1)
        after = after.lstrip('.')
        array = _get_path(obj, before)
        if not array or not isinstance(array, list):
            return []
        results = []
        for item in array:
            if after:
                val = _get_path(item, after)
                if val and isinstance(val, str):
                    # Retourner le conteneur parent et la clé finale
                    after_parts = after.split('.')
                    container = item
                    for p in after_parts[:-1]:
                        container = container.get(p, {})
                    results.append((container, after_parts[-1], val))
            elif isinstance(item, str):
                results.append((None, None, item))
        return results
    else:
        val = _get_path(obj, path)
        if val and isinstance(val, str):
            parts = path.split('.')
            container = obj
            for p in parts[:-1]:
                container = container.get(p, {})
            return [(container, parts[-1], val)]
        return []


# =============================================================
#  TRAITEMENT PRINCIPAL
# =============================================================

def load_mapping(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def process_record(record, mode, fort, use_nlp, use_tech, tokens, stats, scorer, mapping):
    """Traite un enregistrement JSON (plat ou imbriqué)."""
    champs = mapping.get('champs_sensibles', {})
    texte_libre = mapping.get('texte_libre', [])
    lookup = mapping.get('lookup_noms', {})
    whitelist = mapping.get('whitelist', [])
    blacklist = mapping.get('blacklist', [])

    # --- Unwrap JSON stringifié si configuré ---
    structure = mapping.get('structure', {})
    unwrap_config = structure.get('unwrap')
    unwrapped = None
    if unwrap_config:
        field = unwrap_config['field']
        raw = record.get(field, '')
        if raw and isinstance(raw, str):
            unwrapped = json.loads(raw)
            # Fusionner temporairement pour la navigation par chemin
            record['_unwrapped'] = unwrapped
        else:
            record['_unwrapped'] = {}

    # Objet de travail : pour les chemins pointés, on navigue dans record
    # Les chemins commençant par le nom du champ unwrappé naviguent dans l'unwrap
    def _resolve_obj_for_path(path):
        """Retourne l'objet racine approprié pour un chemin donné."""
        if unwrapped and '.' in path:
            first_part = path.split('.')[0]
            # Si le premier segment est une clé de l'objet unwrappé, naviguer dedans
            if isinstance(unwrapped, dict) and first_part in unwrapped:
                return unwrapped
        return record

    # --- Lookup noms ---
    firstname = ''
    lastname = ''
    if lookup:
        fn_path = lookup.get('prenom', '')
        ln_path = lookup.get('nom', '')
        if fn_path:
            obj = _resolve_obj_for_path(fn_path)
            firstname = _get_path(obj, fn_path) or ''
        if ln_path:
            obj = _resolve_obj_for_path(ln_path)
            lastname = _get_path(obj, ln_path) or ''

    # --- Phase 1 : Champs structurés ---
    for field_path, config in champs.items():
        obj = _resolve_obj_for_path(field_path)
        val = _get_path(obj, field_path)
        if val is None or (isinstance(val, str) and not val.strip()):
            continue

        t = config['type']
        prefix = config['jeton']

        if mode == 'pseudo':
            token = tokens.get_typed_token(t, prefix, val)
            stats.add(t, val, token)
            _set_path(obj, field_path, token)
        else:
            anon_values = {
                'prenom': '***', 'nom': '***',
                'email': 'anonyme@example.com',
                'tel': '00 00 00 00 00',
                'cp': '00000', 'genre': 'Non renseigné',
                'id': stats.counts.get('id', 0) + 1,
                'uuid': str(uuid.uuid4()),
            }
            replacement = anon_values.get(t, '***')
            stats.add(t, val, replacement)
            _set_path(obj, field_path, replacement)

    # --- Phase 2 : Texte libre ---
    for field_path in texte_libre:
        obj = _resolve_obj_for_path(field_path)
        text_fields = _get_text_fields(obj, field_path)

        for container, key, val in text_fields:
            text = val

            # Lookup direct noms du déclarant
            if firstname:
                fn = firstname.strip()
                ln = lastname.strip() if lastname else ''
                if len(fn) < 4 and ln:
                    for pat in [
                        re.compile(r'\b' + re.escape(fn) + r'\s+' + re.escape(ln) + r'\b', re.IGNORECASE),
                        re.compile(r'\b' + re.escape(ln) + r'\s+' + re.escape(fn) + r'\b', re.IGNORECASE),
                    ]:
                        if mode == 'pseudo':
                            for m_hit in pat.finditer(text):
                                stats.add('lookup_nom', m_hit.group(), tokens.get_token(m_hit.group()))
                            text = pat.sub(lambda m: tokens.get_token(m.group()), text)
                        else:
                            for m_hit in pat.finditer(text):
                                stats.add('lookup_nom', m_hit.group(), '[SUPPRIMÉ]')
                            text = pat.sub('[SUPPRIMÉ]', text)
                else:
                    for name, label in [(fn, 'lookup_prenom'), (ln, 'lookup_nom')]:
                        if not name:
                            continue
                        pat = re.compile(r'\b' + re.escape(name) + r'\b', re.IGNORECASE)
                        if mode == 'pseudo':
                            for m_hit in pat.finditer(text):
                                stats.add(label, m_hit.group(), tokens.get_token(m_hit.group()))
                            text = pat.sub(lambda m: tokens.get_token(m.group()), text)
                        else:
                            for m_hit in pat.finditer(text):
                                stats.add(label, m_hit.group(), '[SUPPRIMÉ]')
                            text = pat.sub('[SUPPRIMÉ]', text)

            # Pipeline complet
            text = pseudonymise_texte(text, mode, fort, use_nlp, use_tech, tokens, stats, scorer,
                                      whitelist, blacklist)
            if mode == 'anon':
                text = re.sub(r'\[PERSONNE_\d+\]', '[SUPPRIMÉ]', text)

            # Écrire la valeur modifiée
            if container is not None and key is not None:
                container[key] = text

    # --- Re-sérialisation unwrap ---
    if unwrap_config and unwrapped is not None:
        field = unwrap_config['field']
        record.pop('_unwrapped', None)
        record[field] = json.dumps(unwrapped, ensure_ascii=False)

    return record


# =============================================================
#  MAIN
# =============================================================

# =============================================================
#  GÉNÉRATION AUTOMATIQUE DE MAPPING
# =============================================================

def generate_mapping(input_path):
    """Inspecte un JSON et propose un mapping squelette."""
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if not isinstance(data, list) or len(data) == 0:
        print('Erreur : le JSON doit etre un array non vide.', file=sys.stderr)
        sys.exit(1)

    sample = data[:min(10, len(data))]
    champs = {}
    texte_libre = []

    # Analyser les clés du premier niveau
    all_keys = set()
    for rec in sample:
        if isinstance(rec, dict):
            all_keys.update(rec.keys())

    for key in sorted(all_keys):
        values = [rec.get(key) for rec in sample if key in rec]
        values_non_null = [v for v in values if v is not None]
        if not values_non_null:
            continue

        # Deviner le type
        sample_val = values_non_null[0]

        if isinstance(sample_val, str):
            val_upper = str(sample_val).upper().strip()

            # Email ?
            if '@' in str(sample_val) and '.' in str(sample_val):
                champs[key] = {'type': 'email', 'jeton': 'EMAIL', '_raison': 'contient @'}
            # Téléphone ?
            elif re.match(r'^[\d\s\+\.\-]{8,}$', str(sample_val)):
                champs[key] = {'type': 'tel', 'jeton': 'TEL', '_raison': 'format numerique'}
            # Code postal ?
            elif re.match(r'^\d{5}$', str(sample_val)):
                champs[key] = {'type': 'cp', 'jeton': 'CP', '_raison': '5 chiffres'}
            # UUID ?
            elif re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
                          str(sample_val), re.IGNORECASE):
                champs[key] = {'type': 'uuid', 'jeton': 'UUID', '_raison': 'format UUID'}
            # Nom/Prénom ? (vérifier dans les dictionnaires)
            elif val_upper in PRENOMS:
                champs[key] = {'type': 'prenom', 'jeton': 'PRENOM', '_raison': 'dans dictionnaire prenoms'}
            elif val_upper in PATRONYMES:
                champs[key] = {'type': 'nom', 'jeton': 'NOM', '_raison': 'dans dictionnaire patronymes'}
            # Texte long = texte libre ?
            elif len(str(sample_val)) > 50:
                texte_libre.append(key)
            # Genre ?
            elif str(sample_val).lower() in ('male', 'female', 'homme', 'femme', 'm', 'f'):
                champs[key] = {'type': 'genre', 'jeton': 'GENRE', '_raison': 'valeur genre'}
            # Nom de clé suggestif ?
            elif any(k in key.lower() for k in ('nom', 'name', 'last')):
                champs[key] = {'type': 'nom', 'jeton': 'NOM', '_raison': 'nom de champ suggestif'}
            elif any(k in key.lower() for k in ('prenom', 'first', 'given')):
                champs[key] = {'type': 'prenom', 'jeton': 'PRENOM', '_raison': 'nom de champ suggestif'}
            elif any(k in key.lower() for k in ('mail', 'email', 'courriel')):
                champs[key] = {'type': 'email', 'jeton': 'EMAIL', '_raison': 'nom de champ suggestif'}
            elif any(k in key.lower() for k in ('tel', 'phone', 'mobile')):
                champs[key] = {'type': 'tel', 'jeton': 'TEL', '_raison': 'nom de champ suggestif'}
            elif any(k in key.lower() for k in ('comment', 'note', 'description', 'texte', 'question', 'message')):
                texte_libre.append(key)

        elif isinstance(sample_val, (int, float)):
            # ID ?
            if any(k in key.lower() for k in ('id', 'ident', 'numero')):
                champs[key] = {'type': 'id', 'jeton': 'ID', '_raison': 'nom de champ suggestif'}

    # Deviner le lookup noms
    lookup = {}
    for key, config in champs.items():
        if config['type'] == 'prenom':
            lookup['prenom'] = key
        elif config['type'] == 'nom' and 'nom' not in lookup:
            lookup['nom'] = key

    # Construire le mapping
    mapping = {
        'description': f'Mapping genere automatiquement depuis {os.path.basename(input_path)}',
        'champs_sensibles': {},
        'texte_libre': texte_libre,
    }
    if lookup:
        mapping['lookup_noms'] = lookup
    mapping['whitelist'] = []
    mapping['blacklist'] = []

    # Affichage
    print(f'\nChamps detectes ({len(all_keys)} cles) :', file=sys.stderr)
    for key in sorted(all_keys):
        if key in champs:
            c = champs[key]
            print(f'  {key:30s} -> type : {c["type"]:10s} ({c["_raison"]})', file=sys.stderr)
            mapping['champs_sensibles'][key] = {'type': c['type'], 'jeton': c['jeton']}
        elif key in texte_libre:
            print(f'  {key:30s} -> texte_libre', file=sys.stderr)
        else:
            print(f'  {key:30s} -> ignore', file=sys.stderr)

    # Écriture du mapping
    output_name = os.path.splitext(os.path.basename(input_path))[0]
    output_path = f'mapping-{output_name}.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)

    print(f'\nMapping propose ecrit dans : {output_path}', file=sys.stderr)
    print('Verifier et ajuster avant utilisation.', file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description='Pseudonymise ou anonymise un JSON generique.')
    parser.add_argument('input', help='Fichier source (JSON, CSV, XLSX, ODS, DOCX, PDF)')
    parser.add_argument('--mapping', help='Fichier de mapping JSON')

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--pseudo', action='store_true', help='Pseudonymisation reversible')
    group.add_argument('--anon', action='store_true', help='Anonymisation irreversible')
    group.add_argument('--dry-run', action='store_true', help='Test sur 100 enregistrements')
    group.add_argument('--score-only', action='store_true', help='Scoring RGPD sans pseudonymiser')
    group.add_argument('--mapping-generate', action='store_true',
                       help='Inspecte le JSON et propose un mapping')

    parser.add_argument('--fort', action='store_true', help='Mode fort (pipeline complet)')
    parser.add_argument('--nlp', action='store_true', help='Activer spaCy NLP (optionnel)')
    parser.add_argument('--tech', action='store_true', help='Regex techniques (IPv4/v6, MAC, JWT, API keys)')
    parser.add_argument('--input-dir', help='Traite tous les .json d un dossier (remplace input)')
    parser.add_argument('--chunk-size', type=int, default=0,
                       help='Traitement streaming par paquets de N enregistrements (pour fichiers > 2 Go)')

    args = parser.parse_args()

    # --- Mode --mapping-generate ---
    if args.mapping_generate:
        if not os.path.exists(args.input):
            print(f'Erreur : fichier introuvable : {args.input}', file=sys.stderr)
            sys.exit(1)
        generate_mapping(args.input)
        return

    # --- Mode --input-dir ---
    if args.input_dir:
        if not os.path.isdir(args.input_dir):
            print(f'Erreur : dossier introuvable : {args.input_dir}', file=sys.stderr)
            sys.exit(1)
        json_files = sorted(f for f in os.listdir(args.input_dir)
                           if f.endswith('.json') and not f.endswith('_PSEUDO.json')
                           and not f.endswith('_ANON.json'))
        if not json_files:
            print(f'Aucun fichier .json dans {args.input_dir}', file=sys.stderr)
            sys.exit(1)
        print(f'{len(json_files)} fichiers JSON a traiter.', file=sys.stderr)
        for jf in json_files:
            full_path = os.path.join(args.input_dir, jf)
            print(f'\n{"=" * 60}', file=sys.stderr)
            print(f'Traitement de {jf}...', file=sys.stderr)
            # Relancer main avec le fichier individuel
            original_input = args.input
            args.input = full_path
            _process_single(args)
            args.input = original_input
        return

    # --- Mode standard ---
    if not args.mapping:
        print('Erreur : --mapping requis (sauf en mode --mapping-generate)', file=sys.stderr)
        sys.exit(1)

    _process_single(args)


def _process_single(args):
    """Traite un seul fichier JSON."""
    mode = 'pseudo' if (args.pseudo or args.dry_run or args.score_only) else 'anon'
    chunk_size = getattr(args, 'chunk_size', 0)

    if not os.path.exists(args.input):
        print(f'Erreur : fichier introuvable : {args.input}', file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(args.mapping):
        print(f'Erreur : mapping introuvable : {args.mapping}', file=sys.stderr)
        sys.exit(1)

    mapping = load_mapping(args.mapping)
    print(f'Mapping : {mapping.get("description", "sans description")}', file=sys.stderr)

    if args.nlp:
        load_nlp()

    # --- Mode streaming (--chunk-size) ---
    if chunk_size > 0:
        _process_streaming(args, mode, mapping, chunk_size)
        return

    # --- Mode standard (tout en mémoire) ---
    # Détection du format
    # Import du module formats (même dossier)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    from formats import detect_format, load_file, save_file
    ext = detect_format(args.input)

    print(f'Chargement de {args.input} (format: {ext})...', file=sys.stderr)
    if ext == '.json':
        with open(args.input, 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        data = load_file(args.input, mapping)
        # Pour DOCX/PDF avec texte_libre=["*"], mapper "texte" comme texte libre
        if ext in ('.docx', '.odt', '.pdf') and mapping.get('texte_libre') == ['*']:
            mapping = {**mapping, 'texte_libre': ['texte']}

    total = len(data)
    print(f'{total} enregistrements charges.', file=sys.stderr)

    if args.dry_run:
        data = data[:100]
        print(f'Mode dry-run : traitement des 100 premiers.', file=sys.stderr)

    tokens = TokenTable()
    stats = Stats()
    scorer = RiskScorer()
    output = []

    for i, record in enumerate(data):
        try:
            scorer_rec = RiskScorer()
            processed = process_record(record, mode, args.fort, args.nlp,
                                       getattr(args, 'tech', False),
                                       tokens, stats, scorer_rec, mapping)
            scorer.score += scorer_rec.score
            for k, v in scorer_rec.details.items():
                scorer.details[k] = scorer.details.get(k, 0) + v
            output.append(processed)
        except Exception as e:
            stats.errors += 1
            print(f'ERREUR [{i}] : {e}', file=sys.stderr)
            continue

        if (i + 1) % 1000 == 0:
            print(f'  [{i + 1}/{len(data)}]', file=sys.stderr)

    stats.report(total, len(output), scorer)

    if args.dry_run or args.score_only:
        print('\nAucun fichier ecrit.', file=sys.stderr)
        return

    suffix = '_PSEUDO' if args.pseudo else '_ANON'
    base_dir = os.path.dirname(args.input)

    print(f'\nEcriture...', file=sys.stderr)
    output_path = save_file(output, args.input, suffix, mapping)
    print(f'Fichier ecrit : {output_path} ({len(output)} enregistrements)', file=sys.stderr)

    if args.pseudo:
        csv_path = os.path.join(CONFIDENTIEL_DIR, 'correspondances.csv')
        os.makedirs(CONFIDENTIEL_DIR, exist_ok=True)
        tokens.export_csv(csv_path)
        print(f'Correspondances : {csv_path}', file=sys.stderr)

        gitignore_path = os.path.join(CONFIDENTIEL_DIR, '.gitignore')
        if not os.path.exists(gitignore_path):
            with open(gitignore_path, 'w') as f:
                f.write('# Ne jamais commiter les correspondances\n*\n')


def _process_streaming(args, mode, mapping, chunk_size):
    """Traitement streaming par paquets — ne charge jamais tout en mémoire."""
    try:
        import ijson
    except ImportError:
        print('Erreur : --chunk-size necessite ijson. Installer avec :', file=sys.stderr)
        print('  pip3 install ijson', file=sys.stderr)
        sys.exit(1)

    base_dir = os.path.dirname(args.input)
    base_name = os.path.splitext(os.path.basename(args.input))[0]
    suffix = '_PSEUDO' if args.pseudo else '_ANON'
    output_path = os.path.join(base_dir, f'{base_name}{suffix}.json')

    tokens = TokenTable()
    stats = Stats()
    scorer = RiskScorer()
    total_processed = 0

    print(f'Mode streaming : paquets de {chunk_size} enregistrements.', file=sys.stderr)
    print(f'Lecture de {args.input}...', file=sys.stderr)

    # Ouvrir le fichier de sortie en écriture incrémentale
    with open(output_path, 'w', encoding='utf-8') as out_f:
        out_f.write('[')
        first = True

        # Parser le JSON en streaming avec ijson
        with open(args.input, 'rb') as in_f:
            for record in ijson.items(in_f, 'item'):
                try:
                    scorer_rec = RiskScorer()
                    processed = process_record(record, mode, args.fort, args.nlp,
                                               getattr(args, 'tech', False),
                                               tokens, stats, scorer_rec, mapping)
                    scorer.score += scorer_rec.score
                    for k, v in scorer_rec.details.items():
                        scorer.details[k] = scorer.details.get(k, 0) + v

                    # Écrire l'enregistrement
                    if not first:
                        out_f.write(',')
                    out_f.write(json.dumps(processed, ensure_ascii=False))
                    first = False
                    total_processed += 1

                except Exception as e:
                    stats.errors += 1
                    print(f'ERREUR [{total_processed}] : {e}', file=sys.stderr)
                    continue

                if total_processed % 1000 == 0:
                    print(f'  [{total_processed}]', file=sys.stderr)

        out_f.write(']')

    stats.report(total_processed, total_processed, scorer)
    print(f'\nFichier ecrit : {output_path} ({total_processed} enregistrements)', file=sys.stderr)

    if args.pseudo:
        csv_path = os.path.join(CONFIDENTIEL_DIR, 'correspondances.csv')
        os.makedirs(CONFIDENTIEL_DIR, exist_ok=True)
        tokens.export_csv(csv_path)
        print(f'Correspondances : {csv_path}', file=sys.stderr)

        gitignore_path = os.path.join(CONFIDENTIEL_DIR, '.gitignore')
        if not os.path.exists(gitignore_path):
            with open(gitignore_path, 'w') as f:
                f.write('# Ne jamais commiter les correspondances\n*\n')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
Serveur web local pour la pseudonymisation générique.
Sert l'interface DSFR et expose l'API de pseudonymisation.

Usage :
    python3 serveur.py
    python3 serveur.py --port 8090
"""

import argparse
import io
import json
import os
import re
import sys
import tempfile
import traceback
from http.server import HTTPServer, SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

# Ajouter le dossier courant au path pour les imports
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

# Import du moteur de pseudonymisation (charge les dictionnaires au démarrage)
import pseudonymise as engine
from formats import detect_format, load_file, save_file


INTERFACE_DIR = os.path.join(SCRIPT_DIR, 'interface')


class APIHandler(SimpleHTTPRequestHandler):
    """Gestionnaire HTTP : sert les fichiers statiques + routes API."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=INTERFACE_DIR, **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == '/api/mapping/generate':
            self._handle_mapping_generate(parsed)
        elif path == '/api/stats':
            self._handle_stats()
        elif path == '/api/health':
            self._json_response({'status': 'ok', 'dictionnaires': {
                'patronymes': len(engine.PATRONYMES),
                'prenoms': len(engine.PRENOMS),
            }})
        elif path == '/api/download':
            self._handle_download(parsed)
        else:
            # Fichiers statiques — redirige / vers index.html
            if path == '/':
                self.path = '/index.html'
            super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == '/api/pseudonymise':
            self._handle_pseudonymise()
        elif path == '/api/depseudonymise':
            self._handle_depseudonymise()
        elif path == '/api/score':
            self._handle_score()
        elif path == '/api/pseudonymise-texte':
            self._handle_pseudonymise_texte()
        elif path == '/api/pseudonymise-local':
            self._handle_pseudonymise_local()
        elif path == '/api/mapping/generate':
            self._handle_mapping_generate_post()
        elif path == '/api/pseudonymise-batch':
            self._handle_pseudonymise_batch()
        else:
            self._json_error(404, 'Route non trouvee')

    # ----- API : pseudonymiser du texte brut -----

    def _handle_pseudonymise_texte(self):
        try:
            body = self._read_json_body()
            texte = body.get('texte', '')
            mode = body.get('mode', 'pseudo')
            fort = body.get('fort', False)
            use_nlp = body.get('nlp', False)
            use_tech = body.get('tech', False)
            whitelist = set(body.get('whitelist', []))
            blacklist = set(body.get('blacklist', []))

            tokens = engine.TokenTable()
            stats = engine.Stats()
            scorer = engine.RiskScorer()

            result = engine.pseudonymise_texte(
                texte, mode, fort, use_nlp, use_tech,
                tokens, stats, scorer,
                whitelist=whitelist, blacklist=blacklist
            )

            # Construire la table de correspondances
            correspondances = self._tokens_to_list(tokens)

            self._json_response({
                'texte_original': texte,
                'texte_pseudonymise': result,
                'correspondances': correspondances,
                'stats': self._stats_to_dict(stats),
                'score': {
                    'total': scorer.score,
                    'niveau': scorer.level(),
                    'details': scorer.details,
                },
            })
        except Exception as e:
            self._json_error(500, str(e))

    # ----- API : pseudonymiser un fichier (JSON, CSV, etc.) -----

    def _handle_pseudonymise(self):
        try:
            content_type = self.headers.get('Content-Type', '')

            if 'multipart/form-data' in content_type:
                file_data, params = self._read_multipart()
            else:
                body = self._read_json_body()
                file_data = None
                params = body

            mapping = json.loads(params.get('mapping', '{}'))
            mode = params.get('mode', 'pseudo')
            fort = params.get('fort', False)
            if isinstance(fort, str):
                fort = fort.lower() in ('true', '1', 'oui')
            use_nlp = params.get('nlp', False)
            if isinstance(use_nlp, str):
                use_nlp = use_nlp.lower() in ('true', '1', 'oui')
            use_tech = params.get('tech', False)
            if isinstance(use_tech, str):
                use_tech = use_tech.lower() in ('true', '1', 'oui')
            dry_run = params.get('dry_run', False)
            if isinstance(dry_run, str):
                dry_run = dry_run.lower() in ('true', '1', 'oui')

            # Charger les données
            if file_data:
                filename = params.get('filename', 'upload.json')
                ext = os.path.splitext(filename)[1].lower()
                tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
                tmp.write(file_data)
                tmp.close()
                try:
                    if ext == '.json':
                        with open(tmp.name, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                    else:
                        data = load_file(tmp.name, mapping)
                        if ext in ('.docx', '.odt', '.pdf') and mapping.get('texte_libre') == ['*']:
                            mapping = {**mapping, 'texte_libre': ['texte']}
                finally:
                    os.unlink(tmp.name)
            elif 'data' in params:
                data = params['data']
            else:
                self._json_error(400, 'Aucune donnee fournie')
                return

            # Dry-run : limiter a 100 enregistrements
            if dry_run and isinstance(data, list):
                data = data[:100]

            # Traitement
            tokens = engine.TokenTable()
            stats = engine.Stats()
            scorer = engine.RiskScorer()
            whitelist = set(mapping.get('whitelist', []))
            blacklist = set(mapping.get('blacklist', []))
            output = []

            for record in data:
                try:
                    processed = engine.process_record(
                        record, mode, fort, use_nlp, use_tech,
                        tokens, stats, scorer, mapping
                    )
                    output.append(processed)
                except Exception:
                    stats.errors += 1
                    output.append(record)

            correspondances = self._tokens_to_list(tokens)

            response = {
                'data': output,
                'correspondances': correspondances,
                'stats': self._stats_to_dict(stats),
                'score': {
                    'total': scorer.score,
                    'niveau': scorer.level(),
                    'details': scorer.details,
                },
                'total': len(data),
                'traites': len(output) - stats.errors,
                'erreurs': stats.errors,
            }
            if dry_run:
                response['dry_run'] = True
            self._json_response(response)
        except Exception as e:
            traceback.print_exc()
            self._json_error(500, str(e))

    # ----- API : pseudonymiser un fichier local (gros fichiers) -----

    def _handle_pseudonymise_local(self):
        """Traite un fichier directement sur disque — zero transfert HTTP."""
        try:
            body = self._read_json_body()
            file_path = body.get('path', '')
            mapping_path = body.get('mapping_path', '')
            mapping = body.get('mapping', {})
            mode = body.get('mode', 'pseudo')
            fort = body.get('fort', False)
            use_nlp = body.get('nlp', False)
            use_tech = body.get('tech', False)
            dry_run = body.get('dry_run', False)

            if not file_path:
                self._json_error(400, 'Chemin de fichier requis (champ "path")')
                return

            if not os.path.isfile(file_path):
                self._json_error(404, f'Fichier introuvable : {file_path}')
                return

            # Charger le mapping depuis un chemin si fourni
            if mapping_path:
                if not os.path.isfile(mapping_path):
                    self._json_error(404, f'Mapping introuvable : {mapping_path}')
                    return
                with open(mapping_path, 'r', encoding='utf-8') as f:
                    mapping = json.load(f)

            ext = os.path.splitext(file_path)[1].lower()

            print(f'[serveur] Traitement local : {file_path}', file=sys.stderr)

            # Charger le fichier
            if ext == '.json':
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = load_file(file_path, mapping)
                if ext in ('.docx', '.odt', '.pdf') and mapping.get('texte_libre') == ['*']:
                    mapping = {**mapping, 'texte_libre': ['texte']}

            total = len(data)
            if dry_run:
                data = data[:100]
                import copy
                apercu_avant = copy.deepcopy(data[:5])
            print(f'[serveur] {total} enregistrements charges{" (dry-run: 100 max)" if dry_run else ""}.', file=sys.stderr)

            # Traitement
            tokens = engine.TokenTable()
            stats = engine.Stats()
            scorer = engine.RiskScorer()
            output = []

            for i, record in enumerate(data):
                try:
                    processed = engine.process_record(
                        record, mode, fort, use_nlp, use_tech,
                        tokens, stats, scorer, mapping
                    )
                    output.append(processed)
                except Exception:
                    stats.errors += 1
                    output.append(record)
                if (i + 1) % 1000 == 0:
                    print(f'[serveur] [{i + 1}/{total}]', file=sys.stderr)

            correspondances = self._tokens_to_list(tokens)

            print(f'[serveur] Termine : {len(output)} enregistrements, '
                  f'{sum(stats.counts.values())} remplacements.', file=sys.stderr)

            if dry_run:
                # Dry-run : pas d'ecriture, retour du rapport + apercu avant/apres
                self._json_response({
                    'dry_run': True,
                    'output_path': None,
                    'csv_path': None,
                    'zip_path': None,
                    'correspondances': correspondances,
                    'apercu_avant': apercu_avant,
                    'apercu_apres': output[:5],
                    'apercu_champs': self._build_apercu_champs(apercu_avant, output[:5], mapping),
                    'stats': self._stats_to_dict(stats),
                    'score': {
                        'total': scorer.score,
                        'niveau': scorer.level(),
                        'details': scorer.details,
                    },
                    'total': total,
                    'traites': len(output) - stats.errors,
                    'erreurs': stats.errors,
                })
                return

            # Ecriture sur disque
            suffix = '_PSEUDO' if mode == 'pseudo' else '_ANON'
            base_dir = os.path.dirname(file_path)

            output_path = save_file(output, file_path, suffix, mapping)

            # Correspondances
            csv_path = None
            if mode == 'pseudo':
                csv_dir = os.path.join(SCRIPT_DIR, 'confidentiel')
                os.makedirs(csv_dir, exist_ok=True)
                csv_path = os.path.join(csv_dir, 'correspondances.csv')
                tokens.export_csv(csv_path)

            # Creer un zip avec le resultat + correspondances
            zip_path = None
            if output_path:
                import zipfile
                zip_name = os.path.splitext(os.path.basename(output_path))[0] + '.zip'
                zip_path = os.path.join(base_dir, zip_name)
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                    zf.write(output_path, os.path.basename(output_path))
                    if csv_path and os.path.exists(csv_path):
                        zf.write(csv_path, f'confidentiel/{os.path.basename(csv_path)}')
                print(f'[serveur] Zip cree : {zip_path}', file=sys.stderr)

            self._json_response({
                'output_path': output_path,
                'csv_path': csv_path,
                'zip_path': zip_path,
                'correspondances': correspondances,
                'stats': self._stats_to_dict(stats),
                'score': {
                    'total': scorer.score,
                    'niveau': scorer.level(),
                    'details': scorer.details,
                },
                'total': total,
                'traites': len(output) - stats.errors,
                'erreurs': stats.errors,
            })
        except Exception as e:
            traceback.print_exc()
            self._json_error(500, str(e))

    # ----- API : traitement batch (dossier) -----

    SUPPORTED_EXT = {'.json', '.csv', '.tsv', '.xlsx', '.xls', '.ods', '.docx', '.odt', '.pdf'}

    def _handle_pseudonymise_batch(self):
        """Traite tous les fichiers supportes d'un dossier."""
        try:
            body = self._read_json_body()
            dir_path = body.get('path', '')
            mapping = body.get('mapping', {})
            mapping_path = body.get('mapping_path', '')
            mode = body.get('mode', 'pseudo')
            fort = body.get('fort', False)
            use_nlp = body.get('nlp', False)
            use_tech = body.get('tech', False)
            dry_run = body.get('dry_run', False)

            if not dir_path:
                self._json_error(400, 'Chemin de dossier requis (champ "path")')
                return

            if not os.path.isdir(dir_path):
                self._json_error(404, f'Dossier introuvable : {dir_path}')
                return

            # Charger le mapping
            if mapping_path:
                if not os.path.isfile(mapping_path):
                    self._json_error(404, f'Mapping introuvable : {mapping_path}')
                    return
                with open(mapping_path, 'r', encoding='utf-8') as f:
                    mapping = json.load(f)

            # Lister les fichiers supportes
            fichiers = sorted(
                f for f in os.listdir(dir_path)
                if os.path.isfile(os.path.join(dir_path, f))
                and os.path.splitext(f)[1].lower() in self.SUPPORTED_EXT
                and '_PSEUDO' not in f
                and '_ANON' not in f
            )

            if not fichiers:
                self._json_error(400, f'Aucun fichier traitable dans {dir_path}')
                return

            print(f'[serveur] Batch : {len(fichiers)} fichiers dans {dir_path}', file=sys.stderr)

            # Dry-run batch : traiter uniquement le premier fichier (100 enregistrements)
            if dry_run:
                fichiers_a_traiter = fichiers[:1]
            else:
                fichiers_a_traiter = fichiers

            resultats = []
            total_enregistrements = 0
            total_remplacements = 0
            fichiers_en_erreur = 0

            for nom_fichier in fichiers_a_traiter:
                file_path = os.path.join(dir_path, nom_fichier)
                print(f'[serveur] Batch : traitement de {nom_fichier}...', file=sys.stderr)

                try:
                    ext = os.path.splitext(nom_fichier)[1].lower()
                    if ext == '.json':
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                    else:
                        data = load_file(file_path, mapping)
                        if ext in ('.docx', '.odt', '.pdf') and mapping.get('texte_libre') == ['*']:
                            mapping = {**mapping, 'texte_libre': ['texte']}

                    if dry_run:
                        data = data[:100]

                    tokens = engine.TokenTable()
                    stats = engine.Stats()
                    scorer = engine.RiskScorer()
                    output = []

                    for record in data:
                        try:
                            processed = engine.process_record(
                                record, mode, fort, use_nlp, use_tech,
                                tokens, stats, scorer, mapping
                            )
                            output.append(processed)
                        except Exception:
                            stats.errors += 1
                            output.append(record)

                    remplacements = sum(stats.counts.values())
                    total_enregistrements += len(data)
                    total_remplacements += remplacements

                    resultat = {
                        'nom': nom_fichier,
                        'statut': 'ok',
                        'total': len(data),
                        'remplacements': remplacements,
                        'score': scorer.score,
                    }

                    if dry_run:
                        # Dry-run : retourner les correspondances du premier fichier
                        resultat['correspondances'] = self._tokens_to_list(tokens)
                    else:
                        # Ecriture sur disque
                        output_path = save_file(output, file_path, '_PSEUDO' if mode == 'pseudo' else '_ANON', mapping)
                        resultat['output_path'] = output_path

                        # Correspondances par fichier
                        csv_path = None
                        if mode == 'pseudo':
                            csv_dir = os.path.join(SCRIPT_DIR, 'confidentiel')
                            os.makedirs(csv_dir, exist_ok=True)
                            base_name = os.path.splitext(nom_fichier)[0]
                            csv_path = os.path.join(csv_dir, f'correspondances_{base_name}.csv')
                            tokens.export_csv(csv_path)
                        resultat['csv_path'] = csv_path

                    resultats.append(resultat)

                except Exception as e:
                    fichiers_en_erreur += 1
                    resultats.append({
                        'nom': nom_fichier,
                        'statut': 'erreur',
                        'erreur': str(e),
                    })
                    print(f'[serveur] Batch : erreur sur {nom_fichier} : {e}', file=sys.stderr)

            response = {
                'fichiers': resultats,
                'fichiers_detectes': fichiers,
                'resume': {
                    'fichiers_traites': len(fichiers_a_traiter) - fichiers_en_erreur,
                    'fichiers_en_erreur': fichiers_en_erreur,
                    'total_enregistrements': total_enregistrements,
                    'total_remplacements': total_remplacements,
                },
            }
            if dry_run:
                response['dry_run'] = True

            print(f'[serveur] Batch termine : {len(fichiers_a_traiter)} fichiers, '
                  f'{total_enregistrements} enregistrements, {total_remplacements} remplacements.', file=sys.stderr)

            self._json_response(response)
        except Exception as e:
            traceback.print_exc()
            self._json_error(500, str(e))

    # ----- API : depseudonymiser -----

    def _handle_depseudonymise(self):
        try:
            body = self._read_json_body()
            texte = body.get('texte', '')
            correspondances = body.get('correspondances', [])

            # Construire la map inverse jeton -> valeur
            reverse_map = {}
            for entry in correspondances:
                jeton = entry.get('jeton', '')
                valeur = entry.get('valeur', '')
                if jeton and valeur:
                    reverse_map[jeton] = valeur

            # Remplacer les jetons par les valeurs originales
            result = texte
            # Trier par longueur décroissante pour éviter les remplacements partiels
            for jeton in sorted(reverse_map.keys(), key=len, reverse=True):
                result = result.replace(jeton, reverse_map[jeton])

            self._json_response({
                'texte_original': result,
                'remplacements': len(reverse_map),
            })
        except Exception as e:
            self._json_error(500, str(e))

    # ----- API : scoring RGPD -----

    def _handle_score(self):
        try:
            body = self._read_json_body()
            texte = body.get('texte', '')
            fort = body.get('fort', False)

            tokens = engine.TokenTable()
            stats = engine.Stats()
            scorer = engine.RiskScorer()

            engine.pseudonymise_texte(
                texte, 'pseudo', fort, False, False,
                tokens, stats, scorer,
                whitelist=set(), blacklist=set()
            )

            self._json_response({
                'score': {
                    'total': scorer.score,
                    'niveau': scorer.level(),
                    'details': scorer.details,
                },
                'stats': self._stats_to_dict(stats),
            })
        except Exception as e:
            self._json_error(500, str(e))

    # ----- API : generation de mapping -----

    def _handle_mapping_generate(self, parsed):
        """Redirige vers POST."""
        self._json_response({
            'message': 'Utilisez POST /api/mapping/generate avec {"path": "/chemin/fichier.json"}',
        })

    def _handle_mapping_generate_post(self):
        """Analyse un fichier et propose un mapping squelette."""
        try:
            body = self._read_json_body()
            file_path = body.get('path', '')

            if not file_path:
                self._json_error(400, 'Chemin de fichier requis (champ "path")')
                return

            if not os.path.isfile(file_path):
                self._json_error(404, f'Fichier introuvable : {file_path}')
                return

            # Charger un echantillon (5 premiers enregistrements)
            ext = os.path.splitext(file_path)[1].lower()
            if ext == '.json':
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = load_file(file_path, {})

            if not isinstance(data, list) or len(data) == 0:
                self._json_error(400, 'Le fichier doit contenir un array JSON non vide')
                return

            sample = data[:min(5, len(data))]

            # Analyser les cles
            all_keys = set()
            for rec in sample:
                if isinstance(rec, dict):
                    all_keys.update(rec.keys())

            champs = {}
            texte_libre = []
            structure = {}
            unwrapped_keys = set()

            for key in sorted(all_keys):
                values = [rec.get(key) for rec in sample if key in rec]
                values_non_null = [v for v in values if v is not None]
                if not values_non_null:
                    continue

                sample_val = values_non_null[0]

                if isinstance(sample_val, str):
                    # Detection JSON stringifie
                    if len(sample_val) > 10 and sample_val.strip()[:1] in ('{', '['):
                        try:
                            parsed_json = json.loads(sample_val)
                            if isinstance(parsed_json, (dict, list)):
                                structure = {
                                    'unwrap': {
                                        'field': key,
                                        'parse': 'json_string'
                                    }
                                }
                                # Analyser les cles du JSON imbrique
                                if isinstance(parsed_json, dict):
                                    self._analyze_nested(parsed_json, '', champs,
                                                         texte_libre, unwrapped_keys)
                                continue
                        except (json.JSONDecodeError, ValueError):
                            pass

                    self._classify_field(key, sample_val, champs, texte_libre)

                elif isinstance(sample_val, (int, float)):
                    if any(k in key.lower() for k in ('id', 'ident', 'numero')):
                        champs[key] = {'type': 'id', 'jeton': 'ID'}

            # Deviner le lookup noms
            lookup = {}
            for field_key, config in champs.items():
                if config['type'] == 'prenom' and 'prenom' not in lookup:
                    lookup['prenom'] = field_key
                elif config['type'] == 'nom' and 'nom' not in lookup:
                    lookup['nom'] = field_key

            # Construire le mapping
            mapping = {
                'description': f'Mapping genere depuis {os.path.basename(file_path)}',
            }
            if structure:
                mapping['structure'] = structure
            mapping['champs_sensibles'] = champs
            mapping['texte_libre'] = texte_libre
            if lookup:
                mapping['lookup_noms'] = lookup
            mapping['whitelist'] = []
            mapping['blacklist'] = []

            self._json_response({
                'mapping': mapping,
                'analyse': {
                    'cles_totales': len(all_keys),
                    'champs_detectes': len(champs),
                    'texte_libre_detecte': len(texte_libre),
                    'structure_unwrap': bool(structure),
                    'echantillon': len(sample),
                },
            })
        except Exception as e:
            traceback.print_exc()
            self._json_error(500, str(e))

    def _classify_field(self, key, sample_val, champs, texte_libre):
        """Classifie un champ par heuristique (nom de cle prioritaire, puis valeur)."""
        val_str = str(sample_val)
        val_upper = val_str.upper().strip()
        key_lower = key.lower().split('.')[-1]  # Dernier segment pour les chemins pointes

        # --- Par nom de cle (prioritaire — plus fiable que la valeur) ---
        if any(k in key_lower for k in ('firstname', 'prenom', 'first_name', 'given')):
            champs[key] = {'type': 'prenom', 'jeton': 'PRENOM'}
        elif any(k in key_lower for k in ('lastname', 'nom', 'last_name', 'family', 'patronyme')):
            champs[key] = {'type': 'nom', 'jeton': 'NOM'}
        elif any(k in key_lower for k in ('siret',)):
            champs[key] = {'type': 'siret', 'jeton': 'SIRET'}
        elif any(k in key_lower for k in ('siren',)):
            champs[key] = {'type': 'siren', 'jeton': 'SIREN'}
        elif any(k in key_lower for k in ('guid', 'uuid')):
            champs[key] = {'type': 'uuid', 'jeton': 'UUID'}
        elif any(k in key_lower for k in ('mail', 'email', 'courriel')):
            champs[key] = {'type': 'email', 'jeton': 'EMAIL'}
        elif any(k in key_lower for k in ('phone', 'mobile', 'fax', 'consumerphone')):
            champs[key] = {'type': 'tel', 'jeton': 'TEL'}
        elif any(k in key_lower for k in ('postal', 'cp', 'zipcode', 'zip_code', 'code_postal', 'postalcode')):
            champs[key] = {'type': 'cp', 'jeton': 'CP'}
        elif any(k in key_lower for k in ('gender', 'genre', 'sexe')):
            champs[key] = {'type': 'genre', 'jeton': 'GENRE'}
        elif any(k in key_lower for k in ('comment', 'note', 'description', 'texte',
                                           'question', 'message', 'detail', 'contenu', 'objet')):
            texte_libre.append(key)
        # --- Par valeur (fallback quand le nom de cle n'est pas parlant) ---
        elif '@' in val_str and '.' in val_str:
            champs[key] = {'type': 'email', 'jeton': 'EMAIL'}
        elif re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
                      val_str, re.IGNORECASE):
            champs[key] = {'type': 'uuid', 'jeton': 'UUID'}
        elif re.match(r'^\d{14}$', val_str):
            champs[key] = {'type': 'siret', 'jeton': 'SIRET'}
        elif re.match(r'^\d{9}$', val_str):
            champs[key] = {'type': 'siren', 'jeton': 'SIREN'}
        elif re.match(r'^\d{5}$', val_str):
            champs[key] = {'type': 'cp', 'jeton': 'CP'}
        elif val_str.lower() in ('male', 'female', 'homme', 'femme', 'm', 'f'):
            champs[key] = {'type': 'genre', 'jeton': 'GENRE'}
        elif re.match(r'^[\d\s\+\.\-]{8,}$', val_str) and not re.match(r'^\d{9,14}$', val_str):
            champs[key] = {'type': 'tel', 'jeton': 'TEL'}
        elif val_upper in engine.PRENOMS:
            champs[key] = {'type': 'prenom', 'jeton': 'PRENOM'}
        elif val_upper in engine.PATRONYMES:
            champs[key] = {'type': 'nom', 'jeton': 'NOM'}
        elif len(val_str) > 80:
            texte_libre.append(key)

    def _analyze_nested(self, obj, prefix, champs, texte_libre, seen):
        """Analyse recursivement un objet JSON imbrique."""
        if not isinstance(obj, dict):
            return
        for key, val in obj.items():
            full_key = f'{prefix}.{key}' if prefix else key
            if full_key in seen:
                continue
            seen.add(full_key)

            if isinstance(val, str):
                self._classify_field(full_key, val, champs, texte_libre)
            elif isinstance(val, dict):
                self._analyze_nested(val, full_key, champs, texte_libre, seen)
            elif isinstance(val, list) and val:
                if isinstance(val[0], dict):
                    # Notation avec []
                    self._analyze_nested(val[0], f'{full_key}[]', champs, texte_libre, seen)
                elif isinstance(val[0], str):
                    self._classify_field(f'{full_key}[]', val[0], champs, texte_libre)

    # ----- API : telechargement de fichier -----

    def _build_apercu_champs(self, avant_list, apres_list, mapping):
        """Construit un apercu structure par champ du mapping pour la previsualisation."""
        champs_sensibles = mapping.get('champs_sensibles', {})
        texte_libre = mapping.get('texte_libre', [])
        unwrap_config = (mapping.get('structure', {}) or {}).get('unwrap')

        result = []
        for champ, config in champs_sensibles.items():
            exemples = []
            for i, (av, ap) in enumerate(zip(avant_list, apres_list)):
                val_avant = self._resolve_dotted(av, champ, unwrap_config)
                val_apres = self._resolve_dotted(ap, champ, unwrap_config)
                if val_avant != val_apres and val_avant:
                    exemples.append({
                        'enregistrement': i + 1,
                        'avant': str(val_avant)[:150],
                        'apres': str(val_apres)[:150],
                    })
                if len(exemples) >= 3:
                    break
            result.append({
                'champ': champ,
                'type': config.get('type', ''),
                'jeton': config.get('jeton', ''),
                'exemples': exemples,
            })

        for champ in texte_libre:
            exemples = []
            for i, (av, ap) in enumerate(zip(avant_list, apres_list)):
                val_avant = self._resolve_dotted(av, champ, unwrap_config)
                val_apres = self._resolve_dotted(ap, champ, unwrap_config)
                if val_avant != val_apres and val_avant:
                    exemples.append({
                        'enregistrement': i + 1,
                        'avant': str(val_avant)[:200],
                        'apres': str(val_apres)[:200],
                    })
                if len(exemples) >= 2:
                    break
            result.append({
                'champ': champ,
                'type': 'texte_libre',
                'jeton': '',
                'exemples': exemples,
            })
        return result

    def _resolve_dotted(self, record, dotted_key, unwrap_config=None):
        """Resout un champ en notation pointee (Report.Firstname) dans un enregistrement."""
        obj = record
        # Si unwrap configure, desemballer d'abord
        if unwrap_config and '.' in dotted_key:
            field = unwrap_config.get('field', '')
            raw = record.get(field, '')
            if isinstance(raw, str) and raw.strip().startswith('{'):
                try:
                    obj = json.loads(raw)
                except Exception:
                    return None
            elif isinstance(raw, dict):
                obj = raw
            # Retirer le prefixe du champ unwrap si present
            parts = dotted_key.split('.')
        else:
            parts = dotted_key.split('.')

        for part in parts:
            if isinstance(obj, dict):
                obj = obj.get(part)
            else:
                return None
            if obj is None:
                return None
        return obj

    def _handle_download(self, parsed):
        """Sert un fichier local en telechargement."""
        try:
            qs = parse_qs(parsed.query)
            file_path = qs.get('path', [''])[0]

            if not file_path or not os.path.isfile(file_path):
                self._json_error(404, 'Fichier introuvable')
                return

            filename = os.path.basename(file_path)
            with open(file_path, 'rb') as f:
                data = f.read()

            self.send_response(200)
            self.send_header('Content-Type', 'application/octet-stream')
            self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self._json_error(500, str(e))

    # ----- API : statistiques serveur -----

    def _handle_stats(self):
        self._json_response({
            'dictionnaires': {
                'patronymes': len(engine.PATRONYMES),
                'prenoms': len(engine.PRENOMS),
                'stopwords_cap': len(engine.STOPWORDS_CAP),
                'stopwords_min': len(engine.STOPWORDS_MIN),
                'villes': len(engine.VILLES_FRANCE),
                'organisations': len(engine.MOTS_ORGANISATIONS),
            },
        })

    # ----- Helpers -----

    def _read_json_body(self):
        length = int(self.headers.get('Content-Length', 0))
        raw = self.rfile.read(length)
        return json.loads(raw.decode('utf-8'))

    def _read_multipart(self):
        """Parse multipart/form-data basique."""
        content_type = self.headers.get('Content-Type', '')
        length = int(self.headers.get('Content-Length', 0))
        raw = self.rfile.read(length)

        # Extraire le boundary
        boundary = None
        for part in content_type.split(';'):
            part = part.strip()
            if part.startswith('boundary='):
                boundary = part[9:].strip('"')
                break

        if not boundary:
            return None, {}

        file_data = None
        params = {}
        parts = raw.split(f'--{boundary}'.encode())

        for part in parts:
            if b'Content-Disposition' not in part:
                continue

            header_end = part.find(b'\r\n\r\n')
            if header_end == -1:
                continue

            header = part[:header_end].decode('utf-8', errors='replace')
            body = part[header_end + 4:]
            if body.endswith(b'\r\n'):
                body = body[:-2]

            # Extraire le nom du champ
            name = None
            filename = None
            for line in header.split('\r\n'):
                if 'name="' in line:
                    name = line.split('name="')[1].split('"')[0]
                if 'filename="' in line:
                    filename = line.split('filename="')[1].split('"')[0]

            if filename:
                file_data = body
                params['filename'] = filename
            elif name:
                params[name] = body.decode('utf-8', errors='replace')

        return file_data, params

    def _tokens_to_list(self, tokens):
        result = []
        for type_name, mapping in tokens._typed.items():
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
            prefix = prefix_map.get(type_name, type_name.upper())
            for key, (num, original) in mapping.items():
                result.append({
                    'type': type_name,
                    'jeton': f'[{prefix}_{num}]',
                    'valeur': original,
                })
        for key, (pid, original) in tokens._personnes.items():
            result.append({
                'type': 'personne',
                'jeton': f'[{pid}]',
                'valeur': original,
            })
        return sorted(result, key=lambda r: (r['type'], r['jeton']))

    def _stats_to_dict(self, stats):
        return {
            'remplacements': stats.counts,
            'total': sum(stats.counts.values()),
            'erreurs': stats.errors,
            'echantillons': {
                t: [{'original': o, 'remplacement': r} for o, r in samples]
                for t, samples in stats.samples.items()
            },
        }

    def _json_response(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _json_error(self, status, message):
        self._json_response({'erreur': message}, status)

    def do_OPTIONS(self):
        """CORS preflight."""
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def log_message(self, format, *args):
        """Log concis."""
        sys.stderr.write(f'[serveur] {args[0]}\n')


def main():
    parser = argparse.ArgumentParser(description='Serveur de pseudonymisation locale')
    parser.add_argument('--port', type=int, default=8090, help='Port (defaut: 8090)')
    parser.add_argument('--host', default='127.0.0.1', help='Hote (defaut: 127.0.0.1)')
    args = parser.parse_args()

    # Vérifier que le dossier interface existe
    if not os.path.isdir(INTERFACE_DIR):
        print(f'Attention : dossier {INTERFACE_DIR} absent, creation...', file=sys.stderr)
        os.makedirs(INTERFACE_DIR, exist_ok=True)

    server = ThreadingHTTPServer((args.host, args.port), APIHandler)
    print(f'\nServeur de pseudonymisation demarre', file=sys.stderr)
    print(f'  Interface : http://{args.host}:{args.port}/', file=sys.stderr)
    print(f'  API       : http://{args.host}:{args.port}/api/', file=sys.stderr)
    print(f'  Arret     : Ctrl+C\n', file=sys.stderr)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nArret du serveur.', file=sys.stderr)
        server.server_close()


if __name__ == '__main__':
    main()

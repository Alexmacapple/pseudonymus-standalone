#!/usr/bin/env node

/**
 * valider.mjs — Validation deterministe des manifests YAML et de la config.
 *
 * Usage :
 *   node tests-visuels/valider.mjs                    # valider tout
 *   node tests-visuels/valider.mjs --config-only      # valider la config seule
 *   node tests-visuels/valider.mjs chemin/manifest.yaml  # valider un manifest
 *
 * Exit 0 si tout valide, exit 1 avec detail des erreurs.
 */

import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { join, dirname, relative, extname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const yaml = require('js-yaml');

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const ROOT = __dirname; // tests-visuels/

// --- Types d'actions valides et leurs champs obligatoires ---

const ACTIONS_VALIDES = {
  open:       { obligatoires: ['url'] },
  click:      { obligatoires: ['target'] },
  fill:       { obligatoires: ['target', 'value'] },
  screenshot: { obligatoires: ['filename'] },
  'llm-check':{ obligatoires: ['criteria', 'severity'] },
  attendre:   { obligatoires: ['duree'] },
  upload:     { obligatoires: ['target', 'fichier'] },
  press:      { obligatoires: ['touche'] },
  include:    { obligatoires: ['fichier'] },
};

const SEVERITES_VALIDES = ['critique', 'haute', 'normale', 'basse'];
const FRAMEWORKS_VALIDES = ['statique', 'next', 'react', 'vue', 'angular', 'auto'];

// --- Utilitaires ---

function collecterYaml(dossier, prefixeIgnore = '_') {
  const fichiers = [];
  if (!existsSync(dossier)) return fichiers;

  for (const entry of readdirSync(dossier, { withFileTypes: true })) {
    const chemin = join(dossier, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === 'node_modules' || entry.name === '_resultats') continue;
      fichiers.push(...collecterYaml(chemin, prefixeIgnore));
    } else if (
      (extname(entry.name) === '.yaml' || extname(entry.name) === '.yml') &&
      !entry.name.startsWith(prefixeIgnore)
    ) {
      fichiers.push(chemin);
    }
  }
  return fichiers;
}

function lireYaml(chemin) {
  const contenu = readFileSync(chemin, 'utf-8');
  return yaml.load(contenu);
}

// --- Validation de la config ---

function validerConfig() {
  const erreurs = [];
  const cheminConfig = join(ROOT, '_config.yaml');

  if (!existsSync(cheminConfig)) {
    erreurs.push('ERREUR _config.yaml : fichier absent');
    return erreurs;
  }

  let config;
  try {
    config = lireYaml(cheminConfig);
  } catch (e) {
    erreurs.push(`ERREUR _config.yaml : YAML invalide — ${e.message}`);
    return erreurs;
  }

  if (!config || typeof config !== 'object') {
    erreurs.push('ERREUR _config.yaml : le fichier doit contenir un objet YAML');
    return erreurs;
  }

  // Champs obligatoires
  if (!config.projet || typeof config.projet !== 'string') {
    erreurs.push('ERREUR _config.yaml : champ "projet" manquant ou vide');
  }
  if (!config.url_base || typeof config.url_base !== 'string') {
    erreurs.push('ERREUR _config.yaml : champ "url_base" manquant ou vide');
  }
  if (config.framework && !FRAMEWORKS_VALIDES.includes(config.framework)) {
    erreurs.push(`ERREUR _config.yaml : framework "${config.framework}" invalide (valides : ${FRAMEWORKS_VALIDES.join(', ')})`);
  }

  // Vérifier les variables d'environnement non résolues
  const contenuBrut = readFileSync(cheminConfig, 'utf-8');
  const varsEnv = contenuBrut.match(/\$\{([^}]+)\}/g);
  if (varsEnv) {
    for (const v of varsEnv) {
      const nom = v.slice(2, -1);
      if (!process.env[nom]) {
        erreurs.push(`ERREUR _config.yaml : variable d'environnement ${v} non definie`);
      }
    }
  }

  // Version
  if (config.version !== undefined && config.version !== 1) {
    erreurs.push(`ERREUR _config.yaml : version ${config.version} non supportee (attendue : 1)`);
  }

  return erreurs;
}

// --- Validation d'un manifest ---

function validerManifest(chemin) {
  const erreurs = [];
  const relatif = relative(ROOT, chemin);

  let manifest;
  try {
    manifest = lireYaml(chemin);
  } catch (e) {
    erreurs.push(`ERREUR ${relatif} : YAML invalide — ${e.message}`);
    return erreurs;
  }

  if (!manifest || typeof manifest !== 'object') {
    erreurs.push(`ERREUR ${relatif} : le fichier doit contenir un objet YAML`);
    return erreurs;
  }

  // name obligatoire
  if (!manifest.name || typeof manifest.name !== 'string' || !manifest.name.trim()) {
    erreurs.push(`ERREUR ${relatif} : champ "name" manquant ou vide`);
  }

  // steps obligatoire
  if (!Array.isArray(manifest.steps) || manifest.steps.length === 0) {
    erreurs.push(`ERREUR ${relatif} : champ "steps" manquant ou vide (liste attendue)`);
    return erreurs;
  }

  // Valider chaque step
  for (let i = 0; i < manifest.steps.length; i++) {
    const step = manifest.steps[i];
    const prefixe = `ERREUR ${relatif} : step ${i + 1}`;

    if (!step || typeof step !== 'object') {
      erreurs.push(`${prefixe} — step invalide (objet attendu)`);
      continue;
    }

    if (!step.action || typeof step.action !== 'string') {
      erreurs.push(`${prefixe} — champ "action" manquant`);
      continue;
    }

    const spec = ACTIONS_VALIDES[step.action];
    if (!spec) {
      erreurs.push(`${prefixe} — action "${step.action}" inconnue (valides : ${Object.keys(ACTIONS_VALIDES).join(', ')})`);
      continue;
    }

    // Champs obligatoires de l'action
    for (const champ of spec.obligatoires) {
      if (step[champ] === undefined || step[champ] === null || step[champ] === '') {
        erreurs.push(`${prefixe} — champ "${champ}" manquant pour action "${step.action}"`);
      }
    }

    // Validations specifiques
    if (step.action === 'llm-check' && step.severity && !SEVERITES_VALIDES.includes(step.severity)) {
      erreurs.push(`${prefixe} — severity "${step.severity}" invalide (valides : ${SEVERITES_VALIDES.join(', ')})`);
    }

    if (step.action === 'attendre' && step.duree !== undefined) {
      if (typeof step.duree !== 'number' || step.duree <= 0) {
        erreurs.push(`${prefixe} — "duree" doit etre un nombre positif (recu : ${step.duree})`);
      }
    }
  }

  return erreurs;
}

// --- Main ---

function main() {
  const args = process.argv.slice(2);
  const configOnly = args.includes('--config-only');
  const fichierCible = args.find(a => !a.startsWith('--'));

  let toutesErreurs = [];

  // Toujours valider la config (sauf si fichier cible specifique)
  if (!fichierCible) {
    const erreursConfig = validerConfig();
    toutesErreurs.push(...erreursConfig);
  }

  if (configOnly) {
    // Config seule
  } else if (fichierCible) {
    // Un seul manifest
    const chemin = fichierCible.startsWith('/') ? fichierCible : join(process.cwd(), fichierCible);
    if (!existsSync(chemin)) {
      toutesErreurs.push(`ERREUR : fichier introuvable — ${fichierCible}`);
    } else {
      toutesErreurs.push(...validerManifest(chemin));
    }
  } else {
    // Tous les manifests
    const manifests = collecterYaml(ROOT);
    if (manifests.length === 0) {
      console.log('Aucun manifest YAML trouve dans tests-visuels/');
    } else {
      for (const m of manifests) {
        toutesErreurs.push(...validerManifest(m));
      }
      if (toutesErreurs.length === 0) {
        console.log(`${manifests.length} manifest(s) valide(s)`);
      }
    }
  }

  if (toutesErreurs.length > 0) {
    for (const e of toutesErreurs) {
      console.error(e);
    }
    process.exit(1);
  } else {
    if (!fichierCible && !configOnly) {
      console.log('Config OK');
    }
    process.exit(0);
  }
}

main();

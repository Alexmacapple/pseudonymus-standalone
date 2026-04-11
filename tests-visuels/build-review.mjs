#!/usr/bin/env node

/**
 * build-review.mjs — Genere une page de revue HTML DSFR standalone.
 *
 * Usage :
 *   node tests-visuels/build-review.mjs                     # generer revue.html
 *   node tests-visuels/build-review.mjs --serve [port]      # generer + serveur HTTP
 *   node tests-visuels/build-review.mjs --stop [port]       # arreter le serveur
 *
 * Lit : _config.yaml, _resultats/resultats.json, captures/
 * Produit : _resultats/revue.html
 */

import { readFileSync, writeFileSync, readdirSync, existsSync, statSync } from 'node:fs';
import { join, dirname, basename, relative, extname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createServer } from 'node:http';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const yaml = require('js-yaml');

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const ROOT = __dirname;

// --- Utilitaires ---

function deepMerge(target, source) {
  const result = { ...target };
  for (const key of Object.keys(source)) {
    if (
      source[key] && typeof source[key] === 'object' && !Array.isArray(source[key]) &&
      target[key] && typeof target[key] === 'object' && !Array.isArray(target[key])
    ) {
      result[key] = deepMerge(target[key], source[key]);
    } else {
      result[key] = source[key];
    }
  }
  return result;
}

function lireConfig() {
  const cheminConfig = join(ROOT, '_config.yaml');
  if (!existsSync(cheminConfig)) {
    console.error('ERREUR : _config.yaml introuvable dans tests-visuels/');
    process.exit(1);
  }
  let config = yaml.load(readFileSync(cheminConfig, 'utf-8'));

  const cheminLocal = join(ROOT, '_config.local.yaml');
  if (existsSync(cheminLocal)) {
    const local = yaml.load(readFileSync(cheminLocal, 'utf-8'));
    if (local && typeof local === 'object') {
      config = deepMerge(config, local);
    }
  }
  return config;
}

function lireResultats(config) {
  const chemin = join(ROOT, '_resultats', 'resultats.json');
  if (!existsSync(chemin)) {
    console.error('ERREUR : _resultats/resultats.json introuvable. Lancer /scan-visuel d\'abord.');
    process.exit(1);
  }
  return JSON.parse(readFileSync(chemin, 'utf-8'));
}

function collecterManifests(dossier) {
  const manifests = {};
  if (!existsSync(dossier)) return manifests;
  function parcourir(dir) {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      if (entry.isDirectory() && !entry.name.startsWith('_') && entry.name !== 'node_modules') {
        parcourir(join(dir, entry.name));
      } else if ((entry.name.endsWith('.yaml') || entry.name.endsWith('.yml')) && !entry.name.startsWith('_')) {
        try {
          const contenu = yaml.load(readFileSync(join(dir, entry.name), 'utf-8'));
          if (contenu && contenu.name && contenu.steps) {
            const rel = relative(dossier, join(dir, entry.name)).replace(/\.(yaml|yml)$/, '');
            manifests[rel] = contenu;
          }
        } catch (e) { /* ignorer les YAML invalides */ }
      }
    }
  }
  parcourir(dossier);
  return manifests;
}

function scannerAvantApres(dossierCaptures) {
  if (!existsSync(dossierCaptures)) return [];
  const fichiers = readdirSync(dossierCaptures);
  const paires = [];
  const avants = fichiers.filter(f => f.includes('-avant-'));
  for (const avant of avants) {
    const base = avant.replace(/-avant-\d{8}\.png$/, '');
    const date = avant.match(/-avant-(\d{8})\.png$/)?.[1];
    if (!date) continue;
    const apres = fichiers.find(f => f === `${base}-apres-${date}.png`);
    if (apres) {
      paires.push({ base, date, avant, apres });
    }
  }
  return paires;
}

function echapper(str) {
  if (typeof str !== 'string') return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;');
}

function cheminCapture(dossierCaptures, fichier) {
  // Chemin relatif depuis _resultats/ vers captures/
  if (!fichier) return '';
  if (fichier.startsWith('captures/')) return fichier;
  return `captures/${fichier}`;
}

// --- Validation path traversal ---

function validerChemin(chemin) {
  if (chemin.includes('..') || chemin.startsWith('/')) {
    throw new Error(`Chemin suspect refuse : ${chemin}`);
  }
}

// --- Generation HTML ---

function formaterDateFR(iso) {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    return d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })
      + ' a ' + d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
  } catch (e) { return iso; }
}

function genererHTML(config, resultats, paires, manifests) {
  const tests = resultats.tests || [];
  const resume = resultats.resume || { total: 0, pass: 0, fail: 0, erreur: 0 };
  const dateFR = formaterDateFR(resultats.date);

  // Enrichir chaque test avec les donnees du manifest
  for (const test of tests) {
    const manifest = manifests[test.id];
    if (manifest) {
      if (!test.description) test.description = manifest.description || '';
      if (!test.priority) test.priority = manifest.priority || '';
      if (!test.url) {
        const openStep = (manifest.steps || []).find(s => s.action === 'open');
        if (openStep) test.url = openStep.url || '';
      }
      // Ajouter les steps du manifest (spec) si pas deja enrichis
      if (!test.manifest_steps) {
        test.manifest_steps = (manifest.steps || []).map(s => ({
          action: s.action,
          target: s.target || '',
          value: s.value || '',
          url: s.url || '',
          criteria: s.criteria || '',
          description: s.description || '',
          severity: s.severity || '',
          filename: s.filename || '',
          duree: s.duree || 0
        }));
      }
    }
  }

  // Categories auto-detectees
  const categories = [...new Set(tests.map(t => t.categorie || 'sans-categorie'))].sort();

  // Donnees JSON pour le JS inline
  const donneesJSON = JSON.stringify({
    tests: tests.map(t => ({
      id: t.id,
      name: t.name,
      categorie: t.categorie,
      statut: t.statut,
      duree: t.duree,
      capture: t.capture,
      steps: t.steps,
      description: t.description || '',
      priority: t.priority || '',
      url: t.url || '',
      manifest_steps: t.manifest_steps || []
    })),
    paires: paires.map(p => ({
      base: p.base,
      date: p.date,
      avant: `captures/${p.avant}`,
      apres: `captures/${p.apres}`
    })),
    resume
  });

  return `<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Revue visuelle — ${echapper(config.projet || 'Projet')}</title>
<style>
/* --- DSFR subset inline --- */
:root {
  --blue-france: #000091;
  --blue-france-hover: #1212ff;
  --red-marianne: #ce0500;
  --green-emeraude: #18753c;
  --orange-warning: #b34000;
  --blue-info: #0063cb;
  --grey-975: #f6f6f6;
  --grey-950: #eeeeee;
  --grey-200: #3a3a3a;
  --grey-50: #161616;
  --text-default: var(--grey-50);
  --bg-default: #fff;
  --focus: #0a76f6;
  --font-family: "Marianne", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  --spacing-2v: 0.5rem;
  --spacing-4v: 1rem;
  --spacing-6v: 1.5rem;
  --spacing-8v: 2rem;
}
*, *::before, *::after { box-sizing: border-box; }
body {
  font-family: var(--font-family);
  color: var(--text-default);
  background: var(--grey-975);
  margin: 0;
  padding: 0;
  line-height: 1.5;
}
a { color: var(--blue-france); }
a:hover { color: var(--blue-france-hover); }

/* Layout */
.fr-container { max-width: 78rem; margin: 0 auto; padding: 0 var(--spacing-4v); }
.fr-grid-row { display: flex; flex-wrap: wrap; gap: var(--spacing-4v); }
.fr-col-4 { width: calc(33.333% - .67rem); }

/* Header DSFR institutionnel */
.fr-header { background: #fff; box-shadow: 0 8px 16px 0 rgba(0,0,0,.1); }
.fr-header__body { padding: 1rem 0; }
.fr-header__body-row { display: flex; align-items: center; }
.fr-header__brand { display: flex; align-items: center; gap: 1.5rem; }
.fr-logo {
  display: inline-block; font-size: .7875rem; font-weight: 700;
  letter-spacing: -.01em; line-height: 1.04em;
  text-transform: uppercase; vertical-align: middle; margin: 0;
}
.fr-logo::before {
  background-image: url("data:image/svg+xml;charset=utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 44 18'%3E%3Cpath fill='%23fff' d='M11.3 10.2c-.9.6-1.7 1.3-2.3 2.1v-.1c.4-.5.7-1 1-1.5.4-.2.7-.5 1-.8.5-.5 1-1 1.7-1.3.3-.1.5-.1.8 0-.1.1-.2.1-.4.2H13v-.1c-.3.3-.7.5-1 .9-.1.2-.2.6-.7.6 0 .1.1 0 0 0zm1.6 4.6c0-.1-.1 0-.2 0l-.1.1-.1.1-.2.2s.1.1.2 0l.1-.1c.1 0 .2-.1.2-.2.1 0 .1 0 .1-.1 0 .1 0 0 0 0zm-1.6-4.3c.1 0 .2 0 .2-.1s.1-.1.1-.1v-.1c-.2.1-.3.2-.3.3zm2.4 1.9s0-.1 0 0c.1-.1.2-.1.3-.1.7-.1 1.4-.3 2.1-.6-.8-.5-1.7-.9-2.6-1h.1c-.1-.1-.3-.1-.5-.2h.1c-.2-.1-.5-.1-.7-.2.1 0 .2-.2.2-.3h-.1c-.4.2-.6.5-.8.9.2.1.5 0 .7.1h-.3c-.1 0-.2.1-.2.2h.1c-.1 0-.1.1-.2.1.1.1.2 0 .4 0 0 .1.1.1.1.1-.1 0-.2.1-.3.3-.1.2-.2.2-.3.3v.1c-.3.2-.6.5-.9.8v.1c-.1.1-.2.1-.2.2v.1c.4-.1.6-.4 1-.5l.6-.3c.2 0 .3-.1.5-.1v.1h.2c0 .1-.2 0-.1.1s.3.1.4 0c.2-.2.3-.2.4-.2zM12.4 14c-.4.2-.9.2-1.2.4 0 0 0 .1-.1.1 0 0-.1 0-.1.1-.1 0-.1.1-.2.2l-.1.1s0 .1.1 0l.1-.1s-.1.1-.1.2V15.3l-.1.1s0 .1-.1.1l-.1.1.2-.2.1-.1h.2s0-.1.1-.1c.1-.1.2-.2.3-.2h.1c.1-.1.3-.1.4-.2.1-.1.2-.2.3-.2.2-.2.5-.3.8-.5-.1 0-.2-.1-.3-.1 0 .1-.2 0-.3 0zM30 9.7c-.1.2-.4.2-.6.3-.2.2 0 .4.1.5.1.3-.2.5-.4.5.1.1.2.1.2.1 0 .2.2.2.1.4s-.5.3-.3.5c.1.2.1.5 0 .7-.1.2-.3.4-.5.5-.2.1-.4.1-.6 0-.1 0-.1-.1-.2-.1-.5-.1-1-.2-1.5-.2-.1 0-.3.1-.4.1-.1.1-.3.2-.4.3l-.1.1c-.1.1-.2.2-.2.3-.1.2-.2.4-.2.6-.2.5-.2 1 0 1.4 0 0 1 .3 1.7.6.2.1.5.2.7.4l1.7 1H13.2l1.6-1c.6-.4 1.3-.7 2-1 .5-.2 1.1-.5 1.5-.9.2-.2.3-.4.5-.5.3-.4.6-.7 1-1l.3-.3s0-.1.1-.1c-.2.1-.2.2-.4.2 0 0-.1 0 0-.1s.2-.2.3-.2v-.1c-.4 0-.7.2-1 .5h-.2c-.5.2-.8.5-1.2.7v-.1c-.2.1-.4.2-.5.2-.2 0-.5.1-.8 0-.4 0-.7.1-1.1.2-.2.1-.4.1-.6.2v.1l-.2.2c-.2.1-.3.2-.5.4l-.5.5h-.1l.1-.1.1-.1c0-.1.1-.1.1-.2.2-.1.3-.3.5-.4 0 0-.1 0 0 0 0 0 0-.1.1-.1l-.1.1c-.1.1-.1.2-.2.2v-.1-.1l.2-.2c.1-.1.2-.1.3-.2h.1c-.2.1-.3.1-.5.2H14h-.1c0-.1.1-.1.2-.2h.1c1-.8 2.3-.6 3.4-1 .1-.1.2-.1.3-.2.1-.1.3-.2.5-.3.2-.2.4-.4.5-.7v-.1c-.4.4-.8.7-1.3 1-.6.2-1.3.4-2 .4 0-.1.1-.1.1-.1 0-.1.1-.1.1-.2h.1s0-.1.1-.1h.1c-.1-.1-.3.1-.4 0 .1-.1 0-.2.1-.2h.1s0-.1.1-.1c.5-.3.9-.5 1.3-.7-.1 0-.1.1-.2 0 .1 0 0-.1.1-.1.3-.1.6-.3.9-.4-.1 0-.2.1-.3 0 .1 0 .1-.1.2-.1v-.1h0c0-.1.1 0 .2-.1h-.1c.1-.1.2-.2.4-.2 0-.1-.1 0-.1-.1h.1-.5c-.1 0 0-.1 0-.1.1-.2.2-.5.3-.7h-.1c-.3.3-.8.5-1.2.6h-.2c-.2.1-.4.1-.5 0-.1-.1-.2-.2-.3-.2-.2-.1-.5-.3-.8-.4-.7-.2-1.5-.4-2.3-.3.3-.1.7-.2 1.1-.3.5-.2 1-.3 1.5-.3h-.3c-.4 0-.9.1-1.3.2-.3.1-.6.2-.9.2-.2.1-.3.2-.5.2v-.1c.3-.4.7-.7 1.1-.8.5-.1 1.1 0 1.6.1.4 0 .8.1 1.1.2.1 0 .2.2.3.3.2.1.4 0 .5.1v-.2c.1-.1.3 0 .4 0 .2-.2-.2-.4-.3-.6v-.1c.2.2.5.4.7.6.1.1.5.2.5 0-.2-.3-.4-.6-.7-.9v-.2c-.1 0-.1 0-.1-.1-.1-.1-.1-.2-.1-.3-.1-.2 0-.4-.1-.5-.1-.2-.1-.3-.1-.5-.1-.5-.2-1-.3-1.4-.1-.6.3-1 .6-1.5.2-.4.5-.7.8-1 .1-.4.3-.7.6-1 .3-.3.6-.5.9-.6.3-.1.5-.2.8-.3l2.5-.4H25l1.8.3c.1 0 .2 0 .2.1.1.1.3.2.4.2.2.1.4.3.6.5.1.1.2.3.1.4-.1.1-.1.4-.2.4-.2.1-.4.1-.6.1-.1 0-.2 0-.4-.1.5.2.9.4 1.2.8 0 .1.2.1.3.1v.1c-.1.1-.1.1-.1.2h.1c.1-.1.1-.4.3-.3.2.1.2.3.1.4-.1.1-.2.2-.4.3v.2c.1.1.1.2.2.4s.1.5.2.7c.1.5.2.9.2 1.4 0 .2-.1.5 0 .7l.3.6c.1.2.2.3.3.5.2.3.6.6.4 1zm-15.6 5.2c-.1 0-.1.1-.1.1s.1 0 .1-.1zm5.8-1.8c-.1.1 0 0 0 0zm-6.7-.2c0 .1.1 0 .1 0 .2-.1.5 0 .6-.2-.1-.1-.2 0-.2-.1-.1 0-.2 0-.2.1-.1.1-.3.1-.3.2z'/%3E%3Cpath fill='gray' d='M27.9 6.8c.1 0 .3 0 .3.1-.1.2-.4.3-.6.5h-.1c-.1.1-.1.2-.1.2h-.3c.1.1.3.2.5.2l.1.1h.2V8c-.1.1-.2.1-.4.1.2.1.5.1.7 0 .2-.1 0-.4.1-.5-.1 0 0-.1-.1-.1.1-.1.1-.2.2-.2s.1 0 .2-.1c0-.1-.1-.1-.1-.2.2-.1.3-.3.3-.5 0-.1-.3-.1-.4-.2h-.5c-.2 0-.3.1-.5.1l-.6.3c.2-.1.4-.1.7-.2 0 .3.2.3.4.3'/%3E%3C/svg%3E"),linear-gradient(90deg,#000091,#000091 50%,#e1000f 0,#e1000f),linear-gradient(90deg,#000,#000);
  background-position: 0 -.0625rem, 0 0, 0 0;
  background-repeat: no-repeat;
  background-size: 2.75rem 1.125rem, 2.75rem 1rem, 0;
  content: ""; display: block; height: 1rem; margin-bottom: .333rem; width: 2.75rem;
}
.fr-logo::after {
  background-image: url("data:image/svg+xml;charset=utf8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 252 180'%3E%3Cdefs%3E%3Csymbol id='a' viewBox='0 0 11 15.5'%3E%3Cpath d='M10.4 5.3C11.9 1.5 10.1 0 7.9 0 4.2 0 0 6.5 0 11.7c0 2.5 1.2 3.8 3 3.8 2.1 0 4.3-2 6.2-5.5h-1c-1.2 1.5-2.6 2.6-3.9 2.6-1.3 0-2-.8-2-2.6a10.7 10.7 0 01.3-2.2zm-4-3.1c1.1 0 2 .8 1.5 2.6L3.1 6.1c.8-2.2 2.2-4 3.4-4z'/%3E%3C/symbol%3E%3Csymbol id='b' viewBox='0 0 12.4 21.8'%3E%3Cuse width='11' height='15.5' y='6.4' href='%23a'/%3E%3Cpath d='M7.9 4.7L12.4.6V0h-3L6.7 4.7H8z'/%3E%3C/symbol%3E%3Csymbol id='c' viewBox='0 0 11.5 19'%3E%3Cpath d='M1.7 5.7h2.6L.1 17.1a1.3 1.3 0 001.2 2c3 0 6.4-2.6 7.8-6.2h-.7a9.4 9.4 0 01-5.1 3.5L7 5.7H11l.5-1.6H7.7L9 0H7.6L4.9 4.1l-3.2.4v1.2z'/%3E%3C/symbol%3E%3Csymbol id='d' viewBox='0 0 9.8 21.9'%3E%3Cpath d='M7.6 8c.3-1-.4-1.6-1-1.6-2.2 0-5 2.1-6 5h.7A5.6 5.6 0 014.4 9L.1 20.3a1.1 1.1 0 001 1.6c2.2 0 4.7-2 5.8-5H6A5.6 5.6 0 013 19.5zM8 3.7a1.8 1.8 0 001.8-1.8A1.8 1.8 0 008 0a1.8 1.8 0 00-1.8 1.8A1.8 1.8 0 008 3.6'/%3E%3C/symbol%3E%3Csymbol id='e' viewBox='0 0 14.8 15.5'%3E%3Cpath d='M3.3 3.1c.7 0 1 1 0 3.4l-3 6.8c-.7 1.3 0 2.2 1.2 2.2a1.3 1.3 0 001.5-1l3-8C7.4 4.8 10 3 11 3s.8.6.3 1.6l-4.6 9a1.3 1.3 0 001.1 1.9c2.3 0 5-2 6-5h-.6A5.6 5.6 0 0110 13l4-8a6.1 6.1 0 00.8-2.8A2 2 0 0012.6 0c-2 0-3.6 2.2-6 5V2.8C6.6 1.4 6.1 0 4.8 0 3.2 0 1.8 2.5.7 4.9h.7c.7-1.1 1.3-1.8 2-1.8'/%3E%3C/symbol%3E%3Csymbol id='f' viewBox='0 0 12 15.5'%3E%3Cpath d='M11.8 3.5c.5-1.9.2-3.5-1.2-3.5-1.8 0-2.3 1.2-4 5V2.8C6.5 1.3 6 0 4.6 0 3.1 0 1.7 2.5.5 5h.8C2 3.7 2.8 3 3.3 3c.7 0 1 1 0 3.4l-3 6.8c-.7 1.3 0 2.1 1.2 2.1a1.3 1.3 0 001.5-1l3-8a50.3 50.3 0 012.6-3h3.2z'/%3E%3C/symbol%3E%3Csymbol id='g' viewBox='0 0 14.7 16.2'%3E%3Cpath d='M10.5 13.1c-.6 0-1-1 0-3.4L14.6.1 13.4 0l-1.3 1.3h-.3C6.1 1.3 0 8.6 0 14.2a2 2 0 002.1 2.1c1.7 0 3.3-2.4 5.2-5l-.1 1c-.3 2.6.6 4 2 4 1.5 0 3-2.4 4-4.9h-.7c-.7 1.1-1.5 1.8-2 1.8zM7.9 9.8c-1.3 1.6-3.4 3.5-4.3 3.5-.5 0-.9-.5-.9-1.6 0-3.5 4-8.2 6-8.2a4.2 4.2 0 011.4.2z'/%3E%3C/symbol%3E%3Csymbol id='h' viewBox='0 0 21.9 19.8'%3E%3Cpath d='M11.2 19.8l.3-.9c-3.8-.7-4.3-.7-2.7-4.8l1.4-3.9h3c1.9 0 1.9.9 1.6 3h1l2.6-6.9h-1c-1 1.6-1.8 2.9-3.8 2.9h-3l2-5.6c.8-2 1.1-2.4 3.7-2.4h.7c2.6 0 3 .7 3 3.5h1l.9-4.7H7.3L7 .9c3 .6 3.3.9 2 4.8L5.7 14c-1.5 3.9-2 4.2-5.5 4.8l-.3.9z'/%3E%3C/symbol%3E%3Csymbol id='i' viewBox='0 0 10.1 21.9'%3E%3Cpath d='M2.9 19.4L10.1.3 9.8 0l-5 .6v.6l1 .7c.9.7.6 1.3-.2 3.4L.2 19.9a1.3 1.3 0 001.1 2c2.3 0 4.7-2.1 5.8-5h-.7a6.5 6.5 0 01-3.5 2.5'/%3E%3C/symbol%3E%3Csymbol id='j' viewBox='0 0 18 22'%3E%3Cpath d='M18 .6h-4.3a3.8 3.8 0 00-2.1-.6A6.6 6.6 0 005 6.5a3.3 3.3 0 003 3.6c-1.9.8-3 1.8-3 2.9a1.7 1.7 0 00.9 1.5c-4.3 1.3-6 2.8-6 4.7 0 2 2.6 2.8 5.6 2.8 5.3 0 9.6-2.7 9.6-5.1 0-1.8-1.6-2.5-4.3-3.3-2.2-.7-3.2-.8-3.2-1.6A2.4 2.4 0 019 10.2a6.6 6.6 0 006.1-6.5 4.5 4.5 0 00-.2-1.5h2.5zM9.8 16.2c2.1.7 3 1 3 1.6 0 1.4-2 2.5-5.6 2.5-2.7 0-4-.6-4-2 0-1.5 1.4-2.5 3.5-3.3a21.5 21.5 0 003 1.2zM9 9c-1 0-1.3-.8-1.3-1.7 0-2.8 1.4-6.2 3.5-6.2 1 0 1.3.8 1.3 1.6 0 2.9-1.4 6.3-3.5 6.3z'/%3E%3C/symbol%3E%3Csymbol id='k' viewBox='0 0 23 25.1'%3E%3Cpath d='M14.3 15.6c1.9 0 2 .8 1.6 2.8H17l2.5-6.8h-1c-1 1.6-1.7 2.9-3.8 2.9h-4.1l2-5.6c.7-2 1-2.4 3.7-2.4H18c2.6 0 3 .7 3 3.5h1l.9-4.7H7.3l-.3.9c3 .6 3.3.9 2 4.8l-3.2 8.4c-1.5 3.9-2 4.2-5.6 4.8l-.2 1h17.4l3.2-5h-1.2c-2 2-4 3.8-8 3.8-4.7 0-4.3-.3-2.7-4.6l1.4-3.8h4.2zm2.3-11.8L21 .6V0h-3l-2.6 3.9h1.2v-.1z'/%3E%3C/symbol%3E%3Csymbol id='l' viewBox='0 0 13.6 21.8'%3E%3Cpath d='M11.4 6.4c-2 0-4 2.2-5.8 4.8L9.6.3 9.4 0l-5 .6V1l1 .8c.9.7.6 1.3-.2 3.4L.8 16.8A13.9 13.9 0 000 19c0 1.4 1.8 2.7 3.5 2.7 3.8 0 10-6.9 10-12.2 0-2.3-.5-3.2-2.1-3.2zM4.8 19.5c-.8 0-1.9-.7-1.9-1.3a15.5 15.5 0 01.8-2.2L5 12.7C6.3 11 8.4 9.3 9.6 9.3c.7 0 1.2.4 1.2 1.5 0 3.1-2.9 8.7-6 8.7z'/%3E%3C/symbol%3E%3Csymbol id='m' viewBox='0 0 19.2 19.9'%3E%3Cpath d='M17.6 0H7.3L7 .9c3 .6 3.3.9 2 4.8l-3.2 8.5c-1.5 3.9-2 4.2-5.5 4.8L0 20h15.7l3.5-6H18c-2 2-4.2 4.8-7.7 4.8-2.7 0-3-.5-1.6-4.5l3.1-8.5c1.4-3.9 2-4.2 5.5-4.8z'/%3E%3C/symbol%3E%3Csymbol id='n' viewBox='0 0 126 90'%3E%3Cuse width='12.4' height='21.8' x='112.7' y='66.1' href='%23b'/%3E%3Cuse width='11.5' height='19' x='102.2' y='69' href='%23c'/%3E%3Cuse width='9.8' height='21.9' x='93.6' y='66.1' href='%23d'/%3E%3Cuse width='14.8' height='15.5' x='77.2' y='72.5' href='%23e'/%3E%3Cuse width='12' height='15.5' x='65.7' y='72.5' href='%23f'/%3E%3Cuse width='11' height='15.5' x='54.3' y='72.5' href='%23a'/%3E%3Cuse width='11.5' height='19' x='43.7' y='69' href='%23c'/%3E%3Cuse width='14.7' height='16.2' x='28.9' y='71.8' href='%23g'/%3E%3Cuse width='12' height='15.5' x='19.6' y='72.5' href='%23f'/%3E%3Cuse width='21.9' height='19.8' y='67.6' href='%23h'/%3E%3Cuse width='12.4' height='21.8' x='77.3' y='33.1' href='%23b'/%3E%3Cuse width='11.5' height='19' x='66.8' y='36' href='%23c'/%3E%3Cuse width='9.8' height='21.9' x='58.2' y='33' href='%23d'/%3E%3Cuse width='10.1' height='21.9' x='49.4' y='33.1' href='%23i'/%3E%3Cuse width='14.7' height='16.2' x='34.9' y='38.8' href='%23g'/%3E%3Cuse width='18' height='22' x='18.6' y='39.4' href='%23j'/%3E%3Cuse width='23' height='25.1' y='29.3' href='%23k'/%3E%3Cuse width='12.4' height='21.8' x='76.8' y='.1' href='%23b'/%3E%3Cuse width='11.5' height='19' x='66.2' y='2.9' href='%23c'/%3E%3Cuse width='12' height='15.5' x='54.8' y='6.5' href='%23f'/%3E%3Cuse width='11' height='15.5' x='43.4' y='6.4' href='%23a'/%3E%3Cuse width='13.6' height='21.8' x='29.4' y='.1' href='%23l'/%3E%3Cuse width='9.8' height='21.9' x='20.6' href='%23d'/%3E%3Cuse width='19.2' height='19.9' y='1.4' href='%23m'/%3E%3C/symbol%3E%3C/defs%3E%3Cuse fill='%23000' width='126' height='90' x='0' y='0' href='%23n'/%3E%3Cuse fill='%23fff' width='126' height='90' x='126' y='90' href='%23n'/%3E%3C/svg%3E");
  background-position: 0 calc(100% + 1.875rem); background-repeat: no-repeat;
  background-size: 5.25rem 3.75rem; content: ""; display: block;
  min-width: 2.625rem; padding-top: 2.2083333333rem;
}
.fr-header__service-title { font-size: 1.25rem; font-weight: 700; margin: 0; color: var(--grey-50); }
.fr-header__service-tagline { font-size: .875rem; color: #666; margin: .25rem 0 0; }
.fr-header__service a { text-decoration: none; color: inherit; }

/* Alert DSFR */
.fr-alert { font-family: var(--font-family); padding: 1rem 1.5rem; margin: 1.5rem 0 1rem; border-left: 4px solid; }
.fr-alert__title { font-size: 1rem; font-weight: 700; margin: 0 0 .25rem; }
.fr-alert p { font-size: .875rem; margin: 0; }
.fr-alert--success { border-left-color: var(--green-emeraude); background-color: #b8fec9; }
.fr-alert--success .fr-alert__title { color: var(--green-emeraude); }
.fr-alert--error { border-left-color: var(--red-marianne); background-color: #fce4e4; }
.fr-alert--error .fr-alert__title { color: var(--red-marianne); }

/* Search bar DSFR */
.fr-search-bar { display: flex; align-items: stretch; margin: var(--spacing-4v) 0; }
.fr-search-bar .fr-label { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); border: 0; }
.fr-search-bar .fr-input {
  flex: 1; padding: .5rem .75rem; border: 1px solid var(--grey-200); border-right: none;
  font-size: .875rem; font-family: var(--font-family); color: var(--grey-50); min-width: 0;
}
.fr-search-bar .fr-input:focus { outline: 2px solid var(--focus); outline-offset: -2px; }
.fr-search-bar .fr-btn { border-radius: 0; padding: .5rem .75rem; }

/* Tabs DSFR */
.fr-tabs { margin: var(--spacing-4v) 0; }
.fr-tabs__list {
  display: flex; list-style: none; padding: 0; margin: 0;
  border-bottom: 1px solid #ddd; overflow-x: auto;
}
.fr-tabs__tab {
  padding: .75rem 1rem; cursor: pointer; border: none; background: none;
  font-family: var(--font-family); font-size: .875rem; font-weight: 500;
  color: #666; border-bottom: 2px solid transparent; white-space: nowrap;
}
.fr-tabs__tab:hover { color: var(--blue-france); background-color: #f5f5fe; }
.fr-tabs__tab[aria-selected="true"] {
  color: var(--blue-france); border-bottom-color: var(--blue-france); font-weight: 700;
}
.fr-tabs__tab:focus-visible { outline: 2px solid var(--focus); outline-offset: -2px; }
.fr-tabs__panel { display: none; padding: var(--spacing-4v) 0; }
.fr-tabs__panel--selected { display: block; }

/* Cards DSFR */
.fr-card {
  border: 1px solid var(--grey-950); background: #fff;
  overflow: hidden; position: relative;
  display: flex; flex-direction: column-reverse;
}
.fr-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
.fr-card[data-statut="PASS"] { border-left: 3px solid var(--green-emeraude); }
.fr-card[data-statut="FAIL"] { border-left: 3px solid var(--red-marianne); }
.fr-card[data-statut="ERREUR"] { border-left: 3px solid var(--orange-warning); }
.fr-card[data-statut="INSTABLE"] { border-left: 3px solid var(--blue-info); }
.fr-enlarge-link .fr-card__link { text-decoration: none; color: inherit; }
.fr-enlarge-link .fr-card__link::after { content: ""; position: absolute; inset: 0; z-index: 1; }
.fr-enlarge-link:focus-within { outline: 2px solid var(--focus); outline-offset: 2px; }
.fr-enlarge-link:focus-within .fr-card__link:focus { outline: none; }
.fr-card__header { position: relative; }
.fr-card__img { overflow: hidden; }
.fr-responsive-img { width: 100%; aspect-ratio: 16/9; object-fit: cover; display: block; background: var(--grey-975); }
.fr-card__body { padding: var(--spacing-2v) var(--spacing-4v) var(--spacing-4v); }
.fr-card__content {}
.fr-card__title { font-size: .875rem; font-weight: 700; margin: 0 0 var(--spacing-2v); }
.fr-card__title a { color: var(--grey-50); }
.fr-card__title a:hover { color: var(--blue-france); }
.fr-card__end { display: flex; align-items: center; gap: .5rem; }
.fr-card__detail { font-size: .75rem; color: #666; }

/* Badges DSFR */
.fr-badge {
  display: inline-flex; align-items: center; padding: .125rem .375rem;
  font-size: .6875rem; font-weight: 700; text-transform: uppercase;
  letter-spacing: .03em; white-space: nowrap; margin: 0;
}
.fr-badge--success { background: #b8fec9; color: var(--green-emeraude); }
.fr-badge--error { background: #fce4e4; color: var(--red-marianne); }
.fr-badge--warning { background: var(--grey-950); color: var(--grey-200); }
.fr-badge--info { background: #e8edff; color: var(--blue-info); }

/* Modal DSFR (dialog natif) */
.fr-modal {
  position: fixed; inset: 0; z-index: 1000;
  display: none; align-items: center; justify-content: center;
  background: rgba(0,0,0,.5); padding: 0; border: none;
  max-width: 100%; max-height: 100%; width: 100%; height: 100%;
}
.fr-modal[open] { display: flex; }
.fr-modal__body {
  background: #fff; max-height: 90vh; overflow-y: auto;
  box-shadow: 0 16px 32px rgba(0,0,0,.2); max-width: 90vw; min-width: 50vw;
}
.fr-modal__header { display: flex; justify-content: flex-end; padding: 1rem 1.5rem 0; }
.fr-modal__content { padding: 0 1.5rem 1.5rem; }
.fr-modal__title { font-size: 1.25rem; font-weight: 700; margin: 0 0 1rem; }
.fr-btn--close {
  font-size: .75rem; font-weight: 500; background: none; border: none;
  color: var(--blue-france); cursor: pointer; padding: .25rem .5rem;
  text-transform: uppercase; font-family: var(--font-family);
}
.fr-btn--close:hover { background-color: #e3e3fd; }
.fr-btn--close:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }

/* Screenshot container avec annotation */
.screenshot-container { position: relative; display: inline-block; max-width: 100%; }
.screenshot-container img { max-width: 100%; display: block; }
.screenshot-container canvas {
  position: absolute; top: 0; left: 0; width: 100%; height: 100%;
  cursor: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='%23000091' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z'/%3E%3C/svg%3E") 2 22, crosshair;
}

/* Comparaison avant/apres */
.comparaison { display: flex; gap: var(--spacing-4v); margin: var(--spacing-4v) 0; }
.comparaison__col { flex: 1; }
.comparaison__col img { width: 100%; border: 1px solid var(--grey-950); border-radius: var(--border-radius); }
.comparaison__label { font-weight: 700; margin-bottom: var(--spacing-2v); font-size: 0.875rem; }

/* Boutons DSFR */
.fr-btn {
  display: inline-flex; align-items: center; gap: .5rem;
  padding: .5rem 1rem; background: var(--blue-france); color: #fff; border: none;
  border-radius: 0; font-family: var(--font-family);
  font-size: .875rem; font-weight: 500; cursor: pointer; text-decoration: none;
}
.fr-btn:hover { background: var(--blue-france-hover); }
.fr-btn:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }
.fr-btn--secondary { background: transparent; color: var(--blue-france); box-shadow: inset 0 0 0 1px var(--blue-france); }
.fr-btn--secondary:hover { background: #e3e3fd; }
.fr-btn--sm { padding: .25rem .75rem; font-size: .75rem; }

/* Sidemenu DSFR */
.fr-sidemenu { font-family: var(--font-family); }
.fr-sidemenu__inner { border-left: 1px solid #ddd; padding-left: 1rem; }
.fr-sidemenu__title { font-size: .875rem; font-weight: 700; text-transform: uppercase; letter-spacing: .03em; margin-bottom: .5rem; }
.fr-sidemenu__list { list-style: none; padding: 0; margin: 0; }
.fr-sidemenu__list li { margin-bottom: .25rem; }
.fr-sidemenu__item {
  display: block; padding: .5rem .75rem; font-size: .875rem; color: var(--grey-50);
  background: none; border: none; border-left: 2px solid transparent;
  margin-left: -1.0625rem; cursor: pointer; width: calc(100% + 1.0625rem);
  text-align: left; font-family: var(--font-family);
}
.fr-sidemenu__item:hover { background: #f5f5fe; }
.fr-sidemenu__item[aria-current="true"] { color: var(--blue-france); font-weight: 700; border-left-color: var(--blue-france); }
.fr-sidemenu__item:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }

/* Layout deux colonnes */
.layout-deux-cols { display: flex; gap: 2rem; align-items: flex-start; margin-top: var(--spacing-4v); }
.layout-deux-cols__aside { width: 14rem; flex-shrink: 0; padding-top: var(--spacing-2v); }
.layout-deux-cols__main { flex: 1; min-width: 0; }

/* Steps detail */
.steps-list { padding: 0 0 0 1.25rem; margin: var(--spacing-2v) 0; }
.steps-list li { padding: var(--spacing-2v) 0; border-bottom: 1px solid var(--grey-950); font-size: .875rem; }
.steps-list .step-ok { color: var(--green-emeraude); }
.steps-list .step-fail { color: var(--red-marianne); }

/* Accordeon steps */
.fr-accordion { margin-bottom: var(--spacing-2v); }
.fr-accordion__btn {
  font-family: var(--font-family); font-size: .875rem; font-weight: 700;
  background: var(--grey-975); border: none; padding: .75rem 1rem; width: 100%;
  text-align: left; cursor: pointer; color: var(--blue-france);
}
.fr-accordion__btn:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }
.fr-collapse--expanded { padding: 0 1rem; }

/* Modal footer */
.fr-modal__footer { padding: 1rem 1.5rem; border-top: 1px solid #ddd; }

/* Annotations */
.annotations-zone { margin-top: var(--spacing-4v); }
.annotation-rect {
  position: absolute; border: 2px solid var(--red-marianne);
  background: rgba(225, 0, 15, 0.1); pointer-events: none;
}

/* Selection + Checkbox DSFR */
.fr-card.selected { outline: 3px solid var(--blue-france); outline-offset: -3px; background: #f5f5fe; }
.fr-checkbox-group {
  position: absolute; top: .75rem; right: .75rem; z-index: 2;
}
.fr-checkbox-group input[type="checkbox"] {
  width: 1.5rem; height: 1.5rem; appearance: none; -webkit-appearance: none;
  border: 2px solid var(--grey-200); background: #fff; cursor: pointer; margin: 0;
}
.fr-checkbox-group input[type="checkbox"]:checked {
  background-color: var(--blue-france); border-color: var(--blue-france);
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='%23fff'%3E%3Cpath d='M9 16.2l-3.5-3.5 1.4-1.4L9 13.4l7.1-7.1 1.4 1.4z'/%3E%3C/svg%3E");
  background-size: 1rem; background-repeat: no-repeat; background-position: center;
}
.fr-checkbox-group input[type="checkbox"]:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }
.fr-checkbox-group .fr-label { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); border: 0; }
.fr-col-4 { position: relative; }

/* Barre d'actions sticky DSFR */
.fr-action-bar {
  position: sticky; bottom: 0; left: 0; right: 0;
  background: #fff; border-top: 1px solid #ddd;
  padding: 1rem 0; box-shadow: 0 -4px 12px rgba(0,0,0,.08);
  display: none; z-index: 500;
}
.fr-action-bar.visible { display: block; }
.fr-action-bar__inner { display: flex; align-items: center; gap: .75rem; }
.fr-action-bar__count { font-weight: 700; font-size: .875rem; margin-right: auto; }
.fr-action-bar .fr-btn--danger { background: var(--red-marianne); color: #fff; }
.fr-action-bar .fr-btn--danger:hover { opacity: 0.9; }

/* Responsive */
@media (max-width: 62rem) {
  .fr-col-4 { width: calc(50% - .5rem); }  /* tablette : 2 colonnes */
  .layout-deux-cols { flex-direction: column; }
  .layout-deux-cols__aside { width: 100%; }
}
@media (max-width: 36rem) {
  .fr-col-4 { width: 100%; }
  .comparaison { flex-direction: column; }
  .fr-action-bar__inner { flex-wrap: wrap; }
}
/* Fil d'Ariane DSFR */
.fr-breadcrumb { padding: .75rem 0; margin: 0 auto; max-width: 78rem; padding-left: var(--spacing-4v); padding-right: var(--spacing-4v); }
.fr-breadcrumb__button { display: none; }
.fr-breadcrumb__list { list-style: none; padding: 0; margin: 0; display: flex; flex-wrap: wrap; gap: .25rem; font-size: .75rem; }
.fr-breadcrumb__list li { display: flex; align-items: center; }
.fr-breadcrumb__list li:not(:last-child)::after { content: ">"; margin-left: .5rem; color: #666; }
.fr-breadcrumb__link { color: var(--blue-france); text-decoration: none; }
.fr-breadcrumb__link:hover { text-decoration: underline; }
.fr-breadcrumb__link[aria-current="page"] { color: var(--grey-50); font-weight: 500; pointer-events: none; }
.fr-breadcrumb__link:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }
@media (max-width: 36rem) {
  .fr-breadcrumb__button { display: block; background: none; border: none; color: var(--blue-france); font-size: .75rem; cursor: pointer; padding: .5rem 0; font-family: var(--font-family); }
  .fr-collapse:not(.fr-collapse--expanded) { display: none; }
}

/* Footer DSFR */
.fr-footer { background: #fff; border-top: 2px solid var(--blue-france); margin-top: 3rem; }
.fr-footer__body { display: flex; align-items: center; gap: 1.5rem; padding: 2rem 0 1rem; }
.fr-footer__brand { flex-shrink: 0; }
.fr-footer__content-desc { font-size: .875rem; color: #666; margin: 0; }
.fr-footer__bottom { padding: 1rem 0; border-top: 1px solid #ddd; }
.fr-footer__bottom-copy { font-size: .75rem; color: #666; }
.fr-footer__bottom-copy p { margin: 0; }

.sr-only,.fr-sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
</style>
</head>
<body>

<!-- Header DSFR institutionnel -->
<header class="fr-header">
  <div class="fr-header__body">
    <div class="fr-container">
      <div class="fr-header__body-row">
        <div class="fr-header__brand">
          <div>
            <p class="fr-logo">R\u00e9publique<br>Fran\u00e7aise</p>
          </div>
          <div>
            <p class="fr-header__service-title">Revue visuelle \u2014 ${echapper(config.projet || 'Projet')}</p>
            <p class="fr-header__service-tagline">${echapper(dateFR)} | ${resume.total} test(s), ${resume.pass} pass, ${resume.fail} fail, ${resume.erreur || 0} erreur(s)</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</header>
<a href="#contenu" class="sr-only">Aller au contenu</a>
<h1 class="sr-only">Revue visuelle \u2014 ${echapper(config.projet || 'Projet')}</h1>

<!-- Fil d'Ariane DSFR -->
<nav role="navigation" class="fr-breadcrumb" aria-label="vous \u00eates ici :">
  <button class="fr-breadcrumb__button" aria-expanded="false" aria-controls="breadcrumb-1" type="button">Voir le fil d'Ariane</button>
  <div class="fr-collapse fr-collapse--expanded" id="breadcrumb-1">
    <ol class="fr-breadcrumb__list" id="fil-ariane">
      <li><a class="fr-breadcrumb__link" href="#tab-tous">Tous les tests</a></li>
      <li><a class="fr-breadcrumb__link" aria-current="page">Tous (${resume.total})</a></li>
    </ol>
  </div>
</nav>

<main class="fr-container" id="contenu" style="padding-top:2rem;padding-bottom:5rem">

  <!-- R\u00e9sum\u00e9 -->
  <div class="fr-alert ${resume.fail > 0 ? 'fr-alert--error' : 'fr-alert--success'}" role="status">
    <h2 class="fr-alert__title">${resume.fail > 0 ? resume.fail + ' probl\u00e8me(s) d\u00e9tect\u00e9(s)' : 'Tous les tests passent'}</h2>
    <p>${resume.total} test\u00e9(s), ${resume.pass} pass, ${resume.fail} fail, ${resume.erreur || 0} erreur(s)</p>
  </div>

  <!-- Annonce resultats filtres (RGAA 7.3) -->
  <p class="sr-only" id="annonce-resultats" aria-live="polite" aria-atomic="true"></p>

  <!-- Recherche -->
  <div class="fr-search-bar" role="search">
    <label class="fr-label" for="recherche">Rechercher un test</label>
    <input class="fr-input" type="search" id="recherche" placeholder="Rechercher un test..." name="recherche" title="Rechercher un test par nom">
    <button class="fr-btn" title="Rechercher" type="button">Rechercher</button>
  </div>

  <!-- Onglets -->
  <div class="fr-tabs">
    <ul class="fr-tabs__list" role="tablist" aria-label="Filtrage des tests">
      <li role="presentation"><button type="button" class="fr-tabs__tab" role="tab" tabindex="0" aria-selected="true" aria-controls="tab-tous-panel" id="tab-tous">Tous (${resume.total})</button></li>
      <li role="presentation"><button type="button" class="fr-tabs__tab" role="tab" tabindex="-1" aria-selected="false" aria-controls="tab-pass-panel" id="tab-pass">Pass (${resume.pass})</button></li>
      <li role="presentation"><button type="button" class="fr-tabs__tab" role="tab" tabindex="-1" aria-selected="false" aria-controls="tab-fail-panel" id="tab-fail">Fail (${resume.fail})</button></li>
      ${paires.length > 0 ? '<li role="presentation"><button type="button" class="fr-tabs__tab" role="tab" tabindex="-1" aria-selected="false" aria-controls="tab-comparaison-panel" id="tab-comparaison">Avant/Apr\u00e8s (' + paires.length + ')</button></li>' : ''}
    </ul>
  </div>

  <p id="compteur-resultats" style="font-size:.875rem;color:#666;margin:var(--spacing-2v) 0">${resume.total} r\u00e9sultats</p>

  <div class="layout-deux-cols">
    <!-- Sidemenu categories -->
    <aside class="layout-deux-cols__aside">
      <nav class="fr-sidemenu" aria-labelledby="sidemenu-title">
        <div class="fr-sidemenu__inner">
          <p class="fr-sidemenu__title" id="sidemenu-title">Cat\u00e9gories</p>
          <ul class="fr-sidemenu__list">
            <li><button class="fr-sidemenu__item" aria-current="true" data-categorie="toutes" type="button">Toutes</button></li>
${categories.map(c => `            <li><button class="fr-sidemenu__item" data-categorie="${echapper(c)}" type="button">${echapper(c)}</button></li>`).join('\n')}
          </ul>
        </div>
      </nav>
    </aside>

    <!-- Contenu principal -->
    <div class="layout-deux-cols__main">
      <!-- Panel Tous -->
      <div class="fr-tabs__panel fr-tabs__panel--selected" id="tab-tous-panel" role="tabpanel" aria-labelledby="tab-tous" tabindex="0">
        <div class="fr-grid-row" id="grille-tous"></div>
      </div>
      <div class="fr-tabs__panel" id="tab-pass-panel" role="tabpanel" aria-labelledby="tab-pass" tabindex="0">
        <div class="fr-grid-row" id="grille-pass"></div>
      </div>
      <div class="fr-tabs__panel" id="tab-fail-panel" role="tabpanel" aria-labelledby="tab-fail" tabindex="0">
        <div class="fr-grid-row" id="grille-fail"></div>
      </div>
      ${paires.length > 0 ? '<div class="fr-tabs__panel" id="tab-comparaison-panel" role="tabpanel" aria-labelledby="tab-comparaison" tabindex="0"><div id="zone-comparaison"></div></div>' : ''}
    </div>
  </div>

<!-- Barre d'actions (multi-selection) -->
<div class="fr-action-bar" id="barre-actions" role="toolbar" aria-label="Actions sur les tests s\u00e9lectionn\u00e9s">
  <div class="fr-container">
    <div class="fr-action-bar__inner">
      <span class="fr-action-bar__count" id="compteur-selection" aria-live="polite">0 test s\u00e9lectionn\u00e9</span>
      <button class="fr-btn" id="btn-valider-rapport" type="button">Rapport de validation</button>
      <button class="fr-btn fr-btn--secondary" id="btn-copier-ids" type="button">Copier les identifiants</button>
      <button class="fr-btn fr-btn--secondary" id="btn-exporter" type="button">Exporter annotations</button>
      <button class="fr-btn fr-btn--secondary" id="btn-deselectionner" type="button">Effacer la s\u00e9lection</button>
    </div>
  </div>
</div>

</main>

<!-- Modal DSFR -->
<dialog id="modal-overlay" class="fr-modal" aria-labelledby="modal-titre" aria-modal="true">
  <div class="fr-container fr-container--fluid">
    <div class="fr-grid-row fr-grid-row--center">
      <div class="fr-col-12" style="max-width:56rem">
        <div class="fr-modal__body">
          <div class="fr-modal__header">
            <button aria-controls="modal-overlay" title="Fermer" type="button" id="modal-fermer" class="fr-btn--close fr-btn">Fermer</button>
          </div>
          <div class="fr-modal__content">
            <h3 id="modal-titre" class="fr-modal__title">D\u00e9tail du test</h3>
            <div id="modal-badge" style="margin-bottom:var(--spacing-2v)"></div>
            <details class="fr-accordion" open>
              <summary class="fr-accordion__btn">\u00c9tapes du test</summary>
              <div class="fr-collapse--expanded">
                <ol class="steps-list" id="modal-steps"></ol>
              </div>
            </details>
            <div class="screenshot-container" id="screenshot-container" style="margin-top:var(--spacing-4v)">
              <img id="modal-img" src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" alt="Capture du test">
              <canvas id="modal-canvas"></canvas>
            </div>
            <p style="font-size:.875rem;color:var(--blue-france);font-weight:500;margin-top:var(--spacing-2v)">Cliquer et dessiner pour annoter un probl\u00e8me</p>
          </div>
          <div class="fr-modal__footer">
            <ul class="fr-btns-group" style="list-style:none;margin:0;padding:0;display:flex;justify-content:space-between">
              <li><button type="button" class="fr-btn fr-btn--secondary" id="modal-precedent">Pr\u00e9c\u00e9dent</button></li>
              <li><button type="button" class="fr-btn fr-btn--secondary" id="modal-suivant">Suivant</button></li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  </div>
</dialog>

<!-- Donnees + logique -->
<script>
(function() {
  'use strict';
  var DATA = ${donneesJSON};
  var annotations = {};
  var selected = {};
  var categorieActive = 'toutes';
  var rechercheActive = '';
  var ongletActif = 'tous';

  // --- Rendu des cartes ---
  function badgeHTML(statut) {
    var map = { PASS: 'success', FAIL: 'error', ERREUR: 'warning', INSTABLE: 'info' };
    var cls = 'fr-badge--' + (map[statut] || 'warning');
    return '<p class="fr-badge ' + cls + '" style="margin:0">' + statut + '</p>';
  }

  function carteHTML(test, prefixe) {
    var capture = test.capture || '';
    var imgSrc = capture ? capture : '';
    var sel = selected[test.id] ? ' selected' : '';
    var checked = selected[test.id] ? ' checked' : '';
    var uid = (prefixe || 'a') + '-' + esc(test.id).replace(/[^a-z0-9]/gi,'-');
    return '<div class="fr-col-4" data-id="' + esc(test.id) + '" data-categorie="' + esc(test.categorie) + '" data-statut="' + esc(test.statut) + '">' +
      '<div class="fr-card fr-enlarge-link' + sel + '" data-statut="' + esc(test.statut) + '">' +
      '<div class="fr-card__body">' +
        '<div class="fr-card__content">' +
          '<h3 class="fr-card__title"><a href="#detail-' + uid + '" class="fr-card__link">' + esc(test.name) + '</a></h3>' +
          '<div class="fr-card__end">' + badgeHTML(test.statut) + '<span class="fr-card__detail">' + (test.duree || 0).toFixed(1) + 's</span></div>' +
        '</div>' +
      '</div>' +
      (imgSrc ? '<div class="fr-card__header"><div class="fr-card__img"><img class="fr-responsive-img" src="' + esc(imgSrc) + '" alt="" loading="lazy"></div>' +
        '<div class="fr-checkbox-group" style="position:absolute;top:.75rem;right:.75rem;z-index:2"><input type="checkbox" tabindex="-1" id="sel-' + uid + '"' + checked + '><label class="fr-label" for="sel-' + uid + '">S\u00e9lectionner ' + esc(test.name) + '</label></div>' +
      '</div>' : '') +
      '</div></div>';
  }

  function esc(s) {
    if (!s) return '';
    var d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }

  function filtrer(tests) {
    return tests.filter(function(t) {
      if (categorieActive !== 'toutes' && t.categorie !== categorieActive) return false;
      if (rechercheActive && t.name.toLowerCase().indexOf(rechercheActive) === -1 && t.id.toLowerCase().indexOf(rechercheActive) === -1) return false;
      return true;
    });
  }

  function annoncer(texte) {
    var el = document.getElementById('annonce-resultats');
    if (el) { el.textContent = ''; setTimeout(function() { el.textContent = texte; }, 100); }
  }

  function rendre() {
    var tous = filtrer(DATA.tests);
    var pass = tous.filter(function(t) { return t.statut === 'PASS'; });
    var fail = tous.filter(function(t) { return t.statut === 'FAIL' || t.statut === 'ERREUR' || t.statut === 'INSTABLE'; });

    // Annonce RGAA
    var ctx = categorieActive !== 'toutes' ? ' dans ' + categorieActive : '';
    if (rechercheActive) ctx += ', recherche "' + rechercheActive + '"';
    annoncer(tous.length + ' test' + (tous.length > 1 ? 's' : '') + ' affich\u00e9' + (tous.length > 1 ? 's' : '') + ctx);

    // Compteur visible
    var compteurVis = document.getElementById('compteur-resultats');
    if (compteurVis) {
      var ctxVis = categorieActive !== 'toutes' ? ' dans \u00ab ' + categorieActive + ' \u00bb' : '';
      compteurVis.textContent = tous.length + ' r\u00e9sultat' + (tous.length > 1 ? 's' : '') + ctxVis;
    }

    document.getElementById('grille-tous').innerHTML = tous.length ? tous.map(function(t) { return carteHTML(t, 'tous'); }).join('') : '<p style="padding:var(--spacing-4v);color:#666">Aucun test \u00e0 afficher</p>';
    document.getElementById('grille-pass').innerHTML = pass.length ? pass.map(function(t) { return carteHTML(t, 'pass'); }).join('') : '<p style="padding:var(--spacing-4v);color:#666">Aucun test pass</p>';
    document.getElementById('grille-fail').innerHTML = fail.length ? fail.map(function(t) { return carteHTML(t, 'fail'); }).join('') : '<p style="padding:var(--spacing-4v);color:#666">Aucun test en \u00e9chec</p>';

    rendreComparaison();
    attacherClicsCartes();
  }

  function rendreComparaison() {
    var zone = document.getElementById('zone-comparaison');
    if (!zone) return;
    if (!DATA.paires.length) return;
    zone.innerHTML = DATA.paires.map(function(p) {
      return '<div class="comparaison">' +
        '<div class="comparaison__col"><p class="comparaison__label">Avant (' + esc(p.date) + ')</p><img src="' + esc(p.avant) + '" alt="Avant ' + esc(p.base) + '"></div>' +
        '<div class="comparaison__col"><p class="comparaison__label">Apres (' + esc(p.date) + ')</p><img src="' + esc(p.apres) + '" alt="Apres ' + esc(p.base) + '"></div>' +
        '</div>';
    }).join('');
  }

  // --- Onglets ---
  // --- Onglets DSFR (APG Tabs pattern) ---
  var tabs = document.querySelectorAll('.fr-tabs__tab');
  function activerOnglet(tab) {
    tabs.forEach(function(t) { t.setAttribute('aria-selected', 'false'); t.setAttribute('tabindex', '-1'); });
    tab.setAttribute('aria-selected', 'true');
    tab.setAttribute('tabindex', '0');
    document.querySelectorAll('.fr-tabs__panel').forEach(function(p) { p.classList.remove('fr-tabs__panel--selected'); });
    var panelId = tab.getAttribute('aria-controls');
    var panel = document.getElementById(panelId);
    if (panel) panel.classList.add('fr-tabs__panel--selected');
    ongletActif = tab.id.replace('tab-', '');
    history.replaceState(null, '', '#' + tab.id);
  }
  tabs.forEach(function(tab) {
    tab.addEventListener('click', function() { activerOnglet(tab); });
    tab.addEventListener('keydown', function(e) {
      if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
        e.preventDefault();
        var idx = Array.from(tabs).indexOf(tab);
        var next = e.key === 'ArrowRight' ? (idx + 1) % tabs.length : (idx - 1 + tabs.length) % tabs.length;
        tabs[next].focus();
        activerOnglet(tabs[next]);
      }
    });
  });
  // Fil d'Ariane
  function majFilAriane() {
    var ol = document.getElementById('fil-ariane');
    if (!ol) return;
    var tabActif = document.querySelector('.fr-tabs__tab[aria-selected="true"]');
    var tabLabel = tabActif ? tabActif.textContent.trim() : 'Tous';
    var items = '<li><a class="fr-breadcrumb__link" href="#tab-tous">Tous les tests</a></li>';
    if (categorieActive !== 'toutes') {
      items += '<li><a class="fr-breadcrumb__link" href="#tab-tous">' + esc(categorieActive) + '</a></li>';
    }
    items += '<li><a class="fr-breadcrumb__link" aria-current="page">' + esc(tabLabel) + '</a></li>';
    ol.innerHTML = items;
  }

  // Enrichir activerOnglet pour MAJ fil d'Ariane
  var _activerOngletOrig = activerOnglet;
  activerOnglet = function(tab) { _activerOngletOrig(tab); majFilAriane(); };

  // Restaurer onglet depuis ancre URL
  if (location.hash) {
    var hashTab = document.getElementById(location.hash.substring(1));
    if (hashTab && hashTab.classList.contains('fr-tabs__tab')) activerOnglet(hashTab);
  }

  // --- Recherche ---
  document.getElementById('recherche').addEventListener('input', function(e) {
    rechercheActive = e.target.value.toLowerCase();
    rendre();
  });

  // --- Categories ---
  document.querySelectorAll('.fr-sidemenu__item').forEach(function(item) {
    item.addEventListener('click', function() {
      document.querySelectorAll('.fr-sidemenu__item').forEach(function(i) {
        i.removeAttribute('aria-current');
      });
      item.setAttribute('aria-current', 'true');
      categorieActive = item.getAttribute('data-categorie');
      history.replaceState(null, '', '#cat-' + categorieActive);
      rendre();
      majFilAriane();
    });
  });

  // --- Modal ---
  var overlay = document.getElementById('modal-overlay');
  var canvasEl = document.getElementById('modal-canvas');
  var imgEl = document.getElementById('modal-img');
  var testActif = null;
  var dessin = { actif: false, x1: 0, y1: 0 };

  function ouvrirModal(test) {
    testActif = test;
    document.getElementById('modal-titre').textContent = test.name;
    document.getElementById('modal-badge').innerHTML = badgeHTML(test.statut) +
      '<span style="margin-left:.5rem;font-size:.75rem;color:#666;font-family:monospace">' + esc(test.id) + '</span>' +
      (test.priority ? '<span style="margin-left:.5rem" class="fr-badge fr-badge--info">' + esc(test.priority) + '</span>' : '') +
      (test.url ? '<p style="font-size:.75rem;color:#666;margin:.5rem 0 0">' + esc(test.url) + '</p>' : '') +
      (test.description ? '<p style="font-size:.875rem;margin:.5rem 0 0">' + esc(test.description) + '</p>' : '');
    imgEl.src = test.capture || '';
    imgEl.alt = 'Capture de ' + test.name;

    // Steps : manifest (spec) + resultats (execution)
    var stepsHTML = '';
    var ms = test.manifest_steps || [];
    var rs = test.steps || [];
    if (ms.length > 0) {
      // Afficher les steps du manifest avec les resultats
      stepsHTML = ms.map(function(s, i) {
        var r = rs[i] || {};
        var cls = r.resultat === 'PASS' || r.resultat === 'OK' ? 'step-ok' : (r.resultat ? 'step-fail' : '');
        var detail = s.action;
        if (s.url) detail += ' <code>' + esc(s.url) + '</code>';
        if (s.target) detail += ' <code>' + esc(s.target) + '</code>';
        if (s.value) detail += ' = <code>' + esc(s.value) + '</code>';
        if (s.criteria) detail += ' : ' + esc(s.criteria);
        if (s.description) detail += ' <em>(' + esc(s.description) + ')</em>';
        var result = r.resultat ? ' <span style="color:#666">' + esc(r.resultat) + ' (' + (r.duree || 0).toFixed(1) + 's)</span>' : '';
        var li = '<li class="' + cls + '">' + detail + result;
        if (r.justification) li += '<br><span style="color:var(--blue-france);font-style:italic">' + esc(r.justification) + '</span>';
        return li + '</li>';
      }).join('');
    } else {
      // Fallback : resultats seuls
      stepsHTML = rs.map(function(s, i) {
        var cls = s.resultat === 'PASS' || s.resultat === 'OK' ? 'step-ok' : 'step-fail';
        var li = '<li class="' + cls + '"><strong>' + esc(s.action + ' ' + (s.detail || '')) + '</strong> <span style="color:#666">' + esc((s.resultat || '') + ' (' + (s.duree || 0).toFixed(1) + 's)') + '</span>';
        if (s.justification) li += '<br><span style="color:var(--blue-france);font-style:italic">' + esc(s.justification) + '</span>';
        return li + '</li>';
      }).join('');
    }
    document.getElementById('modal-steps').innerHTML = stepsHTML;

    // Navigation prev/next
    var testsFiltres = filtrer(DATA.tests);
    var idx = testsFiltres.findIndex(function(t) { return t.id === test.id; });
    document.getElementById('modal-precedent').disabled = idx <= 0;
    document.getElementById('modal-suivant').disabled = idx >= testsFiltres.length - 1;

    overlay.showModal();
    document.getElementById('modal-fermer').focus();

    imgEl.onload = function() { ajusterCanvas(); dessinerAnnotations(); };
    if (imgEl.complete) { ajusterCanvas(); dessinerAnnotations(); }
  }

  // Navigation prev/next
  document.getElementById('modal-precedent').addEventListener('click', function() {
    if (!testActif) return;
    var testsFiltres = filtrer(DATA.tests);
    var idx = testsFiltres.findIndex(function(t) { return t.id === testActif.id; });
    if (idx > 0) ouvrirModal(testsFiltres[idx - 1]);
  });
  document.getElementById('modal-suivant').addEventListener('click', function() {
    if (!testActif) return;
    var testsFiltres = filtrer(DATA.tests);
    var idx = testsFiltres.findIndex(function(t) { return t.id === testActif.id; });
    if (idx < testsFiltres.length - 1) ouvrirModal(testsFiltres[idx + 1]);
  });

  function fermerModal() {
    overlay.close();
    testActif = null;
  }

  document.getElementById('modal-fermer').addEventListener('click', fermerModal);
  overlay.addEventListener('click', function(e) { if (e.target === overlay) fermerModal(); });

  function majBarreActions() {
    var count = Object.keys(selected).length;
    var annCount = Object.keys(annotations).filter(function(k) { return annotations[k].length > 0; }).length;
    var barre = document.getElementById('barre-actions');
    var compteur = document.getElementById('compteur-selection');
    var btnExporter = document.getElementById('btn-exporter');
    if (count > 0 || annCount > 0) {
      barre.classList.add('visible');
      compteur.textContent = count > 0 ? count + ' test' + (count > 1 ? 's' : '') + ' s\u00e9lectionn\u00e9' + (count > 1 ? 's' : '') : annCount + ' annotation' + (annCount > 1 ? 's' : '');
    } else {
      barre.classList.remove('visible');
    }
    if (btnExporter) btnExporter.style.display = annCount > 0 ? '' : 'none';
  }

  function toggleSelection(id) {
    if (selected[id]) { delete selected[id]; } else { selected[id] = true; }
    // Mettre a jour visuellement
    document.querySelectorAll('[data-id="' + id + '"]').forEach(function(col) {
      var card = col.querySelector('.fr-card');
      var cb = col.querySelector('.fr-checkbox-group input');
      if (card) { if (selected[id]) card.classList.add('selected'); else card.classList.remove('selected'); }
      if (cb) cb.checked = !!selected[id];
    });
    majBarreActions();
  }

  function attacherClicsCartes() {
    document.querySelectorAll('.fr-col-4[data-id]').forEach(function(col) {
      var link = col.querySelector('.fr-card__link');
      var cb = col.querySelector('.fr-checkbox-group input');
      // Checkbox = selection (z-index au-dessus du lien enlarge)
      if (cb) {
        cb.addEventListener('click', function(e) { e.stopPropagation(); });
        cb.addEventListener('change', function() {
          var id = col.getAttribute('data-id');
          if (id) toggleSelection(id);
        });
      }
      // Lien carte = ouvrir la modale (intercepter le clic)
      if (link) {
        link.addEventListener('click', function(e) {
          e.preventDefault();
          var id = col.getAttribute('data-id');
          var test = DATA.tests.find(function(t) { return t.id === id; });
          if (test) ouvrirModal(test);
        });
      }
    });
  }

  // --- Annotation canvas ---
  function ajusterCanvas() {
    canvasEl.width = imgEl.naturalWidth || imgEl.width;
    canvasEl.height = imgEl.naturalHeight || imgEl.height;
  }

  function dessinerAnnotations() {
    var ctx = canvasEl.getContext('2d');
    ctx.clearRect(0, 0, canvasEl.width, canvasEl.height);
    if (!testActif) return;
    var rects = annotations[testActif.id] || [];
    ctx.strokeStyle = '#e1000f';
    ctx.lineWidth = 3;
    ctx.fillStyle = 'rgba(225,0,15,0.08)';
    rects.forEach(function(r) {
      var x = r.x1 * canvasEl.width;
      var y = r.y1 * canvasEl.height;
      var w = (r.x2 - r.x1) * canvasEl.width;
      var h = (r.y2 - r.y1) * canvasEl.height;
      ctx.fillRect(x, y, w, h);
      ctx.strokeRect(x, y, w, h);
    });
  }

  function posCanvas(e) {
    var rect = canvasEl.getBoundingClientRect();
    return {
      x: (e.clientX - rect.left) / rect.width,
      y: (e.clientY - rect.top) / rect.height
    };
  }

  canvasEl.addEventListener('mousedown', function(e) {
    var pos = posCanvas(e);
    dessin = { actif: true, x1: pos.x, y1: pos.y };
  });

  canvasEl.addEventListener('mousemove', function(e) {
    if (!dessin.actif) return;
    var pos = posCanvas(e);
    dessinerAnnotations();
    var ctx = canvasEl.getContext('2d');
    ctx.strokeStyle = '#e1000f';
    ctx.lineWidth = 2;
    ctx.setLineDash([5, 5]);
    var x = dessin.x1 * canvasEl.width;
    var y = dessin.y1 * canvasEl.height;
    var w = (pos.x - dessin.x1) * canvasEl.width;
    var h = (pos.y - dessin.y1) * canvasEl.height;
    ctx.strokeRect(x, y, w, h);
    ctx.setLineDash([]);
  });

  canvasEl.addEventListener('mouseup', function(e) {
    if (!dessin.actif || !testActif) return;
    var pos = posCanvas(e);
    dessin.actif = false;
    var rect = {
      x1: Math.min(dessin.x1, pos.x),
      y1: Math.min(dessin.y1, pos.y),
      x2: Math.max(dessin.x1, pos.x),
      y2: Math.max(dessin.y1, pos.y)
    };
    // Ignorer les rectangles trop petits (clic sans drag)
    if (Math.abs(rect.x2 - rect.x1) < 0.01 || Math.abs(rect.y2 - rect.y1) < 0.01) return;
    if (!annotations[testActif.id]) annotations[testActif.id] = [];
    annotations[testActif.id].push(rect);
    dessinerAnnotations();
  });

  // --- Export annotations ---
  document.getElementById('btn-exporter').addEventListener('click', function() {
    var export_data = Object.keys(annotations).map(function(id) {
      return { test: id, zones: annotations[id] };
    }).filter(function(a) { return a.zones.length > 0; });
    if (!export_data.length) { alert('Aucune annotation \u00e0 exporter'); return; }
    var json = JSON.stringify(export_data, null, 2);
    var blob = new Blob([json], { type: 'application/json' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = 'annotations-visuelles.json';
    a.click();
    URL.revokeObjectURL(url);
  });

  // --- Barre d'actions : 4 boutons ---

  // 1. Valider et generer rapport
  document.getElementById('btn-valider-rapport').addEventListener('click', function() {
    var ids = Object.keys(selected);
    if (!ids.length) { alert('S\u00e9lectionner des tests'); return; }
    var NL = String.fromCharCode(10);
    var rapport = '# Rapport de validation visuelle' + NL + NL;
    rapport += '**Date** : ' + new Date().toISOString().split('T')[0] + NL;
    rapport += '**Tests s\u00e9lectionn\u00e9s** : ' + ids.length + NL + NL + '---' + NL + NL;
    ids.forEach(function(id, i) {
      var t = DATA.tests.find(function(x) { return x.id === id; });
      if (!t) return;
      rapport += '## ' + (i + 1) + '. ' + t.name + NL + NL;
      rapport += '- **ID** : ' + t.id + NL;
      rapport += '- **Statut** : ' + t.statut + NL;
      rapport += '- **Duree** : ' + (t.duree || 0).toFixed(1) + 's' + NL;
      if (t.capture) rapport += '- **Capture** : ' + t.capture + NL;
      if (t.steps && t.steps.length) {
        rapport += NL + '| Etape | Action | Resultat | Justification |' + NL + '|-------|--------|----------|---------------|' + NL;
        t.steps.forEach(function(s, j) {
          rapport += '| ' + (j + 1) + ' | ' + s.action + ' | ' + (s.resultat || '') + ' | ' + (s.justification || '') + ' |' + NL;
        });
      }
      rapport += NL + '---' + NL + NL;
    });
    var blob = new Blob([rapport], { type: 'text/markdown' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url; a.download = 'rapport-validation-' + Date.now() + '.md'; a.click();
    URL.revokeObjectURL(url);
  });

  // 2. Copier les identifiants
  document.getElementById('btn-copier-ids').addEventListener('click', function() {
    var ids = Object.keys(selected).join(String.fromCharCode(10));
    if (!ids) { alert('S\u00e9lectionner des tests'); return; }
    if (navigator.clipboard) {
      navigator.clipboard.writeText(ids).then(function() {
        var btn = document.getElementById('btn-copier-ids');
        var orig = btn.textContent;
        btn.textContent = Object.keys(selected).length + ' ID(s) copi\u00e9(s)';
        setTimeout(function() { btn.textContent = orig; }, 1500);
      });
    } else {
      window.prompt('Copier ces IDs :', ids);
    }
  });

  // 4. Effacer la selection
  document.getElementById('btn-deselectionner').addEventListener('click', function() {
    selected = {};
    document.querySelectorAll('.fr-card.selected').forEach(function(c) { c.classList.remove('selected'); });
    document.querySelectorAll('.fr-checkbox-group input').forEach(function(cb) { cb.checked = false; });
    majBarreActions();
  });

  // --- Init ---
  rendre();
  majFilAriane();
  // Garantir qu'un onglet a tabindex=0 (RGAA)
  var tabActif = document.querySelector('.fr-tabs__tab[aria-selected="true"]');
  if (tabActif) tabActif.setAttribute('tabindex', '0');
})();
</script>


<!-- Pied de page DSFR -->
<footer class="fr-footer">
  <div class="fr-container">
    <div class="fr-footer__body">
      <div class="fr-footer__brand">
        <p class="fr-logo">R\u00e9publique<br>Fran\u00e7aise</p>
      </div>
      <div class="fr-footer__content">
        <p class="fr-footer__content-desc">Page de revue g\u00e9n\u00e9r\u00e9e par /revue-visuelle \u2014 Suite de test visuel PRD-091</p>
      </div>
    </div>
    <div class="fr-footer__bottom">
      <div class="fr-footer__bottom-copy">
        <p>Sauf mention explicite de propri\u00e9t\u00e9 intellectuelle d\u00e9tenue par des tiers, les contenus de ce site sont propos\u00e9s sous licence etalab-2.0</p>
      </div>
    </div>
  </div>
</footer>

</body>
</html>`;
}

// --- Serveur HTTP ---

function lancerServeur(dossier, port) {
  const mimeTypes = {
    '.html': 'text/html',
    '.css': 'text/css',
    '.js': 'application/javascript',
    '.json': 'application/json',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.svg': 'image/svg+xml',
  };

  const server = createServer((req, res) => {
    if (req.url === '/stop') {
      res.writeHead(200, { 'Content-Type': 'text/plain' });
      res.end('Serveur arrete');
      server.close();
      console.log('Serveur arrete');
      process.exit(0);
      return;
    }

    let fichier = req.url === '/' ? '/revue.html' : req.url;
    // Protection path traversal
    if (fichier.includes('..')) {
      res.writeHead(403);
      res.end('Interdit');
      return;
    }

    const chemin = join(dossier, fichier);
    if (!existsSync(chemin) || !statSync(chemin).isFile()) {
      res.writeHead(404);
      res.end('Non trouve');
      return;
    }

    const ext = extname(chemin);
    const mime = mimeTypes[ext] || 'application/octet-stream';
    res.writeHead(200, { 'Content-Type': mime });
    res.end(readFileSync(chemin));
  });

  server.listen(port, () => {
    console.log(`Serveur de revue : http://localhost:${port}`);
    console.log(`Arreter : curl http://localhost:${port}/stop`);
  });
}

// --- Main ---

function main() {
  const args = process.argv.slice(2);

  if (args.includes('--stop')) {
    const port = parseInt(args[args.indexOf('--stop') + 1]) || 3333;
    import('node:http').then(({ request }) => {
      const req = request({ hostname: 'localhost', port, path: '/stop', method: 'GET' }, (res) => {
        console.log('Serveur arrete');
        process.exit(0);
      });
      req.on('error', () => {
        console.error(`Aucun serveur sur le port ${port}`);
        process.exit(1);
      });
      req.end();
    });
    return;
  }

  const config = lireConfig();
  const resultats = lireResultats(config);
  const dossierCaptures = join(ROOT, '_resultats', 'captures');
  const paires = scannerAvantApres(dossierCaptures);
  const manifests = collecterManifests(ROOT);

  const html = genererHTML(config, resultats, paires, manifests);

  const sortie = join(ROOT, '_resultats', 'revue.html');
  writeFileSync(sortie, html, 'utf-8');
  console.log(`Page de revue generee : ${sortie}`);

  if (args.includes('--serve')) {
    const port = parseInt(args[args.indexOf('--serve') + 1]) || 3333;
    lancerServeur(join(ROOT, '_resultats'), port);
  }
}

main();

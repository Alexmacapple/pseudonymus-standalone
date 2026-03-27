/**
 * Interface DSFR pour la pseudonymisation locale.
 * Communique avec le serveur Python via fetch().
 */

const API = '';  // Meme origine

// --- Etat global ---
let correspondancesEnMemoire = [];
let dernierResultatImport = null;

// --- Navigation par hash ---

const PAGE_TITLES = {
    'pseudonymisation': 'Pseudonymisation',
    'correspondances': 'Correspondances',
    'restauration': 'Restauration',
    'import-fichier': 'Import fichier',
    'scoring-rgpd': 'Scoring RGPD',
    'documentation': 'Documentation',
};

const DEFAULT_PAGE = 'pseudonymisation';

const VIRTUAL_PAGES = {
    'import-local': {
        physicalPage: 'import-fichier',
        title: 'Import local',
        onActivate: () => {
            document.getElementById('import-source-local').checked = true;
            document.getElementById('import-upload-zone').hidden = true;
            document.getElementById('import-local-zone').hidden = false;
        }
    }
};

function navigateTo(pageId) {
    const virtual = VIRTUAL_PAGES[pageId];
    const realPageId = virtual ? virtual.physicalPage : pageId;

    if (!PAGE_TITLES[realPageId]) {
        pageId = DEFAULT_PAGE;
        return navigateTo(pageId);
    }

    // Masquer toutes les pages
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('[data-page]').forEach(l => l.removeAttribute('aria-current'));

    // Afficher la page physique
    const target = document.getElementById('page-' + realPageId);
    if (target) target.classList.add('active');

    // Mettre a jour la nav
    const navLink = document.querySelector(`[data-page="${pageId}"]`)
                 || document.querySelector(`[data-page="${realPageId}"]`);
    if (navLink) navLink.setAttribute('aria-current', 'page');

    // Mettre a jour le title
    const pageName = virtual ? virtual.title : PAGE_TITLES[realPageId];
    document.title = realPageId === DEFAULT_PAGE
        ? 'Pseudonymisation - Outil local'
        : pageName + ' - Pseudonymisation';

    // Mettre a jour le fil d'Ariane
    const breadcrumbList = document.getElementById('breadcrumb-list');
    if (realPageId === DEFAULT_PAGE) {
        breadcrumbList.innerHTML =
            '<li><a class="fr-breadcrumb__link" aria-current="page">Accueil</a></li>';
    } else {
        breadcrumbList.innerHTML =
            '<li><a class="fr-breadcrumb__link" href="#pseudonymisation">Accueil</a></li>' +
            '<li><a class="fr-breadcrumb__link" aria-current="page">' + escapeHtml(pageName) + '</a></li>';
    }

    // Activer le callback de la page virtuelle
    if (virtual && virtual.onActivate) {
        virtual.onActivate();
    }

    // Si navigation explicite vers import-fichier, remettre le mode upload
    if (pageId === 'import-fichier') {
        document.getElementById('import-source-upload').checked = true;
        document.getElementById('import-upload-zone').hidden = false;
        document.getElementById('import-local-zone').hidden = true;
    }

    // Reinitialiser les composants DSFR sur la page nouvellement visible
    if (window.dsfr) {
        window.dsfr.start();
    }
}

// Ecouter les changements de hash
window.addEventListener('hashchange', () => {
    const hash = window.location.hash.slice(1) || DEFAULT_PAGE;
    navigateTo(hash);
});

// Navigation initiale au chargement
(function() {
    const hash = window.location.hash.slice(1) || DEFAULT_PAGE;
    navigateTo(hash);
})();

// --- Page Pseudonymisation ---

document.getElementById('btn-pseudonymise').addEventListener('click', async () => {
    const texte = document.getElementById('input-texte').value.trim();
    if (!texte) {
        showAlert('alert-pseudo', 'Veuillez saisir du texte.', 'warning');
        return;
    }

    const fort = document.getElementById('mode-fort').checked;
    const tech = document.getElementById('opt-tech').checked;
    const nlp = document.getElementById('opt-nlp').checked;
    const whitelist = parseList(document.getElementById('input-whitelist').value);
    const blacklist = parseList(document.getElementById('input-blacklist').value);

    const btn = document.getElementById('btn-pseudonymise');
    btn.disabled = true;
    btn.textContent = 'Traitement...';

    try {
        const res = await fetch(API + '/api/pseudonymise-texte', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({texte, mode: 'pseudo', fort, tech, nlp, whitelist, blacklist}),
        });
        const data = await res.json();

        if (data.erreur) {
            showAlert('alert-pseudo', 'Erreur : ' + data.erreur, 'error');
            return;
        }

        document.getElementById('output-texte').value = data.texte_pseudonymise;
        correspondancesEnMemoire = data.correspondances;

        const total = data.stats.total;
        const niveau = data.score.niveau;
        showAlert('alert-pseudo',
            total + ' remplacement(s) effectué(s). Score RGPD : ' + data.score.total + ' (' + niveau + ').',
            'success');

        // Mettre a jour la page correspondances
        renderCorrespondances();
    } catch (err) {
        showAlert('alert-pseudo', 'Erreur de connexion au serveur : ' + err.message, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Pseudonymiser';
    }
});

document.getElementById('btn-clear').addEventListener('click', () => {
    document.getElementById('input-texte').value = '';
    document.getElementById('output-texte').value = '';
    hideAlert('alert-pseudo');
});

// --- Page Correspondances ---

const ITEMS_PER_PAGE = 20;
let correspondancesPage = 1;
let correspondancesFiltrees = [];

function renderCorrespondances() {
    const vide = document.getElementById('correspondances-vide');
    const content = document.getElementById('correspondances-content');

    if (!correspondancesEnMemoire.length) {
        vide.hidden = false;
        content.hidden = true;
        return;
    }

    vide.hidden = true;
    content.hidden = false;

    correspondancesFiltrees = [...correspondancesEnMemoire];
    correspondancesPage = 1;
    renderCorrespondancesTable();
}

function renderCorrespondancesTable() {
    const filtre = document.getElementById('search-correspondances').value.toLowerCase();
    const filtered = correspondancesFiltrees.filter(c =>
        c.type.toLowerCase().includes(filtre) ||
        c.jeton.toLowerCase().includes(filtre) ||
        c.valeur.toLowerCase().includes(filtre)
    );

    const tbody = document.getElementById('tbody-correspondances');
    const totalPages = Math.max(1, Math.ceil(filtered.length / ITEMS_PER_PAGE));
    if (correspondancesPage > totalPages) correspondancesPage = totalPages;

    const start = (correspondancesPage - 1) * ITEMS_PER_PAGE;
    const pageItems = filtered.slice(start, start + ITEMS_PER_PAGE);

    tbody.innerHTML = pageItems.map(c =>
        '<tr><td>' + escapeHtml(c.type) + '</td>' +
        '<td><code>' + escapeHtml(c.jeton) + '</code></td>' +
        '<td>' + escapeHtml(c.valeur) + '</td></tr>'
    ).join('');

    // Compteur de resultats
    document.getElementById('correspondances-count').textContent =
        filtered.length + ' correspondance' + (filtered.length > 1 ? 's' : '');

    renderPagination(totalPages, filtered.length);
}

function renderPagination(totalPages, totalItems) {
    const ul = document.getElementById('pagination-correspondances');
    if (totalPages <= 1) {
        ul.innerHTML = '';
        return;
    }

    let html = '';
    // Precedent
    if (correspondancesPage > 1) {
        html += '<li><a class="fr-pagination__link fr-pagination__link--prev" href="#" data-page-num="' +
            (correspondancesPage - 1) + '" aria-label="Page précédente">Précédent</a></li>';
    }

    // Pages
    for (let i = 1; i <= totalPages; i++) {
        if (totalPages > 7 && i > 3 && i < totalPages - 2 && Math.abs(i - correspondancesPage) > 1) {
            if (i === 4 || i === totalPages - 3) {
                html += '<li><span class="fr-pagination__link">...</span></li>';
            }
            continue;
        }
        if (i === correspondancesPage) {
            html += '<li><a class="fr-pagination__link" href="#" data-page-num="' + i +
                '" aria-current="page" aria-label="Page ' + i + '">' + i + '</a></li>';
        } else {
            html += '<li><a class="fr-pagination__link" href="#" data-page-num="' + i +
                '" aria-label="Page ' + i + '">' + i + '</a></li>';
        }
    }

    // Suivant
    if (correspondancesPage < totalPages) {
        html += '<li><a class="fr-pagination__link fr-pagination__link--next" href="#" data-page-num="' +
            (correspondancesPage + 1) + '" aria-label="Page suivante">Suivant</a></li>';
    }

    ul.innerHTML = html;

    ul.querySelectorAll('[data-page-num]').forEach(link => {
        link.addEventListener('click', e => {
            e.preventDefault();
            const num = parseInt(link.dataset.pageNum);
            if (num >= 1 && num <= totalPages) {
                correspondancesPage = num;
                renderCorrespondancesTable();
            }
        });
    });
}

document.getElementById('search-correspondances').addEventListener('input', () => {
    correspondancesPage = 1;
    renderCorrespondancesTable();
});

document.getElementById('btn-export-csv').addEventListener('click', () => {
    if (!correspondancesEnMemoire.length) return;
    let csv = 'type;jeton;valeur_originale\n';
    correspondancesEnMemoire.forEach(c => {
        csv += escapeCSV(c.type) + ';' + escapeCSV(c.jeton) + ';' + escapeCSV(c.valeur) + '\n';
    });
    downloadBlob(csv, 'correspondances.csv', 'text/csv;charset=utf-8');
});

// --- Page Restauration ---

let correspondancesCsv = [];

document.getElementById('upload-correspondances').addEventListener('change', e => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
        correspondancesCsv = parseCorrespondancesCsv(reader.result);
        document.getElementById('restauration-source-info').textContent =
            correspondancesCsv.length + ' correspondances chargées depuis ' + file.name;
    };
    reader.readAsText(file);
});

document.getElementById('btn-restaurer').addEventListener('click', async () => {
    const source = correspondancesCsv.length ? correspondancesCsv : correspondancesEnMemoire;
    await restaurer(source);
});

document.getElementById('btn-restaurer-auto').addEventListener('click', async () => {
    await restaurer(correspondancesEnMemoire);
});

async function restaurer(correspondances) {
    const texte = document.getElementById('input-restauration').value.trim();
    if (!texte) {
        showAlert('alert-restauration', 'Veuillez saisir du texte pseudonymisé.', 'warning');
        return;
    }
    if (!correspondances.length) {
        showAlert('alert-restauration', 'Aucune correspondance disponible. Chargez un CSV ou lancez une pseudonymisation.', 'warning');
        return;
    }

    try {
        const res = await fetch(API + '/api/depseudonymise', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({texte, correspondances}),
        });
        const data = await res.json();

        if (data.erreur) {
            showAlert('alert-restauration', 'Erreur : ' + data.erreur, 'error');
            return;
        }

        document.getElementById('output-restauration').value = data.texte_original;
        showAlert('alert-restauration', data.remplacements + ' jeton(s) restauré(s).', 'success');
    } catch (err) {
        showAlert('alert-restauration', 'Erreur de connexion : ' + err.message, 'error');
    }
}

// --- Page Import fichier ---

// Bascule upload / chemin local
document.querySelectorAll('input[name="import-source"]').forEach(radio => {
    radio.addEventListener('change', () => {
        const isLocal = document.getElementById('import-source-local').checked;
        document.getElementById('import-upload-zone').hidden = isLocal;
        document.getElementById('import-local-zone').hidden = !isLocal;
        const newPage = isLocal ? 'import-local' : 'import-fichier';
        history.replaceState(null, '', '#' + newPage);
        // Synchroniser la nav active
        document.querySelectorAll('[data-page]').forEach(l => l.removeAttribute('aria-current'));
        const navLink = document.querySelector(`[data-page="${newPage}"]`);
        if (navLink) navLink.setAttribute('aria-current', 'page');
        // Synchroniser le titre et fil d'Ariane
        const virtual = VIRTUAL_PAGES[newPage];
        const pageName = virtual ? virtual.title : PAGE_TITLES[newPage];
        document.title = pageName + ' - Pseudonymisation';
        const breadcrumbList = document.getElementById('breadcrumb-list');
        breadcrumbList.innerHTML =
            '<li><a class="fr-breadcrumb__link" href="#pseudonymisation">Accueil</a></li>' +
            '<li><a class="fr-breadcrumb__link" aria-current="page">' + escapeHtml(pageName) + '</a></li>';
    });
});

// Bouton "Proposition de mapping automatique"
document.getElementById('btn-analyze').addEventListener('click', async () => {
    const isLocal = document.getElementById('import-source-local').checked;
    let filepath = '';

    let fetchOptions;

    if (isLocal) {
        filepath = document.getElementById('input-filepath').value.trim();
        if (!filepath) {
            showAlert('alert-import', 'Veuillez saisir le chemin du fichier à analyser.', 'warning');
            return;
        }
        fetchOptions = {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({path: filepath}),
        };
    } else {
        const fileInput = document.getElementById('upload-fichier');
        const file = fileInput.files[0];
        if (!file) {
            showAlert('alert-import', 'Veuillez sélectionner un fichier à analyser.', 'warning');
            return;
        }
        const formData = new FormData();
        formData.append('file', file, file.name);
        formData.append('filename', file.name);
        fetchOptions = {
            method: 'POST',
            body: formData,
        };
    }

    const btn = document.getElementById('btn-analyze');
    btn.disabled = true;
    btn.textContent = 'Analyse...';

    try {
        const res = await fetch(API + '/api/mapping/generate', fetchOptions);
        const data = await res.json();

        if (data.erreur) {
            showAlert('alert-import', 'Erreur : ' + data.erreur, 'error');
            return;
        }

        // Pre-remplir le textarea avec le mapping genere
        document.getElementById('import-mapping').value = JSON.stringify(data.mapping, null, 2);

        const a = data.analyse;
        showAlert('alert-import',
            'Structure analysée : ' + a.cles_totales + ' clés, ' +
            a.champs_detectes + ' champs sensibles détectés, ' +
            a.texte_libre_detecte + ' champs texte libre.' +
            (a.structure_unwrap ? ' Structure JSON imbriqué détectée.' : '') +
            ' Vérifiez le mapping avant de lancer le traitement.',
            'info');
    } catch (err) {
        showAlert('alert-import', 'Erreur : ' + err.message, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Proposition de mapping automatique';
    }
});

document.getElementById('upload-mapping').addEventListener('change', e => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
        document.getElementById('import-mapping').value = reader.result;
    };
    reader.readAsText(file);
});

document.getElementById('btn-import').addEventListener('click', async () => {
    const isLocal = document.getElementById('import-source-local').checked;

    const mappingText = document.getElementById('import-mapping').value.trim();
    const hasMappingPath = isLocal && document.getElementById('input-mappingpath').value.trim();

    if (!mappingText && !hasMappingPath) {
        showAlert('alert-import', 'Veuillez fournir un mapping (textarea, fichier, ou chemin local).', 'warning');
        return;
    }

    let mapping = {};
    if (mappingText) {
        try {
            mapping = JSON.parse(mappingText);
        } catch {
            showAlert('alert-import', 'Le mapping n\'est pas un JSON valide.', 'error');
            return;
        }
    }

    const mode = document.querySelector('input[name="import-mode"]:checked').value;
    const fort = document.getElementById('import-fort').checked;

    const btn = document.getElementById('btn-import');
    btn.disabled = true;
    btn.textContent = 'Traitement en cours...';

    const progress = document.getElementById('import-progress');
    progress.hidden = false;

    try {
        let data;

        if (isLocal) {
            // --- Mode chemin local ---
            const filepath = document.getElementById('input-filepath').value.trim();
            if (!filepath) {
                showAlert('alert-import', 'Veuillez saisir le chemin du fichier.', 'warning');
                return;
            }

            const mappingPath = document.getElementById('input-mappingpath').value.trim();
            const isBatch = document.getElementById('import-batch') && document.getElementById('import-batch').checked;

            document.getElementById('import-progress-text').textContent = isBatch ? 'Traitement du dossier...' : 'Traitement en cours...';
            document.getElementById('import-progress-bar').removeAttribute('value');

            const nlp = document.getElementById('import-nlp').checked;
            const tech = document.getElementById('import-tech').checked;
            const payload = {path: filepath, mode, fort, nlp, tech};
            if (mappingPath && !mappingText) {
                payload.mapping_path = mappingPath;
            } else {
                payload.mapping = mapping;
            }

            const endpoint = isBatch ? '/api/pseudonymise-batch' : '/api/pseudonymise-local';
            const res = await fetch(API + endpoint, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload),
            });
            data = await res.json();

            // Affichage batch
            if (isBatch && data.fichiers) {
                document.getElementById('import-progress-bar').value = 100;
                document.getElementById('import-progress-bar').max = 100;
                document.getElementById('import-progress-text').textContent = 'Terminé.';

                if (data.erreur) {
                    showAlert('alert-import', 'Erreur : ' + data.erreur, 'error');
                    return;
                }

                document.getElementById('batch-result').hidden = false;
                document.getElementById('import-result').hidden = true;

                const r = data.resume;
                document.getElementById('batch-summary').textContent =
                    r.fichiers_traites + ' fichiers traités, ' + r.fichiers_en_erreur + ' en erreur, ' +
                    r.total_enregistrements + ' enregistrements, ' + r.total_remplacements + ' remplacements.';

                const tbody = document.getElementById('tbody-batch');
                tbody.innerHTML = data.fichiers.map(f => {
                    if (f.statut === 'erreur') {
                        return '<tr class="fr-text--error"><td>' + escapeHtml(f.nom) + '</td><td>Erreur</td>' +
                            '<td colspan="3">' + escapeHtml(f.erreur) + '</td></tr>';
                    }
                    return '<tr><td>' + escapeHtml(f.nom) + '</td><td>OK</td>' +
                        '<td>' + f.total + '</td><td>' + f.remplacements + '</td><td>' + f.score + '</td></tr>';
                }).join('');

                showAlert('alert-import', r.fichiers_traites + ' fichiers traités avec succès.', 'success');
                return;
            }

        } else {
            // --- Mode upload classique (petits fichiers) ---
            const fileInput = document.getElementById('upload-fichier');
            const file = fileInput.files[0];
            if (!file) {
                showAlert('alert-import', 'Veuillez sélectionner un fichier.', 'warning');
                return;
            }

            document.getElementById('import-progress-text').textContent = 'Envoi du fichier...';
            document.getElementById('import-progress-bar').removeAttribute('value');

            const formData = new FormData();
            formData.append('file', file, file.name);
            formData.append('mapping', JSON.stringify(mapping));
            formData.append('mode', mode);
            formData.append('fort', fort);
            formData.append('nlp', document.getElementById('import-nlp').checked);
            formData.append('tech', document.getElementById('import-tech').checked);
            formData.append('filename', file.name);

            document.getElementById('import-progress-text').textContent = 'Traitement en cours...';

            const res = await fetch(API + '/api/pseudonymise', {
                method: 'POST',
                body: formData,
            });
            data = await res.json();
        }

        document.getElementById('import-progress-bar').value = 100;
        document.getElementById('import-progress-bar').max = 100;

        if (data.erreur) {
            showAlert('alert-import', 'Erreur : ' + data.erreur, 'error');
            return;
        }

        dernierResultatImport = data;
        correspondancesEnMemoire = data.correspondances;

        // Afficher les stats
        document.getElementById('import-result').hidden = false;
        document.getElementById('import-stat-total').textContent = data.total;
        document.getElementById('import-stat-remplacements').textContent = data.stats.total;
        document.getElementById('import-stat-score').textContent = data.score.total + ' (' + data.score.niveau + ')';

        document.getElementById('import-progress-text').textContent = 'Terminé.';
        let msg = data.total + ' enregistrements traités, ' + data.stats.total + ' remplacements.';
        if (data.output_path) {
            msg += ' Fichier : ' + data.output_path;
            document.getElementById('btn-download-result').textContent = 'Télécharger le zip';
        } else {
            document.getElementById('btn-download-result').textContent = 'Télécharger le résultat';
        }
        if (data.csv_path) {
            msg += ' | Correspondances : ' + data.csv_path;
        }
        showAlert('alert-import', msg, 'success');

        renderCorrespondances();
    } catch (err) {
        showAlert('alert-import', 'Erreur : ' + err.message, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Lancer le traitement';
    }
});

// --- Bouton Previsualiser (dry-run) ---

document.getElementById('btn-preview').addEventListener('click', async () => {
    const isLocal = document.getElementById('import-source-local').checked;

    const mappingText = document.getElementById('import-mapping').value.trim();
    const hasMappingPath = isLocal && document.getElementById('input-mappingpath').value.trim();

    if (!mappingText && !hasMappingPath) {
        showAlert('alert-import', 'Veuillez fournir un mapping pour la prévisualisation.', 'warning');
        return;
    }

    let mapping = {};
    if (mappingText) {
        try {
            mapping = JSON.parse(mappingText);
        } catch {
            showAlert('alert-import', 'Le mapping n\'est pas un JSON valide.', 'error');
            return;
        }
    }

    const fort = document.getElementById('import-fort').checked;
    const nlp = document.getElementById('import-nlp').checked;
    const tech = document.getElementById('import-tech').checked;

    const btn = document.getElementById('btn-preview');
    btn.disabled = true;
    btn.textContent = 'Analyse...';

    // Masquer les anciens resultats
    document.getElementById('preview-result').hidden = true;
    document.getElementById('import-result').hidden = true;

    try {
        let data;

        if (isLocal) {
            const filepath = document.getElementById('input-filepath').value.trim();
            if (!filepath) {
                showAlert('alert-import', 'Veuillez saisir le chemin du fichier.', 'warning');
                return;
            }
            const mappingPath = document.getElementById('input-mappingpath').value.trim();
            const isBatch = document.getElementById('import-batch') && document.getElementById('import-batch').checked;
            const payload = {path: filepath, mode: 'pseudo', fort, nlp, tech, dry_run: true};
            if (mappingPath && !mappingText) {
                payload.mapping_path = mappingPath;
            } else {
                payload.mapping = mapping;
            }
            const endpoint = isBatch ? '/api/pseudonymise-batch' : '/api/pseudonymise-local';
            const res = await fetch(API + endpoint, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload),
            });
            data = await res.json();

            // Batch dry-run : affichage specifique
            if (isBatch && data.fichiers) {
                const previewResult = document.getElementById('preview-result');
                previewResult.hidden = false;
                const f = data.fichiers[0] || {};
                const detectes = (data.fichiers_detectes || []).length;
                document.getElementById('preview-summary').textContent =
                    detectes + ' fichiers détectés. Prévisualisation sur ' + (f.nom || '?') + ' : ' +
                    (f.total || 0) + ' enregistrements, ' + (f.remplacements || 0) + ' remplacements, Score RGPD ' + (f.score || 0);
                const correspondances = f.correspondances || [];
                const tbody = document.getElementById('tbody-preview');
                tbody.innerHTML = correspondances.slice(0, 10).map(c =>
                    '<tr><td>' + escapeHtml(c.type) + '</td>' +
                    '<td>' + escapeHtml(c.valeur) + '</td>' +
                    '<td><code>' + escapeHtml(c.jeton) + '</code></td></tr>'
                ).join('');
                showAlert('alert-import', 'Prévisualisation batch (dry-run). ' + detectes + ' fichiers détectés. Aucun fichier écrit.', 'info');
                return;
            }
        } else {
            const fileInput = document.getElementById('upload-fichier');
            const file = fileInput.files[0];
            if (!file) {
                showAlert('alert-import', 'Veuillez sélectionner un fichier.', 'warning');
                return;
            }
            const formData = new FormData();
            formData.append('file', file, file.name);
            formData.append('mapping', JSON.stringify(mapping));
            formData.append('mode', 'pseudo');
            formData.append('fort', fort);
            formData.append('nlp', nlp);
            formData.append('tech', tech);
            formData.append('dry_run', 'true');
            formData.append('filename', file.name);

            const res = await fetch(API + '/api/pseudonymise', {
                method: 'POST',
                body: formData,
            });
            data = await res.json();
        }

        if (data.erreur) {
            showAlert('alert-import', 'Erreur : ' + data.erreur, 'error');
            return;
        }

        // Afficher le resultat de previsualisation
        const previewResult = document.getElementById('preview-result');
        previewResult.hidden = false;

        const traites = data.traites || 0;
        const totalRemp = data.stats ? data.stats.total : 0;
        const score = data.score ? data.score.total : 0;
        const niveau = data.score ? data.score.niveau : '';

        document.getElementById('preview-summary').textContent =
            traites + ' enregistrements testés (sur ' + (data.total || '?') + '), ' +
            totalRemp + ' remplacements détectés. Score RGPD : ' + score + ' (' + niveau + ')';

        // Apercu par fiche (cards DSFR)
        const fiches = data.apercu_fiches || [];
        const recordsDiv = document.getElementById('preview-records');

        if (fiches.length > 0) {
            let html = '<div class="fr-grid-row fr-grid-row--gutters">';
            for (const fiche of fiches) {
                const modifies = fiche.champs.filter(c => c.modifie);
                if (modifies.length === 0) continue;
                html += '<div class="fr-col-12 fr-col-md-6">';
                html += '<div class="fr-card fr-card--no-arrow">';
                html += '<div class="fr-card__body">';
                html += '<div class="fr-card__content">';
                html += '<h4 class="fr-card__title">Fiche ' + fiche.index + '</h4>';
                html += '<div class="fr-card__desc">';
                for (const c of modifies) {
                    const label = c.jeton ? c.jeton : c.type;
                    if (c.type === 'texte_libre') {
                        html += '<p class="fr-mb-1w"><strong>' + escapeHtml(c.champ) + '</strong> ' +
                            '<span class="fr-badge fr-badge--sm fr-badge--purple-glycine">texte libre</span><br>' +
                            '<span style="color:var(--text-mention-grey)">' + escapeHtml(c.avant) + '</span><br>' +
                            '→ <code>' + escapeHtml(c.apres) + '</code></p>';
                    } else {
                        html += '<p class="fr-mb-1w"><strong>' + escapeHtml(c.champ) + '</strong> ' +
                            '<span class="fr-badge fr-badge--sm fr-badge--blue-cumulus">' + escapeHtml(label) + '</span><br>' +
                            '<span style="color:var(--text-mention-grey)">' + escapeHtml(c.avant) + '</span>' +
                            ' → <code>' + escapeHtml(c.apres) + '</code></p>';
                    }
                }
                html += '</div></div></div></div></div>';
            }
            html += '</div>';
            recordsDiv.innerHTML = html;
        } else {
            recordsDiv.innerHTML = '<p class="fr-text--sm" style="color:var(--text-mention-grey)">Aucune modification détectée dans les 5 premiers enregistrements.</p>';
        }


        showAlert('alert-import',
            'Prévisualisation terminée (dry-run). Aucun fichier écrit. Cliquez sur « Lancer le traitement » pour tout traiter.',
            'info');
    } catch (err) {
        showAlert('alert-import', 'Erreur : ' + err.message, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Prévisualiser 10 fiches';
    }
});

document.getElementById('btn-download-result').addEventListener('click', () => {
    if (!dernierResultatImport) return;
    if (dernierResultatImport.zip_path) {
        // Mode local : telecharger le zip via le serveur
        window.location.href = API + '/api/download?path=' + encodeURIComponent(dernierResultatImport.zip_path);
        return;
    }
    if (dernierResultatImport.output_path) {
        // Fallback : telecharger le fichier seul
        window.location.href = API + '/api/download?path=' + encodeURIComponent(dernierResultatImport.output_path);
        return;
    }
    const json = JSON.stringify(dernierResultatImport.data, null, 2);
    downloadBlob(json, 'resultat_pseudo.json', 'application/json');
});

document.getElementById('btn-download-correspondances').addEventListener('click', () => {
    if (!correspondancesEnMemoire.length) return;
    document.getElementById('btn-export-csv').click();
});

// --- Page Scoring RGPD ---

document.getElementById('btn-score').addEventListener('click', async () => {
    const texte = document.getElementById('input-scoring').value.trim();
    if (!texte) {
        return;
    }

    const fort = document.getElementById('score-fort').checked;
    const btn = document.getElementById('btn-score');
    btn.disabled = true;

    try {
        const res = await fetch(API + '/api/score', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({texte, fort}),
        });
        const data = await res.json();

        if (data.erreur) return;

        document.getElementById('scoring-result').hidden = false;

        // Badge niveau
        const badge = document.getElementById('score-badge');
        const niveau = data.score.niveau;
        badge.textContent = niveau;
        badge.className = 'fr-badge fr-badge--' + niveau.toLowerCase()
            .replace('modere', 'modere').normalize('NFD').replace(/[\u0300-\u036f]/g, '');

        document.getElementById('score-value').textContent = data.score.total;

        // Tableau categories
        const points = {finance: 5, direct: 3, tech: 2, indirect: 1};
        const tbody = document.getElementById('tbody-scoring');
        tbody.innerHTML = ['direct', 'finance', 'tech', 'indirect'].map(cat => {
            const count = data.score.details[cat] || 0;
            const pts = points[cat];
            return '<tr><td>' + cat.charAt(0).toUpperCase() + cat.slice(1) + '</td>' +
                '<td>' + pts + '</td><td>' + count + '</td>' +
                '<td>' + (count * pts) + '</td></tr>';
        }).join('');

        // Tableau details
        const tbodyD = document.getElementById('tbody-scoring-details');
        const stats = data.stats;
        tbodyD.innerHTML = Object.keys(stats.remplacements).sort().map(type => {
            const count = stats.remplacements[type];
            const samples = (stats.echantillons[type] || [])
                .map(s => escapeHtml(s.original)).join(', ');
            return '<tr><td>' + escapeHtml(type) + '</td><td>' + count + '</td>' +
                '<td>' + samples + '</td></tr>';
        }).join('');
    } catch (err) {
        console.error(err);
    } finally {
        btn.disabled = false;
    }
});

// --- Modale informations serveur ---

// Ouverture de la modale serveur
const modalServeur = document.getElementById('modal-serveur');
const btnOpenModal = document.querySelector('[aria-controls="modal-serveur"]');
const btnCloseModal = document.getElementById('modal-serveur-close');

function openModal() {
    if (!modalServeur) return;
    modalServeur.showModal();
    loadServerInfo();
}
function closeModal() {
    if (!modalServeur) return;
    modalServeur.close();
}

if (btnOpenModal) btnOpenModal.addEventListener('click', openModal);
if (btnCloseModal) btnCloseModal.addEventListener('click', closeModal);
if (modalServeur) {
    modalServeur.addEventListener('click', (e) => {
        if (e.target === modalServeur) closeModal();
    });
}

async function loadServerInfo() {
    const container = document.getElementById('modal-serveur-content');
    container.innerHTML = '<p>Chargement...</p>';

    try {
        const [healthRes, statsRes] = await Promise.all([
            fetch(API + '/api/health'),
            fetch(API + '/api/stats'),
        ]);
        const health = await healthRes.json();
        const stats = await statsRes.json();
        const dict = stats.dictionnaires || {};

        const statusBadge = health.status === 'ok'
            ? '<span class="fr-badge fr-badge--success fr-badge--no-icon">En ligne</span>'
            : '<span class="fr-badge fr-badge--error fr-badge--no-icon">Erreur</span>';

        container.innerHTML = `
            <div class="fr-table fr-mt-2w">
                <table>
                    <caption>Informations techniques</caption>
                    <tbody>
                        <tr><td><strong>Statut</strong></td><td>${statusBadge}</td></tr>
                        <tr><td><strong>Version</strong></td><td>v3.3.0</td></tr>
                        <tr><td><strong>Adresse</strong></td><td><code>${window.location.origin}</code></td></tr>
                        <tr><td><strong>Formats supportés</strong></td><td>JSON, CSV, TSV, XLSX, XLS, ODS, DOCX, ODT, PDF, TXT, MD</td></tr>
                        <tr><td><strong>Patronymes INSEE</strong></td><td>${(dict.patronymes || 0).toLocaleString('fr-FR')}</td></tr>
                        <tr><td><strong>Prénoms INSEE</strong></td><td>${(dict.prenoms || 0).toLocaleString('fr-FR')}</td></tr>
                        <tr><td><strong>Stopwords capitalisés</strong></td><td>${(dict.stopwords_cap || 0).toLocaleString('fr-FR')}</td></tr>
                        <tr><td><strong>Stopwords minuscules</strong></td><td>${(dict.stopwords_min || 0).toLocaleString('fr-FR')}</td></tr>
                        <tr><td><strong>Villes françaises</strong></td><td>${(dict.villes || 0).toLocaleString('fr-FR')}</td></tr>
                        <tr><td><strong>Mots organisations</strong></td><td>${(dict.organisations || 0).toLocaleString('fr-FR')}</td></tr>
                    </tbody>
                </table>
            </div>
            <p class="fr-text--sm fr-mt-2w">Traitement 100 % local. Aucune donnée ne quitte votre machine.</p>
        `;
    } catch (err) {
        container.innerHTML = '<div class="fr-alert fr-alert--error"><p>Impossible de contacter le serveur : ' + escapeHtml(err.message) + '</p></div>';
    }
}

// --- Utilitaires ---

function showAlert(id, message, type) {
    const el = document.getElementById(id);
    el.hidden = false;
    el.className = 'fr-alert fr-alert--' + type + ' fr-my-2w';
    el.innerHTML = '<p>' + escapeHtml(message) + '</p>';
}

function hideAlert(id) {
    document.getElementById(id).hidden = true;
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function escapeCSV(str) {
    if (str.includes(';') || str.includes('"') || str.includes('\n')) {
        return '"' + str.replace(/"/g, '""') + '"';
    }
    return str;
}

function parseList(str) {
    return str.split(',').map(s => s.trim()).filter(Boolean);
}

function parseCorrespondancesCsv(text) {
    const lines = text.split('\n').filter(l => l.trim());
    if (lines.length < 2) return [];
    return lines.slice(1).map(line => {
        const parts = line.split(';');
        if (parts.length >= 3) {
            return {type: parts[0], jeton: parts[1], valeur: parts[2]};
        }
        return null;
    }).filter(Boolean);
}

function downloadBlob(content, filename, type) {
    const blob = new Blob([content], {type});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
}

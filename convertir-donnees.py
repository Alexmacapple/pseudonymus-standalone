#!/usr/bin/env python3
"""
Regenere les fichiers de donnees statiques dans data/.

Les fichiers noms.json et prenoms.json sont des donnees de reference
immuables livrees avec le projet — ils ne sont pas regeneres par ce script.

Usage :
    python3 convertir-donnees.py
"""

import json
import os
import sys

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')

os.makedirs(DATA_DIR, exist_ok=True)


def save_json(data, filename):
    path = os.path.join(DATA_DIR, filename)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(sorted(data) if isinstance(data, list) else data,
                  f, ensure_ascii=False, indent=None)
    print(f'  {filename} : {len(data)} entrees')


# =============================================================
#  1. Stopwords capitalises
# =============================================================
print('Generation des stopwords...')
stopwords_cap = [
    # Salutations et formules
    'Bonjour', 'Bonsoir', 'Bonne', 'Cordialement', 'Respectueusement', 'Merci', 'Veuillez',
    'Bien', 'Suite', 'Afin', 'Pour', 'Dans', 'Depuis', 'Selon', 'Après', 'Avant', 'Entre',
    # Déterminants et pronoms
    'Le', 'La', 'Les', 'De', 'Du', 'Des', 'Et', 'En', 'À', 'Au', 'Aux', 'Un', 'Une',
    'Je', 'Nous', 'Vous', 'Il', 'Elle', 'On', 'Ils', 'Elles', 'Leur', 'Leurs',
    'Sans', 'Avec', 'Par', 'Sur', 'Sous', 'Vers', 'Chez',
    'Cette', 'Ces', 'Ce', 'Cet', 'Qui', 'Que', 'Quoi', 'Dont', 'Où',
    'Mon', 'Mes', 'Ton', 'Tes', 'Son', 'Ses', 'Notre', 'Votre',
    'Tout', 'Tous', 'Toute', 'Toutes', 'Très', 'Plus', 'Moins', 'Aussi',
    'Mais', 'Donc', 'Car', 'Ni', 'Or', 'Si', 'Comme', 'Quand',
    # Verbes courants
    'Contactez', 'Envoyez', 'Appelez', 'Demandez', 'Informez', 'Prévoyez',
    'Voir', 'Faire', 'Être', 'Avoir', 'Aller', 'Dire', 'Savoir', 'Pouvoir',
    # Termes institutionnels
    'Logo', 'Région', 'Régional', 'Régionale', 'Académique', 'Académie',
    'Conseil', 'Direction', 'Service', 'Bureau', 'Département', 'Ministère',
    'Commission', 'Comité', 'Assemblée', 'Tribunal', 'Préfecture',
    'National', 'Nationale', 'Général', 'Générale', 'Municipal', 'Municipale',
    # Termes administratifs / techniques
    'Lieu', 'Date', 'Sexe', 'Genre', 'Nationalité', 'Nationalite', 'Age', 'Né', 'Née', 'Ne', 'Nee',
    'Adresse', 'Ville', 'Code', 'Postal', 'Pays', 'Email', 'Mail', 'Site', 'Web', 'Tel', 'Tél', 'Phone',
    'Numéro', 'Numero', 'No', 'Ref', 'Référence', 'Reference', 'Dossier', 'Client', 'Compte', 'Banque', 'Bic', 'Iban', 'Rib', 'Carte',
    'Ip', 'Wifi', 'Login', 'User', 'Username', 'Pseudo', 'Mot', 'Passe', 'Password', 'Identifiant', 'Id',
    'Siret', 'Siren', 'Rcs', 'Tva', 'Ape', 'Naf',
    'Objet', 'Sujet', 'Piece', 'Pièce', 'Jointe', 'Pj', 'Poste', 'Fonction', 'Statut',
    'Nom', 'Prénom', 'Prenom', 'Signature', 'Signé', 'Signe',
    # Mots scolaires / familiaux
    'Maman', 'Papa', 'Père', 'Mère', 'Frère', 'Sœur', 'Soeur', 'Fils', 'Fille', 'Enfant', 'Élève', 'Eleve',
    'Parent', 'Parents', 'Famille', 'Adulte', 'Niveau', 'Classe', 'Groupe', 'Section', 'Moyenne', 'Grande', 'Petite',
    'Enseignant', 'Enseignante', 'Maitresse', 'Maîtresse', 'Directeur', 'Directrice', 'Animatrice', 'Animateur',
    'Président', 'Présidente', 'Maire', 'Préfet', 'Préfète', 'Recteur', 'Rectrice', 'Ministre', 'Député', 'Sénateur',
    'Avs', 'Aesh', 'Atsem', 'Avs-i', 'Avs-co', 'Ulis', 'Rased', 'Cm1', 'Cm2', 'Ce1', 'Ce2', 'Cp', 'Gs', 'Ms', 'Ps',
]
save_json(stopwords_cap, 'stopwords-capitalises.json')


# =============================================================
#  2. Stopwords minuscules
# =============================================================
stopwords_min = [
    'le', 'la', 'les', 'de', 'du', 'des', 'et', 'en', 'au', 'aux', 'un', 'une',
    'par', 'sur', 'sous', 'vers', 'chez', 'sans', 'avec', 'pour', 'dans', 'depuis',
    'entre', 'selon', 'lors', 'après', 'avant',
    'je', 'tu', 'il', 'elle', 'on', 'nous', 'vous', 'ils', 'elles',
    'mon', 'ton', 'son', 'mes', 'tes', 'ses', 'notre', 'votre', 'leur', 'leurs',
    'qui', 'que', 'quoi', 'dont', 'moi', 'toi', 'lui', 'soi',
    'mais', 'donc', 'car', 'ni', 'or', 'si', 'comme', 'quand', 'aussi', 'bien',
    'plus', 'moins', 'tout', 'tous', 'toute', 'toutes', 'pas', 'non', 'oui',
    'encore', 'aussi', 'parfois', 'souvent', 'jamais', 'toujours', 'ici', 'là',
    'lors', 'puis', 'cela', 'ceci', 'rien', 'quelque',
    'est', 'sont', 'ont', 'avoir', 'faire', 'aller', 'dire', 'voir', 'venir',
    'pouvoir', 'vouloir', 'devoir', 'savoir', 'prendre', 'mettre', 'oublie',
    'prenom', 'nom', 'surnom', 'personne', 'gens', 'enfant', 'adulte', 'homme', 'femme',
    'madame', 'monsieur', 'notamment', 'exemple', 'souvent', 'objet', 'sujet',
    'texte', 'liste', 'date', 'lieu', 'pays', 'ville', 'code', 'rue', 'chemin',
    'dossier', 'document', 'fichier', 'compte', 'mail', 'site', 'ecrit', 'appel',
    'ainsi', 'alors', 'avoir', 'cette', 'celui', 'celle', 'ceux', 'celles',
    'quel', 'quelle', 'quels', 'quelles', 'lequel', 'duquel', 'auquel',
]
save_json(stopwords_min, 'stopwords-minuscules.json')


# =============================================================
#  3. Majuscules a garder
# =============================================================
acronymes = ['DRANE', 'DRASI', 'DRAN', 'EAFC', 'SOFIA', 'FMO', 'TED', 'TED-I', 'EPLE', 'ENT', 'IA', 'PDF']

majuscules = [
    'REUNION', 'RÉUNION', 'REGION', 'RÉGION', 'ACADEMIQUE', 'ACADÉMIQUE',
    'TWITTER', 'FACEBOOK', 'INSTAGRAM', 'YOUTUBE',
    'NORD', 'SUD', 'EST', 'OUEST',
    'FRANCE', 'PARIS', 'LYON', 'MARSEILLE', 'LILLE', 'BORDEAUX', 'TOULOUSE', 'NANTES', 'STRASBOURG',
    'DENAIN', 'LOURCHES', 'HAULCHIN', 'VALENCIENNES', 'CAMBRAI', 'DOUAI', 'ARRAS', 'LENS', 'LIEVIN',
    'MAUBEUGE', 'DUNKERQUE', 'CALAIS', 'BOULOGNE', 'ROUBAIX', 'TOURCOING', 'VILLENEUVE',
    'SAINT', 'SAINTE', 'MONT', 'LE', 'LA', 'LES', 'AUX', 'SUR', 'SOUS', 'LEZ', 'LÈZ',
    'NE', 'PAS', 'MINISTERE', 'MINISTÈRE', 'HOPITAL', 'HÔPITAL', "L'HOPITAL", "L'HÔPITAL",
    'WAVRECHAIN', 'NEUVILLE', 'ESCAUT', 'ESCAUDAIN', 'BOUCHAIN', 'ABSCON', 'ROEULX', 'ROUVIGNIES',
    'DOUCHY', 'MINES', 'ANZIN', 'BRUAY', 'ST', 'AMAND', 'EAUX', 'CONDÉ', 'VIEUX',
    'ONNAING', 'QUIEVRECHAIN', 'CRESPIN', 'MARLY', 'SAULT', 'AULNOY', 'FAMARS',
] + acronymes
save_json(majuscules, 'majuscules-garder.json')

save_json(acronymes, 'acronymes-garder.json')


# =============================================================
#  4. Villes francaises
# =============================================================
villes = [
    'PARIS', 'LYON', 'MARSEILLE', 'TOULOUSE', 'NICE', 'NANTES', 'MONTPELLIER', 'STRASBOURG', 'BORDEAUX', 'LILLE',
    'RENNES', 'REIMS', 'TOULON', 'SAINT-ÉTIENNE', 'LE HAVRE', 'GRENOBLE', 'DIJON', 'ANGERS', 'NÎMES', 'VILLEURBANNE',
    'SAINT-DENIS', 'AIX-EN-PROVENCE', 'CLERMONT-FERRAND', 'LE MANS', 'BREST', 'TOURS', 'AMIENS', 'LIMOGES', 'ANNECY',
    'PERPIGNAN', 'BOULOGNE-BILLANCOURT', 'METZ', 'BESANÇON', 'ORLÉANS', 'ARGENTEUIL', 'ROUEN', 'MULHOUSE',
    'MONTREUIL', 'CAEN', 'SAINT-PAUL', 'NANCY', 'NOUMÉA', 'TOURCOING', 'ROUBAIX', 'NANTERRE', 'VITRY-SUR-SEINE', 'CRÉTEIL',
    'AVIGNON', 'POITIERS', 'AUBERVILLIERS', 'DUNKERQUE', 'AULNAY-SOUS-BOIS', 'COLOMBES', 'ASNIÈRES-SUR-SEINE', 'VERSAILLES',
    'COURBEVOIE', 'CHERBOURG-EN-COTENTIN', 'RUEIL-MALMAISON', 'BÉZIERS', 'LA ROCHELLE', 'CHAMPIGNY-SUR-MARNE', 'PAU',
    'MÉRIGNAC', 'SAINT-MAUR-DES-FOSSÉS', 'ANTIBES', 'AJACCIO', 'CANNES', 'SAINT-NAZAIRE', 'DRANCY', 'NOISY-LE-GRAND',
    'ISSY-LES-MOULINEAUX', 'CERGY', 'LEVALLOIS-PERRET', 'CALAIS', 'PESSAC', 'VÉNISSIEUX', 'CLICHY', 'VALENCE', 'IVRY-SUR-SEINE',
    'QUIMPER', 'ANTONY', 'NEUILLY-SUR-SEINE', 'TROYES', 'SARCELLES', 'MONTAUBAN', 'CHAMBÉRY', 'NIORT', 'LORIENT',
    'VALENCIENNES', 'DENAIN', 'CAMBRAI', 'DOUAI', 'ARRAS', 'LENS', 'LIEVIN', 'MAUBEUGE', 'BOULOGNE-SUR-MER',
]
save_json(villes, 'villes-france.json')


# =============================================================
#  5. Mots-cles organisations
# =============================================================
organisations = [
    'SA', 'SAS', 'SARL', 'SNC', 'EURL', 'SASU', 'SCI', 'SCM', 'SCOP', 'SEM', 'GIE',
    'ASSOCIATION', 'FONDATION', 'GROUPE', 'FILIALE', 'CABINET', 'ETABLISSEMENT',
    'SOCIÉTÉ', 'SOCIETE', 'ORGANISME', 'AGENCE', 'CONSEIL',
    'FÉDÉRATION', 'FEDERATION', 'SYNDICAT', 'UNION', 'MUTUELLE', 'ASSURANCE', 'BANQUE',
    'HOPITAL', 'HÔPITAL', 'CLINIQUE', 'LABORATOIRE', 'PHARMACIE',
    'LYCÉE', 'COLLÈGE', 'ÉCOLE', 'UNIVERSITÉ',
]
save_json(organisations, 'mots-organisations.json')


# =============================================================
#  6. Contexte institutionnel
# =============================================================
contexte_inst = [
    'maternelle', 'maternelles', 'élémentaire', 'élémentaires', 'elementaire', 'elementaires',
    'primaire', 'primaires',
    'collège', 'collèges', 'college', 'colleges',
    'lycée', 'lycées', 'lycee', 'lycees',
    'école', 'écoles', 'ecole', 'ecoles',
    'université', 'universités', 'universite', 'universites',
    'crèche', 'crèches', 'creche', 'creches',
    'garderie', 'garderies', 'académie', 'académies', 'academie', 'academies',
    'clinique', 'cliniques', 'centre', 'centres', 'hôpital', 'hopital', 'hôpitaux', 'hopitaux',
    'bibliothèque', 'bibliothèques', 'bibliotheque', 'bibliotheques',
    'médiathèque', 'médiathèques', 'mediatheque', 'mediatheques',
    'stade', 'stades', 'gymnase', 'gymnases', 'piscine', 'piscines',
    'groupe', 'groupement', 'scolaire', 'scolaires',
]
save_json(contexte_inst, 'contexte-institution.json')


# =============================================================
#  Résumé
# =============================================================
print(f'\nRegeneration terminee. Fichiers ecrits dans {DATA_DIR}/')
total_files = len([f for f in os.listdir(DATA_DIR) if f.endswith('.json')])
print(f'{total_files} fichiers JSON presents (dont noms.json et prenoms.json non regeneres).')

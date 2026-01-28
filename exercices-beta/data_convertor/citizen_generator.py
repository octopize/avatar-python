"""
Synthetic Citizen (Job Seeker) Dataset Generator

Generates realistic synthetic data for job seekers ("demandeurs d'emploi")
respecting the metadata rules defined in metadata.csv.

The generator implements realistic correlations:
- Age correlates with marital status, education, experience
- Education correlates with job type and salary expectations
- Nationality correlates with language skills
- Residence type affects work authorization requirements
- Education level affects mobility and job targets
"""

import random
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# Seed for reproducibility
random.seed(42)
np.random.seed(42)

DATA_SOURCE = Path(__file__).parent.parent / "data_source"
DATA_PROCESSED = Path(__file__).parent.parent / "data_processed"

# ============================================================================
# REFERENCE DATA
# ============================================================================

# Luxembourg communes with postal codes
COMMUNES_LU = [
    ("Luxembourg", "1000"),
    ("Esch-sur-Alzette", "4000"),
    ("Differdange", "4500"),
    ("Dudelange", "3400"),
    ("Pétange", "4700"),
    ("Ettelbruck", "9000"),
    ("Diekirch", "9200"),
    ("Strassen", "8000"),
    ("Bertrange", "8100"),
    ("Bettembourg", "3200"),
    ("Hesperange", "5765"),
    ("Schifflange", "3800"),
    ("Sanem", "4400"),
    ("Mamer", "8200"),
    ("Mersch", "7500"),
    ("Kayl", "3600"),
    ("Rumelange", "3700"),
    ("Echternach", "6400"),
    ("Grevenmacher", "6700"),
    ("Remich", "5500"),
    ("Mondorf-les-Bains", "5600"),
    ("Clervaux", "9700"),
    ("Vianden", "9400"),
    ("Wiltz", "9500"),
]

# Neighboring countries (for non-residents / cross-border workers)
CROSS_BORDER = {
    "France": [
        ("Thionville", "57100"),
        ("Metz", "57000"),
        ("Longwy", "54400"),
        ("Audun-le-Tiche", "57390"),
    ],
    "Belgique": [
        ("Arlon", "6700"),
        ("Virton", "6760"),
        ("Aubange", "6790"),
    ],
    "Allemagne": [
        ("Trier", "54290"),
        ("Bitburg", "54634"),
        ("Saarburg", "54439"),
    ],
}

# Nationalities with weights (reflecting Luxembourg demographics)
NATIONALITIES = {
    "Luxembourgeoise": 0.30,
    "Portugaise": 0.16,
    "Française": 0.15,
    "Italienne": 0.04,
    "Belge": 0.04,
    "Allemande": 0.03,
    "Espagnole": 0.02,
    "Britannique": 0.01,
    "Polonaise": 0.02,
    "Roumaine": 0.02,
    "Cap-Verdienne": 0.01,
    "Marocaine": 0.01,
    "Ukrainienne": 0.02,
    "Syrienne": 0.01,
    "Érythréenne": 0.01,
    "Autres": 0.15,
}

# Common first names by gender (Luxembourg/European mix)
FIRST_NAMES_M = [
    "Jean", "Pierre", "Marc", "Michel", "Paul", "André", "Claude", "François",
    "Luc", "Patrick", "Thierry", "Carlos", "José", "Manuel", "António",
    "Marco", "Fabio", "Matteo", "Stefan", "Thomas", "Alexander", "Sébastien",
    "Nicolas", "Philippe", "Laurent", "David", "Julien", "Romain", "Yannick",
    "Piotr", "Andrei", "Oleksandr", "Mohammed", "Ahmed", "Ali",
]

FIRST_NAMES_F = [
    "Marie", "Anne", "Jeanne", "Sophie", "Claire", "Isabelle", "Catherine",
    "Nathalie", "Sylvie", "Christine", "Véronique", "Maria", "Ana", "Paula",
    "Fernanda", "Giulia", "Chiara", "Elena", "Laura", "Sarah", "Emma",
    "Léa", "Chloé", "Camille", "Charlotte", "Julie", "Céline", "Aurélie",
    "Anna", "Kateryna", "Olena", "Fatima", "Aïcha", "Mariam",
]

# Common last names
LAST_NAMES = [
    "Müller", "Weber", "Schmidt", "Schmit", "Wagner", "Hoffmann", "Klein",
    "Becker", "Meyer", "Kieffer", "Schroeder", "Reding", "Thill", "Reuter",
    "Fernandes", "Silva", "Santos", "Rodrigues", "Pereira", "Costa",
    "Martin", "Bernard", "Dubois", "Thomas", "Robert", "Petit", "Durand",
    "Rossi", "Russo", "Ferrari", "Esposito", "Bianchi",
    "Janssen", "Peeters", "Claes", "Maes",
    "Kowalski", "Nowak", "Popa", "Ionescu",
]

# ROME job codes (simplified list of common job categories)
ROME_CODES = {
    "M1607": ("Secrétariat", ["Secrétaire", "Secrétaire administratif", "Secrétaire juridique"]),
    "N1103": ("Magasinage et préparation de commandes", ["Préparateur de commandes", "Magasinier", "Agent logistique"]),
    "K2204": ("Nettoyage de locaux", ["Agent de nettoyage", "Agent d'entretien", "Technicien de surface"]),
    "D1106": ("Vente en alimentation", ["Vendeur", "Employé de libre-service", "Caissier"]),
    "F1704": ("Préparation du gros œuvre", ["Maçon", "Coffreur", "Ferrailleur"]),
    "H3302": ("Opérations manuelles d'assemblage", ["Agent de fabrication", "Opérateur de production"]),
    "M1602": ("Opérations administratives", ["Agent administratif", "Employé administratif"]),
    "K1304": ("Services domestiques", ["Aide à domicile", "Auxiliaire de vie"]),
    "G1603": ("Personnel polyvalent en restauration", ["Serveur", "Commis de cuisine", "Plongeur"]),
    "I1604": ("Mécanique automobile", ["Mécanicien auto", "Technicien automobile"]),
    "H2502": ("Management et ingénierie de production", ["Ingénieur production", "Responsable production"]),
    "M1805": ("Études et développement informatique", ["Développeur", "Ingénieur logiciel", "Analyste programmeur"]),
    "K1802": ("Développement local", ["Chargé de projet", "Coordinateur"]),
    "C1501": ("Gérance immobilière", ["Gestionnaire locatif", "Agent immobilier"]),
    "E1101": ("Animation de site multimédia", ["Community manager", "Webmaster"]),
}

# Education specialties by ISCED level
EDUCATION_SPECIALTIES = {
    3: ["Commerce", "Comptabilité", "Mécanique", "Électricité", "Hôtellerie", "Administration"],
    4: ["Artisanat", "Éducation", "Technique"],
    5: ["Informatique", "Commerce international", "Gestion", "Marketing"],
    6: ["Informatique", "Économie", "Droit", "Sciences", "Ingénierie", "Communication"],
    7: ["Finance", "Management", "Data Science", "Droit des affaires", "Ingénierie"],
    8: ["Recherche", "Sciences", "Économie appliquée"],
}

DIPLOMA_BY_ISCED = {
    1: "Primaire",
    2: "Secondaire (1er cycle)",
    3: ["DAP", "DT", "Secondaire classique", "Secondaire technique"],
    4: ["Brevet de maîtrise", "Diplôme d'éducateur"],
    5: "BTS",
    6: "Bachelor",
    7: "Master",
    8: "PhD",
}

# Street names for addresses
STREET_NAMES = [
    "rue de la Gare", "avenue de la Liberté", "rue du Commerce", "place Guillaume",
    "rue de Strasbourg", "boulevard Royal", "rue de l'Alzette", "rue de Hollerich",
    "avenue Monterey", "rue des Capucins", "rue Philippe II", "avenue J.F. Kennedy",
    "rue de Bonnevoie", "rue de Beggen", "avenue Pasteur", "rue de Luxembourg",
    "Grand-Rue", "rue Principale", "rue de l'Église", "rue du Parc",
]


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def generate_matricule() -> str:
    """Generate a 13-digit Luxembourg matricule."""
    # Format: YYYYMMDDXXXCC (birth date + sequence + check)
    return "".join([str(random.randint(0, 9)) for _ in range(13)])


def generate_birth_date(min_age: int = 18, max_age: int = 65) -> tuple[date, int]:
    """Generate a birth date and return (date, age)."""
    today = date.today()
    age = random.randint(min_age, max_age)
    # Random day in birth year
    birth_year = today.year - age
    birth_month = random.randint(1, 12)
    birth_day = random.randint(1, 28)  # Safe day
    birth_date = date(birth_year, birth_month, birth_day)
    return birth_date, age


def weighted_choice(choices_dict: dict) -> str:
    """Make a weighted random choice from a dictionary."""
    items = list(choices_dict.keys())
    weights = list(choices_dict.values())
    return random.choices(items, weights=weights, k=1)[0]


def get_marital_status_by_age(age: int) -> str:
    """Get marital status correlated with age."""
    if age < 25:
        return random.choices(
            ["Célibataire", "Marié", "PA", "Inconnu"], @
            weights=[0.85, 0.10, 0.03, 0.02],
        )[0]
    elif age < 35:
        return random.choices(
            ["Célibataire", "Marié", "PA", "Divorcé", "Inconnu"],
            weights=[0.45, 0.40, 0.08, 0.05, 0.02],
        )[0]
    elif age < 50:
        return random.choices(
            ["Célibataire", "Marié", "Divorcé", "Séparé", "Veuf", "PA", "Inconnu"],
            weights=[0.15, 0.50, 0.18, 0.08, 0.02, 0.05, 0.02],
        )[0]
    else:
        return random.choices(
            ["Célibataire", "Marié", "Divorcé", "Veuf", "Séparé", "Inconnu"],
            weights=[0.10, 0.45, 0.20, 0.15, 0.08, 0.02],
        )[0]


def get_children_by_age_and_status(age: int, marital_status: str) -> str:
    """Get children indicator correlated with age and marital status."""
    base_prob = 0.0
    if marital_status in ["Marié", "Divorcé", "Veuf", "Séparé"]:
        base_prob = 0.7
    elif marital_status == "PA":
        base_prob = 0.4
    else:
        base_prob = 0.15

    # Adjust by age
    if age < 25:
        base_prob *= 0.3
    elif age < 30:
        base_prob *= 0.6
    elif age > 45:
        base_prob *= 0.9

    if random.random() < base_prob:
        return "Oui"
    elif random.random() < 0.95:
        return "Non"
    else:
        return "Inconnu"


def get_education_level_by_age(age: int) -> int:
    """Get ISCED education level correlated with age (younger = more educated on average)."""
    if age < 30:
        return random.choices(
            [2, 3, 4, 5, 6, 7, 8],
            weights=[0.05, 0.25, 0.10, 0.15, 0.25, 0.18, 0.02],
        )[0]
    elif age < 45:
        return random.choices(
            [1, 2, 3, 4, 5, 6, 7, 8],
            weights=[0.02, 0.10, 0.35, 0.12, 0.12, 0.18, 0.10, 0.01],
        )[0]
    else:
        return random.choices(
            [1, 2, 3, 4, 5, 6, 7],
            weights=[0.05, 0.20, 0.40, 0.10, 0.10, 0.10, 0.05],
        )[0]


def get_language_levels_by_nationality(nationality: str) -> dict[str, str | None]:
    """Get language levels correlated with nationality."""
    levels = ["A", "B", "C"]

    # Base probabilities
    lang = {"FR": None, "LB": None, "DE": None, "EN": None}

    if nationality == "Luxembourgeoise":
        lang["LB"] = random.choices(levels, weights=[0.05, 0.15, 0.80])[0]
        lang["FR"] = random.choices(levels, weights=[0.05, 0.25, 0.70])[0]
        lang["DE"] = random.choices(levels, weights=[0.10, 0.30, 0.60])[0]
        lang["EN"] = random.choices(levels + [None], weights=[0.15, 0.35, 0.30, 0.20])[0]
    elif nationality in ["Française", "Belge"]:
        lang["FR"] = "C"
        lang["LB"] = random.choices(levels + [None], weights=[0.30, 0.20, 0.10, 0.40])[0]
        lang["DE"] = random.choices(levels + [None], weights=[0.25, 0.20, 0.10, 0.45])[0]
        lang["EN"] = random.choices(levels + [None], weights=[0.20, 0.30, 0.20, 0.30])[0]
    elif nationality == "Allemande":
        lang["DE"] = "C"
        lang["FR"] = random.choices(levels + [None], weights=[0.25, 0.25, 0.15, 0.35])[0]
        lang["LB"] = random.choices(levels + [None], weights=[0.35, 0.20, 0.10, 0.35])[0]
        lang["EN"] = random.choices(levels + [None], weights=[0.15, 0.35, 0.30, 0.20])[0]
    elif nationality == "Portugaise":
        lang["FR"] = random.choices(levels, weights=[0.15, 0.40, 0.45])[0]
        lang["LB"] = random.choices(levels + [None], weights=[0.30, 0.25, 0.15, 0.30])[0]
        lang["DE"] = random.choices(levels + [None], weights=[0.35, 0.20, 0.05, 0.40])[0]
        lang["EN"] = random.choices(levels + [None], weights=[0.30, 0.20, 0.10, 0.40])[0]
    elif nationality in ["Britannique"]:
        lang["EN"] = "C"
        lang["FR"] = random.choices(levels + [None], weights=[0.25, 0.30, 0.15, 0.30])[0]
        lang["DE"] = random.choices(levels + [None], weights=[0.35, 0.15, 0.05, 0.45])[0]
        lang["LB"] = random.choices(levels + [None], weights=[0.40, 0.15, 0.05, 0.40])[0]
    else:
        # Other nationalities
        lang["FR"] = random.choices(levels + [None], weights=[0.30, 0.30, 0.20, 0.20])[0]
        lang["EN"] = random.choices(levels + [None], weights=[0.25, 0.30, 0.20, 0.25])[0]
        lang["DE"] = random.choices(levels + [None], weights=[0.40, 0.20, 0.10, 0.30])[0]
        lang["LB"] = random.choices(levels + [None], weights=[0.50, 0.20, 0.05, 0.25])[0]

    return lang


def get_mobility_by_age_and_residence(age: int, is_resident: bool) -> tuple[str, list[str]]:
    """Get mobility and driving permits correlated with age."""
    # Younger people less likely to have car
    if age < 25:
        mobility_weights = [0.15, 0.45, 0.30, 0.10]
    elif age < 40:
        mobility_weights = [0.50, 0.30, 0.15, 0.05]
    else:
        mobility_weights = [0.55, 0.25, 0.12, 0.08]

    mobility_options = [
        "Excellente (permis A, B et véhicule personnel)",
        "Moyenne (permis B mais pas de voiture disponible ou utilisation de transports en communs)",
        "Limitée (pas de voiture et pas de transports en commun disponible)",
        "Limitée pour des raisons psychiques et/ou physiques (durée de trajet restreinte)",
    ]

    mobility = random.choices(mobility_options, weights=mobility_weights)[0]

    # Permits based on mobility and random chance
    permits = []
    if "Excellente" in mobility or "Moyenne" in mobility:
        permits.append("B")
        if random.random() < 0.15:
            permits.append("A")
        if random.random() < 0.08:
            permits.append("C")
        if random.random() < 0.05:
            permits.append("D")

    return mobility, permits


def get_rome_jobs_by_education(isced_level: int, age: int) -> list[dict]:
    """Get ROME job codes correlated with education level."""
    jobs = []

    # Higher education -> more qualified jobs
    if isced_level >= 6:
        eligible_codes = ["M1805", "H2502", "K1802", "C1501", "E1101", "M1607", "M1602"]
    elif isced_level >= 4:
        eligible_codes = ["M1607", "M1602", "I1604", "D1106", "K1304", "G1603"]
    else:
        eligible_codes = ["N1103", "K2204", "D1106", "F1704", "H3302", "K1304", "G1603"]

    # Pick 1-3 jobs
    num_jobs = random.choices([1, 2, 3], weights=[0.40, 0.40, 0.20])[0]
    selected_codes = random.sample(eligible_codes, min(num_jobs, len(eligible_codes)))

    for i, code in enumerate(selected_codes, 1):
        category, appellations = ROME_CODES[code]
        appellation = random.choice(appellations)

        # Experience correlated with age
        max_exp = max(0, (age - 20) * 12)  # months
        exp_months = random.randint(0, max_exp) if max_exp > 0 else 0

        if exp_months >= 24:
            exp_str = f"{exp_months // 12} ans"
        elif exp_months > 0:
            exp_str = f"{exp_months} mois"
        else:
            exp_str = None

        jobs.append({
            "code": f"{code} - {category}",
            "appellation": appellation,
            "experience": exp_str,
        })

    return jobs


def requires_work_authorization(nationality: str) -> bool:
    """Check if nationality requires work authorization in Luxembourg."""
    eu_nationalities = [
        "Luxembourgeoise", "Française", "Allemande", "Belge", "Italienne",
        "Espagnole", "Portugaise", "Polonaise", "Roumaine", "Britannique",
    ]
    return nationality not in eu_nationalities


# ============================================================================
# MAIN GENERATOR
# ============================================================================


def generate_citizen() -> dict[str, Any]:
    """Generate a single citizen record respecting all metadata rules."""
    record = {}

    # Basic identification
    record["Matricule"] = generate_matricule()

    # Gender
    genre = random.choices(["Masculin", "Féminin"], weights=[0.52, 0.48])[0]
    record["Genre"] = genre

    # Names based on gender
    if genre == "Masculin":
        record["Prenom"] = random.choice(FIRST_NAMES_M)
    else:
        record["Prenom"] = random.choice(FIRST_NAMES_F)
    record["Nom"] = random.choice(LAST_NAMES)

    # Birth date and age
    birth_date, age = generate_birth_date()
    record["Date_Naissance"] = birth_date.strftime("%Y-%m-%d")

    # Nationality
    nationality = weighted_choice(NATIONALITIES)
    record["Nationalite"] = nationality

    # Residence type (correlated with nationality)
    if nationality in ["Luxembourgeoise"]:
        residence_type = "résident"
    elif nationality in ["Française", "Belge", "Allemande"]:
        residence_type = random.choices(
            ["résident", "non-résident"],
            weights=[0.40, 0.60],
        )[0]
    else:
        residence_type = random.choices(
            ["résident", "non-résident", "inconnu"],
            weights=[0.75, 0.15, 0.10],
        )[0]
    record["Type_Residence"] = residence_type

    # Address based on residence type
    if residence_type == "résident" or residence_type == "inconnu":
        commune, postal = random.choice(COMMUNES_LU)
        record["Residence_Pays"] = "Luxembourg"
    else:
        # Cross-border worker
        country = random.choice(list(CROSS_BORDER.keys()))
        commune, postal = random.choice(CROSS_BORDER[country])
        record["Residence_Pays"] = country

    record["Residence_Commune"] = commune
    record["Residence_Code_Postal"] = postal
    record["Residence_Localite"] = f"{postal} - {commune}"
    record["Residence_Rue"] = random.choice(STREET_NAMES)
    record["Residence_Num_Rue"] = str(random.randint(1, 200))

    # Birth location (often same country as nationality)
    if nationality == "Luxembourgeoise":
        record["Pays_Naissance"] = "Luxembourg"
        record["Lieu_Naissance"] = random.choice(COMMUNES_LU)[0]
    else:
        country_map = {
            "Française": "France", "Portugaise": "Portugal", "Allemande": "Allemagne",
            "Belge": "Belgique", "Italienne": "Italie", "Espagnole": "Espagne",
            "Britannique": "Royaume-Uni", "Polonaise": "Pologne", "Roumaine": "Roumanie",
            "Cap-Verdienne": "Cap-Vert", "Marocaine": "Maroc",
            "Ukrainienne": "Ukraine", "Syrienne": "Syrie", "Érythréenne": "Érythrée",
        }
        record["Pays_Naissance"] = country_map.get(nationality, "Autre")
        record["Lieu_Naissance"] = ""

    # Marital status and children (correlated)
    marital_status = get_marital_status_by_age(age)
    record["Etat_Civil"] = marital_status
    record["Enfants"] = get_children_by_age_and_status(age, marital_status)

    # Handicap status (small percentage)
    record["Statut_SH"] = random.random() < 0.03
    if record["Statut_SH"]:
        record["Orientation_SH"] = random.choices(
            ["Marché ordinaire", "Atelier protégé", "Inconnu"],
            weights=[0.60, 0.30, 0.10],
        )[0]
    else:
        record["Orientation_SH"] = None

    # Reduced work capacity
    record["Statut_CTR"] = random.random() < 0.05

    # REVIS (social inclusion income) - correlated with employment difficulty
    record["REVIS"] = random.random() < 0.08

    # Work authorization (for non-EU nationals)
    if requires_work_authorization(nationality):
        record["Titre_Sejour"] = random.choice(["065", "100", "109"])
        today = date.today()
        debut = today - timedelta(days=random.randint(30, 365))
        fin = debut + timedelta(days=random.randint(365, 730))
        record["Debut_Titre_Sejour"] = debut.strftime("%Y-%m-%d")
        record["Fin_Titre_Sejour"] = fin.strftime("%Y-%m-%d")
        record["Autorisation_Travail_Debut"] = debut.strftime("%Y-%m-%d")
        record["Autorisation_Travail_Fin"] = fin.strftime("%Y-%m-%d")
        record["Autorisation_Travail_ISCO"] = None
    else:
        record["Titre_Sejour"] = None
        record["Debut_Titre_Sejour"] = None
        record["Fin_Titre_Sejour"] = None
        record["Autorisation_Travail_Debut"] = None
        record["Autorisation_Travail_Fin"] = None
        record["Autorisation_Travail_ISCO"] = None

    # Education (correlated with age)
    isced_level = get_education_level_by_age(age)
    record["Formation_Reussie_ISCED"] = str(isced_level)

    diploma = DIPLOMA_BY_ISCED.get(isced_level, "Inconnu")
    if isinstance(diploma, list):
        diploma = random.choice(diploma)
    record["Formation_Reussie_Diplome"] = diploma

    record["Formation_Reussie_Classe"] = None
    if isced_level <= 2:
        record["Formation_Reussie_Classe"] = random.choice(
            ["5ème primaire", "6ème primaire", "9ème EST", "10ème EST"]
        )

    if isced_level >= 3:
        specialties = EDUCATION_SPECIALTIES.get(isced_level, ["Général"])
        record["Formation_Reussie_Specialite"] = random.choice(specialties)
        record["Formation_Toutes_Specialites"] = record["Formation_Reussie_Specialite"]
    else:
        record["Formation_Reussie_Specialite"] = None
        record["Formation_Toutes_Specialites"] = None

    record["Formation_Reussie_Pays"] = record["Pays_Naissance"]
    record["Formation_Reussie_Preuve"] = random.choices(
        ["Vérifié", "Reconnu", "Homologué", "Déclaré", "A valider"],
        weights=[0.30, 0.25, 0.20, 0.15, 0.10],
    )[0]

    # Languages (correlated with nationality)
    languages = get_language_levels_by_nationality(nationality)
    record["Langue_FR"] = languages["FR"]
    record["Langue_LB"] = languages["LB"]
    record["Langue_DE"] = languages["DE"]
    record["Langue_EN"] = languages["EN"]
    record["Langues_Autres"] = random.choice([None, "Portugais", "Italien", "Espagnol", "Arabe", "Russe"])

    # Mobility and permits
    is_resident = residence_type == "résident"
    mobility, permits = get_mobility_by_age_and_residence(age, is_resident)
    record["Mobilite"] = mobility
    record["Permis"] = ", ".join(permits) if permits else None

    # Job targets (ROME codes)
    jobs = get_rome_jobs_by_education(isced_level, age)
    for i in range(1, 4):
        if i <= len(jobs):
            job = jobs[i - 1]
            record[f"Metier_ROME_{i}"] = job["code"]
            record[f"Metier_ROME_{i}_Appellation"] = job["appellation"]
            record[f"Metier_ROME_{i}_Experience"] = job["experience"]
        else:
            record[f"Metier_ROME_{i}"] = None
            record[f"Metier_ROME_{i}_Appellation"] = None
            record[f"Metier_ROME_{i}_Experience"] = None

    # Work preferences
    record["Temps_De_Travail"] = random.choices(
        ["Temps complet", "Temps partiel", "Sans préférence"],
        weights=[0.65, 0.25, 0.10],
    )[0]

    record["Horaire_Journalier"] = random.choices(
        ["Matin et Après-midi", "Flexible", "Matin", "Après-midi", "Soir", "Après-midi et Soir"],
        weights=[0.40, 0.30, 0.10, 0.10, 0.05, 0.05],
    )[0]

    # Weekly hours (correlated with time preference)
    if record["Temps_De_Travail"] == "Temps complet":
        record["Nbr_Heure_Semaine"] = random.randint(35, 40)
    elif record["Temps_De_Travail"] == "Temps partiel":
        record["Nbr_Heure_Semaine"] = random.randint(15, 30)
    else:
        record["Nbr_Heure_Semaine"] = random.randint(20, 40)

    return record


def generate_dataset(n_citizens: int = 1000) -> pd.DataFrame:
    """Generate a dataset of n citizens."""
    records = [generate_citizen() for _ in range(n_citizens)]
    return pd.DataFrame(records)


if __name__ == "__main__":
    print("Generating synthetic citizen dataset...")

    # Generate 1000 citizens
    df = generate_dataset(1000)

    # Display summary
    print(f"\nGenerated {len(df)} citizens")
    print("\nColumn summary:")
    print(f"  - Total columns: {len(df.columns)}")
    print(f"  - Gender distribution: {df['Genre'].value_counts().to_dict()}")
    print(f"  - Residence type: {df['Type_Residence'].value_counts().to_dict()}")
    print(f"  - Top nationalities: {df['Nationalite'].value_counts().head(5).to_dict()}")
    print(f"  - Education levels (ISCED): {df['Formation_Reussie_ISCED'].value_counts().sort_index().to_dict()}")

    # Save to CSV
    output_file = DATA_PROCESSED / "citizens_synthetic.csv"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_file, index=False)
    print(f"\nDataset saved to: {output_file}")

    # Also display first few rows
    print("\nFirst 5 rows (selected columns):")
    display_cols = ["Matricule", "Nom", "Prenom", "Genre", "Nationalite", "Type_Residence", "Formation_Reussie_ISCED"]
    print(df[display_cols].head().to_string(index=False))

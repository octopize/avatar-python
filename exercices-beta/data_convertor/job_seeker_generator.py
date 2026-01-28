"""
Generate synthetic job seeker dataset based on metadata description
"""

import pandas as pd
import random
from datetime import datetime, timedelta
from faker import Faker

# Initialize Faker for different locales
fake_fr = Faker("fr_FR")
fake_de = Faker("de_DE")
fake_en = Faker("en_US")


def random_date(start_year=1950, end_year=2005):
    """Generate random date between start_year and end_year"""
    start_date = datetime(start_year, 1, 1)
    end_date = datetime(end_year, 12, 31)
    delta = end_date - start_date
    random_days = random.randint(0, abs(delta.days))
    return (start_date + timedelta(days=random_days)).strftime("%Y%m%d")


def random_recent_date(days_back=730):
    """Generate recent date within last days_back days"""
    today = datetime.now()
    start_date = today - timedelta(days=days_back)
    delta = today - start_date
    random_days = random.randint(0, abs(delta.days))
    return (start_date + timedelta(days=random_days)).strftime("%Y%m%d")


def generate_matricule():
    """Generate 13-digit matricule number"""
    return "".join([str(random.randint(0, 9)) for _ in range(13)])


def generate_luxembourg_communes():
    """Return list of Luxembourg communes"""
    return [
        "Luxembourg",
        "Esch-sur-Alzette",
        "Differdange",
        "Dudelange",
        "Pétange",
        "Sanem",
        "Hésperange",
        "Bettembourg",
        "Strassen",
        "Bertrange",
        "Schifflange",
        "Rodange",
        "Ettelbruck",
        "Diekirch",
        "Wiltz",
        "Echternach",
        "Remich",
        "Grevenmacher",
        "Vianden",
        "Clervaux",
        "Mersch",
        "Capellen",
        "Redange",
        "Mondorf-les-Bains",
        "Walferdange",
    ]


def generate_luxembourg_localities():
    """Return dict of localities with codes"""
    localities = {
        "Luxembourg": "110101",
        "Esch-sur-Alzette": "110201",
        "Differdange": "110301",
        "Dudelange": "110401",
        "Echternach": "110502",
        "Grevenmacher": "110601",
        "Remich": "110701",
        "Ettelbruck": "110801",
        "Diekirch": "110901",
        "Wiltz": "111001",
    }
    return localities


def generate_postal_codes():
    """Generate realistic Luxembourg postal codes"""
    return [str(i) for i in range(1000, 10000, 100)]


def generate_nationalities():
    """Return list of common nationalities in Luxembourg"""
    return [
        "Luxembourgeoise",
        "Portugaise",
        "Française",
        "Italienne",
        "Belge",
        "Allemande",
        "Espagnole",
        "Britannique",
        "Néerlandaise",
        "Syrienne",
        "Érythréenne",
        "Somalienne",
        "Afghane",
        "Roumaine",
        "Polonaise",
    ]


def generate_countries():
    """Return list of countries"""
    return [
        "Luxembourg",
        "Portugal",
        "France",
        "Italie",
        "Belgique",
        "Allemagne",
        "Espagne",
        "Royaume-Uni",
        "Pays-Bas",
        "Syrie",
        "Érythrée",
        "Somalie",
        "Afghanistan",
        "Roumanie",
        "Pologne",
    ]


def generate_isco_codes():
    """Generate ISCO occupation codes"""
    return ["2411", "2412", "1211", "5120", "4110", "2310", "2320", "7231", "9321", "5223"]


def generate_rome_codes():
    """Generate ROME occupation codes with descriptions"""
    rome_codes = {
        "M1607": "Secrétariat",
        "M1203": "Comptabilité",
        "K2111": "Formation professionnelle",
        "D1406": "Management en force de vente",
        "I1308": "Assistance informatique",
        "J1501": "Soins infirmiers",
        "H2901": "Ajustement et montage",
        "N1103": "Magasinage et préparation de commandes",
        "K1207": "Intervention socioéducative",
        "G1603": "Personnel polyvalent en restauration",
    }
    return rome_codes


def generate_rome_appellations():
    """Generate ROME occupation appellations"""
    appellations = {
        "M1607": ["Secrétaire", "Secrétaire juridique", "Assistant administratif"],
        "M1203": ["Comptable", "Assistant comptable", "Aide-comptable"],
        "K2111": ["Formateur", "Formateur professionnel", "Conseiller en formation"],
        "D1406": ["Commercial", "Responsable commercial", "Chef des ventes"],
        "I1308": ["Technicien support", "Technicien helpdesk", "Support informatique"],
        "J1501": ["Infirmier", "Aide-soignant", "Auxiliaire de vie"],
        "H2901": ["Monteur", "Ajusteur-monteur", "Mécanicien monteur"],
        "N1103": ["Magasinier", "Préparateur de commandes", "Agent logistique"],
        "K1207": ["Éducateur", "Éducateur spécialisé", "Animateur social"],
        "G1603": ["Serveur", "Employé de restauration", "Agent de restauration"],
    }
    return appellations


def generate_diplomas():
    """Generate diploma types"""
    return [
        "DAP",
        "DT",
        "CATP",
        "Secondaire technique",
        "Secondaire classique",
        "Brevet de maîtrise",
        "BTS",
        "Bachelor",
        "Master",
        "PhD",
        "Diplôme d'éducateur",
    ]


def generate_specialties():
    """Generate education specialties"""
    return [
        "Comptabilité",
        "Économie",
        "Division administrative et commerciale",
        "Informatique",
        "Électronique",
        "Mécanique",
        "Commerce",
        "Hôtellerie-Restauration",
        "Soins infirmiers",
        "Éducation sociale",
        "Droit",
        "Sciences humaines",
        "Langues",
        "Sciences naturelles",
    ]


def generate_titre_sejour():
    """Generate residence permit codes"""
    codes = {
        "065": "Membre de famille (UE avec hors UE)",
        "100": "Protection internationale (BPI)",
        "109": "Protection temporaire (BPT)",
        "120": "Carte de séjour UE",
        "130": "Autorisation de séjour temporaire",
        "": "",  # No permit needed
    }
    return codes


def generate_individual():
    """Generate one individual record"""

    # Basic personal information
    genre = random.choice(["Masculin", "Féminin"])
    if genre == "Masculin":
        nom = fake_fr.last_name()
        prenom = fake_fr.first_name_male()
    else:
        nom = fake_fr.last_name()
        prenom = fake_fr.first_name_female()

    matricule = generate_matricule()
    date_naissance = random_date(1950, 2005)

    # Nationality and birth place
    nationalite = random.choice(generate_nationalities())
    pays_naissance = random.choice(generate_countries())

    # For Luxembourg-born, use Luxembourg communes, otherwise use Faker
    if pays_naissance == "Luxembourg":
        lieu_naissance = random.choice(generate_luxembourg_communes())
    else:
        lieu_naissance = fake_fr.city()

    # Residence information
    type_residence = random.choice(["résident", "résident", "résident", "non-résident", "inconnu"])

    residence_num_rue = str(random.randint(1, 250))
    residence_rue = fake_fr.street_name()
    residence_code_postal = random.choice(generate_postal_codes())

    localities = generate_luxembourg_localities()
    residence_commune = random.choice(list(localities.keys()))
    residence_localite = f"{localities[residence_commune]} {residence_commune}"

    residence_pays = random.choice(
        ["Luxembourg", "Luxembourg", "Luxembourg", "France", "Belgique", "Allemagne"]
    )

    # Civil status and children
    etat_civil = random.choice(
        ["Célibataire", "Marié", "Divorcé", "Veuf", "Séparé", "Inconnu", "PA"]
    )
    enfants = random.choice(["Oui", "Non", "Inconnu"])

    # Special statuses
    statut_sh = random.choice([True, False, False, False, False])
    orientation_sh = (
        random.choice(["Marché ordinaire", "Atelier protégé", "Inconnu"])
        if statut_sh
        else "Inconnu"
    )
    statut_ctr = random.choice([True, False, False, False, False])
    revis = random.choice([True, False, False, False, False])

    # Residence permit
    titre_sejour_dict = generate_titre_sejour()
    has_titre = random.choice([True, False, False, False])
    if has_titre and nationalite not in ["Luxembourgeoise"]:
        titre_sejour_code = random.choice(["065", "100", "109", "120", "130"])
        titre_sejour = f"{titre_sejour_code} {titre_sejour_dict[titre_sejour_code]}"
        debut_titre_sejour = random_recent_date(1095)
        fin_titre_sejour = random_recent_date(-365)  # Future date
    else:
        titre_sejour = ""
        debut_titre_sejour = ""
        fin_titre_sejour = ""

    # Work authorization
    needs_work_auth = random.choice([True, False, False, False])
    if needs_work_auth:
        autorisation_travail_debut = random_recent_date(730)
        autorisation_travail_fin = random_recent_date(-180)
        autorisation_travail_isco = random.choice(generate_isco_codes())
    else:
        autorisation_travail_debut = ""
        autorisation_travail_fin = ""
        autorisation_travail_isco = ""

    # Targeted occupations
    rome_codes = list(generate_rome_codes().keys())
    rome_appellations = generate_rome_appellations()

    metier_rome_1 = random.choice(rome_codes)
    metier_rome_1_appellation = random.choice(rome_appellations[metier_rome_1])
    metier_rome_1_experience = f"{random.randint(0, 20)} ans" if random.random() > 0.3 else ""

    # Second occupation (optional)
    if random.random() > 0.5:
        metier_rome_2 = random.choice([c for c in rome_codes if c != metier_rome_1])
        metier_rome_2_appellation = random.choice(rome_appellations[metier_rome_2])
        metier_rome_2_experience = f"{random.randint(0, 15)} ans" if random.random() > 0.4 else ""
    else:
        metier_rome_2 = ""
        metier_rome_2_appellation = ""
        metier_rome_2_experience = ""

    # Third occupation (optional)
    if random.random() > 0.7:
        metier_rome_3 = random.choice(
            [c for c in rome_codes if c not in [metier_rome_1, metier_rome_2]]
        )
        metier_rome_3_appellation = random.choice(rome_appellations[metier_rome_3])
        metier_rome_3_experience = f"{random.randint(0, 10)} ans" if random.random() > 0.5 else ""
    else:
        metier_rome_3 = ""
        metier_rome_3_appellation = ""
        metier_rome_3_experience = ""

    # Education
    formation_reussie_isced = random.choice(["0", "1", "2", "3", "4", "5", "6", "7", "8"])

    # Diploma based on ISCED level
    if formation_reussie_isced in ["0", "1", "2"]:
        formation_reussie_diplome = random.choice(
            ["", "Secondaire technique", "Secondaire classique"]
        )
        formation_reussie_classe = random.choice(
            ["9ème EST", "12ème EST", "2ème ESC", "5ème primaire"]
        )
    elif formation_reussie_isced == "3":
        formation_reussie_diplome = random.choice(["DAP", "DT", "CATP"])
        formation_reussie_classe = ""
    elif formation_reussie_isced == "4":
        formation_reussie_diplome = random.choice(["Brevet de maîtrise", "Diplôme d'éducateur"])
        formation_reussie_classe = ""
    elif formation_reussie_isced == "5":
        formation_reussie_diplome = "BTS"
        formation_reussie_classe = ""
    elif formation_reussie_isced == "6":
        formation_reussie_diplome = "Bachelor"
        formation_reussie_classe = ""
    elif formation_reussie_isced == "7":
        formation_reussie_diplome = "Master"
        formation_reussie_classe = ""
    else:  # 8
        formation_reussie_diplome = "PhD"
        formation_reussie_classe = ""

    specialties = generate_specialties()
    formation_reussie_specialite = random.choice(specialties) if random.random() > 0.2 else ""
    formation_toutes_specialites = ", ".join(random.sample(specialties, k=random.randint(1, 3)))
    formation_reussie_pays = random.choice(generate_countries())
    formation_reussie_preuve = random.choice(
        ["Déclaré", "Vérifié", "Homologué", "Reconnu", "A valider"]
    )

    # Languages
    langue_fr = random.choice(["A", "B", "C", "C", "B"])  # French more common at higher levels
    langue_lb = random.choice(["", "A", "B", "C"])
    langue_de = random.choice(["", "A", "B", "C"])
    langue_en = random.choice(["", "A", "B", "C"])

    other_langs = ["Portugais", "Italien", "Espagnol", "Néerlandais", "Arabe", "Russe"]
    if random.random() > 0.6:
        langues_autres = f"{random.choice(other_langs)}: {random.choice(['A', 'B', 'C'])}"
    else:
        langues_autres = ""

    # Mobility
    mobilite = random.choice(
        [
            "Excellente (permis A, B et véhicule personnel)",
            "Moyenne (permis B mais pas de voiture disponible ou utilisation de transports en communs)",
            "Limitée (pas de voiture et pas de transports en commun disponible)",
            "Limitée pour des raisons psychiques et/ou physiques (durée de trajet restreinte)",
        ]
    )

    return {
        "Matricule": matricule,
        "Nom": nom,
        "Prenom": prenom,
        "Genre": genre,
        "Date_Naissance": date_naissance,
        "Pays_Naissance": pays_naissance,
        "Lieu_Naissance": lieu_naissance,
        "Nationalite": nationalite,
        "Type_Residence": type_residence,
        "Residence_Num_Rue": residence_num_rue,
        "Residence_Rue": residence_rue,
        "Residence_Code_Postal": residence_code_postal,
        "Residence_Localite": residence_localite,
        "Residence_Commune": residence_commune,
        "Residence_Pays": residence_pays,
        "Etat_Civil": etat_civil,
        "Enfants": enfants,
        "Statut_SH": statut_sh,
        "Orientation_SH": orientation_sh,
        "Statut_CTR": statut_ctr,
        "REVIS": revis,
        "Titre_Sejour": titre_sejour,
        "Debut_Titre_Sejour": debut_titre_sejour,
        "Fin_Titre_Sejour": fin_titre_sejour,
        "Autorisation_Travail_Debut": autorisation_travail_debut,
        "Autorisation_Travail_Fin": autorisation_travail_fin,
        "Autorisation_Travail_ISCO": autorisation_travail_isco,
        "Metier_ROME_1": metier_rome_1,
        "Metier_ROME_1_Appellation": metier_rome_1_appellation,
        "Metier_ROME_1_Experience": metier_rome_1_experience,
        "Metier_ROME_2": metier_rome_2,
        "Metier_ROME_2_Appellation": metier_rome_2_appellation,
        "Metier_ROME_2_Experience": metier_rome_2_experience,
        "Metier_ROME_3": metier_rome_3,
        "Metier_ROME_3_Appellation": metier_rome_3_appellation,
        "Metier_ROME_3_Experience": metier_rome_3_experience,
        "Formation_Reussie_ISCED": formation_reussie_isced,
        "Formation_Reussie_Diplome": formation_reussie_diplome,
        "Formation_Reussie_Classe": formation_reussie_classe,
        "Formation_Reussie_Specialite": formation_reussie_specialite,
        "Formation_Toutes_Specialites": formation_toutes_specialites,
        "Formation_Reussie_Pays": formation_reussie_pays,
        "Formation_Reussie_Preuve": formation_reussie_preuve,
        "Langue_FR": langue_fr,
        "Langue_LB": langue_lb,
        "Langue_DE": langue_de,
        "Langue_EN": langue_en,
        "Langues_Autres": langues_autres,
        "Mobilite": mobilite,
    }


def generate_dataset(n_individuals=200):
    """Generate complete dataset with n individuals"""
    print(f"Generating dataset with {n_individuals} individuals...")

    data = []
    for i in range(n_individuals):
        if (i + 1) % 50 == 0:
            print(f"Generated {i + 1}/{n_individuals} individuals...")
        data.append(generate_individual())

    df = pd.DataFrame(data)
    print(f"Dataset generated successfully with {len(df)} rows and {len(df.columns)} columns")
    return df


if __name__ == "__main__":
    # Generate dataset
    df = generate_dataset(200)

    # Save to CSV
    output_file = "data_processed/job_seekers_synthetic_200.csv"
    df.to_csv(output_file, index=False, encoding="utf-8-sig")
    print(f"\nDataset saved to: {output_file}")

    # Display summary
    print("\n=== Dataset Summary ===")
    print(f"Total individuals: {len(df)}")
    print(f"Total columns: {len(df.columns)}")
    print(f"\nFirst few rows:")
    print(df.head())
    print(f"\nColumn names:")
    print(df.columns.tolist())

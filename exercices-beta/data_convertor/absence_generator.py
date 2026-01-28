"""
Synthetic Absence Dataset Generator

Generates realistic synthetic absence data for 4000 individuals based on the metadata description.
Includes realistic scenarios for different types of absences (sick leave, maternity/paternity,
work accidents, etc.) with appropriate durations and diagnoses.
"""

import pandas as pd
import random
from datetime import datetime, timedelta
from pathlib import Path
import numpy as np

# Seed for reproducibility
random.seed(42)
np.random.seed(42)

DATA_PROCESSED = Path(__file__).parent.parent / "data_processed"

# ============================================================================
# REFERENCE DATA
# ============================================================================

# Absence types for private scheme workers
ABSENCE_TYPES = [
    "Sick Leave",  # Congé de maladie
    "Maternity Leave",  # Congé de maternité
    "Paternity Leave",  # Congé de paternité
    "Work Accident",  # Accident de travail
    "Occupational Disease",  # Maladie professionnelle
    "Long-term Illness",  # Maladie de longue durée
    "Surgery Recovery",  # Convalescence chirurgicale
    "Burnout",  # Épuisement professionnel
    "Mental Health",  # Santé mentale
    "Rehabilitation",  # Rééducation
]

# Common diagnoses by absence type
DIAGNOSES = {
    "Sick Leave": [
        "Influenza",
        "Gastroenteritis",
        "Upper respiratory infection",
        "Bronchitis",
        "Migraine",
        "Back pain",
        "Sinusitis",
        "Pharyngitis",
        "Acute stress reaction",
        "Musculoskeletal disorder",
    ],
    "Maternity Leave": [
        "Normal pregnancy and delivery",
        "Pregnancy complications",
        "Cesarean section",
        "Postpartum recovery",
        "High-risk pregnancy",
    ],
    "Paternity Leave": ["Birth of child", "Adoption"],
    "Work Accident": [
        "Sprain or strain",
        "Fracture",
        "Laceration",
        "Contusion",
        "Burn",
        "Back injury from lifting",
        "Repetitive strain injury",
        "Slip and fall injury",
    ],
    "Occupational Disease": [
        "Carpal tunnel syndrome",
        "Tendinitis",
        "Hearing loss",
        "Dermatitis",
        "Respiratory disease",
        "Asbestosis",
        "Chronic back disorder",
    ],
    "Long-term Illness": [
        "Cancer treatment",
        "Cardiovascular disease",
        "Diabetes complications",
        "Chronic obstructive pulmonary disease",
        "Autoimmune disorder",
        "Neurological disorder",
    ],
    "Surgery Recovery": [
        "Appendectomy",
        "Hernia repair",
        "Knee surgery",
        "Hip replacement",
        "Gallbladder removal",
        "Spinal surgery",
        "Cardiac surgery",
    ],
    "Burnout": [
        "Work-related stress disorder",
        "Chronic fatigue syndrome",
        "Anxiety disorder",
        "Adjustment disorder",
    ],
    "Mental Health": [
        "Depression",
        "Anxiety disorder",
        "Post-traumatic stress disorder",
        "Panic disorder",
        "Bipolar disorder",
    ],
    "Rehabilitation": [
        "Post-surgery rehabilitation",
        "Physical therapy",
        "Occupational therapy",
        "Cardiac rehabilitation",
        "Stroke rehabilitation",
    ],
}

# Typical duration ranges (in days) for each absence type
DURATION_RANGES = {
    "Sick Leave": (1, 14),  # 1-14 days
    "Maternity Leave": (112, 140),  # 16-20 weeks (Luxembourg standard)
    "Paternity Leave": (10, 10),  # 10 days (Luxembourg standard)
    "Work Accident": (3, 90),  # 3 days to 3 months
    "Occupational Disease": (30, 180),  # 1-6 months
    "Long-term Illness": (60, 365),  # 2 months to 1 year
    "Surgery Recovery": (7, 60),  # 1 week to 2 months
    "Burnout": (30, 180),  # 1-6 months
    "Mental Health": (14, 120),  # 2 weeks to 4 months
    "Rehabilitation": (21, 90),  # 3 weeks to 3 months
}

# ============================================================================
# GENERATOR FUNCTIONS
# ============================================================================


def generate_individual_id():
    """Generate pseudonymised 12-character ID"""
    return "ID" + "".join([str(random.randint(0, 9)) for _ in range(10)])


def random_date_in_range(start_date, end_date):
    """Generate random date between start_date and end_date"""
    delta = end_date - start_date
    random_days = random.randint(0, delta.days)
    return start_date + timedelta(days=random_days)


def generate_absence_start_date():
    """Generate absence start date within last 2 years"""
    today = datetime.now()
    two_years_ago = today - timedelta(days=730)
    return random_date_in_range(two_years_ago, today)


def calculate_end_date(start_date, duration_days):
    """Calculate end date based on start date and duration"""
    return start_date + timedelta(days=int(duration_days))


def generate_duration(absence_type):
    """Generate realistic duration based on absence type"""
    min_days, max_days = DURATION_RANGES[absence_type]

    # Use different distributions for different types
    if absence_type == "Sick Leave":
        # Most sick leaves are short (1-3 days), fewer are longer
        weights = [0.4, 0.3, 0.15, 0.08, 0.04, 0.02, 0.01]
        duration_buckets = [1, 2, 3, 5, 7, 10, 14]
        return random.choices(duration_buckets, weights=weights)[0]

    elif absence_type in ["Maternity Leave", "Paternity Leave"]:
        # Maternity/Paternity leave is standardized
        return random.randint(min_days, max_days)

    elif absence_type in ["Long-term Illness", "Burnout", "Mental Health"]:
        # Long-term absences tend toward longer durations
        return int(np.random.triangular(min_days, max_days, max_days))

    else:
        # Other types use triangular distribution (peak in middle)
        return int(np.random.triangular(min_days, (min_days + max_days) / 2, max_days))


def determine_worker_scheme():
    """Determine if individual is private or public scheme worker"""
    # Approximately 75% private, 25% public in Luxembourg
    return random.choices(["private", "public"], weights=[0.75, 0.25])[0]


def should_have_absence(individual_idx, total_individuals):
    """Determine if individual has absence record"""
    # About 60% of workers have at least one absence per year
    # Some individuals may have multiple absences
    if random.random() < 0.40:  # 40% have no absences
        return 0
    elif random.random() < 0.70:  # 70% of those with absences have 1 absence
        return 1
    elif random.random() < 0.85:  # 15% have 2 absences
        return 2
    elif random.random() < 0.95:  # 10% have 3 absences
        return 3
    else:  # 5% have 4+ absences
        return random.randint(4, 6)


def generate_absence_type_weighted():
    """Generate absence type with realistic distribution"""
    types = list(ABSENCE_TYPES)
    # Sick leave is most common
    weights = [
        0.50,  # Sick Leave (most common)
        0.08,  # Maternity Leave
        0.05,  # Paternity Leave
        0.12,  # Work Accident
        0.05,  # Occupational Disease
        0.05,  # Long-term Illness
        0.06,  # Surgery Recovery
        0.04,  # Burnout
        0.03,  # Mental Health
        0.02,  # Rehabilitation
    ]
    return random.choices(types, weights=weights)[0]


def generate_individual_absences(individual_id, num_absences, scheme):
    """Generate absence records for a single individual"""
    absences = []

    if scheme == "public":
        # Public scheme workers: no absence data available
        absences.append(
            {
                "individual_IDnumber": individual_id,
                "a_absence_type": None,
                "a_start_date": None,
                "a_end_date": None,
                "a_length_absence": None,
                "a_diagnosis": None,
            }
        )
    else:
        # Private scheme workers: may have absence records
        if num_absences == 0:
            # No absences recorded
            absences.append(
                {
                    "individual_IDnumber": individual_id,
                    "a_absence_type": None,
                    "a_start_date": None,
                    "a_end_date": None,
                    "a_length_absence": None,
                    "a_diagnosis": None,
                }
            )
        else:
            # Generate multiple absences for this individual
            used_dates = []

            for _ in range(num_absences):
                absence_type = generate_absence_type_weighted()
                duration = generate_duration(absence_type)

                # Generate start date avoiding overlaps
                max_attempts = 20
                for attempt in range(max_attempts):
                    start_date = generate_absence_start_date()
                    end_date = calculate_end_date(start_date, duration)

                    # Check for overlap with existing absences
                    overlap = False
                    for used_start, used_end in used_dates:
                        if start_date <= used_end and end_date >= used_start:
                            overlap = True
                            break

                    if not overlap:
                        used_dates.append((start_date, end_date))
                        break
                else:
                    # If we couldn't find non-overlapping dates, use the last generated ones anyway
                    used_dates.append((start_date, end_date))

                diagnosis = random.choice(DIAGNOSES[absence_type])

                absences.append(
                    {
                        "individual_IDnumber": individual_id,
                        "a_absence_type": absence_type,
                        "a_start_date": start_date.strftime("%Y%m%d"),
                        "a_end_date": end_date.strftime("%Y%m%d"),
                        "a_length_absence": float(duration),
                        "a_diagnosis": diagnosis,
                    }
                )

    return absences


def generate_absence_dataset(num_individuals=4000):
    """
    Generate synthetic absence dataset for specified number of individuals

    Args:
        num_individuals: Number of unique individuals to generate (default: 4000)

    Returns:
        pandas.DataFrame: Dataset with absence records
    """
    print(f"Generating absence dataset for {num_individuals} individuals...")

    all_absences = []

    for i in range(num_individuals):
        if (i + 1) % 500 == 0:
            print(f"  Generated {i + 1}/{num_individuals} individuals...")

        # Generate unique individual ID
        individual_id = generate_individual_id()

        # Determine worker scheme
        scheme = determine_worker_scheme()

        # Determine number of absences for this individual
        num_absences = should_have_absence(i, num_individuals)

        # Generate absence records
        individual_absences = generate_individual_absences(individual_id, num_absences, scheme)
        all_absences.extend(individual_absences)

    # Create DataFrame
    df = pd.DataFrame(all_absences)

    print(f"\nDataset generation complete!")
    print(f"  Total individuals: {num_individuals}")
    print(f"  Total absence records: {len(df)}")
    print(f"  Records with absences: {df['a_absence_type'].notna().sum()}")
    print(f"  Records without absences: {df['a_absence_type'].isna().sum()}")

    return df


def save_dataset(df, filename="absence_dataset.csv"):
    """Save dataset to CSV file"""
    output_path = DATA_PROCESSED / filename
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"\nDataset saved to: {output_path}")
    return output_path


def print_dataset_statistics(df):
    """Print statistics about the generated dataset"""
    print("\n" + "=" * 70)
    print("DATASET STATISTICS")
    print("=" * 70)

    # Basic stats
    print(f"\nTotal records: {len(df)}")
    print(f"Unique individuals: {df['individual_IDnumber'].nunique()}")

    # Absence type distribution
    print("\nAbsence Type Distribution:")
    absence_counts = df["a_absence_type"].value_counts()
    for absence_type, count in absence_counts.items():
        if pd.notna(absence_type):
            percentage = (count / len(df[df["a_absence_type"].notna()])) * 100
            print(f"  {absence_type:.<35} {count:>5} ({percentage:>5.1f}%)")

    print(f"\n  {'No absence data':.<35} {df['a_absence_type'].isna().sum():>5}")

    # Duration statistics
    print("\nDuration Statistics (days):")
    print(f"  Mean: {df['a_length_absence'].mean():.1f}")
    print(f"  Median: {df['a_length_absence'].median():.1f}")
    print(f"  Min: {df['a_length_absence'].min():.1f}")
    print(f"  Max: {df['a_length_absence'].max():.1f}")

    # Duration by absence type
    print("\nAverage Duration by Absence Type:")
    for absence_type in df[df["a_absence_type"].notna()]["a_absence_type"].unique():
        avg_duration = df[df["a_absence_type"] == absence_type]["a_length_absence"].mean()
        print(f"  {absence_type:.<35} {avg_duration:>6.1f} days")

    # Most common diagnoses
    print("\nTop 10 Most Common Diagnoses:")
    top_diagnoses = df["a_diagnosis"].value_counts().head(10)
    for diagnosis, count in top_diagnoses.items():
        if pd.notna(diagnosis):
            print(f"  {diagnosis:.<50} {count:>4}")

    print("\n" + "=" * 70)


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    # Generate dataset
    df = generate_absence_dataset(num_individuals=4000)

    # Print statistics
    print_dataset_statistics(df)

    # Save to CSV
    save_dataset(df, "absence_dataset.csv")

    # Display sample records
    print("\nSample Records (first 10 with absences):")
    print(df[df["a_absence_type"].notna()].head(10).to_string())

    print("\nSample Records (without absences):")
    print(df[df["a_absence_type"].isna()].head(5).to_string())

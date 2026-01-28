"""
Generate synthetic auxiliary healthcare services dataset
"""

import pandas as pd
import random
from datetime import datetime, timedelta


def generate_reference_period(start_year=2020, end_year=2026):
    """Generate year and month in YYYYMM format"""
    year = random.randint(start_year, end_year)
    month = random.randint(1, 12)
    return f"{year}{month:02d}"


def generate_individual_id():
    """Generate pseudonymised individual ID"""
    return f"IND{random.randint(100000, 999999)}"


def generate_act_id():
    """Generate act identification number"""
    return f"ACT{random.randint(1000000, 9999999)}"


def generate_provider_id():
    """Generate healthcare provider ID"""
    return f"PRV{random.randint(10000, 99999)}"


def generate_auxiliary_service_types():
    """Return list of auxiliary healthcare service types"""
    return [
        "Kinésithérapie",
        "Physiothérapie",
        "Ergothérapie",
        "Orthophonie",
        "Psychothérapie",
        "Diététique",
        "Podologie",
        "Soins infirmiers à domicile",
        "Analyses de laboratoire",
        "Imagerie médicale (radiologie)",
        "Imagerie médicale (IRM)",
        "Imagerie médicale (échographie)",
        "Analyses sanguines",
        "Electrocardiogramme (ECG)",
        "Consultation psychologique",
        "Consultation nutritionniste",
        "Soins de plaies",
        "Perfusion à domicile",
        "Prélèvements biologiques",
        "Oxygénothérapie",
    ]


def generate_service_cost(service_type):
    """Generate realistic cost based on service type"""
    cost_ranges = {
        "Kinésithérapie": (35, 65),
        "Physiothérapie": (40, 70),
        "Ergothérapie": (45, 75),
        "Orthophonie": (50, 80),
        "Psychothérapie": (60, 120),
        "Diététique": (50, 90),
        "Podologie": (40, 70),
        "Soins infirmiers à domicile": (30, 60),
        "Analyses de laboratoire": (20, 150),
        "Imagerie médicale (radiologie)": (50, 200),
        "Imagerie médicale (IRM)": (150, 500),
        "Imagerie médicale (échographie)": (80, 180),
        "Analyses sanguines": (25, 100),
        "Electrocardiogramme (ECG)": (30, 80),
        "Consultation psychologique": (70, 130),
        "Consultation nutritionniste": (55, 95),
        "Soins de plaies": (25, 60),
        "Perfusion à domicile": (45, 120),
        "Prélèvements biologiques": (15, 40),
        "Oxygénothérapie": (80, 200),
    }

    min_cost, max_cost = cost_ranges.get(service_type, (30, 100))
    return round(random.uniform(min_cost, max_cost), 2)


def generate_ss_coverage_ratio(service_type):
    """Generate Social Security coverage ratio (typically 80-100%)"""
    # Most services are covered at 80-88%
    # Some preventive services might have different coverage
    coverage_ratios = [0.80, 0.85, 0.88, 0.90, 0.95, 1.00]
    weights = [30, 25, 20, 15, 7, 3]  # Most common is 80%

    return random.choices(coverage_ratios, weights=weights)[0]


def generate_auxiliary_service_record(individual_ids, provider_ids):
    """Generate one auxiliary service record"""

    reference_period = generate_reference_period(2020, 2025)
    individual_id = random.choice(individual_ids)
    act_id = generate_act_id()

    service_types = generate_auxiliary_service_types()
    auxiliary_service_type = random.choice(service_types)

    provider_id = random.choice(provider_ids)

    # Generate cost
    auxiliary_service_cost = generate_service_cost(auxiliary_service_type)

    # Calculate SS coverage
    coverage_ratio = generate_ss_coverage_ratio(auxiliary_service_type)
    auxiliary_service_cost_paid_ss = round(auxiliary_service_cost * coverage_ratio, 2)

    # Number of invoices (typically 1, but can be multiple for recurring services)
    # Services like physiotherapy often have multiple sessions
    if auxiliary_service_type in [
        "Kinésithérapie",
        "Physiothérapie",
        "Orthophonie",
        "Psychothérapie",
    ]:
        auxiliary_service_nb_invoices = random.choices(
            [1, 2, 3, 4, 5, 6, 8, 10, 12], weights=[20, 15, 12, 10, 8, 10, 8, 10, 7]
        )[0]
    else:
        auxiliary_service_nb_invoices = random.choices([1, 2, 3], weights=[75, 20, 5])[0]

    return {
        "reference_period": reference_period,
        "individual_IDnumber": individual_id,
        "act_IDnumber": act_id,
        "auxiliary_service_type": auxiliary_service_type,
        "provider_IDnumber": provider_id,
        "auxiliary_service_cost": auxiliary_service_cost,
        "auxiliary_service_cost_paid_SS": auxiliary_service_cost_paid_ss,
        "auxiliary_service_nb_invoices": auxiliary_service_nb_invoices,
    }


def generate_dataset(n_individuals=200, n_services=1000, n_providers=50):
    """
    Generate complete auxiliary services dataset

    Parameters:
    - n_individuals: Number of unique individuals (default 200)
    - n_services: Number of service records (default 1000)
    - n_providers: Number of unique healthcare providers (default 50)
    """
    print(f"Generating auxiliary services dataset...")
    print(f"Individuals: {n_individuals}, Services: {n_services}, Providers: {n_providers}")

    # Generate unique individual IDs and provider IDs
    individual_ids = [generate_individual_id() for _ in range(n_individuals)]
    provider_ids = [generate_provider_id() for _ in range(n_providers)]

    # Generate service records
    data = []
    for i in range(n_services):
        if (i + 1) % 200 == 0:
            print(f"Generated {i + 1}/{n_services} service records...")
        data.append(generate_auxiliary_service_record(individual_ids, provider_ids))

    df = pd.DataFrame(data)

    # Sort by reference period and individual ID
    df = df.sort_values(["reference_period", "individual_IDnumber"]).reset_index(drop=True)

    print(f"\nDataset generated successfully!")
    print(f"Total records: {len(df)}")
    print(f"Unique individuals: {df['individual_IDnumber'].nunique()}")
    print(f"Unique providers: {df['provider_IDnumber'].nunique()}")
    print(f"Date range: {df['reference_period'].min()} to {df['reference_period'].max()}")

    return df


def print_dataset_summary(df):
    """Print comprehensive dataset summary"""
    print("\n" + "=" * 80)
    print("DATASET SUMMARY")
    print("=" * 80)

    print(f"\n📊 Basic Statistics:")
    print(f"   Total records: {len(df):,}")
    print(f"   Unique individuals: {df['individual_IDnumber'].nunique():,}")
    print(f"   Unique providers: {df['provider_IDnumber'].nunique():,}")
    print(f"   Period range: {df['reference_period'].min()} - {df['reference_period'].max()}")

    print(f"\n💰 Cost Statistics:")
    print(f"   Total service cost: €{df['auxiliary_service_cost'].sum():,.2f}")
    print(f"   Total SS coverage: €{df['auxiliary_service_cost_paid_SS'].sum():,.2f}")
    print(f"   Average service cost: €{df['auxiliary_service_cost'].mean():.2f}")
    print(f"   Average SS coverage: €{df['auxiliary_service_cost_paid_SS'].mean():.2f}")
    print(
        f"   Average coverage ratio: {(df['auxiliary_service_cost_paid_SS'].sum() / df['auxiliary_service_cost'].sum() * 100):.1f}%"
    )

    print(f"\n🏥 Top 10 Service Types:")
    service_counts = df["auxiliary_service_type"].value_counts().head(10)
    for service, count in service_counts.items():
        pct = (count / len(df)) * 100
        print(f"   {service:.<50} {count:>5} ({pct:>5.1f}%)")

    print(f"\n📅 Services per Period (Top 10):")
    period_counts = df["reference_period"].value_counts().head(10)
    for period, count in period_counts.items():
        print(f"   {period}: {count:>5} services")

    print(f"\n🔢 Invoice Distribution:")
    invoice_dist = df["auxiliary_service_nb_invoices"].value_counts().sort_index()
    for n_invoices, count in invoice_dist.items():
        pct = (count / len(df)) * 100
        print(f"   {int(n_invoices)} invoice(s): {count:>5} ({pct:>5.1f}%)")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    # Generate dataset
    df = generate_dataset(n_individuals=200, n_services=1000, n_providers=50)

    # Save to CSV
    output_file = "data_processed/auxiliary_services_synthetic.csv"
    df.to_csv(output_file, index=False, encoding="utf-8-sig")
    print(f"\n✅ Dataset saved to: {output_file}")

    # Print summary
    print_dataset_summary(df)

    # Show sample records
    print("\n📋 Sample Records:")
    print(df.head(10).to_string(index=False))

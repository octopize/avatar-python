"""
Synthetic Job Characteristics Dataset Generator

Generates realistic synthetic job/employment data for 4000 individuals based on Luxembourg's
labor market metadata. Includes realistic scenarios for different employment types, wages,
working hours, and contract types.

Author: Data Generator
Date: January 2026
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

# Job sectors in Luxembourg
JOB_SECTORS = {
    "Finance & Insurance": [
        "Bank Analyst",
        "Financial Advisor",
        "Insurance Broker",
        "Accountant",
        "Auditor",
    ],
    "IT & Technology": [
        "Software Developer",
        "Data Analyst",
        "IT Consultant",
        "System Administrator",
        "DevOps Engineer",
    ],
    "Healthcare": ["Nurse", "Doctor", "Medical Assistant", "Pharmacist", "Physiotherapist"],
    "Education": ["Teacher", "Professor", "Education Assistant", "School Administrator", "Tutor"],
    "Construction": ["Construction Worker", "Electrician", "Plumber", "Carpenter", "Site Manager"],
    "Retail & Commerce": ["Sales Associate", "Store Manager", "Cashier", "Buyer", "Merchandiser"],
    "Hospitality": ["Chef", "Waiter", "Hotel Manager", "Receptionist", "Housekeeper"],
    "Manufacturing": [
        "Machine Operator",
        "Quality Controller",
        "Production Manager",
        "Warehouse Worker",
        "Technician",
    ],
    "Transportation": [
        "Truck Driver",
        "Bus Driver",
        "Logistics Coordinator",
        "Delivery Driver",
        "Dispatcher",
    ],
    "Public Administration": [
        "Administrative Assistant",
        "Civil Servant",
        "Policy Analyst",
        "Urban Planner",
        "Social Worker",
    ],
    "Agriculture": [
        "Farmer",
        "Agricultural Worker",
        "Vineyard Worker",
        "Farm Manager",
        "Agricultural Technician",
    ],
}

# Contract types
CONTRACT_TYPES = {
    "0": "Permanent contract",
    "1": "Fixed-term contract",
    "2": "Temporary contract",
    "3": "Apprenticeship contract",
    "4": "Summer or student job",
}

# Job status types
JOB_STATUS = {"0": "Private sector worker", "1": "Civil servant", "2": "Self-employed"}

# NACE sectors (simplified)
NACE_SECTORS = [
    "K64",
    "K65",
    "K66",  # Financial services
    "J62",
    "J63",  # IT services
    "Q86",
    "Q87",  # Healthcare
    "P85",  # Education
    "F41",
    "F42",
    "F43",  # Construction
    "G47",  # Retail
    "I56",  # Food services
    "C10",
    "C20",
    "C30",  # Manufacturing
    "H49",
    "H52",  # Transportation
    "O84",  # Public administration
    "A01",
    "A02",  # Agriculture
]

# Minimum wage in Luxembourg (2026 est.)
MINIMUM_WAGE_HOURLY = 15.50  # EUR
NORMAL_MONTHLY_HOURS = 173  # Standard monthly hours

# ============================================================================
# GENERATOR FUNCTIONS
# ============================================================================


def generate_id(prefix, length=10):
    """Generate pseudonymised ID"""
    return prefix + "".join([str(random.randint(0, 9)) for _ in range(length)])


def generate_reference_period():
    """Generate year-month reference period"""
    year = random.choice([2024, 2025, 2026])
    month = random.randint(1, 12)
    return f"{year}{month:02d}"


def random_date_yyyymm(start_year=2015, end_year=2026):
    """Generate random date in YYYYMM format"""
    year = random.randint(start_year, end_year)
    month = random.randint(1, 12)
    return f"{year}{month:02d}"


def select_job_status():
    """Select job status with realistic distribution"""
    # 70% private, 20% civil servant, 10% self-employed
    return random.choices(list(JOB_STATUS.keys()), weights=[0.70, 0.20, 0.10])[0]


def select_contract_type(job_status):
    """Select contract type based on job status"""
    if job_status == "1":  # Civil servant - permanent
        return "0"
    elif job_status == "2":  # Self-employed - not applicable
        return "-9"
    else:  # Private sector
        # 70% permanent, 20% fixed-term, 5% temporary, 3% apprentice, 2% student
        return random.choices(["0", "1", "2", "3", "4"], weights=[0.70, 0.20, 0.05, 0.03, 0.02])[0]


def generate_job_duration(contract_type):
    """Generate job start and end dates based on contract type"""
    start_year = random.randint(2015, 2025)
    start_month = random.randint(1, 11)
    start_date = f"{start_year}{start_month:02d}"

    if contract_type == "0":  # Permanent - no end date or future end
        if random.random() < 0.85:  # 85% still active
            end_date = None
            planned_end = "999909"
            planned_duration = "-9"
        else:  # 15% ended
            end_year = random.randint(start_year, 2026)
            if end_year == start_year:
                end_month = random.randint(start_month + 1, 12)
            else:
                end_month = random.randint(1, 12)
            end_date = f"{end_year}{end_month:02d}"
            planned_end = "999909"
            planned_duration = "-9"

    elif contract_type == "1":  # Fixed-term
        duration_category = random.choices(
            ["0", "1", "2", "3", "4", "5", "6"], weights=[0.05, 0.10, 0.15, 0.30, 0.25, 0.10, 0.05]
        )[0]

        duration_months = {"0": 0.5, "1": 1, "2": 1.5, "3": 4, "4": 9, "5": 18, "6": 30}[
            duration_category
        ]

        end_year = start_year
        end_month = start_month + int(duration_months)
        while end_month > 12:
            end_month -= 12
            end_year += 1

        if end_year > 2026 or (end_year == 2026 and end_month > 1):
            end_date = None  # Still active
        else:
            end_date = f"{end_year}{end_month:02d}"

        planned_end = f"{end_year}{end_month:02d}"
        planned_duration = duration_category

    elif contract_type == "3":  # Apprenticeship - typically 2-3 years
        duration_months = random.choice([24, 36])
        end_year = start_year + (duration_months // 12)
        end_month = start_month

        if end_year > 2026:
            end_date = None
        else:
            end_date = f"{end_year}{end_month:02d}"

        planned_end = f"{end_year}{end_month:02d}"
        planned_duration = "5"  # 12-24 months category

    elif contract_type == "4":  # Summer/student job - 1-3 months
        duration_months = random.randint(1, 3)
        end_year = start_year
        end_month = start_month + duration_months
        if end_month > 12:
            end_month -= 12
            end_year += 1

        end_date = f"{end_year}{end_month:02d}"
        planned_end = end_date
        planned_duration = random.choice(["0", "1", "2"])

    else:  # Temporary or other
        duration_months = random.randint(1, 6)
        end_year = start_year
        end_month = start_month + duration_months
        if end_month > 12:
            end_month -= 12
            end_year += 1

        if end_year > 2026:
            end_date = None
        else:
            end_date = f"{end_year}{end_month:02d}"

        planned_end = f"{end_year}{end_month:02d}"
        planned_duration = random.choice(["2", "3", "4"])

    return start_date, end_date, planned_end, planned_duration


def is_blue_collar(sector):
    """Determine if job is blue collar based on sector"""
    blue_collar_sectors = [
        "Construction",
        "Manufacturing",
        "Transportation",
        "Agriculture",
        "Hospitality",
    ]
    return "1" if sector in blue_collar_sectors else "0"


def generate_wage(job_status, is_blue_collar_worker, hours_worked):
    """Generate realistic wages based on job characteristics"""
    if job_status == "2":  # Self-employed - not applicable
        return None, None, None, None, None

    # Base hourly wage varies by sector and skill level
    if job_status == "1":  # Civil servant - higher wages
        hourly_base = random.uniform(22, 45)
    elif is_blue_collar_worker == "1":
        hourly_base = random.uniform(15.5, 28)
    else:  # White collar
        hourly_base = random.uniform(18, 50)

    # Calculate monthly base wage
    base_wage = hourly_base * hours_worked if hours_worked else hourly_base * NORMAL_MONTHLY_HOURS

    # Additional wage (bonuses, commissions) - 30% chance
    if random.random() < 0.30:
        additional_wage = random.uniform(100, 1000)
    else:
        additional_wage = 0

    # Overtime - 15% chance
    if random.random() < 0.15 and job_status != "1":
        overtime_hours = random.uniform(5, 20)
        overtime_wage = hourly_base * 1.5 * overtime_hours
    else:
        overtime_hours = 0
        overtime_wage = 0

    total_wage = base_wage + additional_wage + overtime_wage

    return (
        round(base_wage, 2),
        round(additional_wage, 2),
        round(overtime_wage, 2),
        round(total_wage, 2),
        overtime_hours,
    )


def generate_working_hours(job_status, contract_type):
    """Generate realistic working hours"""
    if job_status == "2":  # Self-employed - not applicable
        return None, None, None, None, None

    # Base hours vary by contract type
    if contract_type == "4":  # Student job - part time
        base_hours = random.uniform(60, 120)
    elif contract_type == "3":  # Apprenticeship
        base_hours = random.uniform(140, 173)
    else:  # Full time
        base_hours = random.uniform(160, 173)

    # Overtime - 15% of workers
    if random.random() < 0.15:
        overtime_hours = random.uniform(5, 20)
    else:
        overtime_hours = 0

    total_hours = base_hours + overtime_hours

    # Adjusted hours (calendar effect)
    base_hours_adj = base_hours * random.uniform(0.98, 1.02)
    total_hours_adj = total_hours * random.uniform(0.98, 1.02)

    return (
        round(base_hours, 2),
        round(overtime_hours, 2),
        round(total_hours, 2),
        round(base_hours_adj, 2),
        round(total_hours_adj, 2),
    )


def generate_trial_period(contract_type, start_date):
    """Generate trial period information"""
    if contract_type in ["0", "1"]:  # Permanent or fixed-term - 70% have trial period
        if random.random() < 0.70:
            trial_weeks = random.choice([4, 6, 8, 12, 26])  # Common trial periods

            # Calculate end date
            start_year = int(start_date[:4])
            start_month = int(start_date[4:6])
            trial_months = trial_weeks // 4
            end_month = start_month + trial_months
            end_year = start_year
            if end_month > 12:
                end_month -= 12
                end_year += 1

            trial_end = f"{end_year}{end_month:02d}"
            return "1", trial_end, float(trial_weeks)
        else:
            return "0", None, None
    else:
        return "-9", None, None


def generate_special_statuses():
    """Generate special employment statuses"""
    # Posted worker - 2% of private sector
    posted = "1" if random.random() < 0.02 else "0"

    # Assisting family member - 1% (mainly agriculture/commerce)
    assisting_family = "1" if random.random() < 0.01 else "0"

    # Maternity leave - 3% of workers at any time
    maternity_leave = "1" if random.random() < 0.03 else "0"

    # Activation measure (ADEM program) - 5%
    activation = "1" if random.random() < 0.05 else "0"
    activation_type = (
        random.choice(
            [
                "CAE - Contrat d'appui-emploi",
                "CIE - Contrat d'initiation à l'emploi",
                "PAN - Projet d'activité national",
            ]
        )
        if activation == "1"
        else None
    )

    # Short-time working (chômage partiel) - 8%
    short_time = "1" if random.random() < 0.08 else "0"

    return posted, assisting_family, maternity_leave, activation, activation_type, short_time


def generate_job_record(individual_id):
    """Generate a complete job record for an individual"""
    job_id = generate_id("JOB", 12)
    employer_id = generate_id("EMP", 10)
    reference_period = generate_reference_period()

    # Job status determines many other fields
    job_status = select_job_status()
    contract_type = select_contract_type(job_status)

    # Generate dates
    start_date, end_date, planned_end, planned_duration = generate_job_duration(contract_type)

    # Sector and blue collar status
    sector = random.choice(list(JOB_SECTORS.keys()))
    blue_collar = is_blue_collar(sector) if job_status != "2" else "-8"

    # Working hours
    base_hours, overtime_hours, total_hours, base_hours_adj, total_hours_adj = (
        generate_working_hours(job_status, contract_type)
    )

    # Wages
    if base_hours:
        base_wage, additional_wage, overtime_wage, total_wage, ot_hours = generate_wage(
            job_status, blue_collar, base_hours
        )
        if ot_hours:
            overtime_hours = ot_hours
            total_hours = base_hours + overtime_hours
            total_hours_adj = base_hours_adj + overtime_hours
    else:
        base_wage = additional_wage = overtime_wage = total_wage = None

    # Calculate hourly wages
    if base_hours_adj and base_wage:
        hourly_base = round(base_wage / base_hours_adj, 2)
    else:
        hourly_base = None

    if total_hours_adj and total_wage:
        hourly_total = round(total_wage / total_hours_adj, 2)
    else:
        hourly_total = None

    # Trial period
    trial_period, trial_end, trial_weeks = generate_trial_period(contract_type, start_date)

    # Special statuses
    posted, assisting_family, maternity_leave, activation, activation_type, short_time = (
        generate_special_statuses()
    )

    # Short-time working details
    if short_time == "1" and base_wage and base_hours:
        short_time_benefit = round(base_wage * 0.3, 2)  # 30% of wage
        short_time_hours = round(base_hours * 0.3, 2)  # 30% of hours
    else:
        short_time_benefit = None
        short_time_hours = None

    # Temporary jobs employer (5% of cases)
    temp_employer = generate_id("TMP", 10) if random.random() < 0.05 else "-9"

    # Official statistics inclusion (95% included)
    official_stat = "1" if random.random() < 0.95 else "0"

    # Build record
    record = {
        "reference_period": reference_period,
        "job_IDnumber": job_id,
        "individual_IDnumber": individual_id,
        "employer_IDnumber": employer_id if job_status != "2" else "-9",
        "temporary_jobs_employer_IDnumber": temp_employer,
        "j_job_start_date": start_date,
        "j_job_end_effective_date": end_date if end_date else None,
        "j_contract_type": contract_type,
        "j_job_end_planned_date": planned_end,
        "j_contract_planned_duration": planned_duration,
        "j_job_status": job_status,
        "j_blue_collar": blue_collar,
        "j_posted_worker": posted if job_status != "2" else "-9",
        "j_assisting_family_member": assisting_family,
        "j_maternity_leave": maternity_leave,
        "j_activation_measure": activation,
        "j_activation_measure_type": activation_type,
        "j_trial_period": trial_period,
        "j_trial_period_end_date": trial_end,
        "j_trial_period_length": trial_weeks,
        "j_F_short_time_working": short_time if job_status != "2" else "-9",
        "j_short_time_working_benefit": short_time_benefit,
        "j_short_time_working_hours": short_time_hours,
        "j_F_month_base_wage": "1" if base_wage else ("-9" if job_status == "2" else "-8"),
        "j_month_base_wage": base_wage,
        "j_F_month_additionnal_wage": "1"
        if additional_wage and additional_wage > 0
        else ("-9" if job_status == "2" else "-8"),
        "j_month_additionnal_wage": additional_wage
        if additional_wage and additional_wage > 0
        else None,
        "j_F_month_overtime_wage": "1"
        if overtime_wage and overtime_wage > 0
        else ("-9" if job_status == "2" else "-8"),
        "j_month_overtime_wage": overtime_wage if overtime_wage and overtime_wage > 0 else None,
        "j_F_month_total_wage": "1" if total_wage else ("-9" if job_status == "2" else "-8"),
        "j_month_total_wage": total_wage,
        "j_F_nb_base_worked_hours": "1" if base_hours else ("-9" if job_status == "2" else "-8"),
        "j_nb_base_worked_hours": base_hours,
        "j_F_nb_overtime_paid_hours": "1"
        if overtime_hours and overtime_hours > 0
        else ("-9" if job_status == "2" else "-8"),
        "j_nb_overtime_paid_hours": overtime_hours
        if overtime_hours and overtime_hours > 0
        else None,
        "j_F_nb_total_worked_hours": "1" if total_hours else ("-9" if job_status == "2" else "-8"),
        "j_nb_total_worked_hours": total_hours,
        "j_F_nb_base_worked_hours_ADJ": "1"
        if base_hours_adj
        else ("-9" if job_status == "2" else "-8"),
        "j_nb_base_worked_hours_ADJ": base_hours_adj,
        "j_F_nb_total_worked_hours_ADJ": "1"
        if total_hours_adj
        else ("-9" if job_status == "2" else "-8"),
        "j_nb_total_worked_hours_ADJ": total_hours_adj,
        "j_F_hourly_base_wage": "1" if hourly_base else ("-9" if job_status == "2" else "-8"),
        "j_hourly_base_wage": hourly_base,
        "j_F_hourly_total_wage": "1" if hourly_total else ("-9" if job_status == "2" else "-8"),
        "j_hourly_total_wage": hourly_total,
        "j_F_official_stat": official_stat,
    }

    return record


def generate_job_dataset(num_individuals=4000):
    """
    Generate synthetic job characteristics dataset

    Args:
        num_individuals: Number of unique individuals (default: 4000)

    Returns:
        pandas.DataFrame: Dataset with job records
    """
    print(f"Generating job characteristics dataset for {num_individuals} individuals...")

    all_jobs = []

    for i in range(num_individuals):
        if (i + 1) % 500 == 0:
            print(f"  Generated {i + 1}/{num_individuals} individuals...")

        # Generate unique individual ID
        individual_id = generate_id("ID", 10)

        # Some individuals may have multiple jobs (10%)
        num_jobs = random.choices([1, 2], weights=[0.90, 0.10])[0]

        for _ in range(num_jobs):
            job_record = generate_job_record(individual_id)
            all_jobs.append(job_record)

    # Create DataFrame
    df = pd.DataFrame(all_jobs)

    print(f"\nDataset generation complete!")
    print(f"  Total individuals: {num_individuals}")
    print(f"  Total job records: {len(df)}")

    return df


def save_dataset(df, filename="job_characteristics_dataset.csv"):
    """Save dataset to CSV file"""
    output_path = DATA_PROCESSED / filename
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"\nDataset saved to: {output_path}")
    return output_path


def print_dataset_statistics(df):
    """Print statistics about the generated dataset"""
    print("\n" + "=" * 70)
    print("JOB CHARACTERISTICS DATASET STATISTICS")
    print("=" * 70)

    print(f"\nTotal job records: {len(df)}")
    print(f"Unique individuals: {df['individual_IDnumber'].nunique()}")
    print(
        f"Unique employers: {df[df['employer_IDnumber'] != '-9']['employer_IDnumber'].nunique()}"
    )

    # Job status distribution
    print("\nJob Status Distribution:")
    for status_code, status_name in JOB_STATUS.items():
        count = (df["j_job_status"] == status_code).sum()
        percentage = (count / len(df)) * 100
        print(f"  {status_name:.<35} {count:>5} ({percentage:>5.1f}%)")

    # Contract type distribution
    print("\nContract Type Distribution:")
    for contract_code, contract_name in CONTRACT_TYPES.items():
        count = (df["j_contract_type"] == contract_code).sum()
        percentage = (
            (count / len(df[df["j_contract_type"] != "-9"])) * 100
            if len(df[df["j_contract_type"] != "-9"]) > 0
            else 0
        )
        print(f"  {contract_name:.<35} {count:>5} ({percentage:>5.1f}%)")

    # Wage statistics (private sector only)
    private_sector = df[df["j_month_total_wage"].notna()]
    if len(private_sector) > 0:
        print("\nMonthly Wage Statistics (EUR):")
        print(f"  Mean: {private_sector['j_month_total_wage'].mean():,.2f}")
        print(f"  Median: {private_sector['j_month_total_wage'].median():,.2f}")
        print(f"  Min: {private_sector['j_month_total_wage'].min():,.2f}")
        print(f"  Max: {private_sector['j_month_total_wage'].max():,.2f}")

        print("\nHourly Wage Statistics (EUR):")
        hourly_data = df[df["j_hourly_total_wage"].notna()]
        if len(hourly_data) > 0:
            print(f"  Mean: {hourly_data['j_hourly_total_wage'].mean():.2f}")
            print(f"  Median: {hourly_data['j_hourly_total_wage'].median():.2f}")
            print(f"  Min: {hourly_data['j_hourly_total_wage'].min():.2f}")
            print(f"  Max: {hourly_data['j_hourly_total_wage'].max():.2f}")

    # Working hours statistics
    hours_data = df[df["j_nb_total_worked_hours"].notna()]
    if len(hours_data) > 0:
        print("\nMonthly Working Hours Statistics:")
        print(f"  Mean: {hours_data['j_nb_total_worked_hours'].mean():.1f}")
        print(f"  Median: {hours_data['j_nb_total_worked_hours'].median():.1f}")
        print(f"  Min: {hours_data['j_nb_total_worked_hours'].min():.1f}")
        print(f"  Max: {hours_data['j_nb_total_worked_hours'].max():.1f}")

    # Special statuses
    print("\nSpecial Employment Statuses:")
    print(f"  Blue collar workers: {(df['j_blue_collar'] == '1').sum()}")
    print(f"  Posted workers: {(df['j_posted_worker'] == '1').sum()}")
    print(f"  Maternity leave: {(df['j_maternity_leave'] == '1').sum()}")
    print(f"  Activation measures: {(df['j_activation_measure'] == '1').sum()}")
    print(f"  Short-time working: {(df['j_F_short_time_working'] == '1').sum()}")
    print(f"  Trial period: {(df['j_trial_period'] == '1').sum()}")

    print("\n" + "=" * 70)


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    # Generate dataset
    df = generate_job_dataset(num_individuals=4000)

    # Print statistics
    print_dataset_statistics(df)

    # Save to CSV
    save_dataset(df, "job_characteristics_dataset.csv")

    # Display sample records
    print("\nSample Records (first 5):")
    sample_cols = [
        "individual_IDnumber",
        "j_job_status",
        "j_contract_type",
        "j_month_total_wage",
        "j_nb_total_worked_hours",
        "j_hourly_total_wage",
    ]
    print(df[sample_cols].head(10).to_string())

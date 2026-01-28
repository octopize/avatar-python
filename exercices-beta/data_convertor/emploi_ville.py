import pandas as pd
from pathlib import Path

# Define paths
DATA_SOURCE = Path(__file__).parent.parent / "data_source"
INPUT_FILE = DATA_SOURCE / "Emploi_ville.csv"
DATA_PROCESSED = Path(__file__).parent.parent / "data_processed"


def load_and_transform_employment_data(reference_date: str = "2025.09.30") -> pd.DataFrame:
    """
    Load employment data, filter by reference date, and pivot to create
    employment columns by gender and status.

    Args:
        reference_date: The date to filter on (default: "2025.09.30")

    Returns:
        DataFrame with columns:
        - Canton, Commune
        - nb_homme_salarie, nb_femme_salarie
        - nb_homme_non_salarie, nb_femme_non_salarie
        - employ_rate, employ_woman_rate, employ_men_rate
    """
    # Load the CSV file
    df = pd.read_csv(INPUT_FILE)

    # Filter by reference date
    df_filtered = df[df["Date de référence"] == reference_date].copy()

    # Create a combined key for pivoting
    df_filtered["genre_statut"] = df_filtered["Genre"] + "_" + df_filtered["Statut"]

    # Pivot the data to get columns for each combination of Genre and Statut
    df_pivot = df_filtered.pivot_table(
        index=["Canton", "Commune"],
        columns="genre_statut",
        values="Nombre de personnes en emploi",
        aggfunc="sum",
    ).reset_index()

    # Rename columns to match requested format
    column_mapping = {
        "Hommes_Salariés": "nb_homme_salarie",
        "Femmes_Salariés": "nb_femme_salarie",
        "Hommes_Non-salariés": "nb_homme_non_salarie",
        "Femmes_Non-salariés": "nb_femme_non_salarie",
    }
    df_pivot = df_pivot.rename(columns=column_mapping)

    # Calculate total employed by gender
    df_pivot["total_hommes"] = df_pivot["nb_homme_salarie"] + df_pivot["nb_homme_non_salarie"]
    df_pivot["total_femmes"] = df_pivot["nb_femme_salarie"] + df_pivot["nb_femme_non_salarie"]
    df_pivot["total_employes"] = df_pivot["total_hommes"] + df_pivot["total_femmes"]

    # Calculate employment rates (proportion of each category)
    # employ_rate: ratio of salaried to total employed
    df_pivot["employ_rate"] = (
        (df_pivot["nb_homme_salarie"] + df_pivot["nb_femme_salarie"]) / df_pivot["total_employes"]
    ).round(4)

    # employ_woman_rate: proportion of women in total employed
    df_pivot["employ_woman_rate"] = (
        df_pivot["nb_femme_salarie"] / df_pivot["total_femmes"]
    ).round(4)

    # employ_men_rate: proportion of men in total employed
    df_pivot["employ_men_rate"] = (df_pivot["nb_homme_salarie"] / df_pivot["total_hommes"]).round(
        4
    )

    # Select and order final columns
    final_columns = [
        "Canton",
        "Commune",
        "nb_homme_salarie",
        "nb_femme_salarie",
        "nb_homme_non_salarie",
        "nb_femme_non_salarie",
        "employ_rate",
        "employ_woman_rate",
        "employ_men_rate",
        "total_employes",
    ]

    return df_pivot[final_columns]


if __name__ == "__main__":
    # Process the data
    result = load_and_transform_employment_data("2025.09.30")

    # Display results
    print(f"Processed {len(result)} communes")
    print("\nFirst 10 rows:")
    print(result.head(10).to_string(index=False))

    # Save to CSV
    output_file = DATA_PROCESSED / "Emploi_ville_processed.csv"
    result.to_csv(output_file, index=False)
    print(f"\nResults saved to: {output_file}")

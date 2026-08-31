# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.19.4
# ---

# %% [markdown]
# # Tutorial 8 Pseudonymization (Beta)
#
# > **⚠️ Beta Feature** — Pseudonymization is currently in beta. The API and behavior may
# > change in future releases.
#
# In this tutorial, you'll learn how to use Avatar's pseudonymization capabilities to replace
# personally identifiable information (PII) with artificial values while preserving referential
# integrity across tables.
#
# Pseudonymization is an optional post-processing step that runs after avatarization. PII columns
# are set aside before the Avatar method runs and reattached with pseudonymized values in the output.

# %% [markdown]
# ## Connection

# %%
import os

import pandas as pd

from avatars import (
    FakeDataStrategy,
    Manager,
    PiiType,
    SpecificIdStrategy,
    Uuid4Strategy,
)

# %%
manager = Manager(
    api_key=os.environ.get("AVATAR_API_KEY")
)  # or Manager(api_key="...", base_url="https://your-server.com")

# %% [markdown]
# ## What is Pseudonymization?
#
# Pseudonymization replaces direct identifiers (names, emails, phone numbers, etc.) with
# artificial substitutes. Unlike anonymization — which transforms the statistical content of the
# data — pseudonymization focuses on replacing identifiable values.
#
# In the Avatar platform, pseudonymization and anonymization are **complementary**:
# - The **Avatar method** anonymizes the statistical content of the data
# - **Pseudonymization** replaces direct identifiers with fake or hashed values
#
# Six strategies are available:
#
# | Strategy | Description | Consistent by default |
# |----------|-------------|:---:|
# | `FakeDataStrategy` | Realistic fake values matching PII type | Yes |
# | `HashSha256Strategy` | SHA-256 hash (deterministic, one-way) | Always |
# | `Uuid4Strategy` | Random UUID version 4 | Yes |
# | `ConstantStrategy` | Fixed constant string for all rows | N/A |
# | `IntegerStrategy` | Unique pseudonymous integer (randomized order) | Yes |
# | `SpecificIdStrategy` | Structured ID from a user-defined pattern | Yes |

# %% [markdown]
# ## Sample Data
#

# %%
patients_df = pd.read_csv("../fixtures/pseudo_data.csv")
patients_df.head()

# %% [markdown]
# ## Single-Table Pseudonymization
#
# Let's pseudonymize the PII columns using different strategies:
# - `email` → `FakeDataStrategy` with `PiiType.EMAIL` (generates realistic fake emails)
# - `first_name` → `FakeDataStrategy` with `PiiType.FIRST_NAME` (generates realistic fake names)
# - `ssn` → `Uuid4Strategy` (replaces with random UUIDs)

# %%
runner = manager.create_runner("pseudo_single_table")

runner.add_table("patients", data=patients_df, primary_key="ssn")

runner.set_parameters(
    "patients",
    k=3,
    pseudonymized_columns={
        "first_name": FakeDataStrategy(pii_type=PiiType.FIRST_NAME),
        "last_name": FakeDataStrategy(pii_type=PiiType.LAST_NAME),
        "ssn": Uuid4Strategy(),
        "email": FakeDataStrategy(pii_type=PiiType.EMAIL),
        "phone": FakeDataStrategy(pii_type=PiiType.PHONE),
        "address": FakeDataStrategy(pii_type=PiiType.ADDRESS),
        "zip_code": SpecificIdStrategy(pattern="#####"),
    },
    use_categorical_reduction=True,
)

runner.run()

# %%
result_patient = runner.shuffled(table_name="patients")

result_patient.head()

# %% [markdown]
# Notice how:
# - The `email` column now contains realistic but fake email addresses
# - The `first_name` column contains different first names
# - The `ssn` column contains UUIDs instead of the original social security numbers
# - The other columns have been anonymized by the Avatar method

# %% [markdown]
# ## Comparing Strategies
#
# Let's compare the pseudonymization strategies on the same column
# to understand their differences.

# %% [markdown]
# ### Strategy: FakeDataStrategy
#
# Generates realistic fake values. Requires specifying the PII type.
# By default (`consistent=True`), the same source value maps to the same fake value within a run.

# %%
# parameters:  "email": FakeDataStrategy(pii_type=PiiType.EMAIL),
result_patient["email"].head()

# %% [markdown]
# ### Strategy: SpecificIdStrategy
#
# Generates structured identifiers from a user-defined pattern. Placeholders:
# - `#` — random digit (0–9)
# - `?` — random letter (case controlled by `letter_case`)
# - `^` — random alphanumeric character (a–z, 0–9)
# - `{{col}}` — value of another column for the same row
#
# Prefix a placeholder with `\` to include it literally (e.g. `\#` outputs `#`).
#
# By default (`consistent=True`), the same source value maps to the same generated ID within a run.

# %%
# parameters:  "zip_code": SpecificIdStrategy(pattern="#####"),

result_patient["zip_code"].head()

# %% [markdown]
# ### Strategy: Uuid4Strategy
#
# Generates random UUIDs. By default (`consistent=True`), the same source value maps to the same
# UUID within a run. Pass `consistent=False` to generate a fresh UUID for every row.

# %%
# parameters:  "ssn": Uuid4Strategy(),

result_patient["ssn"].head()

# %% [markdown]
# ## Multi-Table Pseudonymization with Referential Integrity
#
# When working with related tables, pseudonymization automatically maintains referential
# integrity. A pseudonymized primary key in the parent table is consistently applied to
# matching foreign keys in child tables.
#
# **You only need to configure pseudonymization on the parent table's primary key** — child
# table foreign keys automatically inherit the mapping.

# %%
parents_df = pd.DataFrame(
    {
        "patient_id": ["P001", "P002", "P003", "P004", "P005"],
        "email": [
            "alice@hospital.org",
            "bob@hospital.org",
            "claire@hospital.org",
            "david@hospital.org",
            "emma@hospital.org",
        ],
        "first_name": ["Alice", "Bob", "Claire", "David", "Emma"],
        "age": [34, 45, 28, 52, 41],
    }
)

visits_df = pd.DataFrame(
    {
        "visit_id": ["V001", "V002", "V003", "V004", "V005", "V006", "V007"],
        "patient_id": ["P001", "P001", "P002", "P003", "P003", "P004", "P005"],
        "date": [
            "2024-01-15",
            "2024-03-22",
            "2024-02-10",
            "2024-01-05",
            "2024-04-18",
            "2024-02-28",
            "2024-03-10",
        ],
        "diagnosis_code": ["J06", "J20", "I10", "E11", "E11", "J06", "I10"],
    }
)

print("Patients table:")
print(parents_df.to_string(index=False))
print("\nVisits table:")
print(visits_df.to_string(index=False))

# %% [markdown]
# Notice that `patient_id` appears in both tables. When we pseudonymize it in the parent
# table, the same mapping is automatically applied in the child table.

# %%
runner_multi = manager.create_runner("pseudo_multi_table")

runner_multi.add_table("patients", data=parents_df, primary_key="patient_id")
runner_multi.add_table(
    "visits",
    data=visits_df,
    primary_key="visit_id",
    foreign_keys=["patient_id"],
)

runner_multi.add_link(
    parent_table_name="patients",
    child_table_name="visits",
    parent_field="patient_id",
    child_field="patient_id",
)

# Configure pseudonymization only on the parent table
runner_multi.set_parameters(
    "patients",
    k=3,
    pseudonymized_columns={
        "patient_id": Uuid4Strategy(),
        "email": FakeDataStrategy(pii_type=PiiType.EMAIL),
        "first_name": FakeDataStrategy(pii_type=PiiType.FIRST_NAME),
    },
)

runner_multi.set_parameters("visits", k=3)

runner_multi.run()

# %%
patients = runner_multi.shuffled("patients")
visits = runner_multi.shuffled("visits")

print("Pseudonymized patients:")
print(patients.to_string(index=False))
print("\nPseudonymized visits:")
print(visits.to_string(index=False))

# %% [markdown]
# Observe that:
# - `patient_id` values in the **visits** table match the pseudonymized `patient_id` values
#   in the **patients** table — referential integrity is preserved
# - No explicit pseudonymization configuration was needed on the visits table's `patient_id`
#   column — it was automatically inherited from the parent

# %% [markdown]
# ## Choosing the Right Strategy
#
# | Use Case | Recommended Strategy | Why |
# |----------|---------------------|-----|
# | Realistic-looking data for testing / demos | `FakeDataStrategy` | Human-readable, structurally valid values |
# | Linking datasets across systems or runs | `HashSha256Strategy` | Same input always produces the same hash |
# | Unique opaque identifiers (PKs, IDs) | `Uuid4Strategy` | Guaranteed uniqueness, no info leakage |
# | Full suppression / redaction | `ConstantStrategy` | All rows get the same placeholder |
# | Numeric identifiers expected downstream | `IntegerStrategy` | Preserves integer type, randomized mapping |
# | Structured IDs with a known format | `SpecificIdStrategy` | Custom patterns (e.g. `EMP-####`, `{{dept}}-???`) |
#
# **Tips:**
# - Use `FakeDataStrategy` when the output needs to look realistic (e.g. user acceptance testing)
# - Use `HashSha256Strategy` when consistency across multiple runs or datasets is required
# - Use `Uuid4Strategy` for primary keys where uniqueness matters more than readability
# - Use `ConstantStrategy` to suppress a column entirely (e.g. free-text notes)
# - Use `IntegerStrategy` when downstream code expects integer IDs
# - Use `SpecificIdStrategy` when IDs must follow a corporate or regulatory format
# - `FakeDataStrategy` requires a `pii_type`; all other strategies work without it
# - Pass `consistent=False` to any consistent strategy to generate an independent value per row

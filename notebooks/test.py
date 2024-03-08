import numpy as np
import pandas as pd
import os
import saiph
#poetry add saiph 
#pyproject.toml avatar-python
#make install 
import seaborn as sns
import missingno as msno
import matplotlib.pyplot as plt
from scipy.spatial import distance_matrix

url = os.environ.get("AVATAR_BASE_URL")
username = os.environ.get("AVATAR_USERNAME")
password = os.environ.get("AVATAR_PASSWORD")

from avatars.client import ApiClient
from avatars.models import AvatarizationJobCreate, AvatarizationParameters, PrivacyMetricsMultiTableJobCreate, AvatarizationMultiTableJobCreate
from avatars.models import ReportCreate
from avatars.models import TableReference, TableLink, PrivacyMetricsParameters, PrivacyMetricsMultiTableParameters, AvatarizationMultiTableParameters
from avatars.models import Projections
from scipy.optimize import linear_sum_assignment
client = ApiClient(base_url=url)
client.authenticate(username=username, password=password)

patient = pd.read_csv('fixtures/patient.csv').drop(columns=['Unnamed: 0'])
doctor = pd.read_csv('fixtures/doctor.csv').drop(columns=['Unnamed: 0']).rename(columns={"age":"age_doctor"})
visit =  pd.read_csv('fixtures/visit.csv').drop(columns=['Unnamed: 0'])


dataset_patient = client.pandas_integration.upload_dataframe(patient,
                                                             name="patient",
                                                             identifier_variables="patient_id")

dataset_doctor = client.pandas_integration.upload_dataframe(doctor,
                                                            name="doctor",
                                                            identifier_variables=["doctor_id"])
dataset_visit = client.pandas_integration.upload_dataframe(visit,
                                                          name="visit",
                                                          identifier_variables=["visit_id", "patient_id", "doctor_id"])

# TABLE LINKS
doctor_ref = TableReference(
    dataset_id=dataset_doctor.id,
    is_individual_level=True,
)
patient_ref = TableReference(
    dataset_id=dataset_patient.id,
    is_individual_level=True,
)
visit_ref = TableReference(
    dataset_id=dataset_visit.id,
    is_individual_level=False,
)


table_links = [
    TableLink(
        parent_table=patient_ref,
        child_table=visit_ref,
        link_method="bottom_projection",
        parent_link_key="patient_id",
        child_link_key="patient_id",
    ),
    TableLink(
        parent_table=doctor_ref,
        child_table=visit_ref,
        link_method="bottom_projection",
        parent_link_key="doctor_id",
        child_link_key="doctor_id",
    ),
]


privacy_parameters_test = parameters = [
    PrivacyMetricsParameters(
        original_id=dataset_patient.id,
        unshuffled_avatars_id=dataset_patient.id,
    ),
    PrivacyMetricsParameters(
        original_id=dataset_doctor.id,
        unshuffled_avatars_id=dataset_doctor.id,
    ),
    PrivacyMetricsParameters(
        original_id=dataset_visit.id,
        unshuffled_avatars_id=dataset_visit.id,
    ),
]

privacy_job_test = client.jobs.create_privacy_metrics_multi_table_job(
    PrivacyMetricsMultiTableJobCreate(
        parameters=PrivacyMetricsMultiTableParameters(
            table_links=table_links,
            table_parameters=privacy_parameters_test,
        )
    )
)

privacy_job_test = client.jobs.get_privacy_metrics_multi_table_job(privacy_job_test.id, timeout=1000)

print(privacy_job_test)
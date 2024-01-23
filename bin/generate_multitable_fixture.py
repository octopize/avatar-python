import numpy as np
import pandas as pd

nb_visit = 300
nb_doctor = 50
nb_female = 100
nb_male = 50
nb_patient = nb_female + nb_male
nb_pediatrician = 10
nb_general = 40

mean_age_female = 70
mean_age_male = 60
mean_height_female = 165
mean_height_male = 180
mean_random_noise = 0
mean_age_pediatrician = 40
mean_age_general = 55
std = 5


def table_patient_bigger() -> None:
    """Generate a fake patient table with structured and correlated data.

    Patients have more females than males and females are on average older,
    smaller and lighter than males. Also weight is correlated to height.
    """
    age_female = np.random.normal(mean_age_female, std, nb_female)
    age_male = np.random.normal(mean_age_male, std, nb_male)
    height_female = np.random.normal(mean_height_female, 2 * std, nb_female)
    height_male = np.random.normal(mean_height_male, 2 * std, nb_male)
    weight_female = (
        height_female - 100 + np.random.normal(mean_random_noise, 2 * std, nb_female)
    )
    weight_male = (
        height_male - 100 + np.random.normal(mean_random_noise, 2 * std, nb_male)
    )

    table_patient = pd.DataFrame(
        {
            "patient_id": list(range(nb_patient)),
            "gender": np.repeat(["Female", "Male"], [nb_female, nb_male]),
            "height": np.concatenate((height_female, height_male), axis=0),
            "age": np.concatenate((age_female, age_male), axis=0),
            "weight": np.concatenate((weight_female, weight_male), axis=0),
        }
    )
    table_patient.to_csv("fixtures/table_patient.csv", index=False) 


def table_doctor_bigger() -> None:
    """Generate a fake doctor table with structured and correlated data.

    Two kind of specialities, pediatrics being rarer than general practitioner.
    General practitioner are older on average than pediatrician.
    """
    age_general = np.random.normal(mean_age_general, std, nb_general)
    age_pediatrician = np.random.normal(mean_age_pediatrician, std, nb_pediatrician)
    table_doctor = pd.DataFrame(
        {
            "doctor_id": list(range(nb_doctor)),
            "job": np.repeat(
                ["pediatrician", "general practitioner"], [nb_pediatrician, nb_general]
            ),
            "age": np.concatenate((age_pediatrician, age_general), axis=0),
        }
    )
    table_doctor.to_csv("fixtures/table_doctor.csv", index=False)

def table_visit_bigger() -> None:
    """Generate a fake visit table with structured and correlated data.
    
    Females have visit only on "Monday", "Tuesday", "Thursday".
    Males have visits on "Wednesday", "Thursday", "Friday", Thursday is the only common value.
    Peditricans perform "routine_check", "pediatrics" exams.
    General practitioner perform "routine_check", "vaccine", routine_check is the only common exam.
    """
    table_visit = pd.DataFrame(
        {
            "visit_id": list(range(nb_visit)),
            "patient_id": np.random.choice(list(range(nb_patient)), nb_visit),
            "doctor_id": np.random.choice(list(range(nb_doctor)), nb_visit),
        }
    )

    table_visit["day_visit"] = np.where(
        table_visit["patient_id"] < nb_female,
        np.random.choice(["Monday", "Tuesday", "Thursday"], nb_visit),
        np.random.choice(["Wednesday", "Thursday", "Friday"], nb_visit),
    )

    exam = np.where(
        table_visit["doctor_id"] < nb_pediatrician,
        np.random.choice(["routine_check", "pediatrics"], nb_visit),
        np.random.choice(["routine_check", "vaccine"], nb_visit),
    )
    table_visit["exam"] = exam
    table_visit.to_csv("fixtures/table_visit.csv", index=False)

if __name__ == "__main__":
    table_patient_bigger()
    table_doctor_bigger()
    table_visit_bigger()
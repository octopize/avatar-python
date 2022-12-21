import numpy as np
import pandas as pd


class DatetimeProcessor:
    """Process datetime for avatarization."""

    def preprocess(self, df: pd.DataFrame) -> pd.DataFrame:
        """Turn datetime variables into int64 (seconds since epoch)."""
        df = df.copy()
        for col in df.columns:
            if not str(df[col].dtype).startswith("datetime"):
                continue
            epoch = np.datetime64(0, "Y")  # 0 years since epoch ==> epoch itself
            df[col] = (df[col] - epoch) / np.timedelta64(1, "s")
            df[col] = df[col].astype(float)  # Necessary, else its float64

        return df

    def postprocess(self, source: pd.DataFrame, dest: pd.DataFrame) -> pd.DataFrame:
        """Transform datetime columns from seconds since epoch back to datetime[ns] type."""
        datetime_variables = filter(
            lambda col: source[col].dtype == "datetime64[ns]", source.columns
        )
        epoch = np.datetime64(0, "Y")  # 0 years since epoch ==> epoch itself

        for name in datetime_variables:
            dest[name] = (dest[name] * np.timedelta64(1, "s")) + epoch
            dest[name] = pd.to_datetime(dest[name])
        return dest

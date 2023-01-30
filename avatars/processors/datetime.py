import numpy as np
import pandas as pd


class DatetimeProcessor:
    """Process datetime for avatarization.

    Examples
    --------
    >>> df = pd.DataFrame(
    ...    {
    ...        "date_1": ["2015-01-01 07:00:00", "2015-01-01 10:00:00"],
    ...        "date_2": ["2018-01-01 11:00:00", "2020-01-01 11:00:00"],
    ...    }
    ... )
    >>> df = df.apply(pd.to_datetime, format='%Y-%m-%d %H:%M:%S.%f')
    >>> processor = DatetimeProcessor()
    >>> processor.preprocess(df)
             date_1        date_2
    0  1.420096e+09  1.514804e+09
    1  1.420106e+09  1.577876e+09
    >>> avatar = pd.DataFrame(
    ...    {
    ...        "date_1": [1.420096e+09, 1.537804e+09],
    ...        "date_2": [1.420106e+09, 1.568676e+09],
    ...    }
    ... )
    >>> avatar
             date_1        date_2
    0  1.420096e+09  1.420106e+09
    1  1.537804e+09  1.568676e+09
    >>> processor.postprocess(df, avatar)
                   date_1              date_2
    0 2015-01-01 07:06:40 2015-01-01 09:53:20
    1 2018-09-24 15:46:40 2019-09-16 23:20:00
    """

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

from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


class GeolocationNormalizationProcessor:
    """Processor to normalize longitude values for different latitude.

    Use of this processor is recommended on data with latitude and longitude variables where the
    overall area covered has regions with no points (e.g. lake, forests etc ...)
    or non-squared bounds (e.g. country borders) and it is required to retain this lack of points
    in the anonymized data.

    Keyword Arguments
    -----------------
        latitude_variable:
            latitude variable name
        longitude_variable:
            longitude variable name
        n_reference_lat:
            number of discretized reference latitudes. A high number of references will yield a
            higher fidelity in the latitude dimension
        n_bins:
            number of discretized longitude bins at each reference latitude.  A high number of
            bins will yield a higher fidelity in the longitude dimension.

    Examples
    --------
    >>> import numpy as np
    >>> df = pd.DataFrame(
    ...    {
    ...        'lat': [49.1, 49.2, 49.3, 49.3],
    ...        'lon': [3.21, 3.19, 3.11, 3.18]
    ...    }
    ... )
    >>> df
        lat   lon
    0  49.1  3.21
    1  49.2  3.19
    2  49.3  3.11
    3  49.3  3.18
    >>> processor = GeolocationNormalizationProcessor(
    ...    latitude_variable='lat',
    ...    longitude_variable='lon',
    ...    n_reference_lat=3,
    ...    n_bins=5
    ... )
    >>> processed = processor.preprocess(df)
    >>> processed
        lat  lon
    0  49.1  0.5
    1  49.2  0.5
    2  49.3  0.0
    3  49.3  1.0

    The pre process expresses one of the coordinate dimension (i.e. lon) between 0 and 1.
    The range of values is different for different lat.

    >>> processor.postprocess(source=df, dest=processed)
        lat   lon
    0  49.1  3.21
    1  49.2  3.19
    2  49.3  3.11
    3  49.3  3.18

    The post process re-express the coordinates in the same original ranges.

    """

    def __init__(
        self, *, latitude_variable: str, longitude_variable: str, n_reference_lat: int, n_bins: int
    ):
        self.latitude_variable = latitude_variable
        self.longitude_variable = longitude_variable
        self.n_reference_lat = n_reference_lat
        self.n_bins = n_bins
        self.model: Dict[float, Dict[str, List[Tuple[float, float]]]] = {}

    def _compute_references(self, df: pd.DataFrame) -> pd.DataFrame:
        """Define reference latitudes and associate original points to each."""

        # Pick n lats along the lat range
        reference_lats = np.linspace(min(df["lat"]), max(df["lat"]), self.n_reference_lat)

        # align points to reference lats
        delta_reference = (max(df["lat"]) - min(df["lat"])) / (self.n_reference_lat - 1)
        # points_to_reference_tolerance: defines which points are mapped to each lat reference.
        # points_to_reference_tolerance = 0 -> only points with the exact lat are mapped.
        # points_to_reference_tolerance = 0.2 -> points that are within 20% of the distance
        #    between two reference lats are mapped to each reference
        # Using points_to_reference_tolerance >= 0.5 ensures all points are mapped to a
        #    reference lat. This ensure transformed values are within [0, 1] bounds.
        points_to_reference_tolerance = 0.5
        tol = points_to_reference_tolerance * delta_reference

        ref_dfs = []  # copy of original df where lat is changed to the associated ref lat
        for ref_lat in reference_lats:
            # get points matching the ref with the given tolerance tol
            tmp_df = df[(df["lat"] >= (ref_lat - tol)) & (df["lat"] <= (ref_lat + tol))][
                ["lat", "lon"]
            ].copy()
            tmp_df["lat"] = ref_lat  # set lat as ref_lat
            ref_dfs.append(tmp_df)
        ref_df = pd.concat(ref_dfs).reset_index(drop=True)

        return ref_df

    def _compute_ranges(self, ref_df: pd.DataFrame, nbins: int) -> None:
        """Calculate ranges of lon where there are points for each reference lat"""

        # "Cut" values of each reference lat in `nbins` bins. A bin represent a portion of the lon
        # covered at that lat
        for ref_lat in ref_df["lat"].unique():
            range_min = min(ref_df[ref_df["lat"] == ref_lat]["lon"])
            range_max = max(ref_df[ref_df["lat"] == ref_lat]["lon"])

            # count number of points in each of the bin (i.e. each of the bin)
            pmf1, bin_edges = np.histogram(
                ref_df[ref_df["lat"] == ref_lat]["lon"],
                bins=nbins,
                range=(range_min, range_max),
                density=True,
            )

            # only keep ranges where there are points
            non_zero_bin_starts = np.where(np.array(pmf1) > 0)[0]
            # and store the start and end lon of each range in a list of tuples
            ranges = [
                (bin_edges[bin_start], bin_edges[bin_start + 1])
                for bin_start in non_zero_bin_starts
            ]
            n_ranges = len(ranges)
            # also store the proportion of total lon covered by each range. Range proportions
            # should sum to 1 for each reference lat.
            ranges_proportions = [
                (i / n_ranges, i / n_ranges + 1 / n_ranges) for i in range(n_ranges)
            ]

            self.model[ref_lat] = {"ranges": ranges, "ranges_proportions": ranges_proportions}

    def _transform_one_point(self, row: pd.Series) -> pd.Series:
        # get closest reference lat for point to transform
        refs = list(self.model.keys())
        closest_ref = min(refs, key=lambda x: abs(x - row["lat"]))

        # compute proportion value based on closest reference lat using the lon of
        # the point to. The proportion value is based on the range in which the original lon falls
        # and is a linear estimation calculated from start and end of the range
        selected_i = -1
        for i, r in enumerate(self.model[closest_ref]["ranges"]):
            if r[0] <= row["lon"] < r[1]:
                selected_i = i
                break

        min_val = self.model[closest_ref]["ranges"][selected_i][0]
        max_val = self.model[closest_ref]["ranges"][selected_i][1]
        proportion_of_val = (row["lon"] - min_val) / (max_val - min_val)

        min_val = self.model[closest_ref]["ranges_proportions"][selected_i][0]
        max_val = self.model[closest_ref]["ranges_proportions"][selected_i][1]
        transformed_val = min_val + proportion_of_val * (max_val - min_val)

        x_transformed = row.copy()
        x_transformed["lon"] = transformed_val

        return x_transformed

    def _inv_transform_one_point(self, row: pd.Series) -> pd.Series:
        # inverse transform follows the same logic as the transform (see _transform_one_point)
        refs = list(self.model.keys())
        closest_ref = min(refs, key=lambda x: abs(x - row["lat"]))

        selected_i = -1
        for i, r in enumerate(self.model[closest_ref]["ranges_proportions"]):
            if r[0] <= row["lon"] < r[1]:
                selected_i = i
                break

        min_val = self.model[closest_ref]["ranges_proportions"][selected_i][0]
        max_val = self.model[closest_ref]["ranges_proportions"][selected_i][1]
        proportion_of_val = (row["lon"] - min_val) / (max_val - min_val)

        min_val = self.model[closest_ref]["ranges"][selected_i][0]
        max_val = self.model[closest_ref]["ranges"][selected_i][1]
        transformed_val = min_val + proportion_of_val * (max_val - min_val)

        x_inv_transformed = row.copy()
        x_inv_transformed["lon"] = transformed_val

        return x_inv_transformed

    def _fit(self, df: pd.DataFrame) -> None:
        self.ref_df = self._compute_references(df)
        self._compute_ranges(self.ref_df, self.n_bins)

    def preprocess(self, df: pd.DataFrame) -> pd.DataFrame:
        self._fit(df)

        transformed_tmp = []
        for i in range(len(df)):
            x = df.iloc[i]
            x_transformed = self._transform_one_point(x)
            transformed_tmp.append(x_transformed)
        df_transformed = pd.concat(transformed_tmp, axis=1).T

        return df_transformed

    def postprocess(self, source: pd.DataFrame, dest: pd.DataFrame) -> pd.DataFrame:
        inv_transformed_tmp = []
        for i in range(len(dest)):
            x = dest.iloc[i]
            x_transformed = self._inv_transform_one_point(x)
            inv_transformed_tmp.append(x_transformed)
        df_transformed = pd.concat(inv_transformed_tmp, axis=1).T
        return df_transformed

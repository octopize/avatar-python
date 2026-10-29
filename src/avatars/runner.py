import os
import random
import time
import warnings
import webbrowser
from dataclasses import asdict, dataclass
from logging import getLogger
from pathlib import Path
from typing import Any, Literal

import pandas as pd
import yaml
from avatar_yaml import (
    AvatarizationFastDPParameters,
    AvatarizationOpenDPParameters,
    AvatarizationParameters,
    Config,
    PrivacyMetricsParameters,
    TimeSeriesParameters,
)
from avatar_yaml.models.advice import AdviceType
from avatar_yaml.models.avatar_metadata import (
    DataRecipient,
    DataSubject,
    DataType,
    SensitivityLevel,
)
from avatar_yaml.models.parameters import (
    AlignmentMethod,
    AugmentationStrategy,
    AvatarizationProcessorParameters,
    ExcludeVariablesMethod,
    ImputeMethod,
    ProjectionType,
    ReportLanguage,
    ReportType,
    UnalignmentStrategy,
)
from avatar_yaml.models.schema import (
    ColumnType,
    LinkMethod,
    PseudonymizationStrategy,
)
from avatar_yaml.run_shape import REFERENCE_JOB, REFERENCE_SET, dump, reference_set
from IPython.display import HTML, display

from avatars import __version__
from avatars.constants import (
    DEFAULT_DELAY_BETWEEN_CONSECUTIVE_JOBS,
    DEFAULT_TYPE,
    JOB_EXECUTION_ORDER,
    MATCHERS,
    RESULTS_TO_STORE,
    VOLUME_NAME,
    PlotKind,
    Results,
    TypeResults,
)
from avatars.crash_handler import register_runner
from avatars.file_downloader import FileDownloader
from avatars.input_files import InputFile, missing_file_message
from avatars.job_launcher import JobLauncher
from avatars.job_polling import SYSTEM_CLOCK, Clock, wait_for_jobs
from avatars.links_advice import TablesLinksAdvice, parse_tables_links_advice
from avatars.metrics_summary import build_metrics_summary_df
from avatars.models import BulkDeleteRequest, BulkDeleteResponse, JobKind, JobResponse, JobStatus
from avatars.results_organizer import ResultsOrganizer
from avatars.schema_plan import (
    SchemaPlan,
    SharedEntity,
    config_creator,
    qualified_table,
)
from avatars.schema_plan import connection as _connection
from avatars.sdk_client import SdkClient

logger = getLogger(__name__)

_PER_TABLE_FIELDS = (
    "tables",
    "avatar_tables",
    "avatarization",
    "avatarization_open_dp",
    "avatarization_fast_dp",
    "time_series",
    "privacy_metrics",
    "signal_metrics",
)
"""The configuration fields keyed by table name, so a projection filters them all.

Named once because missing one silently gives a cluster job another cluster's
parameters -- and it would still run.
"""


@dataclass(frozen=True)
class _ClusterJob:
    """One avatarization job's worth of a database run."""

    name: str
    """Identifies the job: its parameters, its schema and its results."""

    tables: list[str]
    """The tables it works on, named as the schema declares them."""

    copy: str | None
    """Which database, for a run copying several. None for a single one."""

    within: str
    """The group's name inside that database's own plan."""


def _base36(number: int) -> str:
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    out = ""
    while number:
        number, rest = divmod(number, 36)
        out = digits[rest] + out
    return out or "0"


class Runner:
    def __init__(
        self,
        api_client: SdkClient,
        display_name: str,
        *,
        seed: int | None = None,
        max_distribution_plots: int | None = None,
        output_format: Literal["csv", "parquet"] | None = None,
        compute_figures: bool | None = None,
        pia_data_recipient: DataRecipient = DataRecipient.UNKNOWN,
        pia_data_type: DataType = DataType.UNKNOWN,
        pia_data_subject: DataSubject = DataSubject.UNKNOWN,
        pia_sensitivity_level: SensitivityLevel = SensitivityLevel.UNDEFINED,
        report_language: ReportLanguage = ReportLanguage.EN,
    ) -> None:
        """Initialize a Runner for avatarization workflows.

        Parameters
        ----------
        api_client
            The API client for communicating with the Avatar service.
        display_name
            Display name for this runner and its results set.
        seed
            Random seed for reproducible avatarization. If None, a random seed is generated.
        max_distribution_plots
            Maximum number of distribution plots to generate in reports.
            If None, uses server default.
        output_format
            Output format for results (e.g., "csv", "parquet").
            If None, the output format matches the input format.
        compute_figures
            Whether to compute figures/plots during avatarization.
            If None, uses server default (typically True). Set to False for faster runs
            when plots are not needed.
        pia_data_recipient
            Data recipient category for PIA reports.
        pia_data_type
            Data type category for PIA reports.
        pia_data_subject
            Data subject category for PIA reports.
        pia_sensitivity_level
            Sensitivity level category for PIA reports.
        report_language
            Language for generated reports (EN or FR).

        """
        self.client = api_client
        self.display_name = display_name
        self.set_name: str | None = None
        self.config = Config(
            set_name=self.display_name,
            seed=seed,
            compute_figures=compute_figures,
        )
        self.file_downloader = FileDownloader(api_client)
        self.results: ResultsOrganizer = ResultsOrganizer()
        self.jobs = JobLauncher(api_client, self.config)
        self.results_urls: dict[str, dict[str, list[str]]] = {}
        self._downloaded_results: set[tuple[str, Results]] = set()
        self._has_results_missing_warning_issued: bool = False
        self._clock: Clock = SYSTEM_CLOCK
        self._job_started_at: dict[str, float] = {}
        self.report_language = report_language
        self._database_plan: SchemaPlan | None = None
        self._launch: str | None = None
        """This launch of the run, the same for every group's set, in each set's display name."""
        self._copy_plans: dict[str, SchemaPlan] = {}
        self._cluster_jobs: dict[str, _ClusterJob] = {}
        """Group name -> what its run works on, when this run is several runs.

        Empty for every other run, including a database run whose plan covers a
        single group of related tables -- which is the ordinary case and is not
        a fan-out.
        """
        self._cluster_launchers: dict[str, JobLauncher] = {}
        self._reference_launcher: JobLauncher | None = None
        """Group name -> the launcher of its run, once `run` has created them."""

        annotations = {
            "client_type": "python",
            "client_version": __version__,
        }
        self.config.create_metadata(
            annotations,
            pia_datarecipient=pia_data_recipient,
            pia_datatype=pia_data_type,
            pia_datasubject=pia_data_subject,
            pia_sensitivitylevel=pia_sensitivity_level,
        )

        if max_distribution_plots is not None or output_format is not None:
            self.config.create_results(
                max_distribution_plots=max_distribution_plots,
                format=output_format,
            )

        # Register this Runner instance for crash reporting
        register_runner(self)

    def add_annotations(self, annotations: dict[str, str]) -> None:
        """Add metadata annotations to the config.

        Parameters
        ----------
        annotations
            A dictionary of annotations to add to the metadata.

        """
        if self.config.avatar_metadata is None:
            self.config.create_metadata(annotations)
        else:
            current_annotations = self.config.avatar_metadata.annotations or {}
            current_annotations.update(annotations)
            self.config.create_metadata(current_annotations)

    def add_table(
        self,
        table_name: str,
        data: str | pd.DataFrame | InputFile,
        *,
        primary_key: str | None = None,
        foreign_keys: list[str] | None = None,
        time_series_time: str | None = None,
        types: dict[str, ColumnType] | None = None,
        columns_to_drop: list[str] | None = None,
        individual_level: bool | None = None,
        avatar_data: str | pd.DataFrame | InputFile | None = None,
    ) -> None:
        """Add a table to the config and upload the data in the server.

        Parameters
        ----------
        table_name
            The name of the table.
        data
            The data to add to the table. Can be a path to a file, a pandas DataFrame, or a
            file already in your storage, as ``manager.list_input_files()`` lists
            them. A stored file is not uploaded again: its name is checked against the
            listing of your storage, and a name that is not there raises a
            ``ValueError`` before anything is uploaded. An upload is stored under the
            table name, ``<table_name>.parquet`` for a DataFrame or the extension of
            the path, and overwrites a file of that name already in your storage.
        primary_key
            The primary key of the table.
        foreign_keys
            Foreign keys of the table.
        time_series_time
            name of the time column in the table (time series case).
        types
            A dictionary of column types with the column name as the key and the type as the value.
        columns_to_drop
            A list of column names to drop from the table before avatarization. These columns will
            not be included in the avatarization process and will be removed from the output avatar
            table.
        individual_level
            A boolean as true if the table is at individual level or not. An individual level table
            is a table where each row corresponds to an individual (ex: patient, customer, etc.).
            Default behavior is True.
        avatar_data
            The avatar table if there is one. Can be a path to a file, a pandas DataFrame
            or a file already in your storage.

        """
        if types is None:
            types = {}
        file, avatar_file = self.upload_file(table_name, data, avatar_data)
        if isinstance(data, pd.DataFrame):
            types = self._get_types(data, types)

        self.config.create_table(
            table_name=table_name,
            original_volume=VOLUME_NAME,
            original_file=file,
            avatar_volume=VOLUME_NAME if avatar_data is not None else None,
            avatar_file=avatar_file,
            primary_key=primary_key,
            foreign_keys=foreign_keys,
            time_series_time=time_series_time,
            types=types,
            individual_level=individual_level,
            columns_to_drop=columns_to_drop,
        )

    def advise_parameters(self, table_name: str | None = None) -> None:
        """Fill the parameters set with the server recommendation.

        Parameters
        ----------
        table_name
            The name of the table. If None, all tables will be used.

        """
        self._setup_advice_config()
        if table_name:
            tables = [table_name]
        else:
            tables = list(self.config.tables.keys())
        self._create_advice_jobs(tables)
        self._apply_advice_parameters(tables)

    def advise_links(self, *, apply: bool = True) -> TablesLinksAdvice:
        """Advise the links between the tables, from the identifiers of each table.

        Declare the primary key and the foreign keys of each table with ``add_table`` first.
        The server advises one parent table for each foreign key that no link covers yet. It
        chooses the links from the names of the tables and of their identifiers only, not from
        their values; the advice job still reads and checks each table, as every advice does.

        Parameters
        ----------
        apply
            Add each advised link to the config with ``add_link``. Set it to False to review
            the advice first, then add the links you keep yourself.

        Returns
        -------
        TablesLinksAdvice
            ``links``: the advised links, each with a ``confidence`` (``high``, ``medium`` or
            ``low``). ``unlinked_foreign_keys``: the foreign keys that the server could not
            link, each with the tables that can be its parent. Link them with ``add_link``.

        """
        if len(self.config.tables) < 2:
            raise ValueError(
                f"Expected at least two tables to advise links, got {len(self.config.tables)}."
            )
        advisor_type = [AdviceType.TABLES_LINKS]
        self.config.create_advice(advisor_type=advisor_type)
        # The tables are not linked yet: only an advice job accepts such a schema.
        resource_response = self.client.resources.put_resources(
            display_name=self.display_name,
            yaml_string=self.config.get_advice_yaml(check_links_between_tables=False),
        )
        self.set_name = str(resource_response.set_name)
        job_name = self.config.get_parameters_advice_name(name="advice", advisor_type=advisor_type)
        self.jobs.launch_job(job_name, self.set_name)
        self.results_urls.pop(job_name, None)
        # Read apart from the stored advice, which holds the parameters advice of each table.
        urls = self.get_specific_result_urls(job_name=job_name, result=Results.ADVICE)
        advice = parse_tables_links_advice(
            self.file_downloader.download_files_batch(urls).values()
        )
        if apply:
            for link in advice.links:
                self.add_link(
                    parent_table_name=link.parent_table,
                    parent_field=link.parent_field,
                    child_table_name=link.child_table,
                    child_field=link.child_field,
                    method=link.method,
                )
        return advice

    def reference_tables_report(self, table_name: str | None = None) -> dict[str, dict[str, Any]]:
        """What the run's reference tables found, by reference table name.

        A subject declared on the wrong key column **succeeds**: every person
        gets an identity of their own in each table, and nothing fails. The
        numbers are how to tell -- how many subjects each source contributed,
        how many were seen in one source only, how many disagreed.

        Parameters
        ----------
        table_name
            The table the report is filed against. Omit it: the engine files
            one report per run, against one of its tables, and this finds it.

        Returns
        -------
        Reference table name -> ``subjects``, ``sources`` (``table``, ``rows``,
        ``subjects`` each), ``in_one_source_only``, ``conflicting_subjects``,
        ``conflicting_attributes`` and ``unresolved_rows``. Counts only -- no
        subject key or value. Empty for a run that declared no subjects.

        Examples
        --------
        >>> for name, outcome in runner.reference_tables_report().items():
        ...     print(name, outcome["subjects"], outcome["in_one_source_only"])

        """
        if table_name is not None:
            report = self.get_specific_result(
                table_name, JobKind.standard, Results.REFERENCE_TABLES
            )
            return report if isinstance(report, dict) else {}
        if not self.results.reference_tables:
            # Fetched once, for whichever table holds it, rather than once per
            # table: only one of them has a file to fetch.
            job_name = self.jobs.get_parameters_name(JobKind.standard)
            self._download_specific_result(job_name, Results.REFERENCE_TABLES)
        return next((r for r in self.results.reference_tables.values() if r), {})

    def _setup_advice_config(self) -> None:
        """Create advice config and upload resources to server."""
        self.config.create_advice(advisor_type=[AdviceType.PARAMETERS])
        yaml = self.config.get_yaml()
        resource_response = self.client.resources.put_resources(
            display_name=self.display_name,
            yaml_string=yaml,
        )
        # Update set_name with the actual UUID returned by the backend
        self.set_name = str(resource_response.set_name)

    def _create_advice_jobs(self, tables: list[str]) -> None:
        """Download advice results for the specified tables."""
        if all(self.results.advice.get(table_name) is not None for table_name in tables):
            return
        if self.set_name is None:
            raise ValueError("Set name is not set. Cannot launch advice job.")
        self._launch_job(JobKind.advice, self.set_name)
        job_name = self.jobs.get_parameters_name(JobKind.advice)
        self.results_urls.pop(job_name, None)
        self._download_specific_result(job_name, Results.ADVICE)

    def _apply_advice_parameters(self, tables: list[str]) -> None:
        """Apply the downloaded advice parameters to each table."""
        job_name = self.jobs.get_parameters_name(JobKind.advice)
        for table_name in tables:
            advise_parameters = self.results.get_results(table_name, Results.ADVICE, job_name)
            if not isinstance(advise_parameters, dict):
                raise ValueError("Expected advice parameters to be a dictionary")
            if not advise_parameters:
                # An advice run can carry column suggestions and no computed
                # advice; there is then nothing to set here.
                continue

            imputation_data: dict[str, Any] = {}
            if advise_parameters.get("imputation") is not None:
                imputation_result = advise_parameters.get("imputation")
                if isinstance(imputation_result, dict):
                    imputation_data = imputation_result

            imputation_method = None
            if imputation_data.get("method") is not None:
                imputation_method = ImputeMethod(imputation_data.get("method"))

            self.set_parameters(
                k=advise_parameters.get("k"),
                use_categorical_reduction=advise_parameters.get("use_categorical_reduction"),
                ncp=advise_parameters.get("ncp"),
                imputation_method=imputation_method,
                imputation_k=imputation_data.get("k"),
                imputation_training_fraction=imputation_data.get("training_fraction"),
                imputation_return_data_imputed=imputation_data.get("return_data_imputed", False),
                table_name=table_name,
            )

    def proposed_plan(self, database: str | None = None) -> SchemaPlan:
        """The plan schema discovery proposes, ready to review.

        Parameters
        ----------
        database
            Which copy, for a run covering several. Omit for a single database.

        Returns
        -------
        A :class:`SchemaPlan` whose proposals are all unreviewed -- read
        `proposals()`, then `confirm`/`reject` your way through it.

        Raises
        ------
        NotImplementedError
            While schema discovery is not yet a job you can launch. The engine
            discovers and classifies; nothing runs it as a step, so there is no
            proposal to fetch. Until then, build a plan yourself::

                plan = SchemaPlan().for_tables("customer", "order")
                plan.pseudonymize("customer").purge("audit_log")

        """
        self.discover_schema()
        job_name = f"schema_discovery{'' if database is None else '_' + database}"
        proposal = self.results.advice.get(job_name)
        if proposal is None:
            raise ValueError(
                "schema discovery produced no proposal for "
                f"{database or 'this database'}. Check the discovery job's status."
            )
        return SchemaPlan.from_proposal(proposal)

    def discover_schema(self) -> None:
        """Read the declared source and propose what to do with each table.

        The first phase of a database run: discovery proposes a treatment per
        table and an action per column, and stops. Nothing is copied and
        nothing is anonymized -- a person reads the proposal, corrects it, and
        only then is there a run. See :meth:`proposed_plan`.

        Runs once. Asking for the plan again returns the proposal already
        fetched rather than reading the source a second time.
        """
        if self.results.advice.get("schema_discovery") is not None:
            return

        # The configuration at this point declares the database and no tables,
        # which is the whole point: the run exists to find out what they are.
        resource_response = self.client.resources.put_resources(
            display_name=self.display_name,
            yaml_string=self.config.get_yaml(),
        )
        self.set_name = str(resource_response.set_name)

        self.jobs.launch_job(JobKind.schema_discovery, self.set_name)
        job_name = self.jobs.get_parameters_name(JobKind.schema_discovery)
        self._download_specific_result(job_name, Results.ADVICE)

    def add_database(
        self,
        source: str,
        target: str,
        tables: list[str] | None = None,
        plan: SchemaPlan | None = None,
        shared_entities: list[SharedEntity] | None = None,
    ) -> None:
        """Copy a database to another, anonymized.

        Parameters
        ----------
        source, target
            **Named connections** your deployment holds. Ask your administrator
            which are available. They must be different, and the same engine -- except that
            the target may be a SQLite file whatever the source is: the copy builds its
            tables there from the discovered schema.
        tables
            Which tables to copy. Omit for every table discovered.
        plan
            What happens to each table and column, from
            :meth:`proposed_plan` and reviewed with :class:`SchemaPlan`.
            Without one the run is a plain copy and nothing is anonymized.
        shared_entities
            What several tables share -- people, products, configuration data --
            declared with :func:`avatars.shared_entity`, so each gets one
            replacement everywhere.

        Notes
        -----
        The target must already have the schema and hold no rows -- nothing here
        creates or empties a database. Restore a schema-only dump into it first.

        """
        config_creator(self.config, "create_input_database")(
            source=_connection(source),
            target=_connection(target),
            tables=tables,
            reference_tables=[e.to_dict() for e in shared_entities] if shared_entities else None,
            plan=plan.to_dict() if plan is not None else None,
        )
        self._plan_the_run(plan)

    def _plan_the_run(self, plan: SchemaPlan | None) -> None:
        """Work out how many jobs this plan is, and declare the tables.

        A schema's tables have to form one connected graph -- the engine builds
        a metagraph over them and requires it -- so a plan covering several
        unrelated groups of tables is not one avatarization. It is one per
        group, which is what ADR-0008 specifies: "a database job is split into
        one multi-table job per PK/FK cluster", N jobs contributing to one
        target database.

        One group is the ordinary case and stays exactly as it was: one
        avatarization, nothing named after a cluster.
        """
        if plan is None:
            return

        self._database_plan = plan.ensure_individual_level()
        clusters = plan.clustered()
        if len(clusters) > 1:
            self._cluster_jobs = {
                name: _ClusterJob(name=name, tables=tables, copy=None, within=name)
                for name, tables in clusters.items()
            }
            self._pin_a_seed()

        # Declared on this configuration whether or not the run fans out. It is
        # what every table-keyed call on `Runner` reads -- `set_parameters`
        # refuses a table it cannot find -- so declaring them only per cluster
        # would leave the caller unable to set `k` for any of them. Each cluster
        # configuration is a *projection* of this one; what is never emitted is
        # this schema, which would hold every cluster's tables at once and be
        # the disconnected graph the fan-out exists to avoid.
        self._declare_planned_tables(plan)

    def _plan_the_copies(self, plans: dict[str, SchemaPlan]) -> None:
        """Declare the tables of every copy, and work out how many jobs it is.

        Nothing declared them, so every cross-database run was refused on
        upload with "Schema 'schema' does not have any individual_level table
        defined" -- the same wall the single-database path hit.

        **Names are qualified by copy.** Two databases both holding
        ``customer`` are two tables, and the protocol stages them as
        ``crm.customer`` and ``billing.customer``; a configuration naming
        either of them ``customer`` describes neither.

        **Every copy is at least one job.** No foreign key crosses a database,
        so the tables of two copies are never one connected graph -- here the
        fan-out is not a choice but the only shape that runs. The groups within
        a copy are then its own, so the unit is (copy, group).

        Shared entities still span everything: they are declared once, on the
        run, and every job collects them from every database before resolving.
        It is also why one seed across the jobs matters more here than for a
        single database.
        """
        if not plans:
            return

        self._copy_plans = dict(plans)
        for copy, plan in plans.items():
            plan.ensure_individual_level()
            for cluster, tables in plan.clustered().items():
                name = f"{copy}_{cluster}"
                self._cluster_jobs[name] = _ClusterJob(
                    name=name,
                    tables=[qualified_table(copy, table) for table in tables],
                    copy=copy,
                    within=cluster,
                )
            self._declare_planned_tables(plan.qualified_by(copy))
        self._pin_a_seed()

    def _pin_a_seed(self) -> None:
        """Give the run one seed, so its several jobs agree about people.

        A shared entity's replacement follows the order entities are collected
        rather than the value, and each job resolves the reference tables for itself.
        Same seed, same replacements; different seeds and Alice is a different
        person in every group, with nothing downstream able to tell.

        `ParametersSpec.seed` has a `default_factory` on the engine side, so
        leaving it unset does not mean "no seed" -- it means a fresh one per
        parameters document, which is exactly the failure. Generating one here
        and saying so beats refusing a run over a field nobody asked about.
        """
        if self.config.seed is not None:
            return
        self.config.seed = random.SystemRandom().randrange(2**32)
        logger.info(
            "this run is %d jobs, one per group of related tables, and they have to agree "
            "about every person -- so it is seeded with %d. Pass seed= to choose your own.",
            len(self._cluster_jobs),
            self.config.seed,
        )

    def _cluster_configs(self) -> dict[str, Config]:
        """One complete configuration per job, each an ordinary multi-table run.

        This is the shape of the fan-out: **one document set per group**, not
        one set holding several schemas. Each configuration is exactly what a
        multi-table run has always emitted -- a schema called ``schema``,
        parameters called ``standard`` -- so nothing about the document shape
        that today's multi-table jobs rely on changes, and every job kind
        (metrics, report) keeps working per group without being renamed.

        Each is a **projection** of the run's configuration: everything about
        the run, narrowed to one group's tables. A projection rather than a
        fresh build for two reasons -- it cannot forget a field somebody set,
        and the links, column types and pseudonymization it needs are already
        on those tables. Re-declaring them here appended the links a second
        time, which is a different schema, not a tidier one.

        What each one gets that the run's own configuration does not:

        * only its own tables. A group is closed under foreign keys, so no link
          crosses out of it and the links need no surgery;
        * a plan scoped the same way, so the job reads, avatarizes and writes
          its own tables and leaves the other groups' alone.
        """
        built: dict[str, Config] = {}
        for job in self._cluster_jobs.values():
            config = self.config.model_copy(deep=True)
            keep = set(job.tables)
            for field in _PER_TABLE_FIELDS:
                current = getattr(config, field)
                setattr(config, field, {k: v for k, v in current.items() if k in keep})
            # Emitted afresh for this group's tables. The run's own schema
            # holds every group's at once, which is the disconnected graph the
            # fan-out exists to avoid.
            config.original_schema = None
            config.avatar_schema = None
            self._scope_the_input(config, job)
            built[job.name] = config
        return built

    def _scope_the_input(self, config: Config, job: _ClusterJob) -> None:
        """Give the job the whole run's plan, every table labelled with its group (ADR-0012).

        The set describes its whole database -- every group's tables, with their real
        treatments -- and its Extraction says which group it runs. The engine leaves the other
        groups' tables alone, as the former scoping did by marking them `ignore`. A set reads
        one database: a copy of several is written as the set of the copy the group is in.

        A group is labelled with the job's name, which is unique across the run: two
        databases may both have a `group-customer`. A purged table belongs to no group --
        nothing of it is modelled -- and is given to the first group of its database, so it
        is emptied once rather than by every group or by none.

        The shared entities are left exactly as the run declared them. They are what gives an
        entity one replacement across the whole estate, so every set collects it from every
        database it is found in, with the run's seed as the entity's own.
        """
        if config.input is None:
            return
        if config.input.database is not None and self._database_plan is not None:
            config.input.database.plan = self._labelled(self._database_plan, None)
        if config.input.databases is not None:
            for copy in config.input.databases.copies:
                plan = self._copy_plans.get(copy.name)
                if plan is not None:
                    copy.plan = self._labelled(plan, copy.name)
        config.create_run(group=job.name, seed=config.seed)

    def _labelled(self, plan: SchemaPlan, copy: str | None) -> dict[str, Any]:
        """*plan* as a dict, each participating table labelled with the job that runs it."""
        labelled = plan.to_dict()
        jobs = [j for j in self._cluster_jobs.values() if j.copy == copy]
        group_of = {
            table: job.name for job in jobs for table in plan.clustered().get(job.within, [])
        }
        first = min((job.name for job in jobs), default=None)
        for table in labelled.get("tables", []):
            if table["name"] in group_of:
                table["cluster"] = group_of[table["name"]]
            elif table.get("treatment") == "purge" and first is not None:
                table["cluster"] = first
            else:
                table.pop("cluster", None)
        return labelled

    def _declare_planned_tables(
        self, plan: SchemaPlan | None, config: Config | None = None
    ) -> None:
        """Give the run a table per table the plan keeps.

        Nothing else declares them. The engine streams each one onto storage
        when the job runs, but the configuration is validated when it is
        *uploaded*, long before that -- so a run with no declared tables was
        refused outright with "Schema 'schema' does not have any
        individual_level table defined", which is where every database run
        stopped.

        `individual_level` comes from the plan, where discovery proposed it
        from the shape of the links and a reviewer may have corrected it. Rows
        of a customer table are people; rows of an invoice table are not, and
        calling both individual-level would change what the metrics mean.

        Without a plan there is nothing to declare -- that is the discovery
        phase, and the tables are not known yet.

        *config* is the configuration to declare them on, which for a fanned-out
        run is one cluster's rather than the run's own.
        """
        if plan is None:
            return
        config = config if config is not None else self.config

        participating = set(plan.participating())
        for name in plan.participating():
            if name in config.tables:
                continue
            types = {column: ColumnType(kind) for column, kind in plan.column_types(name).items()}
            # Only the keys pointing at a table this run has. One aimed at a
            # table the plan excluded would be declared and unlinkable.
            foreign_keys = [
                link["column"]
                for link in plan.links(name)
                if link["references_table"] in participating
            ]
            # A link table keyed on its foreign keys -- `PRIMARY KEY (playlist_id,
            # track_id)` -- has no single-column key, and the first column of the
            # composite one is a foreign key, which a column cannot also be. It is
            # declared the way a link table without a key is: two foreign keys,
            # both linkable.
            primary_key = plan.primary_key(name)
            if primary_key in foreign_keys:
                primary_key = None
            config.create_table(
                name,
                individual_level=plan.is_individual_level(name),
                provided_by_input=True,
                types=types or None,
                primary_key=primary_key,
                # A column the plan drops is absent from the copy, so it is
                # also a column nothing should model. Declared here because
                # every column is streamed onto storage whatever the plan says
                # -- the sink writes the table's whole column list -- so
                # without this the values are read, avatarized and written.
                # So is one that arrives empty: the avatarization leaves it out of
                # the avatars, and a job reading them afterwards -- the Génération,
                # the metrics -- would expect it there.
                columns_to_drop=plan.dropped_columns(name) + plan.emptied_columns(name) or None,
                foreign_keys=foreign_keys or None,
            )

        self._declare_planned_pseudonymization(plan, config)
        self._declare_planned_links(plan, config)

    def _declare_planned_pseudonymization(self, plan: SchemaPlan, config: Config) -> None:
        """Carry each column's replacement strategy onto the schema.

        The per-column half of the plan, and without it the plan's central
        decision is silently dropped: the avatarization *resamples* a
        categorical column, drawing its values from the real distribution, so
        every real email stays in the copy against a different person. A live
        run put six of eight source addresses in the target, two of them twice,
        while the plan said "pseudonymize customer.email".

        Only where the reviewer asked for it. A column the plan keeps is
        avatarized with the rest of the table, which for a quantity is exactly
        right -- an amount should be synthetic, not a real amount belonging to
        somebody else.
        """
        for name in config.tables:
            strategies = plan.pseudonymized_columns(name)
            if strategies:
                config.apply_pseudonymized_columns(name, strategies)

    def _with_frozen_columns(self, table: str, excluded: list[str] | None) -> list[str] | None:
        """Add the columns a reviewed plan froze to the ones the caller excluded.

        A frozen column keeps its original values, and "excluded from the
        avatarization" is how that is said to the engine -- so without this the
        decision reaches nothing and the column is avatarized like any other.
        That is the same failure as a dropped pseudonymization strategy: the
        run reports success and the plan's decision is simply absent from the
        result.

        Added to what the caller passed rather than replacing it: somebody
        excluding a column for their own reasons should not lose it, and
        somebody reviewing a plan should not have to restate the exclusions.
        """
        plans = [self._database_plan, *self._copy_plans.values()]
        frozen: list[str] = []
        for plan in plans:
            if plan is None:
                continue
            frozen.extend(plan.frozen_columns(table))
            _require_something_to_model(plan, table, frozen)
        if not frozen:
            return excluded
        return list(dict.fromkeys([*(excluded or []), *frozen]))

    def _declare_planned_links(self, plan: SchemaPlan, config: Config) -> None:
        """Declare the foreign keys between the tables this run works on.

        Not decoration. The engine builds a metagraph over a schema's tables
        and requires it connected, so a cluster whose links are undeclared is
        indistinguishable from unrelated tables -- and a copy written without
        them breaks referential integrity in the target, which is the one thing
        a working test database has to keep.

        Links are declared after every table exists, because a link names two
        of them, and only between tables this run actually has: a key pointing
        at a table the plan excluded has nothing to point at here.
        """
        declared = set(config.tables)
        for child in declared:
            for link in plan.links(child):
                parent = link["references_table"]
                # A table referencing itself -- `employees.reports_to` -- is a
                # cycle in the metagraph, which the API refuses. The column
                # stays a key; only the link is not declared, as the web app does.
                if parent not in declared or parent == child:
                    continue
                config.create_link(
                    parent_table_name=parent,
                    child_table_name=child,
                    parent_field=link["references_column"],
                    child_field=link["column"],
                    method=_link_method(plan, parent),
                )

    def add_databases(
        self,
        copies: dict[str, tuple[str, str]] | None = None,
        plans: dict[str, SchemaPlan] | None = None,
        shared_entities: list[SharedEntity] | None = None,
    ) -> None:
        """Copy several databases together, sharing one identity per person.

        Worth using for exactly one reason: the same people appear in more than
        one database, and a test estate where they are different people in each
        is useless. A single database wants :meth:`add_database`.

        Parameters
        ----------
        copies
            Name -> (source connection, target connection). The name is how a
            subject refers to that database::

                copies={"crm": ("crm_prod", "crm_test"),
                        "billing": ("billing_prod", "billing_test")}
        plans
            Name -> the reviewed plan for that database.
        shared_entities
            Declared with :func:`avatars.shared_entity` using its ``across`` form,
            so each is resolved once across every database.

        Notes
        -----
        Every target is validated before any is written: a half-written estate
        cannot be completed by retrying the missing half, because the identities
        of the half that landed cannot be reproduced from a subset.

        """
        declared = copies or {}
        given_plans = plans or {}
        config_creator(self.config, "create_input_databases")(
            copies=[
                {
                    "name": name,
                    "source": _connection(source),
                    "target": _connection(target),
                    **({"plan": given_plans[name].to_dict()} if name in given_plans else {}),
                }
                for name, (source, target) in declared.items()
            ],
            reference_tables=[e.to_dict() for e in shared_entities] if shared_entities else None,
        )
        self._plan_the_copies(given_plans)

    def upload_file(
        self,
        table_name: str,
        data: str | pd.DataFrame | InputFile,
        avatar_data: str | pd.DataFrame | InputFile | None = None,
    ) -> tuple[str, str | None]:
        """Upload the data of a table to the server, and return the stored file names.

        Parameters
        ----------
        table_name
            The name of the table, which names the uploaded file. A file of that name
            already in your storage is overwritten.
        data
            The data to upload. Can be a path to a file or a pandas DataFrame. A file
            already in your storage (an ``InputFile``) is not uploaded: its own name is
            returned once the listing of your storage confirms it is there.
        avatar_data
            The avatar table if there is one, of the same kinds.

        Raises
        ------
        ValueError
            A stored file named by ``data`` or ``avatar_data`` is not in your storage.

        """
        self._check_stored(data, avatar_data)
        file = self._stored_file(data, name=table_name)
        avatar_file = None
        if avatar_data is not None:
            avatar_file = self._stored_file(avatar_data, name=table_name + "_avatars")
        return file, avatar_file

    def _check_stored(self, *data: str | pd.DataFrame | InputFile | None) -> None:
        """Refuse a stored file that is not in your storage, before anything is uploaded."""
        named = [table_data for table_data in data if isinstance(table_data, InputFile)]
        if not named:
            return
        stored = self.client.list_input_files()
        for file in named:
            if file.name not in stored:
                raise ValueError(missing_file_message(file.name, stored))

    def _stored_file(self, data: str | pd.DataFrame | InputFile, *, name: str) -> str:
        """The name of the stored file that holds ``data``, uploaded under ``name`` if needed."""
        if isinstance(data, InputFile):
            return data.name
        extension = ".parquet" if isinstance(data, pd.DataFrame) else Path(data).suffix
        file = name + extension
        self.client.upload_file(data=data, key=file)
        return file

    def _get_types(
        self, data: pd.DataFrame, types: dict[str, ColumnType] | None = None
    ) -> dict[str, ColumnType]:
        if types is None:
            types = {}
        dtypes = {}
        for column_name, _type in data.dtypes.items():
            column_name_str = str(column_name)
            if column_name_str in types:
                dtypes[column_name_str] = types[column_name_str]
            else:
                dtypes[column_name_str] = self._get_type_from_pandas(str(_type))
        return dtypes

    def _get_type_from_pandas(self, value: str) -> ColumnType:
        """Return our data type from pandas type."""
        for matcher, our_type in MATCHERS.items():
            if matcher.search(value):
                return our_type
        return DEFAULT_TYPE

    def add_link(
        self,
        parent_table_name: str,
        parent_field: str,
        child_table_name: str,
        child_field: str,
        method: LinkMethod = LinkMethod.LINEAR_SUM_ASSIGNMENT,
    ) -> None:
        """Add a table link to the config.

        Parameters
        ----------
        parent_table_name
            The name of the parent table.
        child_table_name
            The name of the child table.
        parent_field
            The parent link key field (primary key) in the parent table.
        child_field
            The child link key field (foreign key)in the child table.
        method
            The method to use for linking the tables. Defaults to "linear_sum_assignment".

        """
        self.config.create_link(
            parent_table_name, child_table_name, parent_field, child_field, method
        )

    def set_parameters(
        self,
        table_name: str,
        *,
        k: int | None = None,
        ncp: int | None = None,
        use_categorical_reduction: bool | None = None,
        column_weights: dict[str, float] | None = None,
        exclude_variable_names: list[str] | None = None,
        exclude_replacement_strategy: ExcludeVariablesMethod | None = None,  # DEPRECATED
        exclude_variable_method: ExcludeVariablesMethod | None = None,
        imputation_method: ImputeMethod | None = None,
        imputation_k: int | None = None,
        imputation_training_fraction: float | None = None,
        imputation_return_data_imputed: bool | None = None,
        open_dp_epsilon: float | None = None,
        fast_dp_epsilon: float | None = None,
        time_series_nf: int | None = None,
        time_series_projection_type: ProjectionType | None = None,
        time_series_nb_points: int | None = None,
        time_series_method: AlignmentMethod | None = None,
        time_series_unalignment: UnalignmentStrategy | None = None,
        known_variables: list[str] | None = None,
        target: str | None = None,
        quantile_threshold: int | None = None,
        data_augmentation_strategy: float | AugmentationStrategy | dict[str, float] | None = None,
        data_augmentation_target_column: str | None = None,
        data_augmentation_should_anonymize_original_table: bool | None = None,
        processors: list[AvatarizationProcessorParameters] | None = None,
        pseudonymized_columns: dict[str, PseudonymizationStrategy] | None = None,
        use_excluded_variables_in_metrics: bool = False,
    ) -> None:
        """Set the parameters for a given table.

        This will overwrite any existing parameters for the table, including parameters set using
        `advise_parameter()`.

        Parameters
        ----------
        table_name
            The name of the table.
        k
            Number of nearest neighbors to consider for KNN-based methods.
        ncp
            Number of dimensions to consider for the KNN algorithm.
        use_categorical_reduction
            Whether to transform categorical variables into a
            latent numerical space before projection.
        column_weights
            Dictionary mapping column names to their respective weights,
            indicating the importance of each variable during the projection process.
        exclude_variable_names
            List of variable names to exclude from the projection.
        exclude_replacement_strategy:
            DEPRECATED: use exclude_variable_method instead.
        exclude_variable_method:
            Strategy for replacing excluded variables. Options: ROW_ORDER, COORDINATE_SIMILARITY.
        imputation_method
            Method for imputing missing values. Options: ``ImputeMethod.KNN``,
            ``ImputeMethod.MODE``, ``ImputeMethod.MEDIAN``, ``ImputeMethod.MEAN``,
            ``ImputeMethod.FAST_KNN``.
        imputation_k
            Number of neighbors to use for imputation if the method is KNN or FAST_KNN.
        imputation_training_fraction
            Fraction of the dataset to use for training the imputation model
            when using KNN or FAST_KNN.
        imputation_return_data_imputed:
            Whether to return the data with imputed values.
        open_dp_epsilon
            Epsilon value for differential privacy using OpenDP implementation.
        fast_dp_epsilon
            Epsilon value for fastDP avatarization.
        time_series_nf
            In time series context, number of degrees of freedom to
            retain in time series projections.
        time_series_projection_type
            In time series context, type of projection for time series. Options:
            ``ProjectionType.FCPA`` (default) or ``ProjectionType.FLATTEN``.
        time_series_method
            In time series context, method for aligning series. Options:
            ``AlignmentMethod.SPECIFIED``, ``AlignmentMethod.MAX``,
            ``AlignmentMethod.MIN``, ``AlignmentMethod.MEAN``.
        time_series_nb_points
            In time series context, number of points to generate for time series.
        time_series_unalignment
            In time series context, how the avatar series come back from the aligned number
            of points. Options: ``UnalignmentStrategy.UNIFORM`` (default) gives each avatar
            series its own number of points, ``UnalignmentStrategy.SKIP`` keeps the aligned
            number of points for every avatar series.
        known_variables
            List of known variables to be used for privacy metrics.
            These are variables that could be easily known by an attacker.
        target
            Target variable to predict, used for signal metrics.
        quantile_threshold
            Quantile threshold for privacy metrics calculations.
        data_augmentation_strategy
            Strategy for data augmentation. Can be a float representing the
            augmentation ratio, an AugmentationStrategy enum, or a dictionary
            mapping modality to their respective augmentation ratios.
        data_augmentation_target_column
            Target column for data augmentation when using a dictionary strategy or
            AugmentationStrategy.
        data_augmentation_should_anonymize_original_table
            SENSITIVE: Whether to anonymize the original table during data augmentation.
            Default is True.
        processors
            List of processor parameter objects (subclasses of AvatarizationProcessorParameters).
            Supports InterRecordRangeDifferenceParameters and RelativeDifferenceParameters.
            The order of the list determines the order in which processors are applied
            during preprocessing (and reversed during postprocessing).

            The transformations are transparent to the user - input and output have the same
            column structure at the end.
        pseudonymized_columns
            A mapping of column name to a pseudonymization strategy object describing how to
            replace PII values in each column.  Available strategy classes (importable from
            ``avatar_yaml``):

            * ``FakeDataStrategy(pii_type=PiiType.EMAIL)`` — replace with realistic fake data
              of the specified :class:`PiiType` (EMAIL, FIRST_NAME, LAST_NAME, FULL_NAME,
              PHONE, SSN, ADDRESS, FREE_TEXT).  Pass ``consistent=False`` to generate a fresh
              value per row instead of mapping the same source value to the same fake value.
              Leave ``high_variability=False`` (default) to sample from a pre-generated pool
              for faster processing, or set ``high_variability=True`` to generate a unique
              value per row (slower but collision-free).
            * ``HashSha256Strategy()`` — replace with the SHA-256 hex digest (deterministic,
              irreversible).
            * ``Uuid4Strategy()`` — replace each unique value with a UUID v4.  Pass
              ``consistent=False`` to generate a new UUID per row.
            * ``ConstantStrategy(value="REDACTED")`` — replace every value with a fixed string.
            * ``IntegerStrategy()`` — map each unique value to a unique pseudonymous integer.
              Pass ``consistent=False`` for an independent integer per row.
            * ``SpecificIdStrategy(pattern="EMP-####")`` — generate structured IDs from a
              pattern.  Placeholders: ``#`` (digit), ``?`` (letter), ``^`` (alphanumeric),
              ``{{col}}`` (value of another column).  Control letter case with
              ``letter_case=SpecificIdLetterCase.UPPER/LOWER/BOTH``.

            Only columns that should be pseudonymized need to be listed.  Foreign key columns
            in child tables automatically inherit the pseudonymization mapping of the referenced
            parent primary key — no explicit configuration is needed on child FK columns.
        use_excluded_variables_in_metrics
            When True, excluded variables are NOT passed to metrics parameters,
            allowing privacy and signal metrics to include them in calculations.
            When False (default), excluded variables are also excluded from metrics calculations.

        """
        imputation = imputation_method.value if imputation_method else None
        exclude_variable_names = self._with_frozen_columns(table_name, exclude_variable_names)
        if exclude_variable_method:
            replacement_strategy = exclude_variable_method.value
        elif exclude_replacement_strategy:
            warnings.warn(
                "The 'exclude_replacement_strategy' parameter is deprecated and will be removed "
                "in a future release. Please use 'exclude_variable_method' instead.",
                stacklevel=2,
            )
            replacement_strategy = exclude_replacement_strategy.value
        else:
            replacement_strategy = None
        if k and open_dp_epsilon:
            raise ValueError(
                "Expected either k or open_dp_epsilon to be set, not both. "
                "If you want to use OpenDP avatarization, set open_dp_epsilon and remove k."
            )
        if k and fast_dp_epsilon:
            raise ValueError(
                "Expected either k or fast_dp_epsilon to be set, not both. "
                "If you want to use fastDP avatarization, set fast_dp_epsilon and remove k."
            )
        if open_dp_epsilon and fast_dp_epsilon:
            raise ValueError(
                "Expected either open_dp_epsilon or fast_dp_epsilon to be set, not both. "
                "Choose either OpenDP (open_dp_epsilon) or FastDP (fast_dp_epsilon)."
            )
        if k == 2:
            warnings.warn(
                "You have set k = 2, which is the minimum allowed value. With such a low k, "
                "each synthesized record closely mirrors only 2 original records, "
                "significantly reducing privacy protection.",
                stacklevel=2,
            )

        # reset the parameters if they were already set
        if self.config.avatarization and self.config.avatarization.get(table_name):
            del self.config.avatarization[table_name]
        avatarization_open_dp = getattr(self.config, "avatarization_open_dp", None)
        if avatarization_open_dp and avatarization_open_dp.get(table_name):
            del avatarization_open_dp[table_name]
        avatarization_fast_dp = getattr(self.config, "avatarization_fast_dp", None)
        if avatarization_fast_dp and avatarization_fast_dp.get(table_name):
            del avatarization_fast_dp[table_name]
        if self.config.privacy_metrics and self.config.privacy_metrics.get(table_name):
            del self.config.privacy_metrics[table_name]
        if self.config.signal_metrics and self.config.signal_metrics.get(table_name):
            del self.config.signal_metrics[table_name]
        if self.config.time_series and self.config.time_series.get(table_name):
            del self.config.time_series[table_name]
        if k:
            # Avatarizaztion with avatar method
            self.config.create_avatarization_parameters(
                table_name=table_name,
                k=k,
                ncp=ncp,
                use_categorical_reduction=use_categorical_reduction,
                imputation_method=imputation,
                imputation_k=imputation_k,
                imputation_training_fraction=imputation_training_fraction,
                imputation_return_data_imputed=imputation_return_data_imputed,
                column_weights=column_weights,
                exclude_variable_names=exclude_variable_names,
                exclude_variable_method=replacement_strategy,
                data_augmentation_strategy=data_augmentation_strategy,
                data_augmentation_target_column=data_augmentation_target_column,
                data_augmentation_should_anonymize_original_table=data_augmentation_should_anonymize_original_table,
                avatarization_processors_parameters=processors,
                pseudonymized_columns=pseudonymized_columns,
            )

        elif open_dp_epsilon:
            # OpenDP avatarization (MST method)
            self.config.create_avatarization_open_dp_parameters(
                table_name=table_name,
                epsilon=open_dp_epsilon,
                ncp=ncp,
                use_categorical_reduction=use_categorical_reduction,
                imputation_method=imputation,
                imputation_k=imputation_k,
                imputation_training_fraction=imputation_training_fraction,
                imputation_return_data_imputed=imputation_return_data_imputed,
                column_weights=column_weights,
                exclude_variable_names=exclude_variable_names,
                exclude_variable_method=replacement_strategy,
                data_augmentation_strategy=data_augmentation_strategy,
                data_augmentation_target_column=data_augmentation_target_column,
                data_augmentation_should_anonymize_original_table=data_augmentation_should_anonymize_original_table,
                avatarization_processors_parameters=processors,
                pseudonymized_columns=pseudonymized_columns,
            )

        elif fast_dp_epsilon:
            # FastDP avatarization (DP mechanisms in latent space)
            self.config.create_avatarization_fast_dp_parameters(
                table_name=table_name,
                epsilon=fast_dp_epsilon,
                ncp=ncp,
                use_categorical_reduction=use_categorical_reduction,
                imputation_method=imputation,
                imputation_k=imputation_k,
                imputation_training_fraction=imputation_training_fraction,
                imputation_return_data_imputed=imputation_return_data_imputed,
                column_weights=column_weights,
                exclude_variable_names=exclude_variable_names,
                exclude_variable_method=replacement_strategy,
                data_augmentation_strategy=data_augmentation_strategy,
                data_augmentation_target_column=data_augmentation_target_column,
                data_augmentation_should_anonymize_original_table=data_augmentation_should_anonymize_original_table,
                avatarization_processors_parameters=processors,
                pseudonymized_columns=pseudonymized_columns,
            )

        if (
            time_series_nf
            or time_series_projection_type
            or time_series_nb_points
            or time_series_method
            or time_series_unalignment
        ):
            method = time_series_method.value if time_series_method else None
            unalignment = time_series_unalignment.value if time_series_unalignment else None
            if unalignment and method is None:
                # avatar-yaml 0.1.46 writes a missing method as `method: null`, which the engine
                # refuses. `mean` is the method that the engine takes by default.
                method = AlignmentMethod.MEAN.value
            projection_type = (
                time_series_projection_type.value if time_series_projection_type else None
            )
            self.config.create_time_series_parameters(
                table_name=table_name,
                nf=time_series_nf,
                projection_type=projection_type,
                nb_points=time_series_nb_points,
                method=method,
                exclude_variable_names=exclude_variable_names,
                exclude_variable_method=replacement_strategy,
                unalignment=unalignment,
            )

        metrics_exclude_variable_names = (
            None if use_excluded_variables_in_metrics else exclude_variable_names
        )
        metrics_replacement_strategy = (
            None if use_excluded_variables_in_metrics else replacement_strategy
        )

        self.config.create_privacy_metrics_parameters(
            table_name=table_name,
            ncp=ncp,
            use_categorical_reduction=use_categorical_reduction,
            imputation_method=imputation,
            imputation_k=imputation_k,
            imputation_training_fraction=imputation_training_fraction,
            imputation_return_data_imputed=imputation_return_data_imputed,
            exclude_variable_names=metrics_exclude_variable_names,
            exclude_variable_method=metrics_replacement_strategy,
            known_variables=known_variables,
            target=target,
            quantile_threshold=quantile_threshold,
            column_weights=column_weights,
        )

        self.config.create_signal_metrics_parameters(
            table_name=table_name,
            ncp=ncp,
            use_categorical_reduction=use_categorical_reduction,
            imputation_method=imputation,
            imputation_k=imputation_k,
            imputation_training_fraction=imputation_training_fraction,
            imputation_return_data_imputed=imputation_return_data_imputed,
            exclude_variable_names=metrics_exclude_variable_names,
            exclude_variable_method=metrics_replacement_strategy,
            column_weights=column_weights,
        )

    def update_parameters(self, table_name: str, **kwargs: Any) -> None:
        """Update specific parameters for the table while preserving other existing parameters.
        Only updates the parameters that are provided, keeping existing values for others.

        Parameters
        ----------
        table_name
            The name of the table.
        **kwargs
            The parameters to update. Only parameters that are provided will be updated.
            See set_parameters for the full list of available parameters.

        """
        per_table_params = (
            "avatarization",
            "avatarization_open_dp",
            "avatarization_fast_dp",
            "time_series",
            "privacy_metrics",
            "signal_metrics",
        )
        if not any(
            (getattr(self.config, field, None) or {}).get(table_name) is not None
            for field in per_table_params
        ):
            raise ValueError(
                f"No existing parameters found for table '{table_name}'. "
                "Use set_parameters to create new parameters."
            )
        # Get current parameters for this table
        current_params = self._extract_current_parameters(table_name)

        # Update only the parameters that were provided
        for param_name, param_value in kwargs.items():
            current_params[param_name] = param_value
        # Apply all parameters back using set_parameters
        self.set_parameters(table_name=table_name, **current_params)

    def _extract_current_parameters(self, table_name: str) -> dict[str, Any]:
        """Extract the current parameters for a given table.

        Parameters
        ----------
        table_name
            The name of the table.

        Returns
        -------
        dict
            A dictionary containing the current parameters for
            the table as it is used in set_parameters.

        """
        current_params: dict[str, Any] = {}

        # Extract avatarization parameters
        if (
            self.config.avatarization is not None
            and table_name in self.config.avatarization.keys()
        ):
            # Standard avatarization parameters
            params: (
                AvatarizationParameters
                | AvatarizationOpenDPParameters
                | AvatarizationFastDPParameters
                | PrivacyMetricsParameters
                | None
            ) = self.config.avatarization[table_name]
            if isinstance(params, AvatarizationParameters):
                current_params.update(
                    {
                        "k": params.k,
                        "column_weights": params.column_weights,
                        "use_categorical_reduction": params.use_categorical_reduction,
                        "ncp": params.ncp,
                    }
                )
                current_params.update(self._extract_exclude_parameters(params))
        elif (
            hasattr(self.config, "avatarization_open_dp")
            and self.config.avatarization_open_dp is not None
            and table_name in self.config.avatarization_open_dp.keys()
        ):
            # OpenDP avatarization parameters (end-to-end DP)
            params = self.config.avatarization_open_dp[table_name]
            if isinstance(params, AvatarizationOpenDPParameters):
                current_params.update(
                    {
                        "open_dp_epsilon": params.epsilon or None,
                        "column_weights": params.column_weights,
                        "use_categorical_reduction": params.use_categorical_reduction,
                        "ncp": params.ncp,
                    }
                )
                current_params.update(self._extract_exclude_parameters(params))
        elif (
            hasattr(self.config, "avatarization_fast_dp")
            and self.config.avatarization_fast_dp is not None
            and table_name in self.config.avatarization_fast_dp.keys()
        ):
            # FastDP avatarization parameters
            # Only epsilon is exposed; mechanism-specific params use defaults
            params = self.config.avatarization_fast_dp[table_name]
            if isinstance(params, AvatarizationFastDPParameters):
                current_params.update(
                    {
                        "fast_dp_epsilon": params.epsilon or None,
                        "column_weights": params.column_weights,
                        "use_categorical_reduction": params.use_categorical_reduction,
                        "ncp": params.ncp,
                    }
                )
                current_params.update(self._extract_exclude_parameters(params))
        else:
            params = None  # No parameters has been preset

        if (
            self.config.privacy_metrics is not None
            and self.config.privacy_metrics.get(table_name) is not None
        ):
            params = self.config.privacy_metrics[table_name]
            current_params.update(
                {
                    "use_categorical_reduction": params.use_categorical_reduction,
                    "ncp": params.ncp,
                }
            )
        else:
            params = None  # No parameters has been preset

        # Extract imputation parameters
        if params and params.imputation:
            current_params.update(
                {
                    "imputation_method": ImputeMethod(params.imputation["method"])
                    if params.imputation["method"]
                    else None,
                    "imputation_k": params.imputation["k"] or None,
                    "imputation_training_fraction": params.imputation["training_fraction"] or None,
                    "imputation_return_data_imputed": params.imputation["return_data_imputed"],
                }
            )

        # Extract time series parameters
        if self.config.time_series and table_name in self.config.time_series.keys():
            ts_params = self.config.time_series[table_name]

            # Projection parameters
            if ts_params.projection:
                current_params.update(
                    {
                        "time_series_nf": ts_params.projection["nf"] or None,
                        "time_series_projection_type": ProjectionType(
                            ts_params.projection["projection_type"]
                        )
                        if ts_params.projection["projection_type"]
                        else None,
                    }
                )

            # Alignment parameters
            if ts_params.alignment:
                current_params.update(
                    {
                        "time_series_nb_points": ts_params.alignment.get("nb_points") or None,
                        "time_series_method": AlignmentMethod(ts_params.alignment["method"])
                        if ts_params.alignment.get("method")
                        else None,
                        "time_series_unalignment": UnalignmentStrategy(
                            ts_params.alignment["unalignment"]
                        )
                        if ts_params.alignment.get("unalignment")
                        else None,
                    }
                )

            # Exclude variables parameters (time series entry takes precedence)
            current_params.update(self._extract_exclude_parameters(ts_params))

        # Extract privacy metrics parameters
        if (
            self.config.privacy_metrics is not None
            and table_name in self.config.privacy_metrics.keys()
        ):
            pm_params = self.config.privacy_metrics[table_name]
            to_update = {
                "known_variables": pm_params.known_variables,
                "target": pm_params.target,
                "quantile_threshold": pm_params.quantile_threshold,
            }
            current_params.update(to_update)

            # Detect use_excluded_variables_in_metrics: True when avatarization has
            # exclude_variables but privacy metrics does not.
            avatarization_has_excluded = bool(current_params.get("exclude_variable_names"))
            metrics_has_excluded = bool(
                pm_params.exclude_variables and pm_params.exclude_variables.get("variable_names")
            )
            if avatarization_has_excluded and not metrics_has_excluded:
                current_params["use_excluded_variables_in_metrics"] = True

        return current_params

    def _extract_exclude_parameters(
        self,
        params: AvatarizationParameters
        | AvatarizationOpenDPParameters
        | AvatarizationFastDPParameters
        | TimeSeriesParameters,
    ) -> dict[str, Any]:
        """Extract exclude variables parameters from parameter object.

        Parameters
        ----------
        params:
            The parameters object that contains exclude_variables information.

        Returns
        -------
        A dictionary containing exclude_variable_names and exclude_variable_method parameters.

        """
        result = {}
        if params.exclude_variables:
            result["exclude_variable_names"] = params.exclude_variables["variable_names"] or None
            result["exclude_variable_method"] = (
                ExcludeVariablesMethod(params.exclude_variables["replacement_strategy"])
                if params.exclude_variables["replacement_strategy"]
                else None
            )
        return result

    def delete_parameters(
        self, table_name: str, parameters_names: list[str] | None = None
    ) -> None:
        """Delete parameters from the config.

        Parameters
        ----------
        table_name
            The name of the table.
        parameters_names
            The names of the parameters to delete. If None, all parameters will be deleted.

        """
        self.config.delete_parameters(table_name, parameters_names)

    def delete_link(self, parent_table_name: str, child_table_name: str) -> None:
        """Delete a link from the config.

        Parameters
        ----------
        parent_table_name
            The name of the parent table.
        child_table_name
            The name of the child table.

        """
        self.config.delete_link(parent_table_name, child_table_name)

    def delete_table(self, table_name: str) -> None:
        """Delete a table from the config.

        Parameters
        ----------
        table_name
            The name of the table.

        """
        self.config.delete_table(table_name)

    def get_yaml(self, path: str | None = None) -> str:
        """Get the yaml config.

        Parameters
        ----------
        path
            The path to the yaml file. If None, the default config will be returned.

        Raises
        ------
        ValueError
            When this run is several document sets -- a database whose tables
            fall into more than one group of related tables. There is no single
            configuration to return; see :meth:`cluster_yamls`.

        """
        if self._cluster_jobs:
            raise ValueError(
                f"this run is {len(self._cluster_jobs)} document sets, one per group of "
                f"related tables ({', '.join(self._cluster_jobs)}), so there is no single "
                "configuration to return. Use `cluster_yamls()` for one per group."
            )
        return self.config.get_yaml(path)

    def cluster_yamls(self, directory: str | None = None) -> dict[str, str]:
        """One complete configuration per group of related tables.

        Each is an ordinary multi-table configuration -- the same documents
        under the same names a multi-table run has always emitted -- because
        the fan-out is one *set* per group rather than one set holding several
        schemas. Nothing about the shape today's multi-table jobs rely on
        changes, and every job kind keeps working per group.

        Empty for a run that is a single job, where :meth:`get_yaml` is the
        answer.

        Parameters
        ----------
        directory
            Write each one to ``<directory>/<group>.yaml`` as well as
            returning it.

        """
        yamls = {cluster: config.get_yaml() for cluster, config in self._cluster_configs().items()}
        if directory is not None:
            for cluster, yaml in yamls.items():
                Path(directory, f"{cluster}.yaml").write_text(yaml)
        return yamls

    def _handle_existing_results(self, ignore_warnings: bool = False) -> None:
        """Warn and clean up local state when re-running a runner that already has results."""
        advice_job_names = {
            self.jobs.get_parameters_name(JobKind.advice),
            self.config.get_parameters_advice_name(
                name="advice", advisor_type=[AdviceType.TABLES_LINKS]
            ),
        }
        has_run_before = (
            not self.results.is_results_empty()
            or any(key not in advice_job_names for key in self.results_urls)
            or any(job not in advice_job_names for job in self.jobs.get_launched_jobs())
        )

        if has_run_before:
            if not ignore_warnings:
                set_name = self.set_name
                warnings.warn(
                    f"\nThis runner already has results for set_name '{set_name}'.\n"
                    "Re-running will create a new set_name — previous results will no longer "
                    "be accessible from this runner.\n"
                    f"To access previous results later:\n"
                    f"regenerated_runner = manager.create_runner_from_id('{set_name}')\n"
                    "regenerated_runner.shuffled(...)",
                    UserWarning,
                    stacklevel=2,
                )
            self.results_urls.clear()
            self._downloaded_results.clear()
            self.results = ResultsOrganizer()
            self.jobs.jobs.clear()

    def run(
        self, jobs_to_run: list[JobKind] = JOB_EXECUTION_ORDER, ignore_warnings: bool = False
    ) -> None:
        """Run avatarization jobs.

        This method creates resources and launches the specified jobs in the correct order.
        If this runner has existing results from a previous run, a ``UserWarning`` is emitted
        with the old ``set_name`` so you can recover previous results if needed. Local state
        is then cleared and a new run starts.

        Parameters
        ----------
        jobs_to_run : list[JobKind]
            List of job types to run. Defaults to all jobs in execution order.
        ignore_warnings: bool
            Whether to ignore warnings about existing results when re-running a runner.
            Defaults to False.

        Examples
        --------
        >>> runner = manager.create_runner("my_dataset")
        >>> runner.add_table("customers", data=df)
        >>> runner.run()
        >>>
        >>> # Running again emits a UserWarning with the old set_name, then proceeds
        >>> runner.run()

        """
        self._handle_existing_results(ignore_warnings=ignore_warnings)

        # Create report configurations if report job is requested and report configurations
        # are not already set (could happen when creating a runner from an existing config)
        if JobKind.report in jobs_to_run:
            if self.config.report is None or ReportType.BASIC not in self.config.report:
                self.config.create_report(language=self.report_language)
            if self.config.report is None or ReportType.PIA not in self.config.report:
                self.config.create_report(ReportType.PIA, language=self.report_language)

        # Execute jobs in order
        jobs_to_run = sorted(jobs_to_run, key=JOB_EXECUTION_ORDER.index)

        if self._cluster_jobs:
            self._run_each_cluster(jobs_to_run)
            return

        resource_response = self.client.resources.put_resources(
            display_name=self.display_name,
            yaml_string=self.get_yaml(),
        )
        # Update set_name with the actual UUID returned by the backend
        self.set_name = str(resource_response.set_name)
        self.jobs.set_name = self.set_name

        for i, job_kind in enumerate(jobs_to_run):
            # Add small delay between job creations to avoid bursts in api calls
            # Skip delay for first job
            if i > 0:
                time.sleep(DEFAULT_DELAY_BETWEEN_CONSECUTIVE_JOBS)
            self._launch_job(job_kind, self.set_name)

    def _launch_job(self, job_kind: JobKind, set_name: str) -> None:
        known = set(self.jobs.get_launched_jobs())
        self.jobs.launch_job(job_kind, set_name)
        started = self._clock.monotonic()
        for name in self.jobs.get_launched_jobs():
            if name not in known:
                self._job_started_at[name] = started

    def _run_each_cluster(self, jobs_to_run: list[JobKind]) -> None:
        """One document set per group of related tables, each an ordinary run.

        Uploaded and launched exactly the way a multi-table run is, once per
        group, because that is what each of them is: the same documents under
        the same names, over one group's tables. Nothing here is a special job
        kind or a renamed parameter, so metrics and the report work per group
        without knowing about any of this.

        The groups are independent of each other, with no `depends_on` between
        them: a group is closed under foreign keys, so two of them share no
        table and neither ordering nor a fan-in is needed to keep the target's
        referential integrity. They run at once, and one failing leaves the
        others' work standing rather than cancelling them.

        Each writes its own tables into the shared target and checks only its
        own are empty there, because the schema it validates against is its own
        -- so a sibling that has already written does not make this one refuse.
        """
        self._cluster_launchers = {}
        # One token per launch, from the clock as the web app does: two launches of one
        # configuration are two runs, and their sets must not be listed as one.
        self._launch = _base36(time.time_ns() // 1_000_000)
        # Every group's set is stored before any job starts, as the web app does. Pushing and
        # launching group by group left a run half-launched when a later group's set was
        # refused -- the first group's jobs already writing the target.
        pushed: list[tuple[str, Config, str]] = []
        for index, (cluster, config) in enumerate(self._cluster_configs().items()):
            if index > 0:
                time.sleep(DEFAULT_DELAY_BETWEEN_CONSECUTIVE_JOBS)
            response = self.client.resources.put_resources(
                # The web app's convention, so it lists the groups of one launch as one run:
                # `name__launch--group`. A display name may hold only letters, digits, `_`
                # and `-`; the API refuses anything else.
                display_name=f"{self.display_name}__{self._launch}--{cluster}",
                yaml_string=config.get_yaml(),
            )
            pushed.append((cluster, config, str(response.set_name)))
        reference = self._launch_reference_job(pushed[0][1] if pushed else None)
        for cluster, config, set_name in pushed:
            launcher = JobLauncher(self.client, config)
            launcher.set_name = set_name
            launcher.reference_job = reference
            for position, job_kind in enumerate(jobs_to_run):
                if position > 0:
                    time.sleep(DEFAULT_DELAY_BETWEEN_CONSECUTIVE_JOBS)
                launcher.launch_job(job_kind, set_name)
            self._cluster_launchers[cluster] = launcher
        # No single set holds this run, so `set_name` stays as it was rather
        # than naming one group and implying it is the whole thing. The set of
        # each group is `cluster_sets()`.
        logger.info(
            "launched %d run(s), one per group of related tables: %s",
            len(self._cluster_launchers),
            ", ".join(
                f"{cluster} ({len(self._cluster_jobs[cluster].tables)} table(s), set "
                f"{launcher.set_name})"
                for cluster, launcher in self._cluster_launchers.items()
            ),
        )

    def _launch_reference_job(self, group: Config | None) -> str | None:
        """Resolve the run's shared entities once, in a set of their own (ADR-0013).

        A shared entity belongs to no group: it is collected from tables of every database the
        run copies. Its set -- named like a group, ``name__launch--reference-tables``, so the
        web lists it with the run -- holds the databases it is found in, the entities and the
        reference job. Every group's Extraction and Génération wait for that job and apply the
        map it leaves. None, and nothing launched, when the run declares no entity.
        """
        self._reference_launcher = None
        if group is None:
            return None
        documents = reference_set([d for d in yaml.safe_load_all(group.get_yaml()) if d])
        if not documents:
            return None
        response = self.client.resources.put_resources(
            display_name=f"{self.display_name}__{self._launch}--{REFERENCE_SET}",
            yaml_string=dump(documents),
        )
        launcher = JobLauncher(self.client, group)
        launcher.launch_reference_job(str(response.set_name))
        self._reference_launcher = launcher
        logger.info("launched the run's reference job, set %s", launcher.set_name)
        return launcher.jobs[REFERENCE_JOB].Location

    def cluster_sets(self) -> dict[str, str]:
        """Group of related tables -> the resource set its run created.

        Each group is its own set, so its results are read the way any other
        run's are::

            for cluster, set_name in runner.cluster_sets().items():
                manager.create_runner_from_id(set_name).get_all_results()

        Empty until :meth:`run` has been called, and for a run that is a single
        job -- where `runner.set_name` is the answer.
        """
        return {
            cluster: str(launcher.set_name)
            for cluster, launcher in self._cluster_launchers.items()
        }

    def clusters(self) -> dict[str, list[str]]:
        """The groups of related tables this run works on, one job per group.

        Empty unless the run fanned out. A database whose tables all reference
        each other is one job, like any other run, and a plan reviewed down to
        one group is too.

        The names identify the runs, and say what is in them: discovery names
        a group after the table the most links touch, so ``group-customer``
        has its own document set (:meth:`cluster_sets`) and its own jobs,
        reported by :meth:`statuses` as ``group-customer/standard`` and so on.
        """
        return {job.name: list(job.tables) for job in self._cluster_jobs.values()}

    def get_job(self, job_name: JobKind | str) -> JobResponse:
        """Get the job by name.

        Parameters
        ----------
        job_name
            The name of the job to get.

        """
        return self.jobs.get_job_status(job_name)

    def statuses(self) -> dict[str, JobStatus]:
        """Where every job this runner launched has got to.

        A run is several jobs -- the anonymization, the metrics, the report, and
        for a document run the extraction and the write-back as well -- and
        until now there was no way to ask about more than one at a time. So
        "did my run work?" meant calling :meth:`get_status` once per kind and
        knowing which kinds to expect, and a job that failed while its siblings
        finished was easy to miss entirely.

        Ordered the way the work happens rather than the way the jobs were
        registered: the dependent jobs are all created at once, so registration
        order says nothing, and a reader scanning for the first failure wants
        the sequence.

        A database run covering several groups of related tables is several
        runs, one per group, and every one of their jobs is reported here --
        prefixed by the group, since each group has a job of each kind. See
        :meth:`clusters` and :meth:`cluster_sets`.

        Examples
        --------
        >>> runner.statuses()
        {'standard': 'finished', 'signal_metrics': 'error'}
        >>> runner.statuses()  # a database with two groups of related tables
        {'group-customer/standard': 'finished', 'group-audit_log/standard': 'pending'}

        """
        if self._cluster_launchers:
            reference = self._reference_launcher
            return {
                **(
                    {
                        f"{REFERENCE_SET}/{REFERENCE_JOB}": reference.get_job_status(
                            REFERENCE_JOB
                        ).status
                    }
                    if reference is not None
                    else {}
                ),
                **{
                    f"{cluster}/{kind}": launcher.get_job_status(kind).status
                    for cluster, launcher in self._cluster_launchers.items()
                    for kind in _ordered(launcher.get_launched_jobs())
                },
            }
        return {
            str(kind): self.get_job(kind).status
            for kind in _ordered(self.jobs.get_launched_jobs())
        }

    def get_status(
        self,
        job_kind: JobKind | str | None = None,
        *,
        job_name: JobKind | str | None = None,
    ) -> str:
        """Get the status of a job.

        Parameters
        ----------
        job_kind
            The job to query. Accepts a :class:`~avatars.models.JobKind` enum value
            (e.g. ``JobKind.standard``) or the equivalent string (e.g. ``"standard"``).
        job_name
            Deprecated. Use ``job_kind`` instead.

        Returns
        -------
        str
            The job status string as returned by the server (e.g. ``"finished"``,
            ``"pending"``, ``"error"``).

        Examples
        --------
        >>> runner.get_status(JobKind.standard)
        'finished'
        >>> runner.get_status("privacy_metrics")
        'finished'

        """
        if job_name is not None:
            warnings.warn(
                "The 'job_name' parameter is deprecated, use 'job_kind' instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            job_kind = job_name
        if job_kind is None:
            raise ValueError("job_kind is required.")
        return self.get_job(job_kind).status

    def delete(
        self, job_names: JobKind | str | list[JobKind | str] | None = None
    ) -> BulkDeleteResponse:
        """Delete one or more jobs launched by this runner.

        When called without arguments, every job launched by this runner is deleted.

        Parameters
        ----------
        job_names
            A single job kind/name, a list of job kinds/names, or ``None`` to
            delete all launched jobs.

        Returns
        -------
        BulkDeleteResponse
            Response containing deleted and failed jobs.

        Examples
        --------
        >>> runner.delete()                                              # all jobs
        >>> runner.delete(JobKind.standard)                             # single job
        >>> runner.delete([JobKind.standard, JobKind.privacy_metrics])  # multiple jobs

        """
        if job_names is None:
            names: list[JobKind | str] = list(self.jobs.get_launched_jobs())
        elif not isinstance(job_names, list):
            names = [job_names]
        else:
            names = job_names
        job_ids = [self.jobs.get_job_id(name) for name in names]
        return self.client.jobs.bulk_delete_jobs(BulkDeleteRequest(job_names=job_ids))

    def cancel(
        self, job_names: JobKind | str | list[JobKind | str] | None = None
    ) -> list[JobResponse]:
        """Stop one or more jobs launched by this runner.

        When called without arguments, every job of this runner that is still
        going is cancelled. A job that has not started stops at once; a running
        one is asked to stop and does so at its next safe point -- between
        stages, batches, tables or documents -- so it comes back with its phase
        set to ``"cancelling"`` and turns ``"cancelled"`` shortly after. The
        jobs that were waiting on a cancelled job are cancelled with it.

        A job that is already over is left alone rather than refused, so
        cancelling a whole run does not fail on the parts that finished -- or
        on the dependents the first cancel already took with it.

        .. warning::
           A database copy cancelled while writing keeps the tables it had
           already written in the target: writes cannot be rolled back across
           tables. The cancelled job's ``exception`` names them.

        Parameters
        ----------
        job_names
            A single job kind/name, a list of job kinds/names, or ``None`` for
            every job this runner launched.

        Returns
        -------
        list[JobResponse]
            The jobs a cancel was sent for, as the server answered.

        Examples
        --------
        >>> runner.cancel()                     # the whole run
        >>> runner.cancel(JobKind.standard)     # one job, and what waits on it

        """
        if job_names is None:
            names: list[JobKind | str] = list(self.jobs.get_launched_jobs())
        elif not isinstance(job_names, list):
            names = [job_names]
        else:
            names = job_names
        cancelled: list[JobResponse] = []
        for name in names:
            if self.get_job(name).done:
                continue
            cancelled.append(self.client.jobs.cancel_job(self.jobs.get_job_id(name)))
        return cancelled

    def _retrieve_job_result_urls(self, job_name: str) -> None:
        """Get the result of a job by name.

        Parameters
        ----------
        job_name
            The name of the job to get.

        """
        wait_for_jobs([job_name], self.get_job, self._clock, self._job_started_at)
        self._fetch_job_result_urls(job_name)

    def _fetch_job_result_urls(self, job_name: str) -> None:
        job_id = self.jobs.get_job_id(job_name)
        self.results_urls[job_name] = self.client.results.get_results(job_id)

    def _populate_results_from_existing_jobs(self) -> None:
        """Register all jobs and fetch result URLs from completed jobs for this set_name.

        This method is used when reconstructing a Runner from an existing set_name.
        It fetches all jobs associated with the set_name, registers every job with the
        JobLauncher (regardless of completion status), and then populates the results_urls
        dictionary for successfully completed jobs only.

        Registering all jobs (not just done ones) ensures that methods like
        ``get_status()`` work correctly even for in-progress or errored jobs.

        If a job's results are no longer available on the server (404 error), a warning
        is issued but the method continues to process other jobs.
        """
        if not self.set_name:
            return

        set_name_jobs = self.client.jobs.get_jobs(set_name=self.set_name)
        set_jobs = list(set_name_jobs.jobs)

        # Pass 1: Register ALL jobs for this set_name so that get_status() works
        # regardless of whether the job has finished.
        # The client-side set_name guard is a safety net for older API versions that
        # do not support server-side set_name filtering (they return all user jobs).
        for job in set_jobs:
            self.jobs.register_existing_job(job.parameters_name, job.name, f"/jobs/{job.name}")

        # Pass 2: Fetch result URLs only for successfully completed jobs.
        jobs_done = [job for job in set_jobs if job.status == JobStatus.finished]
        for job in jobs_done:
            job_name = job.name
            parameters_name = job.parameters_name
            try:
                self.results_urls[parameters_name] = self.client.results.get_results(job_name)

            except Exception as e:
                # Keep backward-compatible behavior only for missing-results 404s.
                error_message = str(e).lower()
                is_missing_results_404 = (
                    "error status 404" in error_message and "results file for job" in error_message
                )
                if is_missing_results_404:
                    if not self._has_results_missing_warning_issued:
                        tables_list = list(self.config.tables.keys())
                        warnings.warn(
                            f"Results for job '{job_name}' are no longer "
                            "available on the server. "
                            "Input data has also been cleaned up. "
                            f"You need to reupload the following tables: {tables_list}. "
                            "You can relaunch the job with the same configuration by calling "
                            "runner.run() after re-uploading your data with "
                            "runner.upload_file().",
                            stacklevel=2,
                        )
                        # raise only once if multiple jobs are missing results
                        self._has_results_missing_warning_issued = True
                    continue

                raise

    def get_specific_result_urls(
        self,
        job_name: str,
        result: Results = Results.SHUFFLED,
    ) -> list[str]:
        if not self.jobs.has_job(job_name):
            raise ValueError(f"Expected job '{job_name}' to be created. Try running it first.")
        if job_name not in self.results_urls:
            self._retrieve_job_result_urls(job_name)
        if result not in self.results_urls[job_name]:
            return []
        return self.results_urls[job_name][result]

    def _download_all_files(self) -> None:
        launched = self.jobs.get_launched_jobs()
        waiting = [name for name in launched if name not in self.results_urls]
        wait_for_jobs(waiting, self.get_job, self._clock, self._job_started_at)
        for job_name in launched:
            if job_name not in self.results_urls:
                self._fetch_job_result_urls(job_name)
            for result in self.results_urls[job_name].keys():
                if result in Results and Results(result) in RESULTS_TO_STORE:
                    self._download_result_once(job_name, Results(result))

    def _download_specific_result(
        self,
        job_name: str,
        result_name: Results,
    ) -> None:
        urls = self.get_specific_result_urls(job_name=job_name, result=result_name)
        # Use batch download to get all file credentials at once
        downloaded_results = self.file_downloader.download_files_batch(urls)
        figures_metadatas = (
            self._download_figures_metadatas(job_name)
            if result_name == Results.FIGURES and downloaded_results
            else []
        )
        for url, result in downloaded_results.items():
            metadata: dict[str, Any] | None = None
            if result_name == Results.FIGURES:
                metadata = self.results.find_figure_metadata(figures_metadatas, url)
            elif result_name == Results.METADATA:
                metadata = {"kind": job_name}
            table_name = self.results.get_table_name(result_name, url, result, metadata)
            if table_name is not None:
                self.results.set_results(
                    table_name=table_name,
                    result=result,
                    result_name=result_name,
                    metadata=metadata,
                )
        self._downloaded_results.add((job_name, result_name))

    def _download_result_once(self, job_name: str, result_name: Results) -> None:
        if (job_name, result_name) not in self._downloaded_results:
            self._download_specific_result(job_name, result_name)

    def _download_figures_metadatas(self, job_name: str) -> list[dict[str, Any]]:
        url = self.results_urls[job_name][Results.FIGURES_METADATA][0]
        figures_metadatas = self.file_downloader.download_file(url)
        if isinstance(figures_metadatas, list):
            return figures_metadatas
        raise TypeError(
            f"Expected a list, got {type(figures_metadatas)} instead for {url} metadata."
        )

    def get_specific_result(
        self,
        table_name: str,
        job_name: JobKind | str,
        result: Results = Results.SHUFFLED,
    ) -> TypeResults:
        job_name_str = self.jobs.get_parameters_name(job_name)
        if table_name not in self.config.tables.keys():
            raise ValueError(f"Expected table '{table_name}' to be created.")
        if not self.jobs.has_job(job_name_str):
            raise ValueError(f"Expected job '{job_name}' to be created. Try running it first.")
        self._download_result_once(job_name_str, result)
        return self.results.get_results(table_name, result, job_name_str)

    def get_all_results(self) -> ResultsOrganizer:
        """Get all results.

        Returns
        -------
        dict
            A dictionary with the results of each job on every table.
        Each job is a dictionary with the table name as key and the results as value.
        The results are a dictionary with the result name as key and the data as value.
        The data can be a pandas DataFrame or a dictionary depending on the result type.

        """
        self._download_all_files()
        return self.results

    def download_report(
        self, path: str | None = None, report_type: ReportType = ReportType.BASIC
    ) -> None:
        """Download the report.

        Parameters
        ----------
        path
            The path to save the report. For a single report this is used as-is.
            When multiple PIA reports are returned (one per table), an index
            prefix is added to the filename only: ``dir/0_report.pdf``,
            ``dir/1_report.pdf``, etc.

        """
        is_pia = report_type == ReportType.PIA
        job_name = self.jobs.get_parameters_name(JobKind.report, pia_report=is_pia)
        if self.results_urls.get(job_name) is None:
            self._retrieve_job_result_urls(job_name)
        urls = self.results_urls[job_name][Results.REPORT]
        is_multi = len(urls) > 1
        for i, url in enumerate(urls):
            if path is not None:
                if is_multi:
                    p = Path(path)
                    output_path = str(p.parent / f"{i}_{p.name}")
                else:
                    output_path = path
            else:
                output_path = Path(url).name
            self.file_downloader.download_file(url, path=output_path)

    def print_parameters(self, table_name: str | None = None) -> None:
        """Print the parameters for a table.

        Parameters
        ----------
        table_name
            The name of the table.
            If None, all parameters will be printed.

        """
        if table_name is None:
            for table_name in self.config.tables.keys():  # noqa: PLR1704 - reuse param as loop var
                self.print_parameters(table_name)
            return
        if table_name not in self.config.tables.keys():
            raise ValueError(f"Expected table '{table_name}' to be created. Try running it first.")

        # Print avatarization parameters
        avatarization_open_dp = getattr(self.config, "avatarization_open_dp", None)
        avatarization_fast_dp = getattr(self.config, "avatarization_fast_dp", None)
        if self.config.avatarization and table_name in self.config.avatarization:
            print(f"--- Avatarization parameters for {table_name}: ---")  # noqa: T201
            print(asdict(self.config.avatarization[table_name]))  # noqa: T201
            print("\n")  # noqa: T201
        elif avatarization_open_dp and table_name in avatarization_open_dp:
            print(f"--- Avatarization OpenDP parameters for {table_name}: ---")  # noqa: T201
            print(asdict(avatarization_open_dp[table_name]))  # noqa: T201
            print("\n")  # noqa: T201
        elif avatarization_fast_dp and table_name in avatarization_fast_dp:
            print(f"--- Avatarization FastDP parameters for {table_name}: ---")  # noqa: T201
            print(asdict(avatarization_fast_dp[table_name]))  # noqa: T201
            print("\n")  # noqa: T201
        else:
            print(f"--- No avatarization parameters set for {table_name} ---")  # noqa: T201
            print("\n")  # noqa: T201

        # Print privacy metrics parameters
        if self.config.privacy_metrics and table_name in self.config.privacy_metrics:
            print(f"--- Privacy metrics for {table_name}: ---")  # noqa: T201
            print(asdict(self.config.privacy_metrics[table_name]))  # noqa: T201
            print("\n")  # noqa: T201
        else:
            print(f"--- No privacy metrics parameters set for {table_name} ---")  # noqa: T201
            print("\n")  # noqa: T201

        # Print signal metrics parameters
        if self.config.signal_metrics and table_name in self.config.signal_metrics:
            print(f"--- Signal metrics for {table_name}: ---")  # noqa: T201
            print(asdict(self.config.signal_metrics[table_name]))  # noqa: T201
        else:
            print(f"--- No signal metrics parameters set for {table_name} ---")  # noqa: T201

    def kill(self) -> None:
        """Method not implemented yet."""

    def shuffled(self, table_name: str) -> pd.DataFrame:
        """Get the shuffled data.

        Parameters
        ----------
        table_name
            The name of the table to get the shuffled data from.

        Returns
        -------
        pd.DataFrame
            The shuffled data as a pandas DataFrame.

        """
        shuffled = self.get_specific_result(table_name, JobKind.standard, Results.SHUFFLED)
        if not isinstance(shuffled, pd.DataFrame):
            raise TypeError(f"Expected a pd.DataFrame, got {type(shuffled)} instead.")
        return shuffled

    def sensitive_unshuffled(self, table_name: str) -> pd.DataFrame:
        """Get the unshuffled data.
        This is sensitive data and should be used with caution.

        Parameters
        ----------
        table_name
            The name of the table to get the unshuffled data from.

        Returns
        -------
        pd.DataFrame
            The unshuffled data as a pandas DataFrame.

        """
        unshuffled = self.get_specific_result(table_name, JobKind.standard, Results.UNSHUFFLED)
        if not isinstance(unshuffled, pd.DataFrame):
            raise TypeError(f"Expected a pd.DataFrame, got {type(unshuffled)} instead.")
        return unshuffled

    def privacy_metrics(self, table_name: str) -> list[dict[str, Any]]:
        """Get the privacy metrics.

        Parameters
        ----------
        table_name
            The name of the table to get the privacy metrics from.

        Returns
        -------
        dict
            The privacy metrics as a list of dictionary.

        """
        results = self.get_specific_result(
            table_name, JobKind.privacy_metrics, Results.PRIVACY_METRICS
        )
        if not isinstance(results, list):
            raise TypeError(f"Expected a list, got {type(results)} instead.")
        return results

    def signal_metrics(self, table_name: str) -> list[dict[str, Any]]:
        """Get the signal metrics.

        Parameters
        ----------
        table_name
            The name of the table to get the signal metrics from.

        Returns
        -------
        dict
            The signal metrics as a list of dictionary.

        """
        results = self.get_specific_result(
            table_name, JobKind.signal_metrics, Results.SIGNAL_METRICS
        )
        if not isinstance(results, list):
            raise TypeError(f"Expected a list, got {type(results)} instead.")
        return results

    def render_privacy_metrics_summary(
        self,
        open_in_browser: bool = False,  # DEPRECATED
    ) -> dict[str, Any]:
        """Get the aggregated privacy metrics summary across tables.

        Only available for multi-table jobs.

        Parameters
        ----------
        open_in_browser
            Whether to save the summary to a file and open it in a browser. deprecated and will be
            removed in the future, as the summary is now returned as a dict instead of an HTML file

        Returns
        -------
        dict
            A nested dict ``{table_name: {reference: meta_metric}}``.

        """
        if len(self.config.tables) <= 1:
            raise ValueError(
                "render_privacy_metrics_summary is only available for multi-table jobs."
            )
        self._download_result_once("privacy_metrics", Results.PRIVACY_METRICS_SUMMARY)
        results = self.results.get_results(
            "summary", Results.PRIVACY_METRICS_SUMMARY, "privacy_metrics"
        )
        if not isinstance(results, dict):
            raise TypeError(f"Expected a dict, got {type(results)} instead.")
        return results

    def render_signal_metrics_summary(self) -> dict[str, Any]:
        """Get the aggregated signal metrics summary across tables.

        Only available for multi-table jobs.

        Returns
        -------
        dict
            A nested dict ``{table_name: {reference: meta_metric}}``.

        """
        if len(self.config.tables) <= 1:
            raise ValueError(
                "render_signal_metrics_summary is only available for multi-table jobs."
            )
        self._download_result_once("signal_metrics", Results.SIGNAL_METRICS_SUMMARY)
        results = self.results.get_results("summary", Results.SIGNAL_METRICS_SUMMARY, "")
        if not isinstance(results, dict):
            raise TypeError(f"Expected a dict, got {type(results)} instead.")
        return results

    def metrics_summary(self) -> pd.DataFrame:
        """Get the combined privacy and signal metrics summary across tables as a DataFrame.

        Only available for multi-table jobs.

        Returns
        -------
        pd.DataFrame
            A DataFrame indexed by ``table_name`` with MultiIndex columns ``(reference, metric)``
            where ``reference`` is the top level and ``metric`` is ``privacy`` or ``signal``,
            combining both meta-metrics for each table/reference pair.

        """
        return build_metrics_summary_df(
            privacy=self.render_privacy_metrics_summary(),
            signal=self.render_signal_metrics_summary(),
        )

    def render_plot(
        self, table_name: str, plot_kind: PlotKind, open_in_browser: bool = False
    ) -> None:
        """Render a plot for a given table.
        The different plot kinds are defined in the PlotKind enum.

        Parameters
        ----------
        table_name
            The name of the table to get the plot from.
        plot_kind
            The kind of plot to render.
        open_in_browser
            Whether to save the plot to a file and open it in a browser.

        """
        results = self.get_specific_result(table_name, JobKind.standard, Results.FIGURES)
        if not isinstance(results, dict):
            raise TypeError(f"Expected a dict, got {type(results)} instead.")
        if plot_kind not in results:
            raise ValueError(f"No {plot_kind} found for table '{table_name}'.")
        plots = results[plot_kind]
        for idx, plot in enumerate(plots):
            filename = None
            if open_in_browser:
                filename = f"{table_name}_{plot_kind.value}_{idx}.html"
                self._save_file(plot, filename=filename)
            self._open_plot(plot, filename=filename)

    def projections(self, table_name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Get the projections.

        Parameters
        ----------
        table_name
            The name of the table to get the projections from.

        Returns
        -------
        pd.DataFrame
            The projections as a pandas DataFrame.

        """
        original_coordinates = self.get_specific_result(
            table_name, JobKind.standard, Results.PROJECTIONS_ORIGINAL
        )
        avatars_coordinates = self.get_specific_result(
            table_name, JobKind.standard, Results.PROJECTIONS_AVATARS
        )
        if not (
            isinstance(avatars_coordinates, pd.DataFrame)
            and isinstance(original_coordinates, pd.DataFrame)
        ):
            raise TypeError(
                "Expected a pd.DataFrame, "
                f"got {type(original_coordinates)} and {type(avatars_coordinates)} instead."
            )
        return original_coordinates, avatars_coordinates

    def table_summary(self, table_name: str) -> pd.DataFrame:
        """Get the table summary.

        Parameters
        ----------
        table_name
            The name of the table to get the summary from.

        Returns
        -------
        pd.DataFrame
            The table summary as a dataframe.

        """
        results = self.get_specific_result(table_name, JobKind.advice, Results.ADVICE)
        if not isinstance(results, dict) or "summary" not in results.keys():
            raise ValueError(f"Summary not found in results for table '{table_name}'")

        summary_data = results["summary"]
        if "stats" not in summary_data.keys():
            raise ValueError(f"Summary not found in results for table '{table_name}'")
        return pd.DataFrame(summary_data["stats"])

    def from_yaml(self, yaml_path: str) -> None:
        """Load configuration from a YAML file.

        This replaces the current runner's configuration with the one from the file.

        **Note**: Table data files are not automatically loaded. Use ``upload_file()``
        to provide data before running jobs.

        Parameters
        ----------
        yaml_path : str
            The path to the YAML configuration file.

        """
        with open(yaml_path) as file:
            yaml_string = file.read()

        # Parse YAML using ConfigParser
        self.config = Config.from_yaml(yaml_string)

    def _open_plot(self, plot_html: HTML, filename: str | None = None) -> None:
        """Render a plot, optionally saving it and opening it in a browser."""
        if filename:
            file_path = os.path.abspath(filename)
            webbrowser.open(f"file://{file_path}")
        else:
            # IPython.display.display ships py.typed but is unannotated.
            display(plot_html)  # type: ignore[no-untyped-call]

    def _save_file(self, file_content: HTML, filename: str | None = None) -> None:
        """Save the HTML file content to a specified path."""
        if filename is None:
            return
        with open(filename, "w", encoding="utf-8") as file:
            file.write(file_content.data)


def _require_something_to_model(plan: SchemaPlan, table: str, frozen: list[str]) -> None:
    """Refuse a table the avatarization would be left nothing to work on.

    The engine refuses it too, from three layers down and without naming the
    table: "Expected at least one column to be left after excluding
    variables". Which is right -- excluding every column asks it to model
    nothing -- but it arrives mid-run, from a processor, about a decision
    made at review time.

    It is reachable the moment freezing is: a lookup table of a key and one
    label, with the label frozen, has nothing left. So it is said here,
    naming the table and the two ways out.
    """
    if not frozen:
        return
    modellable = set(plan.anonymizable_columns(table)) - set(frozen)
    if modellable:
        return
    treatment = plan.treatment_of(table)
    described = (
        "is set to copy, so every column of it is kept verbatim"
        if treatment == "copy"
        else f"has every column the avatarization could model frozen ({', '.join(frozen)})"
    )
    raise ValueError(
        f"table {table!r} {described}, which leaves the avatarization nothing to "
        "work on and is refused by the engine mid-run. Either anonymize one column "
        f"of {table!r}, or leave the table out of the run with `ignore`."
    )


def _link_method(plan: SchemaPlan, parent: str) -> LinkMethod:
    """How children are matched to their parent rows after anonymization.

    Row order, for every link, for now -- a deliberate decision while the
    database path is being built rather than a discovered constraint. It is
    the only method that works from a parent the avatarization leaves
    nothing to do, and picking per link instead meant a lookup table whose
    only real column is pseudonymized got the assignment method and the
    engine refused the run:

        Link from table 'country' to table 'customer' uses link method
        'LINEAR_SUM_ASSIGNMENT' but parent table 'country' has no
        anonymizable columns.

    The trade-off is real and recorded on the enum member itself: keeping
    the original order to assign a child to its parent is a privacy breach,
    so this is a "for now" and not an answer. `LINEAR_SUM_ASSIGNMENT` is the
    one to return here when a link method is chosen per link properly --
    which needs to know whether the parent has anything to avatarize, which
    `plan.anonymizable_columns(parent)` answers.
    """
    return LinkMethod.SENSITIVE_ORIGINAL_ORDER_ASSIGNMENT


def _ordered(launched: list[str]) -> list[str]:
    """The jobs of one run, in the order the work happens."""
    order = [
        JobKind.extract,
        JobKind.standard,
        JobKind.regenerate,
        JobKind.signal_metrics,
        JobKind.privacy_metrics,
        JobKind.report,
    ]
    rank = {str(kind): index for index, kind in enumerate(order)}
    return sorted(
        launched,
        # A kind this list does not name still appears, after the ones it
        # does, rather than being dropped from the answer.
        key=lambda kind: (rank.get(str(kind), len(order)), str(kind)),
    )

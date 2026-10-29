"""The serverless client, exercised without the engine.

The end-to-end test at the bottom is the one that matters: it drives a real
``Runner`` through ``ServerlessClient`` from ``add_table`` to ``shuffled``, so every
seam the SDK depends on -- volume injection, the upload path, job creation and
dependency resolution, ``results.json``, the access envelope, download,
``ResultsOrganizer`` -- is covered in one pass.
"""

from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

import pandas as pd
import pytest
from avatar_yaml.models.config import INPUT_VOLUME_NAME, OUTPUT_VOLUME_NAME

from avatars.manager import Manager
from avatars.models import (
    BulkDeleteRequest,
    CompatibilityResponse,
    CompatibilityStatus,
    JobCreateRequest,
    JobKind,
    JobStatus,
)
from avatars.runner import Runner
from avatars.serverless.client import LicenseSummary, NotAvailableOfflineError, ServerlessClient
from avatars.serverless.config import ServerlessConfig
from avatars.serverless.store import ServerlessStore
from tests.unit.conftest import FakeApiClient
from tests.unit.serverless.conftest import IRIS, FakeEngineExecutor


def a_summary() -> LicenseSummary:
    return LicenseSummary(
        email="alice@acme.test",
        organization="Acme",
        jti="j-1",
        license_type="starter",
        feature_scopes=("avatar_parameters", "single_table"),
        max_rows=100_000,
        max_columns=2**31 - 1,
        expires_at=datetime(2027, 3, 31, tzinfo=UTC),
        engine_build_ends=date(2028, 4, 26),
    )


class TestPutResources:
    def test_injects_the_two_volumes_the_sdk_never_emits(self, client: ServerlessClient) -> None:
        """`Runner` never calls create_volume, so the deployment must add them.

        The names are not free choices: `avatar_yaml` writes `volume: results` into
        every parameters document by default, so an injected volume under any other
        name would not be found.
        """
        response = client.resources.put_resources("my_dataset", "kind: AvatarSchema\n")
        stored = client.workdir.resources_path(response.set_name).read_text()
        assert f"name: {INPUT_VOLUME_NAME}" in stored
        assert f"name: {OUTPUT_VOLUME_NAME}" in stored
        assert str(client.workdir.input_dir) in stored
        assert str(client.workdir.results_dir(response.set_name)) in stored

    def test_each_call_is_a_new_set(self, client: ServerlessClient) -> None:
        first = client.resources.put_resources("d", "kind: AvatarSchema\n")
        second = client.resources.put_resources("d", "kind: AvatarSchema\n")
        assert first.set_name != second.set_name

    def test_display_name_is_echoed_and_recorded(self, client: ServerlessClient) -> None:
        response = client.resources.put_resources("my_dataset", "kind: AvatarSchema\n")
        assert response.display_name == "my_dataset"
        stored = client.store.get_set(response.set_name)
        assert stored is not None
        assert stored.display_name == "my_dataset"

    def test_get_resources_returns_what_was_stored(self, client: ServerlessClient) -> None:
        response = client.resources.put_resources("d", "kind: AvatarSchema\n")
        assert "AvatarSchema" in client.resources.get_resources(str(response.set_name))

    def test_a_database_or_documents_input_is_refused(self, client: ServerlessClient) -> None:
        """Not offered offline yet, and such a run is not bounded by the licence's caps."""
        yaml_string = (
            "kind: AvatarParameters\nmetadata:\n  name: standard\n"
            "spec:\n  input:\n    database: crm\n"
        )
        with pytest.raises(NotAvailableOfflineError, match="database or documents"):
            client.resources.put_resources("d", yaml_string)

    def test_get_resources_for_an_unknown_set_says_so(self, client: ServerlessClient) -> None:
        with pytest.raises(ValueError, match="No resource set"):
            client.resources.get_resources(str(uuid4()))


class TestUploadDownload:
    def test_dataframe_lands_in_the_input_volume_as_parquet(
        self, client: ServerlessClient
    ) -> None:
        client.upload_file(IRIS, "iris.parquet")
        written = client.workdir.input_dir / "iris.parquet"
        assert written.is_file()
        pd.testing.assert_frame_equal(pd.read_parquet(written), IRIS)

    def test_a_path_is_copied_byte_for_byte(
        self, client: ServerlessClient, tmp_path: Path
    ) -> None:
        source = tmp_path / "source.csv"
        source.write_text("a,b\n1,2\n")
        client.upload_file(str(source), "iris.csv")
        assert (client.workdir.input_dir / "iris.csv").read_text() == "a,b\n1,2\n"

    def test_anything_else_is_refused_clearly(self, client: ServerlessClient) -> None:
        with pytest.raises(ValueError, match="path to a file or a pandas dataframe"):
            client.upload_file(42, "x.csv")  # type: ignore[arg-type]

    def test_upload_url_points_at_the_input_volume(self, client: ServerlessClient) -> None:
        assert client.results.get_upload_url() == client.workdir.input_url

    def test_download_reads_text_and_binary_the_way_the_server_client_does(
        self, client: ServerlessClient
    ) -> None:
        csv = client.workdir.input_dir / "a.csv"
        csv.write_text("x\n1\n")
        IRIS.to_parquet(client.workdir.input_dir / "a.parquet")

        access = client.results.get_permission_to_download(f"file://{csv}")
        assert client.download_file(access) == "x\n1\n"

        parquet_access = client.results.get_permission_to_download(
            f"file://{client.workdir.input_dir / 'a.parquet'}"
        )
        assert isinstance(client.download_file(parquet_access), bytes)

    def test_permission_echoes_the_url_and_mints_no_credentials(
        self, client: ServerlessClient
    ) -> None:
        access = client.results.get_permission_to_download("file:///a/b.csv")
        assert access.url == "file:///a/b.csv"
        assert access.credentials.access_key_id == ""

    def test_batch_permission_preserves_order(self, client: ServerlessClient) -> None:
        urls = ["file:///a.csv", "file:///b.csv"]
        assert [a.url for a in client.results.get_permissions_to_download_batch(urls)] == urls


class TestJobLifecycle:
    def _set(self, client: ServerlessClient) -> str:
        return str(client.resources.put_resources("d", "kind: AvatarSchema\n").set_name)

    def test_a_job_runs_synchronously_and_is_finished_on_return(
        self, client: ServerlessClient
    ) -> None:
        """Runner.run() does not wait, so the first status read must be the final one."""
        set_name = self._set(client)
        created = client.send_request(
            method="post",
            url="/jobs",
            json_data=JobCreateRequest(set_name=set_name, parameters_name="standard"),
        )
        status = client.jobs.get_job_status(created["name"])
        assert status.status == JobStatus.finished
        assert status.done is True

    def test_failure_is_recorded_not_raised(self, workdir, store) -> None:
        """The server records the error and lets run() continue; so must we, or the
        remaining jobs of a run would never be created.
        """
        client = ServerlessClient(
            settings=ServerlessConfig(workdir=workdir.root),
            workdir=workdir,
            store=store,
            executor=FakeEngineExecutor(fail_with=RuntimeError("boom")),
        )
        set_name = self._set(client)
        created = client.send_request(
            method="post",
            url="/jobs",
            json_data=JobCreateRequest(set_name=set_name, parameters_name="standard"),
        )
        status = client.jobs.get_job_status(created["name"])
        assert status.status == JobStatus.error
        assert "RuntimeError: boom" in status.exception
        assert client.workdir.log_path(created["name"]).is_file()

    def test_a_dependent_job_is_not_run_when_its_parent_failed(self, workdir, store) -> None:
        executor = FakeEngineExecutor(fail_with=RuntimeError("boom"))
        client = ServerlessClient(
            settings=ServerlessConfig(workdir=workdir.root),
            workdir=workdir,
            store=store,
            executor=executor,
        )
        set_name = self._set(client)
        parent = client.send_request(
            method="post",
            url="/jobs",
            json_data=JobCreateRequest(set_name=set_name, parameters_name="standard"),
        )
        executor.fail_with = None
        child = client.send_request(
            method="post",
            url="/jobs",
            json_data=JobCreateRequest(
                set_name=set_name,
                parameters_name="privacy_metrics",
                depends_on=[parent["Location"]],
            ),
        )
        status = client.jobs.get_job_status(child["name"])
        assert status.status == JobStatus.parent_error
        # And crucially it was never handed to the executor.
        assert [r.parameters_name for r in executor.runs] == ["standard"]

    def test_dependencies_are_resolved_to_the_parameters_hierarchy(
        self, client: ServerlessClient, executor: FakeEngineExecutor
    ) -> None:
        """`create_dependent_config` wants parameters names; `depends_on` carries job
        Locations. A report additionally needs its parents' own parents.
        """
        set_name = self._set(client)
        standard = client.send_request(
            method="post",
            url="/jobs",
            json_data=JobCreateRequest(set_name=set_name, parameters_name="standard"),
        )
        privacy = client.send_request(
            method="post",
            url="/jobs",
            json_data=JobCreateRequest(
                set_name=set_name,
                parameters_name="privacy_metrics",
                depends_on=[standard["Location"]],
            ),
        )
        client.send_request(
            method="post",
            url="/jobs",
            json_data=JobCreateRequest(
                set_name=set_name,
                parameters_name="report",
                depends_on=[privacy["Location"]],
            ),
        )
        report_run = executor.runs[-1]
        assert report_run.parent_parameters == ["privacy_metrics"]
        assert report_run.grandparent_parameters == {"privacy_metrics": "standard"}

    def test_job_kind_is_derived_from_the_parameters_name(self, client: ServerlessClient) -> None:
        set_name = self._set(client)
        for parameters_name, expected in [
            ("standard", JobKind.standard),
            ("privacy_metrics", JobKind.privacy_metrics),
            ("signal_metrics", JobKind.signal_metrics),
            ("report", JobKind.report),
            ("report_pia", JobKind.report),
            ("advice_parameters", JobKind.advice),
        ]:
            created = client.send_request(
                method="post",
                url="/jobs",
                json_data=JobCreateRequest(set_name=set_name, parameters_name=parameters_name),
            )
            assert client.jobs.get_job_status(created["name"]).kind == expected

    def test_creating_a_job_for_an_unknown_set_says_so(self, client: ServerlessClient) -> None:
        with pytest.raises(ValueError, match="No resource set"):
            client.send_request(
                method="post",
                url="/jobs",
                json_data=JobCreateRequest(set_name=uuid4(), parameters_name="standard"),
            )

    def test_bulk_delete_reports_hits_and_misses(self, client: ServerlessClient) -> None:
        set_name = self._set(client)
        created = client.send_request(
            method="post",
            url="/jobs",
            json_data=JobCreateRequest(set_name=set_name, parameters_name="standard"),
        )
        response = client.jobs.bulk_delete_jobs(
            BulkDeleteRequest(job_names=[created["name"], "nope"])
        )
        assert [j.name for j in response.deleted_jobs] == [created["name"]]
        assert response.failed_jobs == ["nope"]

    def test_get_jobs_filters_by_name(self, client: ServerlessClient) -> None:
        set_name = self._set(client)
        names = [
            client.send_request(
                method="post",
                url="/jobs",
                json_data=JobCreateRequest(set_name=set_name, parameters_name="standard"),
            )["name"]
            for _ in range(2)
        ]
        found = client.jobs.get_jobs(names=[names[0], "nope"])
        assert [j.name for j in found.jobs] == [names[0]]

    def test_cancel_refuses_a_job_that_is_already_over(self, client: ServerlessClient) -> None:
        """Every serverless job is over once created, so cancel always gets the server's 409."""
        set_name = self._set(client)
        created = client.send_request(
            method="post",
            url="/jobs",
            json_data=JobCreateRequest(set_name=set_name, parameters_name="standard"),
        )
        with pytest.raises(ValueError, match="already over"):
            client.jobs.cancel_job(created["name"])
        assert client.jobs.get_job_status(created["name"]).status == JobStatus.finished


class TestGetResults:
    def _run_standard(self, client: ServerlessClient) -> str:
        set_name = str(client.resources.put_resources("d", "kind: AvatarSchema\n").set_name)
        created = client.send_request(
            method="post",
            url="/jobs",
            json_data=JobCreateRequest(set_name=set_name, parameters_name="standard"),
        )
        return str(created["name"])

    def test_paths_come_back_wrapped_in_access_envelopes(self, client: ServerlessClient) -> None:
        results = client.results.get_results(self._run_standard(client))
        assert all(url.startswith(client.base_url) for urls in results.values() for url in urls)
        assert all("?url=file://" in url for urls in results.values() for url in urls)

    def test_internal_kinds_are_never_exposed(self, client: ServerlessClient) -> None:
        """Holdout halves exist only so dependent jobs can find them by path;
        handing them to the SDK would make _download_all_files try to load them.
        """
        results = client.results.get_results(self._run_standard(client))
        assert "holdout_original" not in results
        assert "shuffled" in results

    def test_a_missing_results_file_carries_both_substrings_runner_matches_on(
        self, client: ServerlessClient
    ) -> None:
        """Runner._populate_results_from_existing_jobs greps the message to decide
        between a warning and a re-raise.
        """
        set_name = str(client.resources.put_resources("d", "kind: AvatarSchema\n").set_name)
        created = client.send_request(
            method="post",
            url="/jobs",
            json_data=JobCreateRequest(set_name=set_name, parameters_name="advice"),
        )
        with pytest.raises(ValueError, match="error status 404") as excinfo:
            client.results.get_results(created["name"])
        assert "results file for job" in str(excinfo.value)

    def test_unknown_job(self, client: ServerlessClient) -> None:
        with pytest.raises(ValueError, match="No job"):
            client.results.get_results("nope")


class TestUnavailableSurface:
    def test_protocol_lookups_see_a_missing_attribute(self, client: ServerlessClient) -> None:
        """copy, pickle and hasattr probe dunders; they must not hit an API refusal."""
        assert not hasattr(client.api_keys, "__iter__")

    @pytest.mark.parametrize(
        "attribute",
        ["api_keys", "event_logs", "capabilities", "openapi", "connections", "documents"],
    )
    def test_server_only_resources_explain_themselves(
        self, client: ServerlessClient, attribute: str
    ) -> None:
        with pytest.raises(NotAvailableOfflineError, match="requires an Avatar server"):
            getattr(client, attribute).anything()

    def test_an_unexpected_raw_request_is_refused_by_name(self, client: ServerlessClient) -> None:
        with pytest.raises(NotAvailableOfflineError, match="GET /whatever"):
            client.send_request(method="get", url="/whatever")


class TestHandshake:
    def test_the_licence_counts_as_the_credential(self, client: ServerlessClient) -> None:
        assert client.is_using_api_key() is True

    def test_get_me_answers_without_a_directory(self, client: ServerlessClient) -> None:
        assert client.users.get_me().email == "serverless@localhost"

    def test_get_me_is_the_licensee_with_the_same_ids_every_session(
        self, workdir, store, executor
    ) -> None:
        def a_session() -> ServerlessClient:
            return ServerlessClient(
                settings=ServerlessConfig(workdir=workdir.root),
                workdir=workdir,
                store=store,
                executor=executor,
                licensee=a_summary(),
            )

        first, second = a_session().users.get_me(), a_session().users.get_me()
        assert first.environment.max_allowed_lines_per_dataset == 100_000
        assert first.environment.license_type == "starter"
        assert first.email == "alice@acme.test"
        assert (first.id, first.organization_id) == (second.id, second.organization_id)

    def test_each_job_records_the_licence_it_ran_under(self, workdir, store, executor) -> None:
        client = ServerlessClient(
            settings=ServerlessConfig(workdir=workdir.root),
            workdir=workdir,
            store=store,
            executor=executor,
            licensee=a_summary(),
        )
        set_name = str(client.resources.put_resources("d", "kind: AvatarSchema\n").set_name)
        created = client.send_request(
            method="post",
            url="/jobs",
            json_data=JobCreateRequest(set_name=set_name, parameters_name="standard"),
        )
        record = store.get_job(created["name"])
        assert record is not None
        assert record.license_jti == "j-1"

    def test_health_says_which_mode_it_is_in(self, client: ServerlessClient) -> None:
        health = client.health.get_health()
        assert health["status"] == "ok"
        assert health["mode"] == "serverless"

    def test_compatibility_defaults_to_compatible_when_the_engine_declares_nothing(
        self, client: ServerlessClient
    ) -> None:
        assert client.compatibility.is_client_compatible().status == "compatible"

    def test_compatibility_reports_what_the_engine_declared(self, workdir, store) -> None:
        """The real point of the handshake offline: catching an SDK that emits
        avatar_yaml documents the installed engine cannot parse.
        """
        declared = CompatibilityResponse(
            message="engine supports >=1.29,<1.31",
            most_recent_compatible_client="1.30.0",
            status=CompatibilityStatus.incompatible,
        )
        client = ServerlessClient(
            settings=ServerlessConfig(workdir=workdir.root),
            workdir=workdir,
            store=store,
            executor=FakeEngineExecutor(),
            compatible=declared,
        )
        assert client.compatibility.is_client_compatible().status == "incompatible"


class TestEndToEndThroughRunner:
    """The whole SDK chain, driven by a real Runner, with no engine installed."""

    def test_add_table_run_and_read_results_back(self, client: ServerlessClient) -> None:
        runner = Runner(api_client=client, display_name="iris_test")
        runner.add_table("iris", data=IRIS)
        runner.set_parameters("iris", k=5, ncp=2)
        runner.run([JobKind.standard, JobKind.privacy_metrics])

        assert runner.get_status(JobKind.standard) == "finished"
        assert runner.get_status(JobKind.privacy_metrics) == "finished"

        shuffled = runner.shuffled("iris")
        assert isinstance(shuffled, pd.DataFrame)
        assert shuffled.shape == IRIS.shape

        privacy = runner.privacy_metrics("iris")
        assert privacy
        assert privacy[0]["hidden_rate"] == 95.0

    def test_the_uploaded_table_lands_in_the_shared_input_volume(
        self, client: ServerlessClient
    ) -> None:
        runner = Runner(api_client=client, display_name="iris_test")
        runner.add_table("iris", data=IRIS)
        runner.set_parameters("iris", k=5, ncp=2)
        runner.run([JobKind.standard])
        assert list(client.workdir.input_dir.iterdir())

    def test_advice_is_found_where_its_document_says_and_applied(
        self, client: ServerlessClient
    ) -> None:
        """Advice documents are named ``advice_parameters`` but write to ``advice``.

        Looking under the document's name instead of its ``results.path`` made every
        ``advise_parameters()`` fail with a 404 against the compiled engine.
        """
        runner = Runner(api_client=client, display_name="iris_test")
        runner.add_table("iris", data=IRIS)
        runner.advise_parameters("iris")

        assert runner.get_status(JobKind.advice) == "finished"
        [job] = client.store.find_jobs(kind=[JobKind.advice])
        assert job.parameters_name == "advice_parameters"
        assert runner.config.avatarization["iris"].k == 20

    def test_results_survive_a_new_client_on_the_same_workdir(
        self, client: ServerlessClient, workdir, executor
    ) -> None:
        """The kernel-restart case, which is the normal one in a notebook."""
        runner = Runner(api_client=client, display_name="iris_test")
        runner.add_table("iris", data=IRIS)
        runner.set_parameters("iris", k=5, ncp=2)
        runner.run([JobKind.standard])

        reopened = ServerlessClient(
            settings=ServerlessConfig(workdir=workdir.root),
            workdir=workdir,
            store=ServerlessStore(workdir.index_path),
            executor=executor,
        )
        found = reopened.jobs.get_jobs(display_name="iris_test")
        assert found.jobs
        assert found.jobs[0].status == JobStatus.finished


class TestLicenseSummary:
    def test_it_reads_like_inspect(self) -> None:
        text = str(a_summary())
        assert "alice@acme.test" in text
        assert "starter" in text
        assert "avatar_parameters, single_table" in text
        assert "100,000 rows per dataset" in text
        assert "Columns      no limit" in text
        assert "2027-03-31 00:00 UTC" in text
        assert "stops on 2028-04-26" in text
        assert "j-1" in text

    def test_the_manager_gives_it_in_serverless_mode(
        self, workdir, store, executor, monkeypatch
    ) -> None:
        client = ServerlessClient(
            settings=ServerlessConfig(workdir=workdir.root),
            workdir=workdir,
            store=store,
            executor=executor,
            licensee=a_summary(),
        )
        monkeypatch.setattr("avatars.manager._build_serverless_client", lambda **_: client)
        assert Manager(serverless=True).license_info() == a_summary()

    def test_a_server_manager_says_where_its_limits_come_from(self) -> None:
        manager = Manager(api_client=FakeApiClient())
        with pytest.raises(ValueError, match="platform account"):
            manager.license_info()

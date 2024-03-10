import logging
import itertools
import time

from avatars.models import JobStatus

from contextlib import contextmanager
from io import BytesIO
from enum import Enum
from json import loads as json_loads
from typing import (
    Any, Dict, Optional, TypeVar, Union, Sequence,
    Mapping, Generator, Type, Callable
)
from pydantic import BaseModel
import httpx
from httpx import ReadTimeout, Response, WriteTimeout
from toolz.dicttoolz import valfilter, valmap
from avatars.models import Login, LoginResponse


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

DEFAULT_RETRY_TIMEOUT = 60
DEFAULT_TIMEOUT = 60

IN_PROGRESS_STATUSES = (
    JobStatus.pending,
    JobStatus.started
)

T = TypeVar('T')
CreateClass = TypeVar('CreateClass', bound=BaseModel)
ResponseClass = TypeVar('ResponseClass', bound=BaseModel)


def _get_nested_value(
    obj: Union[Mapping[Any, Any], Sequence[Any]],
    key: str,
    default: Any = None
) -> Any:
    """
    Return value from (possibly) nested key in JSON dictionary.
    """
    if isinstance(obj, Sequence) and not isinstance(obj, str):
        for item in obj:
            return _get_nested_value(item, key, default=default)

    if isinstance(obj, Mapping):
        if key in obj:
            return obj[key]
        return _get_nested_value(list(obj.values()), key, default=default)

    return default


class Timeout(Exception):
    pass


class BaseClient:
    def __init__(
        self,
        base_url: str,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
        should_verify_ssl: bool = True,
        *,
        verify_auth: bool = True,
        http_client: Optional[httpx.Client] = None,
        headers: Dict[str, str] = {}
    ) -> None:
        """Client to communicate with the Avatar API.

        Parameters
        ----------
        base_url
            url of the API
        timeout:
            timeout in seconds, by default DEFAULT_TIMEOUT
        should_verify_ssl :, optional
            whether to verify SSL certificates on the server. By default True
        http_client :, optional
            allow passing in custom httpx.Client instance, by default None
        verify_auth :, optional
            Bypass client-side authentication verification, by default True
        """
        self.base_url = base_url
        self.timeout = timeout
        self.should_verify_ssl = should_verify_ssl
        self.verify_auth = verify_auth
        self._http_client = http_client
        self._headers = headers

    def set_header(self, key: str, value: str) -> None:
        self._headers[key] = value

    def authenticate(self) -> None:
        kwargs: Dict[str, Any] = {
            "method": "post",
            "url": f"/login",
            "form_data": Login(username="user_integration", password="password_integration"),
            "should_verify_auth": False,
        }

        r = LoginResponse(**self.request(**kwargs))
        self.set_header("Authorization", f"Bearer {r.access_token}")

    @contextmanager
    def client(self) -> Generator[httpx.Client, None, None]:
        cli = self._http_client or httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
            verify=self.should_verify_ssl,
        )

        yield cli

    # privacy_metrics_job = client.jobs.create_privacy_metrics_job(
    #     PrivacyMetricsJobCreate(parameters=privacy_metrics_parameters)
    # )
    # privacy_metrics_job = client.jobs.get_privacy_metrics(
    #     privacy_metrics_job.id, timeout=TIMEOUT
    # )

    def create(
        self,
        *,
        create_url: str,
        create_obj: CreateClass,
        response_cls: Type[ResponseClass],
        timeout: Optional[int] = None,
    ) -> ResponseClass:
        kwargs: Dict[str, Any] = {
            "method": "post",
            "url": create_url,
            "timeout": timeout,
            "json": create_obj,
        }

        res = self.request(**kwargs)

        print(f"### GOT RESULT {res}")

        return res

        job = response_cls(**res)

        kwargs: Dict[str, Any] = {
            "method": "get",
            "url": f"/jobs/{id}/metrics/privacy",
            "timeout": timeout,
        }

        return get_job(
            client=self.client,
            response_cls=PrivacyMetricsJob,
            per_request_timeout=per_request_timeout,
            **kwargs,
        )

        return job

    def request(
        self,
        method: str,
        url: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[BaseModel] = None,
        form_data: Optional[Union[BaseModel, Dict[str, Any]]] = None,
        file: Optional[Sequence["HttpxFile"]] = None,  # type: ignore[name-defined]
        timeout: Optional[int] = None,
        should_verify_auth: bool = True,
        **kwargs: Dict[str, Any],
    ) -> Any:
        """Request the API."""
        should_verify = self.verify_auth and should_verify_auth

        if should_verify and "Authorization" not in self._headers:
            raise Exception("You are not authenticated.")

        # Remove params if they are set to None (allow handling of optionals)
        if isinstance(params, dict):
            params = valfilter(lambda x: x is not None, params)
            params = valmap(lambda x: x.value if isinstance(x, Enum) else x, params)

        json_arg = json_loads(json.model_dump_json()) if json else None
        form_data_arg = (
            form_data.model_dump() if isinstance(form_data, BaseModel) else form_data
        )

        if form_data_arg:
            form_data_arg = valfilter(lambda x: x is not None, form_data_arg)
            form_data_arg = valmap(
                lambda x: x.value if isinstance(x, Enum) else x, form_data_arg
            )

        should_stream = bool(kwargs.get("should_stream", False))  # for download

        with self.client() as client:
            request = client.build_request(
                method=method,
                url=url,
                params=params,
                json=json_arg,
                data=form_data_arg,
                files=file,
                headers=self._headers,
                timeout=timeout or self.timeout,
            )

            try:
                result = client.send(
                    request=request,
                    stream=should_stream,
                )

                if should_stream:
                    return self._handle_streaming_response(result)
                else:
                    return self._handle_standard_response(result)
            except (WriteTimeout, ReadTimeout):
                raise Timeout(
                    "The call timed out."
                    " Consider increasing the timeout with the `timeout` parameter."
                ) from None

    def get_job(
        self,
        response_cls: Callable[..., T],
        *,
        per_request_timeout: Optional[int] = DEFAULT_TIMEOUT,
        timeout: Optional[int] = DEFAULT_TIMEOUT,
        **kwargs: Dict[str, Any],
    ) -> T:
        retry_timeout = timeout or DEFAULT_RETRY_TIMEOUT

        start = time.time()
        current: float = 0

        max_interval = 10
        # Exponential interval, capped at max_interval
        sleep_interval = iter(min(2**i, max_interval) for i in itertools.count())

        # Iterate while we are < retry_timeout
        while current == 0 or (current < retry_timeout):
            timeout = per_request_timeout  # to pass to client.request
            result = self.request(**kwargs, timeout=timeout)  # type: ignore[arg-type]
            response = response_cls(**result)

            self._log_response(response)

            if response.status not in IN_PROGRESS_STATUSES:  # type: ignore[attr-defined]
                return response

            # Sleep, but not longer than timeout
            time_to_sleep = min(next(sleep_interval), retry_timeout - current)
            time.sleep(time_to_sleep)

            current = time.time() - start

        return response

    def _log_response(self, job_response: Any) -> None:
        if not job_response.current_progress:
            return

        message = f"[{job_response.current_progress.created_at.time()}]"
        message += f" Status: {job_response.status}"
        message += f", current_step: {job_response.current_progress.name}"

        logger.info(message)

    def _handle_standard_response(
        self, result: Response
    ) -> Union[Dict[str, Any], bytes, str]:
        if not result.is_success:
            self._raise_on_status(result, result.json())

        print(f"###### GOT RESULT HEADERS {result.headers}")

        if result.headers["content-type"] == "application/json":
            as_json: Dict[str, Any] = result.json()
            return as_json
        elif result.headers["content-type"] in (
            "application/pdf",
            "application/octet-stream",
        ):
            return result.content
        else:
            return result.text

    def _handle_streaming_response(self, result: Response) -> BytesIO:
        if not result.is_success:
            content = result.read()
            encoding = result.encoding or "utf-8"
            as_json: Dict[str, Any] = json_loads(content.decode(encoding))
            self._raise_on_status(result, as_json)

        buffer = BytesIO()

        try:
            for chunk in result.iter_bytes():
                buffer.write(chunk)
        finally:
            result.close()

        return buffer

    def _raise_on_status(self, result: Response, content: Dict[str, Any]) -> None:
        value = content.get("detail")
        if (
            result.status_code == 401
            and isinstance(value, str)
            and "authenticated" in value
        ):
            raise Exception("You are not authenticated.")

        standard_error = _get_nested_value(content, "message")

        if standard_error:
            error_msg = standard_error
        elif validation_error := _get_nested_value(content, "msg"):
            if detailed_message := _get_nested_value(content, "loc"):
                field = detailed_message[-1]
                error_msg = f"{validation_error}: {field}"
            else:
                error_msg = f"Bad Request: {validation_error}"
        else:
            error_msg = "Internal error"

        raise Exception(
            f"Got error in HTTP request: {result.request.method} {result.request.url}."
            f" Error status {result.status_code} - {error_msg}"
        )

    def __str__(self) -> str:
        return ", ".join(
            f"ApiClient(base_url={self.base_url}"
            f"timeout={self.timeout}"
            f"should_verify_ssl={self.should_verify_ssl}"
            "verify_auth={self.verify_auth})"
        )

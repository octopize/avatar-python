import inspect
import io
import os
import struct
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from io import BytesIO
from pathlib import Path
from typing import (
    IO,
    Any,
    AsyncGenerator,
    BinaryIO,
    Callable,
    Generator,
    Iterator,
    Optional,
    Union,
)

import clevercsv
import pandas as pd
import pyarrow as pa
import pyarrow.csv as pcsv
import pyarrow.dataset as ds
import pyarrow.ipc as pi
import pyarrow.parquet as pq
import structlog

ERROR_PRE = "Invalid Arrow stream - "
PARQUET_MARKER = b"PAR1"
ARROW_BEGIN_OF_STREAM_MARKER = b"ARRBOS1"
ARROW_END_OF_STREAM_MARKER = b"ARREOS1"
ARROW_BATCH_MARKER = b"ARRB1"
DEFAULT_MAX_ROWS_PER_BATCH = 1_000_000
APPLICATION_ARROW_STREAM = "application/vnd.apache.arrow.stream"

DEFAULT_MAGIC_BYTES = 2048
SNIFF_SIZE = 1024 * 10


BatchBytesFunction = Callable[[bytes], None]
TableFunction = Callable[[pa.Table], None]

Stream = AsyncGenerator[bytes, None]
FileLike = Union[BinaryIO, IO[Any], io.IOBase]
FileLikes = list[FileLike]
TableSource = Union[str, FileLike]
DataSourceItem = Union[TableSource, pa.Table]
DataSourceItems = Union[DataSourceItem, list[DataSourceItem]]

logger = structlog.get_logger(__name__)


@dataclass
class FileInfo:
    fmt: Optional[str] = None
    error: list[str] = field(default_factory=list)


class StreamState(Enum):
    WAIT_STREAM_BEGIN = "stream-begin"
    AT_STREAM_END = "stream-end"
    WAIT_BATCH = "batch"
    DATA = "data"


def has_method(obj: Any, name: str) -> bool:
    return hasattr(obj, name) and callable(getattr(obj, name))


def is_existing_file_or_dir(item: Any) -> Optional[Path]:
    if isinstance(item, str):
        p = Path(item)

        if p.is_file() or p.is_dir():
            return p

    return None


def is_file_like(obj: Any) -> bool:
    return has_method(obj, "read") and has_method(obj, "write")


def is_text_file(obj: Any) -> bool:
    # Cannot test solely on inheritance because of TemporaryFileWrapper for example
    return is_file_like(obj) and hasattr(obj, "mode") and "b" not in obj.mode


def is_text_buffer(obj: Any) -> bool:
    return isinstance(obj, io.TextIOBase)


def is_text_file_or_buffer(obj: Any) -> bool:
    # Cannot test solely on inheritance because of TemporaryFileWrapper for example
    return is_text_file(obj) or is_text_buffer(obj)


@contextmanager
def save_pos(obj: Any) -> Generator[None, None, None]:
    pos = 0

    if is_file_like(obj):
        pos = obj.tell()

    yield

    if is_file_like(obj):
        obj.seek(pos, os.SEEK_SET)


@contextmanager
def to_start(data: BytesIO, ofs: int = 0) -> Generator[None, None, None]:
    with save_pos(data):
        data.seek(ofs, os.SEEK_SET)
        yield


@contextmanager
def to_end(data: BytesIO) -> Generator[None, None, None]:
    with save_pos(data):
        data.seek(0, os.SEEK_END)
        yield


def available(data: BytesIO) -> int:
    with to_end(data):
        return data.tell()


def try_format(finfo: FileInfo, fmt: str, obj: Any, func: Callable[[Any], Any]) -> None:
    if finfo.fmt:
        return

    with save_pos(obj):
        try:
            func(obj)
            finfo.fmt = fmt
            finfo.error.clear()
        except pa.ArrowInvalid as e:
            finfo.error = [fmt, str(e)]


def guess_file_format(obj: Any) -> FileInfo:
    finfo = FileInfo()

    try_format(finfo, "parquet", obj, lambda obj: pq.ParquetFile(obj))
    try_format(finfo, "csv", obj, lambda obj: pcsv.read_csv(obj))

    if not finfo.fmt:
        finfo.fmt = "unknown"

    return finfo


def flatten(items: Any) -> Iterator[Any]:
    if isinstance(items, list):
        for item in items:
            yield from flatten(item)
    else:
        yield items


class MarkerBase:
    def __init__(self, *, total_size: int) -> None:
        self.total_size = total_size

    def make(self) -> bytes:
        return bytes()

    def can_load(self, data: memoryview) -> bool:
        return len(data) >= self.total_size

    def check_can_load(self, data: memoryview) -> None:
        if not self.can_load(data):
            raise ValueError(
                f"Expected at least {self.total_size} bytes, "
                f"got {len(data)} instead"
            )

    def load(self, data: memoryview) -> memoryview:
        self.check_can_load(data)

        return data

    def try_load(self, data: memoryview) -> bool:
        if self.can_load(data):
            self.load(data)
            return True
        else:
            return False

    def skip_data(self, data: memoryview, size: int) -> memoryview:
        return data[size:]


class Marker(MarkerBase):
    def __init__(self, marker: bytes, *, aux_size: int = 0) -> None:
        self.marker = marker
        self.marker_size = len(self.marker)
        self.aux_size = aux_size
        super().__init__(total_size=self.marker_size + self.aux_size)

    def make(self) -> bytes:
        return super().make() + self.marker

    def identify(self, data: memoryview) -> bool:
        if self.can_load(data):
            return self.check_marker(data, expected=False)

        return False

    def load(self, data: memoryview) -> memoryview:
        # Load "my" parts (marker) and return the rest
        my_data = super().load(data)
        self.check_marker(my_data)

        return self.skip_data(my_data, self.marker_size)

    def check_marker(self, data: memoryview, *, expected: bool = True) -> bool:
        marker = data[0 : self.marker_size]

        if marker != self.marker:
            if expected:
                raise ValueError(
                    f"{ERROR_PRE}"
                    f"Expected '{self.marker!r}', got {bytes(marker)!r} instead"
                )
            else:
                return False

        return True


class MarkerWithSize(Marker):
    size_format = "!I"
    size_packed_size = struct.calcsize(size_format)

    def __init__(self, marker: bytes, size: int = 0) -> None:
        self.size = size
        super().__init__(marker, aux_size=MarkerWithSize.size_packed_size)

    def make(self) -> bytes:
        return super().make() + struct.pack(self.size_format, self.size)

    def load(self, data: memoryview) -> memoryview:
        my_data = super().load(data)
        packed_size = my_data[0 : MarkerWithSize.size_packed_size]

        self.size = struct.unpack(MarkerWithSize.size_format, packed_size)[0]

        return self.skip_data(my_data, MarkerWithSize.size_packed_size)


class ArrowDatasetBuilder:
    def __init__(self) -> None:
        self.inferred_type: Optional[str] = None

    def sniff_csv_data(self, source: TableSource) -> dict[Any, Any]:
        if isinstance(source, (str, Path)):
            with open(source, "rb") as f:
                sample = f.read(SNIFF_SIZE)
        else:
            sample = source.read(SNIFF_SIZE)
            source.seek(0)

        if isinstance(sample, bytes):
            sample = sample.decode(errors="ignore")  # type: ignore[assignment]
        else:
            sample = str(sample)

        try:
            # Python csv module is really struggling on simple cases
            # CleverCSV seems to do a better job
            dialect = clevercsv.Sniffer().sniff(sample)  # type: ignore[arg-type]
        except clevercsv.Error as e:
            raise ValueError(str(e))

        if not dialect:
            raise ValueError("Failed to find CSV format")

        if not dialect.delimiter:
            dialect.delimiter = ","

        return dialect.to_dict()

    def read_table(self, source: TableSource, finfo: FileInfo) -> pa.Table:
        if finfo.fmt == "csv":
            dialect = self.sniff_csv_data(source)
            parse_options = pcsv.ParseOptions(delimiter=dialect["delimiter"])
            return pcsv.read_csv(source, parse_options=parse_options)  # type: ignore[arg-type]
        elif finfo.fmt == "parquet":
            return pq.read_table(source)  # type: ignore[arg-type]

        if finfo.error:
            detail = finfo.error[1]
        else:
            detail = f"Expected known format, got '{finfo.fmt}' instead"

        raise ValueError(f"{ERROR_PRE}{detail}")

    def to_table(self, source: TableSource) -> pa.Table:
        finfo = guess_file_format(source)
        self.inferred_type = finfo.fmt

        logger.info(f"dataset item guessed format is {finfo.fmt}")

        return self.read_table(source, finfo)

    def to_source(self, item: Any) -> Union[str, pa.Table]:
        if p := is_existing_file_or_dir(item):
            if p.is_file():
                return self.to_table(item)
            else:
                return item  # type: ignore[no-any-return]
        elif is_text_file(item):
            # Let pyarrow open the file itself (in binary mode)
            return self.to_table(item.name)
        elif isinstance(item, io.IOBase):
            if is_text_file_or_buffer(item):
                item = io.BytesIO(item.read().encode())

            return self.to_table(item)
        elif isinstance(item, pd.DataFrame):
            return pa.Table.from_pandas(item)  # type: ignore[no-any-return,unused-ignore]
        else:
            raise TypeError(f"Unsupported dataset source {type(item)}")

    def to_dataset(self, items: DataSourceItems) -> tuple[ds.Dataset, Optional[str]]:
        self.inferred_type = None
        sources = [self.to_source(s) for s in flatten(items)]

        return ds.dataset(sources), self.inferred_type  # type: ignore[arg-type]


class ArrowStreamReader:
    def __init__(
        self,
        *,
        batch_bytes_func: Optional[BatchBytesFunction] = None,
        table_func: Optional[TableFunction] = None,
    ) -> None:
        self.batch_bytes_func = batch_bytes_func
        self.table_func = table_func
        self.func_stack: list[Any] = []
        self.batch = bytes()
        self.data = bytearray()
        self.stream_header = MarkerWithSize(ARROW_BEGIN_OF_STREAM_MARKER)
        self.stream_footer = MarkerWithSize(ARROW_END_OF_STREAM_MARKER)
        self.batch_header = MarkerWithSize(ARROW_BATCH_MARKER)
        self.state = StreamState.WAIT_STREAM_BEGIN
        self.nb_batches = 0
        self.total_rows = None

    def __enter__(self) -> Any:
        return self

    def __exit__(self, *args: Any) -> Any:
        pass

    def write_parquet(
        self,
        where: Union[str, IO[bytes]],
        iter_bytes: Iterator[bytes],
    ) -> None:
        writer: Optional[pq.ParquetWriter] = None

        logger.info(f"WP: file is {where}")

        def write_table(table: pa.Table) -> None:
            # In case you wonder: writer is created here on the first run because ParquetWriter
            # needs a table schema, hence a table, which we only have on the first call when
            # the first table is produced (while streaming from server)
            nonlocal writer

            if not writer:
                writer = pq.ParquetWriter(where, table.schema)

            logger.info(f"WP: {where=} {table.num_rows=}")
            writer.write_table(table)

        self.process_bytes(iter_bytes, table_func=write_table)

        if writer:
            writer.close()

        logger.info(f"WP: {where=} closing")

    async def process_stream(
        self,
        stream: Stream,
        *,
        batch_bytes_func: Optional[BatchBytesFunction] = None,
        table_func: Optional[TableFunction] = None,
    ) -> None:
        self.process_begin(batch_bytes_func=batch_bytes_func, table_func=table_func)

        async for chunk in stream:
            self.process_chunk(chunk)

        self.process_end()

    def process_bytes(
        self,
        iter_bytes: Iterator[bytes],
        *,
        batch_bytes_func: Optional[BatchBytesFunction] = None,
        table_func: Optional[TableFunction] = None,
    ) -> None:
        self.process_begin(batch_bytes_func=batch_bytes_func, table_func=table_func)

        for chunk in iter_bytes:
            self.process_chunk(chunk)

        self.process_end()

    def process_begin(
        self,
        *,
        batch_bytes_func: Optional[BatchBytesFunction] = None,
        table_func: Optional[TableFunction] = None,
    ) -> None:
        self.push_funcs()
        self.batch_bytes_func = batch_bytes_func
        self.table_func = table_func

    def process_end(self) -> None:
        self.update_state()
        self.check_stream_started()
        self.flush()
        self.check_at_stream_end()
        self.check_no_remaining_data()
        self.check_nb_batches()
        self.pop_funcs()

    def process_chunk(self, chunk: bytes) -> None:
        if len(chunk) == 0:
            return

        if self.state == StreamState.AT_STREAM_END:
            raise ValueError("Receiving data after stream end")

        self.data.extend(chunk)
        self.update_state()

    def update_state(self) -> None:
        while True:
            prev_state = self.state

            if self.state == StreamState.WAIT_STREAM_BEGIN:
                self.try_load_header(self.stream_header, StreamState.WAIT_BATCH)
                self.total_rows = self.stream_header.size  # type: ignore[assignment]
            elif self.state == StreamState.WAIT_BATCH:
                self.try_load_header(self.batch_header, StreamState.DATA)
            elif self.state == StreamState.DATA:
                self.flush()

            if self.state == prev_state:
                # No progress in this loop, need more data
                break

    def try_load_header(self, header: Marker, new_state: StreamState) -> None:
        data = memoryview(self.data)

        if self.stream_footer.identify(data):
            self.stream_footer.load(data)
            # End of stream
            self.skip_marker_and_set_state(
                self.stream_footer, StreamState.AT_STREAM_END
            )
        elif header.try_load(data):
            self.skip_marker_and_set_state(header, new_state)

    def skip_marker_and_set_state(
        self, marker: MarkerBase, new_state: StreamState
    ) -> None:
        self.skip_data(marker.total_size)
        self.state = new_state

    def flush(self) -> None:
        if not self.is_batch_complete() or self.no_data():
            return

        # Read batch bytes
        self.batch = self.extract_data(self.batch_header.size)
        self.nb_batches += 1

        # Keep remaining data from next batch
        self.skip_data(self.batch_header.size)

        self.call_funcs()

        self.set_wait_batch()

    def is_batch_complete(self) -> Any:
        return len(self.data) >= self.batch_header.size

    def set_wait_batch(self) -> None:
        self.state = StreamState.WAIT_BATCH
        self.batch_header.size = 0

    def push_funcs(self) -> None:
        self.func_stack.append([self.batch_bytes_func, self.table_func])

    def pop_funcs(self) -> None:
        self.batch_bytes_func, self.table_func = self.func_stack.pop()

    def call_funcs(self) -> None:
        if self.batch_bytes_func:
            self.batch_bytes_func(self.batch)

        if self.table_func:
            reader = pi.RecordBatchStreamReader(self.batch)  # type: ignore[call-arg]
            nb_args = len(inspect.signature(self.table_func).parameters)
            if nb_args == 2:
                self.table_func(  # type: ignore[call-arg]
                    reader.read_all(),
                    self.total_rows,
                )
            elif nb_args == 1:
                self.table_func(reader.read_all())
            else:
                raise ValueError(
                    f"Expected 1 or 2 arguments for table_func, got {nb_args}"
                )

    def skip_data(self, size: int) -> None:
        self.data = self.data[size:]

    def extract_data(self, size: int) -> bytes:
        return bytes(self.data[0:size])

    def no_data(self) -> bool:
        return len(self.data) == 0

    def check_no_remaining_data(self) -> None:
        remaining = len(self.data)

        if remaining:
            raise ValueError(f"Expected no remaining data, got {remaining} bytes")

    def check_nb_batches(self) -> None:
        if self.nb_batches != self.stream_footer.size:
            raise ValueError(
                f"Expected {self.stream_footer.size} batches, "
                f"got {self.nb_batches} instead"
            )

    def check_stream_started(self) -> None:
        if self.state == StreamState.WAIT_STREAM_BEGIN:
            raise ValueError(f"Expected a stream, got {bytes(self.data)!r} instead")

    def check_at_stream_end(self) -> None:
        if self.state != StreamState.AT_STREAM_END:
            raise ValueError(
                "Expected to be at stream end, " f"got {self.state.value} instead"
            )


class ArrowStreamWriter:
    def __init__(
        self, ds: ds.Dataset, nb_rows_per_batch: int = DEFAULT_MAX_ROWS_PER_BATCH
    ) -> None:
        self.ds = ds
        self.total_rows = ds.count_rows()
        self.nb_rows_per_batch = nb_rows_per_batch
        self.batch_header = MarkerWithSize(ARROW_BATCH_MARKER)
        self.batch: Optional[bytes] = None
        self.nb_batches = 0
        self.reset_writer()

    def __enter__(self) -> Any:
        return self

    def __exit__(self, *args: Any) -> Any:
        pass

    def iter_core(self) -> Iterator[bytes]:
        yield MarkerWithSize(ARROW_BEGIN_OF_STREAM_MARKER, size=self.total_rows).make()

        for batch in self.ds.to_batches(batch_size=self.nb_rows_per_batch):
            yield from self.process_batch(batch)

        yield from self.flush()

        yield MarkerWithSize(ARROW_END_OF_STREAM_MARKER, self.nb_batches).make()

    async def stream(self) -> Stream:
        for v in self.iter_core():
            yield v

    def __iter__(self) -> Iterator[bytes]:
        yield from self.iter_core()

    def process_batch(self, batch: pa.RecordBatch) -> Iterator[bytes]:
        if self.should_flush(batch):
            yield from self.flush()

        self.writer.write_batch(batch)
        self.row_count += batch.num_rows

    def should_flush(self, batch: pa.RecordBatch) -> Any:
        return self.row_count + batch.num_rows > self.nb_rows_per_batch

    def flush(self) -> Iterator[bytes]:
        self.close_writer()
        self.reset_writer()
        self.nb_batches += 1

        yield from self.get_buffers()

    def get_buffers(self) -> Iterator[bytes]:
        if self.batch:
            self.batch_header.size = len(self.batch)

            yield self.batch_header.make()
            yield self.batch

            self.batch = None

    def close_writer(self) -> None:
        self.writer.close()
        buffer = self.buf.getvalue()
        self.batch = buffer if len(buffer) else None

    def reset_writer(self) -> None:
        self.buf = io.BytesIO()
        self.writer = pi.RecordBatchStreamWriter(self.buf, self.ds.schema)
        self.row_count = 0

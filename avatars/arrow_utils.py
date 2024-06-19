import io
import os
import struct
from contextlib import contextmanager
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

import pandas as pd
import pyarrow as pa
import pyarrow.csv as pcsv
import pyarrow.dataset as ds
import pyarrow.ipc as pi
import pyarrow.parquet as pq

PARQUET_MARKER = b"PAR1"
ARROW_STREAM_MARKER = b"ARRS1"
ARROW_BATCH_MARKER = b"ARRB1"
DEFAULT_MAX_ROWS_PER_BATCH = 1_000_000
APPLICATION_ARROW_STREAM = "application/vnd.apache.arrow.stream"


BatchBytesFunction = Callable[[bytes], None]
TableFunction = Callable[[pa.Table], None]

Stream = AsyncGenerator[bytes, None]
FileLike = Union[BinaryIO, IO[Any], io.IOBase]
FileLikes = list[FileLike]
TableSource = Union[str, FileLike]
DataSourceItem = Union[TableSource, pa.Table]
DataSourceItems = Union[DataSourceItem, list[DataSourceItem]]


class StreamState(Enum):
    WAIT_STREAM = "stream"
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


def flatten(items: Any) -> Iterator[Any]:
    if isinstance(items, list):
        for item in items:
            yield from flatten(item)
    else:
        yield items


@contextmanager
def save_pos(data: BytesIO) -> Generator[None, None, None]:
    pos = data.tell()
    yield
    data.seek(pos, os.SEEK_SET)


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


class HeaderBase:
    def __init__(self, *, total_size: int) -> None:
        self.total_size = total_size

    def make(self) -> bytes:
        return bytes()

    def can_load(self, data: memoryview) -> bool:
        return len(data) >= self.total_size

    def check_can_load(self, data: memoryview) -> None:
        if not self.can_load(data):
            raise RuntimeError(
                f"Expected at least {self.total_size} bytes, "
                f" got {len(data)} insrtead"
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


class Header(HeaderBase):
    def __init__(self, marker: bytes, *, aux_size: int = 0) -> None:
        self.marker = marker
        self.marker_size = len(self.marker)
        self.aux_size = aux_size
        super().__init__(total_size=self.marker_size + self.aux_size)

    def make(self) -> bytes:
        return super().make() + self.marker

    def load(self, data: memoryview) -> memoryview:
        # Load "my" parts (marker) and return the rest
        my_data = super().load(data)
        self.check_marker(my_data)

        return self.skip_data(my_data, self.marker_size)

    def check_marker(self, data: memoryview) -> None:
        marker = data[0 : self.marker_size]

        if marker != self.marker:
            raise ValueError(
                f"Expected '{str(self.marker)}', got {str(marker)} instead"
            )


class HeaderWithSize(Header):
    size_format = "!I"
    size_packed_size = struct.calcsize(size_format)

    def __init__(self, marker: bytes, size: int = 0) -> None:
        self.size = size
        super().__init__(marker, aux_size=HeaderWithSize.size_packed_size)

    def make(self) -> bytes:
        return super().make() + struct.pack(self.size_format, self.size)

    def load(self, data: memoryview) -> memoryview:
        my_data = super().load(data)
        packed_size = my_data[0 : HeaderWithSize.size_packed_size]

        self.size = struct.unpack(HeaderWithSize.size_format, packed_size)[0]

        return self.skip_data(my_data, HeaderWithSize.size_packed_size)


class ArrowDatasetBuilder:
    def __init__(self) -> None:
        self.inferred_type: Optional[str] = None

    def to_table(self, source: TableSource) -> pa.Table:
        try:
            self.inferred_type = "csv"
            return pcsv.read_csv(source)
        except:  # noqa: E722
            self.inferred_type = "parquet"
            return pq.read_table(source)

    def to_source(self, item: Any) -> Union[str, pa.Table]:
        if p := is_existing_file_or_dir(item):
            if p.is_file():
                return self.to_table(item)
            else:
                return item
        elif is_text_file(item):
            # Let pyarrow open the file itself (in binary mode)
            return self.to_table(item.name)
        elif isinstance(item, io.IOBase):
            if is_text_file_or_buffer(item):
                item = io.BytesIO(item.read().encode())

            return self.to_table(item)
        elif isinstance(item, pd.DataFrame):
            return pa.Table.from_pandas(item)
        else:
            raise TypeError(f"Unsupported dataset source {type(item)}")

    def to_dataset(self, items: DataSourceItems) -> tuple[ds.Dataset, Optional[str]]:
        self.inferred_type = None
        sources = [self.to_source(s) for s in flatten(items)]

        return ds.dataset(sources), self.inferred_type


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
        self.stream_header = Header(ARROW_STREAM_MARKER)
        self.batch_header = HeaderWithSize(ARROW_BATCH_MARKER)
        self.state = StreamState.WAIT_STREAM
        self.offset = 0

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

        def write_table(table: pa.Table) -> None:
            # In case you wonder: writer is created here on the first run because ParquetWriter
            # needs a table schema, hence a table, which we only have on the first call when
            # the first table is produced (while streaming from server)
            nonlocal writer

            if not writer:
                writer = pq.ParquetWriter(where, table.schema)

            writer.write_table(table)

        self.process_bytes(iter_bytes, table_func=write_table)

        if writer:
            writer.close()

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
        self.flush()
        self.check_no_remaining_data()
        self.pop_funcs()

    def process_chunk(self, chunk: bytes) -> None:
        self.data.extend(chunk)

        while True:
            prev_state = self.state

            if self.state == StreamState.WAIT_STREAM:
                self.load_header(self.stream_header, StreamState.WAIT_BATCH)
            elif self.state == StreamState.WAIT_BATCH:
                self.load_header(self.batch_header, StreamState.DATA)
            elif self.state == StreamState.DATA:
                self.flush()

            if self.state == prev_state:
                # No progress in this loop, need more data
                break

    def load_header(self, header: HeaderBase, new_state: StreamState) -> None:
        if header.try_load(memoryview(self.data)):
            self.skip_data(header.total_size)
            self.state = new_state

    def flush(self) -> None:
        if not self.is_batch_complete() or self.no_data():
            return

        # Read batch bytes
        self.batch = self.extract_data(self.batch_header.size)

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
            reader = pi.RecordBatchStreamReader(self.batch)
            self.table_func(reader.read_all())

    def skip_data(self, size: int) -> None:
        self.data = self.data[size:]

    def extract_data(self, size: int) -> bytes:
        return bytes(self.data[0:size])

    def no_data(self) -> bool:
        return len(self.data) == 0

    def check_no_remaining_data(self) -> None:
        remaining = len(self.data)

        if remaining:
            raise RuntimeError(f"Expected no remaining data, got {remaining} bytes")


class ArrowStreamWriter:
    def __init__(
        self, ds: ds.Dataset, nb_rows_per_batch: int = DEFAULT_MAX_ROWS_PER_BATCH
    ) -> None:
        self.ds = ds
        self.nb_rows_per_batch = nb_rows_per_batch
        self.batch_header = HeaderWithSize(ARROW_BATCH_MARKER)
        self.batch: Optional[bytes] = None
        self.reset_writer()

    def __enter__(self) -> Any:
        return self

    def __exit__(self, *args: Any) -> Any:
        pass

    def __iter__(self) -> Iterator[bytes]:
        yield Header(ARROW_STREAM_MARKER).make()

        for batch in self.ds.to_batches():
            yield from self.process_batch(batch)

        yield from self.flush()

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
        yield from self.get_buffers()

    def get_buffers(self) -> Iterator[bytes]:
        if self.batch:
            self.batch_header.size = len(self.batch)

            yield self.batch_header.make()
            yield self.batch

            self.batch = None

    def close_writer(self) -> None:
        self.writer.close()
        self.batch = self.buf.getvalue()

    def reset_writer(self) -> None:
        self.buf = io.BytesIO()
        self.writer = pi.RecordBatchStreamWriter(self.buf, self.ds.schema)
        self.row_count = 0

import io
import os
import struct
from pathlib import Path
from typing import (
    IO,
    Any,
    AsyncGenerator,
    BinaryIO,
    Callable,
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
ARROW_BATCH_MARKER = b"ARROW"
MAX_ROWS_PER_BATCH = 1_000_000
APPLICATION_ARROW_STREAM = "application/vnd.apache.arrow.stream"


BatchBytesFunction = Callable[[bytes], None]
TableFunction = Callable[[pa.Table], None]

Stream = AsyncGenerator[bytes, None]
FileLike = Union[BinaryIO, IO[Any], io.IOBase]
FileLikes = list[FileLike]
TableSource = Union[str, FileLike]
DataSourceItem = Union[TableSource, pa.Table]
DataSourceItems = Union[DataSourceItem, list[DataSourceItem]]


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
        self.data = io.BytesIO()
        self.batch_size_format = "!I"
        self.batch_size_packed_size = struct.calcsize(self.batch_size_format)
        self.min_size = len(ARROW_BATCH_MARKER) + self.batch_size_packed_size
        self.batch_size = 0

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
        self.push_funcs()

        self.batch_bytes_func = batch_bytes_func
        self.table_func = table_func

        async for chunk in stream:
            self.process_chunk(chunk)

        self.flush()

        self.pop_funcs()

    def process_bytes(
        self,
        iter_bytes: Iterator[bytes],
        *,
        batch_bytes_func: Optional[BatchBytesFunction] = None,
        table_func: Optional[TableFunction] = None,
    ) -> None:
        self.push_funcs()

        self.batch_bytes_func = batch_bytes_func
        self.table_func = table_func

        for chunk in iter_bytes:
            self.process_chunk(chunk)

        self.flush()

        self.pop_funcs()

    def process_chunk(self, chunk: bytes) -> bool:
        batch_is_ready: bool = False
        avail = self.append(chunk)

        if self.batch_size == 0 and avail >= self.min_size:
            # We are looking for a new batch
            self.check_marker()
            self.read_batch_size()
        else:
            # Try to flush
            batch_is_ready = self.flush()

        return batch_is_ready

    def flush(self) -> bool:
        avail = self.available()

        if self.batch_size == 0 or avail < self.batch_size + self.min_size:
            # Not enough data yet
            return False

        # Read batch bytes (skipping marker and size)
        self.data.seek(self.min_size, os.SEEK_SET)
        self.batch = self.data.read(self.batch_size)

        if len(self.batch) != self.batch_size:
            raise ValueError(
                f"Expected a batch of {self.batch_size}, got {len(self.batch)} instead"
            )

        # Reset with remaining data
        remaining_size = avail - self.min_size - self.batch_size
        remaining = self.data.read(remaining_size)

        if len(remaining) != remaining_size:
            raise ValueError(
                f"Expected remaining size {remaining_size}"
                f", got {len(remaining)} instead"
            )

        self.data = io.BytesIO(remaining)
        self.batch_size = 0

        self.call_funcs()

        return True

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

    def check_marker(self) -> None:
        self.data.seek(0, os.SEEK_SET)
        marker = self.data.read(len(ARROW_BATCH_MARKER))

        if len(marker) != len(ARROW_BATCH_MARKER) or marker != ARROW_BATCH_MARKER:
            raise ValueError(
                f"Expected '{str(ARROW_BATCH_MARKER)}', got {str(marker)} instead"
            )

    def read_batch_size(self) -> None:
        packed_size = self.data.read(self.batch_size_packed_size)
        self.batch_size = struct.unpack(self.batch_size_format, packed_size)[0]

    def append(self, chunk: bytes) -> int:
        self.data.seek(0, os.SEEK_END)
        self.data.write(chunk)
        return self.data.tell()

    def available(self) -> int:
        self.data.seek(0, os.SEEK_END)
        return self.data.tell()


class ArrowStreamWriter:
    def __init__(self, ds: ds.Dataset) -> None:
        self.ds = ds
        self.header = bytearray(ARROW_BATCH_MARKER)
        self.header += struct.pack("!I", 0)
        self.batch = bytes()
        self.reset_writer()

    def __enter__(self) -> Any:
        return self

    def __exit__(self, *args: Any) -> Any:
        pass

    def __iter__(self) -> Iterator[bytes]:
        for batch in self.ds.to_batches():
            if self.process_batch(batch):
                yield bytes(self.header)
                yield self.batch

        if self.flush():
            yield bytes(self.header)
            yield self.batch

    def process_batch(self, batch: pa.RecordBatch) -> bool:
        batch_is_ready = False

        if self.row_count + batch.num_rows > MAX_ROWS_PER_BATCH:
            batch_is_ready = self.flush()

        self.writer.write_batch(batch)
        self.row_count += batch.num_rows

        return batch_is_ready

    def flush(self) -> bool:
        if self.row_count:
            self.close_writer()
            self.reset_writer()
            self.make_header()

            return True

        return False

    def make_header(self) -> None:
        struct.pack_into(
            "!I",
            self.header,
            len(ARROW_BATCH_MARKER),
            len(self.batch),
        )

    def close_writer(self) -> None:
        self.writer.close()
        self.batch = self.buf.getvalue()

    def reset_writer(self) -> None:
        self.buf = io.BytesIO()
        self.writer = pi.RecordBatchStreamWriter(self.buf, self.ds.schema)
        self.row_count = 0

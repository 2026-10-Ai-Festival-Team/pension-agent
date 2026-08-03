from dataclasses import dataclass


@dataclass(frozen=True)
class ChunkingConfig:
    target_chars: int = 1000
    max_chars: int = 1500
    min_chars: int = 100
    table_rows_per_chunk: int = 20
    refined_table_rows_per_chunk: int = 2
    refined_table_min_chars: int = 250
    refined_table_max_data_rows: int = 8
    spreadsheet_rows_per_chunk: int = 20
    spreadsheet_header_rows: int = 1

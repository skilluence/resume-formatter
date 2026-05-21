from formatters.compact_ats import format_compact


def format_readable(data: dict, output_path: str):
    format_compact(data, output_path)

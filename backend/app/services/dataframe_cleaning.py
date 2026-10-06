import pandas as pd


def replace_placeholders(series: pd.Series, placeholders: list[str], replacement, strip_whitespace: bool = False) -> pd.Series:
    if not strip_whitespace:
        return series.replace(placeholders, replacement)
    # Compare trimmed strings while preserving every unmatched original value.
    mask = series.notna() & series.astype(str).str.strip().isin(placeholders)
    return series.mask(mask, replacement)

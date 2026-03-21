import io
import logging
from typing import Any

import pandas as pd
from fastapi import UploadFile

logger = logging.getLogger(__name__)

COLUMN_MAPPING = {
    "名字": "name",
    "姓名": "name",
    "name": "name",
    "公司": "company",
    "公司名": "company",
    "company": "company",
    "company_name": "company",
    "电话": "phone",
    "手机": "phone",
    "phone": "phone",
    "telephone": "phone",
    "mobile": "phone",
    "邮箱": "email",
    "email": "email",
    "e-mail": "email",
    "语言": "language",
    "language": "language",
    "国家": "country",
    "country": "country",
    "行业": "industry",
    "industry": "industry",
    "职位": "title",
    "title": "title",
    "job_title": "title",
}


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Map Chinese/English column names to standard field names."""
    rename_map = {}
    for col in df.columns:
        col_lower = col.strip().lower()
        if col_lower in COLUMN_MAPPING:
            rename_map[col] = COLUMN_MAPPING[col_lower]
    if rename_map:
        df = df.rename(columns=rename_map)
    return df


def parse_file(file: UploadFile) -> list[dict[str, Any]]:
    """Parse CSV or Excel file and return list of lead dicts."""
    content = file.file.read()
    filename = file.filename or ""

    try:
        if filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(content))
        else:
            for encoding in ["utf-8", "gbk", "gb2312", "latin1"]:
                try:
                    df = pd.read_csv(io.BytesIO(content), encoding=encoding)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                df = pd.read_csv(io.BytesIO(content), encoding="utf-8", errors="replace")

        df = _normalize_columns(df)
        df = df.fillna("")
        df = df.astype(str)

        rows = df.to_dict(orient="records")
        # Ensure required 'name' field
        for row in rows:
            if not row.get("name"):
                row["name"] = row.get("company", "") or row.get("email", "") or "Unknown"
            # Clean phone numbers
            phone = row.get("phone", "")
            if phone:
                row["phone"] = phone.strip().replace(" ", "").replace("nan", "")

        return rows

    except Exception as e:
        logger.error(f"File parse error: {e}")
        raise ValueError(f"Failed to parse file: {str(e)}")

"""
Multi-source lead import adapters.

Each adapter normalizes external data into a standard lead dict format:
{
    "name": str,
    "company": str,
    "phone": str,
    "email": str,
    "industry": str,
    "country": str,
    "language": str,
    "source": str,           # LeadSource enum value
    "source_url": str,
    "source_detail": dict,   # adapter-specific metadata
    "profile_data": dict,    # raw profile info
}
"""

import io
import logging
from abc import ABC, abstractmethod
from typing import Any

import pandas as pd
from fastapi import UploadFile

logger = logging.getLogger(__name__)

# Shared column mapping for CSV/Excel files
COLUMN_MAPPING = {
    "名字": "name", "姓名": "name", "name": "name",
    "公司": "company", "公司名": "company", "company": "company", "company_name": "company",
    "电话": "phone", "手机": "phone", "phone": "phone", "telephone": "phone", "mobile": "phone",
    "邮箱": "email", "email": "email", "e-mail": "email",
    "语言": "language", "language": "language",
    "国家": "country", "country": "country", "地区": "country", "region": "country",
    "行业": "industry", "industry": "industry", "sector": "industry",
    "职位": "title", "title": "title", "job_title": "title",
    "网址": "website", "website": "website", "url": "website",
    "linkedin": "linkedin_url", "linkedin_url": "linkedin_url",
}


class LeadSourceAdapter(ABC):
    """Base class for all lead source adapters."""

    source_name: str = ""

    @abstractmethod
    def parse(self, **kwargs) -> list[dict[str, Any]]:
        """Parse input and return normalized lead dicts."""
        ...

    def _clean_phone(self, phone: str) -> str:
        if not phone or phone == "nan":
            return ""
        return phone.strip().replace(" ", "").replace("nan", "")

    def _ensure_name(self, row: dict) -> str:
        return row.get("name") or row.get("company") or row.get("email") or "Unknown"


class CSVAdapter(LeadSourceAdapter):
    """Import from CSV/Excel files."""

    source_name = "csv"

    def parse(self, *, file: UploadFile, **kwargs) -> list[dict[str, Any]]:
        content = file.file.read()
        filename = file.filename or ""

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

        df = self._normalize_columns(df).fillna("").astype(str)
        rows = df.to_dict(orient="records")

        results = []
        for row in rows:
            row["name"] = self._ensure_name(row)
            row["phone"] = self._clean_phone(row.get("phone", ""))
            row["source"] = self.source_name
            row["source_detail"] = {"filename": filename}
            row["profile_data"] = {k: v for k, v in row.items() if k not in (
                "name", "company", "phone", "email", "source", "source_detail"
            )}
            results.append(row)
        return results

    @staticmethod
    def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
        rename_map = {}
        for col in df.columns:
            col_lower = col.strip().lower()
            if col_lower in COLUMN_MAPPING:
                rename_map[col] = COLUMN_MAPPING[col_lower]
        return df.rename(columns=rename_map) if rename_map else df


class LinkedInAdapter(LeadSourceAdapter):
    """Import from LinkedIn Sales Navigator export (CSV)."""

    source_name = "linkedin"

    def parse(self, *, file: UploadFile, **kwargs) -> list[dict[str, Any]]:
        csv_adapter = CSVAdapter()
        rows = csv_adapter.parse(file=file)

        for row in rows:
            row["source"] = "linkedin"
            # LinkedIn exports often have "First Name" + "Last Name"
            first = row.get("profile_data", {}).get("first_name", "")
            last = row.get("profile_data", {}).get("last_name", "")
            if first and last:
                row["name"] = f"{first} {last}"
            linkedin_url = row.get("profile_data", {}).get("linkedin_url", "")
            if linkedin_url:
                row["source_url"] = linkedin_url
            row["source_detail"] = {
                "platform": "linkedin",
                "filename": file.filename or "",
            }
        return rows


class AlibabaAdapter(LeadSourceAdapter):
    """Import from Alibaba International Station export."""

    source_name = "alibaba"

    # Alibaba-specific column mappings
    ALI_COLUMNS = {
        "buyer_name": "name", "contact_person": "name",
        "company_name": "company", "buyer_company": "company",
        "contact_email": "email", "buyer_email": "email",
        "contact_phone": "phone", "buyer_phone": "phone",
        "buyer_country": "country", "destination_country": "country",
        "product_name": "industry", "product_category": "industry",
    }

    def parse(self, *, file: UploadFile, **kwargs) -> list[dict[str, Any]]:
        csv_adapter = CSVAdapter()
        rows = csv_adapter.parse(file=file)

        for row in rows:
            # Apply Alibaba-specific mappings from profile_data
            pd_data = row.get("profile_data", {})
            for ali_key, std_key in self.ALI_COLUMNS.items():
                if ali_key in pd_data and not row.get(std_key):
                    row[std_key] = pd_data[ali_key]

            row["source"] = "alibaba"
            row["source_detail"] = {
                "platform": "alibaba",
                "filename": file.filename or "",
            }
        return rows


class TradeShowAdapter(LeadSourceAdapter):
    """Import from trade show / exhibition attendee lists."""

    source_name = "trade_show"

    def parse(self, *, file: UploadFile, show_name: str = "", **kwargs) -> list[dict[str, Any]]:
        csv_adapter = CSVAdapter()
        rows = csv_adapter.parse(file=file)

        for row in rows:
            row["source"] = "trade_show"
            row["source_detail"] = {
                "platform": "trade_show",
                "show_name": show_name,
                "filename": file.filename or "",
            }
        return rows


class ManualAdapter(LeadSourceAdapter):
    """Single lead manual entry."""

    source_name = "manual"

    def parse(self, *, lead_data: dict[str, Any], **kwargs) -> list[dict[str, Any]]:
        lead_data["source"] = "manual"
        lead_data["source_detail"] = {"platform": "manual"}
        lead_data["name"] = self._ensure_name(lead_data)
        lead_data["phone"] = self._clean_phone(lead_data.get("phone", ""))
        return [lead_data]


# Registry
ADAPTERS: dict[str, type[LeadSourceAdapter]] = {
    "csv": CSVAdapter,
    "linkedin": LinkedInAdapter,
    "alibaba": AlibabaAdapter,
    "trade_show": TradeShowAdapter,
    "manual": ManualAdapter,
}


def get_adapter(source: str) -> LeadSourceAdapter:
    """Get adapter instance by source name."""
    adapter_cls = ADAPTERS.get(source)
    if not adapter_cls:
        raise ValueError(f"Unknown source: {source}. Available: {list(ADAPTERS.keys())}")
    return adapter_cls()


def list_sources() -> list[dict[str, str]]:
    """Return available data sources with metadata."""
    return [
        {"id": "csv", "name": "CSV / Excel", "description": "Upload CSV or Excel file"},
        {"id": "linkedin", "name": "LinkedIn", "description": "LinkedIn Sales Navigator export"},
        {"id": "alibaba", "name": "Alibaba International", "description": "Alibaba buyer inquiry export"},
        {"id": "trade_show", "name": "Trade Show", "description": "Exhibition attendee list"},
        {"id": "manual", "name": "Manual Entry", "description": "Add lead manually"},
    ]

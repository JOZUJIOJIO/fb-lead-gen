from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Lead, LeadStatus, User
from app.routers.auth import get_current_user
from app.schemas import (
    BatchIds,
    DataSourceInfo,
    ImportResult,
    LeadCreate,
    LeadListResponse,
    LeadResponse,
    LeadUpdate,
)
from app.services.ai_engine import analyze_lead, generate_message
from app.services.csv_import import parse_file
from app.services.data_sources import get_adapter, list_sources

router = APIRouter()


@router.get("", response_model=LeadListResponse)
def list_leads(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    min_score: float | None = None,
    search: str | None = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Lead).filter(Lead.user_id == current_user.id)
    if status:
        query = query.filter(Lead.status == status)
    if min_score is not None:
        query = query.filter(Lead.score >= min_score)
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            (Lead.name.ilike(pattern))
            | (Lead.company.ilike(pattern))
            | (Lead.email.ilike(pattern))
        )

    total = query.count()

    if sort_order == "desc":
        query = query.order_by(getattr(Lead, sort_by).desc())
    else:
        query = query.order_by(getattr(Lead, sort_by).asc())

    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return LeadListResponse(items=items, total=total, page=page, page_size=page_size)


@router.post("", response_model=LeadResponse)
def create_lead(
    data: LeadCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lead = Lead(**data.model_dump(), user_id=current_user.id)
    db.add(lead)
    db.commit()
    db.refresh(lead)
    return lead


@router.post("/import", response_model=ImportResult)
def import_leads(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not file.filename.endswith((".csv", ".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Only CSV and Excel files are supported")

    rows = parse_file(file)
    imported = 0
    duplicates = 0
    errors = 0

    existing_phones = set()
    if rows:
        phones = [r.get("phone", "") for r in rows if r.get("phone")]
        if phones:
            existing = (
                db.query(Lead.phone)
                .filter(Lead.user_id == current_user.id, Lead.phone.in_(phones))
                .all()
            )
            existing_phones = {e[0] for e in existing}

    for row in rows:
        try:
            phone = row.get("phone", "")
            if phone and phone in existing_phones:
                duplicates += 1
                continue
            lead = Lead(
                name=row.get("name", "Unknown"),
                company=row.get("company", ""),
                phone=phone,
                email=row.get("email", ""),
                source="csv",
                profile_data=row,
                language=row.get("language", "en"),
                user_id=current_user.id,
            )
            db.add(lead)
            if phone:
                existing_phones.add(phone)
            imported += 1
        except Exception:
            errors += 1

    db.commit()
    return ImportResult(total=len(rows), imported=imported, duplicates=duplicates, errors=errors)


@router.get("/sources", response_model=list[DataSourceInfo])
def get_data_sources():
    """List available lead data sources."""
    return list_sources()


@router.post("/import/{source}", response_model=ImportResult)
def import_from_source(
    source: str,
    file: UploadFile = File(...),
    show_name: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import leads from a specific data source (linkedin, alibaba, trade_show, csv)."""
    try:
        adapter = get_adapter(source)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    kwargs = {"file": file}
    if show_name:
        kwargs["show_name"] = show_name

    rows = adapter.parse(**kwargs)
    imported = 0
    duplicates = 0
    errors = 0

    existing_phones = set()
    phones = [r.get("phone", "") for r in rows if r.get("phone")]
    if phones:
        existing = (
            db.query(Lead.phone)
            .filter(Lead.user_id == current_user.id, Lead.phone.in_(phones))
            .all()
        )
        existing_phones = {e[0] for e in existing}

    for row in rows:
        try:
            phone = row.get("phone", "")
            if phone and phone in existing_phones:
                duplicates += 1
                continue
            lead = Lead(
                name=row.get("name", "Unknown"),
                company=row.get("company", ""),
                phone=phone,
                email=row.get("email", ""),
                source=row.get("source", source),
                source_url=row.get("source_url", ""),
                source_detail=row.get("source_detail", {}),
                industry=row.get("industry", ""),
                country=row.get("country", ""),
                profile_data=row.get("profile_data", {}),
                language=row.get("language", "en"),
                user_id=current_user.id,
            )
            db.add(lead)
            if phone:
                existing_phones.add(phone)
            imported += 1
        except Exception:
            errors += 1

    db.commit()
    return ImportResult(
        total=len(rows), imported=imported, duplicates=duplicates, errors=errors, source=source
    )


@router.get("/{lead_id}", response_model=LeadResponse)
def get_lead(
    lead_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.user_id == current_user.id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


@router.put("/{lead_id}", response_model=LeadResponse)
def update_lead(
    lead_id: int,
    data: LeadUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.user_id == current_user.id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(lead, key, value)
    db.commit()
    db.refresh(lead)
    return lead


@router.delete("/{lead_id}")
def delete_lead(
    lead_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.user_id == current_user.id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    db.delete(lead)
    db.commit()
    return {"detail": "Lead deleted"}


@router.post("/{lead_id}/analyze", response_model=LeadResponse)
def analyze_single_lead(
    lead_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.user_id == current_user.id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    result = analyze_lead(
        name=lead.name,
        company=lead.company,
        profile_data=lead.profile_data,
        email=lead.email,
    )
    lead.score = result["score"]
    lead.ai_analysis = result["analysis"]
    lead.language = result.get("language", lead.language)
    lead.status = LeadStatus.analyzed
    db.commit()
    db.refresh(lead)
    return lead


@router.post("/batch-analyze")
def batch_analyze(
    data: BatchIds,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    leads = (
        db.query(Lead)
        .filter(Lead.id.in_(data.ids), Lead.user_id == current_user.id)
        .all()
    )
    analyzed = 0
    for lead in leads:
        try:
            result = analyze_lead(
                name=lead.name,
                company=lead.company,
                profile_data=lead.profile_data,
                email=lead.email,
            )
            lead.score = result["score"]
            lead.ai_analysis = result["analysis"]
            lead.language = result.get("language", lead.language)
            lead.status = LeadStatus.analyzed
            analyzed += 1
        except Exception:
            continue
    db.commit()
    return {"analyzed": analyzed, "total": len(data.ids)}

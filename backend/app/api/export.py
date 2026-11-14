"""Audit trail export — PDF and Excel."""
import csv
import io
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.reconciliation import AuditLog, Reconciliation

router = APIRouter(prefix="/api/export", tags=["export"])

ACTION_LABELS = {
    "match_created":             "Match created",
    "exception_raised":          "Exception raised",
    "entry_approved":            "Entry approved",
    "entry_rejected":            "Entry rejected",
    "entry_edited":              "Entry edited",
    "reconciliation_started":    "Reconciliation started",
    "reconciliation_completed":  "Reconciliation completed",
    "user_logged_in":            "User logged in",
}


@router.get("/audit/csv")
async def export_audit_csv(
    reconciliation_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download the audit trail as a CSV file."""
    q = select(AuditLog).order_by(AuditLog.id)
    if reconciliation_id:
        q = q.where(AuditLog.reconciliation_id == reconciliation_id)
    result = await db.execute(q)
    logs = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Timestamp (UTC)", "Action", "Entity Type", "Entity ID",
        "User ID", "Reconciliation ID", "Details", "Entry Hash", "Previous Hash",
    ])
    for log in logs:
        writer.writerow([
            log.id,
            log.created_at.strftime("%Y-%m-%d %H:%M:%S") if log.created_at else "",
            ACTION_LABELS.get(log.action.value if hasattr(log.action, "value") else log.action, str(log.action)),
            log.entity_type,
            log.entity_id or "",
            log.user_id or "AI agent",
            log.reconciliation_id or "",
            str(log.details or ""),
            log.entry_hash,
            log.previous_hash or "genesis",
        ])

    output.seek(0)
    filename = f"primeledger_audit_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),  # BOM for Excel compatibility
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/audit/excel")
async def export_audit_excel(
    reconciliation_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Download the audit trail as an Excel (.xlsx) file.
    Uses openpyxl if available, falls back to CSV with .xlsx extension.
    """
    q = select(AuditLog).order_by(AuditLog.id)
    if reconciliation_id:
        q = q.where(AuditLog.reconciliation_id == reconciliation_id)
    result = await db.execute(q)
    logs = result.scalars().all()

    filename = f"primeledger_audit_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"

    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Audit Trail"

        # Header style
        header_fill = PatternFill(start_color="1F3864", end_color="1F3864", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True, size=11)
        headers = [
            "ID", "Timestamp (UTC)", "Action", "Entity Type", "Entity ID",
            "User", "Reconciliation ID", "Details", "Entry Hash", "Previous Hash",
        ]
        for col_idx, h in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_idx, value=h)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center")

        # Column widths
        col_widths = [6, 20, 22, 14, 10, 12, 18, 40, 20, 20]
        for i, w in enumerate(col_widths, 1):
            ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w

        # Data rows
        for row_idx, log in enumerate(logs, 2):
            action_label = ACTION_LABELS.get(
                log.action.value if hasattr(log.action, "value") else log.action,
                str(log.action)
            )
            row_data = [
                log.id,
                log.created_at.strftime("%Y-%m-%d %H:%M:%S") if log.created_at else "",
                action_label,
                log.entity_type,
                log.entity_id,
                log.user_id if log.user_id else "AI agent",
                log.reconciliation_id,
                str(log.details or ""),
                log.entry_hash,
                log.previous_hash or "genesis",
            ]
            for col_idx, val in enumerate(row_data, 1):
                ws.cell(row=row_idx, column=col_idx, value=val)

        # Freeze header row
        ws.freeze_panes = "A2"

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except ImportError:
        # openpyxl not installed — return CSV with xlsx extension
        return await export_audit_csv(reconciliation_id, db, current_user)


@router.get("/reconciliation/csv")
async def export_reconciliation_csv(
    reconciliation_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download all transactions for a reconciliation as CSV."""
    from app.models.reconciliation import BankTransaction

    q = (
        select(BankTransaction)
        .where(BankTransaction.reconciliation_id == reconciliation_id)
        .order_by(BankTransaction.transaction_date)
    )
    result = await db.execute(q)
    txns = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Date", "Description", "Amount", "Reference",
        "Match Status", "Confidence", "Match Method",
    ])
    for t in txns:
        writer.writerow([
            t.transaction_date,
            t.description,
            t.amount,
            t.reference or "",
            t.match_status.value if hasattr(t.match_status, "value") else t.match_status,
            t.confidence_score or "",
            t.match_method or "",
        ])

    output.seek(0)
    filename = f"primeledger_transactions_{reconciliation_id}_{datetime.utcnow().strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

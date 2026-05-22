"""
Evidence Lifecycle Manager
==========================
Runs daily (or manually). For each suspect marked as CAUGHT for 30+ days:
  1. Generates a comprehensive PDF report (suspect info + evidence photos)
  2. Saves the PDF to data/archives/
  3. Removes the suspect from the database (stops live scanning)
  4. Cleans up evidence images from disk

Usage:
  python evidence_cleanup.py              # Process all eligible suspects
  python evidence_cleanup.py --dry-run    # Preview without making changes
  python evidence_cleanup.py --days 1     # Override 30-day threshold (for testing)
"""

import os
import sys
import argparse
import json
import glob
import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from app.database.connection import SessionLocal, engine
from app.database.models import Person, FaceEmbedding, EventLog

from fpdf import FPDF

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("EvidenceCleanup")

ARCHIVE_DIR = os.path.join(os.getcwd(), "data", "archives")
EVIDENCE_DIR = os.path.join(os.getcwd(), "data", "evidence")


class SuspectReportPDF(FPDF):
    """Custom PDF class for suspect archival reports."""

    def header(self):
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 10, "AI SURVEILLANCE ENGINE - SUSPECT ARCHIVE REPORT", ln=True, align="C")
        self.set_font("Helvetica", "", 9)
        self.cell(0, 6, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True, align="C")
        self.line(10, self.get_y() + 2, 200, self.get_y() + 2)
        self.ln(6)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}} | CONFIDENTIAL", align="C")


def generate_pdf_report(person: Person, events: list, db: Session) -> str:
    """Generate a comprehensive PDF report for a caught suspect."""
    os.makedirs(ARCHIVE_DIR, exist_ok=True)

    safe_name = "".join([c if c.isalnum() else "_" for c in person.name])
    filename = f"{person.suspect_code}_{safe_name}_{datetime.now().strftime('%Y%m%d')}.pdf"
    filepath = os.path.join(ARCHIVE_DIR, filename)

    pdf = SuspectReportPDF()
    pdf.alias_nb_pages()
    pdf.add_page()

    # --- Section 1: Suspect Profile ---
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "SUSPECT PROFILE", ln=True)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(3)

    pdf.set_font("Helvetica", "", 10)
    profile_data = [
        ("Suspect Code", person.suspect_code or "N/A"),
        ("Full Name", person.name),
        ("Aliases", person.aliases or "None"),
        ("Category", person.category or "suspect"),
        ("UUID", person.uuid or "N/A"),
        ("Enrolled On", str(person.created_at)),
        ("Caught On", str(person.caught_at)),
        ("Days in System", str((person.caught_at - person.created_at).days) if person.caught_at and person.created_at else "N/A"),
    ]

    # Parse metadata
    if person.metadata_json:
        try:
            meta = json.loads(person.metadata_json)
            for k, v in meta.items():
                profile_data.append((k.title(), str(v)))
        except Exception:
            pass

    for label, value in profile_data:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(50, 7, f"{label}:", align="L")
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 7, value, ln=True)

    pdf.ln(5)

    # --- Section 2: Suspect Photo (from images/ folder if exists) ---
    suspect_photo = None
    images_dir = os.path.join(os.getcwd(), "images")
    if os.path.exists(images_dir):
        for ext in ["jpg", "jpeg", "png"]:
            matches = glob.glob(os.path.join(images_dir, f"*{safe_name}*.{ext}"))
            if matches:
                suspect_photo = matches[0]
                break

    if suspect_photo and os.path.exists(suspect_photo):
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "ENROLLMENT PHOTO", ln=True)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(3)
        try:
            pdf.image(suspect_photo, x=10, w=60)
            pdf.ln(5)
        except Exception:
            pdf.cell(0, 7, "[Photo could not be embedded]", ln=True)

    # --- Section 3: Evidence Timeline ---
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, f"EVIDENCE TIMELINE ({len(events)} sightings)", ln=True)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(3)

    if not events:
        pdf.set_font("Helvetica", "I", 10)
        pdf.cell(0, 7, "No evidence events recorded.", ln=True)
    else:
        # Table header
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(10, 7, "#", border=1, align="C")
        pdf.cell(45, 7, "Date/Time", border=1, align="C")
        pdf.cell(30, 7, "Camera", border=1, align="C")
        pdf.cell(25, 7, "Confidence", border=1, align="C")
        pdf.cell(80, 7, "Evidence File", border=1, align="C")
        pdf.ln()

        pdf.set_font("Helvetica", "", 8)
        for i, event in enumerate(events, 1):
            pdf.cell(10, 6, str(i), border=1, align="C")
            pdf.cell(45, 6, str(event.timestamp)[:19] if event.timestamp else "N/A", border=1)
            pdf.cell(30, 6, str(event.camera_id) if event.camera_id else "N/A", border=1)
            pdf.cell(25, 6, f"{event.confidence:.2f}" if event.confidence else "N/A", border=1, align="C")
            img_path = event.image_path if event.image_path else "N/A"
            pdf.cell(80, 6, os.path.basename(img_path), border=1)
            pdf.ln()

            # If evidence image exists, embed it (max 4 per page to save space)
            if event.image_path and os.path.exists(event.image_path) and i <= 20:
                try:
                    pdf.image(event.image_path, x=15, w=40)
                    pdf.ln(2)
                except Exception:
                    pass

    # --- Section 4: Summary ---
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "CASE SUMMARY", ln=True)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(3)

    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 7, (
        f"Suspect '{person.name}' (Code: {person.suspect_code}) was enrolled on "
        f"{str(person.created_at)[:10]} and marked as CAUGHT on {str(person.caught_at)[:10]}. "
        f"A total of {len(events)} evidence sightings were recorded across the surveillance network. "
        f"This report was auto-generated by the AI Surveillance Engine's Evidence Lifecycle Manager "
        f"after the mandatory 30-day retention period. All related data has been purged from the "
        f"active database to optimize system performance."
    ))

    pdf.ln(10)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 7, "--- END OF REPORT ---", ln=True, align="C")

    pdf.output(filepath)
    return filepath


def cleanup_caught_suspects(days_threshold: int = 30, dry_run: bool = False):
    """Find caught suspects older than threshold and archive them."""
    db: Session = SessionLocal()
    cutoff_date = datetime.now() - timedelta(days=days_threshold)

    logger.info("=" * 60)
    logger.info("  AI SURVEILLANCE ENGINE - EVIDENCE LIFECYCLE MANAGER")
    logger.info("=" * 60)
    logger.info(f"  Threshold  : {days_threshold} days")
    logger.info(f"  Cutoff Date: {cutoff_date.strftime('%Y-%m-%d')}")
    logger.info(f"  Mode       : {'DRY RUN (no changes)' if dry_run else 'LIVE (will delete)'}")
    logger.info("=" * 60)

    try:
        # Find all suspects who were caught before the cutoff date
        eligible = db.query(Person).filter(
            Person.is_caught == True,
            Person.caught_at != None,
            Person.caught_at <= cutoff_date
        ).all()

        if not eligible:
            logger.info("\n[OK] No suspects eligible for archival. System is clean.")
            return

        logger.info(f"\n[INFO] Found {len(eligible)} suspect(s) eligible for archival:\n")

        for person in eligible:
            days_since_caught = (datetime.now() - person.caught_at).days
            logger.info(f"  - {person.name} ({person.suspect_code}) | Caught {days_since_caught} days ago")

            # Get all evidence events for this person
            events = db.query(EventLog).filter(EventLog.person_id == person.id).order_by(EventLog.timestamp).all()

            if dry_run:
                logger.info(f"    [DRY RUN] Would generate PDF with {len(events)} events and delete from DB.")
                continue

            # 1. Generate PDF Report
            logger.info(f"    [1/3] Generating PDF report...")
            pdf_path = generate_pdf_report(person, events, db)
            logger.info(f"    [OK] PDF saved: {pdf_path}")

            # 2. Delete evidence images from disk
            logger.info(f"    [2/3] Cleaning up {len(events)} evidence files...")
            cleaned_files = 0
            for event in events:
                if event.image_path and os.path.exists(event.image_path):
                    try:
                        os.remove(event.image_path)
                        cleaned_files += 1
                    except Exception:
                        pass
            logger.info(f"    [OK] Removed {cleaned_files} evidence files from disk.")

            # 3. Delete from database
            logger.info(f"    [3/3] Removing from database...")
            db.query(FaceEmbedding).filter(FaceEmbedding.person_id == person.id).delete()
            db.query(EventLog).filter(EventLog.person_id == person.id).delete()
            db.delete(person)
            db.commit()
            logger.info(f"    [OK] {person.name} permanently removed from active system.\n")

        # Sync FAISS after all deletions
        if not dry_run:
            from app.recognition.faiss_sync import sync_faiss_from_db
            sync_faiss_from_db()
            logger.info("[OK] FAISS index synced.")

        logger.info("\n" + "=" * 60)
        logger.info("  ARCHIVAL COMPLETE")
        logger.info(f"  PDF reports saved to: {ARCHIVE_DIR}")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evidence Lifecycle Manager")
    parser.add_argument("--dry-run", action="store_true", help="Preview without making changes")
    parser.add_argument("--days", type=int, default=30, help="Days threshold (default: 30)")
    args = parser.parse_args()

    cleanup_caught_suspects(days_threshold=args.days, dry_run=args.dry_run)

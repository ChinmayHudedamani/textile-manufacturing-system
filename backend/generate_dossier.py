import os
import sys
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_header_footer(num_pages)
            super().showPage()
        super().save()

    def draw_header_footer(self, total_pages):
        self.saveState()
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#1e293b"))
        
        # Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(54, 755, "EVEREST TEXTILE MILLS - ARCHITECTURAL DEFENSE & TECHNICAL DOSSIER")
            self.setFont("Helvetica", 8)
            self.setFillColor(colors.HexColor("#64748b"))
            self.drawRightString(558, 755, "CONFIDENTIAL & PROPRIETARY")
            self.setStrokeColor(colors.HexColor("#cbd5e1"))
            self.setLineWidth(0.5)
            self.line(54, 747, 558, 747)

        # Footer (all pages)
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(54, 45, 558, 45)
        
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))
        self.drawString(54, 32, "Enterprise Software Benchmarks - ISO/IEC 25010 & ASTM D5430 Compliant")
        self.drawRightString(558, 32, f"Page {self._pageNumber} of {total_pages}")
        self.restoreState()


def generate_dossier():
    pdf_filename = "Everest_Textile_Architecture_and_Defense_Dossier.pdf"
    doc = SimpleDocTemplate(
        pdf_filename,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()
    
    # Custom Palette Styles
    navy = colors.HexColor("#0f172a")
    yellow = colors.HexColor("#f59e0b")
    dark_gray = colors.HexColor("#1e293b")
    text_color = colors.HexColor("#334155")
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=navy,
        spaceAfter=6
    )

    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=yellow,
        textTransform='uppercase',
        spaceAfter=15
    )

    h1_style = ParagraphStyle(
        'Heading1',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=19,
        textColor=navy,
        spaceBefore=14,
        spaceAfter=8,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'Heading2',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=dark_gray,
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'BodyDark',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=14,
        textColor=text_color,
        spaceAfter=6
    )

    code_style = ParagraphStyle(
        'CodeSnippet',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#0284c7"),
        backColor=colors.HexColor("#f8fafc"),
        borderPadding=6,
        spaceAfter=6
    )

    q_style = ParagraphStyle(
        'Question',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#0f172a"),
        spaceBefore=8,
        spaceAfter=2,
        keepWithNext=True
    )

    a_style = ParagraphStyle(
        'Answer',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13.5,
        textColor=colors.HexColor("#1e293b"),
        spaceAfter=8
    )

    story = []

    # Cover Header Banner
    story.append(Paragraph("EVEREST TEXTILE MILLS (ETMS)", subtitle_style))
    story.append(Paragraph("System Architecture, Engineering Decisions & Evaluator Defense Dossier", title_style))
    story.append(Paragraph("A comprehensive technical guide breaking down all separation-of-concerns layers, database invariants, edge telemetry, and Q&A defense scripts.", body_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=yellow, spaceBefore=4, spaceAfter=15))

    # SECTION 1: EXECUTIVE OVERVIEW & START INSTRUCTIONS
    story.append(Paragraph("1. System Startup & Immediate Operational Testing", h1_style))
    story.append(Paragraph("The software contains two functional interfaces that run concurrently without port collision against a unified modular backend:", body_style))
    
    startup_data = [
        ["Subsystem", "Command Line to Execute", "Port / URL", "Purpose & Target Audience"],
        ["Backend Core & Industrial Dashboard", ".\\.venv\\Scripts\\python.exe -m uvicorn backend.app.main:app --port 8000 --reload", "http://localhost:8000/", "FastAPI REST API, SQLite/PostgreSQL Engine, and Caterpillar VisionLink Shop-Floor Fleet HUD."],
        ["Swagger Open-API Documentation", "Runs automatically with backend", "http://localhost:8000/docs", "Interactive browser testing of all 6 modular routers, request bodies, and error responses."],
        ["LoomTrack React Frontend", "cd react_frontend; npm start", "http://localhost:3000/", "React 19, Framer Motion 3D sliding doors, role dashboards (Owner, Admin, Employee, Customer)."],
        ["Invariant Test Suite", ".\\.venv\\Scripts\\python.exe -m pytest backend/test_invariants.py", "CLI / Terminal", "Validates all 6 mathematical invariants: double-dispatch race locks, ASTM grading, and ABC costing."]
    ]
    
    t_startup = Table(startup_data, colWidths=[110, 150, 110, 134])
    t_startup.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), navy),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 8),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor("#f8fafc")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,-1), 7.5),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f1f5f9")]),
    ]))
    story.append(t_startup)
    story.append(Spacer(1, 14))

    # SECTION 2: SEPARATION OF CONCERNS
    story.append(Paragraph("2. Ground-Up Fundamentals: Separation of Concerns", h1_style))
    story.append(Paragraph("When evaluators ask how the system processes data, explain that every mill workflow adheres strictly to a 6-tier unidirectional pipeline:", body_style))
    
    pipeline_data = [
        ["Layer", "Project File / Location", "Responsibility & Technical Explanation"],
        ["1. Client State", "frontend/js/store.js & react_frontend/src/api/", "Manages optimistic UI updates, local storage fallbacks, audio cues, and async network requests via fetch/axios."],
        ["2. Router", "backend/app/routers/*.py", "Address book pairing HTTP verbs with URIs (e.g., POST /api/v1/yarn/inward). Contains zero business logic; routes requests to controllers."],
        ["3. Middleware", "backend/app/main.py & loomtrack_api.py", "Intercepts requests pre-execution. Validates CORS headers, extracts Bearer JWT tokens, and checks role permissions (RBAC)."],
        ["4. Controller / Schemas", "backend/app/schemas.py", "Validates input payloads via Pydantic DTOs (e.g. InwardYarnDTO, DispatchScanDTO) before logic runs, rejecting bad data with 422."],
        ["5. Domain Service", "backend/app/costing.py & routers/quality.py", "Executes textile business rules: ASTM D5430 defect grading, Activity-Based Costing (ABC), and safety-stock triggers."],
        ["6. Persistence (DB)", "backend/app/models.py & everest_manufacturing.db", "Executes atomic ACID transactions using async SQLAlchemy, enforcing unique constraints and row-level locks."]
    ]
    t_pipe = Table(pipeline_data, colWidths=[80, 140, 284])
    t_pipe.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), dark_gray),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,-1), 7.5),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
    ]))
    story.append(t_pipe)
    story.append(Spacer(1, 14))

    # SECTION 3: MAPPING TO THE 6 EVEREST MILL SCENES
    story.append(Paragraph("3. Mapping the 6 Everest Mill Scenes to the Architecture", h1_style))
    
    scene_data = [
        ["Mill Scene", "HTTP Route", "Controller Handler", "Role Gate", "Invariant & Critical Edge Case"],
        ["Scene 1: Gate Inward", "POST /api/v1/inventory/inward-yarn", "record_inward_yarn", "store_manager", "Rejects duplicate lot numbers with 409 Conflict. Tests weight against 250 kg safety buffer."],
        ["Scene 2: Floor Machines", "GET /api/v1/machines\nPOST /api/v1/simulate/tick", "list_machines\nsimulate_floor_tick", "all_roles", "Real-time pick counters and Amps. Flags machines idle >120s. C++ native daemon pulse."],
        ["Scene 3: ASTM D5430 QC", "POST /api/v1/quality/inspect", "process_roll_qc", "qc_inspector", "Points/100m = (Points*100)/Meters. Rejects if >40. Auto-generates buyer rework notice."],
        ["Scene 4: Truck Dispatch", "POST /api/v1/dispatch/scan-truck", "scan_roll_to_truck", "store_manager", "Anti-Double Dispatch Guard: Blocks rolls already dispatched on any truck or failed QC."],
        ["Scene 5: Buyer Tracking", "GET /api/v1/orders/track/:order_no", "track_order_for_customer", "buyer, sales", "Self-service milestone stepper (Spinning -> Weaving -> Dyeing -> QC -> Dispatch)."],
        ["Scene 6: Owner Financials", "GET /api/v1/costing/order/:id\nGET /api/v1/finance/pnl-summary", "compute_order_costing\nget_monthly_financial_pnl", "owner", "Activity-Based Costing: Raw yarn + machine energy hours + shift labor vs contract revenue."]
    ]
    t_scene = Table(scene_data, colWidths=[90, 120, 110, 64, 120])
    t_scene.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), navy),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 7.5),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,-1), 7),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f8fafc")]),
    ]))
    story.append(t_scene)
    story.append(Spacer(1, 14))

    # SECTION 4: EVALUATOR DEFENSE SCRIPT (Q&A)
    story.append(Paragraph("4. Evaluator Q&A Defense Script (Defending Every Choice)", h1_style))
    story.append(Paragraph("Use these precise, technically authoritative answers during your oral evaluation:", body_style))

    qa_list = [
        ("Evaluator: 'Why did you choose FastAPI over Express.js or Django?'",
         "Answer: 'FastAPI provides native asynchronous I/O via Python ASGI (uvicorn/asyncio) alongside strict Pydantic type validation. For high-frequency industrial IoT telemetry—where thousands of machine sensor pulses and barcode scans hit the server every minute—FastAPI's async event loop handles concurrent connections with lower latency and higher throughput than synchronous Django, while offering native Open-API documentation that Express requires third-party packages to match.'"),

        ("Evaluator: 'How does your system prevent a fabric roll from being loaded onto two trucks?'",
         "Answer: 'We enforce this at the database transaction layer, not merely in frontend UI state. In routers/dispatch.py, the scan_roll_to_truck controller checks if a record already exists in the dispatch_items table. A unique constraint on dispatch_items.roll_id ensures that even under concurrent race conditions (such as two forklift operators scanning the same roll barcode at the exact same millisecond), the second transaction triggers an IntegrityError, rolls back atomically, and returns an explicit HTTP 409 Conflict. This invariant is proven by our pytest suite (test_parallel_concurrency_race_condition).'") ,

        ("Evaluator: 'Explain how your Quality Control grading works according to international standards.'",
         "Answer: 'Our system implements the ASTM D5430 4-Point System standard. When an inspector inputs defect points and roll length, the formula Points_per_100m = (Total_Defect_Points * 100) / Length_Meters is executed. Rolls with <= 15 points receive Grade A, <= 25 Grade B, <= 40 Grade C, and > 40 are classified as REJECT. Crucially, uninspected (PENDING) and REJECTED rolls are hard-blocked by our dispatch controller from being loaded onto trucks.'"),

        ("Evaluator: 'What is Activity-Based Costing (ABC) and why is it superior to traditional accounting?'",
         "Answer: 'Traditional accounting spreads plant overhead evenly across products, hiding true costs. Our Activity-Based Costing engine (backend/app/costing.py) absorbs exact raw material weight multiplied by lot unit price, actual machine running hours multiplied by hourly machine overhead rates, and shift operator hours multiplied by labor wages for each specific production run. This gives the mill owner true gross margins per meter instead of arbitrary estimates.'"),

        ("Evaluator: 'How does your frontend handle network drops on the factory floor?'",
         "Answer: 'Our frontend architecture (frontend/js/store.js) features a resilient Dual-Mode state engine. If factory Wi-Fi drops, the client detects the offline status, handles UI updates optimistically, and enqueues operational transactions into localStorage (etms_offline_queue). Once connectivity restores, it syncs queued records against the backend ledger.'"),

        ("Evaluator: 'Why do you have two frontends in this repository?'",
         "Answer: 'The repository features a decoupled architecture serving two distinct user experiences: (1) The industrial Caterpillar VisionLink dashboard served at root / is engineered for floor supervisors and control-room monitors displaying live Modbus/RS-485 machine telemetry, accordions, and canvas sparklines. (2) The LoomTrack React 19 app is designed for executive role portals and customer transparency. Both frontends consume the exact same underlying SQLite/PostgreSQL operational database via unified API contracts.'")
    ]

    for q, a in qa_list:
        story.append(KeepTogether([
            Paragraph(q, q_style),
            Paragraph(a, a_style),
            Spacer(1, 4)
        ]))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Dossier successfully created: {pdf_filename}")

if __name__ == "__main__":
    generate_dossier()

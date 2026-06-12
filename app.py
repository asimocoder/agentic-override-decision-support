import gradio as gr
from uw_helper import UWHelper

uw_helper = UWHelper()

async def scan_pii(excel_file):
    """Fires on file upload. Scans raw sheets for PII before any LLM call."""
    if excel_file is None:
        return (
            gr.update(value="", visible=False),   # pii_warning_box
            gr.update(interactive=False),          # go_button — disable until scan done
            gr.update(visible=False),              # pii_action_row
        )
    raw_sheets = uw_helper.data_ingestor.read_raw_sheets(excel_file.name)
    hits = uw_helper.data_ingestor.detect_pii_raw(raw_sheets)
    if hits:
        warning_md = (
            "⚠️ **Possible PII detected in the uploaded file.**\n\n"
            "The following cells may contain sensitive identifiers that should be "
            "stripped before processing. Review each cell in your Excel file, strip "
            "the identified fields, and re-upload — or click **Proceed** to continue "
            "anyway (your responsibility).\n\n"
            + "\n".join(f"- {h}" for h in hits)
        )
        return (
            gr.update(value=warning_md, visible=True),
            gr.update(interactive=False),          # keep go_button disabled
            gr.update(visible=True),               # show pii_action_row
        )
    # Clean — no PII found
    return (
        gr.update(value="✅ No PII detected. Ready to proceed.", visible=True),
        gr.update(interactive=True),               # enable go_button
        gr.update(visible=False),                  # hide pii_action_row
    )


async def run_agent1(excel_file, trigger_type, thread_id):
    """Step 1 — run ingestion and analyst"""

    # Immediately disable button and show status
    yield (
        gr.update(visible=True),                                    # step1_group
        gr.update(visible=False, open=False),                       # step2_group
        gr.update(interactive=False, value="Running analysis..."),  # go_button
        [],                                                         # trends_table
        [],                                                         # queries_table
        trigger_type,                                               # trigger_state
    )

    trends_display, queries_display = await uw_helper.run_agent1_step(
        excel_file, trigger_type, thread_id
    )

    # Final yield — analysis complete, make step2 visible
    yield (
        gr.update(visible=False),                                   # step1_group
        gr.update(visible=True, open=False),                        # step2_group — JS opens it
        gr.update(interactive=True, value="Run Analysis"),          # go_button
        trends_display,                                             # trends_table
        queries_display,                                            # queries_table
        trigger_type,                                               # trigger_state
    )


async def run_agent2(trends_data, queries_data, company_name, cin, thread_id):
    """Step 3 — resume graph with named entity inputs and edited tables"""

    # Immediately disable button; collapse step2, keep step3 open while running
    yield (
        gr.update(visible=True, open=False),                                # step2_group
        gr.update(visible=True, open=True),                                 # step3_group
        gr.update(visible=False, open=False),                               # step4_group
        gr.update(interactive=False, value="Running external research..."), # research_button
        "",                                                                 # go_nogo_display
        "",                                                                 # brief_display
        "",                                                                 # go_nogo_state
        "",                                                                 # brief_state
    )

    brief, go_nogo = await uw_helper.run_agent2_step(trends_data, queries_data, company_name, cin, thread_id)

    # Final yield — research complete, make step4 visible
    yield (
        gr.update(visible=True, open=False),                                # step2_group
        gr.update(visible=True, open=False),                                # step3_group
        gr.update(visible=True, open=False),                                # step4_group — JS opens it
        gr.update(interactive=True, value="Run External Research"),         # research_button
        go_nogo,                                                            # go_nogo_display
        brief,                                                              # brief_display
        go_nogo,                                                            # go_nogo_state
        brief,                                                              # brief_state
    )


def download_docx(brief, go_nogo, company_name, trigger_type):
    """Generate and return DOCX file for download."""
    if not brief:
        raise gr.Error("No intelligence brief available — please complete the full workflow first.")
    try:
        path = uw_helper.generate_brief_docx(
            brief=brief,
            go_nogo=go_nogo,
            company_name=company_name,
            trigger_type=trigger_type,
        )
        return gr.update(value=path, visible=True)
    except Exception as e:
        raise gr.Error(f"DOCX generation failed: {e}")


def download_pdf(brief, go_nogo, company_name, trigger_type):
    """Generate and return PDF file for download."""
    if not brief:
        raise gr.Error("No intelligence brief available — please complete the full workflow first.")
    try:
        path = uw_helper.generate_brief_pdf(
            brief=brief,
            go_nogo=go_nogo,
            company_name=company_name,
            trigger_type=trigger_type,
        )
        return gr.update(value=path, visible=True)
    except RuntimeError as e:
        if "LibreOffice not found" in str(e):
            raise gr.Error(
                "PDF download requires LibreOffice. "
                "Install LibreOffice locally (libreoffice.org) or deploy to Railway "
                "where it is installed automatically."
            )
        raise gr.Error(f"PDF generation failed: {e}")


def copy_analyst_output(trends_data, queries_data) -> str:
    """
    Format trends and queries tables as tab-separated text for clipboard copy.
    Pastes cleanly into Excel (tab-separated) or a credit note (readable text).
    Returns the formatted string — JS in the UI handles the actual clipboard write.
    """
    lines = []

    lines.append("FINANCIAL ANOMALIES")
    lines.append("Observation\tSupporting Data\tSeverity")
    try:
        for row in trends_data.values.tolist():
            if any(cell for cell in row):
                lines.append("\t".join(str(cell) for cell in row))
    except Exception:
        pass

    lines.append("")
    lines.append("QUERIES FOR EXTERNAL RESEARCH")
    lines.append("Question\tCategory")
    try:
        for row in queries_data.values.tolist():
            if any(cell for cell in row):
                lines.append("\t".join(str(cell) for cell in row))
    except Exception:
        pass

    return "\n".join(lines)


async def reset():
    new_thread = uw_helper.make_thread_id()
    return (
        gr.update(visible=True),                      # step1_group
        gr.update(visible=False, open=False),         # step2_group
        gr.update(visible=False, open=False),         # step3_group
        gr.update(visible=False, open=False),         # step4_group
        None,                                         # excel_file
        "Below Threshold",                            # trigger_type
        [],                                           # trends_table
        [],                                           # queries_table
        "",                                           # company_name
        "",                                           # cin
        "",                                           # go_nogo_display
        "",                                           # brief_display
        new_thread,                                   # thread
        "",                                           # trigger_state
        gr.update(value=None, visible=False),         # docx_output
        gr.update(value=None, visible=False),         # pdf_output
        "",                                           # brief_state
        "",                                           # go_nogo_state
        gr.update(value="", visible=False),           # pii_warning_box
        gr.update(interactive=False),                 # go_button — disabled until next upload
        gr.update(visible=False),                     # pii_action_row
    )


with gr.Blocks() as demo:
    gr.Markdown("# Underwriter Helper")
    gr.Markdown("Agentic Override Decision Support System — MSME Lending")
    thread = gr.State(uw_helper.make_thread_id())
    trigger_state = gr.State("")   # stores trigger_type for use at download time
    brief_state = gr.State("")     # stores brief text — gr.Textbox(interactive=False) not reliable as input
    go_nogo_state = gr.State("")   # stores go/nogo stance for same reason

    # --- STEP 1 — INTAKE ---
    with gr.Group(visible=True) as step1_group:
        gr.Markdown("### Step 1 — Case Intake")
        gr.Markdown(
            "⚠️ **Before uploading:** strip Company Name, CIN, and PAN from the CAM workbook. "
            "The system will scan for these fields immediately on upload and warn you if found."
        )
        excel_file = gr.File(
            label="Upload CAM Excel Workbook",
            file_types=[".xlsx", ".xls"]
        )

        # PII scan result — shown immediately after upload, before Run Analysis
        pii_warning_box = gr.Markdown("", visible=False)
        with gr.Row(visible=False) as pii_action_row:
            proceed_pii_button = gr.Button("Proceed Anyway", variant="secondary")
            abort_pii_button = gr.Button("Abort — Strip PII First", variant="stop")

        trigger_type = gr.Dropdown(
            choices=["Below Threshold", "Anomaly Flagged", "Standard Diligence"],
            value="Below Threshold",
            label="Trigger Type"
        )
        go_button = gr.Button("Run Analysis", variant="primary", interactive=False)

    # --- STEP 2 — AGENT 1 OUTPUT ---
    with gr.Accordion("Step 2 — Review and Edit Agent 1 Output", open=False, visible=False, elem_id="step2_accordion") as step2_group:
        gr.Markdown("Review the findings below. You may edit, add, or delete rows before proceeding.")
        gr.Markdown("#### Financial Anomalies and Signals")
        trends_table = gr.Dataframe(
            headers=["Observation", "Supporting Data", "Severity"],
            datatype=["str", "str", "str"],
            column_count=(3, "fixed"),
            interactive=True,
            wrap=True
        )
        gr.Markdown("#### Queries for External Research")
        queries_table = gr.Dataframe(
            headers=["Question", "Category"],
            datatype=["str", "str"],
            column_count=(2, "fixed"),
            interactive=True,
            wrap=True
        )
        with gr.Row():
            copy_button = gr.Button("Copy Analyst Output", variant="secondary")
            proceed_button = gr.Button("Proceed to External Research", variant="primary")
        # Hidden textbox holds formatted text; JS reads it and writes to clipboard
        copy_text = gr.Textbox(visible=False, elem_id="copy_text_hidden")

    # --- STEP 3 — NAMED ENTITY HANDOFF ---
    with gr.Accordion("Step 3 — Provide Borrower Identity", open=False, visible=False, elem_id="step3_accordion") as step3_group:
        gr.Markdown("This information will be used for external research only and was not shared with the financial analyst.")
        company_name = gr.Textbox(label="Company Name")
        cin = gr.Textbox(label="CIN (Corporate Identification Number)")
        research_button = gr.Button("Run External Research", variant="primary")

    # --- STEP 4 — INTELLIGENCE BRIEF ---
    with gr.Accordion("Step 4 — Intelligence Brief", open=False, visible=False, elem_id="step4_accordion") as step4_group:
        go_nogo_display = gr.Textbox(label="Recommended Stance", interactive=False)
        brief_display = gr.Textbox(
            label="Full Intelligence Brief",
            interactive=False,
            lines=30
        )
        with gr.Row():
            docx_button = gr.Button("Download DOCX", variant="secondary")
            pdf_button = gr.Button("Download PDF", variant="secondary")
        docx_output = gr.File(label="DOCX", visible=False)
        pdf_output = gr.File(label="PDF", visible=False)
        reset_button = gr.Button("Start New Case", variant="stop")

    # --- EVENT WIRING ---

    # PII scan fires on upload — before Run Analysis is enabled
    excel_file.upload(
        scan_pii,
        inputs=[excel_file],
        outputs=[pii_warning_box, go_button, pii_action_row],
        show_progress=False,
    )

    # Proceed despite PII — enable Run Analysis, hide action buttons
    proceed_pii_button.click(
        fn=lambda: (
            gr.update(interactive=True),
            gr.update(visible=False),
        ),
        inputs=[],
        outputs=[go_button, pii_action_row]
    )

    # Abort — clear file, reset PII warning, disable Run Analysis
    abort_pii_button.click(
        fn=lambda: (
            None,
            gr.update(value="", visible=False),
            gr.update(interactive=False),
            gr.update(visible=False),
        ),
        inputs=[],
        outputs=[excel_file, pii_warning_box, go_button, pii_action_row]
    )

    go_button.click(
        run_agent1,
        inputs=[excel_file, trigger_type, thread],
        outputs=[step1_group, step2_group, go_button, trends_table, queries_table, trigger_state]
    ).then(
        fn=None,
        inputs=[],
        outputs=[],
        js="() => { setTimeout(() => { var btn = document.querySelector('#step2_accordion button.label-wrap'); if (btn && !btn.classList.contains('open')) btn.click(); }, 400); }"
    )

    copy_button.click(
        copy_analyst_output,
        inputs=[trends_table, queries_table],
        outputs=[copy_text]
    ).then(
        fn=None,
        inputs=[copy_text],
        outputs=[],
        js="(text) => { navigator.clipboard.writeText(text); }"
    )

    proceed_button.click(
        fn=lambda: (gr.update(visible=True, open=False), gr.update(visible=True, open=False)),
        inputs=[],
        outputs=[step2_group, step3_group]
    ).then(
        fn=None,
        inputs=[],
        outputs=[],
        js="() => { setTimeout(() => { var btn = document.querySelector('#step3_accordion button.label-wrap'); if (btn && !btn.classList.contains('open')) btn.click(); }, 400); }"
    )

    research_button.click(
        run_agent2,
        inputs=[trends_table, queries_table, company_name, cin, thread],
        outputs=[step2_group, step3_group, step4_group, research_button, go_nogo_display, brief_display, go_nogo_state, brief_state]
    ).then(
        fn=None,
        inputs=[],
        outputs=[],
        js="() => { setTimeout(() => { var btn = document.querySelector('#step4_accordion button.label-wrap'); if (btn && !btn.classList.contains('open')) btn.click(); }, 600); }"
    )

    docx_button.click(
        download_docx,
        inputs=[brief_state, go_nogo_state, company_name, trigger_state],
        outputs=[docx_output]
    )

    pdf_button.click(
        download_pdf,
        inputs=[brief_state, go_nogo_state, company_name, trigger_state],
        outputs=[pdf_output]
    )

    reset_button.click(
        reset,
        inputs=[],
        outputs=[
            step1_group, step2_group, step3_group, step4_group,
            excel_file, trigger_type, trends_table, queries_table,
            company_name, cin, go_nogo_display, brief_display,
            thread, trigger_state, docx_output, pdf_output,
            brief_state, go_nogo_state, pii_warning_box,
            go_button, pii_action_row
        ]
    )

if __name__ == "__main__":
    demo.launch(theme=gr.themes.Default(primary_hue="emerald"))
import gradio as gr
from uw_helper import UWHelper


uw_helper = UWHelper()

async def run_agent1(excel_file, trigger_type, thread_id):
        """Step 1 — run ingestion and analyst"""
        
        # Immediately disable button and show status
        yield (
            gr.update(visible=True),                                    # step1_group
            gr.update(visible=False),                                   # step2_group
            gr.update(interactive=False, value="Running analysis..."),  # go_button
            [],                                                         # trends_table
            []                                                          # queries_table
        )

        trends_display, queries_display = await uw_helper.run_agent1_step(excel_file, trigger_type, thread_id)

        # Final yield — show results and re-enable button
        yield (
            gr.update(visible=False),                                   # step1_group
            gr.update(visible=True),                                    # step2_group
            gr.update(interactive=True, value="Run Analysis"),          # go_button
            trends_display,                                             # trends_table
            queries_display                                             # queries_table
        )


async def run_agent2(trends_data, queries_data, company_name, cin, thread_id):
    """Step 3 — resume graph with named entity inputs and edited tables"""

    # Immediately disable button and show status
    yield (
        gr.update(visible=True),                                            # step2_group
        gr.update(visible=True),                                            # step3_group
        gr.update(visible=False),                                           # step4_group
        gr.update(interactive=False, value="Running external research..."), # research_button
        "",                                                                 # go_nogo_display
        ""                                                                  # brief_display
    )

    brief, go_nogo = await uw_helper.run_agent2_step(trends_data, queries_data, company_name, cin, thread_id)

    # Final yield — show brief and re-enable button
    yield (
        gr.update(visible=False),                                           # step2_group
        gr.update(visible=False),                                           # step3_group
        gr.update(visible=True),                                            # step4_group
        gr.update(interactive=True, value="Run External Research"),         # research_button
        go_nogo,                                                            # go_nogo_display
        brief                                                               # brief_display
    )

async def reset():
    new_thread = uw_helper.make_thread_id()
    return (
        gr.update(visible=True),           # step1_group
        gr.update(visible=False),          # step2_group
        gr.update(visible=False),          # step3_group
        gr.update(visible=False),          # step4_group
        None,                              # excel_file
        "Below Threshold",                 # trigger_type
        [],                                # trends_table
        [],                                # queries_table
        "",                                # company_name
        "",                                # cin
        "",                                # go_nogo_display
        "",                                # brief_display
        new_thread                         # thread
    )


with gr.Blocks() as demo:
    gr.Markdown("# Underwriter Helper")
    gr.Markdown("Agentic Override Decision Support System — MSME Lending")
    thread = gr.State(uw_helper.make_thread_id())

    # --- STEP 1 — INTAKE ---
    with gr.Group(visible=True) as step1_group:
        gr.Markdown("### Step 1 — Case Intake")
        excel_file = gr.File(
            label="Upload CRAN Excel Workbook",
            file_types=[".xlsx", ".xls"]
        )
        trigger_type = gr.Dropdown(
            choices=["Below Threshold", "Anomaly Flagged", "Standard Diligence"],
            value="Below Threshold",
            label="Trigger Type"
        )
        go_button = gr.Button("Run Analysis", variant="primary")

    # --- STEP 2 — AGENT 1 OUTPUT ---
    with gr.Group(visible=False) as step2_group:
        gr.Markdown("### Step 2 — Review and Edit Agent 1 Output")
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
        proceed_button = gr.Button("Proceed to External Research", variant="primary")

    # --- STEP 3 — NAMED ENTITY HANDOFF ---
    with gr.Group(visible=False) as step3_group:
        gr.Markdown("### Step 3 — Provide Borrower Identity")
        gr.Markdown("This information will be used for external research only and was not shared with the financial analyst.")
        company_name = gr.Textbox(label="Company Name")
        cin = gr.Textbox(label="CIN (Corporate Identification Number)")
        research_button = gr.Button("Run External Research", variant="primary") 

    # --- STEP 4 — INTELLIGENCE BRIEF ---
    with gr.Group(visible=False) as step4_group:
        gr.Markdown("### Step 4 — Intelligence Brief")
        go_nogo_display = gr.Textbox(label="Recommended Stance", interactive=False)
        brief_display = gr.Textbox(
            label="Full Intelligence Brief",
            interactive=False,
            lines=30
        )
        reset_button = gr.Button("Start New Case", variant="stop")

    # --- EVENT WIRING ---
    go_button.click(
    run_agent1,
    inputs=[excel_file, trigger_type, thread],
    outputs=[step1_group, step2_group, go_button, trends_table, queries_table]
    )

    proceed_button.click(
        fn=lambda: (gr.update(visible=False), gr.update(visible=True)),
        inputs=[],
        outputs=[step2_group, step3_group]
    )

    research_button.click(
    run_agent2,
    inputs=[trends_table, queries_table, company_name, cin, thread],
    outputs=[step2_group, step3_group, step4_group, research_button, go_nogo_display, brief_display]
    )

    reset_button.click(
        reset,
        inputs=[],
        outputs=[
            step1_group, step2_group, step3_group, step4_group,
            excel_file, trigger_type, trends_table, queries_table,
            company_name, cin, go_nogo_display, brief_display, thread
        ]
    )

demo.launch(theme=gr.themes.Default(primary_hue="emerald"))
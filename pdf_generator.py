"""
pdf_generator.py
Converts a DOCX intelligence brief to PDF via LibreOffice headless.

Same approach as the Resume Tailor project — python-docx generates the DOCX,
LibreOffice headless converts it to PDF. One rendering path, consistent output.

LibreOffice must be installed:
  - Local Windows dev:  Install LibreOffice from https://www.libreoffice.org/
                        Ensure soffice.exe is on PATH or set LIBREOFFICE_PATH env var
  - Railway/VM:         Installed via buildCommand in railway.toml:
                        apt-get install -y libreoffice

Environment variable (optional):
  LIBREOFFICE_PATH — full path to soffice executable if not on PATH
                     e.g. "C:\\Program Files\\LibreOffice\\program\\soffice.exe"
"""

import os
import subprocess
import tempfile
from pathlib import Path

from docx_generator import generate_docx


def _get_soffice_path() -> str:
    """
    Resolve LibreOffice executable path.
    Checks LIBREOFFICE_PATH env var first, then known Windows paths,
    then PATH via shutil.which. Raises immediately if not found —
    avoids slow Windows CreateProcess failure on subprocess.run.
    """
    import shutil

    env_path = os.environ.get("LIBREOFFICE_PATH")
    if env_path:
        if Path(env_path).exists():
            return env_path
        raise RuntimeError(
            f"LIBREOFFICE_PATH is set to {env_path!r} but the file does not exist."
        )

    # Common Windows install locations — instant Path.exists() check
    windows_paths = [
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ]
    for wp in windows_paths:
        if Path(wp).exists():
            return wp

    # Linux/Railway — check PATH
    found = shutil.which("soffice")
    if found:
        return found

    raise RuntimeError(
        "LibreOffice not found. "
        "Install LibreOffice or set the LIBREOFFICE_PATH environment variable. "
        "On Railway, add \'apt-get install -y libreoffice\' to railway.toml buildCommand."
    )


def generate_pdf(
    brief: str,
    go_nogo: str,
    company_name: str,
    trigger_type: str,
    output_path: str | None = None,
) -> str:
    """
    Generate a PDF intelligence brief.

    Internally generates a DOCX first, then converts via LibreOffice headless.

    Args:
        brief:        Full brief text from Researcher agent
        go_nogo:      Stance string — "GO", "NOGO", or "NEEDS FURTHER RESEARCH"
        company_name: Borrower company name
        trigger_type: Trigger type from Step 1
        output_path:  Optional explicit output path for the PDF.
                      If None, writes to a temp file.

    Returns:
        Path to the generated PDF file as a string.

    Raises:
        RuntimeError: If LibreOffice conversion fails.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Step 1 — generate DOCX into temp directory
        docx_filename = f"brief_{company_name.replace(' ', '_')}.docx"
        docx_path = str(Path(tmp_dir) / docx_filename)
        generate_docx(
            brief=brief,
            go_nogo=go_nogo,
            company_name=company_name,
            trigger_type=trigger_type,
            output_path=docx_path,
        )

        # Step 2 — convert DOCX to PDF via LibreOffice headless
        soffice = _get_soffice_path()
        cmd = [
            soffice,
            "--headless",
            "--convert-to", "pdf",
            "--outdir", tmp_dir,
            docx_path,
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except FileNotFoundError:
            raise RuntimeError(
                "LibreOffice not found. "
                "Install LibreOffice or set the LIBREOFFICE_PATH environment variable. "
                "On Railway, add 'apt-get install -y libreoffice' to railway.toml buildCommand."
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("LibreOffice PDF conversion timed out after 60 seconds.")

        if result.returncode != 0:
            raise RuntimeError(
                f"LibreOffice conversion failed (exit {result.returncode}).\n"
                f"stderr: {result.stderr}\nstdout: {result.stdout}"
            )

        # Step 3 — locate the generated PDF
        pdf_filename = docx_filename.replace(".docx", ".pdf")
        pdf_tmp_path = Path(tmp_dir) / pdf_filename

        if not pdf_tmp_path.exists():
            raise RuntimeError(
                f"LibreOffice ran successfully but PDF not found at {pdf_tmp_path}. "
                f"Directory contents: {list(Path(tmp_dir).iterdir())}"
            )

        # Step 4 — move to final output path
        if output_path is None:
            # Write to a persistent temp file outside the temp directory
            out_tmp = tempfile.NamedTemporaryFile(
                suffix=".pdf", delete=False,
                prefix=f"brief_{company_name.replace(' ', '_')}_"
            )
            output_path = out_tmp.name
            out_tmp.close()

        # Copy PDF to output location
        import shutil
        shutil.copy2(str(pdf_tmp_path), output_path)

    return output_path

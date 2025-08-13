import sys
from pathlib import Path

def main():
    try:
        import sys
        import os

        # Remove project root from sys.path to avoid local shadowing
        project_root = os.path.abspath(os.getcwd())
        if project_root in sys.path:
            sys.path.remove(project_root)

        venv_site_packages = os.path.join(
            os.path.dirname(sys.executable),
            "..", "Lib", "site-packages"
        )
        venv_site_packages = os.path.abspath(venv_site_packages)
        if venv_site_packages not in sys.path:
            sys.path.insert(0, venv_site_packages)

        import markitdown
        print("Imported markitdown from:", markitdown.__file__)
        print("markitdown attributes:", dir(markitdown))
        MarkItDown = markitdown.MarkItDown
    except ImportError as e:
        print("markitdown is not installed or not available in this environment.")
        sys.exit(1)

    pdf_path = r"C:\Users\deepakgupta13\OneDrive - Nagarro\Cloud Practice\migration_platform_2\NBQ Assessment documents\NBQ- Documents Received\D5_NBQ-WAN-DIAGRAM-MAY-2025-HLD.pdf"
    output_md = "backend_exported.md"

    if not Path(pdf_path).exists():
        print(f"PDF file not found: {pdf_path}")
        sys.exit(1)

    try:
        converter = MarkItDown()
        result = converter.convert(pdf_path)
        print("Result type:", type(result))
        print("Result repr:", repr(result))
        print("Result dir:", dir(result))
        if hasattr(result, "markdown"):
            md_content = result.markdown
        elif hasattr(result, "content"):
            md_content = result.content
        elif isinstance(result, str):
            md_content = result
        else:
            print("Unexpected result type from MarkItDown.convert")
            sys.exit(1)
        with open(output_md, "w", encoding="utf-8") as f:
            f.write(md_content)
        print(f"Conversion successful. Output written to {output_md}")
    except Exception as e:
        print(f"Error during conversion: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

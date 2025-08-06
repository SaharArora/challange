Vendra Quote Parser
Introduction

This project provides a Python-based command-line tool designed to parse unstructured supplier quotes from PDF files. It extracts key pricing data, including line items, quantities, and total prices, and presents them in a structured JSON format.
Tech Requirements

    Python 3.x

    PyMuPDF (fitz): This library is used for extracting text efficiently from PDF documents.

Setup Instructions

To get this tool running, follow these steps:

    Clone the Repository:
    Clone the project from GitHub:

    git clone https://github.com/SaharArora/challange
    cd challange

    If you just have the Python file, simply save it to your computer.

    Create a Virtual Environment (Recommended):
    It's a good practice to use a virtual environment to manage project dependencies.

    python -m venv venv
    source venv/bin/activate  # On Windows, use: `venv\Scripts\activate`

    Install Dependencies:
    Install the necessary library, PyMuPDF, using pip:

    pip install PyMuPDF

Usage

This script is a command-line tool. You can run it by providing the path to one or more PDF files, a directory containing PDFs, or a pattern to match multiple files.

python quote_parser.py <paths> [options]

Arguments

    <paths>: Specify one or more PDF files, a directory, or a glob pattern (like *.pdf) to process.

        Example: file.pdf

        Example: quotes/ (this will process all PDFs inside the quotes/ folder)

        Example: *.pdf (this will process all PDFs in the current folder)

        Example: file1.pdf file2.pdf (to process specific multiple files)

Options

    --out <path>: Sets the name and path for the output JSON file. If not specified, it defaults to parsed_quotes.json.

    --pretty: Formats the JSON output with indentation, making it easier to read.

    --quiet, -q: Hides the progress messages during processing.

    --separate-files: Creates a distinct JSON file for each PDF processed, instead of combining all results into one file. If you use this, the --out option will be ignored, and files will be named like <original_filename>_parsed.json.

Examples

    Parse a single PDF file:

    python quote_parser.py VendraSampleQuote-01.pdf

    Parse a PDF and save the results to a specific, formatted JSON file:

    python quote_parser.py VendraSampleQuote-02.pdf --out my_parsed_quote.json --pretty

    Process all PDF files in a folder and save each result to its own JSON file:

    # Assuming your PDFs are in a folder called 'my_pdfs'
    python quote_parser.py my_pdfs/ --separate-files --pretty

    Process a few specific PDF files and combine their results:

    python quote_parser.py VendraSampleQuote-01.pdf VendraSampleQuote-03.pdf --out combined_quotes.json


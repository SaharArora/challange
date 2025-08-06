# Technical Writeup

## How I Handled Different Quote Formats

### Format Detection
- Built keyword matching system that searches for company names in PDF text
- Converted all text to uppercase for reliable string matching
- Created fallback system that tries VTN → Sematool → Thirty-Two Machine parsers in order
- If no format detected, attempts all parsers sequentially *(could improve with ML classification)*

### VTN Manufacturing Parser
- Used regex to find lines starting with numbers (quantities)
- Validated quantities are under 10,000 to avoid treating item codes as quantities
- Extracted prices by finding rightmost numeric values on each line
- Removed prices from line text to isolate descriptions
- Used regex to remove common item code patterns from descriptions
- Grouped parsed items by quantity to handle multi-quantity quotes

### Sematool Parser
- Searched for header lines containing words like 'item', 'description', 'quantity'
- Parsed each line after the header as a table row
- Extracted quantities by finding numbers that aren't part of price values
- Combined all items into single quote with calculated average unit price
- Manually removed '/EA' and '/EACH' text from descriptions *(could improve with standardized unit parsing)*

### Thirty-Two Machine Parser
- Built state machine that accumulates description lines until hitting price data
- Used regex pattern to detect lines ending with `quantity, price, total` format
- Joined multi-line descriptions with spaces
- Cleaned CSV formatting and quote characters from extracted data
- Combined all items into single quote group

### Price Normalization Function
- Created single function that handles `$2,000.00`, `€1,234.56`, `1500` formats
- Strips currency symbols (`$`, `€`, `£`, `¥`) and commas
- Handles negative values and missing decimal places
- Returns consistent `XXXX.XX` string format
- Falls back to `"0.00"` for unparseable values *(could improve with currency detection)*

## Assumptions and Fallbacks Used

### Hard-Coded Assumptions
- Quantities over 10,000 are item codes, not actual quantities
- Rightmost numbers on lines are prices/costs
- Text remaining after removing quantities and prices is the description
- All prices use same currency within a quote
- Valid items must have description, quantity > 0, and price > 0

### Built-In Fallbacks
- If format detection fails: try all parsers in sequence
- If individual line fails: skip line, continue processing
- If quantity missing: default to `"1"`
- If price invalid: default to `"0.00"`
- If description empty: use remaining cleaned text
- If no items parsed: return empty array *(could improve with better error messages)*

### Error Handling I Added
- Wrapped each line parsing in try/except blocks
- Continued processing rest of document when individual items fail  
- Filtered out items with missing required fields
- Used multiple regex patterns as backups for price extraction

## Scalability

### What I Built
- Command-line tool that processes PDFs sequentially one at a time
- Built-in support for multiple input methods: single files, directories, glob patterns
- JSON output with option for separate files per PDF or combined results
- Memory management by closing PyMuPDF documents after text extraction
- Batch processing capability through file discovery system

### Current Limitations and Improvements
- **Processing**: Single-threaded execution *(improve: add multiprocessing for parallel PDF handling)*
- **Memory**: Loads entire PDF text into memory at once *(improve: streaming/page-by-page processing)*
- **Storage**: File-based JSON output only *(improve: database integration for large-scale storage)*
- **API**: CLI-only interface *(improve: REST API for web integration)*
- **Caching**: No result caching between runs *(improve: cache parsed results to avoid re-processing)*
- **Monitoring**: Basic console output only *(improve: metrics collection and monitoring)*

## Robustness

### Error Handling I Built
- Try/except blocks around PDF text extraction with graceful failure
- Individual line parsing wrapped in exception handling to continue processing
- File existence checking before attempting to process PDFs
- Input validation for command-line arguments
- Fallback cascade when format detection fails
- Filtering of incomplete/invalid items before output

### Robustness Features Added
- Multiple regex patterns as backup for price extraction
- Default value assignment when data is missing or invalid
- Format detection that tries multiple parsers if first attempt fails
- Glob pattern support for flexible file input handling
- Continued processing even when individual PDFs fail
- Summary reporting of successful vs failed parses

### Current Gaps and Improvements
- **PDF Corruption**: Basic PyMuPDF error handling *(improve: add PDF repair/recovery)*
- **Network Issues**: No handling for remote PDF sources *(improve: add retry logic with exponential backoff)*
- **Resource Limits**: No protection against very large files *(improve: add file size limits and timeouts)*
- **Data Validation**: Limited validation of extracted data *(improve: add business rule validation)*
- **Recovery**: No ability to resume failed batch jobs *(improve: add checkpoint/resume functionality)*
- **Logging**: Basic print statements *(improve: structured logging with different severity levels)*

## Ideas for Improving Accuracy and Reliability

### What I Built vs What Could Be Better
- **Format Detection**: Used simple keyword search *(improve: train ML classifier on document structure)*
- **Price Extraction**: Used regex patterns for common US formats *(improve: support international currency formats)*  
- **Description Cleaning**: Used basic regex to remove item codes *(improve: use NLP for smarter text parsing)*
- **Validation**: Only checked for non-zero values *(improve: validate price × quantity = total)*
- **Processing**: Single-threaded file processing *(improve: add parallel processing)*
- **Output**: JSON files only *(improve: add database storage and API)*
- **Error Reporting**: Basic console output *(improve: detailed logging and metrics)*
- **Testing**: Manual testing on sample files *(improve: automated test suite)*

### Specific Reliability Improvements Needed
- Cross-validate calculated totals against document totals *(math validation)*
- Add confidence scoring for parsed results *(quality metrics)*
- Handle multi-currency quotes *(international support)* 
- Detect and merge duplicate items *(data deduplication)*
- Add retry logic for PDF extraction failures *(robustness)*
- Create feedback system for human corrections *(continuous improvement)*

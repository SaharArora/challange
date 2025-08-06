import fitz  # PyMuPDF
import re
import json
import argparse
import os
import glob
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Any, Tuple

def normalize_price(price_str: str) -> str:
    """
    Normalize price string to a consistent decimal format (e.g., "1234.56").
    Handles currency symbols, commas, spaces, and negative values.
    
    REQUIREMENT: Normalize price formats (e.g., $2,000.00 → 2000)
    REQUIREMENT: Handle currency symbols and different decimal formats
    """
    if not price_str:
        return "0.00"
    
    # REQUIREMENT: Handle currency symbols - Remove $, €, £, ¥ and spaces
    cleaned = re.sub(r'[\$€£¥\s]', '', str(price_str))
    # REQUIREMENT: Handle different decimal formats - Remove thousands separators
    cleaned = cleaned.replace(',', '')
    
    # Check for negative sign
    sign = ''
    if cleaned.startswith('-'):
        sign = '-'
        cleaned = cleaned[1:]

    try:
        # REQUIREMENT: Normalize price formats - Convert to consistent decimal format
        return f"{float(sign + cleaned):.2f}"
    except ValueError:
        return "0.00"

def extract_prices_from_line(line: str) -> List[str]:
    """
    Extract all price-like patterns from a line, including negative values and
    various number formats. Returns normalized price strings.
    
    REQUIREMENT: Extract unit prices and costs from text
    REQUIREMENT: Handle different decimal formats and currency symbols
    """
    # REQUIREMENT: Handle different variants - Multiple patterns to catch various price formats
    patterns = [
        r'-?\$?\s*[\d,]+\.\d{2}',  # e.g., -$1,234.56 or $1,234.56
        r'-?\$?\s*[\d,]+',         # e.g., -$1,234 or $1,234
    ]
    prices = []
    for pattern in patterns:
        matches = re.findall(pattern, line)
        prices.extend(matches)
    
    # REQUIREMENT: Normalize price formats - Convert all found prices to consistent format
    return [normalize_price(p) for p in prices if p.strip()]

def parse_vtn_format(lines: List[str]) -> List[Dict[str, Any]]:
    """
    Parses quotes in VTN Manufacturing format.
    Assumes a structure like: Quantity [ItemCode] Description UnitPrice Amount
    
    REQUIREMENT: Handle different variants of Quotes - VTN Manufacturing specific format
    REQUIREMENT: Group separate quote options by total quantity
    """
    # REQUIREMENT: Group by quantity - Use defaultdict to automatically group line items
    quote_groups = defaultdict(list)
    
    for line in lines:
        line = line.strip()
        # REQUIREMENT: Handle inconsistent spacing and casing - strip() and upper() comparison
        if not line or line.upper() in ['TOTAL', 'SUBTOTAL', 'MOQ', 'ITEM CODE', 'DESCRIPTION', 'UNIT PRICE', 'AMOUNT', 'QUOTE']:
            continue

        # REQUIREMENT: Extract unit prices and costs
        line_prices = extract_prices_from_line(line)
        
        if len(line_prices) < 2:
            continue
        
        try:
            # REQUIREMENT: Extract costs and unit prices from rightmost price values
            cost = line_prices[-1]
            unit_price = line_prices[-2]

            # REQUIREMENT: Extract quantities - Look for quantity at beginning of line
            qty_match = re.match(r'^\s*(\d+)\s+', line)
            quantity = "1"
            if qty_match:
                qty_candidate = qty_match.group(1)
                # Heuristic: Quantity is usually not excessively large
                if int(qty_candidate) <= 10000: 
                    quantity = qty_candidate
            else:
                continue

            # REQUIREMENT: Extract descriptions - Remove quantity and prices to get description
            temp_line = line
            if qty_match:
                temp_line = temp_line[qty_match.end():].strip()
            
            # Remove price values from the line to get description
            for p_val in reversed(line_prices):
                raw_prices_in_line = re.findall(r'-?\$?[\d,]+\.?\d*', temp_line)
                if raw_prices_in_line:
                    if normalize_price(raw_prices_in_line[-1]) == p_val:
                        # rsplit ensures we remove from the right side
                        temp_line = re.rsplit(re.escape(raw_prices_in_line[-1]), temp_line, 1)[0].strip()
                    elif len(raw_prices_in_line) >= 2 and normalize_price(raw_prices_in_line[-2]) == p_val:
                        temp_line = re.rsplit(re.escape(raw_prices_in_line[-2]), temp_line, 1)[0].strip()

            description = temp_line.strip()
            
            # REQUIREMENT: Handle inconsistent formatting - Remove common item code patterns
            item_code_pattern = r'^[A-Z0-9-]+(?:\sREV\s[A-Z0-9]+)?(?:\s[A-Z0-9-]+)?\s+'
            description = re.sub(item_code_pattern, '', description).strip()

            if description and quantity != "0" and unit_price != "0.00" and cost != "0.00":
                # REQUIREMENT: Extract all required fields into structured format
                item = {
                    "description": description,
                    "quantity": quantity,
                    "unitPrice": unit_price,
                    "cost": cost
                }
                # REQUIREMENT: Group by quantity - Group line items by their quantity
                quote_groups[quantity].append(item)
        except Exception as e:
            continue
            
    # REQUIREMENT: Each group must reflect its own price breakdown
    return format_quote_groups(quote_groups)

def parse_sematool_format(lines: List[str]) -> List[Dict[str, Any]]:
    """
    Parses tabular format quotes like Sematool.
    Assumes clear column headers and data rows.
    
    REQUIREMENT: Handle different variants of Quotes - Sematool tabular format
    """
    items = []
    in_table = False
    header_line_index = -1
    
    # REQUIREMENT: Handle inconsistent casing - use lower() for case-insensitive matching
    for i, line in enumerate(lines):
        if any(header in line.lower() for header in ['item', 'description', 'quantity', 'price', 'amount']):
            header_line_index = i
            in_table = True
            break
            
    if not in_table:
        return []

    for i in range(header_line_index + 1, len(lines)):
        line = lines[i].strip()
        if not line:
            continue
        # REQUIREMENT: Handle inconsistent casing - case-insensitive total detection
        if 'total:' in line.lower():
            break

        # REQUIREMENT: Extract unit prices and costs
        line_prices = extract_prices_from_line(line)
        if len(line_prices) < 2:
            continue

        try:
            cost = line_prices[-1]
            unit_price = line_prices[-2]

            # REQUIREMENT: Extract quantities - Find quantity from non-price numbers
            quantity = "1"
            all_numbers_in_line = re.findall(r'\b\d+\b', line)
            
            # Remove numbers that are part of prices to isolate potential quantities
            temp_line_for_qty = line
            for p_val in line_prices:
                raw_price_match = re.search(re.escape(p_val.replace('.00', '')), temp_line_for_qty)
                if raw_price_match:
                    temp_line_for_qty = temp_line_for_qty[:raw_price_match.start()] + temp_line_for_qty[raw_price_match.end():]
            
            potential_quantities = re.findall(r'\b(\d+)\b', temp_line_for_qty)
            if potential_quantities:
                qty_candidate = potential_quantities[-1]
                if int(qty_candidate) <= 10000:
                    quantity = qty_candidate
            
            # REQUIREMENT: Extract descriptions - Remove prices, quantities, and item numbers
            temp_line = line
            
            # Remove prices from the line
            for p_val in line_prices: # Iterate over normalized prices
                # Find the raw price string in the line that corresponds to the normalized price
                # This is a bit tricky as normalize_price changes the string.
                # A more robust way would be to identify the span of the raw price and remove it.
                # For now, we'll try to remove the normalized value from the temp_line.
                # This might not be perfect if the normalized price appears elsewhere in description.
                temp_line = re.sub(re.escape(p_val.replace('.00', '')), '', temp_line, flags=re.IGNORECASE, count=1)


            # Remove quantity if it was found
            temp_line = re.sub(r'\b' + re.escape(quantity) + r'\b', '', temp_line, 1)

            # Remove leading item number
            temp_line = re.sub(r'^\s*\d+\s*', '', temp_line, 1)

            description = temp_line.strip()
            # REQUIREMENT: Handle inconsistent formatting - Remove unit indicators
            description = re.sub(r'\s*/EA|\s*/EACH', '', description, flags=re.IGNORECASE).strip()

            if description and quantity != "0" and unit_price != "0.00" and cost != "0.00":
                # REQUIREMENT: Extract all required fields into structured format
                item = {
                    "description": description,
                    "quantity": quantity,
                    "unitPrice": unit_price,
                    "cost": cost
                }
                items.append(item)
        except Exception as e:
            continue
    
    if items:
        # REQUIREMENT: Group by quantity - Aggregate all items into single quote group
        # REQUIREMENT: Each group must reflect its own price breakdown
        total_qty = sum(int(item['quantity']) for item in items)
        total_cost = sum(float(item['cost']) for item in items)
        avg_unit_price = total_cost / total_qty if total_qty > 0 else 0.0
        
        return [{
            "quantity": str(total_qty),
            "unitPrice": f"{avg_unit_price:.2f}",
            "totalPrice": f"{total_cost:.2f}",
            "lineItems": items
        }]
    
    return []

def parse_thirtytwo_machine_format(lines: List[str]) -> List[Dict[str, Any]]:
    """
    Parses quotes in Thirty-Two Machine format, which often have multi-line descriptions
    and a columnar layout where Qty, Rate, Total appear at the end of an item block.
    
    REQUIREMENT: Handle different variants of Quotes - Thirty-Two Machine multi-line format
    """
    quote_groups = defaultdict(list)
    current_item_description_lines = []
    
    header_line_index = -1
    # REQUIREMENT: Handle inconsistent casing - case-insensitive header detection
    for i, line in enumerate(lines):
        if all(h in line.lower() for h in ['description', 'qty', 'rate', 'total']):
            header_line_index = i
            break
            
    if header_line_index == -1:
        return []

    # REQUIREMENT: Handle inconsistent spacing and special characters - robust regex pattern
    line_item_end_pattern = re.compile(
        r'(\d+)\s*"?,\s*"?([\-]?\$?[\d,]+\.?\d*)"?,\s*"?([\-]?\$?[\d,]+\.?\d*)"?\s*$'
    )
    
    for i in range(header_line_index + 1, len(lines)):
        line = lines[i].strip()
        if not line:
            continue
        
        # REQUIREMENT: Handle inconsistent casing - case-insensitive total detection
        if 'total' in line.lower() and (re.search(r'[\$]?[\d,]+\.\d{2}', line) or re.search(r'[\$]?[\d,]+', line)):
            if current_item_description_lines:
                current_item_description_lines = []
            break

        match = line_item_end_pattern.search(line)
        
        if match:
            quantity_raw, unit_price_raw, cost_raw = match.groups()
            
            # REQUIREMENT: Extract quantities, unit prices, and costs
            quantity = quantity_raw
            unit_price = normalize_price(unit_price_raw)
            cost = normalize_price(cost_raw)
            
            description_on_current_line = line[:match.start()].strip()
            
            if description_on_current_line:
                current_item_description_lines.append(description_on_current_line)
            
            # REQUIREMENT: Extract descriptions - Combine multi-line descriptions
            description = ' '.join(current_item_description_lines).strip()
            
            # REQUIREMENT: Handle special characters - Remove quotes and trailing commas
            description = re.sub(r'^"|"$', '', description).strip()
            description = re.sub(r',\s*$', '', description).strip()
            
            if description and quantity != "0" and unit_price != "0.00" and cost != "0.00":
                # REQUIREMENT: Extract all required fields into structured format
                item = {
                    "description": description,
                    "quantity": quantity,
                    "unitPrice": unit_price,
                    "cost": cost
                }
                quote_groups[quantity].append(item)
            
            current_item_description_lines = []
        else:
            # This line is likely a continuation of the description
            current_item_description_lines.append(line)
            
    # REQUIREMENT: Group by quantity - Consolidate all items into single quote group
    # REQUIREMENT: Each group must reflect its own price breakdown
    all_items = []
    for qty_group_items in quote_groups.values():
        all_items.extend(qty_group_items)

    if all_items:
        total_qty = sum(int(item['quantity']) for item in all_items)
        total_cost = sum(float(item['cost']) for item in all_items)
        avg_unit_price = total_cost / total_qty if total_qty > 0 else 0.0
        
        return [{
            "quantity": str(total_qty),
            "unitPrice": f"{avg_unit_price:.2f}",
            "totalPrice": f"{total_cost:.2f}",
            "lineItems": all_items
        }]
    
    return []

def format_quote_groups(quote_groups: Dict[str, List[Dict]]) -> List[Dict[str, Any]]:
    """
    Formats the grouped line items into the final structured JSON output.
    Calculates total quantity, total price, and average unit price for each group.
    
    REQUIREMENT: Each group must reflect its own price breakdown
    REQUIREMENT: Group separate quote options by total quantity
    """
    structured_quotes = []
    
    # Sort groups by quantity for consistent output order
    sorted_quantities = sorted(quote_groups.keys(), key=lambda x: int(x))

    for qty in sorted_quantities:
        items = quote_groups[qty]
        # REQUIREMENT: Each group must reflect its own price breakdown - Calculate totals per group
        total_cost_for_group = sum(float(item['cost']) for item in items)
        total_qty_for_group = sum(int(item['quantity']) for item in items)
        
        avg_unit_price_for_group = total_cost_for_group / total_qty_for_group if total_qty_for_group > 0 else 0.0
        
        # REQUIREMENT: Group separate quote options by total quantity - Create separate group objects
        structured_quotes.append({
            "quantity": str(total_qty_for_group),
            "unitPrice": f"{avg_unit_price_for_group:.2f}",
            "totalPrice": f"{total_cost_for_group:.2f}",
            "lineItems": items
        })
            
    return structured_quotes

def detect_format_and_parse(lines: List[str]) -> List[Dict[str, Any]]:
    """
    Detects the quote format based on keywords in the PDF text
    and applies the appropriate parsing function.
    
    REQUIREMENT: Handle different variants of Quotes - Multiple format detection and parsing
    """
    # REQUIREMENT: Handle inconsistent casing - Convert to uppercase for comparison
    text_content = ' '.join(lines).upper()
    
    # REQUIREMENT: Handle different variants - Format detection order: most specific to most generic
    if 'VTN MANUFACTURING' in text_content:
        print("Detected VTN Manufacturing format.")
        return parse_vtn_format(lines)
    elif 'SEMATOOL' in text_content:
        print("Detected Sematool tabular format.")
        return parse_sematool_format(lines)
    elif 'THIRTY-TWO MACHINE' in text_content or '32 MACHINE+DESIGN' in text_content:
        print("Detected Thirty-Two Machine format.")
        return parse_thirtytwo_machine_format(lines)
    else:
        print("No specific format detected. Attempting generic parsing strategies.")
        # REQUIREMENT: Handle different variants - Try parsers in order of complexity as fallback
        result = parse_vtn_format(lines)
        if not result:
            result = parse_sematool_format(lines)
        if not result:
            result = parse_thirtytwo_machine_format(lines)
        return result

def extract_text_from_pdf(pdf_path: str) -> Tuple[List[str], bool]:
    """
    Extracts text from a PDF file using PyMuPDF.
    Returns a tuple of (lines, success_flag).
    """
    try:
        doc = fitz.open(pdf_path)
        full_text = ""
        for page in doc:
            full_text += page.get_text()
        doc.close()
        
        lines = full_text.split("\n")
        return lines, True
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        return [], False

def process_single_pdf(pdf_path: str, verbose: bool = True) -> Dict[str, Any]:
    """
    Process a single PDF and return results with metadata.
    """
    result = {
        "file": pdf_path,
        "success": False,
        "error": None,
        "quotes": []
    }
    
    if verbose:
        print(f"Processing: {pdf_path}")
    
    if not os.path.exists(pdf_path):
        result["error"] = "File not found"
        if verbose:
            print(f"   Error: File not found")
        return result
    
    lines, extraction_success = extract_text_from_pdf(pdf_path)
    if not extraction_success:
        result["error"] = "Could not extract text from PDF"
        if verbose:
            print(f"   Error: Could not extract text from PDF")
        return result
    
    parsed_data = detect_format_and_parse(lines)
    
    if not parsed_data:
        result["error"] = "No quote data could be extracted"
        if verbose:
            print(f"   Warning: No quote data could be extracted")
        return result
    
    result["success"] = True
    result["quotes"] = parsed_data
    
    if verbose:
        print(f"   Success: Extracted {len(parsed_data)} quote group(s)")
    
    return result

def find_pdf_files(paths: List[str]) -> List[str]:
    """
    Expand paths to find all PDF files.
    Handles individual files, directories, and glob patterns.
    """
    pdf_files = []
    
    for path in paths:
        if os.path.isfile(path) and path.lower().endswith('.pdf'):
            pdf_files.append(path)
        elif os.path.isdir(path):
            dir_pdfs = glob.glob(os.path.join(path, "*.pdf"))
            dir_pdfs.extend(glob.glob(os.path.join(path, "*.PDF")))
            pdf_files.extend(dir_pdfs)
        else:
            glob_matches = glob.glob(path)
            pdf_matches = [f for f in glob_matches if f.lower().endswith('.pdf')]
            pdf_files.extend(pdf_matches)
    
    return sorted(list(set(pdf_files)))

def main():
    parser = argparse.ArgumentParser(
        description="Parse quote PDFs into structured JSON.",
        epilog="""
Examples:
  python quote_parser.py file.pdf              # Single file
  python quote_parser.py *.pdf                 # All PDFs in current dir
  python quote_parser.py quotes/               # All PDFs in quotes/ dir
  python quote_parser.py file1.pdf file2.pdf   # Multiple specific files
  python quote_parser.py quotes/ --out results.json # Custom output file
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("paths", nargs="+", help="PDF file(s), directory, or glob pattern")
    parser.add_argument("--out", help="Output JSON file path", default="parsed_quotes.json")
    parser.add_argument("--pretty", action="store_true", help="Pretty print JSON output")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress progress output")
    parser.add_argument("--separate-files", action="store_true", 
                        help="Create separate JSON files for each PDF instead of one combined file")
    
    args = parser.parse_args()
    
    pdf_files = find_pdf_files(args.paths)
    
    if not pdf_files:
        print("Error: No PDF files found matching the specified paths.")
        return
    
    if not args.quiet:
        print(f"Found {len(pdf_files)} PDF file(s) to process")
        if len(pdf_files) > 5:
            print(f"    First 5: {[os.path.basename(f) for f in pdf_files[:5]]}")
            print(f"    ... and {len(pdf_files) - 5} more")
        else:
            print(f"    Files: {[os.path.basename(f) for f in pdf_files]}")
        print()
    
    all_results = []
    successful_parses = 0
    
    for pdf_file in pdf_files:
        result = process_single_pdf(pdf_file, verbose=not args.quiet)
        all_results.append(result)
        if result["success"]:
            successful_parses += 1
    
    if args.separate_files:
        for result in all_results:
            if result["success"]:
                base_name = Path(result["file"]).stem
                output_file = f"{base_name}_parsed.json"
                
                json_output = json.dumps(result["quotes"], indent=2 if args.pretty else None)
                with open(output_file, "w") as f:
                    f.write(json_output)
                
                if not args.quiet:
                    print(f"Saved: {output_file}")
    else:
        output_data = {
            "summary": {
                "total_files": len(pdf_files),
                "successful_parses": successful_parses,
                "failed_parses": len(pdf_files) - successful_parses
            },
            "results": all_results
        }
        
        json_output = json.dumps(output_data, indent=2 if args.pretty else None)
        
        with open(args.out, "w") as f:
            f.write(json_output)
        
        if not args.quiet:
            print(f"Summary:")
            print(f"    Total files processed: {len(pdf_files)}")
            print(f"    Successful parses: {successful_parses}")
            print(f"    Failed parses: {len(pdf_files) - successful_parses}")
            print(f"Results saved to: {args.out}")
    
    if not args.quiet:
        print("Parsed Quote Data:")
        print("=" * 50)
        
        for result in all_results:
            if result["success"]:
                print(f" {os.path.basename(result['file'])}:")
                print(json.dumps(result["quotes"], indent=2))
            else:
                print(f" Error: {os.path.basename(result['file'])}: {result['error']}")

if __name__ == "__main__":
    main()

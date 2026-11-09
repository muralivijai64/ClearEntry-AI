
import json
import re
from decimal import Decimal, InvalidOperation


# ---------------------------------------------------------
# VALUE NORMALIZATION
# ---------------------------------------------------------

def parse_number(value):
    if value is None or value == "":
        return None

    if isinstance(value, (int, float, Decimal)):
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None

    text = str(value).strip().replace(",", "")
    match = re.search(r"-?\d+(?:\.\d+)?", text)

    if not match:
        return None

    try:
        return Decimal(match.group(0))
    except InvalidOperation:
        return None


def normalize_text(value):
    if value is None:
        return None

    if isinstance(value, dict):
        value = " ".join(
            str(v).strip()
            for v in value.values()
            if v is not None and str(v).strip()
        )

    text = str(value).strip().lower()

    if not text:
        return None

    text = re.sub(r"\s+", " ", text)
    text = text.replace(".", "").replace(",", "")

    return text


def normalize_party_identity(value):
    """
    Extract the core company identity separately from its address.

    Examples:
    Company D, Unit 508, Example Tower, Shanghai, China
    Company D, Shanghai, China

    Both normalize to:
    company d

    This avoids false mismatches caused by different address details.
    """

    if value is None:
        return None

    if isinstance(value, dict):
        value = " ".join(
            str(v).strip()
            for v in value.values()
            if v is not None and str(v).strip()
        )

    text = str(value).strip()

    if not text:
        return None

    # Use the first non-empty line.
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    if not lines:
        return None

    first_line = lines[0]

    # Extract company name before the address.
    company_name = first_line.split(",", 1)[0].strip()

    return normalize_text(company_name)


def normalize_package_type(value):
    text = normalize_text(value)

    if not text:
        return None

    missing_values = {
        "none", "null", "n/a", "na", "not available",
        "not provided", "not specified", "unknown",
        "missing", "not mentioned", "not stated",
        "unavailable", "nil",
    }

    if text in missing_values:
        return None

    aliases = {
        "carton": "cartons",
        "cartons": "cartons",
        "box": "cartons",
        "boxes": "cartons",
        "ctn": "cartons",
        "ctns": "cartons",
        "pallet": "pallets",
        "pallets": "pallets",
    }

    return aliases.get(text, text)


def values_equal_numeric(values, tolerance=Decimal("0.01")):
    parsed = [parse_number(value) for value in values]

    if not parsed or any(value is None for value in parsed):
        return False

    return max(parsed) - min(parsed) <= tolerance


def values_equal_text(values):
    normalized = [normalize_text(value) for value in values]

    if not normalized or any(value is None for value in normalized):
        return False

    return len(set(normalized)) == 1


# ---------------------------------------------------------
# DOCUMENT HELPERS
# ---------------------------------------------------------

def get_extraction(document):
    if not isinstance(document, dict):
        return {}

    extraction = (
        document.get("extraction")
        or document.get("extracted_data")
        or {}
    )

    if isinstance(extraction, str):
        try:
            extraction = json.loads(extraction)
        except (json.JSONDecodeError, TypeError):
            return {}

    if not isinstance(extraction, dict):
        return {}

    nested = extraction.get("extracted_data")

    if isinstance(nested, dict):
        return nested

    return extraction


def get_document_type(document):
    if not isinstance(document, dict):
        return None

    value = document.get("document_type") or document.get("type")

    if not value:
        return None

    value = str(value).strip().lower()

    aliases = {
        "commercial_invoice": "invoice",
        "invoice": "invoice",
        "packing list": "packing_list",
        "packing-list": "packing_list",
        "packing_list": "packing_list",
        "bill of lading": "bill_of_lading",
        "bill-of-lading": "bill_of_lading",
        "bol": "bill_of_lading",
        "bill_of_lading": "bill_of_lading",
    }

    return aliases.get(value, value)


def latest_extracted_documents(documents):
    """
    main.py supplies documents ordered by descending ID.

    Sort by document_id here as an additional safeguard.
    The highest ID is the newest uploaded document.
    """

    valid_documents = [
        document
        for document in documents
        if isinstance(document, dict)
    ]

    def document_sort_key(document):
        document_id = document.get("document_id") or document.get("id")

        try:
            return int(document_id)
        except (TypeError, ValueError):
            return -1

    valid_documents.sort(
        key=document_sort_key,
        reverse=True,
    )

    latest = {}

    for document in valid_documents:
        document_type = get_document_type(document)

        if document_type not in {
            "invoice",
            "packing_list",
            "bill_of_lading",
        }:
            continue

        if document_type in latest:
            continue

        extraction = get_extraction(document)

        if extraction:
            latest[document_type] = extraction

    return latest


def get_line_items(extraction):
    items = extraction.get("line_items")

    if not isinstance(items, list):
        return []

    return [
        item for item in items
        if isinstance(item, dict)
    ]


def get_line_item_comparison_value(extraction, field):
    """
    Read item fields from line_items.

    Multiple item values are sorted before comparison so that
    different line-item ordering does not create a false mismatch.
    """

    items = get_line_items(extraction)

    if not items:
        # Backward compatibility with older extraction formats.
        fallback_fields = {
            "quantity": (
                "total_item_quantity",
                "total_quantity",
            ),
            "hsn": ("hsn",),
            "description": ("item_description",),
        }

        for key in fallback_fields.get(field, ()):
            value = extraction.get(key)

            if value not in (None, ""):
                return value

        return None

    values = []

    for item in items:
        value = item.get(field)

        if value in (None, ""):
            return None

        values.append(value)

    if field == "quantity":
        parsed_values = [parse_number(value) for value in values]

        if any(value is None for value in parsed_values):
            return None

        # Preserve individual line-item quantities.
        return "|".join(
            str(value.normalize())
            for value in sorted(parsed_values)
        )

    normalized_values = [
        normalize_text(value)
        for value in values
    ]

    if any(value is None for value in normalized_values):
        return None

    return " | ".join(sorted(normalized_values))


# ---------------------------------------------------------
# VALIDATION CHECK CREATION
# ---------------------------------------------------------

def add_check(
    checks,
    field,
    invoice_value,
    packing_list_value,
    bill_of_lading_value=None,
    status="PENDING",
    message="",
):
    checks.append({
        "field": field,
        "invoice_value": invoice_value,
        "packing_list_value": packing_list_value,
        "bill_of_lading_value": bill_of_lading_value,
        "status": status,
        "message": message,
    })


def compare_three_numeric(
    checks,
    field,
    invoice_value,
    packing_list_value,
    bill_of_lading_value,
    tolerance=Decimal("0.01"),
):
    values = [
        invoice_value,
        packing_list_value,
        bill_of_lading_value,
    ]

    if any(value is None or value == "" for value in values):
        add_check(
            checks, field,
            invoice_value, packing_list_value, bill_of_lading_value,
            "PENDING",
            "A required value is missing from one or more documents.",
        )
        return

    parsed = [parse_number(value) for value in values]

    if any(value is None for value in parsed):
        add_check(
            checks, field,
            invoice_value, packing_list_value, bill_of_lading_value,
            "PENDING",
            "One or more values could not be interpreted as numbers.",
        )
        return

    difference = max(parsed) - min(parsed)

    if difference <= tolerance:
        add_check(
            checks, field,
            invoice_value, packing_list_value, bill_of_lading_value,
            "MATCH",
            "Values agree across the invoice, packing list and Bill of Lading.",
        )
    else:
        add_check(
            checks, field,
            invoice_value, packing_list_value, bill_of_lading_value,
            "MISMATCH",
            f"Values differ across the three documents. Maximum difference: {difference}. Human review required.",
        )


def compare_three_text(
    checks,
    field,
    invoice_value,
    packing_list_value,
    bill_of_lading_value,
):
    values = [
        invoice_value,
        packing_list_value,
        bill_of_lading_value,
    ]

    if any(value is None or value == "" for value in values):
        add_check(
            checks, field,
            invoice_value, packing_list_value, bill_of_lading_value,
            "PENDING",
            "A required value is missing from one or more documents.",
        )
        return

    if values_equal_text(values):
        add_check(
            checks, field,
            invoice_value, packing_list_value, bill_of_lading_value,
            "MATCH",
            "Values agree across all three documents.",
        )
    else:
        add_check(
            checks, field,
            invoice_value, packing_list_value, bill_of_lading_value,
            "MISMATCH",
            "Values differ across the three documents. Human review required.",
        )


def compare_three_parties(
    checks,
    field,
    invoice_value,
    packing_list_value,
    bill_of_lading_value,
):
    """
    Compare core company identities instead of complete addresses.

    Additional address details are allowed.

    Different company identities remain mismatches.
    Missing party information remains pending.
    """

    values = [
        invoice_value,
        packing_list_value,
        bill_of_lading_value,
    ]

    if any(value is None or value == "" for value in values):
        add_check(
            checks, field,
            invoice_value, packing_list_value, bill_of_lading_value,
            "PENDING",
            "A required party name is missing from one or more documents.",
        )
        return

    normalized = [
        normalize_party_identity(value)
        for value in values
    ]

    if any(value is None for value in normalized):
        add_check(
            checks, field,
            invoice_value, packing_list_value, bill_of_lading_value,
            "PENDING",
            "One or more party names could not be interpreted.",
        )
        return

    if len(set(normalized)) == 1:
        add_check(
            checks, field,
            invoice_value, packing_list_value, bill_of_lading_value,
            "MATCH",
            "Company identities agree across all three documents. "
            "Additional address details are permitted.",
        )
    else:
        add_check(
            checks, field,
            invoice_value, packing_list_value, bill_of_lading_value,
            "MISMATCH",
            "Company identities differ across the documents. "
            "Human review required.",
        )


def compare_two_numeric(
    checks,
    field,
    invoice_value,
    packing_list_value,
    bill_of_lading_value=None,
    tolerance=Decimal("0.01"),
):
    if invoice_value in (None, "") or packing_list_value in (None, ""):
        add_check(
            checks, field,
            invoice_value, packing_list_value, bill_of_lading_value,
            "PENDING",
            "A value is missing from the invoice or packing list.",
        )
        return

    first = parse_number(invoice_value)
    second = parse_number(packing_list_value)

    if first is None or second is None:
        add_check(
            checks, field,
            invoice_value, packing_list_value, bill_of_lading_value,
            "PENDING",
            "One or more values could not be interpreted as numbers.",
        )
        return

    if abs(first - second) <= tolerance:
        add_check(
            checks, field,
            invoice_value, packing_list_value, bill_of_lading_value,
            "MATCH",
            "Values agree between the invoice and packing list.",
        )
    else:
        add_check(
            checks, field,
            invoice_value, packing_list_value, bill_of_lading_value,
            "MISMATCH",
            "Invoice and packing list values differ. Human review required.",
        )


def compare_two_text(
    checks,
    field,
    invoice_value,
    packing_list_value,
    bill_of_lading_value=None,
):
    if invoice_value in (None, "") or packing_list_value in (None, ""):
        add_check(
            checks, field,
            invoice_value, packing_list_value, bill_of_lading_value,
            "PENDING",
            "A value is missing from the invoice or packing list.",
        )
        return

    if values_equal_text([invoice_value, packing_list_value]):
        add_check(
            checks, field,
            invoice_value, packing_list_value, bill_of_lading_value,
            "MATCH",
            "Values agree between the invoice and packing list.",
        )
    else:
        add_check(
            checks, field,
            invoice_value, packing_list_value, bill_of_lading_value,
            "MISMATCH",
            "Invoice and packing list values differ. Human review required.",
        )


# ---------------------------------------------------------
# SHIPMENT VALIDATION
# ---------------------------------------------------------

def validate_shipment_documents(documents):
    """
    Validate the latest invoice, packing list and Bill of Lading.

    Party names:
        Compare core company identities separately from addresses.

    Package type:
        Required in the invoice and packing list.
        Missing BOL package type is not applicable when the
        invoice and packing list agree.

    Gross weight:
        Must agree across all three documents.

    Net weight:
        Must agree between invoice and packing list.

    Export:
        Requires all three documents and no mismatches or pending checks.
    """

    extracted = latest_extracted_documents(documents)

    invoice = extracted.get("invoice", {})
    packing = extracted.get("packing_list", {})
    bol = extracted.get("bill_of_lading", {})

    documents_found = {
        "invoice": bool(invoice),
        "packing_list": bool(packing),
        "bill_of_lading": bool(bol),
    }

    checks = []

    missing_documents = [
        name
        for name, found in documents_found.items()
        if not found
    ]

    for name in missing_documents:
        add_check(
            checks,
            f"document_{name}",
            None, None, None,
            "PENDING",
            f"Required document is missing: {name}.",
        )

    # -----------------------------------------------------
    # PARTY INFORMATION
    # Compare company identities, not complete addresses.
    # -----------------------------------------------------

    compare_three_parties(
        checks, "supplier",
        invoice.get("supplier"),
        packing.get("supplier"),
        bol.get("supplier"),
    )

    compare_three_parties(
        checks, "importer",
        invoice.get("importer"),
        packing.get("importer"),
        bol.get("importer"),
    )

    # -----------------------------------------------------
    # PACKAGE COUNT
    # -----------------------------------------------------

    compare_three_numeric(
        checks, "package_count",
        invoice.get("package_count"),
        packing.get("package_count"),
        bol.get("package_count"),
        tolerance=Decimal("0"),
    )

    # -----------------------------------------------------
    # PACKAGE TYPE
    # Invoice and packing list must agree.
    # BOL omission is allowed.
    # -----------------------------------------------------

    invoice_package_type = normalize_package_type(
        invoice.get("package_type")
    )

    packing_package_type = normalize_package_type(
        packing.get("package_type")
    )

    bol_package_type = normalize_package_type(
        bol.get("package_type")
    )

    if not invoice_package_type or not packing_package_type:
        add_check(
            checks, "package_type",
            invoice.get("package_type"),
            packing.get("package_type"),
            bol.get("package_type"),
            "PENDING",
            "Package type must be available in both the invoice and packing list.",
        )

    elif invoice_package_type != packing_package_type:
        add_check(
            checks, "package_type",
            invoice.get("package_type"),
            packing.get("package_type"),
            bol.get("package_type"),
            "MISMATCH",
            "Package type differs between the invoice and packing list.",
        )

    elif not bol_package_type:
        add_check(
            checks, "package_type",
            invoice.get("package_type"),
            packing.get("package_type"),
            bol.get("package_type"),
            "MATCH",
            "Invoice and packing list agree on package type. "
            "BOL does not provide this field, so it is not applicable.",
        )

    elif invoice_package_type == packing_package_type == bol_package_type:
        add_check(
            checks, "package_type",
            invoice.get("package_type"),
            packing.get("package_type"),
            bol.get("package_type"),
            "MATCH",
            "Package type agrees across all three documents.",
        )

    else:
        add_check(
            checks, "package_type",
            invoice.get("package_type"),
            packing.get("package_type"),
            bol.get("package_type"),
            "MISMATCH",
            "Package type differs across the documents.",
        )

    # -----------------------------------------------------
    # WEIGHT AND MEASUREMENT
    # -----------------------------------------------------

    compare_three_numeric(
        checks, "gross_weight_kg",
        invoice.get("gross_weight_kg"),
        packing.get("gross_weight_kg"),
        bol.get("gross_weight_kg"),
        tolerance=Decimal("0.01"),
    )

    compare_two_numeric(
        checks, "net_weight_kg",
        invoice.get("net_weight_kg"),
        packing.get("net_weight_kg"),
        bol.get("net_weight_kg"),
        tolerance=Decimal("0.01"),
    )

    compare_three_numeric(
        checks, "measurement_cbm",
        invoice.get("measurement_cbm"),
        packing.get("measurement_cbm"),
        bol.get("measurement_cbm"),
        tolerance=Decimal("0.01"),
    )

    # -----------------------------------------------------
    # ITEM QUANTITY
    # -----------------------------------------------------

    invoice_quantity = get_line_item_comparison_value(
        invoice, "quantity"
    )

    packing_quantity = get_line_item_comparison_value(
        packing, "quantity"
    )

    bol_quantity = get_line_item_comparison_value(
        bol, "quantity"
    )

    compare_three_text(
        checks, "total_item_quantity",
        invoice_quantity,
        packing_quantity,
        bol_quantity,
    )

    # -----------------------------------------------------
    # HSN
    # -----------------------------------------------------

    compare_three_text(
        checks, "hsn",
        get_line_item_comparison_value(invoice, "hsn"),
        get_line_item_comparison_value(packing, "hsn"),
        get_line_item_comparison_value(bol, "hsn"),
    )

    # -----------------------------------------------------
    # ITEM DESCRIPTION
    # -----------------------------------------------------

    compare_three_text(
        checks, "item_description",
        get_line_item_comparison_value(invoice, "description"),
        get_line_item_comparison_value(packing, "description"),
        get_line_item_comparison_value(bol, "description"),
    )

    # -----------------------------------------------------
    # INVOICE TOTAL
    # Compare only when both documents provide the value.
    # -----------------------------------------------------

    invoice_total = (
        invoice.get("invoice_total")
        or invoice.get("total_invoice_value")
    )

    packing_total = (
        packing.get("invoice_total")
        or packing.get("total_invoice_value")
    )

    if invoice_total is not None and packing_total is not None:
        compare_two_numeric(
            checks,
            "invoice_total_calculation",
            invoice_total,
            packing_total,
            None,
            tolerance=Decimal("0.01"),
        )

    # -----------------------------------------------------
    # VALIDATION SUMMARY
    # -----------------------------------------------------

    matches = sum(
        1 for check in checks
        if check["status"] == "MATCH"
    )

    mismatches = sum(
        1 for check in checks
        if check["status"] == "MISMATCH"
    )

    pending = sum(
        1 for check in checks
        if check["status"] == "PENDING"
    )

    if mismatches > 0 or pending > 0:
        overall_status = "REVIEW_REQUIRED"
    else:
        overall_status = "CLEAR"

    export_allowed = (
        overall_status == "CLEAR"
        and all(documents_found.values())
    )

    return {
        "overall_status": overall_status,
        "review_required": not export_allowed,
        "summary": {
            "matches": matches,
            "mismatches": mismatches,
            "pending": pending,
            "total_checks": len(checks),
        },
        "documents_found": documents_found,
        "checks": checks,
        "export_allowed": export_allowed,
        "message": (
            "All applicable document checks passed."
            if export_allowed
            else "Shipment requires human review before approval and export."
        ),
    }

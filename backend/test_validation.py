from app.cross_validation import validate_shipment_documents


documents = [
    {
        "document_type": "invoice",
        "document_id": 1,
        "extraction": {
            "package_type": "Cartons",
        },
    },
    {
        "document_type": "packing_list",
        "document_id": 2,
        "extraction": {
            "package_type": "Cartons",
        },
    },
    {
        "document_type": "bill_of_lading",
        "document_id": 4,
        "extraction": {
            "package_type": "Not provided",
        },
    },
]

result = validate_shipment_documents(documents)

package_check = next(
    check for check in result["checks"]
    if check["field"] == "package_type"
)

print("Package type status:", package_check["status"])
print("Message:", package_check["message"])

assert package_check["status"] == "MATCH"

print("PACKAGE TYPE TEST PASSED")
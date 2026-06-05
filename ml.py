import pandas as pd
import re

# =========================
# Extraction Functions
# =========================

def extract_invoice(text):

    if pd.isna(text):
        return None

    text = str(text)

    patterns = [

        # Invoice Number: SIN033500
        r'Invoice\s*Number\s*[:\-]?\s*([A-Za-z0-9\/\-\s]+)',

        # Vendor Invoice Number SIN033500
        r'Vendor\s*Invoice\s*Number\s*[:\-]?\s*([A-Za-z0-9\/\-\s]+)',

        # Invoice number 2023/001605
        r'Invoice\s*number\s*[:\-]?\s*([A-Za-z0-9\/\-\s]+)',

        # Invoice SIN033500
        r'Invoice\s*[:\-]?\s*([A-Za-z0-9\/\-\s]+)'
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            invoice = match.group(1).strip()

            # stop at common labels
            invoice = re.split(
                r'(Invoice\s+Date|PO\s+Number|PO\s+No|Vendor\s+Name|Amount|Currency)',
                invoice,
                flags=re.IGNORECASE
            )[0]

            invoice = invoice.strip()

            if len(invoice) > 0:
                return invoice

    return None


def extract_po(text):

    if pd.isna(text):
        return None

    text = str(text)

    patterns = [

        r'PO\s*Number\s*[:\-]?\s*(\d+)',
        r'PO\s*No\.?\s*[:\-]?\s*(\d+)',
        r'PO\s*[:\-]?\s*(\d+)'

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:
            return match.group(1)

    return None


# =========================
# Read File
# =========================

# Excel
df = pd.read_excel("tickets.xlsx")

# CSV
# df = pd.read_csv("tickets.csv")

# =========================
# Combine Columns
# =========================

df["FULL_TEXT"] = (
    df["Title"].fillna("").astype(str)
    + " "
    + df["Description"].fillna("").astype(str)
)

# =========================
# Apply Functions
# =========================

df["InvoiceNumber"] = df["FULL_TEXT"].apply(extract_invoice)

df["PONumber"] = df["FULL_TEXT"].apply(extract_po)

# =========================
# View Result
# =========================

print(
    df[
        [
            "TicketID",
            "InvoiceNumber",
            "PONumber"
        ]
    ].head()
)

# =========================
# Save Output
# =========================

df.to_excel(
    "output.xlsx",
    index=False
)

print("Completed")

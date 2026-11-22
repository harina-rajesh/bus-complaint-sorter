
"""
BUS COMPLAINT SORTER
Offline Version

Input files:
    complaints.csv
    routes.csv

Classification is performed using local keyword rules.
No API key or internet connection is required.
"""

import csv
import re
from collections import Counter
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent

COMPLAINTS_FILE = BASE_DIR / "complaints.csv"
ROUTES_FILE = BASE_DIR / "routes.csv"
OUTPUT_DIR = BASE_DIR / "outputs"

ALLOWED_CATEGORIES = {
    "delay",
    "crowding",
    "driver",
    "vehicle",
    "route_request",
    "other",
}


def load_csv(file_path, required_columns):
    """Load a CSV file and validate its columns."""

    if not file_path.exists():
        raise FileNotFoundError(
            f"Input file not found: {file_path.name}"
        )

    with file_path.open(
        "r", newline="", encoding="utf-8-sig"
    ) as file:

        reader = csv.DictReader(file)

        if not reader.fieldnames:
            raise ValueError(
                f"{file_path.name} has no header."
            )

        missing = set(required_columns) - set(reader.fieldnames)

        if missing:
            raise ValueError(
                f"Missing columns: {', '.join(sorted(missing))}"
            )

        return list(reader)


def load_routes():
    """Load valid bus route numbers and areas."""

    rows = load_csv(
        ROUTES_FILE,
        {"route", "area"}
    )

    routes = {}

    for row in rows:
        try:
            route_number = int(row["route"].strip())
        except (ValueError, AttributeError):
            continue

        routes[route_number] = row["area"].strip()

    if not routes:
        raise ValueError("No valid routes found.")

    return routes


def find_route_in_complaint(complaint):
    """Extract an explicitly mentioned route number."""

    patterns = [
        r"\broute\s*#?\s*(\d+)\b",
        r"\bbus\s*#?\s*(\d+)\b",
    ]

    found = []

    for pattern in patterns:
        found.extend(
            re.findall(pattern, complaint, re.IGNORECASE)
        )

    numbers = {int(number) for number in found}

    if len(numbers) == 1:
        return numbers.pop()

    return None


def classify_complaint(complaint, valid_routes):
    """Classify a complaint using offline keyword rules."""

    text = complaint.lower()

    category = "other"
    urgent = False

    # Identify route requests first.
    if any(word in text for word in [
        "new stop",
        "new route",
        "pickup point",
        "pick up point",
        "railway station",
        "medavakkam junction",
        "change the pickup",
        "add a stop",
        "increase the number of buses",
        "extra bus",
        "extra buses",
        "extra bus arrange",
    ]):
        category = "route_request"

    # Identify overcrowding.
    elif any(word in text for word in [
        "crowded",
        "crowding",
        "overcrowded",
        "too many students",
        "no space",
        "standing",
        "full",
        "romba crowd",
    ]):
        category = "crowding"

    # Identify delays.
    elif any(word in text for word in [
        "late",
        "delay",
        "delayed",
        "did not arrive",
        "not arrived",
        "pickup time",
        "usual pickup",
        "bus varala",
    ]):
        category = "delay"

    # Identify driver-related complaints.
    elif any(word in text for word in [
        "driver",
        "driving",
        "phone while driving",
        "using the horn",
        "behaves angrily",
        "spoke rudely",
        "rude",
    ]):
        category = "driver"

    # Identify vehicle-related complaints.
    elif any(word in text for word in [
        "ac",
        "air conditioning",
        "window",
        "door",
        "tyre",
        "tire",
        "brake",
        "engine",
        "smoke",
        "seat",
        "broken",
    ]):
        category = "vehicle"

    # Check for safety risks.
    safety_patterns = [
        r"phone.{0,30}driv",
        r"driv.{0,30}phone",
        r"rash driving",
        r"driv.{0,30}fast",
        r"footboard",
        r"nearly hit",
        r"near miss",
        r"brak.{0,30}nearly",
        r"door.{0,30}does not close",
        r"tyre.{0,30}damaged",
        r"tire.{0,30}damaged",
        r"smoke",
        r"dangerous driving",
    ]

    if any(
        re.search(pattern, text)
        for pattern in safety_patterns
    ):
        urgent = True

    # Extract only valid, explicitly mentioned routes.
    route = find_route_in_complaint(complaint)

    if route not in valid_routes:
        route = None

    # Create a short summary.
    words = complaint.split()
    summary = " ".join(words[:12])

    return {
        "category": category,
        "urgent": urgent,
        "route": route,
        "summary": summary,
    }


def write_csv(file_path, rows, fieldnames):
    """Write report data to a CSV file."""

    with file_path.open(
        "w", newline="", encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()
        writer.writerows(rows)


def generate_reports(results, manual_reviews, routes):
    """Generate all output reports."""

    OUTPUT_DIR.mkdir(exist_ok=True)

    result_fields = [
        "id",
        "date",
        "complaint",
        "category",
        "urgent",
        "route",
        "summary",
    ]

    urgent_fields = [
        "id",
        "date",
        "complaint",
        "route",
        "summary",
    ]

    review_fields = [
        "id",
        "date",
        "complaint",
        "reason",
    ]

    write_csv(
        OUTPUT_DIR / "results.csv",
        results,
        result_fields
    )

    urgent_rows = [
        {
            "id": row["id"],
            "date": row["date"],
            "complaint": row["complaint"],
            "route": row["route"],
            "summary": row["summary"],
        }
        for row in results
        if row["urgent"] == "True"
    ]

    write_csv(
        OUTPUT_DIR / "urgent.csv",
        urgent_rows,
        urgent_fields
    )

    write_csv(
        OUTPUT_DIR / "manual_review.csv",
        manual_reviews,
        review_fields
    )

    category_counts = Counter(
        row["category"] for row in results
    )

    urgent_count = sum(
        row["urgent"] == "True"
        for row in results
    )

    route_counts = Counter(
        row["route"]
        for row in results
        if row["route"] != ""
    )

    summary_lines = [
        "BUS COMPLAINT SORTER SUMMARY",
        "============================",
        "Classification Mode: OFFLINE KEYWORD RULES",
        f"Total complaints: {len(results) + len(manual_reviews)}",
        f"Successfully classified: {len(results)}",
        f"Manual review: {len(manual_reviews)}",
        "",
        "Complaints by category:",
    ]

    for category in sorted(ALLOWED_CATEGORIES):
        summary_lines.append(
            f"{category:<15} {category_counts[category]}"
        )

    summary_lines.extend([
        "",
        f"Urgent complaints: {urgent_count}",
        "",
        "Complaints by route:",
    ])

    for route_number in sorted(route_counts):
        area = routes.get(
            int(route_number),
            "Area not listed"
        )

        summary_lines.append(
            f"Route {route_number} ({area}): "
            f"{route_counts[route_number]}"
        )

    summary_lines.extend([
        "",
        "Offline keyword rules were used.",
        "Safety-related complaints require human verification.",
        "The transport officer makes all final decisions.",
    ])

    (OUTPUT_DIR / "summary.txt").write_text(
        "\n".join(summary_lines),
        encoding="utf-8"
    )


def main():
    """Run the Bus Complaint Sorter."""

    print("===================================")
    print("       BUS COMPLAINT SORTER")
    print("            OFFLINE MODE")
    print("===================================\n")

    try:
        complaints = load_csv(
            COMPLAINTS_FILE,
            {"id", "date", "complaint"}
        )

        routes = load_routes()

    except (FileNotFoundError, ValueError) as error:
        print(f"Input error: {error}")
        return

    results = []
    manual_reviews = []

    print(f"Loaded complaints: {len(complaints)}")
    print(f"Loaded routes: {len(routes)}\n")

    for row in complaints:

        complaint_id = (row.get("id") or "").strip()
        date = (row.get("date") or "").strip()
        complaint = (row.get("complaint") or "").strip()

        print(f"Processing {complaint_id}...")

        if not complaint:
            manual_reviews.append({
                "id": complaint_id,
                "date": date,
                "complaint": complaint,
                "reason": "Empty complaint; manual review required.",
            })

            print("    Manual review required")
            continue

        data = classify_complaint(
            complaint,
            routes
        )

        results.append({
            "id": complaint_id,
            "date": date,
            "complaint": complaint,
            "category": data["category"],
            "urgent": str(data["urgent"]),
            "route": (
                ""
                if data["route"] is None
                else str(data["route"])
            ),
            "summary": data["summary"],
        })

        status = " URGENT" if data["urgent"] else ""

        print(
            f"    {data['category']:<14}"
            f" route={data['route']}{status}"
        )

    generate_reports(
        results,
        manual_reviews,
        routes
    )

    print("\nProcessing complete!")
    print(f"Successfully classified: {len(results)}")
    print(f"Manual review: {len(manual_reviews)}")
    print(f"Reports saved in: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

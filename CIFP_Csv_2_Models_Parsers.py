import csv
from pathlib import Path

# === PROMPT USER ===
source_file = input("Enter the name of the source CSV file (including .csv): ").strip()
cifp_section_name = input("Enter the Cifp Section Name: ").strip()
cifp_section_id = input("Enter the Cifp Section ID: ").strip()

# === VALIDATE ===
csv_path = Path(source_file)
if not csv_path.exists():
    raise FileNotFoundError(f"CSV file '{source_file}' not found.")

try:
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
except UnicodeDecodeError:
    with open(csv_path, newline='', encoding='cp1252') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

required_fields = ["FieldName", "PropertyName", "ReferenceFieldId", "Index", "Length", "DataType", "Remarks"]
if reader.fieldnames != required_fields:
    raise ValueError("CSV headers must match exactly: " + ", ".join(required_fields))

for row in rows:
    if not row["PropertyName"] and row["FieldName"] not in ("Reserved (Expansion)", "Blank (Spacing)"):
        raise ValueError(f"Missing PropertyName for non-reserved field: {row['FieldName']}")

# === OUTPUT PATHS ===
model_filename = f"{cifp_section_name}CifpDataModel.cs"
parser_filename = f"{cifp_section_name}CifpParser.cs"

# === GENERATE MODEL ===
with open(model_filename, "w", encoding="utf-8") as f:
    f.write("using System;\n")
    f.write("using System.Collections.Generic;\n\n")
    f.write("namespace FAA_DATA_HANDLER.Models.CIFP\n{")
    f.write(f"\n    /// <summary>\n")
    f.write(f"    /// FAACIFP18 File - {cifp_section_name} ({cifp_section_id}) section data\n")
    f.write(f"    /// </summary>\n")
    f.write(f"    /// <remarks>\n")
    f.write(f"    /// ???\n")
    f.write(f"    /// </remarks>\n")
    f.write(f"    public class {cifp_section_name}CifpDataModel\n    {{\n")
    for row in rows:
        field = row["FieldName"]
        prop = row["PropertyName"]
        ref_id = row["ReferenceFieldId"]
        idx = row["Index"]
        length = row["Length"]
        dtype = row["DataType"]
        remarks = row["Remarks"]

        if field in ("Reserved (Expansion)", "Blank (Spacing)"):
            name = "ReservedExpansion" if "Reserved" in field else "BlankSpacing"
            f.write(f"\n        /// <summary>\n")
            f.write(f"        /// {field}\n")
            f.write(f"        /// _Idx: {idx}\n")
            f.write(f"        /// _MaxLength: {length}\n")
            f.write(f"        /// </summary>\n")
            f.write(f"        /// <remarks>\n")
            f.write(f"        /// {remarks}\n")
            f.write(f"        /// </remarks>\n")
            f.write(f"        // public string {name} {{ get; set; }}\n")
        else:
            f.write(f"\n        /// <summary>\n")
            f.write(f"        /// {field}\n")
            f.write(f"        /// _Ref: {ref_id}\n")
            f.write(f"        /// _Idx: {idx}\n")
            f.write(f"        /// _MaxLength: {length}\n")
            f.write(f"        /// _DataType: {dtype}\n")
            f.write(f"        /// </summary>\n")
            f.write(f"        /// <remarks>\n")
            f.write(f"        /// {remarks}\n")
            f.write(f"        /// </remarks>\n")
            f.write(f"        public string? {prop} {{ get; set; }}\n")
    f.write("    }\n}")

# === GENERATE PARSER ===
with open(parser_filename, "w", encoding="utf-8") as f:
    f.write(f"using FAA_DATA_HANDLER.Models.CIFP;\n")
    f.write("using System;\n")
    f.write("using System.Collections.Generic;\n\n")
    f.write("namespace FAA_DATA_HANDLER.Parsers.CIFP\n{")
    f.write(f"\n    public static class {cifp_section_name}CifpParser\n    {{\n")
    f.write(f"        private static readonly List<{cifp_section_name}CifpDataModel> _results = new();\n\n")
    f.write("        public static void Parse(string line)\n        {")
    f.write("\n            if (string.IsNullOrWhiteSpace(line) || line.Length < 4)")
    f.write("\n                return;\n")
    f.write(f"\n            var model = new {cifp_section_name}CifpDataModel\n            {{\n")
    for row in rows:
        prop = row["PropertyName"]
        idx = row["Index"]
        length = row["Length"]
        field = row["FieldName"]

        if not idx or not length:
            continue

        start = int(idx.split(":")[0])
        length_val = int(length)
        if field in ("Reserved (Expansion)", "Blank (Spacing)"):
            name = "ReservedExpansion" if "Reserved" in field else "BlankSpacing"
            f.write(f"                // {field} ??? = line.Substring({start}, {length_val}).Trim()\n")
        else:
            f.write(f"                {prop} = line.Substring({start}, {length_val}).Trim(),\n")
    f.write("            };\n\n")
    f.write("            _results.Add(model);\n")
    f.write("        }\n\n")
    f.write(f"        public static IReadOnlyList<{cifp_section_name}CifpDataModel> GetParsedResults() => _results.AsReadOnly();\n")
    f.write("    }\n}")

print(f"Generated: {model_filename}, {parser_filename}")

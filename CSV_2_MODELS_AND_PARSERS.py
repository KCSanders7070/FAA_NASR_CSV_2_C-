# faa_csv_parser_generator.py

import os
import csv
import re
from collections import defaultdict
from pathlib import Path

# === USER PROMPT ===
def prompt_common_fields():
    while True:
        user_input = input("Enter common fields (comma-separated, no spaces): ")
        if user_input:
            return user_input.split(',')
        print("Invalid input. Try again.")

# === HELPERS ===
def to_pascal_case(s):
    return ''.join(word.capitalize() for word in s.lower().split('_'))

def csv_to_dicts(file_path):
    try:
        with open(file_path, newline='', encoding='utf-8') as f:
            return list(csv.DictReader(f))
    except UnicodeDecodeError:
        with open(file_path, newline='', encoding='cp1252') as f:
            return list(csv.DictReader(f))

def get_datadomain_prefix(files):
    prefixes = [f.name.split('_')[0] for f in files if '_' in f.name]
    return prefixes[0].capitalize() if prefixes else 'Unknown'

def get_class_name(data_domain_id, subtype):
    subtype_pascal = ''.join(word.capitalize() for word in subtype.split('_'))
    return f"{data_domain_id}{subtype_pascal}"

def resolve_type(data_type, max_length, nullable):
    if data_type != 'int':
        return data_type + '?' if nullable else data_type
    if max_length.startswith('(') and max_length.endswith(')'):
        precision = max_length.strip('()').split(',')
        if len(precision) == 2 and precision[1] != '0':
            return 'double?' if nullable else 'double'
        return 'int?' if nullable else 'int'
    return 'int?' if nullable else 'int'

# === MAIN SCRIPT ===
def main():
    cwd = Path.cwd()
    csv_files = [f for f in cwd.glob("*.csv") if not f.name.endswith("CSV_DATA_STRUCTURE.csv")]
    structure_file = next((f for f in cwd.glob("*_CSV_DATA_STRUCTURE.csv")), None)

    if not structure_file:
        print("ERROR: No structure file found.")
        return

    data_domain_id = get_datadomain_prefix(csv_files)
    common_fields = prompt_common_fields()
    common_fields_set = set(f.upper() for f in common_fields)

    structure_rows = csv_to_dicts(structure_file)

    schema = defaultdict(dict)
    for row in structure_rows:
        key = (row['CSV File'].upper(), row['Column Name'].upper())
        schema[key] = {
            'max_length': row['Max Length'],
            'data_type': 'int' if row['Data Type'] == 'NUMBER' else 'string',
            'nullable': row['Nullable'].lower() == 'yes'
        }

    prop_sources = defaultdict(set)
    subtype_to_props = defaultdict(list)

    for file in csv_files:
        subtype = file.stem.replace(data_domain_id.upper() + '_', '')
        rows = csv_to_dicts(file)
        if not rows:
            continue
        for col in rows[0].keys():
            prop_name = to_pascal_case(col)
            prop_sources[(col.upper(), prop_name)].add(file.name)
            subtype_to_props[subtype].append((col, prop_name, file.name))

    duplicate_columns = {
        col.upper(): prop for (col, prop), files in prop_sources.items()
        if len(files) > 1 and col.upper() not in common_fields_set
    }

    # === Duplicates.txt ===
    with open("Duplicates.txt", "w") as f:
        for (col, prop), sources in sorted(prop_sources.items()):
            if len(sources) > 1 and col not in common_fields_set:
                f.write(f"{prop}\n")
                for s in sorted(sources):
                    f.write(f"\t{s}\n")

    # === Models.cs ===
    with open(f"{data_domain_id}Models.cs", "w") as f:
        f.write(f"namespace FAA_DATA_HANDLER.Models.NASR.CSV\n{{\n")
        f.write(f"    public class {data_domain_id}DataModel\n    {{\n")

        # Common Fields
        f.write(f"        #region Common Fields\n")
        f.write(f"        public class CommonFields\n        {{\n")
        for col in common_fields:
            col_up = col.upper()
            prop = to_pascal_case(col_up)
            file_src = f"All {data_domain_id}_*.csv files({col_up})"
            sch = next((v for (k, c), v in schema.items() if c == col_up), None)
            if not sch: continue
            cs_type = resolve_type(sch['data_type'], sch['max_length'], sch['nullable'])
            cs_data_type = cs_type[:-1] if cs_type.endswith('?') else cs_type
            f.write(f"            /// <summary>\n")
            f.write(f"            /// NoTitleYet\n")
            f.write(f"            /// _Src: {file_src}\n")
            f.write(f"            /// _MaxLength: {sch['max_length']}\n")
            f.write(f"            /// _DataType: {cs_data_type}\n")
            f.write(f"            /// _Nullable: {'Yes' if sch['nullable'] else 'No'}\n")
            f.write(f"            /// </summary>\n")
            f.write(f"            /// <remarks>NoRemarksYet</remarks>\n")
            f.write(f"            public {cs_type} {prop} {{ get; set; }}\n\n")
        f.write(f"        }}\n        #endregion\n\n")

        # DataSubtype Fields
        for subtype, props in subtype_to_props.items():
            class_name = get_class_name(data_domain_id, subtype)
            f.write(f"        #region {data_domain_id}_{subtype} Fields\n")
            f.write(f"        public class {class_name} : CommonFields\n        {{\n")
            for col, original_prop, filename in props:
                is_common = col.upper() in common_fields_set
                if is_common:
                    continue
                sch = schema.get((f"{data_domain_id}_{subtype}".upper(), col.upper()))
                if not sch:
                    continue
                cs_type = resolve_type(sch['data_type'], sch['max_length'], sch['nullable'])
                cs_data_type = cs_type[:-1] if cs_type.endswith('?') else cs_type
                is_dup = col.upper() in duplicate_columns
                prop = f"{to_pascal_case(subtype)}{original_prop}" if is_dup else original_prop
                remarks = "PropertyName changed due to identical column name in other " + data_domain_id.upper() + "_*.csv files" if is_dup else "NoRemarksYet"
                f.write(f"            /// <summary>\n")
                f.write(f"            /// NoTitleYet\n")
                f.write(f"            /// _Src: {filename}({col.upper()})\n")
                f.write(f"            /// _MaxLength: {sch['max_length']}\n")
                f.write(f"            /// _DataType: {cs_data_type}\n")
                f.write(f"            /// _Nullable: {'Yes' if sch['nullable'] else 'No'}\n")
                f.write(f"            /// </summary>\n")
                f.write(f"            /// <remarks>{remarks}</remarks>\n")
                f.write(f"            public {cs_type} {prop} {{ get; set; }}\n\n")
            f.write(f"        }}\n        #endregion\n\n")

        f.write(f"    }}\n}}")

    # === Parser.cs ===
    with open(f"{data_domain_id}Parser.cs", "w") as f:
        f.write(f"using FAA_DATA_HANDLER.Models.NASR.CSV;\n")
        f.write(f"using System;\nusing System.Collections.Generic;\nusing System.IO;\n")
        f.write(f"using static FAA_DATA_HANDLER.Models.NASR.CSV.{data_domain_id}DataModel;\n\n")
        f.write(f"namespace FAA_DATA_HANDLER.Parsers.NASR.CSV\n{{\n")
        f.write(f"    public class {data_domain_id}CsvParser\n    {{\n")

        for subtype, props in subtype_to_props.items():
            class_name = get_class_name(data_domain_id, subtype)
            f.write(f"        public {data_domain_id}DataCollection Parse{class_name}(string filePath)\n        {{\n")
            f.write(f"            var result = new {data_domain_id}DataCollection();\n\n")
            f.write(f"            result.{class_name} = FebCsvHelper.ProcessLines(\n")
            f.write(f"                filePath,\n")
            f.write(f"                fields => new {class_name}\n                {{\n")
            for col, original_prop, _ in props:
                sch_key = (f"{data_domain_id}_{subtype}".upper(), col.upper())
                is_common = col.upper() in common_fields_set
                prop = to_pascal_case(col) if is_common else (
                    f"{to_pascal_case(subtype)}{original_prop}" if col.upper() in duplicate_columns else original_prop
                )
                if is_common:
                    f.write(f"                    {prop} = fields[\"{col}\"],\n")
                    continue
                sch = schema.get(sch_key)
                if not sch:
                    continue
                cs_type = resolve_type(sch['data_type'], sch['max_length'], sch['nullable'])
                if cs_type == 'int':
                    f.write(f"                    {prop} = FebCsvHelper.ParseInt(fields[\"{col}\"]),\n")
                elif cs_type == 'int?':
                    f.write(f"                    {prop} = FebCsvHelper.ParseNullableInt(fields[\"{col}\"]),\n")
                elif cs_type == 'double':
                    f.write(f"                    {prop} = FebCsvHelper.ParseDouble(fields[\"{col}\"]),\n")
                elif cs_type == 'double?':
                    f.write(f"                    {prop} = FebCsvHelper.ParseNullableDouble(fields[\"{col}\"]),\n")
                else:
                    f.write(f"                    {prop} = fields[\"{col}\"],\n")
            f.write(f"                }});\n\n")
            f.write(f"            return result;\n        }}\n\n")

        f.write(f"    }}\n\n")
        f.write(f"    public class {data_domain_id}DataCollection\n    {{\n")
        for subtype in subtype_to_props:
            class_name = get_class_name(data_domain_id, subtype)
            f.write(f"        public List<{class_name}> {class_name} {{ get; set; }} = new();\n")
        f.write(f"    }}\n}}")

    # === Program.cs ===
    with open("Program.cs", "w") as f:
        f.write(f'Console.WriteLine("Parsing {data_domain_id} csv files");\n')
        f.write(f"{data_domain_id}CsvParser {data_domain_id.lower()}CsvParser = new {data_domain_id}CsvParser();\n")
        f.write(f"{data_domain_id}DataCollection allParsed{data_domain_id}Data = new {data_domain_id}DataCollection();\n")
        for subtype in subtype_to_props:
            class_name = get_class_name(data_domain_id, subtype)
            f.write(f"allParsed{data_domain_id}Data.{class_name} = {data_domain_id.lower()}CsvParser.Parse{class_name}(Path.Combine(userSelectedSourceDirectory, \"{data_domain_id.upper()}_{subtype}.csv\")).{class_name};\n")
        f.write(f'\nConsole.WriteLine("Generating {data_domain_id}.json");\n')
        f.write(f"Generate{data_domain_id}Json.Generate(allParsed{data_domain_id}Data, userSelectedOutputDirectory);\n")
        f.write(f'Console.WriteLine("{data_domain_id} data created.");\n')

    print("Models.cs, Parser.cs, Program.cs, and Duplicates.txt generated.")

if __name__ == '__main__':
    main()

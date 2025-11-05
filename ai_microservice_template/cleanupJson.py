import re
import json


with open("failed_assets.json", "r") as f:
    lines = f.readlines()

fixed_lines = []

for line in lines:
    if '"MANUFACTURER"' in line:
        prefix, rest = line.split('"MANUFACTURER"', 1)
        colon_index = rest.find(':')
        after_colon = rest[colon_index + 1:]
        
        comma_index = after_colon.find(',')
        if comma_index == -1:
            value = after_colon.strip()
            trailing = ''
        else:
            value = after_colon[:comma_index].strip()
            trailing = after_colon[comma_index:]

        if not value:
            value_fixed = '""'
        else:
            value = value.strip('"')
            value_fixed = '"' + value.replace('"', r'\"') + '"'

        fixed_line = f'{prefix}"MANUFACTURER" : {value_fixed}{trailing}'
        fixed_lines.append(fixed_line)
    else:
        fixed_lines.append(line)


fixed_content = ''.join(fixed_lines)


try:
    data = json.loads(fixed_content)
except json.JSONDecodeError as e:
    print("Error parsing JSON:", e)
    exit(1)


for item in data:
    if "metadata" in item and item["metadata"]:
        try:
            metadata_json = json.loads(item["metadata"])
            item["metadata"] = metadata_json
        except json.JSONDecodeError:
            pass


with open("failed_assets_fixed.json", "w") as f:
    json.dump(data, f, indent=4)

print("JSON pretty-printed in 'failed_assets_fixed.json'!")

import json
import os
import re
from groq import Groq
import time
from dotenv import load_dotenv

load_dotenv()

def countdown(minutes):
    total_seconds = minutes * 60
    while total_seconds:
        mins, secs = divmod(total_seconds, 60)
        timer = f"Cooldown Period {mins:02d}:{secs:02d}"
        print(timer, end='\r')  
        time.sleep(1)
        total_seconds -= 1
    print()  

def reference_urls(tool_results):
    print("\nReference Urls:\n")

    if not tool_results or not tool_results.results:
        print("No reference URLs found.\n")
        return

    # Sort by highest -> lowest score
    results_sorted = sorted(
        tool_results.results,
        key=lambda r: r.score,
        reverse=True
    )

    # Print in neat JSON style
    for r in results_sorted:
        print("{")
        print(f'  "title": "{r.title}",')
        print(f'  "url": "{r.url}",')
        print(f'  "score": {r.score}')
        print("}\n")

def get_children_for_group(json_file, group_name):
    """
    Given a second_level_tree.json and a group name,
    return all nested children as a formatted string.
    If the group has no children, return a message indicating that.
    """

    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    if group_name not in data:
        available = ', '.join(data.keys())
        return f"❌ Group '{group_name}' not found in {json_file}\nAvailable groups: {available}"

    tree = data[group_name]

    # Check if the tree is empty
    if not tree:
        return f"{group_name} has no children"

    def build_children_string(tree, level=0):
        result = ""
        indent = "  " * level
        if isinstance(tree, dict):
            for key, value in tree.items():
                result += f"{indent}- {key}\n"
                result += build_children_string(value, level + 1)
        elif isinstance(tree, list):
            for item in tree:
                if isinstance(item, dict):
                    result += build_children_string(item, level)
                else:
                    result += f"{indent}- {item}\n"
        return result

    children_str = f"\n📂 Children of '{group_name}':\n"
    children_str += build_children_string(tree)
    return children_str

# Load your asset data
with open("failed_assets_fixed.json", "r") as f:
    data = json.load(f)

if not data:
    raise SystemExit("No assets found in failed_assets_fixed.json")

asset = data[0]
model = asset.get("MODEL", "")
manufacturer = asset.get("MANUFACTURER", "")
metadata_dict = asset.get("metadata", {})

try:
    metadata = json.dumps(metadata_dict, indent=4)
except (TypeError, ValueError):
    metadata = str(metadata_dict)


TECH_TYPES = [ "Hardware", "License", "Subscription", "Maintenance", "Virtual Machines", "Freeware", "Certificate" ]
TECH_GROUPS = [
  "3D Design",
  "AV Blank Media",
  "AV Receivers",
  "Accounting",
  "Albums, Frames & Presentation",
  "Amplifiers",
  "Animation",
  "Anti-Spam",
  "Anti-Spyware",
  "Antivirus",
  "Antivirus & Security Software",
  "Arts & Culture",
  "Assorted Accessories",
  "Audio & Video Equipment Mounts",
  "Audio & Video Switches",
  "Authentication Software",
  "Batteries",
  "Blu-ray Players",
  "Books, Manuals & Periodicals",
  "Boomboxes",
  "Bridges & Routers",
  "Browsers",
  "Business & Productivity Software",
  "Business / Economics / Legal",
  "CAD/CAM Software",
  "CD Decks",
  "CD/DVD Authoring",
  "CD/DVD Wallets",
  "CRM Software",
  "Cables",
  "Calculators & Typewriters",
  "Camcorder Accessories",
  "Camcorders",
  "Camera Accessories",
  "Camera Lenses",
  "Car Accessories",
  "Car Amplifiers & Equalizers",
  "Car Audio",
  "Car Audio & Video Cables",
  "Car Speakers",
  "Car Video",
  "Cash Drawers",
  "Cellular Phones",
  "Cleaning Accessories",
  "Compact AV Systems",
  "Computer / Math / Logic",
  "Computer Based Training",
  "Computer Speakers",
  "Controller Cards",
  "Converters",
  "DVD / HDD Combos",
  "DVD Players",
  "DVD Recorders",
  "DVD/VCR Combos",
  "DVRs",
  "Darkroom",
  "Data Analysis & Content Management",
  "Databases & Tools",
  "Desktop Accessories",
  "Desktop Publishing",
  "Desktops & Workstations",
  "Developer Tools",
  "Digital Cameras",
  "Digital Signage Players",
  "Digital Voice Recorders",
  "Disc Duplicators",
  "Disk Arrays",
  "Docking Cradles",
  "Document Management Software",
  "E-commerce Software",
  "Early Learning",
  "Email Software",
  "Encryption Software",
  "Encyclopedia",
  "Equalizers",
  "External Storage Enclosures",
  "Fans & Cooling Systems",
  "Fax Software",
  "File Managers",
  "File Transfer",
  "Film Cameras",
  "Finance / Tax Preparation",
  "Firewalls",
  "Flash Memory",
  "Fonts & Font Tools",
  "Foreign Languages & Translation",
  "GIS & Map Creation Software",
  "GPS",
  "GPS Software",
  "Game Controllers",
  "Game Utilities",
  "Gamer Clothing",
  "Graphics & Photo Editing",
  "Graphics & Publishing Software",
  "Groupware",
  "HD DVD Players",
  "HSE management",
  "Handheld Accessories",
  "Hard Drives",
  "Headphones",
  "Headphones Accessories",
  "Headphones Cables",
  "Headphones Carrying Cases",
  "HelpDesk & Inventory Systems",
  "Home Audio Accessories",
  "Home Media Players",
  "Home Speakers",
  "Hubs & Switches",
  "Human Resources",
  "IP TV",
  "IP Telephony",
  "Ink Cartridges",
  "Instant Communication Software",
  "Interactive Whiteboards",
  "Internet Filtering Software",
  "Internet Utilities",
  "Intrusion Detection/Prevention",
  "KVM",
  "Keyboards & Mice",
  "LNB",
  "Labeling / Barcode Software",
  "Large Format Displays",
  "Learning Management",
  "Legacy Drives",
  "Lighting & Studio",
  "Linux / Unix",
  "MP3 Players",
  "Mac Software",
  "MacOS",
  "Map/Atlas/Travel",
  "Marine Electronics",
  "Memory Upgrades / RAM",
  "Microcassette Recorders",
  "Microphones",
  "Microsoft Windows",
  "Miscellaneous Drives",
  "Mobile Device Management",
  "Mobile Device Synchronization",
  "Modems",
  "Monitors",
  "Motherboards",
  "Movies & TV Shows",
  "Multi-Purpose Bags",
  "Multimedia Players",
  "Music",
  "Natural Sciences",
  "Network & Enterprise Management",
  "Network Adapters",
  "Network Appliance Software",
  "Network Audio Components",
  "Network Cabling",
  "Network Security",
  "Network Software",
  "Network Storage",
  "Network Utilities",
  "Notebooks & Accessories",
  "OCR Software",
  "OS Suites",
  "Office Application Suites",
  "Office Products",
  "Office Software",
  "Optical Drives",
  "Outdoor Speakers",
  "Output Accessories",
  "PC Maintenance",
  "POS Machines",
  "Photo / Video / Sound Libraries",
  "Point Of Sale Equipment",
  "Policy Management",
  "Portable CD Players",
  "Portable Cassette Players & Recorders",
  "Portable DVD & Blu-ray Players",
  "Portable MD Players",
  "Portable Media Players",
  "Portable Player Accessories",
  "Portable Player Cables",
  "Portable Player Carrying Cases",
  "Portable Player Power",
  "Portable Radios",
  "Portable Speakers",
  "Power Protection Devices",
  "Presentation",
  "Print Management",
  "Print Servers",
  "Printers",
  "Programming Languages",
  "Project Management",
  "Projectors",
  "Projectors & Accessories",
  "Public Address Speakers",
  "Quad Processors & Video Multiplexers",
  "Radio Tuners",
  "Recovery / Backup Software",
  "Religion",
  "Remote Access Software",
  "Remote Controls",
  "Satellite & Cable TV Accessories",
  "Satellite Dishes",
  "Satellite Radio",
  "Satellite Receivers",
  "Satellite Receivers With HDD",
  "Satellite TV Systems",
  "Scan Management",
  "Scanners",
  "Schedule & Contact Management",
  "Security & Privacy Filters",
  "Security Cables & Locks",
  "Security Cameras",
  "Security Chips, Tokens & Smart Cards",
  "Security DVRs",
  "Server Accessories",
  "Servers",
  "Signal Extenders",
  "Single-board Computers & Accessories",
  "Software Suites",
  "Sound Bars",
  "Sound Editing & Recording",
  "Spare Parts",
  "Speaker Accessories",
  "Speaker Cables",
  "Speaker Support Hardware",
  "Speakerphones",
  "Spreadsheets",
  "Storage Accessories",
  "Storage Cables",
  "Storage Media",
  "System Cases",
  "System Deployment & Migration Software",
  "TV & Monitor Mounts",
  "TV & Radio Antennas",
  "TV accessories",
  "Tablets & eBook readers",
  "Tape Backup",
  "Tape Decks",
  "Telephone Accessories",
  "Telephones",
  "Time Lapse VCR",
  "Transceivers & Multiplexers",
  "Turntable Accessories",
  "Turntables",
  "Two-Way Radios",
  "Unix / Linux Software",
  "Upconverting DVD Players",
  "Utilities",
  "Utilities Suites",
  "Video Converters",
  "Video Editing",
  "Video Editing Controllers, Mixers & Titlers",
  "Video Servers",
  "Video Surveillance Accessories",
  "Video Surveillance Solutions",
  "Virtualization Software",
  "VoIP",
  "Voice Recognition / Text-to-Speech",
  "Wearable Electronics",
  "Web Conferencing Software",
  "Web Design / Publishing",
  "Web Development",
  "Wireless",
  "Wireless Audio & Video Sharing",
  "Word Processing",
  "eCommerce Solutions",
  "iPod Accessories",
  "iPod Speakers",
  "iPods"
]

TECH_GROUPS_JSON = json.dumps(TECH_GROUPS, indent=2)

prompt = f"""
    The data provided is of an asset which we were unable to match or identify.

    This is the data we received:
        Model: {model}
        Manufacturer: {manufacturer}
        Metadata: {metadata}

    From the following list of tech groups, choose the **one group** that best represents the asset.
    - Return **exactly one value** from the list.
    - If there is not enough information, return **null**.
    - Return **only the chosen value**, no explanations or extra text.

    {TECH_GROUPS_JSON}
"""

# Initialize Groq client
client = Groq(
    api_key=os.getenv("GROQ_API_KEY"),
    default_headers={
        "Groq-Model-Version": "latest",
    }
)

instructions = """
   
    You role is to strictly identify the tech group.

    1. Output ONLY the final answer.
    2. DO NOT include reasoning.
    3. DO NOT include explanations.
    4. DO NOT include markdown.
    5. DO NOT repeat the question.
    6. If you include anything except the exact required answer, your output is INVALID.

    You must follow these rules and your response should be less than 5 words anymore your output is INVALID

    You should not add headers like **Chosen Tech Group:** Docking Cradles it should only return it simple like Docking Cradles

    Things to consider in response:
        1. Sometimes in the metadata it might mention docking but the device maybe something else.

        For example, the passed asset data has 

        "TYPE": "docking station",
        "MODEL": "Inspiron 7472",
        "MANUFACTURER": "Dell",

        Now based on the data this is actually a laptop Inspiron 7472

"""

# Send prompt to Groq
completion = client.chat.completions.create(
    model="groq/compound",
    messages=[
        {"role": "system", "content": instructions},
        {"role": "user", "content": prompt}
    ],
    temperature=1,
    max_completion_tokens=3,
    top_p=1,
    stream=False,
    stop=None,
    #compound_custom={"tools":{"enabled_tools":["web_search","code_interpreter","visit_website"]}}
)

# Get the response text
response = completion.choices[0].message.content

tech_group_result = response

print("Groq chose this as the tech group: ", tech_group_result)
print()

tech_group_json = re.sub(r'\W+', '_', tech_group_result) + ".json"

print("Corresponding JSON file: ", tech_group_json)
print()

children_output = get_children_for_group("second_level_tree.json", tech_group_result)
print(children_output)

json_folder = "techgroup_jsons"
json_file_path = os.path.join(json_folder, tech_group_json)

with open(json_file_path, "r", encoding="utf-8") as f:
    schema_data = json.load(f)

cleaned_schema = json.dumps(schema_data, indent=2)

promptTwo = f"""
    
    The data provided is of an asset which we were unable to match or identify.
    
    This is the data we received:
        Model: {model}
        Manufacturer: {manufacturer}
        Metadata: {metadata}

    Using this data help to find the exact model. 
    
    If you are unable to find the exact model find the closest results.

    Return these pieces of data

    Brand/Manufacturer/Vendor: (e.g. Apple or ASUS)
    Brand Country: 
    Brand Domain: (e.g. https://www.asus.com/ or https://www.apple.com/)
    Tech Type: Fill this field using this list: {TECH_TYPES}
    
    Product SKU/ID: 
    Product Description: 
    Product Features: Only list 5 features (e.g., RAM, CPU, Display, Refresh Rate, etc.)

    Make sure to fill this json file and enrich the data

    {cleaned_schema}
"""
# WAIT 1 minute BEFORE SENDING NEXT PROMPT
countdown(1)
# Send prompt to Groq
completion = client.chat.completions.create(
    model="groq/compound",
    messages=[
      {
        "role": "user",
        "content": promptTwo
      }
    ],
    temperature=1,
    max_completion_tokens=1024,
    top_p=1,
    stream=False,
    stop=None,
    compound_custom={"tools":{"enabled_tools":["web_search","visit_website"]}}
)

# Get the response text
final_result = completion.choices[0].message.content

if completion.choices[0].message.executed_tools: 
    tools_used = completion.choices[0].message.executed_tools[0].search_results

print()
print(f"\n--- Final Result for First Asset ---\n{final_result}\n")
print()

reference_urls(tools_used)


output_folder = "groq_output"
os.makedirs(output_folder, exist_ok=True)

md_filename = os.path.join(output_folder, "asset_1.md")

md_content = "# Asset Resolution Output\n\n"
md_content += "## Final Result\n\n"
md_content += f"{final_result}\n\n"

md_content += "## Reference URLs\n\n"

if tools_used and tools_used.results:
    results_sorted = sorted(tools_used.results, key=lambda r: r.score, reverse=True)
    for item in results_sorted:
        md_content += f"- **{item.title}**\n"
        md_content += f"  - URL: {item.url}\n"
        md_content += f"  - Score: {item.score}\n\n"
else:
    md_content += "_No reference URLs found._\n"

with open(md_filename, "w", encoding="utf-8") as md_file:
    md_file.write(md_content)

print(f"Markdown file saved at: {md_filename}")


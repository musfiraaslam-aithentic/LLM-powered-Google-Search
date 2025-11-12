import json
from google import genai
from google.genai import types
import os
from dotenv import load_dotenv 
import time
import re

# Load environment variables
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    raise SystemExit("GOOGLE_API_KEY not set in environment!")

# Initialize client
client = genai.Client()

# Rate limits
requests_per_minute = 10
tokens_per_minute = 250000
requests_per_day = 250
ideal_tokens_per_request = tokens_per_minute / requests_per_minute

# Enable Google Search tool
grounding_tool = types.Tool(
    google_search=types.GoogleSearch()
)

# Configure generation with the grounding tool
config = types.GenerateContentConfig(
    tools=[grounding_tool]
)

def model_call_with_retry(prompt, max_retries=5, base_delay=2.0, max_delay=30.0):
    """
    Calls the model with retries using exponential backoff.
    
    Args:
        prompt (str): The prompt to send to the model.
        max_retries (int): Maximum number of retries.
        base_delay (float): Initial delay between retries in seconds.
        max_delay (float): Maximum delay between retries in seconds.
    
    Returns:
        response: The model response.
    
    Raises:
        Exception: If all retries fail.
    """
    for attempt in range(max_retries + 1):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=config,
            )
            return response
        except Exception as e:
            if attempt == max_retries:
                raise  # all retries failed
            delay = min(base_delay * (2 ** attempt), max_delay)
            print(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay:.1f} seconds...")
            time.sleep(delay)

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

def add_citations_at_end(response):
    text = response.text
    supports = response.candidates[0].grounding_metadata.grounding_supports
    chunks = response.candidates[0].grounding_metadata.grounding_chunks
    
    citation_dict = {}
    for support in supports:
        for i in support.grounding_chunk_indices:
            if i < len(chunks):
                uri = chunks[i].web.uri
                title = getattr(chunks[i].web, 'title', uri)
                citation_dict[i] = (uri, title)
    
    if citation_dict:
        citations_text = "\n\nReference Urls:\n"
        for idx, (uri, title) in enumerate(citation_dict.values(), start=1):
            citations_text += f"[{idx}] {title} - {uri}\n"
        text += citations_text
    
    return text



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

# Load failed asset data
with open("failed_assets_fixed.json", "r") as f:
    data = json.load(f)


for i, asset in enumerate(data, start=1):

    model = asset.get("MODEL", "")
    manufacturer = asset.get("MANUFACTURER", "")
    metadata_dict = asset.get("metadata", {})

    try:
        metadata = json.dumps(metadata_dict, indent=4)
    except (TypeError, ValueError):
        metadata = str(metadata_dict) 

    TECH_GROUPS_JSON = json.dumps(TECH_GROUPS, indent=2)
    TECH_TYPES_JSON = json.dumps(TECH_TYPES, indent=2)

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

    #print("This is the prompt\n", prompt)
    #print()

    # There is no charge or quota restriction for using the CountTokens API. 
    # The maximum quota for the CountTokens API is 3000 requests per minute.
    # https://docs.cloud.google.com/vertex-ai/generative-ai/docs/multimodal/get-token-count
    
    token_info = client.models.count_tokens(
        model="gemini-2.5-flash",  
        contents=prompt
    )
    
    total_tokens = token_info.total_tokens  

    if total_tokens < ideal_tokens_per_request:
        response = model_call_with_retry(prompt)
        
        tech_group_result = response.text

        print("Gemini chose this as the tech group: ", tech_group_result)
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
            Tech Type: Fill this field using this list: {TECH_TYPES_JSON}
            
            Product SKU/ID: 
            Product Description: 
            Product Features: Only list 5 features (e.g., RAM, CPU, Display, Refresh Rate, etc.)

            Make sure to fill this json file and enrich the data

            {cleaned_schema}
        """

        response = model_call_with_retry(promptTwo)
        final_result = add_citations_at_end(response)

        # Debugging print statements
        print(f"\n--- Result for Asset #{i} ---\n{final_result}\n")
        print(f"Total Tokens in Prompt: {total_tokens}/{ideal_tokens_per_request}")
        print("=" * 100)

   
        time.sleep(10) 

    else:
        print("Prompt is too large skipping asset.")
        continue
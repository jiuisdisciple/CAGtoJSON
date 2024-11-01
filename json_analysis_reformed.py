import json
import pandas as pd

# Load the data from the JSON file
with open('D:/STUDY/2024-1.5/240627_CAGtoJSON/reformed/CSVtoJSON_240910.json') as file:
    data = [json.loads(line) for line in file if line.strip()]

# Extract the JSON_Revised field and parse the JSON strings within it
coronary_angiography_data = []
for entry in data:
    try:
        parsed_entry = json.loads(entry["review"].replace("```json", "").replace("```", ""))
        if isinstance(parsed_entry, dict):
            coronary_angiography_data.append(parsed_entry)
        else:
            coronary_angiography_data.append({})
    except (json.JSONDecodeError, KeyError) as e:
        print(f"Error parsing JSON: {e}")
        coronary_angiography_data.append({})

# Extract patient_number and date_of_angiography
patient_numbers = [entry['patient_number'] for entry in data]
sex = [entry.get('sex', 'N/A') for entry in data]
age = [entry.get('age', 'N/A') for entry in data]
review = coronary_angiography_data
 
dates_of_angiography = [entry['date_of_angiography'] for entry in data]

# Add "cag" and "pci" columns
for entry in coronary_angiography_data:
    entry["cag"] = bool(entry.get("coronary_angiography"))
    entry["pci"] = bool(entry.get("pci_details"))



# Define a function to determine the type based on lesion characteristics
def determine_type(lesion_characteristics):
    type_c_criteria = {"diffuse", "total occlusion", "CTO"}
    type_b2_criteria = {"subtotal occlusion", "ISR"}
    type_b_criteria = {"tubular", "eccentric", "calcification", "moderate calcification", "severe calcification", "os", "bifurcation", "irregular"}


    if type_c_criteria & set(lesion_characteristics):
        return "C"
    if type_b2_criteria & set(lesion_characteristics):
        return "B2"
    elif len(type_b_criteria & set(lesion_characteristics)) >= 2:
        return "B2"
    elif len(type_b_criteria & set(lesion_characteristics)) == 1:
        return "B1"
    else:
        return "A"


# Define function to categorize vessel disease
def categorize_vessel_disease(segment_codes, previous_stents):
    rca_segments = {"1", "2", "3", "4", "16", "16a", "16b", "16c"}
    lad_segments = {"6", "7", "8", "9", "9a", "10", "10a"}
    lcx_segments = {"11", "12", "12a", "12b", "13", "14", "14a", "14b", "15"}
    vessel_disease = set()

    combined_codes = set(segment_codes) | set(previous_stents)
    
    for code in combined_codes:
        if code in rca_segments:
            vessel_disease.add("RCA")
        if code in lad_segments:
            vessel_disease.add("LAD")
        if code in lcx_segments:
            vessel_disease.add("LCx")
        if code == "5":
            vessel_disease.add("LM")
    
    return list(vessel_disease)


def extract_segments_with_types(entry):
    lesions = entry.get("coronary_angiography", {}).get("lesions", [])
    segments_with_types = [
        [segment_code, determine_type(lesion.get("lesion_characteristics", []))]
        for lesion in lesions
        if lesion.get("luminal_narrowing_percentage") is not None and lesion.get("luminal_narrowing_percentage", 0) >= 50
        for segment_code in lesion.get("segment_code", [])
    ]
    return merge_segment_codes(segments_with_types)


def merge_segment_codes(segments_with_types):
    hierarchy = {"A": 0, "B1": 1, "B2": 2, "C": 3}
    merged_segments = {}
    
    for segment_code, lesion_type in segments_with_types:
        if segment_code in merged_segments:
            merged_segments[segment_code] = max(merged_segments[segment_code], lesion_type, key=lambda t: hierarchy[t])
        else:
            merged_segments[segment_code] = lesion_type
    
    return [[code, type_] for code, type_ in merged_segments.items()]

# Apply the extract_segments_with_types function to all entries
all_segment_codes_with_types = [extract_segments_with_types(entry) for entry in coronary_angiography_data]

# Define the function to determine anatomical_dx
def determine_anatomical_dx(vessel_disease):
    if "LM" in vessel_disease:
        lm_count = 1
        nvd_count = len([v for v in vessel_disease if v in {"RCA", "LCx", "LAD"}])
        if nvd_count > 0:
            return f"LM+{nvd_count}VD"
        return "LM"
    else:
        nvd_count = len([v for v in vessel_disease if v in {"RCA", "LCx", "LAD"}])
        return f"{nvd_count}VD" if nvd_count > 0 else "N/A"

def extract_previous_stent(entry):
    if not entry.get("cag"):
        return [["N/A"]]
    previous_stents = entry.get("previous_stents_rearrange", [])
    return [[stent.get("device", "N/A"), stent.get("diameter_mm", "N/A"), stent.get("length_mm", "N/A"), stent.get("segment_code", "N/A")] for stent in previous_stents] or [["N/A"]]

# Define function to determine three_vessel_PCI and three_or_more_lesions_treated
def check_three_vessel_PCI(previous_stents, current_stents, dcb_deb, thrombus_aspiration):
    rca_segments = {"1", "2", "3", "4", "16", "16a", "16b", "16c"}
    lad_segments = {"6", "7", "8", "9", "9a", "10", "10a"}
    lcx_segments = {"11", "12", "12a", "12b", "13", "14", "14a", "14b", "15"}
    
    all_segments = set(current_stents) | set(dcb_deb) | set(thrombus_aspiration)
    
    has_rca = any(seg in rca_segments for seg in all_segments)
    has_lad = any(seg in lad_segments for seg in all_segments)
    has_lcx = any(seg in lcx_segments for seg in all_segments)
    
    return has_rca and has_lad and has_lcx

def check_three_or_more_lesions_treated(current_stents, dcb_deb, thrombus_aspiration):
    treated_segments = set(current_stents) | set(dcb_deb) | set(thrombus_aspiration)
    return len(treated_segments) >= 3

def check_bifurcation_two_stents(previous_stents, current_stents):
    bifurcation_junctions = [
        {"5", "6", "11"}, {"6", "7", "9"}, {"7", "8", "10"},
        {"11", "13", "12a"}, {"13", "14", "14a"}, {"3", "4", "16"}, {"13", "14", "15"}
    ]
    
    combined_segments = set(previous_stents) | set(current_stents)
    
    for junction in bifurcation_junctions:
        if junction.issubset(combined_segments):
            return True
    return False

# Define a function to determine 'complex_pci'
def determine_complex_pci(row):
    if not row['pci']:
        return 'N/A'
    complex_pci_conditions = [
        row['three_vessel_PCI'],
        row['three_or_more_lesions_treated'],
        row['bifurcation_two_stents'],
        row['three_or_more_stents'],
        row['length_gt_60mm'],
        row['cto_pci']
    ]
    return any(complex_pci_conditions)

def extract_stent(entry):
    if not entry.get("pci"):
        return "N/A"
    stents = entry.get("pci_details", [{}])[0].get("stents", [])
    return [[stent.get("device", "N/A"), stent.get("diameter_mm", "N/A"), stent.get("length_mm", "N/A"), stent.get("segment_code", "N/A")] for stent in stents] or "N/A"

from collections import defaultdict



# Extract necessary columns from the data
vessel_disease = []
lesion_total_num = []
lesion_B2C_num = []
anatomical_dx_json = []
segment_codes_of_previous_stents = []
lengths_of_current_stents = []
segment_codes_of_current_stents = []
segment_codes_of_deb_dcb = []
segment_codes_of_thrombus_aspiration = []
segment_codes_of_kissing = []
cags = []
pcis = []
cto_pci = []


for entry in coronary_angiography_data:
    # Extract values or assign empty lists if missing
    previous_stents = entry.get("previous_stents_rearrange", [])
    current_stents = entry.get("current_stents_rearrange", [])
    pci_details = entry.get("pci_details", [])
    coronary_angiography = entry.get("coronary_angiography", {})

    # Extract segment codes and lengths from the new format
    previous_stent_codes = [stent.get("segment_code", []) for stent in previous_stents]
    current_stent_codes = [stent.get("segment_code", []) for stent in current_stents]

    segment_codes_of_previous_stents.append(previous_stent_codes)
    lengths_of_current_stents.append([stent.get("length_mm", 0) for stent in current_stents])
    segment_codes_of_current_stents.append(current_stent_codes)

    # Extract DEB/DCB and thrombus aspiration segment codes from both coronary_angiography and pci_details
    deb_dcb_segments = [
        balloon.get("segment_code", [])
        for balloon in coronary_angiography.get("DEB_DCB", [])
    ]
    deb_dcb_segments += [
        balloon.get("segment_code", [])
        for pci in pci_details
        for balloon in pci.get("DEB_DCB", [])
    ]
    segment_codes_of_deb_dcb.append(deb_dcb_segments)

    thrombus_aspiration_segments = [
        thrombus.get("segment_code", [])
        for thrombus in coronary_angiography.get("thrombus_aspiration", [])
    ]
    thrombus_aspiration_segments += [
        thrombus.get("segment_code", [])
        for pci in pci_details
        for thrombus in pci.get("thrombus_aspiration", [])
    ]
    segment_codes_of_thrombus_aspiration.append(thrombus_aspiration_segments)

    # Assuming kissing segment codes are missing for now
    segment_codes_of_kissing.append([])

    cags.append(bool(entry.get("coronary_angiography")))
    pcis.append(bool(entry.get("pci_details")))

# Flatten, remove duplicates, and sort the lists
segment_codes_of_previous_stents = [
    sorted(set(flatten(codes))) if isinstance(codes, list) else []
    for codes in segment_codes_of_previous_stents
]

segment_codes_of_current_stents = [
    sorted(set(flatten(codes))) if isinstance(codes, list) else []
    for codes in segment_codes_of_current_stents
]

segment_codes_of_deb_dcb = [
    sorted(set(flatten(codes))) if isinstance(codes, list) else []
    for codes in segment_codes_of_deb_dcb
]

segment_codes_of_thrombus_aspiration = [
    sorted(set(flatten(codes))) if isinstance(codes, list) else []
    for codes in segment_codes_of_thrombus_aspiration
]



for entry in coronary_angiography_data:
    pci_details = entry.get("pci_details", [])
    cto_detected = any(pci.get("CTO", False) for pci in pci_details)
    cto_pci.append(cto_detected)

previous_stent_array = [extract_previous_stent(entry) for entry in coronary_angiography_data]
current_stent_array = [extract_current_stent(entry) for entry in coronary_angiography_data]

vessel_disease = [categorize_vessel_disease([code[0] for code in segment_codes], stents) for segment_codes, stents in zip(all_segment_codes_with_types, segment_codes_of_previous_stents)]
lesion_total_num = [len(segments) for segments in all_segment_codes_with_types]
lesion_B2C_num = [sum(1 for _, type_ in segments if type_ in {"B2", "C"}) for segments in all_segment_codes_with_types]
anatomical_dx_json = [determine_anatomical_dx(categorize_vessel_disease([code[0] for code in segment_codes], stents)) for segment_codes, stents in zip(all_segment_codes_with_types, segment_codes_of_previous_stents)]

# Sort vessel_disease
def sort_vessel_disease(vessels):
    order = {'LM': 0, 'LAD': 1, 'LCx': 2, 'RCA': 3}
    return sorted(vessels, key=lambda x: order.get(x, len(order)))

vessel_disease = [
    sort_vessel_disease(categorize_vessel_disease([code[0] for code in segment_codes], stents))
    for segment_codes, stents in zip(all_segment_codes_with_types, segment_codes_of_previous_stents)
]


df = pd.DataFrame({
    "patient_number": patient_numbers,
    "sex": sex,
    "age": age,
    "date_of_angiography": dates_of_angiography,
    "review": review,
    "cag": cags,
    "segment_codes_of_previous_stents": segment_codes_of_previous_stents,
    "segment_code": all_segment_codes_with_types,
    "vessel_disease": vessel_disease,
    "anatomical_dx_json": anatomical_dx_json,
    "lesion_total_num": lesion_total_num,
    "lesion_B2/C_num": lesion_B2C_num,
    "pci": pcis,
    "lengths_of_current_stents": lengths_of_current_stents,
    "segment_codes_of_current_stents": segment_codes_of_current_stents,
    "segment_codes_of_deb_dcb": segment_codes_of_deb_dcb,
    "segment_codes_of_thrombus_aspiration":segment_codes_of_thrombus_aspiration,
    "segment_codes_of_kissing": segment_codes_of_kissing,
    "three_vessel_PCI": [False] * len(coronary_angiography_data),
    "three_or_more_lesions_treated": [False] * len(coronary_angiography_data),
    "bifurcation_two_stents": [False] * len(coronary_angiography_data),
    "three_or_more_stents": [False] * len(coronary_angiography_data),
    "length_gt_60mm": [False] * len(coronary_angiography_data),
    "cto_pci": cto_pci,
    "complex_pci": [False] * len(coronary_angiography_data),
    "previous_stent": previous_stent_array,
    "current_stent": stent_array,  # New column added at the end
})


df["three_vessel_PCI"] = df.apply(lambda row: 'N/A' if not row['pci'] else check_three_vessel_PCI(
    row["segment_codes_of_previous_stents"],
    row["segment_codes_of_current_stents"],
    row["segment_codes_of_deb_dcb"],
    row["segment_codes_of_thrombus_aspiration"]
), axis=1)

df["three_or_more_lesions_treated"] = df.apply(lambda row: 'N/A' if not row['pci'] else check_three_or_more_lesions_treated(
    row["segment_codes_of_current_stents"],
    row["segment_codes_of_deb_dcb"],
    row["segment_codes_of_thrombus_aspiration"]
), axis=1)

df["bifurcation_two_stents"] = df.apply(lambda row: 'N/A' if not row['pci'] else check_bifurcation_two_stents(
    row["segment_codes_of_previous_stents"],
    row["segment_codes_of_current_stents"]
), axis=1)

df["three_or_more_stents"] = df.apply(lambda row: 'N/A' if not row['pci'] else len(row["lengths_of_current_stents"]) >= 3, axis=1)

df["length_gt_60mm"] = df.apply(lambda row: 'N/A' if not row['pci'] else sum(row["lengths_of_current_stents"]) >= 60, axis=1)

df["cto_pci"] = df.apply(lambda row: 'N/A' if not row['pci'] else row["cto_pci"], axis=1)


# Add 'complex_pci' column at the last position
df['complex_pci'] = df.apply(determine_complex_pci, axis=1)


# Print the first 20 results
print(df.head(20))

# Calculate and print the proportion of B2 and C lesions for 'cag' == True
if df['cag'].sum() > 0:  # Check if there are any rows where 'cag' is True
    proportion_b2_c_lesions = df.loc[df['cag'], 'lesion_B2/C_num'].sum() / df.loc[df['cag'], 'lesion_total_num'].sum() * 100
    print(f"proportion of B2 and C lesion: {proportion_b2_c_lesions:.1f}%")


# Save the DataFrame to a CSV file if needed
# df.to_csv('D:/STUDY/2024-1.5/240627_CAGtoJSON/reformed/json_analysis_final_240925_ISRSubtotal.csv', index=False)


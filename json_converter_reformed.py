import pandas as pd

# File paths provided by the user
csv_file_path = 'D:/STUDY/2024-1.5/240627_CAGtoJSON/ilsan/ilsan_GPTtoCSV_240910.csv'
json_output_path = 'D:/STUDY/2024-1.5/240627_CAGtoJSON/ilsan/ilsan_CSVtoJSON_240910.json'

# Read the CSV file into a DataFrame
data = pd.read_csv(csv_file_path)

# Convert the DataFrame to JSON format and save to the specified path
data.to_json(json_output_path, orient='records', lines=True)

# Display a confirmation message and the path to the JSON file
json_output_path

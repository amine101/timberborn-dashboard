import os
import json
import zipfile
import numpy as np
import socket 
import sqlite3
from contextlib import closing
import webbrowser

# Class to handle save file operations
class SaveFileHandler:
    def __init__(self, directory):
        self.directory = directory
        self.latest_timestamp = None

    def load_all_files(self):
        try:
            files = [os.path.join(self.directory, f) for f in os.listdir(self.directory) if f.endswith('.timber')]
            return sorted(files, key=os.path.getmtime)
        except ValueError:
            return []

    def load_latest_file(self):
        files = self.load_all_files()
        if files:
            return files[-1]
        return None

    def read_world_data(self, path):
        try:
            with zipfile.ZipFile(path, 'r') as z:
                with z.open('world.json') as file:
                    data = json.load(file)
                    self.latest_timestamp = data.get("Timestamp")
                    return data
        except (zipfile.BadZipFile, KeyError, json.JSONDecodeError) as e:
            print(f"Error reading world data: {e}")
            return None

    def save_world_data(self, path, game_data):
        temp_zip_path = path + '.tmp'
        try:
            with zipfile.ZipFile(path, 'r') as z:
                with zipfile.ZipFile(temp_zip_path, 'w') as temp_zip:
                    for item in z.infolist():
                        if item.filename != 'world.json':
                            temp_zip.writestr(item, z.read(item.filename))
                    temp_zip.writestr('world.json', json.dumps(game_data, indent=4))
            os.remove(path)
            os.rename(temp_zip_path, path)
        except Exception as e:
            print(f"Error saving world data: {e}")

# Class to handle historical data operations
class HistoricalDataHandler:
    def __init__(self, directory, db_name="historical_data.db"):
        self.db_path = os.path.join(directory, db_name)
        self._ensure_database()
        self.obsolete_json_path = os.path.join(directory, "historical_data.json" )  # the old format of historical data, to migrate to db if exists

    def _ensure_database(self):
        with closing(sqlite3.connect(self.db_path)) as conn, conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS historical_data (
                    id INTEGER PRIMARY KEY,
                    timestamp TEXT UNIQUE,
                    data TEXT
                )
            ''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON historical_data (timestamp)')

    def save_historical_data(self, data):
        try:
            with closing(sqlite3.connect(self.db_path)) as conn, conn:
                conn.execute(
                    "INSERT OR IGNORE INTO historical_data (timestamp, data) VALUES (?, ?)",
                    (data["timestamp"], json.dumps(data))
                )
        except Exception as e:
            print(f"Error saving historical data: {e}")

    def get_historical_data(self):
        try:
            with closing(sqlite3.connect(self.db_path)) as conn, conn:
                cursor = conn.execute("SELECT data FROM historical_data")
                return [json.loads(row[0]) for row in cursor]
        except Exception as e:
            print(f"Error reading historical data: {e}")
            return []

    def query_historical_data(self, key, value):
        try:
            query = f"$.{key}"
            with closing(sqlite3.connect(self.db_path)) as conn, conn:
                cursor = conn.execute(
                    "SELECT data FROM historical_data WHERE json_extract(data, ?) = ?",
                    (query, value)
                )
                return [json.loads(row[0]) for row in cursor]
        except Exception as e:
            print(f"Error querying historical data: {e}")
            return []

    def migratejson_to_db(self):
        if not os.path.exists(self.obsolete_json_path):
            #print("JSON file does not exist.")
            return

        try:
            # Read the JSON file
            with open(self.obsolete_json_path, 'r') as file:
                historical_data = json.load(file)
            
            json_entries_count = len(historical_data)
            print(f"Number of entries in JSON file: {json_entries_count}")

            # Clean up the database
            with closing(sqlite3.connect(self.db_path)) as conn, conn:
                conn.execute("DELETE FROM historical_data")
            
            # Insert historical data into the database
            saved_entries_count = 0
            with closing(sqlite3.connect(self.db_path)) as conn, conn:
                for data in historical_data:
                    conn.execute(
                        "INSERT OR IGNORE INTO historical_data (timestamp, data) VALUES (?, ?)",
                        (data["timestamp"], json.dumps(data))
                    )
                    saved_entries_count += 1
            
            print(f"Number of entries saved to the database: {saved_entries_count}")

            # Verify data integrity
            with closing(sqlite3.connect(self.db_path)) as conn, conn:
                cursor = conn.execute("SELECT COUNT(*) FROM historical_data")
                db_entries_count = cursor.fetchone()[0]
                print(f"Number of entries in the database: {db_entries_count}")

            if json_entries_count == db_entries_count:
                print("All entries from the JSON file were successfully saved to the database.")
            else:
                print("Some entries from the JSON file were not saved to the database.")

            # Further verification by checking each timestamp
            with closing(sqlite3.connect(self.db_path)) as conn, conn:
                missing_entries = []
                for data in historical_data:
                    cursor = conn.execute(
                        "SELECT COUNT(*) FROM historical_data WHERE timestamp = ?",
                        (data["timestamp"],)
                    )
                    if cursor.fetchone()[0] == 0:
                        missing_entries.append(data["timestamp"])

                if missing_entries:
                    print(f"Missing entries with timestamps: {missing_entries}")
                else:
                    print("All entries verified successfully.")

            # Remove the JSON file after successful load
            os.remove(self.obsolete_json_path)
            print(f"JSON file {self.obsolete_json_path} removed successfully.")

        except Exception as e:
            print(f"Error loading historical data from JSON to database: {e}")

    def close(self):
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.close()




# Class to modify game settings
class SettingsModifier:
    def __init__(self, game_data):
        self.singletons = game_data['Singletons']

    def update_settings(self, new_values):
        
        settings = {
            'temperate_min': ('TemperateWeatherDurationService', 'MinTemperateWeatherDuration'),
            'temperate_max': ('TemperateWeatherDurationService', 'MaxTemperateWeatherDuration'),
            'drought_min': ('DroughtWeather', 'MinDroughtDuration'),
            'drought_max': ('DroughtWeather', 'MaxDroughtDuration'),
            'badtide_min': ('BadtideWeather', 'MinBadtideWeatherDuration'),
            'badtide_max': ('BadtideWeather', 'MaxBadtideWeatherDuration'),
        }
        for key, (service, attr) in settings.items():
            value = int(new_values[key])
            self.singletons[service][attr] = value

    def get_current_settings(self):
        settings = {
            'temperate_min': self.singletons['TemperateWeatherDurationService']['MinTemperateWeatherDuration'],
            'temperate_max': self.singletons['TemperateWeatherDurationService']['MaxTemperateWeatherDuration'],
            'drought_min': self.singletons['DroughtWeather']['MinDroughtDuration'],
            'drought_max': self.singletons['DroughtWeather']['MaxDroughtDuration'],
            'badtide_min': self.singletons['BadtideWeather']['MinBadtideWeatherDuration'],
            'badtide_max': self.singletons['BadtideWeather']['MaxBadtideWeatherDuration'],
        }
        return settings
    

class BeaverInfo:  # Currently not used anywhere
    def __init__(self, game_data):
        self.game_data = game_data

    def get_beaver_counts(self):
        entities = self.game_data['Entities']
        total_beavers = 0
        adult_beavers = 0
        child_beavers = 0

        for entity in entities:
            if 'Template' in entity:
                if entity['Template'] == 'BeaverAdult':
                    adult_beavers += 1
                    total_beavers += 1
                elif entity['Template'] == 'BeaverChild':
                    child_beavers += 1
                    total_beavers += 1

        return total_beavers, adult_beavers, child_beavers



# Class to handle weather, water, and moisture information
class WeatherAndWaterAndMoistureInfo:
    def __init__(self, game_data):
        self.singletons = game_data['Singletons']
        self.clean_water_levels = []
        self.width = self.singletons['MapSize']['Size']['X']
        self.height = self.singletons['MapSize']['Size']['Y']

    def calculate_total_clean_water(self):
        water_depths_str = self.singletons['WaterMap']['WaterDepths']['Array']
        contamination_levels_str = self.singletons['ContaminationMap']['Contaminations']['Array']
        water_depths = np.array([float(depth) for depth in water_depths_str.split()])
        contamination_levels = np.array([float(level) for level in contamination_levels_str.split()])
        
        # Calculate pure water amount
        pure_water_depths = water_depths - (water_depths * contamination_levels)
        total_clean_water = np.sum(pure_water_depths)
        
        self.clean_water_levels.append(total_clean_water)
        return total_clean_water
    
    def get_weather_info(self):
        hazardous_weather = self.singletons['HazardousWeatherService']
        weather_service = self.singletons['WeatherService']

        weather_info = {
            'HazardousWeatherDuration': hazardous_weather['HazardousWeatherDuration'],
            'IsDrought': hazardous_weather['IsDrought'],
            'Cycle': weather_service['Cycle'],
            'CycleDay': weather_service['CycleDay'],
            'TemperateWeatherDuration': weather_service['TemperateWeatherDuration']
        }

        return weather_info

    def get_water_levels_matrix(self):
        water_depths_str = self.singletons['WaterMap']['WaterDepths']['Array']
        water_depths = np.array([float(depth) for depth in water_depths_str.split()])
        water_levels_matrix = water_depths.reshape((self.height, self.width)).T  # Transpose the matrix
        return water_levels_matrix

    def get_contamination_percentage_matrix(self):
        contamination_levels_str = self.singletons['ContaminationMap']['Contaminations']['Array']
        contamination_levels = np.array([float(level) for level in contamination_levels_str.split()])
        contamination_percentage_matrix = contamination_levels.reshape((self.height, self.width)).T  # Transpose the matrix
        return contamination_percentage_matrix

    def get_moisture_levels_matrix(self):
        moisture_levels_str = self.singletons['SoilMoistureSimulator']['MoistureLevels']['Array']
        moisture_levels = np.array([float(level) for level in moisture_levels_str.split()])
        moisture_levels_matrix = moisture_levels.reshape((self.height, self.width)).T  # Transpose the matrix
        return moisture_levels_matrix

    def get_soil_contamination_matrix(self):
        soil_contamination_str = self.singletons['SoilContaminationSimulator']['ContaminationLevels']['Array']
        soil_contamination = np.array([float(level) for level in soil_contamination_str.split()])
        soil_contamination_matrix = soil_contamination.reshape((self.height, self.width)).T  # Transpose the matrix
        return soil_contamination_matrix
    

    def get_evaporation_modifiers_matrix(self):
        evaporation_modifiers_str = self.singletons['WaterEvaporationMap']['EvaporationModifiers']['Array']
        # Remove trailing dot characters if present and convert to float
        cleaned_modifiers = [float(modifier.rstrip('.')) for modifier in evaporation_modifiers_str.split()]
        evaporation_modifiers = np.array(cleaned_modifiers)
        evaporation_modifiers_matrix = evaporation_modifiers.reshape((self.height, self.width)).T  # Transpose the matrix
        return evaporation_modifiers_matrix


# Function to open the browser after a delay
def open_browser(PORT):
    webbrowser.open_new(f"http://127.0.0.1:{PORT}/")

# Function to check and terminate previous instances of the app
def check_port(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            s.close()
            return True  # The port is available
        except socket.error:
            return False  # The port is in use
        
import os
import json
import zipfile
import numpy as np
import socket 

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
    def __init__(self, directory, file_name="historical_data.json"):
        self.file_path = os.path.join(directory, file_name)
        if not os.path.exists(self.file_path):
            with open(self.file_path, 'w') as f:
                json.dump([], f)

    def save_historical_data(self, data):
        try:
            with open(self.file_path, 'r+') as f:
                try:
                    f.seek(0)
                    historical_data = json.load(f)
                    if not isinstance(historical_data, list):
                        historical_data = []
                except json.JSONDecodeError:
                    historical_data = []

                if not historical_data or historical_data[-1]["timestamp"] != data["timestamp"]:
                    historical_data.append(data)
                    f.seek(0)
                    json.dump(historical_data, f, indent=4)
                    f.truncate()
        except Exception as e:
            print(f"Error saving historical data: {e}")

    def get_historical_data(self):
        try:
            with open(self.file_path, 'r') as f:
                try:
                    historical_data = json.load(f)
                    if not isinstance(historical_data, list):
                        historical_data = []
                except json.JSONDecodeError:
                    historical_data = []
            return historical_data
        except Exception as e:
            print(f"Error reading historical data: {e}")
            return []

# Class to modify game settings
class SettingsModifier:
    def __init__(self, game_data):
        self.game_data = game_data

    def update_settings(self, new_values):
        singletons = self.game_data['Singletons']
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
            singletons[service][attr] = value

    def get_current_settings(self):
        singletons = self.game_data['Singletons']
        settings = {
            'temperate_min': singletons['TemperateWeatherDurationService']['MinTemperateWeatherDuration'],
            'temperate_max': singletons['TemperateWeatherDurationService']['MaxTemperateWeatherDuration'],
            'drought_min': singletons['DroughtWeather']['MinDroughtDuration'],
            'drought_max': singletons['DroughtWeather']['MaxDroughtDuration'],
            'badtide_min': singletons['BadtideWeather']['MinBadtideWeatherDuration'],
            'badtide_max': singletons['BadtideWeather']['MaxBadtideWeatherDuration'],
        }
        return settings

# Class to handle weather, water, and moisture information
class WeatherAndWaterAndMoistureInfo:
    def __init__(self, game_data):
        self.game_data = game_data
        self.clean_water_levels = []
        self.width = self.game_data['Singletons']['MapSize']['Size']['X']
        self.height = self.game_data['Singletons']['MapSize']['Size']['Y']

    def calculate_total_clean_water(self):
        water_depths_str = self.game_data['Singletons']['WaterMap']['WaterDepths']['Array']
        contamination_levels_str = self.game_data['Singletons']['ContaminationMap']['Contaminations']['Array']
        water_depths = np.array([float(depth) for depth in water_depths_str.split()])
        contamination_levels = np.array([float(level) for level in contamination_levels_str.split()])
        
        # Calculate pure water amount
        pure_water_depths = water_depths - (water_depths * contamination_levels)
        total_clean_water = np.sum(pure_water_depths)
        
        self.clean_water_levels.append(total_clean_water)
        return total_clean_water
    
    def get_weather_info(self):
        hazardous_weather = self.game_data['Singletons']['HazardousWeatherService']
        weather_service = self.game_data['Singletons']['WeatherService']

        weather_info = {
            'HazardousWeatherDuration': hazardous_weather['HazardousWeatherDuration'],
            'IsDrought': hazardous_weather['IsDrought'],
            'Cycle': weather_service['Cycle'],
            'CycleDay': weather_service['CycleDay'],
            'TemperateWeatherDuration': weather_service['TemperateWeatherDuration']
        }

        return weather_info

    def get_water_levels_matrix(self):
        water_depths_str = self.game_data['Singletons']['WaterMap']['WaterDepths']['Array']
        water_depths = np.array([float(depth) for depth in water_depths_str.split()])
        water_levels_matrix = water_depths.reshape((self.height, self.width)).T  # Transpose the matrix
        return water_levels_matrix

    def get_contamination_percentage_matrix(self):
        contamination_levels_str = self.game_data['Singletons']['ContaminationMap']['Contaminations']['Array']
        contamination_levels = np.array([float(level) for level in contamination_levels_str.split()])
        contamination_percentage_matrix = contamination_levels.reshape((self.height, self.width)).T  # Transpose the matrix
        return contamination_percentage_matrix

    def get_moisture_levels_matrix(self):
        moisture_levels_str = self.game_data['Singletons']['SoilMoistureSimulator']['MoistureLevels']['Array']
        moisture_levels = np.array([float(level) for level in moisture_levels_str.split()])
        moisture_levels_matrix = moisture_levels.reshape((self.height, self.width)).T  # Transpose the matrix
        return moisture_levels_matrix

    def get_soil_contamination_matrix(self):
        soil_contamination_str = self.game_data['Singletons']['SoilContaminationSimulator']['ContaminationLevels']['Array']
        soil_contamination = np.array([float(level) for level in soil_contamination_str.split()])
        soil_contamination_matrix = soil_contamination.reshape((self.height, self.width)).T  # Transpose the matrix
        return soil_contamination_matrix
    

    def get_evaporation_modifiers_matrix(self):
        evaporation_modifiers_str = self.game_data['Singletons']['WaterEvaporationMap']['EvaporationModifiers']['Array']
        # Remove trailing dot characters if present and convert to float
        cleaned_modifiers = [float(modifier.rstrip('.')) for modifier in evaporation_modifiers_str.split()]
        evaporation_modifiers = np.array(cleaned_modifiers)
        evaporation_modifiers_matrix = evaporation_modifiers.reshape((self.height, self.width)).T  # Transpose the matrix
        self.save_matrix_to_json( evaporation_modifiers_matrix , "output.json")
        return evaporation_modifiers_matrix



# Function to check and terminate previous instances of the app
def check_port(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            s.close()
            return True  # The port is available
        except socket.error:
            return False  # The port is in use
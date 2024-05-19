import os
import json
import zipfile
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import dash
from dash import Dash, dcc, html, Input, Output, State, callback_context
import dash_bootstrap_components as dbc
from dash.exceptions import PreventUpdate
import webbrowser
from threading import Timer
from utils.tools import SaveFileHandler, HistoricalDataHandler, SettingsModifier, WeatherAndWaterAndMoistureInfo

# Initialize Dash app
app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

# Define the layout
app.layout = dbc.Container([
    dbc.Row([
        dbc.Col(html.H1("Timberborn Save Editor", className="text-center"))
    ]),
    dbc.Row([
        dbc.Col([
            html.Label("Save Folder Path:"),
            dbc.Input(id='folder-path-input', type='text', placeholder="Enter folder path here...", className='mb-2'),
            html.Div(id='folder-path', className='mb-2'),
            dbc.Checkbox(
                id='analyze-all-files',
                className="mb-3",
                label="Analyze all existing .timber files"
            ),
            dbc.Button("Load Save Files", id='load-save-button', color="primary", className="mb-3")
        ])
    ]),
    dbc.Row([
        dbc.Col([
            html.Label("Settings"),
            html.Div([
                html.Label("Min Temperate Weather Duration"),
                dbc.Input(id='temperate_min', type='number', className='mb-2')
            ]),
            html.Div([
                html.Label("Max Temperate Weather Duration"),
                dbc.Input(id='temperate_max', type='number', className='mb-2')
            ]),
            html.Div([
                html.Label("Min Drought Duration"),
                dbc.Input(id='drought_min', type='number', className='mb-2')
            ]),
            html.Div([
                html.Label("Max Drought Duration"),
                dbc.Input(id='drought_max', type='number', className='mb-2')
            ]),
            html.Div([
                html.Label("Min Badtide Weather Duration"),
                dbc.Input(id='badtide_min', type='number', className='mb-2')
            ]),
            html.Div([
                html.Label("Max Badtide Weather Duration"),
                dbc.Input(id='badtide_max', type='number', className='mb-2')
            ]),
            dbc.Button("Update Save", id='update-save-button', color="success", className="mb-3")
        ])
    ]),
    dbc.Row([
        dbc.Col([
            html.Div(id='clean-water-output', className='mb-2'),
            html.Div(id='weather-info-output', className='mb-2')
        ])
    ]),
    dbc.Row([
        dbc.Col(html.H2("Water Depth", className='text-center'), width=6),
        dbc.Col(html.H2("Contamination", className='text-center'), width=6)
    ]),
    dbc.Row([
        dbc.Col(dcc.Graph(id='water-depth-heatmap', className='mb-4'), width=6),
        dbc.Col(dcc.Graph(id='contamination-heatmap', className='mb-4'), width=6)
    ]),
    dbc.Row([
        dbc.Col(html.H2("Soil Moisture", className='text-center'), width=6),
        dbc.Col(html.H2("Soil Contamination", className='text-center'), width=6)
    ]),
    dbc.Row([
        dbc.Col(dcc.Graph(id='moisture-heatmap', className='mb-4'), width=6),
        dbc.Col(dcc.Graph(id='soil-contamination-heatmap', className='mb-4'), width=6)
    ]),
    dbc.Row([
        dbc.Col(html.Div(id='latest-save-file', className='mb-2'))
    ]),
    dbc.Toast(
        id="update-success-toast",
        header="Update Successful",
        is_open=False,
        duration=4000,
        children=[html.Div("Save file modified successfully. Please reload the save to take effect.")],
        icon="success",
        style={"position": "fixed", "top": 10, "right": 10, "width": 350}
    ),
    dbc.Toast(
        id="update-fail-toast",
        header="Update Failed",
        is_open=False,
        duration=4000,
        children=[html.Div("Failed to modify the save file. Please try again.")],
        icon="danger",
        style={"position": "fixed", "top": 10, "right": 10, "width": 350}
    ),
    dcc.Interval(
        id='interval-component',
        interval=10*1000,  # 10 seconds
        n_intervals=0
    )
])

# Helper function to sanitize folder path
def sanitize_folder_path(folder_path):
    folder_path = folder_path.replace(',', '').replace('"', '').replace("'", "").strip()
    folder_path = folder_path.replace('\\', os.sep).replace('/', os.sep)
    return folder_path

# Helper function to load save file data
def load_save_files(folder_path, analyze_all):
    folder_path = sanitize_folder_path(folder_path)
    save_handler = SaveFileHandler(folder_path)
    if analyze_all:
        files = save_handler.load_all_files()
    else:
        latest_file = save_handler.load_latest_file()
        files = [latest_file] if latest_file else []

    return files, save_handler

# Helper function to process save files and return required outputs
def process_save_files(files, save_handler):
    historical_data_handler = HistoricalDataHandler(save_handler.directory)
    historical_data = historical_data_handler.get_historical_data()

    for path in files:
        game_data = save_handler.read_world_data(path)
        if not game_data:
            continue

        settings_modifier = SettingsModifier(game_data)
        weather_and_water_info = WeatherAndWaterAndMoistureInfo(game_data)

        clean_water_total = weather_and_water_info.calculate_total_clean_water()
        weather_info = weather_and_water_info.get_weather_info()
        current_settings = settings_modifier.get_current_settings()

        water_levels_matrix = weather_and_water_info.get_water_levels_matrix()
        contamination_matrix = weather_and_water_info.get_contamination_percentage_matrix()
        moisture_levels_matrix = weather_and_water_info.get_moisture_levels_matrix()
        soil_contamination_matrix = weather_and_water_info.get_soil_contamination_matrix()

        clean_water_text = f"Clean Water: {clean_water_total:.2f} cubic meters"
        weather_info_text = [
            html.Div(f"Hazardous Weather Duration: {weather_info['HazardousWeatherDuration']} days"), html.Br(),
            html.Div(f"Is Drought: {'Yes' if weather_info['IsDrought'] else 'No'}"), html.Br(),
            html.Div(f"Cycle: {weather_info['Cycle']}"), html.Br(),
            html.Div(f"Cycle Day: {weather_info['CycleDay']}"), html.Br(),
            html.Div(f"Temperate Weather Duration: {weather_info['TemperateWeatherDuration']} days")
        ]

        historical_data_entry = {
            "timestamp": save_handler.latest_timestamp,
            "clean_water_total": clean_water_total,
            "water_levels_matrix": water_levels_matrix.tolist(),
            "contamination_matrix": contamination_matrix.tolist(),
            "moisture_levels_matrix": moisture_levels_matrix.tolist(),
            "soil_contamination_matrix": soil_contamination_matrix.tolist(),
            "weather_info": weather_info,
            "map_width": weather_and_water_info.width,
            "map_height": weather_and_water_info.height
        }

        # Save historical data
        historical_data_handler.save_historical_data(historical_data_entry)

    if not historical_data:
        return [html.Span("No save file found in the specified directory.", style={"color": "red"})] * 15

    water_levels_matrix = np.array(historical_data[-1]["water_levels_matrix"])
    contamination_matrix = np.array(historical_data[-1]["contamination_matrix"])
    moisture_levels_matrix = np.array(historical_data[-1]["moisture_levels_matrix"])
    soil_contamination_matrix = np.array(historical_data[-1]["soil_contamination_matrix"])

    # Common layout for all heatmaps
    common_layout = dict(
        width=650,
        height=650,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        margin=dict(l=0, r=0, t=0, b=0),
        coloraxis_showscale=True
    )

    water_depth_fig = px.imshow(water_levels_matrix, color_continuous_scale='Blues')
    water_depth_fig.update_layout(common_layout)
    water_depth_fig.update_traces(hovertemplate='x: %{x}<br>y: %{y}<br>Water Depth: %{z:.2f}')

    contamination_fig = px.imshow(contamination_matrix, color_continuous_scale='Reds')
    contamination_fig.update_layout(common_layout)
    contamination_fig.update_traces(hovertemplate='x: %{x}<br>y: %{y}<br>Contamination Percentage: %{z:.2f}')

    moisture_fig = px.imshow(moisture_levels_matrix, color_continuous_scale='Greens')
    moisture_fig.update_layout(common_layout)
    moisture_fig.update_traces(hovertemplate='x: %{x}<br>y: %{y}<br>Moisture Level: %{z:.2f}')

    soil_contamination_fig = px.imshow(soil_contamination_matrix, color_continuous_scale='Oranges')
    soil_contamination_fig.update_layout(common_layout)
    soil_contamination_fig.update_traces(hovertemplate='x: %{x}<br>y: %{y}<br>Soil Contamination: %{z:.2f}')

    latest_file_path = files[-1] if files else "No files found"

    return (
        current_settings['temperate_min'], current_settings['temperate_max'],
        current_settings['drought_min'], current_settings['drought_max'],
        current_settings['badtide_min'], current_settings['badtide_max'],
        clean_water_text, weather_info_text, water_depth_fig, contamination_fig, moisture_fig, soil_contamination_fig, latest_file_path
    )

# Combined callback for loading and updating save
@app.callback(
    [
        Output('folder-path', 'children'),
        Output('temperate_min', 'value'),
        Output('temperate_max', 'value'),
        Output('drought_min', 'value'),
        Output('drought_max', 'value'),
        Output('badtide_min', 'value'),
        Output('badtide_max', 'value'),
        Output('clean-water-output', 'children'),
        Output('weather-info-output', 'children'),
        Output('water-depth-heatmap', 'figure'),
        Output('contamination-heatmap', 'figure'),
        Output('moisture-heatmap', 'figure'),
        Output('soil-contamination-heatmap', 'figure'),
        Output('latest-save-file', 'children'),
        Output('update-success-toast', 'is_open'),
        Output('update-fail-toast', 'is_open')
    ],
    [
        Input('load-save-button', 'n_clicks'),
        Input('update-save-button', 'n_clicks'),
        Input('interval-component', 'n_intervals')
    ],
    [
        State('folder-path-input', 'value'),
        State('temperate_min', 'value'),
        State('temperate_max', 'value'),
        State('drought_min', 'value'),
        State('drought_max', 'value'),
        State('badtide_min', 'value'),
        State('badtide_max', 'value'),
        State('analyze-all-files', 'value')
    ]
)
def handle_buttons(load_clicks, update_clicks, n_intervals, folder_path, temperate_min, temperate_max, drought_min, drought_max, badtide_min, badtide_max, analyze_all):
    ctx = callback_context
    if not ctx.triggered:
        raise PreventUpdate

    button_id = ctx.triggered[0]['prop_id'].split('.')[0]

    if button_id == 'load-save-button':
        if folder_path is None or not os.path.isdir(sanitize_folder_path(folder_path)):
            return [html.Span("Please enter a valid folder path.", style={"color": "red"})] * 16 + [False, False]

        files, save_handler = load_save_files(folder_path, analyze_all)
        if not files:
            return [html.Span("No save file found in the specified directory.", style={"color": "red"})] * 16 + [False, False]

        return (folder_path, *process_save_files(files, save_handler), False, False)

    elif button_id == 'update-save-button' and update_clicks:
        if folder_path:
            folder_path = sanitize_folder_path(folder_path)
            save_handler = SaveFileHandler(folder_path)
            latest_file = save_handler.load_latest_file()
            if not latest_file:
                return dash.no_update + (False, True)

            game_data = save_handler.read_world_data(latest_file)
            if not game_data:
                return dash.no_update + (False, True)

            modifier = SettingsModifier(game_data)

            new_values = {
                'temperate_min': temperate_min,
                'temperate_max': temperate_max,
                'drought_min': drought_min,
                'drought_max': drought_max,
                'badtide_min': badtide_min,
                'badtide_max': badtide_max,
            }

            try:
                modifier.update_settings(new_values)
                save_handler.save_world_data(latest_file, game_data)
                return (
                    folder_path, temperate_min, temperate_max, drought_min, drought_max, badtide_min, badtide_max,
                    "", "", go.Figure(), go.Figure(), go.Figure(), go.Figure(), latest_file, True, False
                )
            except Exception as e:
                print(f"Error occurred: {e}")
                return dash.no_update + (False, True)

    elif button_id == 'interval-component':
        if folder_path is None or not os.path.isdir(sanitize_folder_path(folder_path)):
            return dash.no_update

        files, save_handler = load_save_files(folder_path, analyze_all)
        if not files:
            return dash.no_update

        return (folder_path, *process_save_files(files, save_handler), False, False)

    return folder_path, temperate_min, temperate_max, drought_min, drought_max, badtide_min, badtide_max, "", "", go.Figure(), go.Figure(), go.Figure(), go.Figure(), "", False, False

# Function to open the browser after a delay
def open_browser():
    webbrowser.open_new("http://127.0.0.1:8050/")

if __name__ == "__main__":
    Timer(1, open_browser).start()
    app.run_server(debug=False)
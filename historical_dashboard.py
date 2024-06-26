import os
from dash import Dash, dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
import plotly.graph_objs as go
import numpy as np
from dash.exceptions import PreventUpdate
from utils.tools import HistoricalDataHandler, check_port
import webbrowser
from threading import Timer
import time

PORT = 8051
# Initialize Dash app
app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

# Define the layout
app.layout = dbc.Container([
    dbc.Row([
        dbc.Col(html.H1("Historical Data Dashboard", className="text-center"))
    ]),
    dbc.Row([
        dbc.Col([
            html.Label("Select Folder Path:"),
            dbc.Input(id='folder-path-input', type='text', placeholder="Enter folder path here...", className='mb-2'),
            dbc.Button("Load Historical Data", id='load-data-button', color="primary", className="mb-3")
        ])
    ]),
    dbc.Row([
        dbc.Col([
            html.H2("Historical Water Depth"),
            dcc.Graph(id='water-depth-heatmap', className='mb-4')
        ], width=6),
        dbc.Col([
            html.H2("Historical Contamination"),
            dcc.Graph(id='contamination-heatmap', className='mb-4')
        ], width=6)
    ]),
    dbc.Row([
        dbc.Col([
            html.H2("Historical Soil Moisture Levels"),
            dcc.Graph(id='moisture-heatmap', className='mb-4')
        ], width=6),
        dbc.Col([
            html.H2("Historical Soil Contamination"),
            dcc.Graph(id='soil-contamination-heatmap', className='mb-4')
        ], width=6)
    ]),
    dbc.Row([
        dbc.Col([
            html.H2("Historical Evaporation Modifiers"),
            dcc.Graph(id='evaporation-heatmap', className='mb-4')
        ], width=6)
    ]),
    dbc.Row([
        dbc.Col([
            dcc.Graph(id='total-water-graph', className='mb-4')
        ])
    ]),
    dbc.Row([
        dbc.Col([
            dcc.Slider(
                id='day-slider',
                min=0,
                max=0,
                step=1,
                value=0,
                marks={0: '0'},
                tooltip={"placement": "bottom", "always_visible": True},
            )
        ])
    ])
])

# Helper function to sanitize folder path
def sanitize_folder_path(folder_path):
    folder_path = folder_path.replace(',', '').replace('"', '').replace("'", "").strip()
    folder_path = folder_path.replace('\\', os.sep).replace('/', os.sep)
    return folder_path

# Helper function to load historical data
def load_historical_data(folder_path):
    folder_path = sanitize_folder_path(folder_path)
    historical_data_handler = HistoricalDataHandler(folder_path)
    historical_data = historical_data_handler.get_historical_data()
    return historical_data

# Common function to create heatmap figures
def create_heatmap_figure(data, frames, colorscale, hovertemplate):
    fig = go.Figure(
        data=go.Heatmap(
            z=data,
            colorscale=colorscale,
            hovertemplate=hovertemplate
        ),
        frames=frames
    )
    
    fig.update_layout(
        width=650, height=650,
        updatemenus=[{
            "buttons": [
                {"args": [None, {"frame": {"duration": 500, "redraw": True}, "fromcurrent": True}], "label": "Play", "method": "animate"},
                {"args": [[None], {"frame": {"duration": 0, "redraw": True}, "mode": "immediate"}], "label": "Pause", "method": "animate"}
            ],
            "direction": "left",
            "pad": {"r": 10, "t": 87},
            "showactive": False,
            "type": "buttons",
            "x": 0.1,
            "xanchor": "right",
            "y": 0,
            "yanchor": "top"
        }],
        sliders=[{
            'steps': [{'args': [[f.name], {'frame': {'duration': 500, 'redraw': True}, 'mode': 'immediate'}], 'label': f.name, 'method': 'animate'} for f in frames],
            'transition': {'duration': 500},
            'x': 0.1,
            'len': 0.9
        }]
    )
    return fig

# Callback to load historical data and update heatmaps and slider
@app.callback(
    [
        Output('water-depth-heatmap', 'figure'),
        Output('contamination-heatmap', 'figure'),
        Output('moisture-heatmap', 'figure'),
        Output('soil-contamination-heatmap', 'figure'),
        Output('evaporation-heatmap', 'figure'),
        Output('total-water-graph', 'figure'),
        Output('day-slider', 'min'),
        Output('day-slider', 'max'),
        Output('day-slider', 'value'),
        Output('day-slider', 'marks')
    ],
    [Input('load-data-button', 'n_clicks')],
    [State('folder-path-input', 'value')]
)
def update_dashboard(n_clicks, folder_path):
    if n_clicks is None or not folder_path:
        raise PreventUpdate

    historical_data = load_historical_data(folder_path)
    if not historical_data:
        raise PreventUpdate

    # Extract data for plots
    total_water = [entry['clean_water_total'] for entry in historical_data]
    cycle_days = [f"[{entry['weather_info']['Cycle']}|{entry['weather_info']['CycleDay']}]" for entry in historical_data]

    def get_matrix(entry, key, shape):
        return  np.flipud(np.array(entry.get(key, np.zeros(shape)))  )

    width, height = historical_data[0]['map_width'], historical_data[0]['map_height']
    
    water_depth_frames = [
        go.Frame(
            data=go.Heatmap(
                z=get_matrix(entry, "water_levels_matrix", (height, width)),
                colorscale='Blues',
                hovertemplate='x: %{x}<br>y: %{y}<br>Water Depth: %{z:.2f}<extra></extra>'
            ),
            name=cycle_days[i]
        )
        for i, entry in enumerate(historical_data)
    ]

    contamination_frames = [
        go.Frame(
            data=go.Heatmap(
                z=get_matrix(entry, "contamination_matrix", (height, width)),
                colorscale='Reds',
                hovertemplate='x: %{x}<br>y: %{y}<br>Contamination Percentage: %{z:.2f}<extra></extra>'
            ),
            name=cycle_days[i]
        )
        for i, entry in enumerate(historical_data)
    ]

    moisture_frames = [
        go.Frame(
            data=go.Heatmap(
                z=get_matrix(entry, "moisture_levels_matrix", (height, width)),
                colorscale='Greens',
                hovertemplate='x: %{x}<br>y: %{y}<br>Moisture Level: %{z:.2f}<extra></extra>'
            ),
            name=cycle_days[i]
        )
        for i, entry in enumerate(historical_data)
    ]

    soil_contamination_frames = [
        go.Frame(
            data=go.Heatmap(
                z=get_matrix(entry, "soil_contamination_matrix", (height, width)),
                colorscale='Oranges',
                hovertemplate='x: %{x}<br>y: %{y}<br>Soil Contamination: %{z:.2f}<extra></extra>'
            ),
            name=cycle_days[i]
        )
        for i, entry in enumerate(historical_data)
    ]

    evaporation_frames = [
        go.Frame(
            data=go.Heatmap(
                z=get_matrix(entry, "evaporation_modifiers_matrix", (height, width)),
                colorscale='Purples',
                hovertemplate='x: %{x}<br>y: %{y}<br>Evaporation Modifier: %{z:.2f}<extra></extra>'
            ),
            name=cycle_days[i]
        )
        for i, entry in enumerate(historical_data)
    ]

    water_depth_fig = create_heatmap_figure(
        data=get_matrix(historical_data[0], "water_levels_matrix", (height, width)),
        frames=water_depth_frames,
        colorscale='Blues',
        hovertemplate='x: %{x}<br>y: %{y}<br>Water Depth: %{z:.2f}<extra></extra>'
    )

    contamination_fig = create_heatmap_figure(
        data=get_matrix(historical_data[0], "contamination_matrix", (height, width)),
        frames=contamination_frames,
        colorscale='Reds',
        hovertemplate='x: %{x}<br>y: %{y}<br>Contamination Percentage: %{z:.2f}<extra></extra>'
    )

    moisture_fig = create_heatmap_figure(
        data=get_matrix(historical_data[0], "moisture_levels_matrix", (height, width)),
        frames=moisture_frames,
        colorscale='Greens',
        hovertemplate='x: %{x}<br>y: %{y}<br>Moisture Level: %{z:.2f}<extra></extra>'
    )

    soil_contamination_fig = create_heatmap_figure(
        data=get_matrix(historical_data[0], "soil_contamination_matrix", (height, width)),
        frames=soil_contamination_frames,
        colorscale='Oranges',
        hovertemplate='x: %{x}<br>y: %{y}<br>Soil Contamination: %{z:.2f}<extra></extra>'
    )

    evaporation_fig = create_heatmap_figure(
        data=get_matrix(historical_data[0], "evaporation_modifiers_matrix", (height, width)),
        frames=evaporation_frames,
        colorscale='Purples',
        hovertemplate='x: %{x}<br>y: %{y}<br>Evaporation Modifier: %{z:.2f}<extra></extra>'
    )

    total_water_fig = go.Figure(
        data=go.Scatter(x=cycle_days, y=total_water, mode='lines+markers'),
        layout=go.Layout(
            title='Total Water Amount Over Time',
            xaxis_title='Cycle Day',
            yaxis_title='Total Water Amount'
        )
    )

    min_day = 0
    max_day = len(historical_data) - 1
    marks = {i: cycle_days[i] for i in range(len(cycle_days))}

    return water_depth_fig, contamination_fig, moisture_fig, soil_contamination_fig, evaporation_fig, total_water_fig, min_day, max_day, min_day, marks

# Function to open the browser after a delay
def open_browser():
    webbrowser.open_new(f"http://127.0.0.1:{PORT}/")

if __name__ == "__main__":
    Timer(1, open_browser).start()
    if check_port(PORT):
        app.run_server(debug=False, host="127.0.0.1", port=PORT)
    else:
        print(f"Error, another instance is already running (port {PORT} in use)")

    time.sleep(10)

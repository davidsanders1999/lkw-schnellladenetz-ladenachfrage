import os
import time
import pandas as pd
import numpy as np

# ------------------------------------------------------------------------------
# KONFIGURATION
# ------------------------------------------------------------------------------
CONFIG = {
    'INPUT_FILE_TRAFFIC_FLOW':  '01_Trucktrafficflow.csv',
    'INPUT_FILE_EDGES':         '04_network-edges.csv',
    'INPUT_FILE_NODES':         '03_network-nodes.csv',
    'OUTPUT_BREAKS':            'breaks.csv',
    'DISTANCE_THRESHOLD': 360,  # km -> Ab dieser Distanz wird eine Pause erzwungen
    'MAX_DISTANCE_SINGLEDRIVER': 4320  # km -> Grenze zw. Ein- und Zwei-Fahrer-Route
}

def parse_edge_string(edge_str: str) -> list:
    """
    Nimmt einen String, der Edge-IDs in eckigen Klammern enthält,
    und gibt eine Liste von Integers zurück.
    Beispiel: '[12,13,14]' -> [12, 13, 14]
    """
    try:
        edges_parsed = list(map(int, edge_str.strip('[]').split(',')))
        return edges_parsed
    except Exception:
        # Optional: Warnung ausgeben oder Fehler protokollieren
        return []

def main():
    """
    Hauptfunktion zum Einlesen und Verarbeiten von Daten 
    zur Ermittlung von 'Breaks' (Pausen) bei unterschiedlichen Fahrten.
    """
    time_start = time.time()

    # -------------------------------------------------------------------------
    # 1. Pfade festlegen und Daten importieren
    # -------------------------------------------------------------------------
    base_path = os.path.dirname(os.path.abspath(__file__))
    
    traffic_flow_path = os.path.join(base_path, 'Input', CONFIG['INPUT_FILE_TRAFFIC_FLOW'])
    edges_path        = os.path.join(base_path, 'Input', CONFIG['INPUT_FILE_EDGES'])
    nodes_path        = os.path.join(base_path, 'Input', CONFIG['INPUT_FILE_NODES'])
    
    # Einlesen der CSV-Dateien in DataFrames
    df_traffic_flow = pd.read_csv(traffic_flow_path, sep=',', decimal='.', index_col=0)
    df_edges        = pd.read_csv(edges_path,        sep=',', decimal='.', index_col=0)
    df_nodes        = pd.read_csv(nodes_path,        sep=',', decimal='.', index_col=0)
    
    print("Daten importiert.")
    
    # -------------------------------------------------------------------------
    # 2. Filtern des Traffic Flows
    # -------------------------------------------------------------------------
    # Unterschiedliche Behandlung von Ein-Fahrer (<= MAX_DISTANCE_SINGLEDRIVER) 
    # und Zwei-Fahrer (> MAX_DISTANCE_SINGLEDRIVER).
    
    max_singledriver_dist = CONFIG['MAX_DISTANCE_SINGLEDRIVER']
    
    df_traffic_flow_filtered = df_traffic_flow[
        (df_traffic_flow['Distance_from_origin_region_to_E_road'] 
         + df_traffic_flow['Distance_within_E_road'] > 0)
        & (df_traffic_flow['Distance_from_origin_region_to_E_road'] 
           + df_traffic_flow['Distance_within_E_road'] <= max_singledriver_dist)
        & (df_traffic_flow['Traffic_flow_trucks_2030'] > 0)
    ].copy()
    df_traffic_flow_filtered.reset_index(drop=True, inplace=True)
    
    df_traffic_flow_filtered_two_driver = df_traffic_flow[
        (df_traffic_flow['Distance_from_origin_region_to_E_road'] 
         + df_traffic_flow['Distance_within_E_road'] > max_singledriver_dist)
        & (df_traffic_flow['Traffic_flow_trucks_2030'] > 0)
    ].copy()
    df_traffic_flow_filtered_two_driver.reset_index(drop=True, inplace=True)
    
    # -------------------------------------------------------------------------
    # 3. Umwandeln der Edge-Strings in Listen von Edge-IDs
    # -------------------------------------------------------------------------
    list_trip_edges_strings = df_traffic_flow_filtered['Edge_path_E_road'].tolist()
    list_trip_edges_strings_two_driver = df_traffic_flow_filtered_two_driver['Edge_path_E_road'].tolist()
    
    list_trip_edges = [parse_edge_string(s) for s in list_trip_edges_strings]
    list_trip_edges_two_driver = [parse_edge_string(s) for s in list_trip_edges_strings_two_driver]
    
    # -------------------------------------------------------------------------
    # 4. Erstellen von Dictionaries für Edges und Nodes
    # -------------------------------------------------------------------------
    dict_edge_length = df_edges.set_index('Network_Edge_ID')['Distance'].to_dict()
    dict_edge_node_b = df_edges.set_index('Network_Edge_ID')['Network_Node_B_ID'].to_dict()
    dict_node_lat    = df_nodes.set_index('Network_Node_ID')['Network_Node_Y'].to_dict()
    dict_node_lon    = df_nodes.set_index('Network_Node_ID')['Network_Node_X'].to_dict()
    
    # -------------------------------------------------------------------------
    # 5. Erstellen von Listen aus DataFrame-Spalten
    # -------------------------------------------------------------------------
    list_trip_traffic             = df_traffic_flow_filtered['Traffic_flow_trucks_2030'].tolist()
    list_distance_origin_road     = df_traffic_flow_filtered['Distance_from_origin_region_to_E_road'].tolist()
    
    list_trip_traffic_two_driver  = df_traffic_flow_filtered_two_driver['Traffic_flow_trucks_2030'].tolist()
    list_distance_origin_road_two_driver = df_traffic_flow_filtered_two_driver['Distance_from_origin_region_to_E_road'].tolist()
    
    # -------------------------------------------------------------------------
    # 6. Zuweisen von Breaks (Pausen) bei Fahrten
    # -------------------------------------------------------------------------
    # Annahme: Jede Fahrt wird segmentiert, sobald 'DISTANCE_THRESHOLD' km 
    # zurückgelegt wurden.
    
    trip_distance = CONFIG['DISTANCE_THRESHOLD']  # 360 km, lt. CONFIG
    
    # Dictionary zum Sammeln aller Pausendaten
    dict_break = {
        'Trip_ID': [],
        'Driver': [],
        'Break_Nr': [],
        'Break_Type': [],
        'Edge': [],
        'Edge_length': [],
        'Node_B': [],
        'Latitude_B': [],
        'Longitude_B': [],
        'Break_Number': []  # Truck-Anzahl für diese Pause
    }
    
    # -------------------------------------------------------------------------
    # 6a. Zuweisen der Pausen für Ein-Fahrer-Fahrten
    # -------------------------------------------------------------------------
    for index, edges_list in enumerate(list_trip_edges):
        
        travel_distance = list_distance_origin_road[index]  # Start-Distanz
        breaks = 0  # Zähler für Pausen (zur Bestimmung short/long)
        
        for edge_id in edges_list:
            travel_distance += dict_edge_length[edge_id]
            # Überprüfung: Wird die maximale Distanz erreicht?
            if travel_distance > (trip_distance + np.random.randint(-50, 50)):
                travel_distance = 0
                breaks += 1
                
                break_edge_id        = edge_id
                break_edge_length    = dict_edge_length[break_edge_id]
                break_edge_node_b    = dict_edge_node_b[edge_id]
                break_node_id        = break_edge_node_b
                break_node_lat       = dict_node_lat[break_node_id]
                break_node_lon       = dict_node_lon[break_node_id]
                break_traffic_number = list_trip_traffic[index]
                
                # Unterscheidung short/long (gerade vs. ungerade Pausen-Nummer)
                if breaks % 2 == 1:
                    break_type = 'short'
                else:
                    break_type = 'long'
                
                dict_break['Trip_ID'].append(index)
                dict_break['Driver'].append(1)
                dict_break['Break_Nr'].append(breaks)
                dict_break['Break_Type'].append(break_type)
                dict_break['Edge'].append(break_edge_id)
                dict_break['Edge_length'].append(break_edge_length)
                dict_break['Node_B'].append(break_node_id)
                dict_break['Latitude_B'].append(break_node_lat)
                dict_break['Longitude_B'].append(break_node_lon)
                dict_break['Break_Number'].append(break_traffic_number)
    
    # -------------------------------------------------------------------------
    # 6b. Zuweisen der Pausen für Zwei-Fahrer-Fahrten
    # -------------------------------------------------------------------------
    # Logik: Bei 2 Fahrern wird nach 2 kurzen Pausen die nächste Pause lang, 
    # danach wieder Reset (0).
    for index, edges_list in enumerate(list_trip_edges_two_driver):
        
        travel_distance = list_distance_origin_road_two_driver[index]
        breaks = 0        # Zähler für alle Pausen
        breaks_reset = 0  # Zählt die kurzen Pausen bis zur nächsten langen Pause
        
        for edge_id in edges_list:
            travel_distance += dict_edge_length[edge_id]
            # Wird die maximale Distanz überschritten?
            if travel_distance > (trip_distance + np.random.randint(-50, 50)):
                travel_distance = 0
                breaks += 1
                
                break_edge_id        = edge_id
                break_edge_length    = dict_edge_length[break_edge_id]
                break_edge_node_b    = dict_edge_node_b[edge_id]
                break_node_id        = break_edge_node_b
                break_node_lat       = dict_node_lat[break_node_id]
                break_node_lon       = dict_node_lon[break_node_id]
                break_traffic_number = list_trip_traffic_two_driver[index]
                
                # Wenn weniger als oder gleich 2 Kurzpausen, dann "short"
                # Sonst "long" und Reset
                if breaks_reset <= 2:
                    break_type   = 'short'
                    breaks_reset += 1
                else:
                    break_type   = 'long'
                    breaks_reset = 0
                
                dict_break['Trip_ID'].append(index)
                dict_break['Driver'].append(2)
                dict_break['Break_Nr'].append(breaks)
                dict_break['Break_Type'].append(break_type)
                dict_break['Edge'].append(break_edge_id)
                dict_break['Edge_length'].append(break_edge_length)
                dict_break['Node_B'].append(break_node_id)
                dict_break['Latitude_B'].append(break_node_lat)
                dict_break['Longitude_B'].append(break_node_lon)
                dict_break['Break_Number'].append(break_traffic_number)
    
    # -------------------------------------------------------------------------
    # 7. Erstellen des Ergebnis-DataFrames und Sortierung
    # -------------------------------------------------------------------------
    df_breaks = pd.DataFrame(dict_break)
    df_breaks.sort_values(by=['Trip_ID', 'Break_Nr'], inplace=True)
    df_breaks.reset_index(drop=True, inplace=True)
    
    # -------------------------------------------------------------------------
    # 8. Validierung und Export
    # -------------------------------------------------------------------------
    short_breaks_count = len(df_breaks[df_breaks['Break_Type'] == 'short'])
    long_breaks_count  = len(df_breaks[df_breaks['Break_Type'] == 'long'])
    
    print("Short Breaks:", short_breaks_count)
    print("Long Breaks:", long_breaks_count)
    
    output_path = os.path.join(base_path, 'output', CONFIG['OUTPUT_BREAKS'])
    df_breaks.to_csv(output_path, sep=';', decimal=',', index=False)
    print(f"Datei exportiert unter: {output_path}")
    
    # -------------------------------------------------------------------------
    # 9. Zeitmessung
    # -------------------------------------------------------------------------
    time_end = time.time()
    time_total = time_end - time_start
    print(f"Gesamtdauer: {time_total:.2f} Sekunden.")

if __name__ == '__main__':
    main()
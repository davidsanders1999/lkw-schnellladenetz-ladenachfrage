import os
import time
import pandas as pd
import geopandas as gpd
import numpy as np
import matplotlib.pyplot as plt

# --------------------------------------------------------------------------
# KONFIGURATION
# --------------------------------------------------------------------------
CONFIG = {
    'BUFFER_RADIUS': 40000,          # Radius für den Zuordnungsradius (in Metern)
    'INPUT_AUSSCHREIBUNG': 'ausschreibung_deutschlandnetz.xlsx',
    'INPUT_GPKG': 'DE_NUTS5000.gpkg',
    'INPUT_BREAKS': 'breaks.csv',
    'OUTPUT_AUSSCHREIBUNG': 'ausschreibung_deutschlandnetz_breaks.xlsx',
    'OUTPUT_MAP': 'karte_breaks.png',
    'CRS_TARGET': 'EPSG:32632'       # Ziel-Koordinatensystem
}

def load_data(base_path: str) -> tuple:
    """
    Lädt alle erforderlichen Daten in DataFrames/GeoDataFrames und gibt sie zurück.
    """
    # Pfade definieren
    ausschreibung_path = os.path.join(base_path, 'Input', CONFIG['INPUT_AUSSCHREIBUNG'])
    nuts1_path         = os.path.join(base_path, "Input", CONFIG['INPUT_GPKG'])
    breaks_path        = os.path.join(base_path, 'output', CONFIG['INPUT_BREAKS'])
    
    # Einlesen der Dateien
    df_ausschreibung      = pd.read_excel(ausschreibung_path)
    gdf_deutschland_nuts1 = gpd.read_file(nuts1_path, layer='nuts5000_n1')
    df_breaks             = pd.read_csv(breaks_path, sep=';', decimal=',', index_col=0)
    
    # Aufteilen in Short und Long Breaks
    df_short_breaks = df_breaks[df_breaks['Break_Type'] == 'short'].copy()
    df_long_breaks  = df_breaks[df_breaks['Break_Type'] == 'long'].copy()
    
    return df_ausschreibung, gdf_deutschland_nuts1, df_short_breaks, df_long_breaks

def create_geodataframes(
    df_ausschreibung: pd.DataFrame,
    gdf_deutschland_nuts1: gpd.GeoDataFrame,
    df_short_breaks: pd.DataFrame,
    df_long_breaks: pd.DataFrame,
    buffer_radius: float = 25000,
    target_crs: str = 'EPSG:32632'
) -> tuple:
    """
    Erzeugt alle benötigten GeoDataFrames aus den geladenen Daten,
    transformiert sie ins gewünschte Koordinatensystem 'target_crs',
    und erstellt zudem einen Kreis-Puffer (buffer_radius) um die Ausschreibungspunkte.
    """
    # GeoDataFrame für die Ladepunkte (Ausschreibung)
    gdf_ausschreibung = gpd.GeoDataFrame(
        df_ausschreibung,
        geometry=gpd.points_from_xy(df_ausschreibung.Laengengrad, df_ausschreibung.Breitengrad),
        crs='EPSG:4326'
    )
    
    # GeoDataFrames für Short und Long Breaks
    gdf_short_breaks = gpd.GeoDataFrame(
        df_short_breaks,
        geometry=gpd.points_from_xy(df_short_breaks.Longitude_B, df_short_breaks.Latitude_B),
        crs='EPSG:4326'
    ).drop(columns=['Longitude_B', 'Latitude_B'])
    
    gdf_long_breaks = gpd.GeoDataFrame(
        df_long_breaks,
        geometry=gpd.points_from_xy(df_long_breaks.Longitude_B, df_long_breaks.Latitude_B),
        crs='EPSG:4326'
    ).drop(columns=['Longitude_B', 'Latitude_B'])
    
    # Deutschland-Geometrie auf NUTS0-Ebene aggregieren und nur Geometrie behalten
    gdf_deutschland_nuts0 = gdf_deutschland_nuts1.dissolve(by='NUTS_LEVEL')[['geometry']]
    gdf_deutschland_nuts0.reset_index(drop=True, inplace=True)
    
    # Transformieren ins Ziel-Koordinatensystem
    gdf_ausschreibung     = gdf_ausschreibung.to_crs(target_crs)
    gdf_short_breaks      = gdf_short_breaks.to_crs(target_crs)
    gdf_long_breaks       = gdf_long_breaks.to_crs(target_crs)
    gdf_deutschland_nuts0 = gdf_deutschland_nuts0.to_crs(target_crs)
    
    # Kreis-Buffer um jeden Punkt (z.B. 25 km)
    gdf_ausschreibung_kreis = gdf_ausschreibung.copy()
    gdf_ausschreibung_kreis['geometry'] = gdf_ausschreibung['geometry'].buffer(buffer_radius)
    
    return (gdf_ausschreibung,
            gdf_short_breaks,
            gdf_long_breaks,
            gdf_deutschland_nuts0,
            gdf_ausschreibung_kreis)

def filter_breaks_in_germany(
    gdf_breaks: gpd.GeoDataFrame,
    gdf_deutschland_nuts0: gpd.GeoDataFrame
) -> gpd.GeoDataFrame:
    """
    Begrenzt die Break-GeoDataFrames auf Punkte innerhalb Deutschlands,
    indem ein Spatial Join ('within') durchgeführt wird.
    """
    gdf_filtered = gpd.sjoin(gdf_breaks, gdf_deutschland_nuts0, how='inner', predicate='within')
    gdf_filtered = gdf_filtered.drop(columns='index_right')
    gdf_filtered.reset_index(drop=True, inplace=True)
    print(len(gdf_filtered))
    return gdf_filtered

def assign_breaks_to_points(
    gdf_breaks_in_germany: gpd.GeoDataFrame,
    gdf_ausschreibung: gpd.GeoDataFrame,
    gdf_ausschreibung_kreis: gpd.GeoDataFrame,
    anschlussleistung_col: str,
    breaks_colname: str
) -> pd.Series:
    """
    Weist jeder Zeile in gdf_breaks_in_germany einen Standort (Index in gdf_ausschreibung) zu,
    basierend auf:
      1) Ist der Punkt im Kreis-Puffer enthalten? Falls mehrere, wähle den Kreis
         mit minimalem Verhältnis (Summe Breaks / Netzanschlussleistung).
      2) Falls kein Kreis den Punkt enthält, suche den nächstgelegenen Kreis (Minimum distance).
    
    Liefert eine Series zurück, die die Anzahl Breaks pro Standort enthält.
    """
    # Liste für Break-Anzahlen, initiiert mit 0
    results_breaks = [0]*len(gdf_ausschreibung)
    
    # Extrahieren notwendiger Daten als Listen (Beschleunigt wiederholten Zugriff)
    list_anschlussleistung = gdf_ausschreibung[anschlussleistung_col].tolist()
    list_break_numbers     = gdf_breaks_in_germany['Break_Number'].tolist()
    
    polygons_kreis = gdf_ausschreibung_kreis['geometry']
    
    # Durch alle Break-Punkte iterieren
    for idx, row in gdf_breaks_in_germany.iterrows():
        point_geom  = row.geometry
        break_count = list_break_numbers[idx]
        
        if break_count >= 10000:
            print(break_count)
        
        # Prüfen, ob mind. ein Kreis den Punkt enthält
        contained = polygons_kreis.contains(point_geom)
        contained_indices = np.where(contained)[0]  # Indexliste der True-Werte
        
        if len(contained_indices) == 0:
            # Kein Kreis enthält den Punkt -> Finde nächstgelegenen Kreis
            distances = polygons_kreis.distance(point_geom)
            nearest_geom_idx = distances.idxmin()
            results_breaks[nearest_geom_idx] += break_count
            continue
        
        if len(contained_indices) == 1:
            # Genau ein Kreis enthält den Punkt -> Direkt zuweisen
            kreis_idx = contained_indices[0]
            results_breaks[kreis_idx] += break_count
            continue
        
        # Mehrere Kreise enthalten den Punkt -> Minimaler Wert von (Breaks)
        min_ratio_value = float('inf')
        selected_kreis  = None
        for kreis_idx in contained_indices:
            # Verhindern einer Division durch 0
            
            current_ratio = results_breaks[kreis_idx]
            
            if current_ratio < min_ratio_value:
                min_ratio_value = current_ratio
                selected_kreis  = kreis_idx
        
        results_breaks[selected_kreis] += break_count
    
    # Rückgabe als Pandas Series
    return pd.Series(results_breaks, index=gdf_ausschreibung.index, name=breaks_colname)

def main():
    # -------------------------
    # 1. Startzeit messen
    # -------------------------
    start_time = time.time()
    
    # -------------------------
    # 2. Daten laden
    # -------------------------
    base_path = os.path.dirname(os.path.abspath(__file__))
    (df_ausschreibung,
     gdf_deutschland_nuts1,
     df_short_breaks,
     df_long_breaks) = load_data(base_path)
    
    print('Daten eingelesen.')
    
    # -------------------------
    # 3. GeoDataFrames erstellen & transformieren
    #    Buffer-Radius aus CONFIG
    # -------------------------
    (gdf_ausschreibung,
     gdf_short_breaks,
     gdf_long_breaks,
     gdf_deutschland_nuts0,
     gdf_ausschreibung_kreis) = create_geodataframes(
         df_ausschreibung,
         gdf_deutschland_nuts1,
         df_short_breaks,
         df_long_breaks,
         buffer_radius=CONFIG['BUFFER_RADIUS'],
         target_crs=CONFIG['CRS_TARGET']
     )
    
    # -------------------------
    # 4. Break-Punkte auf Deutschland beschränken
    # -------------------------
    gdf_short_breaks_germany = filter_breaks_in_germany(gdf_short_breaks, gdf_deutschland_nuts0)
    gdf_long_breaks_germany  = filter_breaks_in_germany(gdf_long_breaks,  gdf_deutschland_nuts0)
    
    # -------------------------
    # 5. Breaks zuordnen
    # -------------------------
    # 5a. Short-Breaks
    short_breaks_series = assign_breaks_to_points(
        gdf_short_breaks_germany,
        gdf_ausschreibung,
        gdf_ausschreibung_kreis,
        anschlussleistung_col='Netzanschlussleistung',
        breaks_colname='short_breaks_2030'
    )
    gdf_ausschreibung['short_breaks_2030'] = short_breaks_series
    
    print('Short Breaks zugeordnet.')
    
    # 5b. Long-Breaks
    long_breaks_series = assign_breaks_to_points(
        gdf_long_breaks_germany,
        gdf_ausschreibung,
        gdf_ausschreibung_kreis,
        anschlussleistung_col='Netzanschlussleistung',
        breaks_colname='long_breaks_2030'
    )
    gdf_ausschreibung['long_breaks_2030'] = long_breaks_series
    
    gdf_ausschreibung['Sum'] = short_breaks_series + long_breaks_series
    
    print('Long Breaks zugeordnet.')
    
    # -------------------------
    # 6. Ergebnisse exportieren
    # -------------------------
    output_path = os.path.join(base_path, 'output', CONFIG['OUTPUT_AUSSCHREIBUNG'])
    gdf_ausschreibung.drop(columns='geometry').to_excel(output_path, index=False)
    print(f'Ergebnisse exportiert: {output_path}')
    
    # -------------------------
    # 7. Plot (optional)
    # -------------------------
    fig, ax = plt.subplots()
    # gdf_deutschland_nuts0.plot(ax=ax, facecolor='none', edgecolor='black')
    # gdf_short_breaks_germany.plot(ax=ax, markersize=1)
    # gdf_long_breaks_germany.plot(ax=ax, markersize=1)
    gdf_ausschreibung_kreis.plot(ax=ax, facecolor='none', edgecolor='black', alpha=0.5)
    fig.set_size_inches(9, 9)
    
    output_map_path = os.path.join(base_path, 'output', CONFIG['OUTPUT_MAP'])
    fig.savefig(output_map_path, dpi=150)
    plt.close(fig)
    print(f'Karte erstellt: {output_map_path}')
    
    # -------------------------
    # 8. Validierung
    # -------------------------
    # Menge an Breaks im Input
    sum_short_breaks_in = gdf_short_breaks_germany['Break_Number'].sum()
    sum_long_breaks_in  = gdf_long_breaks_germany['Break_Number'].sum()
    print("Menge an Breaks (Inputdaten)")
    print((sum_short_breaks_in + sum_long_breaks_in) * 0.15 / 330)
    
    # Menge an Breaks im Output
    sum_short_breaks_out = gdf_ausschreibung['short_breaks_2030'].sum()
    sum_long_breaks_out  = gdf_ausschreibung['long_breaks_2030'].sum()
    print("Menge an Breaks (Outputdaten)")
    print((sum_short_breaks_out + sum_long_breaks_out) * 0.15 / 330)

    # -------------------------
    # 9. Zeitmessung
    # -------------------------
    end_time = time.time()
    duration = end_time - start_time
    print(f'Gesamtdauer: {duration:.2f} sec')
    

if __name__ == '__main__':
    main()
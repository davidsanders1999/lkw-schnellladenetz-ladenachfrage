import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

# ------------------------------------------------------------------------------
# KONFIGURATION
# ------------------------------------------------------------------------------
CONFIG = {
    # Pfade: Eingabe/Ausgabe
    'INPUT_FILE_AUSSCHREIBUNG':  os.path.join('output', 'ausschreibung_deutschlandnetz_laden_mauttabelle.csv'),
    'OUTPUT_FILE_CLUSTER':       os.path.join('output', 'ladevorgaenge_daily_cluster.csv'),
    'OUTPUT_FILE_AUSSCHREIBUNG': os.path.join('output', 'ausschreibung_deutschlandnetz_laden_mauttabelle_cl.xlsx'),
    
    # Zu verwendende Spalten (schnell & nacht je Wochentag)
    'FEATURE_COLUMNS': [
        'Montag_schnell', 'Dienstag_schnell', 'Mittwoch_schnell', 'Donnerstag_schnell', 'Freitag_schnell', 'Samstag_schnell', 'Sonntag_schnell',
        'Montag_nacht', 'Dienstag_nacht', 'Mittwoch_nacht', 'Donnerstag_nacht', 'Freitag_nacht', 'Samstag_nacht', 'Sonntag_nacht'
    ],
    
    # K-Means-Parameter
    'KMEANS': {
        'n_clusters': 3,
        'init': 'k-means++',
        'n_init': 10,
        'max_iter': 300,
        'random_state': 42
    },
    
    # Mapping für Wochentage
    'WOCHENTAG_MAP': {
        'Montag': 1, 
        'Dienstag': 2, 
        'Mittwoch': 3, 
        'Donnerstag': 4, 
        'Freitag': 5, 
        'Samstag': 6, 
        'Sonntag': 7
    }
}

# ------------------------------------------------------------------------------
# FUNKTIONEN
# ------------------------------------------------------------------------------
def load_data(config: dict) -> pd.DataFrame:
    """
    Liest die Ausschreibungsdaten mit Tages-schnell- und nacht-Werten ein.
    Gibt ein DataFrame zurück.
    """
    base_path = os.path.dirname(os.path.abspath(__file__))
    input_file = os.path.join(base_path, config['INPUT_FILE_AUSSCHREIBUNG'])
    df_data = pd.read_csv(input_file, index_col=0, sep=";", decimal=",")
    return df_data


def preprocess_data(df_data: pd.DataFrame, config: dict) -> pd.DataFrame:
    """
    Selektiert die relevanten Spalten und entfernt Zeilen, in denen Montag_schnell = 0 (bspw. ungenutzte Standorte).
    Skaliert anschließend die Daten (StandardScaler).
    Gibt das skalierte DataFrame und den Scaler zurück.
    """
    # Nur relevante Spalten extrahieren
    df_features = df_data[config['FEATURE_COLUMNS']].copy()
    
    # Entferne Zeilen, in denen 'Montag_schnell' = 0
    # df_features = df_features[df_features['Montag_schnell'] != 0]
    
    # Skalierung
    scaler = StandardScaler()
    scaled_array = scaler.fit_transform(df_features)
    df_scaled = pd.DataFrame(scaled_array, columns=df_features.columns, index=df_features.index)
    
    return df_scaled, scaler


def perform_kmeans(df_scaled: pd.DataFrame, config: dict) -> tuple:
    """
    Führt das K-Means-Clustering auf den skalierten Daten durch und gibt
    das angepasste KMeans-Modell sowie die ermittelten Cluster-Zuordnungen zurück.
    """
    kmeans_params = config['KMEANS']
    kmeans = KMeans(
        n_clusters=kmeans_params['n_clusters'],
        init=kmeans_params['init'],
        n_init=kmeans_params['n_init'],
        max_iter=kmeans_params['max_iter'],
        random_state=kmeans_params['random_state']
    )
    kmeans.fit(df_scaled)
    cluster_labels = kmeans.labels_
    return kmeans, cluster_labels


def create_cluster_centers(kmeans: KMeans, scaler: StandardScaler, config: dict) -> pd.DataFrame:
    """
    Erzeugt ein DataFrame mit den (rücktransformierten) Cluster-Zentren 
    und sortiert es nach der Spalte 'Montag_schnell' aufsteigend.
    """
    # Rücktransformation der Clusterzentren
    cluster_centers_scaled = kmeans.cluster_centers_
    cluster_centers = scaler.inverse_transform(cluster_centers_scaled)
    
    df_centers = pd.DataFrame(cluster_centers, columns=config['FEATURE_COLUMNS'])
    df_centers.sort_values(by='Montag_schnell', ascending=True, inplace=True)
    df_centers.reset_index(drop=True, inplace=True)
    
    return df_centers


def create_cluster_df(df_centers: pd.DataFrame, config: dict) -> pd.DataFrame:
    """
    Erstellt aus den Cluster-Zentren ein DataFrame, in dem jede Zeile 
    'Cluster, Wochentag, Ladetype, Anzahl' repräsentiert.
    Die Clusternummer wird um 1 erhöht, um bei 1 zu starten.
    """
    dict_cluster = {
        'Cluster': [],
        'Wochentag': [],
        'Ladetype': [],
        'Anzahl': []
    }
    
    # Anzahl der Cluster
    num_clusters = len(df_centers)
    
    # Mögliche Wochentage
    weekdays = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']
    ladetypes = ['schnell', 'nacht']
    dict_lt = {'schnell': 'Schnelllader', 'nacht': 'Nachtlader'}
    
    for cluster_idx in range(num_clusters):
        for day in weekdays:
            for lt in ladetypes:
                dict_cluster['Cluster'].append(cluster_idx + 1)
                dict_cluster['Wochentag'].append(day)
                dict_cluster['Ladetype'].append(dict_lt[lt])
                
                wert = df_centers.loc[cluster_idx, f"{day}_{lt}"]
                # Runden auf ganze Zahl
                dict_cluster['Anzahl'].append(round(wert))
    
    df_cluster = pd.DataFrame(dict_cluster)
    
    # Sortierung
    #  1) Nach Cluster,
    #  2) Laden-Typ,
    #  3) Wochentag
    df_cluster.sort_values(by=['Cluster','Ladetype','Wochentag'], inplace=True)
    df_cluster.reset_index(drop=True, inplace=True)
    
    # Mapping Wochentag und Ladetype
    df_cluster['Wochentag'] = df_cluster['Wochentag'].map(config['WOCHENTAG_MAP'])
    df_cluster.sort_values(by=['Cluster', 'Ladetype', 'Wochentag'], inplace=True)
    
    return df_cluster


def save_results(df_data: pd.DataFrame,
                 df_centers: pd.DataFrame,
                 df_cluster: pd.DataFrame,
                 cluster_labels: np.ndarray,
                 config: dict) -> None:
    """
    Hängt dem ursprünglichen DataFrame die Cluster-Labels an,
    exportiert das `df_cluster` mit den Clusterzusammenfassungen 
    und kann optional Visualisierungen oder andere Analysen anstoßen.
    """
    base_path = os.path.dirname(os.path.abspath(__file__))
    output_file = os.path.join(base_path, config['OUTPUT_FILE_CLUSTER'])
    
    # Option: Cluster-Labels zum Original-Datensatz hinzufügen (falls gewünscht)
    df_data['Cluster'] = cluster_labels  # -> Nur wenn man df_data noch exportieren möchte.
    
    # Export des clusterisierten Ergebnisses
    df_cluster.to_csv(output_file, sep=";", decimal=",", index=False)
    
    # Export des ursprünglichen Datensatzes mit Cluster-Labels 
    df_data.to_excel(config['OUTPUT_FILE_AUSSCHREIBUNG'])
    
    print(f"Cluster-Zusammenfassung exportiert.")


def main():
    """
    Hauptfunktion:
      1. Daten laden
      2. Daten vorbereiten (filtern, skalieren)
      3. K-Means-Clustering ausführen
      4. Clusterzentren rücktransformieren
      5. Zusammenfassendes DataFrame (Cluster-Werte pro Wochentag/Ladetype) erstellen
      6. Ergebnisse speichern
    """
    # 1. Daten laden
    df_data = load_data(CONFIG)
    
    # 2. Vorverarbeitung (Filtern & Skalieren)
    df_scaled, scaler = preprocess_data(df_data, CONFIG)
    
    # 3. K-Means-Clustering
    kmeans_model, cluster_labels = perform_kmeans(df_scaled, CONFIG)
    
    # 4. Clusterzentren rücktransformieren
    df_centers = create_cluster_centers(kmeans_model, scaler, CONFIG)
    
    # 5. DataFrame erstellen (Cluster, Wochentag, Ladetype, Anzahl)
    df_cluster = create_cluster_df(df_centers, CONFIG)
    
    # 6. Speichern
    save_results(df_data, df_centers, df_cluster, cluster_labels, CONFIG)


if __name__ == '__main__':
    main()
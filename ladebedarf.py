import os
import pandas as pd
import numpy as np

# ------------------------------------------------------------------------------
# KONFIGURATION
# ------------------------------------------------------------------------------
CONFIG = {
    # Eingabe- und Ausgabedateien
    'INPUT_FILE_BREAKS':      os.path.join('Output', 'ausschreibung_deutschlandnetz_breaks.xlsx'),
    'INPUT_FILE_BEFAHRUNG':   os.path.join('Input', 'Befahrungen_25_1Q.csv'),
    'INPUT_FILE_MAUTTABELLE': os.path.join('Input', 'Mauttabelle.xlsx'),
    'OUTPUT_FILE':            os.path.join('Output', 'ausschreibung_deutschlandnetz_laden_mauttabelle.csv'),
    
    # Parameter
    'R_BEV_2035': 0.74,
    'R_TRAFFIC_2035': 1.041,
    'R_SECTION': 0.6,
    
    # Relevante Spalten / Einstellungen
    'HIGHWAY_COL': 'Bundesautobahn',   # Name der Spalte, in der Autobahnkürzel stehen
    'DISTANCE_COL': 'distance',        # Temporäre Distanzspalte
}

# ------------------------------------------------------------------------------
# FUNKTIONEN
# ------------------------------------------------------------------------------
def load_data(config: dict) -> tuple:
    """
    Lädt die Ausschreibungsdaten (Breaks), die Befahrungen (CSV) und die Mauttabelle (XLSX).
    Gibt drei DataFrames zurück.
    """
    base_path = os.path.dirname(os.path.abspath(__file__))
    
    # Pfade auflösen
    path_breaks      = os.path.join(base_path, config['INPUT_FILE_BREAKS'])
    path_befahrung   = os.path.join(base_path, config['INPUT_FILE_BEFAHRUNG'])
    path_mauttabelle = os.path.join(base_path, config['INPUT_FILE_MAUTTABELLE'])
    
    # Einlesen
    df_ausschreibung = pd.read_excel(path_breaks)
    df_befahrung     = pd.read_csv(path_befahrung, sep=';')
    df_mauttabelle   = pd.read_excel(path_mauttabelle, header=1)
    
    # String-Trim
    df_mauttabelle['Bundesfernstraße'] = df_mauttabelle['Bundesfernstraße'].str.strip()
    df_ausschreibung['Bundesautobahn'] = df_ausschreibung['Bundesautobahn'].str.strip()
    
    return df_ausschreibung, df_befahrung, df_mauttabelle


def calculate_schnell_nacht(df_ausschreibung: pd.DataFrame, config: dict) -> pd.DataFrame:
    """
    Berechnet schnell_2035 und nacht_2035 auf Basis der Spalten 
    'short_breaks_2030' und 'long_breaks_2030' und den Faktoren 
    R_BEV_2035 und R_TRAFFIC_2035 aus der Konfiguration.
    """
    r_bev_2035     = config['R_BEV_2035']
    r_traffic_2035 = config['R_TRAFFIC_2035']
    r_section      = config['R_SECTION']
    
    df_ausschreibung['schnell_2035'] = (
        df_ausschreibung['short_breaks_2030'] 
        * r_bev_2035 
        * r_traffic_2035
        * r_section
    )
    df_ausschreibung['nacht_2035'] = (
        df_ausschreibung['long_breaks_2030'] 
        * r_bev_2035 
        * r_traffic_2035
        * r_section
    )
    return df_ausschreibung


def update_mauttabelle_with_befahrung(df_mauttabelle: pd.DataFrame, df_befahrung: pd.DataFrame) -> pd.DataFrame:
    """
    Aktualisiert die Mauttabelle-Spalten (Mo-So) mit den Werten aus df_befahrung.
    Dabei wird für jede 'Strecken-ID' in df_befahrung der entsprechende 'Abschnitts-ID'
    in df_mauttabelle gesucht.
    """
    # Kopie anlegen nach dem Filtern, um SettingWithCopyWarning zu vermeiden
    df_mauttabelle = df_mauttabelle.loc[~df_mauttabelle['Bundesfernstraße'].str.contains('B')].copy()
    
    # Aktualisieren mithilfe einer Schleife (oder Merge bei großen Datenmengen)
    for _, row in df_befahrung.iterrows():
        mask = (df_mauttabelle['Abschnitts-ID'] == row['Strecken-ID'])
        if not mask.any():
            continue
        
        df_mauttabelle.loc[mask, 'Montag']    = row['Montag']
        df_mauttabelle.loc[mask, 'Dienstag'] = row['Dienstag']
        df_mauttabelle.loc[mask, 'Mittwoch'] = row['Mittwoch']
        df_mauttabelle.loc[mask, 'Donnerstag'] = row['Donnerstag']
        df_mauttabelle.loc[mask, 'Freitag']  = row['Freitag']
        df_mauttabelle.loc[mask, 'Samstag']  = row['Samstag']
        df_mauttabelle.loc[mask, 'Sonntag']  = row['Sonntag']
    
    return df_mauttabelle


def find_closest_row(ausschreibung_row: pd.Series, df_mauttabelle: pd.DataFrame, config: dict) -> pd.Series:
    """
    Findet in df_mauttabelle den am nächsten gelegenen Autobahn-Abschnitt 
    basierend auf Mittelwerten von Länge/Breite. 
    Gibt die Spalten dieses 'nächsten' Abschnitts als Series zurück.
    """
    laengengrad = ausschreibung_row['Laengengrad']
    breitengrad = ausschreibung_row['Breitengrad']
    autobahn    = ausschreibung_row[config['HIGHWAY_COL']]
    
    # Kopie anlegen, damit Zuweisungen eindeutig auf diese Teilmenge erfolgen
    df_filtered = df_mauttabelle.loc[df_mauttabelle['Bundesfernstraße'] == autobahn].copy()
    if df_filtered.empty:
        raise ValueError(f'Keine Daten für Autobahn = {autobahn} vorhanden.')
    
    # Distanzspalte hinzufügen
    df_filtered[config['DISTANCE_COL']] = np.sqrt(
        (
            ((df_filtered['Länge Von'] + df_filtered['Länge Nach']) / 2) - laengengrad
        )**2 + 
        (
            ((df_filtered['Breite Von'] + df_filtered['Breite Nach']) / 2) - breitengrad
        )**2
    )
    
    # Nächste Zeile bestimmen
    closest_index = df_filtered[config['DISTANCE_COL']].idxmin()
    return df_filtered.loc[closest_index]


def assign_closest_rows(df_ausschreibung: pd.DataFrame, df_mauttabelle: pd.DataFrame, config: dict) -> pd.DataFrame:
    """
    Wendet find_closest_row pro Zeile des df_ausschreibung an und 
    hängt die ermittelten Spalten (z. B. Montag-Sonntag) an df_ausschreibung an.
    """
    # Für Statistik/Debug
    closest_series = df_ausschreibung.apply(
        lambda row: find_closest_row(row, df_mauttabelle, config),
        axis=1
    )
    
    # Concat: erweiterte DF mit Spalten des 'closest' Datensatzes
    df_result = pd.concat([df_ausschreibung, closest_series.reset_index(drop=True)], axis=1)
    
    # # Distanz-Statistik ausgeben
    # distances = closest_series[config['DISTANCE_COL']].tolist()
    # print("Statistiken Distanz:")
    # print(f"  Kleinste Distanz: {min(distances):.6f}")
    # print(f"  Größte Distanz:  {max(distances):.6f}")
    
    return df_result


def compute_weekday_shares(df_ausschreibung: pd.DataFrame) -> pd.DataFrame:
    """
    Normalisiert die Mauttabelle-Werte (Mo-So) pro Zeile und berechnet daraus
    schnell- und nacht-Werte pro Wochentag (geteilt durch 52).
    """
    weekdays = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']
    
    for idx, row in df_ausschreibung.iterrows():
        total = row[weekdays].sum()
        if total == 0:
            continue
        
        # Berechnungen erfolgen auf .loc, um SettingWithCopy zu vermeiden
        for day in weekdays:
            day_share = row[day] / total if total != 0 else 0
            
            # schnell
            df_ausschreibung.loc[idx, f"{day}_schnell"] = round(day_share * row['schnell_2035'] / 52)
            # nacht
            df_ausschreibung.loc[idx, f"{day}_nacht"] = round(day_share * row['nacht_2035'] / 52)
    
    return df_ausschreibung


def reorder_and_export(df_ausschreibung: pd.DataFrame, config: dict) -> None:
    """
    Sortiert das DataFrame in die gewünschte Spaltenreihenfolge und exportiert als CSV.
    """
    df_ausschreibung.columns = df_ausschreibung.columns.str.strip()
    
    # Beispielspalten – anpassen, falls nötig
    desired_columns = [
        'ID', 'Standortname', 'schnell_2035', 'nacht_2035',
        'Montag_schnell', 'Dienstag_schnell', 'Mittwoch_schnell', 'Donnerstag_schnell',
        'Freitag_schnell', 'Samstag_schnell', 'Sonntag_schnell',
        'Montag_nacht', 'Dienstag_nacht', 'Mittwoch_nacht', 'Donnerstag_nacht',
        'Freitag_nacht', 'Samstag_nacht', 'Sonntag_nacht'
    ]
    existing_columns = [c for c in desired_columns if c in df_ausschreibung.columns]
    df_final = df_ausschreibung[existing_columns].copy()
    
    base_path = os.path.dirname(os.path.abspath(__file__))
    output_file = os.path.join(base_path, config['OUTPUT_FILE'])
    
    # Export (index=False falls kein Index exportiert werden soll)
    df_final.to_csv(output_file, sep=';', decimal=',', index=False)
    print(f"Ladebedarfe exportiert.")


def main():
    """
    Hauptfunktion: führt alle Verarbeitungsschritte in der richtigen Reihenfolge aus.
    """
    # 1. Daten laden
    df_ausschreibung, df_befahrung, df_mauttabelle = load_data(CONFIG)
    
    # 2. schnell_2035 und nacht_2035 berechnen
    df_ausschreibung = calculate_schnell_nacht(df_ausschreibung, CONFIG)
    
    # 3. Mauttabelle mit Befahrungsdaten aktualisieren
    df_mauttabelle = update_mauttabelle_with_befahrung(df_mauttabelle, df_befahrung)
    
    # 4. Nächsten Autobahn-Abschnitt pro Standort finden und anfügen
    df_ausschreibung = assign_closest_rows(df_ausschreibung, df_mauttabelle, CONFIG)
    
    # 5. Wochentagsanteile normalisieren + schnell-/nacht-Werte je Tag berechnen
    df_ausschreibung = compute_weekday_shares(df_ausschreibung)
    
    # 6. Sortierung & Export
    reorder_and_export(df_ausschreibung, CONFIG)


if __name__ == '__main__':
    main()
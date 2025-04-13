# Modellierung der Flexibilitätspotenziale eines Lkw-Schnellladenetzes

Dieses Repository enthält die Implementierung der Modellierung zur Bestimmung der Ladenachfrage und des Flexibilitätspotenzials für das vom Bund ausgeschriebene Schnellladenetz für elektrifizierte Lkw an deutschen Autobahnen. Die Implementierung basiert auf der Masterarbeit "Potenziale eines flexibilisierten Schnellladenetzwerks für den elektrifizierten Schwerlastverkehr am deutschen Autobahnnetz" von David Sanders.

## Überblick

Die Modellierung dient zur Berechnung und Analyse der Ladeanforderungen an 352 definierten Standorten an bewirtschafteten und unbewirtschaften Rastanlagen am deutschen Autobahnnetz. Die wesentlichen Schritte sind:

1. **Ermittlung von Pausenstandorten** auf Basis von Transportfahrten und regulatorischen Anforderungen
2. **Zuordnung der Pausen** zu den Ladestandorten nach geometrischer Nähe und Auslastungsverteilung
3. **Berechnung des Ladebedarfs** basierend auf Elektrifizierungsprognosen und Verkehrswachstum
4. **Clustering der Standorte** in drei repräsentative Nachfragecluster für weitere Analysen

## Projektstruktur

Das Projekt besteht aus vier Hauptmodulen, die in sequentieller Reihenfolge ausgeführt werden:

- `pausenkoordinaten.py`: Generiert geografische Pausenpunkte entlang von Transportrouten
- `pausenzuordnung.py`: Ordnet Pausenpunkte den nächstgelegenen Ladestandorten zu
- `ladebedarf.py`: Berechnet den tatsächlichen Ladebedarf basierend auf Skalierungsfaktoren
- `clustern.py`: Kategorisiert Standorte nach ähnlichen Nachfrageprofilen
- `main.py`: Steuert die Ausführung der vier Module

## Anforderungen

### Systemanforderungen

- Python 3.8+
- Pandas
- NumPy
- GeoPandas
- Matplotlib
- Scikit-learn

### Datensätze

Die folgenden Eingabedateien müssen im Verzeichnis `Input/` vorhanden sein:

- `01_Trucktrafficflow.csv`, `03_network-nodes.csv`, `04_network-edges.csv`

Daten aus Speth et al. (2022) "Synthetic European road freight transport flow data." [LINK](https://doi.org/10.1016/j.dib.2021.107786)
- `ausschreibung_deutschlandnetz.xlsx`

Standorte des von der Bundesregierung geplanten Initialnetzes [LINK](https://www.autobahn.de/storage/user_upload/qbank/Standortliste_Lkw-Ladenetz.pdf)

- `Befahrungen_25_1Q.csv`

Pognostizierte Abschnittsbefahrungen des 1. Quartals 2025 erhoben durch das Bundesamt für Logistik und Mobilität (BALM) [LINK](https://www.balm.bund.de/SharedDocs/Downloads/DE/Verkehrsdatenmanagement/Befahrungen_2025_1Q.html?nn=541818)

- `Mauttabelle.xlsx`

 Mautabschnitte mit geographischen Koordinaten und Streckeninformationen des BALM [LINK](https://www.balm.bund.de/SharedDocs/Downloads/DE/Verkehrsdatenmanagement/Befahrungen_2025_1Q.html?nn=541818)
 
- `DE_NUTS5000.gpkg`
  
 GeoPackage mit Informationen zu geografischen Regionen in Deutschland (Eurostat NUTS-Regionen) [LINK](https://ec.europa.eu/eurostat/web/regions/database)

## Ausführung

Um die komplette Modellierung auszuführen:

```bash
python main.py
```

Alternativ können die Module auch einzeln ausgeführt werden:

```bash
python pausenkoordinaten.py
python pausenzuordnung.py
python ladebedarf.py
python clustern.py
```

## Detaillierte Funktionsweise

### 1. Pausenkoordinaten

Dieses Modul generiert Pausenpunkte für jeden Lkw basierend auf gesetzlichen Lenk- und Ruhezeiten:

- Einlesen von O-D-Transportfahrten und Netzwerkdaten
- Bestimmung von Pausenpunkten nach dem Trip-Chain-Ansatz unter Berücksichtigung der EU-Verordnung 561/2006
- Unterscheidung zwischen Ein- und Zwei-Fahrerfahrten
- Berücksichtigung von Kurz- und Langzeitpausen (Lenkzeitunterbrechungen vs. Ruhezeiten)
- Ausgabe der geografischen Koordinaten und Anzahl der Pausen

#### Konfigurationsmöglichkeiten:
- `DISTANCE_THRESHOLD`: Fahrtstrecke (in km), nach der eine Pause eingeplant wird (standardmäßig 360 km)
- `MAX_DISTANCE_SINGLEDRIVER`: Maximale Distanz für Ein-Fahrer-Betrieb (standardmäßig 4320 km)

### 2. Pausenzuordnung

Dieses Modul ordnet die erzeugten Pausenpunkte den nächstgelegenen Ladestandorten zu:

- Erzeugung von räumlichen Puffern (standardmäßig 40 km) um Standorte
- Filterung von Pausen innerhalb der deutschen Landesgrenzen
- Zuordnung der Pausen nach folgendem Algorithmus:
  - Wenn ein Pausenpunkt in nur einem Puffer liegt, direkte Zuordnung
  - Wenn ein Pausenpunkt in mehreren Puffern liegt, Zuordnung zum Standort mit der geringsten Standortbelastung
  - Wenn ein Pausenpunkt in keinem Puffer liegt, Zuordnung zum nächstgelegenen Standort
- Summe der Pausen je Standort als Output

#### Konfigurationsmöglichkeiten:
- `BUFFER_RADIUS`: Radius um jeden Ladestandort für die Zuordnung (standardmäßig 40000 m)
- `CRS_TARGET`: Projektion für die räumliche Analyse (standardmäßig 'EPSG:32632')

### 3. Ladebedarf

Dieses Modul berechnet den tatsächlichen Ladebedarf unter Berücksichtigung von Entwicklungsfaktoren:

- Skalierung der Pausenzahlen mit Elektrifizierungsrate (`R_BEV_2035`) und Verkehrswachstum (`R_TRAFFIC_2035`)
- Berücksichtigung des Anteils der Ladevorgänge am ausgeschriebenen Ladenetz (`R_SECTION`)
- Verknüpfung der Standorte mit Verkehrszählungsdaten pro Wochentag
- Berechnung der täglichen Anzahl an Schnelllade- und Nachtladepausen für jeden Wochentag und Standort

#### Konfigurationsmöglichkeiten:
- `R_BEV_2035`: Elektrifizierungsrate für 2035 (standardmäßig 0.74)
- `R_TRAFFIC_2035`: Wachstumsrate für den schweren Güterverkehr (standardmäßig 1.041)
- `R_SECTION`: Anteil der Ladevorgänge am ausgeschriebenen Netz (standardmäßig 0.6)

### 4. Clustering

Dieses Modul teilt die Standorte in Cluster ein:

- Standardisierung der Ladenachfragedaten
- K-Means Clustering mit drei Clustern
- Erzeugung von tagesaufgelösten Ladenachfragen je Cluster
- Berechnung der Clusterzentren als repräsentative Nachfrageprofile

#### Konfigurationsmöglichkeiten:
- `KMEANS`: Parameter für den K-Means-Algorithmus (z.B. Anzahl der Cluster, Initialisierungsmethode, etc.)

## Ausgabedateien

Die Modellierung erzeugt folgende Ausgabedateien im Verzeichnis `Output/`:

- `breaks.csv`: Pausenpunkte mit geographischen Koordinaten
- `ausschreibung_deutschlandnetz_breaks.xlsx`: Ausschreibungsstandorte mit zugeordneten Pausen
- `ausschreibung_deutschlandnetz_laden_mauttabelle.csv`: Standorte mit täglichem Ladebedarf je Wochentag
- `ausschreibung_deutschlandnetz_laden_mauttabelle_cl.xlsx`: Standorte mit Clusterzuordnung
- `ladevorgaenge_daily_cluster.csv`: Tägliche Ladevorgänge pro Cluster und Ladetyp
- `karte_breaks.png`: Visualisierung der Pausenverteilung

## Modellierungslogik

Die implementierte Modellierung folgt den in der Masterarbeit entwickelten methodischen Ansätzen:

1. **Trip-Chain-Ansatz**: Ermittlung von Pausenpunkten auf Basis von Transportfahrten und EU-Lenk- und Ruhezeitvorschriften
2. **Geometrische Zuordnung**: Räumliche Zuordnung der Pausenpunkte zu Ladestandorten mit Lastkappung für gleichmäßige Verteilung
3. **Skalierung nach Verkehrszählungen**: Wochentagsabhängige Verteilung der Ladevorgänge basierend auf Mauttabellendaten
4. **Szenario 2035**: Projektion des Schwerlastverkehrs auf 2035 mit einer Elektrifizierungsrate von 74% und Verkehrswachstum von 4,1%
5. **K-Means-Clustering**: Zusammenfassung der Standorte in drei repräsentative Cluster für weitere Analysen

## Lizenz

Dieses Projekt steht unter einer OpenSource-Lizenz. Die Modellierung basiert auf der Masterarbeit "Potenziale eines flexibilisierten Schnellladenetzwerks für den elektrifizierten Schwerlastverkehr am deutschen Autobahnnetz" von David Sanders am Institut für Energiesystemökonomik (FCN-ESE) des E.ON Energy Research Center der RWTH Aachen.

## Kontakt

Für Fragen zur Modellierung oder zur Masterarbeit wenden Sie sich an David Sanders.

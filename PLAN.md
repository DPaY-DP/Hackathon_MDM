# AgroTechNova MDM Hackathon — Allgemeiner Prüfplan

**Ziel:** Datenvertrauen über SAP, Salesforce und HubSpot messbar machen — Befunde finden, bewerten (Ursache vs. Folge), priorisieren und den Fachbereichen einen klaren Sanierungsweg geben.

**Datenpaket**

| Datei | System | Inhalt |
|-------|--------|--------|
| `AgroTechNova_Stammdaten_MARC_dirty.xlsx` | SAP | MARC Werksdaten (FERT/ERSA) + MARA |
| `AgroTechNova_Produktdaten_Salesforce_dirty.xlsx` | Salesforce | Product2, Pricebook2, PricebookEntry |
| `AgroTechNova_Produktdaten_HubSpot_dirty.xlsx` | HubSpot | Products, Price Books, Price Book Items |
| `AgroTechNova_Service_Salesforce_dirty.xlsx` | Salesforce | Account, Contact, Asset, WorkOrder |

**Führendes System (laut Briefing / Produktmanagement):** SAP Materialstamm. CRM- und Katalogdaten sollen davon abgeleitet / abgleichbar sein.

**Join-Schlüssel über Systeme**

| Ebene | Schlüssel |
|-------|-----------|
| Produkt | SAP `MATNR` ↔ SF `ATN_SAP_Materialnummer__c` ↔ HS `atn_sap_materialnummer` |
| SKU / Code | SF `StockKeepingUnit` / `ProductCode` ↔ HS `hs_sku` / Name |
| Preis | Listenpreis + Händlerpreis je Produkt (2 Pricebooks / Price Books) |
| Service | SF Product2Id → Asset → WorkOrder; Account ↔ Contact |

**Schweregrade (Abgabe / Pitch)**

| Grad | Bedeutung | typische Business-Wirkung |
|------|-----------|---------------------------|
| **hoch** | blockiert Prozess, Geld-/Compliance-Risiko, falsche verkaufbare Wahrheit | Zollstopp, Auslaufprodukt aktiv beworben, Preisdifferenz Angebot vs. Katalog, kaputte Referenzen |
| **mittel** | verzerrt Disposition/Reporting, Dubletten, inkonsistente Stammdaten | Doppelbestände, falsche Marktberichte, Leerfahrten-Risiko |
| **niedrig** | Format, Schreibweise, Cosmetik ohne direkte Prozessblockade | Trailing spaces, Case-Varianten, uneinheitliche Datumsformate |

---

## 1. Prüfung der Fehler auf den einzelnen Tabellen

Scope: **eine Tabelle / ein Blatt isoliert** — Vollständigkeit, Format, Wertebereiche, Eindeutigkeit. Keine Joins.

### 1.1 Generische Checks (alle Blätter)

- Pflichtfelder leer / nur Whitespace
- Überflüssige Leerzeichen (Leading/Trailing/Doppelspaces)
- Schreibvarianten (Case, Bindestrich, Umlaute `ä` vs `ae` / Encoding)
- Doppelte Schlüssel (Id, MATNR, SKU, SerialNumber, WorkOrderNumber, …)
- Ungültige / zukünftige / inkonsistente Datumsformate (`YYYY-MM-DD` vs `DD.MM.YYYY` vs `DD/MM/YYYY`)
- Typfehler (Zahl als Text mit Währung, Bool als `wahr`/`1`/`True`)
- Erlaubte Werte (Picklists / SAP-Customizing laut Feldlegende)

### 1.2 SAP — `Produkte (FERT)` / `Ersatzteile (ERSA)` (MARC)

| Check | Felder | Hinweis |
|-------|--------|---------|
| Pflichtschlüssel | MATNR, WERKS, MANDT | Composite Key MATNR+WERKS |
| Materialart zum Blatt | MTART | FERT-Blatt nur `FERT`; ERSA-Blatt nur `ERSA` |
| Werke | WERKS | Erlaubt: 1000, 1100 (Fertigung); 2000, 2100, 2200 (Ersatzteil). Unbekannte Werke (z. B. 1500, 2300, 9999) = Fehler |
| Status / Löschung | MMSTA, LVORM, MMSTD | MMSTA ∈ {01, 02}; LVORM leer oder `X` |
| Disposition | DISMM, DISLS, BESKZ, MAABC | Werte laut Legende (PD/VB/VM/ND; EX/FX/HB/WB/MB; E/F/X; A/B/C) |
| Mengenlogik | BSTMI ≤ BSTMA; MINBE/EISBE/MABST ≥ 0 | Negative Losgrößen = hoch |
| Herkunft / Zoll | STAWN, HERKL | STAWN numerisch plausibel (Länge/Format); HERKL ISO-Land |
| Lagerorte | LGPRO, LGFSB | Code-Format, kein Klartext-Mix ohne Regel |
| Kurztext | MAKTX | nicht leer; Encoding |

### 1.3 SAP — `MARA`

| Check | Felder |
|-------|--------|
| Eindeutigkeit MATNR | 1:1 zu Material |
| MTART / MATKL / SPART / EXTWG | Konsistenz zu Produktfamilie |
| MEINS / BSTME | Einheitencode |
| Gewichte/Volumen | NTGEW ≤ BRGEW; GEWEI/VOLEH |
| EAN | EAN11 Prüfziffer / Länge; NUMTP |
| Status | MSTAE/MSTDE; LVORM mandantenweit |
| Revision | KZREV ∈ {leer, X} |

### 1.4 Salesforce Produkte — `Product2` / `Pricebook2` / `PricebookEntry`

| Check | Felder |
|-------|--------|
| Id-Format | 15/18-stellige Salesforce-Ids |
| Pflicht | Name, ProductCode/SKU, IsActive |
| Bool-Normalisierung | IsActive/IsArchived ∈ True/False (nicht `1`/`wahr`) |
| Mengeneinheit | QuantityUnitOfMeasure einheitlich (`Stueck` vs `pcs`) |
| Custom SAP-Refs | ATN_SAP_Materialnummer__c, Warengruppe, Werk |
| Pricebook | genau 1 IsStandard; Währung EUR/EURO vereinheitlichen |
| PricebookEntry | UnitPrice numerisch, > 0 für aktive Verkaufsprodukte; Product2Id/Pricebook2Id referenzierbar **innerhalb** Datei erst in Ebene 2 |

### 1.5 HubSpot — `Products` / `Price Books` / `Price Book Items`

| Check | Felder |
|-------|--------|
| Ids | `hs_object_id` numerisch bzw. Prefix-Fehler (`HS-…`) |
| SKU | `hs_sku` Muster `ATN-######` |
| Status / Typ | hs_status ACTIVE/INACTIVE; hs_product_type; hs_pricing_model FLAT |
| Preis | numerisch (kein `417.350,00 EUR`); price ≥ 0; COGS |
| Custom SAP | atn_sap_materialnummer, Warengruppe, Herstellwerk |
| Tax / Owner | hs_tax_category; hubspot_owner_id Format |
| Price Book | Währung EURO vs EUR; archived vs ACTIVE Konflikt |

### 1.6 Salesforce Service — `Account` / `Contact` / `Asset` / `WorkOrder`

| Check | Felder |
|-------|--------|
| Account | Name Pflicht; Type; BillingCountry; Phone/Website Format; NumberOfEmployees numerisch; Marktregion |
| Contact | Name, Email-Format, Salutation, AccountId vorhanden (Existenz → Ebene 2) |
| Asset | SerialNumber eindeutig + Format; Status; Datumsreihenfolge Purchase ≤ Install ≤ UsageEnd; Price/Quantity |
| WorkOrder | Status/Priority Domäne; Start ≤ End; Kosten; Wartungsart |

**Output Ebene 1:** Befundliste je Zeile/Feld mit Schweregrad; Score „Tabelle X: % fehlerfreie Datensätze“.

---

## 2. Prüfung innerhalb des Systems

Scope: **Joins und Regeln innerhalb eines Systems** (eine Datei bzw. zusammengehörige Objekte). Ursache oft hier, Folge in Ebene 3.

### 2.1 SAP (MARC ↔ MARA)

1. **Abdeckung:** Jede MATNR in FERT/ERSA existiert in MARA und umgekehrt (keine Orphans).
2. **Feldgleichheit MARA↔MARC-Referenz:** MAKTX, MTART, MATKL, MEINS müssen übereinstimmen, wenn in beiden geführt.
3. **MTART vs. Blatt:** FERT-Material nicht im ERSA-Blatt und umgekehrt; MARA.MTART = MARC.MTART.
4. **SPART ↔ MATKL-Familie:** z. B. Erntetechnik/Robotik → SPART 10; Sensorik → 20; Ersatzteile → 90.
5. **Werksstrategie:** FERT primär Werk 1000/1100; ERSA 2000/2100/2200 — Abweichungen flaggen.
6. **Auslauf-Konsistenz:** LVORM=`X` und/oder MMSTA=`02` ↔ sinnvolle MARA-Status (MSTAE); keine „aktiven“ Dispositionsparameter ohne Regel.
7. **Dubletten fachlich:** gleicher MAKTX / ähnliche Kurztexte bei unterschiedlicher MATNR (Disposition: „Teile doppelt“).
8. **Physische Plausibilität:** BRGEW/NTGEW/VOLUM je Materialart (FERT vs Sensor vs Ersatzteil) Ausreißer.

### 2.2 Salesforce Produkte

1. **Referenzen:** Jeder PricebookEntry.Product2Id ∈ Product2; Pricebook2Id ∈ Pricebook2.
2. **Vollständigkeit Preis:** Jedes aktive Product2 hat Eintrag im Standard- und im Händler-Pricebook (laut Übersicht: 2 je Produkt).
3. **Preislogik:** Händlerpreis ≤ Listenpreis; UnitPrice > 0 wenn IsActive.
4. **Status-Kohärenz:** Product2.IsActive=False / IsArchived=True → zugehörige Entries idealerweise inaktiv.
5. **SKU/Code-Eindeutigkeit:** ProductCode und StockKeepingUnit unique; Mapping Code↔SKU stabil.
6. **Family vs. SAP-Warengruppe:** Family (`Erntetechnik`, `Feldrobotik`, …) passt zu `ATN_SAP_Warengruppe__c`.
7. **Werk:** `ATN_Herstellwerk__c` ∈ {1000, 1100} für FERT-ähnliche Produkte.

### 2.3 HubSpot

1. **Referenzen:** Price Book Items → gültige `price_book_id` und `hs_associated_product_id`.
2. **Zwei Preisbücher je Produkt:** Standard-Listenpreis + Händlerpreisliste.
3. **Preis-Sync intern:** `Products.price` ≈ Item-Preis im Standard-Preisbuch.
4. **Status:** Product INACTIVE → Items/Books nicht als aktiv vermarkten; archived Price Book nicht ACTIVE.
5. **SKU-Konsistenz:** `Products.hs_sku` = Item `hs_sku` für dasselbe Produkt.
6. **SAP-Ref:** `atn_sap_materialnummer` unique unter aktiven Produkten.

### 2.4 Salesforce Service

1. **Contact.AccountId** ∈ Account.Id; REF_AccountName plausibel zum Account.
2. **Asset.AccountId / ContactId / Product2Id** referenzieren existierende Records (Product2Id gegen Produktdatei → oft erst Ebene 3, wenn getrennte Exports).
3. **SerialNumber** global unique; Name enthält Serial konsistent.
4. **Datums-/Garantielogik:** InstallDate ≥ PurchaseDate; UsageEndDate ≥ InstallDate.
5. **WorkOrder:** Account/Contact/Asset konsistent zueinander (Contact gehört zum Account; Asset gehört zum Account).
6. **Business-Regeln Service:** Garantiefall → Kosten ≈ 0; Obsolete Asset + neue WorkOrders = mittel/hoch.
7. **Account-Dubletten:** gleicher Name + Land/Stadt oder gleiche Website/Phone → Verdacht (Customer Success).
8. **Geo-Konsistenz:** BillingCountry ↔ ATN_Marktregion__c; Contact.MailingCountry ↔ Account-Land.

**Output Ebene 2:** Befunde mit Objektbeziehung; Markierung „Ursache (Systemregel)“ vs. „lokale Inkonsistenz“.

---

## 3. Prüfung systemübergreifend

Scope: **Goldener Pfad SAP → Salesforce → HubSpot** und Service-Anbindung. Hier entstehen die Briefing-Schmerzpunkte (Preis, Auslauf, Katalog, Service).

### 3.1 Produktabdeckung (Golden Record)

| Prüfung | Erwartung | Schwere |
|---------|-----------|---------|
| SAP FERT (aktiv) in SF Product2 | je MATNR ein Product | hoch |
| SAP FERT (aktiv) in HS Products | je MATNR ein Product | hoch |
| SF/HS-Produkt ohne SAP-MATNR | Orphan / Sync-Bruch | hoch |
| Anzahl | Übersicht sagt ~100 FERT; SF-Übersicht 98 — Delta erklären | hoch |

### 3.2 Attribute Match (SAP führend)

Vergleich je MATNR:

| Attribut | SAP | Salesforce | HubSpot |
|----------|-----|------------|---------|
| Kurztext/Name | MAKTX | Name | name |
| Warengruppe | MATKL | ATN_SAP_Warengruppe__c | atn_sap_warengruppe |
| Werk | WERKS (FERT) | ATN_Herstellwerk__c | atn_herstellwerk |
| Aktiv/Auslauf | LVORM/MMSTA/MSTAE | IsActive / IsArchived | hs_status |
| SKU | (abgeleitet / Zeichnung) | StockKeepingUnit | hs_sku |

Regel: Abweichung vom SAP-Wert = **Folgefehler** im CRM/Katalog, Ursache in Sync/Pflege.

### 3.3 Preise (Lena Vos / Controlling / Marketing)

- Listenpreis SF Standard Price Book ≡ HS Standard-Preisbuch ≡ (soweit vorhanden) HS `Products.price`
- Händlerpreis SF ≡ HS Händlerpreisliste
- Toleranz: exakt oder definierte Rundung (0,00)
- COGS vs. Verkaufspreis: Preis < COGS → Controlling-Flag (Felix Brenner)
- Währung EUR überall normalisiert

### 3.4 Lebenszyklus / Auslauf (Anouk de Wit / Jonas Brandt)

- SAP Auslauf (LVORM=X oder MMSTA/MSTAE Auslauf) → SF nicht aktiv verkaufbar, HS nicht ACTIVE / nicht beworben
- SAP aktiv → in beiden CRMs auffindbar und konsistent aktiv
- Delta „beworben aber nicht lieferbar“ / „lieferbar aber nicht im Katalog“ = **hoch**

### 3.5 Service ↔ Produkt (Carla Meier)

- Asset.Product2Id / REF_ProductName ∈ Salesforce Product2
- Serial-/Produktbezug konsistent zu verkauftem Produkt
- WorkOrder auf unstimmigem Asset/Account = Folge der Stammdaten-/Zuordnungsfehler

### 3.6 Markt-Score (Pitch-Anforderung)

Pro Land/Region (aus Service Accounts + optional Werk/Herkunft):

\[
Score_{Markt} = 100 - gewichtete\ Befunde\ (hoch \times 5,\ mittel \times 2,\ niedrig \times 0{,}5)
\]

Anzeige: Heatmap / Ranking „wo tut es am meisten weh“.

**Output Ebene 3:** Befundliste mit `Ursache-System` (meist SAP oder Sync) und `Folge-Systeme`; Priorisierte Top-10 für Pitch.

---

## 4. Klassifikationssystem für SAP-Befunde

Jeder SAP-Befund erhält eine strukturierte Klassifikation (für Tool, CSV-Abgabe und Governance).

### 4.1 Dimensionen

| Dimension | Werte | Zweck |
|-----------|-------|-------|
| **DQ-Dimension** | Vollständigkeit, Eindeutigkeit, Gültigkeit, Konsistenz, Aktualität, Genauigkeit | Fachliche DQ-Sprache (Mike / Lukas) |
| **Ebene** | E1 Tabelle · E2 SAP-intern · E3 systemübergreifend | Prüfplan-Zuordnung |
| **Objekt** | MARA · MARC-FERT · MARC-ERSA · MARC↔MARA | wo korrigieren |
| **Fehlerklasse** | KEY · REF · DOMAIN · FORMAT · LOGIC · DUP · SYNC · MASTER | siehe unten |
| **Schweregrad** | hoch / mittel / niedrig | Abgabe + Priorisierung |
| **Ursache/Folge** | Ursache · Folge · unklar | Head of Governance |
| **Business-Impact** | Vertrieb · Marketing · Disposition · Zoll/Logistik · Service · Controlling · Compliance | Stimmen aus dem Briefing |
| **Owner-Vorschlag** | Stammdaten/MDM · Disposition · Logistik · Produktmanagement | „wer zuerst“ |

### 4.2 Fehlerklassen (SAP)

| Code | Klasse | Beschreibung |
|------|--------|--------------|
| **KEY** | Schlüssel-/Identitätsfehler | MATNR fehlt/doppelt; WERKS ungültig; Composite Key Bruch |
| **REF** | Referenzbruch | MARC ohne MARA; Werk nicht im Werkestamm; ungültige Disponent-/Lager-Codes |
| **DOMAIN** | Wertebereich / Customizing | MMSTA, DISMM, BESKZ, MAABC, MTART außerhalb erlaubter Menge |
| **FORMAT** | Darstellung | Encoding in MAKTX; STAWN mit Punkten; HERKL Klartext statt ISO; Einheiten `EA`/`PC` statt `ST` |
| **LOGIC** | Fachliche Plausibilität | BSTMI > BSTMA; Negativbestand; NTGEW > BRGEW; Auslauf aber Disposition „voll aktiv“ ohne Regel |
| **DUP** | fachliche Dublette | Zwei MATNR, inhaltlich gleiches Teil (Kurztext/EAN) |
| **SYNC** | Abgleich zu CRM | (E3) SAP-Wert weicht von SF/HS ab — SAP bleibt Quelle, CRM ist Folge |
| **MASTER** | führende Stammdaten-Regel | MTART falsch für Produkttyp; SPART/MATKL-Bruch; FERT als ERSA gekennzeichnet |

### 4.3 Bewertungsmatrix (Richtschnur)

| Klasse | Default-Schwere | Eskalation auf „hoch“ wenn… |
|--------|-----------------|------------------------------|
| KEY | hoch | immer |
| REF | hoch | Material nicht mehr findbar / Orphan |
| DOMAIN | mittel | Status/Beschaffung falsch → Disposition/Zoll betroffen |
| FORMAT | niedrig | Zollfeld STAWN/HERKL oder EAN betroffen → hoch |
| LOGIC | mittel | negative Mengen, Gewichtsbruch → hoch |
| DUP | mittel | Kapitalbindung / Fehlteil in Ernte → hoch |
| SYNC | hoch | Preis, Aktiv-Status, fehlendes Produkt im Katalog |
| MASTER | hoch | falsche Materialart auf Fertigerzeugnis |

---

## 5. Potenzielle Fehlerliste SAP (mit Klassifizierung)

Abgeleitet aus Briefing-Stimmen, Feldlegende und sichtbaren Dirty-Mustern in den Rohdaten. Dient als Checkkatalog für Implementierung und als Start-Befundhypothesen.

### 5.1 MARC — Produkte (FERT)

| ID | Befund (potenziell) | Felder | Klasse | DQ | Ebene | Schwere | Impact | Owner |
|----|---------------------|--------|--------|-----|-------|---------|--------|-------|
| SAP-F01 | Materialart `ERSA` im FERT-Blatt | MTART | MASTER | Gültigkeit | E1 | hoch | Disposition, Produkt | MDM / Produkt |
| SAP-F02 | Encoding-/Umlautfehler im Kurztext | MAKTX | FORMAT | Genauigkeit | E1 | niedrig–mittel | Marketing, Vertrieb | MDM |
| SAP-F03 | Bindestrich-/Schreibvarianten im Namen | MAKTX | FORMAT | Konsistenz | E1 | niedrig | Marketing | MDM |
| SAP-F04 | STAWN fehlt | STAWN | KEY/Vollst. | Vollständigkeit | E1 | hoch | Zoll/Logistik | Logistik |
| SAP-F05 | STAWN Format falsch (zu lang / mit Punkten) | STAWN | FORMAT | Gültigkeit | E1 | hoch | Zoll | Logistik |
| SAP-F06 | HERKL nicht ISO (`Deutschland`, `nl`) | HERKL | DOMAIN | Gültigkeit | E1 | hoch | Zoll | Logistik |
| SAP-F07 | LGPRO Klartext/Code-Mix (`AUSL`/`FERT`/`0001`) | LGPRO | DOMAIN | Konsistenz | E1 | mittel | Disposition | Disposition |
| SAP-F08 | MMSTA nicht 01/02 bzw. führende Null fehlt | MMSTA | DOMAIN | Gültigkeit | E1 | mittel | Disposition | MDM |
| SAP-F09 | MAABC fehlt | MAABC | KEY | Vollständigkeit | E1 | mittel | Disposition | Disposition |
| SAP-F10 | DISLS außerhalb EX/FX/HB/WB/MB | DISLS | DOMAIN | Gültigkeit | E1 | mittel | Disposition | Disposition |
| SAP-F11 | Negative / unsinnige Losgröße | BSTMI | LOGIC | Genauigkeit | E1 | hoch | Disposition | Disposition |
| SAP-F12 | Unerlaubtes Werk für FERT (z. B. 2100) | WERKS | REF | Gültigkeit | E1 | mittel–hoch | Disposition | MDM |
| SAP-F13 | LVORM=X aber MMSTA noch „aktiv“ ohne Regel | LVORM, MMSTA | LOGIC | Konsistenz | E2 | hoch | Vertrieb, Marketing | Produkt |
| SAP-F14 | Eigenfertigungszeit / Planlieferzeit Ausreißer | DZEIT, PLIFZ | LOGIC | Genauigkeit | E1 | niedrig–mittel | Disposition | Disposition |

### 5.2 MARC — Ersatzteile (ERSA)

| ID | Befund (potenziell) | Felder | Klasse | DQ | Ebene | Schwere | Impact | Owner |
|----|---------------------|--------|--------|-----|-------|---------|--------|-------|
| SAP-E01 | MAKTX leer | MAKTX | KEY | Vollständigkeit | E1 | hoch | Disposition, Service | MDM |
| SAP-E02 | MTART Tippfehler (`FRET` statt `ERSA`) | MTART | MASTER | Gültigkeit | E1 | hoch | Disposition | MDM |
| SAP-E03 | Unbekannte Werke (1500, 2300, 9999) | WERKS | REF | Gültigkeit | E1 | hoch | Disposition, Logistik | MDM |
| SAP-E04 | MEINS uneinheitlich (`ST`/`EA`/`PC`/`M`) | MEINS | DOMAIN | Konsistenz | E1 | mittel–hoch | Disposition, Controlling | MDM |
| SAP-E05 | BESKZ außerhalb E/F/X (z. B. `Z`, `e`) | BESKZ | DOMAIN | Gültigkeit | E1 | mittel | Disposition | Disposition |
| SAP-E06 | MAABC ungültig (`D`, `a`) | MAABC | DOMAIN | Gültigkeit | E1 | mittel | Disposition | Disposition |
| SAP-E07 | MMSTA ungültig (`1`, `XX`) | MMSTA | DOMAIN | Gültigkeit | E1 | mittel | Disposition | MDM |
| SAP-E08 | DISMM=`PD` auf klassischem Bestellpunkt-Teil | DISMM | LOGIC | Konsistenz | E1 | mittel | Disposition | Disposition |
| SAP-E09 | Fachliche Dublette (gleicher Kurztext/EAN) | MATNR, MAKTX, EAN | DUP | Eindeutigkeit | E2 | hoch | Disposition (Kapital) | Disposition |
| SAP-E10 | Auslauf (LVORM/MMSTA) vs. hoher Meldebestand | LVORM, MINBE | LOGIC | Konsistenz | E2 | mittel | Disposition | Disposition |
| SAP-E11 | HERKL Schreibvarianten (`nl`/`Netherlands`) | HERKL | FORMAT | Konsistenz | E1 | hoch | Zoll | Logistik |

### 5.3 MARA

| ID | Befund (potenziell) | Felder | Klasse | DQ | Ebene | Schwere | Impact | Owner |
|----|---------------------|--------|--------|-----|-------|---------|--------|-------|
| SAP-M01 | MATNR in MARC ohne MARA (oder umgekehrt) | MATNR | REF | Vollständigkeit | E2 | hoch | alle | MDM |
| SAP-M02 | MAKTX/MTART/MATKL weicht von MARC ab | MAKTX, MTART, MATKL | SYNC/LOGIC | Konsistenz | E2 | hoch | Sync CRM | MDM |
| SAP-M03 | SPART passt nicht zu MATKL/EXTWG | SPART, MATKL | MASTER | Konsistenz | E2 | mittel | Controlling, Produkt | Produkt |
| SAP-M04 | NTGEW > BRGEW | NTGEW, BRGEW | LOGIC | Genauigkeit | E1 | hoch | Logistik | Logistik |
| SAP-M05 | EAN11 ungültig / Prüfziffer | EAN11 | FORMAT | Gültigkeit | E1 | mittel–hoch | Logistik, Vertrieb | MDM |
| SAP-M06 | MSTAE Auslauf inkonsistent zu MARC LVORM/MMSTA | MSTAE, LVORM | LOGIC | Konsistenz | E2 | hoch | Vertrieb, Marketing | Produkt |
| SAP-M07 | ERNAM/`MDM_LOAD` ohne fachliche Nachpflege-Flags | ERNAM | FORMAT | Aktualität | E1 | niedrig | Governance | MDM |
| SAP-M08 | KZREV=X ohne Zeichnungsnummer | KZREV, ZEINR | LOGIC | Vollständigkeit | E1 | mittel | Compliance, Fertigung | Produkt |

### 5.4 Systemübergreifend (SAP als Ursache)

| ID | Befund (potenziell) | Vergleich | Klasse | Ebene | Schwere | Impact |
|----|---------------------|-----------|--------|-------|---------|--------|
| SAP-X01 | FERT in SAP, fehlt in SF und/oder HS | MATNR | SYNC | E3 | hoch | Vertrieb, Marketing |
| SAP-X02 | Name/MAKTX ≠ SF Name ≠ HS name | MAKTX | SYNC | E3 | mittel | Marketing, Vertrieb |
| SAP-X03 | MATKL ≠ SF/HS Warengruppe | MATKL | SYNC | E3 | mittel | Reporting |
| SAP-X04 | Werk ≠ SF/HS Herstellwerk | WERKS | SYNC | E3 | mittel | Service, Logistik |
| SAP-X05 | SAP Auslauf, CRM noch ACTIVE | LVORM/MMSTA vs IsActive/hs_status | SYNC | E3 | hoch | Vertrieb, Marketing |
| SAP-X06 | SAP aktiv, Katalog INACTIVE / fehlend | Status | SYNC | E3 | hoch | Marketing |
| SAP-X07 | Preis SF ≠ HS (SAP löst nicht Preis, aber Master für Existenz) | Pricebooks | SYNC | E3 | hoch | Vertrieb (Lena) |
| SAP-X08 | SF ProductCount ≠ 100 SAP FERT | Abdeckung | SYNC | E3 | hoch | alle |

---

## 6. Empfohlene Umsetzungsreihenfolge (5h Hackathon)

1. **Parser + Datenmodell** — alle Sheets mit Header-Erkennung laden; Keys normalisieren (MATNR als String, Trim).
2. **E1 Rules Engine** — Domänen aus Feldlegende hardcoded/config; Befund-CSV schreiben.
3. **E2 Joins** — MARA↔MARC; SF/HS interne Referenzen; Service-Graph.
4. **E3 Matching** — MATNR-Goldpfad; Preis- und Status-Vergleich.
5. **Klassifikation + Score** — Schema aus Kap. 4 an jeden Befund; Markt-Score.
6. **UI** — Befundliste filterbar (System, Schwere, Impact), Score-Dashboard, Korrekturhinweis + Owner.
7. **Pitch-Zahlen** — Top-Befunde, €-Story an Briefing-Stimmen koppeln (Preis, Zoll, Disposition, Service).

---

## 7. Abgabe-Mapping

Befundzeile (laut Briefing) ergänzt um interne Klassifikation:

| Abgabe-Spalte | Inhalt |
|---------------|--------|
| Datei | Excel-Dateiname |
| Blatt | Sheet |
| Zeile | Excel-Zeile |
| Feld | Spaltenname |
| Befund | Kurztext + Fehlerklassen-Code (z. B. `SAP-E03`) |
| Schweregrad | hoch / mittel / niedrig |

Zusätzlich empfohlen (Tool-intern, nicht zwingend Abgabe): Ebene, Ursache/Folge, Business-Impact, Owner, Korrekturvorschlag.

---

*Stand: basierend auf Hackathon-Briefing und Analyse der vier Dirty-Excel-Dateien (AgroTechNova).*

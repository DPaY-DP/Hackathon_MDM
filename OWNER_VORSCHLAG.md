# Owner-Modell — Vorschlag (systemübergreifend)

**Ziel:** Ein fester Owner-Katalog für alle Systeme (SAP, Salesforce, HubSpot).  
Ein Befund hat **genau einen Owner** = wer die Korrektur fachlich verantwortet / zuerst anpackt.  
**Impact** bleibt getrennt (= wer den Schmerz spürt) und darf mehrere Bereiche listen.

---

## 1. Vorgeschlagener Katalog (8 Owner)

| Code | Owner (Anzeigename) | Fachbereich / Produktionsnähe | Typische Daten | Briefing-Bezug |
|------|---------------------|-------------------------------|----------------|----------------|
| `MDM` | Stammdaten / MDM | Querschnitt Material- & Produktschlüssel, Sync-Regeln | MATNR, SKU, Ids, Domänen-Customizing, Abdeckung SAP↔CRM | Norbert (Head of MDM) |
| `PRODUKT` | Produktmanagement | Sortiment, Lebenszyklus, Bezeichnung, Klassifikation | Name/MAKTX, Auslauf/Aktiv, SPART/MATKL/Family, Zeichnung | Anouk de Wit |
| `DISPO` | Disposition / Supply | Bestände, Nachschub, Werks-/MRP-Parameter | DISMM, DISLS, BESTÄNDE, Losgrößen, Dubletten ERSA | Marta Kowalczyk (Poznań) |
| `LOGISTIK` | Logistik & Zoll | physische & zollrelevante Attribute | STAWN, HERKL, Gewicht/Volumen, EAN, Versanddaten | Henk Jansen (Rotterdam) |
| `VERTRIEB` | Vertrieb | verkaufbare Wahrheit: Preise, Preisbücher, Angebotsdaten | UnitPrice, Pricebooks, Händlerkonditionen, aktive Verkaufsstatus im CRM | Lena Vos (EMEA) |
| `MARKETING` | Marketing / Katalog | HubSpot-Katalog, Content, Kampagnen-Sichtbarkeit | description, URL, Katalog-Status, Price Books Marketing | Jonas Brandt |
| `SERVICE` | Field Service | installierte Basis, Einsätze, Kunden-Zuordnung im Service | Asset, WorkOrder, SerialNumber, Service-Account-Links | Carla Meier |
| `CUSTOMER` | Customer Success / Kundenstamm | Kunden- & Kontaktqualität, Marktzuordnung | Account, Contact, Dubletten, Marktregion, Geo | Ingrid Larsen |

**Optional / nur wenn nötig** (sonst Impact belassen, nicht Owner):

| Code | Wann |
|------|------|
| `CONTROLLING` | Nur wenn Korrektur primär Zahlen-/Margenpflege ist (sonst oft `VERTRIEB` oder `PRODUKT`) |
| `IT_SYNC` | Nur technische Integrationsfehler ohne Fachinhalt (sonst `MDM`) |

**Empfehlung Hackathon:** die **8 Kern-Owner** reichen. `CONTROLLING` / `IT_SYNC` weglassen, um die Liste klein und pitchbar zu halten.

---

## 2. Regeln (damit es konsistent bleibt)

1. **Genau ein Owner pro Befund** — keine `MDM / Produkt`-Kombis mehr.
2. **Owner ≠ Impact** — Impact darf `"Vertrieb, Marketing"` sein; Owner ist die Korrekturstelle.
3. **Ursache entscheidet, nicht Symptom**  
   - Falsche MATNR in HubSpot → oft `MDM` (Sync/Schlüssel), auch wenn Schmerz bei Marketing liegt.  
   - Falscher Listenpreis SF≠HS → `VERTRIEB` (Preishoheit), nicht Marketing.  
   - SAP Auslauf nicht in CRM → `PRODUKT` (Lebenszyklus-Entscheidung), MDM nur wenn Sync-Technik kaputt.
4. **Code ist maschinenlesbar** (`MDM`, `DISPO`, …) — Anzeigename nur für UI/Pitch.
5. **Gleiche Codes in SAP-, HubSpot- und Salesforce-Listen.**

### Entscheidungsbaum (kurz)

```
Schlüssel / Domäne / Sync-Bruch?          → MDM
Sortiment / Name / Auslauf / Klassifikation? → PRODUKT
MRP / Bestand / Losgröße / ERSA-Dublette? → DISPO
Zoll / Herkunft / Gewicht / EAN / Versand? → LOGISTIK
Preis / Preisbuch / Verkaufspreis-Status? → VERTRIEB
Katalog-Content / URL / Marketing-Status? → MARKETING
Asset / WorkOrder / Serial / Service-Link? → SERVICE
Account / Contact / Kunden-Dublette / Markt? → CUSTOMER
```

---

## 3. Mapping: bisherige Werte → neuer Code

| Bisher (uneinheitlich) | Neu |
|------------------------|-----|
| MDM, MDM / Produkt, MDM / Marketing Ops | `MDM` oder laut Baum `PRODUKT`/`MARKETING` |
| Produkt, Produktmanagement | `PRODUKT` |
| Disposition | `DISPO` |
| Logistik | `LOGISTIK` |
| Vertrieb, Vertrieb / MDM | `VERTRIEB` (Sync-Technik → `MDM`) |
| Marketing Ops, Marketing | `MARKETING` |
| Controlling | Impact belassen; Owner meist `VERTRIEB` oder `PRODUKT` |
| Governance | `MDM` |
| (Service später) | `SERVICE` |
| (Kundenstamm später) | `CUSTOMER` |

---

## 4. Beispiel-Zuordnung (Stichprobe)

| ID | Befund kurz | Alter Owner | Vorschlag neu | Begründung |
|----|-------------|-------------|---------------|------------|
| SAP-F04 | STAWN fehlt | Logistik | `LOGISTIK` | Zollattribut |
| SAP-F11 | Negative Losgröße | Disposition | `DISPO` | MRP-Parameter |
| SAP-F13 | Auslauf vs. MMSTA | Produkt | `PRODUKT` | Lebenszyklus |
| SAP-E09 | ERSA-Dublette | Disposition | `DISPO` | Kapitalbindung Ersatzteil |
| SAP-M01 | MARC↔MARA Orphan | MDM | `MDM` | Stammdaten-Integrität |
| SAP-X05 | SAP Auslauf, CRM aktiv | Produkt | `PRODUKT` | fachliche Freigabe/Auslauf |
| SAP-X07 | Preis SF ≠ HS | Vertrieb / MDM | `VERTRIEB` | Preishoheit |
| HS-P07 | Lorem-Beschreibung | Marketing Ops | `MARKETING` | Content |
| HS-P14 | Preis als Text | Marketing Ops | `VERTRIEB` | Preisdatenqualität |
| HS-P24 | MATNR fehlt in HS | MDM | `MDM` | Schlüssel/Sync |
| HS-B02 | archived + ACTIVE | Marketing Ops | `MARKETING` | Katalog-Preisbuch |
| HS-X06 | Preis HS ≠ SF | Marketing Ops | `VERTRIEB` | Preiskonsistenz |

---

## 5. Offene Punkte zur Entscheidung

1. **Preise in HubSpot:** Owner immer `VERTRIEB` — oder Katalog-Pflege `MARKETING`, Listenpreis-Hoheit `VERTRIEB`?  
   → Vorschlag: **Preise = `VERTRIEB`**, Content/URL/Beschreibung = `MARKETING`.
2. **Status ACTIVE/INACTIVE im CRM:** bei Abweichung zu SAP-Auslauf → `PRODUKT`; rein technisches Picklist-Format → System-Fachowner (`MARKETING` bzw. später SF-Vertrieb-Admin als `VERTRIEB`).
3. **Controlling als Owner?** Nur wenn ihr Felix als Korrekturverantwortlichen braucht — sonst Impact.
4. **Soll der Code in der CSV `Owner` heißen oder `OwnerCode` + `OwnerName`?**  
   → Vorschlag Hackathon: eine Spalte `Owner` mit Code (`MDM`, `DISPO`, …).

---

Wenn ihr den Katalog so freigebt, mappe ich anschließend SAP- und HubSpot-Listen (MD + CSV) auf diese Codes um.

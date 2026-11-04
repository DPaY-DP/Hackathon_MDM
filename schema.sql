-- AgroTechNova Datencheck — SQLite Schema v3
-- Standalone-DB: data/datencheck.db
-- Quellen: Power-Query-Skripte + Power-BI-Beziehungen + Fehler-Zielmodell
-- IDs bewusst TEXT (Dirty Data, Prefixe, führende Nullen)

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- Meta & Fehler
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS Fehlerdefinition (
    Fehlercode       TEXT PRIMARY KEY,
    Schwere          TEXT NOT NULL,
    Owner            TEXT NOT NULL,
    Kurzbeschreibung TEXT NOT NULL,
    System           TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fehlerdefinition_system
    ON Fehlerdefinition (System);
CREATE INDEX IF NOT EXISTS idx_fehlerdefinition_owner
    ON Fehlerdefinition (Owner);
CREATE INDEX IF NOT EXISTS idx_fehlerdefinition_schwere
    ON Fehlerdefinition (Schwere);

CREATE TABLE IF NOT EXISTS Fehlerliste (
    Fehlerid         INTEGER PRIMARY KEY AUTOINCREMENT,
    Fehlercode       TEXT NOT NULL,
    Ursprungstabelle TEXT NOT NULL,
    Ursprungs_ID     TEXT NOT NULL,
    FOREIGN KEY (Fehlercode) REFERENCES Fehlerdefinition (Fehlercode)
);

CREATE INDEX IF NOT EXISTS idx_fehlerliste_fehlercode
    ON Fehlerliste (Fehlercode);
CREATE INDEX IF NOT EXISTS idx_fehlerliste_ursprung
    ON Fehlerliste (Ursprungstabelle);
CREATE INDEX IF NOT EXISTS idx_fehlerliste_ursprung_id
    ON Fehlerliste (Ursprungstabelle, Ursprungs_ID);

-- Dokumentierte Verbindungen (inkl. systemübergreifend ohne harte FK)
CREATE TABLE IF NOT EXISTS Beziehung (
    Beziehungid   INTEGER PRIMARY KEY AUTOINCREMENT,
    VonTabelle    TEXT NOT NULL,
    VonSpalte     TEXT NOT NULL,
    NachTabelle   TEXT NOT NULL,
    NachSpalte    TEXT NOT NULL,
    Art           TEXT NOT NULL CHECK (Art IN ('FK', 'PowerBI', 'logisch')),
    Systemkontext TEXT
);

-- ---------------------------------------------------------------------------
-- SAP Grundtabellen
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS MARA (
    MATNR  TEXT PRIMARY KEY,
    MAKTX  TEXT,
    MTART  TEXT,
    MBRSH  TEXT,
    MATKL  TEXT,
    EXTWG  TEXT,
    SPART  TEXT,
    MEINS  TEXT,
    BSTME  TEXT,
    MANDT  TEXT,
    PSTAT  TEXT,
    LVORM  TEXT,
    MSTAE  TEXT,
    MSTDE  TEXT,
    BEGRU  TEXT,
    ERSDA  TEXT,
    ERNAM  TEXT,
    LAEDA  TEXT,
    AENAM  TEXT,
    NTGEW  REAL,
    BRGEW  REAL,
    GEWEI  TEXT,
    VOLUM  REAL,
    VOLEH  TEXT,
    GROES  TEXT,
    NORMT  TEXT,
    WRKST  TEXT,
    ZEINR  TEXT,
    TRAGR  TEXT,
    RAUBE  TEXT,
    EAN11  TEXT,
    NUMTP  TEXT,
    KZREV  TEXT
);

CREATE TABLE IF NOT EXISTS Produkte_FERT (
    MATNR  TEXT NOT NULL,
    MAKTX  TEXT,
    MTART  TEXT,
    MATKL  TEXT,
    MEINS  TEXT,
    MANDT  TEXT,
    WERKS  TEXT NOT NULL,
    PSTAT  TEXT,
    LVORM  TEXT,
    MMSTA  TEXT,
    MMSTD  TEXT,
    MAABC  TEXT,
    DISMM  TEXT,
    DISPO  TEXT,
    DISLS  TEXT,
    DISGR  TEXT,
    BESKZ  TEXT,
    SOBSL  TEXT,
    EKGRP  TEXT,
    BSTMI  INTEGER,
    BSTMA  INTEGER,
    BSTFE  INTEGER,
    MINBE  INTEGER,
    EISBE  INTEGER,
    MABST  INTEGER,
    PLIFZ  INTEGER,
    WEBAZ  INTEGER,
    DZEIT  INTEGER,
    PERKZ  TEXT,
    RGEKZ  TEXT,
    STAWN  TEXT,
    HERKL  TEXT,
    LADGR  TEXT,
    PRCTR  TEXT,
    XCHPF  TEXT,
    USEQU  TEXT,
    LGPRO  TEXT,
    LGFSB  TEXT,
    MTVFP  TEXT,
    KAUTB  TEXT,
    FHORI  TEXT,
    UEETO  INTEGER,
    UEETK  TEXT,
    UNETO  INTEGER,
    PRIMARY KEY (MATNR, WERKS),
    FOREIGN KEY (MATNR) REFERENCES MARA (MATNR)
);

CREATE TABLE IF NOT EXISTS Ersatzteile_ERSA (
    MATNR  TEXT NOT NULL,
    MAKTX  TEXT,
    MTART  TEXT,
    MATKL  TEXT,
    MEINS  TEXT,
    MANDT  TEXT,
    WERKS  TEXT NOT NULL,
    PSTAT  TEXT,
    LVORM  TEXT,
    MMSTA  TEXT,
    MMSTD  TEXT,
    MAABC  TEXT,
    DISMM  TEXT,
    DISPO  TEXT,
    DISLS  TEXT,
    DISGR  TEXT,
    BESKZ  TEXT,
    SOBSL  TEXT,
    EKGRP  TEXT,
    BSTMI  INTEGER,
    BSTMA  INTEGER,
    BSTFE  INTEGER,
    MINBE  INTEGER,
    EISBE  INTEGER,
    MABST  INTEGER,
    PLIFZ  INTEGER,
    WEBAZ  INTEGER,
    DZEIT  INTEGER,
    PERKZ  TEXT,
    RGEKZ  TEXT,
    STAWN  TEXT,
    HERKL  TEXT,
    LADGR  TEXT,
    PRCTR  TEXT,
    XCHPF  TEXT,
    USEQU  TEXT,
    LGPRO  TEXT,
    LGFSB  TEXT,
    MTVFP  TEXT,
    KAUTB  TEXT,
    FHORI  TEXT,
    UEETO  INTEGER,
    UEETK  TEXT,
    UNETO  INTEGER,
    PRIMARY KEY (MATNR, WERKS),
    FOREIGN KEY (MATNR) REFERENCES MARA (MATNR)
);

-- ---------------------------------------------------------------------------
-- Salesforce Produkte
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS Product2 (
    Id                         TEXT PRIMARY KEY,
    Name                       TEXT,
    ProductCode                TEXT,
    StockKeepingUnit           TEXT,
    Description                TEXT,
    Family                     TEXT,
    IsActive                   TEXT,
    QuantityUnitOfMeasure      TEXT,
    IsArchived                 INTEGER,
    ATN_SAP_Materialnummer__c  TEXT,
    ATN_SAP_Warengruppe__c     TEXT,
    ATN_Herstellwerk__c        TEXT,
    CreatedDate                TEXT,
    CreatedById                TEXT,
    LastModifiedDate           TEXT,
    LastModifiedById           TEXT,
    OwnerId                    TEXT,
    IsDeleted                  INTEGER
);

CREATE INDEX IF NOT EXISTS idx_product2_sku
    ON Product2 (StockKeepingUnit);
CREATE INDEX IF NOT EXISTS idx_product2_matnr
    ON Product2 (ATN_SAP_Materialnummer__c);

CREATE TABLE IF NOT EXISTS Pricebook2 (
    Id               TEXT PRIMARY KEY,
    Name             TEXT,
    IsActive         INTEGER,
    IsStandard       INTEGER,
    Description      TEXT,
    CurrencyIsoCode  TEXT,
    CreatedDate      TEXT,
    CreatedById      TEXT
);

CREATE TABLE IF NOT EXISTS PricebookEntry (
    Id                 TEXT PRIMARY KEY,
    Pricebook2Id       TEXT NOT NULL,
    Product2Id         TEXT NOT NULL,
    UnitPrice          REAL,
    IsActive           INTEGER,
    UseStandardPrice   INTEGER,
    CurrencyIsoCode    TEXT,
    CreatedDate        TEXT,
    REF_Pricebook_Name TEXT,
    REF_Product_Name   TEXT,
    REF_ProductCode    TEXT,
    FOREIGN KEY (Pricebook2Id) REFERENCES Pricebook2 (Id),
    FOREIGN KEY (Product2Id) REFERENCES Product2 (Id)
);

CREATE INDEX IF NOT EXISTS idx_pricebookentry_pb
    ON PricebookEntry (Pricebook2Id);
CREATE INDEX IF NOT EXISTS idx_pricebookentry_prod
    ON PricebookEntry (Product2Id);

-- ---------------------------------------------------------------------------
-- Salesforce Service
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS Account (
    Id                  TEXT PRIMARY KEY,
    Name                TEXT,
    Type                TEXT,
    Industry            TEXT,
    BillingCountry      TEXT,
    BillingCity         TEXT,
    BillingStreet       TEXT,
    BillingPostalCode   TEXT,
    Phone               TEXT,
    Website             TEXT,
    NumberOfEmployees   TEXT,
    OwnerId             TEXT,
    CreatedDate         TEXT,
    ATN_Marktregion__c  TEXT
);

CREATE TABLE IF NOT EXISTS Contact (
    Id               TEXT PRIMARY KEY,
    AccountId        TEXT,
    Salutation       TEXT,
    FirstName        TEXT,
    LastName         TEXT,
    Title            TEXT,
    Email            TEXT,
    Phone            TEXT,
    MailingCountry   TEXT,
    OwnerId          TEXT,
    CreatedDate      TEXT,
    REF_AccountName  TEXT
);

CREATE INDEX IF NOT EXISTS idx_contact_account
    ON Contact (AccountId);

CREATE TABLE IF NOT EXISTS Asset (
    Id              TEXT PRIMARY KEY,
    Name            TEXT,
    AccountId       TEXT,
    ContactId       TEXT,
    Product2Id      TEXT,
    SerialNumber    TEXT,
    Status          TEXT,
    PurchaseDate    TEXT,
    InstallDate     TEXT,
    UsageEndDate    TEXT,
    Price           REAL,
    Quantity        INTEGER,
    OwnerId         TEXT,
    CreatedDate     TEXT,
    ATN_Standort__c TEXT,
    REF_ProductName TEXT,
    REF_AccountName TEXT,
    REF_Land        TEXT,
    FOREIGN KEY (AccountId) REFERENCES Account (Id),
    FOREIGN KEY (ContactId) REFERENCES Contact (Id),
    FOREIGN KEY (Product2Id) REFERENCES Product2 (Id)
);

CREATE INDEX IF NOT EXISTS idx_asset_account ON Asset (AccountId);
CREATE INDEX IF NOT EXISTS idx_asset_contact ON Asset (ContactId);
CREATE INDEX IF NOT EXISTS idx_asset_product ON Asset (Product2Id);
CREATE INDEX IF NOT EXISTS idx_asset_serial ON Asset (SerialNumber);

CREATE TABLE IF NOT EXISTS WorkOrder (
    Id                          TEXT PRIMARY KEY,
    WorkOrderNumber             TEXT,
    AccountId                   TEXT,
    ContactId                   TEXT,
    AssetId                     TEXT,
    Subject                     TEXT,
    Description                 TEXT,
    Status                      TEXT,
    Priority                    TEXT,
    StartDate                   TEXT,
    EndDate                     TEXT,
    CreatedDate                 TEXT,
    ATN_Wartungsart__c          TEXT,
    ATN_Techniker__c            TEXT,
    ATN_Wartungskosten__c       TEXT,
    ATN_Ersatzteile_verwendet__c TEXT,
    REF_AssetName               TEXT,
    REF_AccountName             TEXT,
    REF_Land                    TEXT,
    FOREIGN KEY (AssetId) REFERENCES Asset (Id)
);

CREATE INDEX IF NOT EXISTS idx_workorder_account ON WorkOrder (AccountId);
CREATE INDEX IF NOT EXISTS idx_workorder_asset ON WorkOrder (AssetId);
CREATE INDEX IF NOT EXISTS idx_workorder_number ON WorkOrder (WorkOrderNumber);

-- ---------------------------------------------------------------------------
-- HubSpot
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS Products (
    hs_object_id               TEXT PRIMARY KEY,
    name                       TEXT,
    hs_sku                     TEXT,
    description                TEXT,
    hs_product_type            TEXT,
    hs_status                  TEXT,
    price                      TEXT,
    hs_cost_of_goods_sold      REAL,
    hs_pricing_model           TEXT,
    hs_tax_category            TEXT,
    hs_recurring_billing_period TEXT,
    hs_url                     TEXT,
    hubspot_owner_id           TEXT,
    createdate                 TEXT,
    hs_lastmodifieddate        TEXT,
    hs_object_source           TEXT,
    hs_object_source_label     TEXT,
    atn_sap_materialnummer     TEXT,
    atn_sap_warengruppe        TEXT,
    atn_herstellwerk           TEXT
);

CREATE INDEX IF NOT EXISTS idx_products_sku ON Products (hs_sku);
CREATE INDEX IF NOT EXISTS idx_products_matnr ON Products (atn_sap_materialnummer);

CREATE TABLE IF NOT EXISTS Price_Books (
    hs_object_id                   TEXT PRIMARY KEY,
    hs_name                        TEXT,
    hs_description                 TEXT,
    hs_supported_currencies        TEXT,
    hs_status                      TEXT,
    hs_count_of_included_products  INTEGER,
    hs_is_auto_assigned_enabled    INTEGER,
    hs_createdate                  TEXT,
    hs_lastmodifieddate            TEXT,
    archived                       INTEGER
);

CREATE TABLE IF NOT EXISTS Price_Book_Items (
    hs_object_id              TEXT PRIMARY KEY,
    price_book_id             TEXT NOT NULL,
    hs_associated_product_id  TEXT,
    hs_name                   TEXT,
    hs_sku                    TEXT,
    hs_price_eur              REAL,
    hs_pricing_model          TEXT,
    hs_product_type           TEXT,
    hs_status                 TEXT,
    hs_cost_of_goods_sold     REAL,
    hs_tax_category           TEXT,
    hs_createdate             TEXT,
    hs_lastmodifieddate       TEXT,
    REF_price_book_name       TEXT,
    FOREIGN KEY (price_book_id) REFERENCES Price_Books (hs_object_id)
);

CREATE INDEX IF NOT EXISTS idx_pbi_book ON Price_Book_Items (price_book_id);
CREATE INDEX IF NOT EXISTS idx_pbi_product ON Price_Book_Items (hs_associated_product_id);

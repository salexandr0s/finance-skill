#!/usr/bin/env python3
"""
CSV Import Module for Personal Finance Skill

Supports importing bank transaction CSVs from multiple European banks.
Includes automatic format detection, deduplication, and multi-account support.
"""

import csv
import hashlib
import json
import re
from datetime import datetime, date
from io import StringIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# Known CSV formats for European banks
BANK_FORMATS = {
    # ==========================================================================
    # SWITZERLAND
    # ==========================================================================
    'ubs': {
        'name': 'UBS (Switzerland)',
        'country': 'CH',
        'date_column': ['Valuta', 'Date', 'Buchungsdatum', 'Valutadatum'],
        'amount_column': ['Betrag', 'Amount', 'Debit', 'Credit', 'Belastung', 'Gutschrift'],
        'description_column': ['Beschreibung', 'Description', 'Buchungstext'],
        'date_formats': ['%d.%m.%Y', '%Y-%m-%d', '%d/%m/%Y'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': '.',
    },
    'credit_suisse': {
        'name': 'Credit Suisse',
        'country': 'CH',
        'date_column': ['Valutadatum', 'Datum', 'Date', 'Buchungsdatum'],
        'amount_column': ['Betrag', 'Amount', 'Belastung', 'Gutschrift'],
        'description_column': ['Buchungstext', 'Text', 'Beschreibung'],
        'date_formats': ['%d.%m.%Y', '%Y-%m-%d'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': '.',
    },
    'postfinance': {
        'name': 'PostFinance',
        'country': 'CH',
        'date_column': ['Datum', 'Date', 'Buchungsdatum', 'Valuta'],
        'amount_column': ['Gutschrift', 'Lastschrift', 'Betrag', 'Credit', 'Debit'],
        'description_column': ['Buchungsdetails', 'Details', 'Beschreibung', 'Mitteilungen'],
        'date_formats': ['%d.%m.%Y', '%Y-%m-%d'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': '.',
    },
    'raiffeisen_ch': {
        'name': 'Raiffeisen (Switzerland)',
        'country': 'CH',
        'date_column': ['Datum', 'Valuta', 'Date', 'Buchungsdatum'],
        'amount_column': ['Betrag', 'Amount', 'Belastung', 'Gutschrift'],
        'description_column': ['Text', 'Buchungstext', 'Beschreibung'],
        'date_formats': ['%d.%m.%Y', '%Y-%m-%d'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': '.',
    },
    'zkb': {
        'name': 'Zürcher Kantonalbank (ZKB)',
        'country': 'CH',
        'date_column': ['Datum', 'Valuta', 'Buchungsdatum'],
        'amount_column': ['Betrag', 'Belastung', 'Gutschrift'],
        'description_column': ['Buchungstext', 'Text', 'Beschreibung'],
        'date_formats': ['%d.%m.%Y'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': '.',
    },
    'bcv': {
        'name': 'Banque Cantonale Vaudoise (BCV)',
        'country': 'CH',
        'date_column': ['Date', 'Date valeur', 'Datum'],
        'amount_column': ['Montant', 'Débit', 'Crédit', 'Betrag'],
        'description_column': ['Libellé', 'Description', 'Beschreibung'],
        'date_formats': ['%d.%m.%Y', '%d/%m/%Y'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': '.',
    },
    'bcge': {
        'name': 'Banque Cantonale de Genève (BCGE)',
        'country': 'CH',
        'date_column': ['Date', 'Date valeur'],
        'amount_column': ['Montant', 'Débit', 'Crédit'],
        'description_column': ['Libellé', 'Description'],
        'date_formats': ['%d.%m.%Y', '%d/%m/%Y'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': '.',
    },
    'migros_bank': {
        'name': 'Migros Bank',
        'country': 'CH',
        'date_column': ['Datum', 'Valuta', 'Buchungsdatum'],
        'amount_column': ['Betrag', 'Belastung', 'Gutschrift'],
        'description_column': ['Buchungstext', 'Text'],
        'date_formats': ['%d.%m.%Y'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': '.',
    },
    'cler': {
        'name': 'Bank Cler',
        'country': 'CH',
        'date_column': ['Datum', 'Valuta'],
        'amount_column': ['Betrag', 'Belastung', 'Gutschrift'],
        'description_column': ['Buchungstext', 'Text'],
        'date_formats': ['%d.%m.%Y'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': '.',
    },

    # ==========================================================================
    # GERMANY
    # ==========================================================================
    'deutsche_bank': {
        'name': 'Deutsche Bank',
        'country': 'DE',
        'date_column': ['Buchungstag', 'Wertstellung', 'Booking date', 'Buchungsdatum'],
        'amount_column': ['Betrag (EUR)', 'Betrag', 'Amount', 'Umsatz'],
        'description_column': ['Verwendungszweck', 'Purpose', 'Buchungstext'],
        'date_formats': ['%d.%m.%Y', '%d.%m.%y'],
        'encoding': 'iso-8859-1',
        'delimiter': ';',
        'decimal_separator': ',',
    },
    'sparkasse': {
        'name': 'Sparkasse',
        'country': 'DE',
        'date_column': ['Buchungstag', 'Valutadatum', 'Buchungsdatum'],
        'amount_column': ['Betrag', 'Umsatz', 'Betrag (EUR)'],
        'description_column': ['Verwendungszweck', 'Buchungstext', 'Kundenreferenz'],
        'date_formats': ['%d.%m.%y', '%d.%m.%Y'],
        'encoding': 'iso-8859-1',
        'delimiter': ';',
        'decimal_separator': ',',
    },
    'commerzbank': {
        'name': 'Commerzbank',
        'country': 'DE',
        'date_column': ['Buchungstag', 'Wertstellung', 'Buchungsdatum'],
        'amount_column': ['Betrag', 'Umsatz', 'Betrag (EUR)'],
        'description_column': ['Buchungstext', 'Vorgang', 'Verwendungszweck'],
        'date_formats': ['%d.%m.%Y'],
        'encoding': 'iso-8859-1',
        'delimiter': ';',
        'decimal_separator': ',',
    },
    'ing_diba': {
        'name': 'ING (Germany)',
        'country': 'DE',
        'date_column': ['Buchung', 'Valuta', 'Buchungsdatum'],
        'amount_column': ['Betrag', 'Saldo', 'Betrag (EUR)'],
        'description_column': ['Verwendungszweck', 'Auftraggeber/Empfänger', 'Buchungstext'],
        'date_formats': ['%d.%m.%Y'],
        'encoding': 'iso-8859-1',
        'delimiter': ';',
        'decimal_separator': ',',
    },
    'dkb': {
        'name': 'DKB (Deutsche Kreditbank)',
        'country': 'DE',
        'date_column': ['Buchungstag', 'Wertstellung', 'Belegdatum'],
        'amount_column': ['Betrag (EUR)', 'Betrag', 'Umsatz'],
        'description_column': ['Verwendungszweck', 'Auftraggeber / Begünstigter'],
        'date_formats': ['%d.%m.%Y', '%d.%m.%y'],
        'encoding': 'iso-8859-1',
        'delimiter': ';',
        'decimal_separator': ',',
    },
    'n26_de': {
        'name': 'N26 (Germany)',
        'country': 'DE',
        'date_column': ['Date', 'Datum', 'Booking Date'],
        'amount_column': ['Amount (EUR)', 'Betrag', 'Amount'],
        'description_column': ['Payee', 'Empfänger', 'Reference', 'Verwendungszweck'],
        'date_formats': ['%Y-%m-%d', '%d.%m.%Y'],
        'encoding': 'utf-8',
        'delimiter': ',',
        'decimal_separator': '.',
    },
    'comdirect': {
        'name': 'comdirect',
        'country': 'DE',
        'date_column': ['Buchungstag', 'Valuta', 'Wertstellung'],
        'amount_column': ['Umsatz', 'Betrag', 'Betrag in EUR'],
        'description_column': ['Vorgang', 'Buchungstext', 'Verwendungszweck'],
        'date_formats': ['%d.%m.%Y'],
        'encoding': 'iso-8859-1',
        'delimiter': ';',
        'decimal_separator': ',',
    },
    'hypovereinsbank': {
        'name': 'HypoVereinsbank (UniCredit)',
        'country': 'DE',
        'date_column': ['Buchungsdatum', 'Valuta', 'Wertstellung'],
        'amount_column': ['Betrag', 'Umsatz'],
        'description_column': ['Verwendungszweck', 'Buchungstext'],
        'date_formats': ['%d.%m.%Y'],
        'encoding': 'iso-8859-1',
        'delimiter': ';',
        'decimal_separator': ',',
    },
    'postbank_de': {
        'name': 'Postbank (Germany)',
        'country': 'DE',
        'date_column': ['Buchungsdatum', 'Wertstellung'],
        'amount_column': ['Betrag', 'Umsatz'],
        'description_column': ['Verwendungszweck', 'Empfänger/Auftraggeber'],
        'date_formats': ['%d.%m.%Y'],
        'encoding': 'iso-8859-1',
        'delimiter': ';',
        'decimal_separator': ',',
    },
    'volksbank': {
        'name': 'Volksbank / Raiffeisenbank (Germany)',
        'country': 'DE',
        'date_column': ['Buchungstag', 'Valuta'],
        'amount_column': ['Betrag', 'Umsatz'],
        'description_column': ['Vorgang/Verwendungszweck', 'Empfänger/Zahlungspflichtiger'],
        'date_formats': ['%d.%m.%Y'],
        'encoding': 'iso-8859-1',
        'delimiter': ';',
        'decimal_separator': ',',
    },
    'targobank': {
        'name': 'Targobank',
        'country': 'DE',
        'date_column': ['Buchungstag', 'Valuta'],
        'amount_column': ['Betrag', 'Umsatz'],
        'description_column': ['Verwendungszweck', 'Buchungstext'],
        'date_formats': ['%d.%m.%Y'],
        'encoding': 'iso-8859-1',
        'delimiter': ';',
        'decimal_separator': ',',
    },

    # ==========================================================================
    # FRANCE
    # ==========================================================================
    'bnp_paribas': {
        'name': 'BNP Paribas',
        'country': 'FR',
        'date_column': ['Date', 'Date opération', 'Date de valeur', 'Date comptable'],
        'amount_column': ['Montant', 'Débit', 'Crédit', 'Montant (EUR)'],
        'description_column': ['Libellé', 'Description', 'Libellé opération'],
        'date_formats': ['%d/%m/%Y', '%d/%m/%y', '%d-%m-%Y'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': ',',
    },
    'societe_generale': {
        'name': 'Société Générale',
        'country': 'FR',
        'date_column': ['Date', 'Date opération', 'Date valeur'],
        'amount_column': ['Montant', 'Débit', 'Crédit'],
        'description_column': ['Libellé', 'Détail', 'Description'],
        'date_formats': ['%d/%m/%Y'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': ',',
    },
    'credit_agricole': {
        'name': 'Crédit Agricole',
        'country': 'FR',
        'date_column': ['Date', 'Date opération', 'Date valeur', 'Date comptable'],
        'amount_column': ['Montant', 'Débit', 'Crédit', 'Montant en euros'],
        'description_column': ['Libellé', 'Nature', 'Libellé simplifié'],
        'date_formats': ['%d/%m/%Y', '%d/%m/%y'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': ',',
    },
    'credit_mutuel': {
        'name': 'Crédit Mutuel',
        'country': 'FR',
        'date_column': ['Date', 'Date opération', 'Date valeur'],
        'amount_column': ['Montant', 'Débit', 'Crédit'],
        'description_column': ['Libellé', 'Description'],
        'date_formats': ['%d/%m/%Y'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': ',',
    },
    'la_banque_postale': {
        'name': 'La Banque Postale',
        'country': 'FR',
        'date_column': ['Date', 'Date opération', 'Date valeur'],
        'amount_column': ['Montant', 'Débit', 'Crédit'],
        'description_column': ['Libellé', 'Description'],
        'date_formats': ['%d/%m/%Y'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': ',',
    },
    'lcl': {
        'name': 'LCL (Le Crédit Lyonnais)',
        'country': 'FR',
        'date_column': ['Date', 'Date opération', 'Date valeur'],
        'amount_column': ['Montant', 'Débit', 'Crédit'],
        'description_column': ['Libellé', 'Description'],
        'date_formats': ['%d/%m/%Y'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': ',',
    },
    'boursorama': {
        'name': 'Boursorama Banque',
        'country': 'FR',
        'date_column': ['dateOp', 'dateVal', 'Date opération', 'Date valeur'],
        'amount_column': ['amount', 'Montant', 'Débit', 'Crédit'],
        'description_column': ['label', 'Libellé', 'Description'],
        'date_formats': ['%Y-%m-%d', '%d/%m/%Y'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': ',',
    },
    'fortuneo': {
        'name': 'Fortuneo',
        'country': 'FR',
        'date_column': ['Date opération', 'Date valeur'],
        'amount_column': ['Montant', 'Débit', 'Crédit'],
        'description_column': ['Libellé', 'Description'],
        'date_formats': ['%d/%m/%Y'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': ',',
    },
    'caisse_epargne': {
        'name': "Caisse d'Épargne",
        'country': 'FR',
        'date_column': ['Date', 'Date opération', 'Date comptable'],
        'amount_column': ['Montant', 'Débit', 'Crédit'],
        'description_column': ['Libellé', 'Nature opération'],
        'date_formats': ['%d/%m/%Y'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': ',',
    },

    # ==========================================================================
    # UNITED KINGDOM
    # ==========================================================================
    'barclays': {
        'name': 'Barclays',
        'country': 'GB',
        'date_column': ['Date', 'Transaction Date', 'Booking Date'],
        'amount_column': ['Amount', 'Money In', 'Money Out', 'Value'],
        'description_column': ['Description', 'Memo', 'Reference', 'Narrative'],
        'date_formats': ['%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d', '%d %b %Y'],
        'encoding': 'utf-8',
        'delimiter': ',',
        'decimal_separator': '.',
    },
    'hsbc': {
        'name': 'HSBC',
        'country': 'GB',
        'date_column': ['Date', 'Transaction Date', 'Value Date'],
        'amount_column': ['Amount', 'Paid In', 'Paid Out', 'Credit', 'Debit'],
        'description_column': ['Description', 'Transaction Description', 'Narrative'],
        'date_formats': ['%d/%m/%Y', '%d %b %Y', '%d-%m-%Y'],
        'encoding': 'utf-8',
        'delimiter': ',',
        'decimal_separator': '.',
    },
    'lloyds': {
        'name': 'Lloyds Bank',
        'country': 'GB',
        'date_column': ['Transaction Date', 'Date', 'Value Date'],
        'amount_column': ['Debit Amount', 'Credit Amount', 'Amount', 'Value'],
        'description_column': ['Transaction Description', 'Description', 'Narrative'],
        'date_formats': ['%d/%m/%Y', '%d %b %Y'],
        'encoding': 'utf-8',
        'delimiter': ',',
        'decimal_separator': '.',
    },
    'natwest': {
        'name': 'NatWest',
        'country': 'GB',
        'date_column': ['Date', 'Transaction Date', 'Value Date'],
        'amount_column': ['Value', 'Amount', 'Debit', 'Credit'],
        'description_column': ['Description', 'Narrative', 'Type'],
        'date_formats': ['%d/%m/%Y', '%d %b %Y'],
        'encoding': 'utf-8',
        'delimiter': ',',
        'decimal_separator': '.',
    },
    'rbs': {
        'name': 'Royal Bank of Scotland',
        'country': 'GB',
        'date_column': ['Date', 'Transaction Date'],
        'amount_column': ['Value', 'Amount', 'Debit', 'Credit'],
        'description_column': ['Description', 'Narrative'],
        'date_formats': ['%d/%m/%Y', '%d %b %Y'],
        'encoding': 'utf-8',
        'delimiter': ',',
        'decimal_separator': '.',
    },
    'santander_uk': {
        'name': 'Santander UK',
        'country': 'GB',
        'date_column': ['Date', 'Transaction Date'],
        'amount_column': ['Amount', 'Money In', 'Money Out'],
        'description_column': ['Description', 'Narrative'],
        'date_formats': ['%d/%m/%Y'],
        'encoding': 'utf-8',
        'delimiter': ',',
        'decimal_separator': '.',
    },
    'halifax': {
        'name': 'Halifax',
        'country': 'GB',
        'date_column': ['Transaction Date', 'Date'],
        'amount_column': ['Debit Amount', 'Credit Amount', 'Amount'],
        'description_column': ['Transaction Description', 'Description'],
        'date_formats': ['%d/%m/%Y'],
        'encoding': 'utf-8',
        'delimiter': ',',
        'decimal_separator': '.',
    },
    'monzo': {
        'name': 'Monzo',
        'country': 'GB',
        'date_column': ['Date', 'Created'],
        'amount_column': ['Amount', 'Money In', 'Money Out'],
        'description_column': ['Description', 'Name', 'Notes'],
        'date_formats': ['%d/%m/%Y', '%Y-%m-%d'],
        'encoding': 'utf-8',
        'delimiter': ',',
        'decimal_separator': '.',
    },
    'starling': {
        'name': 'Starling Bank',
        'country': 'GB',
        'date_column': ['Date', 'Transaction Date'],
        'amount_column': ['Amount', 'Amount (GBP)'],
        'description_column': ['Reference', 'Counter Party', 'Description'],
        'date_formats': ['%d/%m/%Y', '%Y-%m-%d'],
        'encoding': 'utf-8',
        'delimiter': ',',
        'decimal_separator': '.',
    },
    'revolut_uk': {
        'name': 'Revolut (UK)',
        'country': 'GB',
        'date_column': ['Started Date', 'Completed Date', 'Date'],
        'amount_column': ['Amount', 'Fee', 'Balance'],
        'description_column': ['Description', 'Reference'],
        'date_formats': ['%Y-%m-%d %H:%M:%S', '%d %b %Y', '%Y-%m-%d'],
        'encoding': 'utf-8',
        'delimiter': ',',
        'decimal_separator': '.',
    },
    'nationwide': {
        'name': 'Nationwide',
        'country': 'GB',
        'date_column': ['Date', 'Transaction date'],
        'amount_column': ['Paid in', 'Paid out', 'Amount'],
        'description_column': ['Description', 'Transactions'],
        'date_formats': ['%d %b %Y', '%d/%m/%Y'],
        'encoding': 'utf-8',
        'delimiter': ',',
        'decimal_separator': '.',
    },

    # ==========================================================================
    # NETHERLANDS
    # ==========================================================================
    'ing_nl': {
        'name': 'ING (Netherlands)',
        'country': 'NL',
        'date_column': ['Datum', 'Date', 'Boekingsdatum'],
        'amount_column': ['Bedrag (EUR)', 'Af Bij', 'Amount', 'Bedrag'],
        'description_column': ['Naam / Omschrijving', 'Mededelingen', 'Omschrijving'],
        'date_formats': ['%Y%m%d', '%d-%m-%Y', '%Y-%m-%d'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': ',',
    },
    'rabobank': {
        'name': 'Rabobank',
        'country': 'NL',
        'date_column': ['Datum', 'Rentedatum', 'Boekingsdatum'],
        'amount_column': ['Bedrag', 'Amount', 'Af', 'Bij'],
        'description_column': ['Omschrijving-1', 'Naam tegenpartij', 'Omschrijving'],
        'date_formats': ['%Y-%m-%d', '%d-%m-%Y'],
        'encoding': 'utf-8',
        'delimiter': ',',
        'decimal_separator': '.',
    },
    'abn_amro': {
        'name': 'ABN AMRO',
        'country': 'NL',
        'date_column': ['Transactiedatum', 'Boekdatum', 'Datum'],
        'amount_column': ['Transactiebedrag', 'Bedrag', 'Af', 'Bij'],
        'description_column': ['Omschrijving', 'Tegenrekening', 'Naam'],
        'date_formats': ['%Y%m%d', '%d-%m-%Y'],
        'encoding': 'utf-8',
        'delimiter': '\t',
        'decimal_separator': ',',
    },
    'sns_bank': {
        'name': 'SNS Bank',
        'country': 'NL',
        'date_column': ['Datum', 'Boekingsdatum'],
        'amount_column': ['Bedrag', 'Af', 'Bij'],
        'description_column': ['Omschrijving', 'Naam'],
        'date_formats': ['%d-%m-%Y'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': ',',
    },
    'triodos_nl': {
        'name': 'Triodos Bank (Netherlands)',
        'country': 'NL',
        'date_column': ['Datum', 'Boekingsdatum'],
        'amount_column': ['Bedrag', 'Af', 'Bij'],
        'description_column': ['Omschrijving', 'Naam tegenrekening'],
        'date_formats': ['%d-%m-%Y'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': ',',
    },
    'bunq': {
        'name': 'bunq',
        'country': 'NL',
        'date_column': ['Date', 'Datum'],
        'amount_column': ['Amount', 'Bedrag'],
        'description_column': ['Description', 'Omschrijving', 'Name'],
        'date_formats': ['%Y-%m-%d', '%d-%m-%Y'],
        'encoding': 'utf-8',
        'delimiter': ',',
        'decimal_separator': '.',
    },

    # ==========================================================================
    # BELGIUM
    # ==========================================================================
    'kbc': {
        'name': 'KBC Bank',
        'country': 'BE',
        'date_column': ['Datum', 'Date', 'Boekingsdatum'],
        'amount_column': ['Bedrag', 'Montant', 'Credit', 'Debet'],
        'description_column': ['Omschrijving', 'Description', 'Mededeling'],
        'date_formats': ['%d/%m/%Y', '%d-%m-%Y'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': ',',
    },
    'belfius': {
        'name': 'Belfius',
        'country': 'BE',
        'date_column': ['Datum', 'Date', 'Boekingsdatum'],
        'amount_column': ['Bedrag', 'Montant', 'Amount'],
        'description_column': ['Omschrijving', 'Description', 'Mededeling'],
        'date_formats': ['%d/%m/%Y'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': ',',
    },
    'ing_be': {
        'name': 'ING (Belgium)',
        'country': 'BE',
        'date_column': ['Date', 'Datum', 'Date comptable'],
        'amount_column': ['Montant', 'Bedrag', 'Amount'],
        'description_column': ['Description', 'Omschrijving', 'Communication'],
        'date_formats': ['%d/%m/%Y'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': ',',
    },
    'bnp_fortis': {
        'name': 'BNP Paribas Fortis',
        'country': 'BE',
        'date_column': ['Date', 'Datum', 'Date de valeur'],
        'amount_column': ['Montant', 'Bedrag', 'Crédit', 'Débit'],
        'description_column': ['Communication', 'Mededeling', 'Description'],
        'date_formats': ['%d/%m/%Y'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': ',',
    },
    'argenta': {
        'name': 'Argenta',
        'country': 'BE',
        'date_column': ['Datum', 'Date'],
        'amount_column': ['Bedrag', 'Montant'],
        'description_column': ['Omschrijving', 'Description'],
        'date_formats': ['%d/%m/%Y'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': ',',
    },

    # ==========================================================================
    # AUSTRIA
    # ==========================================================================
    'erste_bank': {
        'name': 'Erste Bank',
        'country': 'AT',
        'date_column': ['Buchungsdatum', 'Valuta', 'Datum'],
        'amount_column': ['Betrag', 'Umsatz', 'Haben', 'Soll'],
        'description_column': ['Buchungstext', 'Verwendungszweck', 'Text'],
        'date_formats': ['%d.%m.%Y'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': ',',
    },
    'raiffeisen_at': {
        'name': 'Raiffeisen (Austria)',
        'country': 'AT',
        'date_column': ['Buchungsdatum', 'Valutadatum', 'Datum'],
        'amount_column': ['Betrag', 'Umsatz'],
        'description_column': ['Buchungstext', 'Verwendungszweck'],
        'date_formats': ['%d.%m.%Y'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': ',',
    },
    'bank_austria': {
        'name': 'Bank Austria (UniCredit)',
        'country': 'AT',
        'date_column': ['Buchungsdatum', 'Valuta'],
        'amount_column': ['Betrag', 'Umsatz'],
        'description_column': ['Buchungstext', 'Verwendungszweck'],
        'date_formats': ['%d.%m.%Y'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': ',',
    },
    'bawag': {
        'name': 'BAWAG PSK',
        'country': 'AT',
        'date_column': ['Buchungsdatum', 'Valuta'],
        'amount_column': ['Betrag', 'Umsatz'],
        'description_column': ['Buchungstext', 'Verwendungszweck'],
        'date_formats': ['%d.%m.%Y'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': ',',
    },

    # ==========================================================================
    # SPAIN
    # ==========================================================================
    'santander_es': {
        'name': 'Santander (Spain)',
        'country': 'ES',
        'date_column': ['Fecha', 'F. Valor', 'Fecha operación'],
        'amount_column': ['Importe', 'Importe (EUR)', 'Cargo', 'Abono'],
        'description_column': ['Concepto', 'Descripción', 'Observaciones'],
        'date_formats': ['%d/%m/%Y', '%d-%m-%Y'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': ',',
    },
    'bbva': {
        'name': 'BBVA',
        'country': 'ES',
        'date_column': ['Fecha', 'F. Valor', 'Fecha operación'],
        'amount_column': ['Importe', 'Cargo', 'Abono'],
        'description_column': ['Concepto', 'Descripción'],
        'date_formats': ['%d/%m/%Y'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': ',',
    },
    'caixabank': {
        'name': 'CaixaBank',
        'country': 'ES',
        'date_column': ['Fecha', 'F. Valor'],
        'amount_column': ['Importe', 'Cargo', 'Abono'],
        'description_column': ['Concepto', 'Descripción'],
        'date_formats': ['%d/%m/%Y'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': ',',
    },
    'sabadell': {
        'name': 'Banco Sabadell',
        'country': 'ES',
        'date_column': ['Fecha', 'F. Valor'],
        'amount_column': ['Importe', 'Cargo', 'Abono'],
        'description_column': ['Concepto', 'Descripción'],
        'date_formats': ['%d/%m/%Y'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': ',',
    },

    # ==========================================================================
    # ITALY
    # ==========================================================================
    'intesa_sanpaolo': {
        'name': 'Intesa Sanpaolo',
        'country': 'IT',
        'date_column': ['Data', 'Data Contabile', 'Data Valuta'],
        'amount_column': ['Importo', 'Dare', 'Avere'],
        'description_column': ['Descrizione', 'Causale'],
        'date_formats': ['%d/%m/%Y'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': ',',
    },
    'unicredit_it': {
        'name': 'UniCredit (Italy)',
        'country': 'IT',
        'date_column': ['Data', 'Data Contabile', 'Data Valuta'],
        'amount_column': ['Importo', 'Dare', 'Avere'],
        'description_column': ['Descrizione', 'Causale'],
        'date_formats': ['%d/%m/%Y'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': ',',
    },
    'bnl': {
        'name': 'BNL (Banca Nazionale del Lavoro)',
        'country': 'IT',
        'date_column': ['Data', 'Data operazione', 'Data valuta'],
        'amount_column': ['Importo', 'Dare', 'Avere'],
        'description_column': ['Descrizione', 'Causale'],
        'date_formats': ['%d/%m/%Y'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': ',',
    },
    'fineco': {
        'name': 'FinecoBank',
        'country': 'IT',
        'date_column': ['Data', 'Data Contabile'],
        'amount_column': ['Entrate', 'Uscite', 'Importo'],
        'description_column': ['Descrizione', 'Descrizione operazione'],
        'date_formats': ['%d/%m/%Y'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': ',',
    },

    # ==========================================================================
    # PORTUGAL
    # ==========================================================================
    'cgd': {
        'name': 'Caixa Geral de Depósitos',
        'country': 'PT',
        'date_column': ['Data', 'Data Mov.', 'Data Valor'],
        'amount_column': ['Montante', 'Valor', 'Débito', 'Crédito'],
        'description_column': ['Descrição', 'Descritivo'],
        'date_formats': ['%d-%m-%Y', '%d/%m/%Y'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': ',',
    },
    'millennium_bcp': {
        'name': 'Millennium BCP',
        'country': 'PT',
        'date_column': ['Data', 'Data Mov.', 'Data Valor'],
        'amount_column': ['Montante', 'Valor', 'Débito', 'Crédito'],
        'description_column': ['Descrição', 'Descritivo'],
        'date_formats': ['%d-%m-%Y', '%d/%m/%Y'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': ',',
    },
    'novo_banco': {
        'name': 'Novo Banco',
        'country': 'PT',
        'date_column': ['Data', 'Data Mov.'],
        'amount_column': ['Montante', 'Valor'],
        'description_column': ['Descrição', 'Descritivo'],
        'date_formats': ['%d-%m-%Y'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': ',',
    },

    # ==========================================================================
    # IRELAND
    # ==========================================================================
    'aib': {
        'name': 'AIB (Allied Irish Banks)',
        'country': 'IE',
        'date_column': ['Date', 'Posted Date', 'Value Date'],
        'amount_column': ['Debit', 'Credit', 'Amount'],
        'description_column': ['Description', 'Narrative'],
        'date_formats': ['%d/%m/%Y', '%d %b %Y'],
        'encoding': 'utf-8',
        'delimiter': ',',
        'decimal_separator': '.',
    },
    'bank_of_ireland': {
        'name': 'Bank of Ireland',
        'country': 'IE',
        'date_column': ['Date', 'Transaction Date'],
        'amount_column': ['Debit', 'Credit', 'Amount'],
        'description_column': ['Description', 'Details'],
        'date_formats': ['%d/%m/%Y'],
        'encoding': 'utf-8',
        'delimiter': ',',
        'decimal_separator': '.',
    },
    'ptsb': {
        'name': 'Permanent TSB',
        'country': 'IE',
        'date_column': ['Date', 'Transaction Date'],
        'amount_column': ['Debit', 'Credit', 'Amount'],
        'description_column': ['Description', 'Narrative'],
        'date_formats': ['%d/%m/%Y'],
        'encoding': 'utf-8',
        'delimiter': ',',
        'decimal_separator': '.',
    },

    # ==========================================================================
    # NORDIC COUNTRIES
    # ==========================================================================
    'nordea': {
        'name': 'Nordea',
        'country': 'FI',
        'date_column': ['Kirjauspäivä', 'Arvopäivä', 'Booking date', 'Date'],
        'amount_column': ['Määrä', 'Amount', 'Summa'],
        'description_column': ['Saaja/Maksaja', 'Viesti', 'Message', 'Description'],
        'date_formats': ['%d.%m.%Y', '%Y-%m-%d'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': ',',
    },
    'op_bank': {
        'name': 'OP Bank (Finland)',
        'country': 'FI',
        'date_column': ['Kirjauspäivä', 'Arvopäivä'],
        'amount_column': ['Määrä', 'Summa'],
        'description_column': ['Selite', 'Saaja/Maksaja'],
        'date_formats': ['%d.%m.%Y'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': ',',
    },
    'danske_bank': {
        'name': 'Danske Bank',
        'country': 'DK',
        'date_column': ['Dato', 'Bogføringsdato', 'Date'],
        'amount_column': ['Beløb', 'Amount'],
        'description_column': ['Tekst', 'Description'],
        'date_formats': ['%d.%m.%Y', '%d-%m-%Y'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': ',',
    },
    'seb': {
        'name': 'SEB (Sweden)',
        'country': 'SE',
        'date_column': ['Bokföringsdatum', 'Transaktionsdatum', 'Date'],
        'amount_column': ['Belopp', 'Amount'],
        'description_column': ['Text', 'Beskrivning', 'Description'],
        'date_formats': ['%Y-%m-%d', '%d.%m.%Y'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': ',',
    },
    'swedbank': {
        'name': 'Swedbank',
        'country': 'SE',
        'date_column': ['Bokföringsdatum', 'Transaktionsdatum'],
        'amount_column': ['Belopp', 'Summa'],
        'description_column': ['Beskrivning', 'Text'],
        'date_formats': ['%Y-%m-%d'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': ',',
    },
    'handelsbanken': {
        'name': 'Handelsbanken',
        'country': 'SE',
        'date_column': ['Datum', 'Bokföringsdatum'],
        'amount_column': ['Belopp', 'Summa'],
        'description_column': ['Text', 'Beskrivning'],
        'date_formats': ['%Y-%m-%d'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': ',',
    },
    'dnb': {
        'name': 'DNB (Norway)',
        'country': 'NO',
        'date_column': ['Dato', 'Bokføringsdato'],
        'amount_column': ['Beløp', 'Inn', 'Ut'],
        'description_column': ['Forklaring', 'Beskrivelse'],
        'date_formats': ['%d.%m.%Y'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': ',',
    },

    # ==========================================================================
    # POLAND
    # ==========================================================================
    'pko_bp': {
        'name': 'PKO Bank Polski',
        'country': 'PL',
        'date_column': ['Data operacji', 'Data księgowania', 'Data'],
        'amount_column': ['Kwota', 'Kwota operacji'],
        'description_column': ['Opis operacji', 'Tytuł'],
        'date_formats': ['%Y-%m-%d', '%d.%m.%Y'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': ',',
    },
    'mbank': {
        'name': 'mBank',
        'country': 'PL',
        'date_column': ['Data operacji', 'Data księgowania'],
        'amount_column': ['Kwota', 'Kwota operacji'],
        'description_column': ['Opis', 'Tytuł'],
        'date_formats': ['%Y-%m-%d'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': ',',
    },
    'ing_pl': {
        'name': 'ING Bank Śląski',
        'country': 'PL',
        'date_column': ['Data transakcji', 'Data księgowania'],
        'amount_column': ['Kwota', 'Kwota transakcji'],
        'description_column': ['Opis', 'Tytuł'],
        'date_formats': ['%Y-%m-%d', '%d.%m.%Y'],
        'encoding': 'utf-8',
        'delimiter': ';',
        'decimal_separator': ',',
    },

    # ==========================================================================
    # NEOBANKS / DIGITAL BANKS (Pan-European)
    # ==========================================================================
    'revolut': {
        'name': 'Revolut',
        'country': 'EU',
        'date_column': ['Started Date', 'Completed Date', 'Date'],
        'amount_column': ['Amount', 'Fee', 'Balance'],
        'description_column': ['Description', 'Reference', 'Type'],
        'date_formats': ['%Y-%m-%d %H:%M:%S', '%d %b %Y', '%Y-%m-%d'],
        'encoding': 'utf-8',
        'delimiter': ',',
        'decimal_separator': '.',
    },
    'n26': {
        'name': 'N26',
        'country': 'EU',
        'date_column': ['Date', 'Booking Date'],
        'amount_column': ['Amount (EUR)', 'Amount', 'Original Amount'],
        'description_column': ['Payee', 'Reference', 'Payment Reference'],
        'date_formats': ['%Y-%m-%d', '%d.%m.%Y'],
        'encoding': 'utf-8',
        'delimiter': ',',
        'decimal_separator': '.',
    },
    'wise': {
        'name': 'Wise (TransferWise)',
        'country': 'EU',
        'date_column': ['Date', 'Created on'],
        'amount_column': ['Amount', 'Target amount', 'Source amount'],
        'description_column': ['Description', 'Reference', 'Recipient'],
        'date_formats': ['%Y-%m-%d', '%d-%m-%Y'],
        'encoding': 'utf-8',
        'delimiter': ',',
        'decimal_separator': '.',
    },
    'vivid': {
        'name': 'Vivid Money',
        'country': 'EU',
        'date_column': ['Date', 'Transaction date'],
        'amount_column': ['Amount', 'Transaction amount'],
        'description_column': ['Description', 'Merchant'],
        'date_formats': ['%Y-%m-%d', '%d.%m.%Y'],
        'encoding': 'utf-8',
        'delimiter': ',',
        'decimal_separator': '.',
    },
    'tomorrow': {
        'name': 'Tomorrow Bank',
        'country': 'DE',
        'date_column': ['Date', 'Booking date'],
        'amount_column': ['Amount', 'Betrag'],
        'description_column': ['Description', 'Verwendungszweck'],
        'date_formats': ['%Y-%m-%d', '%d.%m.%Y'],
        'encoding': 'utf-8',
        'delimiter': ',',
        'decimal_separator': '.',
    },

    # ==========================================================================
    # GENERIC FALLBACK
    # ==========================================================================
    'generic': {
        'name': 'Generic CSV',
        'country': 'XX',
        'date_column': ['Date', 'Datum', 'date', 'Transaction Date', 'Booking Date',
                       'Fecha', 'Data', 'Dato', 'Päivämäärä'],
        'amount_column': ['Amount', 'Betrag', 'amount', 'Montant', 'Value',
                         'Importe', 'Importo', 'Beløb', 'Kwota', 'Summa'],
        'description_column': ['Description', 'Beschreibung', 'description', 'Text', 'Memo',
                              'Libellé', 'Concepto', 'Descrizione', 'Omschrijving'],
        'date_formats': ['%Y-%m-%d', '%d/%m/%Y', '%d.%m.%Y', '%m/%d/%Y', '%d-%m-%Y',
                        '%Y%m%d', '%d %b %Y'],
        'encoding': 'utf-8',
        'delimiter': ',',
        'decimal_separator': '.',
    },
}


class CSVImportError(Exception):
    """Custom exception for CSV import errors"""
    pass


def detect_bank_format(csv_content: str, filename: str = None) -> Tuple[str, Dict]:
    """
    Auto-detect bank format from CSV content and filename.

    Args:
        csv_content: Raw CSV content as string
        filename: Optional filename for hints

    Returns:
        Tuple of (bank_key, format_config)
    """
    # Try to detect from filename
    if filename:
        filename_lower = filename.lower()
        for bank_key, config in BANK_FORMATS.items():
            if bank_key in filename_lower or config['name'].lower() in filename_lower:
                return bank_key, config

    # Try each delimiter to parse headers
    for delimiter in [',', ';', '\t']:
        try:
            # Read first few lines
            reader = csv.reader(StringIO(csv_content), delimiter=delimiter)
            headers = next(reader, [])
            if not headers or len(headers) < 2:
                continue

            headers_lower = [h.lower().strip() for h in headers]

            # Score each bank format
            best_match = ('generic', BANK_FORMATS['generic'], 0)

            for bank_key, config in BANK_FORMATS.items():
                if bank_key == 'generic':
                    continue

                score = 0
                # Check date columns
                for col in config['date_column']:
                    if col.lower() in headers_lower:
                        score += 10
                        break

                # Check amount columns
                for col in config['amount_column']:
                    if col.lower() in headers_lower:
                        score += 10
                        break

                # Check description columns
                for col in config['description_column']:
                    if col.lower() in headers_lower:
                        score += 5
                        break

                # Check delimiter match
                if config['delimiter'] == delimiter:
                    score += 5

                if score > best_match[2]:
                    best_match = (bank_key, config, score)

            if best_match[2] > 15:  # Minimum threshold
                return best_match[0], best_match[1]

        except Exception:
            continue

    return 'generic', BANK_FORMATS['generic']


def parse_amount(value: str, decimal_separator: str = '.') -> float:
    """
    Parse amount string to float, handling various formats.

    Args:
        value: Amount as string (may include currency symbols, spaces, etc.)
        decimal_separator: Decimal separator character

    Returns:
        Parsed float value
    """
    if not value or not str(value).strip():
        return 0.0

    # Clean the value
    value = str(value).strip()

    # Remove currency codes and symbols (EUR, USD, GBP, CHF, etc.)
    value = re.sub(r'^(EUR|USD|GBP|CHF|JPY|CAD|AUD|SEK|NOK|DKK|PLN|CZK|HUF)\s*', '', value, flags=re.IGNORECASE)
    value = re.sub(r'\s*(EUR|USD|GBP|CHF|JPY|CAD|AUD|SEK|NOK|DKK|PLN|CZK|HUF)$', '', value, flags=re.IGNORECASE)

    # Remove currency symbols and whitespace
    value = re.sub(r'[€$£¥₣\s]', '', value)

    # Handle European number format (1.234,56 -> 1234.56)
    if decimal_separator == ',':
        value = value.replace('.', '')  # Remove thousand separators
        value = value.replace(',', '.')  # Convert decimal separator
    else:
        value = value.replace(',', '')  # Remove thousand separators

    # Handle parentheses for negative numbers
    if value.startswith('(') and value.endswith(')'):
        value = '-' + value[1:-1]

    # Handle CR/DR suffixes
    if value.upper().endswith('CR'):
        value = value[:-2]
    elif value.upper().endswith('DR'):
        value = '-' + value[:-2]

    try:
        return float(value)
    except ValueError:
        return 0.0


def parse_date(value: str, formats: List[str]) -> Optional[date]:
    """
    Parse date string using multiple format attempts.

    Args:
        value: Date string
        formats: List of date formats to try

    Returns:
        Parsed date or None
    """
    if not value or not str(value).strip():
        return None

    value = str(value).strip()

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue

    # Try ISO format as last resort
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).date()
    except ValueError:
        pass

    return None


def find_column(headers: List[str], candidates: List[str]) -> Optional[int]:
    """
    Find column index from list of candidate names.

    Args:
        headers: CSV headers
        candidates: List of possible column names

    Returns:
        Column index or None
    """
    headers_lower = [h.lower().strip() for h in headers]

    for candidate in candidates:
        candidate_lower = candidate.lower().strip()
        if candidate_lower in headers_lower:
            return headers_lower.index(candidate_lower)

    return None


def create_transaction_hash(account_id: str, booking_date: str, amount: float,
                           description: str) -> str:
    """
    Create deterministic hash for transaction deduplication.

    Args:
        account_id: Account identifier
        booking_date: Transaction date (ISO format)
        amount: Transaction amount
        description: Transaction description

    Returns:
        MD5 hash string
    """
    # Normalize description (remove extra whitespace, lowercase)
    desc_normalized = ' '.join(description.lower().split()) if description else ''

    # Round amount to 2 decimal places for consistency
    amount_normalized = f"{amount:.2f}"

    # Create hash from key fields
    key = f"{account_id}|{booking_date}|{amount_normalized}|{desc_normalized}"
    return hashlib.md5(key.encode('utf-8')).hexdigest()


def import_csv(csv_content: str, account_id: str, account_name: str = None,
               bank_format: str = None, currency: str = 'EUR',
               filename: str = None) -> Dict[str, Any]:
    """
    Import transactions from CSV content.

    Args:
        csv_content: Raw CSV content
        account_id: Identifier for the account (user-defined)
        account_name: Friendly name for the account
        bank_format: Bank format key (auto-detected if not provided)
        currency: Default currency if not in CSV
        filename: Original filename (helps with format detection)

    Returns:
        Dict with import results including transactions, stats, and errors
    """
    from db import (
        get_db, init_database, create_transaction_id,
        get_connected_accounts, store_csv_account
    )

    # Ensure database is initialized
    init_database()

    # Detect or use specified format
    if bank_format and bank_format in BANK_FORMATS:
        format_key = bank_format
        format_config = BANK_FORMATS[bank_format]
    else:
        format_key, format_config = detect_bank_format(csv_content, filename)

    # Try to decode with specified encoding
    try:
        if isinstance(csv_content, bytes):
            csv_content = csv_content.decode(format_config['encoding'])
    except UnicodeDecodeError:
        # Fallback to utf-8
        if isinstance(csv_content, bytes):
            csv_content = csv_content.decode('utf-8', errors='replace')

    # Parse CSV
    delimiter = format_config['delimiter']
    reader = csv.reader(StringIO(csv_content), delimiter=delimiter)

    # Get headers
    headers = next(reader, None)
    if not headers:
        raise CSVImportError("CSV file is empty or has no headers")

    # Find required columns
    date_col = find_column(headers, format_config['date_column'])
    amount_col = find_column(headers, format_config['amount_column'])
    desc_col = find_column(headers, format_config['description_column'])

    if date_col is None:
        raise CSVImportError(f"Could not find date column. Expected one of: {format_config['date_column']}")
    if amount_col is None:
        raise CSVImportError(f"Could not find amount column. Expected one of: {format_config['amount_column']}")

    # Check for separate debit/credit columns
    debit_col = None
    credit_col = None
    for col_name in ['Debit', 'Lastschrift', 'Débit', 'Money Out', 'Paid Out', 'Debit Amount']:
        idx = find_column(headers, [col_name])
        if idx is not None:
            debit_col = idx
            break
    for col_name in ['Credit', 'Gutschrift', 'Crédit', 'Money In', 'Paid In', 'Credit Amount']:
        idx = find_column(headers, [col_name])
        if idx is not None:
            credit_col = idx
            break

    # Process rows
    transactions = []
    duplicates = []
    errors = []
    existing_hashes = set()

    # Get existing transaction hashes for this account
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT id FROM transactions WHERE account_id = ?",
            (account_id,)
        )
        existing_hashes = {row['id'] for row in cursor.fetchall()}

    row_num = 1  # Start after header
    for row in reader:
        row_num += 1

        try:
            if len(row) <= max(date_col, amount_col):
                continue  # Skip incomplete rows

            # Parse date
            date_str = row[date_col].strip()
            booking_date = parse_date(date_str, format_config['date_formats'])
            if not booking_date:
                errors.append(f"Row {row_num}: Could not parse date '{date_str}'")
                continue

            # Parse amount
            if debit_col is not None and credit_col is not None:
                # Separate debit/credit columns
                debit = parse_amount(row[debit_col] if debit_col < len(row) else '',
                                    format_config['decimal_separator'])
                credit = parse_amount(row[credit_col] if credit_col < len(row) else '',
                                     format_config['decimal_separator'])
                amount = credit - debit if credit else -abs(debit)
            else:
                # Single amount column
                amount = parse_amount(row[amount_col], format_config['decimal_separator'])

            if amount == 0.0:
                continue  # Skip zero-amount transactions

            # Parse description
            description = row[desc_col].strip() if desc_col and desc_col < len(row) else ''

            # Create transaction hash for deduplication
            txn_hash = create_transaction_hash(
                account_id,
                booking_date.isoformat(),
                amount,
                description
            )

            # Check for duplicate
            if txn_hash in existing_hashes:
                duplicates.append({
                    'row': row_num,
                    'date': booking_date.isoformat(),
                    'amount': amount,
                    'description': description[:50]
                })
                continue

            # Add to transactions list
            transactions.append({
                'id': txn_hash,
                'account_id': account_id,
                'booking_date': booking_date.isoformat(),
                'amount': amount,
                'currency': currency,
                'description': description,
                'raw_row': row,
            })

            existing_hashes.add(txn_hash)

        except Exception as e:
            errors.append(f"Row {row_num}: {str(e)}")

    # Store account if new
    store_csv_account(account_id, account_name or f"CSV Import - {format_config['name']}", currency)

    # Store transactions
    stored_count = 0
    with get_db() as conn:
        for txn in transactions:
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO transactions
                    (id, account_id, booking_date, amount, currency, description,
                     category_source, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'pending', datetime('now'))
                """, (
                    txn['id'],
                    txn['account_id'],
                    txn['booking_date'],
                    txn['amount'],
                    txn['currency'],
                    txn['description'],
                ))
                stored_count += 1
            except Exception as e:
                errors.append(f"Failed to store transaction: {str(e)}")

        conn.commit()

    return {
        'success': True,
        'bank_format': format_key,
        'bank_name': format_config['name'],
        'account_id': account_id,
        'account_name': account_name,
        'total_rows': row_num - 1,
        'imported': stored_count,
        'duplicates': len(duplicates),
        'duplicate_details': duplicates[:10],  # First 10 duplicates
        'errors': errors[:10],  # First 10 errors
        'error_count': len(errors),
        'transactions': transactions,
    }


def import_csv_file(file_path: str, account_id: str, account_name: str = None,
                    bank_format: str = None, currency: str = 'EUR') -> Dict[str, Any]:
    """
    Import transactions from a CSV file.

    Args:
        file_path: Path to CSV file
        account_id: Identifier for the account
        account_name: Friendly name for the account
        bank_format: Bank format key (auto-detected if not provided)
        currency: Default currency

    Returns:
        Import results dict
    """
    path = Path(file_path)

    if not path.exists():
        raise CSVImportError(f"File not found: {file_path}")

    if not path.suffix.lower() == '.csv':
        raise CSVImportError(f"File must be a CSV file: {file_path}")

    # Try multiple encodings
    content = None
    for encoding in ['utf-8', 'iso-8859-1', 'cp1252', 'utf-16']:
        try:
            with open(path, 'r', encoding=encoding) as f:
                content = f.read()
            break
        except UnicodeDecodeError:
            continue

    if content is None:
        raise CSVImportError(f"Could not decode file with any known encoding")

    return import_csv(
        content,
        account_id,
        account_name=account_name,
        bank_format=bank_format,
        currency=currency,
        filename=path.name
    )


def get_supported_banks() -> List[Dict[str, str]]:
    """Get list of supported bank formats."""
    return [
        {'key': key, 'name': config['name']}
        for key, config in BANK_FORMATS.items()
        if key != 'generic'
    ]


def list_csv_accounts() -> List[Dict]:
    """List all CSV-imported accounts."""
    from db import get_db

    with get_db() as conn:
        cursor = conn.execute("""
            SELECT id, name, currency, created_at, last_import_at,
                   (SELECT COUNT(*) FROM transactions WHERE account_id = accounts.id) as transaction_count,
                   (SELECT MAX(booking_date) FROM transactions WHERE account_id = accounts.id) as latest_transaction
            FROM accounts
            WHERE institution_id = 'csv_import'
            ORDER BY name
        """)
        return [dict(row) for row in cursor.fetchall()]


# ============================================================================
# Monthly Reminder System
# ============================================================================

def get_reminder_settings() -> Dict[str, Any]:
    """Get current reminder settings."""
    from db import get_user_setting

    enabled = get_user_setting('csv_reminder_enabled', 'true') == 'true'
    day = int(get_user_setting('csv_reminder_day', '28'))
    last_reminder = get_user_setting('csv_reminder_last_sent', '')

    return {
        'enabled': enabled,
        'day_of_month': day,
        'last_reminder_sent': last_reminder,
    }


def set_reminder_settings(enabled: bool = None, day_of_month: int = None) -> None:
    """Update reminder settings."""
    from db import set_user_setting

    if enabled is not None:
        set_user_setting('csv_reminder_enabled', 'true' if enabled else 'false')

    if day_of_month is not None:
        # Clamp to valid range
        day = max(1, min(28, day_of_month))
        set_user_setting('csv_reminder_day', str(day))


def mark_reminder_sent() -> None:
    """Mark that the monthly reminder was sent."""
    from db import set_user_setting
    set_user_setting('csv_reminder_last_sent', date.today().isoformat())


def should_send_reminder() -> Tuple[bool, str]:
    """
    Check if we should send a monthly CSV import reminder.

    Returns:
        Tuple of (should_send, reason_message)
    """
    settings = get_reminder_settings()

    if not settings['enabled']:
        return False, "Reminders are disabled"

    today = date.today()

    # Check if it's the right day
    if today.day < settings['day_of_month']:
        return False, f"Not reminder day yet (day {settings['day_of_month']})"

    # Check if already sent this month
    last_sent = settings['last_reminder_sent']
    if last_sent:
        try:
            last_date = date.fromisoformat(last_sent)
            if last_date.year == today.year and last_date.month == today.month:
                return False, "Already sent reminder this month"
        except ValueError:
            pass

    # Check if there are accounts to remind about
    accounts = list_csv_accounts()
    if not accounts:
        return False, "No CSV accounts configured"

    return True, f"Time for monthly import reminder ({len(accounts)} accounts)"


def get_reminder_message() -> str:
    """Generate the monthly reminder message."""
    accounts = list_csv_accounts()

    if not accounts:
        return ""

    today = date.today()
    month_name = today.strftime('%B %Y')

    lines = [
        f"📅 **Monthly Finance Import Reminder - {month_name}**",
        "",
        "It's time to download and import your bank statements!",
        "",
        "**Your accounts:**",
    ]

    for acc in accounts:
        latest = acc.get('latest_transaction', 'Never')
        lines.append(f"  • {acc['name']} - Last transaction: {latest}")

    lines.extend([
        "",
        "**To import:**",
        "1. Download CSV from your bank's online portal",
        "2. Share the CSV file with me",
        "3. I'll import and categorize your transactions",
        "",
        "💡 Tip: Most banks let you export 1-3 months of transactions at once.",
    ])

    return '\n'.join(lines)

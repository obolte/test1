#!/usr/bin/env python3
"""
Web Scraper für de.enfplastic.com
Extrahiert Firmendetails aus allen Ländern und erstellt eine übersichtliche Tabelle
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import csv
from urllib.parse import urljoin, urlparse
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import json

class EnfplasticScraper:
    def __init__(self):
        self.base_url = "https://de.enfplastic.com/"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.companies_data = []
        
        # Setup Selenium WebDriver
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
        except Exception as e:
            print(f"Chrome WebDriver konnte nicht initialisiert werden: {e}")
            print("Fallback auf requests-basierte Lösung...")
            self.driver = None

    def get_page_content(self, url):
        """Holt den Inhalt einer Seite mit Selenium oder requests"""
        try:
            if self.driver:
                self.driver.get(url)
                time.sleep(2)
                return self.driver.page_source
            else:
                response = self.session.get(url, timeout=10)
                response.raise_for_status()
                return response.text
        except Exception as e:
            print(f"Fehler beim Laden von {url}: {e}")
            return None

    def extract_countries_and_links(self):
        """Extrahiert alle Länder und deren Links von der Hauptseite"""
        print("Lade Hauptseite und extrahiere Länder...")
        
        content = self.get_page_content(self.base_url)
        if not content:
            return []
            
        soup = BeautifulSoup(content, 'html.parser')
        
        countries = []
        
        # Verschiedene Selektoren ausprobieren um Länder zu finden
        possible_selectors = [
            'a[href*="country"]',
            'a[href*="land"]', 
            'a[href*="/de/"]',
            '.country-link',
            '.country',
            '[data-country]',
            'li a',
            'nav a',
            '.menu a'
        ]
        
        for selector in possible_selectors:
            elements = soup.select(selector)
            for element in elements:
                href = element.get('href')
                text = element.get_text(strip=True)
                
                if href and text and len(text) > 1:
                    # Prüfe ob es sich um einen Länder-Link handeln könnte
                    if any(keyword in text.lower() for keyword in ['land', 'country', 'deutsch', 'german', 'frankreich', 'france', 'italien', 'italy', 'spanien', 'spain']):
                        full_url = urljoin(self.base_url, href)
                        countries.append({
                            'name': text,
                            'url': full_url
                        })
        
        # Entferne Duplikate
        seen_urls = set()
        unique_countries = []
        for country in countries:
            if country['url'] not in seen_urls:
                seen_urls.add(country['url'])
                unique_countries.append(country)
        
        print(f"Gefundene Länder: {len(unique_countries)}")
        for country in unique_countries:
            print(f"  - {country['name']}: {country['url']}")
            
        return unique_countries

    def extract_companies_from_country(self, country_url, country_name):
        """Extrahiert alle Firmen aus einem bestimmten Land"""
        print(f"\nAnalysiere Land: {country_name}")
        
        content = self.get_page_content(country_url)
        if not content:
            return []
            
        soup = BeautifulSoup(content, 'html.parser')
        companies = []
        
        # Verschiedene Selektoren für Firmen-Links
        company_selectors = [
            'a[href*="company"]',
            'a[href*="firma"]',
            'a[href*="unternehmen"]',
            '.company-link',
            '.company',
            '.firm',
            'li a',
            'div.content a',
            '.listing a'
        ]
        
        for selector in company_selectors:
            elements = soup.select(selector)
            for element in elements:
                href = element.get('href')
                text = element.get_text(strip=True)
                
                if href and text and len(text) > 2:
                    full_url = urljoin(country_url, href)
                    companies.append({
                        'name': text,
                        'url': full_url,
                        'country': country_name
                    })
        
        # Entferne Duplikate
        seen_urls = set()
        unique_companies = []
        for company in companies:
            if company['url'] not in seen_urls:
                seen_urls.add(company['url'])
                unique_companies.append(company)
        
        print(f"  Gefundene Firmen: {len(unique_companies)}")
        return unique_companies

    def extract_email_from_text(self, text):
        """Extrahiert E-Mail-Adressen aus Text"""
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, text)
        return emails[0] if emails else ""

    def extract_phone_from_text(self, text):
        """Extrahiert Telefonnummern aus Text"""
        phone_patterns = [
            r'\+?\d{1,4}[\s-]?\(?\d{1,4}\)?[\s-]?\d{1,4}[\s-]?\d{1,4}[\s-]?\d{1,9}',
            r'\(\d+\)\s*\d+[\s-]?\d+',
            r'\d+[\s-]\d+[\s-]\d+'
        ]
        
        for pattern in phone_patterns:
            phones = re.findall(pattern, text)
            if phones:
                return phones[0]
        return ""

    def extract_website_from_text(self, text):
        """Extrahiert Website-URLs aus Text"""
        url_pattern = r'https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:[\w.])*)?)?'
        urls = re.findall(url_pattern, text)
        return urls[0] if urls else ""

    def extract_company_details(self, company_url, company_name, country_name):
        """Extrahiert detaillierte Informationen über eine Firma"""
        print(f"    Extrahiere Details für: {company_name}")
        
        content = self.get_page_content(company_url)
        if not content:
            return None
            
        soup = BeautifulSoup(content, 'html.parser')
        
        # Extrahiere den gesamten sichtbaren Text
        text = soup.get_text()
        
        # Firmendetails extrahieren
        company_details = {
            'Firmenname': company_name,
            'Land': country_name,
            'URL': company_url,
            'E-Mail': self.extract_email_from_text(text),
            'Telefon': self.extract_phone_from_text(text),
            'Website': '',
            'Adresse': '',
            'Beschreibung': '',
            'Kontaktperson': '',
            'Fax': '',
            'Weitere_Informationen': ''
        }
        
        # Spezifische Selektoren für verschiedene Felder
        selectors = {
            'E-Mail': ['[href^="mailto:"]', '.email', '.mail', '#email'],
            'Telefon': ['.phone', '.tel', '#phone', '.telefon'],
            'Website': ['[href^="http"]', '.website', '.homepage', '.web'],
            'Adresse': ['.address', '.adresse', '.location', '.standort'],
            'Kontaktperson': ['.contact-person', '.ansprechpartner', '.kontakt'],
            'Fax': ['.fax', '#fax']
        }
        
        for field, field_selectors in selectors.items():
            for selector in field_selectors:
                elements = soup.select(selector)
                for element in elements:
                    if field == 'E-Mail' and element.get('href'):
                        email = element.get('href').replace('mailto:', '')
                        if '@' in email and not company_details['E-Mail']:
                            company_details['E-Mail'] = email
                    elif field == 'Website' and element.get('href'):
                        href = element.get('href')
                        if href.startswith('http') and href != company_url:
                            company_details['Website'] = href
                    else:
                        text_content = element.get_text(strip=True)
                        if text_content and not company_details[field]:
                            company_details[field] = text_content[:200]  # Limitiere Länge
        
        # Fallback: Wenn keine spezifischen E-Mails gefunden wurden, nutze Regex
        if not company_details['E-Mail']:
            company_details['E-Mail'] = self.extract_email_from_text(text)
        
        # Fallback für Telefon
        if not company_details['Telefon']:
            company_details['Telefon'] = self.extract_phone_from_text(text)
        
        # Beschreibung aus ersten Absätzen extrahieren
        paragraphs = soup.find_all('p')
        if paragraphs:
            description_parts = []
            for p in paragraphs[:3]:  # Erste 3 Absätze
                p_text = p.get_text(strip=True)
                if len(p_text) > 20:
                    description_parts.append(p_text)
            company_details['Beschreibung'] = ' '.join(description_parts)[:500]
        
        return company_details

    def scrape_all_companies(self):
        """Hauptmethode zum Scrapen aller Firmen"""
        print("Starte Web-Scraping von de.enfplastic.com...")
        
        # Schritt 1: Länder extrahieren
        countries = self.extract_countries_and_links()
        
        if not countries:
            print("Keine Länder gefunden. Prüfe Website-Struktur...")
            # Fallback: Analysiere die Hauptseite direkt nach Firmen
            self.analyze_main_page_structure()
            return
        
        # Schritt 2: Für jedes Land die Firmen extrahieren
        for country in countries:
            companies = self.extract_companies_from_country(country['url'], country['name'])
            
            # Schritt 3: Für jede Firma die Details extrahieren
            for company in companies:
                details = self.extract_company_details(company['url'], company['name'], company['country'])
                if details:
                    self.companies_data.append(details)
                    
                # Pause zwischen Requests
                time.sleep(1)
        
        print(f"\nInsgesamt {len(self.companies_data)} Firmen gefunden.")

    def analyze_main_page_structure(self):
        """Analysiert die Struktur der Hauptseite wenn keine Länder-Struktur gefunden wird"""
        print("Analysiere Hauptseite direkt...")
        
        content = self.get_page_content(self.base_url)
        if not content:
            print("Hauptseite konnte nicht geladen werden.")
            return
            
        soup = BeautifulSoup(content, 'html.parser')
        
        print("Gefundene Links auf der Hauptseite:")
        links = soup.find_all('a', href=True)
        for i, link in enumerate(links[:20]):  # Erste 20 Links
            print(f"  {i+1}. {link.get_text(strip=True)} -> {link['href']}")
        
        print(f"\nGesamte Seitenstruktur analysiert. {len(links)} Links gefunden.")

    def save_to_csv(self, filename="enfplastic_firmen.csv"):
        """Speichert die gesammelten Daten in eine CSV-Datei"""
        if not self.companies_data:
            print("Keine Daten zum Speichern vorhanden.")
            return
            
        df = pd.DataFrame(self.companies_data)
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"Daten gespeichert in: {filename}")

    def save_to_markdown(self, filename="enfplastic_firmen_tabelle.md"):
        """Speichert die Daten als schöne Markdown-Tabelle"""
        if not self.companies_data:
            print("Keine Daten zum Speichern vorhanden.")
            return
            
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("# Firmenverzeichnis von de.enfplastic.com\n\n")
            f.write(f"*Extrahiert am: {time.strftime('%Y-%m-%d %H:%M:%S')}*\n\n")
            f.write(f"**Anzahl Firmen:** {len(self.companies_data)}\n\n")
            
            if self.companies_data:
                # Erstelle Markdown-Tabelle
                df = pd.DataFrame(self.companies_data)
                f.write(df.to_markdown(index=False))
                f.write("\n\n")
                
                # Zusätzliche Statistiken
                f.write("## Statistiken\n\n")
                countries = df['Land'].value_counts()
                f.write("### Firmen pro Land:\n")
                for country, count in countries.items():
                    f.write(f"- {country}: {count} Firmen\n")
                
                # Firmen mit E-Mail
                email_count = df['E-Mail'].apply(lambda x: bool(x and '@' in str(x))).sum()
                f.write(f"\n### Kontaktdaten:\n")
                f.write(f"- Firmen mit E-Mail: {email_count}\n")
                f.write(f"- Firmen mit Telefon: {df['Telefon'].apply(lambda x: bool(str(x).strip())).sum()}\n")
                f.write(f"- Firmen mit Website: {df['Website'].apply(lambda x: bool(str(x).strip())).sum()}\n")
        
        print(f"Markdown-Tabelle gespeichert in: {filename}")

    def cleanup(self):
        """Aufräumen und Browser schließen"""
        if self.driver:
            self.driver.quit()

def main():
    scraper = EnfplasticScraper()
    
    try:
        scraper.scrape_all_companies()
        scraper.save_to_csv()
        scraper.save_to_markdown()
        
    except Exception as e:
        print(f"Fehler beim Scraping: {e}")
    finally:
        scraper.cleanup()

if __name__ == "__main__":
    main()
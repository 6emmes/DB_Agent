# Raport: Agent WIG20

## Streszczenie

Projekt realizuje automatyczny system do pobierania, przechowywania i analizy danych giełdowych z indeksu WIG20. System integruje web scraping, bazę danych MySQL i model sztucznej inteligencji (Ollama) do przetwarzania zapytań w języku naturalnym.

---

## 1. Cel i Zakres

Projekt ma na celu stworzenie narzędzia do:
- Automatycznego pobierania cen akcji WIG20 z portalu Bankier.pl
- Przechowywania danych historycznych w bazie MySQL
- Udostępniania informacji poprzez API REST
- Odpowiadania na pytania użytkowników za pomocą AI

---

## 2. Architektura Systemu

System składa się z czterech głównych komponentów:

```
Web Scraper → Database Updater → MySQL Database
                                      ↓
                    ┌──────────────┬──────────────┬──────────────┐
                    ↓              ↓              ↓              ↓
                FastAPI          MCP Server    Ollama AI      Client
```

### 2.1 Komponenty

**Web Scraper (scraper.py)**
- Pobiera dane z https://www.bankier.pl/inwestowanie/profile/quote.html?symbol=WIG20
- Używa BeautifulSoup do parsowania HTML
- Ekstrahuje symbole, ceny i kapitalizację rynkową
- Timeout: 10 sekund, obsługa błędów

**Database Layer (db_updater.py)**
- MySQL 8.0 z dwoma tabelami:
  - `Symbols` - lista spółek i ich kapitalizacja
  - `Prices` - ceny z czasami aktualizacji
- Unikatowe indeksy zapobiegają duplikatom
- UPSERT operations dla idempotentnych operacji

**FastAPI Service (main.py)**
- Endpoint `POST /ask` do wysyłania zapytań
- Klasyfikacja intencji (porównanie, analiza, przegląd rynku)
- Pobranie danych z bazy i wysłanie do Ollamy
- Obsługa polskich i angielskich zapytań

**MCP Server (mcp_server.py)**
- Zasoby (resources): stock://wig20/all, stock://wig20/prices
- Narzędzia (tools): set_price_alert
- Transport SSE dla aktualizacji w czasie rzeczywistym

---

## 3. Stack Techniczny

| Komponent | Technologia | Cel |
|-----------|-------------|-----|
| Runtime | Python 3.11 | Główny język |
| Framework | FastAPI + Uvicorn | API REST |
| Baza danych | MySQL 8.0 | Przechowywanie |
| Scraping | BeautifulSoup4 | Parsing HTML |
| AI/LLM | Ollama + Qwen2.5 | Przetwarzanie tekstu |
| Konteneryzacja | Docker Compose | Deployment |

---

## 4. Architektura Deployment

**Dockerfile**: Python 3.11-slim + zależności
**Docker Compose**: 4 serwisy

```yaml
Services:
  - db: MySQL 8.0 (port: domyślny)
  - ollama: LLM inference (port 11434)
  - api: FastAPI (port 8000)
  - mcp: MCP Server
```

**Dependency ordering**:
- API i MCP czekają na gotowość DB (health check)
- Zmienne środowiskowe w `.env`

---

## 5. Przepływ Danych

1. **Pobieranie**: Scraper uruchamia się okresowo, pobiera dane z Bankier.pl
2. **Zapis**: db_updater zapisuje do MySQL z deduplicacją
3. **Zapytanie**: Użytkownik wysyła POST na /ask
4. **Klasyfikacja**: System określa typ zapytania (porównanie/analiza/przegląd)
5. **Pobranie**: Zapytanie SQL do bazy
6. **AI**: Prompt z danymi do Ollamy (Qwen2.5)
7. **Odpowiedź**: Zwrócenie wyniku użytkownikowi

---

## 6. Klucze Funkcjonalności

✓ **Multi-language**: Obsługa polskiego i angielskiego  
✓ **Smart Intent**: Klasyfikacja zapytań (porównanie, analiza, rynek)  
✓ **Data Integrity**: UNIQUE constraints, FOREIGN KEYS  
✓ **Error Handling**: Timeouty, fallback responses  
✓ **Scalability**: Architektura microservices  
✓ **AI Integration**: Prompt engineering redukujący halucynacje  

---

## 7. Wyzwania i Rozwiązania

| Wyzwanie | Rozwiązanie |
|----------|------------|
| Anti-bot blokada | User-Agent spoofing, timeout |
| AI halucynacje | Strict prompt z kontekstem |
| Duplikaty cen | UNIQUE constraints, UPSERT |
| Koordynacja serwisów | Health checks, dependency ordering |

---

## 8. Obecny Stan i Testy

**Działające komponenty**:
- ✓ Web scraper z obsługą błędów
- ✓ MySQL z poprawnym schema
- ✓ FastAPI endpoints
- ✓ MCP protocol
- ✓ Docker containerization

**Rekomendowane testy**:
- Unit testy: scraper, db_updater, symbol extraction
- Integration: end-to-end query
- Load: 100+ concurrent requests

---

## 9. Ograniczenia i Rozwój

### Ograniczenia
1. Jedno źródło danych (Bankier.pl) → dodać fallback
2. Prosta klasyfikacja intencji → transformer-based NLP
3. Brak analizy historycznej → dodać time-series
4. Brak autentykacji → JWT tokens

### Zaplanowane Ulepszenia
| Ulepszenie | Priorytet | Wysiłek |
|-----------|-----------|---------|
| Multi-source agregacja | Wysoki | Średni |
| Advanced NLP | Wysoki | Średni |
| Time-series tools | Średni | Wysoki |
| Authentication | Wysoki | Niski |
| Rate limiting | Średni | Niski |

---

## 10. Podsumowanie

System WIG20 Stock Agent to funkcjonalna implementacja nowoczesnego pipeline'u danych łączącego:
- Web scraping
- Persystencję danych
- API REST
- Sztuczną inteligencję

**Osiągnięcia**:
✓ Automatyczne pobieranie cen z obsługą błędów  
✓ Baza danych z integralnością referencyjną  
✓ API z klasyfikacją intencji  
✓ LLM z kontrolą halucynacji  
✓ Deployment containeryzowany  

**Następne kroki**:
1. Comprehensive test suite
2. Monitoring i observability
3. Wielokrotne źródła danych
4. Advanced intent classification
5. CI/CD pipeline

---


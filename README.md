# KSeF Link

`ksef-link` to CLI i pakiet Python do pracy z KSeF:

- uwierzytelnianie tokenem KSeF
- odświeżanie `accessToken`
- pobieranie metadanych faktur
- pobieranie pełnych XML faktur po `ksefNumber`

Projekt jest ułożony jako pakiet `src/`, uruchamiany przez `uv`, z walidacją przez `pytest`, `ruff` i `mypy --strict`.

## Struktura projektu

Projekt używa architektury heksagonalnej (ports & adapters) z podziałem na warstwy:

```text
src/ksef_link/
  __init__.py
  __main__.py
  bootstrap.py
  main.py
  adapters/          # Implementacje zewnętrznych interfejsów
    cli/
      parser.py
    filesystem/
      invoice_storage.py
    ksef_api/
      auth_gateway.py
      auth_support.py
      http_client.py
      invoice_gateway.py
      models.py
      pagination.py
  application/       # Logika aplikacji i przypadki użycia
    auth_handlers.py
    commands.py
    context.py
    dispatcher.py
    invoice_handlers.py
    invoice_serializers.py
  domain/            # Model domenowy
    auth.py
    invoices.py
  ports/             # Interfejsy (abstrakcje)
    auth.py
    invoices.py
    storage.py
  shared/            # Wspólne komponenty
    errors.py
    logging.py
    settings.py

tests/               # Testy jednostkowe i integracyjne
  ...
```

## Setup

```bash
uv python install 3.14
uv sync --extra dev
cp .env.example .env
```

## `.env`

Przykładowe zmienne:

```dotenv
KSEF_TOKEN="your-ksef-token-here"
KSEF_ACCESS_TOKEN="your-access-token-here"
KSEF_REFRESH_TOKEN="your-refresh-token-here"
KSEF_CONTEXT_TYPE="Nip"
KSEF_CONTEXT_VALUE="5265877635"
KSEF_DEBUG="false"
```

## Uruchamianie

Help:

```bash
UV_CACHE_DIR=.uv-cache uv run ksef-link --help
```

Uwierzytelnienie tokenem KSeF:

```bash
UV_CACHE_DIR=.uv-cache uv run ksef-link authenticate \
  --context-type Nip \
  --context-value 5265877635
```

Odświeżenie access tokena:

```bash
UV_CACHE_DIR=.uv-cache uv run ksef-link refresh --refresh-token 'eyJ...'
```

Pobranie metadanych faktur zakupowych za bieżący miesiąc:

```bash
UV_CACHE_DIR=.uv-cache uv run ksef-link invoices
```

Pobranie XML znalezionych faktur do katalogu:

```bash
UV_CACHE_DIR=.uv-cache uv run ksef-link invoices --download-dir ./invoices
```

Włączenie debug logów HTTP:

```bash
UV_CACHE_DIR=.uv-cache uv run ksef-link --debug invoices
```

## Domyślne zachowanie `invoices`

Komenda `invoices`:

- domyślnie używa `subjectType=Subject2`, czyli faktur zakupowych
- domyślnie używa `dateType=PermanentStorage`
- domyślnie pobiera zakres od pierwszego dnia bieżącego miesiąca do chwili uruchomienia w strefie `Europe/Warsaw`
- bierze `accessToken` z CLI lub `KSEF_ACCESS_TOKEN`
- jeśli `accessToken` nie istnieje, próbuje `refreshToken` z CLI lub `KSEF_REFRESH_TOKEN`
- jeśli nie ma także `refreshToken`, wykonuje pełny flow uwierzytelnienia z `KSEF_TOKEN`

## Endpointy KSeF używane przez projekt

Uwierzytelnianie:

- `POST /auth/challenge`
- `GET /security/public-key-certificates`
- `POST /auth/ksef-token`
- `GET /auth/{referenceNumber}`
- `POST /auth/token/redeem`
- `POST /auth/token/refresh`

Faktury:

- `POST /invoices/query/metadata`
- `GET /invoices/ksef/{ksefNumber}`

Domyślny adres API:

- `https://api.ksef.mf.gov.pl/v2`

## Developer workflow

```bash
UV_CACHE_DIR=.uv-cache uv run pytest
UV_CACHE_DIR=.uv-cache uv run ruff check .
UV_CACHE_DIR=.uv-cache uv run mypy
```

## Uwagi

- Debug logi maskują `Authorization`, `accessToken`, `refreshToken`, `authenticationToken` i `encryptedToken`.
- Pobieranie metadanych wymaga uprawnienia `InvoiceRead` w bieżącym kontekście KSeF.
- Pełna treść faktury jest dostępna dopiero po `GET /invoices/ksef/{ksefNumber}`, nie w `query/metadata`.

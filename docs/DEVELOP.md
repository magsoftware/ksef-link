# DEVELOP

## Project Goal

`ksef-link` ma być prostym, technicznym klientem KSeF do:

1. uwierzytelniania,
2. pobierania faktur,
3. pobierania pełnych XML,
4. dalszej rozbudowy o wysyłkę i tworzenie faktur.

## Architecture

Projekt używa architektury heksagonalnej (ports & adapters) z podziałem na warstwy odpowiedzialności:

- `adapters/` - implementacje zewnętrznych interfejsów (CLI, filesystem, KSeF API)
- `application/` - logika aplikacji, przypadki użycia i orkiestracja
- `domain/` - model domenowy i reguły biznesowe
- `ports/` - abstrakcje i interfejsy
- `shared/` - wspólne komponenty (logging, settings, errors)
- `bootstrap.py` - inicjalizacja aplikacji i dependency injection
- `main.py` - punkt wejścia aplikacji

## Design Rules

- stosować uznane wzorce tylko wtedy, gdy upraszczają kod,
- trzymać cienkie warstwy i małe funkcje,
- nie mieszać CLI, HTTP i logiki domenowej w jednym module,
- nie logować danych wrażliwych.

## Quality Bar

Kod powinien przechodzić:

- `uv run pytest`
- `uv run ruff check .`
- `uv run mypy`

# Opta F7

## Format

Opta F7 is the standard XML feed format for football event data.

## Usage

```python
from kawkab.services.opta_importer import OptaF7Importer

importer = OptaF7Importer()

# Parse match info
match = importer.parse_match_xml(xml_string)

# Parse events
events = importer.parse_event_xml(xml_string)

# Parse lineups
lineups = importer.parse_lineup_xml(xml_string)
```

## Data Provider Interface

```python
importer.get_provider_name()  # "opta_f7"
importer.get_rate_limit_info()  # {"type": "local_file", ...}
```

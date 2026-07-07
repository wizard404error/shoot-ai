# Data Import

## StatsBomb

```python
from kawkab.services.statsbomb_service import get_shots

shots = await get_shots(match_id=3788741)
```

## Opta F7

```python
from kawkab.services.opta_importer import OptaF7Importer

importer = OptaF7Importer()
match = importer.parse_match_xml(xml_content)
events = importer.parse_event_xml(xml_content)
```

## CSV / JSON

```python
from kawkab.services.data_import_service import import_data

result = await import_data(file_path="data.csv", format="auto")
```

## Data Provider Base

```python
from kawkab.services.data_provider_base import DataProviderRegistry

registry = DataProviderRegistry()
registry.register(OptaF7Importer())
```

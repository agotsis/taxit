# State Fixtures

This directory contains YAML fixtures for all 50 US states with their tax residency day thresholds.

## Tax Residency Thresholds

The day thresholds are based on statutory residency rules for each state:

- **Most states**: 183 days (standard rule)
- **New York**: 184 days
- **New Mexico**: 185 days  
- **Hawaii**: 200 days
- **Idaho**: 270 days

## Loading States

To load all states into the database:

```bash
python manage.py load_states
```

### Options

- `--file <path>`: Specify a custom YAML file (default: `tracker/fixtures/states.yaml`)
- `--update`: Update existing states instead of skipping them

### Examples

```bash
# Load states (skip existing)
python manage.py load_states

# Update existing states with new data
python manage.py load_states --update

# Load from custom file
python manage.py load_states --file path/to/custom_states.yaml
```

## Natural Key

The State model implements Django's natural key system:

- **`StateManager.get_by_natural_key(abbreviation)`**: Looks up states by abbreviation
- **`State.natural_key()`**: Returns the abbreviation as a tuple for serialization

This allows Django's serialization framework to automatically handle state lookups by abbreviation instead of primary key. You can safely run the load command multiple times without creating duplicates.

The natural key system also enables:
- Loading fixtures with `python manage.py loaddata` using natural keys
- Exporting data with `python manage.py dumpdata --natural-foreign --natural-primary`
- Referencing states by abbreviation in fixtures instead of database IDs

## Active States

By default, all states are loaded with `is_active=false`. Users must activate the states they want to track through:

1. The frontend States management page at `/states/`
2. The Django admin interface

Only active states will appear in:
- Day entry forms
- Bulk edit forms
- State statistics and reports

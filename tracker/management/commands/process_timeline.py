import json
import yaml
from datetime import datetime, timedelta, timezone
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from tracker.models import State, Day, Office

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class Command(BaseCommand):
    help = "Process timeline segments and categorize days by state based on placeId matching"

    def add_arguments(self, parser):
        parser.add_argument(
            "file_path",
            type=str,
            help="Path to YAML or JSON file containing timeline segments",
        )
        parser.add_argument("place_id", type=str, help="PlaceId to match against timeline segments")
        parser.add_argument(
            "state_abbreviation",
            type=str,
            help="State abbreviation to categorize matching segments as",
        )
        parser.add_argument(
            "--office-name",
            type=str,
            help="Office name to associate with matching segments (optional)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be processed without actually saving to database",
        )

        parser.add_argument(
            "--no-input",
            action="store_true",
            help="Do not prompt for interactive input.",
        )

        parser.add_argument(
            "--days-of-week",
            type=str,
            help=(
                "Comma-separated list of days to include. "
                "Accepted: mon,tue,wed,thu,fri,sat,sun (case-insensitive). "
                "Example: --days-of-week mon,tue,wed,thu,fri"
            ),
        )

        parser.add_argument(
            "--timezone",
            type=str,
            default="America/Los_Angeles",
            help="IANA timezone name for date bucketing (e.g. America/Los_Angeles)."
            " DST-aware. (default: America/Los_Angeles)",
        )

    def handle(self, *args, **options):
        file_path = Path(options["file_path"])
        place_id = options["place_id"]
        state_abbreviation = options["state_abbreviation"]
        office_name = options.get("office_name")
        dry_run = options["dry_run"]
        tz_name = options["timezone"]
        no_input = options["no_input"]
        days_of_week = options.get("days_of_week")

        self.allowed_weekdays = self.parse_days_of_week(days_of_week)

        try:
            self.local_tz = ZoneInfo(tz_name)
        except ZoneInfoNotFoundError as e:
            raise CommandError(
                f"Unknown timezone '{tz_name}'. Use an IANA name like 'America/Los_Angeles'."
            ) from e

        # Validate file exists
        if not file_path.exists():
            raise CommandError(f"File not found: {file_path}")

        # Get or validate state
        try:
            state = State.objects.get(abbreviation__iexact=state_abbreviation)
        except State.DoesNotExist:
            raise CommandError(f"State with abbreviation '{state_abbreviation}' not found")

        # Get office if specified
        office = None
        if office_name:
            try:
                office = Office.objects.get(name__iexact=office_name)
            except Office.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(f"Office '{office_name}' not found. Creating new office.")
                )
                if not dry_run:
                    # For now, we'll skip creating offices without coordinates
                    self.stdout.write(
                        self.style.WARNING(
                            "Cannot create office without coordinates. Skipping office assignment."
                        )
                    )

        if office and place_id:
            self.maybe_update_office_place_id(
                office=office,
                place_id=place_id,
                dry_run=dry_run,
                no_input=no_input,
            )

        # Load timeline data
        try:
            timeline_data = self.load_timeline_data(file_path)
        except Exception as e:
            raise CommandError(f"Error loading timeline data: {e}")

        # Process segments
        matching_days = self.find_matching_segments(timeline_data, place_id)

        if not matching_days:
            self.stdout.write(
                self.style.WARNING("No matching segments found for the given placeId")
            )
            return

        self.stdout.write(f"Found {len(matching_days)} matching segments")

        if dry_run:
            self.stdout.write("\n--- DRY RUN - Would process the following days ---")
            for day_date in matching_days:
                self.stdout.write(f"  {day_date} - {state.name} - {office}")
            return

        # Save to database
        self.save_days_to_database(matching_days, state, office)

    def load_timeline_data(self, file_path):
        """Load timeline data from YAML or JSON file"""
        with open(file_path, "r", encoding="utf-8") as f:
            if file_path.suffix.lower() in [".yaml", ".yml"]:
                return yaml.safe_load(f)
            elif file_path.suffix.lower() == ".json":
                return json.load(f)
            else:
                raise CommandError("Unsupported file format. Use .yaml, .yml, or .json")

    def find_matching_segments(self, timeline_data, target_place_id):
        """Find all segments that contain the target placeId and extract dates"""
        matching_days = set()

        if isinstance(timeline_data, list):
            segments = timeline_data
        elif isinstance(timeline_data, dict):
            segments = timeline_data.get("semanticSegments", [])
        else:
            segments = []

        for segment in segments:
            # Check if this segment contains the target placeId
            if self.segment_contains_place_id(segment, target_place_id):
                # Extract dates from this segment
                dates = self.extract_dates_from_segment(segment)
                if self.allowed_weekdays is not None:
                    dates = [d for d in dates if d.weekday() in self.allowed_weekdays]
                matching_days.update(dates)

        return sorted(matching_days)

    def segment_contains_place_id(self, segment, target_place_id):
        """Check if a segment contains the target placeId"""
        # Check in visit data
        visit = segment.get("visit", {})
        top_candidate = visit.get("topCandidate", {})
        if top_candidate.get("placeId") == target_place_id:
            return True

        # Check in timelineMemory (destinations)
        timeline_memory = segment.get("timelineMemory", {})
        trip = timeline_memory.get("trip", {})
        destinations = trip.get("destinations", [])
        for destination in destinations:
            if destination.get("placeId") == target_place_id:
                return True

        return False

    def extract_dates_from_segment(self, segment):
        """Extract all dates covered by a segment"""
        start_time = segment.get("startTime")
        end_time = segment.get("endTime")

        if not start_time or not end_time:
            return []

        try:
            # Parse ISO datetime strings
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))

            # Normalize timezone (assume UTC if naive), then bucket by *local* date
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=timezone.utc)
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=timezone.utc)

            local_start = start_dt.astimezone(self.local_tz)
            local_end = end_dt.astimezone(self.local_tz)

            start_date = local_start.date()
            end_date = local_end.date()

            # Generate all dates in the range
            dates = []
            current_date = start_date
            while current_date <= end_date:
                dates.append(current_date)
                current_date = current_date + timedelta(days=1)

            return dates

        except Exception as e:
            self.stdout.write(self.style.WARNING(f"Error parsing dates for segment: {e}"))
            return []

    def parse_days_of_week(self, value):
        if value is None:
            return None

        day_map = {
            "mon": 0,
            "monday": 0,
            "tue": 1,
            "tues": 1,
            "tuesday": 1,
            "wed": 2,
            "wednesday": 2,
            "thu": 3,
            "thur": 3,
            "thurs": 3,
            "thursday": 3,
            "fri": 4,
            "friday": 4,
            "sat": 5,
            "saturday": 5,
            "sun": 6,
            "sunday": 6,
        }

        parts = [p.strip().lower() for p in value.split(",") if p.strip()]
        if not parts:
            raise CommandError("--days-of-week was provided but empty")

        unknown = [p for p in parts if p not in day_map]
        if unknown:
            raise CommandError(f"Unknown day(s) in --days-of-week: {', '.join(unknown)}")

        return {day_map[p] for p in parts}

    def maybe_update_office_place_id(self, office, place_id, dry_run, no_input):
        current = getattr(office, "place_id", None)
        if current == place_id:
            return

        if dry_run:
            if current:
                self.stdout.write(
                    self.style.WARNING(
                        f"DRY RUN: Would update Office '{office.name}' place_id "
                        f"from '{current}' to '{place_id}'"
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"DRY RUN: Would set Office '{office.name}' place_id to '{place_id}'"
                    )
                )
            return

        if no_input:
            return

        if current:
            prompt = (
                f"Office '{office.name}' already has place_id='{current}'. "
                f"Update to '{place_id}'? [y/N]: "
            )
        else:
            prompt = f"Set Office '{office.name}' place_id to '{place_id}'? [y/N]: "

        answer = input(prompt).strip().lower()
        if answer not in {"y", "yes"}:
            return

        office.place_id = place_id
        office.save(update_fields=["place_id"])
        self.stdout.write(
            self.style.SUCCESS(f"Updated Office '{office.name}' place_id -> '{place_id}'")
        )

    @transaction.atomic
    def save_days_to_database(self, dates, state, office):
        """Save days to database with the specified state"""
        created_count = 0
        updated_count = 0

        for date in dates:
            day, created = Day.objects.get_or_create(
                date=date,
                defaults={
                    "day_type": Day.DayType.STANDARD_WORKDAY,
                    "note": "Added via timeline processing for placeId match",
                },
            )

            if created:
                day.states.add(state)
                if office:
                    day.office = office
                    day.save()
                created_count += 1
                self.stdout.write(f"Created: {date} - {state.name}")
            else:
                # Update existing day
                day.states.add(state)
                if office and not day.office:
                    day.office = office
                    day.save()
                updated_count += 1
                self.stdout.write(f"Updated: {date} - {state.name}")

        self.stdout.write(
            self.style.SUCCESS(
                f"\nProcessing complete! Created: {created_count}, Updated: {updated_count}"
            )
        )

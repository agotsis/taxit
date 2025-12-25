from pathlib import Path
from django.core.management.base import BaseCommand
from django.core import serializers
from django.db import transaction
from tracker.models import State


class Command(BaseCommand):
    help = "Load US states from YAML fixtures using Django's natural key system"

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            default="tracker/fixtures/states.yaml",
            help="Path to YAML fixtures file (default: tracker/fixtures/states.yaml)",
        )
        parser.add_argument(
            "--update",
            action="store_true",
            help="Update existing states instead of skipping them",
        )

    def handle(self, *args, **options):
        file_path = Path(options["file"])
        update_existing = options["update"]

        if not file_path.exists():
            self.stderr.write(self.style.ERROR(f"File not found: {file_path}"))
            return

        created_count = 0
        updated_count = 0
        skipped_count = 0

        try:
            with open(file_path, "r") as f:
                with transaction.atomic():
                    for obj in serializers.deserialize("yaml", f, ignorenonexistent=True):
                        if obj.object.__class__.__name__ != "State":
                            continue

                        abbreviation = obj.object.abbreviation

                        try:
                            # Use natural key to look up existing state
                            existing_state = State.objects.get_by_natural_key(abbreviation)

                            if update_existing:
                                # Update existing state
                                existing_state.name = obj.object.name
                                existing_state.day_threshold = obj.object.day_threshold
                                existing_state.is_active = obj.object.is_active
                                existing_state.save()
                                updated_count += 1
                                self.stdout.write(
                                    self.style.SUCCESS(
                                        f"Updated: {existing_state.name} ({abbreviation})"
                                    )
                                )
                            else:
                                skipped_count += 1
                                self.stdout.write(
                                    self.style.WARNING(
                                        f"Skipped existing: {existing_state.name} ({abbreviation})"
                                    )
                                )
                        except State.DoesNotExist:
                            # Create new state
                            obj.save()
                            created_count += 1
                            self.stdout.write(
                                self.style.SUCCESS(f"Created: {obj.object.name} ({abbreviation})")
                            )

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error loading fixtures: {e}"))
            return

        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(self.style.SUCCESS(f"Created: {created_count}"))
        self.stdout.write(self.style.SUCCESS(f"Updated: {updated_count}"))
        self.stdout.write(self.style.WARNING(f"Skipped: {skipped_count}"))
        self.stdout.write("=" * 50)

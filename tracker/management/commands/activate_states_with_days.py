from django.core.management.base import BaseCommand
from tracker.models import State, Day


class Command(BaseCommand):
    help = "One-time command to activate states that have existing day records"

    def handle(self, *args, **options):
        self.stdout.write("=" * 60)
        self.stdout.write("Activating states that have existing day records...")
        self.stdout.write("=" * 60)

        # Get all states that have at least one day associated with them
        states_with_days = State.objects.filter(days__isnull=False).distinct()

        if not states_with_days.exists():
            self.stdout.write("\nNo states found with existing day records.")
            self.stdout.write("All states remain inactive.")
            return

        self.stdout.write(f"\nFound {states_with_days.count()} state(s) with existing days:\n")

        activated_count = 0
        already_active_count = 0

        for state in states_with_days:
            day_count = Day.objects.filter(states=state).count()

            if state.is_active:
                self.stdout.write(
                    f"  ✓ {state.name} ({state.abbreviation}) - {day_count} days - Already active"
                )
                already_active_count += 1
            else:
                state.is_active = True
                state.save()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✓ {state.name} ({state.abbreviation}) - {day_count} days - ACTIVATED"
                    )
                )
                activated_count += 1

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("Summary:")
        self.stdout.write(f"  - Newly activated: {activated_count}")
        self.stdout.write(f"  - Already active: {already_active_count}")
        self.stdout.write(f"  - Total states with days: {states_with_days.count()}")
        self.stdout.write("=" * 60)

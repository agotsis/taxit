from django.db import models


class State(models.Model):
    """A US state with tax residency day threshold."""

    name = models.CharField(max_length=100, unique=True)
    abbreviation = models.CharField(max_length=2, unique=True)
    day_threshold = models.PositiveIntegerField(
        help_text="Number of days before tax residency is triggered"
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.abbreviation})"


class Office(models.Model):
    """An office location with coordinates."""

    name = models.CharField(max_length=200)
    place_id = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        help_text="Google maps PlaceID, if available",
    )
    latitude = models.DecimalField(max_digits=17, decimal_places=14)
    longitude = models.DecimalField(max_digits=17, decimal_places=14)
    state = models.ForeignKey(
        State, on_delete=models.SET_NULL, null=True, blank=True, related_name="offices"
    )
    address = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Day(models.Model):
    """A single day record for tax tracking."""

    class DayType(models.TextChoices):
        STANDARD_WORKDAY = "WORK", "Standard Workday"
        PTO_WORKDAY = "PTO_WORK", "PTO Workday Mix"
        COMPANY_HOLIDAY = "HOLIDAY", "Company Holiday on which we worked"

    date = models.DateField(unique=True)
    day_type = models.CharField(
        max_length=10, choices=DayType.choices, default=DayType.STANDARD_WORKDAY
    )
    states = models.ManyToManyField(
        State, related_name="days", help_text="States this day counts toward"
    )
    office = models.ForeignKey(
        Office,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="days",
        help_text="Office worked from (if applicable)",
    )
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]
        verbose_name_plural = "Days"

    def __str__(self):
        states_str = ", ".join(s.abbreviation for s in self.states.all())
        return f"{self.date} - {self.get_day_type_display()} ({states_str})"


class RatioView(models.Model):
    """A saved date range view for analyzing state day ratios."""

    name = models.CharField(max_length=200)
    start_date = models.DateField()
    end_date = models.DateField()
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name}: {self.start_date} to {self.end_date}"

    @property
    def days_in_range(self):
        return (self.end_date - self.start_date).days + 1

    @property
    def workdays_in_range(self):
        """Return the count of actual workdays (days with state entries) in the date range."""
        return (
            Day.objects.filter(date__range=[self.start_date, self.end_date], states__isnull=False)
            .distinct()
            .count()
        )
